# Implementation Spec — Playbooks Page Redesign

**Repo:** `guyfromajax/gob-simplified` · branch `develop`
**Lens:** Simple, Stable, Scalable (SS&S)
**Design source:** four signed-off Claude Design files — `Playbooks Editing Tile.html` (D1), `Playbooks Page.html` (D2), `Playbooks Redistribution.html` (D3), `Playbooks PCC Assign + Reorder.html` (D4)

Design is complete and signed off. This spec is the handoff. Where this doc and the design HTML disagree, **this doc wins** — it's grounded in the real repo state.

---

## 0. Files touched

| File | Change |
| --- | --- |
| `FrontEnd/static/playbooks.html` | Layout rebuild — tabs, tile grids, rail, shot-weights strip |
| `FrontEnd/static/playbooks.js` | Enforced model, PCC single-source, delete `syncSelectionFromPcOrder` |
| `FrontEnd/static/playbooks.css` | Tile styles, CMD tokens, rail restyle |
| `FrontEnd/static/franchise-command-center.css` | CMD tokens only (§2) |
| `FrontEnd/static/franchise-command-center.js` | CMD threshold fn only (§2) |

**No backend changes.** The save payload shape (`playbook_settings.{motion,set_plays,fast_breaks,hc_traps,man_defense,zone_defense,pc_order,...}`) is unchanged. This is a frontend redesign against the existing API.

---

## 1. Ship this first, independently

**The CMD fork fix.** It's ~5 lines, has zero dependency on the redesign, and shipping it now means the live app and the comps agree while the rest is built.

Currently the two screens use different scales and neither knows about the other:

| | FCC | playbooks.js |
| --- | --- | --- |
| classes | `is-good` / `is-mid` / `is-low` | `is-high` / `is-mid` / `is-low` |
| thresholds | ≥70 / ≥40 | ≥67 / ≥34 |

A play with CMD 68 is currently amber in the FCC and green on the playbooks page. Same play, same number, two colors.

See §2 for the exact change.

---

## 2. CMD scale — canonical values

**Thresholds: 40 / 70. Classes: `is-good` / `is-mid` / `is-low`. Colors: blue / green / yellow.**

```
CMD ≥ 70  → is-good → #4A90D9  (blue)
CMD ≥ 40  → is-mid  → #34EC27  (green)
CMD < 40  → is-low  → #FFD700  (yellow)
```

**Blue ranks above green. This is deliberate.** GOB's rating scale drafts off OOTP Baseball, where players are conditioned to read blue as the top band. Do not "correct" this to a green-is-best ramp.

### 2a. `playbooks.css`

```css
/* :root — replace */
--eff-low:  #F5C518;   →  #FFD700
--eff-mid:  #A8D400;   →  #34EC27
--eff-high: #4CAF50;   →  #4A90D9
```

Rename `--eff-high` → `--eff-good` and the `.eff-score.is-high` rule → `.eff-score.is-good` (the class name `is-high` is emitted by `playbooks.js` but matches nothing in the FCC stylesheet — killing it removes a live footgun).

Note `--success: #34EC27` already exists in this file and is the same green as `--eff-mid`. Consider whether they should reference one token.

### 2b. `playbooks.js` — `renderEffScore()` (~line 751)

```js
// FROM
const className = numeric >= 67 ? "is-high" : (numeric >= 34 ? "is-mid" : "is-low");
// TO
const className = numeric >= 70 ? "is-good" : (numeric >= 40 ? "is-mid" : "is-low");
```

### 2c. `franchise-command-center.css` (~lines 2620–2630)

```css
.fcc-playbooks-item-eff.is-good { color: #4CAF50; }  →  #4A90D9
.fcc-playbooks-item-eff.is-mid  { color: #A8D400; }  →  #34EC27
.fcc-playbooks-item-eff.is-low  { color: #F5C518; }  →  #FFD700
```

