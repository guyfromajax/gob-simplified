# Legacy page migration plan — 2026-09-30

Branch `docs/legacy-migration-plan` in `~/gob-audit`, from `origin/develop`. Read-only: no product code. Sources: `reports/coverage-map-2026-09-29.md`, `scripts/check_ui_tokens.py --strict --no-write` (this morning), `gobShell.js` `PAGES`, `scripts/ci/migration_gates_allowlist.json` Gate B, UX_System §7, frames under `_documentation_master/projects`. Colour-law counts are **legacy surface only** (new-design is already 0). Gate B is the allow-listed line count for that page’s own files (shared shell files `gobShell.js` 14 / `gobNav.js` 27 are not re-counted on every row).

**Already on the new design system — do not re-brief.** Shell chrome, Settings, Home Base (`css/home-base.css`), Trophy Case, Season Peak, Milestone, Office weekly (`css/office-home.css`), and the in-app Team / League / News browse views that already use `gob-tables` / `gob-views` plus frames in `design_handoff_browse_templates` and `design_handoff_office_shell`. Coverage-map “New design: yes” on those views is still true for chrome. This plan is the leftover **legacy CSS/markup a player still sees**.

**Court / live sim:** `/court.html` is reachable every game. **Flag only. Do not plan a visual rewrite of the sim.** 7,799-line file, 91 colour-law hits, Gate B 1. Frames exist (`design_handoff_office_shell/frames/gameplay-audio-1280.html`, `sim-broadcast-handoff/`). Treat court as a separate product, not a Chapter 8 batch.

---

## 1. Inventory

