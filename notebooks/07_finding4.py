"""Finding 4 — Parameter interaction effects (γ × σ_mult heatmap with MC).

Inputs:
    results/f4/grid/smult_{05,10,20,40,80}/gamma_*/seed_*/

Outputs:
    docs/figures/f4_pnl_heatmap.png
    docs/figures/f4_pnl_heatmap_5pct.png
    docs/figures/f4_pnl_heatmap_95pct.png
    docs/figures/f4_optimal_gamma_vs_vol.png
    docs/figures/f4_summary.json
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

SMULTS = {"smult_05": 0.5, "smult_10": 1.0, "smult_20": 2.0, "smult_40": 4.0, "smult_80": 8.0}


def collect() -> pd.DataFrame:
    rows = []
    base = RESULTS_DIR / "f4" / "grid"
    if not base.exists():
        return pd.DataFrame()
    for smult_dir, smult_val in SMULTS.items():
        d = base / smult_dir
        if not d.exists():
            continue
        for gamma_dir in d.iterdir():
            if not gamma_dir.is_dir():
                continue
            gamma_val = float(gamma_dir.name.split("_", 1)[1])
            for seed_dir in gamma_dir.iterdir():
                if not seed_dir.is_dir() or not seed_dir.name.startswith("seed_"):
                    continue
                seed = int(seed_dir.name.split("_", 1)[1])
                try:
                    data = load_run(seed_dir)
                except FileNotFoundError:
                    continue
                rows.append(
                    {
                        "smult": smult_val,
                        "gamma": gamma_val,
                        "seed": seed,
                        "total_pnl": data["summary"]["total_pnl"],
                        "max_abs_inv": data["summary"]["max_abs_inventory"],
                    }
                )
    return pd.DataFrame(rows)


def main() -> None:
    df = collect()
    if df.empty:
        raise SystemExit("no f4 results yet")

    # Aggregate over seeds
    agg = df.groupby(["smult", "gamma"]).total_pnl.agg(
        mean="mean",
        p5=lambda x: np.percentile(x, 5),
        p95=lambda x: np.percentile(x, 95),
        n="count",
    ).reset_index()

    def heatmap(value_col: str, title: str, filename: str) -> None:
        pivot = agg.pivot(index="smult", columns="gamma", values=value_col)
        fig, ax = plt.subplots(figsize=(8, 6))
        im = ax.imshow(pivot.values, aspect="auto", origin="lower", cmap="RdYlGn")
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels(pivot.columns)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels(pivot.index)
        ax.set_xlabel("γ")
        ax.set_ylabel("σ multiplier")
        # Annotate cells
        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                v = pivot.values[i, j]
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8, color="black")
        plt.colorbar(im, ax=ax, label="Total PnL ($)")
        ax.set_title(title)
        save(fig, str(figures_path(filename)))

    heatmap("mean", "Finding 4: mean Total PnL across γ × σ-mult", "f4_pnl_heatmap.png")
    heatmap("p5", "Finding 4: 5th-percentile PnL (worst-case across seeds)", "f4_pnl_heatmap_5pct.png")
    heatmap("p95", "Finding 4: 95th-percentile PnL (best-case across seeds)", "f4_pnl_heatmap_95pct.png")

    # Optimal gamma per smult
    pivot = agg.pivot(index="smult", columns="gamma", values="mean")
    optimal = pivot.idxmax(axis=1)
    fig, ax = plt.subplots()
    smults = optimal.index.to_numpy()
    gammas = optimal.to_numpy()
    ax.plot(smults, gammas, "o-", color="C0")
    for s, g in zip(smults, gammas):
        ax.annotate(f"γ*={g}", (s, g), textcoords="offset points", xytext=(0, 8), ha="center")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("σ multiplier")
    ax.set_ylabel("optimal γ")
    ax.set_title("Finding 4: optimal γ shifts with vol regime")
    save(fig, str(figures_path("f4_optimal_gamma_vs_vol.png")))

    # Summary
    summary = {
        "n_runs": int(df.shape[0]),
        "seeds_per_cell": int(df.groupby(["smult", "gamma"]).size().min()),
        "optimal_gamma_by_smult": {str(k): float(v) for k, v in optimal.items()},
        "mean_pnl_grid": agg.pivot(index="smult", columns="gamma", values="mean").to_dict(),
    }
    with open(figures_path("f4_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(json.dumps({k: summary[k] for k in ("n_runs", "seeds_per_cell", "optimal_gamma_by_smult")}, indent=2))


if __name__ == "__main__":
    main()