### 2d. `franchise-command-center.js` — `getFccPlaybookEffClass()` (~line 1692)

Thresholds are already 70/40 and classes already `is-good`. **No change needed** — it's the reference implementation.

**Expected visual delta:** the playbooks page scale *tightens* (67→70, 34→40), so some plays shift down a band. That's the fix landing, not a regression.

---

## 3. The constraint model

Two models, split by section. This is settled.

### 3a. Enforced — Motion, Set Plays, Man Defense, Zone Defense

The section is **always exactly 100**. Invalid state cannot exist. No error text, no `73 / 100`, no readiness gate for these sections.

Reference implementation (verified against ~24,000 exhaustive + randomized cases — invariant holds, locks never move, nothing goes negative, no drift over 20k-step walks):

```js
// largest-remainder proportional distribution of integer S across weights
function distribute(weights, S) {
  const n = weights.length;
  if (n === 0) return [];
  if (S <= 0) return weights.map(() => 0);
  const total = weights.reduce((a, b) => a + b, 0);
  const raw = weights.map(w => total <= 0 ? (S / n) : (w / total * S));
  const fl = raw.map(x => Math.floor(x));
  const left = S - fl.reduce((a, b) => a + b, 0);
  const order = raw
    .map((x, i) => ({ i, r: x - Math.floor(x) }))
    .sort((a, b) => b.r - a.r);
  for (let k = 0; k < left && order.length; k++) fl[order[k % order.length].i]++;
  return fl;
}

// returns true if the target was capped (hard stop hit)
function setEnforced(arr, idx, target) {
  target = Math.round(target);

  // ⚠️ INACTIVE ROWS ARE OUT OF THE ARITHMETIC ENTIRELY — see §3b
  const live = arr.filter(p => p.isActive !== false);
  const lockedSum = live.reduce((s, p) => s + (p.locked ? p.pct : 0), 0);

  const max = 100 - lockedSum;
  let capped = false;
  if (target > max) { target = max; capped = true; }
  if (target < 0) target = 0;

  const others = arr
    .map((p, i) => i)
    .filter(i => i !== idx && !arr[i].locked && arr[i].isActive !== false);

  const dist = distribute(others.map(i => arr[i].pct), 100 - lockedSum - target);
  others.forEach((i, k) => { arr[i].pct = dist[k]; });
  arr[idx].pct = target;

  // inactive rows pinned at 0, always
  arr.forEach(p => { if (p.isActive === false) p.pct = 0; });

  return capped;
}
```

**Rules:**
- **Proportional.** Plays surrender in proportion to current share; relative shape of untouched plays preserved.
- **Locks.** Per-tile lock affordance. Locked plays exempt from redistribution; their value counts toward `lockedSum`. This is what makes the model tolerable — without it, a coach who sets Play B to exactly 25 watches it drift on every unrelated edit.
- **Floors cascade.** Handled naturally by `distribute` — a play at 0 gives nothing further; shortfall spreads to whoever's left.
- **Hard stop.** When `target > 100 - lockedSum`, the slider **visibly stops**. Never a slider that silently refuses.
- **Computed last play.** If exactly one non-locked active play remains, it's fully determined → render as a **value, not a control** (no slider). See §3b.

### 3b. ⚠️ Inactive rows — the hazard

**This is the most important correctness note in this spec.**

`man_defense_rows` carry `is_active`. Inactive rows render today with `row-dead` + a **"Coming Later"** pill, disabled inputs, and no event bindings. `playbooks.js` already sums man defense over **active rows only**:

```js
manDefense: this.state.manDefense
  .filter(item => item.isActive !== false)
  .reduce((sum, item) => sum + item.percentage, 0)
```

**The enforced model reintroduces a hazard the old table couldn't have.** In the old UI, inactive rows had no bindings, so nothing could push a value into them. Under redistribution, *the user doesn't touch the inactive row — the algorithm does.* Without an active-aware filter:

