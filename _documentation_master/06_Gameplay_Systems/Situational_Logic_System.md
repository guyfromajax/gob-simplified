# Situational Logic (Q4/OT)

**Score Delta** = Offense Team Score − Defense Team Score (zero in the case of a tie).

All logic below applies only when **quarter ≥ 4**, except **Final Turn / FLSS** (clock ≤ 30s), which applies in **all quarters and OT**. Evaluate the time-band table first to determine Slow It Down, Quick Shot, shot ratios, and Force Foul; then apply Execution.

> **EOQ execution (Final Shot, FLSS, chain flags, post-shot routing, debugging):** see **[`EOQ_System.md`](EOQ_System.md)** — canonical doc for end-of-quarter logic. This file covers Q4/OT **score-band situational playcalling** and how those branches interact with Final Turn at ≤ 30s.

---

## Time-band table (source of truth)

**Time Remaining 2:01 – 3:00**
- If Score Delta ≥ 12 → Slow It Down = True
- Else if Score Delta < -12 and > -24 → Quick Shot = True
- Force Foul = False

**Time Remaining 1:01 – 2:00**
- If Score Delta ≥ 9 → Slow It Down = True
- Else if Score Delta < -9 and > -18 → Quick Shot = True
- Force Foul = False

**Time Remaining 0:31 – 1:00**
- If Score Delta ≥ 3 → Slow It Down = True
- Else if Score Delta < -3 and > -12 → Quick Shot = True
- Force Foul: True if 3 < Score Delta < 12, else False

**Time Remaining 0:01 – 0:30**
- If Score Delta ≥ 1 → Slow It Down = True
- Else if Score Delta < -3 → Quick Shot = True
- Force Foul: True if 0 < Score Delta < 9, else False

When Score Delta falls in neither Slow It Down nor Quick Shot for that band → use normal playcall logic (motion/set mix, playbook weights, focus sliders).

**Implementation:** `BackEnd/models/turn_manager.py` → `set_playcalls()` (situational branches call `_select_motion_play_situational_slow` / `_select_set_play_situational_quick_shot`).

---

## Slow It Down / Quick Shot Execution

**When Slow It Down applies (per time-band table):**
- **Force Foul (Quick Foul):** evaluate at BIP/SIP setup time (to build the bespoke formation) and again at the **start of the following routed possession** (HCO/HCT/FCP/Fast Break), where the foul actually executes. See **Force Foul Execution** below.
- If Force Foul = False: proceed to next step.
- **Conservative defense (temp override):** the Slow It Down (leading) team’s `fast_breaks`, `hc_trap`, `fc_press`, and `aggression` are all treated as **0** for as long as they’re in Slow It Down — see **Slow It Down conservative-defense state** below. These are read-time overrides only; the team’s stored `strategy_settings` (and their DB team doc) are never mutated.
- Next step (if Force Foul = False): offense tempo = `"slow"` (see **Offense tempo overrides** below).
- **Playcall (HCO):** Call a **motion** play only. Select from motion plays that have a **non-zero percentage** in the offense team’s playbook settings (weighted by those percentages). If no motion play has a percentage assigned, choose any motion play at random. Playbook set-play percentages and motion/set mix do not apply. User Playcall Center overrides still take precedence when set.

**When Quick Shot applies (per time-band table):**
- Offense tempo = `"fast"` (see **Offense tempo overrides** below).
- Override Defense Team's FCP & HCT settings to 0 (temp override; revert when Quick Shot no longer applies).
- **Playcall (HCO):** Call a **set play** with **outside** shot focus only. All outside set plays are eligible; choose one at **uniform random**. Playbook percentages and motion/set mix do not apply. User Playcall Center overrides still take precedence when set.

Temp overrides (Fast Break, FCP, HCT) are re-evaluated each turn and revert when the situation no longer applies.

---

## Slow It Down conservative-defense state

