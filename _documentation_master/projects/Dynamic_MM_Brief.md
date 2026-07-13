
**Objective**
I want to work on our subtle movements (SM) system in HCO turns to add more varability of options in them, where offensvie players will look to do more than just use the SM to get open, but they'll also use them to potentially make a dynamic decisition to get more open or inot a more favorable location to shoot an open or ideal shot. 

This will require two steps
1. We need to make defender movements more dynamic in HCO turns, not just against SM but also against normal skeleton steps, freelance movements, and hot reads. Right now I think we have some dynamism to defender movmeents at each step, but for the most part they seem pretty tied to their offensive player they're guarding at pretty much all costs.
2. We need to add more variability of options to offensive players afte rhtey make an SM, hot read or freelance movement. We should also get clear if these are turly seprate actions or if some of them are the same, just under different names or structure. i.e. are feelance movements simply SM with freelance logic instead of set play/motion logic? Same for hot reads? Are they also SM wiht freelance logic?

I'll pause here, please read the Dynamic_HCO_System.md doc and trace teh code to get up to speed. and as a first step add teh following to teh bottom of this doc

1. A simple and easy for human to read list of our subtle movements (SM)
2. Definitive explanation of how freelance and hot reads relate to SM. Are both logic guiding SM, or something else.

Keep this doc content very simple, clear and focused. I don't need overly verbose and overwhelming explanations of things. That is what our documentaiotn is for. This is a brainstomring doc that will transition to a brief, so clarity and focus is valued over completeness and depth of info.

---

## Trace results (added by Claude)

> **Naming note:** we call these **subtle movements** ("SM"). In code they are `build_subtle_beat` (motion_subtle.py). Separate from the **shot-time** micros (pump fake, dunk, etc.) in `Shot_Micro_Movements_System.md` — those fire at the shot, not mid-possession.

### 1. Our subtle movements (SM)

An SM beat is **one off-pattern nudge inserted between skeleton steps**; the next skeleton step pulls everyone back to their defined spot ("pop back"). It is **positional only** — no ball transfer, no shot.

**Ball handler picks one** (`BH_SUBTLE_MOVES`):
| Move | What it does |
|---|---|
| Hold in place | dribbles without relocating |
| Back out | dribbles 2–5 spots away from the basket |
| Drive in | dribbles 2–5 spots toward the basket |
| Side dribble | slides halfway to an open neighboring perimeter spot (perimeter spots only) |

**Each teammate then makes his own read** (`(player_read + off_eff) × d6 > 110`). Pass → he holds. Clear → he relocates, by where he is:
| Player location | Relocation options |
|---|---|
| Inside | flash to another inside spot (midLane / mid- or high-post), **or** pop out toward the perimeter |
| Perimeter | slide to an adjacent open perimeter spot, **or** hard-step inward (pops back next step) |
| Elsewhere | small drift out from the basket |

### 2. How freelance and hot reads relate to SM

They are **three different layers**, not three names for the same thing.

| | What it is | Movement? |
|---|---|---|
| **Subtle movement (SM)** | one off-pattern beat, then rejoin the skeleton (§1) | yes — its own beat builder `build_subtle_beat` |
| **Freelance** | **abandons** the skeleton and runs a free multi-cycle progression: all five players relocate/nudge each cycle (own beat builder `build_freelance_beat`, wider 9-grid radius, moves to real spots, not read-gated), looping up to 6 cycles until a shot/pass | yes — a **separate** movement mechanic |
| **Hot read** | **not movement at all** — a *label* on the shoot/dish decision. `should_shoot` runs every step; when a genuine mismatch drives an optimal look it tags the shot `hot_read=True`. The shot can be a self-shot or a **dish** (`via_pass`) to an open teammate | no |

