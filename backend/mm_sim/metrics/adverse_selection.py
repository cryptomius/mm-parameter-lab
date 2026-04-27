"""Adverse-selection tracker.

For every MM fill, we want to know how the mid moves over the next 1s, 10s, 60s.
A negative drift after the MM bought (or positive drift after MM sold) is adverse.

The tracker holds open fills until each requested horizon elapses, then resolves
the drift by comparing the mid at that future time to mid_at_fill. Uses a deque
keyed by t + horizon for efficient resolution.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from mm_sim.types import FillEvent, Side

DEFAULT_HORIZONS_S: tuple[float, ...] = (1.0, 10.0, 60.0)


@dataclass
class _Pending:
    fill: FillEvent
    resolve_at: float  # t + horizon
    horizon_s: float


@dataclass
class AdverseSelectionTracker:
    horizons_s: tuple[float, ...] = DEFAULT_HORIZONS_S
    pending: deque[_Pending] = field(default_factory=deque)
    # Resolved drift bps per horizon (positive = bad for MM)
    resolved: dict[float, list[tuple[FillEvent, float]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for h in self.horizons_s:
            self.resolved.setdefault(h, [])

    def on_mm_fill(self, fill: FillEvent) -> None:
        for h in self.horizons_s:
            self.pending.append(_Pending(fill=fill, resolve_at=fill.t + h, horizon_s=h))

    def update(self, t: float, mid: float) -> list[tuple[FillEvent, float, float]]:
        """Resolve any pending fills whose horizon has elapsed.

        Returns a list of (fill, horizon_s, drift_bps) for newly resolved entries.
        drift_bps is signed from the MM's perspective: positive = adverse.
        """
        out: list[tuple[FillEvent, float, float]] = []
        while self.pending and self.pending[0].resolve_at <= t:
            p = self.pending.popleft()
            f = p.fill
            # For MM bid (we BOUGHT), price going UP is favourable; price going DOWN is adverse
            # adverse_drift = -(mid - mid_at_fill) when MM is long; +(mid - mid_at_fill) when MM is short
            # MM is on side `f.side` as maker:
            #   side=BID -> MM bought -> adverse if mid < mid_at_fill -> drift = (mid_at_fill - mid)
            #   side=ASK -> MM sold   -> adverse if mid > mid_at_fill -> drift = (mid - mid_at_fill)
            mid_at_fill = f.mid_at_fill
            if mid_at_fill <= 0:
                continue
            raw = (
                (mid_at_fill - mid) if f.side is Side.BID else (mid - mid_at_fill)
            )
            drift_bps = raw / mid_at_fill * 1e4
            self.resolved[p.horizon_s].append((f, drift_bps))
            out.append((f, p.horizon_s, drift_bps))
        return out

    def mean_drift_bps(self, horizon_s: float) -> float:
        rs = self.resolved.get(horizon_s, [])
        if not rs:
            return 0.0
        return sum(d for _, d in rs) / len(rs)
