# Chapter 7 — Home Base + Reward Ladder · design handoff

Two pieces of work:

- **Home Base.** The pre-franchise hub. It replaces `mode-select.html` / `mode-select.css`.
- **The Reward Ladder.** The Everyday / Weekly / Milestone / Season-peak tiers in the management UI. There is no court animation in this chapter.

The system is `../design_handoff_browse_templates/`: tokens, components, templates. `ch7.css` holds the new pieces only. Its last block, "Preview harness", is not product code. The Office frames reuse `../design_handoff_prep_v2/shell.js` (copied to `frames/shell.js`, with Office on).

Open `index.html` to see every frame at its real size. Each frame also opens on its own, and query parameters set the state:

| Frame | Parameters |
|---|---|
| `frames/home-base.html` | `net=online\|offline` · `s=first\|one\|two\|live` · `ui=menu\|confirm` · `tab=lb` · `d=1920` |
| `frames/trophy-case.html` | `s=populated\|empty` · `d=1920` |
| `frames/office-weekly.html` | `s=win\|loss\|gain\|lossgain` · `d=1920` · `still` (skip entrance) · `rm` (reduced motion) |
| `frames/milestone.html` | `v=signing\|bracket\|elim` (signing queues a second moment; press Next) |
| `frames/season-peak.html` | `v=title\|review` · `d=1920` |

**Sample values are illustrative.** That covers team names, records, ranks, scores, player names, stat lines, recruit names, RT letters, Geek Points, coach names, highlight copy, archetype copy, week numbers and round names. Initials stand in for headshots, and the portrait placeholder stands in for served player images. Only structure, tokens and behaviour are the spec. Copy marked *existing* keeps the production string.

---

## Decisions

### Colour law (locked, applied)
1. **Green = the single primary forward action.** On Home Base that is one button per screen:
   - **Online:** the last-played program's **Enter**. It becomes **Resume Game** when that program has a game in progress (the game in progress wins over last played). The other slot's Enter is a quiet `.btn-ghost.sm`.
   - **Offline:** the same rule as online. The last-played program's **Enter** (or **Resume Game**) is green, and the other slot's Enter is quiet. There is no Continue hero any more; it repeated the left zone.
   - **No programs:** nothing is green.
   - In franchise, the top-bar Advance stays the only green. Modals, the season peak and the review use `.btn-ghost`, never green. This supersedes the shipped Championship Moments green CTA.
2. **Find Your Program is quiet** (`.btn-ghost.sm`). It is not orange and not green. This fixes the violation flagged in the inventory.
3. **Orange** does not appear anywhere in Ch7. There are no saves here.
4. **Navy = "yours":** your Around GOB card, your leaderboard row, your team in the bracket path, your standings row.
5. **Blue appears only on RT A and attribute 9+.** Team colours enter only through program art and the `--team-primary` wash, and never as ink.
6. **Reward gold** is one new token. The definition is below. The weekly WIN tag is a white plate with dark ink, not green. The shipped green ▲ / red ▼ attribute chips become neutral ▲ (t100) / ▼ (t60), as in Prep v2 decision 4. *To confirm:* say so if you'd rather keep the delta colours on the Office.
7. **Delete is red outline + red text** (`.btn-del`). It appears only in the confirm dialog. The menu item is red text only.

