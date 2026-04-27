"""Per-counterparty fill stats and toxicity rolling estimator.

For Finding 2 we need (1) per-CP fill counts and avg post-fill drift, and
(2) a rolling toxicity score that the per-counterparty-penalty intervention
consumes. Toxicity here is in bps (positive = costs the MM)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class CPStats:
    fill_count: int = 0
    total_volume: float = 0.0
    sum_drift_bps_10s: float = 0.0
    n_drift_obs: int = 0

    @property
    def mean_drift_bps_10s(self) -> float:
        return self.sum_drift_bps_10s / self.n_drift_obs if self.n_drift_obs > 0 else 0.0


@dataclass
class PerCounterpartyStats:
    by_cp: dict[str, CPStats] = field(default_factory=lambda: defaultdict(CPStats))

    def on_fill(self, cp_id: str, size: float) -> None:
        s = self.by_cp[cp_id]
        s.fill_count += 1
        s.total_volume += size

    def on_drift_resolved(self, cp_id: str, drift_bps_10s: float) -> None:
        s = self.by_cp[cp_id]
        s.sum_drift_bps_10s += drift_bps_10s
        s.n_drift_obs += 1
