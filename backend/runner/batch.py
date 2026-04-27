"""Run a list of experiments either sequentially or via multiprocessing."""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from mm_sim.engine import Engine
from mm_sim.logging_config import configure, get_logger
from mm_sim.results import Timer, run_output_dir, write_results
from mm_sim.rng import RngFactory
from mm_sim.types import ExperimentConfig

log = get_logger("runner.batch")


def run_one(cfg: ExperimentConfig) -> tuple[str, Path, float]:
    """Run a single experiment. Returns (id, output_path, wall_seconds)."""
    configure(level=os.environ.get("MM_LOG_LEVEL", "INFO"))
    rng = RngFactory(seed=cfg.seed)
    engine = Engine(cfg, rng)
    started = datetime.now(timezone.utc)
    with Timer() as t:
        result = engine.run()
    out = write_results(cfg, result, started_at=started, wall_seconds=t.elapsed)
    return cfg.id + ("/" + cfg.sweep_label if cfg.sweep_label else "") + f"/seed_{cfg.seed}", out, t.elapsed


def run_many(cfgs: list[ExperimentConfig], workers: int = 1) -> list[Path]:
    """Run a batch with optional multiprocessing."""
    out_paths: list[Path] = []
    if workers <= 1:
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("running", total=len(cfgs))
            for cfg in cfgs:
                _, out, elapsed = run_one(cfg)
                log.info("run.done", id=cfg.id, sweep=cfg.sweep_label, seed=cfg.seed, elapsed=elapsed, out=str(out))
                out_paths.append(out)
                progress.update(task, advance=1)
        return out_paths

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task("running", total=len(cfgs))
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(run_one, cfg): cfg for cfg in cfgs}
            for fut in as_completed(futures):
                cfg = futures[fut]
                _, out, elapsed = fut.result()
                log.info("run.done", id=cfg.id, sweep=cfg.sweep_label, seed=cfg.seed, elapsed=elapsed, out=str(out))
                out_paths.append(out)
                progress.update(task, advance=1)
    return out_paths


def expected_output(cfg: ExperimentConfig) -> Path:
    return run_output_dir(cfg)
