# Senior Tribute — design handoff

Approved redesign of the Senior Tribute (FCC → Go To Next Season). Direction: **Last Page**.
Two other directions were explored and retired (Rafters, Spotlight).

## Suggested repo location

    _documentation_master/projects/senior-tribute-handoff/

Matching `design_handoff_roster_attribute_tiles/` and `sim-broadcast-handoff/`.

## Contents

| File | What it is |
|---|---|
| `CC Prompt - Senior Tribute.md` | **Start here.** The implementation prompt — paste into the IDE agent. Discovery-first: it must report the owning files and which data fields actually exist before writing code. |
| `Senior Tribute - Last Page.html` | The hi-fi prototype. Open it in a browser — it plays the real 6s sequence. |
| `senior-tribute-hifi.css` | All styles. Production CSS should be ported from here, not re-derived. |
| `senior-tribute-hifi.js` | Sequence, staggered entrances, portrait FLIP into the resolution card, reduced-motion path, state dock. Lift `renderSlide` / `renderRes` / `flip`. |
| `art/tribute/*.png` | **Stand-in portraits only** — cut out of screenshots. Production serves transparent PNGs via `API_CONFIG.getPlayerImageUrl(id, {size})`. |
| `fonts/` | Bebas Neue Pro, so the prototype renders standalone. |

## Driving the prototype

Review dock, bottom right (prototype-only, not part of the design):
class size **1 / 5 / 12** · titles **none / all four** · name **typical / longest** ·
portrait **served / missing** · motion **full / reduced** · restart (`R`) · resolution (`E`).

## What the IDE agent must not change

The 6s hold, no skip/pause, the trigger and confirm modal, the music wiring, `teardown()`,
the FCC background `finish-season` handoff, `onAdvance`, RT ordering, the CTA copy, the
title label strings, and existing payload field names. Details in §7 of the prompt.

## Fixture values are illustrative

Names, jersey numbers, PPG/RPG/APG/DEF%, games and career points are invented for the mock.
The career sentence ("… four seasons in a Knights uniform") is a sample of the shape — the
prompt tells the agent to drop the seasons clause rather than derive it if no such field
exists.
