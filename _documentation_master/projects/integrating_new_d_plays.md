# Integrating New Man Defense Plays (Base Man / Man Tight / Man Loose)

**Status:** Sequenced integration plan (execution logic owned elsewhere)  
**Date:** 2026-07-15  
**Related:** `Dynamic_MM_Brief.md` (posture / deny↔tight), `O_&_D_Plays_Collections.md`, `Defense_ID_Migration.md`, `Sim_Playcalling_System.md`, `Playcall_Center.md`, `Mode_Init_System.md`, `Game_Init_System.md`

---

## 0. Locked product decisions (this thread)

These are **confirmed** and must not be second-guessed in implementation:

1. **`man_pressure` → rename to `man_tight`** (playbook id + all display / save / migrate paths).
2. **Three independent man plays** — **unified coach-facing names** (scoreboard + all FE UI):
   | Role | Playbook id (usage %) | Catalog `defense_id` | Display label (everywhere) |
   |------|----------------------|----------------------|----------------------------|
   | Base | **`man_normal`** (keep) | **`base-man`** | **Base Man** |
   | Deny / tight | **`man_tight`** | **`man-tight`** | **Deny Man** |
   | Loose | **`man_loose`** | **`man-loose`** | **Loose Man** |

   Internal posture for execution may still be `tight` / `loose` / `normal`; coach-facing string is always the display label above (not “Man Tight” / “Man Loose” / “Man Normal”).
3. Each is a **first-class defense play**: own command (effectiveness) + cloaking, own usage %, independently selectable in Playcall Center, independently callable by sim/CPU.
4. **`game_state["defense_playcall"]` stores catalog `defense_id`** (same pattern as zones: `2-3-zone`, not `zone_23`). Playbook % maps stay on playbook ids (`man_normal`, …).
5. **Existing FTD migration:** copy current single `man` scouting EFF/MOM/CLK onto **Base Man** (`base-man`); Tight/Loose start at **0**. Rename `man_pressure` → `man_tight` in playbooks.
6. **Zone tight/loose variants:** out of scope (man only).
7. **Execution logic:** separate thread. This plan = identity, persistence, init, selection, UI/UX, hand-off only.
8. **Offense `vs_man`:** keep **one** offense-vs-man bucket for all three man shells (default unless product revisits).
9. **Defense Matchups:** **shared** across all three man plays.

### What “legacy `man` doc” means (Q3 explained)

Mongo `defenses` was seeded twice for “standard man”:

| Source | `defense_id` | `name` |
|--------|--------------|--------|
| `scripts/init_defenses_collection.py` | **`man`** | Man-to-Man |
| `scripts/add_base_man_defense.py` | **`base-man`** | Base Man |

Runtime today treats them as aliases: playbook `man_normal` / `man_pressure` / `man_loose` all map to catalog **`man`**, and `canonical_scouting_defense_key` collapses `base-man` → scouting row **`man`**. That shared row is why you only have one man CMD/CLK today.

**For this project:** Base Man’s canonical id becomes **`base-man`**. The old **`man`** document is the “legacy man doc” — keep it as a **dual-read alias** during migration (resolve `man` → `base-man` or treat as same row), then deprecate so we do not maintain two competing base identities forever.

---

## 1. Identity model today (Q4 answered) — catalog vs playbook

### Defense (current)

| Layer | What is stored | Example |
|-------|----------------|---------|
| Playbook % keys | **Playbook ids** | `zone_23`, `man_normal` |
| `game_state["defense_playcall"]` | **Catalog `defense_id`** (canonical slug) | `2-3-zone`, `man` |
| `scouting_data["defense"]` rows | **Catalog / canonical row keys** | `man`, `2-3-zone`, … |

Zone path is the template to copy for man variants:

- Playbook: `zone_23` / `zone_32` / `zone_131`
- Sim expand (`_select_zone_defense_with_playbook_weights`): returns **`2-3-zone` / `3-2-zone` / `1-3-1-zone`**
- Those catalog ids go into `defense_playcall`

Man path today **skips** playbook expand: strategy `"man"` → `defense_playcall = "man"` always.

Module + docs:

- Code SSOT: `BackEnd/utils/defense_identity.py` (header + maps)
- Migration task: `_documentation_master/tasks/Defense_ID_Migration.md`
- Sim overview: `_documentation_master/06_Gameplay_Systems/Sim_Playcalling_System.md` (defensive flow; playbook identity rules)
- Collections: `_documentation_master/00_Data_Systems/O_&_D_Plays_Collections.md`

### Offense (for comparison — intentionally different)

