"""
Dedicated RNG for the training system.

WHY THIS EXISTS
---------------
Training used to draw from the global ``random`` module — the same stream
``pymongo`` draws from. ``bulk_write`` consumes the global stream even when it
matches **zero documents**, so unrelated database activity shifted training
results. Measured on a 12-man roster over 4 weeks with an identical seed: adding
a single no-op ``bulk_write`` before training changed the attributes of **all 12
players** (e.g. RB 17 -> 14, SH 69 -> 71).

Because the amount of DB work in the franchise training path varies run to run,
training was **unreproducible in practice** even though it is deterministic in
isolation. A seeded training run could not be replayed.

This is the same defect, and the same fix, as ``BackEnd/utils/sim_random`` —
but a SEPARATE stream, deliberately. Training runs concurrently with simulation
(a franchise week sims games and trains teams), so sharing ``sim_rng`` would
reintroduce exactly the cross-subsystem coupling both modules exist to remove:
a change in the number of games simmed would shift training outcomes.

USAGE
-----
Training modules bind this in place of the stdlib module, so call sites are
unchanged::

    from BackEnd.utils.training_random import training_rng as random
    ...
    random.randint(1, 100)   # same call surface, isolated stream

Converted modules: ``models/training_execution_v2.py``, ``models/training_notes.py``,
``models/training_manager.py``.

NOT CONVERTED, deliberately: ``populate_team_plays`` / ``populate_scouting_data``
in ``api/gameplan_routes.py`` (function-local ``import random`` at lines 572 and
879). They seed play effectiveness/momentum/cloaking at franchise and game
CREATION and are not called anywhere in the training path — ``run_franchise_training``
contains no call to either. They belong to whatever stream game setup eventually
owns, not to this one.

Unseeded, this instance seeds itself from OS entropy just like the global module,
so production behaviour is statistically unchanged.
"""

from __future__ import annotations

import random as _stdlib_random

# The training stream. Unseeded => OS entropy, same as the global module.
training_rng = _stdlib_random.Random()


def seed(value: int | None) -> None:
    """Seed the training stream. No-op when ``value`` is None (production)."""
    if value is not None:
        training_rng.seed(value)


def getstate():
    """Snapshot the training stream (diagnostics / draw-count probes)."""
    return training_rng.getstate()


def setstate(state) -> None:
    training_rng.setstate(state)