```
start:       Man 100 · Box-and-One 0 (coming later) · Triangle-2 0 (coming later)
drag Man→60: Man  60 · Box-and-One 20 (coming later) · Triangle-2 20 (coming later)
```

Section reads 100. Backend sums active only → sees **60**. The user has silently dumped 40% of their defense into plays that don't exist.

**Requirements:**
1. `setEnforced` filters inactive out of `others` **and** out of `lockedSum` — inactive ≠ locked-at-0. A locked play's value *counts toward* the 100; an inactive play is **out of the arithmetic entirely**, pinned at 0.
2. Defense in depth: the filter lives **inside** `setEnforced`, not in the caller.
3. Normalize (§3c) gets the same treatment — distributes across active rows only, pins inactive at 0.
4. **Man renders computed today.** With Man the only active row, it's fully determined → `= 100%`, no slider, "Determined — the only active play." Not because "Man is a single fixed play" — because it's the only *active* one. It **self-corrects into normal enforced sliders the moment Box-and-One ships.** No layout change needed.
5. Inactive tile state: dimmed, "Coming Later" pill, slider inert. **This is visually distinct from the 0%-unassigned dim (§5).** That one is a state the user chose and can undo; this one isn't editable at all.

### 3c. Normalize — Fast Breaks, HC Traps

%-only, few plays. Keep a validity state, but never strand the user: a **Normalize** action per section snaps to 100 in one click. User then adjusts from a valid state.

Rationale for the split: 3a's machinery is real cost against SS&S and only earns its keep where play count makes hand-balancing painful.

### 3d. Section totals & save gating

- Enforced sections: quiet `100 · balanced`. No counter, no error, no gate.
- Normalize sections: `8 left to assign` + Normalize button. **Countdown, not scold** — never `73 / 100` in red.
- **Save gates on the two normalize sections only.**
- **Delete the `0 / 6 sections ready` indicator** (`#sections-ready-indicator`). It's incoherent — four of six can never be un-ready.

---

## 4. The tile

Sibling of the FCC read-only chip, not a clone. Inherits radius, border, gradient wash, inset highlight, type scale, name/% top row, CMD+TOP meta anatomy, CMD color logic. Diverges: ~2× taller, 3-across not 4.

**Anatomy — 3 rows:**
1. `[+ OFF / OFF · 3] [name] [lock] [% input]`
2. Slider (track / fill / thumb / bubble / floor wall)
3. Meta: `[select] [TOP scorer] [CMD]`

**Meta row flex — this is load-bearing:**
- **CMD** `flex: 0 0 auto`, pinned right. Never moves, never shrinks. It's a color-scanned number; a value that shifts position between tiles is unscannable.
- **TOP** `flex: 0 1 auto; min-width: 0`, ellipsis. **The only element allowed to truncate.**
- **Select** `flex: 0 0 auto`, content width. Options are a finite set, max 9 chars ("Balanced").

**No control labels.** No `FOCUS`, no `TARGET`. Measured, the label costs ~44px — nearly the entire CMD block — to describe a dropdown that already reads "Balanced". The section header establishes context.

**The `100` edge case:** the % input is `2.6ch` (two digits). At exactly 100 it clips. Fix is a `threed` class that shrinks only the 3-digit case — no layout shift, no cost to the common case.

**%-only variants** (Fast Breaks / HC Traps) have no select, so the meta row is `[TOP] [CMD]` — *exactly* the FCC chip. Keep it; don't fill the space.

**Tile states:** default · locked · at-floor (hatched wall, red thumb ring) · computed (`= n%`, no slider) · dimmed-0%-unassigned · inactive ("Coming Later") · slider hover/active.

---

## 5. 0% plays — visibility rules

**The rule is not "0% = hide." It's `pct === 0 && !inPCC` = inert.** PCC membership is what makes a play live, independent of weight.