| Layer | Identity |
|-------|----------|
| Playbook % | **`play_id`** = `str(plays._id)` |
| `game_state["current_playcall"]` | Display **name** (compatibility); resolution uses `play_id` under the hood |
| Team owned plays | Copied from universal `plays` by `play_id` |

**Defense and offense are not the same format by design** (`Defense_ID_Migration.md`: defense = `defense_id` slug; offense = Mongo `play_id`). Do not force parity.

### Locked for new man plays

```text
Playbook %                Catalog defense_id      Scouting row / defense_playcall
──────────────            ────────────────────    ───────────────────────────────
man_normal            →   base-man            →   base-man
man_tight             →   man-tight           →   man-tight
man_loose             →   man-loose           →   man-loose
```

---

## 1b. Remaining soft defaults (only if revisited)

| # | Topic | Locked default |
|---|--------|----------------|
| Q5 | Offense vs_* | Single `vs_man` for all three |
| Q10 | Matchups | Shared man matchups |
| Display labels | **Base Man** / **Deny Man** / **Loose Man** (scoreboard + all FE) |

---

## 2. Current state (why work is required)

| Area | Today |
|------|--------|
| Collection | Mongo **`defenses`** (not `universal_defenses`) |
| Team defense rows | **Hardcoded** scouting template — **not** organically copied from `defenses` |
| Playbook man keys | `man_normal`, `man_pressure`, `man_loose` — only `man_normal` **active** |
| Identity | All three playbook keys **collapse to** catalog `"man"`; scouting one `"man"` row |
| Catalog overlap | Both **`man`** (init script) and **`base-man`** (add_base_man script) may exist |
| Sim selection | Zone uses playbook weights → catalog ids; **man never expands** |
| Playcall Center | “Man Normal” + zones; override often collapses to `"Man"` |
| Training | Disables pressure/loose |

**Implication:** Mongo docs alone will **not** activate plays on teams/UI. Full stack wiring required.

---

## 3. Target architecture (independent man plays)

```text
Playbook % keys       Catalog defense_id      Scouting + defense_playcall
─────────────────     ──────────────────      ───────────────────────────
man_normal        →   base-man            →   base-man
man_tight         →   man-tight           →   man-tight
man_loose         →   man-loose           →   man-loose

Strategy "man"  →  weighted pick among the three playbook keys
                →  map to catalog defense_id
                →  set game_state["defense_playcall"] = that catalog id
                →  execution thread reads defense_playcall
```

**DB (both `gob` and `gob-staging`):**

| defense_id | name | Action |
|------------|------|--------|
| `base-man` | Base Man | Upsert; make canonical base (alias legacy `man` → this) |
| `man-tight` | Deny Man | **New** (display name; id keeps `man-tight`) |
| `man-loose` | Loose Man | **New** (stop aliasing to `man`) |
| `man` | Man-to-Man | Legacy — keep as dual-read alias during soak, then deprecate |

Team init still **hardcodes** scouting + playbook seeds; Mongo supplies catalog identity / baseline fields.

---

## 4. Sequenced plan

### Phase 0 — Scope freeze (DONE — 2026-07-15)

Naming / identity sheet locked in §0. Zone variants out of scope. Execution hand-off ids in §6.

---

### Phase 1 — Catalog & identity (backend foundation)

**Goal:** Three distinct, resolvable defense identities.

1. **Seed / upsert Mongo `defenses`** (run against **gob-staging**, then **gob**):
   - Script(s) patterned on `scripts/add_base_man_defense.py`
   - Fields: `defense_id`, `name`, `defense_type: "Man"`, baseline `effectiveness` / `cloaking`, stats shells, `zone_definitions: null`
   - Reconcile existing `man` vs `base-man` docs (do not leave two competing “base” identities without an alias map)
2. **`BackEnd/utils/defense_identity.py`**
   - Stop collapsing `man_tight` / `man_loose` / base → single `"man"` for **scouting row** and playcall resolution
   - Update `PLAYBOOK_MAN_KEY_TO_DEFENSE_ID`, legacy candidates, `defense_scouting_row_key`, `is_zone_defense_id` (all three remain man)
   - `offense_vs_key_from_defense_input`: keep `vs_man` unless Q5 splits
3. **`BackEnd/utils/playbook_settings_utils.py`**
   - `MAN_DEFENSE_ID_TO_NAME`: rename pressure→tight; set base display name; keep loose
   - `DEFENSE_NAME_TO_ID` / save maps
