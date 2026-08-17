# Recruiting UX — Build Plan

GOB · 2026-08-16 · this is the project that ships

---

## 1. Scope

**Mechanics are unchanged.** Weeks 1–19 stay passive with team performance driving lean
movement, weeks 20–26 stay the invite window, week 35 stays Signing Day. No fog of war, no
scout, no motivation archetypes, no legacy locks, no reweighted rolls.

This is a UX project with three goals:

1. **Get recruiting out of Run Training** and make it a first-class FCC presence all season.
2. **Report the mechanic that already exists** — lean movement in both directions, not just
   gains.
3. **Rework the three screens** — Recruits, Invites, Signing Day.

The long-term direction lives in `recruiting/overhaul-design.md` and stays there. Nothing in
this plan blocks it, and several pieces here (the FCC model, the event log, the letter-grade
unification) are the foundation it would build on.

## 2. Three fixes that are bugs, not design

Called out separately because they need no design discussion — they're wrong today.

**Signing Day pre-spends your budget.** `recruiting-hub.js:343-350` allocates 12/9/6 points
— 27 of 50 — to your top three leaners on load, and attaches **binding playing-time promises
to two of them**, unmarked, before you touch anything. Delete `seedAlloc()` entirely. If a
helper is wanted later it must be a button the player presses.

**Weeks 27–34 report nothing.** `_append_franchise_week_news` returns early for `week > 26`.
Lean movement happens; no news is generated. One early-return to lift.

**The scholarship toggle does nothing.** It's normalized false/dormant and affects neither
score nor roster state. Remove it from the UI.

---

## 3. Phase 0 — Ground clearing

No user-visible change. Everything downstream gets cheaper.

**Repoint.** `franchise-command-center.js:4073` still builds `/recruiting-orders.html` for
the week-35 CTA. Point it at `/recruiting.html`, matching what `updateRecruitingButton()`
already does at `:3961`.

**Delete.** 11 files, ~5,173 lines, ~188 KB — verified by full reference sweep including
config, deploy files, backend routes, tests and both Playwright specs. Order matters:

1. `recruiting.js`, `recruiting-invites.js`, `recruiting-orders.js`, `recruiting-results.js`
2. `recruiting-invites.html`, `recruiting-results.html` (zero live inbound links)
3. `recruiting-orders.html` — only after the repoint above is verified
4. `recruiting.css`, `recruiting-spine-data.js`, `recruiting-spine-gallery.html`,
   `Recruiting Orders v2.html`

**Keep:** `recruiting-common.js` (loaded by the live hub at `recruiting.html:45`) and
`recruiting-lean-ladder.css` (loaded by `training-report.html` and
`franchise-command-center.html`).

**Caveat:** `recruiting.css`'s only real consumer is `awards.html`, which is itself orphaned
— the FCC Awards button points at `leaders.html` (`js:1599`). Confirm nothing external links
to `awards.html`, then delete both together.

**Adopt letter grades.** Retire recruiting's 4-band raw-colour RT scale in favour of the
Styleguide's 9-tier letter grades, which are already mandated as *"identical for active
players and recruits."* `rt_current_potential()` already emits the `"C/B"` pair format.

**Correct the manifest.** `recruiting_file_manifest.md` §1 lists four live screens; only the
Hub is reachable — the other three redirect from `<head>`. §7's dead list needs the three
stubs, their JS, and `recruiting.css` added. §6's "Prompt 0 shipped" understates it; Prompts
0–4 shipped.

**Also worth clearing while in the FCC:** `bindResourcesLinks()` (`js:1562-1601`) assigns
hrefs to eight ids that exist in no HTML in the repo, and re-runs on every tab switch.
`updatePlaybooksButtonState()` fires a live `GET /api/playbooks` on every FCC init purely to
style an element that isn't in the DOM.

---

## 4. Phase 1 — The Wire

The passive weeks already generate lean movement. The UI reports only the good half.

### 4.1 The event log

At both lean mutation sites the code holds `old_lean` and `new_lean` in the same scope and
discards everything except one additions-only boolean. A pure helper recovers the rest with
no extra DB reads:

```
diff_lean(old, new) -> [ gained_you | dropped_you | moved_up | moved_down
                       | rival_took_your_top | displaced ]
```

Persist as `franchise_doc["recruiting_lean_events"][week]`, matching the existing week-keyed
pattern used by `recruiting_results`. **Filter at write time to user-relevant events** —
user is actor, displaced party, or already on that recruit's ladder — which holds a season at
~150–300 events, ~60 KB. Unfiltered league-wide would be ~3,000 and belongs in its own
collection.

