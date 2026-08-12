"""
Reproducibility helpers for measurement harnesses.

PYTHONHASHSEED
--------------
Python randomises string hashing per process. That reaches simulation behaviour:
several code paths iterate sets or resolve ties in iteration order, so **two runs
of the same configuration produce different games**. Twelve such sites were found
and fixed (see ``_documentation_master/projects/bugs.md``) — the first divergence
between two hash worlds moved from draw 9,051 to 31,023 as they were fixed — but
divergence persists, and the remaining sites are subtler.

Measured spread on an UNCHANGED arm, 96 team-games, across three hash seeds:
points/team-game 69.22-70.58, FCP foul-outs/team-game 1.04-1.35. That is
comparable to the effects being measured, and it has produced three false
conclusions: a phantom test regression, "identity doesn't raise scoring", and
"damping cuts foul-outs".

Pinning works perfectly. The failure mode is not the dependency, it is
**"requires remembering"** — every one of those false results came from an
unpinned run. So harnesses pin themselves:

    from BackEnd.utils.repro import pin_hash_seed
    pin_hash_seed()          # must be the FIRST thing the harness does

THE RULE: ``pin_hash_seed()`` MUST BE THE FIRST THING A HARNESS DOES
--------------------------------------------------------------------
``PYTHONHASHSEED`` is read by the interpreter at startup, so it cannot be set
from inside a running process — ``pin_hash_seed`` **re-executes** the interpreter
with it set. The process restarts from ``argv``, which means:

    **Everything executed before the call runs TWICE.**

So it must come before any import or statement with a side effect:

===========================  ====================================================
side effect                  what running it twice costs
===========================  ====================================================
DB connections               two clients, two connection pools
file / directory creation    duplicate or clobbered output, doubled appends
logging setup                duplicate handlers, doubled log lines
network calls, API clients   duplicated requests
argparse with side effects   duplicated prompts or writes
expensive imports            the whole cost paid twice
===========================  ====================================================

This is not hypothetical. The first version of the harness preamble did
``from BackEnd.utils.repro import pin_hash_seed``, and ``BackEnd/utils/__init__``
imports ``stat_updater -> db`` — so every pinned harness opened a Mongo
connection, re-executed, and opened a second one. The fix was to load this module
**by path** so no package ``__init__`` runs:

    import os as _os, sys as _sys, importlib.util as _ilu
    _GOB_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    _sys.path.insert(0, _GOB_ROOT)
    _spec = _ilu.spec_from_file_location(
        "_gob_repro", _os.path.join(_GOB_ROOT, "BackEnd", "utils", "repro.py"))
    _repro = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_repro)
    _repro.pin_hash_seed()

Path-loading fixes today's case; **the rule is what prevents the next one.** If a
harness must do something before pinning, set ``PYTHONHASHSEED`` in the
environment when launching it instead, and skip the re-exec entirely.

REPLAY IS NOT YET POSSIBLE — hash pinning is necessary, not sufficient
----------------------------------------------------------------------
Pinning makes hash ORDER deterministic. It does **not** make a production game
replayable, because production passes ``seed_base=None`` and therefore never
seeds ``sim_rng`` at all — no per-game seed exists, let alone gets recorded. See
the "per-game seed is not persisted" ticket in ``projects/bugs.md``.

An explicit ``PYTHONHASHSEED`` in the environment is RESPECTED, not overridden —
deliberately varying it across runs is how you measure between-world spread. Only
the *unset* case is pinned, so an unpinned run becomes impossible while a
deliberately-varied one stays easy.

Production pins it too, in ``start.sh``, so live games are replayable going
forward.
"""

from __future__ import annotations

import os
import sys

DEFAULT_HASH_SEED = "0"
_REEXEC_GUARD = "GOB_HASH_PIN_REEXEC"


def hash_seed_is_pinned() -> bool:
    value = os.environ.get("PYTHONHASHSEED")
    return value not in (None, "", "random")


def pin_hash_seed(default: str = DEFAULT_HASH_SEED) -> str:
    """Ensure this process runs with a fixed PYTHONHASHSEED, re-executing if needed.

    Returns the seed in force. Respects an explicit value; pins only when unset.
    Raises if the re-exec did not take, so a harness fails loudly rather than
    silently producing another unpinned result.
    """
    if hash_seed_is_pinned():
        return os.environ["PYTHONHASHSEED"]

    if os.environ.get(_REEXEC_GUARD) == "1":
        raise RuntimeError(
            "pin_hash_seed(): re-exec did not take effect — PYTHONHASHSEED is still "
            "unset. Refusing to run unpinned; results would not be reproducible. "
            f"Re-run with PYTHONHASHSEED={default} set explicitly."
        )

    env = dict(os.environ)
    env["PYTHONHASHSEED"] = default
    env[_REEXEC_GUARD] = "1"
    os.execve(sys.executable, [sys.executable, *sys.argv], env)
    raise AssertionError("unreachable")  # pragma: no cover
