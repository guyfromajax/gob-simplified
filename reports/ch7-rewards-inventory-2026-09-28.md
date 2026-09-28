# Chapter 7 — Rewards & feedback inventory

Branch: `docs/ch7-rewards-inventory` (`~/gob-stats`, from `origin/develop`).  
Scope: **management UI** (Office, FCC, modals, Advance, recruiting hub surfaces that celebrate/commit). **Out of scope:** in-court animation / `feature/animation-reward` (only noted where EOG hands off to the locker room).  
Context: UX audit (`ux/ux-audit-2026-09-23`) — “rare moments lavish, weekly moments flat”; proposed ladder **EVERYDAY / WEEKLY / MILESTONE / SEASON PEAK**.  
Home Base (Ch7): planned offline **Trophy case** + **Coach career** — callouts below where data already exists.

---

## 1. Existing reward / feedback surfaces

### A. Coach’s Office (`office_digest` → `GOBOffice`)

| Surface | Trigger | Data (keys / route) | Frequency | Intensity today | Owner files |
|--------|---------|---------------------|-----------|-----------------|-------------|
| **Since last week — result card** | FCC Office tab render after CC load; digest built server-side | `GET /franchise/command-center/data` → `office_digest.result` (scores, `user_won`, `opponent_rank`, `round_name`, `leader` / `potg`, `headline` from `season_news`, box-score link) | Every CC visit while `result` populated (after user game finalized) | **Low–medium** — WIN/LOSS kicker, scores, leader line; subtle enter animation (`office-res`, `arriving` / `is-loss`) | `BackEnd/utils/office_digest.py` (`build_office_digest`), `FrontEnd/static/js/shared/officeHome.js`, `FrontEnd/static/css/office-home.css` |
| **What moved** | Same | `office_digest.what_moved`: `national_rank` {now, prev, delta}, `conference_standing`, `record`, `streak`, `attribute_changes[]` | Weekly after snapshot captured | **Medium** — rank/conf/record strip + attribute chips; no sound | `office_digest.py`, `officeHome.js` |
| **Team snapshot — moved_most** | Same | `office_digest.team_snapshot.moved_most` (from `office_week_snapshots` on franchise) | Weekly when measures shift | **Low** — text list of team measures | `office_digest.py` (`moved_most`), `officeHome.js` |
| **Recruiting wire rows** | Same | `office_digest.recruiting_wire.events[]` (lean gained/lost copy, direction class `up`/`dn`) | Invite weeks when events exist | **Low** — text rows, colour edge on up/down | `office_digest.py` (`recruiting_wire_digest`, `recruiting_lean_events`), `officeHome.js` |
| **Signing day column** | Same | `office_digest.signing_day` | Week 35 | **Low–medium** — compact signing summary | `office_digest.py`, `officeHome.js` |
| **Conference standings strip** | Same | `office_digest.conference_standings` | Most weeks | **Low** — table context, not celebratory | `office_digest.py`, `officeHome.js` |
| **Season preview (week 1)** | `office_digest.state === 'first_week'` | `season_preview`, `newcomers` | Once per season | **Medium** — opener framing | `office_digest.py`, `officeHome.js` |
| **Office todos** | Same | `office_digest.todos` from advance flags | Persistent until task done | **Functional** — not reward | `office_digest.py` (`build_todos`), `gobAdvance.js` |

**Snapshot dependency:** `capture_office_week_snapshot` runs during **week finalize** (before rank writer), stored on franchise as `office_week_snapshots` — enables rank/conf **delta** on the next visit. `BackEnd/api/franchise_routes.py` (~7887–7899), `office_digest.py` (`capture_office_week_snapshot`).

**Sounds:** none on Office render. Advance uses `confirm-1-lowervol.wav` via `gobAdvance.js` / `uiSfx.js`.

---

### B. FCC modal stack (load order)

Orchestrator: `franchise-command-center.js` after `GET /franchise/command-center/data` (~3820–3890). Competing-modal guard: `fccHasCompetingModal` (~4057).

