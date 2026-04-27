"""Scenario action library.

Each scenario is a callable that mutates the engine state when invoked at
the scheduled time. Implemented as small functions that take an engine
handle (loosely typed via Protocol below) and parameter dict.
"""

from __future__ import annotations

from typing import Any, Protocol

from mm_sim.types import (
    CounterpartyId,
    CounterpartyType,
    OrderEvent,
    ScenarioEventKind,
    Side,
)


class ScenarioHandle(Protocol):
    """Surface of the engine that scenarios are allowed to touch."""

    sim_t: float

    def submit_external_order(self, order: OrderEvent) -> None: ...
    def adjust_noise_arrival_rate(self, multiplier: float, duration_s: float) -> None: ...
    def schedule_jump(self, log_jump: float) -> None: ...
    def adjust_informed_concentration(self, multiplier: float, duration_s: float) -> None: ...
    def schedule_latency_spike(self, extra_ms: float, duration_s: float) -> None: ...
    def schedule_vol_regime(self, sigma_multiplier: float, duration_s: float) -> None: ...


SCENARIO_BOT = CounterpartyId(id="scenario_bot", type=CounterpartyType.NOISE)


def apply(handle: ScenarioHandle, kind: ScenarioEventKind, params: dict[str, Any]) -> None:
    if kind is ScenarioEventKind.SELLOFF:
        size = float(params.get("size", 50.0))
        handle.submit_external_order(
            OrderEvent(
                t=handle.sim_t,
                cp=SCENARIO_BOT,
                side=Side.ASK,  # Aggressive seller -> hits bids
                price=None,
                size=size,
                order_id=f"selloff#{handle.sim_t:.3f}",
            )
        )
    elif kind is ScenarioEventKind.BUYIN:
        size = float(params.get("size", 50.0))
        handle.submit_external_order(
            OrderEvent(
                t=handle.sim_t,
                cp=SCENARIO_BOT,
                side=Side.BID,
                price=None,
                size=size,
                order_id=f"buyin#{handle.sim_t:.3f}",
            )
        )
    elif kind is ScenarioEventKind.NEWSSPIKE:
        log_jump = float(params.get("log_jump", 0.01))
        sigma_mult = float(params.get("sigma_mult", 3.0))
        duration = float(params.get("vol_duration_s", 60.0))
        handle.schedule_jump(log_jump)
        handle.schedule_vol_regime(sigma_mult, duration)
    elif kind is ScenarioEventKind.LIQWITHDRAW:
        mult = float(params.get("multiplier", 0.2))
        duration = float(params.get("duration_s", 120.0))
        handle.adjust_noise_arrival_rate(mult, duration)
    elif kind is ScenarioEventKind.TOXICBURST:
        mult = float(params.get("multiplier", 5.0))
        duration = float(params.get("duration_s", 60.0))
        handle.adjust_informed_concentration(mult, duration)
    elif kind is ScenarioEventKind.LATENCY_SPIKE:
        extra_ms = float(params.get("extra_ms", 500.0))
        duration = float(params.get("duration_s", 30.0))
        handle.schedule_latency_spike(extra_ms, duration)
    elif kind is ScenarioEventKind.VOL_REGIME:
        mult = float(params.get("multiplier", 2.0))
        duration = float(params.get("duration_s", 300.0))
        handle.schedule_vol_regime(mult, duration)
    else:  # pragma: no cover
        raise ValueError(f"unknown scenario kind: {kind}")
