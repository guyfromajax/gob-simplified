# Chapter 7 PR 4 — Milestone modal template

Branch `app/milestone-modal` off `origin/develop`. One `.mm` pop-up for every MILESTONE-tier kind in `moments_for_this_visit`, played by `momentQueue.js` from the server queue v2. The client does not rank, style, or invent fields.

The Chapter 7 design handoff is on `develop` (`_documentation_master/projects/design_handoff_ch7/`). This branch merged `origin/develop` before the fix pass. Frame markup is the spec; `ch7.css` (milestone block, not the Preview harness) is the CSS source of truth.

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

- Header: moment-type eyebrow, dots plus “N of M” from `moments_for_this_visit`, ×.
- Footer: “Up next · \<type\>” or a follow-on link, plus one `.btn-ghost` (Next / Done) with an Enter keycap.
- Next / Enter steps with out/in motion. Done closes the last item. × / Esc / scrim closes the current item; the rest stay eligible for the next visit.
- Seen is PATCHed only for moments that were shown.
- Focus trap; focus returns to the previously focused node.
- Gold: scrim fade, dialog rise, gold rule draws, body stagger, `playSfx(item.sting)` at 200ms (`STING_MILESTONE` when the server says so).
- Quiet: fade only, no gold rule / diamond / medallion, no sound.
- Reduced motion: final state, no rule animation; sting still follows audio settings.

## Colour law (computed)

Gold (`--reward-gold`) is only the 2px top rule, the `.mm-k::before` diamond, and `.med.gold` on the archetype variant. Buttons, dek, and elimination carry none. Navy is `.me` on your team in the bracket path. RT uses the existing ramp (A blue, B green). No green / orange chrome. No confetti at this tier.

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

## Fix pass

Merged `origin/develop` on `app/milestone-modal` (handoff commit `962d38621`). Read decisions 21 / 23 / 24, the Moment queue behaviour, and the Milestone rows of the Motion table. Ported the `ch7.css` milestone block into `milestone-modal.css` (scrim `position:fixed` so it covers the live Office; Preview harness left out). Rewrote the mount to the frame DOM: `.mm-k` / `.mq` (dots **plus** “N of M”) / `.mm-t` / `.mm-d` / `.mm-f` / `.mm-nx` / `Next|Done` + `<kbd>Enter</kbd>`.

Kept the first-pass behaviour: gold / quiet split, no confetti, seen PATCHes only for shown items, queue abort on × / Esc, `playSfx(item.sting)` at 200ms, focus trap and restore, reduced motion final state.

### Template vs frames (1280×720)

Opened every file listed here after retaking.

| Live | Frame | Side-by-side |
|---|---|---|
| `signed-class.png` | `frame-signing.png` | `compare-signing.png` |
| `bracket-reveal.png` | `frame-bracket.png` | `compare-bracket.png` |
| `elimination.png` | `frame-elim.png` | `compare-elim.png` |

Also opened: `walk-ons.png`, `first-archetype.png`, `region-bye.png`, `signed-class-1920.png`, and `frame-archetype.png` (signing queue, press Next).

**Signing.** Hairline `.rc` rows (not boxed cards). Header is dots + “1 of 2”. Footer is “Up next · Walk-ons” and Next with the Enter keycap. The extra “N signed.” line is gone; the dek already says it. Remaining: the frame’s five Lawrence names and “Region B” labels are sample copy; live rows are the fixture (`Dee Prospect` / `Marcus Vane`, `home_region` left as stored `B`, Marcus omits region and potential because the payload does). The live Next control is the product `.btn-ghost` (taller pill) rather than the frame’s preview ghost.

**Bracket.** `.seed-n` is the numeral + “Seed”, not “2 your seed”. `.mu` shows Round 1 (navy `.me` on Lancaster) and Round 2 as “Winner of” the other first-round pair. Remaining: the frame invents a Round 3 “Region B, top half” row and a “Region B” place name. Reveal payloads clear `round2` / `final` (`_sanitize_bracket_for_reveal`), so that third row is omitted. Title is “You’re in: 2 seed, Conference” from `tier`, and the dek is the payload `eyebrow` (“Conference Tournament · Weeks 27–29”), not the frame’s Lawrence sentence. Live shows “1 of 1”; the frame hides `.mq` when the queue is one item.

**Elimination.** `.fin` scoreboard + `.mm-sum` (record / 2nd / #11). Quiet: no gold rule, no diamond, no sting. Remaining: the frame’s `#3` / `#2` seed lines, “Conference A2”, and “Signing Day is Week 35…” sentence are sample. This payload is a region loss, so seeds are absent and not invented; conference place is the number only.

**Archetype.** Live `.arch` + `.med.gold` “P” and the Pure Offense manifest sentence match the frame’s Systems Coach layout (gold letter medallion, copy in the plate, Done + Enter). Remaining: live is a one-item visit so the footer is “Explore archetypes”; the frame’s 2 of 2 has no follow-on link. Copy is the real `GOBArchetype.descFor`, not the frame’s Systems Coach paragraph.

### Gate counts (this pass)

- Relevant Playwright (`milestone-modal`, `moment-queue`), `--workers=1`, `PORT=8172`, `CI` unset: **18 passed**.
- `pytest --ignore=tests/e2e`: **4063 passed, 16 skipped, 109 xfailed, 1 xpassed, 0 failed.**
- Full `tests/e2e` once, `--workers=1`, `PORT=8173`, `CI` unset, no other Playwright run: **684 passed, 3 skipped, 1 failed** (11.2m). The failure is `navigation-fixes-3` “recruiting and cut-players exits…” — 60s timeout / browser closed on the last test of the run, not a milestone assertion. Isolated retry of that test on `PORT=8174`: **passed** (9.8s).

STATUS: COMPLETE