| Surface | Trigger | Data | Frequency | Intensity | Owner files |
|--------|---------|------|-----------|-----------|-------------|
| **Championship Moments** | `pending_championship_moments[]` on CC payload | Built in `franchise_championship_moments.py`; dismissed `PATCH` consume | Rare (title runs, special wins) | **High** — full-screen overlay, team banner, green primary CTA | `championshipMoments.js`, `franchise_championship_moments.py`, `big-news-modals.css` (blocker list) |
| **Conference RS / Region modal** | `conference_rs_region_modal.eligible` | CC payload; season-stamped seen field | Postseason elimination beats | **High** | `conferenceRsRegionModal.js` |
| **Region bye modal** | `region_bye_modal_eligible` / payload | CC payload | Week 30 bye | **Medium–high** | `regionByeModal.js` |
| **Walk-On Welcome** | `walk_on_welcome_modal.eligible` | Snapshotted at `finish_season`; walk-on roster table | Season 2+ start | **High** — wide Sammy chrome, orange nav CTA | `walkOnWelcomeModal.js`, `walk-on-welcome.css` |
| **Recruit visit** | `recruit_visit_modal` (weeks 20–26) | CC payload + recruit row | Weekly in invite window | **Medium** — Sammy moment modal | `recruitVisitModal.js`, `sammy-modal.css` |
| **Big News — Bracket reveal** | `bracket_reveal_modal.eligible` | Bracket layout, seeds, tier; `markBracketSeen` | Once per reveal key (postseason) | **Very high** — trophy SVG, **gold gradient**, confetti (60), bracket animation | `bigNewsModals.js`, `big-news-modals.css`, `fcc-tournament-style-a.js` |
| **Big News — Bracket update** | `bracket_update_modal.eligible` | Same family, no reveal animation | After tournament rounds | **Medium** — no confetti | `bigNewsModals.js` |
| **Big News — Recruiting results (signed class)** | `recruiting_results_modal.eligible` | Signed recruits list, counts; `markRecruitingSeen` | After signing (pre–week-36 list era) / when modal armed | **High** — star seal, confetti (75), recruit cards with RT display | `bigNewsModals.js`, `_build_recruiting_results_modal_payload` in `franchise_routes.py` |
| **Cut players required** | `cut_required` + count | CC flags | Roster trim weeks | **Blocking** — not celebratory | `franchise-command-center.js` |
| **Archetype evolution** | `me.archetype_evolution_pending` (via auth me, consumed on run) | `/api/auth/me`; PATCH seen | When lead archetype changes (not first establish) | **Medium–high** — reuses arch-reveal chrome | `archetypeEvolutionModal.js`, `archetypeReveal.js` styles |
| **Tutorial alerts** | `GOBTutorialAlerts` on return / intercept Advance | Tutorial progress on user / franchise | First seasons | **Instructional** — can block Advance | `gobTutorialAlerts.js`, `gobAdvance.js` |
| **Alpha feedback prompt** | Auth bar after 4th/8th non-tutorial game | `/api/auth/me` alpha_feedback_* | Twice early alpha | **Medium** — purple accent, not green | `alphaFeedbackModal.js`, `authBarInit.js` |

**Big News queue:** one modal per `maybeShow` pass — bracket reveal → bracket update → recruiting results; retries every 1s if another overlay visible (`blockerVisible`, max 300 retries). `bigNewsModals.js`.

**Sounds:** Championship moment dismiss may call `click-tiny.wav`; most modals silent.

**Confetti:** `spawnConfetti` in `bigNewsModals.js` — colours `#f0c560`, `#d4a848`, `#2bd66a`, white.

---

### C. Recruiting hub (management, not court)

| Surface | Trigger | Data | Frequency | Intensity | Owner |
|--------|---------|------|-----------|-----------|--------|
| **Signing Day conference reveal** | Week 35 after submit / run | `/franchise/recruiting-data`, `week_35_recruiting_results`, `conferences` | Once per signing run | **High** — full-stage card playback (`#hub-reveal`, `.sd-*`) | `recruiting-hub.js`, `recruiting-signing.css` |
| **Week 36 results list** | Phase `results` | Same payload, `#hub-signings` browse cards | Once per season | **Medium** — list + PATCH seen | `recruiting-hub.js`, `recruiting-results-hub.css` |
| **Hub toasts** | Submit/run errors | Local | Rare | **Low** — error toast | `recruiting-hub.js` (`showToast`) |
| **Recruit visit modal** | Also on FCC (above) | — | — | — | — |

