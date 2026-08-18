# CURSOR BRIEF — Sim Broadcast Overlay (Act 2)

**Scope:** the presentation that plays after a user sims instead of playing turn-by-turn — the region below the live scoreboard on the court screen. Most players sim, so this is the most-seen screen in the game.

**How to read this brief.** The design half is settled and authoritative: geometry, states, cadence, copy source and motion are specified here and should be implemented as written. The data half is stated as **objectives and acceptance criteria only**. You have the codebase; I don't. Where this brief describes what the renderer needs, verify the actual payload, module boundaries and existing helpers yourself and implement to the repo's conventions. **Do not invent a data shape to satisfy a design detail — if something can't be sourced, flag it before building.**

---

## 1. The problem this replaces

The current build is a dashboard: every element on screen at all times, equal weight, updating continuously. Nothing changes priority, so a one-point thriller and a 39–70 blowout look structurally identical.

The fix is a **mechanism for emphasis, not more information.** The screen's job is choosing, not displaying. If the result is busier than today's build, it has failed.

The viewer is a coach watching orders he already gave — lineup, tempo, aggression, game plan, playbook — with no ability to intervene. The emotional payload is consequence, not surprise: *was I right?*

---

## 2. Reference artifacts (in this design project)

| File | Authoritative for |
|---|---|
| `Sim Broadcast - Mockup 1 Rest State.html` | Zone layout, locked geometry, resting state |
| `Sim Broadcast - Mockup 2 Cards.html` | Card system, live cadence engine, team stats panel |
| `Sim Broadcast - Mockup 3 Clutch.html` | Clutch frame mode and its gate |
| `sim-broadcast-frame.css` | Every measurement and token in the frame |
| `sim-broadcast-parts.js` | Board rows, worm, team panel, control cluster renderers |
| `sim-card-engine.js` | Selection weights, gates, cadence curve |
| `sim-moment-copy.md` | All card copy — ships as data |

The mockups drive themselves from a **synthetic event stream** standing in for real emitted turns. That stream is scaffolding: replace it, keep everything it feeds.

Each mockup has a harness below the frame with toggles and a measurement/cadence readout. Harness chrome is **not** part of the product — the 1280×720 frame is.

---

## 3. Zone contract

```
┌─────────────────────────────────────────────────────────┐
│  SCOREBOARD — existing, unchanged, always live  (120px) │
├───────────────┬───────────────────────┬─────────────────┤
│  BOARD        │   STAGE               │   BOARD         │
│  away five    │   worm + directed slot│   home five     │
│  never        │   the only thing      │   never         │
│  restructures │   that changes        │   restructures  │
├───────────────┴───────────────────────┴─────────────────┤
│  bench chips  ·  control cluster  ·  bench chips        │
└─────────────────────────────────────────────────────────┘
```

**All variability is confined to the stage.** That confinement is what makes emphasis read as emphasis. The boards are structurally identical every second of every game — bare numbers, no baselines, no annotations, no cards. Their job is "how are my guys doing": always available, never demanding.

### Locked geometry at the 1280×720 floor

| | |
|---|---|
| Overlay | everything below the 120px scoreboard = 600px tall |
| Overlay padding | 16 top / 26 sides / 12 bottom → inner 1228 × 572 |
| Zones row | 512px, then a 14px gap, then a 46px footer (512 + 14 + 46 = 572) |
| Columns | board 398 · **stage 400** · board 398, 16px gaps |
| Player row | 84px (62px portrait + breathing), 11px gaps, five rows + 16px board header = 491 of 512 |
| Stat bar track | 241px at this board width |
| Worm | 246px tall at rest; **302px in clutch** |
| Directed slot | **200px reserved at rest**, 144px in clutch |

Stage width 400 was chosen over 500 deliberately: at 500 the board falls to 348 and the bar track to 191px, at which point the bars read as state rather than motion. **The stage buys room vertically, not horizontally.**

Above 720p everything scales up; 720p is the floor that must fit, not the target.

---

## 4. Do not redesign

