# Styleguide rewrite — 2026-10-01

Branch `docs/styleguide-rewrite` off `origin/develop`. Docs only: `Styleguide.md` rewritten (639 → 181 lines), `UX_System.md` colour-law body replaced by a summary + link (last commit), this report. No code, CSS, JS or tests touched.

Sources read: `gob-tokens.css`, `UX_System.md` (Principles, Colour law, Live-game overlays, Tokens and density, headshots, §12 Office, §14 Views/Save feedback, §16 Cross-cutting, Set Lineup), `check_ui_tokens.py`, all `reports/*-2026-09-30.md`. There are **no `reports/*-2026-10-01.md` on develop**. Also checked the live component CSS (`gob-components.css`, `gob-buttons.css`, `gob-toast.css`, modal CSS in `auth-bar.css` / `resource-pages.css`), `attributeDisplay.js`, `attrTiles.js`, `rtBucket.js`, `rt-buckets.css`, `recruiting-spine.css`.

## (a) Contradictions fixed

| Old Styleguide | New (source) |
|---|---|
| Orange = brand colour and "warning / low" data | Orange = saved / committed only (UX_System law, checker) |
| Light blue = "good / above average" data; secondary brand accent | Blue = RT A / 9+ / elite only, via `--tier-blue` |
| Yellow `#FFD700` = brand accent | Yellow is a data tier only (`--tier-yellow`) |
| Attribute bar 0–40 / 41–60 / 61–80 / 81+ | 1–10 first digit (`floor(raw/10)`): 0–4 red, 5–6 yellow, 7–8 green, 9+ blue; no upper cap in game; Team Builder caps at 99 |
| Attribute tiles 10+ / 7–9 / ≤3 ("unresolved") | Resolved in code: tiles call `attrTier()`, same scale |
| 52 hex literals + many rgba() | 0 hex. Tokens only (grep below) |
| Button spec: 138px min, 42px, 10px radius, hex borders | `--radius-10`, `--dsz-40`, `--space-20`, `--tracking-btn`, white-alpha borders; 138px min width kept (live `.advance` and `.btn-ghost` still use it) |
| Walk-On CTA navigation = orange | Navigation-only buttons are neutral (law) |
| Toast bottom-right, 3s, green accent, icon, slide-in | `GOBToast`: neutral, centred over `.main`, `--dsp-24` up, 1.5s, no icon (UX_System §14) |
| Moment modal W/L badge green/red | W/L plate white / outline |
| Functional modal accent orange default / green confirm | Accent follows the law; default orange flagged (Open Q4) |
| Team-colour "atmosphere" on panels; navy accent backgrounds | No team-colour wash; navy = "yours" only, never a background |
| Rankings previous win green / loss red text | W/L neutral; current CSS drift flagged (Open Q3) |
| Missing | Reward-gold surfaces; navy = yours; choice controls neutral; info codes neutral; ▲/▼ neutral; square headshots (`--radius-6` / `--radius-10`); one measure vocabulary (no Momentum); team names as stored; annotation rule incl. the 2-lines-above window |

Kept because still true and not covered elsewhere: sticky action bar for long pages; back/return as ghost link; modal types (functional incl. action-only, moment, strategic, tutorial) with dismiss rules and widths; toast replaces success modals; one modal at a time / `.is-visible`; class-year abbreviations; RT letter grades and display-boundary rule; table rules (contained, sticky header, separators not gridlines, subtle alternation, no white zebra, alignment, link underline on hover only); interaction-state list; above-the-fold intent; recruiting presence dot doesn't pulse.

## (b) Cut, and why

- History and dated notes, "Removed Treatments", "Remaining sections to formalize", "Open confirmation" (fonts are locked in tokens).
- Resource Pages divergent token set note (Barlow etc.) — superseded by the token migration; not a rule.
- Page Background System CSS blocks (shell gradient, diagonal banding, Mode Select franchise card, community rows, Set Lineup banner strip, split panels) — literal CSS, mostly legacy/out of shell; surfaces now come from `--bg*` / `--surface-*`.
- Theme Behaviour / Team Colors Mode — replaced by the team-colour row in the law.
- Button sizing heuristics (60–70% fill, cap height), exact tab clip-path px, modal px paddings, tutorial alert/resume footer pixel specs — implementation detail that lives in the CSS.
- Position colour map hexes — no tokens exist (Open Q10).
- Audio Rules — owned by UX_System §3.
- Inbox-tab orange pulsing badge — the Inbox tab no longer exists; rail badge/dot covered instead.

## (c) Token-name check

Every `--name` in the new Styleguide was extracted and compared with the names defined in `gob-tokens.css`. 141 distinct cited; all are defined except these deliberate non-tokens:

- `--dsp-`, `--dsz-`, `--space-`, `--surface-`, `--white-` — family prefixes written as `--dsp-*` etc.
- `--action`, `--gate`, `--ghost` — class suffixes (`.gob-btn--action`).
- `--strict` — CLI flag.
- `--you`, `--you-soft`, `--you-line`, `--you-ink` — cited only in Open Q7 as *not* tokens (local to `recruiting-spine.css`).

`grep -E '#[0-9A-Fa-f]{3,8}\b' Styleguide.md` → 0 hits.

Note: some rules are written to the token the law implies where the live legacy CSS still has raw values (modal surface/scrim, `gob-buttons.css`). Those files weren't touched; drift is listed in Open questions.

## (d) Open questions (also in the doc)

1. Navy for selected items (vs "yours" only) — Jamie.
2. ▲/▼ neutral vs green/red delta chips on Office attribute changes and `.chip.up/.down`.
3. W/L: `.wl.win/.loss` and Rankings "Last Week" still green/red.
4. Orange beyond saves: token comment ("non-advancing actions, gated-task tag"), checker allow-list (`.gated`, `.td-gate`, `.is-on`), Office blocking-step outline, attitude bars, rail `--badge`, functional-modal default accent, tutorial alert.
5. `.office-res` `--team-primary` gradient vs no-wash rule.
6. Destructive actions: red or neutral?
7. Promote `--you*` aliases into `gob-tokens.css` (UX_System cites them as if they were tokens).
8. RT colours are hard-coded in `rtBucket.js` and use the `--blue` value, not `--tier-blue`.
9. `css/gob-buttons.css` still hard-codes the old spec and calls orange "advances UI".
10. No tokens for position colours / broadcast data palette.
11. Token comment "player digit 0–16" vs `attributeDisplay.js` "no upper cap".
12. Repo `CLAUDE.md` says the colour law lives in UX_System — now it lives in Styleguide. Not changed (out of scope).

Also: this report is committed because the brief says so; repo `CLAUDE.md` says reports are untracked by convention.

## Gates

- `python3 scripts/check_ui_tokens.py --strict --no-write` → **exit 1**. Colour-law hits: 1 new (green), 710 legacy. The new hit is the pre-existing `box-score.css:494` (`.attr-chip.up`, green on develop already); this branch has no `FrontEnd/` or `scripts/` diff. Not fixed, per brief.
- `python3 scripts/ci/check_migration_gates.py` → **exit 0**. Gate A 0, Gate B 134 lines / 43 files. It notes `training-report.html` and `training.html` are now clean and can be removed from the allowlist (not touched).
- No Playwright, no pytest (docs only).
