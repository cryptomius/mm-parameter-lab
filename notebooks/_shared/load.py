"""Notebook helpers: load parquet results into pandas/polars DataFrames."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"
FIGURES_DIR = REPO_ROOT / "docs" / "figures"


def iter_runs(experiment_path: str) -> Iterator[Path]:
    """Yield each run directory (containing fills.parquet etc.) under an experiment."""
    base = REPO_ROOT / experiment_path
    if not base.exists():
        raise FileNotFoundError(f"experiment results not found: {base}")
    # If sweeps are present, yield <sweep>/seed_<n>; otherwise yield seed_<n> directly
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("seed_"):
            yield child
            continue
        # treat as sweep dir
        for grand in sorted(child.iterdir()):
            if grand.is_dir() and grand.name.startswith("seed_"):
                yield grand


def load_run(run_dir: Path) -> dict[str, object]:
    """Load every artefact for one run."""
    out: dict[str, object] = {
        "fills": pl.read_parquet(run_dir / "fills.parquet"),
        "quotes": pl.read_parquet(run_dir / "quotes.parquet"),
        "inventory": pl.read_parquet(run_dir / "inventory.parquet"),
        "summary": json.loads((run_dir / "metrics_summary.json").read_text()),
        "path": run_dir,
    }
    return out


def load_sweep(experiment_path: str) -> dict[str, dict[str, object]]:
    """Returns {sweep_label: {fills, quotes, inventory, summary, path}}.

    For experiments with one sweep dim only, the sweep_label is the parent dir
    name (e.g. "gamma_0.1").
    """
    out: dict[str, dict[str, object]] = {}
    base = REPO_ROOT / experiment_path
    for sweep_dir in sorted(base.iterdir()):
        if not sweep_dir.is_dir():
            continue
        # Pick the first seed (single-seed for M1)
        seed_dirs = sorted(p for p in sweep_dir.iterdir() if p.is_dir())
        if not seed_dirs:
            continue
        run_dir = seed_dirs[0]
        out[sweep_dir.name] = load_run(run_dir)
    return out


def figures_path(name: str) -> Path:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    return FIGURES_DIR / name


def gamma_from_label(label: str) -> float:
    # e.g. "gamma_0.1" -> 0.1
    return float(label.split("_", 1)[1])