Signing CSS uses **gold/amber** for odds emphasis (`--gold`, amber action). No shared `uiSfx` hooks found in `recruiting-hub.js` for reveal beats.

---

### D. Advance / gating (`GOBAdvance`)

| Surface | Trigger | Data | Intensity | Owner |
|--------|---------|------|-----------|--------|
| **Green Advance button** | `office_digest.todos` + CC flags | Modes: play, training, cut-players, recruiting, finish-cpu-sims, view-recruiting-results, etc. | **Functional reward** — colour law aligned (green = one advance) | `gobAdvance.js`, `gob-components.css` |
| **Advance confirm sound** | Click Advance | `confirm-1-lowervol.wav` | Low | `uiSfx.js`, `gobAdvance.js` |
| **Training / play intercepts** | Tutorial | — | Blocks navigation | `gobTutorialAlerts.js` |

---

### E. Training & reports (post–training camp)

| Surface | Trigger | Data | Intensity | Owner |
|--------|---------|------|-----------|--------|
| **Training report** | After training session | `/franchise/...` training report payload; `player_attribute_display_movements` | **Medium on report page** — `change-gold` / `change-positive` for big gains, orange momentum card | `training-report.js`, `training-report.css` |
| **Office “Attributes” under What moved** | Digest only | Subset of training report movements | **Low on Office** — capped list + link “All changes” | `officeHome.js` |

Exceptional gain threshold drives **gold** text on report; Office shows plain attr chips without gold tier.

---

### F. Legacy / secondary FCC home tab

| Surface | Trigger | Data | Intensity | Owner |
|--------|---------|------|-----------|--------|
| **Last game / POTG block** | Home tab (legacy cards) | CC `last_game_summary` / game summary with `_calculate_potg_summary` | **Medium text** | `franchise-command-center.js`, `franchise_routes.py` (`_calculate_potg_summary`) |

Office tab is the primary “weekly story”; Home tab duplicates some game praise.

---

### G. Court-adjacent (handoff only — not Ch7 animation work)

| Surface | Trigger | Notes |
|--------|---------|--------|
| **Game completion popup** | EOG in Phaser | Routes to locker room / PGPC / phase B; can chain to championship moment check. **Owner:** `gameCompletionPopup.js` (excluded from animation-reward workstream). |
| **PGPC / Sammy post-game** | Tutorial / alpha paths | `sammyModal.js`, `postGamePressConference.js` |

---

### H. Mode Select / community (online reward *social*, not Office)

| Surface | Trigger | Data | Offline |
|--------|---------|------|---------|
| **Around The League** | Poll 20s | `/api/community/around-the-league` | Fails |
| **Leaderboard / highlights** | Load | `/api/auth/leaderboard`, `/api/community/highlights` | Empty / error |
| **Geek Points** | Awarded on finalize (win/loss) | `franchise_geek_points.py` → **user doc** (remote) | Not shown offline |

Relevant to **Coach career** on Home Base (online today via Settings `/api/auth/me`: `record`, `championships_total`).

---

## 2. Moments with weak or missing feedback

| Moment | Backend knows? | Where / how | Feedback today |
|--------|----------------|-------------|----------------|
| **Win / loss** | Yes — game + `results` | `office_digest.result`, finalize | Office result card; legacy Home POTG; **no** win/loss modal; community highlight (online) |
| **National rank change** | Yes — snapshot delta | `what_moved.national_rank` | Small chip on Office; no fanfare |
| **Conference place change** | Yes | `what_moved.conference_standing` | Same |
| **Record / streak** | Yes | `record`, `streak` on digest | Text + streak chip; no milestone thresholds |
| **Player attribute +1/+2** | Yes | `training_report` → `attribute_changes` | Office list (subset); report page styled |
| **RT letter change** | Partial — ratings in roster/report | Not surfaced as its own moment in digest | **Missing** as explicit feedback |
| **Team measure “moved most”** | Yes — snapshot | `team_snapshot.moved_most` | Quiet Office list |
| **Recruit lean gained/lost** | Yes — `recruiting_wire.events` | Lean event writers | Office wire row (up/down colour) |
| **POTG** | Yes — `_calculate_potg_summary` | `result.leader` on win | One line on result card |
| **Training breakthrough (“exceptional gain”)** | Yes — report thresholds | `training-report.js` | **Gold on report only**, not Office |
| **Practice Squad week results** | Yes — PS sim + news | `_append_franchise_week_news` (all-stars) | **News feed**, not Office modal |
| **Awards / All-League** | Yes — awards data | Awards browse (`awards.html` / tab); button gated post-season | Browse view, no moment modal |
| **Tournament round win/loss** | Yes | Bracket update modal (structural), not emotional | Update modal informational |
| **Championship / title** | Yes | `pending_championship_moments` | **Strong** modal |
| **Signing class** | Yes | Hub reveal + optional `recruiting_results_modal` | **Strong** (duplicate paths) |
| **Walk-ons joined** | Yes | Walk-on welcome modal | **Strong** (season start) |
| **Coach archetype established/evolved** | Yes — user counters | First: separate reveal; evolution modal | **Medium–high** |
| **Geek Points delta** | Yes — user game block | Computed on finalize; community highlight | **Invisible in franchise UI** except online leaderboard/highlight |
| **Season rollover / EOS** | Yes | `finish_season`, news | No single “season peak” Office beat (modals per sub-event) |

