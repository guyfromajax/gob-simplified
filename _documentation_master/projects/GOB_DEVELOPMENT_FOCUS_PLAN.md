# Development Focus — implementation plan

Per-player training profile selected by **position + focus**, replacing the position-only
efficiency lookup. Companion to `GOB_POSITION_TRAINING_FOCUS_SPEC.md` (matrices) and
`GOB_POSITION_TRAINING_PROMPT.md` (original kickoff).

**Status:** planned, not started. Decisions below are settled with the owner (2026-09-21).

---

## 1. What the spec got right, and the two premises that were wrong

**Verified against the tree and against `gob-staging`:**

| Spec claim | Verdict |
|---|---|
| All 30 profiles total 808 | ✅ confirmed by script |
| FT / IQ / ND = 100 in every profile | ✅ confirmed |
| `standard` == today's live behaviour | ✅ **byte-identical** to `TRAINING_GAIN_PERCENTAGES`; live totals are already 808/position |

**Premise 1 — "reuse the canonical `position` field" — there is no such field.**
`position` exists on **0 of 1,536** staging player docs and **0 of 173,184** FPD docs.
`Player` carries `position_ratings`, and lineups key by slot.

**Premise 2 — "when a user assigns a training point to an attribute" — points are team-wide drills.**
The coach allocates drill points from a weekly budget; the position multiplier is applied per player
during execution. There is no per-attribute, per-player surface to hang a selector on.

**What already exists.** `player_development.py:613-615` documents the intended design and says the
UI was deferred — "`training_position`: where the player is being coached this cycle. Defaults to
`position_intent` (natural fit) and is forward-copied; **a user converting a player sets it
explicitly (UI deferred to a later pass)**." This workstream is that pass.

---

## 2. Settled decisions

