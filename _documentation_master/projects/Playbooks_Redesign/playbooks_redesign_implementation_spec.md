# Implementation Spec — Playbooks Page Redesign

**Repo:** `guyfromajax/gob-simplified` · feature branch off `develop`
**Lens:** Simple, Stable, Scalable (SS&S)
**Design source (sole SoT):** `Playbooks_Page_D2_CURRENT.html` (Deliverable 2)

D1 / D3 / D4 are **stale** — do not add them unless Design re-cuts. D3 in particular still contains the inactive-row bug.

Where this doc and D2 disagree, **this doc wins**, except where a decision below explicitly prefers D2 (ready indicator).

---

## Decisions (resolved 2026-07-17)

| # | Decision |
| --- | --- |
| 1 | **Design SoT** = D2 only. |
| 2 | **Live shot-weights** = debounced preview **backend** endpoint. Do not port `compute_position_shot_weights` to JS. Fire on settle (same principle as slider SFX / one gesture → one delta), not per `pointermove`. Spec's earlier "no backend changes" is **wrong** on this point. |
| 3 | **0%-in-PCC on read-only venues** is in scope. Change FCC + Set Lineup filters from `percentage > 0` to `percentage > 0 \|\| inPCC`. 0% and not in PCC stays excluded. |
| 4 | **CSS sharing** = extract shared CMD/tile tokens out of `#franchise-container` (option A). No duplicated drifting hex/threshold values. |
| 5 | **Locks persist** in the save payload (backend work with #2). Not session-only. |
| 6 | **Sort** = drop entirely. No sort UI; array order is not user-controllable. |
| 7 | **Save feedback** = existing toast pattern, copy `"Playbooks Saved"`. Drop save-confirm modal and its "Back To Locker Room" CTA. |
| 8 | **Ready indicator** = implement D2's successor (`N of 2 flexible sections` / `Ready to save`), not a bare deletion. Spec's "delete 0/6" means delete the incoherent counter only. |
| 9 | Doc ≠ D2 → doc wins for enforced/inactive arithmetic. **Note:** the checked-in D2 export's `setEnforced` still lacks the inactive-row filter — treat that export as stale until Design re-pulls; implement the active-aware version in §3. |
| 10 | **Docs** = update `Playbooks_Page.md` + this spec if build changes anything. |
| 11 | **Ship order** = CMD fix (§2) as its own commit/PR, then redesign. |
| 12 | **Branch** = feature branch off `develop`. |

---

## 0. Files touched

| File | Change |
| --- | --- |
| `FrontEnd/static/playbooks.html` | Layout rebuild — tabs, tile grids, rail, shot-weights strip; toast host |
| `FrontEnd/static/playbooks.js` | Enforced model, PCC single-source, delete `syncSelectionFromPcOrder` + sort, debounced shot-weights preview, locks in state/payload |
| `FrontEnd/static/playbooks.css` | Tile styles, rail restyle; consume shared CMD tokens |
| `FrontEnd/static/franchise-command-center.css` | Consume shared tokens; drop scoped CMD color drift |
| `FrontEnd/static/franchise-command-center.js` | 0%-in-PCC visibility; CMD via shared helper/tokens |
| `FrontEnd/static/set-lineup.js` | 0%-in-PCC visibility; CMD thresholds/classes aligned |
| `FrontEnd/static/set-lineup.css` | CMD colors aligned (`is-good` / mid / low) |
| Shared stylesheet (new) | CMD thresholds + colors (+ later shared tile tokens) — one place |
| Backend playbook routes / settings utils | Locks persistence; debounced shot-weights **preview** endpoint |

Payload grows: existing `playbook_settings` maps stay; add **locks** (durable per-play) and keep computing `position_shot_weights` server-side only.

---

## 1. Ship this first, independently

**The CMD fork fix.** Zero dependency on the redesign. Ship as its own PR so live venues agree while the rest is built.

Currently venues disagree:

| | FCC | playbooks.js | set-lineup.js |
| --- | --- | --- | --- |
| classes | `is-good` / `is-mid` / `is-low` | `is-high` / `is-mid` / `is-low` | `is-high` / `is-mid` / `is-low` |
| thresholds | ≥70 / ≥40 | ≥67 / ≥34 | ≥67 / ≥34 |

A play with CMD 68 is amber in the FCC and green on the playbooks page / Set Lineup. Same play, same number, two colors.

See §2 for the exact change. Include Set Lineup in the CMD PR — acceptance requires all three venues.

---

## 2. CMD scale — canonical values

**Thresholds: 40 / 70. Classes: `is-good` / `is-mid` / `is-low`. Colors: blue / green / yellow.**

```
CMD ≥ 70  → is-good → #4A90D9  (blue)
CMD ≥ 40  → is-mid  → #34EC27  (green)
CMD < 40  → is-low  → #FFD700  (yellow)
```

**Blue ranks above green. This is deliberate.** GOB's rating scale drafts off OOTP Baseball, where players are conditioned to read blue as the top band. Do not "correct" this to a green-is-best ramp.

### 2a. Shared source of truth (landed with CMD PR)

| Artifact | Role |
| --- | --- |
| `FrontEnd/static/css/playbook-cmd.css` | `--cmd-good/mid/low` + `.is-good/.is-mid/.is-low` colors for playbooks, FCC, Set Lineup |
| `FrontEnd/static/common.js` → `getPlaybookCmdClass()` | Thresholds 70 / 40 → class names |

Venue wrappers (`renderEffScore`, `getFccPlaybookEffClass`, `getLineupPlaybookEffClass`) call the shared helper. Local hex/threshold copies removed from venue stylesheets.

**Expected visual delta:** playbooks + Set Lineup scales *tighten* (67→70, 34→40), so some plays shift down a band. That's the fix landing, not a regression.

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
- **Locks.** Per-tile lock affordance. Locked plays exempt from redistribution; their value counts toward `lockedSum`. This is what makes the model tolerable — without it, a coach who sets Play B to exactly 25 watches it drift on every unrelated edit. **Locks persist in the save payload** (Decision 5) — durable intention, not session UI state. Exact key shape is set during backend work; must round-trip on GET/save and survive reload.
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
- Normalize sections: `8 left to assign` + Normalize button. **Countdown, not scold** — never `73 / 100` in red. Normalize snaps via `distribute(currentWeights, 100)` (proportional; all-zero → equal split).
- **Save gates on the two normalize sections only.**
- **Replace** `#sections-ready-indicator` (`0 / 6 sections ready`) with D2's successor: warn `N of 2 flexible sections balanced` / ok `Ready to save · all sections balanced`. Delete the incoherent 0/6 counter — not the readiness concept.

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

**Read-only venues (FCC summary + Set Lineup playbooks modal):** filter `percentage > 0 || inPCC` (Decision 3). Exclusion of 0%-not-in-PCC stays; only the PCC exception is new.

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

`renderShotWeights` already exists. **Server remains the only computation** (`compute_position_shot_weights`). Wire a **debounced preview endpoint**; refresh the strip on settle (slider `pointerup`, % commit, normalize, lock toggle that changes arithmetic) — not on every `pointermove`. No client-side port of the weight math (Decision 2).

**Keep:** `#gameplay-lockout` card (top banner, dims the editing column), the `.pc-card` sticky rail structure, `back-btn` / return-url handling, `authGuard`, `gameStore` import.

**Drop sort entirely** (Decision 6).

**Collapse the save-confirm modal to a toast** (Decision 7): reuse the existing toast pattern; copy `"Playbooks Saved"`; no "Back To Locker Room" in that flow — header back link already covers return.

---

## 8. ⚠️ SFX — preserve all of it

There are **9** `playSound` call sites in `playbooks.js` today. Sort is deleted (Decision 6), so **8** remain to rebind. **Rebind, don't drop** the rest.

| Current site | Fires on | After |
| --- | --- | --- |
| L390 | sort button click | **drop** with sort (Decision 6) |
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

## 9. Shared CSS / tokens

**Decided (Decision 4):** extract shared tokens/stylesheet out of `#franchise-container`. FCC tile CSS today is scoped under `#franchise-container` (~lines 2490–2660). Shared CMD colors + thresholds (and later tile anatomy tokens) live in exactly one stylesheet/helper. CMD PR may still inline the canonical hex once in each venue if the shared sheet lands with the redesign — but values must not diverge; prefer extracting the shared sheet in or immediately after the CMD PR.

---

## 10. Suggested sequence

1. **CMD fix** (§2) — own commit/PR (playbooks + FCC colors + Set Lineup)
2. **Shared tokens sheet** (§9) if not landed in step 1
3. **Backend:** locks persistence + shot-weights preview endpoint
4. **Tile component** (§4) + tile states
5. **Enforced model** (§3) — inactive-row filter from day one
6. **PCC single-source** (§6) — delete `syncSelectionFromPcOrder`; drop sort
7. **Page layout** (§7) — tabs, rail, live shot-weights strip, D2 ready indicator
8. **Read-only venue filters** — FCC + Set Lineup `percentage > 0 || inPCC`
9. **SFX pass** (§8) — 8 remaining sites (sort dropped)
10. **Toast** replacing save-confirm modal
11. **Docs** — `Playbooks_Page.md` + this spec

---

## 11. Acceptance

- [ ] CMD reads identically on playbooks page, FCC tab, Set Lineup modal (blue/green/yellow, 40/70, `is-good`/`is-mid`/`is-low`)
- [ ] Motion/Set/Man/Zone always sum to exactly 100 — invalid state unreachable
- [ ] **Redistribution never assigns value to an `is_active: false` row** (drag Man 100→60; Box-and-One and Triangle-2 stay at 0)
- [ ] Man renders `= 100%` computed today; becomes a normal slider grid when a second man defense activates — **with no code change**
- [ ] Locked plays never drift; locks survive save/reload
- [ ] Raised slider visibly stops at `100 - lockedSum`
- [ ] `syncSelectionFromPcOrder` no longer exists; PCC badge derives from `pcOrder` index
- [ ] PCC cap 8/side; tiles pre-disabled at capacity
- [ ] 0%-in-PCC play survives redistribution and still shows in FCC / Set Lineup modal
- [ ] 0%-unassigned tile is dimmed but fully grabbable
- [ ] Shot-weights update from **server preview** on settle (not a JS port; not per-`pointermove`)
- [ ] SFX: assign/unassign, rail reorder/remove, selects, % commit, slider `pointerup` only, save toast — redistribution silent; sort SFX gone with sort
- [ ] `0 / 6 sections ready` is gone; D2 ready copy + save gates on the two normalize sections only
- [ ] Save success = `"Playbooks Saved"` toast; no save-confirm modal