These work. They need re-placing into the new structure, not reinventing: the scoreboard · the worm's chart treatment · the four-bar stat display (PTS · REB · AST · DEF%) · portraits and RT badges · foul pips · hot/cold glyphs · the ◆ TOP marker · bench chips · the quarter-break card.

**Two rules that are easy to break by accident:**

1. **Team colour must be the resolved colour.** The display already picks primary or secondary per team based on which pops against the background. Every coloured element must consume that resolved value, never a raw primary: portrait borders, worm strokes and fills, tug fills, board headers, scoreboard edge. Two dark-primary teams facing each other is the case a naive implementation breaks on.
2. **RT badges use the existing 4-band scale, unmodified.** Where RT is missing, render the badge empty. Never guess a band.

---

## 5. State machine

Four states. The stage is the only thing that differs between them.

| State | Stage | Notes |
|---|---|---|
| **Rest — highlights** | Worm expanded (246px), slot reserved and empty | Default, and the majority of runtime |
| **Rest — team stats** | Worm 246px + team panel in the slot | User-selected; a **hold mode** (§8) |
| **Card** | Worm unchanged + one card in the slot | Interrupts rest; never resizes the stage |
| **Clutch** | Frame mode (§9) | Not a card |

**Rest must be genuinely restful.** If a card is always up, cards stop meaning anything. Because the slot is reserved at both sizes, a card arriving is a *content* change, not a layout change — nothing moves.

Default rest is **highlights**. The team panel should also take the slot automatically on natural lulls (the first several seconds after each quarter break, before cards resume), so the viewer has seen the tugs quietly a few times before one gets promoted. Manual selection overrides.

---

## 6. The worm

- Plotted on a **fixed game-length domain**: x is game progress, so the dot travels left→right and unplayed game remains as visible empty space with structure (zero line to the right edge, quarter ticks at 25/50/75%, a faint "now" rule at the dot).
- **Horizontal position must derive from elapsed game time, not from sample count.** Deriving it from sample count is the bug that put the dot at the right wall in the first minute.
- Axis labels: TIP · Q1 · HALF · Q3 · FINAL — they land where they say.
- Vertical scale auto-fits the largest margin so far. Clamped only in clutch.
- Caption is LEAD MARGIN + the leader's abbreviation and margin.

The fixed axis is load-bearing for clutch: **remaining game is remaining space**, which is how the end announces itself without a countdown gimmick.

---

## 7. The team stats panel

Fixed set, fixed order — shooting first, then how the points were manufactured, then possession:

| # | Stat | Bar points toward |
|---|---|---|
| 1 | FG% | greater |
| 2 | 3PT | greater |
| 3 | Points in the paint | greater |
| 4 | Fast break points | greater |
| 5 | Rebounding | greater |
| 6 | Turnovers | **more** — the bar marks the problem |
| 7 | Team fouls | fewer |

- **Every row is a tug**, including FG% and 3PT, both pulling proportionally toward the greater value. A rate's pull is naturally small (43.1 vs 47.6 is a ~5% edge, so a narrow bar) which is the honest result — don't rescale rates to make them look more decisive.
- **Turnovers point toward the team with MORE.** This is deliberate and it means the bar direction is not "who's winning this row" — it's "where the edge is." Label the panel accordingly; do not caption it "pulls toward better."
- **Bar direction and value emphasis are separate properties.** For turnovers the bar points at the team with more, while the white/emphasised value stays on the team doing better (fewer). Implement them as two independent flags per row — collapsing them into one is how a bad number ends up highlighted as if it were good.
- Team fouls still point toward fewer. **Known inconsistency:** the two negative stats now behave differently. That's an accepted call, not an oversight — don't "fix" it.
- **Team colour appears only in tug fills.** Values are white/dim — colour means "which way the bar pulled", nothing else.
- Values and bars update **live** as the game runs, with the existing 0.5s width transition. Patch values in place rather than rebuilding the panel, or the bars snap instead of easing.

---

## 8. Cards

One at a time, in the directed slot. Four types, **one label each** — the category word was dropped everywhere in favour of the specific one:

