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
