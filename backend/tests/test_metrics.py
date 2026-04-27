"""PnL and adverse-selection sanity."""

from __future__ import annotations

import pytest

from mm_sim.metrics.adverse_selection import AdverseSelectionTracker
from mm_sim.metrics.pnl import PnLState
from mm_sim.types import CounterpartyId, CounterpartyType, FillEvent, Side


def mm_cp() -> CounterpartyId:
    return CounterpartyId(id="mm", type=CounterpartyType.MM)


def noise_cp() -> CounterpartyId:
    return CounterpartyId(id="n1", type=CounterpartyType.NOISE)


def test_round_trip_realises_spread() -> None:
    pnl = PnLState()
    # MM bought 1 @ 99.95
    pnl.on_fill(
        FillEvent(
            t=0.0, maker_cp=mm_cp(), taker_cp=noise_cp(), side=Side.BID,
            price=99.95, size=1.0, mid_at_fill=100.0, maker_order_id="b",
        ),
        is_mm_maker=True, maker_rebate_bps=0, taker_fee_bps=0,
    )
    # MM sold 1 @ 100.05
    pnl.on_fill(
        FillEvent(
            t=1.0, maker_cp=mm_cp(), taker_cp=noise_cp(), side=Side.ASK,
            price=100.05, size=1.0, mid_at_fill=100.0, maker_order_id="a",
        ),
        is_mm_maker=True, maker_rebate_bps=0, taker_fee_bps=0,
    )
    assert pnl.inventory == pytest.approx(0.0)
    assert pnl.realised_spread_pnl == pytest.approx(0.10)


def test_adverse_selection_tracks_drift() -> None:
    asel = AdverseSelectionTracker()
    f = FillEvent(
        t=0.0, maker_cp=mm_cp(), taker_cp=noise_cp(), side=Side.BID,
        price=99.95, size=1.0, mid_at_fill=100.0, maker_order_id="b",
    )
    asel.on_mm_fill(f)
    # 1 second later the mid drops to 99.0 - bad for MM (we bought, price fell)
    out = asel.update(t=1.0, mid=99.0)
    horizons_resolved = {h for _, h, _ in out}
    assert 1.0 in horizons_resolved
    drifts = [d for _, h, d in out if h == 1.0]
    # mid_at_fill=100, mid=99 -> raw=(100-99)=1 for BID -> drift_bps = 1/100*1e4 = 100
    assert drifts[0] == pytest.approx(100.0)