### Home Base
8. **One layout for online and offline.** Left zone: *Your Programs* (two slots), then Tutorials · Settings · FAQs. Right zone: it swaps its contents, and its frame stays the same. No rail and no franchise top bar: Home Base has its own top bar with wordmark, connection state and account.
9. **The occupied slot is a "door".** The program's banner art sits on top, above an info row: name, season/week, next opponent, record, national rank, action. The whole card is the Enter target (`role="link"`) and the button repeats it. The "Last played" tag marks the program the green belongs to.
10. **`···` sits in the slot header (`01 ——— ···`), outside the card.** This is option C from the delete-placement study: it keeps a destructive control off the Enter surface. It opens a one-item menu, *Delete program…*, which opens the confirm dialog. Cancel has default focus. Click count is unchanged (3).
11. **Empty slot copy stays existing:** "Start Your Coaching Journey" when there are 0 programs, "Start Another Franchise" when there is at least 1. The helper line under it is new and illustrative.
12. **Online right zone:**
    - **Find A Game** is a neutral placard with **Coming Soon**. It is non-interactive (`aria-disabled`) and has no gold or orange, since reward gold never goes on chrome.
    - **One tabbed panel, "Around GOB" ⇄ "Leaderboard"** (`.hbt`). Community Highlights is removed, because it repeated Around GOB. The tab fills everything below Find A Game, so each view gets the full right zone. It opens on Around GOB and remembers the last tab (localStorage). When Leaderboard is showing, the Around GOB tab carries a count of results that are new since the last visit.
    - **Name: "Around GOB"** (was Around The League). "League" read as one shared franchise instance, but every card comes from a different coach's own league. "Around GOB" keeps the old name's rhythm and says "all of GOB". It is short in Bebas and sits well next to "Leaderboard". Alternatives considered: *Community Highlights* (generic, and the name of the section we cut), *The World of GOB* (grand and long for a tab), *Coaching Highlights* (sounds like video clips). The sub-line reads "Latest results from every coach's own league".
    - **Around GOB = a grid of result cards** (`.agc`): 3×2 at 1280 and 4×3 at 1920. The energy comes from each coach's own **program banner art**. The same art, blurred, washes the card body, so every card takes its colour from the team without needing a hex value. The card shows: coach tag (with a dot when new since the last visit), W/L plate (white = W, outline = L, never green or red), score, "def./lost to" opponent, team · record · national rank, and **season + week** paired as "SN 3 · WK 14" on the score row. **Your** latest result is the first card, with a navy ring and a "You" tag. There are no empty "Waiting for next result" slots unless there are fewer results than the grid holds; if so, `.agc.is-wait` fills the gap. Cards are not clickable (no destination exists).
    - **Leaderboard** keeps the Geek Points / Titles toggle, now in the tab row. The top 3 sit as numeral tiles, followed by rows 4–12 at 1280 (4–15 at 1920), then your row pinned in navy, then *By team* → and *Coaching archetypes* →.
    - **No boxed panels.** Sections are separated by hairlines and space.
13. **Offline right zone = "Your Career"** (`.cr`). It is built for offline, not the online zone with dead panels, and it makes **no remote calls**. The zone holds the things that fill up as you coach, so it reads as potential when empty and as accomplishment when played.
    - **Career numerals** (`.cr-n`): career record (with win %), titles, seasons and **career Geek Points**, all across programs on this computer. Before anything is earned, the numerals are **hollow** outlines (`.hollow`). They turn solid as they fill. Titles stay hollow until the first title.
    - **Trophy Case shelf.** When empty, it shows labelled dashed medallion slots for what can be won (Conference, Region, National, First signing class), not a blank shelf. When earned, titles are gold and milestones neutral. *View all* → opens the Trophy Case page.
    - **Top Seasons** (`.tsn`): up to 5 seasons across all programs, ranked by **season Geek Points**. Each row shows rank, program banner art, program + season, record, finish (a title finish in reward gold) and GP. An in-progress season can rank and is tagged "In progress · Week N". Unfilled ranks are dashed rows with hollow numerals, and the first empty rank carries one line of copy ("Your next season can land here").
14. **Trophy Case page.** Home Base top bar with ← Home Base. Career numerals in the head. **Titles** use large gold medallions. **Milestones** use neutral medallions. **Season Reviews** is one table row per season, with a Review → link on completed seasons.
15. **Medallions carry a tier letter** (N / R / C, or S / A for milestones) in a circle. They are not drawn trophies. Titles are gold. Milestones stay neutral in the persistent case even though gold is allowed at that tier, because the case is standing UI and gold should stay the exception.
16. **Fit.** Both zones fit 1280×720 and 1920×1080 with nothing below the fold. Home Base is not a live-gameplay screen, but it is the front door.

