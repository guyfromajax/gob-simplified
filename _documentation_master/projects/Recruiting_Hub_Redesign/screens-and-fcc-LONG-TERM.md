# Recruiting — Screens & FCC Design

GOB · 2026-08-16 · companion to *Recruiting Overhaul — Design v2*

The system design says what recruiting should ask of the player. This says where it lives:
the screen inventory, what's new, what changes, what doesn't come back, and how recruiting
occupies the FCC now it's being promoted out of Run Training.

---

## 1. Two findings that shape everything below

**The FCC already has an empty slot for the recruiting button.**
`.hero-buttons-group` is `display:flex; flex-direction:column; align-items:flex-end` and
contains exactly one child — `#play-now` (`franchise-command-center.html:59-63`,
`.css:302-306`). It was built as a *group*, in a column, and nothing has ever occupied the
second position. The button you sketched — below the green CTA, glowing during invite weeks
— goes exactly there. **No layout surgery.**

**The pulsing tab badge you'd want already exists and has never been used.**
`.inbox-badge` (`css:540-566`) is an 8px amber dot, absolutely positioned on a tab button,
with a 2.5s pulse animation and a glow shadow. Grep across all of `FrontEnd/` finds **zero**
places that add the class. It's a finished, unused convention sitting in the stylesheet
waiting for exactly this use case.

Between them, the two hardest-to-place pieces of the FCC promotion are already built.

### What's genuinely constrained

- **Fixed-height shell.** `#franchise-container` is `height: calc(100vh - 30px)`,
  `overflow:hidden`, max 1400px (`css:27-42`). The page never scrolls; only the active tab
  panel does. A new panel must fit or scroll internally.
- **Tab bar is a 7-column grid.** 14 tabs = two clean rows (`css:462-466`). A 15th makes a
  ragged third row. **But we don't need one** — the Recruits tab already exists and gets
  repurposed.
- **Home grid is a hard 4 columns with no breakpoints.** 8 cards = 2 rows (`css:685-689`).
  No card currently spans. Adding a 9th card means either a swap or introducing a span rule.
- **Effectively desktop-only.** No breakpoint touches the home grid, tab bar, or header.

---

## 2. FCC integration

### 2.1 The three levels are driven by *state*, not phase

The v1 model tied each level to a week range. That's wrong, and the scouting question
exposes why: weeks 1–19 need prompting *sometimes* — when days are idle or a report has
landed — but not every week, because standing orders mean no weekly submission is required.

The corrected model: **phase determines what recruiting is. State determines how loudly it
asks.**

| Level | Fires when | Element | Treatment |
|---|---|---|---|
| **Ambient** | Nothing needs the player | Coach's Office **Recruiting card** + **News card** | The wire and scout status sit where the player already looks. |
| **Prompted** | Something is idle, ready, or changed | **Second hero button** in `.hero-buttons-group` + **`.inbox-badge`** on the Recruits tab | Amber, count-bearing, pulsing. Always skippable. |
| **Gated** | Week 20 with no board · Week 35 | **`#play-now` itself** | The green CTA becomes the recruiting action. Cannot advance past it. |

This maps cleanly onto the Styleguide's colour law: **green is for gating actions, orange
for non-gating.** Gated recruiting is the green hero button; prompted recruiting is the
amber secondary. The visual system already encodes the distinction we designed.

### 2.2 What triggers a prompt

**Weeks 1–19 (scouting).** Prompt when — and only when — there is a reason:

| Trigger | Label | Why it matters |
|---|---|---|
| Scout days idle — no standing order, or orders exhausted | `Scout · 5 days idle` | **Unused days are lost forever.** This is the one that must nag. |
| Assignment completed, report unread | `Scout · 2 reports ready` | A payoff is waiting |
| A scouting target's lean moved, or a target committed elsewhere | `Scout · target committed elsewhere` | The plan needs revisiting |
| Orders running, nothing new | *hidden* | — |

That last row is the important one. **Setting standing orders makes the prompting stop** —
which teaches the mechanic without a tutorial, and means the player who doesn't want the
homework is rewarded for configuring it once rather than punished with a permanent badge.

**Weeks 20–26 (invites).** Prompt while the board is unsent this week, or when the wire has
events the player hasn't seen.

**Weeks 27–34 (tournament).** Ambient only — never prompted. Scouting is over, the board is
locked, and the postseason should own the player's attention completely. The wire keeps
reporting lean movement on the Coach's Office card, but recruiting does not ask for anything.

