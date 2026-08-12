# Team Builder System

> **Implementation map.** Product intent lives in `_documentation_master/projects/team-builder-v2-plan.md`; presentation in `projects/design_handoff_team_builder/README.md`. When intent and code disagree, the plan states intent and this file maps wiring — raise a finding, don't silently rewrite either.
>
> **Every section below describes current behaviour.** Superseded behaviour is in §14, marked as history. If you find a claim here that the code contradicts, that is a bug in this file — fix it, don't add a warning label. This document previously carried a table listing nine of its thirteen sections as untrustworthy; that pattern is what §14 exists to prevent.
>
> **Claims marked ⚠ are unverified** — carried forward from prior revisions or from design decisions without confirmation against code. See §15.

---

## 1. What it is

Team Builder lets a user put **their own program** into a new franchise by **replacing one of the 128 core slots**. League size stays 128; conference, schedule and opponents are inherited from the replaced slot via its Mongo **ObjectId**.

Customisations are a **per-franchise overlay**. Core `teams` and `players` are **never mutated**. A franchise without `team_builder` behaves identically to pre-Team-Builder — the resolver and asset path are pass-through no-ops.

The user authors all fifteen players, seeded from the replaced program's roster. There is one roster path: edit.

**Entry:** from the franchise program-select screen at new-franchise start. No franchise document exists until Apply. Mid-franchise editing is out of scope.

**Feature flag:** `TEAM_BUILDER_ENABLED` (default **true** when unset). When **false**, authoring is dark: `/franchise/team-builder/*` returns 404, program-select hides Open Team Builder + unfinished-draft cards, and `team-builder.html` redirects away. Existing franchises that already have a `team_builder` overlay still resolve normally — this flag does not disable chrome/identity for shipped mods. Expose via `GET /app-config` → `teamBuilderEnabled`. Set false on production to merge the branch without shipping the wizard; flip to true when ready.

**Walk-on portraits at Apply:** wizard walk-ons may already carry `meta.image_id` from the TB
450-kit pool. Camp-cut walk-on assignment **skips** any Walk On that already has `meta.image_id`
or `meta.jersey` — TB choices are left alone. Season-init walk-ons without a TB portrait get a
walk-on-pool face + jersey only when they survive onto the post-camp active 12 (see
`Recruiting_System.md` §8).

---

## 2. Fixed constraints

| Constraint | Meaning in code |
|---|---|
| League size invariant | Never insert a 129th team; never rewrite schedule topology |
| Slot replacement | Schedule / FTD / standings stay keyed to the **replaced ObjectId** |
| Per-franchise overlay | Identity lives on `franchises.team_builder`; core `teams`/`players` read-only |
| Single entry | Program select → chapters → Apply; no mid-save edit UI |
| No broken images | Custom art goes through `getTeamAssetPath`; terminal fallback is generic, never a 404 path |
| Client is a pure renderer | The client may aggregate values it already holds; it may not compute values it doesn't hold |

---

## 3. Identity model — read this first

Three layers. Conflating them is how Team Builder franchises break the sim.

```
Structural (never custom names)
  object_id / user_team_object_id  →  schedule pairs, FTD.team_id, standings, load paths
  team_id slug (e.g. HARDWOOD_FIELDS)  →  game-doc teams{} keys, some box-score paths

Identity / keys (always core)
  teams.name (e.g. Hardwood Fields)  →  TeamManager.name, score{}, matchup gate,
                                        init/sim home_team/away_team

Display only (resolved at the edge — response serializers / chrome)
  overlay name (e.g. Hanson)  →  TeamManager.display_name, summary teams[*].display_name,
                                 play-next home_display/away_display, rankings labels
```

| Identifier | Example | Used for |
|---|---|---|
| `object_id` | `69a6fcb6…` | Slot key = `str(teams._id)`. Schedule `(away_id, home_id)`, FTD `team_id`, `user_team_object_id`, resolver key |
| `team_id` (slug) | `HARDWOOD_FIELDS` | Core `teams.team_id`; game document map keys |
| Core name | `Hardwood Fields` | `TeamManager.name`, `score{}` keys, matchup gate, URL `home`/`away` |
| Display name | `Hanson` | Chrome only — never construction, persistence, keys, or matchup equality |
| Player IDs | UUIDs | Unrelated layer — never a team key |

