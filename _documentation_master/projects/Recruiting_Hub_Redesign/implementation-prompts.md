# Recruiting UX — Implementation Prompts

GOB · 2026-08-17 · companion to `recruiting/ux-build-plan.md`

**A sequenced series, not one master prompt.** Reasons: (1) Prompt 0 is destructive and must
be verified before anything is built on top of it; (2) Prompt 1 is backend-only and shouldn't
ride inside a UI prompt; (3) the FCC promotion (Prompt 2) changes how the player *reaches*
recruiting and should land before the screens it routes to are reworked.

**Mechanics are unchanged.** Weeks 1–19 passive with performance driving leans, 20–26 invites,
35 Signing Day. No fog of war, no scout, no motivation archetypes, no legacy locks. If a
prompt seems to imply any of those, it's a mistake — check the build plan.

**The mockups are the visual and behavioural source of truth. Match them; don't reinterpret.**

```
_documentation_master/projects/Recruiting_Hub_Redesign/mockups/
  1-recruits-pool.html      2-fcc-integration.html   3-invite-board.html
  4-signing-day.html        5-results.html           _shelved-scout-desk.html  ← out of scope
```

---

## Prompt 0 — Ground clearing

**Goal:** Remove the dead recruiting frontend and unify RT display. No user-visible change.

**Source:** `scripts/cleanup-phase-0.sh` (already written and dry-run verified against the repo).

**Build:**

1. **Run the script.** `git switch -c chore/recruiting-phase-0` then
   `./scripts/cleanup-phase-0.sh --apply`. It repoints the stale week-35 CTA in
   `franchise-command-center.js` (grep for `recruiting-orders.html` — the line moves), verifies
   no live inbound links remain, deletes 10 files (~3,862 lines), and confirms all keepers
   survived. It stages but does not commit.
2. **Decide on `awards.html`.** `recruiting.css` (1,311 lines) is only consumed by
   `awards.html`, which is itself orphaned — the FCC Awards button points at `leaders.html`
   (`js:1599`). Confirm nothing external links to it, then re-run with `--include-awards`.
3. **Adopt letter grades in recruiting.** Retire the 4-band raw-colour RT scale. Use the
   Styleguide's 9-tier letters, already mandated as *"identical for active players and
   recruits."* `rt_current_potential()` already emits the `"C/B"` pair. Every RT cell in
   recruiting becomes `B` or `B/A`, with a `Current / Potential` tooltip using the app's
   existing `data-tooltip` convention.
4. **Correct `recruiting_file_manifest.md`.** §1 lists four live screens; only the Hub is
   reachable — the other three redirect from `<head>`. Move the three stubs, their JS and
   `recruiting.css` into §7. §6's "Prompt 0 shipped" understates it: Prompts 0–4 shipped.
5. **Optional, same neighbourhood:** `bindResourcesLinks()` (`js:1562-1601`) assigns hrefs to
   eight ids that exist in no HTML in the repo and re-runs on every tab switch.
   `updatePlaybooksButtonState()` fires a live `GET /api/playbooks` on every FCC init to style
   an element that isn't in the DOM.

**Acceptance:** hub loads and all four phases render; the week-35 FCC CTA reaches
`recruiting.html` in one hop; all six recruiting tests and both Playwright specs pass; no
`recruiting-orders.html` references remain outside docs.

---

## Prompt 1 — The Wire (backend only)

**Goal:** Report lean movement in **both** directions. The mechanic already exists; only the
reporting is missing.

**Build:**

1. **`diff_lean(old, new) -> [event]`** — a pure helper. Both lean mutation sites already hold
   `old_lean` and `new_lean` in the same scope and discard everything but one additions-only
   boolean. No extra DB reads. Event kinds:
   `gained_you · dropped_you · moved_up · moved_down · rival_took_your_top · displaced`.
2. **Persist** as `franchise_doc["recruiting_lean_events"][week]`, matching the existing
   week-keyed pattern used by `recruiting_results`. **Filter at write time to user-relevant
   events** — user is actor, displaced party, or already on that recruit's ladder. That holds
   a season to ~150–300 events (~60 KB); unfiltered league-wide is ~3,000 and belongs in its
   own collection.
3. **Lift the `week > 26` early return** in `_append_franchise_week_news`. Weeks 27–34
   currently generate lean movement and report nothing.