| Type | Label | Body |
|---|---|---|
| **Moment** | the stat kind (BUCKET, BOARD, DIME, 3PM, STREAK, 20…) | one line, e.g. `REYES 24 PTS` |
| **Run** | RUN | `FAIRVIEW 11–0` |
| **Margin** | the stat name (e.g. FAST BREAK) | the two values + the tug bar, promoted |
| **Context** | the setting chip (e.g. `AGGRESSION: HIGH`) | the outcome number + baseline sub-line |

- **Hold: 2.6s, every type, clutch included.** Entry is a 180ms transition (opacity + scale .985→1 + 5px rise); the settled state carries no transform. Exit is a fade.
- **Boards dim to brightness .72 under a card**, recovering in 180ms. Do **not** use the quarter-break blur — on a 2.6s card it reads as a modal you have to wait out.
- **Margin is not a separate component.** It is the same tug from §7 at higher emphasis, and it must be **whichever tug currently has the widest edge** — not a fixed stat. The promotion reads because the viewer has already seen that bar sitting quietly.
- **Context cards** juxtapose the coach's own setting against the outcome and make no claim. `AGGRESSION: HIGH` next to 11 team fouls. The viewer draws the conclusion. **Never assert causation. No win probability, no confidence numbers, ever** — counts, margins and multipliers are facts; a probability is a promise the sim can't keep.
- **Team stats is a hold mode:** while the user has the panel up, **all four card types are suppressed** and nothing queues. He asked for the numbers; taking them away is the one thing not to do. Switching back rejoins the live cadence. The quarter-break card is unaffected.

### Moment cards are stat readouts, not play descriptions

This is the design decision that makes Moments buildable: a Moment card states a **running total** off an emitted per-player delta — never a described play. No prose synthesis, no narrative feed.

---

## 9. Cadence

All values in seconds of playback. **Every gate curves across the game, not just the card-to-card gap** — tightening the gap alone changes nothing after Q1, because by then the rest floor, the per-player cooldown and event supply are what bind.

| Gate | Q1 | Q2 | Q3 | Q4 | Clutch |
|---|---|---|---|---|---|
| Card-to-card gap | 6.5 | 5.5 | 5.0 | 4.2 | 3.4 |
| Rest floor after a card | 1.6 | 1.3 | 1.1 | 0.8 | 0.5 |
| Per-player cooldown | 15 | 13 | 11 | 8 | 6 |
| Variety hold on headliners | 35% | 35% | 30% | 22% | none |
| Hold | 2.6 | 2.6 | 2.6 | 2.6 | 2.6 |

Selection: event weight (a three outranks a free throw) × player prominence, with a **1.6× boost for players under 8 points** and the variety hold above on anyone over 14, so the feed never becomes one player's channel. Milestones (10/20/30 points, 10 rebounds, double-double) jump the queue. Run fires on 8+ unanswered, ≥14s apart. Margin ≥26s apart. Context ≥30s apart.

Target outcome: roughly a dozen cards across the broadcast with a card up about a third of runtime, density climbing quarter to quarter. **Instrument this.** The mockup logs every fired and every suppressed candidate with its reason and reports measured per-quarter counts — that panel is how the weights get tuned, and something equivalent behind a debug flag will save days.

---

## 10. Copy

**`sim-moment-copy.md` is the source of truth for every line on a card.** One section per card type, one `-` line per variant, slots (`{NAME}` `{PTS}` `{REB}` `{AST}` `{FGM}` `{FGA}` `{LAST}` `{STREAK}` `{TEAM}` `{RUN}`) filled with live numbers. The engine picks one variant at random per firing.

- **Copy ships as data, never as code, and is never generated at runtime.** No LLM call on the sim path: latency plus fabrication risk, for zero benefit.
- Freshness is a file swap: online play fetches the current pack at session start; downloaded builds bundle one and pick up new packs on patch. Same mechanism, new content, no client update.
- Lines cap at ~34 characters before the type shrinks. Card lines render in an all-caps face.
- The design owner will keep editing this file. **Don't fork the copy into source.**

---

## 11. Clutch — a frame mode

**Gate: under 2:00 remaining AND margin ≤ 6.** Both conditions. A blowout with a minute left gets nothing — treating it as drama is how a broadcast loses credibility.

