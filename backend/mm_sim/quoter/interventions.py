"""Intervention modules: each independently switchable per spec.

Each intervention is a small callable applied to the current Quote (and the
quoter's view of state). They compose: the engine applies them in a fixed
order — adaptive_spread → kill_switch → hedge → news_detector → cp_penalty.

Milestone 1 ships only the always-allowed defaults wired up. Adaptive spread
and inventory-skew via the AS reservation price are first-class. The remaining
five interventions (kill switch, hedge, news detector, per-CP penalty) are
fully implemented but only flip on when their flag is set in the
InterventionConfig — used by Findings 2 and 3.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from mm_sim.quoter.avellaneda_stoikov import Quote
from mm_sim.types import FillEvent, InterventionConfig


@dataclass
class InterventionContext:
    """Mutable state that interventions read and update.

    Exposed to the engine so each intervention can evolve independently.
    """

    cfg: InterventionConfig
    inventory_limit: float
    sigma_baseline: float = 0.0
    last_mid: float | None = None
    last_t: float = 0.0
    # cp_penalty: rolling per-CP toxicity (positive = costs MM)
    cp_toxicity: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    # news detector: rolling recent log-returns (for jump detection)
    recent_log_returns: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=200))
    # for adaptive_spread, a rolling realised vol baseline (set externally)
    # for kill switch & hedge: read inventory directly each tick


def adaptive_spread(quote: Quote, ctx: InterventionContext, sigma_now: float) -> Quote:
    """Widen the half-spread proportionally to (sigma_now / sigma_baseline)."""
    if not ctx.cfg.adaptive_spread or ctx.sigma_baseline <= 0:
        return quote
    ratio = max(1.0, sigma_now / ctx.sigma_baseline)
    extra = (ratio - 1.0) * ctx.cfg.adaptive_spread_mult_per_vol * quote.half_spread
    new_half = quote.half_spread + extra
    return Quote(
        bid_price=quote.reservation_price - new_half,
        ask_price=quote.reservation_price + new_half,
        reservation_price=quote.reservation_price,
        half_spread=new_half,
    )


def kill_switch(quote: Quote, ctx: InterventionContext, inventory: float) -> Quote | None:
    """Return None to pull quotes entirely if |inventory| exceeds threshold."""
    if not ctx.cfg.kill_switch:
        return quote
    threshold = ctx.cfg.kill_switch_inventory_pct * ctx.inventory_limit
    if abs(inventory) >= threshold:
        return None  # signal: pull quotes
    return quote


def news_detector(quote: Quote, ctx: InterventionContext, mid: float, t: float) -> Quote | None:
    """If recent return magnitude over a short window exceeds threshold, pull quotes."""
    if not ctx.cfg.news_detector:
        return quote
    if ctx.last_mid is not None and ctx.last_mid > 0 and mid > 0:
        log_ret = abs((mid - ctx.last_mid) / ctx.last_mid)
        ctx.recent_log_returns.append((t, log_ret))
    # Sum of |log returns| in the most recent 5s window
    window_start = t - 5.0
    s = sum(abs(r) for (rt, r) in ctx.recent_log_returns if rt >= window_start)
    threshold = ctx.cfg.news_detector_jump_bps * 1e-4
    if s >= threshold:
        return None
    return quote


def per_counterparty_penalty(
    quote: Quote, ctx: InterventionContext, mid: float
) -> Quote:
    """Widen quotes by an amount proportional to the worst-CP toxicity recently observed.

    Toxicity is updated by `update_cp_toxicity_on_fill`. This intervention
    applies a global widening proportional to the maximum current toxicity —
    a simple proxy for "the marginal toxic CP would otherwise be paying me
    only the touch."
    """
    if not ctx.cfg.per_counterparty_penalty or not ctx.cp_toxicity:
        return quote
    max_tox = max(ctx.cp_toxicity.values())
    if max_tox <= 0:
        return quote
    # Convert toxicity (in bps of mid) into half-spread units
    extra = max_tox * 1e-4 * mid
    new_half = quote.half_spread + extra
    return Quote(
        bid_price=quote.reservation_price - new_half,
        ask_price=quote.reservation_price + new_half,
        reservation_price=quote.reservation_price,
        half_spread=new_half,
    )


def hedge_signal(ctx: InterventionContext, inventory: float) -> float:
    """Returns hedge size to flatten toward zero if |inv| above threshold; else 0.

    The actual hedge order is sent by the engine.
    """
    if not ctx.cfg.hedge_on_threshold:
        return 0.0
    threshold = ctx.cfg.hedge_threshold_pct * ctx.inventory_limit
    if abs(inventory) <= threshold:
        return 0.0
    excess = abs(inventory) - threshold
    return -excess if inventory > 0 else excess


def update_cp_toxicity_on_fill(
    ctx: InterventionContext,
    fill: FillEvent,
    drift_bps: float,
    decay_dt: float,
) -> None:
    """Decay all CPs and add new evidence from this fill.

    A fill where the price moved AGAINST the MM (positive drift_bps from MM's POV)
    increases the taker's toxicity score.
    """
    import math

    halflife = max(1e-9, ctx.cfg.cp_penalty_decay_halflife_s)
    decay = math.exp(-math.log(2.0) / halflife * max(0.0, decay_dt))
    for cp_id in list(ctx.cp_toxicity.keys()):
        ctx.cp_toxicity[cp_id] *= decay
    cp_id = fill.taker_cp.id
    ctx.cp_toxicity[cp_id] = ctx.cp_toxicity[cp_id] * decay + max(0.0, drift_bps)