**So, definitively:**
- **Freelance is NOT an SM.** They share low-level primitives (radial nudge, coord helpers) but are distinct mechanics: SM = one beat that pops back to the skeleton; freelance = leave the skeleton entirely and free-play to a shot. Freelance is triggered when the defense knocks the BH out of the play (`FREELANCE_FORCED`), not chosen as flavor.
- **Hot read is NOT an SM.** It's the shoot/dish decision layer that runs on *every* step regardless of movement. An SM can *set one up* (the post-subtle `should_shoot`, with an openness bonus if the defender froze), but the hot read itself is the shot decision, not the move.
- SM and freelance are both **movement emissions**; hot read is a **shot decision**.

### 3. How defenders move today (answers Goal 1)

You're right — today defenders are almost entirely **glued to their man**. Per-step placement is `get_defender_coords` → `calculate_defender_coords` (shared_defense.py): a **pure geometric offset** from the assigned offensive player toward the basket, sized by aggression spacing + court spot. The only "randomness" is small cosmetic jitter (`random.randint(-1,1)` … `(2,4)` grid) — visual wobble, not a decision.

**The one real behavioral variance today** is the **SM freeze reaction**: on an SM beat, each defender rolls `(player_read + def_eff) × d6 > 110` (`_roll_subtle_defender_reads`); if his man moved but he *failed* the read, he freezes instead of following (`_subtle_defender_should_freeze`, applied in the animator), leaving the man open. That's it — and it only fires against SM beats, not skeleton steps, freelance, or hot-read dishes.

**Levers that already exist to build on:**
- `aggression_call` (passive / normal / aggressive) already shifts defender **spacing** (via `get_spacing`) — a static tightness offset, not a per-step choice.
- The read roll (`player_read_raw + def_eff`) is the ability signal your dynamism can key off — already used for the freeze, extendable to the other three step types.

So: **Goal 1 = generalize the SM freeze model into a real defender-decision layer** (help, sag, jump the lane, gamble, trail) that runs on *every* HCO step type. Positioning comes from the **defense playcall** (team-wide, per turn), intercept frequency from **team aggression**, and action outcome/freeze from **defender ability** — see §5.

### 4. Defender behavior menu (Goal 1)

Two axes: a **positioning** (team-wide, set per turn by the defense playcall) and an **action** (per defender, per step).

**Positioning** — man-guard vs help balance. **A property of the defense playcall, team-wide, held all turn** (see §5). Fully owns defender spacing (retires the old `get_spacing` aggression map).
| Stance | Meaning |
|---|---|
| normal | balanced between guarding his man and being in help position (default) |
| loose | favors help-defense position over guarding his man |
| tight | favors guarding his man over being in help position |

**Action** — per-defender intent this step:
| Action | Meaning |
|---|---|
| guard | standard defense — guard / help / deny as the situation presents, per the strategy in play |
| deny | deny passes to his assigned man |
| intercept | attempt to intercept a pass — **not a posture choice; a geometric opportunity** (in a pass lane) gated by `aggression_call` (see §5C) |
| help | rotate to provide help on a drive by an offensive player he's *not* guarding (or as the scheme defines) |
| freeze | never desired — the outcome when he gets beat or makes a poor read |

### 5. Where the roll lives (Goal 1) — LOCKED

Three separate signals drive the defense, each from a different source:

| Signal | Source | Cadence |
|---|---|---|
| **Positioning** (tight / normal / loose) | **defense playcall** (team-wide) | per turn |
| **Intercept opportunity** | **geometry** (defender in a pass lane) — posture-independent | per pass |
| **Intercept attempt** | **`aggression_call`** (aggressive 80 / normal 40 / passive 0) | per in-lane opportunity |
| **Action outcome** (success / freeze) | **defender ability** (`player_read_raw + def_eff`) | per step, reactive |

