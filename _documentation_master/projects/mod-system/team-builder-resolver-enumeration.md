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

## Write-time confirmation (pre-implement)

| Check | Result |
|---|---|
| (a) No `season_news` at franchise create | **True** — news written on week completion |
| (b) No game docs at franchise create | **True** — games created on play |
| Related | FPD `meta.team` + `user_team_id` **are** written at create — Apply bakes custom name into both |

## Remaining call sites covered by producers

FE surfaces that only render API payloads (FCC, schedule.html, standings, recruiting maps fed by `_format_team_name_map`, box-score roster colors, live game TeamManager snapshots) inherit overlay through the producers above. Hard-coded Core-8 coach art maps and non-franchise tournament mode are out of Team Builder overlay scope.