Slow It Down is fundamentally about a team with a **comfortable late lead** getting conservative. The existing `tempo = "slow"` override handles their **offense** (see **Offense tempo overrides**); this section covers their **defense**.

**Macro team-state.** Each turn we (re)compute a macro, team-level Slow It Down state stored in `game_state["slow_it_down_team_ids"]` (a list, persisted in the game doc). Unlike the offense-perspective `is_slow_it_down()` (used for tempo/playcall), this is evaluated from the **leading team’s** perspective — `leadScore − trailScore` vs the current time-band’s Slow It Down threshold — so it applies **independent of who is on offense**, i.e. it stays in force while the leading team is on **defense** (the opponent’s possession). It is re-evaluated every turn and reverts the moment the lead no longer meets the band threshold (or we leave Q4/OT). `BackEnd/utils/situational_logic.py` → `get_slow_it_down_team_id()`.

**Conservative-defense overrides (all → 0)** for a team in this state, applied at read time only (their stored `strategy_settings` / DB team doc are never mutated):

| Setting | Effect when 0 | Where applied |
|---------|---------------|---------------|
| `fast_breaks` | No fast-break release off a defensive rebound (DREB, FT-miss DREB) | `shot_manager.py`, `phase_resolution.py` (via `slow_it_down_defense_setting()`) |
| `hc_trap` / `fc_press` | No half-court trap / full-court press → straight `HCO` defense after a made shot | `turn_manager._select_defensive_pressure_type()` |
| `aggression` | Passive defense: `aggression_call = "passive"` (fewer fouls, less steal/help gambling), no transition push off a steal, fewer block attempts, looser zone-defender spacing | `turn_manager.set_strategy_calls()` (resolved `aggression_call`) + raw `strategy_settings["aggression"]` reads in `shot_manager.py` / `phase_resolution.py` (via `slow_it_down_defense_setting()`) |

**Precedence.** The user’s Playcall Center overrides win over these situational overrides:
- **Aggression:** PC `aggression_override` (user team) > Slow It Down `"passive"` > per-break `aggression_roll`.
- **Press/Trap:** PC `press_trap_override` (user team) > Slow It Down `HCO`. (Note the Quick Shot `_situational_quick_shot_fcp_hct_override` is checked first and still precedes the PC override, matching existing Quick Shot behavior.)

**Helpers:** `situational_logic.py` → `is_team_slow_it_down(game_state, team_id)`, `slow_it_down_defense_setting(game_state, team, key, raw_value)`, `SLOW_IT_DOWN_CONSERVATIVE_SETTINGS`. **State refresh:** `turn_manager._refresh_situational_team_state()` (called at the start of `set_strategy_calls()` and `determine_defensive_pressure_type()`).

---

## Offense tempo overrides

When **Slow It Down** or **Quick Shot** applies, the offense team’s `tempo_call` is set to `"slow"` or `"fast"` respectively. This overrides the backend computer sim tempo roll from `strategy_settings["tempo"]` for **all** offense teams (user and CPU).

**Precedence (highest wins):**

1. **Playcall Center tempo** — user’s `tempo_override` when the user’s team is on offense (`set_strategy_calls()` in `turn_manager.py`). Cleared after one use; clearing via ✕ (`tempo_override: null`) removes the PC call so situational tempo applies again on the next turn.
2. **Situational tempo** — `"slow"` (Slow It Down) or `"fast"` (Quick Shot) from `get_situational_tempo_override()` when Q4/OT bands apply.
3. **Backend sim tempo** — random roll from `strategy_settings["tempo"]` when no situational override is active.

**Implementation:** `BackEnd/models/turn_manager.py` → `set_strategy_calls()` applies the stack above. `BackEnd/utils/situational_logic.py` → `get_situational_tempo_override()`.

---

## Force Foul Execution (Quick Foul)

