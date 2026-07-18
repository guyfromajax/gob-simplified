# Recruiting Hub Redesign — Implementation Spec & Status

UI/UX overhaul of the recruiting experience into a single phase-aware **Hub** that takes over `recruiting.html`'s role/URL. Source deliverables (approved mockups + design prototypes): `_documentation_master/projects/Recruiting Hub Deliverables/`. Sequenced as 7 prompts (0–6), **spine-first**.

## Stack decision
Deliverables are React+Babel-in-browser **prototypes**; the production app is **vanilla JS** (classic `<script>`, shared helpers, no build step). Implementation = faithful **vanilla port** of the mockups (identical markup/classnames so the ported CSS applies unchanged and tertiary surfaces stay byte-for-byte identical per Prompt 6). Backend already supplies everything the spine needs — reuse, don't fork.

## Foundational decisions (locked)
| # | Decision | Choice |
|---|---|---|
| Loyal/"locked" | No backend loyalty flag exists (loyalty = lean ordering only) | **Capability only** — ladder renders locks; live data never fabricates one. Real loyalty = deferred backend item. |
| RT color scale | Existing `getRecruitRtBucketClassForYear` is year-aware (recruit scale JH only; player scale FR/SO/JR) | **Keep the year-aware switch** — reuse the helper as-is. |
| Fonts | Bebas Neue Pro OTFs were orphaned (no `@font-face`); app ran on Google 'Bebas Neue' | **App-wide swap** — centralized `@font-face`, Pro-first stacks everywhere. |
| P0 blast radius | — | **Shared modules + QA gallery only**; live pages untouched until Prompts 1 & 5. |

## System boundaries (the "spine" — one source, every surface)
- **`FrontEnd/static/recruiting-spine.js`** → `window.RecruitingSpine = { Lean, Phase, Anchor, rtClassForYear, esc }`. Consumed by the hub pool (P1), FCC Recruits tab + cards (P5), Training Report callout (P6).
- **`FrontEnd/static/recruiting-spine.css`** — tokens + lean/phase/pool/anchor styles. Reconciled to **reuse** `/css/rt-buckets.css` (`.rt-*` colors) and `/css/fonts.css` (`@font-face`) rather than redeclare.
- **Reused, not forked:** `js/shared/rtBucket.js` (`getRecruitRtBucketClassForYear`), `js/shared/playerYear.js` (`GOB_PlayerYear`).

## Data mapping (backend → spine lean model)
Backend `franchise_recruits_data_collection.Lean = {"1": team_id|"open"|null, "2":…, "3":…}` (served verbatim by `GET /franchise/recruiting-data` + `team_name_map`).
`RecruitingSpine.Lean.fromBackend(recruit, {userTeamId, teamNameMap, abbrOf})` → `{ leans:[{open}|{tok,you}], yourRank, leansToUser, locked:false }`. `null`→skip, `"open"`→`{open}`, id→`{tok,you}` (you detected by `team_id`, token derived from name; `locked` always false live).

## Prompt status
| P | Scope | Status |
|---|---|---|
| **0** | Foundation: tokens, lean-model adapter, ranked ladder, phase strip, pool anchor | **DONE** — QA gallery `recruiting-spine-gallery.html`; 25/25 logic tests + headless render verified |
| **1** | D1 The Spine: pool (~300 recruits, region A–H collapse, sort/filter, condensed variant) + assembled shell | **DONE** — `recruiting-hub.js` took over `recruiting.html`; real data; headless render + interaction verified |
| **2** | D2 Invite Dock (wks 20–26) — merge Orders pages into one hub dock | **DONE** — no backend decouple (see below); dock built in hub, render+interactions verified |
| **3** | D3 Signing Board (wk 35) — pool-as-worksheet, 50-pt budget, binding Playing-Time promise, live sign-odds | **DONE** — signing surface in hub; wired to existing wk-35 save+run; verified |
| 4 | D4 Results — hub **states** (weekly overlay + wk-36 signed pool), not a route | pending |
| 5 | D5 Consistency sweep — FCC Recruits tab + Home/Coach cards + tutorial (Signing Day rename, 50-pt, no cap) | pending |
| 6 | Training Report recent-leans callout — reuse the ladder markup | pending |