### Reward ladder
17. **Everyday** (`.evr`) is the quiet style for lean updates, small rank moves and routine +1s. It keeps the existing Office rows:
    - no motion of its own and no sound
    - no hue; direction is a glyph at luminance (▲ t100, ▼ t60, — t38)
    - a 5px t60 dot marks an unseen row
18. **Weekly: one "Since last week" card** (`.wkc`) replaces the Result and What moved cards in Office column 1. It fits the column: about 382×530 at 1280 (content 1180 across three equal columns, below the 56px week strip). It contains, in order:
    - kicker: WIN/LOSS, week and site, Box score →
    - a two-row scoreboard, your team always on top
    - the headline, when one exists
    - Player of the Game (win) or Team leader (loss), with portrait and PTS / REB / AST
    - four badges: National, Conference, Record, Streak
    - Training, up to 3 players at 1280 and 5 at 1920
    - an optional "Also" row for a folded moment
    - All changes →
19. **LOSS is dignified.**
    - No team wash and no count-up.
    - Both teams' names and scores are t87, so the loser isn't dimmed on your own page.
    - The badge ▼ is t60, not red.
    - The label is Team leader, the existing `leader_role` on a loss.
    - No sound.
20. **Exceptional gain is the only weekly gold:** a 6px gold diamond, a 1px gold ring and a gold delta on that one chip, plus an "Exceptional gain" key in the Training head. The attribute tile keeps its tier hue on the glyph. The marker shows on a loss too.
21. **Milestone = one modal template** (`.mm`).
    - Header: moment type, queue position, close.
    - Title and one-line dek.
    - Variant body.
    - Footer: "Up next · …", or a follow-on link, and one `.btn-ghost` that reads **Next** or **Done**.
    - `.is-gold` is used for signing class, walk-ons, first bracket reveal, first coach archetype and region bye. `.is-quiet` is used for elimination: no gold, no sound, fade only.
    - **Confetti moves out of the milestone tier.** Today the bracket reveal and the signed-class modal both throw confetti; confetti is now season-peak only.
22. **Season peak = a full takeover.**
    - **Title:** blurred banner art, gold glow, confetti, the title, final score, this season's title medallions, "Added to your Trophy Case".
    - **End-of-season review:** record, finish (national / conference / region seed), titles, best players, awards (All-American teams), class signed. The review is written to the Trophy Case.
    - Confetti is gold + white only. The shipped `#2bd66a` green is dropped because green is reserved.
23. **One moment queue** (server-side). See the behaviour below.
24. **Duplicate signing celebration.** Keep the Signing Day hub reveal as the live beat and let the Office milestone be the one-time summary. Drop the separate `recruiting_results_modal` confetti path.

## New components (`ch7.css`)