| | 0%, not in PCC | 0%, in PCC |
| --- | --- | --- |
| **Editor** | Present, dimmed | Present, **not** dimmed — it's active |
| **FCC / Set Lineup modal** | Omit | **Show** — it's on the call sheet |

**A play stays in the PCC until the user explicitly removes it. Redistribution never evicts.** A slot holding a play at 0% is a real state: "never called by default, but on the call sheet."

**Dimming is purely visual.** Full opacity on hover, full-size hit target, live slider, `pointer-events: auto`. A 0% play is the one that most needs an obvious "drag me back" affordance — if dimming shrinks the target, the recovery gesture is harder than the normal one, which is backwards.

**No-slack copy.** If locks leave `100 - lockedSum === 0`, a 0% tile's slider won't move at all. Generic "section full" reads as a bug on a tile showing 0%. Use copy that names cause and fix: *"No room — the slack is locked. Unlock a play to make space."*

---

## 6. The Playcall Center rail

### 6a. `syncSelectionFromPcOrder()` — DELETE, don't port

Currently called from 6 sites (~lines 348, 491, 670, 727, 899, and defined at 494). It exists to keep two representations of PCC membership from drifting: the `.control-check` checkboxes in the table rows, and `state.pcOrder`.

**The redesign makes it structurally unnecessary.** `pcOrder[side]` becomes the **single source of truth**; the tile badge is *derived* by index lookup. There is no second copy to sync.

```js
inPCC(id)        → pcOrder[side].includes(id)
badge(id)        → pcOrder[side].indexOf(id) + 1   // null if absent
```

Verified across 30,000 randomized sessions: cap holds at 8, no duplicates, no cross-side leakage, badges always contiguous `1..n` matching call order, no ghost badges on unassigned plays.

This is the same SS&S pattern as `BallController` — single source of truth for state that persists across views.

### 6b. The loop

`+ OFF` on tile → slot fills → badge becomes `OFF · 3` → `×` on slot → badge reverts to `+ OFF`. Removing a slot renumbers those below **and every affected tile badge updates live.**

- **Assign/unassign: one gesture from either side.** Delete `.control-check` / `renderCheckbox` / `bindPcCheckboxEvent` entirely.
- **Drag lives only in the rail.** Order is call priority — genuinely meaningful, so drag earns its keep here and nowhere else. Keep `handleDrop` / `handleDragStart` / `handleDragEnd` / `clearDropHints`. You cannot drag a tile into the rail.
- **Cap 8 per side.** At 8/8, open slots vanish, header confirms `Full — 8 calls set`, and unassigned tiles on that side show a **pre-disabled** `PCC full` button — capacity legible before the click, not discovered at it.
- **Empty slots are invitations.** Numbered, hatched "open call" rows. Header counts down: `3 of 8 set · 5 open`.

### 6c. Destination naming

Badge names its destination and takes its color: `+ OFF` / `OFF · 3` in **orange** `#F79420`, `+ DEF` / `DEF · 2` in **brand navy** `#27408E`.

**Do not use `#4A90D9` for defense** — it's the identical hex to `--cmd-good`, so a defense badge and a top-band CMD would read identically on the same tile. The *word* carries routing; color is only reinforcement.

---

## 7. Page layout

**Offense / Defense tabs, where the tab you're on is the rail column you feed.** The split doubles as routing.

- **Offense tab:** Motion, Set Plays (full tile grids) + Fast Breaks (compact chip strip)
- **Defense tab:** Man Defense, Zone Defense (full tile grids) + HC Traps (compact chip strip)

The %-only lightweights are demoted to compact strips — they're not peers of Motion and the layout shouldn't pretend they are.

**Live shot-weights: sticky strip atop the editing column.** Not in the right rail — the PCC owns that. This puts the consequence directly above its cause.

`renderShotWeights` (Position Shot Weights) already exists and already renders in the FCC tab and in this page's save-confirm modal. **Today the user sees the consequence of the decision only after it's locked.** Wire it live: as percentages move, expected shot distribution shifts in front of them. This is what converts the page from a form into a tactics screen.

