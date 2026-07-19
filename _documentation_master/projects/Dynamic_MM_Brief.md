
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
- **Playbook naming (P6) — ✅ DECIDED 2026-07-19 (owner):** **KEEP the mapping at the playcall→posture boundary** — internal code posture stays **`tight`**; the playcall→posture map translates. Mapping: **deny ↔ tight**, **loose ↔ loose**, existing/unsuffixed play ↔ **normal**. Do NOT rename internal `tight` → `deny`. **FE display name is still OPEN** (owner wants more user feedback before committing to a coach-facing label) — so build with a placeholder/easily-renamed FE label; the internal + playcall-key naming (`deny`/`loose`) can proceed.

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

**New (Goal 2): read the defender's GEOMETRIC commitment on the frozen grid, pick the response the geometry opens.** *Not* a die roll against a posture label — the trigger is the actual coordinate relationship between a defender and the man he guards (the same `def_xy` the intercept model already reads via `_hco_step_def_xy`, decomposed into a small commitment vector — see §6A). The space is real or it isn't; **attributes/dice only modulate execution quality, never whether the space exists.** This is the same organic geo layer as S1's openness, extended from one scalar (cushion) to a directional read.

| Defender geometry vs his man (frozen grid) | What's geometrically open | Offense response (new) |
|---|---|---|
| high **ball-side denial** — shaded between man & ball, overplaying the lane | the **backdoor lane** (man→basket, away from the ball) | **backdoor** to the rim |
| high **cushion / help-sag** — sitting off the man toward the paint | the man's **own spot** (room to catch & rise) | **step-in shot**, or **relocate into** the vacated help-side |
| **beaten / trailing** — lost his read or left behind on a drive (S1 lag / S2 blow-by) → openness | the lane he vacated | **attack** the closeout / drive (reuses S2 tier outcomes) |
| tight & square — low cushion, between man & basket | nothing | today's behavior: run play / SM / mismatch shot |

**Offense action vocabulary (new vs existing):**
| Action | New? | Exploits |
|---|---|---|
| shoot | existing | a conceded / mismatch look |
| dish / pass | existing | an open teammate |
| attack (drive to rim) | existing (`attack_drive_clearance`) — **new trigger** (read a beaten gamble / closeout) | loose / help closeout, or a beaten gamble |
| SM (reposition) | existing | probe for a read |
| relocate (to a better open spot) | partial — freelance-only today | vacated help-side space |
| **backdoor** | **new** | a tight / deny overplay |
| **jab-and-pop** | **new** | on-ball pressure / a bait jab (defender bites) |
| **flash** | **new** (deferred `motion_subtle` variant) | a sagging / lost-contact defender |
| **post** | **new** | a mismatch / a defender playing behind |

> **Naming:** we already have **`attack`** (= drive to the rim; what we informally called "drive"). We also have a generic **`cut`** action that's really just a standard move — so the new backdoor action is named **`backdoor`** (not "backdoor cut") to avoid collision. (`cut` itself may want a clearer name later.)

**Ready-made building blocks in code:** `motion_subtle.py` explicitly **defers** two off-ball ball-transfer variants — *"flash to receive a quick pass and shoot"* and *"cut to the basket and receive a pass from the BH."* Those are precisely the relocate-and-catch / backdoor Goal-2 actions; un-deferring them is a natural first build. Primitives also exist for drive-in (BH `"in"`), move (`"cut"`), and relocate-to-spot (freelance).

**Dish + reception logic today (and a Goal-2 gap):** the BH *already* reads a teammate's mismatch and dishes — `should_shoot(allow_dish=True)` scans all five, and if a teammate's optimal look beats the BH's own it returns `via_pass` to that teammate (the "collapsed hot read as a dish"; plus the desperation `KICKOUT_SHOOT`). But the **receiver has no agency**: his shot type is chosen at *dish* time, `_execute_motion_decision` emits `pass→receive→shoot`, receptions pass `allow_dish=False` (no re-dish), and there's no catch-and-drive / second read — only the dish interception contest (§4) can intervene. **Goal-2 opportunity:** give the receiver his **own read on the catch** (shoot / `attack` a closeout / re-dish / SM), reading how *his* defender closes out. Fits naturally as a P4/P5 add-on.

**Symmetry (the whole design in one line):** Goal 1 defender **commits in space** → Goal 2 offense **reads that space and attacks it** — one geometric commitment signal, pointed both directions. The proactive defender gamble is *designed* to be the thing the offense punishes. That is the objective: an SM becomes a **dynamic decision to get more open / into a better shot**, not just a nudge.

Net-new to build (all feeding the ONE Hot Read — see §6A): the **get-open move menu** (`backdoor` / `jab-and-pop` / `flash` / `post`) + the **beaten-defender-trails linchpin** (reuse S1 lag) that actually opens the space. The *shot decision* is already the Hot Read — no new shot code; the new code is the moves + the defender reactions.

### 6A. The commitment primitive (systemic — ONE signal, thin consumers)

Exactly parallel to S1's openness (one distance → shot contest + dish gate + Goal-2 read), Goal 2 adds **one** geometric primitive and every response is a thin consumer of it — no per-action bespoke geometry.

