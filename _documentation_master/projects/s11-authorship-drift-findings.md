# §11 findings — development vs authorship

**Date:** 6 August 2026 (reframed same day)  
**Question doc (closed as TB issue):** `s11-development-vs-authorship.md`  
**Living home:** `10_Players_Systems/Player_Development_System.md` → Reshape vs grow  
**Repro:** `scripts/s11_authorship_drift_audit.py` → `tmp/s11_audit/{summary,results}.json`

## Code answers (verified against `player_development.py` + TB Apply)

1. **What does development move attributes toward?**  
   Each offseason: shape α-blends toward `position_profile(training_position)` scaled to ladder RT (`OFFSEASON_ATTRACTOR_ALPHA = 0.55`), then a full level rescale so RT hits  
   `_compress_rt(jh_anchor × ladder × coaching_f × potential_factor)`.  
   It does **not** target the player's own generation-time or authored attribute vector.  
   **Archetype string is not the attractor** — the attractor is the position weight profile for `training_position` (defaulting to `position_intent`).

2. **`entry_tier` / `potential_factor`:**  
   - `entry_tier` — categorical tier → scalar `jh_anchor` via `JH_ANCHOR_BY_TIER`.  
   - `potential_factor` — one career-static scalar (±15%), uniform on the RT target.  
   Neither is per-attribute.

3. **Target source:** position/tier/year profile norms (`position_profile`), not the player's own attributes. Homogenisation is league-wide, not authorship-specific.

4. **Is archetype recomputed after generation?**  
   No. Apply carries `meta.archetype` and `position_intent` from the inherited clone; attribute/height edits recompute `position_ratings` only. Portrait classification is separate and does not rewrite development targets. `development` / `entry_tier` / `potential_factor` are never re-rolled by Team Builder edits.

5. **Scope (per brief):** development + TB Apply only — not audited further.

**In-season inputs:** `develop_one_offseason` does not read minutes, usage, or box scores. The only in-season hook is `season_allocation` → `coaching_f`. Live `finish_season` calls `_coaching_accumulator_for_player`, which is **hardwired to `None`** today → `f ≡ 1.0` for everyone. Full game weeks cannot change the retention metric under current code.

## Method

| Item | Choice |
|---|---|
| Base team | **Couer d'Alene** (`69a6fcb68d2c56aa82e48ac0`) — attr total **5504** = league p50; height sum **870** vs league p50 **875**. Not South Lancaster. |
| Arms | control (zero-edit Establish), realistic (moderate away-from-profile swaps within capped budget on 6 scholarship players), extreme (Caleb McNeil → 6'2" / RB 90 / intent C) |
| Seed | `20260806`, identical coaching (`season_allocation=None`) |
| Apply | `apply_diffs_to_inherited_roster` + `build_fpd_docs_from_players` (same as `replace_slot_roster`) |
| Develop | `develop_rollover(..., season_allocation=None)` — the call `finish_season` makes today |
| Scratch | In-memory FPD only; pool read-only. No franchise rows written (no local mongod available). |
| Track | Original 15 to graduation; seniors at t0 never develop (retention 1.0 by definition — excluded from developed mean) |

**Retained deviation** = profile-shape L2 distance at graduation ÷ distance at t0 (post-Apply).

## Measurement

### Developed-player mean retention at graduation

| Arm | t0 mean profile-dev | Mean retention (n=10 developed) |
|---|---:|---:|
| control | 0.121 | **0.147** |
| realistic | 0.123 | **0.150** |
| extreme | 0.134 | **0.147** |

All three are **well below 50%** — and they match each other. The TB threshold said "option space applies"; the match across arms said the option space was aimed at the wrong victim.

### Curves (mean retention among original players still on roster)

| After N offseasons | control | realistic | extreme |
|---|---:|---:|---:|
| 1 | 0.35 | 0.36 | 0.35 |
| 2 | 0.15 | 0.15 | 0.15 |
| 3 | 0.08 | 0.08 | 0.08 |

Matches `(1 − 0.55)^N` — one year of authorship is mostly gone by the second offseason; a freshman is unrecognisable as authored by senior year.

### Extreme focus (Caleb McNeil, SO → SR in 2 develops)

| | |
|---|---|
| t0 | ht 74, RB 90, intent C, profile-dev **0.359**, RT 48 |
| graduation | profile-dev **0.051**, retention **0.142**, mean \|Δattr\| **53.8**, ΔRT **+35** |

Authorship is erased as a *shape*; RT still climbs the ladder (level close), so the user sees a better-rated player who no longer matches what they built.

### Diagnostic

Retention **does not fall as initial deviation grows** (corr(dev₀, retention) ≈ 0.05–0.07 within each arm). Extreme Caleb retains ~14% — same as control Caleb (~13%) despite 2× the starting deviation. That is exactly a **proportional α-blend toward a fixed position profile**: fraction retained depends on develop count, not on how far you authored. Absolute point drift scales with authorship; percent retained does not.

Control ≈ realistic ≈ extreme on the retention curves → authorship is not a special case. Development does this to everyone; Team Builder merely lets the user start farther from the attractor.

## Verdict (reframed 6 August 2026)

The measurement answered the question it was asked — and then overturned the framing.

**Authorship is not the victim. Individuality is.** Control ≈ realistic ≈ extreme means the α-blend homogenises the whole league the same way. Team Builder did not create the force; it made it observable (third instrument finding after the empty defenses cache and the 443 in-loop DB writes).

Original TB option space is mostly **dead**:
- Re-run archetype classification — blend targets `position_profile(training_position)`, not archetype.
- Re-derive `potential_factor` — scalar on magnitude, not the blend target.
- Freeze authored attrs — still the wrong special case.

The live question is simulation design: **reshape vs grow**, plus whether α was chosen against any career-length criterion, plus why `_coaching_accumulator_for_player` is hardwired to `None`. Owned by [`Player_Development_System.md` → Reshape vs grow](../10_Players_Systems/Player_Development_System.md#reshape-vs-grow--open-simulation-design). §11 question doc closed as a TB issue with a pointer there.

