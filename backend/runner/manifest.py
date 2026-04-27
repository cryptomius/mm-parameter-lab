"""Load experiments.yaml and expand sweeps into concrete ExperimentConfig instances."""

from __future__ import annotations

import copy
import fnmatch
from pathlib import Path
from typing import Any

import yaml

from mm_sim.types import ExperimentConfig


def load_manifest(path: Path) -> list[dict[str, Any]]:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, list):
        raise ValueError(f"manifest must be a list of experiments, got {type(raw)}")
    return raw


def expand(entry: dict[str, Any]) -> list[ExperimentConfig]:
    """Expand sweeps (gamma_sweep, multiple seeds) into concrete configs."""
    seeds = entry.get("seeds", [entry.get("seed", 42)])
    if not isinstance(seeds, list):
        seeds = [seeds]

    quoter = entry.get("quoter", {})
    gammas = quoter.get("gamma_sweep") or [quoter.get("gamma", 0.1)]

    out: list[ExperimentConfig] = []
    for gamma in gammas:
        for seed in seeds:
            cfg_dict = copy.deepcopy(entry)
            cfg_dict.pop("seeds", None)
            cfg_dict["seed"] = int(seed)
            quoter_local = dict(quoter)
            quoter_local["gamma"] = float(gamma)
            quoter_local.pop("gamma_sweep", None)
            cfg_dict["quoter"] = quoter_local
            label_parts: list[str] = []
            if len(gammas) > 1:
                label_parts.append(f"gamma_{gamma}")
            cfg_dict["sweep_label"] = "__".join(label_parts) if label_parts else None
            out.append(ExperimentConfig.model_validate(cfg_dict))
    return out


def find_experiment(manifest: list[dict[str, Any]], experiment_id: str) -> dict[str, Any]:
    for e in manifest:
        if e.get("id") == experiment_id:
            return e
    raise KeyError(f"experiment {experiment_id!r} not in manifest")


def select_experiments(
    manifest: list[dict[str, Any]], pattern: str
) -> list[dict[str, Any]]:
    """Glob-pattern match against experiment ids."""
    return [e for e in manifest if fnmatch.fnmatch(e.get("id", ""), pattern)]
