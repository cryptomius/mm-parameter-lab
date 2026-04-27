"""Noise traders: Poisson-arrival uninformed flow.

Each noise trader independently fires limit and market orders at a configured
rate. Limit prices land near the current mid with a configurable bps stddev
(simulating the broad scatter of uninformed liquidity). Market orders pick a
side uniformly. Cancel half-life governs exponential decay of resting orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

import numpy as np
from numpy.random import Generator

from mm_sim.rng import RngFactory
from mm_sim.types import CounterpartyId, NoiseTraderConfig, OrderEvent, Side


@dataclass
class NoiseTraderState:
    cp: CounterpartyId
    next_arrival_t: float
    rng: Generator
    open_order_ids: list[str] = field(default_factory=list)


class NoiseTraderPool:
    """Pool of noise traders. The engine pulls due orders for the current sim time."""

    def __init__(
        self,
        cps: list[CounterpartyId],
        cfg: NoiseTraderConfig,
        rng_factory: RngFactory,
        start_t: float = 0.0,
    ) -> None:
        self.cfg = cfg
        self.states: list[NoiseTraderState] = []
        for cp in cps:
            child = rng_factory.child("noise", cp.id)
            first = start_t + child.exponential(1.0 / cfg.arrival_rate_hz)
            self.states.append(
                NoiseTraderState(cp=cp, next_arrival_t=first, rng=child)
            )
        self._order_seq = 0
        self._cancel_rng = rng_factory.child("noise", "cancels")

    def _next_id(self, cp_id: str) -> str:
        self._order_seq += 1
        return f"{cp_id}#{self._order_seq}"

    def due_orders(self, now: float, mid: float) -> Iterator[OrderEvent]:
        """Yield all orders whose Poisson arrival has fired by `now`."""
        for st in self.states:
            while st.next_arrival_t <= now:
                t = st.next_arrival_t
                yield self._build_order(st, t, mid)
                st.next_arrival_t = t + st.rng.exponential(1.0 / self.cfg.arrival_rate_hz)

    def _build_order(self, st: NoiseTraderState, t: float, mid: float) -> OrderEvent:
        side = Side.BID if st.rng.random() < 0.5 else Side.ASK
        size = max(0.01, st.rng.normal(self.cfg.size_mean, self.cfg.size_std))
        is_limit = st.rng.random() < self.cfg.limit_fraction
        if is_limit:
            offset_bps = st.rng.normal(0.0, self.cfg.price_offset_std_bps)
            offset = mid * offset_bps * 1e-4
            # bid below mid, ask above mid (signed offset is folded into side)
            if side is Side.BID:
                price = mid - abs(offset)
            else:
                price = mid + abs(offset)
            oid = self._next_id(st.cp.id)
            st.open_order_ids.append(oid)
            return OrderEvent(t=t, cp=st.cp, side=side, price=price, size=size, order_id=oid)
        # Market order
        return OrderEvent(
            t=t, cp=st.cp, side=side, price=None, size=size, order_id=self._next_id(st.cp.id)
        )

    def sample_cancellations(self, now: float, dt: float) -> list[str]:
        """Probabilistic cancellations of any open orders this trader has placed.

        Each open order independently survives Δt with probability exp(-ln(2)/halflife * dt).
        Returns list of order_ids to cancel. The engine is responsible for the
        actual book.cancel() — we just decide which.
        """
        if self.cfg.cancel_halflife_s <= 0:
            return []
        survive = float(np.exp(-np.log(2.0) / self.cfg.cancel_halflife_s * dt))
        to_cancel: list[str] = []
        for st in self.states:
            keep: list[str] = []
            for oid in st.open_order_ids:
                if self._cancel_rng.random() < survive:
                    keep.append(oid)
                else:
                    to_cancel.append(oid)
            st.open_order_ids = keep
        return to_cancel

    def forget(self, order_id: str) -> None:
        """Stop tracking an order (e.g., after it filled and is gone from the book)."""
        for st in self.states:
            try:
                st.open_order_ids.remove(order_id)
                return
            except ValueError:
                continue
