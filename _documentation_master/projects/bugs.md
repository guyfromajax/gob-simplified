##Marketing
1. Update GM Games page


##Monetization
1. Wire Stripe into site
2. Founder's Edition monetization plan
3. Publish pricing


##App Build
1. Downloadable game vs Live game dynamics
2. Steam submission for review


##Brand/Product
1. UI Design upgrade, what is this game's personality?
2. UX upgrade -- particularly around tabs and scrolling and back buttons (relative to browser back button), load screens


##Features
1. PvP sim -- playtest post-launch / immediate parallel task
2. College and Pro setup
3. Team Mod System
4. Stronger week 36 CTA to review all Recrutiing results -- and carry forward results chart, not just report/rankings. Order chart within each conference by top to bottom team recruiting performance
6. Replace Kobe look alike image and add more walk on images


##Animation
1. Evolve animation from annoying to rewarding


##Operations
1. Test update system
2. Dashboard


##Full Product Perfection
1. Training Camp News Report
108. Message board
113. Bring logic to screens
114. Better individual player defense stat tracking
116. User account -- link X & Facebook?
127. Get Aggressive / Get Conservative settings and Playcall Center buttons
128. Add a badass design appraoch to New Stories
131. Centralized Turn Transition Helper / System
139. Mod system for uploading custom leagues
140. Better logic and impact to player EM
142. Logic and impact for play scores
143. Nail player plumbing for Mod Teams
144. Nail mod team balance, league-wide

199. Mobile
200. PvP live

##Continuous Evolution (base is built)
1. In-Game SFX: Deny, Picked Up His Dribble, No Good/Missed
2. Advanced Topics tutorials
5. Players as Characters


##Bugs
1. Getting some double rebounds (SFX, maybe animaiton, not sure about logic)
2. Still missing EOQ perfection
2a. Fast Break animation is still sloppy and inconsistent
2b. Still reading fouled 3 pt attempts as 2 pt shots in some instances
2c. some HCO turnovers are still mismatched on BE and FE as to who the ball handler is. Note teh BE logic + turnover animation jiggle are synced, but sometimes a different player is holding teh ball.
3. OPEN — a shooting foul hands off to FREE_THROW but no FREE_THROW turn follows (~0.5/game)
   - Surfaced while measuring the fouled-3PT free-throw misaward (fixed 2026-09-07, see below).
     After that fix the residual misaward rate is entirely this family: 6 of 221 fouled attempts
     (played) and 7 of 203 (sim) over 12 seeded games per arm, seeds 8000-8011.
   - Shape: the shot turn carries `next_turn == "FREE_THROW"` and the branch set a non-zero
     `free_throws`, but zero FREE_THROW turns appear after it in `gm.turns`.
   - NOT the count bug and NOT direction-specific: it hits 2PT and 3PT, made and missed, at
     similar rates, and it was present at the same shape BEFORE the count fix. Independent.
   - Two qualifications, neither excluded yet:
     (a) the free throws may genuinely never be taken (a real dropped-possession bug), or
     (b) the trip may be non-adjacent in the turn list — an intervening turn (foul-out
         substitution, timeout, period bookkeeping) would break the probe's adjacency
         assumption and make this a measurement artifact rather than a bug.
   - Ruled out: end-of-quarter truncation. Every instance has `near_quarter_end=False` and
     `current_turn == "HCO"`, spread through the game rather than clustered at period ends.
   - To diagnose: record the result_type of the turn that actually follows, which distinguishes
     (a) from (b) in one run. Probe: `scratch_ft3.py` / `scratch_ft3_run.py`.

4. FIXED 2026-09-07 — fouled 3PT attempts awarded 2 free throws instead of 3
   - Jamie's original symptom ("some 3s register as 2s"). The classification was never wrong:
     `is_three` was correctly True and `shot_value` correctly 3. The free-throw count simply
     did not ask. `shot_manager.py` block-reconciliation shooting foul hardcoded 2 on a miss.
   - Measured before: 16.9% of fouled 3PT attempts misawarded (23/136) played, 23.8% (24/101)
     sim, 12 games per arm. The `3PT|missed|awarded=2|expected=3` row was n=19 played, n=16 sim.
   - Fixed structurally rather than by correcting the literal: `BackEnd/utils/free_throw_rules.py`
     is now the single source of truth and no branch computes its own count. Also collapses the
     `free_throws` / `free_throws_remaining` drift risk, since the applier writes both together.
   - Restored 1.22 points/game (played) and 0.99 (sim), at a measured 76.8% / 74.5% FT rate.
   - Pinned by `tests/test_free_throw_rules.py`: unit tests for the rule (including the and-one
     and the 1-and-1 front-end split, the two clauses most likely to be "tidied" later) plus
     three static guards in the shape of `test_uess_coord_contract.py` — no direct write to the
     three keys in a shot-resolution module, no count recomputed into a local, and an exact
     per-branch allowlist so a sixth branch must be classified. Each guard was poison-tested by
     reintroducing the defect and confirming it fails.
   - History: the same clause was fixed once at `dynamic_hct_shot.py:832` in `4690c97506`
     (2026-06-21, "added Standard Diamond HCT play") — the commit that introduced coordinate-based
     3PT classification — and never swept to the other branches. It was not recorded as a known
     gap; the commit's `Shot_System.md` note describes only the path it did fix.
5. FIXED 2026-09-07 — the offense animation build did not speak its own module's vocabulary
   - `BackEnd/engine/defender_placement.py` (`build_all_animations`) resolved an offensive
     player's position by testing `"coords"`, then `"location"`, then substituting
     `{"x": 50, "y": 25}` — centre court, the logo. The skeletons author the spot NAME under
     `"spot"`. So the third branch was not a fallback, it was the common case.
   - Scale, 12 seeded games per arm, 192,393 pos_actions: `ELSE_SPOT_IGNORED` 123,890 —
     every single fallthrough. `ELSE_NOTHING_AUTHORED` 0 and `LOCATION_MISS` 0, so nothing
     else ever reached it and no authored name failed to resolve.
   - The same module already read the key correctly at ELEVEN defender sites
     (`off_action.get("location") or off_action.get("spot")`, :520-1122), as does
     `attack_drive_clearance.py:252`. This was the only site in `BackEnd/` that decided which
     key to read, and the only one that got it wrong. That is the class: not a typo, a
     converter that did not speak the vocabulary of the module it lives in.
   - Not two bugs. The schema path piles were traced to the same root: `skeleton_step_emitter`
     is not a converter (zero reads of `spot`/`location`/`HCO_STRING_SPOTS`) and takes its
     coordinates solely from `animations[i].movement[j]`, i.e. from this producer's output.
   - Effect on placement: 4-, 5- and 6-player logo stacks went 812/game to 0, both arms.
     Five-player stacks alone were 644.5/game.
   - Effect on OUTCOMES, which is the part worth remembering — the bug had OPPOSITE signs in
     the two arms. On the population whose shooter was placed by `spot` (i.e. was standing on
     the logo), make% went 14.7 -> 29.4 played and 93.9 -> 31.5 sim. The arm gap was 79.2
     points and is now 2.1. Played also paid 2.82 pts per make, because a shot from the centre
     logo classifies as a three; that is now 1.93.
   - Whole-game effect, `equiv-v3`, n=20: points/team 65.65 -> 55.75 played, 68.95 -> 67.83 sim.
     THE BALANCE REFERENCES NEED RE-CUTTING against these numbers; that is its own scheduled
     work and was deliberately not bundled here.
   - Pinned by `tests/test_pos_action_key_contract.py`: no site may test membership of
     `"location"` on a pos_action without also accepting `"spot"`, with an exact registry so a
     second converter must be classified rather than silently added. Six poisons, all caught.
   - THE FALLTHROUGH NO LONGER INVENTS AN ANSWER, but it does not crash a live game either.
     Skeletons are primarily MongoDB documents authored through the play builder
     (`get_skeleton_by_lean` reads `play_doc["skeletons"]`; there are also `fcp_skeletons` and
     `hct_skeletons` collections) — `BackEnd/playcall_skeletons/` is the FALLBACK. So an
     unresolvable pos_action raises under `GOB_STRICT_POS_ACTION_KEYS` and under pytest, and in
     production logs loudly and DECLINES to place that player for that step. Declining is not a
     new path: an absent pos_action already takes it, and the emitter then backfills from the
     player's live `coords`. Persisted exports audit clean (4,325 offense pos_actions, 100%
     `location`, zero keyless), but the live builder-authored collections were not inspected and
     the builder can author a new shape tomorrow.
   - VERIFICATION NOTE, and a correction to how this was first reported. The SPC principle-8
     **poison-stash test** was initially named rather than run: what was actually run was a pair
     of pytest-baseline poisons, which is a different instrument (see item 6). The real test has
     since been run. `perf_sim_baseline.py --poison-stash` could not be used unmodified because
     it poisons `_step_state["defense"]`, the DEFENDER grid, and this fix changed the OFFENSE
     converter's output; the same method was aimed at the right value instead —
     `build_all_animations` runs in full so the draw count at the poison site is unchanged, and
     only the coordinates it returns are replaced with `{x:-9999,y:-9999}`.
     Result, 6 seeds x 2 arms, no exceptions in any run: the seeded fingerprint diverged 6/6 in
     BOTH arms, over 129 intercepted builds / 7,777 poisoned coordinates played and 2,325 /
     132,878 sim. So this producer's coordinates are genuinely read and reach outcomes — the
     documented sentinel blind spot (a consumer that only checks key presence) does not apply.

   - THE SAME TEST FOUND SOMETHING LARGER, see item 7: offense geometry feeds the GAME CLOCK.
     Absurd coordinates took the played arm from ~370 turns to ~15 in four quarters and its draws
     to -95.7%, with no error raised, because travel time is `dist / rate`
     (`skeleton_step_emitter.py:816`) and the emitter decrements `clock_remaining` by it. The sim
     arm moved far less on the same poison (draws -4.8%, turns -12%). That asymmetry is a
     placement-owned channel into game length, and it changes the reading of item 7.

   - RESIDUAL, OPEN: about 449/game single-player coordinates still land exactly on the logo.
     These survived the counterfactual, so they are a different cause and most likely ordinary
     mid-court traffic — a player legitimately at centre court. Not chased.

6. OPEN — a green baseline is evidence of nothing except that the guards we wrote ourselves
   still pass
   - Found 2026-09-07 while gating the spot-key fix above, and CONFIRMED TWICE MORE since. Logged
     separately because it is not a fact about any one fix — it is a fact about how this project
     verifies itself. Three independent dimensions have now been poisoned and the baseline did not
     move for any of them:
       · **coordinates** (2026-09-07) — mislocating 123,890 pos_actions per 12 games: delta EMPTY
       · **clock payload** (2026-09-08, item 10) — reverting the terminal clock fix so the buzzer
         displays a clock that does not exist: delta EMPTY with the new guard excluded
       · **animation emission** (2026-09-08, item 11) — re-stranding the FLSS skeleton so shots
         render nobody moving at all: delta EMPTY
   - The honest statement is stronger than three observations. `baseline_failures.txt` going green
     does not mean a change is correct, and it never has. It means the assertions we happened to
     write are still passing. Everything nobody wrote an assertion for — where players stand, what
     the clock says, whether anything renders — is outside the gate entirely, and each of those was
     shipped wrong for a long time without a single test objecting.
   - The corollary is what actually changes behaviour: **every increment must bring its own
     evidence.** A guard for the dimension it touches (the coord contract, the free-throw contract,
     the terminal clock contract) plus a poison proving that guard fails when the defect returns.
     A green baseline is a "did I break something structural" check and nothing more.
   - EVIDENCE, by poison. Two mutations, each run against the full suite:
     (a) reverting the spot-key fix, restoring the two-year-old bug that mislocated 123,890
         pos_actions per 12 games — baseline delta EMPTY;
     (b) resolving every `spot` to a deliberately WRONG but structurally valid coordinate —
         baseline delta EMPTY.
     The 114 known failures did not move in either direction, over two full-suite repetitions
     per condition.
   - So a green baseline is not, and has never been, evidence that a coordinate change is
     correct. The suite checks that animations are produced and well-shaped; it never asks
     whether any player is in the right place. Every coordinate change in this project has
     been passing the gate for free.
   - Consequence for how we work: for placement changes, behavioural evidence has to come from
     the `equiv-v3` harness (logo-stack census, make rate by placement class), and
     `baseline_failures.txt` should be read only as a "did I break something structural" check.
   - To fix: a small number of value assertions — a fixed skeleton whose named spots resolve to
     known coordinates, and a census assertion that no more than N players occupy the logo in a
     single step. The second is the one that would have caught this in 2024.

6b. STANDING RULE — measure on the arm the human is looking at
   - Adopted 2026-09-08. Sibling of item 6: that entry is about trusting our own assertions, this
     one is about trusting our own *harness*. Five conclusions in the animation workstream were
     wrong for the same reason — they were measured through `simulate_quarter` while the
     complaint was about played games.
   - THE MECHANISM, verified: `main.py:913` sets `game_state["_is_full_simulation"] = True` for
     `simulate_quarter`. `animator.py:1213` returns `[]` on that flag, so `animations` is empty,
     so `build_skeleton_animation_steps` bails at its `if not skeleton_steps or not animations`
     guard (`skeleton_step_emitter.py:1604`) and **HCO emits zero animation steps**. A played game
     pops the flag (`api.py:5503`) and takes the other branch. Measured on one seed: 110/110
     emitter calls returned `None` on the sim arm; 233/233 returned steps on the played arm.
   - SO THE SIM ARM CANNOT SEE THE LARGEST TURN FAMILY IN THE GAME. Same seed, same game:

     | | HCO turns | HCO steps emitted | total steps |
     |---|---|---|---|
     | sim arm | 108 | **0** | 825 |
     | played arm | 126 | **1,666** | 1,961 |

   - WHAT IT COST, 8 seeds per arm. Every one of these was briefed off the sim arm and is wrong
     for a played game:
       · overall perceptible whole-step freeze rate: **24.7% sim -> 16.3% played**
       · HCO's share of all emitted steps: **0.2% sim -> 83% played**
       · "inbounds are ~85% of content-free frozen steps": **82.1% sim -> 17.3% played.** On the
         played arm the top families are MISS 30.9%, SIDE_INBOUND 14.1%, MAKE 13.9%,
         DEAD BALL 12.1%, FREE_THROW 7.7% — shot outcomes, not inbounds.
       · FREE_THROW freezes at **91.3%** on 508 played steps; it was invisible before.
       · `idle_wander` flourishes per game: **0 sim -> 1,993-2,644 played.** An entire mechanism
         was reported dormant when it fires thousands of times a game.
   - THE RULE. Any measurement whose conclusion is about what a human sees must run on the played
     arm, and the report must say which arm it ran on. A sim-arm number is valid only for
     questions about the CPU-vs-CPU path. `scratch_playedarm.py::use_played_arm(gm)` refuses the
     one flag at the `game_state` level so a probe can walk the played path without a source edit.
   - Note this is NOT the same hazard as item 6. A poisoned baseline going green means our
     assertions are too weak; this means our *observations* were of a different program than the
     one being complained about. Both produce confident wrong answers, but only this one is fixed
     by changing how the harness is launched.

6d. STANDING RULE — a harness that opts IN to the right arm will silently run on the wrong one

   - Adopted 2026-09-09, at the cost of an entire session of measurements. Item 29 has the detail.

     **"Assert the arm. A shim that returns a status nobody reads is a shim nobody ran."**

   - `scratch_playedarm.py::use_played_arm(gm)` returns `False` and does nothing unless
     `PLAYED=1` is in the environment. Every probe in the defect-2 session called it, none set
     the variable, and none checked the return value — so every figure reported as "played arm"
     came off the SIM arm. The corrected numbers moved by factors of 2 to 3, and three families
     of shipped work read as completely dead when they were fine.
   - This is the fourth sibling of 6/6b/6c and it is the nastiest, because the other three are
     about the READER and this one is about the SUBJECT. A perfect reader on the wrong arm
     reports flawless, reproducible, deterministic nonsense — and it passes its own anti-vacuity
     control, because the control tests the reader.
   - THE RULE, in two parts:
     1. **A probe must ASSERT the arm it claims**, not request it. `use_played_arm` returns a
        bool; a probe that ignores it has no idea what it measured. Better still, assert a
        downstream FACT that only holds on the intended arm — on the played arm HCO emits steps,
        so `hco_still > 0` is a one-line proof the arm is live.
     2. **Opt-in via environment variable is the wrong default for a correctness-critical
        switch.** The failure is silent and it looks like data. If a shim can run in two modes,
        the mode belongs in the call, where forgetting it is a `TypeError` rather than a number.
   - Corollary, and it generalises past this shim: any claim of the form "X is never reached" or
     "X writes nothing" must state HOW the arm was established before the count is trusted.

6c. STANDING RULE — a null result and a broken reader look identical in a report
   - Adopted 2026-09-08. Recorded verbatim because the phrasing is the rule:

     **"A null result and a broken reader look identical in a report."**

   - Third sibling of items 6 and 6b. Item 6 is about trusting our own assertions; 6b is about
     which arm the harness ran on; this one is about the shape of a NEGATIVE finding. "No change
     measured" and "the probe could not see the change" arrive as the same sentence, and the
     second one is indistinguishable from good news.
   - It has already cost real work twice in this workstream. `scratch_foul_outcomes.py` reported
     0 fouls and `None` scores across every game and read as "the fix changed nothing" — the
     reader was pulling the wrong fields (`player.get_stat("F", "game")` and `gm.score` were the
     right ones). Separately the item 22 anti-vacuity draft passed a loop that never executed
     once, because six `PAINT_SPOTS` names resolved to no coordinate at all.
   - THE RULE. Every null from here proves its harness is SENSITIVE first, by perturbing
     something the harness must be able to see and showing that it moves. The worked example is
     `scratch_sensitivity.py`: it shifted `CONTEST_EUCLIDEAN_RADIUS` in
     `BackEnd/constants/__init__.py` and showed scores move, which is what licensed reporting
     "item 24's fix changed no outcomes" as a finding rather than as a shrug. Without that step
     the sentence is not a result.
   - A sensitivity control is cheap and it is not optional. It is the only thing separating "we
     looked and there was nothing there" from "we did not look."

7. OPEN, do not chase yet — something OUTSIDE placement is driving the two arms apart, and it is
   now the larger term
   - Recorded 2026-09-07 from the before/after of the spot-key fix, `equiv-v3`, n=20 per arm.
   - The placement channel converged sharply, which was the point: tight-contest divergence
     +26.1% -> +1.4%, defender-distance median divergence -7.8% -> +1.2%.
   - But the headline gameplay numbers diverged. Points per team: sim minus played was 3.3
     before (68.95 vs 65.65) and is 12.1 after (67.83 vs 55.75). Turns FLIPPED SIGN: played was
     22.2 turns ABOVE sim before (419.75 vs 397.55) and is 35.8 BELOW after (371.30 vs 407.10).
   - ORIGINAL READING, now partly WITHDRAWN: "placement was masking a second divergence, and
     something outside placement is the larger term." The second clause is not supported.
   - WHAT THE POISON-STASH TEST SHOWED (run after the above was written). Travel time is
     `dist / rate` (`skeleton_step_emitter.py:816`) and the emitter decrements `clock_remaining`
     by it, so **offense geometry feeds game length**. Replacing the converter's output with
     `{x:-9999,y:-9999}` took the PLAYED arm from ~370 turns to ~15 per game and its draws to
     -95.7%, raising no exception; the SIM arm on the identical poison moved only -12% turns and
     -4.8% draws. 6 seeds, both arms, no errors.
   - So placement owns a strong and STRONGLY ARM-ASYMMETRIC channel into turn count. The fix
     increased real travel distance — players used to be co-located on the logo and now move
     between authored spots — which is a direct mechanism for the played arm's turns falling
     419.75 -> 371.30. That is placement, not something outside it.
   - WHAT IS STILL OPEN, and it is narrower than first stated: why the two arms are coupled to
     geometry to such different degrees, and whether the points/team gap widening to 12.1 is
     fully explained by the played arm simply playing fewer possessions. Note the poison used
     absurd geometry, so it proves the channel exists and is asymmetric; it does not quantify
     how much of the 12.1 it accounts for.
   - Candidate for the asymmetry, still a hypothesis: the shot contest reads live `Player.coords`
     in the played arm and a stamped grid in the sim arm (logged separately below).
   - Deliberately not chased in the placement increment. Needs its own attribution pass, which
     should now start from the distance-to-clock channel rather than looking outside placement.

8. Legacy shot handler crashes on turns with no animations[] (`ShotAnimationSystem.runSetupTween`)
   - Symptom: `TypeError: turnData.animations is not iterable`. Caught by `processShot`, so no crash,
     but that shot silently does not animate (possession appears to skip its shot).
   - A SHOT_ATTEMPT reached the LEGACY handler carrying no `animations[]`. Schema turns bypass these
     handlers entirely, so this is either (a) an un-migrated path whose backend emit produced nothing,
     or (b) a routing bug where a turn WITH `animation_steps[]` was sent to the legacy handler anyway.
   - NOT fixed with a `|| []` guard on purpose: that would silence the console and hide the emission
     failure behind a shot that quietly does not animate. A `[SHOT-NO-ANIM]` diagnostic is in place
     (2026-08-27) logging result_type / current_turn / fast_break_play / hasAnimationSteps / turnKeys.
     `hasAnimationSteps: true` => routing bug. `false` => upstream emission bug.
   - ✅ DIAGNOSTIC ANSWERED 2026-09-08 by measurement, not by waiting for a report: **`false` — an
     upstream emission bug**, so (a), not (b). The culprit is named and fixed in item 11: FLSS
     normal/penalty shots stranded their skeleton on a local `roles` dict, so neither payload was
     emitted. 5 such turns per 8 games; render-nothing turns now 0.
   - Still open here, and NOT addressed by that fix: the inconsistent `turnData.animations` guarding
     in `ShotAnimationSystem.js` below. The emission gap that used to reach it is closed, but the
     handler remains unguarded at 572/666 and would still throw on any future empty payload.
   - Related: `ShotAnimationSystem.js` guards `turnData.animations` inconsistently (guarded at 295/479/486,
     bare at 352/455/572/666). Sites 572/666 remain unguarded on the final_turn-skips-setup path.
   - Pre-existing; unrelated to the animation cleanup pass.
