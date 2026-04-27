"""Single source of randomness, keyed by seed.

All randomness in the engine derives from a top-level seed via numpy SeedSequence.
Each consumer (market generator, each trader, etc.) gets its own independent
Generator spawned from the parent. This makes seed-level reproducibility hold
even when consumer counts change between experiments.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.random import Generator, SeedSequence


@dataclass(frozen=True)
class RngFactory:
    seed: int

    def child(self, *names: str | int) -> Generator:
        """Spawn an independent Generator deterministically from a name path.

        Example: rng.child("market") and rng.child("trader", "noise_03") will
        always return the same Generator for the same factory seed, regardless
        of call order or how many other children have been spawned.
        """
        ss = SeedSequence(
            entropy=self.seed,
            spawn_key=tuple(_to_int(n) for n in names),
        )
        return np.random.default_rng(ss)


def _to_int(name: str | int) -> int:
    if isinstance(name, int):
        return name
    # Stable hash of the name into a 32-bit int
    h = 2166136261
    for ch in name:
        h = (h ^ ord(ch)) * 16777619
        h &= 0xFFFFFFFF
    return h
