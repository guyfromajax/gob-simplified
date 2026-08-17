# Recruiting Overhaul — Design v2

> **SCOPE NOTE — added 2026-08-16.** This document is the **long-term direction**, not the
> project currently being built. The active project is `recruiting/ux-build-plan.md`, which
> keeps today's mechanics unchanged and reworks the UX: recruiting out of Run Training and
> into the FCC, the lean-event wire, and the three screens.
>
> **Deferred from this doc:** fog of war and knowledge levels (§4), the Scout (§5), motivation
> archetypes and legacy locks (§6), fit-weighted lean movement (§7.4), prestige's new jobs (§8),
> live-auction Signing Day (§15).
>
> **Already moved into the build plan:** the Wire and event log (§7), the FCC gated/prompted/
> ambient model (§10), letter-grade RT (§12), cleanup (§13), and the Signing Day fixes (§9.2).
> Nothing in the build plan forecloses anything below — the event log is this design's
> foundation.

GOB · revised 2026-08-16 following design review

**Scope:** mechanics and UX · exposure-based fog of war · passive weeks stay passive but
become informative · recruiting promoted to a first-class FCC surface · dead code removed.

**Supersedes v1.** Changes from the first pass: five knowledge tiers collapsed to three;
fog reframed from *observability* to *exposure*; recruit-quality-to-national-rank coupling
dropped in favour of motivation archetypes; scout day-budget added as the passive-week
engine; recruiting pulled out of Run Training and into the FCC action model.

---

## 1. The problem

Recruiting was designed to ask for a decision every week from 20 to 26 — read the lean
movement, see who's slipping, protect who's committed, redirect the invite. That intent
never reached the player. The board persists across all seven weeks and **no new
information ever arrives to invalidate it**, so seven decisions collapse into one. Nothing
in the code forces set-and-forget; the UI simply never gives a reason to revisit.

Signing Day has the opposite problem: it's a real decision that the game makes *for* you.
`seedAlloc()` pre-allocates 27 of 50 points and two binding playing-time promises before
the player touches anything, so the whole thing can be submitted in one click.

Underneath both sits the root cause: **perfect information.** Every recruit's true
attributes, true ratings, and true projected ceiling are visible to every program from
week 1. With the answer key on the table, recruiting is a sort, not a judgment — and no
amount of UI work fixes a decision that has an obviously correct answer.

## 2. Design pillars

1. **Evaluation is a skill.** The player's edge comes from judging incomplete information
   better than rivals — and from knowing where the public consensus is wrong.
2. **The passive weeks are for reading and planning, not clicking.** Rhythm stays.
   Silence goes.
3. **Every surfaced number is honest.** No placeholder probabilities dressed as fact.
4. **Depth without homework.** Everything added must run itself acceptably for a player
   who never opens it.
5. **Build on the spine.** Lean ladder, phase strip, story strip, pool anchor all stay.

---

## 3. Verified code baseline

Established by direct trace, not inference. Recorded here because the design depends on it.

**Projected potential is deterministic and fully exposed.** `BackEnd/utils/rt_projection.py`:

```
potential = JH_ANCHOR_BY_TIER[entry_tier] × 2.0 × potential_factor
            ratcheted: max(that, current_RT)
```

`JH_ANCHOR_BY_TIER` = Poor 20 · BelowAverage 25 · Average 30 · Good 35 · Great 40 ·
Elite 50. `POTENTIAL_FACTOR_BAND = 0.15`, so `potential_factor` is `uniform(0.85, 1.15)`,
drawn once and career-static.

So a displayed potential is **not an estimate** — it's precise arithmetic on that
recruit's own generation parameters, identical for every program, with no noise anywhere.
But `rt_projection.py`'s docstring notes the ×2.0 is calibrated to a **median-peak
career**; actual outcomes vary via the `development` profile (`peak_count` 0–3 CH-driven,
`peak_rungs`, `family_timing`, `ch_seed`) generated in `player_development.py:278-299`.

**It is therefore a precise median with real hidden variance, presented as a fact.** That
is the fog-of-war opening, and it's better than a noisy number because the uncertainty is
already modelled.

**The potential grade leaks `entry_tier`.** Resolved through `rt_letter_grade`:

| Tier | Potential RT range | Letter range |
|---|---|---|
| Poor | 34 – 46 | D – C |
| BelowAverage | 42.5 – 57.5 | C – C+ |
| Average | 51 – 69 | C+ – B |
| Good | 59.5 – 80.5 | C+ – A |
| Great | 68 – 92 | B – A+ |
| Elite | 85 – 115 | A – A++ |

