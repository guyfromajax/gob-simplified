# Implementation brief: Chapter 7 — Home Base + Reward Ladder

Paste this whole file into the agent. It is written for Claude Code or a Cursor agent working in `guyfromajax/gob-simplified` on branch `develop`.

---

You are implementing two things:
- **Home Base**, the pre-franchise hub. It replaces the legacy Mode Select entirely.
- **The Reward Ladder** in the management UI: the Office weekly card, one milestone modal template, the season-peak takeover, the end-of-season review, and the Trophy Case.

This chapter has no court or game-completion animation.

The spec is `_documentation_master/projects/design_handoff_ch7/`:
- `README.md` holds the decisions, new components, the reward-gold token, motion, the moment queue and **Data needed**. Read all of it first.
- `ch7.css` holds the new components only, built on existing tokens. Its last block, "Preview harness", is **not product code**.
- `frames/*.html` are static references. Open `index.html` to see every frame at 1280 and 1920. Query parameters for each frame are listed in the README.
- `frames/shell.js`, `frames/common.js`, `frames/hb.js` and `frames/moments.js` are preview scaffolding. **Do not port them.**

The system underneath is `_documentation_master/projects/design_handoff_browse_templates/` (`tokens.css`, `components.css`, `templates.css`) and `_documentation_master/11_Design_Systems/UX_System.md`.

## Step 0 — report before writing any code

Stop after this step and wait for my reply.

1. **Owning files.** List the HTML, JS, CSS and Python that own each surface today:
   - **Mode Select / Home Base:** `mode-select.html/.js/.css`, the slot list, Find Your Program, delete, Tutorials/Settings/FAQs, the Around The League cards, the leaderboard, Community Highlights, Find A Game, and the offline/desktop branch.
   - **Office:** `js/shared/officeHome.js`, `css/office-home.css`, and `BackEnd/utils/office_digest.py`.
   - **Every current pop-up:** `bigNewsModals.js`, championship moments, the conference/region modal, the region bye, walk-on welcome, the bracket reveal, the signed class (`recruiting_results_modal`), archetype establish/evolve, and the client chaining logic (`fccHasCompetingModal`, the Big News retry loop).
   - **Audio:** `uiSfx` / `playSfx` and the `sfx` channel.
2. **Data.** For every row under **Data needed** in the README, report whether the field exists. Give its name and source (API route, payload key or table). Mark each row **exists / exists under another name / missing**. Pay particular attention to the rows the README already marks MISSING or PARTIAL. Confirm or correct each one.
3. **Open questions.** Answer each of these, or say you can't find it:
   - Is there any last-played signal per franchise (`updated_at`, `last_played_at`, or the last CC write)? The green button depends on it.
   - Around The League `slots[]`: does each slot carry the **team slug** (needed for `<slug>_banner_card.webp`), **season**, **week**, and a **win flag or both scores**? Can a slot be identified as the current user's?
   - What is the `/api/auth/leaderboard` `top[]` limit? The design needs 12 rows at 1280 and 15 at 1920.
   - **Geek Points:** where is the per-game GP rule computed? Can it run for single-player/offline games without a server round-trip? Is GP stored per season anywhere?
   - Is anything stored per completed season today (record, finish, awards, class) that survives rollover?
   - Are consumed `pending_championship_moments` retained after dismiss?
   - Exceptional training gain: where does `training-report.js` get its `change-gold` threshold, and can `office_digest.py` apply the same rule server-side?
   - Where is "seen" stored for the weekly result, so the entrance and count-up play once?
   - Does the signed-class payload include `home_region`? Does the elimination payload include both teams' seeds?
4. **Plan the server work.** Some features need new stores. Propose the minimal schema and the write points, and say which ones touch `finish_season` or game finalize:
   - the moment queue
   - season reviews / top seasons
   - career GP
   - offline career mirror
   - milestones

   **Do not change finalize logic without my approval.**

## Hard rules

- **Never invent, derive or approximate a missing field. Stop and ask.** Specifically:
  - Don't pick the green slot by slot order.
  - Don't compute GP from wins on the client.
  - Don't count current slots as "programs" or "seasons".
  - Don't rank best players on the client.
  - Don't compute win % on the client.

  Where a field is missing, omit the element. Don't fill it.
- **Mock values are illustrative.** That covers team and coach names, records, ranks, scores, seasons and weeks, GP values, player names, stat lines, recruit names, RT letters, highlight and archetype copy, sample CTA labels, and the portrait placeholder. Initials stand in for headshots. Only structure, tokens and behaviour are the spec. Keep production copy where the README marks it *existing*.
- **Don't micromanage what already works.**
  - Keep existing CTA copy where it exists: Start Your Coaching Journey / Start Another Franchise, Find Your Program, Resume Game.
  - Keep existing column sets.
  - Keep the **RT ramp**, the **energy ramp**, the attribute tile tiers (`floor(raw/10)`), the **shot-weight colour scaling**, and the tier metals (`--tier-metal*`).
