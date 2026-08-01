# Team Builder System (**verified 2026-07-28**)

> Implementation doc for agents and human developers. Product behavior, UX copy, and acceptance criteria live in `_documentation_master/projects/mod-system/team-builder-v1-spec.md` (authoritative on *what* the feature must do). This file documents *how* it is wired in the codebase so you can change it without thread context.
>
> Verified vs `franchise_team_display.py`, `franchise_routes.py` (`team_builder_apply`, play-next), `team_manager.py`, `api.py` (init-game / simulate-quarter matchup gate), `common.js` (`getTeamAssetPath`), `team-builder.js`, identity helpers in `franchise_geek_points.py`.

### Split of duties (read first)

| Doc | Owns | Does **not** own |
|---|---|---|
| **`../projects/mod-system/team-builder-v1-spec.md`** | Product behavior, UX flow, user-facing copy, acceptance criteria, v1 scope cuts | Data models, file paths, how overlay/resolver/sim identity are wired |
| **This file (`Team_Builder_System.md`)** | Implementation: identity rules, overlay schema, Apply/endpoints, shared producers, gameplay path, file map, tests | Product copy strings and “should we build X?” decisions — those stay in the spec |
| **`../projects/mod-system/team-builder-identity-inventory.md`** | Team identity / chrome inventory (derived forms, overlay awareness) | Narrative product or full system architecture |

When product intent and code disagree, treat the **spec** as the statement of intent and this file as the map of current wiring — raise a finding; do not silently rewrite the spec from the codebase (see spec §0).

---

## 1. What it is

Team Builder lets a user put **their own program** into a new franchise by **replacing one of the 128 core slots**. The league size stays 128; conference, schedule, and opponents are inherited from the replaced slot via its Mongo **ObjectId**.

Customizations are a **per-franchise overlay**. Core `teams` and `players` collections are **never mutated**. A franchise without `team_builder` is byte-identical to pre–Team Builder behavior (resolver + asset path are pass-through no-ops).

**Entry point:** only from franchise team-select at new-franchise start. Franchise creation does **not** begin until Apply (`POST /franchise/team-builder/apply`). Mid-franchise editing is out of scope for v1.

**Related orientation:** `Franchise_Mode_Overview.md` (this folder). Product spec and display checklist: see **Split of duties** above.

---

## 2. Fixed constraints (do not violate)

| Constraint | Meaning in code |
|---|---|
| League size invariant | Never insert a 129th team; never rewrite schedule topology |
| Slot replacement | Schedule / FTD / standings stay keyed to the **replaced ObjectId** |
| Per-franchise overlay | Identity lives on `franchises.team_builder`; core `teams`/`players` read-only |
| Single entry | Wizard + Apply only; no mid-save edit UI |
| No broken images | Custom art goes through `getTeamAssetPath`; terminal fallback is generic, never a 404 path |
| Soft budget only | Over-budget imports still apply; eligibility is metadata, not a hard block |

---

## 3. Identity model (read this first)

Three layers. Conflating them is how Team Builder franchises break sim.

```
Structural (never custom names)
  object_id / user_team_object_id  →  schedule pairs, FTD.team_id, standings, load paths
  team_id slug (e.g. HARDWOOD_FIELDS)  →  game-doc teams{} keys, some box-score paths

Identity / keys (always core)
  teams.name (e.g. Hardwood Fields)  →  TeamManager.name, score{}, matchup gate, init/sim home_team/away_team

Display only (resolver at the edge — response serializers / chrome)
  overlay name (e.g. Hanson)  →  TeamManager.display_name, summary teams[*].display_name,
                                  play-next home_display/away_display, rankings labels
```

| Identifier | Example | Used for |
|---|---|---|
| `object_id` | `69a6fcb6…` | Slot key = `str(teams._id)`. Schedule `(away_id, home_id)`, FTD `team_id`, `user_team_object_id`, resolver key |
| `team_id` (slug) | `HARDWOOD_FIELDS` | Core `teams.team_id`; game document map keys |
| Core name | `Hardwood Fields` | `TeamManager.name`, `score{}` keys, simulate-quarter matchup gate, URL `home`/`away` |
| Display name | `Hanson` | Chrome only — never construction, persistence keys, or matchup equality |
| Player IDs | UUIDs | Unrelated layer — do not use as team keys |

**The rule:** resolve at the edge, on the way out. The display resolver belongs in response serialization only — never in object construction, persistence, or anything used as a key. Join / load by ObjectId. Matchup gate stays **strict** core-name equality.

### Why this matters (known failure mode)