**The rule: resolve at the edge, on the way out.** The display resolver belongs in response serialisation only — never in object construction, persistence, or anything used as a key, hash or comparison. Join and load by ObjectId. The matchup gate stays **strict** core-name equality.

### Why the gate is strict

A tolerant comparator hides leaks. The v1 failure: the resolver fed construction (`TeamManager.name` = Hanson) and init-game rewrote request names to display. The court then sent core `Hardwood Fields` while the GM held display, and the strict gate returned `400 game_id belongs to a different matchup`. That 400 was the system working — a tolerant gate would have accepted it and allowed display-keyed game documents to persist.

**Current:** `.name` is core; `.display_name` is overlay; play-next emits core `home`/`away` plus ObjectIds plus `*_display` for chrome; init-game never rewrites via the resolver.

### The chrome hydration gate

All seven chapter screens resolve team identity and colour through `lookupTeamChrome` / `ensureTeamBuilderChromeSnapshot` — never from raw team data or URL parameters. Three separate rounds of identity leaks came from new entry points rendering before hydration settled. **A deep link into a mid-flow chapter is itself an entry point** and does not inherit the guarantee from the chapter before it.

### The leak detector is observe-only

It emits an `X-TB-Leak-Suspect` header rather than blocking. Identity fields are **exempt by design**: core names appearing in `turns[*].offense_team_id` and similar are the architecture working, not a leak. An earlier strict detector refused valid `simulate-quarter` responses for exactly this reason.

Helpers (structural matching — **not** the matchup gate): `teams_match_for_franchise` in `franchise_geek_points.py`, `gm_team_matches_ref` for playbook and team-pick.

---

## 4. Data model

### 4.1 Franchise overlay

Field: `franchises.team_builder` (`TEAM_BUILDER_FIELD` in `franchise_team_display.py`). Written **once**, at Apply, by `team_builder_apply`.

```python
{
  "replaced_object_id": "<ObjectId str>",  # slot key — never changes
  "replaced_name": "Hardwood Fields",      # core name at Apply (orientation copy)
  "name": "Hanson",                        # display name, ≤ 23 chars
  "abbreviation": "HAN",                   # 3 chars, unique
  "mascot": "...",
  "primary_color": "#...",
  "secondary_color": "#...",
  "jersey_preset": 1,                      # 1 SOLID | 2 SOLID WITH TRIM
  "banner_variant": "baseline",            # baseline | keel | plate | sash
  "asset_strategy": "generated",
  "roster_mode": "edit",                   # only value
  "attribute_mode": "capped" | "uncapped",
  "online_eligible": bool,                 # capped only; written once, never recomputed
}
```

Court recipe nests at **`franchises.team_builder.court`** (Apply via `normalize_court_params`; keys in `COURT_PARAM_KEYS`). Fields:

| Key | Stored value |
|---|---|
| `hardwoodStyle` | Style token, e.g. `medium_medium` |
| `oobColor`, `laneColor`, `outsideWoodColor`, `halfArcFillColor` | `#RRGGBB` hex |
| `insideWoodColor` | Optional `#RRGGBB`; omitted when using the style-key tone |

Draft UI keeps palette tokens (`Primary` / `Secondary` / `Black` / custom hex) in identity state; **Apply resolves colours to hex before write.** Hex on the overlay does freeze those surfaces if the team palette later changes — that is current behaviour, not a token store.

### 4.2 What stays on the core slot

| Store | Key | Unchanged? |
|---|---|---|
| `schedule` weeks | `(away_id, home_id)` ObjectIds | Yes — replaced ObjectId |
| `franchise_team_data` | `franchise_id` + `team_id` (slot ObjectId) | Yes |
| `franchise_players_data` | `franchise_id` + `player_id` | Roster is rewritten at Apply with minted `player_id`s; `meta.team` takes the custom name |
| Universal `teams` / `players` | — | **Never written** |

