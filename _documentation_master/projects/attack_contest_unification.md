# Attack-Shot Contest Unification ✅ DONE (2026-07-24)

**Objective:** all attack-shot **drives to the basket** — across **Fast Break, HCT, FCP, and HCO** — resolve through the ONE shared contest, `resolve_cutoff_contest` → `_resolve_moment` (`dynamic_hct.py`), with shared outcome vocabulary. Extends the "unify all moment resolution" follow-up (Dynamic_MM_Brief §S2) to FCP.

## Shared model (reference = Fast Break)

`resolve_cutoff_contest` → `_resolve_moment(..., exclude_steal=True)` → `(outcome, score_ratio, credited)`:

| outcome | meaning | FB | HCT / FCP broken-press (transition) |
|---|---|---|---|
| `POS_O` (+`D_FOUL` variant) | offense beats his man | continue → shot | **CONTINUE_ATTACK** — finish meet → ABA spot, then existing ABA read (HCO vs FB) |
| `NEUTRAL` | contested, neither wins | `DEFENSIVE_STOP` → HCO | **STOP_HCO** — break ends → HCO (no pull-up/dish) |
| `D_STOP` | defender wins cleanly, no contact | `DEFENSIVE_STOP` (same as NEUTRAL until distinct render) | **STOP_HCO** (same) |
| `D_FOUL` / `O_FOUL` / `DEAD BALL` | contact | terminal at meet | terminal at meet (unchanged) |

Geometry: `best_cutoff_on_drive` / `cutoff_meet_point` (`cutoff_resolution.py`).

**Nuance:** contest + vocabulary are universal. Post-stop behavior is context-appropriate — transition (FB / broken HCT / FCP) resets to HCO; HCO half-court uses pull-up/dish (S2). Do not force HCO post-stop onto transition.

## Status per turn type

| Turn | Contest | Consumption |
|---|---|---|
| **FB** | ✅ `resolve_cutoff_contest` | reference (`fb_drive_resolution.py` + `map_cutoff_outcome_to_fb`) |
| **HCT** | ✅ shared cutoff in `_do_broken_hct_cutoff` | ✅ `map_cutoff_outcome_to_hct_transition` — no more POS_O+NEUTRAL → RETAIN |
| **FCP** | ✅ same path (`turn_mode="fcp"`) | ✅ one fix covers both |
| **HCO** | ✅ S2 `_resolve_hco_drive_contest` | half-court pull-up/dish (separate) |

## Key code

- `BackEnd/engine/cutoff_resolution.py` — `resolve_cutoff_contest`, `map_cutoff_outcome_to_fb`, `map_cutoff_outcome_to_hct_transition`
- `BackEnd/engine/dynamic_hct.py` — `_do_broken_hct_cutoff` / `_finish_broken_cutoff_to_aba`
- `BackEnd/engine/fb_drive_resolution.py` — FB reference
- `tests/test_hct_cutoff_outcome_branching.py`

## References
- `_documentation_master/projects/Dynamic_MM_Brief.md` §S2
- `_documentation_master/06_Gameplay_Systems/HCT_System.md` / `FCP_System.md`
