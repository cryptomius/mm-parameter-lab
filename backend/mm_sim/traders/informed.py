"""Informed traders: per D3, they observe `true_price(t + Δ) + noise`.

Each informed trader picks a fresh forward-looking horizon Δ ∈ [Δ_min, Δ_max]
and a noise term per arrival, then trades in the direction of the perceived
edge. They look like noise traders to the MM (same arrival distribution,
similar size distribution); only their *direction* is biased.

In v1 (Milestone 1) this file ships disabled — informed_count defaults to 0.
The full implementation lives here for Milestone 2 wiring; until then it's a
no-op as long as no informed CPs exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator

from numpy.random import Generator

from mm_sim.rng import RngFactory
from mm_sim.types import CounterpartyId, InformedTraderConfig, OrderEvent, Side


@dataclass
class InformedTraderState:
    cp: CounterpartyId
    next_arrival_t: float
    rng: Generator


# A "future price oracle": gives true_mid at time t (for a peek into the
# generator's future). Only the informed pool gets to call this; the MM does not.
FuturePriceFn = Callable[[float], float]


class InformedTraderPool:
    def __init__(
        self,
        cps: list[CounterpartyId],
        cfg: InformedTraderConfig,
        rng_factory: RngFactory,
        future_price_fn: FuturePriceFn | None,
        start_t: float = 0.0,
    ) -> None:
        self.cfg = cfg
        self.future = future_price_fn
        self.states: list[InformedTraderState] = []
        for cp in cps:
            child = rng_factory.child("informed", cp.id)
            first = start_t + child.exponential(1.0 / cfg.arrival_rate_hz) if cfg.arrival_rate_hz > 0 else float("inf")
            self.states.append(InformedTraderState(cp=cp, next_arrival_t=first, rng=child))
        self._order_seq = 0

    def _next_id(self, cp_id: str) -> str:
        self._order_seq += 1
        return f"{cp_id}#{self._order_seq}"

    def due_orders(self, now: float, mid: float) -> Iterator[OrderEvent]:
        if not self.states or self.future is None:
            return
        for st in self.states:
            while st.next_arrival_t <= now:
                t = st.next_arrival_t
                ev = self._build_order(st, t, mid)
                if ev is not None:
                    yield ev
                st.next_arrival_t = t + st.rng.exponential(1.0 / self.cfg.arrival_rate_hz)

    def _build_order(
        self, st: InformedTraderState, t: float, mid: float
    ) -> OrderEvent | None:
        if self.future is None:
            return None
        delta = st.rng.uniform(self.cfg.lookahead_min_s, self.cfg.lookahead_max_s)
        try:
            future_mid = self.future(t + delta)
        except Exception:
            return None
        # Signal = log return over the horizon; add multiplicative noise on the perceived edge
        edge = (future_mid - mid) + st.rng.normal(0.0, self.cfg.signal_noise_std * mid * 1e-3)
        if abs(edge) < 1e-9:
            return None
        side = Side.BID if edge > 0 else Side.ASK  # if I think price will rise, I want to BUY
        size = max(0.01, st.rng.normal(self.cfg.size_mean, 0.2))
        is_market = st.rng.random() < self.cfg.market_order_fraction
        if is_market:
            return OrderEvent(
                t=t, cp=st.cp, side=side, price=None, size=size, order_id=self._next_id(st.cp.id)
            )
        # Aggressive limit just inside the touch
        price_offset_bps = abs(st.rng.normal(0.0, 1.5))
        offset = mid * price_offset_bps * 1e-4
        price = mid - offset if side is Side.BID else mid + offset
        return OrderEvent(
            t=t, cp=st.cp, side=side, price=price, size=size, order_id=self._next_id(st.cp.id)
        )
