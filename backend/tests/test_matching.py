"""Match logic correctness."""

from __future__ import annotations

from mm_sim.market.book import OrderBook, RestingOrder
from mm_sim.market.matching import submit
from mm_sim.types import CounterpartyId, CounterpartyType, FillEvent, OrderEvent, Side


def cp(name: str) -> CounterpartyId:
    return CounterpartyId(id=name, type=CounterpartyType.NOISE)


def test_market_order_walks_book() -> None:
    book = OrderBook()
    book.add(RestingOrder("a1", cp("seller1"), Side.ASK, 100.0, 1.0, 0))
    book.add(RestingOrder("a2", cp("seller2"), Side.ASK, 101.0, 1.0, 0))
    fills: list[FillEvent] = []
    seq = [0]

    def nid() -> str:
        seq[0] += 1
        return f"n{seq[0]}"

    submit(
        book,
        OrderEvent(t=1.0, cp=cp("buyer"), side=Side.BID, price=None, size=1.5, order_id="m1"),
        fills.append,
        nid,
    )
    assert len(fills) == 2
    assert fills[0].price == 100.0 and fills[0].size == 1.0
    assert fills[1].price == 101.0 and fills[1].size == 0.5
    # Book should have 0.5 left at 101
    ba = book.best_ask()
    assert ba is not None and ba.price == 101.0 and ba.size == 0.5


def test_limit_below_touch_rests() -> None:
    book = OrderBook()
    book.add(RestingOrder("a1", cp("seller"), Side.ASK, 101.0, 1.0, 0))
    fills: list[FillEvent] = []
    submit(
        book,
        OrderEvent(t=1.0, cp=cp("buyer"), side=Side.BID, price=100.0, size=1.0, order_id="b1"),
        fills.append,
        lambda: "x",
    )
    assert fills == []
    bb = book.best_bid()
    assert bb is not None and bb.price == 100.0


def test_marketable_limit_partially_fills_then_rests() -> None:
    book = OrderBook()
    book.add(RestingOrder("a1", cp("seller"), Side.ASK, 100.0, 1.0, 0))
    fills: list[FillEvent] = []
    submit(
        book,
        OrderEvent(t=1.0, cp=cp("buyer"), side=Side.BID, price=100.5, size=2.0, order_id="b1"),
        fills.append,
        lambda: "rest",
    )
    assert len(fills) == 1
    bb = book.best_bid()
    assert bb is not None and bb.price == 100.5 and bb.size == 1.0