| Class | What |
|---|---|
| `--reward-gold` + motion tokens | See below. |
| `.hb` `.hb-top` `.hb-body` `.hb-l` `.hb-r` `.hb-h` | Home Base shell: own top bar, two-zone grid (left 480 / 700px). |
| `.slot` `.slot-h` `.slot-more` | Slot with its `01 ——— ···` header outside the card. |
| `.door` (+ `.door-art` `.door-tag` `.door-live` `.door-i` `.door-nums`) | Occupied slot. `.door-live` is the game-in-progress strip. |
| `.vacant` | Empty slot, dashed, quiet button. |
| `.pop` `.pop-i` / `.cfm` / `.btn-del` | Slot menu, delete confirm, destructive button. |
| `.hb-util` `.hb-link` | Tutorials · Settings · FAQs. |
| `.fag` `.soon` | Find A Game placard, Coming Soon pill. |
| `.sec` `.sec-h` `.sec-f` | Open (unboxed) section head. |
| `.hbt` `.hbt-row` `.hbt-tb` `.hbt-n` `.hbt-p` | Home Base tabbed panel (Around GOB ⇄ Leaderboard), new-count pill. |
| `.agc` (`.is-me` `.is-wait`) `.agc-g` `.wl` | Around GOB result card, grid, W/L plate. |
| `.lbp` `.lbt` `.lbl` | Leaderboard top-3 tiles and list. |
| `.cr` `.cr-n` `.hollow` `.cr-cap` | Your Career zone, career numerals, hollow (potential) numeral. |
| `.tro.slot-e` | Empty, labelled medallion slot (what you can win). |
| `.tsn-l` `.tsn` (`.is-e`) | Top Seasons list, row, empty rank. |
| `.cn` | Career numeral (Trophy Case page head). |
| `.tcase` `.shelf` `.tro` `.med` (`.gold` `.ms` `.open` `.lg`) | Trophy shelf, item, medallion. |
| `.tc` `.tc-head` `.tc-col` `.tc-empty` | Trophy Case page. |
| `.evr` `.dir` | Everyday row and direction glyph. |
| `.wkc` (`.is-win` `.is-loss`) with `.wtag` `.sb2` `.pg2` `.bdgs` `.bdg` `.gn` `.gc` (`.xg`) `.xg-key` `.wkc-also` | Weekly card. |
| `.mm-scrim` `.mm` (`.is-gold` `.is-quiet`) with `.mq` `.mm-f` `.rc` `.seed` `.mu` `.fin` `.arch` `.mm-sum` | Milestone template and variant bodies. |
| `.pk` `.cf` / `.rv` `.rv-top` `.rv-cols` `.bp` `.aw` | Season peak title, confetti, end-of-season review. |
| `.btn-ghost.lg` | Larger ghost button for takeovers. |

Everything else is existing: `.advance`, `.btn-ghost(.sm)`, `.lnk`, `.seg`, `.ldb-r`, `.tbl`/`.tcard`, `.ad`, `.rtl`, `.portrait`, `.av`, `.logo`, `.eyebrow`, `.sub-h`, `.tg`, `.up`, `.card` and the Office cards.

## Reward gold

```
--reward-gold: #F0C560
```

This is not a new colour. It is the gold already shipped in `bigNewsModals.js` confetti and emblem.js `TIER_TOKENS` national `metalHi`. Tints are `color-mix()` at use (6–24%). There are no extra gold tokens.

| Allowed | Never |
|---|---|
| Title medallions (Home Base shelf, Trophy Case, season peak, review) | Buttons of any kind |
| Season-peak title glow, rule, confetti | Everyday rows |
| Milestone modal accent (2px top rule, eyebrow diamond, a celebratory medallion) | Weekly chrome: WIN tag, badges, scores |
| Weekly **exceptional-gain** marker (diamond, ring, delta, key) | Elimination, loss, delete, Find A Game |
| "Trophy Case" words in the peak/review footers | Navigation, links, RT, attributes |

The **tier metals** (`--tier-metal*`) stay as they are for the tournament top bar and next-game card. They are a data-driven accent, not a reward.

## Motion