### 2.3 The secondary button

Lives in the free `.hero-buttons-group` slot, beneath `#play-now`. Present in **both**
active stretches — scouting weeks and invite weeks — since both can have something worth
surfacing.

**It carries a count, not a noun.** Not `Recruiting` but:

> **`Recruiting · 2 moved · 1 dropped you`**

A glow says *something happened*. A count says *something happened to you*, and only the
second earns a click. The numbers come straight from the Phase-1 lean event log — no new
data required.

| Weeks | Condition | Label | Treatment |
|---|---|---|---|
| 1–19 | Days idle | `Scout · N days idle` | Amber, `.fcc-invite__dot` pulse |
| 1–19 | Reports ready | `Scout · N reports ready` | Amber, pulse |
| 1–19 | Wire events, orders running | `Recruiting · N moved · M dropped you` | Amber, no pulse |
| 1–19 | Orders running, nothing new | *hidden* | — |
| 20–26 | Board unsent, events pending | `Recruiting · N moved · M dropped you` | Amber, pulse |
| 20–26 | Board unsent, no events | `Recruiting · Invite Wk N of 7` | Amber, no pulse |
| 20–26 | Board sent this week | `Recruiting · Board sent` | Amber, `.is-dead` |
| 27–34 | — | *hidden* | Tournament owns the screen |

**Hover shows a snapshot** — during scouting weeks, the scout's current assignments and days
remaining; during invite weeks, the top 5 of the board with any change this week. Reuse the
`.fcc-invite` card treatment (`css:3869-3938`), already the amber-accented, 3px-left-border
pattern with a pulsing status dot.

### 2.4 Week-20 hard gate

If week 20 arrives with no saved board, `#play-now` itself becomes `Build Invite Board` and
routes to the Hub. It sits in the `updatePlayButton` branch order **immediately after
`cut_required`** and before the week-35 branch — the same slot pattern as the existing
"Assign Practice Squad" gate, which already proves the mechanism.

### 2.5 Coach's Office Recruiting card — becomes the Wire

The 5-row lean table it shows today is a weaker version of what the Recruits tab already
displays; the card's job should be **news, not inventory**.