The bands barely overlap. Showing the potential grade *is* showing the tier. Hiding
`entry_tier` while displaying potential is not a coherent position — they are one lever.

**Hidden information is already GOB policy.** `franchise_routes.py:16693` carries the rule
*"never leak CH"* — the RT-delta flag is deliberately built so `peak_count` stays hidden.
Fog of war extends an existing principle rather than introducing a new one.

**Other confirmed facts.** No hometown, legacy, loyalty, or lock concept exists anywhere in
the backend (grep returns empty) — but `recruiting-spine.js:68-69` notes the lean ladder
*can already render a lock badge* and never receives one. Prestige enters recruiting at
exactly one point, `_select_team_by_prestige_draw` at `franchise_routes.py:11583`, and is
absent from the week-35 signing formula. Passive-week lean movement selects via
`random.choice(pool)` over in-region recruits in an RT band — no prestige, no rival
awareness, no recruit preference.

---

## 4. The information model

### 4.1 The principle

> **You don't know a recruit because you haven't seen him — not because he's unknowable.**

This is the load-bearing idea. Current ability is observable: you can watch a kid play and
see what he is. What you can't do is watch 450 high schoolers. The fog models *attention*,
not the limits of observation — which is why it never feels like the game lying to you,
and why one cheap action always lifts it.

### 4.2 Three knowledge tiers

| L | Player-facing name | What the player sees | RT cell reads |
|---|---|---|---|
| **0** | **Unfilmed** | Name, position, height, weight, year, home region, **★ media ranking**. Nothing evaluative. | `★★★☆☆` |
| **1** | **Filmed** (Film Report) | **True current RT** and true current attributes. Everything observable today. | `B` |
| **2** | **Full** (Full Report) | **Exact potential RT.** Bloom timing (early / standard / late). **Motivation archetype.** Legacy ties revealed. | `B/A` |

**`L0` / `L1` / `L2` are internal spec shorthand and must never appear in the UI.** The
player-facing vocabulary is the report state — *Unfilmed · Filmed · Full* — which is
self-explanatory because it names what the scout has produced. In practice the UI needs no
state badge at all: the RT cell already carries it (stars = no film, one grade = filmed, a
pair = full report), so the words appear only on the pool's filter chips, which is where a
player absorbs them without being taught.

The split is **present versus future**:

- **What he is now** — `attributes` → `position_ratings` → RT. Revealed whole at L1.
- **What he becomes** — `entry_tier × potential_factor`. Revealed whole at L2.
- **How he gets there, and why he'll choose** — `development` profile plus motivation.
  L2 only, governed by the existing "never leak CH" principle.

The RT cell alone tells you the knowledge level at a glance, and the L2 form is exactly the
`"C/B"` current/potential pair that `rt_current_potential()` already emits — no new display
primitive required.

### 4.2.1 There are no estimates anywhere — and that removes a whole class of problem

Every value the player sees is **either the truth or nothing.** No bands, no ranges, no
noisy point estimates. Potential is binary: hidden, or exact.

This is a significant simplification over an estimate-based model, and it deletes several
hard problems outright:

- **No band-width tuning.** Nothing to calibrate.
- **No nesting constraint.** Knowledge can't contradict itself, because a revealed value is
  the real one.
- **No per-team noise, therefore nothing to triangulate.** An estimate-based design would
  need noise seeded deterministically per `(team_id, recruit_id, level)` or players would
  refresh the page to resample and average out the true value. With reveal-gates there is no
  per-team value to resample. The exploit cannot exist.

The only inaccuracy in the whole system is the ★ service ranking (§4.3) — and that is
**public, computed once per recruit, and identical for every program**, so it is not a
per-team estimate either.

Knowledge is stored per-team as `scouting_knowledge`, and it is a pure gate: level → which
fields are permitted through the API boundary. That's it.

A useful side effect: at L0 there is nothing to render, so the pool row is naturally
compact. **The condensed-pool problem that forced attributes to be hidden during Invite
and Signing phases stops existing.**

### 4.3 The ★ service ranking, and why it should lie

L0 must not be blank, or the week-1 recruit list is 450 anonymous names. A **public
recruiting-service ranking** — stars, same for every program, visible from day one —
provides triage material and matches how recruiting actually works.

The important design choice is that **the service is wrong in structured, learnable ways.**

If the error is random noise, scouting is variance reduction and nothing more. If the error
is *biased*, scouting becomes finding where the public consensus is wrong — which is the
Moneyball fantasy, and the thing deep-sim players evangelise about.

The service should systematically:

- **Underrate late bloomers.** A service watching a kid now sees someone who isn't good
  yet. `family_timing = late` pushes stars down.