| Tier | Entrance | Timing | Sound cue slot |
|---|---|---|---|
| **Everyday** | none (appears with the page) | — | none |
| **Weekly · win** | card rises, opacity 0 → 1, 10px, .985 → 1 | `--dur-arrive-card` 380ms `--ease-out`, t=0 | `SFX_WEEKLY_WIN` at `--delay-cue` 720ms (score lands) |
| | score count-up | `--dur-count` 600ms, ease-out cubic, t=120 | |
| | headline / POTG / Training | `--dur-arrive-item` 300ms, from `--delay-arrive-items` 320ms, `--stagger` 60ms | |
| | badges | 280ms ease, from `--delay-chips-calm` 560ms, 40ms stagger | |
| | exceptional-gain marker | `--dur-gain-sweep` 700ms gold halo, once, t=920 | |
| **Weekly · loss** | card fades | 300ms ease, no count-up, no stagger | none |
| **Milestone · gold** | scrim fade | `--dur-panel` 220ms | `SFX_MILESTONE` at t=200 |
| | dialog rises 16px, .98 → 1 | `--dur-moment-in` 320ms `--ease-out` | |
| | gold rule draws, scaleX 0 → 1 | 500ms, t=200 | |
| | body items | 300ms, from 160ms, 60ms stagger | |
| | queue step: current leaves (−24px) / next enters (+24px) | `--dur-queue-out` 180ms ease-in / `--dur-queue` 280ms `--ease-out` | cue replays per moment |
| | dismiss | 180ms fade | |
| **Milestone · quiet** | dialog fades | 280ms ease, no rise, no rule | none |
| **Season peak · title** | eyebrow | 300ms, t=120 | `SFX_PEAK` at t=600 |
| | title, scale .9 → 1 | `--dur-peak-in` 520ms `--ease-pop`, t=260 | |
| | gold rule | 600ms, t=600 | |
| | confetti: 60 pieces, gold/white | `--dur-confetti` 2400ms, t=600 + 0–900ms spread | |
| | team, score, medallions | 300ms, from 760ms, 90ms stagger | |
| | footer | 300ms, t=1200 | |
| **Season peak · review** | sections | 300ms, 90ms stagger | none (the title already played) |
| | medallions pop | `--dur-pop` 280ms `--ease-pop`, from 420ms, 80ms stagger | |

**The weekly entrance plays once**, on the first Office open after that result. Every later open shows the final state.

**Reduced motion** (`prefers-reduced-motion: reduce`; `?rm` in frames):
- Every tier renders its final state.
- No count-up, no translation or scale, no halo.
- **Confetti is not drawn.** The gold rule and medallions stay.
- The live-game dots stop pulsing.
- Sound cues still play, because they follow the audio settings (`uiSfx` sfx channel), not motion.

**Sound:**
- All cues route through `playSfx` on the `sfx` channel.
- The three files are new assets and do not exist yet. Until they exist, the slot is silent. Do not substitute `confirm-1-lowervol.wav`.
- The Home Base music (`Championship_Gridlock`) is unchanged.

## Moment queue (behaviour)

- The server builds **one ordered queue** per franchise from the moments that already exist: championship moments, conference/region modal, region bye, walk-on welcome, bracket reveal, signed class, archetype established or evolved. The FCC client stops chaining its own modals (`fccHasCompetingModal`, the Big News retry loop).
- **At most 2 pop-ups per Office visit.** A season-peak moment shows alone: the title first, then the review as "2 of 2".
- **The rest fold.** A lower-priority moment either becomes the weekly card's **"Also"** row (a one-line link) or waits for the next visit.
- **Priority (proposal):** season peak > elimination > bracket reveal > signed class > walk-ons > region bye > first archetype > bracket update. Bracket update and archetype *evolution* are weekly tier: they always fold.
- **In the modal:**
  - dots plus "N of M" in the header, "Up next · <type>" in the footer
  - **Next** (Enter) steps
  - **Done** closes the last one
  - **× / Esc** closes the current one, and the remaining queued items wait for the next visit (they are not dropped)
- **Seen** is written per moment on dismiss (existing PATCH / seen fields).

---

## Data needed

**EXISTS** means the inventories name the field or route. **MISSING** means it is not there. **PARTIAL** means it exists only online, or only in part.

**Do not invent, derive or approximate a MISSING field. Stop and ask.** Where a field is missing, the element is omitted rather than filled.

