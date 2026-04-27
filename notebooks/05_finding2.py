"""Finding 2 — Adverse selection and the cost of naive quoting.

Inputs:
    results/f2/informed_{00,10,20,30}/seed_42/
    results/f2/penalty_{none,per_cp,global_widen}/seed_42/

Outputs:
    docs/figures/f2_post_fill_drift_histograms.png
    docs/figures/f2_pnl_decomp_by_informed_share.png
    docs/figures/f2_intervention_recovery.png
    docs/figures/f2_counterparty_toxicity_learning.png
    docs/figures/f2_summary.json
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


def maybe_load(path: str) -> dict[str, object] | None:
    p = RESULTS_DIR / path / "seed_42"
    if not p.exists():
        return None
    return load_run(p)


def main() -> None:
    informed_runs = {
        0: maybe_load("f2/informed_00"),
        10: maybe_load("f2/informed_10"),
        20: maybe_load("f2/informed_20"),
        30: maybe_load("f2/informed_30"),
    }
    informed_runs = {k: v for k, v in informed_runs.items() if v is not None}

    if not informed_runs:
        raise SystemExit("no f2 results found; run experiments first")

    # 1. Post-fill drift histograms (10s horizon), separated by TAKER TYPE (informed vs noise),
    #    faceted by informed pct. Aggregate drift hides adverse selection — per-taker reveals it.
    fig, axes = plt.subplots(1, len(informed_runs), figsize=(4 * len(informed_runs), 4), sharey=True)
    if len(informed_runs) == 1:
        axes = [axes]
    per_taker_means: dict[int, dict[str, float]] = {}
    for ax, (pct, data) in zip(axes, sorted(informed_runs.items())):
        fills = data["fills"].to_pandas()
        mm = fills[fills.maker_cp_id == "mm"].dropna(subset=["drift_10s"])
        inf_d = mm[mm.taker_cp_id.str.startswith("informed")]["drift_10s"]
        noise_d = mm[mm.taker_cp_id.str.startswith("noise")]["drift_10s"]
        ax.hist(
            [noise_d, inf_d],
            bins=40, range=(-50, 50),
            label=[f"noise (n={len(noise_d)})", f"informed (n={len(inf_d)})"],
            alpha=0.75, color=["#2d7", "#e44"],
        )
        ax.axvline(0, color="black", lw=0.5)
        m_inf = inf_d.mean() if len(inf_d) else 0.0
        m_noise = noise_d.mean() if len(noise_d) else 0.0
        per_taker_means[pct] = {"informed": m_inf, "noise": m_noise}
        ax.set_title(f"informed {pct}%: noise={m_noise:+.1f}bp  inf={m_inf:+.1f}bp")
        ax.set_xlabel("post-fill drift @ 10s (bps, +ve = adverse to MM)")
        ax.legend(fontsize=7)
    axes[0].set_ylabel("fill count")
    fig.suptitle("Finding 2: per-taker drift exposes adverse selection (aggregates hide it)")
    save(fig, str(figures_path("f2_post_fill_drift_histograms.png")))

    # 2. PnL decomposition by informed share
    rows = []
    for pct, data in sorted(informed_runs.items()):
        s = data["summary"]
        rows.append({"pct": pct, "spread": s["spread_pnl"], "inventory": s["inventory_pnl"], "total": s["total_pnl"]})
    df = pd.DataFrame(rows)
    fig, ax = plt.subplots()
    ax.bar(df.pct - 1.5, df.spread, width=3, label="spread PnL", color="C2")
    ax.bar(df.pct + 1.5, df.inventory, width=3, label="inventory PnL", color="C1")
    ax.plot(df.pct, df.total, "ko-", label="total PnL", lw=1.5)
    ax.set_xlabel("informed flow share (%)")
    ax.set_ylabel("PnL ($)")
    ax.set_title("Finding 2: spread capture eaten by inventory PnL as informed flow grows")
    ax.legend()
    save(fig, str(figures_path("f2_pnl_decomp_by_informed_share.png")))

    # 3. Intervention recovery
    pen_runs = {
        "none": maybe_load("f2/penalty_none"),
        "per-counterparty": maybe_load("f2/penalty_per_cp"),
        "global widening": maybe_load("f2/penalty_global_widen"),
    }
    pen_runs = {k: v for k, v in pen_runs.items() if v is not None}
    if pen_runs:
        labels = list(pen_runs.keys())
        pnls = [pen_runs[l]["summary"]["total_pnl"] for l in labels]
        fig, ax = plt.subplots()
        bars = ax.bar(labels, pnls, color=["C3", "C0", "C4"])
        for b, v in zip(bars, pnls):
            ax.text(b.get_x() + b.get_width() / 2, v, f"${v:.0f}", ha="center", va="bottom")
        ax.set_ylabel("Total PnL ($)")
        ax.set_title("Finding 2: intervention effectiveness vs naive quoting (20% informed flow)")
        save(fig, str(figures_path("f2_intervention_recovery.png")))
    else:
        print("warn: penalty intervention runs missing; skipping recovery chart")

    # 4. Counterparty toxicity learning (per-CP penalty run)
    pcp = pen_runs.get("per-counterparty") if pen_runs else None
    if pcp is not None:
        fills = pcp["fills"].to_pandas()
        mm = fills[fills.maker_cp_id == "mm"].dropna(subset=["drift_10s"])
        # Rolling mean drift per CP, by 5min buckets
        mm["bucket"] = (mm.t // 300).astype(int) * 300
        agg = mm.groupby(["bucket", "taker_cp_id"]).drift_10s.mean().unstack().fillna(0)
        fig, ax = plt.subplots(figsize=(11, 5))
        for col in agg.columns:
            color = "C3" if col.startswith("informed") else "C0"
            alpha = 1.0 if col.startswith("informed") else 0.25
            ax.plot(agg.index / 60, agg[col], color=color, alpha=alpha, lw=0.8)
        ax.axhline(0, color="black", lw=0.4)
        ax.set_xlabel("sim minutes")
        ax.set_ylabel("mean post-fill drift @ 10s (bps)")
        ax.set_title("Finding 2: per-counterparty drift over time (red = informed, blue = noise)")
        save(fig, str(figures_path("f2_counterparty_toxicity_learning.png")))

    # 5. Summary — include per-taker drift breakdown to expose the headline finding
    summary = {
        "informed_sweep": {
            f"{pct}%": {
                "total_pnl": data["summary"]["total_pnl"],
                "spread_pnl": data["summary"]["spread_pnl"],
                "inventory_pnl": data["summary"]["inventory_pnl"],
                "mean_drift_bps_10s_aggregate": data["summary"]["mean_drift_bps_10s"],
                "mean_drift_bps_10s_vs_informed": per_taker_means.get(pct, {}).get("informed"),
                "mean_drift_bps_10s_vs_noise": per_taker_means.get(pct, {}).get("noise"),
                "fill_count": int(data["summary"]["fill_count"]),
            }
            for pct, data in sorted(informed_runs.items())
        },
        "penalty_intervention": {
            label: {
                "total_pnl": data["summary"]["total_pnl"],
                "max_abs_inv": data["summary"]["max_abs_inventory"],
            }
            for label, data in pen_runs.items()
        }
        if pen_runs
        else {},
    }
    with open(figures_path("f2_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
