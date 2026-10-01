# What is still off gob tokens + colour law (2026-10-01)

Planning only. No product code, no Playwright. Branch `docs/ux-remaining-map` from `origin/develop` `868676175`.

## Where things stand

| | Files | Colour literals | Type literals | Colour-law hits (green / orange) |
|---|---|---|---|---|
| New-design surface (gated) | 35 | 468 | 671 | **0** |
| Legacy (reported, not gated) | 91 | 3,031 | 2,581 | **580** (149 / 431) |

Source: `check_ui_tokens.py --no-write` on `868676175`, exit 0. Per-file counts below come from the same scan.

Legacy law hits by surface:

| Surface | Files | Colours | Law hits | Share of 580 |
|---|---|---|---|---|
| Tutorial lesson pages (inline diagrams) | 11 | 279 | 122 | 21% |
| Admin / dev tools (not player-facing) | 6 | 560 | 118 | 20% |
| Live game (`court.html` + Phaser) | 18 | 519 | 97 | 17% |
| Marketing / legal | 6 | 242 | 74 | 13% |
| FCC + shared sheets and scripts | 31 | 829 | 72 | 12% |
| Play-flow leftovers | 5 | 193 | 33 | 6% |
| Entry (Home Base sheet, program select) | 5 | 183 | 31 | 5% |
| Community (in flight) | 5 | 138 | 16 | 3% |
| Auth (done on branch) | 1 | 50 | 11 | 2% |
| Account | 1 | 36 | 6 | 1% |

**A fifth of the remaining count is admin tooling no player sees.** Excluding it and the in-flight / on-branch work, about 420 law hits are left on player surfaces, and 122 of those are tutorial diagrams.

Landed today (now gated, 0 hits): box score + practice squad, Game Plan + Scouting, six game overlays, Team Builder, tutorials/FTE chrome, court chrome part 1.

| In flight | State | Files |
|---|---|---|
| Auth pages | **Done on `ux/auth-pages-tokens`, not merged.** Develop still counts `auth.css` as legacy (50 / 11). | `auth.css`, login, signup, reset |
| Court chrome 2 | **In progress** (`ux/court-chrome-2`, gob-ux). Safe pass; `court.html` law hits 79 → 75. | `court.html` |
| Community | **In progress** (per brief; no branch on origin yet). | archetypes pages, alpha feedback |

## 1. Remaining legacy surfaces

Count = colour literals / colour-law hits. Traffic = how often a franchise player sees it.

### Live game

| File | Count | Screens | Traffic | Risk |
|---|---|---|---|---|
| `court.html` | 413 / 79 | Playcall Center cockpit, side stat panels, reveal HUD, lower-third and secondary ribbons, sim-quarter popup, play-by-play, momentum bar | **High** (every game) | **Court.** Colour encodes game state; some states are asserted by equivalence specs. Grey panels have no 1:1 token (a redesign, not a swap). In progress (safe pass only). |
| `js/phaser/utils/simGamePresentation.js` | 61 / 9 | Sim broadcast (cards, worm) | **High** (every simmed game) | Court-adjacent. One pass done; the rest is data colour. |
| Other Phaser utils (11 files) | 45 / 9 | Pre-game, matchups, end-of-game, press conference, timeout button, foul-out, on-canvas text | High | Residue after the overlays pass. On-canvas text is equivalence-locked. |

### FCC and shared

| File | Count | Screens | Traffic | Risk |
|---|---|---|---|---|
| `franchise-command-center.css` | 283 / 18 | Leftover FCC panels on every Office load | **High** | **FCC freeze** (ceiling 2,261 lines / 293 rules; the file is at the line ceiling). Shrink only. Shared selectors. |
| `resource-pages.css` | 80 / 9 | Loaded by 12+ pages: FCC, set lineup, box score, playbooks, game plan, cut players, team builder, play-flow pages | **High** | **Shared selectors.** Peel per page; never restyle the sheet. |
| `css/auth-bar.css` | 90 / 13 | Top bar on FCC (web), tutorials, FAQs, Team Builder, program select | **High** | **Shared.** Every logged-in web page without the shell. |
| `css/attr-tiles.css` | 44 / 4 | Attribute tiles: FCC, recruiting, roster view | **High** | Shared. Likely the legal ramp; may only need annotation. |
| `js/shared/pageLoadOverlay.js` | 16 / 3 | Loading overlay, 9 pages | **High** | Inline JS styles. 3 green hits on a non-Advance. |
| `js/shared/errorHandler.js` | 44 / 12 | Global error toast / modal, 6 pages | Med (errors only) | Inline JS styles. 12 orange hits. |
| `js/shared/championshipMoments.js` | 65 / 3 | Championship takeover | Low, high-stakes | Reward gold is legal here; mostly raw literals. |
| `franchise-command-center.js` | 30 / 2 | FCC inline styles | High | Large file; touch only the style strings. |
| `css/senior-tribute.css`, `css/big-news-modals.css`, `recruiting-lean-ladder.css` | 91 / 3 | Senior tribute, big-news modals, lean ladder | Med (seasonal) | `.rc` in big-news has leaked into season review before. |
| `command-center-team-styles.css` | 16 / 2 | Team styles on FCC, roster view **and court** | High | **Court** loads it. |
| `css/playbook-cmd.css` | 3 / 1 | CMD band on playbooks, set lineup, FCC | High | Tiny. Blue/green/yellow band is a data ramp. |

