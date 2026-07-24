# Dynamic HCO Motion — Build Brief

> **Status:** Archived (July 2026). Dynamic HCO motion shipped (flagged: `GOB_DYNAMIC_HCO_MOTION`). **Canonical runtime doc:** [`Dynamic_HCO_System.md`](../../06_Gameplay_Systems/Dynamic_HCO_System.md). This file retains build-phase rationale, phase log, and condition matrix.

> 📄 **Authoritative system doc:** [Dynamic_HCO_System.md](../../06_Gameplay_Systems/Dynamic_HCO_System.md) — full architecture, **Tunable Constants**, key files. This brief is build-phase scratch (rationale, phase log).

**Base Behavior**
- Offense team executes the called Motion play per the defined skeleton

**Non-Skeleton Movement Options**
- Subtle Movement
- Freelance Audible
- Freelance Forced
- Hot Read

**Subtle Movement**
- Definition: these are small micro movements by one or more offensive players during a step
- Benefits
    - Breaks the mononotous pattern of structred movements without breaking the overall flow of the motion skeleton. This makes the play a bit harder (or less easy is a more accurate term) for the defense to read and react to.
    - Allows the offender to potentially spot opportunities they would not notice if they simply stay wihtin the predefined motion skeleton
- Risks
    - May throw off the team's motion skeleton progression and force them into a suboptimal freelance situation
- Movements
    - All of these have the primary objective of simply doing something slightly off pattern to keep the defense off balance. The explanations below describe additional potential objectives for each.
    - Ball Handler Movements
        - Ball handler dribbles in place or stands in place without dribbling to assess the situation or deal with the defensive pressure (no movement)
        - Ball Hanlder dribbles a few grid spots backward to assess the situation (2-5 euclidan grid spots away from the basket)
        - Ball Handler dribbles to teh side, only applies if he's positiond outside the three point line and his movement stays outside the three point line - up to halfway between his spot and the next defined spot (i.e. if he's at the key he'll dribble half way toward the upper or lower midWing) -- these are only possible when the bordering spot is unoccupied by a teammate
        - Ball Handler slowly dribbles in a few grid spots toward the basket. This allows him to get a feel for the status of his defender, as well as survey his teammates down on teh block for a quick pass, or his teammates on the outside who may be able to sneak to an open spot is his dribbling in draws other defenders inward. (2-5 euclidian grid spots toward the basket)
    - Non Ball Handler Movements -- only occur if the ball handler executes a subtle movement or we're in a freelance situaton (forced or audible)
        - **note for all fo these, if the bh is in a subtle movement, the non-bh player will hold at this new spot until either the next predefined skeleton step is put into motion, in which case he'll go to his spot defined in that step. Or if a shot is attempted, he'll behave as he normally does for the shot attempt -- either getting into rebound position or attempting to cut of the drive if it is an attack shot and he is within distance of the drive path. If the bh is in a freelance situation, the player will hold this position until freelance starts then he'll execute freelance as defined below.
        - movements:
            - lowPost players can flash to the midLane, one of the midPost or one of the highPost spots to receive a quick pass and attempt an inside or attack shot, or make a a quick pass to a teammate as teh pass sucks teh defenders inward.
            - players outside the 3-point arc can slide to an open spot outside the 3-point arc in an attempt to get more open
            - outsie players can take a few hard steps (2-5 euclidian grid spots) inward then pop back to their startig spot in an attempt to shake their defender and create an Freelance Audible/Hot Read shot
            - outside players can take a few hard steps inward (2-5 euclidian grid spots) to see if they can beat their defender and execut a cut toward the basket and receive a pass form teh bh. This is particularly effective against aggressive defenses that are over playing a deny the pass or high pressure.
            - inside paleyrs can slide a few steps outward (2-5 euclidian grid spots) toward a teammate on the outside to feel out the oppoortunit to set a backdoor cut

**Freelance Audible**
- Definition: a purposeful decision to break the motion offense skeleton and enter freelance progression
- Benefits:
    - Creates opportunities outside the standard motion skeleton
    - Serves as an overall pallette cleanser keeping the defense off-balance in continusouly anticipating established motion patterned plays.
- Risks
    - Easy for offense to flub execution and force themselves into a sub-optimal situation with increased chance of committing a turnover, committing a foul, or taking a bad shot.

