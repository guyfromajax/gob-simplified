# Team Builder — UX & Design Brief

**Product:** Geeked-Out Basketball (GOB)
**For:** Claude Design
**Date:** 4 August 2026
**Deliverable:** an overhauled end-to-end experience for the Team Builder flow

---

## 0. How to read this brief

It is tiered on purpose.

| Tier | Meaning |
|---|---|
| **§3 — Immovable** | Breaks the product if violated. Not preferences. |
| **§4 — Our current thinking** | We have reasons, and they're shown. **Disagree freely** — if a better structure exists, we want it. |
| **§5 — Open** | No proposal from us. Bring us something. |

Please treat §4 as a starting position rather than a specification. Several of its entries are our first idea, not our best one. **§5 is genuinely empty and is where we most want your thinking.**

---

## 1. What the product is

GOB is a browser-based college basketball franchise simulator. A fixed league of **128 programs**, 16 conferences of 8. The player takes over a program and runs it across seasons — recruiting, lineups, tactics, and games simulated play-by-play on a rendered court.

It's currently in alpha. The audience is **sports-sim enthusiasts** — people who enjoy Out of the Park Baseball, Football Manager, NBA 2K's MyNBA. They are comfortable with density and detail. They enjoy configuration. A flow that feels "simplified for them" reads as condescending; a flow that feels *considered* reads as respect.

The visual register is confident, sporty, dark-UI, slightly retro-arcade. Condensed display type, saturated team colours against near-black chrome.

---

## 2. What Team Builder is, and what we're asking for

**Team Builder lets a player put their own program into the league.** Their school takes an existing team's place, so the league stays at 128 and every schedule is unchanged. They choose a slot, name the program, set its colours, design its court, and build its roster player by player.

It works. The engineering is done and verified. **What it doesn't do is feel like a moment.** Today it reads as a five-step form that happens to produce a basketball team. It should feel like founding a program.

That's the brief: **an overhaul of the whole flow's structure, hierarchy, pacing and craft.**

### The emotional arc we're aiming at

- **Choosing a slot** — consequential. You are taking someone's place.
- **Identity and colours** — the creative high point. This is where the thing becomes *yours*.
- **Roster** — absorbing, not laborious. Fifteen players, twelve attributes each, and it should feel like management rather than data entry.
- **Review** — pride. You should want to look at what you made.
- **Building** — anticipation.

Today the middle sags and the ends are flat.

---

## 3. Immovable

Violating any of these means the design can't be built as drawn.

### 3.1 The frontend is a pure renderer

**No business logic in the client.** No calculating derived values, no reimplementing formulas, no evaluating game rules. The frontend renders values the server supplies and posts user input back.

This is a standing architectural rule and it has already caused one round of rework in this feature.

**What it means in practice:**

- **Any derived value shown while editing comes from the server.** Position ratings update on control *release*, from a debounced request — not continuously as a slider moves.
- If a preview would require client-side computation, the answer is either **precompute the domain and ship it as data**, or **don't show the value until the server has it.**
- Court and banner *rendering* is explicitly exempt — those are canvas generators, sanctioned client-side by design, and they can be live and continuous.

### 3.2 Roster shape

- **Exactly 15 players.** Twelve scholarship plus three walk-ons. The count is not adjustable and no design should imply it is.
- **Twelve editable attributes** per player: SC SH ID OD PS BH RB ST AG ND IQ FT.
- **Every attribute clamps 5–99.**
- **Height: 66–84 inches**, displayed as feet and inches.
- **Class: FR / SO / JR / SR only.** No other year exists here.

### 3.3 Budgets and modes

**Capped** and **Uncapped** are a mode choice that **determines online eligibility**. Capped is eligible; uncapped is not. This is the single most consequential decision in the flow and cannot be buried, defaulted silently, or made reversible-feeling after the fact.

In **capped** mode three budgets apply:

| Budget | Rule |
|---|---|
| **Attributes** | Per player — each keeps his inherited total. Points never move *between* players. |
| **Height** | Team total, may not exceed inherited. Under is allowed. |
| **Class** | Team total, must equal inherited **exactly**. |