4. **Tests:** `tests/test_defense_identity.py` — resolve each playbook key ↔ catalog id; no collapse of tight/loose to base for scouting

**Exit:** `resolve_to_defense_id("man_tight")` etc. work; staging + prod catalogs have docs.

---

### Phase 2 — Persistence, init, migration

**Goal:** New and existing teams actually *have* the three plays as data.

1. **Playbook defaults** — `initialize_playbook_settings` / `gameplan_routes.py`
   - Keys: base + `man_tight` + `man_loose`
   - Default %: e.g. base `100`, tight/loose `0` (or even split — product call)
   - Rename any seed of `man_pressure` → `man_tight`
2. **Scouting templates** — `populate_scouting_data`, `team_manager` templates, `normalize_scouting_data_for_gameplay`
   - Add **three** defense rows with own EFF/MOM/CLK (+ granular stats shells)
   - Preserve legacy `"man"` / `"Man"` dual-read during transition; migrate → canonical ids
3. **Franchise / season / game init**
   - Franchise create: seeds new shape
   - **Existing FTD migration / lazy normalize:**  
     - `man_pressure` → `man_tight`  
     - ensure missing tight/loose rows + playbook keys appear  
     - map old single `man` scouting row → base id without wiping trained EFF (policy: copy EFF into base; tight/loose start at 0 **or** split — product call)
4. **Season init:** do not wipe franchise playbooks; only normalize forward
5. **CPU / tutorial defaults** — `cpu_playbook_customization.py`, `tutorial_game.py`
6. **Training** — enable the three ids in training playbooks (remove disable list entries)

**Exit:** New franchise + migrated franchise both show three man rows with independent CMD/CLK fields; playbook % editable.

---

### Phase 3 — Sim / CPU selection (makes them callable)

**Goal:** Strategy “man” can pick among the three independently (mirrors zones).

1. **`turn_manager`**
   - Add `_select_man_defense_with_playbook_weights()` (clone zone helper pattern)
   - Where strategy pick is `"man"`, expand via `playbook_settings["man_defense"]` weights → catalog `defense_id`
   - Set `game_state["defense_playcall"]` to that id
2. **Usage / success tracking**
   - Increment **per-row** scouting stats for the active `defense_id` (not one shared `man` bucket)
3. **`training_execution_v2`**
   - Use `man_defense` weights when multiple man rows exist (existing TODO)
4. **Tests:** weighted man selection; 0% variants never selected; tracking hits correct row

**Exit:** Distant/CPU sims call Base / Tight / Loose per playbook % without UI.

**Note:** Execution behavior differences = other thread; this phase only ensures the **correct playcall id** is armed.

---

### Phase 4 — Game UI / UX

**Goal:** Human can choose each play in-game and in playbooks.

1. **Playbooks API** — `man_defense_rows`
   - `is_active: true` for all three
   - Names from locked sheet; ids match playbook keys
2. **Playbooks page** — `playbooks.js`
   - Remove “Coming Later” / dead-row treatment for tight & loose
3. **Playcall Center** — `court.html` (and POC if still used)
   - `DEFENSE_SCHEMES`: Base Man (or Man Normal), Man Tight, Man Loose, + zones
   - Override payload: map display → playbook id / catalog id consistently with backend
   - Status text shows selected man variant
4. **defense display helpers** — `defenseUi.js`, `playcallDisplay.js`, box score subsections
   - Per Q7: specific labels vs Man bucket
5. **Set-lineup / FCC / reports**
   - Rows driven by active API rows; verify CMD/CLK columns per play
6. **Defense Matchups**
   - Keep shared man matchups (Q10) unless changed — gate on “is man family” not exact id

**Exit:** User can set usage % and call any of the three from Playcall Center; HUD reflects choice.

---

### Phase 5 — Docs & cleanup

1. Update: `O_&_D_Plays_Collections.md`, `Sim_Playcalling_System.md`, `Playbooks_Page.md`, `Playcall_Center.md`, `Mode_Init_System.md`, `Game_Init_System.md`, `Defense_ID_Migration.md`, `Computer_Team_Playbooks_System.md`
2. Cross-link `Dynamic_MM_Brief.md` P6: man playcalls are real; posture may derive from playcall id (`man-tight`→tight, `man-loose`→loose, base→normal) — coordinate with execution thread
3. Remove dead aliases for `Man Pressure` / `man_pressure` after migration soak
4. Archive note in this doc when complete

---

### Phase 6 — Hand-off contract to execution thread

Stable strings execution will see on `game_state["defense_playcall"]`:

| Play | `defense_playcall` | Suggested posture (if used) | FE / scoreboard label |
|------|--------------------|-----------------------------|------------------------|
| Base | `base-man` | `normal` | Base Man |
| Deny | `man-tight` | `tight` / deny | Deny Man |
| Loose | `man-loose` | `loose` | Loose Man |

Also accept legacy `"man"` as alias → treat as Base during soak.

---

## 5. Explicit non-goals (this plan)

- Implementing on-court execution differences (separate thread)
- Zone tight/deny/loose playbook variants (unless Q9 flips)
- Changing offense play copy / universal `plays` pipeline
- Auto-syncing `gob` ↔ `gob-staging` (manual seed both)

---

## 6. Suggested order of work (summary)

| Order | Phase | Blocks |
|------:|-------|--------|
| 0 | Naming sheet | Everything |
| 1 | Mongo `defenses` + identity | Persistence & UI labels |
| 2 | Init / scouting / FTD migrate | Selection & UI data |
| 3 | Sim man weighted picker | CPU/distant usage |
| 4 | Playbooks + Playcall Center UI | Human usage |
| 5 | Docs / alias cleanup | — |
| 6 | Execution hand-off | Parallel OK after Phase 1 ids locked |

---

## 7. Answers already locked

| Topic | Answer |
|-------|--------|
| Base display | **Base Man** |
| Deny / Loose display | **Deny Man** / **Loose Man** (all FE + scoreboard) |
| Base playbook id | **`man_normal`** (keep) |
| Catalog ids | **`base-man`**, **`man-tight`**, **`man-loose`** |
| Legacy `man` doc | Alias during soak → deprecate (see §0) |
| `defense_playcall` | **Catalog `defense_id`** (zone-consistent) |
| Zone variants | Out of scope |
| FTD migrate EFF | Old `man` → Base; Tight/Loose start 0 |
| Organic via init only? | **No** |
| Docs in gob + gob-staging? | **Yes** |
| Execution in this plan? | **No** |

---

## 8. Status

Phase 0 complete. **This doc's first-class-plays model is the committed architecture (owner, 2026-07-19).**
An interim posture prototype was built on a *different* model (S4 in `Dynamic_MM_Brief.md`) and must be
reconciled INTO this plan before Phases 1–6 proceed — see §9.

---

## 9. Reconciliation addendum — converging the S4 posture prototype (2026-07-19)

**Why this exists.** Four days after this plan was written, an "S4 man slice" was built to the
one-line S4 row in `Dynamic_MM_Brief.md` (not to this doc). It took a **different, lighter
architecture** — ONE `man` defense + a posture *attribute* — that CONFLICTS with this doc's
first-class-plays model. **Owner decision 2026-07-19: this doc wins (three independent plays).** The
S4 prototype is therefore partly reusable, partly to be reverted. This section is the exact delta so
whoever runs Phases 1–6 doesn't build on the wrong foundation or redo salvageable work.

### 9.1 What S4 built (the divergent prototype — all UNCOMMITTED as of 2026-07-19)
| File | S4 change | Fate under this doc |
|---|---|---|
| `defense_identity.py` | added `man_deny`→`man` to `PLAYBOOK_MAN_KEY_TO_DEFENSE_ID`; added `hco_defense_posture_from_call(raw)` | **CHANGE** map (see 9.2); **KEEP** the posture fn (repurpose) |
| `phase_resolution.py` | `_roll_defense_posture` reads `game_state["_hco_defense_posture_call"]` instead of `random.choice`; random roll retired | **KEEP the retirement**; **CHANGE the source** to `defense_playcall` (see 9.3) |
| `turn_manager.py` | new `_apply_defense_call` (coerce→canonical `man` + stash posture-call); new `_expand_man_posture_pick` (aggression-weighted); default posture reset in `set_playcalls`; call-sites rewired | **REVERT/REWORK** — collapse-to-`man` and the aggression picker both contradict this doc |
| `constants/__init__.py` | `STRATEGY_MAN_POSTURE_BY_AGGRESSION` | **REVERT** — this doc selects by playbook %, not aggression |
| `court.html` | `DEFENSE_SCHEMES` += `Man Deny`/`Man Loose`; `defenseSchemeToApiValue` → `man_deny`/`man_loose` | **RELABEL** to Deny Man/Loose Man + catalog-id api values (see 9.5) |