v1 leak: resolver fed construction (`TeamManager.name` = Hanson) and init-game rewrote request names to display. Court then sent core `Hardwood Fields` while GM held display → strict gate `400 game_id belongs to a different matchup`. A tolerant gate would have hidden the leak and allowed display-keyed game docs.

**Phase 0 fix:** `.name` = core; `.display_name` = overlay; play-next emits core `home`/`away` + ObjectIds + `*_display` for chrome; init-game never rewrites via resolver; simulate-quarter gate is strict again.

Helpers (structural matching — not the matchup gate):

- `teams_match_for_franchise(a, b)` — `BackEnd/utils/franchise_geek_points.py`
- `gm_team_matches_ref(gm_team, ref)` — playbook / team-pick helpers

Regression: `tests/test_tb_matchup_identity.py`. Score-dict consumers: `../projects/mod-system/team-builder-score-dict-consumers.md`.

---

## 4. Data model

### 4.1 Franchise document overlay

Field: `franchises.team_builder` (`TEAM_BUILDER_FIELD` in `franchise_team_display.py`).

Written **once** at Apply. Shape (authoritative writer: `team_builder_apply`):

```python
{
  "replaced_object_id": "<ObjectId str>",  # slot key — never changes
  "replaced_name": "Hardwood Fields",      # core name at Apply time (orientation copy)
  "name": "Hanson",                        # display name
  "abbreviation": "HAN",                   # 3 chars
  "mascot": "...",
  "city_state": "...",
  "primary_color": "#...",
  "secondary_color": "#...",
  "accent_color": "#...",
  "jersey_preset": 1,                      # 1–5
  "asset_strategy": "generated",
  "roster_mode": "keep" | "generate" | "import",
  # plus budget snapshot fields on the franchise root (see §7)
}
```

Also set on the franchise at init/Apply:

| Field | Meaning |
|---|---|
| `user_team_id` | **Custom display name** (baked at write time) |
| `user_team_object_id` | Replaced slot ObjectId string |
| `online_eligibility` | Soft flag from budget eval at Apply |
| `hasEverExceededBudget` | Set once at Apply; never cleared |
| `roster_shape_at_creation` | `{team_total, top5_total, max_player}` — unread in v1, required for future exploit closure |

### 4.2 What stays on the core slot

| Store | Key | Unchanged by overlay? |
|---|---|---|
| `schedule` weeks | `(away_id, home_id)` ObjectIds | Yes — still the replaced ObjectId |
| `franchise_team_data` | `franchise_id` + `team_id` (= slot ObjectId) | Yes |
| `franchise_players_data` | `franchise_id` + `player_id` | Roster may be replaced; `meta.team` rewritten to custom name on Apply for import/generate |
| Universal `teams` / `players` | — | **Never written** |

### 4.3 Resolver API

`BackEnd/utils/franchise_team_display.py`:

| Function | Role |
|---|---|
| `get_team_builder_overlay(franchise)` | Overlay dict or `None` |
| `resolve_team_display(franchise, team_object_id, core_doc=…)→ dict` | Name, colors, mascot, abbr, `is_custom`, `asset_strategy`, `replaced_name`, … |
| `resolve_team_name_map(franchise, team_ids=…)` | ObjectId → display name map |

**Pass-through:** no overlay, or ObjectId ≠ `replaced_object_id` → core `teams` values unchanged.

---

## 5. Shared producers (display + assets)

**Policy:** intercept at shared producers, not 58 FE call sites. Future screens inherit resolution automatically.

### 5.1 Display producers

| # | Producer | Location |
|---|---|---|
| 1 | `_format_team_name_map(franchise=…)` | `franchise_routes.py` → `resolve_team_name_map` |
| 2 | Season schedule payload | name lookup via resolver |
| 3 | `_ftd_team_display` | `community_highlights.py` (ATL / highlights) |
| 4 | `_franchise_summary_for_list` | mode-select slot cards |
| 5 | `GET /roster?franchise_id=` | identity fields on response |
| 6 | `TeamManager.__init__` | name/colors/mascot; custom-name → overlay → core `_id` |
| 7 | Practice Squad parent labels | `_format_team_name_map(franchise_doc)` |
| 8 | `POST /franchise/play-next-game` | `home`/`away` strings via `resolve_team_display`; **ids remain ObjectIds** |

Identity / chrome inventory: `team-builder-identity-inventory.md`.

### 5.2 Asset producer

`getTeamAssetPath(teamNameOrSlug, assetKey, visualOverride)` in `FrontEnd/static/common.js`.