**A. Positioning = playcall property, team-wide, per turn.** We have 4 defense plays (man, 2-3, 3-2, 1-3-1), all **normal** today. We add **tight** and **loose** variants of each. Positioning **fully owns spacing in the HCO dynamic path** — `get_defender_coords`/`calculate_defender_coords` take an optional `posture` (default `None`); `None` = today's `get_spacing` (unchanged for every other turn type — the function is shared with quarter-start / fast-break / HCT / attack-drives / animator), a set posture overrides it. So `get_spacing` is *bypassed* in HCO, not globally retired.
- **Interim implementation:** since the tight/loose playcall variants don't exist yet, **pick loose/normal/tight at random each turn** (team-wide) and apply it. Later, real playcall selection replaces the random pick (P6).
- **Inside-man exception (locked):** posture applies only to defenders guarding a **perimeter** man. A defender on an **inside** man (`is_inside_location`: lowPost / midPost / midLane / basketSpot) **always plays standard normal post D**, regardless of the turn's posture — no tight/loose shade, no lane gamble.
- **Playbook naming (P6):** the coach-facing playbook names the tight posture **"deny"** (e.g. `man deny`, `2-3 zone deny`); internally the code posture is **`tight`**. Mapping: **deny ↔ tight**, **loose ↔ loose**, existing/unsuffixed play ↔ **normal**. **← open decision at P6:** rename the internal `tight` → `deny` for consistency, or keep the mapping at the playcall→posture boundary.

**B. Positioning is coupled to the action menu.** The turn's posture gates which *positioning* actions are on the table (all defenders share the posture). Intercept is **not** here — it's the geometric layer in §C.

| Posture (per turn) | Available actions (per step) | Feel |
|---|---|---|
| tight | deny, guard | commits to the man / the lane, exploitable backdoor |
| normal | guard, help | balanced |
| loose | help, guard | sits in help, concedes the tight man-guard |

**C. Intercept = two gates (geometric + aggression), NOT a posture menu item.** Interception is an *opportunity that emerges from where a defender is standing*, not a chosen action. Redesigned (2026-07-09):

- **Gate 1 — geometric, dynamic, posture-independent.** When a pass is thrown, any defender within **lane range** of it (perpendicular distance; reuse `HCO_PASS_LANE_DIST`) has an interception *opportunity*. Posture shapes this **indirectly, through placement**: a **tight/deny** defender sits in his own man's lane → more opportunities on entry passes to his man; a **loose/help** defender sits toward the middle → fewer on his man, but he lands in **other players' lanes**. Inside-man defenders (locked normal) participate only as their geometry allows. **The passer's own defender is never eligible** — excluded by position (man), so posture sag can't drift him into the outgoing lane to "pick" his own man's pass.
- **Gate 2 — aggression.** An in-lane defender attempts the pick with P by **`aggression_call`**: **aggressive 80% · normal 40% · passive 0%**. (Replaces the earlier "reuse the 0–4 steal-engagement curve" plan.)
- **Then — attribute contest.** An attempt resolves via the existing `resolve_pass_contest` (skill/anticipation) → `INTERCEPT` / `BAT_OOB` / `complete`. A **missed** attempt leaves the gambled-at man open (Goal 2 fuel).

> **Tight vs normal — where the difference lives.** A tight/deny defender hugs his man **on the ball side** (2 grid off, dead-center in the passing lane to his own guy); a normal defender sits a step behind. With a *binary* Gate 1, both register "in his man's lane," so they get a **similar count of opportunities** — tight's edge is **position quality** (dead-center → higher `resolve_pass_contest` success, Gate 3), not more chances. **Loose** is the posture that changes the *opportunity geometry* itself: it leaves the man and lands in **other** players' lanes.

> **Distance gates viability by posture (owner intent, 2026-07-09).** Because Gate 1 is pure geometry (defender must be inside the pass lane), posture determines whether an interception of *his own man's* pass is even possible: **tight** = dead in the lane → **definitely viable**; **normal** = usually in range → **most likely viable**; **loose** = sagged out of his man's lane → **not viable on his man** (only help-side lanes). Loose isn't disabled — it just can't jump its own assignment. Distance should also scale *effectiveness* (contest success), not just viability, in P2 tuning. The pre-existing steal/turnover mechanics (per-step moment + hot-read/kickout pass contest) carry over unchanged.

