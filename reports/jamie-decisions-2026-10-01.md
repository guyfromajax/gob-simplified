# Open design rulings for Jamie — 2026-10-01

Every design decision flagged across today's reports, consolidated. Each has the current
state (a 1280 screenshot or a cited current shot from today's reports), 2–3 options, and a
one-line recommendation. **No product code changed here** — mocks are test-only CSS overrides.
Answer the summary table at the bottom in one reply.

---

## 1. Navy for selected items / rows / picked plays
Navy (`--you` `#27408E`) is reserved for "yours." It is **not** currently used to mark a
*selected* row / picked play — selection is shown by neutral emphasis. Flagged on
`ux/set-lineup-tokens` (navy HELD pending your call).
Current: `reports/set-lineup-tokens/after-filled-1280.png` (lineup), `reports/playbooks-tokens/after-main-1280.png` (plays).
- **A.** Keep selection neutral (brighter surface + border); navy stays "yours"-only.
- **B.** Use navy fill/left-bar for the selected row / picked play across lineup, playbooks, orders.
- **C.** Navy only for "this is your team/row" identity; selection stays neutral (status quo, documented).
**Rec:** **A** — keep selection neutral; reserve navy for identity, so the two never blur.

## 2. Expected Shot Distribution / shot-weight / playbook CMD ramp (`getPswColor`)
`getPswColor(pct)` → `>35% #4A90D9 blue`, `21–35% #34EC27 green`, `11–20% #FFD700 gold`,
`<11% #ff6d6d red`. Blue is used on a **non-RT** quantity (shot %), but the law says "blue = RT
A/9+/elite only." Used in `common.js`, `set-lineup.js`, `playbooks.js`.
Current: `reports/team-builder-tokens/after-identity-1280.png` (shot-weight), `reports/set-lineup-tokens/after-ratings-1280.png`.
- **A.** Keep as a bespoke data ramp (blue/green/gold/red = shot share), exempt from the RT-blue rule.
- **B.** Drop blue for the top band (green = high share, neutral/gold below); reserve blue for RT only.
- **C.** Re-map to a single-hue intensity ramp (one colour, light→dark) — no law colours at all.
**Rec:** **A** — it's a self-contained data ramp; document the exemption (like the sim-broadcast palette).

## 3. Court live game-state colours (Playcall Center, reveal HUD, ribbons, active-player HUD)
Game-state is colour-coded: spotlight row/"TOP" **orange**, "FOUL TROUBLE" **gold**, timeout
**green**, quarter/shot-clock **gold**, active-player **has-ball gold** / "AUDIBLE!" `#4caf50`
green, playcall-reveal + lower-third team/state colours.
Current: `reports/jamie-decisions/r345-court-current-1280.png`, `reports/game-overlays-tokens/after-matchups-1280.png`.
- **A.** Keep as game-presentation data colours (like the sim broadcast); exempt, documented.
- **B.** Bring onto the law: neutralise the non-data accents (spotlight orange, audible green), keep genuine data (foul-trouble, momentum).
- **C.** Full re-map to a court-specific data palette spec.
**Rec:** **A** for this pass (spec-locked + ramp-adjacent); revisit as a dedicated court-data pass if desired.

## 4. Court side-panel surfaces: grey → navy
Panels use opaque legacy greys (`#1a1a1a` / `#333` / `#555`) with no 1:1 gob token (gob uses
navy surfaces + translucent whites). Flagged on `ux/court-chrome-2`.
Current vs mock: `reports/jamie-decisions/r345-court-current-1280.png` → `…/r345-court-mock-navy-neutral-1280.png` (top panels show navy surface).
- **A.** Keep the greys (status quo; no visual change).
- **B.** Migrate to gob navy surface tokens (`--surface-2`), matching the rest of the app.
**Rec:** **B** — migrate to navy surfaces for consistency (it's a small, contained change once approved).

## 5. Side-panel stat toggles (S1/S2/S3) in team colour
The selected stat-view toggle uses the **panel's team colour** (orange `#ff6200` for these
teams) — a choice control carrying team colour. Flagged on `ux/court-chrome-2`.
Current vs mock: `reports/jamie-decisions/r345-court-current-1280.png` (orange S1) → `…/r345-court-mock-navy-neutral-1280.png` (neutral S1, top panels).
- **A.** Keep team colour on the selected toggle (reads as "this team's view").
- **B.** Neutral selected state (choice controls are neutral per law); team identity stays in the name bar.
**Rec:** **B** — neutral selected toggle; the law says choice controls are neutral.

## 6. Senior-tribute title marks: orange vs neutral
`css/senior-tribute.css` paints the tribute title accents **orange**. It's a seasonal moment
(`seniorTribute.js`); no headless shot. Orange is otherwise "saved/committed."
- **A.** Keep orange (a warm seasonal flourish, deliberately off the everyday law).
- **B.** Neutral/`--reward-gold` (tribute = a reward moment, so gold fits the reward law).
**Rec:** **B (gold)** — a senior tribute is a reward moment; gold is the sanctioned reward colour.

## 7. Recruiting presence dot: orange
The recruiting presence/status dot renders **orange**. Current: `reports/recruiting-tabs/passive-pool-1280.png`.
- **A.** Keep orange as a status accent.
- **B.** Neutralise (status codes are neutral per law) or use green only if it's "positive/active" data.
**Rec:** **B** — neutral dot (or green if it strictly means "active"); orange is reserved for saves.

## 8. Big-news / milestone modal: gold button
The milestone/"big news" modal's primary button reads **gold**. Current: `reports/milestone-modal/first-archetype.png`.
- **A.** Keep gold (milestone = reward surface; gold is lawful there).
- **B.** Neutral button (the modal body carries the reward gold; the CTA is just "OK/Continue").
**Rec:** **A** — gold is lawful on a reward surface; keep it (it's a milestone, not an everyday save).

## 9. Submit Training green + Save buttons orange at rest
"Submit Training" is **green** (Advance); Save/Submit-Orders buttons are **orange** at rest
(committed). Current: `reports/prep-training-tokens/after-in-season-1280.png`.
- **A.** Keep: green = the one Advance, orange = save/commit (matches the colour law exactly).
- **B.** Orange only *after* a change is pending; neutral at rest (orange = "there is something to save").
**Rec:** **A** — this already is the law (green Advance, orange save); confirm and move on.

## 10. Duplicate pages: homepage-v3 vs homepage, play-builder v2 vs v1 (delete?)
Two live copies of each exist. Current: `reports/jamie-decisions/r10-homepage-1280.png` vs
`…/r10-homepage-v3-1280.png`; `…/r10-playbuilder-v1-1280.png` vs `…/r10-playbuilder-v2-1280.png`.
- **A.** Pick the canonical of each (likely `homepage.html` + `play-builder-v2.html`) and **delete** the other + its refs.
- **B.** Keep both (if one is an A/B or a staging source like `homepage-v3-source.html`).
**Rec:** **A** — confirm which is canonical, then delete the dead twin (a follow-up cleanup task).

## 11. Desktop app icon (1024×1024)
`desktop/build/` has only `README.md` — **no `icon.icns` / `icon.ico` / `icon.png`**, and no
≥512px square brand mark exists in the repo (don't invent one). `npm run pack` falls back to
Electron's default icon.
- **A.** You provide a ≥512px (ideally 1024×1024) **square** brand source; we generate `icon.icns/.ico/.png`.
- **B.** Ship with Electron's default icon for now (defer branding).
**Rec:** **A** — provide the square source; the desktop build should carry the brand mark.

---

## Summary — answer in one reply

| # | Ruling | Options | Rec |
|---|---|---|---|
| 1 | Navy for selected rows/plays | A neutral · B navy-select · C status quo | **A** |
| 2 | Shot-weight ramp blue on non-RT (`getPswColor`) | A keep ramp · B drop blue · C single-hue | **A** |
| 3 | Court live game-state colours | A keep (data) · B neutralise accents · C re-map | **A** |
| 4 | Court side panels grey → navy | A keep grey · B navy surfaces | **B** |
| 5 | Stat toggles in team colour | A keep team colour · B neutral selected | **B** |
| 6 | Senior-tribute title orange | A keep orange · B gold/neutral | **B (gold)** |
| 7 | Recruiting presence dot orange | A keep orange · B neutral/green | **B** |
| 8 | Big-news modal gold button | A keep gold · B neutral CTA | **A** |
| 9 | Submit Training green + Save orange | A keep (is the law) · B orange-when-dirty | **A** |
| 10 | Duplicate homepage / play-builder | A pick one, delete twin · B keep both | **A** |
| 11 | Desktop 1024 app icon | A you provide square source · B default icon | **A** |

Shots: fresh ones in `reports/jamie-decisions/` (rulings 3/4/5/10); the rest cite current shots
from today's reports. Nothing here changes product code.
