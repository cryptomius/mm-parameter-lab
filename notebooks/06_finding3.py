"""Finding 3 — Stress scenario responses across intervention variants.

Inputs:
    results/f3/<scenario>/<variant>/seed_42/

Outputs (per scenario):
    docs/figures/f3_<scenario>_pnl_during_event.png
    docs/figures/f3_<scenario>_inventory_during_event.png
And the headline:
    docs/figures/f3_intervention_effectiveness_grid.png
    docs/figures/f3_summary.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared.load import RESULTS_DIR, figures_path, load_run
from _shared.plotting import apply_style, save

apply_style()

SCENARIOS = ["selloff", "newsspike", "liqwithdraw", "toxicburst"]
# Variants per scenario; toxicburst uses per_cp instead of killswitch
VARIANTS = {
    "selloff": ["off", "adaptive", "killswitch", "all"],
    "newsspike": ["off", "adaptive", "killswitch", "all"],
    "liqwithdraw": ["off", "adaptive", "killswitch", "all"],
    "toxicburst": ["off", "adaptive", "per_cp", "all"],
}
EVENT_T = 1800.0


def maybe_load(scenario: str, variant: str) -> dict[str, object] | None:
    p = RESULTS_DIR / "f3" / scenario / variant / "seed_42"
    return load_run(p) if p.exists() else None


def main() -> None:
    grid: dict[str, dict[str, dict[str, object]]] = {}
    for scenario in SCENARIOS:
        runs: dict[str, dict[str, object]] = {}
        for variant in VARIANTS[scenario]:
            data = maybe_load(scenario, variant)
            if data is not None:
                runs[variant] = data
        if runs:
            grid[scenario] = runs

    if not grid:
        raise SystemExit("no f3 results found; run experiments first")

    # Per-scenario PnL & inventory plots
    for scenario, runs in grid.items():
        # PnL during event
        fig, ax = plt.subplots()
        for variant, data in runs.items():
            ts = data["inventory"].to_pandas()
            window = ts[(ts.t >= EVENT_T - 600) & (ts.t <= EVENT_T + 1200)]
            ax.plot((window.t - EVENT_T) / 60, window.total_pnl, lw=1, label=variant)
        ax.axvline(0, color="red", ls=":", lw=0.8, label="event")
        ax.set_xlabel("minutes from event")
        ax.set_ylabel("Total PnL ($)")
        ax.set_title(f"Finding 3 — {scenario}: PnL across interventions")
        ax.legend()
        save(fig, str(figures_path(f"f3_{scenario}_pnl_during_event.png")))

        # Inventory during event
        fig, ax = plt.subplots()
        for variant, data in runs.items():
            ts = data["inventory"].to_pandas()
            window = ts[(ts.t >= EVENT_T - 600) & (ts.t <= EVENT_T + 1200)]
            ax.plot((window.t - EVENT_T) / 60, window.inventory, lw=1, label=variant)
        ax.axvline(0, color="red", ls=":", lw=0.8)
        ax.axhline(0, color="black", lw=0.3)
        ax.set_xlabel("minutes from event")
        ax.set_ylabel("inventory")
        ax.set_title(f"Finding 3 — {scenario}: inventory across interventions")
        ax.legend()
        save(fig, str(figures_path(f"f3_{scenario}_inventory_during_event.png")))

    # Effectiveness grid: ΔPnL vs `off` baseline per scenario × variant
    rows = []
    for scenario, runs in grid.items():
        if "off" not in runs:
            continue
        baseline = runs["off"]["summary"]["total_pnl"]
        for variant, data in runs.items():
            if variant == "off":
                continue
            delta = data["summary"]["total_pnl"] - baseline
            rows.append({"scenario": scenario, "variant": variant, "delta_pnl": delta})
    if rows:
        df = pd.DataFrame(rows)
        pivot = df.pivot(index="scenario", columns="variant", values="delta_pnl")
        fig, ax = plt.subplots(figsize=(10, 5))
        n_vars = len(pivot.columns)
        x = np.arange(len(pivot.index))
        w = 0.8 / n_vars
        for i, var in enumerate(pivot.columns):
            ys = pivot[var].fillna(0).to_numpy()
            ax.bar(x + (i - n_vars / 2 + 0.5) * w, ys, width=w, label=var)
        ax.set_xticks(x)
        ax.set_xticklabels(pivot.index)
        ax.axhline(0, color="black", lw=0.5)
        ax.set_ylabel("ΔPnL vs no-intervention baseline ($)")
        ax.set_title("Finding 3: intervention effectiveness across scenarios (negative = HURT)")
        ax.legend()
        save(fig, str(figures_path("f3_intervention_effectiveness_grid.png")))

    # Summary JSON
    summary = {
        scenario: {
            variant: {
                "total_pnl": data["summary"]["total_pnl"],
                "max_abs_inv": data["summary"]["max_abs_inventory"],
                "quote_uptime_pct": data["summary"]["quote_uptime_pct"],
            }
            for variant, data in runs.items()
        }
        for scenario, runs in grid.items()
    }
    with open(figures_path("f3_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