> **Which passes are interceptable (decided 2026-07-09).** The two-gate contest runs on:
> | Pass type | Interceptable? | Where |
> |---|---|---|
> | Hot-read dish | ✅ (P2a) | `_apply_dish_contest` → `_hco_resolve_dish_contest` |
> | Kickout | ✅ (P2a) | same |
> | **Freelance pass** | ✅ | `_resolve_freelance` reuses `_hco_resolve_dish_contest` on the freelance beat → STEAL via `pass_intercepted`/`_finalize_hco_pass_interception` (passer credited via `passer_pos`) |
> | **Skeleton motion / reversal pass** | ✅ (P2b) | walk hook `_hco_contest_skeleton_pass` (both motion + set-play walks) → same contest → STEAL |
>
> **All pass types now interceptable.** Gated behind `GOB_DYNAMIC_HCO_DEFENSE` (posture set) + Gate 2 aggression. Loose/help defenders now pick swing passes in "other lanes" (their real interception role). Smoke-tested rates on a tight swing lane: aggressive ~16% / normal ~8% / passive 0% per pass.

> **Pass-contest ANIMATION — SHIPPED (as of StepState, 2026-07-13). NOTE: the original "all
> backend-emitted, no imperative send" plan was TRIED and REVERTED for BAT_OOB** — a step-based OOB
> trajectory double-fired with the FE imperative send (ball flew OOB, then bounced back off the
> defender and out again). The two outcomes differ in HOW they animate:
> | | INTERCEPT | BAT_OOB |
> |---|---|---|
> | animation | **backend step-based** (UESS): `steal_reach` defender override → the interceptor steps to the contact point; ball **attaches** to him on the stop step (contact-linked skeleton) | **FE imperative** `_runHctBatOobBallSend` after the steps settle — the schema pipeline can't fly a ball off-court |
> | positions | engine-owned (contact = `pass_contact_point`) | **engine-owned** — contact + exit (`bat_oob_target = nearest_oob_point(contact)`) + deflector; the FE **reads** them (`turnData.bat_oob_target`), only the bounce *shape* is cosmetic FE |
> | stats | STEAL + TO (`is_interception`) | none — offense retains |
> | transition | standard steal (fast-break chance → else HCO) | **SIP, clocks pinned** (`next_play_type=SIDE_INBOUND`, `bat_oob=True`, no flip) |
>
> **UESS status:** INTERCEPT is fully backend-emitted. BAT_OOB is UESS-*compliant on the data* (all game-relevant positions engine-owned; bounce shape is cosmetic) but flown imperatively — a documented residual (see [stepState_gaps.md](stepState_gaps.md) gap #2). **Fixes the random-step bug:** interception no longer routes through `apply_stopper_system_to_skeleton("STEAL")`'s random mid-step — it pins to the actual pass step. HCO/HCT/FCP now all source the OOB exit from the backend. BAT_OOB is NOT a turnover (defender last to touch); same batted-OOB SFX as FCP/HCT, **no secondary announce**.

**D. `freeze` = failed reactive read (ability).** Not a chosen action — the outcome when a defender is beaten or misreads. Generalizes today's SM freeze to every step type; driven by the defender's `player_read_raw + def_eff` roll.

**Net per-turn / per-step flow:**
```
Turn start:  POSTURE = random(loose/normal/tight)   [interim; later = the chosen playcall variant]  — TEAM-WIDE
             posture fully sets spacing + help-shade (perimeter men only; inside men = normal)
Each step:
  1. positioning action (per posture): deny / help / guard
  2. offense action resolves (skeleton / SM / hot-read / freelance) — passes emitted here
  3. INTERCEPT (per pass):  Gate 1 geometry (defender in lane?) → Gate 2 aggression_call
                            (aggr 80 / norm 40 / pass 0) → resolve_pass_contest (attribute) → pick/miss
  4. reactive read (defender ABILITY) → action succeeds, or beaten → freeze / open space (Goal 2 fuel)
```

### 6. Offense response menu (Goal 2) — read & attack the defender's commitment

**The gap today:** the offense reads only **attribute mismatch** (does this player out-shoot/out-drive his defender — `build_motion_read_map`, inside/attack/outside) → a shot or dish. The *only* spatial read is the **binary freeze-openness bonus** on an SM beat. It never reads whether the defender is overplaying, denying, sagging, or gambling — so it can't deliberately attack a commitment. Goal 2 fills exactly that gap, and Goal 1's proactive commitments are what it attacks.

**Everything the offense can do today (baseline):**
| Option | What it does | State |
|---|---|---|
| shoot (self) | `should_shoot` / forced | ✅ |
| dish / kickout | pass to an open teammate who shoots | ✅ |
| SM (reposition) | nudge off-pattern, re-read | ✅ |
| advance / pass_immediate | run the next skeleton step (`pass_immediate` ≈ advance today) | ✅ |
| freelance | break out of the play — **only when knocked out** (`FREELANCE_FORCED`) | ✅ (forced only) |

**New (Goal 2): read the committed posture (§5), pick a response that punishes it.** Mirror of §4 — an offensive read roll (`(read + off_eff) × d6`, ability now / team strategy later) keyed to what the defender committed:

| Defender committed (§4–5) | Space it opens | Offense response (new) |
|---|---|---|
| **tight / deny** (overplays man or lane) | behind him / backdoor | **backdoor** to the rim, or **relocate** off the denied lane to a new open spot |
| **loose / help** (sags off, concedes the man) | the man's own spot | **step-in shot** (take the conceded look), or **relocate into** the vacated help-side |
| **intercept** (gambles the lane) | the man, if the gamble misses | **attack** the now-open man (the pass itself stays contested, §4 pass model) |
| **normal / guard** | nothing special | today's behavior: run play / SM / mismatch shot |

**Offense action vocabulary (new vs existing):**
| Action | New? | Exploits |
|---|---|---|
| shoot | existing | a conceded / mismatch look |
| dish / pass | existing | an open teammate |
| attack (drive to rim) | existing (`attack_drive_clearance`) — **new trigger** (read a beaten gamble / closeout) | loose / help closeout, or a beaten gamble |
| SM (reposition) | existing | probe for a read |
| relocate (to a better open spot) | partial — freelance-only today | vacated help-side space |
| **backdoor** | **new** | a tight / deny overplay |

> **Naming:** we already have **`attack`** (= drive to the rim; what we informally called "drive"). We also have a generic **`cut`** action that's really just a standard move — so the new backdoor action is named **`backdoor`** (not "backdoor cut") to avoid collision. (`cut` itself may want a clearer name later.)

**Ready-made building blocks in code:** `motion_subtle.py` explicitly **defers** two off-ball ball-transfer variants — *"flash to receive a quick pass and shoot"* and *"cut to the basket and receive a pass from the BH."* Those are precisely the relocate-and-catch / backdoor Goal-2 actions; un-deferring them is a natural first build. Primitives also exist for drive-in (BH `"in"`), move (`"cut"`), and relocate-to-spot (freelance).

**Dish + reception logic today (and a Goal-2 gap):** the BH *already* reads a teammate's mismatch and dishes — `should_shoot(allow_dish=True)` scans all five, and if a teammate's optimal look beats the BH's own it returns `via_pass` to that teammate (the "collapsed hot read as a dish"; plus the desperation `KICKOUT_SHOOT`). But the **receiver has no agency**: his shot type is chosen at *dish* time, `_execute_motion_decision` emits `pass→receive→shoot`, receptions pass `allow_dish=False` (no re-dish), and there's no catch-and-drive / second read — only the dish interception contest (§4) can intervene. **Goal-2 opportunity:** give the receiver his **own read on the catch** (shoot / `attack` a closeout / re-dish / SM), reading how *his* defender closes out. Fits naturally as a P4/P5 add-on.

**Symmetry (the whole design in one line):** Goal 1 defender **commits** → Goal 2 offense **reads the commitment and attacks the space** — same read-roll machinery (`(read + eff) × d6` vs a bar), pointed both directions. The proactive defender gamble is *designed* to be the thing the offense punishes. That is the objective: an SM becomes a **dynamic decision to get more open / into a better shot**, not just a nudge.

Net-new offense action to build: **`backdoor`** (one new emitter/beat). `attack` and `relocate` already exist — Goal 2 mostly adds the *reads that trigger* them off a defender commitment.

---

## 7. Phased build brief

**Flag:** `GOB_DYNAMIC_HCO_DEFENSE` — gates the whole feature (Goal 1 + Goal 2). (The motion/set-play flags `GOB_DYNAMIC_HCO_MOTION`/`_SETPLAY` were **retired** — those paths are always-on now, so this is the one remaining HCO gate.) Off → today's glued-to-man behavior. Each phase ships behind it and is testable in isolation.

**Load-bearing architecture constraint (updated for StepState, 2026-07):** the offense's spatial read (Goal 2) **and** the interception contest must see the **same** defender coords the FE renders. This is now **guaranteed by the shared defender grid** (resolve-once → freeze → draw), not a discipline of "route through the reconstruction":
- The engine stamps `compute_defender_grid` (the animator's **own draw code**) on each step *pre-contest* (`_stamp_contest_defender_grid`); the contest reads it via `_hco_step_def_xy`. The emit stashes its exact per-player animations (`game._hco_render_animations`) → `build_step_states` → `StepState.defense`. So **contest == render == the one frozen grid** (live `🔬 STEPSTATE GAP` = 0% man+zone). This is the [[project_emitter_as_god]] façade, realized.
- **Therefore: posture/action shading MUST live inside the placement code `compute_defender_grid` draws** (`get_defender_coords`/`calculate_defender_coords` with the `posture` param) — so the shading rides into BOTH the stamped contest grid and the rendered grid automatically. **Never** shade in the animator's render path alone (contest wouldn't see it) or in the contest alone (render wouldn't) — either breaks the single-source guarantee (UESS teleport risk).
- **Goal 2's spatial read reads the FROZEN grid** (`StepState.defense` / the stamped step grid) — never a fresh reconstruction — so the offense reads exactly what's drawn. The legacy per-mode reconstruction (`get_defender_coords` man / `assign_all_zone_defenders` zone) survives only as the *unstamped fallback*.

**Build man first, then zone parity** within each phase (zone already flows through the same `compute_defender_grid` draw + stamp; posture *placement* for zone is the net-new bit).

| Phase | Goal | Key files | New constants |
|---|---|---|---|
| **P1 — Posture + coord shading** | Pick a **team-wide posture per turn** (interim: `random(loose/normal/tight)`); posture shades every defender (on-ball cushion, off-ball ball-side deny / help-shade), with inside-man lock. Add optional `posture` param (default `None` = unchanged `get_spacing` for all non-HCO callers). Purely positional — visible + testable on its own. | `phase_resolution.py` (`_roll_defense_posture`, store on `game_state`), `shared_defense.py` (`calculate_defender_coords`/`get_defender_coords` take optional `posture`; HCO passes it, others don't) | `POSTURE_SPACING`, `POSTURE_HELP_SHADE`, `DENY_DISTANCE` (ported from the proof) |

> **P1 alignment (do FIRST, before coding):**
> - **No "help position" exists in the geometry today.** `get_spacing` only slides the defender 1–4 grid *along the man→basket line* (BH 2/3/4, non-BH 1/2/3); he's always man-anchored. Today's placement ≈ **tight/normal**. **`loose` (favor help) is net-new geometry.** Posture now owns spacing outright — `get_spacing` is retired.
> - **New primitive to define: "help position"** = a point shaded off the man toward the ball-line / nail / paint. `tight` = man-anchored (≈ today); `normal` = shade partway; `loose` = shade most of the way.
> - **Split the P1 work:** posture is picked at random per turn (trivial — no distribution to tune yet), so the prototype's job here is small; the real work is the **placement geometry**, which needs **visual verification in the running app** (screenshots) — the prototype can't judge spatial correctness.
| **P2 — Per-step defender action + intercept** | *Positioning actions:* within the posture, each defender takes deny/help/guard. *Intercept (two gates):* on any pass, **Gate 1** = defender geometrically in the lane (reuse `HCO_PASS_LANE_DIST`), **Gate 2** = attempt per `aggression_call` (aggr 80 / norm 40 / pass 0), then `resolve_pass_contest`. Extends contests to **all** passes (skeleton included). Generalizes `_roll_subtle_defender_reads` to every step type. | `phase_resolution.py` (positioning action selector; per-pass intercept gate **inside the unified `_resolve_hco_offense_shot_dynamic` walk** — the moment/interception is fused, not a separate walk), `pass_contest.py` (`resolve_pass_contest`) | `POSTURE_ACTION_MENU[posture]`, `INTERCEPT_ATTEMPT_PCT_BY_CALL = {aggressive:80, normal:40, passive:0}` |
| **P3 — Reactive resolution + generalized openness** | After the offense acts, resolve the committed action: success, or beaten → the man is open. Replace the binary SM-only freeze bonus with a **graded spatial openness** read from the **frozen grid** (`StepState.defense` / the stamped step grid — the same coords the FE draws), NOT a fresh reconstruction. | `phase_resolution.py` (openness from the stamped grid), `animator.py` (`_subtle_defender_should_freeze` → general reactive geometry, still render-side) | `OPENNESS_FROM_GAP` scale |
| **P4 — Offense reads (existing actions)** | `should_shoot` / a new read step reads the defender's *commitment/space* (not just attribute mismatch) and triggers **existing** responses: step-in shot (loose/help), `attack` (beaten gamble/closeout), `relocate` (vacated help-side). **The spatial signal MUST read the stamped/frozen defender grid** (what's drawn), keeping the read UESS-consistent with the picture. | `motion_step_decision.py` (`should_shoot`, new read helper), `motion_read_map.py` (spatial signal from the stamped grid alongside the mismatch map) | `OFFENSE_READ_BAR`, `STEP_IN_OPENNESS_MIN` |
| **P5 — New `backdoor` action + receiver agency** | Build the `backdoor` beat (hard cut behind a tight/deny overplay to the rim → layup or catch-and-shoot). Un-defer motion_subtle's two ball-transfer variants as its catch forms. **Give the dish receiver his own read on the catch** (shoot / `attack` closeout / re-dish / SM) — replaces the forced catch-and-shoot (§6). | new `motion_backdoor.py` (mirror `motion_subtle.py`), `phase_resolution.py` (route + reception read in `_execute_motion_decision`), `skeleton_step_emitter.py` (stamp), `motion_subtle.py` (un-defer) | `BACKDOOR_ARCHETYPE`, `BACKDOOR_TRIGGER_BAR`, `RECEIVER_READ_BAR` |
| **P6 — Real playbook variants** | Replace P1's interim `random(posture)` with **coach-selectable playbook plays** per posture. Add to the playbook (owner spec 2026-07-09): **man normal** (exists), **man deny**, **man loose**; zones keep existing names as the *normal* (implied) — **2-3 zone / 3-2 zone / 1-3-1 zone** — and add **`<zone> deny`** + **`<zone> loose`** variants. → 4 base × 3 = **12 playcalls** (4 exist, **8 new**). The chosen playcall sets the turn's posture (no random). | playbook/defense-play definitions, `_roll_defense_posture` → derive posture from playcall | — (playbook data) |
| **P7 — Zone parity, tune, tests, docs** | Confirm every phase's zone path (via `assign_all_zone_defenders`); Monte-Carlo tune the constants; unit tests per phase; fold into `Dynamic_HCO_System.md`. | `tests/test_dynamic_defense_*.py`, `dynamic_defense_prototype.py`, `Dynamic_HCO_System.md` | — |

**Dependency order:** P1→P2→P3 (defender side, Goal 1) then P4→P5 (offense side, Goal 2). P6/P7 layer on after the core reads right. Each phase is shippable behind the flag; P1 alone already changes what the coach sees.

**Ship checkpoint after P3:** Goal 1 is fully functional (dynamic defenders — posture + actions on every step type) even before any offense read exists — a natural first release.

---

## 8. Build status — traced 2026-07-13 (all committed on `develop`, tree clean)

Flag `GOB_DYNAMIC_HCO_DEFENSE` **default-ON** in prod. Everything below is committed; no uncommitted work.

| Phase / piece | Status | Evidence |
|---|---|---|
| **P1** posture roll + coord shading | ✅ **DONE — man only** | `_roll_defense_posture` ([phase_resolution.py:4585](BackEnd/engine/phase_resolution.py#L4585)); `_apply_defender_posture` + `posture` param ([shared_defense.py:1785](BackEnd/utils/shared_defense.py#L1785)); animator threads posture to man defenders ([animator.py:2131](BackEnd/models/animator.py#L2131)). Inside-man lock present. Constants renamed vs brief: `POSTURE_ONBALL_CUSHION_DELTA` / `POSTURE_DENY_DISTANCE` / `POSTURE_HELP_ANCHOR_FRAC` / `POSTURE_HELP_SHADE`. |
| **P2** two-gate intercept (all pass types) | ✅ **DONE** | Gate1 `defenders_in_lane`, Gate2 `INTERCEPT_ATTEMPT_PCT_BY_CALL {80/40/0}` ([:4823](BackEnd/engine/phase_resolution.py#L4823)), Gate3 `resolve_pass_contest`. Covers dish/kickout (`_hco_resolve_dish_contest`), freelance ([:6145](BackEnd/engine/phase_resolution.py#L6145)), skeleton motion+setplay (`_hco_contest_skeleton_pass`), final-skeleton coverage (`_hco_contest_final_skeleton`). Passer's own man / on-ball zone defender excluded. Funnel diagnostics (`_track_hco_intercept_gates`). INTERCEPT animation = backend step-based; BAT_OOB = imperative FE send reading engine-owned `bat_oob_target` (the earlier step-based bat-OOB was reverted — it double-fired; see §5C). HCO pass-contest calibration live at spec values (175/200/170 — the Jul-12 "force interception" temp override was reverted). The INTERCEPT/BAT_OOB *ratio* is now the named constant `PASS_DEFLECT_KIND_D` (was an inline `200`). |
| **P2** per-step deny/help/guard **action menu** | ⚠️ **FOLDED, not built** | No `POSTURE_ACTION_MENU`. The deny/help "action" is expressed only through posture-driven placement, not a per-step discrete action roll. |
| **P2** generalize `_roll_subtle_defender_reads` to every step type | ❌ **not done** | still SM-beat-only. |
| **P3** reactive resolution + graded openness | ❌ **not started** | animator still fires SM-only `_subtle_defender_should_freeze` ([animator.py:2026](BackEnd/models/animator.py#L2026), [:2300](BackEnd/models/animator.py#L2300)); no `OPENNESS_FROM_GAP`. |
| **P4** offense reads (existing actions) | ❌ **not started** | no spatial commitment read; no step-in / relocate / attack trigger off a posture. |
| **P5** `backdoor` action + receiver agency | ❌ **not started** | no `motion_backdoor.py`, no `backdoor` action, receiver still forced catch-and-shoot. |
| **P6** real playbook variants | ❌ **not started** | still interim `random(loose/normal/tight)` in `_roll_defense_posture`. |
| **P7** zone parity / tune / tests / docs | ⚠️ **partial** | zone *intercept* works via the shared grid (`_zone_bh_defender`, stamped `compute_defender_grid`); the **`Dynamic_HCO_System.md` § Dynamic Defense fold-in is DONE** (P1 posture + P2 intercept documented). Still outstanding: zone *posture placement*, Monte-Carlo tuning, unit tests. |

**Net:** Goal 1 defender side is ~⅔ built — **P1 posture placement (man) + the full P2 pass-intercept model are live and committed.** Remaining Goal 1: the per-step action menu, P3 reactive-read generalization (the actual "get beat → open man" spatial layer), and zone posture parity. **Goal 2 (P4/P5 offense reads + backdoor) is untouched.**

**Stale in-code comment to fix:** [phase_resolution.py:4575](BackEnd/engine/phase_resolution.py#L4575) still says *"in-development (P1 = man-defense posture placement only)"* — inaccurate now that the whole P2 intercept model is built.