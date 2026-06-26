# Situational Logic (Q4/OT)

**Score Delta** = Offense Team Score − Defense Team Score (zero in the case of a tie).

All logic below applies only when **quarter ≥ 4**, except **Final Turn / FLSS** (clock ≤ 30s), which applies in **all quarters and OT**. Evaluate the time-band table first to determine Slow It Down, Quick Shot, shot ratios, and Force Foul; then apply Execution.

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
- Calculate Force Foul at the BIP or SIP step if applicable; otherwise at the very beginning of the HCO step.
- If Force Foul = True: defense commits a foul immediately on the pass receiver of the BIP/SIP pass (pass must be animated first), or at HCO on the last rebounder; `time_elapsed = random.randint(1, 3)`; process next step accordingly (goal: get to bonus and force free throws).
  - The player being fouled is the offense player receiving the inbound pass on BIP & SIP steps, or the offense player who holds the ball entering the HCO step (no passes); the fouling defender is the defender closest to the player being fouled at the moment of the foul.
  - Foul animation: move the defensive fouling player's sprite to the offensive player being fouled sprite, execute the announcement system with the fouling player image and text "Quick Foul".
- If Force Foul = False: proceed to next step.
- Override Offense Team’s Fast Break setting to 0 (temp override; revert when Slow It Down no longer applies).
- Next step (if Force Foul = False): offense tempo = "slow".
- **Playcall (HCO):** Call a **motion** play only. Select from motion plays that have a **non-zero percentage** in the offense team’s playbook settings (weighted by those percentages). If no motion play has a percentage assigned, choose any motion play at random. Playbook set-play percentages and motion/set mix do not apply. User Playcall Center overrides still take precedence when set.

**When Quick Shot applies (per time-band table):**
- Offense tempo = "fast".
- Override Defense Team's FCP & HCT settings to 0 (temp override; revert when Quick Shot no longer applies).
- **Playcall (HCO):** Call a **set play** with **outside** shot focus only. All outside set plays are eligible; choose one at **uniform random**. Playbook percentages and motion/set mix do not apply. User Playcall Center overrides still take precedence when set.

Temp overrides (Fast Break, FCP, HCT) are re-evaluated each turn and revert when the situation no longer applies.

---

## Force Foul Execution

**Force Foul after inbound:** When Slow It Down + Force Foul apply, we set a pending Force Foul after each BIP or SIP. On the next turn we **run the Force Foul first** (before any state routing). That way the foul is executed whether the next step would have been HCO, HCT, or FCP—and we avoid running next-turn choice logic (e.g. HCO vs HCT vs FCP) when it would only be overwritten by the foul result.

**Force Foul after DREB:** On a defensive rebound (HCO shot miss → DREB), we **evaluate Force Foul immediately**. If Slow It Down + Force Foul apply, we execute the foul right away: we do not run the normal “next step” logic (no Fast Break vs HCO decision, no outlet pass). The victim is the last rebounder; the fouling defender is the defender closest to that rebounder. We inject a FOUL turn and then enter the standard defensive non-shooting foul flow (possession flip, SIDE_INBOUND or FREE_THROW). Animation: no outlet pass; on the FOUL turn we animate the defender moving to the rebounder and announce “Quick Foul.”

## Announcement System

Situational and result announcements are driven by a central game announcement system. At **turn start** (during turn preparation, before animation), the following context announcements may be shown based on turn data:

- **Fast Break** — when the turn is a fast break (and not steal-initiated).
- **Press!** / **Trap!** — when a baseline inbound is setting up FCP or HCT (defense).
- **Slow It Down** / **Quick Shot** — when an HCO turn has Slow It Down or Quick Shot set (offense).
- **Final Shot** — when the turn is a Final Turn shot attempt (offense). Not shown for FINAL_HOLD (hold until 0).

At **turn end** (or at specific animation moments), the system announces shot results (e.g. "It's Good!", "Shooting Foul!"), fouls ("Quick Foul", "CHARGE!", "BLOCKING FOUL!", etc.), rebounds, steals, and turnovers. Force Foul animations use the announcement system with the fouling player image and text "Quick Foul" as described in Force Foul Execution above.

---

## Final Turn Execution

**Scope:** All quarters and OT. Q4/OT also applies the Slow It Down / Quick Shot / Force Foul / Run Out branches at the end of this section.

### Clock-driven gate

**Trigger:** Any possession with `time_remaining ≤ 30` seconds that is **not** OREB and **not** Fast Break (state is HCO, HCT, or FCP) is eligible for late-clock execution. There is **no** one-shot-per-period cap — multiple late possessions can occur until the game clock reaches 0.

**Excluded:** OREB and Fast Break turns execute normally; the *next* turn after them is re-evaluated if clock is still ≤ 30.

**Follow-up possessions** (made shot or SIP with time still on the clock) skip full Final Turn setup. After BIP/SIP the backend sets `flss_possession_pending`; the next offense turn runs **FLSS** (sprint-and-shoot with ~1s remaining).

**Implementation:** `BackEnd/utils/eoq_clock_progression.py`, `BackEnd/models/turn_manager.py`, `BackEnd/engine/final_turn_pacing.py`.

---

### Full Final Turn setup (structured possession)

