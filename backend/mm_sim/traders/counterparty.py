"""Counterparty pool: stable IDs across the simulation.

A run pre-allocates N noise IDs and M informed IDs. IDs are deterministic
("noise_00"..."noise_15", "informed_00"..."informed_03") so per-CP metrics
keyed by ID are comparable across runs at the same seed.
"""

from __future__ import annotations

from mm_sim.types import CounterpartyId, CounterpartyType, CounterpartiesConfig

MM_CP_ID = "mm"


def mm_counterparty() -> CounterpartyId:
    return CounterpartyId(id=MM_CP_ID, type=CounterpartyType.MM)


def build_counterparties(cfg: CounterpartiesConfig) -> tuple[list[CounterpartyId], list[CounterpartyId]]:
    """Returns (noise_cps, informed_cps)."""
    noise = [
        CounterpartyId(id=f"noise_{i:02d}", type=CounterpartyType.NOISE)
        for i in range(cfg.noise.count)
    ]
    informed = [
        CounterpartyId(id=f"informed_{i:02d}", type=CounterpartyType.INFORMED)
        for i in range(cfg.informed.count)
    ]
    return noise, informed
