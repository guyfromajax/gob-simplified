# Fast Break playcall at shot attempt — implementation plan

This document describes how to resolve **which DREB fast-break play** (Covert Release vs Rim Runner vs future `thirty_two`) **on the shot attempt** (same step as today’s release/get-back geometry), **gate Covert-only release behavior** on that playcall, **decouple fast-break eligibility** from “someone released,” and how **`resolve_fast_break_logic`** should consume a **precomputed** key without rolling twice.

**Related code today**

| Area | Role |
|------|------|
| `BackEnd/models/shot_manager.py` | On every shot, computes `defense_release_list` via `FastBreakTrigger.DEFENSE_RELEASE_CHANCES` + `covert_release.select_covert_release_position`; on DREB sets `next_play_type = "FAST_BREAK"` **only if** `defense_release_list` non-empty; sets `game_state["last_release_player"]`. |
| `BackEnd/engine/phase_resolution.py` — `resolve_fast_break_logic` | Calls `play_key_for_fast_break_entry(rebound)` **again**; branches Rim Runner vs Covert. |
| `BackEnd/constants/fast_break_play_types.py` | `play_key_for_fast_break_entry`, play keys. |
| `BackEnd/engine/rim_runner_fast_break.py` | Still reads `last_release_player` in the “else” outlet branch (“Covert release receiver or fallback PG”). |
| `BackEnd/engine/fast_break_trigger.py` | `DEFENSE_RELEASE_CHANCES`; legacy `can_trigger_from_dreb` ties `can_trigger` to non-empty release list. |

**Problem summary**

1. **Play key is chosen one turn late** vs **release player is chosen on the shot** → Rim Runner inherits Covert-shaped release state.  
2. **FB next play requires a release** → Rim Runner (and future plays) cannot trigger FB without Covert geometry.  
3. **Double randomness risk** if play key is rolled on shot turn and again in `resolve_fast_break_logic`.

---

## Goals

1. **Single decision point** for DREB FB **play key** when the offense is about to lose possession on a miss → DREB → FB (same “moment” as today’s positioning block in `shot_manager`).  
2. **Execute Covert release pipeline** (select position, `defense_release` IDs, `defense_release_coords`, `last_release_player`) **only if** `fast_break_play == covert_release`.  
3. For **Rim Runner** and **`thirty_two`** (until specified otherwise): **no** Covert release list, **no** release coords, **no** `last_release_player`; defense treats all lineup spots as rebounders for that shot’s geometry (unless a future spec adds a different rule for 32).  
4. **Decouple** “we go to `FAST_BREAK` on this DREB” from `defense_release_list`. **Done:** single `fast_break_probability_from_slider(fast_breaks)` on shot / FT DREB; see `Fast_Break_System.md`.  
5. **`resolve_fast_break_logic`** uses **stored** play key; **no second roll** for DREB outlet.  
6. Remove redundant branches and outdated coupling to reduce bloat.

---

## Step-by-step implementation plan

### Phase A — State contract (game_state + turn payload)

1. **Add** a persistent field, e.g. `game_state["pending_dreb_fb_play_key"]` (string: `covert_release` \| `rim_runner` \| `thirty_two` \| unset).  
   - Set **only** when resolving a miss that ends in DREB and the engine commits to **next_play_type `FAST_BREAK`**.  
   - **Clear** after `resolve_fast_break_logic` consumes it (or when possession resets / quarter ends), to avoid carryover bugs (same pattern as `last_release_player`).

2. **Optional (recommended):** mirror on the MISS turn `result` for debugging and tests, e.g. `pending_dreb_fb_play_key` or `fast_break_play_resolved`, so golden logs and frontend can assert play without reading `game_state` only.

3. **Steal-entry FB:** unchanged — still `play_key_for_fast_break_entry(False)` → `after_steal`; **do not** set `pending_dreb_fb_play_key`.

### Phase B — Shot attempt (`shot_manager.py`) ordering

**Intent:** one clear pipeline per shot (before make/miss branch splits that need different result fields):