- **Overrate early bloomers.** Great at 16, won't grow. Stars too high.
- **Overrate physical outliers.** Tall is shiny; a 6'11" project with mediocre attributes
  gets stars he hasn't earned.
- **Be broadly right about the obvious elite.** The top 10–15 of a class are correctly
  identified. Nobody is hiding at the very top.

This costs almost nothing — the bias derives from `development.family_timing` and `height`,
both already generated. And it makes `family_timing` do double duty: the L2 reward *and*
the source of market inefficiency.

It also lets a player build genuine expertise — *"3★ juniors already at 6'8" are traps; 2★
sophomores in my region are where I find guys."* A strategy someone posts on a forum is the
signal this is working.

**Implementation note:** the error is computed **once per recruit**, not per team. Every
program sees identical stars. The player's advantage is never "I see different numbers,"
it's "I looked past the numbers everyone can see" — which is also what makes it
un-exploitable, since there's nothing team-specific to re-roll.

### 4.4 Tuning targets

Set by outcomes, not by sigma:

- **~15–20% of 5★s bust.** Often enough to sting and be memorable; rare enough that stars
  still mean something.
- **~8–12 genuine steals per 450-recruit class** — 3★ or below whose true value is top-40.
  Roughly 2%, so a diligent scout finds one or two a season.

That second number is the whole balance question: **does a season of scouting return more
than it costs?** One genuine steal a year justifies the system. One every three years and
players switch on standing orders and never look again.

**Suggested star distribution**, roughly matching real services: 5★ top ~10 · 4★ next ~40 ·
3★ next ~130 · 2★ next ~180 · remainder unranked.

### 4.5 The fog does not lift at signing — it lifts at Training Camp

**Nothing further is revealed at Signing Day or at week 36, including recruits who signed
with you.** A recruit you only reached L1 on arrives on your roster still at L1. His ceiling
stays hidden until the following season's **Training Camp** completes.

Three reasons this is the right boundary:

- **It's true to the fiction.** You learn what a player really is by coaching him, not by
  signing him.
- **It protects the season's work.** A truth-dump at week 36 would retroactively flatten a
  season of scouting into "you found out a few weeks early." Carrying the fog across the
  boundary means the scouting you did *keeps* paying.
- **It gives Training Camp a real payoff.** Camp becomes the week your recruiting class
  stops being a guess — which is a substantial moment to hand to a system already being
  designed as one.

Practically: `scouting_knowledge` persists across the season rollover for signed players,
and camp completion promotes them to full visibility. A well-scouted signing arrives already
understood; a gamble stays a gamble until camp resolves it. **Recruits who signed elsewhere
never reveal** — they become other teams' players and follow whatever opponent-visibility
rules already apply.

---

## 5. The Scout — the passive-week engine

### 5.1 The budget

One scout has **5 days per week**. Days are a weekly pool the player spends however they
like — *not* a day-by-day calendar. A scheduler is a puzzle; a budget is a decision.

| Action | Produces | Cost |
|---|---|---|
| **Film** — review tape | **Film Report** (L0 → L1) | 1 day |
| **Live** — attend a game, in region | **Full Report** (L1 → L2) | 1 travel + game + 1 report ≈ 2 days |
| **Live** — attend a game, out of region | **Full Report** (L1 → L2) | 2 travel + game + 1 report ≈ 3.5 days |

**Terminology.** *Film* and *Live* — both real scouting language, and deliberately **not**
"Visit," which is reserved exclusively for the week 20–26 recruit visits to your campus.

**Live is locked until Film is complete.** You cannot send a scout to watch a recruit you
have never reviewed on tape. This is realistic, and mechanically it does three things:
it removes a trap (spending 2–3.5 days to reach a level film gives you for 1), it makes the
cost of a Full Report a single fixed number, and it gives the loop its real shape —
**film is the funnel, live is the follow-up.**

**Both actions are atomic.** One film day yields a Film Report outright; there is no partial
progress to accumulate. Progressive reveal was considered and rejected: with only 95 days in
the season a percentage model finishes almost nobody, and it would mean tracking partial
state across 450 recruits for no gain in legibility.

So the full economy is:

| Outcome | In region | Out of region |
|---|---|---|
| Film Report | 1 day | 1 day |
| Full Report | **3 days** | **4.5 days** |

**All scouting happens in weeks 1–19.** Nothing after.

### 5.2 Film and Live reveal different things

**Film gets a recruit to a Film Report and cannot take him past it. A Live evaluation is the
only route to a Full Report — and it requires the Film Report first.**

