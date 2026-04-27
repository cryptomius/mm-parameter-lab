"""Match incoming orders against the book; emit fills.

Marketable limits and market orders walk the book in price-time priority.
Aggressive limits that don't fully fill are added to the book as resting
liquidity.
"""

from __future__ import annotations

from typing import Callable

from mm_sim.market.book import OrderBook, RestingOrder
from mm_sim.types import CounterpartyId, FillEvent, OrderEvent, Side

FillSink = Callable[[FillEvent], None]


def submit(
    book: OrderBook,
    order: OrderEvent,
    on_fill: FillSink,
    next_id: Callable[[], str],
) -> None:
    """Process an incoming order against the book.

    - Market order: walk opposite side until size exhausted (or book empty).
    - Limit order: walk opposite side while price is marketable; rest the rest.

    Fills are emitted from the MAKER's perspective in `FillEvent.side`.
    """
    remaining = order.size
    while remaining > 0:
        opp_best = book.best_ask() if order.side is Side.BID else book.best_bid()
        if opp_best is None:
            break
        if order.price is not None:
            crosses = (
                order.price >= opp_best.price
                if order.side is Side.BID
                else order.price <= opp_best.price
            )
            if not crosses:
                break
        # Cross: take liquidity at opp_best
        trade_size = min(remaining, opp_best.size)
        mid = book.mid() or opp_best.price
        on_fill(
            FillEvent(
                t=order.t,
                maker_cp=opp_best.cp,
                taker_cp=order.cp,
                side=opp_best.side,
                price=opp_best.price,
                size=trade_size,
                mid_at_fill=mid,
                maker_order_id=opp_best.order_id,
            )
        )
        book.reduce_front(opp_best.side, opp_best.price, trade_size)
        remaining -= trade_size

    # Rest the remainder if it's a limit order
    if remaining > 1e-12 and order.price is not None:
        rid = order.order_id or next_id()
        book.add(
            RestingOrder(
                order_id=rid,
                cp=order.cp,
                side=order.side,
                price=order.price,
                size=remaining,
                t_placed=order.t,
            )
        )


def quote_replace(
    book: OrderBook,
    mm_cp: CounterpartyId,
    bid_price: float | None,
    bid_size: float,
    ask_price: float | None,
    ask_size: float,
    t: float,
    next_id: Callable[[], str],
    on_fill: FillSink,
) -> tuple[str | None, str | None]:
    """Cancel any existing MM quotes, then place new bid/ask.

    Returns the (bid_id, ask_id) of the newly placed quotes, either may be None
    if that side wasn't quoted.
    """
    book.cancel_all_for(mm_cp.id)
    bid_id: str | None = None
    ask_id: str | None = None
    if bid_price is not None and bid_size > 0:
        bid_id = next_id()
        submit(
            book,
            OrderEvent(
                t=t, cp=mm_cp, side=Side.BID, price=bid_price, size=bid_size, order_id=bid_id
            ),
            on_fill,
            next_id,
        )
    if ask_price is not None and ask_size > 0:
        ask_id = next_id()
        submit(
            book,
            OrderEvent(
                t=t, cp=mm_cp, side=Side.ASK, price=ask_price, size=ask_size, order_id=ask_id
            ),
            on_fill,
            next_id,
        )
    return bid_id, ask_id