1. **Offense get-back** (existing): `offense_getback_list`, rebounders, coords — **unchanged** unless product wants get-back to depend on play type (defer unless requested).

2. **DREB fast-break eligibility (new / decoupled)**  
   - Implemented: DREB uses rebounding team `fast_breaks`; steals use stealing team `aggression` (`fast_break_probability_from_slider` in `shared.py`).  
   - This boolean **must not** depend on `defense_release_list`.

3. **If not eligible for DREB FB**  
   - `defense_release_list = []`, no release coords, `last_release_player = None`, do not set `pending_dreb_fb_play_key`.  
   - On actual DREB branch: `next_play_type = "HCO"` (current behavior when list empty).

4. **If eligible for DREB FB**  
   - Call **`play_key_for_fast_break_entry(True)` once** → `fb_play_key`.  
   - Store: `game_state["pending_dreb_fb_play_key"] = fb_play_key`.  
   - **If `fb_play_key == covert_release`:** run **today’s** Covert path: `DEFENSE_RELEASE_CHANCES` roll + `select_covert_release_position` → `defense_release_list`, stats, `good_release_flag`, `_calculate_release_coordinates`, populate `result["defense_release"]`, `defense_release_coords`, and on DREB commit `last_release_player`.  
   - **If `fb_play_key` is `rim_runner` or `thirty_two`:** force **`defense_release_list = []`**, skip release coord updates, `last_release_player = None`, `result["defense_release"] = []`, `defense_release_coords = {}` (or omit); **`defense_rebounders` = full lineup** for rebound resolution.  
   - On DREB: `next_play_type = "FAST_BREAK"` whenever **eligible**, regardless of release list.

5. **MAKE / foul / block branches** that today attach `defense_release` / coords: apply the **same** rule — only populate release arrays/coords when **Covert** was selected **and** eligibility was true. If miss never happens, pending key might still be set incorrectly — **only set `pending_dreb_fb_play_key` when you also know the turn will end with DREB→FB** (see Phase C).

**Refinement:** `pending_dreb_fb_play_key` should be set only when the **miss + DREB + FB** path is actually taken, not on every shot that rolled “FB eligible,” to avoid stale keys on makes. Practical approach: compute and store **candidate** play key only inside the **miss → DREB** branch right before setting `next_play_type`, **or** set on shot then **clear** on make — simplest is **defer** play key assignment to the **DREB resolution block** (same function, still “shot attempt step” in code terms) where `next_play_type` is chosen.

### Phase C — DREB commit block (`shot_manager.py` ~DREB handling)

Today: `next_play_type = "FAST_BREAK" if defense_release_list else "HCO"`.

**Replace with:**

1. If `force_foul_after_dreb`: unchanged.  
2. Else if **FB eligible** (from Phase B; may need to recompute or store a boolean on `game_state` at shot time such as `dreb_fb_eligible` cleared after use):  
   - `next_play_type = "FAST_BREAK"`.  
   - Set `pending_dreb_fb_play_key` = result of **`play_key_for_fast_break_entry(True)`** if not already set this possession, **or** use value computed on shot — **single roll**.  
   - If Covert: ensure `last_release_player` set from release list; if RR/32: `last_release_player = None`.  
3. Else: `next_play_type = "HCO"`, clear pending key and release state.

**Recommended pattern to guarantee one roll:** On the **miss** path, when entering DREB logic, if FB eligible:

- If `pending_dreb_fb_play_key` is missing: `pending_dreb_fb_play_key = play_key_for_fast_break_entry(True)`.  
- Then if Covert and release list empty (failed select): either **downgrade to HCO** or **retry select** — product call (document).  
- If RR/32: do not require release list.

Alternatively: compute play key **once** at start of miss handling and store on `game_state` until DREB block consumes it.

### Phase D — `resolve_fast_break_logic` (`phase_resolution.py`)