Four things change together over 600ms:

1. Worm vertical scale **clamps to ±8** (gate plus headroom, so a six-point game isn't pinned to the ceiling), making a single basket a visible swing.
2. Worm takes the stage: **302px**, slot down to **144px**, one line only.
3. Periphery darkens — vignette transparent across the middle 40%, reaching ~62% black at the corners, plus a hairline rule top and bottom in the leading team's resolved colour. **Every number keeps its contrast**; the drama is in the periphery and the scale, never in legibility.
4. **All analysis is suppressed** — no team panel, no Margin, no Context. Nobody wants a rebounding differential here. Moments keep firing at the tighter gap.

Supporting signals: axis labels fade out except **FINAL**; a **wall** line appears at the right edge; the worm caption switches to **ONE POSSESSION** (≤3) or **TWO POSSESSIONS** (4–6) — facts about the score, not predictions. Foul trouble is the one board element that gains emphasis (gold ring on the row), because it's the constraint the coach is living with.

**Nothing restructures.** Same five rows, same four bars, same slot position — the coach never has to re-find anything at the moment he can least afford to. The clamp applies **only** while engaged; disengaged frames revert to auto scale.

---

## 12. Motion and accessibility

Every transition in the design: card entry 180ms · board dim 180ms · stat bars and tugs 0.5s width · spotlight migration ~300ms · foul-out row swap ~350ms · clutch entry 600ms · quarter-break blur as built.

`prefers-reduced-motion` must be respected by everything new: no card entry animation, no pulses, instant value changes.

---

## 13. What you own — objectives, not instructions

I don't have the codebase; these are outcomes, and the implementation is yours to determine against what's actually there.

1. **A frame interface.** The renderer should consume playback frames — clock, score, on-court five per team, cumulative per-player line, DEF%, momentum glyph state, fouls, bench contents — not raw API shapes. Build the boundary; the renderer stays a renderer.
2. **The backend stays authoritative.** Where the renderer accumulates anything client-side to draw a frame, it is display state only, reconciled against emitted authoritative values at every boundary you have one, with the emitted value winning and the disagreement logged. A silent correction hides a real bug.
3. **Drive the existing scoreboard** from the same playback state — score, clock, period, fouls. Do not build a second score strip, and do not let the boards and the scoreboard tell different stories.
4. **Never interpolate a threshold value.** Anything that drives a binary (momentum glyphs, foul states) is step-held between emitted samples; interpolating manufactures transitions the backend never emitted. Interpolating a continuous stat between two emitted endpoints is fine.
5. **Sim times must not change.** The presentation is a renderer, not a second engine: no changes to sim logic, no expansion of the per-turn payload, no persisting turns.
6. **Verify every data assumption in this brief against the repo.** Anything I've described about availability, shape or timing is a design need, not a claim about your code. If a design detail can't be sourced from what the sim emits, say so and we'll change the design — don't approximate it, and don't stub it with random or seeded content that could survive to production.
7. **Debug instrumentation** for cadence (§9) behind a flag.

---

## 14. Acceptance

- Renders at **1280×720** with the geometry in §3 measured, not eyeballed: no zone taller than 512, no row overflowing 84px, budget 512 + 14 + 46 = 572.
- Rest is the majority of runtime; a card up roughly a third; density climbing by quarter, measured.
- Stage never changes size when a card arrives or leaves.
- Team stats suppresses all cards while held; nothing queues.
- Clutch engages only on both conditions and reverts cleanly, including the clamp.
- Worm dot position tracks game clock, not sample count — at 25/50/75% of the game it sits on the ticks.
- All copy sourced from `sim-moment-copy.md`; zero copy in source.
- Every coloured element consumes the resolved team colour.
- `prefers-reduced-motion` honoured throughout.

## 15. Anti-goals

No added information density. No annotating the boards — baselines and context live on the stage only. No interactive dashboard: the control cluster changes what you see, never what happens. No permanent feed — cards are events, rest is the default. No fake precision: no win probability, no confidence numbers. No synthesized play-by-play prose.
