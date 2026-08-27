"""
Dedicated RNG for the simulation engine.

WHY THIS EXISTS
---------------
The sim used to draw from the global ``random`` module — the same stream every
other library in the process draws from. That made game outcomes depend on
unrelated activity. Measured concretely: ``pymongo``'s ``bulk_write`` consumes
the global stream (``find_one`` does not), so a Mongo write that matched **zero
documents** still shifted the basketball. Under a fixed seed, adding or removing
a DB write changed final scores.

Engine randomness now comes from this dedicated instance. Third-party libraries
keep the global module, so their draws can no longer perturb a game.

USAGE
-----
Sim modules bind this in place of the stdlib module, so call sites are unchanged::

    from BackEnd.utils.sim_random import sim_rng as random
    ...
    random.randint(1, 100)   # same call surface, isolated stream

``random.Random`` exposes every method the engine uses (randint, choice, choices,
uniform, shuffle, sample, random, gauss, getrandbits, getstate/setstate, seed).

WHY A PLAIN INSTANCE, NOT A THREAD-LOCAL PROXY
----------------------------------------------
A proxy forwarding via ``__getattr__`` would give per-thread streams (and so
reproducibility under ``--workers > 1``), but it measured **+30%** per draw
against the module baseline. The engine makes ~82k draws per game, so that cost
is real. A plain instance is +1.7% (noise) because the stdlib's module-level
functions are themselves bound methods of a hidden module-level ``Random``.

Consequence: threads still share this stream, exactly as they shared the global
one. Seeded reproducibility therefore still requires single-threaded execution
(``perf_sim_baseline.py --workers 1``), which is unchanged from before.

Unseeded, this instance seeds itself from OS entropy just like the global module,
so production behavior is statistically unchanged.
"""

from __future__ import annotations

import random as _stdlib_random

# The engine's stream. Unseeded => OS entropy, same as the global module.
sim_rng = _stdlib_random.Random()

# Presentation stream — announcement copy, flavor text, and other cosmetic
# choices that must never perturb gameplay.
#
# These draws are decided backend-side (UESS: the frontend renders, it does not
# choose), but they are not gameplay. Sharing `sim_rng` would mean that adding a
# foul-language variant shifts every subsequent basketball outcome — the exact
# coupling this module exists to eliminate, just one layer up. Keeping copy on
# its own stream means presentation changes are provably outcome-neutral.
announcement_rng = _stdlib_random.Random()


def seed(value: int | None) -> None:
    """Seed the simulation stream. No-op when ``value`` is None (production).

    Also seeds the presentation stream (offset, so the two streams never run in
    lockstep) to keep seeded replays byte-identical including announcements.
    """
    if value is not None:
        sim_rng.seed(value)
        announcement_rng.seed(value + 1_000_003)


def getstate():
    """Snapshot the sim stream (diagnostics / draw-count probes)."""
    return sim_rng.getstate()


def setstate(state) -> None:
    sim_rng.setstate(state)


# ---------------------------------------------------------------------------
# Global-draw guard
# ---------------------------------------------------------------------------
# The engine must draw ONLY from `sim_rng`. The module conversion was proven
# against the code paths the verification weeks actually exercised — a draw site
# on a rare branch (overtime, ejections, edge events) could still be bound to the
# global module and would surface much later as an intermittent byte-identical
# failure with no obvious cause.
#
# This guard wraps the stdlib module's draw functions and records any call whose
# immediate caller lives under `BackEnd`. Verification runs assert the tally is
# empty (scripts/perf_sim_baseline.py), so a stray site fails loudly and names
# itself — file, function and line — the first time it fires.
#
# Cost is negligible: after conversion the engine's ~82k draws/game go to
# `sim_rng`, which is NOT wrapped. Only third-party draws (pymongo) reach these
# wrappers, and those are rare.

_GLOBAL_DRAWS: dict[str, int] = {}
_guard_installed = False
_guard_log_only = False

_GUARDED_FNS = (
    "random", "randint", "choice", "choices", "shuffle", "uniform", "sample",
    "gauss", "normalvariate", "betavariate", "triangular", "randrange",
    "getrandbits", "expovariate", "lognormvariate", "vonmisesvariate",
    "paretovariate", "weibullvariate", "randbytes",
)


def install_global_draw_guard(log_only: bool = False) -> None:
    """Start recording BackEnd-attributed draws on the GLOBAL module. Idempotent.

    ``log_only=True`` is the PRODUCTION mode: each offending call site is logged
    once at ERROR with its ``module:function:lineno`` and nothing else happens.
    It never raises and never alters a draw — a stray site costs reproducibility,
    not correctness, and is not worth failing a live game over. Verification runs
    use the default, where the harness asserts the tally is empty.
    """
    global _guard_installed, _guard_log_only
    _guard_log_only = log_only
    if _guard_installed:
        return
    _guard_installed = True

    import functools
    import inspect
    import logging

    _log = logging.getLogger(__name__)

    for _name in _GUARDED_FNS:
        _fn = getattr(_stdlib_random, _name, None)
        if _fn is None or getattr(_fn, "__gob_guarded__", False):
            continue

        def _make(fn=_fn):
            @functools.wraps(fn)
            def wrapper(*a, **k):
                try:
                    frame = inspect.currentframe().f_back
                    mod = frame.f_globals.get("__name__", "")
                    if mod.startswith("BackEnd") and mod != __name__:
                        key = f"{mod}:{frame.f_code.co_name}:{frame.f_lineno}"
                        seen = _GLOBAL_DRAWS.get(key, 0)
                        _GLOBAL_DRAWS[key] = seen + 1
                        # Log-only (production): report each site ONCE. Never raise —
                        # a stray draw costs reproducibility, not correctness, and is
                        # not worth failing a live game over.
                        if _guard_log_only and seen == 0:
                            _log.error(
                                "🎲 [RNG LEAK] %s drew from the GLOBAL random module. "
                                "Engine code must use `from BackEnd.utils.sim_random "
                                "import sim_rng as random` — this site is not isolated "
                                "from third-party RNG (e.g. pymongo) and breaks seeded "
                                "reproducibility.", key)
                except Exception:
                    pass
                return fn(*a, **k)

            wrapper.__gob_guarded__ = True
            return wrapper

        setattr(_stdlib_random, _name, _make())


def global_draw_report() -> dict[str, int]:
    """``{'module:function:lineno': count}`` of BackEnd draws that escaped to the global module."""
    return dict(_GLOBAL_DRAWS)


def reset_global_draw_guard() -> None:
    _GLOBAL_DRAWS.clear()