| # | Decision |
|---|---|
| Name | User-facing **"Development Focus"**. `"Positional Focus"` is taken — a live Player Maximizer sub-option (`training_execution_v2.py:365`) |
| Fields | **`training_position`** (coach's choice) + **`training_focus`** (new). No third position field |
| `position_intent` | Untouched — natural fit, carried from the recruit pool, consumed by jersey assignment and team-builder |
| Authority | **FPD is authoritative.** FTD training reads FPD; all UI writes go to FPD |
| Backfill | All FPD docs: `training_position` = `position_intent` → else highest `position_ratings`, **tie broken randomly once at backfill**; `training_focus = "standard"` |
| Scope | **Camp + in-season only.** Offseason out of scope |
| Floors | Unchanged, position-only. Focus redirects gains; it cannot starve an attribute below its positional floor |
| Amplify | Stacks cleanly. Focus replaces only the position term |
| Cadence | Switchable any week. Cost comes later |
| CPU | All `standard` initially; autotrain reads the field. Identity-driven selection is future work |
| Matrix delivery | Python canonical → **generated static file** + guard test. Works offline in the desktop build |
| Surfaces | Roster (FCC tab + roster page) is the editor; training page mirrors it |
| Roster list | **12 active players only** — no injured, no practice squad |
| Visibility | **User's team only, everywhere.** Development Focus and training position are never shown for opponent, CPU or scouted players on any surface (roster, player detail, training page) |
| Position editing | Editable from day one — on the roster surfaces. Player detail is **read-only** |
| Walls | Deliberately breakable. Rebounding focus lifts PG/SG rebounding 25 → 75 |

**Consequence to document, not a bug:** changing `training_position` also changes which **shape
floors** apply (floors are position-scaled). Converting a guard to PF gives him PF's rebounding and
strength floors.

---

## 3. Execution order (unchanged except the multiplier term)

```
raw roll (PLAYER_ATTR_GAIN_RANGE_BY_POINTS)
  → amplify ×1.5–1.8            (Player Maximizer, if it picked this attr)
  → × gain_scale                (IN_SEASON_GAIN_SCALE 0.28 | CAMP_GAIN_SCALE 0.70)
  → × profile multiplier        ← position-only today; becomes position + focus
  → whole gain + banked remainder (training_gain_remainders)
```

Single swap at `training_execution_v2.py:1074` (`effective_scale = gain_scale ×
player_attr_gain_multiplier(player, attr)`). **No double-apply**: the profile replaces the position
lookup, it does not multiply with it.

---

## 4. Phases

Each phase is independently shippable.

### Phase 1 — Matrix + resolver (no behaviour change)
- Add the 30 profiles to `BackEnd/constants/training_shape.py` as `TRAINING_FOCUS_PERCENTAGES[pos][focus][attr]`.
- `training_attr_gain_multiplier(position, attr, focus="standard")`; `player_attr_gain_multiplier` resolves focus off the player.
- `resolve_training_focus(player)` mirroring `resolve_training_position`, defaulting to `standard`.
- **Gate:** `standard` output is byte-identical to today for all 5 positions × 12 attrs.

### Phase 2 — Data model + backfill
- FPD reads/writes for both fields; validation against the six stored values (reject, don't coerce silently).
- Backfill script in `scripts/` (repo already has `backfill_*.py` precedent), **idempotent, additive-only, never deletes or replaces existing docs**.
- Creation paths default both fields: franchise init, recruit signing, walk-ons, transfers, season rollover.

### Phase 3 — Execution wiring
- Focus flows through camp + in-season.
- Align `positional_focus_attrs_for_player()` (`training_execution_v2.py:251`) to the same resolved position, so Player Maximizer and Development Focus can't disagree.
- CPU autotrain reads the field (all `standard` for now).

### Phase 4 — Roster UI (the editor) + player detail (read-only)
**Roster — the only editor.**
- `franchise-command-center.html` `#roster-tab` + `team-roster-view.html`: **Position** and **Development Focus** columns, user's team only.
- Inline dropdowns, no modal. Multi-select → bulk set.
- Immediate save to FPD + toast.

**Player detail (`player-detail.js`) — read-only display.**
- A **DEVELOPMENT** block directly beneath the position-ratings list (`renderPositionRatingsBlock`), showing Position and Development Focus as values, not controls. Adjacency is the point: the ratings are the evidence for the choice.
- The training position is **marked inside the ratings list** so "where he rates" and "where he is coached" read in one glance.
- **User's team only.** Opponent and scouted players show nothing at all — not an empty block, not a dash. **Recruits keep the existing recruiting block**, which occupies the same slot and has no FPD training fields until they sign.
- **STATUS section removed**, with it `momentum` (it resets to zero at the end of every game, so a profile page shows `0` nearly always). The **attitude emoji moves to the identity line** — `SR · #37 · 😐` — keeping its tooltip.

### Phase 5 — Training page
Prototyped and approved:
- Remove the "Before you submit" bar; Points Remaining + Coaching Focus status move to a centred pill under the page title.
- **6-pip steppers** replace all 20 range inputs.
- Three columns: **Player Drills · Scheme Installs · General**, equal height.
- Player Drills: Offense, Defense, Technical. Weight Room retired — **Strength Training / Agility Training** move to the top of General.
- Team Drills → **Scheme Installs**: Core (Offense/Defense), Fast Breaks (Offense/Defense), Press/Trap (Offense/Defense), Scrimmages. Playbook toggle sits directly under the rows.
- **Player Development** section below Coaching Focus: 4 × 3, RT-descending, column-first. Position + focus tally split left/right above the grid. "Training by Position ↗" button right-justified in the header row, reusing `navigateToTrainingTutorial`'s draft-save + resume pattern (`training.js:121`).

**Regression surface:** `training.js` reads `input[type=range]`. The pip swap needs the read/write path, Auto-Train and the points counter updated.

### Phase 6 — Tutorial
- Generator writes the matrix to a static asset; **guard test fails if it drifts** from Python.
- Rebuild `tutorial-advanced-training-by-position.html` as **By Position / By Focus**, default By Position → PG.
- Remove the archetype subhead.
- Update the doc note in `09_Training_Systems/Training_System.md`, which currently says the page is hand-authored.

---

## 5. Tests

**New:** all 30 profiles exist; each totals 808; FT/IQ/ND = 100; legacy null → `standard`; invalid focus rejected; round-trip through FPD; representative execution values; no double-apply; tutorial renders both orientations from the generated source.

**Existing invariants that the 30 profiles break** (`tests/test_training_shape_framework.py`) — re-scope deliberately, don't delete:

| Test | Breakage |
|---|---|
| `test_25_percent_is_reserved_for_documented_physical_walls` | **13 cells** across focus profiles (e.g. `PG/offensive/ST`, `C/offensive/OD`). None in `standard` |
| `test_cross_position_gain_orderings_are_locked` | ST and RB ordering breaks in 6 focus profiles, beyond the documented PF>C exception |

Recommended: keep both invariants **strict for `standard`**, and assert a looser, explicitly-documented rule for focus profiles.

**Policy:** pytest runs in-memory (mongomock) or against `gob-staging` only, and must never delete or replace pre-existing docs.

---

## 6. Tunable Constants

| Constant | Where | Value / effect |
|---|---|---|
| `TRAINING_GAIN_PERCENTAGES` | `constants/training_shape.py:26` | Position-only table; becomes the `standard` column |
| `TRAINING_FOCUS_PERCENTAGES` | new, same module | 5 × 6 × 12; every profile totals 808 |
| `CLASS_GAIN_PERCENTAGES` |  `training_shape.py:40` | FR 100 / SO 91 / JR 95 / SR 100. Multiplies on top; **deliberately not shown in the tutorial** |
| `IN_SEASON_GAIN_SCALE` | `training_execution_v2.py:453` | 0.28 |
| `CAMP_GAIN_SCALE` / `CAMP_WEEKS` | `training_shape.py` | 0.70 / 1 |
| `CAMP_POINT_BUDGET` / `IN_SEASON_POINT_BUDGET` | `training_shape.py` | 30 / 24 |
| `PLAYER_ATTR_GAIN_RANGE_BY_POINTS` | `training_execution_v2.py:465` | 0 → (−2,−1) … 5 → (3,6) |
| `SHAPE_FLOOR_MULTIPLIERS` | `training_shape.py:60` | Position-only floors; **not** focus-aware |
| Amplify multiplier | `training_execution_v2.py:1067` | `random.choice([1.5, 1.6, 1.7, 1.8])` |
| `TRAINING_PHYSICAL_WALLS` | `training_shape.py:20` | 25% walls; focus profiles may exceed them by design |

---

## 7. Non-goals

Offseason shaping · CPU identity-driven focus · archetype dimension · cost to switch focus ·
focus-aware floors · changing `position_intent` semantics · any gameplay/lineup change.

---

## 8. Open items

1. **Desktop build asset path** — if the packaging step needs a manifest entry, the generator should write where it expects.
2. **Roster bulk-set interaction** — multi-select then apply is specified; exact affordance is a UI detail for Phase 4.
