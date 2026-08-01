# Team Builder — team identity inventory

**Rule:** resolve at the edge, on the way out — never in construction, persistence, or anything used as a key. Core identity (`name`, slug `team_id`, ObjectId) stays stable; display chrome is overlay-resolved for rendering only.

**Legend — role:** identity = lookup / key / comparison / persistence; chrome = rendered to a user; both.  
**Overlay:** yes / no / partial.

This document replaces `team-builder-resolver-enumeration.md`. It covers derived forms and marks identity vs chrome.

---

## Part 1 — Where identity is derived or rendered

### A. Canonical resolvers & session overlay

| Location | Form(s) | Role | Overlay |
|---|---|---|---|
| `BackEnd/utils/franchise_team_display.py` `get_team_builder_overlay` | overlay dict | identity (load) | yes |
| same `resolve_team_display` | display name, abbreviation, mascot, colors, `asset_strategy`, `replaced_name`; core `object_id` / `team_id` | both | yes |
| same `resolve_team_name_map` | ObjectId → display full name | chrome (keys = identity) | yes |
| same `resolve_team_abbreviation` / `abbr_from_name` | abbreviation | chrome | yes |
| `BackEnd/utils/team_slug.team_id_for_display_name` / `identity_slugs_for_display_name` | name → stored `teams.team_id` (lookup) | identity bridge | n/a |
| `BackEnd/utils/team_slug.slug_from_display_name` | path slug from display name | chrome / custom only (not core identity) | n/a |
| `FrontEnd/static/common.js` hydrate / `getActiveTeamBuilderVisual` | visual: name, abbr, colors, replaced_* | both | yes |
| same `resolveTeamAbbreviation` / `deriveTeamAbbreviationFromName` | abbreviation | chrome | yes / no |
| same `teamBuilderVisualMatchesName` | match name / abbr / replaced / slug | identity | yes |
| same `getTeamAssetPath` / `nameToTeamSlug` | asset path / path slug | chrome | yes / pure |
| `FranchiseLS` `team_builder_visual` | cached visual | both | yes |

### B. Persist / Apply / TeamManager / game wire

| Location | Form(s) | Role | Overlay |
|---|---|---|---|
| `team_builder_apply` | overlay name/abbr/mascot/colors; bakes `user_team_id`, FPD `meta.team`, FTD colors | both | yes (writer) |
| Apply abbr uniqueness | `abbr_from_name(other)` vs chosen abbr | identity (validation) | uses shared derive |
| `TeamManager.__init__` | `.name`=core; display/colors/mascot/abbrev from resolver | both | yes |
| `GameManager` score / possession | keyed by core `.name` | identity | no |
| `summarize_game_state` | `name`=core; `display_name`; `abbreviation`; colors; score by core | both | yes |
| play-next / mode-resume | core `home`/`away`; `*_display` chrome | both | yes / partial |

### C. Franchise API chrome edges (selected)

| Location | Form(s) | Role | Overlay |
|---|---|---|---|
| list / FCC top / roster | display name, abbr, colors, mascot | chrome | yes |
| FCC rankings / team-traits / team-stats label | display name + overlay colors | chrome | yes |
| `/teams?franchise_id=` | core `name`; overlay colors + `display_name` for replaced slot | both | yes when fid |
| standings | `name`=core; `display_name`=overlay | both | yes |
| schedule / news name maps | ObjectId → display | chrome | yes |
| `/recruit` lean_display | display name | chrome | yes |
| training-report `recruiting_team_name_map` | display names | chrome | yes |
| `/franchise/recruiting-data` `team_name_map` | **core** names | chrome | no |
| championship moments `_team_view` | name + primary via resolver | chrome | yes |
| player-image paint | colors/mascot via resolver | chrome | yes |
| leaders `meta.team` | baked FPD name | chrome | partial |

### D. BE identity helpers

| Location | Form(s) | Role | Overlay |
|---|---|---|---|
| ObjectId / `teams.team_id` / score keys | identity keys | identity | n/a |
| `_canonical_team_name` / `_norm_slot` / `_normalize_team_name_key` | space/hyphen→`_`; **no** punct strip | identity | no — must not silently accept display |
| Boundaries using `identity_slugs_for_display_name` | display → stored `team_id` (derive only if custom) | bridge | explicit at call site |
| `team_id_resolver` / geek_points / scoreboard enrichment | name/slug → ObjectId | identity | no |
| leak detector (name + derived + core palette colors) | scan only | chrome invariant | yes |

