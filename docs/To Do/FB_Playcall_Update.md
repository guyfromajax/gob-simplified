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
4. **Decouple** “we go to `FAST_BREAK` on this DREB” from `defense_release_list`. Use a **dedicated FB eligibility roll** (reuse or align with `get_fast_break_chance` / team `fast_breaks` — product decision).  
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
   - Roll or compute **whether** a defensive rebound on this miss would lead to **FAST_BREAK** vs **HCO** using team settings / `get_fast_break_chance` (align with existing `phase_resolution` steal/DREB FB chance semantics — **document the chosen rule** in code comments).  
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

1. **Exact FB eligibility formula** for DREB (reuse `get_fast_break_chance` only, or combine with defense `fast_breaks` release odds, or separate sliders).  
2. **Covert release select fails** (no `rp`): HCO vs retry vs force PG release.  
3. **`thirty_two`**: same as RR (no release) until spec says otherwise.  
4. Whether **offense get-back** should differ by play type (probably no for v1).

---

## Review checklist

- [ ] Single roll for DREB play key per possession.  
- [ ] Covert-only release + coords + `last_release_player`.  
- [ ] RR/32 can FB without release list.  
- [ ] Resolver does not re-roll when pending key set.  
- [ ] Steal FB path untouched.  
- [ ] Tests and docs updated; temp flags removed when aligned.
