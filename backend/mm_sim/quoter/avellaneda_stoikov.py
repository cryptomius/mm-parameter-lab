"""Avellaneda-Stoikov quoter, infinite-horizon variant (D2).

Reservation price: r = s − q · γ · σ² · τ
Half-spread:      δ = (γ · σ² · τ) / 2 + (1/γ) · ln(1 + γ/k)
Quotes:           bid = r − δ, ask = r + δ

Where τ replaces the original AS (T − t) so dynamics are stationary —
this is the variant the spec locked in.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Quote:
    bid_price: float
    ask_price: float
    reservation_price: float
    half_spread: float
    inv_risk_term: float
    rent_term: float


class AvellanedaStoikov:
    """Pure-function-style quoter; carries no state but the params."""

    def __init__(
        self,
        gamma: float,
        k: float,
        tau: float,
        spread_min: float,
        spread_max: float,
    ) -> None:
        if gamma <= 0:
            raise ValueError("gamma must be > 0")
        if k <= 0:
            raise ValueError("k must be > 0")
        if tau <= 0:
            raise ValueError("tau must be > 0")
        self.gamma = gamma
        self.k = k
        self.tau = tau
        self.spread_min = spread_min
        self.spread_max = spread_max

    def quote(self, mid: float, inventory: float, sigma: float) -> Quote:
        sigma2 = sigma * sigma
        # Inventory-shaded reservation price
        reservation = mid - inventory * self.gamma * sigma2 * self.tau
        # AS half-spread
        inv_risk_term = (self.gamma * sigma2 * self.tau) / 2.0
        # Guard ln(1+x) when gamma/k is very small or large; both finite for sane inputs
        rent_term = (1.0 / self.gamma) * math.log1p(self.gamma / self.k)
        half_spread = inv_risk_term + rent_term
        # Convert min/max from absolute price units to half-spread caps
        # Caps in the config are total-spread fractions of mid; convert to absolute half-spread
        min_half = 0.5 * self.spread_min * mid
        max_half = 0.5 * self.spread_max * mid
        half_spread = max(min_half, min(max_half, half_spread))
        return Quote(
            bid_price=reservation - half_spread,
            ask_price=reservation + half_spread,
            reservation_price=reservation,
            half_spread=half_spread,
            inv_risk_term=inv_risk_term,
            rent_term=rent_term,
        )
