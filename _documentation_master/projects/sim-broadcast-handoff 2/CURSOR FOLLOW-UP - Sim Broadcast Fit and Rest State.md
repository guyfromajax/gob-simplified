# CURSOR FOLLOW-UP — Sim Broadcast: fit, and the resting state

Reviewed the first implementation in situ. The frame, boards, type and colour all read correctly. Four fixes, in priority order. Same rules as the main brief: design details below are settled; anything touching data shape is yours to verify — don't approximate.

---

## 1. Fit the overlay to the available space — scale, don't stretch

The overlay is rendering at roughly its 720p authored size inside a much larger viewport, leaving a wide dead band below the bench rails.

**Scale the whole composition uniformly.** Treat the overlay's inner content box (1228 × 572 at the floor) as a fixed aspect frame and scale it to fit the available area, preserving aspect ratio, anchored to the top edge under the scoreboard. Cap the scale at about **1.6×** so portraits and type don't become cartoonish on very large displays; below the floor, never scale under 1.0 — the 1280×720 case is the minimum supported, not a target to shrink past.

**Do not** achieve this by letting the zone columns stretch or the rows grow independently. Stretching produces 250px stat-bar tracks while the 84px rows stay put, which both breaks the density relationships tuned at the floor and *still* leaves vertical dead space — five rows can't fill 900px without becoming a different design.

Everything inside the box keeps its authored measurements: stage 400, boards 398, row 84, slot 200, 16px column gaps. One scale factor, applied once, to the whole thing.

---

## 2. The resting slot must not read as an empty box

Right now the worm sits small at the top of the stage with a visibly bordered empty container below it. That is the exact failure mode the rest-state mockup tested and rejected — it reads as a component that failed to load.

At rest with highlights selected:

- The **worm expands to fill the stage** (chart 246 inside a 276 block at the floor), and
- The directed slot is **reserved but invisible** — no border, no background, no placeholder. Nothing was ever there, so nothing is missing.

When a card arrives, the worm gives back the reserved height in one move and the card occupies the slot. When the team panel is selected, the panel occupies that same reserved height. **The stage never changes size across any of the three cases** — only what fills the lower band.

Reference: `Sim Broadcast - Mockup 1 Rest State.html`, "Worm expands" treatment (the "framed" option in that mockup is the rejected one, kept only to show why).

---

## 3. Bench rails are clipping, and shouldn't be populated at tip-off

Both rails are cutting off chips mid-word — "Ellis Clemons 0p" truncated at the away board edge, the home rail truncated on its left.

- Cap at **3 chips per side** at this board width; overflow collapses to a single **+N** chip.
- Order most-recent exit first.
- **Hide the rail entirely when it's empty** — no BENCH label sitting alone.
- The rail's contents are *only* players who have logged court time and are not in the current five. With no rotation subs, the only route onto it is a **foul-out**: the outgoing player drops here with the red **OUT** marker and his replacement takes the same row with an **IN** tag. At 3:06 of Q1 with no foul-outs, both rails should be **empty and hidden**.

Whether the current chips are coming from real bench data or from something else is for you to confirm — but the display rule above is the design.

---

## 4. Worm needs a minimum vertical scale

Early in the game the auto-fit y-scale is amplifying a two-point dip into a cliff, which overstates what happened.

Apply a **minimum scale floor of ±6** — below a six-point maximum margin the chart holds a ±6 range rather than fitting tighter. Above that it continues to auto-fit as built. (Clutch's ±8 clamp is separate and unchanged: it applies only while clutch is engaged.)

---

## Explicitly not in scope for this pass

- **DEF% values and the blue-at-max treatment are fine as-is.** DEF% legitimately starts at 100% for many players, and the maxed state showing early is accepted. Leave both alone.
- The TIED caption on the worm at 2–2 is correct behaviour; don't change it.