1. For DREB outlet (`rebound` True): read `fb_play_key = game_state.pop("pending_dreb_fb_play_key", None)` or `.get` + clear after branch.  
2. **If missing** (old saves, tests): fallback `fb_play_key = play_key_for_fast_break_entry(True)` once for backward compatibility.  
3. **Do not** call `play_key_for_fast_break_entry(True)` when pending key present.  
4. Increment `fb_plays[fb_play_key]["A"]` and rest of scouting as today.  
5. Branch Rim Runner vs Covert vs 32 as today.

### Phase E — Rim Runner (`rim_runner_fast_break.py`)

1. Remove dependency on **`last_release_player`** for outlet ball-handler selection: RR should use **only** rebounder / PG / SG / rim-runner rules already in the first branches.  
2. Collapse the **“Covert release receiver or fallback PG”** else branch to **fallback PG** (or explicit SG/PG outlet rules only).  
3. Stop clearing `last_release_player` in three places if it is never set for RR — optional cleanup.

### Phase F — Frontend / animator

1. Ensure MISS payloads for RR/32 **still** include consistent **`offense_getback`**, rebounder coords, and empty **`defense_release`** where appropriate so animations do not assume a release ID.  
2. Audit `BackEnd/models/animator.py` / `capture_fast_break_animation` for assumptions that **every** DREB FB has release coords.  
3. Audit Phaser `fastBreak.js` / rebound flow for empty `defense_release`.

### Phase G — Tests

1. Update **`tests/test_fast_break_outlet_pass.py`** and **`tests/test_fast_break_comprehensive.py`** (and any test that patches `play_key` or assumes FB iff release).  
2. Add tests: **FB eligible + RR** → `next_play_type FAST_BREAK`, empty `defense_release`, no `last_release_player`.  
3. Add tests: **FB eligible + Covert** → release populated, pending key consumed once in resolver.

### Phase H — Docs and temporary flags

1. Update **`Fast_Break_System.md`** and **`FB_Update_Brief.md`** when implementation lands.  
2. Remove **TEMP** “100% Rim Runner” in `fast_break_play_types.py` when product restores mix (or gate behind settings).

---

## Code removal / de-bloat (after migration)

| Item | Action |
|------|--------|
| Second `play_key_for_fast_break_entry(True)` when pending key exists | **Remove** from `resolve_fast_break_logic` for DREB path when pending set. |
| `last_release_player` reads in `rim_runner_fast_break.py` | **Remove** Covert-style else branch; keep PG/SG/outlet logic only. |
| Comments / logs stating DREB FB requires release | **Update** to “Covert only.” |
| `FastBreakTrigger.can_trigger_from_dreb` | **Deprecate or rewrite** so `can_trigger` is not synonymous with non-empty release list if anything still calls it; grep callers first. |
| Redundant `game_state["last_release_player"] = None` in RR after no setter | **Trim** if noise. |
| Any frontend branches assuming `defense_release.length > 0` for FB | **Delete** or branch on `fast_break_play` / payload flag. |

---

## Execution order (recommended)

1. Introduce `pending_dreb_fb_play_key` + resolver read/pop + fallback (no behavior change if fallback always matches old random).  
2. Move play key assignment to DREB commit; wire Covert-only release.  
3. Add FB eligibility independent of release list; adjust `next_play_type`.  
4. Simplify Rim Runner outlet branch; fix animator/frontend.  
5. Tests, then delete dead code and temp 100% RR if desired.

---

## Open product decisions (resolve before coding)

1. **Exact FB eligibility formula** for DREB (see `fast_break_probability_from_slider` + `SLIDER_TO_FAST_BREAK_PROB`).  
2. **Covert release select fails** (no `rp`): HCO vs retry vs force PG release.  
3. **`thirty_two`**: same as RR (no release) until spec says otherwise.  
4. Whether **offense get-back** should differ by play type (probably no for v1).

---

## RR Animation (Rim Runner — post-outlet sync)

