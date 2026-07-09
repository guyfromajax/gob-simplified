# Tunable Constants

Central registry of tunable game-logic constants — the knobs for balancing gameplay. Each entry lists the constant, its current value, and a one-line effect.

## FLSS (Forced Last Second Shot)

| Constant | Value | Effect |
|---|---|---|
| `FLSS_DEEP_KEY_X_HOME` | 57 | Home x-band floor for penalty-zone FLSS (away mirrors); below → heave zone. |
| `FLSS_NORMAL_SHOT_MIN_X_HOME` | 64 | Home x minimum for normal-zone FLSS (full shot pipeline); away mirrors. |
| `FLSS_HEAVE_MAX_X_HOME` | 50 | Home x at/beyond which heave coach VO may include `duke-heave.mp3`; away mirrors. |
| `FLSS_HEAVE_MISS_RATTLE_MAX` | 5 | Heave miss margin ≤ this → random LITTLE/NORMAL/HEAVY rattle rim action. |
| `FLSS_HEAVE_MISS_RIM_BOUNCE_MAX` | 15 | Heave miss margin 6–15 → BACK_OF_RIM bounce-off-rim animation. |
| `FLSS_HEAVE_MISS_BACKBOARD_MAX` | 30 | Heave miss margin 16–30 → BANK_MISS off-backboard animation; above → AIRBALL (SFX only, no headline). |
| `FLSS_AIRBALL_LAND_X_OFFSET_MIN` | 2 | FLSS AIRBALL only: min x grid distance from attacking basket for short landing before OOB tween. |
| `FLSS_AIRBALL_LAND_X_OFFSET_MAX` | 5 | FLSS AIRBALL only: max x grid distance from attacking basket for short landing before OOB tween. |
| `FLSS_AIRBALL_LAND_Y_VARIANCE` | 5 | FLSS AIRBALL only: landing y = basket y ± this (OOB continuation uses same y). |

## HC Trap

| Constant | Value | Effect |
|---|---|---|
| `TRAP_MOMENT_RANGE` | 5 | Max grid distance a defender can be from the ball-handler to count toward an HC trap/pressure double-team. |