This is the structural change that makes the mechanic work. If film were simply a slower
live visit, it would be strictly dominated and would exist only as filler. Making them
reveal different classes of information means both are necessary, the travel-cost
asymmetry has an obvious justification, and the weekly question becomes genuinely
interesting: **breadth or depth?**

The fiction holds too. Film tells you what a player *is*. It doesn't tell you his ceiling,
his work ethic, what his coach thinks, or why he'll pick a school. Those require being in
the gym.

### 5.3 Scout count comes from prestige, at season start

**Prestige sets scout count when the season begins, locked for the season.** Low prestige
starts at 1; blue-bloods run 2–3.

Deliberately *not* dynamic in-season, for three reasons:

1. **Prestige is already designed as the slow axis** — `Rank_Prestige_System.md` calls it
   "persistent program equity." National rank is the volatile in-season axis. Scouts are
   staff; you don't hire and fire them in March.
2. **Scouting is a planning activity.** A three-week out-of-region campaign that collapses
   in week 12 because you lost a scout isn't tension, it's arbitrariness.
3. **In-season form already pays off in recruiting** via lean movement. Adding scouts on
   top double-dips the same input, and asymmetrically: a struggling team would lose leans
   *and* information, kicked twice in the system where they most need a route back.

*Optional later knob:* if season-start-only feels inert in play, flex **scout-days** rather
than scout-count — 5 base, +1 while ranked top-25. You never lose the scout, just some
slack, so no planned campaign ever breaks. Build the locked version first.

### 5.4 One window, one deadline

| Weeks | Scout | What's reachable |
|---|---|---|
| **1–19** | Film and Live | Film Reports and Full Reports |
| **20–26** | Hosting recruit visits (§5.7) — unavailable for scouting | — |
| **27–34** | Off. Recruits' seasons are over, and the tournament owns the player's attention. | — |

**Everything you know on Signing Day, you knew by the end of week 19.** No late correction,
no last-minute due diligence, no discovering a legacy lock in week 34.

This is the highest-value constraint in the design and it costs nothing to build. Weeks 1–19
become the highest-stakes stretch in the recruiting calendar — a depleting resource against
a fixed, final deadline — and weeks 27–34 stay clear for the tournament. That's deliberate:
the postseason should own the player's attention completely, and recruiting during it is a
thing you *watch*, not a thing you *do*. Leans keep moving on judgments you can no longer
revise, and the wire keeps reporting them.

### 5.5 Budget math

One scout, one window: **19 weeks × 5 days = 95 scout-days.** 450 recruits, ~56 per region.

With Film at 1 day, an in-region Live at 2 and out-of-region at ~3.5, a season yields:

| Strategy | Evaluated (L1+) | Known (L2) | Region coverage |
|---|---|---|---|
| **Breadth** — mostly film | ~70 (16% of class) | ~9 | full 56 |
| **Balanced** | ~57 (13%) | ~15 | full 56 |
| **Depth** — live-heavy | ~47 (10%) | ~19 | 47 of 56 |

Three things fall out of this, and all three are good:

**The board is 20 slots and deep knowledge tops out around 20.** Even a depth strategy barely
gets one board's worth of L2 — so you will always be funding at least a few recruits you
don't fully understand. That's the tension the whole system exists to create.

**You cannot both cover your region and go deep.** Breadth gets you all 56 locals filmed but
only ~9 full reports; depth gets you ~19 full but leaves gaps in your own backyard. A real
strategic fork, not a dominant line.

**Roughly 85–90% of the class stays a star rating and a guess.** With ~9 genuine steals per
class (§4.4), finding one or two means targeting where the service is *biased* rather than
sampling broadly — which is exactly the skill the design wants to reward.

**Calibration note.** Removing the dead-period window cut capacity from ~135 days to 95, and
film moving from ½ day to 1 day compounds it — theoretical maximum evaluations fell from
~270 to ~95. That's the right order of magnitude, but the two changes stack, so if play
proves too thin the first lever is **film cost back to ~0.75 day** (yields ~58–92 filmed),
not more days and not reopening the dead period.

### 5.6 Standing orders — a ranked queue and a weekly mix

Some players will love the weekly assignment; others will find it homework. A binary on/off
forces a choice between two products. A standing order is one product with a good default,
and it has two parts:

**a. The ranked queue.** An ordered list of targets, each tagged with an intended action —
*Film* or *Live*. The player builds it at the start of the season and edits it whenever.
The scout simply works down it.

**b. The weekly mix.** How the week's 5 days divide when the queue offers both kinds of
work — e.g. *4 film days : 1 live day*, or a simpler **film-heavy / balanced /
live-heavy** control. Set once at season start.

