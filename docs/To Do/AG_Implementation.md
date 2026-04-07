# AG → Movement Speed (implementation brief)

**Status:** AG v1 implemented (per-player speed in `getPlayerDuration`); tuning + HCO context scalars optional  
**Scope:** Universal player movement duration/speed from **effective in-game Agility (AG)**, starting with fast-break–style coverage; applicable to all steps/turns that use shared duration helpers.

---

## 1. Goals

- Reflect **player speed differences** in animation (not one global px/s for everyone).
- Use a **smooth linear** mapping from AG → speed (no tier buckets).
- Use **real in-game attributes** (fatigue-aware), not raw anchors only.
- Keep **one universal helper** so tuning happens in one place.
- **Ball handler:** universal **5% slower** than the same AG would predict off-ball (BH-specific modifiers deferred).

---

## 2. Effective AG (energy / fatigue) — SS&S with engine

Per **`docs/docs_1_systems/05_GP_Supporting_Systems/Energy_System.md`**:

- After energy changes, malleable attributes (including **AG**) are rescaled:
  - **`effective_attribute = anchor_attribute × NG`**
  - Code path: `attributes[k] = int(anchor_k * ng)` in `BackEnd/models/player.py` (`_rescale_attributes`).
- **NG** is clamped during play (min **0.1**, max **1.0**).

**Animation rule:** Movement speed must use **`attributes.AG` (or equivalent) from the same player payload the sim exposes after rescaling** — i.e. the value that already reflects **anchor × NG**. Do not use `anchor_AG` alone unless we explicitly add it to the API for debugging.

**Alignment check:** If product intent were ever “max speed at full energy should match roster card AG,” that is already true in the engine: at NG=1, effective AG equals anchor AG. No flag raised against the doc; wording **“anchor × NG = in-game value”** matches the Energy System (integer rounding is implementation detail).

---

## 3. Linear speed curve (no upper clamp on AG)

- Map **AG** (can exceed **100**; no cap for speed purposes) → **pixels per second** with a **linear** function:
  - Example form: `speedPxPerSec = speedBase + speedSlope * AG`
  - Constants **`speedBase`** and **`speedSlope`** are tuning knobs (prototype band discussed ~**400–500** px/s for “typical” AG values).
- **No maximum clamp** on AG for the formula: AG **120** continues the same line (e.g. if `speed = 400 + 1.0 * AG`, then AG **120** → **520** px/s). If a different line is chosen, recompute; **525** px/s at AG **120** implies a slightly steeper slope or higher intercept — pick constants explicitly when implementing.
- **Default AG** if missing: **50** (should not happen in production; assert/log in dev).

---

## 4. Ball handler penalty (v1)

- **Universal 5% reduction** for the player who is the **ball handler for that movement** (explicit context from turn / ball owner, not guessed).
- Later: optional BH attribute–based bonus/penalty **on top of** this universal rule.

---

## 5. Relation to global animation speed

- **Current:** `getPlayerSpeed()` / `window.__GAME_SPEED` use a single default (**~450** px/s).
- **Near term:** Implement AG-based speed using the **current baseline** as the reference (per prior discussion).
- **Later:** User-facing animation speed presets should act as a **multiplier** (or rescale) **around** the universal helper so AG spread and “faster/slower game” compose cleanly, and stay compatible with the **game clock** (already tied to animation pacing — see existing clock sync when reintroducing options).

---

## 6. Roll-out: universal first, HCO fine-tuning second

- **Phase A — Implement once, use everywhere:** Wire the universal AG → speed helper through all code paths that already derive tween duration from **`getPlayerDuration`** (or equivalent). **No separate FB-only fork** at first; fast breaks will show the largest *perceived* spread because players cover more pixel distance, while half court will show the same *relative* speed differences on shorter steps.
- **Phase B — Playtest HCO:** After ship, evaluate half-court *feel*: if movement is too subtle, too twitchy, or lost among dense step churn, add a **second tuning layer** rather than ripping up the AG curve.
- **Phase C — Optional HCO / turn-mode tuning:** Examples of follow-up knobs (pick as needed after playtest):
  - A **context or mode scalar** (e.g. `half_court` vs `open_court` / fast break) applied on top of the same AG-based speed.
  - A **blend** toward a baseline speed for compressed sets so AG differences stay readable without overshooting.
- **Principle:** One shared **AG → px/s** rule stays the source of truth; any HCO or press/trap adjustment is an **additive scalar or blend**, not a duplicate system.

---

## 7. Universal helper (architecture)