| URL / tab | How a player gets there | Legacy files (loads) | Law hits (g/o) | Gate B | Size (lines) | Design frame | Online / offline |
|---|---|---|---|---|---|---|---|
| `/recruiting.html` (Pool / Leans / Visits) | Rail Recruiting (`GOBNav.go`) | `recruiting.html`, `recruiting-hub.js`, `recruiting-spine.css`, `recruiting-dock.css`, `recruiting-signing.css` | 16+17+44 = **77** | hub.js 2 | ~60 + 2,643 + 660+130+467 | `Recruiting Hub Deliverables/` (Spine, Dock, Signing, Results); browse `t2-recruit-pool-1280.html` | both |
| `training-view` | Rail Prep › Training | `training.js`, `training.css`, newswire / focus / PD grid CSS | **51** (`training.css`) + 3+3+0 | `training.html` stub 1 | 2,395 + 2,601 | `design_handoff_prep` + `_v2` `prep-training-*.html` | both |
| `training-report-view` | After training / Office card (often via stub) | `training-report.js`, `training-report.css` | **17** | stub html 1 | 2,175 + 1,859 | `prep-training-report-1280.html` (prep + prep_v2) | both |
| `playbooks-view` | Prep › Playbooks | `playbooks.js`, `playbooks.css`, `css/playbook-tiles.css` | 12+33 = **45** | stub html 1 | 1,960 + 2,072 + 926 | `prep-playbooks-1280.html` (prep + prep_v2) | both |
| `game-plan-view` | Prep › Game Plan | `game-plan.js`, `game-plan.css` | **6** + js 1 | stub html 1 | 1,386 + 919 | `prep-game-plan-1280.html` (prep + prep_v2) | both |
| `game-plan.html?resume_from_timeout=true` / `mode=tutorial` | Timeout / first-time tutorial | same `game-plan.*` (focus, no rail) | same | html 1 | same | same + `set-lineup-handoff 2` timeout reads | both |
| `scouting-view` | Prep › Scouting | `scoutingView.js`, `scouting-report.css`, `scoutingReport.js` | **2** | 0 on view | 548 + 405 + 510 | `prep-scouting-1280/1920.html` (prep + prep_v2) | both |
| `/set-lineup.html` | Advance → Play game | `set-lineup.html/.js/.css` | **29** | js 2 | 230 + 3,731 + 1,685 | `set-lineup-handoff 2/` (v3 Fits, Timeout Read) | both |
| `/box-score.html` | Game row / post-game | `box-score.html/.js/.css` | **12** | 0 | 362 + 2,567 + 746 | none found | both |
| `/cut-players.html` | Advance when over roster cap | `cut-players.js/.css` | **6** | js 2 | 493 + 113 | none found | both (needs flow params) |
| `/playbook-report.html` | Playbooks save | `playbook-report.js/.css` | **12** | 0 | 374 + 299 | none found | both (needs flow) |
| `/training-playbooks.html` | Training → custom playbook | `training-playbooks.js/.css` | **10** | 0 | 412 + 376 | none found | both (session keys) |
| `/training-squad-report.html` | After Training submit | `training-squad-report.html/.js` | 0 in token dump | 0 | small html + js | none found | both |
| `/play-details.html` | Playbooks play row | `play-details.html` (inline) | **4** | 0 | 1,114 | none found | both |
| `player-view` / leftover `player-detail.*` | Roster / Leaders player link | `player-detail.css/.js` still in tree; view is in-app | css **3**, js **4** | html 1, js 1 | 532 + 725 | `design_handoff_browse_templates/frames/t3-player-1280/1920.html` | online works; **offline broken** (coverage-map) |
| `team-view` (via `team-roster-view.html` stub) | Standings / Office team link | stub + `command-center-team-styles.css` **2** | styles 2 | stub html 1, js 1 | 292 css | `t3-team-1280.html` | both (reload, not push) |
| FCC leftover panels | Old `tab-content` still in `franchise-command-center.html` | `franchise-command-center.css` **65**, `.js` **3** | 65+3 | js 4 | 4,326 + 5,712 | office/browse frames already ship the live views | both |
| `/tutorial.html` | Rail Tutorials | `tutorial.html`, `css/gob-tutorial.css` (excluded from new-design) | 11 + **25** | 0 | 251 + 409 | none (copy in `Tutoraial_Pages_Copy/`) | both |
| `/tutorial-training.html` etc. (7 core lessons) | Tutorials hub cards | each `tutorial-*.html` + shared tutorial CSS | 4–27 each (see below) | 0 | 164–534 | none | both |
| Advanced tutorials (4) | Hub Advanced Topics | `tutorial-advanced-*.html`, `css/gob-advanced.css` **16** | 0–16 | 0 | 110–236 | none | both |
| FTE: persona / situation / pick opponent | First-time online flow (`authBarInit`) | those three html + `css/tutorial-pick-opponent.css` **7** | 0–7 | 0 | 38+56+44 | none | **online only** (hidden desktop) |
| `/login.html` `/signup.html` `/reset-password.html` | Auth | `auth.css` **11**, pages | 11 | 0 | 545 + 163/526/183 | none | **online only** |
| `/account.html` | Settings › Account | `account.html` **6** | 6 | 0 | 319 | none | **online only** |
| `/` `homepage.html` | Public entry | `homepage.html` **18**, `homepage-v3.css` **5** | 18+5 | 0 | 700 + 868 | none (marketing) | **online only** |
| `/faqs.html` | Settings / footers | `faqs.html` **1** | 1 | 0 | 123 | none | both |
| `/privacy.html` `/terms.html` | Footers | `css/legal.css` **1** | 1 | 0 | 137+170 + 127 | none | both |
| `/alpha-feedback.html` | Feedback modal (alpha) | `alpha-feedback.html` **7** | 7 | 0 | 550 | none | **online only** |
| `/coaching-archetypes.html` | Account / milestone link | page **2** | 2 | 0 | 213 | none | **online only** (hidden desktop) |
| `/coaching-archetypes-leaderboard.html` | Home Base community | page **3** | 3 | 0 | 193 | none | **online only** |
| `/franchise-select-team.html` | Home Base → Find Your Program | `franchise-select-team.js/.css` | css **16** | 0 | 866 + 153 | `design_handoff_team_builder` program-select shots | both |
| `/team-builder.html` | Select-team builder mode | `team-builder.js/.css` | css **31** | roster.js 1 | 1,085 + 2,141 | `design_handoff_team_builder/design/Team Builder - *.html` | both (feature flag often off) |
| `/stats.html` | URL / dead FCC `#resources-stats` | `stats.html/.css` | css **14** | 0 | 402 + 318 | none (League Team Stats frame already exists) | both (orphan URL) |
| `/team-traits.html` | URL / dead FCC `#resources-team-traits` | `team-traits.html` | not in top law list | 0 | small | none | both (orphan URL) |
| `/court.html` | After lineup / in-game | `court.html` inline + Phaser | **91** | html 1 + bootGame 1 | 7,799 | gameplay-audio / sim-broadcast | both — **do not migrate sim** |

