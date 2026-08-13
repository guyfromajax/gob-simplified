# TRAINING_GAIN_PERCENTAGES — baseline snapshot (revert point)

Captured **2026-08-12**, before the in-season net-deterioration tuning experiment
(boost gain percentages to offset per-year pre-training decay). This is the exact live
`TRAINING_GAIN_PERCENTAGES` in `BackEnd/constants/training_shape.py` and the §867 table in
`Tunable_Constants.md` at capture time. **To revert, restore these values.**

Every row totals **808** (avg 67.3%). FT/IQ/ND are universal 100%.

| Position | ST | AG | SC | SH | ID | OD | PS | BH | RB | FT | IQ | ND | Total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PG | 35 | 83 | 40 | 45 | 25 | 70 | 85 | 100 | 25 | 100 | 100 | 100 | 808 |
| SG | 35 | 68 | 55 | 100 | 25 | 60 | 70 | 70 | 25 | 100 | 100 | 100 | 808 |
| SF | 40 | 53 | 82 | 64 | 50 | 91 | 39 | 39 | 50 | 100 | 100 | 100 | 808 |
| PF | 99 | 45 | 55 | 47 | 67 | 35 | 35 | 25 | 100 | 100 | 100 | 100 | 808 |
| C | 77 | 25 | 68 | 40 | 100 | 40 | 33 | 25 | 100 | 100 | 100 | 100 | 808 |

Class multiplier (separate, unchanged): FR 100 / SO 91 / JR 80 / SR 71.

Guarded by `tests/test_training_shape_framework.py` (percentage/shape battery) and the
in-season invariants `tests/test_in_season_invariants.py`.