**Freelance Forced**
- Definition: motion offense gets disrupted, either due to poor offense execution or superior defense execution, and offense is forced into a freelance progression. This differs from Freelance Audible in that the Audicle is a conscious choice by the offense, while Forced is a situation where the offense is forced into it.
- Benefits
    - Limited, only real benefit is it keeps the HCO turn alive so the offense can attempt a shot
- Risks
    - High likelihood of sub-optimal offensive sitatuion like turnover, offensive foul, or poor shot attempt.

**Hot Read**
- Definiation: offense makes a conscious choice to break from the motion skeleton in an attempt to take advantage of a specific situation. This is like a Freelance Audible in that is a conscious choice, but different in that it is done so with a specific opportunity in mind, whereas the Freelance Audible is purely a conscious choice to try something different with no specific opportunity identified.
- Benefits
    - Offense has identified an ideal situation and has an opportunity to take advantage of it.
- Risks
    - This is reliant on the offensive player making the right reat that the Hot Read is actually a good opportunity. If it is not, it can lead to a suboptimal siituation that leads to a turnover, offensive foul, or poor shot attempt.
- Speciic Hot Reads
    - Ball handler realizes he has an opportunity for an advantage in an outside or attack shot based on the defender who is guarding him.
    - Ball handler realize a teammate has an opportunity for and advantage in an outside, attack, or inside shot based on the defender who is guarding them. 
- Hot Read criteria per shot type is locaiton based
    - Potential inside shot, potential shooter must be stationed at an inside location: lower/upper lowPost, lower/upper midPost, midLane, basketSpot, or a grid spot within that geometric area
    - Potential Outside or Attack shot: potential shooter must be located at any non-inside location or a grid spot otuside the geometric inside spots area

**Movement Options Logic per HCO turn**
- Step 0: 
    - Start with an offensive player level data structure, below is my porposed data structure but tell me what you recommend based on our data persistence methods and SS&S rules:
        {player string id: {"inside": false, "attack": false, "outside": false}} x 5 (one for each offensive player). Also if we use this structure, LMK if we should store all five of these object to a list attached to teh team document. Note these true/false values to not persist beyond hte HCO turn. They start every new turn as false. Unless you think it's best to set these once coming out of the set lineup screen, then persist them wihtin the game until either team changes their lineup so we don't need to run the calculation at the start of each HCO turn?
- Step 1: Determine if any mismatches favor the offense to set any Movement Options to True
    - if defense playcall is a man defense:
        - Identify man defense matchups and calculate each matchup's Shot Type Scores
            - Inside Score: ((offender's SC + ST) - (defender's ID + ST)) / 2 
            - Outside Score: (offender's SH) - (defender's OD) 
            - Attack Score: ((offender's SC + AG) - (defender's ID + AG)) / 2 
            - there will be 15 scores total, 3 for each matchup.
                - if a player has a score > 15, then that Movement Option is true. 
                    - Example: Offense PG has +28 Attack Score, -7 Inside Score, +11 Outside Score 
                     - {player string id: {"inside": false, "attack": true, "outside": false}}    
    - elif defense playcall is a zone defense:
        - Calculate Defense Shot Scores on a team level, delineated by zone areas
            - Inside D Score = average of ((ID + ST) / 2) for any D player whose zone area touches an inside spot (sum of (ID+ST)/2 across those players / number of those players)
            - Outside D Score = average of OD for any D player whose zone area touches an outside spot (sum of OD across those players / number of those players)
            - Attack D Score = average of ((ID + AG) / 2) for any D player whose zone area touches an attack spot (sum of (ID+AG)/2 across those players / number of those players)
        - Calculate offense Shot Scores on an individual level
            - Each players (SC+ST) / 2 = players inside score
            - Each player's SH = outside score
            - Each player's (SC + AG) / 2 = attack score
        - Calculate the 15 Mismatch Scores same as we do for man defense and set the appropriate data items to true if applicable
    - any player/shot type values that are true will be potential optimal reads for the offense as they execute their HCO turn
        
