"""Persist EngineResult to disk as parquet + JSON.

Layout per run:
  <output_path>/<sweep_label>/<seed>/
    fills.parquet
    quotes.parquet
    inventory.parquet
    metrics_summary.json
    config_snapshot.yaml
    run_metadata.json
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import polars as pl
import yaml

from mm_sim import __version__
from mm_sim.engine import EngineResult
from mm_sim.types import ExperimentConfig, RunMetadata


def run_output_dir(cfg: ExperimentConfig) -> Path:
    base = Path(cfg.output_path)
    if cfg.sweep_label:
        base = base / cfg.sweep_label
    return base / f"seed_{cfg.seed}"


def write_results(
    cfg: ExperimentConfig,
    result: EngineResult,
    started_at: datetime,
    wall_seconds: float,
) -> Path:
    out = run_output_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)

    # fills.parquet
    fills_df = pl.DataFrame(
        {
            "t": [f.t for f in result.fills],
            "side": [f.side.value for f in result.fills],
            "price": [f.price for f in result.fills],
            "size": [f.size for f in result.fills],
            "mid_at_fill": [f.mid_at_fill for f in result.fills],
            "maker_cp_id": [f.maker_cp_id for f in result.fills],
            "taker_cp_id": [f.taker_cp_id for f in result.fills],
            "drift_1s": [f.drift_1s if f.drift_1s is not None else float("nan") for f in result.fills],
            "drift_10s": [f.drift_10s if f.drift_10s is not None else float("nan") for f in result.fills],
            "drift_60s": [f.drift_60s if f.drift_60s is not None else float("nan") for f in result.fills],
        }
    )
    fills_df.write_parquet(out / "fills.parquet")

    # quotes.parquet (interventions_active stored as comma-joined string for portability)
    quotes_df = pl.DataFrame(
        {
            "t": [q.t for q in result.quotes],
            "bid_price": [_safe(q.bid_price) for q in result.quotes],
            "ask_price": [_safe(q.ask_price) for q in result.quotes],
            "reservation_price": [_safe(q.reservation_price) for q in result.quotes],
            "half_spread": [_safe(q.half_spread) for q in result.quotes],
            "inventory": [q.inventory for q in result.quotes],
            "sigma_est": [q.sigma_est for q in result.quotes],
            "interventions_active": [",".join(q.interventions_active) for q in result.quotes],
        }
    )
    quotes_df.write_parquet(out / "quotes.parquet")

    # inventory.parquet (1Hz time series)
    ts = result.inventory_series
    ts_df = pl.DataFrame(
        {
            "t": [p.t for p in ts],
            "mid": [p.mid for p in ts],
            "inventory": [p.inventory for p in ts],
            "cash": [p.cash for p in ts],
            "realised_pnl": [p.realised_pnl for p in ts],
            "unrealised_pnl": [p.unrealised_pnl for p in ts],
            "total_pnl": [p.total_pnl for p in ts],
            "sigma_est": [p.sigma_est for p in ts],
        }
    )
    ts_df.write_parquet(out / "inventory.parquet")

    # metrics_summary.json
    (out / "metrics_summary.json").write_text(json.dumps(result.summary, indent=2))

    # config_snapshot.yaml — dump the resolved config
    cfg_dict = json.loads(cfg.model_dump_json())
    (out / "config_snapshot.yaml").write_text(yaml.safe_dump(cfg_dict, sort_keys=False))

    # run_metadata.json
    finished = datetime.now(timezone.utc)
    meta = RunMetadata(
        experiment_id=cfg.id,
        sweep_label=cfg.sweep_label,
        seed=cfg.seed,
        started_at_utc=started_at.isoformat(),
        finished_at_utc=finished.isoformat(),
        wall_seconds=wall_seconds,
        sim_engine_version=__version__,
    )
    (out / "run_metadata.json").write_text(meta.model_dump_json(indent=2))

    return out


def _safe(x: float) -> float:
    return x if not (x is None or math.isnan(x) or math.isinf(x)) else float("nan")


class Timer:
    def __enter__(self) -> "Timer":
        self.start = perf_counter()
        return self

    def __exit__(self, *_: object) -> None:
        self.elapsed = perf_counter() - self.start