### Home Base: slots
| Element | Field | Status |
|---|---|---|
| Slot list, name, season, week, colours, `home_slot`, TB flags | `GET /franchise/list` → `_franchise_summary_for_list` | EXISTS (online + loopback) |
| Banner art | `<slug>_banner_primary.jpg` / `_banner_card.webp`; TB programs via `teamGeneratedArt.js` | EXISTS |
| Record, next opponent, national rank | `/franchise/command-center/data` per franchise (`team_record`, `next_game`, `rank`) | EXISTS (one CC read per slot, as today) |
| Game in progress / Finishing week label | CC `active_game_resume`, `cpu_sim_resume` | EXISTS. The door strip shows "Game in progress · Week N" only. **Score and quarter are not shown**, because their fields are unconfirmed. |
| **Last played** (which slot gets the green, the "Last played" tag) | `updated_at` / `last_played_at` on the list summary | **MISSING.** It is not exposed. Needed before the green can be assigned. Do not fall back to slot order. Ask. |
| Delete | `DELETE /franchise/{id}`, `FranchiseLS.clearAllForFranchise` | EXISTS |
| Slots-full guard | `franchises.length >= max` | EXISTS |

### Home Base: online right zone
| Element | Field | Status |
|---|---|---|
| Find A Game | static | EXISTS (non-interactive) |
| Around GOB cards | `/api/community/around-the-league` → `slots[]` (coach, teams, score, rank, record) | EXISTS. **The team slug per slot is needed to load `<slug>_banner_card.webp`; confirm it is on the payload.** "def./lost to" needs the win flag or both scores per slot; confirm. **Season and week** per slot: confirm both, and omit the pair if either is missing. The "You" card needs a way to tell it is yours (`atlCurrentUserId`). Endpoint name can stay; only the label changes. |
| New-since-last-visit dot | `localStorage gob_atl_last_visit` | EXISTS |
| Leaderboard | `/api/auth/leaderboard` → `top[]`, `current_user`, `titles_top[]`, `titles_current_user` | EXISTS. Needs ≥12 rows in `top[]` (15 at 1920); confirm the limit. A coach's program art on the top-3 tiles would need a team per row, which is MISSING, so the tiles carry no art. |
| Last tab / new count on tab | `localStorage` (new key) + `gob_atl_last_visit` | New client key; the count uses the existing last-visit stamp. |
| Account name / Log Out | `/api/auth/me` | EXISTS |