9. Practice squad assignment sits on the green pulse modal until refresh (found 2026-09-03)
   - Symptom: Confirm on `cut-players.html` in assignment mode (week 1) swaps in the "Assigning
     Practice Squad" pulse and never leaves it. A refresh shows the assignment was in fact saved.
     Seen on a new franchise instance for an existing user.
   - STATUS: root cause UNCONFIRMED. The client-side defects below are proven from code and are
     worth fixing on their own terms. The backend-latency explanation is an untested HYPOTHESIS — it
     shows the wait COULD be long, not that it WAS long in the observed occurrence. Do not treat the
     (a)/(b) workloads as the diagnosed cause until the check under DIAGNOSTIC comes back.
   - Leading alternative, roughly as likely: a transient network/deploy event. A blackholed socket
     (wifi drop, laptop sleep, a container roll mid-request) hangs a `fetch` without rejecting and
     produces an identical screen. Nothing observed so far distinguishes it from the hypothesis.
   - NOT an error. Every failure path in `cut-players.js` (`!res.ok`, `res.json()` reject, network
     reject) lands in the `.catch` and swaps the pulse for "Assignment Failed". The pulse was still
     up, so the `fetch` never settled — a wait (or a dead connection), not a throw. This is
     consistent with BOTH the hypothesis and the network explanation; it does not choose between them.
   - The wait is UNBOUNDED — a defect in its own right, and the one thing certainly wrong here.
     `submitCuts()` (cut-players.js 280-304) replaces the confirm modal with a terminal, action-less
     pulse and hands the remaining UX to one
     `fetch` plus `window.location.href = buildFccUrl()`. No timeout, no progress, no fallback, so
     latency anywhere in the chain is indistinguishable from a freeze. The browser also keeps the
     cut-players document (and its pulse) on screen until the FCC document commits, so the FCC's own
     load time sits inside the same unbounded window.
   - HYPOTHESIS (unconfirmed — see STATUS). Two heavy workloads run synchronously inside
     `POST /franchise/cut-players` (franchise_routes.py 15262). This is the ONLY place week-1 PS init
     happens for a user who owes cuts — CPU training defers it (`defer_if_user_cut_pending=True`,
     15892) and this endpoint owns it (`False`, 15379):
     (a) `initialize_practice_squad` (practice_squad/manager.py 248) does four UNPROJECTED
     franchise-wide reads — every FTD, every FPD, every recruit — plus two full `db.teams` scans
     (`_build_region_team_map`, and `_format_team_name_map` → `resolve_team_name_map` with no
     `team_ids`), builds 48 rosters and a 336-game schedule, then `$set`s the whole `practice_squad`
     blob AND the entire `season_news` array back onto the franchise doc.
     (b) The walk-on portrait warm at 15362 — the only `warm=True` call site in the repo. Per
     surviving walk-on `_warm_walk_on_masters` does 3 `head_object` + 2 `get_object` + a PIL recolor
     composite + 1 `put_object` against R2, serialized. `r2_images._s3()` builds its boto3 client
     with NO timeout config, so botocore defaults apply (60s connect / 60s read, legacy retries up to
     5 attempts) — one unlucky R2 call parks the request for minutes.
   - (b) is a latency regression, not longstanding: it only started doing work in `a1bb6cea0`
     (2026-08-13, "Stop truth-testing pymongo Collections (walk-on warm never ran)"). Before that
     fix `_warm_walk_on_masters` threw on `not teams_collection` and the caller swallowed it, so warm
     cost was zero. The pulse modal landed one day later in `2841525c5` — it was papering over a wait
     that had just become far more expensive.
   - UNVERIFIED PRECONDITION for (b): `is_walk_on_fpd` requires `archetype == "walk on"`. If none of
     the active 12 were Walk Ons, `walk_ons` is empty and `assign_walk_ons_making_active_roster`
     returns before touching R2 — branch (b) evaporates entirely. Never checked for the observed
     franchise; the cut-players screen does not display archetype.
   - NOT evidence, despite looking like it: "happened on a new franchise at week 1, exactly when the
     expensive path runs." Week 1 of a new franchise is the only time this screen exists at all, so
     the coincidence carries zero diagnostic weight.
   - DIAGNOSTIC (do this before re-testing or writing part C). The roster commit is known to have
     landed (assignment was saved), so one read splits the hypotheses:
     `db.franchises.findOne({_id: ObjectId("<fid>")}, {"practice_squad.initialized": 1,
     "practice_squad.initialized_week": 1})`
     - `initialized: true` => the handler ran past the commit, through the warm, through PS init, to
       the return. Server finished the work; the loss was on the wire or the FCC navigation was the
       slow leg. Points at network/deploy; part C is NOT implicated.
     - missing/false => the handler stalled or died between the commit and the PS write, which is
       exactly the warm + PS-init window. Part C is implicated.
     Corroborate in Railway logs for that franchise/timestamp: `[WALK-ON-ROSTER] franchise=… warm=N`
     (INFO, walk_on_roster_identity.py:198) settles whether the R2 paint ran at all;
     `[PRACTICE-SQUAD] week-1 init failed` would show a swallowed exception.
     Observed occurrence: franchise `6a999b82b3eb46146c5710ac`, 2026-09-03 ~12:09pm ET.
   - Re-testing is a WEAK first move: that franchise's `practice_squad.initialized` is now true, so
     the expensive path will not run again — reproduction needs a brand-new franchise. And a
     non-reproduction clears nothing while the transient-network explanation is live.
   - Retry trap: the roster commit (`_update_ftd_roster_state`, ~15325) lands BEFORE the slow work,
     so a user who gives up and retries hits `cut_required == false` → 400 → "Assignment Failed",
     making a succeeded first attempt look like a hard failure.
   - The older failure mode here is genuinely closed and must not be re-fixed: after the roster
     commit both remaining blocks are wrapped in `except Exception`, so this endpoint can no longer
     500 post-commit (that was `2841525c5`).
   - Fix. A and B ship regardless of what DIAGNOSTIC returns — an unbounded client wait and a retry
     that 400s after a successful commit are defects on their own terms, and A is what makes a
     genuine network blip recoverable instead of terminal. C is GATED on DIAGNOSTIC showing the
     backend was the slow leg; if `initialized: true`, do not write C off the back of this report.
     C1's timeout config is defensible as standalone hygiene either way.
     - A. Bound the client wait. The pulse must never be a terminal state: drive the `fetch` with an
       `AbortController` + timeout. On timeout do NOT show "Assignment Failed" (the commit may have
       landed) — re-read `/franchise/command-center/data` and navigate to the FCC when `cut_required`
       is false, otherwise offer an explicit retry.
     - B. Make the POST idempotent so a timeout or refresh resolves cleanly. When `cut_required` is
       false, if the requested ids are already in `training_squad_players` and the active roster is
       12, return the normal success payload instead of 400. This is what actually kills the retry
       trap; A alone only hides it.
     - C1. Give `r2_images._s3()` a botocore `Config` with explicit `connect_timeout` / `read_timeout`
       and `retries={"max_attempts": 2, "mode": "standard"}`, so no single R2 op can park a request
       for minutes. Then drop `warm=True` at 15362 rather than optimizing it — portraits already
       paint lazily via `ensure_player_image`, which is exactly what CPU teams rely on (`warm=False`,
       12925). The eager warm buys nothing a user can perceive and it is the least bounded work in
       the request. CONFIRM FIRST: the lazy-paint claim is read off docstrings/comments in
       walk_on_portraits.py and `_warm_walk_on_masters`, not traced end-to-end. Verify
       `ensure_player_image` actually paints an unwarmed master on demand before deleting the warm.
     - C2. Project the `initialize_practice_squad` reads. It only needs `team_id` +
       `training_squad_players` from FTD, and `player_id` / `meta` / `position_ratings` /
       `attributes` from FPD (see `gather_region_pool`, `_fpd_pool_entry`, `_frd_pool_entry`) — it
       currently pulls entire documents for ~128 teams' worth of players. Pass `team_ids` to
       `resolve_team_name_map` to scope one of the two `db.teams` scans, and stop rewriting the whole
       `season_news` array on a write whose point is `practice_squad`. The read shapes are verified
       against the consumers; the COST is not — nobody has timed `initialize_practice_squad`. Time it
       before optimizing it.
    - Do NOT "fix" this by widening the pulse into a spinner-with-message or by adding a retry button
      alone. The bug is that the client has no bounded outcome and the request carries work it should
      not; a friendlier wait screen leaves both intact.

10. RESOLVED 2026-09-08 — a terminal turn reports ONE clock through FIVE fields, and the renderer
    read a stale one. ⚠️ THE ORIGINAL DIAGNOSIS IN THIS ENTRY WAS WRONG; retraction below.
   - Symptom, as reported: the game clock "stops early — freezes with time still on it", at some
     quarter boundaries but not others. **The symptom was real.** The mechanism logged for it was not.
   - ⚠️ RETRACTION OF THE 2026-09-07 MEASUREMENT. This entry claimed "11/64 = 17.2% of boundaries end
     with clock unconsumed" and blamed call-site coverage of `ensure_quarter_end_clock_drain`. Both
     are false, and the error was in the PROBE, not the game. The residue detector computed
     `rec.get("clock_end") or rec.get("clock")`. At a drained boundary `clock_end` is the integer
     `0` — falsy in Python — so the expression silently fell through to the pre-turn `clock` STRING
     and reported "0:01" as residue. Re-measured without the falsiness bug, 8 games / 32 boundaries:
     `clock_end == 0` on **32/32**, and `game_state["time_remaining"] == 0` on every one of them.
     **The clock is fully consumed.** The same read error produced item 13 (now retracted) and
     inflated item 11. See item 16 for the practice lesson.
   - ACTUAL ROOT CAUSE. One fact — how much clock is left after this turn — is reported through five
     fields: `clock_start`, `time_elapsed`, `clock_end`, `time_remaining`, `clock`. Both terminal
     authors set `clock_end = 0` and left `time_remaining` and `clock` holding their PRE-turn values.
     The renderer resolves the clock as `time_remaining` → `clock`/`game_clock` → `clock_end`
     (`gameScene.js:2671-2677`), so it read the stale field first and never consulted the correct
     one. Measured: **8 of 32 boundaries (25%) displayed a non-zero clock at the buzzer** — 6 DREB,
     1 PUTBACK_MAKE, 1 PUTBACK_MISS, showing 0:01 or 0:02 while the authoritative clock was 0.
   - Found by catching the WRITE rather than reading: a tracing `dict` subclass caught
     `quarter_ends_after = True` being stamped at `eoq_clock_progression.py:530` from
     `_finalize_synthesized_clock_turn`, 6/6 for DREB, with `time_remaining` never touched.
   - FIX: a single author, `stamp_terminal_clock`, writes the whole reported field-set; both terminal
     functions call it. Guarded by `tests/test_terminal_clock_contract.py`.
   - ACCEPTANCE: FE-visible non-zero boundaries **8/32 → 0/32**. Turn counts were a GATE, not a
     report — the fix changes no elapsed time, so every seed had to be unchanged, and all 8 were
     (353/366/378/384/332/373/340/370, identical before and after).
   - THE CALL-SITE THEORY WAS ALSO WRONG, recorded because it survived a design review. The asymmetry
     it rests on is REAL: DREB, PUTBACK_MISS and PUTBACK_MAKE reach `run_micro_turn` (which drains)
     **zero times each**, going instead through `_finalize_synthesized_clock_turn` (390/36/30), which
     does not drain. But adding the drain there would have changed nothing: **0 of 812 synthesized
     turns arrive with clock > 0 and no continuation**, and `quarter_ends_after` is False on all 812
     at that moment, so the predicate would evaluate False every time. The originally "rejected
     explanation" (add DREB to the terminal set) and its replacement (fix the call sites) were BOTH
     no-ops. The clock was never the thing that was broken.
   - `finalize_terminal_dreb_turn` DELETED along with its two gated call sites
     (`game_manager.py:1574-1577`, `:1711-1714`). It fired 0 times across 8 games and would have been
     inert if wired, for the predicate reason above — dead code shaped like a safety net.
   - The `if time_remaining > 0: return` guard in `normalize_quarter_end_after_clock_update` is
     CORRECT and was never the failure — it is the part that WORKS. It passed on exactly the 8
     affected boundaries (entered at 0, proceeded, stamped terminal) and bailed 384/390 times for
     DREB when the clock genuinely had time left. Inverting it would strip continuations from every
     mid-quarter turn. Pinned by `test_normalize_returns_early_while_the_clock_still_runs`.
   - Still true and still not causal: a terminal DREB burns a minimum of 1 second regardless of clock
     remaining (`game_manager.py:1200`), and `POST_DREB_FLSS_MIN_CLOCK = 2` routes to terminal rather
     than a final shot at `time_remaining <= 2`. Together they create the 1-2 second window — which
     the clock then correctly consumes, and only the payload misreported.

11. RESOLVED 2026-09-08 — FLSS shots stranded their skeleton on a local and emitted nothing to render
   - ⚠️ RE-SCOPED. Previously logged as "5 of 64 boundaries". Of the 7 boundaries with neither
     payload, **5 were RUN_OUT_CLOCK, which legitimately carries no coords**, so the real boundary
     population was 2. Measured game-wide, the true population is **5 render-nothing shot turns per
     8 games (0.625/game)**, of which only 2 sit on a boundary and 3 are mid-quarter. It was never
     boundary-specific — that was an artifact of only ever sampling boundaries.
   - ROOT CAUSE, the same CLASS as item 5: a producer that never hands its output to the consumer.
     In `resolve_flss_shot_logic` (`eoq_perfection.py`) the normal/penalty zones build
     `skeleton_steps` into a local `roles` dict, then return `result = shot_manager.resolve_shot(roles)`
     — a DIFFERENT dict. The skeleton stays on the local and never travels. The heave zone does not
     have the bug: it returns its own literal carrying `"skeleton": {"steps": skeleton_steps}`.
   - Consequence chain, measured end to end: `turn_manager.py:2096` gates the ENTIRE FLSS emit block
     on `result.get("skeleton")` → skipped → no `animation_steps`. FLSS never carries `roles` either
     (0 of 11 resolutions), so the legacy fallback lands on `turn_manager.py:2283` `animations = []`.
     Both payloads empty; the frontend is correct on empty input and renders no movement.
   - Split before the fix, 11 FLSS resolutions across 8 games: heave 6, **all** carrying a skeleton;
     normal 4 + penalty 1, **all** without. Exactly the 5 render-nothing turns.
   - ANSWERS ITEM 8's open diagnostic: `hasAnimationSteps` is **false** — an upstream emission gap,
     not a routing bug.
   - DEAD HYPOTHESIS, recorded so nobody re-derives it: the "Quick Shot fallback" path, which logs
     constantly during these games and looked like the obvious culprit. `quick_shot` is False on 5/5;
     `flss` is True on 5/5.
   - FIX: the normal/penalty path stamps `result["skeleton"]`, matching what the heave branch already
     does. ACCEPTANCE: render-nothing shot turns **5 → 0**; `[SHOT-NO-SCHEMA]` fires 30 → 25.
   - ⚠️ THIS HALF IS NOT COSMETIC, which was not anticipated at design time. The skipped block also
     contained `finalize_flss_post_emit` — EOQ CLOCK logic — which fired 6 times before the fix and
     13 after. Restoring it moves game trajectories: turn counts changed on 5 of 8 seeds (e.g.
     366 → 397). This is why the two halves are reported separately.
   - SPC principle 8 (draws moved, so no exact diff applies): poisoning the newly supplied FLSS
     geometry (mirror x) diverged 1 of 8 games. Weak but positive, and expected — an FLSS shot is by
     construction the last of its period, so its geometry usually has nothing downstream left to
     affect. The trajectory movement above comes from the restored `finalize_flss_post_emit`, not
     from travel time.
   - ORIGINAL 2026-09-07 OBSERVATION, retained for the frontend reasoning which still holds:
     the shot resolved and the clock advanced with nothing emitted to move anybody.
   - THE FRONTEND IS CORRECT ON EMPTY INPUT and is not the failing side here. The schema path
     requires a non-empty array (`AnimationEngine.js:646-647`,
     `Array.isArray(...) && length > 0`), so with both payloads empty it falls through to
     `handleShotAttempt` → `ShotAnimationSystem` with `maxSteps = 0`: shot make/miss resolution runs,
     the movement loop is skipped entirely. That renders as "something animates but it's visibly
     wrong" — the ball resolves, the players do not move.
   - This is the BACKEND CAUSE of item 8 above (`ShotAnimationSystem` reaching the legacy handler
     with no `animations[]`). Item 8's diagnostic asks whether `hasAnimationSteps` is true or false to
     split routing bug from emission bug; this measurement answers it for the boundary case —
     **false, an upstream emission gap**, not a routing bug.
   - Distinguish from a related but separate observation: 22.9% of steps at a quarter-final turn have
     nobody moving, vs 15.6% mid-quarter, and one boundary turn emitted 3 steps in which nobody moved
     at all (1/46 at boundaries, 0/4,743 mid-quarter). That one is boundary-specific but n=1.
   - RULED OUT as the cause of "half the team missing": coordinate coverage is complete. Across
     16,632 emitted steps, every step carries all ten players — min 10, max 10, 0% below ten, at
     boundaries and mid-quarter alike.
   - Also ruled out: any frontend quarter-boundary gate. There is NO end-of-quarter handler in the
     renderer at all — EOQ is layered onto the generic turn pipeline via `result_type` and flags like
     `quarter_ends_after`, and nothing flushes or short-circuits the animation queue on a quarter
     change. There is no gate here to be closing wrongly.
   - NOT FIXED.

12. OPEN — every EOQ chain key is absent from BOTH `_init_game_state` and the reload restore list
    (traced 2026-09-07)
   - Same family as the `frontcourt_established` / `offensive_state` gap already logged below, and
     unswept: `game_state` is restored KEY BY KEY at `BackEnd/api/api.py:1652-1690`, and the code
     says so itself — "game_state is restored key-by-key, so a key with no line here is silently
     lost on every reload." (That comment block is duplicated at 1668-1671.)
   - The EOQ chain keys appear in neither place, so on a reload they come back as `_init_game_state`
     defaults, i.e. absent: `late_clock_eoq_chain_active`, `flss_possession_pending`, `flss_from_dreb`,
     `_flss_after_dreb_rebounder_id`, `final_shot_possession_active`, `final_shot_ran_this_chain`,
     `suppress_final_shot_sfx`, `pending_oreb`, `final_turn_shot_this_turn`, `_last_final_turn_quarter`,
     `_shot_dreb_fb_play_key`, `eoq_trace_seq`, `eoq_trace_turn_in_seq`.
   - HAZARD, NOT A ROUTINE PATH — this qualification matters. The rebuild requires the in-process
     `ongoing_games` cache to be dropped, and the drops are new-game, resume-anchor and
     timeout-resume. Timeout-resume was the candidate mechanism and it was MEASURED AND REJECTED:
     **0 of 32 boundaries had a timeout within the last 5 turns**, despite 71 timeouts across those
     8 games. Engine timeouts do not cluster at quarter ends.
   - So this bites when a user refreshes, or resumes from a timeout, NEAR a boundary while an EOQ
     chain is mid-flight — losing the whole chain state — not on every quarter.
   - NOT FIXED. Note it is latent: nothing observed has been attributed to it.

13. ⚠️ RETRACTED 2026-09-08 — the "0:14 RUN_OUT_CLOCK residue" was never real
   - This entry recorded a single RUN_OUT_CLOCK quarter ending with `0:14` on the clock, deliberately
     flagged as n=1 and unexplained. It was the SAME probe falsiness bug as item 10: the detector
     read `clock_end or clock`, and with `clock_end == 0` being falsy it fell through and reported
     `clock_start` as residue.
   - Re-measured: that turn consumed all 14 seconds — `clock_start = 14`, `time_elapsed = 14`,
     `clock_end = 0`, `time_remaining = 0`, `clock = "0:00"`. Every RUN_OUT_CLOCK boundary in the
     sample is clean, and the builder does exactly what the entry said it should.
   - The three untested candidates listed here were explanations for a phenomenon that did not occur.
     No fix was needed and none was made. Nothing to chase.

14. RULED OUT 2026-09-07 — two EOQ hypotheses killed by measurement; do not re-derive them
   - Recorded because both are re-derivable from reading the code and both look right on paper. The
     lesson generalises: on this codebase, reading establishes what should happen and repeatedly is
     not what does.
   - (a) **`final_turn_pacing._step_action_coords` is spot-blind.** It reads `coords` then
     `location` and never `spot` (`final_turn_pacing.py:116-124`), returning `None` otherwise, and it
     feeds `_slowest_offense_move_seconds` — travel time, hence the final turn's pacing, hence the
     clock. That is the exact defect shape of the converter bug fixed the same day (item 5), sitting
     in the EOQ path. It looked like the cause of the clock symptom.
     MEASURED: **55 calls, 55 resolved, zero `None` returns.** It never sees a spot-only pos_action.
     Corroborated independently: that module performs no `game_state` or turn_result writes at all.
   - (b) **The converter fix in item 5 caused this.** Its fallthrough now DECLINES to place a player
     rather than substituting court centre, which would present as missing players — a perfect match
     for "partial animation, half the team".
     MEASURED: **zero keyless pos_actions across 16 games**, so the decline path never fires; and
     coordinate coverage at boundaries is complete (all 10 players in all 16,632 steps). The fix is
     not implicated in the EOQ symptom.
   - Also rejected in the same trace, with its own reasoning: the drain's terminal predicate as the
     cause of item 10 (see item 10 — it would have looked like a fix).
   - Added 2026-09-08: **(c) the "Quick Shot fallback" as the cause of the empty shot payload** —
     it logs constantly during these games and looked obvious. `quick_shot` is False on 5/5 of the
     render-nothing turns. It is FLSS (item 11). And **(d) the whole call-site theory for item 10**,
     which was measured to be a no-op before any code was written.

15. OPEN, LARGER THAN WHAT WAS FIXED — `time_remaining` disagrees with `clock_end` on 17.4% of
    MID-QUARTER turns (measured 2026-09-08)
   - The terminal case is fixed in item 10. The general case is not, and it is bigger:
     **`time_remaining != clock_end` on 497 of 2,864 non-boundary turns (17.4%)**, versus 8 of 32
     boundary turns before the fix.
   - Same shape as item 10 — one fact, five fields, and a renderer that resolves
     `time_remaining` → `clock` → `clock_end` (`gameScene.js:2671-2677`), so it reads the field
     most likely to be stale.
   - The ONLY reason this is invisible mid-quarter is that the next turn's payload overwrites it a
     moment later. At a boundary there is no next turn, which is why the terminal case was the one
     anybody noticed. That makes this latent, not benign: any consumer that reads a single turn in
     isolation — a replay, an export, a paused frame, a resumed game — gets the wrong clock.
   - DELIBERATELY OUT OF SCOPE for the item 10 increment, on the reasoning that fixing it moves the
     displayed clock on roughly one turn in six across the whole game, which is a balance-visible
     change that wants its own before/after. `tests/test_terminal_clock_contract.py` is scoped to
     terminal turns for the same reason and would fail the tree today if widened.
   - Owner of the general path is `turn_manager._attach_clock_contract` (`:205`), the only other
     writer of `clock_end` in `BackEnd/`.

16. PRACTICE, not a code defect — the controls have caught more than the measurements have
    (recorded 2026-09-08)
   - A single `or` falsiness bug in throwaway probe code produced **three wrong bugs.md entries**:
     item 10's entire root-cause diagnosis, item 13 in full, and an inflated population for item 11.
     The expression was `rec.get("clock_end") or rec.get("clock")`; `clock_end` is the integer `0`
     at exactly the moment of interest, which is falsy, so it read a different field and every
     downstream conclusion followed honestly from a bad number.
   - This matters more here than it would elsewhere, because in this project essentially every
     decision is justified by measurement. The measurements are written fast, once, by the same
     person who wants a particular answer, and they are not themselves tested. The controls —
     poisons, counterfactuals, anti-vacuity checks, independence gates — have now caught more real
     errors than the measurements they police, including this one and the item 6 coordinate result.
   - Cheap habits that would have caught it, in order of value: (1) assert the falsy-but-valid case
     explicitly — `x is None` rather than `or`; (2) sanity-check a probe against a second field that
     must agree; (3) before believing a headline number, poison the code path it measures and
     confirm the number MOVES. The third is already policy for fixes (SPC principle 8) and should
     apply to diagnoses too, which is the actual gap.
   - Related: item 6 (the suite has no assertion on resolved coordinate values). Confirmed again for
     the clock dimension on 2026-09-08 — with the new guard excluded, reverting the terminal clock
     fix produces **zero** new test failures, and re-stranding the FLSS skeleton also produces
     **zero**. An empty baseline delta remains evidence of nothing.

