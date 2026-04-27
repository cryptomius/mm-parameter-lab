"""L2 limit order book.

Price-time priority. Single-thread. Optimised for clarity, not throughput —
the engine runs at most a few hundred order events per simulated second so a
sorted-dict implementation is plenty.

The book stores resting limit orders. Crosses (taker against the book) are
handled by the matcher in matching.py; the book itself only knows how to
add, cancel, and pop liquidity.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Iterable

from sortedcontainers import SortedDict

from mm_sim.types import CounterpartyId, L2Level, L2Snapshot, Side


@dataclass
class RestingOrder:
    order_id: str
    cp: CounterpartyId
    side: Side
    price: float
    size: float
    t_placed: float


@dataclass
class _PriceLevel:
    price: float
    queue: deque[RestingOrder] = field(default_factory=deque)

    @property
    def total_size(self) -> float:
        return sum(o.size for o in self.queue)


class OrderBook:
    """L2 book with price-time priority."""

    def __init__(self) -> None:
        # bids: keyed by negative price for descending iteration
        self._bids: SortedDict[float, _PriceLevel] = SortedDict()
        self._asks: SortedDict[float, _PriceLevel] = SortedDict()
        self._index: dict[str, RestingOrder] = {}

    # --- mutation -------------------------------------------------------------

    def add(self, order: RestingOrder) -> None:
        if order.order_id in self._index:
            raise ValueError(f"duplicate order id: {order.order_id}")
        levels = self._bids if order.side is Side.BID else self._asks
        key = -order.price if order.side is Side.BID else order.price
        if key not in levels:
            levels[key] = _PriceLevel(price=order.price)
        levels[key].queue.append(order)
        self._index[order.order_id] = order

    def cancel(self, order_id: str) -> RestingOrder | None:
        order = self._index.pop(order_id, None)
        if order is None:
            return None
        levels = self._bids if order.side is Side.BID else self._asks
        key = -order.price if order.side is Side.BID else order.price
        level = levels.get(key)
        if level is None:
            return order
        try:
            level.queue.remove(order)
        except ValueError:
            return order
        if not level.queue:
            del levels[key]
        return order

    def reduce_front(self, side: Side, price: float, size: float) -> None:
        """Reduce size at front of the given level. Used by the matcher."""
        levels = self._bids if side is Side.BID else self._asks
        key = -price if side is Side.BID else price
        level = levels.get(key)
        if level is None or not level.queue:
            return
        front = level.queue[0]
        front.size -= size
        if front.size <= 1e-12:
            level.queue.popleft()
            self._index.pop(front.order_id, None)
            if not level.queue:
                del levels[key]

    def cancel_all_for(self, cp_id: str) -> int:
        """Cancel every resting order owned by cp_id. Returns count."""
        ids = [oid for oid, o in self._index.items() if o.cp.id == cp_id]
        for oid in ids:
            self.cancel(oid)
        return len(ids)

    # --- read access ----------------------------------------------------------

    def best_bid(self) -> RestingOrder | None:
        if not self._bids:
            return None
        _, level = self._bids.peekitem(0)
        return level.queue[0] if level.queue else None

    def best_ask(self) -> RestingOrder | None:
        if not self._asks:
            return None
        _, level = self._asks.peekitem(0)
        return level.queue[0] if level.queue else None

    def mid(self) -> float | None:
        bb, ba = self.best_bid(), self.best_ask()
        if bb is None or ba is None:
            return None
        return 0.5 * (bb.price + ba.price)

    def iter_bid_levels(self) -> Iterable[_PriceLevel]:
        for _, level in self._bids.items():
            yield level

    def iter_ask_levels(self) -> Iterable[_PriceLevel]:
        for _, level in self._asks.items():
            yield level

    def snapshot(self, t: float, depth: int = 20) -> L2Snapshot:
        bids: list[L2Level] = []
        for level in self.iter_bid_levels():
            bids.append(L2Level(price=level.price, size=level.total_size))
            if len(bids) >= depth:
                break
        asks: list[L2Level] = []
        for level in self.iter_ask_levels():
            asks.append(L2Level(price=level.price, size=level.total_size))
            if len(asks) >= depth:
                break
        m = self.mid()
        return L2Snapshot(t=t, bids=bids, asks=asks, mid=m if m is not None else 0.0)

    def get(self, order_id: str) -> RestingOrder | None:
        return self._index.get(order_id)

    def __len__(self) -> int:
        return len(self._index)