4. **Add a `recruiting_*` story type** to `season_news` so personal recruiting events can be
   filtered on their own. `season_news` already exists and already carries
   `_build_recruiting_leans_story` — extend it, don't build a parallel system.
5. **Deprecate `fcc_pending_new_lean_recruit_ids`.** It **cannot represent a drop** — readers
   re-intersect it against the recruit's *current* lean list, so a recruit who dropped you is
   filtered out by construction. Don't try to extend it; the event log supersedes it.

**Copy:** events render as sentences with causes, not data.
`DeAndre Pope dropped you — Fairview moved to #1` ·
`Marcus Bell moved you to #1 — after the Kettle Falls win` ·
`Andre Whitlock added you at #3`.

**Acceptance:** a season produces both gains and drops; weeks 27–34 produce news; event count
per season lands in the 150–300 range; `/franchise/news` can filter to recruiting only.

---

## Prompt 2 — FCC promotion

**Goal:** Recruiting leaves Run Training and becomes a first-class FCC presence all season.

**Source:** `2-fcc-integration.html`.

**Build:**

1. **Out of Run Training — without risking missed weeks.** The invite **still fires on week
   advance** using whatever board exists, exactly as today; no week can be silently lost.
   `training.js:1453` stops routing to recruiting. This is the resolution to the decoupling
   that was proposed, built, and reversed — the FCC presence below replaces the routing.
2. **Three levels, driven by state, not by phase:**

   | Level | Fires when | Element |
   |---|---|---|
   | Ambient | Nothing needs the player | Coach's Office Recruiting card |
   | Prompted | Board unsent this week, or unseen wire events | Secondary hero button + `.inbox-badge` |
   | Gated | Week 20 with no board · Week 35 | `#play-now` itself |

3. **The secondary button** goes in the **existing empty second slot** of
   `.hero-buttons-group` — it is a flex *column* containing only `#play-now`
   (`html:59-63`, `css:302-306`) and the second position has never been occupied. **No layout
   surgery.** Two lines: `Recruiting` in Bebas, then a smaller count line. **Both buttons are
   `width:186px`** — do not let the secondary size to its content, it renders 265px wide and
   the ragged edge reads as a bug. Carries a count, never a bare noun.

   | Weeks | Condition | Line 1 / Line 2 | Treatment |
   |---|---|---|---|
   | 1–19, 27–34 | Unseen wire events | `Recruiting` / `2 moved · 1 dropped you` | amber, no pulse |
   | 1–19, 27–34 | Nothing new | *hidden* | — |
   | 20–26 | Board unsent, events pending | `Recruiting` / `2 moved · 1 dropped you` | amber + `.fcc-invite__dot` pulse |
   | 20–26 | Board unsent, no events | `Recruiting` / `Invite Wk N of 7` | amber, no pulse |
   | 20–26 | Board sent this week | `Recruiting` / `Board sent` | amber, `.is-dead` |

4. **Tab badge.** `.inbox-badge` (`css:540-566`) is a finished 8px amber pulse dot that grep
   finds **zero** usages of anywhere in `FrontEnd/`. Apply it to the Recruiting tab when
   prompted. Rename the tab **Recruits → Recruiting** (same slot, no tab-bar surgery).
5. **Week-20 gate.** With no saved board at week 20, `#play-now` becomes `Build Invite Board`.
   Slot it in the `updatePlayButton` branch order immediately after `cut_required` — same
   pattern as the existing "Assign Practice Squad" gate.
6. **Coach's Office card becomes the Wire.** Gains *and* drops, newest first, plus a
   phase-appropriate status line. `.fcc-newlean-badge` / `.fcc-newlean-row` (`css:3963-3989`)
   already exist for gains; add a red/amber counterpart for drops. **Drops must render as
   visibly as gains.**
7. **Grid change.** Recruiting card spans two columns; **retire the Standings card** (it
   duplicates the Standings tab *and* `/standings.html`). 8 cards with one spanning 2 is 9
   column-units and doesn't divide into rows of 4 — retiring one resolves it:

   ```
   Row 1:  Locker Room │ Next Game │ RECRUITING (span 2)
   Row 2:  Rankings    │ Last Game │ Player Scoring │ News
   ```

   Locker Room in C1 and Next Game in C2 puts **Next Game directly above Last Game** —
   intentional, keep the pair stacked. Deleting Standings means removing its `<section>`
   (`html:84-87`) and `renderHomeStandingsCard()` (`js:973-1009`); **check first** whether
   `#standings-full-link` (`html:130-132`) is scoped to the card or the tab. At double width,
   revisit the 126px `.fcc-home-list-scroll` cap for this card.