### 4.3 Draft store

Collection `team_builder_wizard_drafts`. **One document per `(user_id, replaced_object_id)`**, carrying `schema_version: 2`. `draft_id` is a stable minted field for walk-on and portrait idempotency — not a second key axis.

Holds the full in-progress program: claim slot, identity, build mode, roster edits, walk-ons and portrait assignments. Portraits especially — the values a user sees must be the values that ship.

- **Looked up server-side by `user_id`**, via `GET /franchise/team-builder/drafts`. `localStorage` (`tb-draft-id`) is an optimisation, never the only path — the unfinished-program card must appear for a user on a different machine or after clearing site data.
- **Old-format rows (no or wrong `schema_version`) are discarded on read**, not migrated. Detection is by the positive version stamp, never by sniffing for missing fields.
- Deleted on Establish and on explicit discard. No TTL.

### 4.4 Resolver API

`BackEnd/utils/franchise_team_display.py`:

| Function | Role |
|---|---|
| `get_team_builder_overlay(franchise)` | Overlay dict or `None` |
| `resolve_team_display(franchise, team_object_id, core_doc=…)` | Name, colours, mascot, abbr, `is_custom`, `asset_strategy`, `replaced_name` |
| `resolve_team_name_map(franchise, team_ids=…)` | ObjectId → display name |

**Pass-through:** no overlay, or ObjectId ≠ `replaced_object_id` → core values unchanged.

---

## 5. Shared producers

**Policy: intercept at shared producers, not at 58 frontend call sites.** New screens inherit resolution automatically. This is the same instinct applied to names, assets, abbreviations and the chrome snapshot — fix the producer, not the call site.

### 5.1 Display producers

| # | Producer | Location |
|---|---|---|
| 1 | `_format_team_name_map(franchise=…)` | `franchise_routes.py` → `resolve_team_name_map` |
| 2 | Season schedule payload | resolver lookup |
| 3 | `_ftd_team_display` | `community_highlights.py` |
| 4 | `_franchise_summary_for_list` | mode-select slot cards |
| 5 | `GET /roster?franchise_id=` | identity fields on response |
| 6 | `TeamManager.__init__` | name / colours / mascot |
| 7 | Practice Squad parent labels | `_format_team_name_map(franchise_doc)` |
| 8 | `POST /franchise/play-next-game` | display strings; **ids remain ObjectIds** |

Plus the seven chapter surfaces, which resolve through the chrome snapshot (§3). Inventory: `team-builder-identity-inventory.md`.

### 5.2 Asset producer

`getTeamAssetPath(teamNameOrSlug, assetKey, visualOverride)` in `FrontEnd/static/common.js`.

- Custom overlays go **through** it, not around it.
- The server franchise payload is source of truth. `FranchiseLS` `team_builder_visual` is a **warm cache only** — a fresh browser must hydrate correctly from the API.
- Terminal fallback is generic art, never a 404 path.

**Player display names come from `/teams`, never derived from slugs** — `nameToTeamSlug` is lossy for internal capitals, periods and apostrophes. The `ida` asset folder is uppercase on disk while its file stem is lowercase; `couer_dalene` has a related mismatch. **Do not "fix" either stored id.**

---

## 6. Flow and Apply

### 6.1 The seven chapters

```
Program Select → Ⅰ Claim → Ⅱ Identity → [Build mode gate] → Ⅲ Roster → Review → Establish
```

Program Select is the shared franchise entry — it serves both ordinary franchise creation and Team Builder. The remaining chapters live in one page with client-side chapter swapping and deep-linkable states, so the hydration gate is passed at two entry points rather than seven.

**The primary action lives in the top status band on every chapter screen.** Nothing else carries it. When unavailable it is visibly disabled with the reason stated beside it — never a control that looks live and isn't. The Established screen is outside the chapter system and keeps its own action.

**Build mode is written permanently at Establish.** There is no path to change it afterwards, and both the gate and Review say so in those words.

### 6.2 The roster editor is a diff, not a form

Two rules, each of which has already caused a production defect:

**Any field the user does not edit keeps its inherited value.** Apply clones the inherited player document and overwrites only what changed; it does not construct a player from the payload. A zero-edit Apply once differed on 36 field paths because it built new documents from the wizard payload.

**Bind by identity, never by ordinal position.** Budgets, edits and inherited values bind to players by identity. `find()` order is not roster order, and aligning to it silently wrote budgets to the wrong players.

### 6.3 Apply

`POST /franchise/team-builder/apply` → `team_builder_apply` in `franchise_routes.py`.

1. Validate `replaced_object_id`, name (≤ 23 chars), abbreviation uniqueness.
2. Allocate `home_slot`.
3. Build the overlay.
4. `FranchiseManager.initialize_season(...)` — schedule still ObjectId-keyed to the slot.
5. Roster rewrite via `team_builder_roster.py`: clone inherited, apply the diff, mint `player_id`s.
6. **Attribute budgets only — no per-attribute shape floors.** Capped mode already forces each player to their inherited core-12 total; uncapped checks the team pool. Within those totals the editor may redistribute freely (including below development shape floors). Shape floors still bind in the development system (decay clamp); they do **not** refuse Team Builder Apply.
7. Write `attribute_mode` and `online_eligible` (mode-only). Soft-budget echo fields are not written.
8. `$set` the overlay; return franchise id for navigation into FCC.

**Weight is computed once here, on the server.** The client shows the inherited value until height changes, then a short label. No `weight_from_height` implementation exists in frontend code.

⚠ **Apply duration has never been measured.** It warm-paints fifteen portrait masters, so the cold figure — the first Establish in a session, which is what every real user gets — is the one the Establish sequence must be built around. A placeholder was used once and misled the design.

### 6.4 Position ratings

Server-computed by `compute_position_ratings` in `BackEnd/utils/position_ratings.py`, exposed through an endpoint that wraps **that exact function** — no parallel implementation. It takes one player mapping: height plus the eleven attributes in `POSITION_WEIGHTS` (`AG BH FT ID IQ OD PS RB SC SH ST`).

The endpoint **rejects incomplete payloads** rather than defaulting a missing attribute to 0. The function's own `missing → 0` behaviour is fail-open, and empty-treated-as-a-value has caused three production defects here.

Ratings arrive on control release. The UI shows `recomputing…` while pending and never displays a guessed value. Ratings are clamped at 1 below and **uncapped above**, so RT can exceed 99 in uncapped mode — no meter assumes a 0–99 range.

**`RT` is the position rating at a slot. There is no overall rating in this product.** Don't introduce one.

---

## 7. Build modes and budgets

Two modes, chosen at the gate, written permanently at Establish.

**Capped** — eligible for online play. Three budgets, all inherited from the replaced program:

| Budget | Rule |
|---|---|
| Attributes | Per player, inherited total. Points never move between players. |
| Height | Team total, may not exceed inherited. Under is permitted and reads as neutral, not amber. |
| Year / class | Team total, must equal inherited **exactly**. Both over and under are refused, with the shortfall or surplus stated. |

Class ranks (`SR=4 / JR=3 / SO=2 / FR=1`) come from the server as `class_rank`, because that mapping is a rule rather than arithmetic.

**Uncapped** — not eligible for online play. No budgets. Meters render as reference readouts rather than being removed, carrying *Not eligible · written permanently*.

**No hardcoded league constants.** Any number derived from roster data is computed at runtime.

**Potential does not respond to Year, height or attribute edits.** It is fixed at generation via `entry_tier` and `potential_factor`. A younger roster has more seasons ahead, not better players. The flow states this once, on the gate.

---

## 8. Assets

### 8.1 Banners

Four compositions — **Keel, Baseline (default), Plate, Sash** — stored as `banner_variant` with semantic string values, not option letters. Ordinals have already written budgets to the wrong players in this codebase.

Primary 1920 × 679; card 400 × 141. Shrink-to-fit wordmark 50px → 20px floor, measured against **each composition's own field width** — Plate's is 264 card units, not 300.

**Ink is pure `#000` or `#fff`, best-of-two by WCAG contrast**, floor ≈ 4.58:1. The guarantee requires pure black and white; near-black breaks it. Secondary colour never appears as text.

