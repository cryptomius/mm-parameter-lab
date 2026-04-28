"""Avellaneda-Stoikov quoter, infinite-horizon variant (D2).

Reservation price: r = s − (q − q_target) · γ · σ² · τ
Half-spread:      δ = (γ · σ² · τ) / 2 + (1/γ) · ln(1 + γ/k)
Quotes:           bid = r − δ, ask = r + δ   (SYMMETRIC; engine applies asymmetry)

Where τ replaces the original AS (T − t) so dynamics are stationary —
this is the variant the spec locked in.

Two operator-level extensions to the canonical formula:

- ``q_target`` lets the operator pre-bias the quoter toward a non-zero
  inventory target (e.g. expecting persistent buy-side pressure → set
  q_target negative so the quoter pre-skews short). Applied directly in
  the reservation-price calculation here.
- ``bid_widening_factor`` / ``ask_widening_factor`` are multiplicative
  per-side spread asymmetries. They are STORED on the quoter for the
  engine's convenience but NOT applied in ``quote()`` — instead the
  engine applies them as the final transformation in
  ``Engine._refresh_quotes`` after running the intervention pipeline
  (adaptive_spread, per_cp_penalty). This keeps the asymmetry composable
  with vol-driven and CP-driven widenings.
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
        q_target: float = 0.0,
        bid_widening_factor: float = 1.0,
        ask_widening_factor: float = 1.0,
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
        self.q_target = q_target
        self.bid_widening_factor = bid_widening_factor
        self.ask_widening_factor = ask_widening_factor

    def quote(self, mid: float, inventory: float, sigma: float) -> Quote:
        sigma2 = sigma * sigma
        # Inventory-shaded reservation price (relative to q_target)
        effective_inv = inventory - self.q_target
        reservation = mid - effective_inv * self.gamma * sigma2 * self.tau
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
        # Symmetric quote. Engine applies bid/ask widening factors after
        # the intervention pipeline (see Engine._refresh_quotes).
        return Quote(
            bid_price=reservation - half_spread,
            ask_price=reservation + half_spread,
            reservation_price=reservation,
            half_spread=half_spread,
            inv_risk_term=inv_risk_term,
            rent_term=rent_term,
        )
