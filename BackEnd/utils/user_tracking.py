"""User account tracking schema — single source of truth.

Defines the shape and defaults for the per-user `record` and `archetypes`
sub-documents on the `users` collection, plus the pure helpers that recompute
their derived fields. Every place that touches these structures (signup
defaults, the backfill migration, the per-game commit in finalize_game, and the
/api/auth/me serializer) should build them from here so the shape can never
drift across call sites.

See `_documentation_master/projects/User_Archetype_System.md` for the spec.
"""

from __future__ import annotations

# Canonical ordered list of the 18 coaching archetypes (matches the spec doc).
# `archetypes.total` is a derived 19th field (sum of these), not in this tuple.
ARCHETYPE_KEYS: tuple[str, ...] = (
    "pure_offense",
    "pure_defense",
    "od_balance",
    "rebounding_king",
    "the_intimidator",
    "mr_fundamentals",
    "outrun_the_competition",
    "cerebral_offense",
    "cerebral_defense",
    "pure_athleticism",
    "pure_discipline",
    "offensive_athleticism",
    "defensive_athleticism",
    "offensive_fundamentals",
    "defensive_fundamentals",
    "offensive_rebounding",
    "defensive_rebounding",
    "mr_unconventional",
)


def default_record() -> dict:
    """A fresh `record` sub-document, all counters zeroed.

    `total_games` and `win_rate` are derived (see `recompute_record_derived`);
    they start at 0 and are recomputed on every write. `discount_wins` /
    `discount_losses` are tracked separately (wiring deferred — see the plan).
    """
    return {
        "wins": 0,
        "losses": 0,
        "total_games": 0,
        "win_rate": 0,
        "discount_wins": 0,
        "discount_losses": 0,
    }


def default_archetypes() -> dict:
    """A fresh `archetypes` sub-document: every archetype at 0 plus `total` (0)."""
    archetypes = {key: 0 for key in ARCHETYPE_KEYS}
    archetypes["total"] = 0
    return archetypes


def default_user_tracking() -> dict:
    """The full tracking block to merge onto a user doc (signup + backfill)."""
    return {
        "record": default_record(),
        "archetypes": default_archetypes(),
    }


def recompute_record_derived(record: dict) -> dict:
    """Return `record` with `total_games` and `win_rate` recomputed from
    `wins`/`losses`, so the derived fields can never drift out of sync.

    - total_games = wins + losses
    - win_rate    = round(100 * wins / total_games) when total_games > 0, else 0
    """
    wins = int(record.get("wins", 0) or 0)
    losses = int(record.get("losses", 0) or 0)
    total_games = wins + losses
    record["total_games"] = total_games
    record["win_rate"] = round(100 * wins / total_games) if total_games > 0 else 0
    return record


def recompute_archetypes_total(archetypes: dict) -> dict:
    """Return `archetypes` with `total` recomputed as the sum of the 18 keys."""
    archetypes["total"] = sum(int(archetypes.get(key, 0) or 0) for key in ARCHETYPE_KEYS)
    return archetypes
