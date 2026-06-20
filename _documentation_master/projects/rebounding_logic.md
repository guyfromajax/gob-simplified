# Rebounding logic (missed shots)

Plain-language summary of how rebounds work today for each miss type.  
Code lives mainly in `shot_manager.py`, `shared.py`, `phase_resolution.py`, `turn_manager.py`, and the step emitters (`skeleton_step_emitter`, `dreb_step_emitter`, `oreb_step_emitter`, `ft_step_emitter`).

For animation contracts and outlet behavior, see `05_GP_Supporting_Systems/Rebound_System.md`.

---

## Three things to keep separate

| Question | What decides it |
|----------|-----------------|
| **Potential rebounders** | Who is eligible to compete for the rebound before the winner is selected |
| **Actual rebounder** | Who gets the stat (`rebounderId`, OREB vs DREB) |
| **Animations** | Where players stand and who moves on which turn |

The `offense_rebounders` / `defense_rebounders` payload lists are animation support. They drive **who can move** on rebound capture steps after the winner is already known. They do **not** by themselves pick the winner, except on older HCO/FCP-style paths where the same strategy-derived position lists are also used as the winner pool.

Current terminology:

- **Candidate pool:** position-keyed lineups used before winner selection.
- **Actual rebounder:** the one player selected from the candidate pool and credited with the stat.
- **Failed attemptors:** player-id lists stamped after the rebounder is known so the DREB/OREB capture step can animate nearby non-captors.

---

## Shared animation ideas

**On the shot MISS turn (when lists exist)**  
`shot_manager` stamps:

- Crash lists (player IDs)
- Rim-cluster positions (`offense_rebounder_coords`, `defense_rebounder_coords`) — random spot near the basket that was shot at, not “closest to bounce”
- Get-back / release positions (HCO only)

The schema MISS path (`[shoot]` → `[ball_flight]` → `[bounce]`) moves overlay players toward those spots; the ball goes to `ball_bounce_x/y`.

**Discrete DREB turn (HCO, FCP, HCT, migrated fast break, FT DREB, putback miss → DREB)**  
One step: rebounder sprints to the ball; everyone on the crash lists (minus the rebounder) takes a short move toward the bounce (±4 x, ±6 y jitter). Everyone else stays put.  
DREB does **not** re-place all ten players—it uses where the prior turn left them.

**Near-bounce failed attemptors**  
For newer miss paths, the backend stamps failed attemptors with `collect_near_bounce_rebound_attemptors()` after the authoritative bounce spot and actual `rebounderId` are known. The helper includes non-captor players within **20 Euclidean grid units** of the bounce. This is an animation helper only; it does not decide the rebound winner.

**Half-court outlet** (DREB → HCO/HCT/FCP) is a **client** beat after the DREB turn, not part of the DREB step.

**OREB turn**  
Step 0 `[rebound_capture]` reuses crash lists from the **original** miss turn. Putback `[bounce]` keeps everyone **stationary** (no second crash animation on the OREB row).

---

## HCO miss

### Potential rebounders
- **Offense:** Everyone except get-back players (0–2 guards retreat based on team `rebounding` slider).
- **Defense:** Everyone except a Covert Release outlet, if that fast-break roll fired on this shot. Otherwise all five crash.

Strategy / roles — **not** distance to the ball.

### Actual rebounder
Two steps:

1. **Per team:** Among crashers only, pick whoever is **closest** to the bounce (Euclidean). Shooter’s distance counts as 20% farther (less likely to be that team’s pick).
2. **Between those two:** Weighted random using rebounding attributes (RB/ST/IQ + die), defense-favored baseline (~70%), extra defenders in the crash, team `rebound_modifier`, and a small zone-defense tweak. **Not** “closest player on the court wins.”

Bounce spot comes from `calculate_bounce_spot` (shot distance affects how far the miss bounces from the rim).

### Animations
- Full overlay maps on the MISS turn → crowded miss/bounce.
- If result is **DREB** and next play is HCO/HCT/FCP → extra **DREB** turn with multiple movers (if lists were filled).
- If **OREB** → separate **OREB** turn chain (putback / kickout), no discrete DREB on the first board.