**Colour law:** green gates, orange doesn't. The amber secondary is always skippable; only
`#play-now` turns green and blocks the week.

**Acceptance:** both hero buttons are 186px wide and share an edge; badge appears only when
prompted; week 20 with no board cannot be advanced past; grid is 7 cards in two clean rows;
Next Game sits directly above Last Game; drops are as visible as gains.

---

## Prompt 3 — Recruits pool

**Goal:** The one screen that must survive **450 rows**.

**Source:** `1-recruits-pool.html`.

**Build:**

1. **Kill `.pool.condensed`** (`recruiting-spine.css:260`). Attributes stay visible in every
   phase — today they're hidden exactly when you're comparing recruits.
2. **Column order:** `Recruit · Pos · RT · Yr · Ht · Rgn · Attributes · Lean · Watch`.
   Name/Pos/RT lead because they answer "is he worth watching" fastest, and it keeps the
   sorted column beside the name. Lean and Watch pair at the right edge because both are about
   *you and him*, not about him.
3. **Name column is capped, not flexed.** A flexed name column leaves dead space between the
   name and Pos. The table sizes to its content (~1030px) rather than stretching — shorter eye
   travel, and it frees room for legible attribute chips.
4. **Headers are centered over their columns**, and **`Attributes` is centered across the full
   12-chip block** — not right-aligned, not left-aligned over the first chip.
5. **Sticky header**, sortable columns, RT descending by default.
6. **Filters split into two labelled rows.** *Filter*: Region dropdown (9 options, rarely
   changed) + **Position and Year as segmented controls** (few options, switched constantly —
   a dropdown costs a click every time) + name search. *Views*: Watchlist · Leans to me ·
   Unranked by me. Two control types were doing different jobs with nothing explaining why;
   the split is the explanation.
7. **⚠ Watchlist — the one new piece of state in the whole project.** A star toggle per row.
   - `recruiting_watchlist`: an array of recruit IDs on the franchise doc, plus a toggle endpoint.
   - **It seeds the week-20 invite board.** That's what makes it a UX fix rather than a feature —
     without it there's no way to remember, across 19 weeks, who you liked.
   - Also a filter view, so 450 collapses to your shortlist in one click.
   - 32px hit target; gold filled when on, hollow when off; no text label (you'll click it
     repeatedly while scanning).
8. **Headshots.** `getRecruitImageUrl(image_id, {size:'card'})` already exists
   (`api-config.js:306`), `image_id` already ships on the recruit record, and there's a
   lazy-paint retry (`ensureRecruitImage` → retry → generic headshot). Portraits already render
   in box score, player detail, POTG and the scouting report — the pool is the one place they
   were never added.
9. **Names link to player detail.**

**Acceptance:** 450 rows scroll at 60fps with the header pinned; filters compose; watchlist
persists across reload and across devices; week-20 board is pre-populated from the watchlist;
every header is centered over its column.

---

## Prompt 4 — Invite board

**Goal:** Give the player a reason to re-rank every week.

**Source:** `3-invite-board.html`.

**Build:**

1. **The dock** shows the top unvisited recruit — re-ranking *is* the invite decision, there's
   no second selection step.
2. **A "This week" column on each board row**, driven by the Prompt 1 event log:
   `Dropped you / Fairview took #1`, `Moved you to #1 / after Kettle Falls`, or `—`. **This is
   the highest-value addition on the screen** — it's the re-rank trigger, delivered inline on
   the row it affects rather than only in a sidebar.
3. **Row tint** for movement: green wash for gains, red wash for drops. `Dropped you` should be
   the loudest thing in its row — it's the only thing on this screen that should make you act.
4. **Right rail:** "N changes affect your board" (each event annotated with the board rank it
   hits) and roster needs by position. Nothing else — earlier drafts had a scout status panel
   here and it was noise.
5. Full lean ladder per row (the shipped spine component), headshots in dock and rows, names
   link to player detail (they render as plain text today — `recruiting-hub.js:232`).
