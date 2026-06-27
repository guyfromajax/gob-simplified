
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
**Coverage:** **man defense first**; zone deferred to a follow-up (the zone def-coord reconstruction already exists from motion).
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

**Implementation note:** set-play skeletons key pos_actions by `pos1..pos5` (motion uses PG/SG/…) and carry 4 variants × ≥2 versions (motion = `base_loop`). `_motion_bh_at_step` keys off the `handle_ball`/`receive` action (key-name agnostic), but other motion-resolver assumptions need an audit when pointing it at a set-play variant skeleton.

**Staged plan:**
- **A — Flag + gating:** add `GOB_DYNAMIC_HCO_SETPLAY`; under it, keep variant selection but turn OFF the up-front event tables for set plays (`skip_upfront_events` extends to set); route set plays (man) toward the dynamic per-step walk.
- **B — Per-step walk on the variant skeleton:** universal hot read + defense-forced disruption (battle with `offense_reads=False`) + forced-subtle progression (recovery roll → re-enter / freelance).
- **C — Per-step moment (man)** on set plays.
- **D — Tests + prototype + doc.**
- **Later:** zone.
