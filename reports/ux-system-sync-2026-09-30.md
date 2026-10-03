# UX_System.md + CLAUDE.md sync — 2026-09-30

Branch `docs/ux-system-sync` off `origin/develop`. **Docs only, no code changed.**
`check_migration_gates.py`: passed (Gate A 0/0, Gate B 136/44 — unchanged). Every item
below was verified against the code on develop, not just copied from a report.

## UX_System.md — sections changed

| Section | Old → New (short) | Source (report / code) |
|---|---|---|
| §15 Team attributes (rows) | "always **twelve** rows … Character: Chemistry, Fight, Discipline, **Momentum**" → "**eleven** rows … Character: Chemistry, Fight, Discipline. Momentum omitted from `measures[]`, stored-snapshot only" | `_MEASURE_FAMILIES` in `BackEnd/utils/office_digest.py` (11 entries; comment 340-343); `test_team_attribute_measures.py`; `reports/training-report-no-momentum-2026-09-30.md` ("Team Attributes GRID_ROWS: Already the same 11") |
| §15 field rows | "the **twelve** measures"→"**eleven**"; signed_scale "other **four**"→"**three**" + dropped Momentum from percentile-bar list; meter_pct "other **eleven**"→"**ten**"; direction "all **eleven** others"→"**ten**" | same as above |
| §15 radar grid | "the **four** character measures on the bottom row" → "the **three** character measures (Chemistry, Fight, Discipline)" | same |
| §10 `moved_most` field | added: server can emit a `momentum_score` row; the Office drops it before the top-two render (never shown) | `FrontEnd/static/js/shared/officeHome.js:1067-1071`; `reports/logout-429-office-2026-09-30.md` §3 |
| **New "Colour law" section** (after §1) | added the full law in one place: green (Advance + positive data), orange (saved/committed), navy (yours), blue (RT A/9+/elite), reward-gold allowed surfaces, choice controls neutral, W/L plates white/outline, deltas neutral (▲ t100 / ▼ t60), no wash on the weekly card, information codes neutral, and the `/* colour-law: positive-data\|committed\|saved\|reward */` convention | task spec + `scripts/check_ui_tokens.py` docstring (lines 25-42) and `NEW_DESIGN_CSS`/`REWARD_SELECTOR_RE`; `reports/names-recruit-colour-2026-09-29.md`, `office-weekly-card-2026-09-29.md`, `recruiting-hub-tokens-2026-09-30.md`, `signing-orders-panel-2026-09-30.md`, `reward-gold-sfx-2026-09-29.md`, `season-peak-trophy-case-2026-09-29.md`, `milestone-modal-2026-09-29.md` |
| §3 Audio | added: one sound per action (data-sfx **xor** playSfx, `__gobSfxCalls` spy); Advance reserved for `#play-now`, page primary → `SFX_COMMIT`; everything through `playSfx`+settings (bare `new Audio()` is a bug); losses silent; `STING_WIN` win-first-showing only; stings server-named, new sting stops previous, follow settings under reduced motion, early close doesn't cancel | `reports/ch8-ci-tokens-sfx-2026-09-30.md`, `reward-gold-sfx-2026-09-29.md`, `prep-scouting-speed-sfx-2026-09-30.md`, `office-weekly-card-2026-09-29.md`, `milestone-modal-2026-09-29.md`; `FrontEnd/static/js/shared/uiSfx.js:14-19` (catalog `.wav`) |
| §8 UI-tokens gate | replaced the short allow-list note with the full new-design surface list, and changed the gate command to `--strict --no-write` (CI job) | `scripts/check_ui_tokens.py:15-42, 226-236`; `reports/ch8-ci-tokens-sfx-2026-09-30.md` (CI job), `ui-token-audit-2026-09-29.md`, `recruiting-hub-tokens-2026-09-30.md` |
| **New §16 Cross-cutting rules** | one measure vocabulary / no Momentum on the 3 team-measure surfaces; team names shown as stored; `API_CONFIG.logout()` + `fetchWithRateLimitRetry`; Scouting reads FCC (never `play-next-game`); Prep views are in-app modules, `prepEmbed.js` retired → `viewLoader.js`; surfaces outside `FrontEnd/static`; fcc-css freeze **pending**; lessons (shell class names, computed-style guards, BEFORE shots) | see per-item citations below |