**Core tutorial law hits (legacy):** scouting 27, recruiting 27, playbooks 19, training 17, team-attributes 9, game-plans 9, player-attributes 4. Hub 11. `css/attribute-tour.css` 26 (player-attributes tour).

**Shared sheets a player hits on many of the above (not a page):** `resource-pages.css` 9, `css/auth-bar.css` 13, `css/sammy-modal.css` 6, `css/big-news-modals.css` 1, `css/team-picker.css` 13 (unlinked; TeamPicker still assumes it).

---

## 2. Batches (~1 agent-day), weekly-loop first

Order is how often a franchise player sees the screen. Each batch is one brief. **Risk** is what else breaks if you restyle the shared file.

| # | Batch (brief title) | Pages | Why this order | Risk |
|---|---|---|---|---|
| 1 | Recruiting hub visual | `/recruiting.html` + spine/dock/signing CSS | Every week of the season except maybe 36; largest leftover full page (~300 ms open) | Shared `recruiting-*.css` is only this hub (good). Do not rewrite the invite-board engine. Results/signing weeks share signing CSS. |
| 2 | Prep Training + Report | `training-view`, `training-report-view` | Weekly Advance path | `training.css` / `training-report.css` also style tutorial-mode and standalone HTML. `resource-pages.css` is shared with other modules — peel, don’t restyle the whole sheet. |
| 3 | Prep Playbooks + tiles | `playbooks-view`, `css/playbook-tiles.css` | Weekly-ish; Playcall Center | `playbook-tiles.css` is shared with court Playcall UI. Touching tiles can change **live game** chrome. Split “browse tiles” vs court before restyle. |
| 4 | Prep Game Plan + Scouting | `game-plan-view`, timeout/tutorial focus, `scouting-view` | Weekly + scouting before games | Game Plan timeout path is **sim-adjacent** (opens from court). Tutorial `mode=tutorial` shares the same CSS. Scouting `new Audio()` close is a known settings bypass. |
| 5 | Set Lineup | `/set-lineup.html` | Every played game | Focus page; timeout-read handoff overlaps Game Plan. Don’t pull court into this brief. |
| 6 | Box Score + Cut Players | `/box-score.html`, `/cut-players.html` | After most games / roster weeks | Box Score is browse-or-focus (`return_url`). No frame. Cut Players is a gate on Advance — colour-law green on the CTA is likely legal Advance green. |
| 7 | Play flow leftovers | `playbook-report`, `training-playbooks`, `play-details`, `training-squad-report` | After save / custom training | `play-details.html` is a second page for the same play object as Playbooks. Shared play markup with `plays-builder.html` (admin). |
| 8 | FCC.css peel + detail leftovers | `franchise-command-center.css` leftovers, `player-detail.css`, `command-center-team-styles.css` | Every FCC load still ships 4.3k CSS | **Highest shared-CSS risk.** Many old `tab-content` rules. Peel per live view; do not rewrite the file in one pass. Team view is still a **reload** (coverage-map). |
| 9 | Tutorials hub + 7 core lessons | `/tutorial.html` + training / attributes / game-plans / playbooks / scouting / recruiting | Rail, not weekly, but high “new coach” use | `css/gob-tutorial.css` is **explicitly not new-design**. Changing it is a design-system decision (Q4). Layout-shift on hub (coverage-map). |
| 10 | Advanced tutorials + FTE | 4 advanced + persona / situation / pick opponent | Rare / once | FTE is online-only. Pick-opponent uses Advance sound. Don’t couple to franchise shell. |
| 11 | Auth + Account | login, signup, reset, account | Online session start | `auth.css` + `css/auth-bar.css` (bar is on FCC too). Restyling auth-bar hits every logged-in web page. |
| 12 | Marketing + legal | homepage, FAQs, privacy, terms | Rare | Homepage is public marketing, not franchise chrome. `homepage-v3-source.html` is the `sync:homepage` destination — not a player page. |
| 13 | New-franchise | `franchise-select-team`, `team-builder` | Once per slot | Team Builder has a full handoff but the live flag is often off. `team-builder.css` is isolated (good). |
| 14 | Rare community | archetypes, archetypes leaderboard, alpha-feedback | Online-only, rare | Hidden on desktop. Don’t spend a day if Jamie would rather delete/hide. |

