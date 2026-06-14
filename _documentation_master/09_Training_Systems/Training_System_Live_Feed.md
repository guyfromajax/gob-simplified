# Training System — Live Feed (**verified 2026-06-13**)

> Verified vs `BackEnd/utils/training_loading_highlights.py` — **highly accurate**. All routing rules match code: `_MAX_LINES = 36`, `_GENERIC_FRACTION = 0.25`, session/lead/combo weights `0.70 / 0.15 / 0.15`, no-combo = 70% session / 30% lead, combo gap rule `second > third + 3` (`_combo_archetype_from_ftd`), lead = highest FTD counter with `random.choice` tie-break, freshman ±4 vs default ±3 strict dead band (`_player_attr_delta_qualifies_for_feed`), one `COACHING_FOCUS_FLAVOR` line per build, breaks/scrimmages `> 0` gates, shot_threshold/rebound_modifier excluded. **Fixed:** team-drill report keys repointed to the canonical fields used in `_TEAM_ATTR_POOLS`.

All **loading-feed copy** lives in **`BackEnd/utils/training_feed_lines.py`**. This document describes **when** lines fire and **how** archetype routing works. Do not duplicate line lists here.

---

## Values and thresholds

Rules use the **final** attribute change after multipliers (same as elsewhere in training docs).

### Player drill attributes

SC, SH, ID, OD, PS, BH, RB, AG, ST, ND, FT, IQ

- **Positive copy:** change **strictly greater than** 3 (i.e. 3 does **not** qualify).
- **Negative copy:** change **strictly less than** -3 (i.e. -3 does **not** qualify).

**Freshman** (`year` on the player, normalized to lowercase in the training report): use a wider dead band — **positive** only if change is **strictly greater than** 4; **negative** only if **strictly less than** -4. (4 and -4 do not qualify.)

### Team drill attributes (report keys)

Track changes for these canonical `team_changes` keys (exact keys in `_TEAM_ATTR_POOLS`, `training_loading_highlights.py`):

- `offensive_efficiency` (offense install)
- `defensive_efficiency` (defense install)
- `fb_efficiency` (fast break install)
- `pt_efficiency` (press/trap install)
- `fb_opp_modifier` (fast break opponent modifier)
- `pt_opp_modifier` (press/trap opponent modifier)

Team-attribute changes use the **same strict ±3 dead band** as player attrs (a change of exactly ±3 does not qualify; `d > 3` → positive pool, `d < -3` → negative pool).

**Ignore for this feed:** anything tied to `shot_threshold` or `rebound_modifier` (per product direction; neither is in `_TEAM_ATTR_POOLS`).

Team lines use the **`TEAM_*`** pools in `training_feed_lines.py` (offense install, defense install, fast break install, press/trap install, scrimmages, breaks). Mapping from **which drill ran** → **which pool** is defined in code alongside the report shape.

### Breaks and scrimmages

- **Breaks:** include when breaks drill contribution / setting is **> 0** (copy from `TEAM_BREAKS_*`).
- **Scrimmages:** include when scrimmage contribution / setting is **> 0** (copy from `TEAM_SCRIMMAGES_*`).

### Player line shape

`{Player Name} {description}.`

- **Name:** player display name.
- **Description:** one string chosen from the archetype pool for that attribute and direction (fragments in `training_feed_lines.py` are written to follow the name).

---

## Archetype routing (FTD + session)

**Inputs**

1. **FTD archetype counts** — four integer counters on the user franchise team doc (`authoritarian`, `systems_coach`, `player_maximizer`, `culture_builder`). Used for **lead** and **combo** logic.
2. **Current training session focus archetype** — the archetype selected for **this** training submission. Used together with FTD for weighted voice selection (implemented in `BackEnd/utils/training_loading_highlights.py`).

**Randomness:** use normal **`random`** for tie-breaks, line picks from pools, and weighted routing. Deterministic / seeded RNG is **not** required for tests.

**Lead archetype (from FTD only)**

- The archetype with the **highest** counter value is the **lead** archetype.
- If two or more are **tied** for highest, pick the lead **at random** among those tied.

**Combo archetype (from FTD only)**

- Sort the four archetypes by counter **descending** (1st = highest, 4th = lowest).
- A **combo** is in play **if and only if**  
  **second-ranked value > third-ranked value + 3**  
  (strict inequality on the gap). Otherwise there is **no** combo archetype for routing.
- When combo is in play, the **second-ranked** archetype is the **combo** voice (exact blending with lead/session is implemented in code).

**Voice weights (non-generic draws)**

- **25%** of picks use the **`generic`** archetype bucket (per line / per flavor draw).
- If **no combo**: **70%** session, **30%** lead.
- If **combo** is in play: **70%** session, **15%** lead, **15%** combo (second-ranked archetype).

**Output cap:** **36** lines maximum (one flavor line first when present, then shuffled player/team/scrimmage/break lines; duplicates removed).

**`COACHING_FOCUS_FLAVOR`**

- Session-level one-liners in `training_feed_lines.py`.
- Emit **exactly one** flavor line **every** time the loading feed is built for a training session, chosen from `COACHING_FOCUS_FLAVOR` using the same archetype routing weights as other session copy (implementation detail in `training_loading_highlights.py`).

---

## Highlight builder behavior (product direction)

- **Replace** legacy loading lines: remove standalone SH-only blurbs, **training_notes**, **coaching focus label** line, **play effectiveness** and **defense effectiveness** delta lines from the previous highlight builder; drive the feed from **`training_feed_lines.py`** plus the rules above.
- Output cap and ordering are defined in **`BackEnd/utils/training_loading_highlights.py`** (max **36** lines; flavor first).
