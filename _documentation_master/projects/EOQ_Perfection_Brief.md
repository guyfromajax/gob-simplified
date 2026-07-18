# EOQ Perfection Brief

**Status:** Canonical rules live in [`EOQ_System.md`](../06_Gameplay_Systems/EOQ_System.md). This brief tracks ownership + polish checklists.

## Ownership rule (source of truth)

> When clock ≤ 30, the EOQ **window** may open on any eligible possession entry (HCO / HCT / FCP).  
> **Full Final Shot** execute flags are **HCO-only**.  
> HCT / FCP / FB in that window play their normal state until entry clock ≤ 8 (or ≤ 0), then **FLSS**.  
> Never leave `final_turn_shot_this_turn` armed on a state that will not run Final Shot.  
> `final_shot_ran_this_chain` flips only after an **executed** Final Shot or FLSS.

Code: `eoq_first_gate_open`, `should_arm_final_shot_execute_flags`, `TurnManager._enter_eoq_first_gate`.

## FLSS zone thresholds (home offense; mirror for away)

| Zone | Home x | Behavior |
|------|--------|----------|
| Normal | x ≥ 64 (`FLSS_NORMAL_SHOT_MIN_X_HOME`) | Standard shot; no coach VO |
| Penalty | 57 ≤ x < 64 (`FLSS_DEEP_KEY_X_HOME`) | Forced outside + penalty; coach VO |
| Heave | x < 57 | Desperation heave math; coach VO; heave SFX eligible when x ≤ 50 |

Constants: `BackEnd/constants/__init__.py`. SFX: `BackEnd/constants/flss_sfx.py` (launch/heave only).

## Progression notes

| Entry @ ≤30 | Window | Final Shot arm | Shot path |
|-------------|--------|----------------|-----------|
| HCO | yes | yes | Final Shot (or FLSS if preflight ≤8) |
| HCT / FCP | yes | **no** | Normal pressure; FLSS if entry ≤8 |
| After HCT window-open → later HCO | already open | yes (first gate still open if no EOQ shot ran) | Final Shot |
| BIP / SIP / OREB / DREB / FT | passthrough | never | Hand clock forward |

## SIP → FLSS playback contract (2026-07-16)

Final Shot → FOUL → SIP → follow-up FLSS must arm via chain-active schedule, prefer pending FLSS over quick foul, emit non-empty `animation_steps` or stamp `eoq_schema_emit_failed`, FE MAKE only when schema steps executed.
