"""Read-time normalization for the core-8 team attributes.

The STORED range of the core-8 team attributes is ±20 (`TEAM_ATTR_CLAMPS`, widened in
the EOG structural pass so teams spread instead of all railing at ±10). But every
in-game constant that consumes these attributes was tuned for the historical ±10
range. Rather than rescale ~27 constants individually — an incoherent mix where some
sites hard-clamp at ±10 (making the widening inert) and others double their swing —
every GAMEPLAY consumer reads the core-8 through `core8_gameplay()`, which maps the
stored ±20 back to a ±10 gameplay value (a straight halving).

Properties:
  * provably gameplay-neutral: a team stored at +20 plays like the old +10; teams now
    SPREAD across ±20 stored but their gameplay effect still spans ±10 — finer
    gradient, unchanged ceiling.
  * the ±10 hard clamps (rim_runner_fast_break, getback_selection) become harmless
    no-ops, because the normalized value never exceeds ±10.
  * one change keeps all constants (the 7 explicit range-dependent sites AND the ~20
    linear ones) correct at once.

═══════════════════════════════════════════════════════════════════════════════
THE RULE — every GAMEPLAY read of a core-8 attribute goes through core8_gameplay().
═══════════════════════════════════════════════════════════════════════════════
Not "every range-dependent read" — EVERY gameplay read, unconditionally. A core-8
attribute that is scaled in one HCO branch and read raw in another is incoherent
basketball. If you add a new gameplay consumer of any `CORE8_ATTRS` member, wrap it.
The only exceptions are the four RAW readers below.

RAW (never wrapped): DISPLAY, LOGGING, EOG progression, and TRAINING deltas read the
stored value directly. Only in-game resolution normalizes. `momentum_score` and
`rebound_modifier` are NOT core-8 and are never passed through here.

Functions that take an ALREADY-normalized value as a parameter mark it with a `_g`
suffix (e.g. `def_mod_g`, `offense_modifier_g`) so a new call site can't silently
feed a raw ±20 value into a ±10 contract.
"""

CORE8_ATTRS = frozenset({
    "offensive_efficiency",
    "defensive_efficiency",
    "fb_efficiency",
    "pt_efficiency",
    "fb_opp_modifier",
    "pt_opp_modifier",
    "fight",
    "discipline",
})


def core8_gameplay(value) -> float:
    """Map a stored core-8 attribute (±20) to its gameplay value (±10). Returns a
    float (so odd stored values yield the intended half-step gradient); int() consumers
    truncate as before. `None`/missing → 0.0."""
    return (value or 0) / 2.0
