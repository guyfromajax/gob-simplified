"""Per-test seeding for every RNG stream the suite can reach.

WHY
---
``BackEnd/utils/sim_random.py`` seeds ``sim_rng`` once from OS entropy and then
advances it as one continuous stream. A full-suite run is reproducible only by
accident — same order, same draws — and any subset run is not. Measured before this
module existed, five identical runs of ``test_motion_dynamic_resolver.py``,
``test_motion_moment.py`` and ``test_setplay_dynamic_resolver.py`` failed 6, 9, 6, 5
and 8 tests. That makes ``tests/baseline_failures.txt`` useless as a gate for anything
short of the whole suite, and blind in exactly the files where engine work lands.

Seeding per test — rather than once per session — is what buys subset reproducibility:
a test's stream position stops depending on how many tests ran before it.

EVERY STREAM, NOT JUST sim_rng
------------------------------
There are four, and pinning fewer leaves the suite non-deterministic:

* the stdlib ``random`` module — ``populate_team_plays`` and ``populate_scouting_data``
  in ``BackEnd/api/gameplan_routes.py`` do a function-local ``import random`` and draw
  straight from it. ``training_random``'s docstring records that as deliberate, not an
  oversight. Third-party code shares this stream too: pymongo's ``bulk_write`` consumes
  it even when it matches zero documents.
* ``sim_random.sim_rng`` — the engine.
* ``sim_random.announcement_rng`` — presentation copy, a separate instance. Reseeded for
  free: ``sim_random.seed()`` pins it at a fixed offset from the sim seed.
* ``training_random.training_rng`` — training, deliberately not shared with the sim.

Three more sites build a throwaway ``random.Random()`` *inside* a function
(``pgpc_selection.py:70``, ``api/press_conference_routes.py:118``,
``recruiting_report_news.py:126``). Those self-seed from OS entropy and no fixture can
reach them; two of the three accept an injected ``rng`` instead. They are not reachable
from the tests this suite runs — determinism is verified empirically, so if that ever
stops being true the three-run check below is what will catch it.

PYTHONHASHSEED
--------------
Hash-order determinism is a separate axis and is NOT handled here. Set it in the
environment if you need it::

    PYTHONHASHSEED=0 python -m pytest ...

Do NOT call ``BackEnd.utils.repro.pin_hash_seed()`` from conftest or from anything
conftest imports. It re-executes the interpreter via ``os.execve`` (repro.py:115), and
a module-scope call to it in ``scripts/verify_deploy.py`` silently replaced the running
pytest process for 18 days — sessions exited 0 with no output at all. See the
2026-09-04 UPDATE block in ``_documentation_master/projects/bugs.md``.
"""

from __future__ import annotations

import hashlib
import random as _stdlib_random

from BackEnd.utils import sim_random, training_random

# Names are personalisation strings, not just labels: deriving each stream's seed from a
# different one keeps the streams from running in lockstep, which sharing a single seed
# would cause.
STREAMS = ("stdlib", "sim", "training")


def seed_for_nodeid(nodeid: str, stream: str) -> int:
    """A stable 64-bit seed for one (test, stream) pair.

    hashlib, never the builtin ``hash()``: Python randomises str hashing per process
    unless PYTHONHASHSEED is pinned, so a hash()-derived seed would differ between runs
    and reintroduce the exact non-determinism this module removes.
    """
    digest = hashlib.blake2b(
        f"{nodeid}\x00{stream}".encode("utf-8"), digest_size=8
    ).digest()
    return int.from_bytes(digest, "big")


def seed_all_streams(nodeid: str) -> None:
    """Pin all four streams for one test."""
    _stdlib_random.seed(seed_for_nodeid(nodeid, "stdlib"))
    # Also reseeds announcement_rng, at sim_seed + 1_000_003.
    sim_random.seed(seed_for_nodeid(nodeid, "sim"))
    training_random.seed(seed_for_nodeid(nodeid, "training"))
