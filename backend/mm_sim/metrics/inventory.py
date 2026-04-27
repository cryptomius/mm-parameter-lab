"""Inventory excursion tracker: peak |inv|, time-at-limit, exposure metrics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InventoryStats:
    limit: float
    max_abs_inventory: float = 0.0
    time_at_limit_s: float = 0.0
    last_t: float | None = None
    last_inv: float = 0.0

    def update(self, t: float, inventory: float) -> None:
        if self.last_t is not None and abs(self.last_inv) >= self.limit * 0.99:
            self.time_at_limit_s += t - self.last_t
        if abs(inventory) > self.max_abs_inventory:
            self.max_abs_inventory = abs(inventory)
        self.last_t = t
        self.last_inv = inventory

    def time_at_limit_pct(self, total_t: float) -> float:
        return 100.0 * self.time_at_limit_s / total_t if total_t > 0 else 0.0
