"""Pydantic models for every event, state object, and config in mm_sim.

These are the canonical types exchanged between the engine, results writer,
runner, and websocket server. The frontend mirrors these in TypeScript.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Side(StrEnum):
    BID = "bid"
    ASK = "ask"


class CounterpartyType(StrEnum):
    NOISE = "noise"
    INFORMED = "informed"
    MM = "mm"


class CounterpartyId(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    type: CounterpartyType


# --- Sim events ---------------------------------------------------------------


class TickEvent(BaseModel):
    t: float
    true_mid: float
    realised_vol: float


class OrderEvent(BaseModel):
    t: float
    cp: CounterpartyId
    side: Side
    price: float | None  # None = market order
    size: float
    order_id: str


class CancelEvent(BaseModel):
    t: float
    order_id: str


class FillEvent(BaseModel):
    t: float
    maker_cp: CounterpartyId
    taker_cp: CounterpartyId
    side: Side  # Side from MAKER's perspective
    price: float
    size: float
    mid_at_fill: float
    maker_order_id: str


class QuoteUpdate(BaseModel):
    t: float
    bid_price: float
    bid_size: float
    ask_price: float
    ask_size: float
    reservation_price: float
    half_spread: float
    inventory: float
    sigma_est: float
    gamma: float
    interventions_active: list[str]


# --- L2 snapshot --------------------------------------------------------------


class L2Level(BaseModel):
    price: float
    size: float


class L2Snapshot(BaseModel):
    t: float
    bids: list[L2Level]
    asks: list[L2Level]
    mid: float


class MMState(BaseModel):
    t: float
    inventory: float
    cash: float
    realised_pnl: float
    unrealised_pnl: float
    total_pnl: float
    fills_total: int
    quote_uptime_pct: float
    sigma_est: float
    active_interventions: list[str]


# --- WebSocket envelope -------------------------------------------------------


class WsMessage(BaseModel):
    seq: int
    kind: Literal["snapshot", "fill", "quote_update", "metric_tick", "scenario_event", "log"]
    payload: dict[str, Any]


# --- Configs ------------------------------------------------------------------


class MarketConfig(BaseModel):
    process: Literal["gbm", "ou", "jump_diffusion"] = "gbm"
    sigma_true: float = 0.01  # per sqrt(second)
    drift: float = 0.0
    initial_price: float = 100.0
    # OU-only:
    ou_mean: float | None = None
    ou_kappa: float | None = None
    # jump-diffusion only:
    jump_intensity: float | None = None
    jump_mean: float | None = None
    jump_std: float | None = None


class NoiseTraderConfig(BaseModel):
    count: int = 16
    arrival_rate_hz: float = 5.0  # per trader
    limit_fraction: float = 0.7  # 70% of orders are limits, rest market
    cancel_halflife_s: float = 30.0
    size_mean: float = 1.0
    size_std: float = 0.3
    price_offset_std_bps: float = 25.0  # wider than MM spread so MM can be inside


class InformedTraderConfig(BaseModel):
    count: int = 0
    arrival_rate_hz: float = 1.0
    lookahead_min_s: float = 1.0
    lookahead_max_s: float = 30.0
    signal_noise_std: float = 0.5  # smaller -> sharper signal -> higher hit rate
    target_hit_rate: float = 0.575  # for reporting only
    size_mean: float = 1.0
    market_order_fraction: float = 0.5


class CounterpartiesConfig(BaseModel):
    noise: NoiseTraderConfig = NoiseTraderConfig()
    informed: InformedTraderConfig = InformedTraderConfig()


class SigmaEstimatorConfig(BaseModel):
    type: Literal["ewma", "cheat"] = "ewma"
    halflife_s: float = 60.0


class SpreadCaps(BaseModel):
    min: float = 0.0001
    max: float = 0.1


class QuoterConfig(BaseModel):
    type: Literal["avellaneda_stoikov"] = "avellaneda_stoikov"
    gamma: float = 0.1
    k: float = 10.0  # AS rent-term slope; tuned so default spread ~5-10 bps on $100 mid
    tau: float = 300.0
    quote_size: float = 1.0
    refresh_ms: float = 100.0
    inventory_limit: float = 100.0
    spread_caps: SpreadCaps = SpreadCaps()
    sigma_estimator: SigmaEstimatorConfig = SigmaEstimatorConfig()
    # sweep helpers — runner expands:
    gamma_sweep: list[float] | None = None


class InterventionConfig(BaseModel):
    """Intervention enable flags. Each is independently switchable per D5/spec."""

    adaptive_spread: bool = False
    kill_switch: bool = False
    hedge_on_threshold: bool = False
    news_detector: bool = False
    per_counterparty_penalty: bool = False
    # tuning
    adaptive_spread_mult_per_vol: float = 1.0
    kill_switch_inventory_pct: float = 0.9
    hedge_threshold_pct: float = 0.7
    news_detector_jump_bps: float = 50.0
    cp_penalty_decay_halflife_s: float = 600.0


class ScenarioEventKind(StrEnum):
    SELLOFF = "selloff"
    BUYIN = "buyin"
    NEWSSPIKE = "newsspike"
    LIQWITHDRAW = "liqwithdraw"
    TOXICBURST = "toxicburst"
    LATENCY_SPIKE = "latency_spike"
    VOL_REGIME = "vol_regime"


class ScenarioEvent(BaseModel):
    at_seconds: float
    kind: ScenarioEventKind
    params: dict[str, Any] = Field(default_factory=dict)


class ExperimentConfig(BaseModel):
    """A single, fully-resolved experiment. The runner expands sweeps into many of these."""

    id: str
    finding: int = 0
    description: str = ""
    seed: int = 42
    duration_seconds: float = 14400.0  # 4 hours
    market: MarketConfig = MarketConfig()
    counterparties: CounterpartiesConfig = CounterpartiesConfig()
    quoter: QuoterConfig = QuoterConfig()
    interventions: InterventionConfig = InterventionConfig()
    events: list[ScenarioEvent] = Field(default_factory=list)
    output_path: str = "results/unspecified"
    # bookkeeping for sweep variants
    sweep_label: str | None = None


class RunMetadata(BaseModel):
    experiment_id: str
    sweep_label: str | None
    seed: int
    started_at_utc: str
    finished_at_utc: str
    wall_seconds: float
    sim_engine_version: str