**`_hco_commitment(off_pos)` → `{cushion, denial, sag}`** — computed once per matchup from the **already-shared** frozen-grid read (`_hco_step_def_xy` → `def_xy`) + the offense coord (`_coord(off_pos)`) + ball (`bh_xy`) + attack basket. It decomposes the defender's offset from his man into three scalars:
- **cushion** = ‖defender − man‖ — the sag magnitude (this IS S1's openness; reused, not recomputed).
- **denial** = projection of (defender − man) onto the man→**ball** axis — how far he's overplaying the passing lane (+ = ball-side deny).
- **sag** = projection onto the man→**basket** axis — how far he sits in the help/drive lane (+ = toward the rim).

**The unifying architecture — "get-open moves feed the Hot Read" (revised 2026-07-14):** Goal 2 is NOT a set of per-action shot triggers. It's a menu of **"get open" MOVES**, and the **existing Hot Read progression carries the shot decision** for all of them:

> **commitment read** (the §6A primitive) → **get-open move** (a directed off-ball relocation) → **defender reacts** (freeze / S1 lag → beaten → *trails*, opening the space) → **the Hot Read** (`should_shoot` + the S3b openness map) finds the open man and feeds him (or he shoots it himself).

The shot/dish half is **already done** — S3b made `should_shoot` openness-aware, so whoever gets open becomes the best look and gets fed, with **no new shot-trigger code per move.** The genuinely new code is *upstream* of the shot: **(a) the linchpin** — a beaten defender must **trail** the move (reuse S1 lag) or no openness is ever created, so the Hot Read has nothing to reward; **(b)** emitting the directed moves; **(c)** each defender's reaction. (This is why the first `backdoor` cut underdelivered: its beaten defender recovered, so the read never became an open look — see §8.)

**The get-open move menu** (each = a commitment read + a move + the defender reaction that opens it — all funnel into the one Hot Read):

| Move | Read that triggers it | Defender reaction that opens it |
|---|---|---|
| **backdoor** | defender **denies** (`denial ≥ bar`) + rim unprotected | beaten ball-side → **trails** behind the cut → open at the rim |
| **jab step** | on-ball pressure / a bait jab | defender **bites** the jab in → caught leaning → pop-out open |
| **flash** (a deferred `motion_subtle` variant) | defender **sags / loses contact** (`cushion` / help-side) | doesn't recover to the flashed gap → open catch |
| **post up** | **mismatch** / defender behind | sealed → entry angle open |
| step-in *(built — S3b)* | `cushion ≥ min` (conceded look) | already sagged → take the shot |
| attack *(built — S2)* | already-open (S1 lag / blow-by) | drive, S2 outcomes |

So the whole layer is: `_hco_commitment` (the ONE primitive) drives every read; the **S1 lag opens every space** (the linchpin); the **Hot Read makes every shot decision** (no new code). Attributes enter only as an *execution* modifier, never the trigger gate — organic + man/zone-agnostic (`def_xy` is unified by `_hco_step_def_xy`).

**Defender reaction to a movement move — ONE shared set (cut / jab / flash; post-up is separate, locked 2026-07-14):** a single read roll (`_roll_defender_reads_graded`, IQ/CH) puts the defender on one continuum; the *move* supplies where the space opens.

| Reaction | Read | Space it opens | Mechanism |
|---|---|---|---|
| **Stick** | follows | none (covered) | lag `1.0` |
| **Trail** | beaten (mild) | behind the move | lag graded |
| **Freeze** | beaten (bad) | full — the man left him | lag → `0.0` |
| **Bite** — **backdoor + jab step only** (a fake/misdirection; **NOT** flash/post up) | beaten + faked | *opposite* the fake | **new** |

Stick / Trail / Freeze are the *existing* S1 graded lag (`_defender_lag_fraction`, `1.0 → 0.0`) — freeze is just the worst-beat end of trail, not a separate action. **Bite** (commit the *wrong* way) is the one net-new reaction — built with jab-and-pop, reused by the cut's fake. The defender's "chance to stay in range" is the graded trail: a **barely-beaten** defender stays close → the mover is covered → the Hot Read won't feed him; only a real beat opens him.

**Decisions locked (2026-07-14 kickoff):** (1) **denial = ball-axis projection** — `denial = (defender − man) · unit(BH − man)`, signed toward the passer; backdoor fires on `denial ≥ BACKDOOR_TRIGGER_BAR` + a clear man→basket landing (openness radius). (2) **Scope = all five off-ball** — every offensive player reads his own defender; an off-ball player whose man overplays can trigger the backdoor/relocate and the BH feeds him (cut+pass, reusing the §4 pass contest). (3) **Geometry-only first** — triggers gate purely on the commitment geometry; the finish is judged by the existing openness shot/catch contest (which already reads attributes). Any extra execution modifier (a slow cutter caught in open space) is a later tune knob, not the first build.

**Decisions locked (2026-07-14, architecture pass):** (4) **Get-open moves feed the Hot Read** — the shot/dish decision is NOT re-implemented per action; it stays the one Hot Read (`should_shoot` + openness map). Moves only reposition + set up the defender reaction. (5) **The linchpin = a move's beaten defender TRAILS** (reuse S1 lag) — without it no move creates openness, so the Hot Read can't reward it; build it first, and it also completes `backdoor`. (6) **Move menu = backdoor + jab-and-pop + flash + post** (plus step-in/attack, already built). (7) **jab-and-pop = off-ball first** (a spot-up player faking his man → pop to an open catch, folding into the dish read); the **on-ball BH jab-and-pull** version (folds into `should_shoot`'s self-shot) is a noted extension, not the first build.

**Terminology (official, locked 2026-07-15):** the four moves are collectively **"altered actions"** — **backdoor**, **jab step**, **flash**, **post up**. (Replaces the working term "get-open moves"; `jab-and-pop`→`jab step`, `post`→`post up`. Doc + code rename `get_open`→`altered_action` bundles with the lever wiring below.)

**Strategic lever — the `alterations` setting gates altered actions (locked 2026-07-15):** altered actions are a coach-controlled lever, hung off the existing per-turn alterations roll:
1. **Once per turn**, roll: is this an **altering turn**? at **`alterations × 20%`** (setting 0→0% / 1→20% / 2→40% / 3→60% / 4→80%). 0 = always run the set straight; 4 = freelance 80% of turns. (Shifts today's `randint(0,4) ≤ alterations` = 20–100% down a notch so **0 = never**.)
2. **Non-altering turn** → set play straight, no SM, **no altered actions**.
3. **Altering turn** → the BH does SMs, and **altered actions fire ONLY on the BH's SM** — they ride the freelance moment (the SM = the BH "probing off-pattern", the natural trigger for off-ball creation). The BH's SM is always him *moving with the ball* (`handle_ball`); shoot/dish is the separate universal `should_shoot`, before the movement matrix.
- This **restructures** the current backdoor (fires ungated, *before* the movement matrix) → evaluated **when the BH executes an SM**. **Defense disruption stays independent** (its own `aggression` roll — a passive offense can still be disrupted).
- **Wiring deferred** to after the 3-i/3-ii in-app verify (a gate is cleanest added once the moves are proven — fits S3e). Design is locked; only the wiring waits.

> ⚠️ **The "get-open moves → linchpin/trail" sub-plan that used to live here is SUPERSEDED by the current model below (rewritten 2026-07-15).** Parts of "Decisions locked 2026-07-14" above are also superseded: the backdoor's `denial ≥ bar` + clear-rim trigger (→ replaced by the per-player roll + selection), and the "graded trail linchpin" (→ replaced by the **binary** stick/freeze reaction). The commitment primitive (S3a) and the `should_shoot` openness_map (S3b) stay as-is.

### S3 — Altered Actions: CURRENT MODEL (rewritten 2026-07-15)

**Spec of record: `Dynamic_HCO_System.md` § Altered Actions** (per-action definitions + defender reactions live there; this is the build plan pointing at it).

**The model (locked):**
- **Altered actions** = **backdoor · jab step · flash · post up** (umbrella term "altered actions"; code rename `get_open → altered_action` bundles with the build).
- **Gate:** fire ONLY on steps where the BH executes an **SM**. Per-turn **`alterations × 20%`** (0→0% … 4→80%) decides an "altering turn"; on it the BH SMs and altered actions ride it. **Freelance is OUT of scope** (leave `_resolve_freelance` as is).
- **Offensive trigger** (each non-BH player, each SM step): `roll = randint(1,100)`; if `roll < (0.8·IQ + 0.2·CH + off_eff)` → he performs an altered action, else stationary.
- **Selection:** if performing, ONE action chosen at random **by his location** — **inside** → {post up, flash}; **outside** → {backdoor, jab step}. (Inside = basketSpot / midLane / upper·lower lowPost·midPost.)
- **Defender reaction** — the read `(0.8·IQ + 0.2·CH + def_eff) × d6`, good ≥ 110 / great ≥ 200:
  - **backdoor** (non-inside → a random inside spot): good → stick with cutter · poor → **stationary**.
  - **jab step** (jab **4–5 grid toward the basket**, random, then return to spot): good → stick · poor → **follow inward & stay** (bite) → jabber pops back out open at his spot.
  - **flash** (inside → a flash-to spot ≠ start; flash-to = midLane/topLane/upper·lower midPost·highPost): great → stick + **FRONT** · good → stick **behind** (contested catch) · poor → stationary (open).
  - **post up** (inside, hold + seal): defender does NOT read — **inside defense** `(ID·0.6 + ST·0.2 + IQ·0.1 + CH·0.1 + def_eff) × d6 > 110` → good = **front**, else **behind** (open).
- **"Fronted" = INELIGIBLE to receive a pass** (a blocked dish target). A forced pass there (future BH poor-read logic) → INTERCEPT / BAT-OOB via the existing pass contest (defender CH+IQ). For now: absolute no-pass.
- **Openness = distance to the NEAREST defender** at the action's landing, read off the **frozen `def_xy`** (not just the assigned man). Folds help defenders in → **retires the clear-rim gate**.
- **The shot/dish = the existing Hot Read** — the post-SM `should_shoot` reads the openness the actions created (+ excludes fronted targets). **No per-action shot code.**

**NEW FOUNDATIONAL ITEM — HCO non-BH defender-placement overhaul (prerequisite; everything reads it).** Retire **aggression** from placement (BH + non-BH); **posture (tight/normal/loose) is the sole control**. Non-BH **perimeter** placement = `man + sag·(ball−man) + shade·(basket−man)`, then **per-dimension anchored** by the man's basket-offset: `w_d = max(FLOOR, off_d / max(off_x, off_y))` → follows the help spot fully in the *far* dimension, stays anchored (with a floor → "comes off it some") in the *basket-aligned* dimension. Handles the whole arc continuously (key/corner/midWing/midCorner) — no spot table. **On-ball** = tight 2–3 / normal 3–4 / loose ~4.5 grid toward the rim. **HCO-CONTAINED**: gate on the posture context; leave the shared `calculate_defender_coords` base intact for **FB / rim-runner / tip-off**. **Inside-man lock stays** (inside men → post/inside defense, not this model). **UESS/StepState-compliant by construction** (lives in the placement fn `compute_defender_grid` draws) — the 0–10% jitter must be **resolved once + frozen** so contest == render.

**Build order (revised):**
1. **Defender-placement overhaul** (foundational).
2. **Trigger + selection + SM gate** (per-player roll → action-by-location, on the BH's SM).
3. **Backdoor** — rebuild on the new trigger (retire denial/clear-rim) + **nearest-defender openness** + binary stick/freeze (already prototyped — reconcile).
4. **Jab step → Flash → Post up** — each = the move + its defender reaction (per spec).
5. **Receiver catch agency** — own closeout read; replaces forced catch-and-shoot.
6. **MC tune.**

**New tunable constants:** `HELP_SAG_NORMAL=0.30` · `HELP_SAG_LOOSE=0.55` · `HELP_SAG_JITTER=0.10` · `HELP_BASKET_SHADE≈0.20` · `HELP_ANCHOR_FLOOR≈0.30` · on-ball `ONBALL_{TIGHT,NORMAL,LOOSE}` · `ALTERED_ACTION_TRIGGER` (the roll) · `JAB_TOWARD_BASKET_GRID=4–5` · flash/post read thresholds (110/200) · post-up inside-defense formula.

**Already built (uncommitted):** **S3a** commitment primitive (`_hco_commitment`/`_hco_commitment_map`) ✅ — the read geometry stays. **S3b** `should_shoot` `openness_map` ✅ (step-in + open-man dish) — stays. **Backdoor prototype** (cut-move → Hot Read → binary stick/freeze; drive-stop 0–2 cap; reception VO) — in prototype testing; will be reconciled to the current model (trigger/selection + nearest-defender openness) after the test.

---

## 7. Phased build brief

**Flag:** `GOB_DYNAMIC_HCO_DEFENSE` — gates the whole feature (Goal 1 + Goal 2). (The motion/set-play flags `GOB_DYNAMIC_HCO_MOTION`/`_SETPLAY` were **retired** — those paths are always-on now, so this is the one remaining HCO gate.) Off → today's glued-to-man behavior. Each phase ships behind it and is testable in isolation.

**Load-bearing architecture constraint (updated for StepState, 2026-07):** the offense's spatial read (Goal 2) **and** the interception contest must see the **same** defender coords the FE renders. This is now **guaranteed by the shared defender grid** (resolve-once → freeze → draw), not a discipline of "route through the reconstruction":
- The engine stamps `compute_defender_grid` (the animator's **own draw code**) on each step *pre-contest* (`_stamp_contest_defender_grid`); the contest reads it via `_hco_step_def_xy`. The emit stashes its exact per-player animations (`game._hco_render_animations`) → `build_step_states` → `StepState.defense`. So **contest == render == the one frozen grid** (live `🔬 STEPSTATE GAP` = 0% man+zone). This is the [[project_emitter_as_god]] façade, realized.
- **Therefore: posture/action shading MUST live inside the placement code `compute_defender_grid` draws** (`get_defender_coords`/`calculate_defender_coords` with the `posture` param) — so the shading rides into BOTH the stamped contest grid and the rendered grid automatically. **Never** shade in the animator's render path alone (contest wouldn't see it) or in the contest alone (render wouldn't) — either breaks the single-source guarantee (UESS teleport risk).
- **Goal 2's spatial read reads the FROZEN grid** (`StepState.defense` / the stamped step grid) — never a fresh reconstruction — so the offense reads exactly what's drawn. The legacy per-mode reconstruction (`get_defender_coords` man / `assign_all_zone_defenders` zone) survives only as the *unstamped fallback*.

**Build man first, then zone parity** within each phase (zone already flows through the same `compute_defender_grid` draw + stamp; posture *placement* for zone is the net-new bit).

### The one primitive everything reads (locked 2026-07-13)

**Openness = the Euclidean distance between a player and the defender guarding him, on the frozen grid.** A defender beaten on *any* step (drive, shot, backdoor cut, jab-and-go) opens that distance. **Three consumers read the one number:** (1) the **shot contest** (graded make), (2) the **dish / hot-read** decision (`_hco_blocked_dish_targets` — an open man is the ideal receiver), (3) [Goal 2] the **offense's own read** that triggers its next action. Build the primitive once; everything downstream is organic — no "beaten" flag to track.

### Already built (see §8 for evidence) — do NOT rebuild, only extend

- **Posture placement (man):** `_roll_defense_posture` (interim `random`), `_apply_defender_posture` + `posture` param on `get_defender_coords`. Threaded to man defenders in the animator. *(Zone placement + real playcalls = Stage 4.)*
- **Two-gate intercept (all pass types):** Gate 1 geometry / Gate 2 `aggression_call` (80/40/0) / Gate 3 `resolve_pass_contest`; INTERCEPT + BAT_OOB animation. Complete — the "make defenders pick passes" slice of Goal 1 is done.
- **Shared frozen grid:** `_stamp_contest_defender_grid` → `_hco_step_def_xy` reads the stamped `_step_state["defense"]`. The read plumbing Stages 1 & 3 need **already exists and is in use**.
- **Binary drive contest:** `_compute_drive_scores` → `drive_offense_wins` (2-tier). Stage 2 replaces it with 3 tiers.

### Rescoped stages (Goal 1 → Goal 2; man-first within each)

| Stage | What | Key files | New constants |
|---|---|---|---|
| **S1 — Openness primitive + graded shot math** ⭐ | Generalize the beat-roll `(player_read_raw + def_eff) × d6 > MOTION_READ_THRESHOLD=110` (today `_roll_subtle_defender_reads`, SM-only) to **every** positional step. On a beat, **open the defender's spacing on the frozen grid** (graded by read-miss margin) so his distance-to-man grows. Replace the shot contest's **boolean** radius gate with a **graded 3→9 proximity scale** on `shot_defense_score_raw` (≤3 = full defensive weight, ramp 4–8, **9–11 = not-open but low impact**; keep `CONTEST_EUCLIDEAN_RADIUS=11`). **Drop the deny/help/guard action label — placement IS the commitment (Q2).** | `phase_resolution.py` (generalize read roll → per-step field), `animator.py` (`_subtle_defender_should_freeze` → graded lag, in `_position_standard/zone_defenders`), `shot_manager.py` (proximity scale on `shot_defense_score_raw`, ~L1004-1028) | `PROXIMITY_CONTEST_SCALE` (3→9 ramp), `OPENNESS_LAG_FROM_MARGIN` |
| **S2 — 3-tier drives + `resolve_drive_contact`** | Replace binary `_compute_drive_scores` with 3 tiers keyed off the contest **margin**: **A offense-wins** (BH blows by, defender left behind; clear path *unless* a geo help defender is in range → **help cutoff, reuse FB meet-point model**); **B neutral** (defender stays *between BH and basket*, stops him **35–65% by the neutral lean** — offense-lean 65 / true 50 / defense-lean 35, read off margin sign; then pull-up or dish; help may double-team on the shot); **C defense-wins** (BH advances **0–5 grid**, stopped). **Truncate the BH path** for B/C (today he always reaches the rim). Fouls/TOs fire organically on help-defender contact (tiers A-cutoff, B, C). | `attack_drive_clearance.py` (3-tier + path-stop), **new `resolve_drive_contact(context="FB"\|"HCO")`** extracted from `fb_stop_decision.py` (FB refactored to call it), `phase_resolution.py`, stat tracking | `DRIVE_TIER_*`, `NEUTRAL_LEAN_DIST = {offense:0.65, neutral:0.50, defense:0.35}`, drive-contact foul/TO rates |
| **S3 — Altered Actions** *(model rewritten 2026-07-15 — see "S3 — Altered Actions: CURRENT MODEL" above + `Dynamic_HCO_System.md` § Altered Actions)* | **Altered actions** (backdoor/jab step/flash/post up) fire on the BH's **SM** (per-turn `alterations×20%` gate); each non-BH player rolls `randint(1,100) < 0.8·IQ+0.2·CH+off_eff` → performs, and a location-chosen action moves him; the **defender reacts** (binary stick/freeze, flash ternary, post-up inside-D); the **existing Hot Read** feeds whoever's open (openness = **nearest defender**, fronted = ineligible). **Prereq: the non-BH defender-placement overhaul** (retire aggression; posture-driven sag+shade+anchor; HCO-contained; UESS-clean). `_hco_commitment` (S3a) + `should_shoot` openness_map (S3b) already built. | placement overhaul (`shared_defense.py`, HCO-gated), trigger/selection + SM gate (`phase_resolution.py`), the four action emitters (reuse SM beat), defender reactions (`animator.py` freeze + inside-D), `_execute_motion_decision` reception read | `HELP_SAG_*`/`HELP_BASKET_SHADE`/`HELP_ANCHOR_FLOOR`/`ONBALL_*`, `ALTERED_ACTION_TRIGGER`, `JAB_TOWARD_BASKET_GRID`, flash/post thresholds, post-up inside-D formula |
| **S4 — Real playcalls + zone posture parity** | Replace interim `random(posture)` with **coach-selectable** tight/normal/loose per defense (man, 2-3, 3-2, 1-3-1 → **12 playcalls, 8 new**; naming **deny↔tight**, loose↔loose, existing↔normal). Build **zone posture placement** (`assign_all_zone_defenders` takes `posture` — net-new geometry). FE/playbook wiring. Derive posture from the playcall (retire random). | playbook/defense-play defs, `shared_defense.py` (zone posture), `_roll_defense_posture` → derive from playcall, FE playcall UI | — (playbook data) |

**S4 — MAN PLAYS ✅ DONE (2026-07-19) — see [`integrating_new_d_plays.md`](integrating_new_d_plays.md) as the authoritative record.**
The interim S4 posture prototype was RECONCILED into the owner-chosen **first-class three-plays**
model and fully implemented (Phases 1–4): distinct `defense_playcall` ids (`base-man`/`man-tight`/
`man-loose`), independent scouting rows + usage %, playbook-key rename (`man_pressure`→`man_tight`),
CPU playbook-%-weighted man picker, and FE labels (Base/Deny/Loose Man). **Posture derives from the
playcall id** — `man-tight`→tight, `man-loose`→loose, base→normal (`hco_defense_posture_from_call`).
Remaining: prod DB seed + base→`base-man` scouting migration (ship). Zone posture parity is still out
of scope. The bullets below are the SUPERSEDED S4-prototype notes, kept only for history:
- **Identity** (`defense_identity.py`): `man_deny` added to `PLAYBOOK_MAN_KEY_TO_DEFENSE_ID` (joins `man_pressure`/`man_loose`, all → canonical `man`); new `hco_defense_posture_from_call(raw)` maps deny/pressure/tight→`tight`, loose→`loose`, else `normal` (keyword-based, robust to spacing/casing). **Use UNDERSCORE keys** (`man_deny`/`man_loose`) — the space form doesn't resolve.
- **Posture link** (`turn_manager.py`): new `_apply_defense_call(raw)` choke point = coerce to canonical (for `defense_playcall`, keeps `man`) + stash `game_state["_hco_defense_posture_call"]`. Default reset to `normal` at top of `set_playcalls` (staleness). `_roll_defense_posture` (`phase_resolution.py`) now READS that stash instead of `random.choice` (rng param kept inert for back-compat).
- **CPU** (`constants/__init__.py` + `turn_manager.py`): `STRATEGY_MAN_POSTURE_BY_AGGRESSION` (0-4) expands a bare CPU `"man"` pick into a posture variant by the defending team's **aggression** setting (separate axis from man/zone `defense` setting) — symmetric to the zone-sentinel expansion. **TUNABLE weights.**
- **FE** (`court.html`): `DEFENSE_SCHEMES` + `defenseSchemeToApiValue` add `Man Deny`→`man_deny` / `Man Loose`→`man_loose`. **Display labels are PLACEHOLDERS** (owner holding the coach-facing name for user feedback).
- **Verified headless:** `defense_playcall` stays canonical `man` (no `man_deny` leak → every `is_zone`/`=="man"` consumer unaffected — the exact-string fixes the recon flagged proved unnecessary); posture varies tight/normal/loose from the playcall.
- **Deferred (the other half of S4):** zone posture parity (2-3/3-2/1-3-1 deny/loose + the net-new `assign_all_zone_defenders(posture=…)` geometry); the active-defense HUD label surfacing posture (today shows canonical `Man`); tuning the CPU weights.

**Drive-contact outcome set (S2, locked):** `clean stop · block · shooting foul on miss · shooting foul on make (and-1) · defensive non-shooting foul · offensive foul / charge · db-turnover` — all feed existing stat tracking. `resolve_drive_contact` is the ONE seeded (SS&S) path for "driver meets defender," shared by FB + HCO drives. (A broader "unify all moment resolution across FB/HCO/HCT" is a deliberate FOLLOW-UP, not this feature.)

### S2 — RECONCILED system-level design (2026-07-14)

**Spine: ONE shared contest per drive — `resolve_cutoff_contest` → `_resolve_moment`** (`dynamic_hct.py:670`; FB + HCT shared). Call it with the HCO driver + primary defender, `def_mod=def_eff`, `off_mod=off_eff`, `exclude_steal=True` (a full-speed drive collision is a charge/block/lost-handle, not a pickpocket — the resolver's own docstring). It uses the **same** `calculate_ball_handling_score` vs `calculate_defender_pressure_score` that S2a's `_compute_drive_scores` used — no new contest math — but returns the full banded outcome + a path ratio in ONE roll.

**Retires S2a's bespoke code:** `_compute_drive_scores` (margin) + `_classify_drive_tier` (±75 band) + the `DRIVE_TIER_*` constants are **subsumed** by `_resolve_moment` (tuned via the shared `HCT_D8_*` levels — no bespoke HCO tuning). S2a's meta stamp (`drive_tier`/`drive_stop_fraction`) **stays**, now populated from the shared outcome/ratio.

**NEW — clean-stop band (this thread).** `_resolve_moment` returns `NEUTRAL` in TWO indistinguishable places: the **defense-wins-no-event** path (`:735`) and the **middle "neither wins"** band (`:785`). Add a distinct **`D_STOP`** outcome for the defense-wins-no-event case (defender wins the matchup but forces no TO/foul = a clean wall-off). **Opt-in param `clean_stop=False`** (HCO passes `True`; FB/HCT default `False` → byte-identical, no mapping churn). Also generalize `score_ratio` (today only meaningful for TOs) to a stop point for all outcomes: POS_O→1.0, NEUTRAL→~0.5, **D_STOP→small (scaled by the defense margin `m_norm`)**, TO→0.2–0.8.

**Outcome → HCO 3-tier + contact (the whole mapping):**
| `_resolve_moment` outcome | Tier | `score_ratio` | Meaning |
|---|---|---|---|
| `POS_O` (+`D_FOUL` variant) | **A blow-by** | 1.0 | beats his man → reaches rim, unless a help cutoff (S2c) |
| `NEUTRAL` (middle) | **B neutral** | ~0.5 | contested → stopped ~mid, pull-up / dish |
| **`D_STOP`** (new) | **C clean stop** | small | walled off early (0–5 grid), returns to walk |
| `D_FOUL` | contact | — | defensive foul on the drive |
| `O_FOUL` | contact | — | offensive foul / charge |
| `DEAD BALL` | contact | 0.2–0.8 | lost-handle turnover at the ratio point |

**S2b (contact) = the shared outcomes, SAME roll.** `D_FOUL`/`O_FOUL`/`DEAD BALL` route through the existing turnover/foul machinery via a new `map_cutoff_outcome_to_hco` (mirror of `map_cutoff_outcome_to_fb`). No second contest. *(Block / shooting-foul-on-miss / and-1 are SHOT outcomes — handled by `resolve_shot` when the BH shoots after a stop, not by the drive collision.)*

**S2d (path-stop) = the shared ratio.** `score_ratio` → truncate the drive at `lerp(driver_start, drive_end, ratio)` (clamp Tier C to ≤ `DRIVE_STOPPED_MAX_GRID=5`); reclassify the shot via the existing `_shot_type_for_coords` (pull-up vs layup); reposition the primary defender at/just beyond the stop (`get_defender_coords`). Contained to `build_attack_drive_sequence`.

**S2c (help cutoff) = the shared geometry.** On `POS_O` (A), run `best_cutoff_on_drive` over HELP defenders (posture-shaded coords + `stop_attempt_prob` by aggression); if one reaches the path (`cutoff_meet_point`), resolve THAT collision via a second `resolve_cutoff_contest`. Loose posture → sits in help lanes → more cutoffs, organically.

**Net (system-level):** ONE contest (`_resolve_moment`), ONE geometry (`cutoff_meet_point`/`best_cutoff_on_drive`), ONE shot path (`resolve_shot`) — all FB/HCT-shared. Net-new HCO code = the outcome→tier/stop mapping + `map_cutoff_outcome_to_hco` + the shot-reclassification wiring. Shared-resolver changes are all **opt-in params** (FB/HCT byte-identical): `clean_stop`→`D_STOP` band, and **`neutral_band`** (win/lose gate width).

> **`neutral_band` — the neutral-tier fix (2026-07-14).** `_resolve_moment`'s default win/lose gate is the **chem+eff margin** (a few pts) → B (neutral) is vanishingly rare (near-binary contest). HCO passes **`neutral_band=DRIVE_NEUTRAL_BAND=100`** (± each way, in score points) → B becomes meaningful: at even matchups B is the **plurality** (contested drive → pull-up/dish); lopsided matchups still resolve decisively. FB/HCT keep the chem+eff default (`neutral_band=None`). Tunable at S2f.

**Sub-plan (reordered):** **S2-spine** (wire `resolve_cutoff_contest` + `D_STOP` + retire S2a bespoke) → **S2d** path-stop (score_ratio) → **S2b** contact routing (`map_cutoff_outcome_to_hco`) → **S2c** help cutoff → **S2e** return-to-walk → **S2f** zone parity + MC tune.

> **Drive-stop snap-back bug — FIXED (2026-07-14, uncommitted, SYSTEMATIC).** When a possession ended AT a drive step (shot-clock violation after a drive, S2b drive foul/charge/TO, or a moment on a drive), `apply_stopper_system_to_skeleton`'s ball-handler detection (phase_resolution.py:3879/3891) didn't recognize the `"drive"` action → it fell through to the pre-drive step and the stopper snapped the BH back to his STARTING spot before the whistle. Fix: add `"drive"` to both action lists — the drive step's BH `pos_action` already carries real coords (preserved at :3930), so the BH now stays at his drive/stop position. One systematic fix covers the violation, S2b, and any drive-stop. **Prerequisite for S2b rendering correctly.**

> **Drive-dish pause bug — FIXED (2026-07-14, uncommitted).** Root: on a drive-and-dish, the stationary catch-and-shoot receiver's END coord (`end_coords.get(receiver)` at the shoot step) didn't resolve → `recv_end=None` → `ball_pass_t=0` → the dish pass step fell to the `HCO_STEP_T_FLOOR=0.50s` = a dead hold ("driver arrives, holds, then passes"). Fix (`skeleton_step_emitter.py`, surgical/contained): when `receiver_end` is None, fall back to `receiver_start` — a stationary receiver can't be led, so the pass target IS his catch spot → correct flight time, ball animates, no hold. Applied to BOTH the `ball_pass_t` timing block AND the `ball_arrival_coord` block (same gap left the ball's landing point unstamped). Only affects the previously-broken `recv_end=None` case; working pass steps unchanged; does NOT touch the shared floor. **This also UNBLOCKS S2d** (the drive step-timing was the reason to hold it).

**S2a BUILT (uncommitted 2026-07-13, ADDITIVE) — being REWORKED onto the shared spine (see §S2 reconciled above).** `_compute_drive_scores` margin + `_classify_drive_tier` (±75 band) are **superseded by `_resolve_moment`** (same base scores, but the full outcome + ratio in one shared roll). The **meta stamp `drive_tier`/`drive_stop_fraction` and the `🚗 [DRIVE TIER]` log stay** — repopulated from the shared outcome/ratio. Retire: `_classify_drive_tier`, `DRIVE_TIER_NEUTRAL_BAND`, `DRIVE_NEUTRAL_STOP_MIN/MAX`, `DRIVE_STOPPED_MAX_FRACTION`. Keep: `DRIVE_STOPPED_MAX_GRID=5` (Tier C clamp). S2a stayed inert (nothing consumed it yet), so the rework is clean — no behavior to unwind.

**Tier C "defense wins" — stop is NOT terminal (S2, locked 2026-07-13):** if `resolve_drive_contact` yields no terminal event (charge / o-foul / db-TO / shooting foul), the stopped BH (0–5 grid short) **returns to the walk's per-step decision at his new coords** — reuses the existing machinery, NO new offense vocabulary. Options, in order: **dish/kick-out** (`should_shoot(allow_dish=True)` → `KICKOUT_SHOOT`; the drive drew the D so the openness signal finds the open man), **contested pull-up** (low-clock forced-shot backstop), **reset** (retreat/back-out → SM or skeleton resume), **freelance** (`FREELANCE_FORCED` — knocked off the play with clock pressure). **No new chance to drive again** (one drive per touch; a reset/SM must precede any re-drive — prevents infinite drive loops). Mirrors `_setplay_recovery_roll` (broken action → resume/freelance). Tier B (neutral, 35–65% pull-up) favors the shot/dish; Tier C favors reset/kick-out (pull-up only as the low-clock backstop).

**S2 sub-plan status (traced 2026-07-14):**

| Step | Status | Notes |
|---|---|---|
| S2-spine | ✅ built (uncommitted) | `_resolve_hco_drive_contest` → `_resolve_moment(clean_stop, neutral_band=100)`; outcome→tier (A/B/C); retired `_compute_drive_scores`/`_classify_drive_tier`. |
| S2d path-stop | ✅ built (uncommitted) | `_drive_stop_coord` lerp; B/C truncate at `score_ratio`, wall defender, reclassify shot via `_shot_type_for_coords`. |
| S2b contact routing | ✅ committed | non-terminal → walk; `D_FOUL`/`O_FOUL`/`DEAD BALL` route via existing turnover/foul machinery; `stamp_foul_contact_rattle` on both sprites. |
| S2e return-to-walk | ✅ **core built (uncommitted 2026-07-14)** | On a B/C stop the stopped BH re-decides **dish-vs-pull-up via the walk's own `should_shoot(allow_dish=True)`** (openness read), replacing the blind `shoot_prob` coin flip: dish to an open teammate if his look beats the contested pull-up, else pull up. HCO-native, flag+B/C-gated, wrapped so a read error → pull-up. Log `🧭 [DRIVE STOP READ]`. **Follow-up:** full reset/freelance re-entry (currently a `should_shoot`-None → contested pull-up, not yet a reset). |
| S2c help cutoff | ✅ **built (uncommitted 2026-07-14)** | On a Tier-A blow-by, `_resolve_hco_help_cutoff` races the HELP defenders (beaten primary excluded) to the drive line via the shared `best_cutoff_on_drive` (corridor `HCO_CUTOFF_PATH_CORRIDOR=11`, aggression-gated `HCO_CUTOFF_STOP_ATTEMPT_PROB`), then resolves the collision through **`_resolve_hco_drive_contest`** (the SAME HCO contest as the primary — `clean_stop` + tuned `neutral_band` — unified in S2f; was the shared `resolve_cutoff_contest`, which couldn't produce a `C` clean stop). A successful cutoff **demotes** the blow-by: the cutoff defender becomes `bh_defender_pos` (walls the ball / credits contact) and the tier re-resolves to B/C or a foul/charge/TO — **S2d/S2b/S2e consume the demotion unchanged**. `POS_O` (BH beats the help too) → stays a blow-by. Log `🚧 [HELP CUTOFF]`. Flag-off/Tier-B/C skip. |
| S2f zone parity + MC tune | ✅ **built (uncommitted 2026-07-14)** | **(a) MC harness** `scripts/s2_drive_monte_carlo.py` (reuses the real contest + cutoff fns, mock players/teams, DB-free) → sweeps `DRIVE_NEUTRAL_BAND` / matchup lean / cutoff corridor×aggression. **(b) S2c contest unified** (above) — the harness surfaced that `resolve_cutoff_contest` never returns `D_STOP`, so help cutoffs never cleanly stopped (dead `C` branch); fixed by routing through `_resolve_hco_drive_contest`. **(c) Zone parity fixes** (both `_three_tier`-gated → flag-off byte-identical): a rim protector whose zone holds no offensive player (2-3 shell, cleared paint, `basketSpot` uncovered) was (i) absent from the S2c cutoff race — now `_help_race_coords` fills unmatched zone defenders with a rim-help coord; (ii) defaulted to **center court** `{50,25}` in the guardian count — now the flag-on zone fallback uses that completed map. Precise zone-anchor placement stays **S4** (zone posture). MC findings in Tunable_Constants.md → HCO 3-Tier Drives. |

### S1 implementation scope (traced 2026-07-13) — 3 parts, mechanism already proven

The existing SM freeze already opens defender spacing *and* rides into the frozen grid (it lives in `_position_standard/zone_defenders`, both inside `compute_defender_grid`'s draw → contest + dish gate + render all read it). S1 = fire it on **every** step + make it **graded**. Build order A → B → C.

- **A — generalize the read roll** (`phase_resolution.py`) — ✅ **BUILT (uncommitted 2026-07-13).** New `_roll_defender_reads_graded` returns `{def_pos: {"follows": bool, "margin": float}}` (margin = score − 110); stamped on **every reached step** at the walk's `output_steps.append(steps[i])` (~:5786), flag-gated on posture (flag-off = byte-identical, no RNG). Rides on top-level **`step["_defender_reads"]`** — NOT `_step_state` (build_step_states overwrites that wholesale, step_state.py:68). Additive; no consumer until Part B. The `movers`/"did my man move?" geometric gate is deferred to Part B (applied at draw time, matching today's `anchor_moved` check).
- **B — graded openness in the shared draw** (`animator.py`) — ✅ **BUILT (uncommitted 2026-07-13, MAN only).** New `_defender_lag_fraction` → [0,1] (1.0 = full track, lower = lagged). Applied in `_position_standard_defenders`: interpolate the beaten defender between his prior and tracked coords by the fraction. Magnitude = read-miss |margin| (option a): `frac = 1 − OPENNESS_LAG_MAX·min(1, |margin|/110)`, so a full beat lags to 20% track, a marginal miss barely lags. Gated on man-moved (`OPENNESS_ANCHOR_MOVE_EPS`) + skips attack-drive-override steps (S2). **Legacy preserved exactly:** no `_defender_reads` on the step (SM beats, flag-off) → delegates to `_subtle_defender_should_freeze` (binary freeze/track). Rides into the frozen grid via `compute_defender_grid`. **ZONE site (`_position_zone_defenders`) still on the legacy call — zone lag deferred (man-first / Stage 4 zone parity).** Verified: 6 lag cases + no test regression (3 failing tests are pre-existing/stale). Not yet screenshot-verified in-app (S1 checkpoint, needs Part C for the shot payoff).
- **C — graded proximity in the shot contest** (`shot_manager.py`) — ✅ **BUILT (uncommitted 2026-07-13).** New `_proximity_contest_factor(dist)` (constants `PROXIMITY_CONTEST_NEAR_DIST=3` / `OPEN_DIST=9` / `OPEN_FLOOR=0.15`): ≤3 → 1.0, linear ramp 4-8 (0.86/0.72/0.58/0.43/0.29), ≥9 → 0.15 floor. In `resolve_shot` (after `has_contest`): compute the primary defender's Euclidean dist to the shot spot, gated on `_hco_defense_posture`; a **non-motion** matchup defender beyond `CONTEST_EUCLIDEAN_RADIUS` → uncontested (parity with the motion-geometry path). Pass `proximity_factor` into `calculate_shot_score`, which scales the primary `defense_score` at the source → flows into `shot_defense_score_raw` (contest classification), the `shot_score` penalty (make prob), AND the shooting-foul check. New keyword-only param defaults 1.0 → every non-HCO caller byte-identical. **Covers BOTH HCO paths** (attack-drive motion_geometry + regular catch-and-shoot via `_resolve_hco_shot_defenders`, which selected by matchup only — the exact dish-payoff gap). **End-to-end chain verified structurally:** B lags the defender in the shared `_build_all_animations` draw → shoot-step coord → `defender.coords` (UESS sync) → C reads the distance. Verified: proximity curve + 39 shot tests pass, no regression.

**S1 boundaries:** positional / off-ball beats only — on-ball *drive* beats are S2 (different trigger, same primitive). Broad behavior change (defenders lag on every step) → needs Monte-Carlo tuning + screenshot verify at the S1 ship checkpoint; FG%/openness will move by design.

**S1 tuning (MC harness `scripts/s1_openness_monte_carlo.py`, 2026-07-13):** reuses the real A/B/C functions (sweeping a constant overrides the shipped value). Constants tracked in `Tunable_Constants.md` → **HCO Micro Movements**. **Finding:** the FG% swing is **bottlenecked by beat-frequency (~14% of possessions), not by `OPENNESS_LAG_MAX`** — sweeping LAG_MAX 0.5→0.95 = +0.6→+1.5 FG; `PROXIMITY_CONTEST_OPEN_DIST` 11→7 = +0.9→+1.9. So the big openness lever is *how often defenders get beaten* (the `MOTION_READ_THRESHOLD=110` bar / how often men move), not lag magnitude. **Open tuning question for the owner:** is ~14% beat-frequency + ~+1% FG the intended subtlety, or should more defenders get beaten (lower the read bar)? Confirm against the live in-app baseline.

**Dependency order:** **S1 → S2 → S3 → S4.** S1 is the linchpin (the one signal all consumers read) and the lowest-risk, highest-visibility start — it makes the system visibly dynamic before any new action exists. Goal 2 (S3) *cannot* read space that S1 hasn't created. S4 is last: random posture already exercises every mechanic, so playcalls are separable coach-facing polish.

**Ship + visual-verify checkpoints:** after **S1** (beaten defenders → better shots + better dish targets, organically — screenshot-verify the spacing), after **S2** (Goal 1 defender side complete), after **S3** (Goal 2 — the objective: an SM becomes a dynamic decision to get more open).

---

## 8. Build status & evidence — traced 2026-07-13 (all committed on `develop`, tree clean)

Flag `GOB_DYNAMIC_HCO_DEFENSE` **default-ON** in prod. Everything below is committed; no uncommitted work. **Old P1–P7 → new stages:** P1(man)+P2-intercept = *already built* (§7 preamble); the rest maps into **S1** (P3 openness generalized + shot math), **S2** (drives, net-new), **S3** (P4+P5 offense), **S4** (P6 playcalls + P7 zone/tune/tests).

| Phase / piece | Status | Evidence |
|---|---|---|
| **P1** posture roll + coord shading | ✅ **DONE — man only** | `_roll_defense_posture` ([phase_resolution.py:4585](BackEnd/engine/phase_resolution.py#L4585)); `_apply_defender_posture` + `posture` param ([shared_defense.py:1785](BackEnd/utils/shared_defense.py#L1785)); animator threads posture to man defenders ([animator.py:2131](BackEnd/models/animator.py#L2131)). Inside-man lock present. Constants renamed vs brief: `POSTURE_ONBALL_CUSHION_DELTA` / `POSTURE_DENY_DISTANCE` / `POSTURE_HELP_ANCHOR_FRAC` / `POSTURE_HELP_SHADE`. |
| **P2** two-gate intercept (all pass types) | ✅ **DONE** | Gate1 `defenders_in_lane`, Gate2 `INTERCEPT_ATTEMPT_PCT_BY_CALL {80/40/0}` ([:4823](BackEnd/engine/phase_resolution.py#L4823)), Gate3 `resolve_pass_contest`. Covers dish/kickout (`_hco_resolve_dish_contest`), freelance ([:6145](BackEnd/engine/phase_resolution.py#L6145)), skeleton motion+setplay (`_hco_contest_skeleton_pass`), final-skeleton coverage (`_hco_contest_final_skeleton`). Passer's own man / on-ball zone defender excluded. Funnel diagnostics (`_track_hco_intercept_gates`). INTERCEPT animation = backend step-based; BAT_OOB = imperative FE send reading engine-owned `bat_oob_target` (the earlier step-based bat-OOB was reverted — it double-fired; see §5C). HCO pass-contest calibration live at spec values (175/200/170 — the Jul-12 "force interception" temp override was reverted). The INTERCEPT/BAT_OOB *ratio* is now the named constant `PASS_DEFLECT_KIND_D` (was an inline `200`). |
| ~~per-step deny/help/guard **action menu**~~ | ❌ **CUT (decided 2026-07-13)** | Placement IS the commitment (§7 Q2) — no separate `POSTURE_ACTION_MENU`. Deliberately dropped, not pending. |
| **P2** generalize `_roll_subtle_defender_reads` to every step type | ❌ **not done** | still SM-beat-only. |
| **P3** reactive resolution + graded openness | ❌ **not started** | animator still fires SM-only `_subtle_defender_should_freeze` ([animator.py:2026](BackEnd/models/animator.py#L2026), [:2300](BackEnd/models/animator.py#L2300)); no `OPENNESS_FROM_GAP`. |
| **P4** offense reads (existing actions) | ❌ **not started** | no spatial commitment read; no step-in / relocate / attack trigger off a posture. |
| **P5** `backdoor` action + receiver agency | ❌ **not started** | no `motion_backdoor.py`, no `backdoor` action, receiver still forced catch-and-shoot. |
| **P6** real playbook variants | ❌ **not started** | still interim `random(loose/normal/tight)` in `_roll_defense_posture`. |
| **P7** zone parity / tune / tests / docs | ⚠️ **partial** | zone *intercept* works via the shared grid (`_zone_bh_defender`, stamped `compute_defender_grid`); the **`Dynamic_HCO_System.md` § Dynamic Defense fold-in is DONE** (P1 posture + P2 intercept documented). Still outstanding: zone *posture placement*, Monte-Carlo tuning, unit tests. |

**Net:** posture placement (man) + the full pass-intercept model are live and committed. **Next up = S1** (the openness primitive + graded shot math — the "get beat → open man" spatial layer that S2/S3 both read). Then S2 (3-tier drives), S3 (Goal 2 offense reads), S4 (playcalls + zone parity).

**Stale in-code comment to fix:** [phase_resolution.py:4575](BackEnd/engine/phase_resolution.py#L4575) still says *"in-development (P1 = man-defense posture placement only)"* — inaccurate now that the whole P2 intercept model is built.