### Home Base: offline right zone, "Your Career" (loopback only, no remote calls)
| Element | Field | Status |
|---|---|---|
| Which slot gets the green (last played) | `updated_at` / `last_played_at` | **MISSING** (see slots, above) |
| Career record, win % | `users.record` | **PARTIAL.** Online only via `/api/auth/me`; desktop skips it. Needs a local mirror. Win % is shown only if the server returns it; the client doesn't compute it. |
| Titles | `users.championships_total` | **PARTIAL.** Online only, and a count only. |
| Seasons coached | — | **MISSING** (online and offline). Do not count current slots. |
| **Career Geek Points** | — | **MISSING offline.** GP exists online (`/api/auth/leaderboard`, per-game award). Single-player needs the same per-game GP rule to run locally and a career total stored per coach. Do not approximate GP on the client from wins. |
| Trophy Case: titles (tier, season, program) | consumed `pending_championship_moments` | **PARTIAL.** Confirm consumed moments are retained per franchise after dismiss. There is no cross-program store. |
| Trophy Case: milestones | — | **MISSING.** There is no achievements store. The milestone list itself needs product sign-off. |
| **Top Seasons**: program, season, record, finish, **season GP** | — | **MISSING.** Needs a per-season record, `season_reviews[]` (written at `finish_season`), plus a live row for each in-progress season. **Season GP** is new (the sum of that season's per-game GP). Ranking is server-side: the top 5 by season GP, with ties broken by record (to confirm). |
| Program art on Top Seasons rows | `<slug>_banner_card.webp`; TB programs via `teamGeneratedArt.js` | EXISTS |
| Trophies/seasons after a program is deleted | — | **Decision needed.** Recommendation: career, trophies and top seasons survive program deletion. |

### Weekly card (`office_digest`)
| Element | Field | Status |
|---|---|---|
| WIN/LOSS, week, site, scores, names, opponent rank, round name, box score | `result.*` (`user_won`, `site`, `opponent_rank`, `round_name`, `box_score`) | EXISTS |
| Your rank prefix | `what_moved.national_rank.now` | EXISTS |
| Headline | `result.headline` (only when a `season_news` story stores the game id) | EXISTS (optional) |
| POTG / Team leader | `result.leader {player_id, name, stats}`, `result.leader_role` | EXISTS. `stats.pts / reb / ast` are confirmed in `office_digest.py`. Anything more is not shown. |
| Portrait | `API_CONFIG.getPlayerImageUrl(player_id)` + silhouette fallback | EXISTS |
| Badges | `what_moved.national_rank`, `conference_standing`, `record`, `streak` | EXISTS. The delta is omitted when 0 or null. **Streak milestone thresholds are MISSING:** no special treatment for W5, W10 and so on. |
| Training rows | `what_moved.attribute_changes[] {player_id, name, attribute, from, to}` | EXISTS |
| **Exceptional gain flag** | per change | **MISSING in the digest.** The training report has the threshold (`training-report.js` `change-gold`), but the digest does not carry it. Add it server-side from the same rule. The client must not recompute it. |
| First open after this result (plays the entrance once) | — | **PARTIAL.** UX_System says the win counts up once. Confirm where "seen" is stored. |
| "Also" row | moment queue | **MISSING** (new). |
| Sound | `SFX_WEEKLY_WIN` | **MISSING** (new asset). |

### Milestone modal
| Variant | Field | Status |
|---|---|---|
| Signing class | `recruiting_results_modal` (signed recruits, counts) | EXISTS. Per recruit: name, position, home region, RT current → potential. Confirm `home_region` is on the payload. |
| Walk-ons | `walk_on_welcome_modal` | EXISTS |
| First bracket reveal | `bracket_reveal_modal` (layout, seeds, tier) | EXISTS. Seed, your first matchup and the path come from the layout. Week labels: confirm `ROUND_NAME_BY_WEEK`. |
| First coach archetype | `archetype_evolution_pending` / first-establish reveal, `GOBArchetype` manifest copy | **PARTIAL.** Needs `/api/auth/me`, so it is broken offline (inventory §5). |
| Region bye | `region_bye_modal_eligible` / payload | EXISTS |
| Elimination | `conference_rs_region_modal` + `result` (final score) + season record / conference place / national rank | EXISTS. The seed per team in the final line: confirm it is on the payload, and omit it if not. |
| Queue position, "Up next" | server-side `moment_queue[] {id, type, tier, priority, payload, seen}` | **MISSING** (new server work; reads existing fields, no finalize changes) |
| Sound | `SFX_MILESTONE` | **MISSING** (new asset) |

### Season peak
| Element | Field | Status |
|---|---|---|
| Title takeover: tier, team, banner, final score | `pending_championship_moments` | EXISTS. Confirm the final score and opponent are on the moment. |
| This season's other titles (medallions) | other consumed moments this season | **PARTIAL** (as Trophy Case) |
| Program title count ("first national title") | — | **MISSING.** Not shown. |
| Review: record, national rank, conference place, region seed | standings / rankings / bracket | EXISTS at season end. Must be **snapshotted** before rollover (MISSING store). |
| Review: awards | `GET /franchise/awards` → `all_american_teams` (1st/2nd/3rd) | EXISTS from week 35 |
| Review: best players | season stat lines exist | **Selection rule MISSING.** Which three, and by what stat? Ask. Do not rank on the client. |
| Review: class signed | `week_35_recruiting_results` | EXISTS |
| Sound | `SFX_PEAK` | **MISSING** (new asset) |

## Not designed here
- Court and end-of-game animation (`gameCompletionPopup.js`, `feature/animation-reward`).
- PvP matchmaking. Find A Game stays a non-interactive, online-only teaser.
- Geek Points inside the franchise UI. It remains online social only, and offline has no local mirror.
- An RT letter-change moment. There is no event field today (inventory §2).
