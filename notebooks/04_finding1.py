"""Finding 1 — Inventory aversion trade-off.

Inputs:
    results/f1/gamma_sweep_low_vol/gamma_*/seed_42/
    results/f1/gamma_sweep_high_vol/gamma_*/seed_42/
    results/f1/sigma_estimation_lowvol/seed_42/  (single run)

Outputs:
    docs/figures/f1_pnl_vs_gamma.png
    docs/figures/f1_inventory_envelope.png
    docs/figures/f1_spread_width_vs_gamma.png
    docs/figures/f1_summary.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared.load import figures_path, gamma_from_label, load_sweep
from _shared.plotting import apply_style, save

apply_style()


def collect(experiment_path: str) -> dict[float, dict[str, object]]:
    sweep = load_sweep(experiment_path)
    return {gamma_from_label(label): data for label, data in sweep.items()}


def main() -> None:
    low = collect("results/f1/gamma_sweep_low_vol")
    try:
        high = collect("results/f1/gamma_sweep_high_vol")
    except FileNotFoundError:
        print("warn: high-vol sweep not found; will plot low-vol only")
        high = {}

    # 1. PnL vs gamma — both regimes overlaid
    fig, ax = plt.subplots()
    for regime, runs, color in [("low vol (σ=0.001)", low, "C0"), ("high vol (σ=0.003)", high, "C3")]:
        if not runs:
            continue
        gammas = sorted(runs.keys())
        pnls = [runs[g]["summary"]["total_pnl"] for g in gammas]
        ax.plot(gammas, pnls, "o-", label=regime, color=color)
    ax.set_xscale("log")
    ax.set_xlabel("γ (inventory aversion)")
    ax.set_ylabel("Total PnL ($)")
    ax.set_title("Finding 1: PnL vs γ across vol regimes")
    ax.legend()
    save(fig, str(figures_path("f1_pnl_vs_gamma.png")))

    # 2. Inventory envelope: |inv| percentiles per gamma (low vol)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)
    for ax, (regime, runs, color) in zip(
        axes,
        [("low vol", low, "C0"), ("high vol", high, "C3")],
    ):
        if not runs:
            ax.set_visible(False)
            continue
        gammas = sorted(runs.keys())
        p50, p95, pmax = [], [], []
        for g in gammas:
            invs = runs[g]["inventory"].to_pandas()["inventory"].abs().to_numpy()
            p50.append(float(np.percentile(invs, 50)))
            p95.append(float(np.percentile(invs, 95)))
            pmax.append(float(invs.max()))
        ax.plot(gammas, pmax, "o-", color=color, label="max")
        ax.plot(gammas, p95, "s--", color=color, alpha=0.7, label="p95")
        ax.plot(gammas, p50, "^:", color=color, alpha=0.5, label="p50")
        ax.set_xscale("log")
        ax.set_xlabel("γ")
        ax.set_title(f"{regime}: |inventory| percentiles")
        ax.legend()
    axes[0].set_ylabel("|inventory|")
    save(fig, str(figures_path("f1_inventory_envelope.png")))

    # 3. Spread width vs gamma (mean half_spread in bps)
    fig, ax = plt.subplots()
    for regime, runs, color in [("low vol", low, "C0"), ("high vol", high, "C3")]:
        if not runs:
            continue
        gammas = sorted(runs.keys())
        spreads_bps = []
        for g in gammas:
            q = runs[g]["quotes"].to_pandas()
            q = q.dropna(subset=["half_spread"])
            mean_bps = (q.half_spread / q.reservation_price * 1e4).mean()
            spreads_bps.append(float(mean_bps))
        ax.plot(gammas, spreads_bps, "o-", label=regime, color=color)
    ax.set_xscale("log")
    ax.set_xlabel("γ")
    ax.set_ylabel("Mean half-spread (bps)")
    ax.set_title("Finding 1: spread width vs γ")
    ax.legend()
    save(fig, str(figures_path("f1_spread_width_vs_gamma.png")))

    # 4. Summary json
    summary = {
        "low_vol": {
            str(g): {
                "pnl": low[g]["summary"]["total_pnl"],
                "max_abs_inv": low[g]["summary"]["max_abs_inventory"],
                "fills": int(low[g]["summary"]["fill_count"]),
            }
            for g in sorted(low.keys())
        },
        "high_vol": {
            str(g): {
                "pnl": high[g]["summary"]["total_pnl"],
                "max_abs_inv": high[g]["summary"]["max_abs_inventory"],
                "fills": int(high[g]["summary"]["fill_count"]),
            }
            for g in sorted(high.keys())
        }
        if high
        else {},
    }
    with open(figures_path("f1_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
