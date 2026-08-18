# CURSOR FOLLOW-UP 2 — the wide-worm restructure

Direction change after live testing. This **supersedes the three-zone layout** in the main brief (§3, §5, §6, §8) — the worm goes full width across the top, the three containers sit beneath it in a band, and the card system is replaced by small callouts pinned to the action point.

Reference: **`Sim Broadcast - Mockup 4 Wide Worm.html`** plus `sim-broadcast-wide.css`, `sim-broadcast-wide.js`, `sim-callout-copy.md`. Mockups 1–3 remain valid for anything not contradicted here (colour rules, motion, clutch gate, preserve list). Same rules as before: design below is settled; anything touching data shape is yours to verify — don't approximate.

---

## 1. New layout

```
┌───────────────────────────────────────────────────────────┐
│  SCOREBOARD — existing, unchanged                 (120px) │
├───────────────────────────────────────────────────────────┤
│  WORM — full width, compressed vertical scale     (242px) │
│  …with highlight callouts pinned to the action point      │
├──────────────────┬────────────────┬───────────────────────┤
│  AWAY LINEUP     │  TEAM STATS    │  HOME LINEUP  (256px) │
├──────────────────┴────────────────┴───────────────────────┤
│  bench chips  ·  HIGHLIGHTS toggle  ·  bench chips  (46px) │
└───────────────────────────────────────────────────────────┘
```

Locked at the 1228 × 572 inner box, scaled as **one uniform transform** exactly as you already implemented (clamped 1.0–1.6, top-anchored).

| | |
|---|---|
| Worm block | **242px** — 14 head + 4 + **208 plot** + 4 + 12 axis |
| Gap | 14px |
| Band | **256px** — columns **433 / 330 / 433**, 16px gaps |
| Gap | 14px |
| Footer | **46px** |
| Total | 242 + 14 + 256 + 14 + 46 = **572** ✓ |

The stage/slot concept is gone. There is no reserved card band any more.

---

## 2. The worm — full width, compressed height

**Horizontal:** the plot spans the full 1228px. Same fixed game-length domain as before (x is elapsed game time, never sample count), same quarter ticks at 25/50/75%, same axis labels TIP · Q1 · HALF · Q3 · FINAL, same wall at the right edge.

This alone resolves the early-steepness problem — the Q1 cliff you saw was ~34px of horizontal run for a two-point swing; at full width the same swing gets ~180px. **The converging y-floor from the previous addendum is withdrawn — do not implement it.** It's superseded by the fixed nonlinear scale below.

**Vertical — fixed and nonlinear.** Not auto-fit:

```
compress(m) = sign(m) * ( min(|m|, 10) + max(0, |m| - 10) * 0.20 )
y(m)        = mid - ( compress(m) / compress(45) ) * (mid - padY)
```

- Full resolution inside a **ten-point** game; each point beyond ±10 is worth **20%** of a point inside it.
- Domain is fixed at ±45 through `compress`, so **the same margin is always at the same height all game.** This is a deliberate change from auto-fit: a scale that re-fits under you makes shape incomparable across the broadcast.
- Draw faint dashed guides at **±10** so the change of slope is disclosed rather than hidden.
- Net effect: a two-point swing inside ten points moves the line ~11% of half-height; a 30-point margin sits only ~59% up, so blowouts flatten toward the top instead of stretching the chart.

We are deliberately **under-drawing blowouts.** That's the correct bias — the coach up 30 doesn't need drama, the one in a two-point game does.

Clutch is unchanged in its gate (under 2:00 **and** margin ≤ 6) and its other four behaviours, except that the ±8 clamp is now redundant — the fixed scale already delivers a tight endgame range. Keep the wall emphasis, axis fade to FINAL, and the ONE POSSESSION / TWO POSSESSIONS caption.

---

## 3. The three containers

Each is a pane: 10px padding, 12px radius, hairline inset, header line then content.

### Lineup panes (433px)

The row compresses from 84px to **40px**, which four stacked bars cannot survive — so the row is now **horizontal**, and the stat treatment you liked is the point of it:

```
[ portrait 34 ] [ identity — flex ] [ PTS ] [ REB ] [ AST ] [ DEF ]
                                      ↑ each cell 52px wide
```

- **Portrait** 34×34, 9px radius, RT badge top-left (existing 4-band scale, unmodified).
- **Identity** stacks two 
 lines: position + name + jersey (12px), then the status row (glyphs + foul pips + FOUL TROUBLE / OUT / IN tags) at 10px.
- **Stat cells:** the **value on top (13px bold, tabular) with a 40×3px progress bar beneath it.** Column labels (PTS REB AST DEF) live once in the pane header, not per row. Same maxima and same colour rules as before — green fill, blue at max, DEF% as a percentage.
- Row states carry over: spotlight glow for the top performer, gold ring for foul trouble, desaturation for fouled out.