**Not a batch:** `/court.html` and Phaser (`gameScene.js`, popups, sim presentation). Sim-adjacent only as a **do-not-touch** constraint on batches 3–5.

---

## 3. Delete or redirect — don’t migrate

Same bar as `chore/ch8-cleanup-1`: no live `<a href>` / `script src` / FastAPI / Electron / `_redirects` (except an intentional stub).

### Already redirects — keep the stub, do not restyle

`standings.html`, `rankings.html`, `leaders.html`, `team-stats.html`, `news.html`, `awards.html`, `brackets.html`, `practice-squad-standings.html`, `practice-squad-bracket.html`, `training.html`, `game-plan.html` (except timeout/tutorial), `playbooks.html`, `training-report.html`, `player-detail.html`, `team-roster-view.html` (except `mode=practice_squad&ps_team_id`). Coverage-map still lists live links that *should* open in-app instead of hitting the stub. That is a nav brief, not a visual migration.

### Orphans — URL works, no live control

| Page | Evidence | Recommend |
|---|---|---|
| `/stats.html` | `gobShell` `PAGES`, `authGuard` allow-list, UX_System. FCC sets `href` on `#resources-stats`, **that id is not in the HTML** (only `stats-nav-btn`). Coverage-map: orphan. | **Redirect** to FCC `?tab=team-stats-view` (League Team Stats already has a frame). Don’t migrate a second stats page. |
| `/team-traits.html` | FCC sets `#resources-team-traits` href; **id missing from HTML**. API `GET /franchise/team-traits` exists. | **Jamie (Q7).** Redirect to Team Attributes, or keep as a hidden resource. Do not restyle until decided. |

### Duplicates / ops — not player migration

| Page | Evidence | Recommend |
|---|---|---|
| `homepage-v3.html` | `authGuard` public list; same marketing content as `/` (`homepage.html`). | Don’t migrate twice. One homepage brief (batch 12). |
| `homepage-v3-source.html` | `package.json` `sync:homepage` **writes** this file. Not linked for play. | Keep as sync dest. Not a player page. |
| `trailer.html` | Netlify `/trailer`. 1 law hit. | Ops. Leave. |
| `maintenance.html` | Netlify wildcard (commented). | Ops. Leave. |
| `fcp-skeletons.html`, `hct-skeletons.html`, `play-builder.html`, `play-builder-v2.html`, `plays-builder.html` | `adminGuard` / skeleton routes. High law hits (31) but **admin**. | Not a player brief. |
| Phaser `runBaselineInboundTests.html` | Animation test harness. | Leave. |

### Dead pages already deleted (ch8-cleanup-1)

Do not re-list as work: Playcall Center POC, Tournament Tab, `_preview-training-phase5`, coaching-grid, homepage-backup, homepage-v2-legacy, scrimmage-select, tb-band-placement-qa, leftover `recruiting.css` / stub companion JS. If something reappears on develop, treat as a regression.

---

## 4. Jamie design decisions (multiple choice)

**Q1. Recruiting stays a full page or becomes an in-app view?**
- (A) Keep `/recruiting.html` (under 800 ms; coverage-map rec). Visual-only brief (batch 1).
- (B) Move Pool/Leans/Visits into FCC like other rail items (~250 ms save). Bigger than one agent-day.

**Q2. Box Score and Cut Players have no frame. What is the target?**
- (A) Apply browse/focus templates (`gob-tables` / `gob-focus`) without a new frame.
- (B) Pause those batches until a frame exists.
- (C) One combined “post-game / roster gate” frame.

**Q3. Play-details: second page or fold into Playbooks?**
- (A) Redirect `/play-details.html` into an in-app play inspector (delete the page after).
- (B) Restyle the standalone page (batch 7).
- (C) Leave until Playbooks batch 3, then decide.