If the player issues no orders in a given week, **the scout keeps executing against the
queue and the mix.** No week is ever wasted through inattention.

**Days do not bank — but trips in progress carry.** An unused day is gone. A multi-day trip
already underway is *not* an unused day; a 3.5-day out-of-region trip spanning a week
boundary simply continues, which is also how travel actually works. The distinction matters
because it means the two rules don't fight: no hoarding, no penalising the expensive action
for costing more than one week.

**The consequence is that days only go idle if the queue empties.** With a populated queue
and a mix set, the scout always fills the week. So an idle day is a *signal* — it means the
player has run out of targets — and that is precisely when the FCC should prompt. This is
what makes the idle-days prompt meaningful rather than nagging.

**Optional auto-refill.** When the queue runs low, top it up by rule — *my region · my
position needs · top of the class · recruits leaning to me*. A player who wants zero homework
sets the queue, the mix, and auto-refill in week 1 and never returns. A player who wants
control leaves auto-refill off and gets prompted when the queue drains.

### 5.7 What the scout does in weeks 20–26

He hosts the recruit visits — and that is not narrative dressing. **The scout owns whether a visiting
recruit actually moves toward you.**

Today that conversion is decided purely by win/loss, region match, and whether the recruit
has an open lean slot (`_update_recruit_lean_after_visit`, `franchise_routes.py:11371-11405`;
the probability gate is at `:11387-11394`). That gate is the designated insertion point for
scout influence.

For now the scout's presence is the *reason* those odds exist rather than a modifier on them.
When unique scout personalities arrive, **conversion ability becomes a scout attribute
multiplying into that same gate** — no restructuring required, just a term added where the
probability is already computed.

This also retroactively justifies the calendar. The scout isn't idle for seven weeks; he's
doing the highest-leverage work of the year. And it makes the staff slot genuinely
important, because scout quality will eventually govern **both** the information you gather
in weeks 1–19 and the conversion you get in 20–26.

---

## 6. Why recruits choose — motivation archetypes

### 6.1 Replacing the quality-to-rank coupling

v1 proposed weighting the lean roll so better-ranked teams attract better recruits. That
was wrong: it compounds, and it makes the wire boring, because the news is never
surprising.

Model **fit, not quality.** A recruit leans toward programs matching what *he* wants. Each
recruit carries a motivation archetype:

| Archetype | Weights | Notes |
|---|---|---|
| **Legacy** | Locked or near-locked to one program | Rare, ~5% |
| **Clout chaser** | **Prestige**, heavily | Chases blue-bloods regardless of fit |
| **Winner** | **National rank + tournament results** | Chases current form; volatile |
| **Homebody** | Region proximity | The small-program lane |
| **Minutes hunter** | Depth-chart openings at his position | Rewards honest roster reading |

Clout chasers key off **prestige** (slow, earned). Winners key off **national rank plus
tournament wins** (fast, volatile). Separating those two gives the pool two distinct
"chase the big program" behaviours with completely different feels — one you build over
years, one you can catch fire and steal.

This self-damps. Clout chasers go to blue-bloods, which is realistic and fine. Homebodies,
minutes hunters and legacies do not — so a small program always has a lane. The variance is
a property of the pool rather than a random roll bolted on top.

### 6.2 Motivation is an L2 reveal — and it's the real prize

Knowing **why** a recruit will choose is worth far more than knowing his shooting rating,
and it's exactly what a live visit would tell you.

It means a scouting report reads *"he's a clout chaser — you're wasting your time"* rather
than *"his OD is 64."* That is information a player acts on immediately. It converts the
scout budget from stat collection into intelligence work, and it makes **negative
information** — the cheapest kind to model — genuinely valuable.

### 6.3 Legacy ties and the lock badge

Legacy recruits are locked or near-locked from generation and **will not move** regardless
of what you spend. The player doesn't know until they scout him.

This is where fog and motivation compound: a locked recruit looks exactly like a gettable
one. You can burn a season and a pile of Signing Day points on a kid whose father played
at Fairview. Learning *not to bother* is a real payoff.

The UI socket already exists — `recruiting-spine.js:68-69` notes the ladder can render a
lock badge and simply never gets one because the backend has no flag. **We're adding the
plug, not the socket.**

---

## 7. The Recruiting Wire — passive weeks as information

### 7.1 What already exists

`season_news` lives on the franchise doc, stores
`{story_id, week, type, headline, lines[], created_at}`, dedupes by `story_id`, clears at
rollover, and already carries a `_build_recruiting_leans_story` builder feeding both the
FCC Coach's Office and `/franchise/news`. **We are extending a working system.**