**UESS / new server work likely needed for:** explicit RT-letter-change events, record milestone thresholds (e.g. 20 wins), streak badges, unified “moment queue” priorities, offline coach-career aggregates if not derived from SQLite user stub.

---

## 3. Proposed intensity tier (draft for Jamie)

| Moment | Tier | Reasoning |
|--------|------|-----------|
| Lean wire row / small rank delta / routine attribute +1 | **EVERYDAY** | Already on Office; should stay quiet |
| Win/loss result card + What moved strip | **WEEKLY** | Core loop; needs richer treatment without modal noise |
| POTG line / team leader on loss | **WEEKLY** | Deserves emphasis on result card, not separate modal |
| Training exceptional gains | **WEEKLY** | Report already gold; mirror one highlight on Office |
| Recruit visit / invite-week wire | **WEEKLY** | Social/recruiting rhythm |
| Bracket update (advanced round) | **WEEKLY** (postseason) | Informational, not peak |
| Signing Day hub reveal + signed-class modal | **MILESTONE** | Season-defining; currently strong |
| Walk-On Welcome | **MILESTONE** | Season beat |
| Bracket reveal (first sight) | **MILESTONE** | Major postseason gate |
| Region bye / conf elimination modals | **MILESTONE** | **Unsure** — elimination vs celebration tone |
| Championship Moments / national title | **SEASON PEAK** | Already lavish |
| Week 36 league results / EOS rollover | **SEASON PEAK** | **Unsure** — list is flat today; could be peak with trophy case tie-in |
| Archetype first establish vs evolution | **MILESTONE** / **WEEKLY** | **Unsure** — first should be milestone; evolution maybe weekly |
| Geek Points awarded | **EVERYDAY–WEEKLY** | **Unsure** — invisible today; if surfaced, probably weekly summary not toast |
| Practice squad all-star news | **WEEKLY** | News only |
| Alpha feedback prompt | N/A (product) | Not in-game reward |

**Home Base Trophy case / Coach career (offline):** surface `championships_total`, title moments consumed, franchise list metadata (season/week/record), local awards if synced — **not** Geek Points or community highlights without remote.

---

## 4. Colour / sound vs colour law

**Law (summary):** green = single Advance; orange = saves / non-advancing commits; navy = user; blue = elite tier; orange not for primary forward progress.

| Surface | Colours / sound | vs law |
|---------|-----------------|--------|
| Office WIN/LOSS | CSS win/loss (green/red semantics in office-home) | Mostly OK |
| `Enter Franchise` / Advance | Green + `confirm-1-lowervol.wav` | **Aligned** |
| Empty slot “Find Your Program” (mode select) | Orange | Violation on **save-slot CTA** (Home Base doc) |
| Big News trophy / confetti | **Gold** `#f0c560`, `#d4a848`, `#c79a3e` | **Candidate “reward gold” token** — not in gob-tokens today |
| Bracket UI trophy badge | Gold gradients | Same |
| Training report `change-gold`, momentum orange | Gold + `#F79420` | Gold = exceptional stat; orange = momentum metric |
| Signing reveal / odds | `--gold`, amber buttons | Reward-adjacent |
| Walk-on welcome | Orange “Go To Locker Room” (nav, not advance) | Intentional per styleguide note |
| Alpha feedback | Purple/violet CTAs | Outside sport palette — feedback product |
| Recruit visit / Sammy modals | Team colours + green continue | Mixed |
| Championship moment CTA | Green | **Aligned** |
| Hub signing amber actions | Orange for mid-run commit | Save/commit semantics — **OK** |