### 4.2 Two things to know

`fcc_pending_new_lean_recruit_ids` **cannot represent a drop.** Readers re-intersect it
against the recruit's *current* lean list, so a recruit who dropped you is filtered out by
construction. The event log supersedes it — don't try to extend it.

`season_news` already exists and already carries a `_build_recruiting_leans_story` builder
feeding the FCC Coach's Office and `/franchise/news`. **We're extending a working system**,
not inventing one. Add a `type: "recruiting_*"` filter so personal recruiting events can be
read on their own — the OOTP pattern.

### 4.3 Copy

Events render as sentences with causes, not as data:

> `DeAndre Pope dropped you — Fairview moved to #1`
> `Marcus Bell moved you to #1 — after the Kettle Falls win`
> `Andre Whitlock added you at #3`

Drops must render as visibly as gains. `.fcc-newlean-badge` / `.fcc-newlean-row`
(`css:3963-3989`) already exist for gains; a red/amber counterpart completes the set.
**The losses are what people will actually read.**

---

## 5. Phase 2 — FCC promotion

### 5.1 Out of Run Training, without risking missed weeks

The original decoupling was proposed, built, and reversed because Run Training was the only
guaranteed weekly trigger. That reasoning was sound. The resolution:

- **The invite still fires on week advance**, using whatever board exists — exactly as today.
  No week can be silently lost.
- **`training.js:1453` stops routing to recruiting.** Training ends at training.
- **Recruiting gets its own presence in the FCC** (below), so the player has a reason and a
  route to open it every week without being forced through another screen.

So recruiting becomes prominent and independent without becoming a chore, and the failure
mode the reversal protected against can't occur.

### 5.2 Three levels, driven by state

| Level | Fires when | Element |
|---|---|---|
| **Ambient** | Nothing needs the player | Coach's Office **Recruiting card** + News card |
| **Prompted** | Board unsent this week, or unseen wire events | **Second hero button** + **`.inbox-badge`** on the tab |
| **Gated** | Week 20 with no board · Week 35 | **`#play-now` itself** |

This maps onto the Styleguide's colour law for free: **green gates, orange doesn't.**

Two pieces of this are already built and unused:

- **`.hero-buttons-group`** is a flex *column* containing exactly one child, `#play-now`
  (`html:59-63`, `css:302-306`). It was built as a group and the second slot has never been
  occupied. The secondary button goes there — no layout surgery.
- **`.inbox-badge`** (`css:540-566`) is an 8px amber pulse dot positioned on a tab button.
  Grep across all of `FrontEnd/` finds **zero** places that add the class.

### 5.3 The secondary button

Carries a count, not a noun:

> **`Recruiting · 2 moved · 1 dropped you`**

| Weeks | Condition | Label | Treatment |
|---|---|---|---|
| 1–19, 27–34 | Unseen wire events | `Recruiting · N moved · M dropped you` | Amber, no pulse |
| 1–19, 27–34 | Nothing new | *hidden* | — |
| 20–26 | Board unsent, events pending | `Recruiting · N moved · M dropped you` | Amber, `.fcc-invite__dot` pulse |
| 20–26 | Board unsent, no events | `Recruiting · Invite Wk N of 7` | Amber, no pulse |
| 20–26 | Board sent this week | `Recruiting · Board sent` | Amber, `.is-dead` |

Hover shows the top of the board with any change this week, reusing the `.fcc-invite` card
treatment (`css:3869-3938`).

### 5.4 Week-20 gate

If week 20 arrives with no saved board, `#play-now` becomes `Build Invite Board`. It sits in
the `updatePlayButton` branch order immediately after `cut_required` — the same slot pattern
as the existing "Assign Practice Squad" gate, which already proves the mechanism.

### 5.5 Coach's Office card — becomes the Wire

The 5-row lean table it shows today is a weaker version of what the Recruits tab displays.
The card's job should be **news, not inventory**: gains and drops, newest first, with a
one-line status beneath (invites sent, points remaining, whatever the phase calls for).

