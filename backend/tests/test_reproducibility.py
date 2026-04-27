"""Same seed -> identical engine output."""

from __future__ import annotations

from datetime import datetime, timezone

from mm_sim.engine import Engine
from mm_sim.rng import RngFactory
from mm_sim.types import (
    CounterpartiesConfig,
    ExperimentConfig,
    MarketConfig,
    NoiseTraderConfig,
    QuoterConfig,
    SigmaEstimatorConfig,
)


def _short_cfg(seed: int = 42) -> ExperimentConfig:
    return ExperimentConfig(
        id="repro_short",
        seed=seed,
        duration_seconds=60.0,
        market=MarketConfig(process="gbm", sigma_true=0.001, initial_price=100.0),
        counterparties=CounterpartiesConfig(
            noise=NoiseTraderConfig(count=4, arrival_rate_hz=2.0)
        ),
        quoter=QuoterConfig(
            gamma=0.1, k=1.5, tau=300.0, refresh_ms=200,
            sigma_estimator=SigmaEstimatorConfig(type="ewma", halflife_s=30.0),
        ),
        output_path="results/_repro_test",
    )


def test_same_seed_identical_runs() -> None:
    cfg_a = _short_cfg(seed=42)
    cfg_b = _short_cfg(seed=42)
    a = Engine(cfg_a, RngFactory(seed=42)).run()
    b = Engine(cfg_b, RngFactory(seed=42)).run()
    assert len(a.fills) == len(b.fills)
    assert len(a.inventory_series) == len(b.inventory_series)
    for fa, fb in zip(a.fills, b.fills):
        assert fa.t == fb.t
        assert fa.price == fb.price
        assert fa.size == fb.size
        assert fa.maker_cp_id == fb.maker_cp_id
        assert fa.taker_cp_id == fb.taker_cp_id
    assert a.summary["total_pnl"] == b.summary["total_pnl"]


def test_different_seed_diverges() -> None:
    a = Engine(_short_cfg(seed=1), RngFactory(seed=1)).run()
    b = Engine(_short_cfg(seed=2), RngFactory(seed=2)).run()
    # Almost surely fill counts or PnL diverge across seeds
    assert (
        len(a.fills) != len(b.fills)
        or a.summary["total_pnl"] != b.summary["total_pnl"]
    )
