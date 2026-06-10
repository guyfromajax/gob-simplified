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
    `discount_losses` track completed games that used Sim Full Game or Sim Rest
    of Game.
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
    """The full tracking block to merge onto a user doc (signup + backfill).

    `lead_archetype` is the denormalized "highest count" key the UI reads to pick
    the coach's badge ("" until they have games). `archetype_reveal_seen` gates the
    one-time first-archetype reveal modal (false → eligible to see it).

    Alpha-feedback fields gate the alpha survey + its post-game prompt modal:
      `alpha_feedback_submitted` — true once the user submits the 12-question survey.
      `alpha_feedback_games`     — FORWARD-ONLY counter of non-tutorial games completed
                                   after this feature shipped (incremented in
                                   commit_user_game_record). Starts at 0 for everyone,
                                   so existing veterans are only prompted after playing
                                   new games — never reuse record.total_games here.
      `alpha_feedback_prompt_level` — highest prompt threshold already shown (0 / 4 / 8; 2 / 5 legacy),
                                   so each modal variant fires once.

    Tutorial-alert fields gate the contextual Sammy modals + nav glow:
      `tutorial_alerts_franchise_id`   — first franchise instance alerts apply to (never changes).
      `tutorial_alerts_dismissed`      — alert ids whose modal was shown (once per user).
      `tutorial_alerts_games`          — games completed on the locked franchise since enrollment.
      `tutorial_alerts_training_returns` — FCC returns after training on the locked franchise.
    """
    return {
        "record": default_record(),
        "archetypes": default_archetypes(),
        "lead_archetype": "",
        "archetype_reveal_seen": False,
        "alpha_feedback_submitted": False,
        "alpha_feedback_games": 0,
        "alpha_feedback_prompt_level": 0,
        "tutorial_alerts_franchise_id": None,
        "tutorial_alerts_dismissed": [],
        "tutorial_alerts_games": 0,
        "tutorial_alerts_training_returns": 0,
    }


TUTORIAL_ALERT_IDS: tuple[str, ...] = (
    "player-attributes",
    "training",
    "team-attributes",
    "game-plans",
    "playbooks",
    "scouting",
    "recruiting",
)


def compute_lead_archetype(archetypes: dict, recent_keys: list | None = None) -> str:
    """The archetype key with the highest count (ignoring `total`).

    Returns "" when every count is 0. Ties are broken by *most recently
    incremented*: pass `recent_keys` (this game's archetypes in chronological
    order) and the latest tied key wins; otherwise the canonical-order first wins.
    """
    counts = {k: int(archetypes.get(k, 0) or 0) for k in ARCHETYPE_KEYS}
    max_count = max(counts.values()) if counts else 0
    if max_count <= 0:
        return ""
    maxed = [k for k in ARCHETYPE_KEYS if counts[k] == max_count]
    if len(maxed) == 1:
        return maxed[0]
    for key in reversed(recent_keys or []):
        if key in maxed:
            return key
    return maxed[0]


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