**Detection.** `quick_foul_in_play(game)` in `BackEnd/utils/quick_foul.py` — pure function of Q4/OT quarter, time band, and score delta (`should_force_foul` ∧ `is_slow_it_down`). Safe to call at BIP/SIP setup or possession start.

**Universal execution hook.** The intentional foul executes at the **start of the offense’s routed possession**, before HCO/HCT/FCP/Fast Break resolution, on the **current ball handler**, via `turn_manager._execute_quick_foul_at_possession_start()`. This single path covers every entry point:

| Entry | Victim (ball handler) | Setup step? |
|-------|----------------------|-------------|
| BIP → routed state | Dynamic inbound pass receiver (see below) | Yes — bespoke quick-foul BIP formation |
| SIP → HCO | Dynamic inbound pass receiver | Yes — bespoke quick-foul SIP formation |
| DREB → routed state | Last rebounder | No — fouler sprints in |
| OREB kickout → HCO | Kickout receiver | No — fouler sprints in |
| Fast Break / Final Turn | Live ball handler | No — fouler sprints in |

BIP/SIP turns **only position players and animate the inbound pass** — no foul logic or foul animation occurs on the inbound turn itself. The foul is the **first action** at the next possession boundary, before the selected HCO/HCT/FCP resolver starts.

**Fouler selection.** At foul time: the **defender closest to the victim** (`select_defender_closest_to_victim`). On BIP/SIP setup, foulers are **pre-positioned within 4 Euclidean grid spots** of their paired candidate receiver (see Setup below).

**Approach radius.** `QUICK_FOUL_APPROACH_RADIUS_GRID = 4`. The fouler’s destination is a **random spot within 4 grid** of the victim (uniform in the disk) so the setup does not look mechanical. Universal — also used by `pick_force_foul_defender_spot()`.

### BIP/SIP quick-foul setup (Q4/OT only)

When `quick_foul_in_play()` is true at inbound setup, the bespoke quick-foul formation (`build_quick_foul_inbound_setup()`) places the selected receiver and fouler for immediate contact. The selected FCP/HCT route remains in the BIP contract, but its resolver never begins because the foul executes first. Normal (non–quick-foul) BIP/SIP are unchanged (SF → PG inbound pass).

**Offense**
- **Inbound passer:** always SF.
- **Two candidate receivers** (the inbound pass targets one of them at random 50/50):
  - Placed within **15 Euclidean grid** of the inbounder, **≥ 10 apart**, in bounds.
  - `roll = random.randint(1, 25)` vs offense `team_chemistry` (7–25):
    - roll **<** chemistry → two best FT shooters among PG/SG/PF/C (ties → random).
    - else → SG + PG.
- **Remaining two offense players:** random distinct spots from: key, upper/lower apex, upper/lower bird, upper/lower corner, upper/lower midCorner.

**Defense**
- **Inbound guard:** tallest defender, placed **3 grid toward the court** from the inbounder (BIP: +x from baseline; SIP: −y from top sideline).
- **Two fouling defenders** (paired to the two candidate receivers at random):
  - Within **4 Euclidean grid** of their paired receiver.
  - `roll = random.randint(1, 25)` vs defense `team_chemistry`:
    - roll **<** chemistry → two active defenders with **fewest fouls** (ties → random).
    - else → two defenders chosen at random from the remaining four.
- **Remaining two defenders:** random distinct spots from: midLane, topLane, upper/lower midPost, upper/lower highPost, upper/lower bird, upper/lower apex. If a bird/apex spot is shared with an offender, the defender’s spot **offsets 2 grid toward the basket**.

**Dynamic inbound receiver.** The BIP/SIP pass step targets the chosen receiver (`receiver_id` param on `build_bip_animation_steps` / `build_sip_animation_steps`). `hco_setup.inbound_pass.to_player_id` records that receiver so the following routed possession’s ball handler = foul victim. **Scope:** quick-foul inbounds only; normal BIP/SIP remain SF → PG.

### DREB routing