When eligible and not routed to FLSS, Run Out, Force Foul, Quick Shot, or FINAL_HOLD:

**Ball handler:** Prefer live `last_ball_handler` if PG/SG/SF; else random 60% PG / 30% SG / 10% SF.

**Starting alignment (offense):**
- PG / SG: deep upper wing or deep lower wing (random, distinct).
- SF / PF: upper corner, lower corner, upper midCorner, lower midCorner (one upper, one lower).
- C: key.
- If SF is ball handler, SF/SG wing placement is swapped so the BH is always on a deep wing.

**Defense:** Random 2-3 or 3-2 zone; PG at **topLane** (not key).

**Shot choice:** 50% Outside / 50% Attack, except Q4+ trailing by **exactly 3** → forced Outside three.

**Shooter weights:** Rank by SH (outside) or SC+AG (attack); weighted random 50 / 30 / 20 / 9 / 1.

**Play execution (movement):**
- Shooter moves to upper or lower wing on his vertical half (C picks wing at random).
- If BH is shooter: dribble to wing. If not: BH passes from deep key when crossing halves; other 3–4 players fill opposite-half spots (midWing, wing, midCorner, corner, deep wing, deep baseline) without duplication.

**Variable shot anchors** (rolled once per possession → `final_turn_anchor_clock`):
- **Outside:** shoot attempt at `random.randint(1, 3)` seconds remaining.
- **Attack:** drive start at `random.randint(2, 4)` seconds remaining.

**UESS schema playback:** `turn_manager._emit_hco_animation_steps` → `build_skeleton_animation_steps`. Frontend plays full `animation_steps[]` from step 0 — no FE alignment tween, step-0 skip, or coord patch.

**Backend preflight** (`final_turn_pacing.py`): Simulates walk-up, alignment, optional entry pass, and move/pass beats backward from the rolled anchor. Sets `_step_t_floor_game_seconds` on skeleton step 0. Routes to **FLSS** when the graph cannot meet the anchor.

**Final Turn vs FLSS tie-break:** If both would trigger at 0:00, **Final Turn wins** — low-clock routing defers to `resolve_final_turn_shot()` when `final_turn_shot_this_turn` is already set.

**Blocking foul on attack:** Exactly 2 FTs (no and-1, no 3 FTs for a three) when `game_state["final_turn"]` during shot resolve.

**Alignment (backend-owned):** `oDestinations` / `dDestinations` in display orientation; away mirrors with `x_away = 100 - x_home`.

**Announcement:** "Final Shot" when `turn.final_turn` and `result_type !== 'FINAL_HOLD'`.

---

### FLSS — Forced Last Second Shot

**When:**
- Final Turn preflight budget fails (`route_flss`), or
- `game_clock ≤ 0` on an eligible possession and Final Turn is **not** already flagged, or
- `flss_possession_pending` after late-clock BIP/SIP.

**What:** BH sprints for `time_remaining − 1` game seconds, then shoots with ~1s on the clock. No alignment / entry-pass graph.

**Implementation:** `BackEnd/engine/eoq_perfection.py` → `resolve_flss_shot_logic()`, `compute_flss_drive_plan()`, `build_flss_skeleton_steps()`.

Zone logic (normal / penalty / heave) unchanged from EOQ brief. Heave remains terminal.

---

### Post-shot progression when clock > 0

Quarter end is **clock-driven**. After shot resolution (or the **final** FT of a trip), if `time_remaining > 0`:

| Outcome | Next step |
|--------|-----------|
| **Make, no foul** | BIP/SIP → `flss_possession_pending` → FLSS |
| **Miss / Block, OREB** | `pending_oreb` → putback (see OREB rules) |
| **Miss / Block, DREB** | Terminal DREB: rebound animation, clock → 0:00, no outlet |
| **Shooting foul** | FTs (clock stopped); branch after **last** FT only |

When `time_remaining == 0`: `quarter_ends_after`, no BIP/OREB/DREB follow-up. Frontend quarter-end hold (`holdFinalShotMs`, default **2000 ms**).

Turns in this chain carry `late_clock_eoq: true`.

---

### OREB rules (universal)

- **Putback vs kickout:** Normally 90% / 10% (`resolve_offensive_rebound`). When **`time_remaining < 6`**, always putback.
- **Putback floor:** `OREB_PUTBACK_MIN_TIME_ELAPSED = 2` (all putbacks).
- **Block → OREB:** Same late-clock routing as a miss when applicable.

Non-shooting fouls use standard situational logic by time remaining.

---

### Qs 1–3

Same structured Final Turn and clock-driven post-shot progression as Q4 trailing/tied, without Q4-only Run Out / Slow+Force / Quick Shot branches.

---

### Q4 (and OT) situational branches

- **Run Out The Clock** (`should_run_out_clock`): Winning or blowout loss (>18), ≤30s, no force-foul defense → move all players offense-side, clock to 0, no shot.
- **FINAL_HOLD:** Slow It Down, Force Foul false → hold until 0.
- **Slow + Force Foul:** Execute Force Foul; no Final Turn alignment.
- **Quick Shot:** Normal quick-shot HCO (no Final Turn setup). Last 30s only when trailing by **more than 3**.
- **Otherwise (trailing/tied):** Full Final Turn setup.
- **Trailing by exactly 3:** Forced Outside three.
