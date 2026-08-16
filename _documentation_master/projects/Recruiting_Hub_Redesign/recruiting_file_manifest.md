# Recruiting — File Manifest

Everything in the repo touching Recruiting. Built 2026-08-16 for the Recruiting UX
improvement effort. Paths are repo-relative from `gob-simplified/`.

Verified live-vs-dead by tracing `<script>` tags and nav links — see §7 for what to skip.

---

## 1. Live screens

Four pages. The Hub is the shell; the other three are phase pages it links into.

| Screen | HTML | JS | CSS |
|---|---|---|---|
| **Recruiting Hub** (phase-aware shell) | `FrontEnd/static/recruiting.html` | `FrontEnd/static/recruiting-hub.js` | `recruiting-spine.css`, `recruiting-dock.css`, `recruiting-signing.css`, `recruiting-results-hub.css` |
| **Recruiting Orders** (signing board, wk 35) | `FrontEnd/static/recruiting-orders.html` | `FrontEnd/static/recruiting-orders.js` | `recruiting.css` |
| **Invites** (wks 20–26) | `FrontEnd/static/recruiting-invites.html` | `FrontEnd/static/recruiting-invites.js` | `recruiting.css` |
| **Results** | `FrontEnd/static/recruiting-results.html` | `FrontEnd/static/recruiting-results.js` | `recruiting-results-hub.css` |

All CSS lives in `FrontEnd/static/`.

## 2. Shared recruiting modules

| File | Role |
|---|---|
| `FrontEnd/static/recruiting-common.js` | Data fetch, attr keys, query context. Loaded by all 4 pages. |
| `FrontEnd/static/recruiting-spine.js` | Phase strip / calendar rendering |
| `FrontEnd/static/recruiting-spine-data.js` | Phase + calendar model |
| `FrontEnd/static/recruiting-lean-ladder.css` | Lean ladder component |
| `FrontEnd/static/recruiting-spine-gallery.html` | Dev-only component gallery for the spine |

Cross-app shared deps the recruiting pages rely on:

- `FrontEnd/static/js/shared/rtBucket.js` + `FrontEnd/static/css/rt-buckets.css` — RT tier display
- `FrontEnd/static/js/shared/playerYear.js`
- `FrontEnd/static/js/shared/attributeTooltips.js`
- `FrontEnd/static/js/config/api-config.js` — recruit portrait resolution (~lines 290–375)

## 3. Entry points & adjacent surfaces

| File | Recruiting role |
|---|---|
| `FrontEnd/static/franchise-command-center.js` | Recruits tab + all 5 links into recruiting (`:1598`, `:2106`, `:3956`, `:3964`, `:4073`) |
| `FrontEnd/static/franchise-command-center.html` / `.css` | FCC recruit cards markup + styling |
| `FrontEnd/static/training.js` | `:1452-1453` — Run Training is where recruiting **execution** actually fires |
| `FrontEnd/static/player-detail.js` / `.css` | Recruit background block |
| `FrontEnd/static/team-roster-view.js` | "Practice Squad + Recruits" roster section |
| `FrontEnd/static/js/shared/scoutingReport.js` | Scouting report on recruits |
| `FrontEnd/static/js/shared/tierEmblem.js` | Tier emblems |
| `FrontEnd/static/js/shared/bigNewsModals.js` | Recruiting-results modal |

## 4. Tutorials

- `FrontEnd/static/tutorial-recruiting.html`
- `FrontEnd/static/tutorial-scouting.html` — links into recruiting at `:368`
- `FrontEnd/static/js/shared/gobTutorialHub.js`
- `FrontEnd/static/js/shared/gobTutorialNav.js`
- `FrontEnd/static/js/shared/gobTutorialAlerts.js`
- `FrontEnd/static/js/shared/gobTutorialAlertResume.js`

## 5. Backend

| File | Recruiting role |
|---|---|
| `BackEnd/api/franchise_routes.py` | **The core.** `/franchise/recruits` (`:10645`), `/franchise/recruiting-orders`, FCC payload assembly (`:9332-9436`), results modal (`:3978`), lean updates (`:7098-7116`) |
| `BackEnd/models/recruit_sets.py` | Recruit set model |
| `BackEnd/services/recruit_image.py` | Portrait generation |
| `BackEnd/services/r2_images.py` | R2 asset delivery |
| `BackEnd/api/api.py` | `:6927-7103` — Practice Squad + Recruits roster payload |
| `BackEnd/utils/scouting_utils.py` | Scouting fog / reveal |
| `BackEnd/utils/rt_display.py` | RT formatting |
| `BackEnd/utils/cpu_week_pool.py` | CPU recruiting pool |

## 6. Documentation

| Doc | Covers |
|---|---|
| `_documentation_master/04_Franchise_Mode_Systems/Recruiting_System.md` | **Primary system doc** — phases, leans, signing |
| `_documentation_master/projects/Recruiting_Hub_Redesign/recruiting_hub_implementation_spec.md` | Current redesign spec (7 prompts, 0–6; Prompt 0 shipped) |
| `_documentation_master/projects/Recruiting Hub Deliverables/CC Recruiting Hub - Implementation Prompts.md` | Prompt-by-prompt build plan |
| `_documentation_master/00_Operations/Recruit_Image_System.md` | Portrait pipeline / R2 |
| `_documentation_master/projects/Website_Copy/faqs.md` | Player-facing recruiting copy |
| `_documentation_master/projects/bugs.md` | Open recruiting bugs |

### Prior design deliverables — high-value context

`_documentation_master/projects/Recruiting Hub Deliverables/` — output from the last
design round:

- 8 HTML mockups: Spine, Invite Dock, Signing Board, Results, D5 Audit, FCC Recruits Tab, FCC Recruiting Cards
- 6 `.jsx` prototypes: `spine-dock`, `spine-lean`, `spine-phase`, `spine-pool`, `spine-results`, `spine-signing`
- Source CSS: `recruiting-spine.css`, `recruiting-dock.css`, `recruiting-signing.css`, `recruiting-results.css`

## 7. Dead / legacy — skip these

| File | Why |
|---|---|
| `FrontEnd/static/recruiting.js` | **Unreferenced.** `recruiting-hub.js` took over `recruiting.html`. |
| `FrontEnd/static/Recruiting Orders v2.html` | Stale mockup sitting in `/static` |

## 8. Tests

- `tests/test_recruiting_week36.py`
- `tests/test_recruit_manager.py`
- `tests/test_recruit_archetypes.py`
- `tests/test_recruit_detail_endpoint.py`
- `tests/test_player_detail_recruit_background.py`
- `tests/test_weekly_recruiting_training_flow.py`

## 9. Content pipeline (not UX, but recruits come from here)

- `scripts/recruit_sets/` — `build_recruit_set.py`, `build_recruit_images.py`, `sign_recruits.py`, `load_recruit_sets.py`, `normalize_recruit_years.py`, `apply_recruit_uniform.py`, `upload_recruit_images_to_r2.py`
- `assets_staging/recruits/` — staged portrait assets

---

## Suggested reading order for a design review

1. `Recruiting_System.md` — what the system does
2. `recruiting_hub_implementation_spec.md` — where the redesign left off
3. `recruiting.html` + `recruiting-hub.js` — the shell as built
4. `recruiting-orders.js`, `recruiting-invites.js` — the two heavy phase screens
5. `Recruiting Hub Deliverables/` — the visual language already agreed on
6. `franchise-command-center.js` — how users get in
