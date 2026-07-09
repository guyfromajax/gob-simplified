# Dynamic HCO Set Plays — Build Brief

> **Status:** Archived (July 2026). Dynamic HCO set plays shipped (flagged: `GOB_DYNAMIC_HCO_SETPLAY`). **Canonical runtime doc:** [`Dynamic_HCO_System.md`](../../06_Gameplay_Systems/Dynamic_HCO_System.md) (§ Set plays). This file retains the overlay-model design decisions and staged build log.

**Dynamic HCO Set Plays**
- The offense does not look to execute subtle movements in Set Plays. They either look to exeucte the play that is called and progress skeleton steps as defined, or execute a Hot Read if the ball handler deems that one is available. 
- The defense can still force subtle movements with pressure. If the offense is forced into a subtle movement in a set play, they can either recover and continue to exectue the Set Play, or be forced into a freelance situation.
- If the ball handler is forced into a subtle movment step, then non bh offenders can also look to execute a subtle movement in order to get into position for a hot read pass reception.

**If Offense Get Knocked Into A Subtle Movement**
- bh performs subtle movement, non-bh players make a read and if they exceed the threshold they make a sublte movement (I think we have teh non-bh reads alerady wired from motion plays, but LMK if not)
- progression once subtle movement is executed
    - bh reads if shoot, hot read pass, or hold and look to re-enter the set play skeleton
        - if he chooses to shoot or pass, execute it
        - elif he chooses to re-enter set play skeleton run the following logic
            - offense score = (offense team chemistry + offense team off execution) * random.randint(1,6)
            - defense score = (defense team chemistry + defense team def execution) * random.randint(1,6)
            - if offense_score > defense_score, re-enter set play skeleton, else enter freelance forced situation


**Notes**
- We should apply per step reconciliation for steal/db turnover/foul, LMK if we need to align on this or if re-using the existing logic and code works here
- LMK if we need to wire vs man defense first, then vs zone. Or if we can do both at the same time

---

## Resolved Design (decisions locked — 2026-06)

**Flag:** `GOB_DYNAMIC_HCO_SETPLAY` (separate from motion's `GOB_DYNAMIC_HCO_MOTION`; independent rollout).
**Coverage:** **man + zone together** (revised). The zone pieces are already built/proven from motion (moment-walk is man+zone, def-coord reconstruction, zone on-ball defender), and Stage A's `skip_upfront_events` disables the up-front tables for *all* set plays — so man-only would leave **zone** set plays event-less. Doing both retires the up-front event tables for set plays entirely.
**Model: OVERLAY.** The up-front **variant roll** (successful / mid_play_change / contested / broken) still selects the skeleton; the dynamic per-step layer overlays on the chosen variant skeleton. (Variant selection STAYS.)

**Per-step layer (walks the chosen variant skeleton):**
1. Offense does **NOT** proactively subtle-move → `offense_reads = False` for set plays (unlike motion).
2. **Universal hot read:** `should_shoot` runs every step (self shot / hot-read dish, with the "truly open" gate + interception contest) — reused from motion.
3. **Defense-forced disruption:** reuse motion's per-step `defense_score`-vs-offense battle with `offense_reads=False`, so only the defense-pressure → `_disruption_branch` path fires → BH knocked into a forced subtle (or freelance).
4. **Per-step moment** (steal / db / foul): reuse `_resolve_hco_moment_walk` (man). **Replaces the up-front event tables for set plays** (turn them OFF under the flag, like motion). Variant selection unaffected.

**Forced-subtle progression (when knocked off):**
- BH performs a subtle movement; non-BH teammates make their reads (reuse `build_subtle_beat`) to relocate for a hot-read reception.
- Then BH reads **shoot / hot-read pass / hold-and-re-enter**:
  - shoot or pass → execute.
  - re-enter → roll: `offense_score = (team_chemistry + offensive_efficiency) × randint(1,6)`; `defense_score = (team_chemistry + defensive_efficiency) × randint(1,6)`. If `offense_score > defense_score` → **re-enter the set play skeleton at the next defined step** (pop players back to defined spots); else → **freelance forced** (`_resolve_freelance`).

**Reused from motion (no re-build):** `should_shoot` + truly-open gate + interception · `_disruption_branch` · `build_subtle_beat` non-BH reads · `_resolve_freelance` · `_resolve_hco_moment_walk` (man).

**Implementation note (slot mapping — RESOLVED):** set-play skeletons key pos_actions by `pos1..pos5` in the DB, BUT `get_hco_skeleton` already runs `_apply_set_play_runtime_position_mapping` → `_remap_set_play_steps_to_canonical(target_shooter)`, which remaps slots → canonical lineup positions (PG/SG/…) **before** the skeleton reaches `resolve_half_court_offense_logic`. So a set-play variant skeleton arrives **position-keyed, just like motion's `base_loop`** — the motion machinery (resolver helpers, moment-walk, def-coord reconstruction) can walk it directly. No slot-mapping work needed in the dynamic layer.

**Staged plan:**
- **A — Flag + gating ✅:** `GOB_DYNAMIC_HCO_SETPLAY` gate + `skip_upfront_events` extended to set plays under the flag + the recovery-roll helper (`_setplay_recovery_roll`). Tested.
- **B — Per-step walk on the variant skeleton ✅:** `_resolve_setplay_offense_shot_dynamic` reuses motion helpers with `offense_reads=False` and `_setplay_recovery_roll`. Tested (`test_setplay_dynamic_resolver.py`).
- **C — Per-step moment (man + zone) ✅:** `_resolve_hco_moment_walk` on set plays. Tested.
- **D — Tests + prototype + doc ✅**