## Prompt 0 — shipped
- `FrontEnd/static/css/fonts.css` (new) — canonical Bebas Neue Pro `@font-face`, loaded app-wide.
- `FrontEnd/static/recruiting-spine.css`, `recruiting-spine.js`, `recruiting-spine-data.js` (mock, gallery only), `recruiting-spine-gallery.html` (QA harness).
- App-wide font swap: 28 CSS files → Pro-first stacks (184 stacks); `fonts.css` linked into every HTML `<head>` (78). Additive — Google links kept as fallback (they also carry Inter/Barlow/JetBrains).
- Acceptance met: all lean states render (you #1/#2/#3/open/all-open/not-listed/loyal-lock/single/none); RT colored (year-aware per decision); phase strip all 4 phases + expandable timeline; anchor scrolls to pool.

## Prompt 1 — shipped
- **Takeover (per decision):** `recruiting.html` is now the hub — new shell loads `recruiting-spine.{js,css}` + `recruiting-hub.js`; the old `recruiting.js` region-card renderer is retired (file left in place, no longer referenced).
- `recruiting-hub.js` — fetches `/franchise/recruiting-data`, computes phase from `week`, renders topbar+anchor, phase strip, passive story strip, and the pool. Reuses `RecruitingCommon.normalizeRecruits` + `RecruitingSpine`.
- **Pool:** region A–H collapsible sections, RT-desc default, sortable headers (name/pos/year/ht/wt/rt — attrs/lean not sortable, per mock), search + region chips + "leaning to me" filters, 12 attrs colored (bands rescaled to 0–100: hi≥65/mid≥40/lo≥20), year-aware RT, shared lean ladder, row mine/list-mine accents, "New" badge. Condensed variant (attrs hidden) when a dock is present.
- **Phase-aware transition glue:** Passive → story strip + no dock. Invite/Signing/Results → condensed pool + a right dock that links out to the existing `recruiting-invites/orders/results.html` until Prompts 2–4 fold them in. (Interim note: wk-36 shows the pool + a "View Signing Results" dock CTA rather than the old inline signed table; Prompt 4 builds the real signed-pool state.)
- Backend: `new_lean_recruit_ids` added to `/franchise/recruiting-data` (additive, gated on a played game — mirrors the FCC card). Powers the story strip + "New" badge. "Dropped you" deferred (no signal).
- Verified: passive (no dock, full pool) + invite@1280px (dock + condensed) render clean; region collapse / sort / region+mine+search filters all work; zero console errors.

## Prompt 2 — shipped
- **Decouple decision REVERSED (user call):** the prompt's "decouple invite execution from Training's Submit" was overstated. Invite **execution stays in Run Training** (`franchise_routes.py:12866-12869` untouched) — it's the mandatory weekly step and the only guaranteed trigger (week advances only via complete-week; **no back-fill** exists, so relocating the run risked permanently-missed weeks). The week-20 "must save orders before training" guard is **kept**. What D2 actually merges is the two forked *ranking* pages → one hub dock; the *cross-page UX* coupling is what's removed, not the backend sequencing.
- **Invite dock** built in `recruiting-hub.js` (invite phase only): condensed pool + add-column (`+` ⇄ rank badge, `on-board` row), draggable ranked slots (≤20) with standing chip (#1 green / on-list amber) + 0–3 lean-fill dots, header (count/20, W20–26 weekly tracker, "leaning to you" badge, position breakdown), empty-state + "rank N more" nudge, Clear + **Save Board**. Board seeds from `saved_orders` (deduped). Save → **existing** `POST /franchise/recruiting-orders` (`{franchise_id, recruit_ids}`) + success toast. `recruiting-dock.css` loaded.
- **Entry points repointed:** Training's "Recruiting Invites" button (wks 20–26) now → `recruiting.html` (the hub) instead of `recruiting-invites.html`. The forked `recruiting-invites/orders.html` are **left in place** (still serve the week-35 flow until Prompt 3); full redirect/delete is the final cutover.
- Verified headless @1280px: dock render, weekly tracker/badges/breakdown, add/remove/drag-reorder, Save (toast + correct payload), Clear; zero console errors.

## Prompt 3 — shipped
- **Signing surface** (Signing Day / wk 35) built in `recruiting-hub.js` as a distinct body (`.hub-body-sign` = `.spool` working pool + `.rail`), replacing the standard pool/dock at phase `day`. `recruiting-signing.css` loaded.
- Each pool row: name + standing badge (#1 green / on-list amber), pos/region/RT, 0–3 lean-fill dots, **points stepper** (0–`MAX_PER` 20, blocked at 0 remaining), **Playing Time** toggle (checked = Binding), live **Sign Odds** band. Rail "Your Orders": 50-pt budget (remaining + bar, over-state), promises count, committed list (points·odds, remove, **click-to-jump + flash**), binding-promise warning, green **Submit Orders**.
- **Auto-fill-then-adjust:** restores the budget from `saved_order_entries_week_35` if present, else seeds the top-3 RT leaners (12+PT / 9+PT / 6). Tabs (Leaning-to-you / All) + region select + search; RT-desc sort.
- **Backend integration (reuse, no new endpoints):** Submit = `POST /franchise/recruiting-orders` (`{franchise_id, order_entries:[{id,points,scholarship:false,playing_time}]}`) → `POST /franchise/run-week-35-recruiting` (`{franchise_id}`, advances to wk 36) → navigate to FCC (results modal), matching the existing flow. Budget cap (sum ≤ 50) enforced client-side, mirrored server-side.
- **Odds are a placeholder** (`signOdds`, isolated/swappable): `base(standing) + points·2.2 + (promise?18:0)`, bands Strong≥72 / In-the-Mix≥48 / Slim≥26 / Long-shot. Real signing math is league-relative (`(1+points+PT_bonus)·lean_mult`, weighted-random finalists) → an absolute per-recruit % isn't client-computable; the placeholder is directionally consistent. Swap-in = a deferred enhancement.
- **Roster-cap divergence (noted, not fixed):** funding is uncapped (bound by 50 pts) per the design, but the backend signing engine hard-caps actual signings at a 15-man roster. Consistent with the prompt's "no recruit cap" (that's about funding); surfacing available roster spots is a possible later enhancement.
- Verified headless @wk35: auto-fill, stepper budget-cap (all `+` disable at 0), promise toggle, live odds recompute, rail add/remove/jump, Submit dual-POST payloads; zero console errors.

## Deferred backend items (do NOT bury in a UI prompt)
1. ~~Invite-loop decouple~~ — **decided AGAINST** (Prompt 2). Execution stays in Run Training by design; do not relocate it.
2. **Loyalty signal (if wanted):** no backend `loyal/locked` flag today; ladder lock stays capability-only until one exists.
3. **"Dropped you" story-strip signal:** none exists; passive strip shows gains only.

## Notes for Prompt 1
- Recruit attributes are stored 0–1000 (÷10 → 0–100 display); the mock's 0–8 `attrCls` thresholds must be re-scaled for real data in the pool.
- Real backend leans emit `"open"` only in slot 1 (never multiple open slots); adapter handles the full range regardless.
- Hub takeover: `recruiting.html` becomes the hub; `recruiting-invites/orders/results.html` deleted/redirected; FCC links already point at `recruiting.html`.