- Step 2: run the motion skeleton, and at each step calculat the following
    - Does the ball handler choose to execute a sekelton stopping action, a hot read or freelance audible or subtle movement, or move immediately to the next step in the skeleton?
    - calculation
        - offense_score = (raw bh read + offense team discipline) * random.randint(1,6)
            - raw bh read = (IQ*0.8 + CH*0.2) — i.e. the player_read() formula WITHOUT its internal random roll. The single outer random.randint(1,6) is the only roll (no double random), and discipline scales with it.
        - if offense_score < 110 run the nested logic here, else proceed to the progression point noted below:
            - tempo modifier: slow = -25, normal = 0, fast = 25
            - roll = random.randint(1,100) + tempo modifier
            - if roll > 4 * current shot clock value, ball handler chooses a skeleton breaking action
                - 75% shot attempt
                    - Inside Shot if he is at an inside location
                    - he chooses to attack shot our outside shot via the following logic
                        - attack score = (bh AG + SC) / 2
                        - outside score = bh SH
                        - sum = attack score + outside score
                        - shot_roll = random.randint(1, sum)
                        - if shot_roll <= attack_score, attack shot is chosen, else outside shot is chosen
                - 25% chance the bh passes to a random teammate within 10 euclidian grid spots, and that receiver immediately shoots (catch-and-shoot) — choosing Inside (if at an inside location) else Attack/Outside via the same logic above, using the RECEIVER's location and attributes. This terminates the turn and enters normal shot resolution. If no teammate is within 10 grid spots, the bh shoots himself via the same logic.
            - else proceed to the progression point
        - porgression point: calculate defense score
            - defense_score = (raw bh defender defensive action + defense team fight) * random.randint(1,6)
                - The single outer random.randint(1,6) is the only roll (no double random), and fight scales with it.
            - raw defensive action = inside defense if ball handler is at an inside location, else outside/pressure defense — each is the helper formula WITHOUT its internal random roll:
                - raw inside defense (paint defender formula, reused from shot resolution): (ID*0.6 + ST*0.2 + IQ*0.1 + CH*0.1)
                - raw outside/pressure defense (calculate_defender_pressure_score sans roll): (OD*0.3 + AG*0.3 + IQ*0.2 + CH*0.2) [* 0.9 if zone]
        - if offense_score > defense_score + defense team def efficiency + defense team chemistry
            - hot read is possible if one exists in this step
                - if hot read exists
                    - 50% it is executed and 50% it is not. Thresholds are adjusted for offense team aggressiveness setting
                        - aggressive: 70% executed, 30% not executed
                        - passive: 30% executed, 70% not executed
                    -if the ball handler executes:
                        - the ball handler's first read is for himself, if he is in a hot read situation, he'll attempt the shot. If he is in multiple hot read situations, choose one at random.
                        - then he'll identify teammates in a hot read situation, if multiple exist, choose the one closest to the bh. If there is a tie, choose one at random.
                    -if the ball handler does not execute, there is not subtle movement and we move immediately to the next skeleton step
                - if hot read does not exist, we move immediately to the next skeleton step
        - elif the defense score > offense score + offense team off efficiency + offenste team chemsitry
            - disruption moment happens
                - 50% chance this is a subtle movement is forced 
                - 20% chance a Freelance Forced is forced
                - 30% chance no effect
                - these thresholds adjust based on the defense team's aggression setting
                    - aggressive (Freelance Forced + 10%, no effect -10%)
                    - passive (Freelance Forced -10%, no effect +10%)
        - else 50% chance the ball handler does a Subtle Movement and 50% chance he passes immediately. These thresholds are are adjusted based on offense teama and defense team aggressiveness settings.
            - offenset team
                - aggressive: pass immediately + 20%, subtle movement -20%
                - passive: pass immediately -20%, subtle movement +20%
            - defense team:
                - aggressive: pass immediately -20%, subtle movement +20%
                - passive: pass immediately +20%, subtle movement -20%
            **note these can cancel each other out for no net effect, or they can build on each other to create a 90/10 scenario


**Spot Classifications For Shot Type**
- Inside Spots: lower/upper lowPost, lower/upper midPost, midLane, basketSpot — plus the geometric area bounded by these (extending to the baseline along the upper lowPost → basketSpot → lower lowPost line), including grid spots within that area
- Subtle-step elapsed by tempo (see `SUBTLE_STEP_ELAPSED_BY_TEMPO` / Tunable Constants for the live values): slow `randint(3,4)` / normal `randint(2,4)` / fast `randint(2,3)`
- advence trigger for subtle movement steps will be the floor being reached, no player's movements
- each non bh offender/ Attack Spots: any non-inside spot (named spots and grid spots outside the inside area above)