---

## Fast break miss

Covers transition shots flagged `is_fast_break` in `resolve_shot` (e.g. Rim Runner, Triangle, Covert outlet path) — **not** the separate “after steal” fast break module (see below).

### Potential rebounders
Only players in the **attacking half** of the court by current `coords.x`:

- Home offense: `x ≥ 50`
- Away offense: `x ≤ 50`

Everyone in that filtered set is on the crash list (often fewer than five per side). No get-back, no release lists.

### Actual rebounder
Same pattern as fast break block in `shot_manager`: closest per team within the filtered pool (shooter penalized 20%), then attribute/team-bias random between the two finalists. Bounce from `calculate_bounce_spot` at the basket being attacked.

### Animations
- Rim-cluster overlays for eligible players only on the MISS turn.
- **DREB** discrete turn when promoted (migrated play keys) — failed attemptors are stamped from the near-bounce helper when available.
- Sparse boards are expected when few players are in the frontcourt half.

### After-steal fast break miss
Resolved in `after_steal_fast_break.py`.

**Potential rebounders / actual rebounder:** uses computed shot-end coordinates, then runs `determine_rebounder` on the active lineups. There is no hard 20-grid eligibility gate before winner selection today; distance still matters because each team's finalist is the player closest to the bounce.

**Animations:** after the winner is known, the resolver stamps `offense_rebounders` / `defense_rebounders` with the near-bounce failed-attemptor helper using the same shot-end coordinate frame. The promoted DREB row can therefore animate nearby non-captors instead of only the actual rebounder.

---

## HCT miss (half-court trap shot)

Uses `shot_manager.resolve_shot` while `offensive_state` is **HCT**.

### Potential rebounders
- **Offense:** All five crash (no get-back).
- **Defense:** All five crash (no Covert Release / outlet logic on HCT shots).

Same **role-style** lists as HCO, but everyone crashes.

### Actual rebounder
**Same as HCO miss** — not the fast-break half-court x-filter. Closest crasher per team, then weighted contest.

> Note: `Rebound_System.md` describes a future x-half-court filter for HCT/FCP. **In code today, only fast break misses use that filter; HCT uses the HCO winner pipeline with “everyone crashes” lists.**

### Animations
Same as HCO: overlays on MISS, discrete **DREB** when chained and promoted.

---

## FCP miss (full-court press shot)

Uses `shot_manager.resolve_shot` from FCP resolution (`fcp_shot` on the turn). **`offensive_state` is not HCT**, so normal HCO positioning rules apply.

### Potential rebounders
- **Offense:** Crashers vs get-back (same `rebounding` slider as HCO).
- **Defense:** Crashers vs Covert Release outlet (same as HCO).

### Actual rebounder
**Same as HCO miss.**

### Animations
**Same as HCO miss** (skeleton/FCP emitter for the shot; rebound data still from `shot_manager`).

---

## Free throw miss (last attempt of the trip)

Handled in `resolve_free_throw_logic` after lane/setup animation updates coords.

### Potential rebounders
`collect_ft_rebound_crashers`:

- Keep players with **|coords.x − bounce_x| ≤ 20** (x only, not full distance).
- Drop the **shooter** and the player who already won the rebound stat.
- If nobody passes the filter on both teams, fall back to full lineups.

### Actual rebounder
`determine_rebounder` with the same **x ≤ 20** gate, then closest per team (with optional shooter/putback penalties when passed in), then attribute/team weighting between the two finalists. Bounce at the basket that was shot at.

### Animations
- FT turn owns the shot arc; last miss gets `ball_bounce_x/y` and crash lists on the **FT** turn.
- May chain discrete **OREB** or **DREB** turns using those lists.
- Airball last FT: no rebound animation path.

---

## OREB — first board (after any miss that was OREB)

Not a separate “miss type,” but the turn after an offensive rebound stat on the prior shot.