On DREB when Force Foul applies, `shot_manager` sets `force_foul_after_dreb = True` and routes straight to HCO (no Fast Break, no outlet). The frontend skips outlet animation when this flag is set. The foul itself executes on the **HCO turn start** (universal hook), not as a separate injected FOUL turn.

### UESS animation (frontend = pure renderer)

The backend emits a 2-step `animation_steps` sequence via `build_quick_foul_animation_steps()`:

1. **Converge** (`quick_foul_converge`): fouler moves at **`sprint` archetype** (AG-scaled backend rate; no frontend multiplier) from current position to a random spot within 4 grid of the victim. Victim holds the ball. **Game clock RUNS.** Step T = natural sprint travel time, **floored to 1 game-second** (`QUICK_FOUL_TIME_ELAPSED_FLOOR`). On BIP/SIP the fouler is already within 4 (setup pre-positioned), so this is typically ~1s; on DREB/OREB/Final Turn it is a real sprint.
2. **Reach-in** (`quick_foul_reach_in`): all players stationary; fouler plays **`reach_in` flourish** toward the ball. **Game clock PINNED** (stops when the reach-in begins). **"Quick Foul!"** announcement mounts on this step (`non_blocking: true` — overlay only, no gameplay freeze). Advance trigger = foul executed → `turn_stop`.

`time_elapsed` on the foul turn = converge T only (reach-in is clock-paused). Passed to `resolve_non_shooting_foul(time_elapsed_override=…)`.

**Implementation:** `BackEnd/utils/quick_foul.py`, `BackEnd/models/turn_manager.py` (`_execute_quick_foul_at_possession_start`), `BackEnd/constants/__init__.py` (quick-foul constants block).

## Announcement System

Situational and result announcements are driven by a central game announcement system. At **turn start** (during turn preparation, before animation), the following context announcements may be shown based on turn data:

- **Fast Break** — when the turn is a fast break (and not steal-initiated).
- **Press!** / **Trap!** — when a baseline inbound is setting up FCP or HCT (defense).
- **Slow It Down** / **Quick Shot** — when an HCO turn has Slow It Down or Quick Shot set (offense).
- **Final Shot** — when the turn is a Final Turn shot attempt (offense).

At **turn end** (or at specific animation moments), the system announces shot results (e.g. "It's Good!", "Shooting Foul!"), fouls ("Quick Foul!", "CHARGE!", "BLOCKING FOUL!", etc.), rebounds, steals, and turnovers. **Quick Foul** announces via the reach-in schema step (`step.end.announcement`, `non_blocking: true`) — see Force Foul Execution and `Announcement_System.md`.

---

## Final Turn / EOQ (pointer)

Final Shot arming, FLSS, EOQ chain flags, post-shot routing (BIP → FLSS, terminal DREB, OREB putback), preflight anchors, observability (`[EOQ-TRACE]`), and debugging checklists are documented in **[`EOQ_System.md`](EOQ_System.md)**.

**Q4/OT possession-entry priority** at `0 < time_remaining <= 30`, before HCO,
HCT, FCP, or Fast Break resolution:

| Branch | When |
|--------|------|
| **Force Foul** | Slow It Down + Force Foul — execute before the selected live-ball resolver |
| **Run Out The Clock** | `should_run_out_clock()` — winning or blowout loss (>18), ≤30s, no force-foul defense; overrides Fast Break/HCT/FCP |
| **Quick Shot** | Quick Shot band — normal quick-shot HCO (no Final Turn setup); last 30s when trailing by **more than 3** |
| **Else (Final Shot)** | HCO uses structured Final Turn; HCT/FCP/Fast Break preserve a fitting turn or hand a safe movement prefix to FLSS |
| **Trailing by exactly 3** | Forced Outside three (within Final Turn shot logic) |

Qs 1–3 use the same structured Final Turn as Q4 trailing/tied, without the rows above.