- Custom overlays go **through** this function (not around it).
- Server franchise payload is source of truth for visuals; `FranchiseLS` `team_builder_visual` is a **warm cache only** — must not be required for correct art (fresh browser / cleared storage must hydrate from API).
- Terminal fallback: generic art (`general`), never a path that 404s.
- Generated art: `FrontEnd/static/js/shared/teamGeneratedArt.js` (initials + colors + jersey presets).

**Banner convention:**

| Asset | File | Use |
|---|---|---|
| Full banner | `{slug}_banner_primary.jpg` | Detail / FCC / court chrome |
| Card banner | `{slug}_banner_card.webp` (~400px wide) | Picker grid / first viewport |

Generated custom art matches card aspect so custom programs never request missing core files.

---

## 6. Create / Apply flow

### 6.1 UX path (FE)

1. `franchise-select-team` — pick existing program **or** enter Team Builder.
2. Wizard: `FrontEnd/static/team-builder.html` + `team-builder.js` + `team-builder.css`.
3. Steps: **Slot (0) → Identity (1) → Colors (2) → Roster optional (3) → Review (4)**.
4. Slot picker reuses shared `TeamPicker` (`FrontEnd/static/js/shared/teamPicker.js`); selection key = `object_id`.
5. Cancel returns to team-select with `home_slot` preserved; **no franchise doc yet**.

### 6.2 Apply endpoint

`POST /franchise/team-builder/apply` — `team_builder_apply` in `franchise_routes.py`.

Order of operations:

1. Validate `replaced_object_id`, name, 3-char abbreviation uniqueness vs `slice(0,3)` of other core names.
2. Allocate `home_slot`.
3. Build overlay dict.
4. `FranchiseManager.initialize_season(user_team_id=custom_name, user_team_object_id=replaced_oid, …)` — schedule still ObjectId-keyed to the slot.
5. Optional roster replace (`keep` | `generate` | `import`) via `BackEnd/utils/team_builder_roster.py`.
6. Evaluate soft budget; persist eligibility + shape flags.
7. `$set` `team_builder` overlay + eligibility fields on the franchise.
8. Return franchise id + overlay + eligibility for FE navigation into FCC.

**Write-time fact:** at create there are **no** `season_news` strings and **no** season game docs yet. News/games are written later, so they can resolve names after the overlay exists. FPD `meta.team` + `user_team_id` **are** written at create and rewritten by Apply when roster mode requires it.

### 6.3 Supporting endpoints

| Endpoint | Role |
|---|---|
| `GET /franchise/team-builder` (page) | Serves wizard HTML |
| `GET /franchise/team-builder/slot-roster.csv` | Download replaced slot’s roster for import editing |
| `GET /teams` | Additive fields: `conference`, `region`, `team_id`, `object_id` |

---

## 7. Budget / online eligibility

Constants: `BackEnd/constants/team_builder_budget.py`.

| Limit | Value | Principle |
|---|---|---|
| Team total (core-12 sum) | 6,400 | ~P90 of league team totals |
| Top-5 sum | 3,950 | League max top-5 (~3,954) |
| Per-player ceiling | 1,035 | League max player |
| Per-player floor | 24 | League min; applies to top 12 only |

Core-12 attrs: `SC SH ID OD PS BH RB ST AG ND IQ FT` (CH/EM/MO excluded; randomized at init like everyone else).

`evaluate_roster_budget(player_attrs)` → soft result. **Never blocks Apply.** Over-limit CSV still imports.

**Eligibility freezes at Apply** — never recomputed for the life of the franchise. Budget constrains *authored* input, not sim outcomes (camp cuts, development, etc.).

`online_eligibility` is forward-looking metadata only. **Do not build online gating or matchmaking** until that product exists.

---

## 8. Roster modes

`BackEnd/utils/team_builder_roster.py` (+ tests under `BackEnd/tests/test_team_builder_roster.py`).

| Mode | Behavior |
|---|---|
| `keep` | Slot’s cloned FPD roster unchanged (fast path) |
| `generate` | New fictional players at slot talent band; meter figures are **estimated** until Apply |
| `import` | CSV → validated rows; required: `first_name`, `last_name`, `class_year` (FR/SO/JR/SR). Position not required |

After import/generate, FPD `meta.team` and franchise `user_team_id` use the custom name; FTD still keyed by replaced ObjectId.

---

## 9. Gameplay path (franchise + overlay)

### 9.1 Play next → lineup → court

1. FCC calls `POST /franchise/play-next-game` → `{ home, away, home_id, away_id, week, … }` with **display** names and **ObjectId** ids.
2. FCC builds `/set-lineup.html?...&home=&away=&home_id=&away_id=`.
3. Lineup / court / Phaser always attach `home_id`/`away_id` on `init-game` and `simulate-quarter` payloads (`set-lineup.js`, `bootGame.js`, `gameScene.js`).
4. Do **not** fall back structural id query params to display names.