### 7.2 The event log

At both lean mutation sites the code holds `old_lean` and `new_lean` in scope and discards
everything except one additions-only boolean. A pure `diff_lean(old, new) -> [event]`
helper — roughly 15 lines, no extra DB reads — recovers all of it:

```
gained_you · dropped_you · moved_up · moved_down · rival_took_your_top · displaced
```

Persist as `franchise_doc["recruiting_lean_events"][week]`, matching the existing
week-keyed pattern. **Filter at write time to user-relevant events** — user is actor,
displaced party, or already on that recruit's ladder — holding a season to ~150–300 events
(~60 KB).

### 7.3 Two bugs this exposes

1. **`fcc_pending_new_lean_recruit_ids` cannot represent a drop.** Readers re-intersect it
   against the recruit's *current* lean list, so a recruit who dropped you is filtered out
   by construction. The event log supersedes it; don't extend it.
2. **Weeks 27–34 produce no news at all.** `_append_franchise_week_news` returns early for
   `week > 26`. Lean movement happens; nothing is reported. Half the passive window is
   already silent.

### 7.4 Making the movement worth narrating

Passive movement is currently `random.choice(pool)` over in-region recruits in an RT band —
region is a hard filter and nothing more. The only honest headline is *"you won, and a
random local kid noticed."*

Motivation archetypes (§6) fix this at the root. Once a recruit has preferences, the roll
can be weighted by **fit** — his archetype against your program's profile — and the wire
gains something real to say:

> *"Marcus Bell moved you to #1 — he wants minutes, and your PG spot is thin."*
> *"You lost DeAndre Pope to Fairview. He's chasing prestige and you're not there yet."*

That second line is the one that matters. **It tells the player why they lost, which tells
them what to do differently.** Losses that explain themselves are the difference between a
system that feels alive and one that feels random.

---

## 8. Prestige — three real jobs

Currently marketed as "recruiting currency" while entering at exactly one point. After this
design it earns the label:

1. **Scout count** (§5.3) — better programs have better information.
2. **Clout-chaser attraction** (§6.1) — the archetype that keys directly off it.
3. **A term in the week-35 signing score** — currently absent entirely.

Slow-moving, compounding gently, and bounded — none of these produce the runaway effect
that tying recruit quality to national rank would have.

---

## 9. The active windows

### 9.1 Invite weeks 20–26

The re-rank problem solves itself. Fog lifts weekly, leans move visibly against you, and
the FCC surfaces *which* recruit moved — so there's a trigger every week without
legislating one. **You don't need a mechanic forcing re-ranks. You need a reason.**

**Hard gate at week 20** if no board exists. This is the one place a gate is unambiguously
correct: an empty board wastes all seven weeks.

### 9.2 Signing Day

- **Delete the auto-allocation.** Confirmed at `recruiting-hub.js:343-350`: 12 points +
  binding promise, 9 + binding promise, 6 + none. 27 points and two binding commitments
  made on the player's behalf, unmarked, on page load. If a helper is wanted it must be a
  *"suggest an allocation"* button the player presses.
- **Replace placeholder odds with real competition.** The current bar is
  `base(standing) + points × 2.2 + (promise ? 18 : 0)` — admitted placeholder, blind to
  rivals. CPU week-35 boards are already seeded server-side on the user's first save, so
  the real competition **is knowable**: *"4 programs are funding him · you're #2 on his
  ladder"* is both more useful and true.
- **Show roster capacity.** `available_roster_spots` and `available_scholarships` are
  already in the payload, unrendered, while funding stays uncapped against a hard 15-man
  ceiling.
- **Resolve the scholarship flag** — currently "normalized false/dormant," a visible lever
  that does nothing. Make it mechanical or remove it.
- **Play the result back as a sequence.** Keep batch resolution, but reveal recruits one at
  a time in signing order with your standing and the competition shown per recruit. Most of
  the drama of a live signing day, none of a new engine. *(Live auction — see §13.)*

---

## 10. FCC integration

Recruiting is currently a routed satellite reached through Run Training, which buries it.
It should be a first-class FCC citizen with three interaction levels:

| Level | When | Behaviour |
|---|---|---|
| **Gated** | Signing Day (wk 35); week-20 empty board | Must act to advance. Terminal and irreversible. |
| **Prompted** | Invite weeks 20–26 | Visible and glowing, but skippable — you *can* re-run the same board, the game just makes sure you knew. |
| **Ambient** | Passive weeks | No action required. The wire and the scout report sit where you'll read them. |

