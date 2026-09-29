# Chapter 7 PR 4 — Milestone modal template

Branch `app/milestone-modal` off `origin/develop`. One `.mm` pop-up for every MILESTONE-tier kind in `moments_for_this_visit`, played by `momentQueue.js` from the server queue v2. The client does not rank, style, or invent fields.

The design-handoff folder (`_documentation_master/projects/design_handoff_ch7/`, `ch7.css`, `frames/milestone.html`) is not in this repo or a sibling tree. Class names, motion, and the gold / quiet split follow the task brief, UX_System §10, and `reports/weekly-queue-v2-2026-09-29.md`.

## Old chromes replaced (queue path only)

| Kind | Was | Now |
|---|---|---|
| `signed_class` | (new; Signing Day hub reveal unchanged) | `.mm` calm recap |
| `walk_on_welcome` | Sammy `WalkOnWelcomeModal.showFromQueue` | `.mm` |
| `bracket_reveal` (in the field) | `BigNewsModals.showBracketReveal` (confetti) | `.mm` path + seed; no confetti |
| `region_bye` | Sammy `RegionByeModal.showFromQueue` | `.mm` with the existing Sammy copy |
| `conference_rs_region` | Sammy `ConferenceRsRegionModal.showFromQueue` | `.mm` with the existing Sammy copy |
| `first_archetype` | `archetypeReveal.js` auto-open on FCC | `.mm`; FCC auto-open disabled |
| `elimination` | (new) | `.mm.is-quiet` |

Championship and `season_review` stay on their current path (`ChampionshipMoments` / no-op until the season-peak PR). WEEKLY kinds stay on the Office weekly card. Each kind keeps its existing seen PATCH. Elimination uses `PATCH /franchise/elimination-seen`. `PATCH /franchise/season-review-seen` is wired for the later PR and is not called from this template.

## Variant data sources and omissions

| Kind | Payload | Rendered | Omitted (not invented) |
|---|---|---|---|
| `signed_class` | `signed_class` → `career_data.class_signed` | Square initials, name, position, `home_region` if present, RT now → potential, count | Marcus Vane has no region and no potential |
| `walk_on_welcome` | `walk_on_welcome_modal.walk_ons` | Same row chrome; `pos` / `rt` / `potential_rt` aliases | Attributes, year, height, weight (not in the milestone row) |
| `bracket_reveal` | `bracket_reveal_modal` + FCC name map | `eyebrow`, your seed (navy chip), first matchup and path | Empty final slot (no opponent); `layout` is `"full"` / `"compact4"`, not a copy object |
| `region_bye` | `region_bye_modal_eligible` (boolean) | Existing Sammy paragraph | No extra facts on that payload |
| `conference_rs_region` | `conference_rs_region_modal` | Existing copy; `lost_round` picks the last sentence | — |
| `first_archetype` | `first_archetype.archetype` | `GOBArchetype.nameFor` / `descFor` / badge; Explore link | `descFor` of `TBD` is dropped; fallback is the old reveal sentence |
| `elimination` | `elimination` | Score, `round_name`, `record`, conference place, national rank | Region seeds (`user_seed` / `opponent_seed` absent on a region loss) |

## Behaviour

- Header: moment-type eyebrow, N of M dots from `moments_for_this_visit`, ×.
- Footer: “Up next · \<title\>” or the archetype follow-on link, plus one `.btn-ghost` (Next / Done).
- Next / Enter steps with out/in motion. Done closes the last item. × / Esc / scrim closes the current item; the rest stay eligible for the next visit.
- Seen is PATCHed only for moments that were shown.
- Focus trap; focus returns to the previously focused node.
- Gold: scrim fade, dialog rise, gold rule draws, body stagger, `playSfx(item.sting)` at 200ms (`STING_MILESTONE` when the server says so).
- Quiet: fade only, no gold rule / diamond / medallion, no sound.
- Reduced motion: final state, no rule animation; sting still follows audio settings.

## Colour law (computed)

Gold (`--reward-gold`) is only the 2px top rule, the eyebrow diamond, and the medallion on `.is-gold`. Buttons, dek, and elimination carry none. Navy is the your-seed chip and the your-team name in the path. RT uses the existing ramp (A blue, B green). No green / orange chrome. No confetti at this tier. The Pure Offense badge is the existing GOBArchetype SVG (offense lean is orange in the icon file, not modal chrome).

## Screenshots (1280×720, one 1920)

Each file below was opened and checked:

- `reports/milestone-modal/signed-class.png` — 1 of 2, Next, recruit rows, omitted Marcus fields
- `reports/milestone-modal/bracket-reveal.png` — seed 2 navy, Kingsport / Lancaster, Done, no confetti
- `reports/milestone-modal/walk-ons.png` — Ellis Clemons, RT pair, Done
- `reports/milestone-modal/first-archetype.png` — Pure Offense + manifest copy + Explore link
- `reports/milestone-modal/region-bye.png` — existing bye paragraph
- `reports/milestone-modal/elimination.png` — quiet, score 58–66, no gold, no seeds
- `reports/milestone-modal/signed-class-1920.png` — same recap on the 1920 Office

### Differences vs `frames/milestone.html`

The frame file is not in the repo. Versus the brief / class list:

- The live modal sits over the real Office, not a bare frame stage.
- Queue dots are the visit list, not a hard-coded 3-up preview.
- Bracket is seed + first matchup, not the full Style A bracket grid (the old Big News chrome).
- Walk-ons are rows, not the wide Sammy roster table.
- Region-bye / conference copy is the existing Sammy text, not frame lorem.
- Elimination has no gold rule, matching the quiet row.

## Gate counts (UX_System §8)

- `pytest --ignore=tests/e2e`: **4052 passed, 16 skipped, 109 xfailed, 1 xpassed, 0 failed.**
- Playwright: relevant specs first (`milestone-modal`, `moment-queue`) **18 passed**. Full `tests/e2e` once, `--workers=1`, `PORT=8168`, `CI` unset, started with no other Playwright run: **656 passed, 3 skipped, 0 failed** (9.8m).

STATUS: COMPLETE