### Potential rebounders
Reuses `offense_rebounders` / `defense_rebounders` from the **miss turn that produced the OREB**. If that miss was sparse (e.g. after-steal FB), capture animation may look thin.

### Actual rebounder
Already chosen on the prior miss; OREB turn is putback (~90%) or kickout (~10%).

### Animations (OREB turn)
- `[rebound_capture]`: rebounder to ball; list members (minus captor) move toward bounce.
- Putback or kickout steps; **no** rim overlays during putback flight.

---

## OREB putback miss (second board)

### Potential rebounders
The winner-selection pool is still full active lineups via `determine_rebounder`; there is no hard 20-grid eligibility gate before winner selection today.

### Actual rebounder
`determine_rebounder` on **full lineups** (both teams), closest-to-bounce logic with **putback shooter 20% distance penalty**.

### Animations
- OREB `[bounce]`: **everyone holds** position.
- The putback miss rebound payload now carries `offense_rebounders` / `defense_rebounders` from the near-bounce failed-attemptor helper.
- If next is **DREB**, `game_manager` builds a discrete DREB turn from the **putback miss** row and passes those failed-attemptor lists into the DREB emitter.

Remaining gameplay hardening question: whether winner selection should also use a pre-rebound geo eligibility gate instead of full active lineups.

---

## Quick comparison table

| Miss type | Potential rebounders | Actual rebounder | MISS-turn crash animation | Follow-up rebound turn |
|-----------|----------------------|------------------|---------------------------|-------------------------|
| **HCO** | Strategy: crash vs get-back / release | Closest per team → weighted contest | Full overlays | DREB or OREB |
| **Fast break** | Frontcourt half (x filter) | Closest in pool → weighted contest | Near-bounce failed attemptors for DREB capture | DREB or OREB |
| **After-steal FB** | Full active lineups at shot-end coords | Full-lineup `determine_rebounder` | Near-bounce failed attemptors for DREB capture | OREB or HCO |
| **HCT** | All five both sides | Same as HCO | Full overlays | DREB or OREB |
| **FCP** | Same as HCO | Same as HCO | Full overlays | DREB or OREB |
| **Free throw (last)** | \|x − bounce\| ≤ 20 | `determine_rebounder` + x gate | FT schema + lists | OREB or DREB |
| **Putback miss** | Full active lineups | Full-lineup `determine_rebounder` | OREB bounce: all hold; DREB capture uses near-bounce failed attemptors | DREB or OREB |

---

## Constants worth knowing

- **FT crash eligibility:** `FREE_THROW_REBOUND_MAX_X_DELTA = 20` (x-axis only) in `shared.py`
- **Near-bounce failed-attemptor animation radius:** `NEAR_BOUNCE_REBOUND_ATTEMPTOR_DISTANCE = 20` (Euclidean) in `shared.py`
- **Shooter / putback penalty:** distance × 1.2 when picking each team’s closest player
- **HCO defense baseline** in the final contest: ~70% before modifiers

---

## Known gaps / proposed hardening

### Animation

The main animation gaps that caused "only the rebounder moves" on after-steal FB misses and putback misses have been addressed by stamping near-bounce failed attemptors after the winner is known.

### Winner-selection candidate pools

Pre-rebound candidate eligibility is still uneven by path:

1. **HCO/FCP:** strategy first (get-back / release), then closest per team. No hard geo gate.
2. **Regular Fast Break:** attacking-half x filter, then closest per team.
3. **After-steal FB / Dynamic HCT / OREB putback miss:** full active lineups at the relevant shot frame, then closest per team. No hard geo gate.
4. **Free throw:** x-axis gate (`|coords.x - bounce_x| <= 20`), then closest per team.

Proposed hardening: add a sibling pre-winner helper, separate from `collect_near_bounce_rebound_attemptors()`, that filters position-keyed candidate lineups near the bounce before `choose_rebounder()` runs. Keep the existing near-bounce helper for post-winner animation only.

Track gameplay fixes in `projects/bugs.md` if you add backlog items there.
