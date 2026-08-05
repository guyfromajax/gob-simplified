# Prompt for the implementing agent

Paste this into Claude Code (or your IDE agent) with the `design_handoff_team_builder/` folder available in the repo.

---

You are implementing the **Team Builder** feature redesign in `guyfromajax/gob-simplified`, branch `develop`.

Read `design_handoff_team_builder/README.md` first, in full, before writing any code. It is self-sufficient: it documents seven screens with exact colors, type, spacing, copy, state and interaction behavior, plus the reasoning behind the flow's structure.

## What you are building

A restructured Team Builder flow, replacing the current five-step wizard:

```
Program Select → Ⅰ Claim → Ⅱ Identity → [Build mode gate] → Ⅲ Roster → Review → Establish
```

Seven screens. The README has a section per screen.

## Ground rules

**1. The HTML files in `design/` are design references, not production code.**
They are React-via-Babel prototypes. Recreate them in this repo's actual environment — vanilla JS + per-page CSS under `FrontEnd/static/`, following the patterns already used by `franchise-select-team.html`, `js/shared/teamPicker.js` and `mode-select.js`. Drop React and Babel entirely.

**2. Three files ARE production code — use them as-is, do not reimplement.**
- `js/shared/teamGeneratedArt.js` (banners, jerseys, marks) — already in the repo
- `js/shared/teamCourtGenerator.js` (courts) — already in the repo
- `design/tb-banner-variants.jsx` — **new** draw functions written to `drawChevronBanner`'s exact contract; port the four functions into `teamGeneratedArt.js`

An earlier prototype revision contained hand-written art generators. They disagreed with production in six documented ways and were deleted. Do not write independent art code.

**3. Two production changes are required.** Both are specified in the README's *Production changes required* section:
- Four banner draw functions + a stored `banner_variant` on the team, defaulting to `baseline`
- `insideWoodColor` on the court generator

**4. Fidelity is high.** Match the documented values. Where the README states a reason for a choice ("under-cap is neutral, not amber", "contain not cover", "a stepper not a slider"), the reason is load-bearing — don't optimise it away.

## Traps worth knowing before you start

These each cost a debugging cycle in the prototype:

- **Any offset that depends on chrome height must be derived from a measurement, never hardcoded.** Three separate bugs had this one cause. In production the prototype's review bar doesn't exist, so hardcoded offsets won't fail visibly in development and will be wrong in production. See *Sticky offsets*.
- **`--tx3` (3.29:1) is chrome only — never body text or data.** Caught five times in review. Treat it as a lint rule.
- **Court fields store tokens, not resolved hex.** Storing hex freezes the court when the palette later changes.
- **`RT` is the position rating at a slot. There is no overall rating anywhere in this product.** Don't introduce one.
- **Player display names must come from `/teams`, never derived from slugs** — `nameToTeamSlug` is lossy for internal capitals, periods and apostrophes.
- **The `ida` asset folder is uppercase on disk** (`images/teams/IDA/`) while its file stem is lowercase.

## Architecture constraints from the original brief

- **The client is a pure renderer for game rules.** Position ratings are server-computed and arrive on release; the UI shows a `recomputing…` state and never guesses.
- **Running totals over server-supplied values ARE allowed** and already shipped — height and year budgets are sums over values the client holds.
- **Build mode is written permanently when the program is established.** There is no path to change it afterwards. The gate and the Review eligibility block both say so in those words.
- **Court geometry is fixed.** Only the five color parameters and the hardwood style key vary.

## Open questions to resolve with the designer or product

Five are listed at the end of the README. Two block nothing but should be answered:
1. **Apply timing** — `SERVER_MS` in the establish sequence is a 2600ms placeholder.
2. **Conference membership** — the prototype derives it from place names; production must use `team.conference` from `/teams`.

## Suggested order

1. **Claim / Program Select** — the largest screen, and it grounds the league data model. It's also closest to what already ships.
2. **Build mode gate** — smallest, fully specified, no new data.
3. **Identity studio** — needs the two generator changes; do those first.
4. **Roster** — hardest. Budget arithmetic, the inspector, and the legality verdict.
5. **Review** — mostly composition over data you now have.
6. **Establish** — timing-dependent; needs the real Apply number.

Ask before deviating from a documented value. Ask before adding anything the README doesn't specify.