17. HAZARD, structural — a block gated on ONE concern was silently carrying an UNRELATED one
    (found 2026-09-08 while fixing item 11)
   - What happened: the FLSS emit block at `turn_manager.py:2096` is gated on
     `result.get("flss") and result.get("skeleton")`. Its name, position and guard all say it is
     about EMITTING ANIMATION. But it also contains `finalize_flss_post_emit` — **EOQ clock
     finalization**, which has nothing to do with whether anything renders.
   - So for the 5 shots per 8 games whose skeleton was stranded (item 11), the missing skeleton did
     not merely suppress animation. It skipped clock finalization for those turns as well, and
     nothing anywhere reported a clock problem. MEASURED: `finalize_flss_post_emit` fired **6 times
     before the fix and 13 after**. Turn counts moved on 5 of 8 seeds (e.g. 366 → 397).
   - THE HAZARD, stated generally: when a block is gated on one condition but performs two jobs, a
     failure of the gate silently disables the job the gate was never about. The visible half
     (nothing renders) gets reported and investigated; the invisible half (clock finalization
     skipped) does not, because there is no symptom attached to it. Fixing the visible half then
     "unexpectedly" changes simulation behaviour — which is exactly what happened here, and would
     have looked like a regression from the fix rather than a restoration.
   - This is distinct from the hazards already logged. It is not a stale field (item 10), not a
     missing assertion (item 6), and not a lost key on reload (item 12). It is **scope creep inside
     a conditional**: the guard is correct for one concern and accidental for the other.
   - SWEPT 2026-09-08, static census of all `BackEnd/**/*.py` (AST, read-only, no instrumentation).
     **RESULT: 1 true instance — this one — and it is still LIVE. 0 latent.**
   - Raw enumeration: **38 candidate blocks** in 7 files — 33 `if <render precondition>:` blocks
     whose body also touches non-render state, plus 5 functions that early-return on a missing
     render payload and do non-render work in the tail. Broadening the body-work detector from a
     curated hint list to "any `game_state` write, any non-render turn-dict key, any stat call"
     moved the count 30 → 33, so the enumeration is not hint-limited.
   - 37 of 38 are LOOKALIKES, and they fail on ONE test: **the predicate IS the body's data
     dependency.** `if anim_steps:` guarding
     `result["time_elapsed"] = burn(anim_steps[0], anim_steps[-1])` is not a hazard, it is a
     function of its argument — with no steps there is no schema burn to compute and `time_elapsed`
     correctly keeps the resolver's value. Same for every step-index/coord stamp
     (`steal_stop_step_index`, `shot_clock_violation_step_index`, `last_stealer_coords`), the screen
     stats counted out of `skeleton["pos_actions"]`, and the pass-interception contest that walks
     the skeleton's own steps. Nothing is skipped in these; the work is vacuous without its input.
   - THE DISCRIMINATOR that isolates the real instance: **the predicate is not the dependency.**
     `finalize_flss_post_emit(game, result)` never reads `result["skeleton"]` — it reads
     `result["flss"]`, `game_state["time_remaining"]` and `result["animation_steps"]`, and it guards
     `animation_steps` ITSELF at `eoq_clock_progression.py:584`. The block would have done correct,
     meaningful work had it run with the predicate false. That is what made it silent-and-wrong
     rather than silent-and-vacuous, and it is the only site in `BackEnd/` with that property.
     (Automatable as: a call inside a render-gated block, to a `BackEnd`-defined state mutator,
     where no argument carries the render payload named in the predicate.)
   - **STILL LIVE — item 11 fixed only one of the two routes into this gate.** Commit 2 made
     `resolve_flss_shot_logic` stamp `result["skeleton"]`, closing the FLSS-shot route. But
     `turn_manager.py:5084` also sets `result["flss"] = True` for a buzzer-fit OREB putback
     (`fit_buzzer_putback_steps` when the putback schema is longer than the clock left), and putback
     results carry no skeleton **by explicit design** — `turn_manager.py:5410` "Putback shots don't
     have a skeleton", `turn_manager.py:5424` `"steps": []  # No skeleton for putbacks`. So
     `result.get("flss")` is true and `result.get("skeleton")` is falsy, and the gate is false.
     `finalize_flss_post_emit` has exactly ONE call site (`turn_manager.py:2120`, inside the gate),
     so that family never reaches EOQ clock finalization at all.
   - What is skipped on that route, named: the schema-burn `time_elapsed` realignment;
     `mark_late_clock_eoq_turn` and `activate_late_clock_eoq_chain` (the late-clock EOQ chain never
     activates); and the `game_state.pop("final_shot_possession_active")` teardown.
   - **CORRECTION 2026-09-08 — the original census entry claimed a cascade here and was wrong.**
     It asserted `final_shot_possession` was "authored solely inside the gate", citing the single
     line `turn_manager.py:2121`. The grep shows THREE authors —
     `grep -rn 'final_shot_possession' BackEnd/ FrontEnd/` → `turn_manager.py:2121`, `:4549`,
     `:5085` — and `:5085` sits directly beneath the `result["flss"] = True` at `:5084` that creates
     this very instance. So for the buzzer-fit putback family `flss` AND `final_shot_possession` are
     both True, `turn_manager.py:2148`'s condition IS satisfied, and `final_shot_ran_this_chain`
     DOES get set. There is no cascade. The claim overstated the defect.
   - Severity is bounded twice over: `turn_manager.py:2142-2146` runs UNCONDITIONALLY, so the
     generic `ensure_quarter_end_clock_drain` / `normalize_quarter_end_after_clock_update` still fire
     for these turns; and `final_shot_possession` is set independently at `:5085`. What is genuinely
     lost is the FLSS-specific late-clock chain, the schema-burn realignment, and the teardown —
     not the whole drain and not the chain-ran flag. The core finding survives:
     `finalize_flss_post_emit` never runs for this family, and item 10's residue concentrating in
     `PUTBACK_MISS` (2) and `PUTBACK_MAKE` (1) corroborates it.
   - LEDGER PRACTICE, changed as a result (second time a single-site citation produced a wrong
     conclusion in this workstream — see also item 10's retraction): any claim of the form "X is
     authored/called only at Y" must cite **the grep**, not a line number. A line number proves the
     site exists; it does not prove it is the only one. Where this entry claims a sole call site —
     `finalize_flss_post_emit` at `turn_manager.py:2120` — the evidence is
     `grep -rn 'finalize_flss_post_emit' BackEnd/`, which returns the def plus that one call and
     nothing else.
   - **SEVERITY DOWNGRADED 2026-09-08 after tracing what the block would actually add (Part A).**
     Three of the four skipped effects turn out to be redundant or contra-spec for this family:
     (1) the schema-burn `time_elapsed` realignment is ALREADY performed by the OREB path itself at
     `turn_manager.py:5089-5113`, and `eoq_shortened_oreb` exists precisely to skip the
     `OREB_PUTBACK_MIN_TIME_ELAPSED` floor there (`:5110`), so the value
     `finalize_flss_post_emit` would compute is the same raw schema burn; (2)
     `ensure_quarter_end_clock_drain` is ALREADY called unconditionally at `turn_manager.py:2142`
     — verified by AST that its only enclosing constructs are `def run_micro_turn` and a bare
     `Try`, no `if`; (3) `mark_late_clock_eoq_turn` and `activate_late_clock_eoq_chain` are the two
     the spec says must NOT run — `EOQ_System.md:19` "OREB ≠ EOQ chain start", `:389` "OREB at >30s
     or without active chain: putback only; **no `late_clock_eoq` tag, no chain activation**", and
     `:150` "**Do not** call `activate_late_clock_eoq_chain()` on every OREB. Early-quarter OREBs
     (e.g. at 5:00) used to permanently block Final Shot because the gate requires
     `not late_clock_eoq_chain_active`." And (4) the `game_state.pop("final_shot_possession_active")`
     teardown is redundant too: `clear_late_clock_eoq_chain` pops that same key
     (`eoq_clock_progression.py:114`) and is called both from the terminal branch of
     `ensure_quarter_end_clock_drain` (`:563`, reached unconditionally via `turn_manager.py:2142`)
     and on every quarter change (`turn_manager.py:1586`).
   - **NET: all four effects are redundant or contra-spec for this family, so the gate evaluating
     false costs nothing.** The instance is LIVE in the reachability sense — the predicate really
     can be false — but its consequence is nil. It stays logged as a HAZARD, not a bug: the shape is
     still one gate carrying two concerns, and the next family routed through it may not be so lucky.
   - CONSEQUENCE FOR THE FIX: **do not split the gate.** Making `finalize_flss_post_emit` run for
     this family would arm an EOQ chain on a buzzer-beating putback, which is the documented
     regression at `EOQ_System.md:150`. The gate evaluating false here is closer to accidentally
     correct than to broken. Closed 2026-09-08 as NO CHANGE.
   - ALSO REJECTED: removing the `flss` tag at `:5084`. It is load-bearing on the FRONTEND, which is
     the non-obvious part. `AnimationEngine.js:395` routes `flss && quarter_ends_after` into
     `_finishFinalTurnQuarterEnd` (the quarter-end finish sequence); `ShotAnimationSystem.js:1158`
     uses `flss || final_turn` to suppress a bogus MAKE announcement when choreography is empty; and
     `turnPreparation.js:206` uses `final_turn && flss !== true` to suppress the FINAL_SHOT stinger.
     Dropping the tag changes all three. No measured symptom is driving that, so it is unbriefed.
   - `infer_eoq_trace_role` mislabels a buzzer-fit putback as `"FLSS"`. Left alone, and here is the
     verified reader inventory so the next person does not have to re-derive it — **`eoq_trace_role`
     is consumed ONLY by the EOQ debug-log subsystem.** Across all of `FrontEnd/` it appears at
     exactly five lines: `animationPlayback.js:1631` and `:1633`, which build a local `eoqFlow`
     used at `:1634-1637` and `:1652-1655` and NOWHERE else (grep for `eoqFlow` in that file
     returns those five lines), both call sites gated on `isEoqTraceEnabled(scene)` and both
     terminating in `logEoqSchemaStep`; and `eoqDebugLog.js:30`, `:149`, `:201`, which are the log
     module itself. Nothing branches playback on it. So changing that function's output IS a
     log-label change, not a playback change — the opposite of what it looks like at first glance.
   - Two ordering facts worth keeping, because they are easy to get backwards: both
     `animationPlayback.js:1629` and `eoqDebugLog.js:199` test `flss` FIRST, so a buzzer-fit putback
     (which has `flss` set) resolves to `'FLSS'` and NEVER reaches the `:1631`
     `final_shot_possession` test. That test would only start covering these turns if the `flss` tag
     were removed — which is a point in favour of removal being survivable, not evidence that the FE
     already treats them as final-shot possessions by that route.
   - RETRACTED, same date: the census claimed item 10's `PUTBACK_MISS`/`PUTBACK_MAKE` residue
     "corroborates" this instance. It does not. The drain at `:2142` is unconditional, so this gate
     never suppressed it; that residue is fully explained by item 10's own payload-consistency
     defect (five fields, one fact), which is fixed. The corroboration was reasoning backwards from
     a matching family name.
   - Reachability is argued statically only; **frequency is unmeasured** (the census was scoped to
     no runtime instrumentation). Requires an OREB turn, `PUTBACK_MAKE`/`PUTBACK_MISS`,
     `clock_available > 0`, and schema seconds > clock left. That measurement is the follow-up.
   - Secondary findings from the same pass, NOT instances of this shape, logged so nobody re-derives
     them: (a) `eoq_perfection.py:361` `combine_eoq_origin_prefix` POPS
     `eoq_origin_prefix_steps` BEFORE its own `if not prefix or not flss_steps: return` guard, so an
     empty `animation_steps` destroys and discards the prefix — a destructive read ahead of a guard;
     (b) `eoq_shortened_turn` and `eoq_origin_prefix_step_count` are written and have **zero**
     consumers anywhere in `BackEnd/` or `FrontEnd/`; (c) the up-front event tables at
     `phase_resolution.py:3292` — **traced separately below, verdict LATENT/UNREACHABLE**;
     (d) `phase_resolution.py:3400` counts screen
     stats off a FRESH `get_hco_skeleton(None, game, lean_score=1.0)` rather than the emitted
     skeleton, and consumes a `random.randint(1, 2)` per attempt; (e) `game_manager.py:1195`
     abandons an entire synthesized DREB turn (`return None`) when `animation_steps` is empty — an
     all-or-nothing gate, not the asymmetric shape, but a render precondition deciding whether a
     turn exists.

18. LATENT, and it kills our only mechanism for symptom #3 — the sunset up-front event tables
    cannot be re-animated (traced 2026-09-08)
   - THE SHAPE, and why it looked dangerous: `phase_resolution.py:3308-3310` retires ~150 lines of
     legacy foul/steal/dead-ball-turnover resolution using a POSITIVE-LIST flag over a key with no
     guaranteed value — `_opt = game_state.get("offense_play_type", "")` then
     `skip_upfront_events = _opt in ("motion", "set", "set_play")`. `""` is not in the tuple, so any
     read that misses the key runs the retired code. `offense_play_type` is absent from
     `_init_game_state` (VERIFIED: 0 occurrences in `game_manager.py`) and `api.py:3908` logs
     "offense_play_type NOT in saved state (will be set by set_playcalls())" on load, so the key
     genuinely can be missing from `game_state`.
   - **VERDICT: LATENT — static argument plus an 8-seed executable control, reload path unverified.**
     Deliberately NOT stated as "proven unreachable": see the coverage limits below.
     The reason it does not fire is ordering, not the key's presence. `resolve_hco_outcome` (which contains 3308) has
     one live caller, `phase_resolution.py:7862` inside `resolve_half_court_offense_logic`; that has
     one caller, `turn_manager.py:3939` inside `resolve_half_court_offense`; that has one caller,
     `turn_manager.py:2045`. AST shows `:2045` and the sole `set_playcalls()` call at
     `turn_manager.py:1939` share an identical enclosing chain down to `If(1935, ELSE)`, with 1939
     strictly before 2045. So every execution that can reach 3308 has already run `set_playcalls()`.
   - `set_playcalls` (`turn_manager.py:2712-3080`) always writes the key before returning: exactly
     two returns (`:2911`, `:3072`), two writes (`:2906` inside the `if user_offense` override body
     that owns `:2911`; `:3067` at function-body top level, unconditional, dominating `:3072`).
     Neither write can be falsy — the normal path draws from `weighted_random_from_dict`, which
     returns a key of the passed dict and RAISES on empty or all-zero weights
     (`shared.py:87-103`), and the override path uses `play_doc.get("play_type", "motion")` where
     **all 23 documents in the live catalog are `motion` (4) or `set_play` (19)** — queried
     read-only, zero anomalies. The key is never popped or blanked anywhere in `BackEnd/` (grep
     empty). `turn_manager.py:2901-2902` shows the override path was already deliberately fixed for
     exactly this ordering concern.
   - The one branch that skips `set_playcalls` — `turn_manager.py:1935` `if result is not None`, the
     Force Foul path — also skips HCO resolution entirely ("skip set_playcalls and
     resolve_half_court_offense"), so it cannot reach 3308 either. A reload with the key missing is
     safe for the same reason: the next HCO possession writes it at `:1939` before resolving.
   - Note the `:3075` shape (`chosen_play_type if chosen_play_type else None`) is in the RETURN dict,
     not the `game_state` write. It cannot introduce a `None` into `game_state`.
   - **SYMPTOM #3 HYPOTHESIS — DEAD.** Jamie's long-standing "turnovers attributed to the wrong ball
     handler" was hypothesised to come from these tables attributing by a different rule. The two
     models DO name the handler differently, and the difference would have fit the symptom: the
     sunset path identifies a ball handler via `get_ball_handler_from_skeleton` at a RANDOM step
     index purely to score the contest, then throws it away — `_check_steal_attempt` returns
     `("STEAL", None, None)` / `("D_FOUL", None, None)` (`:2957`, `:2959`) and
     `_check_dead_ball_turnover` returns `("DEAD_BALL_TURNOVER", None, None)` (`:3131`), so no player
     is propagated at all and attribution falls to whoever downstream picks. The live per-step
     moment walk instead names the actual walked step's handler and credits a defender explicitly
     (`phase_resolution.py:4669-4678`: `bh_pos`, `moment_defender_id`, `_hco_moment_defender_id`).
     But since the sunset path is unreachable, this cannot be the mechanism. **Symptom #3 is now
     without any known mechanism** — that is the useful result, because it stops the search here.
   - NOT FIXED, deliberately. Deleting retired code is its own brief. Recorded so the next reader
     does not re-derive the reachability argument. If the flag is ever touched, the safe shape is a
     NEGATIVE list (skip unless explicitly legacy), not a positive one over a defaultable key.
   - EXECUTABLE CONTROL, run 2026-09-08 (`scratch_optprobe.py`, one game per process,
     `PYTHONHASHSEED=0`, seeds 8001-8008): **8 games, 3,193 turns, 787 HCO resolutions, ZERO falsy
     or unexpected reads.** Distribution was `'motion'` 396 (50.3%) and `'set_play'` 391 (49.7%);
     nothing else appeared. The FIRST read of every one of the 8 games was already valid, which
     directly covers the "first HCO resolution of a fresh game" concern.
   - The probe wraps `resolve_hco_outcome` and does nothing but (1) read
     `game_state.get("offense_play_type")` with a sentinel, (2) record the value in a probe-local
     Counter, (3) raise if it is not in `("motion", "set", "set_play")`, (4) delegate to the
     original unchanged. It writes nothing to any game object, consumes no RNG, and changes no
     ordering — so probed and unprobed runs have no path by which they can diverge, and no separate
     null-control arm is needed. It wraps the function rather than line 3308 because 3308 reads into
     a local that cannot be hooked without a source edit; the wrapper sees the same value because
     nothing between `:3142` and `:3308` writes the key, and it runs before the function's first RNG
     draw at `:3257`.
   - ANTI-VACUITY (item 6's lesson — a green control is worthless unless it can go red): narrowing
     the accept-set to `("motion",)` made a legitimate `'set_play'` read trip the assert on seed
     8002, call 1, Q1 turn 1, with the full context captured. The raise path executes.
   - **COVERAGE LIMITS — a clean run proves unreachable for the game shapes these 8 seeds produce,
     not universally.** Two paths are NOT covered and remain static-argument-only:
     (i) **the user-override path** (`turn_manager.py:2775-2911`). `user_offense` derives from
     `game_state["user_offense_override"]`, written only by `api.py:5527` from a request body, so a
     headless sim never takes it. Its static safety rests on the write at `:2906` preceding the
     return at `:2911`, and on the catalog check (23 docs, all motion/set_play, `"motion"`
     fallback). Related fixture caveat: the harness's mongomock plays catalog loads EMPTY, so
     playcall selection falls back to `"Inside"` — harmless to `chosen_play_type`, which the
     weighted draw still sets, but it means the catalog-backed `play_doc.get("play_type")` read is
     untested at runtime. (ii) **mid-game reload with the key absent from saved state.** The harness
     runs four quarters against one in-process `GameManager` and never reloads from the DB, so the
     `api.py:3905/3908` restore path is entirely outside this control. It stays ASSUMED.
   - So: the first-HCO-of-a-fresh-game concern is now measured and clean; the reload concern is not,
     and a green run must not be read as covering it.


<!--
SEARCH TAG: [CODE-CLEANUP]
Every outstanding code-level fix/cleanup item surfaced during the documentation sweep (and the
ongoing code-cleanup backlog) is tagged with the literal token [CODE-CLEANUP]. To get the complete
list across the whole repo, run:  rg "\[CODE-CLEANUP\]"
This includes items in this file (Future Cleanup, P0, Fast Break backlog, FB test follow-up) plus
inline notes left in individual system docs. (Sunset-mode code removal also carries its own
"SUNSET MODE" tag inside the docs that describe those paths, and is cross-linked from here.)
-->

19. OPEN, needs its own diagnosis — MISS is the largest content-free frozen family and an idle
    loop is the WRONG fix for it
    - ~~MISS is 30.9% of content-free frozen steps on the played arm, the largest single
      family.~~ **SUPERSEDED 2026-09-08 — the 30.9% was keyed on the wrong field and the real
      population is much smaller.** That figure came from `offensive_state`, which lives on
      `game_state` and **never reaches the turn dict**, so it was never selecting the population
      it claimed to. Re-keyed on `turn["result_type"] == "MISS"`, ~~the family is 15.9 s of
      animation per game, of which roughly 79 visible still player-steps over 4.8 s occur while
      the ball is loose. That is one of the SMALLEST remaining items, not the largest.~~
    - **THE RE-KEY WAS ITSELF MEASURED ON THE SIM ARM. CORRECTED 2026-09-09** (items 29 and 31;
      probe `scratch_tails_miss.py`, re-run with `PLAYED=1`, 8 seeds, detectors verified firing).
      MISS is the family the shim bug distorts MOST, because HCO is 83% of played steps and
      near-absent on the sim arm, so the sim run was measuring a different population: 522 MISS
      steps across 8 games against a real 6,129.

      | claim | published (SIM) | corrected (PLAYED) | factor |
      |---|---|---|---|
      | total MISS animation | 15.9 s/game | **247.0 s/game** | 15.5x |
      | still MISS player-steps | 2,098 | 30,930 (3,866/game) | 14.7x |
      | frozen MISS steps | 3 across 8 games | 928 | 309x |
      | frozen AND content-free | 1 across 8 games | 636 (79.5/game) | 636x |
      | visible loose-ball slice | ~79 player-steps/game over 4.8 s | **782/game over 39.8 s** | 9.9x / 8.3x |

      **THIS REVERSES A LIVE DECISION.** "One of the SMALLEST remaining items" was the basis for
      ranking MISS 4th of 4, below the `bounce` beat and below the design work. At 39.8 s/game of
      visible loose-ball stillness it is the LARGEST remaining defect after defect 2, and it is
      re-ranked 3rd in `rewarding_animation_fix.md`. Nothing had been built on the wrong number,
      which is the only reason this is a correction and not a rework.

      **WHAT SURVIVES.** The destination split still reads **0.0% `elsewhere`** (56.9% no
      destination, 43.1% already there, against a published 50.2/49.8/0.0), so the authoring-
      absence diagnosis and the no-idle-here exclusion are both untouched. Only the size moved —
      but it moved in the direction that changes what we do next. It was deliberately
      EXCLUDED from the idle-wander stillness work (commits below) and that exclusion is the
      point of this entry, not an oversight.
    - Also established by the re-key: the stillness is **authored**, not a failure to reach a
      destination — there are no unreached destinations in the population. 1,073 player-steps
      (51.1% of still MISS players) are `stationary`/`guard_offball` while the ball is loose,
      which is the indefensible half. **CORRECTED on the played arm: 11,511 such player-steps
      (1,439/game), 37.2% of all still MISS player-steps and 95.6% of the loose-ball still
      population** — so the indefensible half is 10.7x larger than published and is now almost
      the entire loose-ball population rather than half of it. `shoot`, `pass`/`receive` and
      pre-release stillness remain the defensible remainder. The fix is therefore authored
      movement, which is expensive — but on the corrected size it ranks ABOVE the design work,
      not below it.
    - WHY IT IS DIFFERENT FROM THE FAMILIES THAT WERE STAMPED. Free throws, inbounds, dead
      balls and the post-make hold are static basketball moments: play is stopped and men
      standing in place is correct, so a render-space weight shift is the honest fix. A MISS is
      LIVE play — boards crashing, guards leaking out. If those steps are frozen, the defect is
      that NOBODY IS SPRINTING WHEN THEY SHOULD BE, and looping an idle over a rebound scramble
      would look worse than the freeze, not better. Same error class as putting
      CONTINUE_FROM_PREVIOUS on ball-carrying steps: right mechanism, wrong moment.
    - WHAT THE DIAGNOSIS HAS TO ANSWER, and it is a question about authoring, not rendering:
      what are those frozen MISS steps FOR? If they are timing padding they should be deleted.
      If they are beats where off-ball players SHOULD have rebound-crash or leak-out
      destinations, the fix is authoring those destinations, which is the expensive work this
      workstream has been deferring.
    - DO NOT stamp an idle here to make the number go down. The number going down would be the
      defect getting harder to see.

    RELATED AND MEASURED IN THE SAME PASS — DEFECT 4'S FRAMING UNDERSTATED IT BY 2.8x.
    "Whole-step freezes" counts a step as frozen only when all ten players are still, so a step
    where three move and seven stand around scored as NOT frozen. The eye sees seven dead
    players. Measured on the played arm, 8 games, perceptible steps only:

      | | rate | population |
      |---|---|---|
      | whole-step freeze (the number the workstream ran on) | 16.3% | 2,298 of 14,121 steps |
      | **per-player stillness** | **45.6%** | 64,669 of 141,738 player-steps |

    Only 14.8% of steps have everybody moving. 85.2% carry at least one visibly still player,
    the average step has 4.6 of 10 standing, and the distribution is bimodal — the mode is one
    still player (18.6%) with a second peak at all ten (16.0%). HCO alone holds 82% of it
    (52,813 of 64,669), which is invisible on the sim arm per standing rule 6b.
    Per-family stillness: FREE_THROW 82.1%, SIDE_INBOUND 66.7%, OREB 61.9%, BASELINE_INBOUND
    60.0%, FCP 48.9%, HCO 44.6%, HCT 41.1%, FAST_BREAK 33.9%, DREB 7.9%.
    ~~STILL UNADDRESSED after the idle work: OREB (1,695 still player-steps), FCP (1,147),
    HCT (908). Out of scope by decision, not by measurement.~~ — **ALL THREE STAMPED
    2026-09-08, commit `95958565b`. Defect 4 is closed;** see
    `rewarding_animation_fix.md` "Defect 4 — CLOSED". MISS remains excluded and this entry
    remains open for it alone.

    ATTRIBUTION NOTE, since the numbers above do not reproduce keyed the same way. Item 19's
    per-family figures came from `offensive_state`, which is not carried on the turn dict, so
    they cannot be re-derived directly. Re-measured by EMITTER instead — which is the
    attribution the fix actually needed, because it names the function to modify:
    `oreb` 1,705 (`build_oreb_animation_steps`, and 1,013 + 637 + 45 from PUTBACK_MAKE /
    PUTBACK_MISS / OREB_KICKOUT reproduces the 1,695 above exactly), `dynamic_fcp` 1,587,
    `dynamic_hct` 2,730. The FCP/HCT figures are LARGER than item 19's 1,147 and 908 because a
    pressure possession's terminal shot steps come from the skeleton emitter, so the two keyings
    are not interchangeable. Do not treat them as a before/after pair.

    ALSO MEASURED, and unstamped: `dreb` carries 294 still player-steps at 7.9%, the lowest of
    any family, and `hct_step_emitter.build_hct_animation_steps` — the LEGACY HCT emitter —
    emitted zero steps across 8 played games. The live one is `dynamic_hct`. If anyone goes
    looking for HCT authoring, that is the file to read and the other is a candidate for
    deletion.

20. OPEN, small but real — BASELINE_INBOUND steps carry 16 to 20 player ids in `start.coords`,
    not ten
    - Measured on the played arm: BIP steps average 12.6 paired players, with individual steps
      carrying 16, 17 and 20. Every other family carries exactly 10.
    - CONSEQUENCE. Any per-player writer that iterates `start.coords` and trusts it to mean
      "players on court" will act on players who are not in the game. The idle-wander writer
      works around it with an explicit `on_court` intersection built from the lineups
      (`transition_bridge.py` `_stamp_inbound_idles`), and has a poisoned guard against the
      workaround being dropped — but the workaround is not the fix.
    - NOT DIAGNOSED: whether these are the outgoing lineup after a substitution, both teams'
      full rosters, or stale ids from the prior possession. Nobody has followed a specific
      extra id back to where it was written.
    - This is the same shape as the coord-authority problems already logged: a map that names
      more players than are playing is a fact about authorship, and the renderer being
      defensive about it hides rather than fixes it.

21. NOT REPRODUCED on the played arm — the fouled-three misread, and the one population that
    looks like it from the stands
    - THE REPORT: half-court set, released from behind the arc, shooter fouled, shot missed, two
      free throws awarded; box score and announcement also read a two. Observed on staging.
    - MEASURED, 8 played games, 820 field-goal attempts through `resolve_shot`, 174
      shooting-foul free-throw awards, `PYTHONHASHSEED=0`, one game per process. Null control:
      probe installed but silent produced 137,949 sim_rng draws against 137,949 unprobed on
      seed 1, and matched the unprobed count on all 8 seeds, so the probe does not perturb.
    - ZERO reproductions. No attempt was scored as a two while the coord it was classified from
      was behind the arc. Free-throw awards were consistent with `is_three` on 174 of 174
      (missed three → 3, missed two → 2, any make → 1). Coverage is total: 174 of 174 awards
      occurred inside `resolve_shot`, so no shot path escaped the records.
    - ALL FOUR BRIEFED CANDIDATES MEASURE EXACTLY ZERO:
      1. `release.get("x") is None` skipping the `roles["shot_spot"]` write
         (`shot_manager.py:845`) — 0 of 820. `compute_micro_release_coord`
         (`shot_micro_movements.py:554`) builds its return from `shooter_coord` and always
         carries both keys, so the guard cannot fail.
      2. The `release.get("y", pre_micro_sy)` blend at `:848` — 0 of 820, unreachable for the
         same reason. The fallback is dead code, not a live blend.
      3. Inverted `is_away_offense` — 0 disagreements of 860 between the value
         `_build_shot_classification` computes at `:586` and the one passed to the micro plan at
         `:836`. The proposed quarter correlation cannot exist at all: nothing in `BackEnd/`
         switches ends between periods (grep: `switch_ends|swap_baskets|flip_court`, zero hits),
         so home always attacks x≈91 and away x≈9 for all four quarters.
      4. The dunk branch zeroing `is_three` at `:1720` — 0 of 820. The branch is unguarded but
         the block enclosing it is not: `:1686` requires `shot_type in ("inside", "attack")`.
         362 attempts entered it, every one of them `inside` or `attack`, never `outside`.
    - THE ONE POPULATION THAT MATCHES WHAT A VIEWER WOULD REPORT, and it is not a defect in the
      classifier: 45 attempts (5.62/game) where the shooter set up behind or exactly on the arc
      and the micro footwork carried him inside it before release. 11 drew a shooting foul
      (1.38/game), 7 were fouled misses awarded two free throws (0.88/game). Every one is
      `shot_type="attack"` with micro family `strong_attack`, which moves exactly one
      `MICRO_STEP_GRID` rimward — 4.5 grid units, ~4.2 ft
      (`constants/shot_micro_movements_constants.py:8`, `shot_micro_movements.py:1208-1211`).
      42% of them started *exactly on* the line; the median start was 1.0 unit behind it.
      Scoring these as twos is correct basketball: the man drove. But the rendered distance
      between "behind the arc" and "inside it" is four feet at the top of the key, so a viewer
      reasonably reads it as a three that paid two. UNTESTED: whether the animation makes that
      4.5-unit step legible on screen. That is a render question, on the arm the human is
      looking at, and it is the next thing to measure — not the classifier.
    - CONFIRMED THE EXISTING INSTRUMENT WORKS. The `[3PT-READ]` diagnostic at `:1053` fired on
      109 of 109 HCO attempts on seed 1 with DEBUG on, and cost nothing: 137,949 draws with it
      on, 137,949 with it off. `resolved_is_three` agreed with `role_spot_is_three` 109 of 109,
      which is the direct refutation of the brief's premise. It disagreed with `coord_is_three`
      on 12 of 109, which is BY DESIGN and documented in place at `:932` — "Contest geometry
      uses pre-micro shoot spot; classification uses release." Anyone reading that field as a
      misread signal will chase these 12 and find nothing.
    - PREMISES OF THE BRIEF THAT SURVIVED VERIFICATION: `is_three` at `:2116` is the same
      variable assigned at `:865`, sole reassignment between them at `:1720` (grep for
      `is_three` across the file, one assignment each at 860/865/1720); `_build_shot_classification`
      does prefer `roles["shot_spot"]` then `shooter.coords` then the spot name (`:584-617`);
      the fast-break `allow_three` gate at `:854` is not implicated, and in fact the spot-name
      fallback never ran once — all 820 classifications sourced from `shot_spot`, 0 from
      `legacy_spot_fallback` and 0 from `missing_coords`.
    - STILL OPEN, and the reason this is NOT REPRODUCED rather than NOT A BUG: Jamie saw it on
      staging and this measurement is local HEAD (`5b73d722b`; `0fc2dc1dd` is an ancestor, so
      the free-throw arithmetic fix is present). If staging runs a different commit the
      measurement does not cover it. The frontend was ruled out as an independent source — it
      carries no 2-vs-3 determination of its own (grep `is_three|isThree|three_point|threePoint`
      across `FrontEnd/static/js`: one test file, no production reader).

22. OPEN hazard, not currently a bug — 22.3% of shots are classified by a knife-edge comparison
    - The authored arc spots sit EXACTLY on the classification boundary. The `key` spot
      normalizes to x=64.0 and `_three_point_boundary_x(25.0)` returns 64.0
      (`shot_geometry.py:12-22`). The test is `normalized_x <= boundary_x` (`:80`), so equality
      resolves as a three.
    - MEASURED: 153 of 686 attempts (22.3%) have a pre-micro coord sitting exactly on the
      boundary — 65 at `key`, plus `upper wing`, `lower wing`, both midwings, all the
      midcorners. They currently resolve correctly as threes only because the comparison is
      `<=` rather than `<`.
    - THE HAZARD: a 0.01-unit change to the arc table, the normalization, or the authored spot
      coords reflips 22.3% of the shot population in one direction, and a `<=`→`<` edit — the
      kind of change that looks like a tidy-up — silently converts every arc spot to a two.
      Nothing in the suite asserts the value of a resolved classification, which is item 6's
      territory: the coordinate-assertion gap logged there covers this exactly.
    - NOT A DEFECT TODAY. Logged because the population is large, the margin is zero, and the
      failure would present as a league-wide scoring shift rather than as a broken test.

    GUARDED 2026-09-08, commit `46db3bf2a` — `tests/test_three_point_arc_boundary.py`.
    - **The first assertion on a resolved classification value anywhere in this suite.** Item 6's
      gap is now one hole smaller: 37 assertions covering all nine on-boundary spots at both ends
      of the floor, through BOTH entry points (`classify_shot_value` and
      `is_three_point_shot_from_coords` fail different counts under poison, so guarding one would
      have left the other open).
    - Poisoned five ways, all caught. `<=`→`<` on the two entry points separately fails 19 and 27
      of 37. The comparison inverted outright, and the classifier stubbed to `return True`, each
      fail only 2 — which is exactly why the paint-spot and step-inside-the-arc assertions exist.
    - Spot coordinates NOT moved. Adding margin changes which shots are threes, so it is a balance
      change wearing a tidy-up costume; still deferred until after Jamie's balance pass. The zero
      margin is now load-bearing and asserted instead of incidental.

23. SWEPT-ADJACENT HAZARD, found while writing the item 22 guard — spot names are CASE-SPLIT
    across the constant tables, and a case-sensitive lookup silently undercounts
    - `THREE_POINT_SPOTS` and `PAINT_SPOTS` name spots in lowercase (`"lower midwing"`,
      `"basketspot"`). `HCO_STRING_SPOTS` authors the COORDINATES in camelCase
      (`"lower midWing"`, `"basketSpot"`). Grep for `midcorner` finds only the lowercase name
      list and concludes the spot has no coordinate authored anywhere.
    - CONSEQUENCE, measured while enumerating item 22's population: a case-sensitive sweep of the
      arc spots finds FIVE sitting on the classification boundary and misses the four
      mid-wing/mid-corner ones, which are also at margin exactly zero. The real count is nine.
      The same sweep resolves ZERO of the six `PAINT_SPOTS`, which is how the first draft of the
      guard's anti-vacuity check passed a loop that never executed once. A `checked >= 6` floor
      caught it; without the floor the guard would have shipped green and vacuous.
    - THIS IS THE SAME CLASS as the spot-key converter that did not speak its own module's
      vocabulary (`54a2a9c0e`) and as the stranded FLSS skeleton: a producer and a consumer
      disagreeing on a name, with no error at the seam. Third appearance.
    SWEPT 2026-09-08. **ZERO measured crossings. The hazard is LATENT, not live — retire it.**
    Census: `scratch_casecensus.py` (registry-level instrumentation), `scratch_arcresolve.py`
    (end-to-end), `scratch_poison_retry.py` (causal). 8 played games, one per process,
    `PYTHONHASHSEED=0`. Null control: probe installed but silent reproduced canonical draw
    counts exactly (137,949 / 142,536), so it does not perturb. Detector proven to fire by
    self-test on three lookups with known-in-advance outcomes (a hit, a case-crossing miss, an
    unknown-name miss), each classified correctly.

    THE URGENT QUESTION — the nine on-boundary arc spots DO resolve correctly in production.
    101 of 101 shots authored from an on-boundary spot classified as threes, including all 16
    from the four case-collision spots (`lower/upper midWing`, `lower/upper midCorner`). Zero
    disagreements against what each spot's own authored coordinate implies. The item 22 guard is
    NOT sitting over a live defect. It is also not sitting over a dead path: all 860 attempts
    resolve with `classification_source="shot_spot"`, i.e. by COORDINATE, which is exactly the
    path the guard asserts on.

    - **Conventions: three, not two, and the split is authoring vs classification.** My original
      wording ("THREE_POINT_SPOTS is lowercase, HCO_STRING_SPOTS is camelCase") was too coarse.
      The coordinate/authoring registries — `HCO_STRING_SPOTS`, `OFFSET_SPOTS`,
      `HCO_OFFENSIVE_SPOTS`, `INSIDE_PAINT_SPOT_NAMES` — use camelCase for the compound names
      (`midWing`, `lowPost`, `basketSpot`, `midLane`, `topLane`, `highPost`, `midBaseline`,
      `midCorner`, `midPost`). The classification registries — `THREE_POINT_SPOTS`,
      `PAINT_SPOTS` — are all-lowercase. `turn_manager.py:2659` is a third: an inline lowercase
      literal duplicating `PAINT_SPOTS` rather than importing it. FrontEnd
      `courtPositions.js` is camelCase, matching the backend authoring side.
    - **Exactly 10 names collide**, and no others: the 4 arc names (`lower/upper midcorner`,
      `lower/upper midwing`) and the 6 paint names (`basketspot`, `lower/upper lowpost`,
      `lower/upper midpost`, `midlane`). Note `PAINT_SPOTS` and `INSIDE_PAINT_SPOT_NAMES` name
      THE SAME SIX SPOTS in opposite conventions.
    - **WHY NOTHING CROSSES, measured.** 619,038 registry lookups across 8 games at 43 reached
      sites, `miss_crossing` = **0**. Two independent reasons, both verified:
      (a) `shot_manager.py:349` and `:360` — the two return paths of
      `_get_shooter_position_and_spot` — apply `.lower()` at the SOURCE, so every consumer of a
      spot name receives it pre-normalized and the lowercase classification registries match.
      That is the choke point, and it is why the "case insensitive" comments at `:581` and
      `:648` are honest about the contract even though the comparisons beside them are
      case-sensitive.
      (b) The named-spot coordinate path is BYPASSED. `THREE_POINT_SPOTS` and
      `INSIDE_PAINT_SPOT_NAMES` were **never consulted once** in 8 games, and
      `phase_resolution.py:4409`'s legacy named-spot fallback never executed, because the
      skeleton carries explicit coordinates and the branch above prefers them.
    - **`phase_resolution.py:4408-4414` is a DEAD ad-hoc workaround for this exact hazard**,
      comment and all: "Case-insensitive lookup (skeleton may use 'upper midwing' vs constant
      'upper midWing')". It retries case-insensitively after sniffing the `{50,25}` default.
      Poisoned by removing it: on-boundary resolution is byte-for-byte unchanged (58/58 threes,
      13/13 collision-set, 0 disagreements both arms), because the branch it sits in is never
      entered. Someone hit this problem, fixed it at one site, and the fix is now unreachable.
      **Do not treat it as the existing normalizer.** There is no shared normalizer anywhere in
      `BackEnd/` or `FrontEnd/` — grep for `normalize_spot`, `canonical_spot`, `spot_key`,
      `SPOT_ALIAS` returns nothing. What exists is five scattered inline `.lower()` calls.
    - **WHAT KEEPS THIS LATENT RATHER THAN ABSENT: 83% of lookups default to a plausible
      coordinate.** Of 59 `.get()` sites against the coordinate tables, 49 return a real-looking
      coord on a miss — 26 give `{50,25}` (center court), 9 give `{64,25}` (the key), 7 fall
      back to another spot lookup, 5 to a live coord variable. Only 10 return `None`. So the
      day a producer starts emitting a name in the other convention, nothing objects and the
      symptom is a coordinate, not an error. That is the converter-bug shape unchanged; the
      reason it is not firing is that no producer currently crosses, not that a miss would be
      caught.
    - NO FIX. Normalizing names across the codebase moves coordinates and coordinates move
      outcomes, and there is currently nothing to fix — zero crossings. The honest action is to
      leave the conventions alone and NOT write a normalizer nobody needs.

24. OPEN, found by the item 23 census and NOT a case crossing — `select_defender_closest_to_victim`
    looks up POSITION CODES in a spot-name table, so it can never hit
    - `phase_resolution.py:667`: `coords = HCO_STRING_SPOTS.get(pos, {"x": 50, "y": 25})` inside
      `for pos, defender in def_lineup.items()`. `pos` is `"PG"`/`"SG"`/`"SF"`/`"PF"`/`"C"`;
      `HCO_STRING_SPOTS` is keyed by spot NAME. **Measured 0 hits and 20 misses across 8 played
      games — a 100% miss rate**, the only site in the census with one.
    - CONSEQUENCE: when the fallback fires, all five defenders collapse to `{50,25}`, every
      Euclidean distance to the victim is identical, and "closest defender" resolves to whoever
      `def_lineup` happens to iterate first. **This is the logo-stack shape again** — five
      players at one coordinate.

    CORRECTION TO THIS ENTRY, made while fixing it: I wrote "the selected player is CHARGED WITH
    A FOUL". That is wrong, and I took it from the function's own docstring ("For intentional
    foul") rather than from its callers. The caller that actually collapses is
    `turn_manager.py:2639` in `_execute_forced_shot` (shot-clock violation), where the selected
    player becomes `roles["defender"]` — the CONTESTING defender on a forced shot, not a fouler.
    The foul-charging caller is `turn_manager.py:619`, and it passes real per-position coords and
    never collapsed in 8 games. The defect is real; its consequence was one step less severe
    than this entry claimed.
    - The function's own docstring says the fallback uses "position-based default spots (key)".
      It does not: `key` is x=64 and the actual default is x=50. The documented intent is not
      implemented, which is why this reads as working.
    - REACHABILITY, by grep — three callers. `turn_manager.py:619` passes real coords (`d_dest`)
      and is SAFE. `turn_manager.py:2639` and `eoq_perfection.py:711` both pass `None`
      explicitly and take the fallback. Measured 4 occasions per 8 games (~0.5/game, 5 lookups
      each).
    - SYMPTOM VISIBILITY: **invisible.** Both branches consume the same `random.randint` draws,
      so draw counts do not move and no equivalence gate can see it. The only observable is a
      foul attributed to a defender who was not nearest — which is the same family as Jamie's
      long-standing symptom #3 (events attributed to the wrong player), still untraced.
    FIXED 2026-09-08, commit `e23fe0e81` — `phase_resolution.py`,
    `tests/test_nearest_defender_contract.py`. Resolves from `player.coords`; a defender with no
    usable coordinate is SKIPPED rather than given a stand-in, and the function returns None when
    nobody can be placed. Docstring corrected: it claimed the fallback used "position-based
    default spots (key)", but `key` is x=64 and the default was x=50, so the documented intent
    was never implemented — a large part of why this read as working.

    - CONTRACT GATE, and the only gate that means anything here: "the charged defender is the
      nearest by measured distance to the victim." BEFORE 9 satisfied / 3 violated; AFTER 12 / 0.
      Draw counts are identical across both arms and that is a fact about the RNG stream, NOT
      evidence of safety — both branches consume the same `random.randint` draws, so the gate
      that has protected every other change in this workstream is blind to this one.
    - **NO MEASURED OUTCOME CHANGE across 8 seeds** — identical scores, per-player fouls,
      foul-outs, team fouls and turn counts. The reason is worth recording: `resolve_shot`
      RE-DERIVES the contest defender from coordinates and overwrites `roles["defender"]`
      (`shot_manager.py:959/969`) unless `roles["fb_geometry_contest_resolved"]` is set, which
      `_execute_forced_shot` does not set. So the arbitrary pick was being discarded by its own
      consumer. Another producer/consumer seam where the producer's output does not reach the
      decision — the same family as items 5, 11 and 23, though here the disconnection is what
      made the defect harmless rather than what made it expensive.
    - That null was NOT believed on its own. The outcome harness was proven sensitive first by
      perturbing `CONTEST_EUCLIDEAN_RADIUS`, which moved scoring on 3 of 3 seeds. Worth noting
      that the FIRST draft of that harness read `game_stats["fouls"]`, which does not exist —
      fouls live behind `get_stat("F", "game")` — and reported zero fouls in every game on both
      arms. A null result and a broken reader are indistinguishable in a report, which is the
      third time this workstream a control has caught what a measurement asserted.
    - Poisoned four ways, all caught. Reinstating the defect fails 8 of 13 assertions.
      Defaulting a coordless defender to centre court, returning the first defender instead of
      None, and accepting a half-coordinate each fail exactly the assertion written for them. The
      iteration-order assertion is the one the old code could not have passed: same five
      defenders, five different dict insertion orders, one expected winner.
    - STILL LATENT, not fixed by this and worth knowing: `eoq_perfection.py:711` is the third
      caller, also passes None, and never fired in 8 games (it sits behind `zone == "penalty"`).
      It matters more than the one that does fire, because at `:716` it WRITES
      `defender.coords` — so an arbitrarily chosen defender would be teleported to the FLSS
      defender position. The fix covers it, since it is inside the function.

25. LOGGED, NOT FIXED — found by the item 24 Part 1 search, which is why the search came first
    - `defender_coords_by_pos_from_lineup` (`phase_resolution.py:596`) already existed and
      builds exactly the position→coords map item 24 needed. It routes through
      `grid_coords_from_player` (`:580`), whose fallback is `{"x": 50.0, "y": 25.0}` — so it
      carries the same fabrication one layer down. It could not be reused for the item 24 fix
      without reintroducing the defect, which is why `_usable_grid_coord` was added beside it
      rather than the existing helper being called.
    - Not currently harmful: measured 0 collapses at `turn_manager.py:619`, its consumer, across
      8 played games, because all ten players always had coords. It is a hazard, not a bug.
    - THE REST OF THE SEARCH CAME BACK CLEAN, and that is the useful half. The three other live
      proximity selectors — `attack_drive_clearance.py:317` (208 calls),
      `fb_geo_helpers.py:249` (17), `fb_stop_decision.py:43` (4) — showed ZERO collapsed
      candidate sets across 8 played games. They are safe by construction, not by luck:
      `_closest_pass_receiver` SKIPS candidates missing from `off_starts`, and the other two
      receive already-built coordinate maps. `phase_resolution.py:4022`
      `_find_closest_receiver` does default each receiver to `{50,25}` and IS the same shape,
      but it never executed — it sits on the sunset up-front event path (item 20).
    - THE TURNOVER ATTRIBUTION PATH DOES NOT CARRY THIS SHAPE, checked because Jamie's symptom
      #3 made it the priority target. `_check_steal_attempt` and `_check_dead_ball_turnover`
      name the ball handler from `get_ball_handler_from_skeleton`, not by distance, and where
      they do build coordinates (`:2884`, `:3066`) they already prefer `player.coords` with a
      per-player spot fallback that yields DISTINCT coordinates. Both sites also never executed
      in 8 played games. So item 24 is not a mechanism for symptom #3, and symptom #3 still has
      no traced mechanism.

26. POLICY, adopted 2026-09-08 — a coordinate fallback never invents a position
    - Recorded as a rule because the same shape has now produced five instances and two of them
      cost real money. The rule itself:

      **A COORDINATE FALLBACK NEVER INVENTS A POSITION — it skips the candidate, or it fails.**

    - WHY IT IS A RULE AND NOT A PREFERENCE. `{"x": 50, "y": 25}` is centre court, which is a
      perfectly plausible place for a basketball player to be. That is exactly what makes it
      expensive: a fabricated coordinate is indistinguishable from a real one at every point
      downstream, so nothing errors, nothing looks wrong, and the defect is only visible in
      aggregate months later. A `None` or a skipped candidate announces itself at the seam.
    - THE DISTINCTION THAT MATTERS. Placing a sprite and MEASURING between players are different
      contracts. A renderer needs some coordinate and centre court is a defensible choice. A
      comparison needs to tell "no coordinate" apart from "centre court", because a stand-in
      shared by several candidates makes every distance between them equal, and the comparison
      silently degrades into iteration order wearing the costume of a measurement. That is
      precisely how item 24 charged an arbitrary defender.
    - THE FIVE INSTANCES, for whoever does the eventual sweep:
        · the spot-key converter logo stacks (54a2a9c0e) — 644.5 five-player stacks per game,
          and a 79.2-point make-rate gap in the misplaced population
        · item 24's two callers — `turn_manager.py:2639`, `eoq_perfection.py:711`
        · item 25's `grid_coords_from_player` (`phase_resolution.py:580`)
        · `_find_closest_receiver` (`phase_resolution.py:4022`), latent on the sunset path
        · 26 further `.get()` sites that return centre court on a miss
    - DO NOT SWEEP THE SITES YET. Changing a fallback changes coordinates, and coordinates change
      outcomes — item 24 alone was measured against `CONTEST_EUCLIDEAN_RADIUS` sensitivity to
      establish that. A sweep is a balance change wearing a tidy-up costume and it belongs AFTER
      Jamie's balance pass. This entry is the policy only; `_usable_grid_coord`
      (`phase_resolution.py`) is the shape the eventual fix should take.

27. CLOSED — both proposed mechanisms for symptom #3 are eliminated. Do not re-derive them.
    - Symptom #3 is Jamie's long-standing report that TURNOVERS ARE ATTRIBUTED TO THE WRONG BALL
      HANDLER. Two mechanisms were proposed on separate evidence and both are now dead. Recorded
      together so nobody spends a third session rebuilding either one.
    - MECHANISM A — the `offense_play_type` sunset up-front event tables (item 18). The theory
      was that `_check_steal_attempt` and `_check_dead_ball_turnover` name the handler by a
      different rule than the live per-step moment walk, so any turn taking the sunset path
      would attribute turnovers inconsistently. MEASURED LATENT: the positive-list flag at
      `phase_resolution.py:3308-3310` never admitted a falsy read across 8 seeded games, with a
      null control proving the probe did not perturb the sim. The path does not execute, so it
      cannot be the mechanism.
    - MECHANISM B — item 24's arbitrary nearest-defender selector. The theory was that a
      selector which picks by iteration order while appearing to pick by distance could be
      naming the wrong player on a turnover. ELIMINATED BY INSPECTION AND MEASUREMENT: the
      turnover path names the handler from `get_ball_handler_from_skeleton`, not by distance
      (item 25), and item 24's selector chooses a CONTESTING DEFENDER, not a ball handler and
      not a fouler. Wrong player, wrong decision, wrong path.
    - SO SYMPTOM #3 STILL HAS NO TRACED MECHANISM, and the two obvious candidates are spent. A
      future trace should start from the attribution WRITE — where a turnover stat is credited to
      a player id — and work backwards, rather than from selectors that look suspicious.

28. NOT SWEPT, deletion candidate — the `bounce` empty beat

      51 steps per game of `advance_trigger.metadata.kind == "bounce"`, 300 ms each, carrying no
      content: no ball movement, no sound, no announcement, and no player movement. About 15
      seconds a game of nothing.

      Deliberately NOT touched by the defect 2 fill (2026-09-09). Filling it with an idle would
      paper over a beat that probably should not exist, and **deleting it moves step counts**,
      which puts it squarely under SPC principle 8 — a re-cut reference and a poison-stash, not a
      tidy-up. It wants its own brief.

      Establish before deleting: whether the step count feeds any RNG draw or clock burn. The
      earlier padding census asked the same question of the putback emitter's 9 non-content steps
      and it has not been answered for `bounce`.

29. RESOLVED 2026-09-09 — the three "zero-stamp" families were a HARNESS defect, and it
    invalidated a whole session of measurements. Case (a): production is fine.

      **THE ROOT CAUSE, and it is embarrassing rather than subtle.** `scratch_playedarm.py`'s
      `use_played_arm(gm)` is a **no-op unless the environment variable `PLAYED=1` is set**:

          def use_played_arm(gm):
              if os.environ.get("PLAYED") != "1":
                  return False

      Every probe in the defect-2 session called `use_played_arm(gm)` and **never set `PLAYED`**,
      and none of them checked the returned bool. So every run labelled "played arm" was in fact
      the **SIM arm**. `simulate_quarter` sets `_is_full_simulation` (main.py:913), `animator.py:1213`
      returns `[]` on that flag, and `build_skeleton_animation_steps` therefore bails at
      **skeleton_step_emitter.py:1606** (`if not skeleton_steps or not animations: return None`)
      before ever reaching its stamp calls at `:2804` and `:2814`. HCO emitted nothing, so
      `hco_still` and `make_hold` were zero; `_stamp_ft_idles` was likewise never reached.

      Proven by running the same probe both ways on seed 1:

      | family | sim arm | REAL played arm |
      |---|---|---|
      | `hco_still` | **0** | **5,611** |
      | `free_throw` | **0** | **474** |
      | `make_hold` | **0** | **188** |
      | `inbound` | 1,698 | 504 |
      | `_stamp_ft_idles` calls | **0** | **29** |

      `hco_still` at 5,611/game x 8 = 44,888, against the 40,175 the widening task reported.
      **The widening measurement was right and item 29's was wrong.** The residual difference is
      accounted for by the seeded plays catalogue and the intervening `HCO_PASS_SAFETY_BASE`
      175 -> 150 balance change (11bbaa16a).

      **BOTH mechanisms item 29 named were the same artefact.** The entry claimed two distinct
      defects — a producer whose output vanishes, and a call site never executing — and asserted
      "no early return between the `def` at :1549 and the stamp calls." That claim was false: the
      audit used `awk '/^    return /'`, which only matches a return at exactly four spaces of
      indent and therefore **could not see a return nested inside an `if`**. There are three, at
      `:1606`, `:1627` and `:2172`. A grep whose pattern cannot match the thing it is looking for
      returns zero and reads as proof.

      **WHY THE ANTI-VACUITY CONTROL DID NOT CATCH IT.** The probe injected a synthetic flourish
      and confirmed the payload reader counted it, 5/5, in both arms. That control was sound and
      it passed — but it only proved *the reader works*, never that *the harness was on the arm
      it claimed*. The zeros were real; the arm was wrong. **A control has to test the premise
      that is actually load-bearing**, and "am I measuring the thing I said I was" was not tested
      by anything.

      NOT A DEFECT, retracted before it was logged: the gap between stamps *written* (8,432) and
      stamps *in the payload* (5,611) was investigated and **cannot be attributed** with the
      instrument used. The payload path deep-copies, so the identity comparison used to test it
      was invalid by construction — 0 of 304 stamped step objects appear in the payload by
      identity, including for families with no gap at all. The emitter is called ~2x per HCO turn,
      so double-counting is the leading explanation. It is not being recorded as a loss.

30. OPEN, pre-existing — the idle density cap is exceeded on the played arm

      `IDLE_STILL_DENSITY_CAP` is 6, but **344 steps across 8 played games carry more than six
      idlers**. Identical in both arms of the defect-2 gate (344 before, 344 after), so the
      arrival fill does not cause it and does not worsen it — the fill shares one cap correctly.
      The still-player pass itself is what exceeds it, presumably because several families stamp
      the same step from different emitters and each only counts its own. Invisible until the
      arm bug above was fixed, because HCO never emitted on the sim arm.

31. BLAST RADIUS of the PLAYED=1 shim bug (item 29) — audited 2026-09-09, no re-measurement yet

      **MECHANICAL AUDIT.** 23 probes call `use_played_arm`. **NONE sets `PLAYED` internally and
      NONE checks the returned bool** — the shim is opt-in from the command line, so the probe
      source can never tell you which arm a figure came off. That is why this had to be settled
      from preserved OUTPUT rather than from code.

      What the source DOES show is a split in intent. 12 probes document `PLAYED=1` in their
      usage line and 8 branch on `os.environ.get("PLAYED")`; the probes written during the
      defect-2 session (`scratch_gate_settle`, `scratch_gate_curve`, `scratch_tails_miss`,
      `scratch_famcensus`, `scratch_knotcount`, `scratch_legacy_reach`, `scratch_shapepeek`,
      `scratch_survivors`) have **neither**. The earlier workstream knew about the flag. The
      defect-2 session did not, and that is the boundary of the damage.

      **THE ARM TEST USED HERE**, since no probe records its arm: on the sim arm
      `build_skeleton_animation_steps` returns None at `skeleton_step_emitter.py:1606`, so HCO
      emits almost nothing and **HCO idle-wander stamps are exactly zero**. Any preserved output
      containing HCO stamps, or HCO-dominated step counts, is therefore played-arm. Scale is the
      secondary test: ~17,700-19,800 player-steps per game on the played arm against ~8,000-10,000
      on the sim arm.

      | reported figure | probe | verdict | evidence |
      |---|---|---|---|
      | whole-step freeze census — 15,781 steps / 8 games, 16.3% freeze rate | `scratch_content.py` + `scratch_freeze.py` | **PLAYED — CLEAN** | `.arm/content_played_*` totals **exactly 15,781**. A companion `.arm/content_sim_*` set totals 6,350 and was NOT the figure published. `freeze_played` has turns_with_steps 1,954/1,987 = 98.3%; `freeze_sim` 1,701/3,158 = 53.9%. Both arms were deliberately run and correctly labelled. |
      | per-player stillness — 45.6% (item 19) | `scratch_perplayer.py` | **PLAYED — CLEAN** | `.arm/pp_*`: still 64,669 of 141,738 player-steps = **45.6%**, exact. HCO is 118,540/141,738 = **83.6%**, which is the "HCO 83%" also quoted. Decisively, HCO carries `wander_now` 1,373 on seed 1 — HCO idle stamps cannot be non-zero on the sim arm. |
      | continuity classification — 63,995 player-steps, ONE_STEP_JOURNEY 42.9% | `scratch_continuity.py` | **CITED FIGURE SUSPECT** | The preserved played-arm output `.arm/ease/live_*` totals **158,338** player-steps, with ONE_STEP_JOURNEY at 12.8% of all player-steps, 24.9% of moving ones, and 51.8% of journeys. **None of those is 42.9%**, and 63,995 is sim-arm scale (~8,000/game vs the artifact's 19,792/game). So a played-arm measurement of this exists and DISAGREES with what was published. |
      | MISS re-keying — 15.9 s/game, ~79 visible still player-steps | `scratch_tails_miss.py` | **SIM — SUSPECT** | Defect-2 session probe: no `PLAYED` in usage, no internal guard, and the item 29 root cause applies directly. Same probe whose tail headline moved 703.4 -> 1,849.6 s/game when the arm was fixed. |
      | item 23 lookup census — 619,038 lookups, 43 sites | `scratch_casecensus.py` | **UNDETERMINED — lower risk** | Output not preserved (`.arm/case/arc_*` is `scratch_arcresolve.py`, a different probe). The probe documents `PLAYED=1` AND carries an internal guard, so it was written arm-aware. Risk is limited because spot-name lookups sit on the RESOLUTION path, which runs on both arms; but any lookup inside an emitter would have been invisible on the sim arm, so the SITE LIST is what needs re-confirming, not the miss rate. |
      | item 24 selector census — 12 calls, 4 collapsed | not `scratch_proximity_audit.py` | **UNDETERMINED — lower risk** | `.arm/prox/after_*` does NOT contain `select_defender_closest_to_victim`; it records three OTHER selectors (`attack_drive_clearance.py:317`, `fb_geo_helpers.py:249`, `fb_stop_decision.py:43`), all with 0 collapsed. The 12/4 figure came from an output that was not preserved. `select_defender_closest_to_victim` is on the resolution path so it runs on both arms, which caps the exposure. |

      **NET: two clean, one published figure contradicted by its own artifact, one sim-arm, two
      undetermined.** The two that drove the biggest shipped decisions — the freeze census and the
      45.6% per-player stillness that redirected the idle wander — are both CLEAN, which is the
      most important result here.

      **RE-RUN 2026-09-09, three of the six.** Chosen by decision-relevance rather than by size
      of the discrepancy: could a corrected number still change what we DO next. All three ran
      `PLAYED=1`, 8 seeds, one game per process, `PYTHONHASHSEED=0`, detectors verified firing
      (`SELFTEST detector_ok=True` on both censuses), and with a null control — the `SILENT=1`
      arm produced byte-identical draw counts to the live arm, so the probes do not perturb the
      sim.

      | figure | published (SIM) | corrected (PLAYED) | changes a DECISION, or only the RECORD? |
      |---|---|---|---|
      | MISS re-keying | 15.9 s/game; ~79 visible player-steps over 4.8 s | **247.0 s/game; 782 visible player-steps over 39.8 s** | **DECISION.** MISS was ranked last of four as "one of the smallest remaining items". It is the largest remaining defect after defect 2 and is re-ranked 3rd. See item 19. |
      | item 23 lookup census | 619,038 lookups, 43 sites, **0 crossings** -> LATENT | 643,746 lookups, 42 sites, **0 crossings** -> still LATENT | **RECORD only, and the decision is CONFIRMED.** The decisive field is unchanged at zero on the real arm, so the choice not to sweep the 26 fabricating-fallback sites stands on played-arm evidence rather than sim-arm evidence. |
      | continuity classification | 63,995 player-steps, ONE_STEP_JOURNEY 42.9% | 164,640 player-steps; ONE_STEP_JOURNEY 12.4% of all, 24.8% of moving, 51.9% of journeys | **RECORD only.** The easing assigns curves from continuity at runtime; the measurement only described it, so a wrong description never produced wrong code. Corroborates the preserved `.arm/ease` artefact (158,338 / 12.8%) rather than the published figure. |

      NOT re-run, deliberately: the freeze census and the 45.6% stillness figure, both already
      shown CLEAN above; and item 24, which is fixed and outcome-neutral either way.

      **THE INSTRUMENT IS NOW HARDENED** (`scratch_playedarm.py`, 2026-09-09):
      - `use_played_arm` RAISES unless `PLAYED` is explicitly `1` or `0`, naming the fix in the
        message. Running the sim arm is still allowed but must be asked for (`PLAYED=0`, or
        `use_sim_arm`), never defaulted into. Poisoned: the raise fires on unset AND on a
        plausible typo (`PLAYED=yes`).
      - Every probe's `OUT` json is stamped with `played_arm`, recorded at the point the switch
        takes effect rather than inferred afterwards. It patches `json.dump` only, and only for
        the file named by `OUT`, so nothing else in the process is affected. The field is
        `played_arm` and not `arm` because `scratch_tails_miss.py` already uses `arm` for its own
        live/no-tweens contrast.
      - **ANY PRESERVED JSON WITH NO `played_arm` FIELD PREDATES THIS AND MUST BE READ AS ARM
        UNKNOWN — not as played.** Every artefact currently under `.arm/` except `.arm/rerun/`
        is in that category.

      A TRAP WORTH NAMING, hit during this very re-run: `SILENT=1` is the NULL CONTROL in
      `scratch_casecensus.py` and `scratch_continuity.py` — it makes the recorder return without
      recording. Passing it to reduce log noise produced a clean-looking run with an empty
      counter, which is exactly the "detector reported zero / detector never ran" ambiguity item
      29 was about. It was caught only because the output carried `keys: {}`. Probes should not
      overload a word that means "be quiet" onto a switch that means "measure nothing".

      DO NOT re-measure the remaining three without deciding first that they are worth it. Note when scoping that draw counts are NOT usable as a cross-era arm test:
      `HCO_PASS_SAFETY_BASE` 175 -> 150 (11bbaa16a) moved them, so a 2026-09-08 probe cannot be
      compared to a 2026-09-09 one by draws.

32. **item 19's loose-ball figure is RETRACTED — 82% of it was correct basketball.** Measured
      2026-09-09, played arm, `PLAYED=1` explicit, probe `scratch_overlay_channel.py`.

      **THE TRIGGER.** Jamie reports by eye on staging that post-shot motion looks CORRECT:
      shooter and shot defender hold at the shot spot, defenders box out or release, offenders
      get back or move to rebound position. item 19's re-run said 782 visible loose-ball
      player-steps/game over 39.8 s with 95.6% "indefensible". Both could not be true.

      **THE HYPOTHESIS UNDER TEST WAS THAT THE DETECTOR READ THE WRONG CHANNEL** — that post-shot
      movement rides the four overlay maps and a detector reading per-step start/end coords is
      blind to it. **THAT HYPOTHESIS IS FALSE, and it is worth saying plainly because it was the
      leading one.** Overlay motion is not a separate channel. It is baked into the same coords:
      `_apply_overlay_motion_to_shoot_step` writes the destination into the shoot step's
      `end.coords` and `start.destination` (`skeleton_step_emitter.py:2982-2984`), and
      `_build_ball_motion_sub_step`, which builds EVERY loose-ball sub-step (flight `:3730`,
      on-rim `:3796`, bounce `:3640`/`:3916`), advances overlay players at their archetype rate
      into `end_coords` (`:3042-3048`).

      RIGHT-CHANNEL PROOF (rule 6d), pointing the detector at players known to be overlay-moved:
      of **46,232 overlay-assigned player-steps the detector reports 24,455 (52.9%) as MOVING**,
      across all four maps (`offense_rebounder` 51.5%, `defense_rebounder` 53.9%,
      `offense_getback` 53.0%, `defense_release` 56.5%). Worked example: an
      `offense_rebounder_coords` player travelling 15.23 grid units in one step, action `cut`,
      detector says moves. The detector sees the channel.

      **THE REAL ERROR IS ONE LINE AWAY, AND IT IS A CLASSIFIER BUG, NOT A CHANNEL BUG.** At
      `skeleton_step_emitter.py:3034-3038`, once an overlay player REACHES his destination he is
      rewritten to action `stationary` with `destination = None` for every later step. In the
      fields item 19 read, a man who has just sprinted to his rebound spot and is now holding it
      is **indistinguishable from a man who was never given a job**. item 19 counted both as
      indefensible. That is also why its destination split read 56.9% "no destination" and 0.0%
      "elsewhere" — "no destination" was silently two populations.

      **RE-DERIVATION.** The probe reproduces item 19's population exactly — 781.5 player-steps
      per game against its 782, and 39.8 s/game against its 39.8 — so this is like-for-like and
      not a different measurement.

      | class of loose-ball still player-step | share | per game | verdict |
      |---|---|---|---|
      | arrived at his overlay spot and holding it | 45.1% | 352.2 | **correct basketball** |
      | no job, but 8-9 team-mates DID get one (the shooter and his defender) | 18.8% | 147.1 | **correct basketball**, and exactly what Jamie describes |
      | on a turn that assigned NOBODY an overlay | 27.2% | 212.4 | **genuine authoring gap** |
      | overlay-assigned but stopped short of the spot | 8.9% | 69.8 | genuine, smaller |

      **63.9% is defensible.** On the 84.4% of MISS turns that carry overlays, 8 or 9 of the 10
      players get a job (mean 7.29 of 10 overall), so the men standing are the shooter and the
      contesting defender — which is the correct read and the thing Jamie is looking at.

      **WHAT SURVIVES IS A DIFFERENT AND MUCH SMALLER DEFECT: 76 of 486 MISS turns (15.6%) author
      NO overlays at all**, and on those all ten men stand through the rebound. They are a
      distinct family, not a random subset: **81.6% of them carry no `shot_type` and no
      `shot_variant`** (against 0.0% of overlay-carrying turns), so they are MISS-labelled turns
      that never went through the shot pipeline that authors the overlays. In step wall time
      that family is **6.9 s/game of the 39.8**, with the other 32.9 s/game sitting on turns
      where players are visibly working.

      **WHY JAMIE CANNOT SEE THE RESIDUE, which was the question if the stillness turned out
      real:** he cannot see it because on 84.4% of misses it is not there. The defect lives in a
      15.6% minority of turns, so watching post-shot play and finding it correct is exactly what
      a correct observer should report. His eye was right and the measurement was wrong.

      **CONSEQUENCE FOR THE RANKING.** MISS was re-ranked 3rd this morning on 39.8 s/game. The
      defensible figure is **6.9 s/game**, which is below the `bounce` empty beat (17.1 s/game).
      MISS should drop to last on measured size, and "author rebound-crash and leak-out
      destinations for the whole family" is NOT the fix — the overlays already do that job on
      84.4% of turns. The remaining question is narrow: why does a MISS with no `shot_type`
      skip overlay authoring? That is a scoping question for a separate brief, and at 6.9 s/game
      it may not be worth one.

      NOT FIXED, NOT SCOPED. `rewarding_animation_fix.md` still carries the retracted 39.8 s/game
      at rank 3 and needs the same correction; it was left untouched because this brief made
      bugs.md the only writable file.

33. **THE STILLNESS DETECTOR DOES NOT TRACK WHAT A HUMAN SEES — it inverts.** Measured
      2026-09-09, played arm, `PLAYED=1`, probe `scratch_calibrate_holds.py`, 8 games.
      This is the first time anything in this workstream has been calibrated against an observer.

      Jamie's eye gives ground truth on two families that point OPPOSITE ways: MISS/post-shot
      looks CORRECT, FCP/HCT attack steps look like "handler and his defender animate, the other
      eight freeze". Running the SAME detector item 19 used against both:

      | family | Jamie | movers/10 (binary) | movers/10 (>=1 ft) | ft/sec on screen |
      |---|---|---|---|---|
      | MISS post-shot | **looks CORRECT** | **3.75** | **3.47** | 11.68 |
      | FCP | looks FROZEN | 4.82 | 4.30 | 13.55 |
      | HCT | looks FROZEN | 6.00 | 5.82 | 21.16 |
      | FAST_BREAK | looks FROZEN | 7.24 | 6.83 | 28.02 |

      **The family the human calls CORRECT scores as the MOST frozen on every formulation, and
      the families he calls FROZEN score as the LEAST.** Three separate reconciliations were
      tried and all three failed: the binary predicate, displacement magnitude (to test whether
      sub-perceptible movement was being counted as motion — `_idle_is_still` uses a 1e-6
      threshold at `animation_step_helpers.py:110`, so an eighth of an inch counts as MOVING),
      and on-screen speed. The ordering is stable and inverted in all three.

      **CONSEQUENCE: "still player-steps" is not a valid proxy for perceived frozenness.** Every
      ranking in this workstream built on it — item 19's, and the sizing behind defect 4 —
      measures something real but not the thing the complaint is about. This does NOT mean the
      counts were wrong; it means they do not predict what a viewer notices. A replacement
      instrument has to be found before any further stillness work is ranked, and the honest
      position until then is that we cannot currently size a "looks frozen" complaint.

      NOT YET EXPLAINED, and deliberately not guessed at: what Jamie IS reacting to on FCP/HCT.
      Three hypotheses are dead; a fourth should be sought with him at the screen rather than
      derived here.

34. **The universal BIP pause is NOT an audio hold and NOT a hold mechanism at all.** Same probe.

      **BIP and SIP steps carry ZERO `wall_clock_hold_ms` and ZERO announcements.** The pause is
      ordinary game-time step duration on steps where all ten players are authored still:
      BASELINE_INBOUND has **28.3% of its steps fully frozen at a 0.45 s mean**, SIDE_INBOUND
      **66.7% fully frozen at 0.60 s**. Jamie is right that it is a DURATION complaint and right
      that the idle wander cannot fix it — the fix is step duration or step deletion.

      **COMPLETE CENSUS OF EVERY MECHANISM THAT HOLDS THE WHOLE COURT** (the brief asked for all
      of them). Exactly three distinct values exist, 60 holds/game, **20.9 s/game total**:

      | ms | per game | source | load-bearing? |
      |---|---|---|---|
      | 300 | 51.9 (43.4 HCO, 5.4 OREB, 2.0 FAST_BREAK, rest) | `make_hold`, `skeleton_step_emitter.py:3210` (`MAKE_HOLD_MS` = `ANNOUNCEMENT_FREEZE_HOLD_MS`) | YES — it is the only thing giving the non-blocking "It's Good!" overlay screen time, deliberately moved off the announcement's own `hold_ms` (see `animation_cleanup_findings.md:268`) |
      | 660 | 6.4 | fumble, `dead_ball_fumble.py:164` (`FUMBLE_WALL_CLOCK_MS`) | YES — the stumble beat is the animation |
      | 640 | 1.8 | shot micro-movements, `shot_micro_movements.py:1464` | YES — carries the micro-movement |

      **NO HOLD IN THE GAME IS PROTECTING AUDIO FROM BEING CUT OFF.** The blocking-announcement
      path (`animationPlayback.js:920-943` pauses both clocks, awaits `hold_ms`, resumes) exists
      but is **never armed**: all 1,411 announcements across 8 games are non-blocking, because
      the FE blocks only on `announcement.blocking === true` (`:940-942`) and nothing sets it.
      So the "hold for the callout" model is not what is happening anywhere.

35. **FCP/HCT "the other eight freeze" — REFUTED as stated, but the authoring does park them.**
      Same probe, 8 games, played arm.

      - **There are no distinct "attack step types."** 98% of FCP/HCT steps carry
        `advance_trigger.metadata.kind` = `<none>`; the family is one undifferentiated kind, so
        the report cannot be narrowed to a step type. FCP 61.1 steps/game, HCT 53.2/game.
      - **Movers are 4.84 of 10 (FCP) and 6.01 of 10 (HCT), not 2.** So "handler and defender
        only" is wrong by a factor of two to three. Directionally he is right that roughly half
        the court holds; the count is not eight.
      - **The still ones are PARKED BY AUTHORING, not left undefined.** Of still player-steps,
        **93.0% (FCP) and 88.9% (HCT) are authored a destination they ALREADY OCCUPY**; only
        7.0%/11.1% have no destination at all. The engine is explicitly saying "stand here",
        which is the same shape as the MISS finding in item 32.
      - **Trailing players DO get authored advance, contradicting the third sub-question.**
        Behind-the-ball players move on **65.0% (FCP) / 60.4% (HCT)** of their player-steps, mean
        **4.80 / 4.69 feet toward the attacking basket**. They are not authored static.

      SCOPE NOTE FOR THE EVENTUAL FIX, recorded now so it is not lost: the remedy Jamie wants —
      trailing players drifting basketward — MUST be backend-authored destinations, not a
      render-side drift, because the coords have to carry into the next step. That moves player
      coords, which feeds `resolve_over_the_back_foul` and the putback contest, so it is
      OUTCOME-CHANGING and requires the poison-stash and an equiv-v3 arm. It is NOT the retired
      CONTINUE_FROM_PREVIOUS mechanism. Given item 33, it should also not be scoped on any
      stillness count until there is an instrument that predicts perception.

##Player Images
1. AI player portrait production (confs 2–16) — see [`player_image_generator.md`](player_image_generator.md)

## Stale FB test suite — open follow-up [CODE-CLEANUP]

Stale pre-refactor FB tests were deleted 6-12-26; suite is green. **Still open:** current-engine FB coverage is thin — `test_fast_break_rr_triangle_updates.py` covers RR/Triangle emitters, but the CR resolver path and `after_steal_fast_break.py` (resolver + emitter) have little/no direct test coverage. Write new tests against the current resolvers when FB work resumes.

## Resolved — stale Final Turn test import (found 2026-08-04, fixed 2026-08-11)

`test_final_turn_entry_pass_chain.py` was repointed from the retired
`_append_final_turn_entry_pass_if_needed` helper to the current
`_prepend_final_turn_handoff_if_needed` path. Its monotonic/no-self-loop contract remains
covered. The separate `roll_anchor_clock` debt was resolved earlier.

## P0 — HCO contract clock overruns (carried from Unified_Animation_System.md, 6-12-26) [CODE-CLEANUP]

Two critical issues from the animation blueprint's "Known HCO Turn Issues" list (`projects/Unified_Animation_System.md`):

1. **HCO resolution hard overrun:** observed throw `"[HCO resolution contract] clock overrun ... elapsedGameSeconds=649.00"` on a `DEAD BALL` path. **Partial mitigation (Option A):** turn-boundary guards in `turnAnimation.js` use contract-capped elapsed (`min(wall_elapsed_ms, real_time_elapsed_ms + guard_slack_ms)`). Throws still exist; needs live validation before closing.
2. **HCO step-pass hard overrun in BATCH/DEAD BALL sub-turns:** observed throw `"[HCO step pass contract] clock overrun ... elapsedGameSeconds=405.78"` at `step=6`. **Still uncapped** — step-pass guard uses raw `Date.now() - stepStartMs` (no Option A). Track separately from #1.

## Animation timing pauses

**Meta:** With dynamic HCO on, Motion/Set-Play render via backend `animation_steps[]` (`animationPlayback.js`). Pause durations are stamped in Python (`time_elapsed`, `hold_ms`); FE-only fixes miss the source. Design work applies only to optional idle-sprite drift (Bucket 1 secondary).

### Open — Bucket 1: Long pauses between HCO steps (Motion only)
- **Symptom:** All ten players frozen 700–1400ms on many Motion steps; Set Play unaffected.
- **Root cause:** Motion "subtle-movement" beats floor at **2–4 game-seconds** (`SUBTLE_STEP_ELAPSED_BY_TEMPO` in `motion_step_decision.py`; stamped via `skeleton_step_emitter.py`). Schema engine hard-waits full `time_elapsed` (`animationPlayback.js`). Set Play forces `offense_reads=False` → fewer subtle beats.
- **Fix:** Decouple sim clock from visual time — keep 2–4s on game ledger, stamp small visual `time_elapsed`. Optional: off-ball drift during BH hold so 9 players don't read as frozen.
- **Secondary:** Confirm BH hold doesn't block the other 9 from moving; consider idle organic sprite animation on truly stationary steps.

## Fast Break animation backlog (legacy path) [CODE-CLEANUP]

Tracked from archived [`Z-Completed/Fast_Break_Refactor.md`](Z-Completed/Fast_Break_Refactor.md). **UESS schema path is primary** for `covert_release`, `rim_runner`, `triangle`, `after_steal` when `animation_steps` exist; legacy `runFastBreakSequence` remains the fallback when steps are missing / variant unmigrated.

- Advance triggers unreliable on legacy `fastBreak.js` / `runFastBreakSequence` (phase boundaries hang or short-circuit).
- FB visual timing still uses FE `getPlayerDuration` on legacy path; backend does not stamp per-player `game_seconds` in legacy `animator.capture_fast_break_animation` payload.
- Charge/blocking foul on FB: stop animation immediately (don't wait for defensive spot) — see Bugs §14.
- Full phase map and backend sites: archived refactor doc.

---

## Future Cleanup (Non-Critical Warnings)

### Sunset mode code removal (Single Game + Tournament) — surfaced during doc sweep 6-13-26 [CODE-CLEANUP]
- **Issue**: Single Game and Tournament modes are sunset (not user-facing), but their code paths still exist throughout the backend/frontend (e.g. `init_game()` mode branches for `single`/`tournament` in `BackEnd/api/api.py`, tournament master-copy seeding, single-game empty-playbook init, plus tournament/single routes and frontend pages).
- **Decision (prior)**: When tournaments / single games are reintroduced, build fresh from current architecture rather than reviving these early-build paths (lots of legacy bloat). So this code is removable, not preserve-for-reuse.
- **Action**: Future cleanup — remove sunset `single`/`tournament` code paths once the team commits to the rebuild-from-scratch plan. Docs that describe these paths are tagged "SUNSET MODE" (e.g. `Game_Init_System.md` Tournament / Single sections; `Lineup_Selection_Screen.md`) and point here.
- **Priority**: Low (dead-end paths; not causing bugs, just bloat/confusion). Do as a deliberate sweep, not piecemeal.

### Steal → HCO setup: backend computes positioning that the frontend no longer renders (found 6-13-26 during doc sweep) [CODE-CLEANUP]
- **Issue**: `resolve_half_court_offense_logic` (`BackEnd/engine/phase_resolution.py`) still emits `is_steal_hco_setup`, `ball_handler_hco_setup_*`, and `other_players_hco_setup_movements`. The frontend has removed `animateStealHCOSetup()` and stopped reading those fields. UESS has a replacement (`_append_post_steal_hco_transition` in `skeleton_step_emitter.py`), but the old role-field contract is unused.
- **Impact**: Low — backend is doing compute-but-unrendered work. No visible bug, just wasted computation and a misleading contract.
- **Action**: Remove the Steal → HCO setup positioning computation and its emitted fields from the backend resolver. Confirm no other consumer reads those fields first.
- **Priority**: Low (dead/unrendered compute, not causing bugs)

### Legacy steal-entry Fast Break dead code + unused `STEAL_ENTRY_*` constants (found 6-13-26 during doc sweep) [CODE-CLEANUP]
- **Issue**: All steals are short-circuited to the UESS-migrated `after_steal` resolver early in `resolve_fast_break_logic` (~L1205), which makes the legacy steal-entry movement block later in the same function (~L1517–1541) unreachable dead code. The `STEAL_ENTRY_MOVE_*` / `STEAL_ENTRY_Y_*` constants that block relied on are now unused on the rendered path in both `BackEnd/constants/fast_break_constants.py` and `FrontEnd/static/js/phaser/constants/fastBreakConstants.js`.
- **Impact**: Low — unreachable code + orphaned constants. No runtime effect, just bloat/confusion for anyone reading the FB resolver.
- **Action**: Delete the unreachable steal-entry block in `resolve_fast_break_logic` and remove the unused `STEAL_ENTRY_*` constants from both the backend and frontend constants files. Verify nothing on the live `after_steal` path references those constants before removing.
- **Priority**: Low (dead code; tie in with the FB-coverage follow-up noted in the "Stale FB test suite" item above)

### State Telemetry Violations (Phase 1.3) [CODE-CLEANUP]
- **Issue**: `game_id` is being read/written to `gameStore` when it should come from URL according to State & Persistence Contract
- **Location**: `FrontEnd/static/js/state/gameStore.js` (`setGameId` / `getGameId` + telemetry)
- **Impact**: Low - telemetry is working as intended, detecting contract violations
- **Action**: Future cleanup - refactor to use URL as source of truth for `game_id` instead of `gameStore`
- **Priority**: Low (informational only, not causing bugs)

### Invalid State Transition Warning [CODE-CLEANUP]
- **Issue**: State machine attempts no-op transition (HalfCourt -> HalfCourt)
- **Location**: `FrontEnd/static/js/phaser/animation/AnimationEngine.js` → `handleBaselineInbound()` still calls `safeTransition` unconditionally (tip path has an `is(HalfCourt)` guard; BIP does not)
- **Impact**: Low - harmless but indicates unnecessary `safeTransition()` call
- **Action**: Review `handleBaselineInbound()` to avoid calling `safeTransition()` when already in target state
- **Priority**: Low (code cleanup)

---

## Open Investigations

### `offensive_state` and `free_throws_remaining` are absent from the cache-refresh restore (found 2026-09-06)

`game_state` is restored KEY BY KEY on the API path, so a key with no line in a restore
function silently reverts to its `_init_game_state` default. This is the same class of hole
that lost `frontcourt_established` before Phase 1B added it to these sites.

**Missing from:**
- `api.py:1652-1690` `refresh_game_cache_from_db` — restores `timeout_*`, `clock`,
  `time_remaining`, `shot_clock_remaining`, `frontcourt_established`,
  `frontcourt_ratcheted`, `score`, team fouls and timeouts. Neither FT key appears.
- `api.py:5757-5768` deferred-computer-timeout clock restore — same omission.

**Present in:** `api.py:1776-1778` (timeout resume) sets both, from
`timeout_free_throws_remaining`.

**Defaults it would revert to:** `offensive_state: "HCO"` (`game_manager.py:235`) and
`free_throws_remaining: 0` (`:250`) — i.e. a pending free-throw trip becomes no trip at all.

**TWO QUALIFICATIONS — do not overstate this.** It is logged as structural, not observed.
1. **It is conditional, not per-turn.** `refresh_game_cache_from_db` overwrites a LIVE cached
   GameManager key by key; it does not rebuild from defaults. Leaving `offensive_state` alone
   therefore preserves the correct in-memory value, which is harmless. The loss requires the
   GameManager to be reconstructed from defaults (cache miss / eviction) while a trip is
   pending. Nobody has yet observed that sequence.
2. **It is NOT the cause of any measured free-throw anomaly.** The 2026-09-06 "free throws
   collapse when animation runs" result was a HARNESS ARTIFACT (see the retraction below) and
   never touched this seam: nothing replaces `gm.game_state` anywhere except
   `GameManager.__init__`, so `simulate_quarter` — which both probes used — never crosses a
   restore seam at all.

Not fixed here; found while investigating something else. The durable fix is the one Phase 1B
argued for: stop restoring key by key, or gate the restore sites with a test that fails when a
possession-scoped key has no line.

### ⚠️ RETRACTED: "free throws collapse when animation runs" — harness artifact (2026-09-06)

Recorded because it burned real measurement time twice, independently, and the trap is reusable.

**The claim (WRONG):** with animation enabled, ~66% of awarded free-throw trips were never
taken; shooting-foul awards specifically went to zero while non-shooting bonus awards survived.

**The actual cause:** both probes built their "played" arm by assigning a `dict` subclass over
`gm.game_state` AFTER construction. `game_manager.py:78-79` constructs `TurnManager(self)` and
`ShotManager(self)` during `__init__`, and `shot_manager.py:286` does
`self.game_state = game.game_state` — capturing the dict BY REFERENCE at that moment.
`ShotManager` is the only object holding a construction-time reference; every other site takes
`game.game_state` fresh inside a function. So the swap orphaned ShotManager on the pre-swap
dict. Shooting fouls resolve inside ShotManager, so their awards were written to the orphan and
were invisible to the dispatcher reading `gm.game_state`. Non-shooting fouls resolve in
`phase_resolution`, which re-reads `game.game_state`, so they were honoured — which is exactly
the "shooting vs non-shooting" split that looked like a real mechanism.

**Reproduction:** swap the dict, then `gm.shot_manager.game_state["offensive_state"] =
"FREE_THROW"`; `gm.game_state.get("offensive_state")` still returns `"HCO"`.

**Tell that would have caught it immediately:** the arm that did NOT swap honoured ~97% of
awards; EVERY arm that swapped landed at 23-36%, including an arm that blocked no flags at all.
The confound tracked the swap, not the variable under test.

**Fixes adopted:**
- Never replace `gm.game_state`. To vary `_is_full_simulation` per call site, flip it IN PLACE
  on the live dict for the duration of the call and restore after (depth-counted, since the
  gated Animator methods nest). Measured leakage of that technique: 402 reads inside the flip
  window, all from `BackEnd.models.animator`, ZERO from anywhere else.
- Any harness that splits arms must report FT-awards-honoured for both arms alongside every
  result, and refuse to print a comparison when the arms disagree on it. Count the award as
  honoured if the free throw lands within a few turns, not strictly the next turn — a TIMEOUT
  legitimately interposes, which is the entire reason a healthy arm scores ~97% and not 100%.

**Scope of the retraction:** every `equiv-v1` figure is void, including the sim-vs-played
divergence table (turns -10.5%, points -24.7%, BLOCK +77.2%, FREE_THROW -66.6%). The sim arm
was never swapped and so was never confounded; only the played arm was. The
`defender_placement` extraction commit is unaffected — its acceptance was before/after identity
under one fixed harness plus two harness-independent proofs (byte-identical test baseline, and
7 of 9 moved bodies AST-identical to their originals).

### `_hco_render_animations` — a mechanism justified by a false premise (measured 2026-09-06)

The stash exists to reconcile a disagreement that is ~zero, and does not address the
disagreement that is real. Written at `skeleton_step_emitter.py:1617`, read at
`step_state.py:49`, and slated for deletion by the defender-placement extraction — this entry
records that it likely deletes on its own merits regardless of what happens to that project.

**The stated justification**, in both comments verbatim: "Defender placement uses RNG (a ~2px
shade), so a *separate* draw would not match; sharing this one draw makes contest == render by
construction." `step_state.py:47` repeats it, and `_diagnose` at `:202-206` calls a fresh redraw
"exactly the disagreement Option A eliminates".

**Measured, and it is not ~2px — it is zero.** `sim_rng` is a stdlib `Random`, so the probe
snapshots its state, re-runs the producer on the identical skeleton with the state restored,
runs it once more WITHOUT restoring, then restores the post-call state so the game's own stream
is untouched:
- same skeleton + same RNG state -> bit-identical grid, **603/603** samples.
- same skeleton, genuine second draw -> **median 0.000, p95 0.000, mean 0.042 grid** across
  **16,880** defender comparisons. The court is 100 grid wide.

**The real disagreement is INPUT-driven.** Comparing the contest's grid against the render's
grid defender-by-defender at the same step, split by whether that step's offensive content was
identical (n=16 seeded games, 1,791 HCO turns):
- identical content: n=63,365, mean 0.075 grid, **93.0% exact match**
- differing content: n=2,230, mean **10.074** grid, median 4.250, p95 **36.497**, max **88.02**

3.4% of pairs carry ~83% of all disagreement. The cause is that `_stamp_contest_defender_grid`
runs ~4.04x per turn against a skeleton that is not final — its own docstring concedes "may
carry recalibrated/expanded steps the pre-walk stamp didn't cover" — so only 75.3% of turns are
byte-identical on step count and content, and ~46 steps per game are drawn having never been
placed against at all. Sharing one draw cannot fix a mismatch of inputs.

**And within the turn it feeds no contest.** Instrumented, not read off the source: of the four
functions that read `step["_step_state"]["defense"]` (`phase_resolution.py:4460`, `:4977`,
`:5862`, `:6334`), **0 of 5,834** played-arm reads occur after `build_step_states` overwrites
`_step_state`; and `build_step_states`' return value is **never touched** — 0 accesses across
883 calls, measured with a list subclass that logs every access to itself.

**Still open:** cross-turn influence is NOT excluded. `step_state.py` warns "a later turn could
still read a prior turn's stamp". The poison test that would settle it is void — see the
arm-independence entry below.

**Separate and larger, do not conflate:** the shot contest reads a DIFFERENT source in each arm.
`_freeze_hco_shot_attempt_geometry` (`phase_resolution.py:4421`) labels its own provenance, and
that label splits 100/0 by arm — sim is 100% `hco-stepstate-shot-step` (the stamped grid, 344
samples), played is 100% `hco-emitter-shot-step` (live `Player.coords` synced by the emitter,
375 samples). That is the placement-source divergence the free-throw chain actually rides on,
and it is neither the stash nor `compute_defender_grid`-vs-render.

### ⚠️ MEASUREMENT: two arms run sequentially in ONE process are NOT independent (2026-09-06)

**Symptom:** run the identical arm three times in one process, changing nothing — three
different games. Fingerprints all differ, and `sim_rng` draw counts come out
**137,106 / 136,832 / 134,387** (2 games per arm, seeds 8000-8001, `PYTHONHASHSEED=0`, all
three RNGs re-seeded per game).

**Carrier:** player/team state persists in the mongomock DB across games and therefore across
arms. Visible directly in the log — `Computer-team lineup exhaustion: Team 'Lancaster' randomly
re-admitted 5 fouled-out player(s)`. Re-seeding the RNGs does not reset the DB.

**How it surfaced:** a poisoned arm produced outcome fingerprints that tracked its POSITION in
the process rather than its intervention. Two entirely different poison mechanisms, each run as
the third arm, produced byte-identical games (seed 8000 -> `fadb4132258776c3`, 517 turns); the
same mechanism run as the fourth arm produced a different game (`c3fb1ed17fbf7d3b`, 451 turns).
An intervention whose effect depends on when you run it is not measuring the intervention.

**Contaminated, must be re-measured one arm per process:** the `equiv-v2` sim-vs-played
divergence table (turns +12.1%, points +4.9%, FREE_THROW +41.2%, BLOCK +51.8% et al) and the
free-throw three-term decomposition (shots +13.7% x contested share +13.4% x foul-rate +8.9%).
The decompositions remain internally exact within each arm's own data; it is the arm-to-arm
ratios that are not reportable. Direction may well survive — the measured gaps are larger than
the ~2% contamination band — but that has to be shown, not assumed.

**NOT contaminated:** anything measured within a single arm, because the comparison is
within-turn or per-call. That covers the contest-vs-render grid comparison and RNG noise floor
above, and the `build_all_animations` mutation probe (1,165 calls, zero mutations). Structural
facts also survive, being immune to which game got played: 0 reads after the overwrite, the
return value never being touched, and the 100/0 shot-contest source split.

**Fix for future harnesses:** one arm per process, or re-seed the database between arms and
prove it with an identical-arm-twice control before trusting any comparison.

### "Play Quarter" Button Requires Two Clicks (Initialization Timing Bug)
- **Issue**: On first page load, users must click "Play Quarter" twice to start the game. First click does nothing, second click works. When returning to the page (e.g., after navigating away and back), first click works correctly.
- **Location**: `FrontEnd/static/js/phaser/bootGame.js` - `initGame()` function
- **Root Cause**:
  - The "Play Quarter" button is visible and clickable immediately when the page loads (`court.html`)
  - `bootGame.js` runs asynchronously and attaches the click event listener late in `initGame()`
  - If user clicks before `initGame()` finishes attaching the handler, the click does nothing
- **Fix Required**:
  1. Disable button initially, enable after `initGame()` completes
  2. OR attach handlers before showing button
  3. OR show loading state until initialization is complete
- **Priority**: Medium (affects user experience and test reliability)

### Live Court Sidebar Shows All 12 Players Instead of Active 5 (July 2026)

- **Symptom:** During live `court.html` gameplay, both player box-score sidebars listed the full 12-man roster per team instead of the five active players. Court sprites still showed 5 per side. Observed after a **computer timeout** (no lineup changes); corrected after a later **user timeout + lineup change** return to court.
- **Fingerprint:** Bad rows used bare full names (`Yadiel Terra`), not Phaser’s `#jersey LastName` format — so the writer was not `gameScene.js` `initTeamTable`.
- **Clear cause (code-backed):**
  1. Backend `GameManager.get_box_score()` intentionally returns lineup **+** bench (~12).
  2. Phaser sidebar correctly builds only `PG/SG/SF/PF/C`.
  3. `displayAccumulatedPlayerStats()` in `FrontEnd/static/js/phaser/utils/loadGameStats.js` clears each tbody and dumps `Object.values(boxScore[teamName])` with **no** active-five filter; names are raw `playerStats.name`.
  4. That runs from `initializeGameStats()` on court load when game data resolves.
  5. Lookup is by URL team **names** (`?home=` / `?away=`). `/api/game/{id}/resume-state` aliases the full box under those names (dump succeeds → 12 rows). `/api/game/{id}` keys by **team_id** (name lookup usually fails → function no-ops → Phaser’s 5 rows remain).
- **Why “fixed” after user timeout + lineup change:** set-lineup Return forces `resume_from_timeout=true` → resume-state probe skipped → `/api/game` path → name lookup fails → dump does not run; Phaser remount rebuilds 5.
- **Not proven without URL/network capture:** exact entry params on the bad computer-timeout return (e.g. whether resume-state was probed because `resume_from_timeout` was missing/false). Mechanism that produces 12 rows is clear; that one trigger instance is the remaining link.
- **Likely fix (when authorized):** filter to `PG`–`C` (or current lineup IDs) in `displayAccumulatedPlayerStats`, and/or resolve box score by `team_id` consistently.

### DEFERRED: M0 throwaway DB for DB-dependent tests — restore runbook (August 2026)

Deferred, not cancelled. Needed when identity wiring starts and DB-dependent tests matter.
Context: `tests/conftest.py` block-lists `gob` and `gob-staging`, so the 217 DB-touching tests
(45 files, 42 of which contain `delete_many({})`) cannot run without a throwaway.

- **Size constraint:** staging is **498.84 MB storage against the 512 MB M0 cap**. A full clone
  does not fit. **Restore a subset**, not everything — `plays`, `teams`, `defenses`, and a small
  slice of `players` cover most fixture needs; skip `games`, `franchise_players_data`,
  `franchise_team_data` and the `players_backup_*` collections, which are the bulk.
- **Namespace rename is required** (source db `gob-staging` → target `gob-test`):
  ```
  mongodump   --uri "<staging-uri>" --db gob-staging \
              --collection plays --collection teams --collection defenses \
              --out /tmp/gobdump
  mongorestore --uri "<m0-uri>" \
              --nsFrom 'gob-staging.*' --nsTo 'gob-test.*' \
              /tmp/gobdump
  ```
  Without `--nsFrom/--nsTo` the restore recreates the database under its original name, which
  the conftest guard then blocks — the rename is what makes the throwaway usable.
- **Then:** point `.env.local` at the M0 with db name `gob-test` (any name not in
  `_BLOCKED_DB_NAMES`) and the guard passes legitimately rather than being worked around.
- **Prefer a separate M0 cluster over a `gob-test` database on the production cluster** — the guard
  block-lists by database *name*, so a same-cluster scratch db is one connection-string typo away
  from the real thing.

### Test suite cannot run end to end — four independent causes (August 2026)

**Impact:** nobody can complete a full run, which is why **19 deterministic failures accumulated
invisibly** in the motion/shot area alone. This blocks regression coverage for the CPU identity
wiring and rotation work that comes next. It is a workstream, not a pre-commit step.

**1. Resolved 2026-08-11 — stale imports no longer block collection.** Final Turn
coverage now targets the current handoff helper, and shared-defense symmetry coverage now
targets the unified `get_defender_coords` API instead of the two deliberately retired
assignment helpers. Full local collection reaches 2,337 tests with the image-mask test
excluded only because the local virtualenv predates the already-declared NumPy/SciPy
requirements; hosted CI installs both from `requirements.txt`.

**2. Ten tests vary run to run, from TWO independent sources.** Measured over 5 identical runs per
arm: **22, 23, 23, 23, 20** vs **26, 21, 23, 22, 22** — same code both times. Flaky:
`test_motion_moment.py` (6), `test_motion_dynamic_resolver.py` (3), `test_motion_pass_lane.py` (1).
  - `BackEnd/utils/sim_random.sim_rng` seeds from OS entropy when unseeded (by design). Tests that
    exercise the walk without seeding get a different stream each run.
  - The **stdlib** `random` module is used directly in `BackEnd/api/gameplan_routes.py`
    (`populate_team_plays`, `populate_scouting_data`) — those draws are NOT on the isolated sim
    stream, so seeding `sim_rng` alone is insufficient.
  - A third factor, `PYTHONHASHSEED`, is filed separately below — it is not only a test problem.

**3. At least one test hangs forever.** `tests/test_defensive_pressure_all_scenarios.py` stalls
after 2 failures and produces no further output — observed 37 minutes with zero progress, at 19%
of the run. Confirmed **pre-existing** (HEAD hangs at the identical point, not caused by the
focus-emphasis change). `pytest-timeout` is **not installed**, so a hang is a wall rather than a
reported failure.
  - ⚠️ **The hang inventory is UNKNOWN.** We only know of this one because we never got past it.
    There may be more beyond 19%.

**4. `pytest.ini` sets `addopts = --maxfail=2`,** so a default invocation aborts after the second
failure — which, given 19 deterministic failures, means a default run shows almost nothing. Needs
`--maxfail=999 --continue-on-collection-errors` to see the real picture.

**Suggested order (when authorized):** install `pytest-timeout` and run with `--timeout=60
--timeout-method=thread` to convert hangs into failures and produce the hang inventory in one pass;
then fix the 3 imports; then seed both RNG streams via an autouse conftest fixture; then revisit
`--maxfail`. Only after that is the 19-failure backlog worth triaging.

### `PYTHONHASHSEED` reaches simulation behaviour — game results depend on an unrecorded value (August 2026)

- **Finding:** with `sim_rng` AND the stdlib `random` both explicitly seeded per quarter, repeated
  runs of the same sim still produced different results — until `PYTHONHASHSEED=0` was set, after
  which two runs were **bit-identical** (results and RNG draw counts alike).
- **Implication:** something on the sim path iterates a `set` or `dict` of strings in an order that
  reaches behaviour. Python randomises string hashing per process by default, so **live game results
  depend on a per-process value that nobody sets, controls, or records.**
- **Why this is not just a test problem:** it means a production game is not reproducible even given
  the same seed, and any seeded investigation is only valid within a single process. It undermines
  SS&S reproducibility guarantees generally.
- **Same class as the pymongo global-stream finding** documented in `BackEnd/utils/sim_random.py`:
  an invisible external input perturbing the simulation. That one was fixed by isolating the RNG;
  this one is still open.
- **Likely fix (when authorized):** find the offending iteration (candidates: any `set` of position
  or player-id strings feeding ordered logic, `_step_locations`, read-map construction, defender
  grids) and impose a deterministic order — `sorted()` at the point of use. Pinning
  `PYTHONHASHSEED` in the runtime would mask it, not fix it, and would not help anyone reading a
  historical game.

#### PARTIAL FIX + method to finish it (August 2026)

**12 genuine hash-order dependencies found and fixed.** Each was a raw `set` iteration whose
order reached RNG draw ORDER, so every subsequent draw in the game shifted:

| file | what |
|---|---|
| `engine/attack_drive_clearance.py:1012` | `for off_pos in perimeter_moved` — set from `_apply_perimeter_relocations`; loop consumes `player_read` + `get_defender_coords` draws per element. **The primary site.** |
| `models/animator.py:1294` | `for position in all_positions` — set; sets `offensive_animations` insertion order, which flows into zone overlap resolution |
| `engine/dynamic_hct.py:1162` | `backcourt` was a set literal → now a tuple |
| `engine/dynamic_hct_step_emitter.py:273`, `utils/shared.py:2543`, `utils/transition_bridge.py:312`, `utils/stat_updater.py` ×4, `utils/playbook_weights_utils.py:245`, `models/training_execution_v2.py:268` | raw set iteration, now `sorted(..., key=str)` |

**Causally confirmed**: the first divergence between hash worlds moved 9,051 → 23,677 →
31,023 draws as sites were fixed, and `PYTHONHASHSEED` 0 and 7 now produce **identical** games
(they did not before).

**STILL NOT FIXED.** Seeds 1 and 2 still diverge. On the identity-ON arm, 96 team-games, the
between-seed spread is **points/tg 69.22–70.58 and FCP foul-outs/tg 1.04–1.35** — comparable
to the effects being measured. **The instrument is still not trustworthy for effects of this
size.** Until it is, pin `PYTHONHASHSEED` for every arm of every comparison.

**Next site**: the OREB rebounder selection. Trace shows identical RNG state through draw
31,022, then `mo_shot_roll` takes a different branch (`player_momentum.py:54` vs `:57`) via
`shot_manager.calculate_shot_score` ← `shared.resolve_offensive_rebound` ← 
`turn_manager.resolve_offensive_rebound_turn:5252`. Same draws, different rebounder — so the
selection is order-dependent, most likely a `max()`/`min()` tie broken by iteration order
rather than a raw set iteration (the static scan for those is now clean).

**Method to continue** (`scratchpad/hashfind.py` + `nextdiv.sh`): wrap every `sim_rng` method
to record the caller's `file:line` per draw; run one game under two hash seeds; diff the
call-site sequences to find the first differing draw index; re-run with deep stacks in a
±2 window around it. That names the function in two passes.

#### RESOLUTION: pinned structurally, remaining hunt PARKED (August 2026)

**Decision: stop chasing sites; fix the failure mode instead.** Twelve fixes with causal
confirmation did not shrink the between-seed spread, and the static scan for raw set iteration
is now clean while divergence persists — so the remaining sites are subtler and possibly
numerous. Pinning, meanwhile, works perfectly. Every false conclusion came from an UNPINNED
run, so the defect to fix is **"requires remembering."**

| where | how |
|---|---|
| measurement harnesses | `BackEnd/utils/repro.pin_hash_seed()` as the first statement. `PYTHONHASHSEED` is read at interpreter startup, so it cannot be set from inside a running process — the helper **re-executes** the interpreter with it set. A harness that cannot be run unpinned cannot produce another false result. |
| production | `export PYTHONHASHSEED=0` in `start.sh`. Does not help with games already played, but from now on a reported game can be replayed. |

An explicit `PYTHONHASHSEED` in the environment is **respected, not overridden** — deliberately
varying it is how you measure between-world spread. Only the unset (and `"random"`) case is
pinned. If the re-exec fails to take, `pin_hash_seed` **raises** rather than continuing
unpinned.

`repro.py` is loaded BY PATH in the harness preamble, not imported as `BackEnd.utils.repro`,
because `BackEnd/utils/__init__.py` pulls in `stat_updater -> db` and the re-exec would
otherwise open a Mongo connection twice. Pinned harnesses: `perf_sim_baseline.py`,
`eog_measurement_season.py`, `simulate_100_quarters.py`, `s11_framework_baseline_measure.py`,
`eog_db_sweep.py`.

**When to un-park:** only if something specifically needs true hash-independence — e.g. running
measurement arms across multiple workers/processes where a shared pin is not achievable, or a
production incident that turns out to depend on hash order rather than seed. The next site and
the two-pass tracing method are recorded above and remain valid.

### Production games are NOT replayable — the per-game seed is never created or persisted (August 2026)

**TICKET, not fixed.** Pinning `PYTHONHASHSEED` (done, `start.sh`) makes hash ORDER
deterministic. It is **necessary but not sufficient**. A user reporting a strange game still
cannot have it reproduced, and it would be easy to believe otherwise.

**Why.** `cpu_week_pool` derives `seed = None if seed_base is None else seed_base + idx`
(`utils/cpu_week_pool.py:85`, `:127`), and **production passes `seed_base=None`**. In
`_run_franchise_cpu_full_simulation_core` (`api/franchise_routes.py:5205`) the seeding call is
guarded by `if seed is not None:` — so in production `sim_rng` is **never seeded**. It
self-seeds once from OS entropy at import and then runs as one continuous stream across every
game in the process.

So there is no per-game seed to record. The fix is not "log the seed we used" — it is
**generate one per game, seed with it, then persist it.**

**What the fix needs:**

1. Generate a per-game seed in the production path (e.g. `secrets.randbits(63)`), pass it
   where `seed_base + idx` goes today, so each game seeds independently of how many ran before
   it. This also removes the current cross-game coupling inside a worker process.
2. Persist it on the game document alongside the other provenance fields — `sim_seed`, plus
   `training_seed` now that training has its own stream (`utils/training_random.py`), plus the
   `PYTHONHASHSEED` in force and the git SHA (`_eog_band_git_sha()` already computes one from
   `RAILWAY_GIT_COMMIT_SHA`).
3. Add a replay entry point that takes a game document and re-runs it from those values.

**Caveats the fix must respect:**

- `sim_rng` is a plain instance shared across threads (deliberately — a thread-local proxy
  measured +30% per draw, and the engine makes ~82k draws/game). **Replay therefore requires
  single-threaded execution**, as `perf_sim_baseline.py --workers 1` already does. Per-game
  seeding makes multi-process pools reproducible, but not multi-threaded ones.
- Hash-order determinism is only partial — twelve sites fixed, divergence still present, hunt
  parked. Replay depends on the pin staying in place, so `PYTHONHASHSEED` must be recorded per
  game rather than assumed to be 0 forever.
- Games played BEFORE this ships are unrecoverable. No amount of later work reconstructs them.

**Value:** this is the difference between "we pinned the hash seed" and "a user can send us a
game ID and we can watch exactly what they watched." Small change, and the second thing is the
one people will actually ask for.

#### AUDIT — which earlier results were affected

The rule: **arms compared WITHIN one process share that process's hash seed and are valid;
arms run as separate invocations are not.**

| harness | structure | verdict |
|---|---|---|
| `w_sweep.py` | `for w in WS` inside one process | **valid** |
| `read_test.py` | `CONFIGS` looped in-process | **valid** |
| `lineup_analyze.py`, `gates.py` | no per-arm invocation | **valid** |
| `head2head.py`, `lineup_diag.py` | `argv[1]` is games count, single config | **valid** (absolute values are one hash world) |
| `slider_ab.py` | `ARM = sys.argv[1]` — one arm per process | **INVALID across arms** |
| `difficulty.py` | `TAG = sys.argv[1]` — one arm per process | **INVALID across arms** |
| `foul_levers.py` | one arm per process | **INVALID** as originally run; later re-run pinned |

No harness set `PYTHONHASHSEED` internally. The lineup diagnostics and gate sweep are
structurally fine; the slider A/B and difficulty comparisons should be re-run pinned before
being quoted again.

### `OUTSIDE_SHOT_SELECTION_MULTIPLIER = 0.55` is the real driver of attack dominance (August 2026)

- **Symptom:** Motion shot types run **~77% attack at NEUTRAL sliders** (2/2/2), and ~90% at
  `attack=4/outside=0`. Measured over 5 matched seed sets, 15 quarters/config.
- **Not the sliders.** Removing team emphasis from the `_weighted_attack_or_outside` type roll
  (so the sliders act only through `_focus_emphasis`) moved the neutral mix by **0.1 points**
  (77.02% → 77.11%) and the 4/0 extreme by only 3 points (92.7% → 89.7%). The sliders were
  symmetric noise on top of an already-lopsided base.
- **Root cause** — `BackEnd/engine/motion_step_decision.py`:
  ```
  attack_score  = (AG + SC)/2                              ~55 for a typical starter
  outside_score = SH * OUTSIDE_SHOT_SELECTION_MULTIPLIER    ~30  (SH ~55, discounted 45%)
  -> attack wins ~65% of type rolls before any emphasis
  ```
  The constant's own comment says it exists to "steer eligible outside players toward drives".
  At 0.55 that thumb is heavy. Raising it toward **~0.8** is the actual lever; it would pull
  neutral attack from ~77% to roughly the mid-60s and bring the 4/0 extreme down with it.
- **⚠️ NOT just a shot-mix dial.** Attack decisions are what generate contact: they route through
  `_create_attack_drive_shoot_steps`, whose drives can end in foul / charge / dead-ball turnover.
  Roughly **two-thirds of attack decisions never become shots** (decision-level attack ~80% vs
  final-shot attack ~25%). So changing this constant moves **foul rate, free-throw rate and
  turnover rate**, not only the inside/attack/outside split.
- **Owner:** belongs with the shot-tuning pass (see `project_shot_system_tuning`), NOT with the
  focus-slider work. Needs its own before/after across those four rates, and it will interact
  with the 3PT-rate calibration.

### MEASURED, NO EFFECT FOUND: archetype-varying objective weight `w` (2026-08-12)

**The second attempt at archetype-driven substitution, and the second one that does not pay.**

After the hysteresis pair below was rejected, `cpu_identity_design.md` §B3's archetype idea
was redirected from the NG gate to the selector objective weight `w`
(`score = w·static + (1−w)·effective`), which `db_utils.py:176` already names as *"the
intended home for archetype influence (via starter_bench_gap)"*. That redirect was right in
principle — `w` changes who the selector considers better rather than holding anyone past a
gate — but the effect is not there.

**The hypothesis, stated precisely.** `c2570c5aa` swept `w` LEAGUE-WIDE and found lower is
better (every value beat `w=1.0`; >10 effective-talent gap 20.8% → 0.7% going 1.0 → 0.25).
The spec wants `w` to go UP for top-heavy rosters. That is only defensible if the optimum
DIFFERS BY ROSTER SHAPE and the league-wide sweep averaged the difference away. So the test
is not "is high `w` good" — it is **"does the optimum differ by band."**

**Method** (`scripts/lineup_w_conditional_sweep.py`, read-only): within-game pairing — one
team gets `w=0.60`, its opponent `w=0.05`, same seed/venue/opponent, with the high arm
alternating home/away. One observation per GAME (the design is zero-sum, so per-team-game
arms are perfect negatives and a two-sample SE over them is meaningless). Matchups restricted
to a single `starter_bench_gap` band, because the bands are 96/23/9 teams and random pairing
spends ~93% of games where the answer is already known.

| gap band | games | high-`w` margin | SE | \|t\| |
|---|---|---|---|---|
| top-heavy (>19) | 32 | **−1.56** | 2.70 | 0.6 |
| shallow (<13) | 32 | **−1.22** | 2.50 | 0.5 |

**Verdict — no conditional effect.** The spec predicts these bands should have OPPOSITE
signs. They have the same sign, similar magnitude, and differ by **0.34 points — about
one-eighth of a single SE**. Both are consistent with the league-wide result that lower `w`
is better; neither supports varying it by roster shape.

**Honest limits.** 32 games/band cannot resolve a ~1.5-point effect on its own (|t| ≈ 0.5–0.6),
so this does not *prove* no effect. What it does is bound the conditional effect as small and
provide zero support for its existence, against a prior that already measured higher `w` as
worse. Single franchise, week-2 rosters, two `w` arms rather than a full sweep.

**Where `starter_bench_gap` came from.** It is not defined anywhere in the codebase — only
named in the `db_utils` comment. The sweep defines it as the mean over the five lineup slots
of (best static slot rating − second best). Static not effective (it is a roster property,
not a fatigue state); second-best per slot not "the bench" (that is who actually replaces the
starter); mean not max (one thin position should not read as top-heavy). Observed on the
identity league: min 2.0, max 29.2, mean 11.1 — so the spec's 13/19 band edges put **75% of
the league in one bucket** and were evidently cut against a different population, the same
failure as the `RT ≥ 50` bar and the frozen `SIGNAL_SCALE` constants.

**When to revisit:** a different `w` grid is not the answer — the league-wide sweep already
mapped that curve and it is monotonic. Like hysteresis, the case for reopening is a change to
the **fatigue economy**, not a better parameter.

---

### MEASURED AND REJECTED: NG pull/return hysteresis pair (August 2026)

Implemented, swept, head-to-head'd, then **stripped** rather than left as inert plumbing —
this project has surfaced four orphaned mechanisms already, and shipping the scaffolding for
a rejected one is the same pattern. Recording the results so the work isn't lost.

**What it was:** replace the single `NG >= 0.80` eligibility gate with a pair — a player ON
THE FLOOR stays eligible until NG < PULL, and once benched cannot return until NG >= RETURN.
The late-game relaxation (0.64 in the final 4:00 of Q4/OT) composed multiplicatively
(factor 0.64/0.80) against BOTH ends, so `(0.80, 0.80)` reproduced the old behaviour exactly.

**Sweep (16 games per pair, w = 1.0 so only the gate moved):**

| pull/return | star min% | stint mean | subs/rebuild | floor NG mean | floor NG min |
|---|---|---|---|---|---|
| 0.80/0.80 (control) | 40.5%* | 1.21 | 4.01 | 0.879 | 0.600 |
| 0.75/0.85 | 40.5%* | 1.41 | 3.37 | 0.852 | 0.520 |
| 0.70/0.90 | 40.5%* | 1.46 | 3.21 | 0.842 | 0.510 |
| 0.65/0.90 | 41.4%* | 1.58 | 2.94 | 0.824 | 0.450 |
| 0.60/0.95 | 41.0%* | 1.71 | 2.68 | 0.805 | 0.420 |

\* these star-minutes figures are VOID — see the metric warning in
`06_Gameplay_Systems/CPU_Team_Rotation_System.md`. The *relative* flatness across pairs is
still informative (the defect was constant across arms); the absolute level is not.

**Head-to-head vs (0.80, 0.80), 32 games each, both directions:**

| pair | record | win% | SE | mean margin |
|---|---|---|---|---|
| 0.75/0.85 | 14-18 | 43.8% | +/-8.8 | **-1.81** |
| 0.70/0.90 | 15-17 | 46.9% | +/-8.8 | **-1.66** |
| 0.65/0.90 | 16-16 | 50.0% | +/-8.8 | -0.56 |

**Verdict — rejected.** Three findings:
1. **Churn improves genuinely** — substitutions per rebuild fall 20-33%, mean stint length
   rises 41%. This is the only real benefit, and it is cosmetic.
2. **It costs about a point a game.** No pair beat the control; all three margins are
   negative. Mechanically unsurprising: holding a tired player past PULL is by construction
   fielding someone worse than the best available alternative.
3. **It does not move star minutes at all** (flat across every pair). Star minutes are an
   equilibrium of the fatigue economy — on-floor decay ~0.015/possession
   (`_ND_DECAY_TIERS`) against bench recovery ~0.009/possession
   (`phase_resolution.py` bench recharge) — not a property of the thresholds. Widening
   hysteresis buys a longer stint and pays for it with a proportionally longer rest.

**When to revisit:** only if the FATIGUE ECONOMY changes. In a slower-decay world long
stints may arise without paying a point a game for them, at which point hysteresis might be
unnecessary rather than merely unprofitable. **Do not revisit by searching for a better
threshold pair** — the sweep covered 0.60-0.80 pull against 0.80-0.95 return and the shape
was monotonic throughout: more hysteresis, less churn, more exhaustion, same minutes.

## Database-safety incident + systemic holes (August 2026)

### `_update_position_ratings` writes a derived cache on every GameManager construction — TICKET, not fixed

- **Finding:** `GameManager.__init__` calls `_update_position_ratings()`, which recomputes
  `position_ratings` from each player's attributes/height/name and **`bulk_write`s them to
  `players`** for every non-franchise, non-synthetic player on both teams
  (`BackEnd/models/game_manager.py:113-121`). **Constructing a GameManager is a database write.**
- **Why it matters:** this made "read-only investigation" false for the entire CPU identity /
  rotation / lineup / motion project. Every sim harness was writing `position_ratings` on each
  game it constructed. On staging that is self-consistent, so it went unnoticed for weeks.
- **The design question (not tonight's work):**
  1. compute in memory, persist **only on change** — would not have helped here, the formula
     genuinely differed;
  2. compute in memory, persist **never**, with an explicit migration owning the stored field;
  3. keep writing, but behind an explicit **read-only / no-persist mode** harnesses opt into.
  Option 2 is cleanest — a cache that self-heals is exactly what makes its staleness invisible.
  Option 3 is the smallest change and would immediately make sim harnesses honest.
- **Supporting evidence:** prod `position_ratings` carries at least three formula generations
  (53.6% match `93737625c`, 39.4% match `a88aa8fcc`, remainder older). Teams hold whatever was
  deployed the last time they played, so the field is unreliable for league-wide analysis.

### `.env.local` resolved against CWD, silently retargeting production — FIXED

- **Was:** `BackEnd/db.py` chose its env file with `os.path.exists(".env.local")`, relative to the
  **working directory**. Any script run from a subdirectory failed to find it, fell through to
  `.env`, and connected to prod. One instance of a class, not a one-off.
- **Incident:** a sim harness run from a scratch directory rewrote `position_ratings` on **192
  prod player documents across 16 teams** with the recalibrated formula, while prod runs a
  pre-recal formula. Deltas up to 38 rating points. Only that field changed — `attributes`,
  `height` and `name` verified untouched.
- **Now:** resolved against the repo root (`Path(__file__).resolve().parent.parent`).
- **Plus a production access guard** in the same file: reaching `gob` requires an explicit
  per-invocation opt-in, `GOB_DB_ACCESS=read` or `=write`, read from the **real process
  environment snapshotted before dotenv load** — so it cannot be armed from a committed `.env`.
  The deployed app is recognised by any `RAILWAY_*` variable. Unrecognised process → refuse at
  import. `aggregate()` is deliberately not blocked in read mode, so `$out`/`$merge` can still
  write; tighten if that becomes a real path.

## EOG leveling pass (August 2026) — follow-ups

### RESOLVED + ESCALATED: the fight / discipline drift owner (August 2026)

**Diagnosed. Two of the three candidates are closed; a bigger one opened.**

**(b) reset/rollover artifact — RULED OUT.** The per-week training delta is SPREAD EVENLY
across all 26 weeks, not spiked. `fight` runs +0.4..+2.0 every week, `discipline` -0.4..-3.6;
the top three weeks hold only 20% and 29% of total movement. Controls
(`offensive_efficiency`, `fb_efficiency`, `shot_threshold`, `team_chemistry`) are equally
smooth, top-3 concentration 15-16% — so §2b is NOT absorbing large one-off EOS/camp writes
into the training column for any attribute.

**Persona coupling — RULED OUT TWICE OVER.** The nudges are equal in magnitude (±1.5 mean) and
fire at 4-of-5 sub-options each way, so they cancel at uniform selection. And they never fire
at all for CPU teams: `auto_train_one_cpu_team` pins `coaching_focus = "player-maximizer-custom"`,
so the archetype is ALWAYS `player-maximizer`. The culture-builder / authoritarian branches are
dead code on the CPU path, and 127 of 128 teams are CPU.

**(a) the CPU reference plan — CONFIRMED OWNER for fight/discipline.** Measured directly via
`auto_train_one_cpu_team(..., dry_run=True)` over 40 teams (all pymongo writes blocked; zero
write attempts):

| attribute | reference plan | §2b inferred | verdict |
|---|---|---|---|
| team_chemistry | -11.7 | -10.2 | ✅ fully explained |
| offensive_efficiency | +7.2 | +7.5 | ✅ fully explained |
| fight | **+16.2** | +27 .. +32 | direction right, ~60% of magnitude |
| discipline | **-24.1** | -35 .. -48 | direction right, ~60% of magnitude |
| **shot_threshold** | **+1.3** | **+51.4** | ❌ **40x GAP — NOT TRAINING** |

The fight/discipline residual is plausibly estimator bias: §2b conditions on BOTH endpoints
unclamped, which progressively drops teams that have drifted to the clamp and leaves only
small-delta survivors (visible as `discipline` decaying -3.55 at wk2 to -0.44 at wk14). That
biases the estimate DOWNWARD, so the true drift is probably larger than either figure.

**Action for fight/discipline:** the owner is the reference plan's drill->team-attr mapping
(`training_execution_v2.py:607-617` — discipline draws 0.25x from four categories, fight 0.5x
from two). Retune there, not in the EOG bands.

### ⚠️ RETRACTED: "shot_threshold has an unidentified writer" — it was a measurement error

**There is no mystery writer.** The claim came from a dry-run measurement taken against
END-OF-SEASON state where **123 of 128 teams sat at the 200 ceiling**, so every training gain
was clamped to zero and the plan appeared to produce +1.3/season. Re-measured with attributes
reset to mid-range, the SAME reference plan produces **+60.5/season** against §2b's +51.4 —
fully explained by training. Only three writers touch team attributes (EOG apply, CPU
auto-train, user training) and that is correct.

Also note: the "nothing in week 1" signal that motivated the hunt is an artifact. The training
delta is computed as `pre[w] - post[w-1]`, so week 1 has no value BY CONSTRUCTION. It is not
evidence of a state-dependent writer.

### ⚠️ THE REAL FINDING: §2b systematically UNDERSTATES training for clamped attributes

Reference plan measured two ways over 40 teams (`dry_run=True`, writes blocked, zero attempts):

| attribute | from LIVE (railed) state | from UNCLAMPED state | §2b inferred | ratio |
|---|---|---|---|---|
| **team_chemistry** | -11.0 | **-93.6** | -10.2 | **9.2x** |
| **discipline** | -17.6 | **-91.6** | -48.1 | **1.9x** |
| **shot_threshold** | +5.9 | **+60.5** | +51.4 | 1.2x |
| fight | +26.0 | +37.1 | +32.0 | 1.2x |
| pt_efficiency | +6.5 | +9.1 | +7.3 | 1.2x |
| offensive_efficiency | +7.2 | +7.8 | +7.5 | 1.0x |
| defensive_efficiency | +11.0 | +7.8 | +7.6 | 1.0x |
| fb_efficiency | +7.8 | +6.5 | +7.4 | 0.9x |
| rebound_modifier | +0.5 | +0.2 | +0.2 | 1.0x |

§2b conditions on BOTH endpoints unclamped, so for an attribute whose population is pressed
against a clamp it measures only the survivors — the teams that have not yet railed, which are
precisely the ones with small deltas. **The unconstrained attributes agree within 10%; the
railing ones are understated by up to 9x.**

**This invalidates part of the leveling pass.** EOG was tuned against the inferred column, so
for the four clamped attributes the resulting combined drift is much worse than the tuner
reported:

| attribute | tuner said | with TRUE training pressure |
|---|---|---|
| team_chemistry | +0.8 | **≈ -83** |
| discipline | -34.2 | **≈ -78** |
| shot_threshold | +48.3 | **≈ +57** |
| fight | +32.0 | **≈ +37** |

The seven unconstrained attributes are unaffected and their tuning stands.

**Which number is the right target?** Neither alone. The unclamped figure is the training
PRESSURE; the inferred figure is the movement REALISED among teams that have not railed. EOG
should be tuned against the pressure — if it is not, the attribute rails, and a railed attribute
carries no information regardless of what the realised drift looks like. Update
`TRAINING_PER_SEASON` in `scripts/eog_band_tuner.py` to the unclamped column and re-tune those
four.

**But the pressure is too large to absorb in EOG alone.** team_chemistry at -93.6/season on an
18-point range cannot be offset by any sane band — EOG would need +3.6/game. The training side
has to come down for team_chemistry and discipline; only then is EOG re-tuning meaningful.

### (superseded by the entry above) Original fight/discipline ticket

**Measured on the identity season:** `fight` **+32.0**/season and `discipline` **−48.1**/season
from TRAINING, against EOG contributions of **+0.6** and **+14.0**. Training dominates both, so
their EOG bands were left DELIBERATELY UNTUNED in the leveling pass — compensating via EOG would
require perverse bands (see below). Revisit the bands only after this is settled.

**The persona coupling is NOT the cause — this was checked and ruled out.**
`_apply_player_training_points` (`training_execution_v2.py:745-767`) looks asymmetric but is not:

| nudge | fires when | sub-options hit |
|---|---|---|
| `fight` +1..+2 | culture-builder, sub != `culture-builder-teamwork` | 4 of 5 |
| `discipline` −2..−1 | culture-builder, sub != `culture-builder-confidence` | 4 of 5 |
| `discipline` +1..+2 | authoritarian, sub != `authoritarian-teamwork` | 4 of 5 |
| `fight` −2..−1 | authoritarian, sub != `authoritarian-rebounding` | 4 of 5 |

Equal magnitudes (±1.5 mean), equal firing rates, and `generate_random_coaching_focus` picks
uniformly from 19 options. Expected net contribution to both attributes is **zero**. The
drill mapping is symmetric too — `discipline` draws 0.25x from four categories, `fight` 0.5x
from two; both total 1.0x.

**Direct measurement contradicts the season figures.** Running `execute_training` 200x with
`generate_random_training_allocations(24)`:

| focus | Δfight/season | Δdiscipline/season |
|---|---|---|
| none | −4.5 | +4.9 |
| random | −10.8 | +3.9 |

**Opposite sign and an order of magnitude smaller** than the season's +32 / −48.

**Two candidates remain, neither yet confirmed:**
1. **CPU auto-train does not use random allocation.** `auto_train_one_cpu_team` trains a
   "coaching-quality REFERENCE" plan (see the comment above `_AUTOTRAIN_PLAYER_ATTRS` in
   `franchise_routes.py`). 127 of 128 teams in the season are CPU, so the measured drift
   reflects that reference plan, not the random path measured above. **Measure the reference
   plan's per-attribute effect first — this is the most likely owner.**
2. **The "training" figure is INFERRED, not measured.** Report §2b derives it from
   unclamped week-to-week `pre`->`post` gaps in the band log, so it attributes EVERY
   non-EOG change to training — including anything else that writes team attributes between
   games (EOS, training camp, rollover). Verify the attribution before trusting the number.

**Why not just tune EOG around it:** `fight` EOG is structurally zero (every game has exactly
one winner, so win +1 / loss −1 nets to 0 league-wide); offsetting +32 would require losses to
hurt far more than wins help, i.e. every team drifts down over a season. `discipline` would need
EOG ≈ +2.04/game, which on a ±20 range rails the ceiling in about six games.

### The two INTERIM constants

`FG_PCT_MID/HIGH` and `OFF_CONC_REWARD/MIDDLE` are cut against inputs already scheduled to
change (shot calibration; the playbook generator's 20% concentration cap for 4+ set plays).
The dependency is recorded beside each constant in `constants/eog_attr_bands.py` — what it was
cut against, its measured value at cut time, and that a material shift requires re-running
`scripts/eog_band_tuner.py`. When either input moves, these cuts invert the problem.

### `rebound_modifier` init 0.2 -> 0.5 — NOT DONE

Not a band, so outside the tuner's model. With the new ladder, rebound drift is +0.1/season on
a 0.0-1.0 range, so 0.5 gives symmetric headroom and should stop the week-3 flooring (93 teams).
Confirm against a short run rather than assuming.

## ⚠️ MEASUREMENT FRANCHISES ARE SEEDED BY PROD CODE, MEASURED BY LOCAL CODE (August 2026)

**The structural hazard behind several hours of confusion, stated once so it is not
rediscovered.** A measurement franchise is created through the UI, which talks to the
**deployed Railway backend running `main`**. The season is then driven **in-process by local
`develop` code**. So every value seeded at creation comes from prod, and everything computed
during the run comes from local. Anything changed since the last deploy **seeds wrong,
silently, and looks like data rather than an error.**

`main` is currently **158 commits behind `develop`**.

### Audit: what differs (prod `main` -> local `develop`)

| surface | prod (main) | local (develop) | consequence for a measurement franchise |
|---|---|---|---|
| **`position_ratings.py` RT model** | pre-recalibration | recalibrated | **100% of FPD players carry old-formula `position_ratings`, median delta 24, max 55.** Baked in at creation and NOT recomputed for franchise mode (`_update_position_ratings` skips `is_franchise`). Feeds `projected_starting_five` -> identity signals -> starter strength, and every lineup decision. |
| **`player_generator.py`, `recruit_generator.py`** | ABSENT | present | prod builds rosters by a different path; the player population itself may differ |
| **`TEAM_ATTR_CLAMPS` core-8** | ±10 | ±20 | prod-written attributes live in HALF the range local code assumes |
| `team_chemistry` init (franchise) | `randint(7, 10)` | `randint(8, 11)` | 21% of the league born on the 7 floor |
| `rebound_modifier` init (franchise) | 0.2 | 0.5 | floors 93/128 teams by week 3 |
| `eog_attr_bands.py` | ABSENT | present | prod has no band configuration at all |
| `team_identity.py`, `franchise_identity.py` | ABSENT | present | prod has no CPU identity |
| `TEAM_ATTR_RANGES["rebound_modifier"]` | (0.0, 0.4) | (0.0, 1.0) | no practical difference — franchise init sets the value explicitly |
| `init_team_attributes` single-mode rebound | `TEAM_ATTR_RANGES` (= 0.0-0.4) | literal 0.0-0.4 | identical behaviour |

### Before the next measurement season, do ONE of

1. **Deploy `develop` first**, so seeded and measured code agree. Cleanest.
2. **Normalise after creation** — a setup script that overwrites every seeded value local code
   would produce differently, run before week 1. This is what was done ad hoc for
   `rebound_modifier` on the verification franchise (all 128 FTDs set to 0.5). It must also
   recompute FPD `position_ratings` with the local formula, which was NOT done.
3. **Provision locally** rather than through the UI.

### Standing caveat for the identity and verification seasons

Both were UI-created, so BOTH carry prod-formula `position_ratings`. They are therefore
consistent WITH EACH OTHER — the band thresholds cut against the identity season apply to the
verification season — but neither matches what local code would generate, and neither will
match production once the recalibration deploys. **The thresholds will need re-cutting after
that deploy.** Re-running `scripts/eog_band_tuner.py` against a post-deploy season is seconds;
the trap is not noticing it is needed.

## DEPLOY CHECKLIST — develop -> main (prepared 2026-08-11)

`main` is 158 commits behind. Testers are on ±10 clamps, no CPU identity, and
pre-recalibration attributes. No migration path is needed: users are told to abandon
existing franchises and start new ones.

| # | step | notes |
|---|---|---|
| 1 | **Back up prod collections** | DONE — `~/gob-measurement-archive/db_backups_predeploy/`, checksummed, reload-verified. `gob.players_backup` is NOT a usable rollback (stale; attributes differ on 1440/1536). |
| 2 | **Merge develop -> main** | code half |
| 3 | **Copy `players` + `recruit_sets`** staging -> prod | data half. NOT the skeletons — see below. |
| 4 | `GOB_DB_ACCESS=write` in Railway | redundant signal for the prod guard; `RAILWAY_*` alone also satisfies it |
| 5 | CSP: allow `fonts.googleapis.com`, `www.googletagmanager.com` | new external hosts |
| 6 | Site callout: abandon current franchises | |
| 7 | **`scripts/verify_deploy.py`** | proves the deploy took — see below |

**ORDERING IS BACKUP -> MERGE -> COPY, not copy -> merge.** New code reading old data is a
known-good combination — both measurement seasons ran 26 weeks on exactly that (local code
against prod-formula ratings). OLD code reading NEW data is untested: prod's current build
would be handling a `recruit_sets` 50% larger than it expects.

### Do NOT copy the skeletons

`fcp_skeletons` / `hct_skeletons` hash differently across databases but are **identical except
for `_id`** — every coordinate matches. Copying would churn prod for no benefit. **Heuristic
worth keeping: same byte size + different hash usually means metadata; a real content change
moves the size.** `recruit_sets` moved 146 KB -> 356 KB, and that one is real.

### `recruit_sets` 300 -> 450 is INTENTIONAL

Deliberate regeneration (`1277580c6`, 2026-08-08): 150 added recruits plus the `entry_tier` /
`position_intent` / `potential_factor` / `has_portrait` fields. It is a balance change riding
along with the attributes deploy — 50% more recruits available — and should be stated in the
callout, not discovered.

⚠️ **Prod's document claims `version=2` but holds the 300-recruit content with none of the
regen fields.** A version check would pass on stale data; only a content checksum catches it.

### Post-deploy verification — `scripts/verify_deploy.py`

Nothing else on the list confirms the deploy took, and silent divergence is the failure being
closed. `/health` now reports `commit`, `hash_seed` and `db_access` so the running build is
answerable from outside.

    scripts/verify_deploy.py --health-url https://<prod>/health   # A: build
    GOB_DB_ACCESS=read scripts/verify_deploy.py --data            # B: data (prod URI)
    scripts/verify_deploy.py --franchise-id <id> --delete         # C: seeding

C needs a throwaway franchise created in the UI (creation requires an authenticated session,
which the script deliberately does not embed) at **week 1, unplayed** — training moves the
seeded values immediately. It checks identity persisted, sliders varying, `rebound_modifier`
0.5, `team_chemistry` 8-11, `shot_threshold` 80-90, core-8 clamps ±20, then deletes the
franchise and its FTD/FPD/FRD rows.

The data check was negative-controlled against prod BEFORE the deploy and correctly FAILED on
both collections — it detects a stale copy rather than merely returning green.


## EOG band logging in PRODUCTION (August 2026)

Enabled so tester franchises produce the re-fit basis for `shot_threshold`. Those seasons are
the first ever run under the new bands, and they generate data in the region the model cannot
see — the fit behind the current calibration has n=256 at S=100-119 against n=1008 at 80-99.

### Why Mongo, not the file sink

`GOB_EOG_BAND_LOG=1` writes JSONL to a local path. **In production that produces nothing
retrievable**: Railway's container filesystem is ephemeral and `railway.json` declares no
volume, so the file dies on the next redeploy, each replica writes its own partial, and no
endpoint serves it. The default path is relative, inheriting the same CWD-relative hazard that
sent a sim harness at production.

    GOB_EOG_BAND_LOG=mongo            # off | file (local harnesses) | mongo (production)
    GOB_EOG_BAND_FRANCHISES=a,b       # OPTIONAL RESTRICTION — unset/empty logs EVERY franchise
    GOB_EOG_BAND_TTL_DAYS=90          # retention

Logging every franchise by default is deliberate: tester franchises are created whenever, so
naming ids in advance would mean discovering which to log only after the season is half gone.

### Cost — measured, not estimated

| | |
|---|---|
| row size | 379 bytes JSONL / **258 bytes BSON** |
| franchise-season | 36,608 rows = **9.0 MiB** in Mongo |
| extra input computation | 0.026 ms/game — **0.001%** of a CPU week |
| Mongo writes, batch 500 | **3.96 ms/game** = 0.25 s on a ~160 s week (**0.16%**) |

Batch is 500, not 50: each `insert_many` is an Atlas round-trip (~45 ms), so batch 50 cost
~20 ms/game. `complete_week` flushes at week end and an `atexit` hook flushes on shutdown, so
a hard crash loses at most the current week's tail.

### Extraction

    GOB_DB_ACCESS=read scripts/eog_band_export.py --list
    GOB_DB_ACCESS=read scripts/eog_band_export.py --franchise-id <id> -o out.jsonl
    scripts/eog_band_tuner.py out.jsonl --validate --live

`--list` shows rows, weeks and whether a season is complete (26 weeks / 36,608 rows). Verified
round-trip: 1,408 rows through Mongo and back came out **byte-identical**.

⚠️ **`--validate` must use the config that PRODUCED the log.** There are now three generations
(pre-leveling, post-leveling, post-shot-retune) and validating against the wrong one reports
mass "drift" that is really a config mismatch — the verification log scored 8 of 11 attributes
as mismatched against `AS_LOGGED`, and 11 of 11 clean against its own config. `--validate` now
honours `--config` and `--live`.

### What tester data can and cannot answer

~99% of rows still come from uniform-reference-plan CPU teams — only 1 of 128 teams in a
franchise is the user's — so the sample is not meaningfully contaminated by deliberate human
training. The real distinction is which QUESTION the data answers:

* **The FG%-vs-shot_threshold slope fit is VALID regardless of training.** It is a property of
  the engine and rosters — what FG% a team produces at a given threshold — and training does
  not enter it. This is exactly the re-fit the `shot_threshold` calibration needs.
* **The band-POSITION calibration is NOT valid**, because it depends on the training drift the
  neutral band must offset (+56.4/season measured on the uniform plan). A league with human
  training has a different balance point.

So tester seasons answer the question we need and not the other one. Re-derive the slope from
them; do not re-derive the training constants from them.

### CPU strategy still derives from a THIRD starting-five picker (August 2026) [CODE-CLEANUP]

The display surfaces were synced to the game's selector in August 2026 — FCC Scouting Report
tab, team roster pages, training report, practice-squad team and tournament scouting all now
run `db_utils.projected_starting_five_from_payload`, the exact max-weight assignment autoset
uses at tip (`06_Gameplay_Systems/CPU_Team_Rotation_System.md` §6).

**`team_identity.projected_starting_five` was deliberately NOT re-pointed.** It is a separate
**greedy** fill on raw `position_ratings`, and it feeds eight signals → vision pair → strategy
sliders → `ftd.identity`. So every CPU team's game plan is still derived from a five that is
not the five it fields.

**Why it was left alone — this is the whole ticket.** `SIGNAL_SCALE`,
`RESIDUAL_SLOPE_VS_STRENGTH` and `STARTER_STRENGTH_MEAN` in `team_identity.py` are FROZEN
constants calibrated once against 128 measured teams **using the greedy five**. Swapping the
picker changes `starter_strength` and shifts every residualised signal off its calibrated
mean. Vision assignment across the league would drift by an unmeasured amount, silently,
because the scale would no longer mean what it was calibrated to mean.

**To finish it:**

1. Re-point `team_identity.projected_starting_five` at `solve_best_assignment`
   (`tie_break="stable"` — identity assignment must not consume sim RNG either).
2. Re-derive the frozen constants against a fresh 128-team pool under the new picker.
3. Bump `CONSTANTS_VERSION` so `ensure_franchise_identities` reassigns existing franchises
   rather than reusing pairs derived under the old scale.
4. Re-run the week-1 measurement gate (`franchise_identity_summary`) — vision distribution
   and slider variance. Zero variance means the treatment is not active.

**Not a perf item.** 128 teams × a 32-state DP once per season is nothing. The cost is the
measurement pass, not the compute.

**Trigger to do it:** the next time the identity constants are being re-derived anyway. Doing
it standalone means paying for a full recalibration to fix a consistency defect no user sees
directly.

## Sunset: `/team-roster/{team}` (removed 2026-08-17)

Removed the route, its 8 Jinja templates, the 8 "In Development" sibling pages, the
dev-only `/team-roster/` static-redirect entry, and `tests/test_team_roster_page.py`.

Why it went rather than being brought in line with the attribute-tile work:

- **Zero inbound links** anywhere in the repo — reachable only by typing the URL.
- **Wrong data source.** It read `players_collection` (the universal player pool), not
  franchise player data, so the same team showed *different numbers* than
  `team-roster-view.html`.
- **Already dead in development.** The dev middleware redirects any `/team-roster/*`
  path to `/static/...` before routing (`api.py`, static_dirs), so the page only ever
  rendered in production. That is likely why its data source drifted unnoticed.
- **No auth.** The route took no `Depends(get_current_user)` while every other roster
  surface is behind auth.

Residual risk accepted: an external bookmark or link would now 404. If that surfaces,
the fix is a 301 to `/team-roster-view.html` rather than restoring the page.