- **Colour law:**
  - **Green** goes on exactly one button per screen. On Home Base that is the last-played program's Enter, or Resume Game when that program has a game in progress; with no programs, nothing is green. In franchise it is the top-bar Advance only. Modals, the season peak and the review use `.btn-ghost`. Remove the shipped green championship CTA.
  - **Orange** does not appear in this chapter.
  - **Navy** only for "yours": your Around GOB card, your leaderboard row, your team in the bracket path.
  - **Blue** only on RT A and attribute 9+.
  - **`--reward-gold` (#F0C560)** is used only where the README's allow-list says:
    - milestone and season-peak surfaces
    - title medallions and title-finish text
    - the weekly exceptional-gain marker

    Never on buttons, never on everyday or weekly chrome, never on elimination.
  - W/L plates are white/outline, never green/red. Weekly ▲/▼ deltas are neutral.
  - Confetti is gold + white only, and only at the season peak. Remove it from the bracket reveal and the signed-class modal.
- **Layout:** Home Base fits 1280×720 and 1920×1080 with nothing below the fold, in every state, online and offline. The weekly card fits Office column 1 at 1280×720.
- **No new tokens** beyond `--reward-gold` and the motion durations in `ch7.css`. Port the classes into the codebase's own structure rather than linking the file wholesale.
- **Sound:** wire `SFX_WEEKLY_WIN`, `SFX_MILESTONE` and `SFX_PEAK` through `playSfx` on the `sfx` channel. The asset files don't exist yet. Leave the slots silent and don't substitute an existing sound.
- **Reduced motion:** every tier renders its final state, confetti isn't drawn, and sound still follows the audio settings.

## Build order (after I approve Step 0)

One PR each, in this order. Server PRs land before the UI that reads them.

1. **Home Base, online.**
   - New top bar and the two-zone layout.
   - Slot "doors", with `···` → Delete program… → confirm (Cancel focused, `.btn-del`).
   - Quiet Find Your Program.
   - Find A Game placard (`aria-disabled`).
   - **Around GOB ⇄ Leaderboard** tabs (`.hbt`): remember the last tab in localStorage, and show the new-results count from `gob_atl_last_visit`.
   - `.agc` cards, with banner art plus its blurred wash.
   - Remove Community Highlights from Home Base.
   - Rename the Around The League label to **Around GOB**. The endpoint name can stay.
   - The green button is blocked on last-played data. If that data is missing, ship with no green and tell me.
2. **Home Base, offline "Your Career".**
   - Career numerals (hollow → solid).
   - Trophy Case shelf with labelled empty medallions.
   - Top Seasons (up to 5, by season GP).
   - Same slots and green rule as online. No remote calls.
   - Depends on the server stores from Step 0.4. Render only the parts whose data exists.
3. **Office weekly card.**
   - `.wkc` replaces the Result and What moved cards: WIN/LOSS states, POTG or Team leader, the four badges, Training with the server-provided exceptional-gain flag, and the optional "Also" row.
   - The entrance plays once per result.
4. **Moment queue (server) + milestone modal.**
   - One ordered queue: at most 2 pop-ups per Office visit, the rest fold. The priority order is in the README.
   - Remove the client-side modal chaining.
   - `.mm` template with the signing class, walk-ons, bracket reveal, first archetype, region bye and elimination (`.is-quiet`).
   - Next/Done, × and Esc keep the remaining moments for the next visit. Mark each moment seen on dismiss.
5. **Season peak + end-of-season review + Trophy Case page.**
   - The title takeover queues the review as "2 of 2".
   - The review is written to the season store and shown on the Trophy Case page.

## Acceptance checks per PR

- Compare side by side with the matching frame at 1280×720 and 1920×1080.
- Home Base: test first launch, 1 program, 2 programs, a game in progress, and delete menu + confirm, both online and offline. Nothing is below the fold in any of them.
- Exactly one green button per screen. A grep of the new CSS for green, orange, navy, blue and `--reward-gold` finds only the allowed uses.
- The offline build makes zero network calls from Home Base.
- Keyboard:
  - tabs switch with arrow keys
  - the door is focusable, and Enter opens it
  - modals trap focus, with Enter = Next/Done and Esc = close
  - every control has a visible `:focus-visible` ring
- Reduced motion (`prefers-reduced-motion: reduce`) shows final states with no confetti.
- Worst-case data renders without overflow:
  - 12 Around GOB cards with the longest coach and team names
  - a full leaderboard
  - 5 Top Seasons
  - 5 trophies
  - a 3-player (1280) / 5-player (1920) Training block with two chips each
  - a queue of 2
- No console errors. Existing save, delete and resume behaviour is unchanged.