### Play-flow leftovers

| File | Count | Screens | Traffic | Risk |
|---|---|---|---|---|
| `training-playbooks.css` | 53 / 10 | Training → custom playbook | Med | Isolated (one page). |
| `playbook-report.css` | 40 / 12 | After a playbooks save | Med | Isolated. |
| `play-details.html` | 33 / 4 | Play row → detail page | Low–med | Inline. Possible fold into Playbooks (old Q3, still open). |
| `player-detail.css` + `.js` | 67 / 7 | Recruit detail only (player detail redirects in-app) | Med | Isolated. Dies if recruit detail moves in-app. |

### Entry

| File | Count | Screens | Traffic | Risk |
|---|---|---|---|---|
| `mode-select.css` | 35 / 2 | Home Base (alongside `home-base.css`) | **High** (every session) | Small. Legacy sheet under a new-design page. |
| `franchise-select-team.css` | 89 / 16 | Find Your Program | Low (once per slot) | Isolated. Pairs with Team Builder, done today. |
| `css/team-picker.css` | 56 / 13 | The picker's `.team-card` styles | Low | **No page links this file**, yet it is the only sheet with `.team-card` rules. Confirm before touching. |

### Tutorials

| File | Count | Screens | Traffic | Risk |
|---|---|---|---|---|
| 7 lesson pages (`tutorial-recruiting`, `-scouting`, `-playbooks`, `-training`, `-team-attributes`, `-game-plans`, `-player-attributes`) | 223 / 114 | Inline teaching diagrams, crumb and handoff labels | Med (new coaches) | Diagram colours carry meaning; chrome is already done. A recolour is a content decision. |
| `css/gob-advanced.css` | 45 / 8 | Advanced-topic diagrams | Low | Exempt by design. |

### Online-only and marketing

| File | Count | Screens | Traffic | Risk |
|---|---|---|---|---|
| `auth.css` | 50 / 11 | Login, signup, reset | High (session start) | **Done on branch; merge it.** |
| `account.html` | 36 / 6 | Settings › Account | Low | Inline. Isolated. |
| `homepage.html`, `homepage-v3.html`, `homepage-v3-source.html` | 218 / 71 | Public entry | High for visitors, zero for franchise play | Blocked on ownership (§4). Two are duplicates. |
| `faqs.html`, `css/legal.css`, `trailer.html` | 24 / 3 | FAQs, privacy, terms, trailer | Low | Trivial. |
| Community: `coaching-archetypes.html`, `-leaderboard.html`, `alpha-feedback.html`, `alphaFeedbackModal.js`, `archetypeReveal.js` | 138 / 16 | Archetypes, leaderboard, feedback | Low (online only) | **In progress.** |

### Not player-facing

| File | Count | What | Recommend |
|---|---|---|---|
| `hct-skeletons.html`, `fcp-skeletons.html`, `play-builder-v2.html`, `play-builder.html`, `plays-builder.html` | 549 / 116 | Admin builders | Do not migrate. |
| `js/phaser/animation/tests/runBaselineInboundTests.html` | 11 / 2 | Test harness inside `static/` | Move out or delete (§3). |

Also off-system but outside the scan: the desktop app icon (§4).

## 2. Proposed next batches, in priority order

| # | Batch | Size | Scope in one line | Blocked by |
|---|---|---|---|---|
| 1 | Shared chrome every page shows | **M** | `pageLoadOverlay.js`, `errorHandler.js`, `css/auth-bar.css`, `mode-select.css`: 185 literals, 30 law hits, highest traffic per line. | Nothing. Auth-bar needs before/after on at least FCC, a tutorial and Team Builder. |
| 2 | FCC peel 2 | **M** | Remove or neutralise the 18 hits in `franchise-command-center.css` (shrink only), `franchise-command-center.js` style strings, annotate `attr-tiles.css`, tidy the three seasonal modal sheets. | Navy ruling, if any selected-row rules are touched. |
| 3 | Play-flow leftovers | **M** | `training-playbooks.css`, `playbook-report.css`, `play-details.html`, recruit `player-detail.*`, each peeled off `resource-pages.css`. | Old Q3 (fold play-details or restyle). Shot-distribution ramp if those pills appear. |
| 4 | Program select | **S** | `franchise-select-team.css` plus a decision on `css/team-picker.css`; finishes the new-franchise flow next to Team Builder. | Team Builder rulings (Continue green, neutral chips) so the two match. |
| 5 | Court part 3: game-state colour | **L** | Playcall Center cockpit, reveal HUD, ribbons, side-panel toggles and the grey → navy panel surfaces. Sim-safe, equivalence specs re-run. | **Jamie rulings** on game-state colour and grey panels. Do not start before court-chrome-2 merges. |