### 9.2 Identity — distinct catalog ids (supersedes S4's collapse)
S4 kept `defense_playcall = "man"` for all three and carried posture in a side field. **This doc
requires distinct ids** (`base-man` / `man-tight` / `man-loose`). So, per Phase 1.2:
- `PLAYBOOK_MAN_KEY_TO_DEFENSE_ID`: `man_normal→base-man`, **`man_tight→man-tight`**, `man_loose→man-loose`
  (values become the DISTINCT catalog ids, not `man`). **Drop S4's `man_deny` key — use `man_tight`** (this
  doc renames `man_pressure`→`man_tight`; `deny` is display-only, "Deny Man").
- `_coerce_hco_defense_id` / `canonical_scouting_defense_key` must resolve each to its OWN id (stop
  collapsing tight/loose/base → `man` for the scouting row + playcall).

### 9.3 Posture derivation — read the id, delete the side field (SIMPLIFIES S4)
Because `defense_playcall` now carries the distinct id, posture derives straight from it — **no side
field**:
- `_roll_defense_posture`: `posture = hco_defense_posture_from_call(game_state["defense_playcall"])`.
  The S4 posture fn already returns the right thing on the catalog ids (`man-tight`→tight,
  `man-loose`→loose, `base-man`/`man`→normal — keyword match), so **KEEP the function**, just point it
  at `defense_playcall`.
- **DELETE**: the `_hco_defense_posture_call` field, its stash inside `_apply_defense_call`, and the
  default-reset line in `set_playcalls`. (Random-roll retirement STAYS.)
- The ~13 downstream posture consumers (`animator`, `step_state`, `shot_manager`,
  `attack_drive_clearance`, and the `_hco_defense_posture`-gated sites in `phase_resolution`) are
  **unchanged** — they still read `game_state["_hco_defense_posture"]`, which `_roll_defense_posture`
  still sets. Only its *source* changed. **This is the Phase 6 hand-off, now concrete.**

### 9.4 CPU selection — playbook %, not aggression (supersedes S4)
**REVERT** `_expand_man_posture_pick` + `STRATEGY_MAN_POSTURE_BY_AGGRESSION`. Build Phase 3's
`_select_man_defense_with_playbook_weights()` (clone the zone picker) — a strategy `"man"` pick
expands among `man_normal`/`man_tight`/`man_loose` by playbook % → catalog id. (The aggression axis was
an S4 invention not in this plan; drop it unless product later wants it as a modifier.)

### 9.5 Exact-string `== "man"` checks — NOW REQUIRED (S4 wrongly dropped them)
S4 concluded these were unnecessary *because it kept `defense_playcall == "man"`*. Under distinct ids
they **break** (`man-tight` ≠ `"man"`). Reinstate as real work (part of Phase 2/3):
`training_execution_v2.py:2504/2540` (`defense_name == "man"`) and `turn_manager.py:3667`
(`def_row == "man"`) → route through the resolver / an "is man family" check. Add any other
exact-`"man"` comparisons surfaced by grep.

### 9.6 FE — relabel + catalog-id payload
`court.html`: `DEFENSE_SCHEMES` → **Base Man / Deny Man / Loose Man** (+ zones); `defenseSchemeToApiValue`
sends the **catalog id** (`base-man`/`man-tight`/`man-loose`) so it round-trips to `defense_playcall`
without collapse. Also do Phase 4's `defenseUi.js` / `playcallDisplay.js` / box-score labels (S4 skipped
these; the card render is safe but the HUD/box-score still show `Man`).

### 9.7 Net-new (S4 didn't touch — full Phases 1–2 stand)
Mongo catalog docs (`base-man`/`man-tight`/`man-loose`), independent scouting rows (own EFF/MOM/CLK),
playbook % defaults, FTD migration, training enablement, Playbooks page — all remain exactly as
Phases 1–2 describe. S4 pre-touched only the *selection* (Phase 3, wrong picker), *posture execution*
(Phase 6, wrong source), and *Playcall Center* (Phase 4, wrong labels/ids).

### 9.8 Reconciliation checklist (do BEFORE/ALONGSIDE Phase 1)
- [ ] `defense_identity.py`: man map → distinct ids; drop `man_deny`; keep `hco_defense_posture_from_call`
- [ ] `_roll_defense_posture` → derive from `defense_playcall`; delete `_hco_defense_posture_call` field + stash + reset
- [ ] Revert `_expand_man_posture_pick` + `STRATEGY_MAN_POSTURE_BY_AGGRESSION`; build playbook-% man picker (Phase 3)
- [ ] Fix the `== "man"` exact-string checks (9.5)
- [ ] FE relabel + catalog-id payload + HUD/box-score labels (9.6)
- [ ] Then proceed with net-new Phases 1–2 (catalog docs, scouting rows, %, migration)