**Terminology:** One backend `FAST_BREAK` turn resolves everything after DREB. The frontend **Phase 1** (`animateRimRunnerBurstPhase` + optional outlet pass) animates **`rim_runner_burst_phase`**. **Phase 2** branches only on **final** `result_type` (shot vs generic `animateDefensiveStop`). Intermediate sim steps (burst open, IQ read, pass vs hold-up) are **not** separate animation beats today.

### Phase 0 — Locked spec (source of truth)

**Status:** captured below for implementation; treat this subsection as authoritative for RR **post-outlet / lane** animation until explicitly revised. **Grid:** HOME orientation; all **x** moves **toward the offensive basket** (+x home offense, −x away offense). **Court clamps** apply everywhere (e.g. x ∈ [4, 97], y per existing rules unless OOB exception).

| # | Scenario | Animation intent (concise) |
|---|----------|----------------------------|
| **1** | Outlet receiver **does not** pass to RR (hold-up) | BH **holds**. All **other** players **+10** x toward basket; then BH **and** everyone **+10** x again; then transition to **HCO**. |
| **2A** | Pass to RR — **RR receives** | Pass **targets a spot 6** grid x **ahead of RR** (attacking direction). **Ball + RR** start **together** toward that spot (speeds aligned for **in-stride** catch). **Other 8** players **+6** x toward basket. RR **catches**, continues into shot; **shot defender** to standard FB spot **between RR and rim**; then **existing FB shot** flow (result + all others still moving toward basket as today). Tune durations/easing in implementation. |
| **2B** | Pass — **defender intercepts** | Same **6-ahead** target for ball/RR start; **interceptor** moves into **passing lane** to intercept. Then **standard steal** rules: **TO passer**, **STL interceptor**, possession change, next **HCO** for new offense. Announce **“Interception!”** with **interceptor headshot**. |
| **2C** | Pass — **batted OOB** | Same setup as intercept through attempt point. Ball **sticks on interceptor 500 ms** (0.5 s), then **bounces** to **y = 1** if defender **y > 24**, else **y = 51**; **x = defender x** at interception point (OOB read for player). **No possession flip:** next is **SIDE_INBOUND**, **same** team on offense as the fast break turn (matches backend: `possession_flips: false`, `next_play_type: SIDE_INBOUND`, `offense_team_id` = FB offense). |

**Outlet pass (rebounder → outlet receiver):** Already animated in Phase 1 when not denied / not dribble-outlet; unchanged unless spec says otherwise.

**Implementation phases** (payload → `fastBreak.js` structure → scenarios 1 → 2A → 2B → 2C → outlet denied → QA → `Fast_Break_System.md`): see assistant work plan; track delivery via task list below.

### Phase 1 — Kickoff (payload contract)

**Goal:** one authoritative mapping from **sim branch → turn JSON** so the frontend never guesses geometry or identity. Phase 1 is **done** when the table below is filled, gaps are implemented or explicitly “derive client-side,” and one sample payload per branch is saved (fixture or test).

**Fastest path to sample JSON:** from repo root, with your normal Python env (`pip install -r requirements.txt` if needed), run `python scripts/dump_rim_runner_turn_contract.py` (this repo: `.venv/bin/python scripts/dump_rim_runner_turn_contract.py`). It writes `tests/fixtures/rim_runner_contract/*.json` (outlet denied, hold-up, open shot, completion shot, bat OOB, intercept). The Phase 1 table below references these files—or use **DevTools → Network** on a turn-by-turn game if you prefer live traffic (same shape).

**Do this in order:**

1. **`turn_registry` pass** — For each Rim Runner resolution path in `resolve_rim_runner_fast_break`, note **`result_type`**, **`next_play_type`**, **`possession_flips`**, top-level IDs (`offense_team_id`, `stealer_id`, `victim_id`, etc.), and **`roles` / `rim_runner_burst_phase`** presence. Paste or link **one real JSON example** per path (hold-up, open shot, no-def shot, intercept steal, bat OOB, outlet denied early return).

