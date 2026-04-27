"""Live session: a worker thread runs the engine and pushes state to subscribers.

Only one session at a time (M3 scope). The engine runs in a worker thread,
sleeping between sim ticks to roughly match wall-clock time so the UI shows
a watchable simulation. State snapshots, fills, and quote updates are pushed
to a per-subscriber asyncio Queue.

For higher throughput, subscribers can request a `speed` multiplier — `1.0`
means real-time, `0` means as-fast-as-possible.
"""

from __future__ import annotations

import asyncio
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from mm_sim.engine import Engine
from mm_sim.logging_config import get_logger
from mm_sim.market.matching import quote_replace, submit
from mm_sim.quoter.interventions import (
    adaptive_spread,
    hedge_signal,
    kill_switch,
    news_detector,
    per_counterparty_penalty,
    update_cp_toxicity_on_fill,
)
from mm_sim.rng import RngFactory
from mm_sim.scenarios import library as scenarios_lib
from mm_sim.types import (
    ExperimentConfig,
    InterventionConfig,
    OrderEvent,
    QuoterConfig,
    ScenarioEvent,
    Side,
    WsMessage,
)

log = get_logger("session")


@dataclass
class Session:
    cfg: ExperimentConfig
    engine: Engine | None = None
    speed: float = 5.0  # 1.0 = real-time, higher = faster
    running: bool = False
    paused: bool = False
    seq: int = 0
    subscribers: list[asyncio.Queue[WsMessage]] = field(default_factory=list)
    _thread: threading.Thread | None = None
    _loop: asyncio.AbstractEventLoop | None = None
    _stop: threading.Event = field(default_factory=threading.Event)

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        if self.running:
            return
        self.engine = Engine(self.cfg, RngFactory(seed=self.cfg.seed))
        self.engine._seed_initial_book()  # type: ignore[attr-defined]
        self._loop = loop
        self.running = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.running = False

    def pause(self, paused: bool) -> None:
        self.paused = paused

    def subscribe(self) -> asyncio.Queue[WsMessage]:
        q: asyncio.Queue[WsMessage] = asyncio.Queue(maxsize=1024)
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[WsMessage]) -> None:
        try:
            self.subscribers.remove(q)
        except ValueError:
            pass

    def update_quoter(self, patch: dict[str, Any]) -> None:
        if not self.engine:
            return
        # Only allow safe live tunables
        for field_name, value in patch.items():
            if field_name == "gamma":
                self.engine.quoter.gamma = float(value)
            elif field_name == "k":
                self.engine.quoter.k = float(value)
            elif field_name == "tau":
                self.engine.quoter.tau = float(value)
            elif field_name == "inventory_limit":
                self.engine.quoter.inventory_limit = float(value)
                self.engine.intervention_ctx.inventory_limit = float(value)

    def update_interventions(self, name: str, enabled: bool) -> None:
        if not self.engine:
            return
        cfg = self.engine.intervention_ctx.cfg
        if hasattr(cfg, name):
            setattr(cfg, name, enabled)

    def inject_event(self, ev: ScenarioEvent) -> None:
        if not self.engine:
            return
        # Apply immediately at current sim_t
        ev2 = ScenarioEvent(at_seconds=self.engine.sim_t, kind=ev.kind, params=ev.params)
        scenarios_lib.apply(self.engine, ev2.kind, ev2.params)
        self._publish(
            "scenario_event",
            {"t": self.engine.sim_t, "kind": ev2.kind.value, "params": ev2.params, "source": "user"},
        )

    # --- internal -------------------------------------------------------------

    def _run_loop(self) -> None:
        """Simulation worker. Streams fills, scenarios, quotes, and L2 snapshots over WS."""
        assert self.engine is not None
        engine = self.engine
        last_quote_emit = 0.0
        last_book_emit = 0.0
        last_scenario_idx = engine._scenario_idx
        last_fill_idx = len(engine.fill_records)
        last_quote_record_idx = len(engine.quote_records)
        mm_id = engine.mm_cp.id
        end_t = self.cfg.duration_seconds
        wall_dt = engine.tick_dt / max(self.speed, 1e-6) if self.speed > 0 else 0.0

        while not self._stop.is_set() and engine.sim_t < end_t:
            if self.paused:
                time.sleep(0.05)
                continue
            t0 = time.perf_counter()
            self._tick_engine(engine)
            while last_fill_idx < len(engine.fill_records):
                fr = engine.fill_records[last_fill_idx]
                # aggressor = opposite of maker side; if maker was BID, taker sold (sell aggressor).
                aggressor = "sell" if fr.side.value == "bid" else "buy"
                mm_involved = fr.maker_cp_id == mm_id or fr.taker_cp_id == mm_id
                self._publish(
                    "fill",
                    {
                        "t": fr.t,
                        "price": fr.price,
                        "size": fr.size,
                        "aggressor": aggressor,
                        "mid": fr.mid_at_fill,
                        "mm": mm_involved,
                    },
                )
                # MM-as-taker = hedge order (only place MM lifts liquidity)
                if fr.taker_cp_id == mm_id:
                    self._publish(
                        "intervention_event",
                        {
                            "t": fr.t,
                            "kind": "hedge_on_threshold",
                            "action": "hedge_fill",
                            "details": {
                                "side": "buy" if fr.side.value == "ask" else "sell",
                                "size": fr.size,
                                "price": fr.price,
                            },
                        },
                    )
                last_fill_idx += 1
            while last_quote_record_idx < len(engine.quote_records):
                qr = engine.quote_records[last_quote_record_idx]
                if "pulled" in qr.interventions_active:
                    reason = next(
                        (n for n in qr.interventions_active if n != "pulled"),
                        "unknown",
                    )
                    self._publish(
                        "intervention_event",
                        {
                            "t": qr.t,
                            "kind": reason,
                            "action": "quotes_pulled",
                            "details": {"inventory": qr.inventory, "sigma_est": qr.sigma_est},
                        },
                    )
                last_quote_record_idx += 1
            if engine._scenario_idx > last_scenario_idx:
                for ev in self.cfg.events[last_scenario_idx : engine._scenario_idx]:
                    self._publish(
                        "scenario_event",
                        {
                            "t": engine.sim_t,
                            "kind": ev.kind.value,
                            "params": ev.params,
                            "source": "scheduled",
                        },
                    )
                last_scenario_idx = engine._scenario_idx
            # Emit selectively — quotes after each refresh, book at ~5Hz
            if engine.sim_t - last_quote_emit >= 0.1:
                book_mid = engine.book.mid()
                ref_mid = book_mid if book_mid is not None else engine.process.price
                last_qr = engine.quote_records[-1] if engine.quote_records else None
                _f = lambda x: None if x is None or math.isnan(x) else x  # noqa: E731
                self._publish(
                    "quote_update",
                    {
                        "t": engine.sim_t,
                        "mid": ref_mid,
                        "fills_count": engine.pnl.fills,
                        "inventory": engine.pnl.inventory,
                        "total_pnl": engine.pnl.total_pnl,
                        "spread_pnl": engine.pnl.realised_spread_pnl,
                        "inventory_pnl": engine.pnl.unrealised_pnl,
                        "sigma_est": engine.vol.sigma,
                        "reservation_price": _f(last_qr.reservation_price if last_qr else None),
                        "half_spread": _f(last_qr.half_spread if last_qr else None),
                        "inv_risk_term": _f(last_qr.inv_risk_term if last_qr else None),
                        "rent_term": _f(last_qr.rent_term if last_qr else None),
                        "active_interventions": [
                            n
                            for n in (
                                "adaptive_spread",
                                "kill_switch",
                                "news_detector",
                                "hedge_on_threshold",
                                "per_counterparty_penalty",
                            )
                            if getattr(engine.intervention_ctx.cfg, n)
                        ],
                    },
                )
                last_quote_emit = engine.sim_t
            if engine.sim_t - last_book_emit >= 0.2:
                snap = engine.book.snapshot(engine.sim_t, depth=10)
                self._publish("snapshot", snap.model_dump())
                last_book_emit = engine.sim_t
            if wall_dt > 0:
                elapsed = time.perf_counter() - t0
                remaining = wall_dt - elapsed
                if remaining > 0:
                    time.sleep(remaining)
        self.running = False
        self._publish("log", {"level": "INFO", "msg": "session ended", "t": engine.sim_t})

    def _tick_engine(self, engine: Engine) -> None:
        """One tick of the engine — copy of Engine.run()'s body, condensed."""
        engine.sim_t = round(engine.sim_t + engine.tick_dt, 9)
        # advance price
        if engine._pending_jump is not None:
            if hasattr(engine.process, "_price"):
                import math

                engine.process._price *= math.exp(engine._pending_jump.log_jump)  # type: ignore[attr-defined]
            engine._pending_jump = None
        engine.process.step(engine.tick_dt)
        engine._maybe_revert_overrides()
        engine._fire_due_scenarios()
        ref_mid = engine.book.mid() or engine.process.price
        engine._dispatch_due_orders(ref_mid)
        cancel_ids = engine.noise_pool.sample_cancellations(engine.sim_t, engine.tick_dt)
        for oid in cancel_ids:
            engine.book.cancel(oid)
        sigma_est = engine.vol.update(ref_mid, engine.sim_t)
        if engine.sim_t >= engine._next_quote_t:
            engine._refresh_quotes(ref_mid, sigma_est)
            engine._next_quote_t = engine.sim_t + engine.quote_refresh_dt
        engine.pnl.mark(ref_mid)
        engine.adv_sel.update(engine.sim_t, ref_mid)
        engine.inv_stats.update(engine.sim_t, engine.pnl.inventory)

    def _publish(self, kind: str, payload: dict[str, Any]) -> None:
        if self._loop is None:
            return
        self.seq += 1
        msg = WsMessage(seq=self.seq, kind=kind, payload=payload)  # type: ignore[arg-type]
        for q in list(self.subscribers):
            try:
                self._loop.call_soon_threadsafe(q.put_nowait, msg)
            except asyncio.QueueFull:
                pass