The 23-character name cap derives from Plate's field at the 20px floor: 24 × W measures 269.7 against 264, 23 × W fits at 258.4. Longest real program name is 22. **Enforced in both clients and at Apply.**

| Asset | File | Use |
|---|---|---|
| Full banner | `{slug}_banner_primary.jpg` | Detail / FCC / court chrome |
| Card banner | `{slug}_banner_card.webp` | Picker grid |

### 8.2 Courts

3333 × 2083, generated by `js/shared/teamCourtGenerator.js` — a port of `scripts/generate_non_a1_courts.mjs`, which produced 120 of 129 courts. Eight A1 exclusions: `bentley_truman, lancaster, four_corners, morristown, ocean_city, little_york, xavien, south_lancaster`.

Geometry is fixed. Five colour parameters vary plus the hardwood style key: `oobColor`, `laneColor`, `outsideWoodColor` (midcourt, not centre), `insideWoodColor`, `halfArcFillColor`. There is no centre-circle colour.

**Custom inside-wood colours must clear 3.0:1 against the fixed line colour `#6e675f`**, so markings can't be erased. The client validates for feedback; **Apply refuses**; the generator stays dumb. **Stock style keys are exempt by measurement, not oversight** — shipping medium hardwood is itself ≈2.99, and extending the floor to style keys would make it illegal across 120 existing courts.

### 8.3 Portraits

Portrait pools: `recruit_set_0001` (**450** after the 2026-08 regen — was 300) plus `builder_set_0001` (150), a distinct kit pool. The old "pool of 450 = 300 + 150" total and the 99.2% classifier-match figure predate the regen and need a recount against the current 450-recruit set.

Base-league players have face and jersey baked into one flat PNG; recruits have kit and mask and are recolourable.

**Assignment classifies on height, weight and attributes, so height is final before assignment.** A later height edit re-runs assignment for that player **unless the user picked a portrait**, in which case `portrait_locked` preserves the choice.

**Choose sets `portrait_locked`. Randomize does not, and clears it** — the user said "not this one," not "this one." Randomize re-rolls against the player's *current* height, weight and attributes.

**The picker filters by tone, frame and definition. No race vocabulary appears anywhere** — not in labels, not in `alt` text, `aria-label` or any accessible name, not in CSS class names or rendered `data-` attributes. Accessible names are positional and tonal ("Skin tone 1 of 5, lightest").

Five tone chips, derived by measurement rather than chosen, mapping to the nine classifier keys which are **unchanged underneath**:

| Chip | Classifier keys | Mean L* |
|---|---|---:|
| 1 | `white-pale` | 67.96 |
| 2 | `white-normal` | 56.32 |
| 3 | `asian` + `hispanic` + `white-tan` + `black-light` + `ambiguous` | 49.42 |
| 4 | `black-normal` | 43.75 |
| 5 | `black-dark` | 26.03 |

The mid chip merges five categories because they are the same colour, not merely similar: full-Lab ΔE00 across that cluster peaks at 2.07, and `white-tan` ↔ `black-light` is 0.54 with identical hue angle. **Merge decisions use CIEDE2000 in full Lab, never ΔL\*** — the first pass used lightness alone and reached the right answer for the wrong reason. Chip fills are the n-weighted mean sRGB of their constituent images. **Do not normalise chroma to even out the ramp** — the ends are duller than the middle and that is the truth about this pool.

Filters **reorder and dim; they never remove.** The grid never empties.

**Two known asset gaps, not defects in the picker:** the pool holds one hue (h° 51.5–55.9 for eight of nine categories), and there is an 18-point lightness hole between L\* 44 and 26 with 218 of 450 images inside a 1.73-point band. Both are for the next image bake. Users also cannot filter by race — the intended consequence of removing race vocabulary, recorded so it isn't rediscovered as a bug.

**Uploads do not exist.** They are a committed fast follow. There is no upload control anywhere — a control that isn't wired is worse than an absent one.

---

## 9. Gameplay path

### 9.1 Play next → lineup → court