| Phase | Card contents |
|---|---|
| **Scout 1–19** | **The Wire** — gains *and drops*, newest first. Below it: `Scout · 3 of 5 days used · 12 weeks to deadline`. |
| **Invite 20–26** | The existing `.fcc-invite` block (this week's visit) + wire events. Scout line reads `Scout · hosting visits`. |
| **Tournament 27–34** | Wire only. No scout line — scouting is over. |
| **Signing Day 35** | Points remaining, promises made, roster spots left. |
| **Results 36** | Signed / lost summary. |

Drops must render as visibly as gains. The `.fcc-newlean-*` green badge convention
(`css:3963-3989`) already exists for gains — a red/amber counterpart for drops completes it.
**The losses are what people will actually read.**

**Decided: the card spans two columns, and the Standings card is retired.**

The card has to carry a wire feed *and* a scout status line, which doesn't fit a 1/4-width
card with a 126px list cap (`.fcc-home-list-scroll`, `css:852`). Spanning is technically
trivial — `grid-column: span 2` works in any CSS grid; it's just that no card does it today.
The constraint was arithmetic: 8 cards where one spans 2 = 9 column-units, which doesn't
divide into rows of 4.

Retiring Standings resolves it. That card shows user-conference rows already available in
the **Standings tab** and in full at `/standings.html` — the most duplicated card on the
surface. New layout:

```
Row 1:  Next Game  │ Locker Room │ RECRUITING (span 2)
Row 2:  Rankings   │ Last Game   │ Player Scoring │ News
```

7 cards, 8 column-units, two clean rows — and recruiting gets double-width prime real estate
on the surface every player lands on first.

**Implementation notes.** `.fcc-home-grid` is `repeat(4, minmax(0,1fr))` with no breakpoints
(`css:685-689`), so the span rule is a one-line addition to `.fcc-home-card-recruiting`.
Removing the Standings card means deleting its `<section>` (`html:84-87`),
`renderHomeStandingsCard()` (`js:973-1009`), and its call site. Check whether
`#standings-full-link` (`html:130-132`) is scoped to the card or the tab before removing it.
At double width the 126px scroll cap is worth revisiting for this card specifically — it was
sized for a quarter-width list.

### 2.6 Recruits tab — becomes the Recruiting dashboard

Today it's a 21-column lean table plus two footer links. The Hub does this better. Repurpose
the tab into the at-a-glance surface that answers *"what's happening in my recruiting?"*
without a page load:

1. **Wire** — full event feed for the season, not just this week's five.
2. **My board** — tracked recruits with knowledge level, standing, and change indicators.
3. **Scout status** — days, assignments, deadline clock, standing orders summary.
4. **Deep link** to the Hub for anything requiring action.

No tab-bar surgery: the tab exists, the label stays, the contents change.

### 2.7 Adjacent cleanup this touches

Worth doing while in here, since the code is already loaded:

- **The entire `resources-*` link set is dead.** `bindResourcesLinks()` (`js:1562-1601`)
  assigns hrefs to eight ids — `resources-recruits`, `resources-awards` and six others —
  **none of which exist in any HTML in the repo.** It re-runs on *every tab switch*.
- **`updatePlaybooksButtonState()` fires a live `GET /api/playbooks` on every FCC init**
  (`js:1526-1536`) purely to style `#playbooks-franchise`, which isn't in the DOM.
- **`updateAwardsButton()` and `updateScoutingButton()`** likewise target missing elements.
- **Tab ids are misnomers**: `press-tab` is labelled "News", `tutorials-tab` is "Inbox".
  Renaming labels is free; renaming ids breaks `?tab=` deep links (`commandCenterTabs.js:18-38`).

**Four tabs are near-total duplicates of standalone pages** — Standings, Team Stats,
Leaders, Inbox each duplicate `/standings.html`, `/team-stats.html`, `/leaders.html` and a
two-line list respectively. Not required for this project, but if you ever want a tab slot,
that's where the room is.

---

## 3. Screen inventory

### 3.1 New

**Scout Desk.** The one genuinely new surface — and it should be **a phase body of the Hub,
not a separate page.** During passive weeks the Hub currently shows a pool you can't act on;
making the Scout Desk the passive-phase body means the passive weeks finally have a purpose
*inside the recruiting screen*, and it costs no new route, no new nav, no new shell.

### 3.2 Substantially changed

| Screen | Change |
|---|---|
| **Recruit Pool** | Knowledge-aware rows; ★ column; fog states; attributes appear at L1 |
| **Recruit Detail** | Knowledge-gated sections; the scouting report becomes the centrepiece |
| **Signing Board** | Auto-allocation deleted; real competition counts; roster spots surfaced |
| **Results** | Sequence playback rather than a static table |
| **FCC Recruits tab** | Lean table → recruiting dashboard (§2.5) |
| **FCC Recruiting card** | Lean list → the Wire + scout status (§2.5) |

### 3.3 Lightly changed

**Invite Board** — slots carry the knowledge block and link to detail (they currently render
names as plain text, `recruiting-hub.js:232`). Ranking and drag-reorder are unchanged.

### 3.4 Retired

Already dead, formalised by the Phase 0 cleanup: `recruiting-invites.html/.js`,
`recruiting-orders.html/.js`, `recruiting-results.html/.js`, `recruiting.js`.

### 3.5 Deliberately not built

- **No standalone scout page** — it's a Hub phase body.
- **No standalone wire page** — `/news.html` exists and `season_news` already backs it.
  The wire is a story type, not a new surface.
- **No separate "my board" page** — the board is a persistent object rendered inside each
  phase, per §11 of the system design.

---

## 4. The Hub, phase by phase

One shell, one route, phase chosen by the calendar. The spine (phase strip, lean ladder,
pool anchor, story strip) carries throughout.

| Weeks | Phase | Body |
|---|---|---|
| 1–19 | **Scout** | Scout Desk + pool. Assignments, budget, deadline clock, the wire. |
| 20–26 | **Invite** | Invite board + pool. Scout unavailable — hosting visits. |
| 27–34 | **Tournament** | Pool (read-only) + wire. No scout desk, no invites. |
| 35 | **Signing Day** | Signing board. |
| 36 | **Results** | Sequence playback, then the class summary. |

### 4.1 One window, one deadline

Scouting exists only in weeks 1–19. The scout hosts visits during 20–26 — where he owns
whether a visiting recruit actually converts (§5.7 of the system design) — and is finished
after that.

**Everything you know on Signing Day, you knew by the end of week 19.** No late correction,
no last-minute due diligence, no discovering a legacy lock in week 34.

Weeks 27–34 are deliberately clear. The postseason should own the player's attention
completely, so recruiting there is something you *watch*, not something you *do*: the Hub is
read-only, the secondary button is hidden, and the wire keeps reporting leans moving on
judgments you can no longer revise. That's a legitimate dramatic shape — the work is done and
the results are still coming — and it keeps the tournament uncontested.

---

## 5. Scout Desk

The screen the whole passive stretch hangs on. Four regions:

**a. The budget bar.** Five day-slots showing what each is committed to. An out-of-region
Live eval consuming 3.5 of 5 days should *look* expensive. Slots auto-filled from the queue
are marked distinctly from ones the player assigned by hand.

Fill precedence, which the panel should state outright: **trips already under way → manual
assignments → auto-fill from the standing-orders queue in rank order, until the five days
are gone.**

**b. The days-remaining hero.** **Scout-days left in the season, not weeks** — `62 of 95`.
Days are the currency the player actually spends, so the number directly answers *can I still
afford that out-of-region trip?* in a way a week count cannot. The week-19 deadline sits
underneath as the caption.

Coverage sits below it as reports filed — *"38 film · 6 full"* — measured against **what is
realistically reachable (~57)**, not against the 450-recruit class. Measured against 450 it
reads as 8%, which looks like failure when it is in fact exactly on plan.

**c. Assignments.** Current orders, each showing target, action type, days committed, and
completion. Cancellable mid-flight (forfeiting spent days — a real cost, and a real
decision when the wire tells you a target just committed elsewhere).

**d. Standing orders — the queue and the mix.** A ranked list of targets, each tagged *Film*
or *Live*, plus the weekly split between the two (§5.6 of the system design). The scout
works down the queue and keeps going if the player never returns. The desk should say so
plainly — that promise is what converts this from homework into a system.

Because the scout always fills the week from the queue, **an idle day means the queue is
empty**, and the desk should surface that as the one thing genuinely needing attention.

**Assignment flow.** From the pool, a recruit row offers **Film** and **Live**, with cost on
the button before commitment and the out-of-region surcharge visible. **Live renders locked
until the Film Report exists**, with a tooltip saying why — that gate is what makes the
economy legible. The desk is where you review and adjust; the pool is where you assign.
Don't build a separate picker.

**Pool filters carry over from the current page**: Region (the user's own listed first) and
Year, plus report-state chips (Unfilmed / Filmed / Full). The pool also shows a compact lean
standing (`#1` / `#3` / `—`) — decision-relevant in both directions, since you want to scout
both the recruits already leaning to you and the ones you could steal. The full lean ladder
stays on the Invite board where it's the primary decision rather than context.

---

## 6. The knowledge block

One component, three states, rendering identically in the pool row, dock slot, signing row,
FCC card, and detail page. This is what makes the fog coherent rather than five bespoke
treatments.

| State | RT cell | Also renders |
|---|---|---|
| **Unfilmed** | `★★★☆☆` | Position · height · region · lean standing. Muted. |
| **Filmed** | `B` | All 12 attributes |
| **Full** | `B/A` | Attributes · bloom timing · motivation · legacy tie |

**The RT cell alone communicates the knowledge state, so no state badge is needed.** Stars
mean no film; a single grade means filmed; a pair means a full report. The progression *is*
the indicator, and the Full form is the `"C/B"` pair `rt_current_potential()` already emits.
The words *Unfilmed / Filmed / Full* appear only on the pool's filter chips — which is where
a player learns the vocabulary without being taught it. `L0/L1/L2` is spec shorthand and
never ships.

**Tooltips carry the explanation, matching the app's existing `data-tooltip` convention.**
The RT cell reads *"Current"* when only current RT is known and *"Current / Potential"* once
both are. The ★ cell explains what stars actually are: *"National media ranking — a
third-party estimate, not a scouting report. Your own scout produces a far more precise
read."* That one string plants the market-inefficiency idea that the whole steal mechanic
depends on.

Three design rules:

1. **Fog reduces density, not increases it.** L0 has almost nothing to show, so rows are
   naturally compact. This is what retires the `.pool.condensed` hack
   (`recruiting-spine.css:260`) that currently hides attributes exactly when you're comparing
   recruits.
2. **Every value shown is the truth.** No bands, no ranges, no estimates with disclaimers.
   Potential is hidden or exact, nothing between. See §4.2.1 of the system design.
3. **Level is always visible.** The player must be able to tell at a glance whether a gap is
   *bad news* or *no news* — a recruit who looks mediocre and a recruit you haven't watched
   are completely different situations and must never look alike. The star/grade/pair
   progression does this for free.

---

## 7. Reuse, don't invent

Conventions already in the codebase that this design should adopt rather than rebuild:

| Need | Existing convention | Status |
|---|---|---|
| Tab needs attention | `.inbox-badge` — amber pulse dot on a tab button (`css:540-566`) | **Built, never used** |
| Secondary hero button | `.hero-buttons-group` column slot (`css:302-306`) | **Built, empty** |
| Status pulse in a card | `.fcc-invite__dot` (`css:3896-3900`) | Live — the FCC's only pulse |
| New-item highlight | `.fcc-newlean-badge` / `.fcc-newlean-row` (`css:3963-3989`) | Live |
| Disabled action | `.is-dead` + `aria-disabled` + neutered click | Codified |
| Copy + small CTA | `.fcc-recruiting-footnote` (`css:391-457`) | Live |
| Empty state | `createEmptyHomeState()` → `.fcc-home-empty` | Live |
| Blocking confirm | `.gob-modal-overlay` / `.gob-modal-box` | Live |
| Lean ladder, phase strip, pool anchor | `RecruitingSpine` | Live, reused across 4 surfaces |
| Lock badge | Lean ladder renders it; backend never sets it (`recruiting-spine.js:68-69`) | **Socket built, no plug** |

Two `prefers-reduced-motion` blocks already exist (`css:1917`, `3938`) — any new pulse or
glow must respect it.

---

## 8. Resolved, and what's left

### Resolved in review

**The wire gets a filtered news view.** `season_news` carries it, with a
`type: "recruiting_*"` filter so personal recruiting events can be read on their own —
the pattern OOTP uses. Riding the existing store means no parallel system.

**Week 1 at zero knowledge is intentional.** 450 rows of stars, sortable by ★, position,
height and region. It needs a treatment that reads as *a class waiting to be scouted*
rather than a broken table — an inviting empty-ish state, not a wall of dashes — but the
emptiness itself is the point. It's what makes the first scouting assignment feel like it
matters.

**Nothing further is revealed until the following season's Training Camp.** Not at Signing
Day, not at week 36 — including recruits who signed with you. You sign a kid you only got to
L1 on, and you don't learn his ceiling until you've coached him through camp.

This is better than the season-end reveal I proposed, for three reasons. It's realistic —
you learn what a player is by working with him. It preserves the fog across the season
boundary instead of dumping the truth and making a season of scouting feel retroactively
pointless. And it hands a genuine payoff to Training Camp, which is being designed as a
bigger moment: **camp becomes the week your recruiting class stops being a guess.** The
knowledge state carries into the next season untouched, so a well-scouted signing arrives
already understood while a gamble stays a gamble until camp resolves it.

**No mobile.** The FCC is desktop-only in practice; the Hub and Scout Desk inherit that.

**Coach's Office two-column span** — technically trivial, but it needs a card retired to
keep the grid even. Proposal and layout in §2.5; Standings is the suggested donor.

**Scouting is weeks 1–19 only.** No film review in the tournament weeks. 27–34 stays clear so the
postseason owns the player's attention; recruiting there is watched, not played. See §4.1.

**The scout owns visit conversion in weeks 20–26.** Not narrative — he's the reason a hosted
recruit moves toward you, and the existing probability gate
(`franchise_routes.py:11387-11394`) is where future scout personalities will multiply in.

**Days don't bank, but trips in progress carry.** Standing orders are a ranked queue plus a
weekly Film/Live mix, so the scout always fills the week from the queue. Idle days therefore
mean *the queue is empty* — which is what makes the idle prompt a real signal rather than a
nag. Full spec in §5.6 of the system design.

**The Coach's Office Recruiting card spans two columns; the Standings card is retired.**
Layout and implementation notes in §2.5.

### Still open

1. **Film cost confirmation.** Capacity is 95 scout-days with Film specced at 1 day, yielding
   ~47–70 recruits filmed and ~9–19 full reports per season. If play proves too thin, the
   lever is Film cost down to ~0.75 day — not more days, and not reopening the tournament
   weeks.
2. **Queue-empty behaviour when auto-refill is off.** The scout idles and the FCC prompts.
   Should the desk also suggest targets inline, or is the prompt enough?