**Q4. Tutorials: stay on `gob-tutorial` chrome (token checker excludes them from `--strict`) or join the franchise design system?**
- (A) Keep tutorial chrome; only fix layout-shift / copy.
- (B) Restyle hub + lessons to `gob-tokens` (then they become `--strict` surface).
- (C) Hub on gob; lessons stay tutorial CSS.

**Q5. Auth + homepage: franchise tokens or keep marketing look?**
- (A) Leave homepage/auth as marketing (batch 12/11 light: tokens only where it already leaks).
- (B) Bring login/account onto gob Settings language; homepage stays marketing.
- (C) Full gob restyle of homepage + auth.

**Q6. Team Builder is flagged off in smoke. Ship the existing handoff or wait?**
- (A) Brief batch 13 now from `design_handoff_team_builder`.
- (B) Wait until the flag is on in staging.
- (C) Franchise-select only; defer the builder studio.

**Q7. `stats.html` / `team-traits.html`?**
- (A) Redirect both into League Team Stats / Team Attributes.
- (B) Redirect stats; keep team-traits as a real resource page (needs a frame).
- (C) Delete both if bookmarks don’t matter.

**Q8. `franchise-command-center.css` (65 law hits, 4.3k lines): peel or freeze?**
- (A) Batch 8 peels dead `tab-content` rules only (safest).
- (B) Rewrite the sheet to gob (multi-day; blocks other FCC work).
- (C) Freeze the file; new views never add rules there.

**Q9. Colour law vs existing frames.** Prep and Recruiting frames predate the green/orange/reward-gold allow-list. If a frame uses raw green/orange off the allow-list:
- (A) Implement the frame, annotate `/* colour-law: … */` only where UX_System already allows.
- (B) Recut the frame to tokens first (pause the batch).
- (C) Agent stops and pings you when a frame conflicts.

---

## 5. Shared CSS — what has to move first

| Shared file | Law | Who loads it | Move first |
|---|---|---|---|
| `franchise-command-center.css` | 65 | Every FCC document | **Peel before** any leftover-panel restyle. Live views already have `gob-views` / `office-home`. Deleting unused `tab-content` rules is the first brief if Q8 = A. |
| `court.html` inline | 91 | Live game only | **Do not start.** If Playbooks tiles (batch 3) share selectors with court, extract court-safe copies first. |
| `team-builder.css` | 31 | Team builder only | Isolated. Batch 13 can own the whole file. |
| `recruiting-spine.css` / `dock` / `signing` | 16+17+44 | Recruiting hub only | Isolated. Batch 1 can own all three. Do not “fix recruiting” by editing FCC.css. |
| `resource-pages.css` | 9 | Training, Game Plan, Playbooks, other modules | **Peel per module.** A global restyle of this file is a multi-batch landmine. |
| `css/auth-bar.css` | 13 | Web FCC + auth pages | Batch 11 only after FCC chrome is left alone, or split “bar on FCC” vs “login page”. |
| `css/playbook-tiles.css` | 33 | Playbooks + court Playcall | **Extract** browse vs court before batch 3. |
| `css/big-news-modals.css` | 1 | FCC + season review leak history | Don’t restyle `.rc` globally (already bit season review). |
| `training.css` / `playbooks.css` / `game-plan.css` | 51 / 12 / 6 | In-app view + standalone + tutorial | Own file per batch; watch `mode=tutorial` and timeout. |

**Suggested sequence for shared files:** (1) Q8 peel FCC.css dead rules, (2) Recruiting trio (isolated), (3) Playbook tiles split from court, (4) module CSS (training / playbooks / game-plan), (5) auth-bar last.

---

## 6. Brief checklist (for whoever writes the ticket)

- Target URL/tab from the inventory table.
- Frame path or “no frame — use Q2/Q3”.
- Files allowed to touch (and the off-limits list: `court.html` / Phaser unless the brief is court).
- Colour-law: `--strict` stays green; this work is legacy until the file is reclassified as new-design.
- Gate B: do not add `URLSearchParams` / `location.search` reads; use `FranchiseContext.get`.
- Online and offline if the row says both; skip desktop-hidden pages on desktop.
- Redirect stubs: re-point callers, don’t restyle the stub.

`scripts/ci/check_migration_gates.py` on this docs branch: pass (nothing changed). Gate A 0/0, Gate B 136/44.
