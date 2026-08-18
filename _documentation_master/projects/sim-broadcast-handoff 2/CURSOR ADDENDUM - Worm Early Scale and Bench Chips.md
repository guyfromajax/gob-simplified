# CURSOR ADDENDUM — worm early scale, and bench chip content

Three answers to your report. Good catches on all of them.

---

## 1. The 302 was my error — your implementation is right

302 is the **clutch** chart height (302 chart + 144 slot), and I carried it into a rest-state instruction by mistake. At rest the numbers are exactly what you measured: **block 276 · chart 246 · slot 200**. You implemented the property — the worm fills the stage — which is the correct reading and reproduces the reference. Nothing to change; the source brief has been corrected.

---

## 2. Early steepness — converge the y-scale, keep the x-domain fixed

Your arithmetic is right and the diagnosis is right: ~76px of rise over ~34px of run is near-vertical no matter how gentle the y-floor is, because the run is fixed by elapsed time.

**Do not touch the x-domain.** A growing or right-anchored domain is the one change I'd refuse: it makes the same 11–0 run occupy different widths at different times, so shape stops being comparable across the broadcast, and it destroys "remaining game is remaining space" — which is what signals the end without a countdown, and what clutch is built on.

**The fix is a y-scale that starts wide and converges.** Instead of a constant floor of ±6, make the floor a function of elapsed game progress, easing from wide at tip to ±6 by the end:

```
floor = 6 + 12 * (1 - progress)        // progress = elapsed game time / full game, 0→1
                                        // tip ±18 · end of Q1 ±15 · half ±12 · end of Q3 ±9 · final ±6
```

Auto-fit still wins whenever the real margin exceeds the floor — this only sets the minimum range. Effect at the frame you saw: a ±2 margin at 3:06 of Q1 draws ~17px of travel instead of ~39px, roughly halving the slope, and the line reads as an early wobble rather than a cliff.

The rationale is honest rather than cosmetic: **early margins genuinely matter less**, and a chart that starts zoomed out and tightens as the game commits says exactly that. It's also consistent with the y-axis already being adaptive, so it introduces no new kind of behaviour — and it hands the clutch clamp (±8, engaged-only) a natural landing point rather than a jump.

Exact constants are tunable; the shape — wide at tip, ±6 at final, auto-fit overriding both — is the design.

---

## 3. Bench chips — keep names whole, drop the rebound stat

Keep the **name intact and the points**; drop the `· Nr` rebounds. Don't ellipsis a name and don't shrink chips conditionally.

Reasoning: the chip exists so a player who left the floor doesn't vanish — that's an identity job first, so the name is the payload and truncating it defeats the chip. Points are the one number that carries at chip size. Rebounds are a nice-to-have that costs a name, and conditional shrinking makes the rail's density change with roster events, which is the kind of quiet instability the whole design is trying to remove.

So: `NAME · Np`, plus the red **OUT** marker where applicable, three chips max, `+N` overflow, rail hidden when empty. Fixed treatment at all times, no responsive variants.