### E. FE render (selected)

| Location | Form(s) | Role | Overlay |
|---|---|---|---|
| court / box-score / potg / sim timeline | `display_name\|\|name` chrome; core for score | both | yes |
| FCC standings / schedule maps / play-next | display labels; ids for keys | both | yes |
| standings.html / rankings.html (standalone) | single field as provided | chrome | producer-dependent |
| recruiting lean tokens | abbreviation via `resolveTeamAbbreviation` | chrome | yes |
| team-builder wizard preview | abbr + full name | chrome | n/a |
| DOM leak detector | name needles + core-palette colors | chrome scan | yes |

---

## Part 2 — Independent implementations by form

### Abbreviation

| Implementation | Algorithm | Agree? |
|---|---|---|
| Overlay `abbreviation` via `resolve_team_display` / `resolve_team_abbreviation` / TM | stored 3-char | canonical when custom |
| BE `abbr_from_name` + FE `deriveTeamAbbreviationFromName` | alnum → `[:3].upper()`; empty `???` | **agree** (shared) |
| Apply uniqueness + wizard `validateAbbr` | same derive | **agree** |
| QA mock `recruiting-spine-data` | raw `slice(0,3)` / rival map | differs; mock only |

### Path slug (display → folder)

| Implementation | Algorithm | Agree? |
|---|---|---|
| BE `slug_from_display_name` | lower; strip `'./`; hyphen→space; spaces→`_` | canonical BE |
| FE `nameToTeamSlug` | same | **agree** with BE |
| Identity `_canonical_team_name` / `_norm_slot` | upper; space/hyphen only; keeps `'` | **different job** — not unified |

### Initials / leak needles

| Implementation | Notes |
|---|---|
| `teamGeneratedArt.initialsFromName` | prefer abbr / resolver; else word initials |
| Leak needles | alnum[:3], slug variants, multi-word initials — scanner only |

### Colors

| Implementation | Source |
|---|---|
| `resolve_team_display` / TM / FCC / roster / traits / rankings / `/teams?franchise_id=` / championship / player-image | overlay when custom |
| Legacy `/teams` without fid; some tournament caches | core only |

---

## Display → identity slug (Queen's Guard)

**Live case:** core display name `Queen's Guard`; stored `team_id` / asset folder `queens_guard` / `QUEENS_GUARD`.

Identity normalizers that only map space/hyphen → `_` produce `QUEEN'S_GUARD` and **must not** be taught to strip punctuation (silent tolerance).

**Bridge:** look up stored `teams.team_id` by display name (`team_id_for_display_name` / `identity_slugs_for_display_name`) at explicit boundaries (roster file path, slot-key match, box-side infer, EOG box fallback, resume tokens, team_id_resolver). Derive (`slug_from_display_name`) only for custom programs with no stored slug.

Asset slugs and identity slugs stay separate families; do not collapse them into one normalizer.

---

## Known anomaly — Couer d'Alene

For **127 of 128** core teams, three string forms agree (case aside):

1. on-disk asset folder under `FrontEnd/static/images/teams/<slug>/`
2. stored `teams.team_id` (from `teams/128_teams.txt` / Mongo)
3. FE/BE derived path slug (`nameToTeamSlug` / `slug_from_display_name`)

**Couer d'Alene is the single exception:**

| Form | Value |
|---|---|
| Display name | `Couer d'Alene` |
| Stored `team_id` | `couer_d_alene` |
| FE/BE derived slug | `couer_dalene` |
| Asset folder | `couer_dalene/` |

Apostrophe handling diverged historically: Queen's Guard / River's Edge / Pike's Prep drop `'` (`queens_guard`, …); Couer's stored id turns `d'` into a separator (`couer_d_alene`) while derivation strips it (`couer_dalene`). No single derive rule can match both conventions.

**Do not "fix" the stored `team_id`.** It is referenced in `teams_uniforms.json`, gameplans, and persisted game docs.

**Tripwire — this team and only this team breaks if:**

- code uses stored `team_id` as an **asset path** (`…/couer_d_alene/…` — folder does not exist), or
- code **derives** a slug for **identity** matching (`couer_dalene` ≠ stored `couer_d_alene`).

Identity boundaries must look up the stored id; asset paths must keep using the derived / `CORE_TEAM_ASSET_SLUGS` family. CI: `tests/test_core_team_slug_agreement.py`.

---

## Pass-through

`resolve_team_display` / `resolve_team_name_map` return core values unchanged when `franchise.team_builder` is absent.