1. FCC calls `POST /franchise/play-next-game` → `{ home, away, home_id, away_id, week, … }` with **display** names and **ObjectId** ids.
2. FCC builds `/set-lineup.html?...&home=&away=&home_id=&away_id=`.
3. Lineup, court and Phaser always attach `home_id`/`away_id` on `init-game` and `simulate-quarter`.
4. **Never** fall back from structural id parameters to display names.

### 9.2 init-game

`POST /api/init-game`. Accepts optional `home_id`/`away_id`. Franchise mode prefers ObjectId, falls back to core name, then overlay custom name → `replaced_object_id`. Resolves display names via `resolve_team_display` **before** constructing `GameManager`.

### 9.3 Mid-game resume

**A separate entry point with its own failure history.** `resume_anchor.snapshot` previously lacked `franchise_id` and `mode`, so resumed quarters loaded a different roster — simulating against core attributes and writing stats against core `player_id`s. That was league-wide, not Team-Builder-specific; Team Builder made it visible.

Anything touching resume must carry franchise identity explicitly. **Empty is not missing** — this is the third defect of that class in this codebase.

### 9.4 In-game name-keyed maps — explicit non-goal

Live `score[team.name]` and box maps stay keyed by the GM's display name for that game. Do not rewrite them to ObjectId in a casual pass: large, high-risk, and unnecessary while init and the matchup gate stay consistent.

---

## 10. Interaction with player development

Team Builder authors **shape**. The development system then owns what happens to it.

- The offseason attractor is retired (`OFFSEASON_ATTRACTOR_ALPHA = 0.0`), so an authored roster's shape is no longer pulled toward the position profile. Authorship persists.
- **Team Builder does not enforce shape floors.** The only attribute restriction at Apply is the inherited per-player total (capped) or team pool (uncapped). Redistributing below a position floor is allowed.
- **Shape floors remain a development concern** (decay clamp in `training_shape.py`). They stop further decline in-season; they do not gate Establish.
- Floors are derived from a **pre-development** population at the per-attribute 6th percentile. Never re-derive them from a developed snapshot.

Details live in the Player Development System document. This section is the boundary, not a duplicate.

---

## 11. Primary files

| Area | Path |
|---|---|
| Resolver | `BackEnd/utils/franchise_team_display.py` |
| Apply + play-next display | `BackEnd/api/franchise_routes.py` |
| Roster rewrite | `BackEnd/utils/team_builder_roster.py` |
| Position ratings | `BackEnd/utils/position_ratings.py` |
| Shape constants / floors / costs | `BackEnd/constants/training_shape.py` |
| Identity match helpers | `BackEnd/utils/franchise_geek_points.py` |
| Team overlay at runtime | `BackEnd/models/team_manager.py` |
| Score keys after overlay | `BackEnd/models/game_manager.py` |
| init / sim / FTD load / gate | `BackEnd/api/api.py` |
| Roster load overlay name | `BackEnd/utils/roster_loader.py` |
| Chapters | `FrontEnd/static/js/team-builder/{constants,identity,gate,roster,review,establish}.js`; orchestrator `FrontEnd/static/team-builder.js` |
| Program select / claim | `FrontEnd/static/franchise-select-team.*` |
| Generated art | `FrontEnd/static/js/shared/teamGeneratedArt.js` |
| Court generator | `FrontEnd/static/js/shared/teamCourtGenerator.js` |
| Assets | `FrontEnd/static/common.js` (`getTeamAssetPath`) |
| Visual cache | `FrontEnd/static/js/shared/franchiseLocalStorage.js` |
| Lineup / court ids | `FrontEnd/static/set-lineup.js`, `js/phaser/bootGame.js`, `gameScene.js` |

---

## 12. Tests

| Test | Covers |
|---|---|
| `tests/test_tb_matchup_identity.py` | Strict core-name gate; display payload rejected; ObjectId helpers |
| `tests/test_franchise_geek_points.py` | Display rename vs ObjectId/slug |
| `BackEnd/tests/test_team_builder_roster.py` | Roster rewrite helpers |
| `BackEnd/tests/test_team_builder_no_shape_floors.py` | Apply accepts below-floor redistribution when totals stay legal |
| `tests/test_training_shape_framework.py` | Cost matrix ordering, walls, floors, camp locks, shape dispersion |

