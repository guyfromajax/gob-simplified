# Sim Broadcast Overlay — design handoff

Paste `CURSOR BRIEF - Sim Broadcast Overlay.md` into the IDE agent. Keep this folder alongside it
so the agent can open the mockups as reference.

## Open these in a browser (they are self-driving)

- `Sim Broadcast - Mockup 1 Rest State.html` — zone layout + locked geometry, live measurement readout
- `Sim Broadcast - Mockup 2 Cards.html` — card system + live cadence engine, decision log
- `Sim Broadcast - Mockup 3 Clutch.html` — clutch frame mode + its gate

Mockups 2 and 3 load the shared files by relative path, so keep the folder flat.

> **Card copy has moved.** `sim-moment-copy.md` is now canonical at
> `FrontEnd/static/sim-moment-copy.md` and is served by the app — edit it there. The copy that
> used to sit in this folder was deleted so the two cannot drift.
> Mockup 2 fetches `sim-moment-copy.md` relative to itself, so with the file gone it now falls
> back to `sim-moment-pack.js` (a designed fallback, not a break) and shows that pack's copy.
> To preview live copy edits in the mockup, drop a copy of the canonical file back into this
> folder temporarily — just don't commit it.

## Shared source

| File | What it is |
|---|---|
| `sim-broadcast-frame.css` | every measurement and token in the frame |
| `sim-broadcast-parts.js` | board rows, worm, team stats panel, control cluster |
| `sim-card-engine.js` | selection weights, cadence gates, per-quarter curve |
| `sim-moment-copy.md` | **all card copy** — now at `FrontEnd/static/sim-moment-copy.md` (canonical, served) |
| `sim-moment-pack.js` | fallback copy pack; the .md wins when reachable |

The mockups drive themselves from a synthetic event stream standing in for real emitted turns.
That stream is scaffolding — replace it, keep everything it feeds.
