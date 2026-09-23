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

### Phase 1 — Matrix + resolver (no behaviour change) — **SHIPPED**
- Add the 30 profiles to `BackEnd/constants/training_shape.py` as `TRAINING_FOCUS_PERCENTAGES[pos][focus][attr]`.
- `training_attr_gain_multiplier(position, attr, focus="standard")`; `player_attr_gain_multiplier` resolves focus off the player.
- `resolve_training_focus(player)` mirroring `resolve_training_position`, defaulting to `standard`.
- **Gate:** `standard` output is byte-identical to today for all 5 positions × 12 attrs.

### Phase 2 — Data model + backfill — **SHIPPED (staging + production)**
- FPD reads/writes for both fields; validation against the six stored values (reject, don't coerce silently).
- Backfill script in `scripts/` (repo already has `backfill_*.py` precedent), **idempotent, additive-only, never deletes or replaces existing docs**.
- Creation paths default both fields: franchise init, recruit signing, walk-ons, transfers, season rollover.

**Production migration — 2026-09-22.** `scripts/backfill_development_focus.py --db gob --apply`.
93,411 FPD docs updated; 60 already carried a `training_position` (the field predates this
project) and took only `training_focus`. Position resolved from: intent 21,060 · ratings
66,803 · ratings-tie 5,488. Zero skipped. Verified by an independent re-query: `total_docs`
matching `MISSING_FILTER` is 0 and `scanned_all_docs` still 93,411.

**Production is pre-recalibration, and this froze that.** The derived position mix came out
PG 17.9% · SG 19.6% · SF 11.7% · PF 15.8% · **C 34.9%**, against staging's 18.7% C — prod
still has the old height-weighted RT formula, without the attribute recalibration and the
height −2 shift. `training_position` is persisted and this backfill is idempotent, so if the
recalibration later ships to prod, **32,590 players stay pinned to C** and will not
re-derive. Decision taken knowingly (2026-09-22). If that recal happens, pair it with a
re-derive pass over players whose focus is still `standard` and whose position was never
coach-set — a deliberate conversion must never be overwritten.

Note the backfill was never required for correctness: `resolve_training_position` /
`resolve_training_focus` already fall back to `position_intent` → best rating → `standard`,
which is exactly what was written. It makes stored state explicit, nothing more.

### Phase 3 — Execution wiring — **SHIPPED**
- Focus flows through camp + in-season.
- Align `positional_focus_attrs_for_player()` (`training_execution_v2.py:251`) to the same resolved position, so Player Maximizer and Development Focus can't disagree.
- CPU autotrain reads the field (all `standard` for now).

### Phase 4 — Roster UI (the editor) + player detail (read-only) — **SHIPPED**
**Roster — read-only (superseded: the roster was originally specced as the only editor).**
- `franchise-command-center.html` `#roster-tab` + `team-roster-view.html`: **Position** and **Development Focus** columns, user's team only.
- Inline dropdowns, no modal. Every change saves on selection. **Later moved to the training page** — see "One editor" below.
- Immediate save to FPD + toast.

**Player detail (`player-detail.js`) — read-only display.**
- A **DEVELOPMENT** block directly beneath the position-ratings list (`renderPositionRatingsBlock`), showing Position and Development Focus as values, not controls. Adjacency is the point: the ratings are the evidence for the choice.
- The training position is **marked inside the ratings list** so "where he rates" and "where he is coached" read in one glance.
- **User's team only.** Opponent and scouted players show nothing at all — not an empty block, not a dash. **Recruits keep the existing recruiting block**, which occupies the same slot and has no FPD training fields until they sign.
- **STATUS section removed**, with it `momentum` (it resets to zero at the end of every game, so a profile page shows `0` nearly always). The **attitude emoji moves to the identity line** — `SR · #37 · 😐` — keeping its tooltip.

**As built.**

| Piece | Where |
|---|---|
| Shared controls (one implementation) | `FrontEnd/static/js/shared/developmentFocus.js` |
| FCC roster tab | `franchise-command-center.js` — `fccDevelopmentCellsHtml`, `fccBindDevelopmentFocus` |
| Roster page | `team-roster-view.js` — `trShowDevelopment`, columns in `trAttrHeadHtml` / `trAttrRowHtml` |
| Player detail (read-only) | `player-detail.js` — `buildDevelopmentBlock` |
| Styles | `css/attr-tiles.css` — `.devfocus-*` |
| Write route | `POST /franchise/player/development-focus` (`franchise_routes.py`) |

**Ownership gate — the one thing everything hangs off.** The franchise document carries
`user_team_id` (the team **name**) and `user_team_object_id` (the **id**); FPD `meta`
mirrors both as `meta.team` / `meta.team_id`. Compare like with like. The first revision
compared `meta.team_id` against `user_team_id`, which matches nothing — the player-page
block never rendered and every save returned 403. Now one helper, `_player_on_user_team`
(`api.py`), accepts either pairing; `/roster/{team}` emits `is_user_team` and attaches the
four development keys **only** for the user's own team, so no view can render a control
the write route would reject. Verified against gob-staging: exactly 12 own-team FPD docs
per franchise out of 1,536.

**One editor.** Editing lives on the training page's Player Development grid and nowhere
else. The roster surfaces and player detail render the same two values read-only, and
deliberately carry **no** link to the editor for now — a "Set development →" affordance was
built and pulled back out, to be revisited once the one-editor flow has been used in anger. Reasons: the setting only does anything at training, so it belongs beside the points
it governs; the roster tables are reference surfaces twelve attribute tiles wide, where a
live `<select>` adds weight to every row and invites a stray write with no undo; and one
editor is one place for state to drift instead of three.

**Known gap from that choice.** The training page is not always reachable —
`redirectIfTrainingAlreadyCommitted()` bounces to the training report once the week's
training is submitted, and `/franchise/training-points` returns 400 after week 26. So
"switchable any week" (settled decision 7) is in practice "switchable between a new week
opening and submitting that week's training", and not at all through the postseason.
Functionally mild — a change after training is inert until the next run, and the value
carries through rollover — but it is a narrowing, recorded here rather than buried.

**Scope of the controls.** Varsity, user's own team, attributes view. Practice-squad rows
render nothing — the practice payload does not carry the two fields, so a control there
would show an invented default as if the coach had chosen it.

**Re-render discipline.** First paint, sort and scope switch each replace every row, so
each rebinds; a save writes back into the in-memory roster caches, so the next sort does
not repaint the pre-change value. A failed save reverts the control and says so.

### Phase 5 — Training page
Prototyped and approved:
- Remove the "Before you submit" bar; Points Remaining + Coaching Focus status move to a centred pill under the page title.
- **6-pip steppers** replace all 20 range inputs.
- Three columns: **Player Drills · Scheme Installs · Full Team Sessions**, equal height.
- Player Drills: Offense, Defense, Technical. Weight Room retired — **Strength Training / Agility Training** move to the top of Full Team Sessions.
- Team Drills → **Scheme Installs**: Core (Offense/Defense), Fast Breaks (Offense/Defense), Press/Trap (Offense/Defense). Playbook toggle sits directly under the rows. **Scrimmages** moved to Full Team Sessions, under Breaks.
- **Player Development** section below Coaching Focus: 4 × 3, RT-descending, column-first. Position + focus tally split left/right above the grid. "Training by Position ↗" button right-justified in the header row, reusing `navigateToTrainingTutorial`'s draft-save + resume pattern (`training.js:121`).

**Regression surface:** `training.js` reads `input[type=range]`. The pip swap needs the read/write path, Auto-Train and the points counter updated.

### Phase 6 — Tutorial — **SHIPPED**
- Generator writes the matrix to a static asset; **guard test fails if it drifts** from Python.
- Rebuild `tutorial-advanced-training-by-position.html` as **By Position / By Focus**, landing on **By Focus → Standard** (the five-position table the page has always shown, and the state every player is in; the focus dimension is opted into).
- Remove the archetype subhead.
- Update the doc note in `09_Training_Systems/Training_System.md`, which currently says the page is hand-authored.

**As built.** Generator `scripts/generate_training_matrix_asset.py` → asset
`FrontEnd/static/js/generated/trainingMatrix.js` → renderer
`js/shared/trainingMatrixGrid.js`. The asset is a `<script src>` rather than JSON fetched
at runtime, so the downloadable build needs no special case (open item 1, closed). The
asset publishes the band thresholds too, so cells and legend cannot disagree; the band
formerly labelled "Standard" is now "Solid Fit", because the page gained a Standard
**focus** and one word cannot mean both. `tests/test_training_matrix_asset.py` compares
the committed asset to `render()` byte for byte and names the regenerate command on
failure.

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

1. ~~**Desktop build asset path**~~ — closed in Phase 6: the asset is a plain `<script src>` beside the other static JS, so there is no fetch, no CORS and no manifest entry to keep in step.
2. ~~**Roster bulk-set interaction**~~ — **dropped.** Built in Phase 4 as a per-row tick plus a toolbar apply, then removed: an unlabelled checkbox beside a control that already saves on change read as a save confirmation, and the toolbar that explained it only appeared *after* the first tick. Every change is one dropdown, saved immediately. Revisit only if setting a whole squad one player at a time proves to be real friction — and if so, with a visible affordance, not a hidden one.
3. **Practice-squad development** — PS players carry no training position/focus on the roster payload, so they are outside the editor. Revisit if PS training is ever meant to be shaped.