- **Single entry** used by `getPlayerDuration` (and any parallel helpers): e.g. resolve **effective AG** from sprite + scene/sim payload, compute **px/s**, apply **BH 5%** when applicable, then `duration = distance / speed` (existing distance-in-pixels behavior).
- **Data wiring:** Sprites may not expose `attributes` today; resolver should:
  - Prefer **`sprite`-attached** `attributes` / `AG` if present after load, else
  - **Lookup** `scene.simData.players` (or equivalent) by `playerId` for **current** `attributes.AG` and **NG** as needed.

---

## 8. Testing plan (support for “dunce mode” friendly tests)

**Unit-level (recommended first):**

- Pure function tests for **`agToSpeedPxPerSec(ag, { isBallHandler })`** (or equivalent):
  - Monotone increasing in AG.
  - AG **0**, **50**, **100**, **120** (extrapolation).
  - Ball handler flag **~5%** slower than off-ball for same AG.
  - Missing AG → defaults to **50**.

**Integration (lighter):**

- Mock sprite positions + `getPlayerDuration`-style call: longer AG **80** vs **40** over same pixel distance → shorter duration for higher AG.

**Fixtures:** `FrontEnd/static/js/phaser/utils/playerMovementSpeed.test.js` — run:

`cd FrontEnd/static/js/phaser && npm run test:movement` (speed + fatigue sprite sync)

---

## 9. Open items / follow-ups

- Final numeric **`speedBase`** / **`speedSlope`** after playtest.
- Whether to use **integer** engine AG only vs **float** `anchor_AG * NG` if exposed.
- Extend BH modeling beyond flat **5%**.
- Re-hook **global game speed** + clock to the helper.
- Post–Phase A playtest: whether **Phase C** context scalars are needed for HCO / press.
- **Skeleton step gating (§11.2):** **done** — HCO / FCP / HCT steps advance when **all offensive** step tweens finish; defensive tweens are **ambient** (started in parallel or with the pass) and **do not** block step progression. Pass choreography unchanged: await **passer**, then **pass animation**, then **`Promise.all` offense** so the passer is included after the ball moves.
- **Shot gating (§11.2–11.3):** still optional — HCO shot keyed on **shooter-only** vs current “all offense finish before `shootBall`”; rebound / display SS&S if shot fires early.

---

## 10. Reference files

- Energy / scaling: `docs/docs_1_systems/05_GP_Supporting_Systems/Energy_System.md`
- Turn structure / buckets: `docs/docs_1_systems/05_GP_Supporting_Systems/Turn_by_Turn_System.md`
- Player coords sync (animation finals → sim): `BackEnd/utils/shared.py` (`sync_lineup_coords_from_turn`, `apply_coords_from_animations_list`)
- Duration base: `FrontEnd/static/js/phaser/animation/turnAnimation.js` (`getPlayerDuration`, `getDurationFromDistance`, `DEFAULT_PLAYER_SPEED`; **offense-gated** skeleton steps — passer, pass only, `Promise.all` on offense; defense non-blocking)
- Shot-turn skeleton steps (same gating): `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js` (mirrors `playTurnAnimation` step phases)
- Fast break “everyone else” tweens: `FrontEnd/static/js/phaser/animation/fastBreak.js` (`animateRebounders` → `getPlayerDuration`)
- Sprite load: `FrontEnd/static/js/phaser/setup/loadPhaserPlayers.js`, `createPhaserPlayer.js` (may need `attributes` attach for AG)
- AG movement speed: `FrontEnd/static/js/phaser/utils/playerMovementSpeed.js`, tests `utils/playerMovementSpeed.test.js`
- Fatigue sync for sprites: `FrontEnd/static/js/phaser/utils/syncPlayerSpriteAttributes.js` (called from `prepareTurnForAnimation` + `applyPlayerStats`), test `utils/syncPlayerSpriteAttributes.test.js`

---

## 11. Animation gating & phase completion (brainstorm — Feb 2026)

**Purpose:** Record how steps advance today, how that intersects **AG** (variable finish times), and **product intent** for “who paces the beat.” Helps avoid blindly waiting on the slowest player when speeds diverge, while staying honest about **sim vs display**.

### 11.1 Concepts

- **Paced motion:** What **must** finish (or hit a milestone) before the next step/phase begins (ball handler spot, pass complete, shooter spot, shot release, etc.).
- **Ambient / trailer motion:** Spacing, trailers, get-backs — often should **not** block the beat unless the design says so.
- **Interrupted movement:** If a new step starts before a tween ends, **retarget from current pixels** (stop old tween, new duration from current position)—normal case, not edge case.

### 11.2 HCO skeleton steps (`turnAnimation.js`, `ShotAnimationSystem.js`)

**Non-shot steps (broadly “run the play”) — offense-gated:**