2. **Map to Phase 0 scenarios** — Tie each path to **§ Phase 0 row (1, 2A, 2B, 2C)** or “outlet denied” / “outlet OK + shot other branch”. Mark **M** if the client can derive all animation inputs from existing fields; mark **G** if something is missing.

3. **Close gaps (minimal backend)** — Only add fields when derivation is fragile or duplicate logic:
   - **Hold-up vs outlet-denied vs generic stop:** all can be `DEFENSIVE_STOP`; distinguish with **`rim_runner_hold_up`** (new bool) **or** stable **`text`** / existing **`rim_runner_outlet_failed`** + **`rim_runner_fb_open`** / **`rim_runner_correct_read`** (document the rule the client must use).
   - **Lane catch point (2A/2B/2C):** spec says **6 x ahead of RR** at pass start — either document **client formula** (`rr.coords`, `roles.is_away_offense` / `rim_runner_burst_phase.is_away_offense`, clamp) **or** add **`roles["rim_runner_lane"] = { "catch_x", "catch_y", "passer_id", "receiver_id", "defender_id" }`** once per sim.
   - **Bat OOB bounce:** add **`rim_runner_bat_oob_from: { "x", "y" }`** (interceptor grid at tip) if sprite positions after Phase 1 don’t match sim coords.
   - **Intercept:** steal payload already has **`stealer_id`**, **`victim_id`**; confirm **`primary_def`** identity matches **`stealer_id`** in `roles`/lineup and document.

4. **Frontend stub** — Read-only: list the **branch `if` order** in `runFastBreakSequence` (after outlet) that will consume the contract; no full animation until contract row is **M** or gap fields exist.

5. **Review gate** — Short review: “Phase 1 approved” = table complete + samples checked + agreed derive-vs-server rules.

**Contract (sample payloads in `tests/fixtures/rim_runner_contract/`):**

| Phase 0 | Backend branch | `result_type` (sample) | Distinguishing flags / IDs | Notes |
|--------|-----------------|------------------------|----------------------------|--------|
| Outlet denied | Early return | `DEFENSIVE_STOP` | `rim_runner_outlet_failed: true`, `next_play_type` HCO | `01_outlet_denied.json` |
| **1** Hold-up | `not pass_attempted` | `DEFENSIVE_STOP` | `rim_runner_fb_open`, `rim_runner_correct_read`, text “holding up”; no lane-pass attempt | `02_hold_up.json` |
| **2A** RR shot (open lane) | `fb_open` + `resolve_shot` | `MAKE` / `MISS` / `BLOCK` | `fast_break`, `fast_break_play: rim_runner`, `roles` incl. `rim_runner_burst_phase`, `rim_runner_id`, BH outlet coords | `03_open_lane_shot.json` (stubbed shot → `MISS`) |
| **2A** RR shot (no primary def) | catch-and-shoot branch | `MAKE` / `MISS` / `BLOCK` | `roles.defender_count` 0 | No fixture yet — add to script if needed |
| **2B** Intercept | `intercept_score > tier_hi` | `STEAL` | `rim_runner_interception: true`, `stealer_id`, `victim_id`, `next_play_type` HCO | `06_intercept_steal.json` (stubbed `resolve_turnover_logic` for stable IDs) |
| **2C** Bat OOB | `intercept_score > tier_mid` | `DEAD BALL` | `rim_runner_bat_oob: true`, `possession_flips: false`, `next_play_type` SIDE_INBOUND | `05_bat_oob.json` — `time_elapsed` may be recomputed by `apply_fast_break_cg_time` when animations are empty |
| Completion shot | crowded lane + shot | `MAKE` / `MISS` / `BLOCK` | Same as open but burst lost; higher shot-threshold path | `04_completion_shot.json` (stubbed shot → `MAKE`) |

**Derive vs gap (quick pass):** Lane catch geometry lives in `roles.rim_runner_burst_phase` / BH–RR coords; client can derive “6 ahead” from that + `is_away_offense` until we add explicit `rim_runner_lane`. Bat OOB bounce coords are still **G** if sprites don’t match sim — consider `rim_runner_bat_oob_from` later.

