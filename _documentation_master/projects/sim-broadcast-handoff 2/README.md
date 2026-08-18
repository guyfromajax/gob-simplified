# Sim Broadcast Overlay — design handoff

## Read the prompts in this order

The layout direction changed after live testing. Later documents win.

1. `CURSOR BRIEF - Sim Broadcast Overlay.md` — the foundation: problem, preserve list, colour rules,
   state machine, cadence, clutch, copy contract, acceptance, anti-goals.
2. `CURSOR FOLLOW-UP - Sim Broadcast Fit and Rest State.md` — uniform scaling, resting state,
   bench rails, worm scale floor.
3. `CURSOR ADDENDUM - Worm Early Scale and Bench Chips.md` — answers on early steepness and chip
   content. **Its converging y-floor is withdrawn by document 4 — do not implement it.**
4. `CURSOR FOLLOW-UP 2 - Wide Worm Restructure.md` — **current layout.** Supersedes the three-zone
   layout in document 1 (its §3, §5, §6, §8): full-width worm, three panes beneath, callouts
   replacing the card system.

Everything in document 1 that document 4 does not contradict still stands — colour resolution,
RT bands, motion, clutch gate, anti-goals.

## Mockups — open in a browser, they drive themselves

| File | Authoritative for |
|---|---|
| `Sim Broadcast - Mockup 4 Wide Worm.html` | **current layout**: wide worm, three panes, callouts |
| `Sim Broadcast - Mockup 3 Clutch.html` | clutch frame mode and its gate |
| `Sim Broadcast - Mockup 2 Cards.html` | superseded card system — kept for the cadence instrumentation pattern |
| `Sim Broadcast - Mockup 1 Rest State.html` | superseded layout — kept for the geometry measurement readout |

Each has a harness below the frame with toggles and a live measurement/cadence readout. **The harness
is not part of the product** — only the 1280×720 frame is.

Keep this folder **flat** (the mockups load shared files by relative path) and **serve it over HTTP**
rather than opening from `file://`, or the copy `.md` files can't be fetched and the mockups fall
back to their inline packs.

## Shared source

| File | What it is |
|---|---|
| `sim-broadcast-frame.css` | base frame tokens and measurements |
| `sim-broadcast-wide.css` | current layout: wide worm, panes, compact rows, callout pill |
| `sim-broadcast-parts.js` | scoreboard, worm, team stats panel, original board rows |
| `sim-broadcast-wide.js` | compressed worm, compact lineup rows, stats pane |
| `sim-card-engine.js` | event stream, team totals, cadence gates, clutch phase |
| `sim-callout-copy.md` | **current callout copy — edit this file, reload, done** |
| `sim-moment-copy.md` | superseded card copy; keep only if the quarter-break card draws from it |
| `sim-moment-pack.js` | fallback copy pack |

The mockups drive themselves from a **synthetic event stream** standing in for real emitted turns.
That stream is scaffolding — replace it, keep everything it feeds.
