# EOQ Perfection Brief

**Status:** Implemented content lives in [`EOQ_System.md`](../06_Gameplay_Systems/EOQ_System.md). This brief is retained as the original product checklist pointer.

## FLSS zone thresholds (home offense; mirror for away)

| Zone | Home x | Behavior |
|------|--------|----------|
| Normal | x ≥ 64 (`FLSS_NORMAL_SHOT_MIN_X_HOME`) | Standard shot; no coach VO |
| Penalty | 57 ≤ x < 64 (`FLSS_DEEP_KEY_X_HOME`) | Forced outside + penalty; coach VO |
| Heave | x < 57 | Desperation heave math; coach VO; heave SFX eligible when x ≤ 50 |

Constants: `BackEnd/constants/__init__.py`. SFX contract: `BackEnd/constants/flss_sfx.py` (launch/heave only).

## SIP → FLSS playback contract (2026-07-16)

Final Shot → FOUL → SIP → follow-up FLSS must:

1. Arm FLSS after SIP when EOQ chain is active (`schedule_flss_after_inbound` + `tag_result_if_late_clock_eoq_chain` on FOUL/CHARGE).
2. Prefer pending FLSS over quick foul at HCO entry.
3. Emit non-empty `animation_steps` or stamp `eoq_schema_emit_failed`.
4. FE: announce MAKE only when schema steps actually executed.

See EOQ_System.md §8–§9.