**Keep:** `#gameplay-lockout` card (top banner, dims the editing column), the `.pc-card` sticky rail structure, `back-btn` / return-url handling, `authGuard`, `gameStore` import, sort behavior where it still applies.

**Collapse the save-confirm modal to a toast.** With shot-weights live, `#save-confirm-modal` + `psw-root` is redundant — it shows the distribution *after* the decision the user has now been watching the whole time.

---

## 8. ⚠️ SFX — preserve all of it

There are **9** `playSound` call sites in `playbooks.js` today. The redesign removes the controls several of them are bound to. **Rebind, don't drop.**

| Current site | Fires on | After |
| --- | --- | --- |
| L390 | sort button click | keep if sort survives |
| L667 | `.pc-remove-btn` click | **keep** → `×` on slot |
| L714 | `handleDrop` | **keep** → rail reorder |
| L825 | % `input` change | → **type-to-set commit** (blur/Enter) |
| L832 | ± spin button click | ⚠️ **rebind → slider `pointerup`** |
| L844 | motion focus `select` change | **keep** → tile select |
| L857 | target shooter `select` change | **keep** → tile select |
| L881 | `.control-check` change | ⚠️ **rebind → `+ OFF` / `+ DEF` assign + unassign** |
| L974 | `handleSave` (`confirm-2-lowervol.wav`) | **keep** → fires with the toast |

**The slider is the trap.** `click-tiny.wav` on `pointermove` would machine-gun the sample across a 15-point drag. It must fire on **`pointerup` only** — one gesture, one sound. Same principle as one gesture, one delta.

**Redistribution itself is silent.** When six tiles move in response to a drag, they make no sound. The sound belongs to the user's action, not the system's reaction.

---

## 9. Known constraint

FCC tile CSS is entirely scoped under `#franchise-container` (`franchise-command-center.css` ~lines 2490–2660). A genuinely shared tile component has to escape that selector.

Decide deliberately: extract to a shared component/stylesheet, or accept duplication with the tokens centralized. **Duplication with drifting values is what caused the CMD fork in the first place** — whatever the choice, the color and threshold values must live in exactly one place.

---

## 10. Suggested sequence

1. **CMD fix** (§2) — ship standalone, immediately
2. **Tile component** (§4) + tile states — the grid depends on it
3. **Enforced model** (§3) — with the inactive-row filter from day one, not bolted on
4. **PCC single-source** (§6) — delete `syncSelectionFromPcOrder`
5. **Page layout** (§7) — tabs, rail, shot-weights strip
6. **SFX pass** (§8) — verify all 9 sites
7. **Toast** replacing save-confirm modal

---

## 11. Acceptance

- [ ] CMD reads identically on playbooks page, FCC tab, Set Lineup modal (blue/green/yellow, 40/70)
- [ ] Motion/Set/Man/Zone always sum to exactly 100 — invalid state unreachable
- [ ] **Redistribution never assigns value to an `is_active: false` row** (drag Man 100→60; Box-and-One and Triangle-2 stay at 0)
- [ ] Man renders `= 100%` computed today; becomes a normal slider grid when a second man defense activates — **with no code change**
- [ ] Locked plays never drift
- [ ] Raised slider visibly stops at `100 - lockedSum`
- [ ] `syncSelectionFromPcOrder` no longer exists; PCC badge derives from `pcOrder` index
- [ ] PCC cap 8/side; tiles pre-disabled at capacity
- [ ] 0%-in-PCC play survives redistribution and still shows in FCC / Set Lineup modal
- [ ] 0%-unassigned tile is dimmed but fully grabbable
- [ ] Shot-weights move live as percentages change
- [ ] All 9 SFX sites fire; slider fires on release only, never during drag
- [ ] `0 / 6 sections ready` is gone; save gates on the two normalize sections