Small enough to ride along: `account.html` + `faqs.html` + `legal.css` (S, with batch 1).

Deliberately not batched: tutorial lesson diagrams (content decision), homepage (ownership), admin tools.

## 3. Delete rather than migrate

| Item | Evidence | Action |
|---|---|---|
| `css/coach-mark.css` + `js/shared/coachMark.js` | The sheet is loaded only by `coachMark.js`; nothing imports `coachMark.js` (the two mentions elsewhere are comments). | Delete both after one more grep. |
| `homepage-v3.html` | Same content and counts as `homepage.html` (61 / 18 each). | Keep one; redirect the other. |
| `js/phaser/animation/tests/runBaselineInboundTests.html` | A test harness under the published directory. | Move to `tests/` or delete. |
| Dead rules in `franchise-command-center.css` | Leftover `tab-content` panels the live views replaced. | Batch 2 deletes, which also lowers the freeze ceiling. |
| Dead rules in `team-builder.css` | `.footbar`, `.stub`, `.toast`, `.alert`, `.uncapped`, `.commit`, `.local`, `.mdl-t/-s/-a`, `.d-warn`, `.warn`: no JS emits them (neutralised today, not removed). | Delete in a small follow-up. |
| `css/team-picker.css` | No page links it. | **Confirm first.** If the picker really renders without it, delete; if it is meant to load, link it and migrate in batch 4. |
| `play-builder.html` | `play-builder-v2.html` exists beside it. | Jamie: delete v1 if v2 superseded it. Not verified. |
| `pgpcSammyReminderModal.js` inline light-shell `<style>` + orange ring fallback | Flagged in the tutorials report; `fte.css` carries overrides only to fight it. | Remove both together in a court-adjacent pass. |
| `.is-orange` callers of the Sammy modal | Now a no-op. | Drop the argument when those files are next touched. |

Already gone or already redirecting, so not work: the four dead `FrontEnd/*.html` root files, `stats.html` and `team-traits.html` (both redirect stubs now).

## 4. Open Jamie decisions that block work

| Decision | Current state | Blocks |
|---|---|---|
| **Navy for selected items** | Inconsistent today. Set Lineup and Team Builder use navy for the selected row; Game Plan, Scouting and Playbooks held selections neutral pending your ruling. | Batches 2, 3, 4 and court side-panel toggles (which use team colour for selected). One answer, applied everywhere. |
| **Expected Shot Distribution ramp (`getPswColor`)** | `common.js:1225`: blue > 35, green ≥ 21, yellow ≥ 11, red below. Blue on a non-RT variable conflicts with "blue is RT only"; the agent docs say preserve the programmed shot-weight scale. Used by Playbooks and Set Lineup. | Batch 3 pills; any further Set Lineup or Playbooks polish. |
| **App icon** | No square brand source at 512px or larger exists. `desktop/pack.js` only passes an icon when `desktop/build/icon.icns` / `.ico` is present, so builds ship the default Electron icon. | Desktop release polish. Needs the artwork from you, not an agent. |
| **Homepage rebuild ownership** | Three files, 218 literals, 71 law hits, two of them duplicates. Marketing surface: unclear whether it joins the design system and who owns the rebuild. | Any homepage batch; the `homepage-v3.html` delete. |

Raised today and also waiting on you:

- **Court game-state colour.** Timeout button green, "AUDIBLE!" green, gold has-ball ring, cockpit active states, and whether grey panels move to navy surfaces. Blocks batch 5.
- **Team Builder rulings.** Continue as the green Advance; position chips and attribute-category labels neutral; Review "your program" row on team colour.
- **Auth submit.** LOG IN / SIGN UP treated as the green Advance on `ux/auth-pages-tokens`.
- **Tutorial lesson diagrams.** Recolour to the law, or exempt them like `gob-advanced.css`.
- **`play-details.html`.** Fold into Playbooks or restyle the standalone page.

## Method notes

- Counts are from one scan of `868676175`. Branch work not yet merged (auth, court-chrome-2, community) is not reflected in them.
- "Screens" and loaders come from grepping `<link>` and script references, not from running the app.
- Not verified: that `css/team-picker.css` is truly unused at runtime, and that `play-builder.html` is superseded.
