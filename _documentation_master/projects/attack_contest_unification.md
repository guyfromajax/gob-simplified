# Attack-Shot Contest Unification

**Objective:** all attack-shot **drives to the basket** — across **Fast Break, HCT, FCP, and HCO** — resolve through the ONE shared contest, `resolve_cutoff_contest` → `_resolve_moment` (`dynamic_hct.py`), with **FB-style consumption**, instead of per-turn-type bespoke logic. Extends the "unify all moment resolution" follow-up (Dynamic_MM_Brief §S2) to FCP.

> This is a FOLLOW-UP pass, sequenced **after** the HCO S2 work lands (HCO joins the model there). Captured here so it isn't lost. Owner directive 2026-07-14.

## The shared model (reference = Fast Break)

`resolve_cutoff_contest` → `_resolve_moment(off, def, bh, defender, def_mod=, off_mod=, exclude_steal=True)` → `(outcome, score_ratio, credited)`:

| outcome | meaning | FB consumption (the reference) |
|---|---|---|
| `POS_O` (+`D_FOUL` variant) | offense beats his man | shimmy past → drive on to the shot |
| `NEUTRAL` | contested, neither wins | `DEFENSIVE_STOP` (break ends → HCO reset) |
| **`D_STOP`** (new, this project) | defender wins cleanly, no contact | *(today folded into `NEUTRAL`)* |
| `D_FOUL` / `O_FOUL` / `DEAD BALL` (/`STEAL`) | contact | foul / charge / turnover, at the meet |

Plus the shared geometry `best_cutoff_on_drive` / `cutoff_meet_point` for WHERE the stop lands.

**Universal signal (from the HCO S2 work):** the new `D_STOP` outcome (distinguishes the *defense-wins-no-event* clean stop from the *middle-band* contested `NEUTRAL`) + a generalized `score_ratio` (meaningful for all outcomes, not just turnovers). Both live in the shared `_resolve_moment`.

## Current state per turn type (traced 2026-07-14)

| Turn | Uses `_resolve_moment`? | Gap vs FB |
|---|---|---|
| **FB** | ✅ reference | — (differentiated `POS_O`→shot / `NEUTRAL`→stop / terminal→foul-TO; geometric meet; discards `score_ratio`) |
| **HCT** | ✅ (shared cutoff) | **collapses `POS_O`+`NEUTRAL` → `RETAIN`** ([dynamic_hct.py:2724](../../BackEnd/engine/dynamic_hct.py)); discards `score_ratio`. ~90% mirrored — align its POS_O/NEUTRAL/`D_STOP` consumption to FB. |
| **HCO** | ✅ per-step moment (`_resolve_hco_moment`); **drive joining via S2** | S2 adds graded stop + `D_STOP` + half-court consumption (pull-up/dish). |
| **FCP** | ❓ **UNVERIFIED** | `fcp_offball_attack.py` is press-break POSITIONING, not a drive contest. FCP shots likely **transition to FB** (broken press → numbers break). **Needs a trace of `resolve_full_court_press_logic`'s shot-production path** to confirm it routes through FB vs. has its own attack-shot resolution. |

## Nuance — consumption is context-appropriate (do NOT force-identical)
The **contest + `D_STOP`/`score_ratio` signal** are universal. The **post-stop behavior is per-context and correct as-is:**
- **FB / transition (HCT press-break, FCP):** a stopped break **resets** (→ HCO). Forcing a contested transition pull-up would be *wrong*.
- **HCO half-court:** a stopped drive → **pull-up / dish / reset** now (S2d/S2e), because the possession continues in the half court.

"Mirror FB" = share the contest, geometry, and outcome vocabulary — not identical rendering after the stop.

## Tasks (post-S2)

1. **Trace** `resolve_full_court_press_logic` (FCP) + the HCT consumption delta → scope precisely (no guessing).
2. **HCT:** differentiate `POS_O` (→ attack/shot) vs `NEUTRAL`/`D_STOP` (→ stop) instead of the single `RETAIN` collapse, to match FB.
3. **FCP:** route/confirm attack-shot drives through `resolve_cutoff_contest` (or confirm they already transition to FB).
4. **FB/HCT adopt `D_STOP`** if a distinct clean-stuff rendering is wanted (optional — mapping to existing `DEFENSIVE_STOP`/`RETAIN` keeps them byte-identical until then).

## References
- `_documentation_master/projects/Dynamic_MM_Brief.md` §S2 (the HCO side + the universal `D_STOP` design)
- `BackEnd/engine/dynamic_hct.py` — `_resolve_moment`
- `BackEnd/engine/cutoff_resolution.py` — `best_cutoff_on_drive`, `resolve_cutoff_contest`, `map_cutoff_outcome_to_fb`
- `BackEnd/engine/fb_drive_resolution.py` — the FB reference consumption