**Pulling recruiting out of Run Training.** The original decoupling was proposed, built, and
reversed because Run Training was the only *guaranteed* weekly trigger and decoupling risked
permanently-missed weeks. That reasoning was correct for the design at the time — **and an
FCC action-button gate solves the exact problem it was protecting against.** A step you
advance *through* cannot be silently missed. This is more robust than burying it, not less.

**Put the reason in the button.** Not "Recruiting" but *"2 recruits moved · 1 dropped you."*
A glow says something happened; a count says something happened **to you**, which is what
earns a click. Hovering shows a snapshot of the top of the board so the player can decide
whether to open it at all.

FCC layout is explicitly open for rework — tabs and Coach's Office containers can be
repurposed to make room.

---

## 11. UX architecture

Keep the phase-driven shell and the spine components. Four structural changes:

**a. One persistent Board.** Pool, invite board and signing board are currently three lists
the player rebuilds each phase. Make it one tracked-recruits object persisting all season,
carrying knowledge level, notes and history. The phases change what you *do* with the
board rather than making you rebuild it.

**b. The knowledge block replaces the number row.** A compact, level-aware component —
stars at L0, current RT + attributes at L1, full profile at L2 — rendering identically
in the pool, dock slot and signing row.

**c. The scout desk.** A genuinely new surface: day budget, assignments, standing orders,
and the deadline clock counting toward week 19.

**d. The wire gets a home.** Persistent panel in the passive phases, styled off the existing
story strip, showing gains **and losses**. The losses are what people will read.

### Defects to fix along the way

| Defect | Where |
|---|---|
| Dock slot and signing row render names as plain text, not links | `recruiting-hub.js:232`, `:371` |
| Year and archetype missing from the signing row | `recruiting-hub.js:362-384` |
| Weekly panel dismiss button bound but never rendered | handler `:624`; no `#weekly-dismiss` emitted |
| Post-submit redirect at 950 ms with no summary of what was committed | `:490-492` |
| Results strip the recruit to Pos/Region/RT at the payoff moment | `:507-550` |

## 12. Design-system decisions

**Adopt the letter grades.** Settled. A letter grade is coarse by nature, which suits a
system where knowledge arrives in steps — and `rt_current_potential()` already emits exactly
the `"C/B"` current/potential pair that L2 needs, so the reveal progression
(`★★★☆☆` → `B` → `B/A`) needs no new display primitive. Retire recruiting's 4-band
raw-colour scale; it actively fights this design.

**Conform to `.fcc-brand-page-shell`.** The Styleguide lists `recruiting.html` as a Type 1
Shell Page; the hub uses a bespoke container. If recruiting is becoming a first-class FCC
citizen it should look like one.

**Green stays reserved** for gating actions and positive-semantic data. Orange for
non-gating saves. Note the gated/prompted distinction in §10 maps cleanly onto this: gated
recruiting actions are green, prompted ones are orange.

**Still unformalised in the Styleguide** — spacing system, type scale, iconography, form
controls, modal sizing. The scout desk will need all five. Worth pinning down before it's
built rather than inventing a sixth local convention.

## 13. Cleanup

Verified by full reference sweep including config, deploy files, backend routes, tests and
both Playwright specs.

**Phase 1 — Repoint.** `franchise-command-center.js:4073` still builds
`/recruiting-orders.html`. Point it at `/recruiting.html`, matching `:3961`.

**Phase 2 — Delete dead JS.** `recruiting.js`, `recruiting-invites.js`,
`recruiting-orders.js`, `recruiting-results.js`.

**Phase 3 — Delete the redirect stubs.** `recruiting-invites.html` and
`recruiting-results.html` are safe now; `recruiting-orders.html` after Phase 1 verifies.

**Phase 4 — Other dead assets.** `recruiting.css`, `recruiting-spine-data.js`,
`recruiting-spine-gallery.html`, `Recruiting Orders v2.html`.

**Keep.** `recruiting-common.js` (loaded by the hub at `recruiting.html:45`) and
`recruiting-lean-ladder.css` (loaded by `training-report.html` and
`franchise-command-center.html`).

**Total: 11 files, ~5,173 lines, ~188 KB.** No test breakage. One caveat: `recruiting.css`'s
only real consumer is `awards.html`, itself orphaned — the FCC Awards button points at
`leaders.html`. Confirm nothing external links to it, then delete both together.

**Manifest corrections.** `recruiting_file_manifest.md` §1 lists four live screens; only the
Hub is reachable. §7's dead list needs the three stubs, their JS, and `recruiting.css`. §6's
"Prompt 0 shipped" understates it — Prompts 0–4 shipped. And the suggested reading order
sends a reviewer to the two largest dead files in the repo at step 4.