- **No pass on the step:** Client waits for **all offensive** step tweens (`Promise.all(offensivePromises)`), then advances. Defensive tweens start **in parallel** and are **not** awaited; the next step may begin while defenders are still moving (retarget from current pixels — §11.1).
- **Pass on the step:** **Staged:** (1) **`await` passer** (passer’s offensive tween); (2) start defensive step tweens when the pass path does (keeps pass and defense visually aligned); **`await` pass animation only** — defense does **not** gate; (3) **`await Promise.all(offensivePromises)`** so **every offensive** player (including the passer) finishes the step. The beat is “offense + pass,” not “slowest defender.”

**FCP / HCT:** Same skeleton machinery as HCO (§11.5).

**AG note:** Everyone on offense still **finishes the step together** (after pass choreography). Variable AG changes **how long** the step takes. **Shot** timing is still separate: see below — **shooter-only** shot gating is not implemented yet.

**Shot steps — product vs implementation:**

- **Desired product (discussion):** Shot should fire when the **shooter** reaches the shooting spot; shooter does **not** wait for trailing teammates.
- **Current client behavior:** After pass/defense, code **`await`s all remaining offensive** step tweens, **then** calls `shootBall`. So the **shooter currently waits for the rest of the offense** before the shot animation. Adopting shooter-only gating is a **deliberate change**, not a documentation polish.

### 11.3 Rebounds & “actual location at shot”

- **Backend SS&S:** After a turn is applied, **`sync_lineup_coords_from_turn`** aligns all ten lineup `Player.coords` with the **final step** of each player’s row in **`animations`**, plus overlays (get-back / release, etc.) — see `BackEnd/utils/shared.py`. That is **skeleton end state for the turn**, not live Phaser sprite positions mid-tween.
- **Implication:** Rebound **resolution** uses whatever geometry the **engine** already used for that turn when it resolved (turn payload is authoritative). The client animates **toward** those finals over time.
- **If we gate the shot on shooter-only:** On screen, teammates may still be **mid-tween** at release. Either we **accept** a display-vs-abstract-sim gap, or we later push **release-time** positions into resolution (heavier SS&S). Worth an explicit decision when implementing shot gating.

### 11.4 Fast breaks

**More event- / key-player-based** in many paths (e.g. burst awaits outlet receiver; shot flow keys off shooter or parallel trailers with early tween stops). Not one global `Promise.all` for every player—**per-sequence** rules in `fastBreak.js` and related code.

### 11.5 Press / traps (FCP / HCT)

**Same as HCO** in practice: shared skeleton / step loop uses **offense-gated** step progression (§11.2). Same pass vs no-pass and **shot** caveats as §11.2 (shooter-only shot still a future change).

### 11.6 Free throws & side inbounds (SIPs)

**Default:** Animate like HCO — wait for setup positions unless a given path keys off one player (verify per handler when auditing).

### 11.7 Baseline inbounds (BIPs)

**For now:** Like HCO. **Future:** Possible **dynamic** BIP when offense is in fast-break mode (not in scope for AG v1).

### 11.8 OREB turns

**Directionally action-based:** Advance on putback shot, kickout pass, or analogous **key action**—verify each path in rebound / OREB animation routing (`ballManager.js`, etc.).

### 11.9 Turn-type checklist (routing / `current_turn`)

**Primary reference:** `docs/docs_1_systems/05_GP_Supporting_Systems/Turn_by_Turn_System.md` (Bucket 1 examples).

**Types commonly used for gameplay animation routing include:**

| Bucket | Examples |
|--------|----------|
| Half court / pressure | `HCO`, `FCP`, `HCT` |
| Transition | `FAST_BREAK` |
| Dead-ball / special | `FREE_THROW`, `OREB` |
| Inbound | `BASELINE_INBOUND`, `SIDE_INBOUND` |
| Flow interrupt | `TIMEOUT` |

**Not the same axis:** `result_type` values (`MAKE`, `MISS`, `FOUL`, `STEAL`, `BLOCK`, `CHARGE`, `DEAD BALL`, …) are **outcomes** carried inside flows—they matter for animation choice but are not a parallel “turn type” list.

**Broader index (not a full enum):** `docs/docs_1/05_Gameplay_Systems.md`.

### 11.10 Design principle (AG + gating)

- Prefer **one gate per step** (“we advance when \_\_\_ completes”) and classify everyone else as **ambient** unless the play truly requires synchronization.
- **Universal AG** first; if HCO shot gating changes, treat **rebound/coords story** as part of the same ticket or an explicit follow-up so art direction and sim truth stay discussable.

---

## 12. Work plan — AG-based movement (implementation)