### 9.2 init-game

`POST /api/init-game` (`api.py`):

- Accepts optional `home_id` / `away_id`.
- Franchise mode: `load_ftd_data_for_team(franchise_id, team_id, team_name)` prefers ObjectId; falls back to core name, then overlay custom name → `replaced_object_id`.
- When ids present, resolves display names via `resolve_team_display` before constructing `GameManager`.
- `GameManager` / `TeamManager` apply overlay onto `.name` / colors; score dict uses **`gm.home_team.name` / `gm.away_team.name`** (stable for that game).

### 9.3 simulate-quarter matchup gate

When a cached GM exists for `game_id`, sides must match via ObjectId/slug/display helpers — **not** raw string equality of request name vs `gm.*.name`.

`QuarterSimulationRequest` includes optional `home_id` / `away_id`.

### 9.4 In-game name-keyed maps (explicit non-goal for v1)

Live `score[team.name]`, box maps, etc. stay keyed by the GM’s chosen display name for that game. Do **not** rewrite those to ObjectId in a casual pass — large and high-risk; unnecessary if init + matchup gate stay consistent.

---

## 10. Primary files (map)

| Area | Path |
|---|---|
| Resolver | `BackEnd/utils/franchise_team_display.py` |
| Apply + play-next display | `BackEnd/api/franchise_routes.py` |
| Budget constants | `BackEnd/constants/team_builder_budget.py` |
| Roster replace / CSV | `BackEnd/utils/team_builder_roster.py` |
| Identity match helpers | `BackEnd/utils/franchise_geek_points.py` |
| Team overlay at runtime | `BackEnd/models/team_manager.py` |
| Score keys after overlay | `BackEnd/models/game_manager.py` |
| init / sim / FTD load / gate | `BackEnd/api/api.py` |
| Roster load overlay name | `BackEnd/utils/roster_loader.py` |
| CE / crowd id resolve | `BackEnd/utils/home_crowd.py` |
| Playbook team pick | `BackEnd/api/gameplan_routes.py`, `team_settings_manager.py` (`gm_team_matches_ref`) |
| Wizard | `FrontEnd/static/team-builder.{html,js,css}` |
| Picker | `FrontEnd/static/js/shared/teamPicker.js` |
| Assets | `FrontEnd/static/common.js` (`getTeamAssetPath`), `teamGeneratedArt.js` |
| Visual cache | `FrontEnd/static/js/shared/franchiseLocalStorage.js` (`team_builder_visual`) |
| FCC hydrate / play URL | `FrontEnd/static/franchise-command-center.js` |
| Lineup / court ids | `FrontEnd/static/set-lineup.js`, `js/phaser/bootGame.js`, `gameScene.js` |

---

## 11. Tests

| Test | Covers |
|---|---|
| `tests/test_tb_matchup_identity.py` | Strict core-name gate; display payload rejected; ObjectId helpers for FTD/schedule |
| `tests/test_franchise_geek_points.py` (`gm_team_matches_ref_…`) | Display rename vs ObjectId/slug |
| `BackEnd/tests/test_team_builder_budget.py` | Soft eligibility math |
| `BackEnd/tests/test_team_builder_roster.py` | Roster replace / import helpers |

When verifying staging: confirm `franchises.team_builder` present, `user_team_object_id` == core slot, core `teams`/`players` unchanged, Sim Full / Play Quarter no longer 400 on matchup, UI shows custom name.

---

## 12. Explicit non-goals (v1)

- Rewrite schedule pairs or FTD to store the custom string as the structural key
- Mutate core `teams` / `players`
- Mid-franchise Team Builder editing / undo after Apply
- Logo upload, multi-slot replace, sharing/community browser
- Online matchmaking gated on `online_eligibility`
- Rewriting all in-game `score[team.name]` maps to ObjectId

---

## 13. Agent checklist (before changing TB)

1. Will this compare or load teams by **display name** when `franchise_id` is present? Prefer ObjectId / `teams_match_for_franchise` / `gm_team_matches_ref`.
2. Will a new UI surface show team identity? Prefer an existing producer or `resolve_team_display` — do not hard-read `teams.name` for the user slot.
3. Will art break for `asset_strategy: generated`? Route through `getTeamAssetPath`; hydrate from server payload, not LS alone.
4. Is the franchise missing `team_builder`? Your path must no-op.
5. Are you about to “fix” eligibility by recomputing mid-season? Don’t — frozen at Apply by design.
