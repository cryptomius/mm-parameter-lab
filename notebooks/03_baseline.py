"""Baseline behaviour: AS quoter on calm GBM, no events, no interventions.

Generates:
    docs/figures/baseline_price_and_quotes.png
    docs/figures/baseline_inventory.png
    docs/figures/baseline_pnl_decomp.png
    docs/figures/baseline_fill_distribution.png
    docs/figures/baseline_summary.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared.load import figures_path, load_run, RESULTS_DIR
from _shared.plotting import apply_style, save

apply_style()

RUN = RESULTS_DIR / "baseline_calm" / "seed_42"


def main() -> None:
    if not RUN.exists():
        raise SystemExit(f"baseline_calm not run yet: {RUN}")
    data = load_run(RUN)
    fills = data["fills"].to_pandas()
    quotes = data["quotes"].to_pandas()
    inv = data["inventory"].to_pandas()
    summary = data["summary"]

    # 1. Price & quotes (first 30 minutes)
    window_end = 1800.0
    q_win = quotes[quotes.t <= window_end]
    inv_win = inv[inv.t <= window_end]
    fig, ax = plt.subplots()
    ax.plot(inv_win.t / 60, inv_win.mid, lw=0.8, label="mid", color="black")
    ax.plot(q_win.t / 60, q_win.bid_price, "--", lw=0.6, color="C3", label="bid")
    ax.plot(q_win.t / 60, q_win.ask_price, "--", lw=0.6, color="C2", label="ask")
    ax.set_xlabel("sim minutes")
    ax.set_ylabel("price")
    ax.set_title("Baseline: mid and MM quotes (first 30 min)")
    ax.legend()
    save(fig, str(figures_path("baseline_price_and_quotes.png")))

    # 2. Inventory over time
    fig, ax = plt.subplots()
    ax.plot(inv.t / 60, inv.inventory, color="C0", lw=0.7)
    ax.axhline(100, color="red", ls=":", lw=0.7, label="limit")
    ax.axhline(-100, color="red", ls=":", lw=0.7)
    ax.set_xlabel("sim minutes")
    ax.set_ylabel("inventory")
    ax.set_title("Baseline: inventory over time")
    ax.legend()
    save(fig, str(figures_path("baseline_inventory.png")))

    # 3. PnL decomposition (stacked area)
    fig, ax = plt.subplots()
    ax.plot(inv.t / 60, inv.realised_pnl, label="spread (realised)", color="C2")
    ax.plot(inv.t / 60, inv.unrealised_pnl, label="inventory (unrealised)", color="C1")
    ax.plot(inv.t / 60, inv.total_pnl, label="total", color="black", lw=1.2)
    ax.set_xlabel("sim minutes")
    ax.set_ylabel("PnL ($)")
    ax.set_title("Baseline: PnL decomposition")
    ax.legend()
    save(fig, str(figures_path("baseline_pnl_decomp.png")))

    # 4. Fill distribution by side (MM-maker fills only)
    mm_fills = fills[fills.maker_cp_id == "mm"]
    fig, ax = plt.subplots()
    ax.hist(
        [mm_fills[mm_fills.side == "bid"]["size"], mm_fills[mm_fills.side == "ask"]["size"]],
        bins=30, label=["bid (MM bought)", "ask (MM sold)"], stacked=False,
    )
    ax.set_xlabel("fill size")
    ax.set_ylabel("count")
    ax.set_title(f"Baseline: MM fill size distribution (n={len(mm_fills)})")
    ax.legend()
    save(fig, str(figures_path("baseline_fill_distribution.png")))

    # 5. Summary
    out = {
        "total_pnl": summary["total_pnl"],
        "spread_pnl": summary["spread_pnl"],
        "inventory_pnl": summary["inventory_pnl"],
        "max_abs_inventory": summary["max_abs_inventory"],
        "time_at_limit_pct": summary["time_at_limit_pct"],
        "quote_uptime_pct": summary["quote_uptime_pct"],
        "fill_count": int(summary["fill_count"]),
        "mean_drift_bps_10s": summary["mean_drift_bps_10s"],
    }
    with open(figures_path("baseline_summary.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