**Milestone name:** AG v1 — per-player movement speed from effective AG  
**Explicitly out of scope** for this milestone: HCO **shooter-only** shot gating (§11.2–11.3), dynamic/non-skeleton movement, reintroducing user **animation-speed presets** (compose with helper in a later milestone).

### 12.0 Success criteria

- Every tween that derives duration via **`getPlayerDuration`** (and **`getPlayerDurationUncapped`** if still used) uses **per-player** speed from **effective AG** + **BH 5%** rule when applicable.
- **AG 50** at full energy feels close to **today’s ~450 px/s** global baseline (tune `speedBase` / `speedSlope` in one place—no accidental wholesale speed shift).
- **`window.__GAME_SPEED`:** Document chosen rule in code comments—either **replace** the per-player px/s result, or **multiply** the AG-derived speed (align with eventual clock sync when presets return).

### 12.1 Tasks (ordered)

| Step | Task | Primary files / notes |
|------|------|----------------------|
| **1** | Add pure **`agToSpeedPxPerSec(ag, { isBallHandler })`**: linear map, no AG cap; apply **×0.95** when `isBallHandler`; missing AG → **50**. Export constants (`SPEED_BASE`, `SPEED_SLOPE` or equivalent) with comment: tune so median roster ≈ legacy feel. | New module e.g. `FrontEnd/static/js/phaser/utils/playerMovementSpeed.js` (or `animation/movementSpeed.js`) |
| **2** | Add **`getEffectiveAgilityForMovement(sprite, scene)`** (or similar): read `attributes.AG` from **`sprite.attributes`** if present; else find player in **`scene.simData?.players`** by `sprite.playerId` / `player_id`; normalize string ids. Optional dev **`console.warn`** if still missing. | Same module or `turnAnimation.js` adjacency; **optional:** attach `attributes` in `loadPhaserPlayers.js` / `createPhaserPlayer.js` from `player` object to reduce lookups |
| **3** | Extend **`getPlayerDuration(sprite, targetX, targetY, isTransition, opts?)`**: compute `speedPxPerSec` via (1)(2); pass **`isBallHandler`** when caller knows ball-handler role for that tween (see 12.2). Feed speed into existing **`getDurationFromDistance`** (may need overload: `speed` argument already there). | `FrontEnd/static/js/phaser/animation/turnAnimation.js` |
| **4** | Audit **call sites** that bypass **`getPlayerDuration`** but use hardcoded player speeds or duplicate duration math; route through helper where the movement is a **player jog** (not ball arc). Prioritize: `fastBreak.js`, other `animation/*.js` grep for `getPlayerDuration`, `DEFAULT_PLAYER_SPEED`, `getPlayerSpeed`. | Repo-wide grep; fix stragglers |
| **5** | **Unit tests** for `agToSpeedPxPerSec`: monotone AG; AG 0 / 50 / 100 / 120 extrapolation; BH vs off-ball ~5%; default 50. Optional: one test that **duration** decreases when AG increases for fixed distance (mock distance fn). | e.g. `FrontEnd/static/js/phaser/utils/playerMovementSpeed.test.js` or existing test runner pattern in repo |
| **6** | **Manual QA:** Fast break trailers, HCO multi-step (pass + cut), FCP/HCT step, DREB outlet. Note any step that should pass **`isBallHandler: true`** but doesn’t yet. | Playtest checklist in PR |
| **7** | **Phase B/C (post-ship):** If HCO feels too noisy or too subtle, add optional **`movementContext`** scalar (§6) without forking the AG curve. | Same speed module + call sites |

### 12.2 Ball-handler flag — when to set `isBallHandler: true`

- **Default `false`** when unknown (off-ball cuts, most defense).
- **`true`** for tweens where that sprite **has the ball** for that movement **or** is unambiguously the **designated ball-handler step** (bring-up, iso drive step) — align with `hasBallAtStep` / `currentBallOwnerRef` / turn roles where available.
- **Passes / shots:** Pass flight uses **ball** duration, not player `getPlayerDuration` for the ball in air; apply BH penalty to **handler’s** movement tweens only.

### 12.3 Follow-on tickets (not AG v1)

- **Done (client):** **Offense-gated skeleton steps** — step advances on all offensive tweens (+ pass choreography); defensive completion does not block. Implemented in `turnAnimation.js` and `ShotAnimationSystem.js` (Feb 2026).
- **§11.2 shot gating:** Shooter-only advance to `shootBall`; coordinate with rebound/display SS&S (still open).
- **Animation speed presets:** Multiply vs baseline + game clock sync.
- **BH attribute** modifier on top of flat 5%.