---

## 14. Phasing

**Phase 0 — Ground clearing.** Cleanup §13, manifest correction, adopt letter grades. No
user-visible change; everything after is cheaper.

**Phase 1 — The Wire.** Lean event diff, event log, drop signals, lift the `week > 26` news
gate. Highest ratio of perceived change to effort in the plan — it makes 27 dead weeks
legible using a news system that already exists.

**Phase 2 — Honest Signing Day.** Delete the auto-allocation, real competition counts,
roster spots, resolve scholarship. Small, self-contained, removes the two most misleading
things on the screen.

**Phase 3 — Motivation and prestige.** Archetypes, legacy ties + the lock flag, fit-weighted
lean movement, prestige in the signing score. Makes the Wire worth reading and prestige
worth having. *Ships without any fog — the wire immediately explains why you win and lose.*

**Phase 4 — FCC promotion.** Gated / prompted / ambient model, recruiting out of Run
Training, the count-bearing button.

**Phase 5 — Fog and the Scout.** `scouting_knowledge`, the ★ service with structural bias,
server-side fogging at the API boundary, day budget, Film vs Live, standing orders, the
knowledge block. The big one — and everything above stands alone if it slips.

**Phase 6 — Board unification, screen redesign, results.** One persistent board; the full
screen pass; a results screen that pays off a season of tracking.

Ordered so each phase ships value alone, and the two riskiest items — server-side fogging
and the reweighted roll — land after the cheap wins have already improved the feature.

### 14.1 Migration — existing franchises are not made retroactive

**Decided: fog of war and scouting apply to new franchises only.** An in-flight franchise
is never back-filled with `scouting_knowledge`, and never has information taken away from
it mid-save. This follows the precedent already set by `Rank_Prestige_System.md`, which
applies "only to franchises created after deployment and marked with the new franchise
rules/version flag," leaving older franchises on the legacy system permanently.

Rationale: retro-fogging a save would *remove* information a player already has and has
been planning around — strictly worse than the alternative, and unrecoverable. Gate it at
creation with a version flag and the question disappears.

The three tiers of the overhaul migrate differently, and it's worth being explicit:

| Change | Applies to existing franchises? |
|---|---|
| **Wire, Signing Day fixes, FCC promotion, cleanup** (Phases 0–2, 4) | **Yes, immediately.** Pure logic and display; no per-recruit or per-team state required. |
| **Motivation archetypes, legacy ties, ★ rankings** (Phase 3) | **At the next season rollover.** These are per-recruit generation fields, and `finish_season` already wipes FRD and generates a fresh 450-recruit class — so an existing franchise picks them up naturally when it rolls over. No back-fill script needed. |
| **Fog of war and the Scout** (Phase 5) | **New franchises only**, behind the version flag. |

That middle row is the useful one: because the recruit class is regenerated every season
anyway, most of the new *content* reaches existing saves for free at the natural boundary.
Only the per-team knowledge state is gated.

**Consequence to accept:** two rule sets coexist indefinitely, exactly as they already do
for prestige. Any recruiting surface that renders knowledge levels must degrade cleanly to
full information when the flag is absent — treat "no flag" as L2 everywhere rather than
branching the UI.

---

## 15. Open items

1. **CPU programs get constrained *reach*, not constrained *knowledge*.** Prestige and
   region determine how far a program can look — low-prestige programs don't board
   out-of-region or above a tier. Same observable result as CPU fog (blue-bloods find the
   gems), a fraction of the cost. True CPU knowledge levels would be invisible to the
   player and worth revisiting only if a scouting arms race becomes an explicit goal.
2. **Scout quality as a second uncertainty axis** (FM's Judging Player Ability/Potential).
   Tempting, but it doubles the uncertainty model. Hold for v2.
3. **Live auction Signing Day.** Deferred — the current engine is a whole-league batch
   resolution guarded to run once, so a live auction is a different resolution engine plus
   real-time CPU bidding plus a permanent sim/live fork. The sequence playback in §9.2
   captures most of the drama now, and resolution is already recruit-by-recruit in RT
   order internally, so the live version stays a natural later addition.
4. **Screen inventory.** Deferred by agreement. Early read: the scout desk is genuinely
   new, recruit detail must become knowledge-aware, and the standalone invites / orders /
   results pages likely don't return at all.
5. **Freshmen net −8.54 RT over a season** (camp +24.08, in-season −32.61) — the only class
   that nets negative. Out of scope, but it means the class you just signed gets *worse*
   the year you sign it, which will feel much sharper once scouting makes players care
   about individual recruits.
