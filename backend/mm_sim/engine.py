"""Discrete-time event loop driving the simulation.

Time advances in fixed `tick_dt` steps (default 100 ms). Each tick:
  1. Advance the price process by tick_dt.
  2. Pull due noise/informed orders that arrived in [t-tick_dt, t].
  3. Submit them to the matcher (in deterministic order: noise then informed).
  4. Probabilistic noise cancellations.
  5. Update the MM's vol estimate from the observed L2 mid.
  6. If quote refresh is due: compute AS quote, apply interventions, replace
     resting MM quotes via the matcher.
  7. Sample inventory/PnL; resolve adverse-selection horizons; tick metrics.
  8. Persist sampled state to results buffers (1Hz).

Determinism: same seed -> identical event ordering -> identical parquet output.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from mm_sim.logging_config import get_logger
from mm_sim.market.book import OrderBook
from mm_sim.market.matching import quote_replace, submit
from mm_sim.market.processes import PrecomputedPath, make_process
from mm_sim.metrics.adverse_selection import AdverseSelectionTracker
from mm_sim.metrics.inventory import InventoryStats
from mm_sim.metrics.per_counterparty import PerCounterpartyStats
from mm_sim.metrics.pnl import PnLState
from mm_sim.quoter.avellaneda_stoikov import AvellanedaStoikov, Quote
from mm_sim.quoter.interventions import (
    InterventionContext,
    adaptive_spread,
    hedge_signal,
    kill_switch,
    news_detector,
    per_counterparty_penalty,
    update_cp_toxicity_on_fill,
)
from mm_sim.quoter.vol_estimator import CheatVol, EWMAVol
from mm_sim.rng import RngFactory
from mm_sim.scenarios import library as scenarios_lib
from mm_sim.traders.counterparty import build_counterparties, mm_counterparty
from mm_sim.traders.informed import InformedTraderPool
from mm_sim.traders.noise import NoiseTraderPool
from mm_sim.types import (
    CounterpartyId,
    CounterpartyType,
    ExperimentConfig,
    FillEvent,
    OrderEvent,
    QuoteUpdate,
    Side,
)

log = get_logger("engine")


@dataclass
class TimeSeriesPoint:
    """Sampled at 1Hz to results.inventory.parquet."""

    t: float
    mid: float
    inventory: float
    cash: float
    realised_pnl: float
    unrealised_pnl: float
    total_pnl: float
    sigma_est: float


@dataclass
class QuoteRecord:
    t: float
    bid_price: float
    ask_price: float
    reservation_price: float
    half_spread: float
    inv_risk_term: float
    rent_term: float
    inventory: float
    sigma_est: float
    interventions_active: list[str]


@dataclass
class FillRecord:
    t: float
    side: Side
    price: float
    size: float
    mid_at_fill: float
    maker_cp_id: str
    taker_cp_id: str
    drift_1s: float | None = None
    drift_10s: float | None = None
    drift_60s: float | None = None


@dataclass
class EngineResult:
    fills: list[FillRecord]
    quotes: list[QuoteRecord]
    inventory_series: list[TimeSeriesPoint]
    summary: dict[str, float]


@dataclass
class _RateOverride:
    """Temporary multiplicative override of a Poisson rate."""

    multiplier: float
    expires_at: float


@dataclass
class _VolOverride:
    multiplier: float
    expires_at: float


@dataclass
class _PendingJump:
    log_jump: float


@dataclass
class _LatencyOverride:
    extra_ms: float
    expires_at: float


class Engine:
    """Discrete-time event loop. Single-instrument, single-MM."""

    def __init__(self, cfg: ExperimentConfig, rng_factory: RngFactory) -> None:
        self.cfg = cfg
        self.rng_factory = rng_factory
        self.sim_t: float = 0.0
        self.tick_dt: float = max(0.001, cfg.quoter.refresh_ms / 1000.0)
        self.quote_refresh_dt: float = cfg.quoter.refresh_ms / 1000.0

        # --- Market ---
        # Pre-generate the full price path so informed traders can peek into
        # the *actual* future, not a parallel ghost. Path is keyed by tick_dt.
        n_steps = int(round(cfg.duration_seconds / max(0.001, cfg.quoter.refresh_ms / 1000.0))) + 100
        base = make_process(cfg.market, rng_factory.child("market"))
        self.process = PrecomputedPath(base, dt=max(0.001, cfg.quoter.refresh_ms / 1000.0), n_steps=n_steps)
        self.book = OrderBook()

        # --- Traders ---
        noise_cps, informed_cps = build_counterparties(cfg.counterparties)
        self.noise_pool = NoiseTraderPool(
            cps=noise_cps, cfg=cfg.counterparties.noise, rng_factory=rng_factory
        )
        self.informed_pool = InformedTraderPool(
            cps=informed_cps,
            cfg=cfg.counterparties.informed,
            rng_factory=rng_factory,
            future_price_fn=self._future_price,
        )
        self.mm_cp = mm_counterparty()

        # --- Quoter & vol ---
        if cfg.quoter.sigma_estimator.type == "ewma":
            self.vol = EWMAVol(
                halflife_s=cfg.quoter.sigma_estimator.halflife_s,
                initial_sigma=cfg.market.sigma_true,
            )
        else:
            self.vol = CheatVol(true_sigma=cfg.market.sigma_true)
        self.quoter = AvellanedaStoikov(
            gamma=cfg.quoter.gamma,
            k=cfg.quoter.k,
            tau=cfg.quoter.tau,
            spread_min=cfg.quoter.spread_caps.min,
            spread_max=cfg.quoter.spread_caps.max,
            q_target=cfg.quoter.q_target,
            bid_widening_factor=cfg.quoter.bid_widening_factor,
            ask_widening_factor=cfg.quoter.ask_widening_factor,
        )
        self.intervention_ctx = InterventionContext(
            cfg=cfg.interventions,
            inventory_limit=cfg.quoter.inventory_limit,
            sigma_baseline=cfg.market.sigma_true,
        )

        # --- Metrics ---
        self.pnl = PnLState()
        self.inv_stats = InventoryStats(limit=cfg.quoter.inventory_limit)
        self.adv_sel = AdverseSelectionTracker()
        self.per_cp = PerCounterpartyStats()

        # --- Result buffers ---
        self.fill_records: list[FillRecord] = []
        self.quote_records: list[QuoteRecord] = []
        self.ts_points: list[TimeSeriesPoint] = []
        self._fill_index: dict[tuple[float, str], FillRecord] = {}

        # --- Bookkeeping ---
        self._next_quote_t: float = 0.0
        self._next_sample_t: float = 0.0
        self._next_external_id: int = 0
        self._noise_rate_override: _RateOverride | None = None
        self._informed_rate_override: _RateOverride | None = None
        self._vol_override: _VolOverride | None = None
        self._latency_override: _LatencyOverride | None = None
        self._pending_jump: _PendingJump | None = None
        self._scenario_idx: int = 0
        self._fees_taker_bps: float = 0.0  # M1: fees default to 0; wire later if needed
        self._maker_rebate_bps: float = 0.0
        self._quote_uptime_active_s: float = 0.0
        self._quotes_pulled: bool = False

    # --- ScenarioHandle protocol ---------------------------------------------

    def submit_external_order(self, order: OrderEvent) -> None:
        submit(self.book, order, self._on_fill, self._next_external_order_id)

    def adjust_noise_arrival_rate(self, multiplier: float, duration_s: float) -> None:
        self._noise_rate_override = _RateOverride(
            multiplier=multiplier, expires_at=self.sim_t + duration_s
        )

    def adjust_informed_concentration(self, multiplier: float, duration_s: float) -> None:
        self._informed_rate_override = _RateOverride(
            multiplier=multiplier, expires_at=self.sim_t + duration_s
        )

    def schedule_jump(self, log_jump: float) -> None:
        self._pending_jump = _PendingJump(log_jump=log_jump)

    def schedule_latency_spike(self, extra_ms: float, duration_s: float) -> None:
        self._latency_override = _LatencyOverride(
            extra_ms=extra_ms, expires_at=self.sim_t + duration_s
        )

    def schedule_vol_regime(self, sigma_multiplier: float, duration_s: float) -> None:
        # NOTE: with PrecomputedPath the path is fixed at construction; this
        # override only takes effect if the underlying process is mutable. For
        # newsspike / vol_regime scenarios the jump still applies via
        # schedule_jump, but the post-event vol multiplier is a no-op on
        # the precomputed path. We keep the bookkeeping field for tests.
        self._vol_override = _VolOverride(
            multiplier=sigma_multiplier, expires_at=self.sim_t + duration_s
        )

    # --- Helpers --------------------------------------------------------------

    def _next_external_order_id(self) -> str:
        self._next_external_id += 1
        return f"ext#{self._next_external_id}"

    def _future_price(self, future_t: float) -> float:
        """Look up the actual future mid from the pre-generated path."""
        return self.process.future_price(future_t)  # type: ignore[union-attr]

    def _on_fill(self, fill: FillEvent) -> None:
        is_mm_maker = fill.maker_cp.type is CounterpartyType.MM
        is_mm_taker = fill.taker_cp.type is CounterpartyType.MM
        # MM-maker fills update spread-PnL/inventory via PnLState (handles FIFO).
        self.pnl.on_fill(
            fill,
            is_mm_maker=is_mm_maker,
            maker_rebate_bps=self._maker_rebate_bps,
            taker_fee_bps=self._fees_taker_bps,
        )
        if is_mm_maker:
            self.adv_sel.on_mm_fill(fill)
            self.per_cp.on_fill(fill.taker_cp.id, fill.size)
        if is_mm_taker:
            # MM hit liquidity (e.g., hedge order). fill.side is the maker's side:
            #   maker BID = maker buys = MM sells -> inventory -size
            #   maker ASK = maker sells = MM buys -> inventory +size
            mm_signed = -fill.size if fill.side is Side.BID else fill.size
            self.pnl._update_fifo(mm_signed, fill.price)  # type: ignore[attr-defined]
            self.pnl.inventory += mm_signed
            self.pnl.cash -= mm_signed * fill.price
            self.pnl.fees_paid -= fill.size * fill.price * self._fees_taker_bps * 1e-4
            self.pnl.fills += 1

        # Record fill
        rec = FillRecord(
            t=fill.t,
            side=fill.side,
            price=fill.price,
            size=fill.size,
            mid_at_fill=fill.mid_at_fill,
            maker_cp_id=fill.maker_cp.id,
            taker_cp_id=fill.taker_cp.id,
        )
        self.fill_records.append(rec)
        self._fill_index[(fill.t, fill.maker_order_id)] = rec
        # Tell noise pool to forget filled order so cancel logic doesn't see it
        self.noise_pool.forget(fill.maker_order_id)

    # --- Main loop ------------------------------------------------------------

    def run(self) -> EngineResult:
        log.info(
            "engine.start",
            experiment=self.cfg.id,
            seed=self.cfg.seed,
            duration_s=self.cfg.duration_seconds,
            tick_dt=self.tick_dt,
        )
        # Seed the book with some baseline liquidity so the MM has a reference mid
        self._seed_initial_book()

        end_t = self.cfg.duration_seconds
        while self.sim_t < end_t:
            self.sim_t = round(self.sim_t + self.tick_dt, 9)
            # 1. Advance price; apply pending jump, vol overrides
            if self._pending_jump is not None:
                if isinstance(self.process, PrecomputedPath):
                    self.process.apply_jump(self._pending_jump.log_jump)
                self._pending_jump = None
            true_mid = self.process.step(self.tick_dt)
            self._maybe_revert_overrides()

            # 2. Apply scheduled scenario events
            self._fire_due_scenarios()

            # Effective book mid for trader/quoter logic
            book_mid = self.book.mid()
            ref_mid = book_mid if book_mid is not None else true_mid

            # 3. Pull noise + informed orders (multipliers applied to arrival rate)
            self._dispatch_due_orders(ref_mid)

            # 4. Probabilistic noise cancellations
            cancel_ids = self.noise_pool.sample_cancellations(self.sim_t, self.tick_dt)
            for oid in cancel_ids:
                self.book.cancel(oid)

            # 5. Update vol estimator from ref mid
            sigma_est = self.vol.update(ref_mid, self.sim_t)

            # 6. Quote refresh (with optional latency override)
            if self.sim_t >= self._next_quote_t:
                self._refresh_quotes(ref_mid, sigma_est)
                latency = self._latency_override.extra_ms if self._latency_override else 0.0
                self._next_quote_t = self.sim_t + self.quote_refresh_dt + latency / 1000.0

            # Hedge intervention: if signal != 0, send a market order from MM
            hedge_size = hedge_signal(self.intervention_ctx, self.pnl.inventory)
            if hedge_size != 0.0:
                hedge_side = Side.BID if hedge_size > 0 else Side.ASK
                submit(
                    self.book,
                    OrderEvent(
                        t=self.sim_t,
                        cp=self.mm_cp,
                        side=hedge_side,
                        price=None,
                        size=abs(hedge_size),
                        order_id=self._next_external_order_id(),
                    ),
                    self._on_fill,
                    self._next_external_order_id,
                )

            # 7. Mark + resolve adverse selection horizons
            self.pnl.mark(ref_mid)
            resolved = self.adv_sel.update(self.sim_t, ref_mid)
            for fill_ev, horizon, drift in resolved:
                key = (fill_ev.t, fill_ev.maker_order_id)
                rec = self._fill_index.get(key)
                if rec is None:
                    continue
                if horizon == 1.0:
                    rec.drift_1s = drift
                elif horizon == 10.0:
                    rec.drift_10s = drift
                    self.per_cp.on_drift_resolved(fill_ev.taker_cp.id, drift)
                    update_cp_toxicity_on_fill(
                        self.intervention_ctx, fill_ev, drift, decay_dt=self.tick_dt
                    )
                elif horizon == 60.0:
                    rec.drift_60s = drift

            self.inv_stats.update(self.sim_t, self.pnl.inventory)
            if not self._quotes_pulled:
                self._quote_uptime_active_s += self.tick_dt

            # 8. Sample 1Hz time series
            if self.sim_t >= self._next_sample_t:
                self.ts_points.append(
                    TimeSeriesPoint(
                        t=self.sim_t,
                        mid=ref_mid,
                        inventory=self.pnl.inventory,
                        cash=self.pnl.cash,
                        realised_pnl=self.pnl.realised_spread_pnl,
                        unrealised_pnl=self.pnl.unrealised_pnl,
                        total_pnl=self.pnl.total_pnl,
                        sigma_est=sigma_est,
                    )
                )
                self._next_sample_t += 1.0

        # Final summary
        summary = self._build_summary()
        log.info(
            "engine.done",
            experiment=self.cfg.id,
            fills=len(self.fill_records),
            total_pnl=summary["total_pnl"],
        )
        return EngineResult(
            fills=self.fill_records,
            quotes=self.quote_records,
            inventory_series=self.ts_points,
            summary=summary,
        )

    # --- Loop helpers ---------------------------------------------------------

    def _seed_initial_book(self) -> None:
        """Pre-populate the book with deep, wide resting liquidity.

        Levels are placed 100..1000 bps from mid so the MM almost always sits
        at the inside of the touch. The seed liquidity is a backstop for noise
        market orders before the MM has had time to quote, and ensures
        large takers always find an opposing level.
        """
        rng = self.rng_factory.child("initial_book")
        mid = self.cfg.market.initial_price
        cp_seed = CounterpartyId(id="seed_lp", type=CounterpartyType.NOISE)
        for i in range(1, 11):
            offset_bps = i * 100  # 100, 200, ..., 1000 bps
            offset = mid * offset_bps * 1e-4
            for side, price in (
                (Side.BID, mid - offset),
                (Side.ASK, mid + offset),
            ):
                submit(
                    self.book,
                    OrderEvent(
                        t=0.0,
                        cp=cp_seed,
                        side=side,
                        price=price,
                        size=float(rng.uniform(5.0, 15.0)),
                        order_id=f"seed#{side.value}#{i}",
                    ),
                    self._on_fill,
                    self._next_external_order_id,
                )

    def _maybe_revert_overrides(self) -> None:
        if self._noise_rate_override and self.sim_t >= self._noise_rate_override.expires_at:
            self._noise_rate_override = None
        if self._informed_rate_override and self.sim_t >= self._informed_rate_override.expires_at:
            self._informed_rate_override = None
        if self._latency_override and self.sim_t >= self._latency_override.expires_at:
            self._latency_override = None
        if self._vol_override and self.sim_t >= self._vol_override.expires_at:
            self._vol_override = None

    def _fire_due_scenarios(self) -> None:
        evs = self.cfg.events
        while self._scenario_idx < len(evs) and evs[self._scenario_idx].at_seconds <= self.sim_t:
            ev = evs[self._scenario_idx]
            scenarios_lib.apply(self, ev.kind, ev.params)
            log.info("scenario.fire", t=self.sim_t, kind=ev.kind.value, params=ev.params)
            self._scenario_idx += 1

    def _dispatch_due_orders(self, mid: float) -> None:
        # Noise (rate may be scaled down by liquidity withdrawal)
        for ev in self.noise_pool.due_orders(self.sim_t, mid):
            submit(self.book, ev, self._on_fill, self._next_external_order_id)
        # Informed
        for ev in self.informed_pool.due_orders(self.sim_t, mid):
            submit(self.book, ev, self._on_fill, self._next_external_order_id)

    def _refresh_quotes(self, mid: float, sigma_est: float) -> None:
        active: list[str] = []
        quote: Quote | None = self.quoter.quote(
            mid=mid, inventory=self.pnl.inventory, sigma=sigma_est
        )
        # Adaptive spread (widen on vol)
        if self.intervention_ctx.cfg.adaptive_spread:
            quote = adaptive_spread(quote, self.intervention_ctx, sigma_est)
            active.append("adaptive_spread")
        # Per-CP penalty (widen against toxic flow)
        if self.intervention_ctx.cfg.per_counterparty_penalty:
            quote = per_counterparty_penalty(quote, self.intervention_ctx, mid)
            active.append("per_counterparty_penalty")
        # Kill switch (pull on inventory limit)
        if self.intervention_ctx.cfg.kill_switch:
            q2 = kill_switch(quote, self.intervention_ctx, self.pnl.inventory)
            if q2 is None:
                self._pull_quotes()
                self._quotes_pulled = True
                self._record_quote_pulled(mid, sigma_est, ["kill_switch"])
                return
            quote = q2
            active.append("kill_switch")
        # News detector (pull on jump)
        if self.intervention_ctx.cfg.news_detector:
            q2 = news_detector(quote, self.intervention_ctx, mid, self.sim_t)
            if q2 is None:
                self._pull_quotes()
                self._quotes_pulled = True
                self._record_quote_pulled(mid, sigma_est, ["news_detector"])
                self.intervention_ctx.last_mid = mid
                return
            quote = q2
            active.append("news_detector")

        self.intervention_ctx.last_mid = mid
        # Asymmetric spread caps — applied AFTER the intervention pipeline so
        # they compose with adaptive_spread and per_cp_penalty widening.
        bid_factor = self.quoter.bid_widening_factor
        ask_factor = self.quoter.ask_widening_factor
        if bid_factor != 1.0 or ask_factor != 1.0:
            r = quote.reservation_price
            h = quote.half_spread
            quote = Quote(
                bid_price=r - h * bid_factor,
                ask_price=r + h * ask_factor,
                reservation_price=r,
                half_spread=h,
                inv_risk_term=quote.inv_risk_term,
                rent_term=quote.rent_term,
            )
        # Place fresh quotes
        quote_replace(
            self.book,
            self.mm_cp,
            bid_price=quote.bid_price,
            bid_size=self.cfg.quoter.quote_size,
            ask_price=quote.ask_price,
            ask_size=self.cfg.quoter.quote_size,
            t=self.sim_t,
            next_id=self._next_external_order_id,
            on_fill=self._on_fill,
        )
        self._quotes_pulled = False
        self.quote_records.append(
            QuoteRecord(
                t=self.sim_t,
                bid_price=quote.bid_price,
                ask_price=quote.ask_price,
                reservation_price=quote.reservation_price,
                half_spread=quote.half_spread,
                inv_risk_term=quote.inv_risk_term,
                rent_term=quote.rent_term,
                inventory=self.pnl.inventory,
                sigma_est=sigma_est,
                interventions_active=active,
            )
        )

    def _pull_quotes(self) -> None:
        self.book.cancel_all_for(self.mm_cp.id)

    def _record_quote_pulled(self, mid: float, sigma_est: float, why: list[str]) -> None:
        self.quote_records.append(
            QuoteRecord(
                t=self.sim_t,
                bid_price=float("nan"),
                ask_price=float("nan"),
                reservation_price=mid,
                half_spread=float("nan"),
                inv_risk_term=float("nan"),
                rent_term=float("nan"),
                inventory=self.pnl.inventory,
                sigma_est=sigma_est,
                interventions_active=why + ["pulled"],
            )
        )

    def _build_summary(self) -> dict[str, float]:
        total_t = self.cfg.duration_seconds
        mm_fills = [f for f in self.fill_records if f.maker_cp_id == self.mm_cp.id or f.taker_cp_id == self.mm_cp.id]
        mean_drift = lambda h: float(  # noqa: E731
            np.mean(
                [getattr(f, f"drift_{h}s") for f in mm_fills if getattr(f, f"drift_{h}s") is not None]
            )
            if any(getattr(f, f"drift_{h}s") is not None for f in mm_fills)
            else 0.0
        )
        return {
            "total_pnl": float(self.pnl.total_pnl),
            "spread_pnl": float(self.pnl.realised_spread_pnl),
            "inventory_pnl": float(self.pnl.unrealised_pnl),
            "fees_paid": float(self.pnl.fees_paid),
            "max_abs_inventory": float(self.inv_stats.max_abs_inventory),
            "time_at_limit_pct": float(self.inv_stats.time_at_limit_pct(total_t)),
            "quote_uptime_pct": float(100.0 * self._quote_uptime_active_s / max(total_t, 1e-9)),
            "fill_count": float(self.pnl.fills),
            "mean_drift_bps_1s": mean_drift(1),
            "mean_drift_bps_10s": mean_drift(10),
            "mean_drift_bps_60s": mean_drift(60),
        }