**Sound inventory (management-relevant):** `click-tiny.wav`, `click-beep.wav`, `click-strong.wav`, `confirm-1-lowervol.wav`, `x-back.mp3` via `uiSfx.js`; mode-select music separate. **No** dedicated “win fanfare” or “milestone sting” on Office/modals except Advance confirm.

---

## 5. Offline (desktop / loopback) differences

| Surface | Offline behavior |
|---------|------------------|
| Office digest / result / what moved | **Works** — derived from SQLite franchise + games |
| Championship / bracket / walk-on / visit / big news modals | **Work** when payload present on franchise (local) |
| Archetype evolution / alpha feedback | **Broken or skipped** — need `/api/auth/me` (remote); evolution PATCH remote |
| Geek Points award + highlight flush | **Remote user doc** — no local trophy for GP |
| Community leaderboard / highlights / mode-select ATL | **Fail or empty** |
| Settings coach stats (12–5, titles) | **Hidden** on desktop (`gobSettings.js` skips me fetch) |
| Recruiting results seen PATCH | Loopback franchise routes OK |

---

## 6. Risks (Advance / finalize / UX)

1. **Finalize path coupling** — `capture_office_week_snapshot`, rank prestige, news, geek points, archetype counters, community highlight pending, and championship moment enqueue all run in **week finalize / complete-week** flows (`franchise_routes.py`). Ch7 must **not** change sim engine, `cpu_week_pool`, `sim_rng`, or finalize ordering without explicit design — reward UX should **read** existing fields and queue, not add finalize work.

2. **Modal pile-up** — Single FCC visit can chain: Championship Moments → region/conf/bye/walk-on/visit → Big News (×3 types) → cut modal → tutorial alert → archetype evolution (1.2s delay). `blockerVisible` + Big News retry can defer **300s**. Risk: user fatigue, missed modals, or “stuck behind overlay.”

3. **Duplicate signing celebration** — Signing Day **hub reveal** (week 35) plus **`recruiting_results_modal`** on FCC can both celebrate the same class.

4. **Performance** — Bracket modal: `fitBracketToContainer` polling, `ResizeObserver`/`scheduleConnectorRedraw`, confetti DOM (60–75 nodes). Office: digest is server-built but client renders many DOM nodes on tab switch.

5. **Intensity flatness** — Weekly beats compressed into Office cards while milestones use full-screen gold/confetti — matches audit finding; ladder work must **raise weekly** without inflating every week to modal tier.

6. **Online-only career stats** — Trophy case / coach career on offline Home Base cannot rely on Geek Points or `/api/auth/me` without local mirrors.

---

## 7. File index (quick reference)

| Area | Primary files |
|------|----------------|
| Office digest | `BackEnd/utils/office_digest.py`, `FrontEnd/static/js/shared/officeHome.js`, `FrontEnd/static/css/office-home.css` |
| CC orchestration | `FrontEnd/static/franchise-command-center.js` |
| Big News | `FrontEnd/static/js/shared/bigNewsModals.js`, `FrontEnd/static/css/big-news-modals.css` |
| Championship | `FrontEnd/static/js/shared/championshipMoments.js`, `BackEnd/utils/franchise_championship_moments.py` |
| Walk-on / visit / region | `walkOnWelcomeModal.js`, `recruitVisitModal.js`, `regionByeModal.js`, `conferenceRsRegionModal.js` |
| Archetype / alpha | `archetypeEvolutionModal.js`, `alphaFeedbackModal.js` |
| Advance | `FrontEnd/static/js/shared/gobAdvance.js` |
| Signing | `recruiting-hub.js`, `recruiting-signing.css` |
| Training praise | `training-report.js`, `training-report.css` |
| Geek / community | `BackEnd/utils/franchise_geek_points.py`, `BackEnd/utils/community_highlights.py`, community routes |
| Modal payloads | `BackEnd/api/franchise_routes.py` (`_build_*_modal_payload`, CC response assembly) |

---

STATUS: COMPLETE