**Hot Reads exist at a step if...**
- A player with a shot type = true is placed at a spot within that shot type area

**Freelance Behavior**
- if the offense enters a freelance situation, players will randomly choose to:
    - execute a subtle movmeent (50%)
    - or move to a new predefined location (predefined as it exists in our constants) that is wihtin 9 euclidian grid spots of his existing location
    - if offense team off eff + team chemsitry > 15, players can never move to the same location
    - if players do move to the same location, execute a visual collission effect (both sprites reach the spot and rattle off each other -- rattle each sprite 3x back and forth like we rattle rim shots, then have them land offset from the target spot by 2 euclidian grid spots, in oppositte directions)
- shot attempt resolution: use the same shot resolutio logic, including use of tempo modifier, as is detailed above for normal HCO skeleton steps.
    - if the ball hanlder does not choose to shoot, he will then choose to pass to a teammate within 20 euclidian grid spots of him (80%) or hold the ball in place (20%). 
    - if no teammate is within 20 euclidian grid spots, he'll shoot, choosing Inside/Attack/Outside via the same logic as above.

---

## Tunable Constants

Live values in `BackEnd/engine/motion_step_decision.py`. `aggr(±x)` = add `+x` if the team's aggression call is aggressive, `-x` if passive, `0` if normal. All probabilities are per-step.

**Read routing — decides which branch fires (line refs in `decide_step_action`)**

| Constant | Where | Value | What it does |
|---|---|---|---|
| `DESPERATION_OFFENSE_CEILING` | L29 | `110` | Offense_score below this enables the shot-clock desperation pre-check; at/above it, skip straight to the read. |
| Desperation shot-clock multiplier | L235 | `tempo based - see below` | Forces a shot when `d100 + tempo > 4 × shot_clock_remaining` (lower = forces earlier). |
    - offense slow tempo | `3×` |
    - offense normal tempo | `4×` |
    - offense fast tempo | `5×` |
| `TEMPO_MOD` | L31 | `slow −25 / normal 0 / fast +25` | Added to the desperation roll so faster tempo forces shots sooner. |
| Offense-wins margin | L248 | `def_eff + def_chem` | Offense wins the read (hot-read branch) only if `offense_score` beats `defense_score` by more than this. |
| Defense-wins margin | L250 | `off_eff + off_chem` | Defense wins the read (disruption branch) only if `defense_score` beats `offense_score` by more than this; otherwise neutral. |

**Branch probabilities — the direct subtle-movement dials**