### Team stats pane (330px)

As you've already implemented it — order FG% · 3PT · Pts in Paint · Fast Break · Rebounds · Turnovers · Team Fouls, every row a tug, turnovers pointing toward **more**, bar direction and white-value emphasis as **separate** flags. 26px rows. The pane is now permanent, so there is no toggle for it.

---

## 4. Highlights become callouts

**The card system is removed.** No 200px slot, no four card types, no board dimming, no Margin or Context cards on the stage. Replaced by a small pill adjacent to the worm's action point.

### Form

- Avatar + one line of text in a rounded pill, ~30px tall, hairline in the category colour.
- **Player highlights → headshot** (30×30, 9px radius).
- **Team highlights → a 38×30 tinted tile with the team's three-letter abbreviation**, 7px radius, filled with the team's resolved colour. There are no square team logos — all are horizontal, and letterboxing one at 30px makes it unreadable. The abbreviation reads at any size.
- **Text is sentence case in Inter, 13.5px semibold** — not Bebas caps. A pill beside the line is an aside, not a lower third. One number per line, bolded.

### Placement — follows the dot

- Anchored **16px to the side of the dot**, offset vertically to the **opposite side of the line's direction** so it never covers the stroke.
- **Flips to the left of the dot** when the dot is within a pill-width of the right edge.
- Clamped inside the plot box vertically.
- A **1px leader** in the category colour runs from the pill back to the dot, so the association is explicit.
- Entry is a 200ms opacity + scale (.94→1); the settled state carries no transform. Hold **2.6s**, then fade.

The rationale: the eye is already at the action point, so a callout there lands inside the existing gaze. That's the reacquisition cost the full-width card was charging.

### What earns one

**Special beats only** — routine events are **dropped, not queued**:

| Tier | Fires on | Avatar |
|---|---|---|
| Point milestone | crossing 10 / 20 / 30 | headshot |
| Ten rebounds | crossing 10 REB | headshot |
| Double-double | 10+ in two categories | headshot |
| Streak | 8+ straight points by one player | headshot |
| Run | 10+ unanswered by one team | abbr |
| Advantage | a team-stat edge reaching ±10 | abbr |
| Clutch bucket | go-ahead score while clutch is engaged | headshot |
| Foul-out | fifth foul | headshot |

Ordinary buckets, single rebounds, assists, cold shooting lines and non-critical fouls earn **nothing**. Minimum **9s** between callouts, plus per-tier cooldowns so one player can't repeat. Target ~**6–8 per broadcast** with something on screen roughly a fifth of runtime — instrument and measure this the way you did cadence.

### Copy source

**`sim-callout-copy.md`** — same contract as `sim-moment-copy.md`: one `###` section per tier, one `-` line per variant, slots filled with live numbers, `*asterisks*` for the bolded number, `avatar headshot|abbr` in the section header. Ships as data, never generated at runtime, editable without a code change. **`sim-moment-copy.md` is superseded for the overlay** — keep it only if the quarter-break card draws from it.

---

## 5. Footer

Bench chips on the outer edges exactly as fixed previously (name + points, three max, `+N` overflow, hidden when empty, OUT marker).

Centre holds **one control: a HIGHLIGHTS on/off toggle, default on.** The Highlights ↔ Team Stats switch is gone — team stats are permanent, so there is nothing to switch. Off suppresses all callouts and is the only way to get a fully quiet screen; keep it.

---

## 6. Acceptance

- Inner box measures **1228 × 572**: worm 242 + 14 + band 256 + 14 + footer 46, scaled by one transform, rows still 40px at 1280 / 1920 / 2560.
- Worm plot spans the full width; dot x tracks game clock — it sits on the 25/50/75% ticks at those points in the game.
- y-scale is fixed: the same margin renders at the same height at tip and at final. A 30-point margin sits nearer the ±10 guide than the top edge.
- A two-point swing inside a ten-point game is visible; a two-point swing in a 30-point game is nearly flat.
- Callout never covers the worm stroke, flips near the right edge, and its leader always terminates on the dot.
- Player highlights show a headshot; team highlights show the 3-letter abbreviation tile.
- ~6–8 callouts per broadcast, measured, with routine events dropped rather than queued.
- HIGHLIGHTS off silences every callout; no other stage control exists.
- All callout copy sourced from `sim-callout-copy.md`; zero copy in source.
- `prefers-reduced-motion` honoured on callout entry and all bar transitions.

## 7. Unchanged from the main brief

Resolved team colour everywhere · RT 4-band scale untouched · scoreboard drives from the same playback state · never interpolate a threshold value · no win probability or confidence numbers ever · no sim-time changes · boards carry bare numbers only, no baselines or annotations · quarter-break card keeps today's treatment and scope.
