# Team Builder §3.2 — Display surface enumeration (PR checklist)

**Decision:** Intercept at the six shared producers, not 58 FE call sites.
**Coverage requirement unchanged:** a user must never see the replaced program's identity.

## Shared producers wired

1. `_format_team_name_map` (`franchise_routes.py`) — optional `franchise=` → `resolve_team_name_map`
2. Schedule payload (`_build_season_schedule_payload`) — name lookup via resolver
3. `_ftd_team_display` (`community_highlights.py`) — ATL / highlights
4. `_franchise_summary_for_list` — mode-select slot cards
5. `GET /roster` — identity fields when `franchise_id` present
6. `TeamManager.__init__` — colors/name/mascot overlay (+ custom-name → ObjectId fallback)
7. Practice Squad `_format_team_name_map(franchise_doc)` — parent team labels

## Banner sizing convention (locked before §3.3)

| Asset | Filename | Size | Use |
|---|---|---|---|
| Full banner | `{slug}_banner_primary.jpg` | 1920×679 | Detail views only (FCC header, loading, game chrome) |
| Card banner | `{slug}_banner_card.webp` | **400px wide**, aspect preserved (~141px), WebP q80 | Picker grid / first viewport |

Generated custom art matches the **card** aspect for `banner_card` / `banner_primary` data URLs so custom programs never request missing files. Core picker uses `banner_card` with onerror → `banner_primary`.

## Pass-through guarantee

`resolve_team_display` / `resolve_team_name_map` return core `teams` values unchanged when `franchise.team_builder` is absent. Existing franchises stay byte-identical on display fields.

## Display audit (Phase 3)

User slot must show overlay name (e.g. Hanson); opponents stay core names. Structural keys unchanged.

| Surface | Status |
|---|---|
| play-next `home`/`away` | Resolved via `resolve_team_display` (ids still ObjectIds) |
| `_format_team_name_map` / schedule / standings | Already resolver-backed |
| `_franchise_summary_for_list` / FCC | Already resolver-backed |
| `GET /roster` + `franchise_id` | Overlay identity fields |
| `TeamManager` / init-game score keys | Display name after overlay; score uses `gm.*.name` |
| Court / lineup URL `home`/`away` | Carry play-next display names; ObjectIds in `home_id`/`away_id` |
| ATL / community highlights | `_ftd_team_display` → resolver |

Non-goal: rewriting in-game `score[team.name]` maps to ObjectId.

## Write-time confirmation (pre-implement)

| Check | Result |
|---|---|
| (a) No `season_news` at franchise create | **True** — news written on week completion |
| (b) No game docs at franchise create | **True** — games created on play |
| Related | FPD `meta.team` + `user_team_id` **are** written at create — Apply bakes custom name into both |

## Remaining call sites covered by producers

FE surfaces that only render API payloads (FCC, schedule.html, standings, recruiting maps fed by `_format_team_name_map`, box-score roster colors, live game TeamManager snapshots) inherit overlay through the producers above. Hard-coded Core-8 coach art maps and non-franchise tournament mode are out of Team Builder overlay scope.

## Identity plumbing inventory (Phase 0 — TB name vs ObjectId)

Structural keys: Mongo **ObjectId** (`object_id` / `user_team_object_id`) and game-doc slug `team_id` (e.g. `HARDWOOD_FIELDS`). Display names (Hanson / Hardwood Fields) are overlay-only. Never use `home_team`/`away_team` strings as the sole franchise matchup equality check.

### Compare (string name equality)

| Site | Note |
|---|---|
| `BackEnd/api/api.py` simulate-quarter matchup gate | Was `body.home_team != gm.*.name` — fails when overlay renames GM |
| `FrontEnd/static/set-lineup.js` new-matchup localStorage | Name-only `game_home`/`game_away` clear |
| `FrontEnd/static/set-lineup.js` `resolveTeam()` | Matches id **or** name string |
| `BackEnd/api/api.py` / `gameplan_routes.py` playbook team pick | `team_id == gm.*.team_id or == gm.*.name` |
| In-game score / box maps | Keyed by GM display name once init chooses it — leave alone in v1 |

### Navigate / payload

| Site | Note |
|---|---|
| `set-lineup.js` / `bootGame.js` / `gameScene.js` init + simulate | Must send `home_id`/`away_id` with names |
| `bootGame.js` resume / fallback URL builders | Must not fall back `home_id` to display name |
| `franchise_routes.py` play-next | Returns ObjectIds + should emit **display** names via resolver |
| FCC play-next → lineup URL | Already carries both names and ids |

### Load (name-only when franchise present)

| Site | Note |
|---|---|
| `load_ftd_data_for_team` | Prefer explicit ObjectId; overlay-name fallback when core name miss |
| `init-game` / simulate-quarter FTD seed | Pass ObjectIds from request |
| `roster_loader` / `home_crowd` | Overlay / ObjectId-aware resolve |
| `TeamManager.__init__` | Already: custom name → overlay → core `_id` |

### Already OK

`teams_match_for_franchise`, geek-points / ATL / championships participant checks, play-next schedule ObjectId match, FCC side resolve, `playbookTeamId.js`.