| Constant | Where | Value | What it does |
|---|---|---|---|
| Desperation BH-shoot share | L110 | `0.75` | On a forced possession, chance the ball handler shoots himself vs kicking out to a teammate (`0.25`). |
| Hot-read execute % | L147 | `0.50 + aggr(±0.20)` | When offense wins the read, chance it actually executes the hot read vs advancing to the next skeleton step. |
| Disruption Freelance-Forced % | L167 | `0.20 + aggr(±0.10)` | When defense wins the read, chance the possession breaks into forced freelance. |
| Disruption none % | L168 | `0.30 + aggr(∓0.10)` | When defense wins the read, chance nothing happens and play advances to the next step. |
| **Disruption subtle %** | L170 | remainder ≈ `0.50` | When defense wins the read, chance the ball handler does a subtle movement (whatever's left after FF + none). |
| Neutral pass-immediate % | L180 | `0.50 + off_aggr(±0.20) + def_aggr(∓0.20)`, clamped `[0.10, 0.90]` | When neither side wins the read, chance the ball handler passes immediately vs doing a subtle movement. |
| **Neutral subtle %** | L184 | remainder of pass % | When neither side wins the read, chance the ball handler does a subtle movement. |
| `KICKOUT_MAX_DIST` | L30 | `10` | Max euclidean grid distance for a desperation kick-out target. |

The two bolded rows are the actual "do a subtle movement" probabilities; the `±0.20` / `±0.10` aggression deltas and the `[0.10, 0.90]` clamp are also dials. Update this table whenever the code values change.

**Subtle-step execution dials (Updated Subtle Movement Logic — IMPLEMENTED)**

Once the BH commits to a subtle movement, these govern who moves, how long the step takes, and the shot-clock backstop. Constants in `motion_step_decision.py`.

| Constant | Value | What it does |
|---|---|---|
| `MOTION_READ_THRESHOLD` | `110` | Single shared read threshold: a `(player_read_raw + team_eff) * d6` read clears when `> 110`. Used by the per-teammate offense read, the per-defender read, and the desperation ceiling. |
| `SUBTLE_STEP_ELAPSED_BY_TEMPO` | `slow (3,4) / normal (2,4) / fast (2,3)` | Game-seconds elapsed floor for a subtle step by offense tempo (the emitter honors it; the slowest mover's natural travel can exceed it). Replaces the old `~0.5s` floor for subtle beats. |
| `SUBTLE_FORCED_SHOT_PENALTY` | `50` | Subtracted from `shot_score` when the BH is forced to shoot because the subtle step ran the shot clock to expiry. |

Removed: `NON_BH_MOVE_PROB` (the old flat 50% teammate coin flip) — teammates now gate on the offense read.


## Updated Subtle Movement Logic (IMPLEMENTED)

Triggered once the BH commits to a subtle movement (how he gets there is the **Turn-Level Read Gating & Condition Matrix** below). `read = (player_read_raw + team_eff) * randint(1,6)`; clears at `> MOTION_READ_THRESHOLD` (110). `player_read_raw = IQ*0.8 + CH*0.2`.

**Offense** — `build_subtle_beat` (`motion_subtle.py`):
- BH always moves (he chose it). Each non-BH teammate makes his own read with the offense team's `offensive_efficiency`; clears the threshold AND has an applicable move → he relocates, else holds. (Replaces the old flat 50% coin flip — smart teams move together, weak readers are hit-and-miss.)
- Step elapsed = a tempo floor (`SUBTLE_STEP_ELAPSED_BY_TEMPO`) the emitter honors, so the deliberate pace costs real game/shot clock.

**Defense** — read rolled in the resolver (`_roll_subtle_defender_reads`), applied geometrically in the animator (`_subtle_defender_should_freeze`, man + zone loops):
- Each defender (incl. the BH defender) reads with the defense team's `defensive_efficiency`. Clears → he tracks his man's new spot; fails → he **freezes** at his prior coords (disengaging auto-tracking — this is what opens the space). If his guarded man didn't move, he holds regardless of the read.
- Anchor (who he's guarding): man = matchup; zone = the per-step assignment `game.zone_defender_assignments_by_step` (`defender_to_offensive_player`, which always assigns one offender — falls back to the BH). On the next skeleton step the zone defender reverts to zone positioning automatically (stateless, recomputed per step).

**Shot-clock backstop** — if finishing a subtle beat would leave `< 1s`, the BH (still holding) is forced to shoot at the 1-second mark: Inside if at an inside location, else Outside (no time for an attack drive), with a `SUBTLE_FORCED_SHOT_PENALTY` (−50) to `shot_score`. The resolver tracks a running shot-clock estimate (subtle floors exact + per-skeleton-step travel estimate); the emitter remains the authoritative timer.

**Stopping actions (G3):** the subtle beat carries an `events` list and the resolver can terminate the walk on a subtle step (the forced shot is the first such case) — structurally ready for fouls/turnovers/quick-shots later.

**Verified — does a frozen defender organically create offense opportunity?** Yes, strongest on attack shots: contest is geometric (`uncontested = len(_guardians_within_radius(shooter_coords, defender_end_coords)) == 0`, `attack_drive_clearance.py`), so a held defender drops out of the contest radius → uncontested → higher shoot-prob/score; pass openness is distance-based the same way. Caveat: plain named-spot inside/outside shots may score contest from the assigned defender's attributes rather than exact distance, so the spacing payoff there is weaker until those are routed through the geometry contest too.

---

## Turn-Level Read Gating & Condition Matrix (IMPLEMENTED)

**Rolled once per HCO turn** in the dynamic resolver (`_resolve_motion_offense_shot_dynamic`), both on a 0–4 scale via `strategy_settings` (defaults 2):
- **Offense:** `random.randint(0,4) <= alterations` → offense executes **reads** this turn (Dynamic HCO). Else it runs the skeleton.
- **Defense:** `random.randint(0,4) <= aggression` → defense executes **pressure** this turn. Else it has no read impact.
- (Currently gates **Motion** plays only; the roll moves to turn setup when Set Play reads land. Sits under the `GOB_DYNAMIC_HCO_MOTION` master flag.)

**The universal `should_shoot` decision runs FIRST each step (see below) — a shot/dish terminates the step.** Only if the BH *progresses* do the two booleans select the per-step **movement** branch in `decide_step_action` (a shot-clock **desperation** pre-check still runs first in engaged cases):

| Offense reads | Defense pressure | Per-step MOVEMENT (after no-shot) |
|---|---|---|
| ✅ | ✅ | **Read battle** — `offense read score` vs `defense_score`. Offense wins → subtle probe; defense wins → disruption (subtle/FF/none); neutral → subtle/pass. |
| ✅ | ❌ | **Offense unopposed** → subtle probe (never a plain advance). |
| ❌ | ✅ | **Ball-handling battle** — `ball_handling_score` vs `defense_score`. Defense wins → disruption; offense wins **or** neutral → advance. (d-foul deferred.) |
| ❌ | ❌ | **Static skeleton** — advance to the next step. (No longer defers to legacy: `should_shoot` still runs every step.) |

**Scores (form B, single d6):**
- Offense read: `(player_read_raw + discipline) * d6`
- Ball-handling: `(ball_handling_raw + offensive_efficiency) * d6`, where `ball_handling_raw = BH*0.6 + IQ*0.2 + CH*0.2` — symmetric to `defender_pressure_raw = OD*0.3 + AG*0.3 + IQ*0.2 + CH*0.2` (both weight to 1.0, both add a team modifier × the same d6).
- Defense: `(defender_pressure_raw | inside_defender_raw + fight) * d6`
- Win margins: offense wins if `> defense_score + def_eff + def_chem`; defense wins if `> offense_score + off_eff + off_chem`; else neutral.

**Shots are no longer in this matrix.** The old hot-read branch was removed from `decide_step_action`; all shooting (incl. the hot read, now a *label*) is the universal `should_shoot` decision that runs **before** this matrix every step. So this matrix is purely *how the BH moves when he doesn't shoot*.

**Tunables:** `alterations` (offense, per-team, 0–4) and `aggression` (defense, per-team, 0–4) — both in `strategy_settings`, default 2. `roll <= setting`, so 2 → ~60% engaged, 4 → always, 0 → 20%.

---

## Universal Shoot Decision (IMPLEMENTED — tune the constants)

One shared decision, `should_shoot` (`motion_step_decision.py`), evaluated at three call sites. Two steps: **(1) is the look optimal?** then **(2) does the shooter make the right call?**. Constants to tune: `OPTIMAL_BAR_STEEPNESS` (2.0), `OPTIMAL_BAR_TEMPO_MULT` (slow 1.2 / normal 1.0 / fast 0.8), `SHOOT_READ_RIGHT/SAFE` (200/125). (`SHOOT_THRESHOLD_BASE` / `SHOOT_TEMPO_ADJ` were retired — see [Tunable_Constants.md](../../11_Design_Systems/Tunable_Constants.md) / [Dynamic_HCO_System.md](../../06_Gameplay_Systems/Dynamic_HCO_System.md).)

**What's live:**
- **Per-step BH** (`_resolve_motion_offense_shot_dynamic` walk): runs every step before the movement matrix, universal (decoupled from `alterations`). A shoot/dish terminates the walk.
- **On-skeleton reception:** covered automatically — the walk evaluates whoever *holds the ball at step end* (`_motion_bh_at_step` prefers `receive`), so a receiver at a skeleton pass step gets the same shoot check (catch-and-shoot, else resume).
- **Post-subtle:** after a subtle beat, re-runs `should_shoot` from the BH's spot with a freeze openness bonus (if his man defender failed his subtle read).
- "Hot read" is now a **label** (`hot_read` flag on the decision when the shot came off a genuine mismatch), not a separate path — shares the read map's raw scores with the shoot check (one computation).

**Deferred refinements:** coord-exact shoot from the *subtle* position (currently the BH moves back to his named spot to shoot — a small move, not a teleport); reception `allow_dish=False` (a skeleton receiver can currently re-dish); off-skeleton-reception → freelance (moot while all dishes shoot); the timeout/quarter-break read-map cache.

`should_shoot(shooter_pos, off_lineup, locations, read_scores, off_team, shot_clock, tempo_call, rng, openness, allow_dish) → SHOOT decision | None`

### Step 1 — Optimal shot?  (`shot_quality >= scaled_threshold`)
- **`shot_quality`** = the **hot-read offender-vs-defender shot-type score** (Step-1 formulas: Inside `((SC+ST)-(ID+ST))/2`, Outside `SH-OD`, Attack `((SC+AG)-(ID+AG))/2`), **location-relative**:
  - inside spot → Inside score;
  - non-inside spot → **attack OR outside** (a perimeter spot supports both), chosen by a **weighted roll biased by team emphasis** (extends `_choose_attack_or_outside`):
    - `attack_score  = (AG+SC)/2 + attack_setting  * 10`
    - `outside_score =  SH       + outside_setting * 10`  (`attack`/`outside` `strategy_settings`, 0–4, default 2)
    - roll in `[1, attack_score + outside_score]` → **attack** if `<= attack_score`, else **outside**; read *that* type's quality. (Weighted, not argmax — a stronger skill / higher team emphasis is chosen *more often*, not always.)
  - then **modified by openness** (defender proximity / contest — a frozen or distant defender boosts the look; dominant term at receptions and after a defender freeze).
- **`scaled_threshold = BASE − clock_relief − TEMPO_MOD[tempo_call]`**
  - `BASE` (≈150, tunable) = the "elite look" bar at a full clock, normal tempo.
  - `clock_relief` grows as the clock drains → lower bar late: e.g. `(SHOT_CLOCK_START − shot_clock) × k` (tunable `k`).
  - `TEMPO_MOD` reuses `{slow −25, normal 0, fast +25}`: **fast lowers the bar** (shoot sooner), slow raises it.
- `optimal = shot_quality >= scaled_threshold`

### Step 2 — Read tier  (shooter's decision quality)
`read = (player_read_raw(shooter) + discipline) * d6`  (form B; `discipline` = shot-selection discipline)
- **`> 200` → right decision:** optimal → **shoot** (or **dish** to a better-positioned teammate); not optimal → **progress**.
- **`> 125` → safe decision:** **progress** (pass up the look).
- **`<= 125` → non-strategic:** 50/50 **shoot vs progress** (the shoot is a forced/contested attempt — no bonus).

### Outcome routing (by site)
| Site | shoot / dish | progress |
|---|---|---|
| **BH step** | shoot, or catch-and-shoot **dish** (the collapsed hot read) | fall through to the movement matrix (subtle / advance / disruption) |
| **After subtle beat** | shoot from the BH's subtle coords | resume the skeleton (next step) |
| **Reception — on-skeleton** | catch-and-shoot | resume the skeleton (its defined flow) |
| **Reception — off-skeleton** (hot-read / subtle dish) | catch-and-shoot | **enter freelance** (`_resolve_freelance`, already built) |

### Resolved
1. **The shoot decision is UNIVERSAL — decoupled from the `alterations` gate.** `alterations` gates only off-pattern *movement* (subtle moves); the BH reads to **shoot-or-progress every step in all four conditions**. ⚠️ Implementation consequence: the resolver's current "both-off → defer to static skeleton" must change when `should_shoot` lands so the shoot decision still runs when neither team alters/pressures.
2. **All dishes catch-and-shoot** (matches existing kick-out / hot-read dishes). So the reception shoot-decision applies to **skeleton passes only**; the off-skeleton-reception → freelance path is deferred (it can't arise while dishes always shoot).
3. **Layering:** the shoot decision runs **before** the movement matrix each step (shoot/dish → else progress → matrix).

### Still open
- (none — spec settled; ready to implement against a unified `should_shoot` + the three call sites.)

---

## Per-step Foul / Steal / Turnover Moment (IMPLEMENTED — migrated from HCT)

Replaces HCO's up-front percentile tables (`STANDARD_D_FOUL`/`STEAL_ATTEMPT`/`DEAD_BALL_TURNOVER`) with HCT's **attribute-driven per-step moment**, reusing HCT's contest + `HCT_D8_*` levels.

**Shared engine:** `_resolve_moment` (`dynamic_hct.py`) now takes optional `def_mod`/`off_mod` (default → HCT's `pt_efficiency`/`pt_opp_modifier`; HCO injects `def_eff`/`off_eff`). `_resolve_hco_moment` is the thin HCO entry. So HCO and HCT share one contest with the same levels — tune `HCT_D8_*`.

**Where it runs:** `_resolve_hco_moment_walk` (`phase_resolution.py`), called right after `resolve_hco_outcome` in `resolve_half_court_offense_logic`:
- Rolls the defense's per-turn pressure engagement (`aggression` 0–4, `roll <= setting`); no pressure → no moment.
- Walks the skeleton steps; per step fires `_resolve_hco_moment` for the BH vs his **man** defender; the **first** hard outcome wins.
- HCT→HCO mapping: `STEAL`→`STEAL`, `DEAD BALL`→`DEAD_BALL_TURNOVER`, `O_FOUL`→`O_FOUL` (charge), `D_FOUL`→`D_FOUL` (reach-in). `POS_O`/`NEUTRAL` → None (shot resolution proceeds).
- On a hard outcome it sets `result`, and the **existing** non-shot resolution + `apply_stopper_system_to_skeleton` + emitter render/route it (no new emission path — same `o_foul`/`d_foul`/`dead_ball_turnover`/`steal` machinery FCP uses).

**Sunset:** `resolve_hco_outcome` skips the up-front tables for motion turns when the flag is on (`skip_upfront_events`); set plays + flag-off keep them.

**Steal / reach-in micro-movement (the "pressure moment" visual):** HCO uses a single on-ball
defender, so it does NOT get FCP/HCT's multi-defender *converge* — it gets the **`reach_in`
flourish** (one defender lunges at the ball + `click-steal.wav`). `skeleton_step_emitter` stamps
`step.start.flourish[id] = {kind:"reach_in", target:"ball"}` from a `reach_in_def_id` tag on the
step (mirrors the HCT emitter); the FE (`flourishes.js`) renders the lunge + plays the SFX. Pure
render-space — never mutates gameplay coords (UESS-safe).

**Option B — reach-in on every contested step of an engaged turn** (chosen over A = defender-wins-only,
so the coach *sees* that an aggressive defense is constantly poking — successes and whiffs alike):
- **Terminal outcome** (`STEAL` / `DEAD_BALL_TURNOVER` / `D_FOUL`): the non-shot block tags the
  **stopper step** with the on-ball defender. (`O_FOUL`, an offensive charge, is excluded.)
- **Non-terminal contest** (`NEUTRAL` near-miss / `POS_O` blow-by): `_resolve_hco_moment_walk`
  collects `(step_index, defender_id)` per contested step into a `reach_in_tags` out-param; the
  caller applies them to `final_skeleton` **after the deepcopy** (the walk never mutates the cached
  skeleton). The continues-to-shot path carries the tags because the dynamic resolver appends the
  base step dicts verbatim (`output_steps.append(steps[i])`), and custom step keys survive to the
  emitter.
- Gated by the same per-turn aggression engagement roll as the moment itself — non-engaged turns
  show no reach-ins at all, so reach-in *presence* reads as defensive aggression.

**scope / deferred:** man **+ zone** defense (zone resolves the on-ball defender by zone polygon, `_zone_bh_defender`; dial `HCO_ZONE_MOMENT_SCALAR`, same D8 weights as man for v1). The moment walk runs **before** shot resolution, so a moment pre-empts the would-be shot — true per-step interleaving with `should_shoot` is a later refinement (needs the late shot resolver, which must run after the shot-clock truncation). Pass interceptions (HCT `pass_contest`), set-play moments, and zone contest-weight reweighting deferred. All behind `GOB_DYNAMIC_HCO_MOTION`. Tune frequency via `HCO_MOMENT_SCALAR` / `HCO_ZONE_MOMENT_SCALAR` (and the shared `HCT_D8_*`). See the [authoritative system doc](../../06_Gameplay_Systems/Dynamic_HCO_System.md).