In **uncapped**, none of these apply.

> **Budget state must be visible where the user is editing** — not only at Apply. This exists because an error once rendered at the top of a long page while the user was at the bottom, and the feature looked like it was hanging. Off-screen feedback is a defect, not a layout choice.

### 3.4 Weight is not editable and is not previewed

Weight derives from height on the server. In the editor it shows the player's inherited weight until height changes, then is replaced by a short label — **"Set at creation"**. It is never recalculated in the client. (See §3.1.)

### 3.5 Portraits

- **Every player is auto-assigned a portrait** by classifying height, weight and attributes. The picker is an **override**, not a required step.
- The pool is **450 images**, filtered on **skin tone** and **build**.
- **Filter combinations can return very few results** — sometimes two or three, occasionally none. This is a property of the pool, not a bug, and the design needs a graceful answer for a nearly-empty grid.
- **No upload control anywhere.** Uploads are a committed fast follow but do not exist yet. A control that isn't wired is worse than an absent one.

### 3.6 Court

The generator is parametric and its **geometry is fixed** — the user colours the court, never moves a marking. Five colour inputs only: hardwood style, out-of-bounds, free-throw lane, free-throw arc, main floor centre. Output dimensions are non-negotiable.

### 3.7 Language that must be accurate

- **Class tiers describe experience, never potential.** A player's ceiling is fixed at generation and does not respond to class. A young roster has *more seasons*, not better players. Labelling otherwise would be false.
- **The abbreviation is exactly three characters** and must be unique in the league.

---

## 4. Our current thinking

**Everything here is a position, not a requirement.** The reasoning is included so you can tell whether it survives contact with a better idea.

### 4.1 The flow

Five steps today: **Slot → Identity → Colors → Roster → Review**, then a build screen.

**We suspect Identity and Colors should merge.** Alone, neither can show anything satisfying — Identity has no colours to render with, Colors has no name to put on the court. Merged, the preview becomes the program's banner assembling live as the user types and picks colours, which is the most rewarding thing this flow could show. It also takes five steps to four, and every step is a place to abandon.

### 4.2 Screen 0 — Program select

The entry point, before Team Builder. A grid of all 128 programs with search and five stacking filters, plus the entry to build your own.

**Proposed copy:**

> **Find Your Program**
> 128 to choose from. Pick one — or build your own.

The build path currently duplicates the words "Team Builder" in both a card title and its button. We'd drop the card title and let the button carry it.

**Filter labels** (all five stack; all are rank-based tiers across the 128):

| Filter | Tier 1 → Tier 5 |
|---|---|
| **Talent** | Loaded · Deep · Average · Thin · Rebuilding |
| **Prestige** | Blue Blood · Established · Respected · Climbing · Unproven |
| **Size** | Tallest · Taller · Balanced · Quicker · Quickest |
| **Experience** | Most Experienced · Experienced · Balanced · Young · Youngest |
| **Geography** | 56 options — 50 US states plus six international regions |

**Filtered-out programs stay visible as dimmed, non-selectable cards.** The grid never reflows and never empties. This is deliberate: it preserves spatial memory and shows the user what they're excluding.

### 4.3 Screen 1 — Slot

Same 128-program grid, now choosing which program yours replaces.

**We think the selection confirmation should be a sticky action bar** — pinned to the bottom of the viewport, appearing on selection, always fully visible, carrying the selection summary and the primary action. Not a modal: a modal interrupts browsing and prevents comparison, and this is a decision people will want to make by looking back and forth.

### 4.4 Screens 2–3 — Identity and Colours

Fields: school name, mascot, three-character abbreviation, primary and secondary colours, jersey style, and the five court colour inputs.

**The preview is the point.** We'd like the generated banner and the court both rendering live. Both generators already run in the browser, so this is free.

Court colour options — each field offers a small set plus Custom:

| Field | Options |
|---|---|
| Out of bounds | Primary · Secondary · Black · Hardwood · Custom |
| Free-throw lane | Primary · Secondary · Hardwood · Custom |
| Free-throw arc | Primary · Secondary · Hardwood · Custom |
| Main floor centre | Hardwood · Custom |

**Defaults should derive from the user's palette**, not start at hardwood — otherwise the first court they see reads as unfinished.

### 4.5 Screen 4 — Roster

**This is the screen most in need of a structural answer.** Fifteen players × twelve attributes is 180 controls. As a table it's a spreadsheet; as a scrolling stack of cards it's endless.

**Our proposal is a list–detail split:** a compact roster rail showing all 15 — portrait, name, number, position ratings — with the selected player's full editor filling the main area. Budget meters pinned and always visible. One player's twelve attributes at a comfortable size.

This solves several problems at once: budgets stay on screen (§3.3), the portrait is large enough for its controls to feel deliberate, and moving between players is a click rather than a scroll.

**Per-player controls we'd propose:**

- **Attributes** — sliders with numeric readout, clamped 5–99
- **Position ratings** — shown as letter grades (F through A++), updating on slider release
- **Height** — a slider rather than a dropdown; it spends a team budget and a slider shows the cost as you move it
- **Class** — a four-option segmented control, always visible
- **Weight** — small, greyed, beneath height, per §3.4
- **Name, jersey number** — plain fields
- **Portrait** — the current image, with *Choose* and *Randomize* appearing on hover

**Mode selection** (capped/uncapped) sits above all of it and stays visible. Per §3.3 it's the most consequential choice in the flow and currently doesn't look like it.

**The portrait picker** filters on skin tone and build. Skin tone should be **unlabelled swatches in a light-to-dark ramp** — no race vocabulary in the interface. Build is a labelled set.

### 4.6 Screen 5 — Review

Currently a list of `Key: value` lines that reads like a state printout.

**We think it should be mostly visual**: the banner at real size as the hero, the court beneath it, the roster as a compact grid of 15 portraits. Text reduced to what the artwork can't say — conference and region, online eligibility, team totals.

Online eligibility is currently buried mid-sentence in the fourth line. If a user reads one thing on this screen it should be their program's name and whether it's eligible.

### 4.7 Global

- **The wizard header repeats a title and two-line subhead on every step**, long after the user knows where they are. We'd collapse it to a compact header after step one — that alone returns roughly 200px of vertical space the flow is currently missing.
- **A full-bleed white FAQ strip** sits directly beneath the primary action on every screen. In a dark UI it's the loudest element on the page and it's a footer link.
- **Vertical rhythm between the Back/Next buttons and the footer is too tight** throughout.

---

## 5. Open — bring us your thinking

No proposal from us on any of these.

1. **What should this flow feel like?** §2 describes an emotional arc we're failing to deliver. We've described the target; we haven't designed for it.

2. **The Review moment.** The user has just built a program. What would make them want to look at it, screenshot it, show someone? We've suggested "show the artwork bigger," which is the obvious answer and probably not the best one.

3. **The build sequence.** After Apply, the franchise is created. We don't yet know how long that takes — we're measuring. If it's genuinely slow, is there a version where the wait becomes a reveal rather than a spinner? If it's fast, should it be a moment at all?

4. **Progress and commitment.** Five steps, a lot of decisions, and every step is somewhere to abandon. How should progress be shown? Should any of it be skippable, with sensible defaults? Should the user be able to jump around?

5. **Density.** This audience likes detail. Where should we be *more* dense rather than less — and where does density become noise?

6. **Anything we haven't considered.** The flow was designed by the people who built it, which means it's shaped by the order the engineering happened in rather than the order a person thinks in. If the whole structure is wrong, say so.

---

## 6. What we'd like back

Whatever form serves the thinking — but the things we most need to see are the **roster screen's structure**, the **identity/colours preview moment**, and the **review screen**. Those are where the flow currently fails hardest and where the constraints bite most.

If a proposal conflicts with §3, we'd rather see it flagged than silently avoided — occasionally a constraint turns out to be softer than we thought, and it's worth knowing when a design is fighting one.