Staging verification: `franchises.team_builder` present, `user_team_object_id` equals the core slot, core `teams`/`players` unchanged, Play Quarter does not 400 on matchup, UI shows the custom name, **and a mid-game resume renders the correct roster**.

---

## 13. Agent checklist

1. Will this compare or load teams by **display name** when `franchise_id` is present? Use ObjectId, `teams_match_for_franchise` or `gm_team_matches_ref`.
2. New UI surface showing team identity? Use an existing producer or the chrome snapshot — never hard-read `teams.name` for the user slot.
3. New rendering surface? It must pass the hydration gate, including deep links.
4. Art for `asset_strategy: generated`? Route through `getTeamAssetPath`; hydrate from the server payload, not local storage alone.
5. Franchise missing `team_builder`? Your path must no-op.
6. Adding client-side arithmetic? The client may aggregate what it holds and may not compute what it doesn't.
7. Correcting an invalid roster state? Refuse and say why. This feature does not adjust silently.

---

## 14. History

Kept because the reasons are load-bearing — several of these were re-proposed after being retired.

**Roster modes.** v1 offered `keep | generate | import`. Keep and Generate were removed first, then CSV import, leaving `edit` alone. Import was retired **including its backend endpoint and `slot-roster.csv`** — a later league-wide upload feature will have different requirements and gets built fresh. The Apply / rewrite diff field is still named **`imported_players`** — a naming artefact from CSV import. **Rename deferred** (cheap ~28 references; not declined — do it when next touching that surface).

**Soft budgets.** v1 used league-wide caps — team total 6,400, top-5 3,950, per-player ceiling 1,035, floor 24 — evaluated at Apply as metadata that never blocked. Replaced by capped/uncapped modes with per-player inherited totals. Franchise-root **`hasEverExceededBudget`** and **`roster_shape_at_creation`** were write-only leftovers (Apply echo / FCC only; FE never read them). **Removed** from Apply `$set` / response and FCC; Apply `$unset`s them on new franchises.

**Shape-floor Apply gates (retired).** Floors briefly bound every core-12 attribute on the shipped roster, then a diff-scoped authored-only variant. Both refused Establish when an edited attribute sat below the position floor. **Product rule now:** mod teams are limited by attribute **totals** only (per-player inherited in capped; team pool in uncapped). Shape floors stay in development (decay clamp) and are not checked at Team Builder Apply.

**The §4.3 top-up.** Any player whose twelve-attribute total fell below 60 was raised to exactly 60 at Apply, because every attribute needs a minimum of 5. It affected 13 players league-wide. **Attribute recalibration retired it** — the league minimum is now ≈190, so no player can be below 60 from inherited data, and the editor's per-attribute floor of 5 makes 60 the minimum reachable by construction. The server-side guard remains; the user-facing copy was removed because it could never render.

**The five-step wizard.** Slot → Identity → Colors → Roster → Review, replaced by the seven chapters. Removed rather than flagged; both flows were never left reachable.

**The offseason shape attractor.** Blended every player 55% toward his position profile each offseason, retaining ~24% of career shape. Retired. Team Builder surfaced it, but it affected all 128 programs equally.

---

## 15. Unverified and outstanding

**Still marked ⚠ above:**

- **Cold Apply duration** — never measured; the Establish sequence was built without it

**Outstanding work:**

- **Portrait uploads (3c)** — committed fast follow, not built
- **`imported_players` rename** — deferred (see §14)
- `player_id` coupling audit — requested, never delivered
- R2 sweeper for orphaned FPDs from bad resumes
- Static league assets to R2
- Trademark clearance on the name "Team Builder"
- `training_position` has no live write path — development floors still resolve by position; TB no longer gates on them
- **Uncapped runtime meter** — Apply uses runtime `league-context`, but the Team Builder frontend
  does not consume the endpoint for a live team-pool/league-marker display
