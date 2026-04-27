"""Consistent matplotlib styling across all findings notebooks."""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt


def apply_style() -> None:
    mpl.rcParams.update(
        {
            "figure.figsize": (9, 5),
            "figure.dpi": 110,
            "savefig.dpi": 130,
            "savefig.bbox": "tight",
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "axes.grid": True,
            "grid.alpha": 0.3,
            "grid.linestyle": "--",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
            "legend.fontsize": 9,
            "font.family": "DejaVu Sans",
        }
    )


def save(fig: plt.Figure, path: str) -> None:
    fig.savefig(path)
    plt.close(fig)