**Span it two columns and retire the Standings card.** Standings duplicates the Standings tab
*and* `/standings.html` — the most duplicated card on the surface. That resolves the grid
arithmetic (8 cards where one spans 2 = 9 column-units, which doesn't divide into rows of 4):

```
Row 1:  Next Game  │ Locker Room │ RECRUITING (span 2)
Row 2:  Rankings   │ Last Game   │ Player Scoring │ News
```

7 cards, 8 column-units, two clean rows. `grid-column: span 2` is a one-line addition;
removing Standings means deleting its `<section>` (`html:84-87`) and
`renderHomeStandingsCard()` (`js:973-1009`). **Check first** whether `#standings-full-link`
(`html:130-132`) is scoped to the card or the tab. At double width, revisit the 126px
`.fcc-home-list-scroll` cap for this card.

### 5.6 Recruits tab → Recruiting

Same slot, no tab-bar surgery, new contents: the season's wire feed, a board summary, and a
deep link into the Hub. Carries `.inbox-badge` when something needs attention.

---

## 6. Phase 3 — The three screens

All three are phase bodies of the existing Hub (`recruiting.html`). The spine — phase strip,
lean ladder, pool anchor, story strip — stays; it's the genuinely good part of the last
redesign.

### 6.1 Recruits (the pool)

**Today:** goes `condensed` during Invite and Signing phases (`recruiting-spine.css:260`),
hiding all 12 attribute columns — so attributes disappear exactly when you're comparing
recruits.

**Changes:**

- Attributes stay visible in all phases. Kill the `.pool.condensed` hack.
- **Filters carry over and expand:** Region (user's own listed first) and Year, as today.
- **Headshots.** `getRecruitImageUrl(image_id, {size:'card'})` already exists at
  `api-config.js:306`, `image_id` already ships on the recruit record, and there's a
  lazy-paint retry path (`ensureRecruitImage` → retry → generic). Portraits already render in
  box score, player detail, POTG and the scouting report — the recruiting pool is the one
  place they were never added.
- RT cell shows the current/potential pair in letter grades, with a `Current / Potential`
  tooltip matching the app convention.
- Names link to player detail.
- **Column order and alignment.** `Recruit · Pos · RT · Yr · Ht · Rgn · Attributes · Lean ·
  Watch`. Name/Pos/RT lead because they answer "is he worth watching" fastest and it puts the
  sorted column beside the name; Lean and Watch pair at the right edge because both are about
  *you and him* rather than about him. Name column is **capped, not flexed** — flexing leaves
  dead space between the name and Pos. Every header is **centered over its column**, and
  **Attributes is centered across the full 12-chip block**.
- **Filters: dimensions and views are visually separated.** Region stays a dropdown (9
  options, rarely changed); **Position and Year are segmented controls** — few options,
  switched constantly while scanning, and a dropdown costs a click every time. Saved views
  (Watchlist · Leans to me · Unranked) sit on their own labelled row.

#### The watchlist — one small addition

**This is the only new state in the plan.** A saved list of recruit IDs per franchise,
persisting all season, toggled by a star in the pool.

It exists because of a real gap: with 450 recruits and 19 weeks of watching leans move, there
is currently **no way to remember who you liked**. By week 20 you rebuild the board from
scratch against a list you last looked at in week 3.

- Storage: one array on the franchise doc (`recruiting_watchlist`), plus a toggle endpoint.
- **It seeds the week-20 invite board** — that's what makes it a UX fix rather than a feature.
- Also a filter view, so 450 collapses to your shortlist in one click.
- It gives the passive weeks something to *do* that isn't a mechanic — building a shortlist as
  leans move. That was part of what the shelved Scout was covering.

### 6.2 Invites (weeks 20–26)

**Today:** board persists across all seven weeks, names render as plain text
(`recruiting-hub.js:232`), and nothing tells you why you'd re-rank.

**Changes:**

- **A "what changed" panel** driven by the Phase-1 event log, annotated with the board rank
  each event hits: *"DeAndre Pope dropped you — board rank 3."* This is the re-rank trigger,
  and it's the single highest-value addition on the screen.
- Dock and board rows link to player detail; headshots in both.
- **Roster needs** visible — position counts and spots remaining, so board order can be read
  against actual need.
- Full lean ladder on each row (the shipped spine component).
- Drag-reorder and the dock stay as designed.

### 6.3 Signing Day (week 35)

**Today:** 27 points and two binding promises pre-spent; a placeholder odds bar; roster
capacity invisible; a dormant scholarship toggle; a blind 950 ms redirect after submit.

**Changes:**

- **`seedAlloc()` deleted.** Loads at 0 of 50, no promises.
- **Placeholder odds replaced with real competition.** The current bar is
  `base(standing) + points × 2.2 + (promise ? 18 : 0)` — admitted placeholder, blind to
  rivals. CPU week-35 boards are already seeded server-side on the user's first save, so the
  field **is** knowable: show *"4 programs funding"* and your lean standing with its
  multiplier (`#1 ×5`), which also teaches the mechanic the tutorial has always claimed
  matters. **This is the one new backend surface in the plan** — a count per recruit on the
  week-35 payload.
- **Roster capacity surfaced.** `available_roster_spots` and `available_scholarships` are
  already in the hub payload and simply aren't rendered, while funding stays uncapped against
  a hard 15-man ceiling.
- **Scholarship toggle removed.**
- Year and archetype back on the signing row (`recruiting-hub.js:362-384`).
- **A submit summary** replacing the 950 ms blind redirect (`:490-492`) — what you committed,
  before you leave.

### 6.4 Results (week 36) — light touch

Not one of the three, but it's the payoff and it currently strips a recruit you tracked for
35 weeks down to Pos/Region/RT (`recruiting-hub.js:507-550`). Minimum: name, headshot,
position, RT pair, where he signed, and **why** — points, lean standing, field size. All
available from the resolution already.

### 6.5 Defects to fix along the way

| Defect | Where |
|---|---|
| Weekly panel dismiss button bound but never rendered | handler `recruiting-hub.js:624`; no `#weekly-dismiss` emitted |
| Dock slot and signing row render names as plain text | `:232`, `:371` |
| Year and archetype missing from signing row | `:362-384` |
| Post-submit blind redirect at 950 ms | `:490-492` |
| Pool hides attributes in Invite/Signing phases | `recruiting-spine.css:260` |
| Hub skips `.fcc-brand-page-shell` though Styleguide lists it Type 1 | conform or register the exception |

---

## 7. Backend work, in total

Deliberately small:

1. `diff_lean()` helper + `recruiting_lean_events` week-keyed store — ~15 lines plus a write.
2. Lift the `week > 26` early return in `_append_franchise_week_news`.
3. A `recruiting_*` story type/filter on `season_news`.
4. Competition count per recruit on the week-35 payload (§6.3).
5. `recruiting_watchlist` array on the franchise doc + a toggle endpoint (§6.1).
6. Deprecate `fcc_pending_new_lean_recruit_ids` once the event log lands.

Everything else is frontend.

---

## 8. Sequence

| Phase | Contents | Ships value alone |
|---|---|---|
| **0** | Cleanup, repoint, letter grades, manifest | No user change, but unblocks everything |
| **1** | The Wire — event log, drops, week>26 gate | Yes — 27 dead weeks become legible |
| **2** | FCC promotion, out of Run Training | Yes — recruiting stops being buried |
| **3a** | Signing Day (incl. the three bug fixes) | Yes — removes the most misleading screen |
| **3b** | Invites | Yes |
| **3c** | Recruits pool | Yes |
| **4** | Results light touch | Yes |

Signing Day is sequenced first among the screens because it carries all three bugs from §1
and is self-contained.

---

## 9. Mockups

Five exist in `_documentation_master/projects/Recruiting_Hub_Redesign/mockups/`. Against this
scope:

| Mockup | Status |
|---|---|
| `2-fcc-integration.html` | **Use as-is.** Nothing in it depends on shelved mechanics. |
| `3-invite-board.html` | **Use, minus** the Read column (motivation) and the lock badge. The wire panel, roster needs, headshots and dock all hold. |
| `4-signing-day.html` | **Use, minus** motivation-derived notes. Standing/Field/Points/Promise structure holds. |
| `5-results.html` | **Use, minus** the Report/Bloom/Motivation stats. |
| `1-scout-desk.html` | **Shelved** with the mechanic. Keep for the future project. |

The Invite Board and Signing Day mockups want a revision pass to strip the shelved columns —
which will also make them measurably less dense, since those columns were the density.

---

## 10. Deferred, and where it lives

Fog of war and knowledge levels · the Scout and the day budget · the ★ media ranking with
structural bias · motivation archetypes · legacy locks · fit-weighted lean movement ·
prestige's new jobs · live-auction Signing Day.

All specified in `recruiting/overhaul-design.md`. Two notes for whenever that project starts:

- **The event log from Phase 1 is its foundation.** Fit-weighted movement needs somewhere to
  report from, and this is it.
- **Nothing here forecloses it.** The letter-grade unification, the FCC model, and the
  knowledge-agnostic RT cell were all designed with the fogged version in mind.