### §16 per-item sources (all verified in code)

- **Logout / retry** — `FrontEnd/static/js/config/api-config.js` (`logout()`, `fetchWithRateLimitRetry`, `RATE_LIMIT_DEFAULT_RETRY_SECONDS=6`, `RATE_LIMIT_MAX_RETRIES=5`); desktop exempt at `BackEnd/utils/rate_limiter.py:122-124`. `reports/logout-429-office-2026-09-30.md`.
- **Scouting / play-next-game** — `BackEnd/api/api.py:5716-5725` (`_maybe_reconcile_region_for_eos` call), `6838-6892` (the write); front-end reads `commandCenterTopDataCache.next_game_summary` / `office_digest.next_game`. `reports/prep-scouting-speed-sfx-2026-09-30.md` §1.
- **Prep modules / viewLoader** — `FrontEnd/static/js/shared/views/viewLoader.js` (exports `ensureCss`, `loadScript`, `ensureFranchiseMode`); `prepEmbed.js` absent, zero importers. `reports/retire-prep-embed-2026-09-30.md`, `prep-modules-2026-09-29.md`. (§14 already documented `init(root)`; §16 adds the retirement + helper move.)
- **Team names as stored** — `reports/names-recruit-colour-2026-09-29.md` (`TEAM_NAMES` / `titleCaseName` removed; IDA / Bentley-Truman / Seattle AAA verified).
- **Coverage note** — `reports/coverage-gap-check-2026-09-30.md`.
- **Lessons** — `reports/signing-orders-panel-2026-09-30.md` (`.rail`→`.srail`), `prep-modules-2026-09-29.md` (computed-style guards, `*_BEFORE=1` shots), `training-report-no-momentum-2026-09-30.md` (`.rc` leak / computed guard).

## CLAUDE.md — changed

| Where | Added |
|---|---|
| Frontend | "If you change or rely on a UI rule that isn't in UX_System.md, update UX_System in the same commit." |
| Don't commit | "Commit by explicit path (`git add <path>`), never `git add .`/`-A`/`-u`; never stage `FrontEnd/static/sounds/` (LFS content-vs-pointer noise)." |

(CLAUDE.md already documents `check_ui_tokens.py --strict --no-write` as a CI gate — left as is.)

## Contradictions / things I resolved against code, and one for Jamie

1. **`franchise-command-center.css` freeze — NOT MERGED.** `chore/fcc-css-peel` exists as a local branch but is not on `develop`. I documented the freeze as **pending** in §16 with a **(Jamie: confirm when to flip)** marker, rather than stating it as a live rule. **→ Jamie: say when the peel lands so the note becomes a rule.**
2. **reward-gold value disagreed across reports.** `reward-gold-sfx-2026-09-29.md` says `--reward-gold: #E8B84A`; `office-weekly-card-2026-09-29.md` asserts the marker computes to `rgb(240,197,96)`. **Resolved against the token source:** `gob-tokens.css:10` is `#F0C560` (= `rgb(240,197,96)`). The `#E8B84A` was an early placeholder; the doc uses `#F0C560`.
3. **Sting file extensions disagreed** (`.mp3` in `reward-gold-sfx`, `.wav` in `ch8-ci-tokens-sfx`). **Resolved against code/files:** `uiSfx.js` maps all three stings to `.wav`, and only `.wav` files exist in `FrontEnd/static/sounds/`. §3 already said `.wav`; left unchanged.
4. **PDG "develops" neutral clause — not in any report.** The task listed it as a colour-law clause; no dated report states it. I documented it from the task + the code element (`playerDevelopmentGrid.js` `.is-develops`, a read-only info marker). Flagging that it is task-provided, not report-sourced — **Jamie: confirm the wording if you want it stricter.**
5. **Team-names-as-stored has legacy stragglers.** `common.js` `formatTeamName`, `set-lineup.js`, `playbook-report.js`, `pgpcSammyReminderModal.js` still reformat names. Noted as pending cleanup in §16 rather than claimed as fully done.

STATUS: COMPLETE (docs only; migration gates pass unchanged)
