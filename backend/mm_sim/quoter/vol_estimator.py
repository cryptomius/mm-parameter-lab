"""EWMA realised-volatility estimator.

Per D4: the quoter sees an estimate, not the true generator σ. Cheat mode
substitutes the true σ for comparison plots in Finding 1.
"""

from __future__ import annotations

import math


class EWMAVol:
    """Exponentially-weighted moving estimate of return std-dev per sqrt(second).

    Each `update(price, t)` ingests a new observation; we compute the log-return
    over the elapsed wall time, normalise by sqrt(dt), and EWMA the squared
    normalised return. Returns the current σ estimate (per sqrt(s)).
    """

    def __init__(self, halflife_s: float, initial_sigma: float = 0.0) -> None:
        if halflife_s <= 0:
            raise ValueError("halflife_s must be > 0")
        self.halflife_s = halflife_s
        self._var = initial_sigma * initial_sigma  # variance of normalised returns
        self._last_price: float | None = None
        self._last_t: float | None = None
        self._initialised = initial_sigma > 0

    def update(self, price: float, t: float) -> float:
        if self._last_price is None or self._last_t is None:
            self._last_price, self._last_t = price, t
            return math.sqrt(self._var)
        dt = t - self._last_t
        if dt <= 0:
            return math.sqrt(self._var)
        log_ret = math.log(price / self._last_price)
        normalised_sq = (log_ret * log_ret) / dt
        # EWMA decay derived from half-life over dt
        alpha = 1.0 - math.exp(-math.log(2.0) / self.halflife_s * dt)
        if not self._initialised:
            self._var = normalised_sq
            self._initialised = True
        else:
            self._var = (1.0 - alpha) * self._var + alpha * normalised_sq
        self._last_price, self._last_t = price, t
        return math.sqrt(self._var)

    @property
    def sigma(self) -> float:
        return math.sqrt(self._var)


class CheatVol:
    """Returns the (true) generator sigma — used for the D4 cheat-mode toggle."""

    def __init__(self, true_sigma: float) -> None:
        self.true_sigma = true_sigma

    def update(self, price: float, t: float) -> float:
        return self.true_sigma

    @property
    def sigma(self) -> float:
        return self.true_sigma