### Alignment check (your framing + gaps)

- **Passes:** There are **two** distinct passes in many RR possessions:
  1. **Outlet pass** — rebounder (or dribble-outlet) → outlet receiver — already in Phase 1 when not denied.
  2. **Lane pass** — ball handler (outlet receiver) → rim runner when the sim attempts the pass into the lane (open path, intercept path, or completion-to-shot path). This second pass often needs **explicit** animation wiring; today Phase 2 may jump straight to shot/stop without a visible BH→RR pass.
- **Outcomes after a lane pass is attempted:** Yes — animate toward **RR shot** (MAKE/MISS/BLOCK), **defender intercept / steal** (`rim_runner_interception`, turnover-style), or **batted OOB** (`rim_runner_bat_oob`, DEAD BALL → SIP). Each may deserve distinct motion/FX vs a single generic defensive stop.
- **Pass not attempted (hold-up):** Backend returns **DEFENSIVE_STOP** (“holding up”) → next **HCO**. We should add a **`step 0` / lead-in** animation before the next HCO turn so the break doesn’t feel like a hard cut. No separate sim turn today.
- **Outlet contest failed** (`rim_runner_outlet_failed`): RR FB dies → **HCO**. Phase 1 may still run burst/outlet tweens in some cases; we should **tighten** motion (e.g. cut outlet short, defender pressure, settle) so “outlet denied” reads clearly before HCO.

### Task list (flesh out / check off as we align)

- [x] **Phase 0 spec** — scenarios Table + bat OOB / SIP / possession captured in **Phase 0 — Locked spec** above.
- [x] **Phase 1 contract samples** — `tests/fixtures/rim_runner_contract/*.json` via `python scripts/dump_rim_runner_turn_contract.py` (`.venv`); table above aligned to fixtures.
- [x] **Phase 1 close-out (stub):** `classifyFastBreakPhase2` + explicit Phase 2 ladder in `FrontEnd/static/js/phaser/animation/fastBreak.js` (steal/bat_oob/hco_settle share `animateDefensiveStop` until TODO sequences land). Optional `07_no_primary_def` fixture still open.
- [x] **Lane pass (v1):** `shouldAnimateRimRunnerLanePass` + `animateRimRunnerLanePass` in `fastBreak.js` — parallel RR tween + `runPass` to catch grid ~`rr + 6` toward basket, before shot / foul / steal / bat OOB. Tune timing vs spec (“in-stride”) as needed.
- [ ] **RR shot:** Ensure open-lane and “completion after crowded lane” paths both land through `animateFastBreakShot` / `WithStopper` with correct **shot_spot** / roles.
- [ ] **Intercept (steal):** Dedicated or extended sequence (defender picks ball / direction) vs generic `animateDefensiveStop`; align with `resolve_turnover_logic` payload.
- [ ] **Batted OOB:** Distinct from intercept and from covert stop — ball trajectory + inbound hint; align with `SIDE_INBOUND` / `rim_runner_bat_oob` announcement path.
- [ ] **Hold-up (no lane pass):** Add **`step 0`** — RR/BH slow or stop, defense converges — before transitioning to **HCO** setup.
- [ ] **Outlet denied:** Improve Phase 1 or add **outlet-fail** branch — shorten/cancel pass, show pressure, then HCO without looking like a full successful outlet.
- [ ] **State machine / `gameStateMachine`:** Confirm `FastBreak` → `HalfCourt` transitions match each outcome (stop, shot foul, turnover).
- [ ] **Docs:** Update `Fast_Break_System.md` Rim Runner subsection once animation phases are fixed.

---

## Review checklist

- [ ] Single roll for DREB play key per possession.  
- [ ] Covert-only release + coords + `last_release_player`.  
- [ ] RR/32 can FB without release list.  
- [ ] Resolver does not re-roll when pending key set.  
- [ ] Steal FB path untouched.  
- [ ] Tests and docs updated; temp flags removed when aligned.
