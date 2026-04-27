"""True-price generators: GBM, OU, jump-diffusion.

All generators are stepwise: `step(dt)` advances by `dt` seconds and returns
the new mid. Each owns its own Generator (from RngFactory.child) so seed-level
reproducibility is preserved across simulation runs with different consumer sets.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

import numpy as np
from numpy.random import Generator

from mm_sim.types import MarketConfig


class PriceProcess(ABC):
    """A stepwise price-path generator."""

    def __init__(self, initial_price: float, rng: Generator) -> None:
        self._price = float(initial_price)
        self._rng = rng

    @property
    def price(self) -> float:
        return self._price

    @abstractmethod
    def step(self, dt: float) -> float:
        """Advance by dt seconds, return new mid."""
        ...


class GBM(PriceProcess):
    """Geometric Brownian Motion: dS/S = mu*dt + sigma*dW.

    sigma is in units per sqrt(second). For a typical crypto pair sigma ~ 0.001
    to 0.01 / sqrt(s) gives reasonable volatility on a unitless price ~ 100.
    """

    def __init__(
        self, initial_price: float, sigma: float, drift: float, rng: Generator
    ) -> None:
        super().__init__(initial_price, rng)
        self.sigma = sigma
        self.drift = drift

    def step(self, dt: float) -> float:
        z = self._rng.standard_normal()
        # Exact GBM step: S_{t+dt} = S_t * exp((mu - 0.5 sigma^2) dt + sigma sqrt(dt) z)
        log_step = (self.drift - 0.5 * self.sigma * self.sigma) * dt + self.sigma * math.sqrt(
            dt
        ) * z
        self._price *= math.exp(log_step)
        return self._price


class OU(PriceProcess):
    """Ornstein-Uhlenbeck on log-price: dX = kappa*(mu - X)*dt + sigma*dW."""

    def __init__(
        self,
        initial_price: float,
        sigma: float,
        kappa: float,
        mean: float,
        rng: Generator,
    ) -> None:
        super().__init__(initial_price, rng)
        self.sigma = sigma
        self.kappa = kappa
        self.mean = mean
        self._x = math.log(initial_price)

    def step(self, dt: float) -> float:
        z = self._rng.standard_normal()
        self._x += self.kappa * (self.mean - self._x) * dt + self.sigma * math.sqrt(dt) * z
        self._price = math.exp(self._x)
        return self._price


class JumpDiffusion(PriceProcess):
    """GBM with Poisson-arrival jumps: lognormal jump multiplier."""

    def __init__(
        self,
        initial_price: float,
        sigma: float,
        drift: float,
        jump_intensity: float,
        jump_mean: float,
        jump_std: float,
        rng: Generator,
    ) -> None:
        super().__init__(initial_price, rng)
        self.sigma = sigma
        self.drift = drift
        self.jump_intensity = jump_intensity
        self.jump_mean = jump_mean  # mean of log jump
        self.jump_std = jump_std  # std of log jump

    def step(self, dt: float) -> float:
        z = self._rng.standard_normal()
        log_step = (self.drift - 0.5 * self.sigma * self.sigma) * dt + self.sigma * math.sqrt(
            dt
        ) * z
        # Poisson jump count for the interval (small dt -> at most one in practice)
        n = self._rng.poisson(self.jump_intensity * dt)
        if n > 0:
            jump = self._rng.normal(self.jump_mean, self.jump_std, size=n).sum()
            log_step += jump
        self._price *= math.exp(log_step)
        return self._price


class PrecomputedPath(PriceProcess):
    """A price process whose path is precomputed and stepped through.

    Used so informed traders can peek into the *actual* future price (not
    a parallel ghost path). Wraps any base PriceProcess at construction:
    we run the base for `n_steps` of `dt` and cache the path; subsequent
    `step(dt)` calls advance through the cache deterministically.
    """

    def __init__(self, base: PriceProcess, dt: float, n_steps: int) -> None:
        super().__init__(base.price, base._rng)
        self._dt = dt
        # Generate the full path
        self._path: list[float] = [base.price]
        for _ in range(n_steps):
            self._path.append(base.step(dt))
        self._idx = 0

    def step(self, dt: float) -> float:
        # dt must match the precompute dt
        self._idx += 1
        if self._idx >= len(self._path):
            self._price = self._path[-1]
            return self._price
        self._price = self._path[self._idx]
        return self._price

    def future_price(self, future_t: float) -> float:
        idx = round(future_t / self._dt)
        idx = max(0, min(len(self._path) - 1, idx))
        return self._path[idx]

    def apply_jump(self, log_jump: float) -> None:
        """Apply a log-jump from the current index forward. Mutates the cached path."""
        import math

        mult = math.exp(log_jump)
        for i in range(self._idx, len(self._path)):
            self._path[i] *= mult
        self._price = self._path[self._idx]


def make_process(cfg: MarketConfig, rng: Generator) -> PriceProcess:
    if cfg.process == "gbm":
        return GBM(cfg.initial_price, cfg.sigma_true, cfg.drift, rng)
    if cfg.process == "ou":
        if cfg.ou_mean is None or cfg.ou_kappa is None:
            raise ValueError("OU requires ou_mean and ou_kappa")
        return OU(
            cfg.initial_price,
            cfg.sigma_true,
            cfg.ou_kappa,
            cfg.ou_mean,
            rng,
        )
    if cfg.process == "jump_diffusion":
        if cfg.jump_intensity is None or cfg.jump_mean is None or cfg.jump_std is None:
            raise ValueError("jump_diffusion requires jump_intensity, jump_mean, jump_std")
        return JumpDiffusion(
            cfg.initial_price,
            cfg.sigma_true,
            cfg.drift,
            cfg.jump_intensity,
            cfg.jump_mean,
            cfg.jump_std,
            rng,
        )
    raise ValueError(f"unknown process: {cfg.process}")


def realised_vol_window(prices: np.ndarray, dt: float) -> float:
    """Realised vol per sqrt(second) from a price array sampled every dt seconds."""
    if len(prices) < 2:
        return 0.0
    log_returns = np.diff(np.log(prices))
    return float(np.std(log_returns, ddof=1) / math.sqrt(dt))