6. Drag-reorder and the 20-slot cap stay as built.

**Acceptance:** board order drives the dock; wire events appear on the affected rows and in the
rail with correct board ranks; drag-reorder persists; a week with no events shows a quiet rail
rather than an empty panel.

---

## Prompt 5 — Signing Day

**Goal:** Stop making the decision for the player, and stop showing them a fake number.

**Source:** `4-signing-day.html`.

**Build:**

1. **Delete `seedAlloc()`** (`recruiting-hub.js:343-350`). It allocates 12/9/6 points — 27 of
   50 — and attaches **binding playing-time promises to two recruits**, unmarked, on page load.
   The page must load at **0 of 50 with no promises**. If a helper is wanted later it must be a
   button the player presses.
2. **Replace the placeholder odds bar.** The current formula is
   `base(standing) + points × 2.2 + (promise ? 18 : 0)` — admitted placeholder, blind to
   rivals. Replace with two honest columns:
   - **Standing** — your lean position with its multiplier (`#1 ×5`, `#2 ×3`, `—  ×1`). This
     also teaches the mechanic the tutorial has always claimed matters.
   - **Field** — how many programs are funding him, as a count plus a segment bar with your
     segment highlighted.
   **⚠ Backend:** this is the one new surface in the project — a per-recruit competition count
   on the week-35 payload. CPU week-35 boards are already seeded server-side on the user's
   first save, so the number is knowable at that moment.
3. **Surface roster capacity.** `available_roster_spots` and `available_scholarships` are
   already in the hub payload and simply aren't rendered, while funding stays uncapped against
   a hard 15-man ceiling.
4. **Remove the scholarship toggle.** It's normalized false/dormant and affects neither score
   nor roster state — a visible control that does nothing.
5. **Year and archetype back on the signing row** (`recruiting-hub.js:362-384`). A senior and a
   freshman currently look identical on the screen where you commit 50 points.
6. **A submit summary** replacing the blind 950ms redirect (`:490-492`) — what you committed,
   before you leave.
7. **Pre-flight rail**: specific warnings, not stats. *"6 programs funding, you're #2 at ×3 —
   five points is unlikely to carry."* *"19 points unspent and 4 roster spots; Ruiz is
   uncontested at ×1."*

**Acceptance:** page loads at 0/50 with zero promises; no percentage is displayed anywhere;
competition counts match the seeded CPU boards; steppers stop at 0 remaining; submit shows a
summary before navigating.

---

## Prompt 6 — Results

**Goal:** Pay off a season of tracking.

**Source:** `5-results.html`.

**Build:**

1. **Sequence playback.** Recruits revealed one at a time in signing order, with Next /
   Auto-play / Skip all. **Batch resolution is unchanged** — the engine already processes
   recruits one at a time in RT order, so this is a presentation of a sequence that already
   happens. No new engine.
2. **Every row explains itself.** The current screen strips a recruit you tracked for 35 weeks
   down to Pos/Region/RT (`:507-550`). Each row carries: headshot, name, position, RT pair,
   where he signed, points spent, your standing, field size, and a one-line *why* —
   `#1 lean ×5 · only 2 programs funding`, `6 programs funding · 5 points didn't carry`,
   `Uncontested — nobody else boarded him`.
3. **Class summary** after the sequence: signed / funded, class average RT, points spent,
   roster spots remaining.

**Acceptance:** playback advances and can be skipped; every row shows a reason; the summary
reconciles with what was submitted on Signing Day.

---

## Sequencing

| # | Prompt | Depends on | Ships alone |
|---|---|---|---|
| 0 | Ground clearing | — | No user change; unblocks everything |
| 1 | The Wire (backend) | — | Yes — 27 dead weeks become legible |
| 2 | FCC promotion | 1 (for counts) | Yes — recruiting stops being buried |
| 3 | Recruits pool | 0 | Yes |
| 4 | Invite board | 1, 3 | Yes |
| 5 | Signing Day | 0 | Yes — removes the most misleading screen |
| 6 | Results | 5 | Yes |

**0 and 1 can run in parallel** — one is frontend deletion, the other backend addition.
**5 can jump the queue** if you want the highest-value single fix first: it carries all three
of the bugs in §2 of the build plan and is self-contained.
