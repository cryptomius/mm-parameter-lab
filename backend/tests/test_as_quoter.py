"""Avellaneda-Stoikov quoter sanity checks."""

from __future__ import annotations

import math

import pytest

from mm_sim.quoter.avellaneda_stoikov import AvellanedaStoikov


def test_zero_inventory_centered() -> None:
    q = AvellanedaStoikov(gamma=0.1, k=1.5, tau=300, spread_min=0, spread_max=1)
    quote = q.quote(mid=100.0, inventory=0.0, sigma=0.001)
    assert quote.reservation_price == pytest.approx(100.0)
    assert quote.bid_price < 100.0 < quote.ask_price


def test_positive_inventory_shifts_quotes_down() -> None:
    q = AvellanedaStoikov(gamma=0.1, k=1.5, tau=300, spread_min=0, spread_max=1)
    flat = q.quote(mid=100.0, inventory=0.0, sigma=0.001)
    long = q.quote(mid=100.0, inventory=10.0, sigma=0.001)
    # Reservation price moves below mid when long
    assert long.reservation_price < flat.reservation_price
    assert long.bid_price < flat.bid_price
    assert long.ask_price < flat.ask_price


def test_higher_sigma_widens_spread() -> None:
    q = AvellanedaStoikov(gamma=0.1, k=1.5, tau=300, spread_min=0, spread_max=1)
    a = q.quote(mid=100.0, inventory=0.0, sigma=0.001)
    b = q.quote(mid=100.0, inventory=0.0, sigma=0.005)
    assert b.half_spread > a.half_spread


def test_higher_gamma_shifts_reservation_more() -> None:
    # Higher gamma always shifts reservation price more (linear in gamma).
    # Half-spread direction depends on whether inv-risk or rent term dominates.
    qa = AvellanedaStoikov(gamma=0.1, k=1.5, tau=300, spread_min=0, spread_max=1)
    qb = AvellanedaStoikov(gamma=1.0, k=1.5, tau=300, spread_min=0, spread_max=1)
    a = qa.quote(mid=100.0, inventory=5.0, sigma=0.001)
    b = qb.quote(mid=100.0, inventory=5.0, sigma=0.001)
    assert b.reservation_price < a.reservation_price


def test_higher_gamma_widens_spread_when_invrisk_dominates() -> None:
    # With high sigma the inventory-risk term dominates and gamma↑ widens spread.
    qa = AvellanedaStoikov(gamma=0.1, k=1.5, tau=300, spread_min=0, spread_max=1)
    qb = AvellanedaStoikov(gamma=1.0, k=1.5, tau=300, spread_min=0, spread_max=1)
    a = qa.quote(mid=100.0, inventory=0.0, sigma=0.05)
    b = qb.quote(mid=100.0, inventory=0.0, sigma=0.05)
    assert b.half_spread > a.half_spread


def test_formula_matches_hand_computation() -> None:
    gamma, k, tau, sigma, mid, q_inv = 0.5, 1.0, 100.0, 0.01, 100.0, 2.0
    q = AvellanedaStoikov(gamma=gamma, k=k, tau=tau, spread_min=0, spread_max=1)
    quote = q.quote(mid=mid, inventory=q_inv, sigma=sigma)
    expected_res = mid - q_inv * gamma * sigma * sigma * tau
    expected_half = (gamma * sigma * sigma * tau) / 2 + (1 / gamma) * math.log1p(gamma / k)
    assert quote.reservation_price == pytest.approx(expected_res)
    assert quote.half_spread == pytest.approx(expected_half)


def test_q_target_shifts_skew_origin() -> None:
    # With q_target=10 and inventory=10, the skew should be zero (quotes centered on mid).
    q = AvellanedaStoikov(
        gamma=0.5, k=1.5, tau=300, spread_min=0, spread_max=1, q_target=10.0
    )
    quote = q.quote(mid=100.0, inventory=10.0, sigma=0.01)
    assert quote.reservation_price == pytest.approx(100.0)


def test_q_target_identity_with_zero_inventory() -> None:
    # q_target=-30 with inventory=0 should match q_target=0 with inventory=+30
    # (mathematical identity: r = mid - (q - q_target) * γ * σ² * τ).
    q1 = AvellanedaStoikov(
        gamma=0.5, k=1.5, tau=300, spread_min=0, spread_max=1, q_target=-30.0
    )
    q2 = AvellanedaStoikov(
        gamma=0.5, k=1.5, tau=300, spread_min=0, spread_max=1, q_target=0.0
    )
    a = q1.quote(mid=100.0, inventory=0.0, sigma=0.01)
    b = q2.quote(mid=100.0, inventory=30.0, sigma=0.01)
    assert a.reservation_price == pytest.approx(b.reservation_price)
    assert a.bid_price == pytest.approx(b.bid_price)
    assert a.ask_price == pytest.approx(b.ask_price)


def test_asymmetric_factors_are_stored_not_applied_in_quote() -> None:
    # The AS quoter stores the factors but emits a SYMMETRIC quote — the
    # engine applies them after the intervention pipeline.
    q = AvellanedaStoikov(
        gamma=0.5,
        k=1.5,
        tau=300,
        spread_min=0,
        spread_max=1,
        bid_widening_factor=2.0,
        ask_widening_factor=0.5,
    )
    quote = q.quote(mid=100.0, inventory=0.0, sigma=0.01)
    assert q.bid_widening_factor == 2.0
    assert q.ask_widening_factor == 0.5
    # Symmetric: |bid - res| == |ask - res|
    assert quote.reservation_price - quote.bid_price == pytest.approx(
        quote.ask_price - quote.reservation_price
    )
