"""Order book correctness."""

from __future__ import annotations

import pytest

from mm_sim.market.book import OrderBook, RestingOrder
from mm_sim.types import CounterpartyId, CounterpartyType, Side


def cp(name: str = "x") -> CounterpartyId:
    return CounterpartyId(id=name, type=CounterpartyType.NOISE)


def order(side: Side, price: float, size: float, oid: str) -> RestingOrder:
    return RestingOrder(order_id=oid, cp=cp(), side=side, price=price, size=size, t_placed=0.0)


def test_best_bid_ask_ordering() -> None:
    b = OrderBook()
    b.add(order(Side.BID, 100.0, 1.0, "b1"))
    b.add(order(Side.BID, 101.0, 1.0, "b2"))
    b.add(order(Side.BID, 99.0, 1.0, "b3"))
    b.add(order(Side.ASK, 102.0, 1.0, "a1"))
    b.add(order(Side.ASK, 103.0, 1.0, "a2"))
    bb = b.best_bid()
    ba = b.best_ask()
    assert bb is not None and bb.price == 101.0
    assert ba is not None and ba.price == 102.0
    assert b.mid() == pytest.approx(101.5)


def test_cancel_removes_order() -> None:
    b = OrderBook()
    b.add(order(Side.BID, 100.0, 1.0, "b1"))
    assert len(b) == 1
    cancelled = b.cancel("b1")
    assert cancelled is not None
    assert len(b) == 0
    assert b.best_bid() is None


def test_reduce_front_pops_when_zero() -> None:
    b = OrderBook()
    b.add(order(Side.BID, 100.0, 1.0, "b1"))
    b.reduce_front(Side.BID, 100.0, 1.0)
    assert b.best_bid() is None


def test_cancel_all_for_cp() -> None:
    b = OrderBook()
    cp_a = CounterpartyId(id="a", type=CounterpartyType.NOISE)
    cp_b = CounterpartyId(id="b", type=CounterpartyType.NOISE)
    b.add(RestingOrder(order_id="o1", cp=cp_a, side=Side.BID, price=100.0, size=1.0, t_placed=0))
    b.add(RestingOrder(order_id="o2", cp=cp_b, side=Side.BID, price=99.0, size=1.0, t_placed=0))
    b.add(RestingOrder(order_id="o3", cp=cp_a, side=Side.ASK, price=101.0, size=1.0, t_placed=0))
    n = b.cancel_all_for("a")
    assert n == 2
    assert len(b) == 1
    assert b.best_bid() is not None and b.best_bid().price == 99.0  # type: ignore[union-attr]
