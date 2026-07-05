# Coord-Consumer UESS Audit — `player.coords` vs render

**Question:** which game-logic consumers decide from `player.coords` (animator row-end, set by `apply_coords_from_animations_list`) instead of the emitter's rendered coord — the same defect that mis-scored 2PT/3PT classification? (2026-07-05, 3 parallel traces + probes.)

## Root cause (one line)
`ShotManager.resolve_shot` and rebound logic read `def_lineup[pos].coords` / `player.coords` = **animator row-end**, which diverges from the emitter's **interrupted** shoot-step render coord (§9.5: only the gate/shooter reaches full destination; others render mid-move). The shipped classification fix synced **only the shooter** (`_uess_terminal_shoot_coord` → `roles["shot_spot"]`); **defenders and rebounders were left on the divergent animator coords** → mixed-frame decisions.

## Systemic question: RESOLVED FAVORABLY
`sync_lineup_coords_from_turn` (shared.py:3589-3609) writes the **emitted** `animation_steps[-1].end.coords` and it **takes precedence** over animator finals for migrated turns → `final_coords`/BIP/SIP/HCO carry-forward propagate the render coord. **The desync is per-shot within a turn, NOT compounding across turns.** Only leak: legacy turns with no `animation_steps` (already logged, shared.py:3616).

## Ranked holes (measured where cheap)

| # | Risk | Location | Decision flipped | Coord read | Impact |
|---|---|---|---|---|---|
| 1 | ✅ **FIXED** | shot_manager.py:773/803 (HCO-motion contest) | contested↔uncontested → block path + shot quality | ~~defender `.coords` = animator row-end~~ → now emitted render coord | **~6% per-defender flip; ~2% aggregate `has_contest` drop** (over-contest removed). Fixed 2026-07-05 via `_uess_sync_emitted_shot_coords` (syncs ALL players to emitted shoot-step coords before resolve_shot; HCO/FT/FCP). Regression-clean. |
| 2 | ✅ **FIXED** | shot_manager.py:809-816 (Covert Release) | block never fires on contested CR | ~~STALE pre-race `def_lineup.coords`~~ → now honors CR's render-matched `roles["defender"]` | Fixed 2026-07-05: CR stamps `roles["fb_geometry_contest_resolved"]`; `resolve_shot` honors `bool(defender)` instead of the stale coord loop → block fires on contested CR. Regression-clean; `test_covert_release_drive_resolution` passes. |
| 3 | ✅ **COVERED by #1** (severity revised) | shared.py:1583/1670 (`select_rebounder_by_score`) | ~~possession~~ → individual rebounder **attribution** | candidate `player.coords` — now render-synced (selection runs inside `resolve_shot`, after #1's sync) | **Measured: ~75% individual-rebounder flip, ~0% possession flip** (box-out/team weighting is possession-stable). #1 routed selection through render-synced shoot-step coords. Bounce-step coords (agent's suggestion) are circular — post-crash positions depend on the selection. No separate fix needed. |
| 4 | ✅ COVERED by #1 | shared.py:1835 (near-bounce pool) | eligible rebounder set | `player.coords` — now render-synced | same sync covers it |
| 5 | MED-HIGH | shot_manager.py:146-162 (zone matchup) | zone contest + double-team | `zone_defender_assignments_by_step` built from animator coords (animator.py:1912) | zone HCO contest y/n |
| 6 | MED | shared.py:862 / 892 (OREB putback def / OTB foul) | putback contest / OTB foul y/n | defender `.coords` = animator/prior-turn | bounded, low-freq |
| 7 | MED | turn_manager.py:3407/5585 (zone `defense_score`) | zone defender → `player_d` | `HCO_STRING_SPOTS[shooter_spot]` (named, not coords) | margin-only |

## Immune / correct pattern (already render-synced)
- **Steal-FB (`after_steal_fast_break.py`), HCT (`dynamic_hct_shot.py`), universal FB drive-step (`fb_drive_resolution.py`)** — compute render ends once and write `player.coords = rendered ends`; contest coord == render coord **by construction**. **This is the pattern to copy.**
- **Man set-play & Final Turn contest** — assignment-based (`has_contest = bool(defender or second_defender)`), not coord-compared.
- **Cross-turn carry-forward** — render-synced (precedence rule above).
- **Bounce origin / block spot / block magnitude** — render-synced via `shot_spot`, or attribute-only.

## Fix architecture (unified)
✅ **DONE for #1:** the shipped shooter-only pre-pass was generalized to **all players** — `_uess_sync_emitted_shot_coords` (phase_resolution.py) runs the RNG-neutral emitter pre-pass once and stamps the emitted shoot-step `end.coords` onto **every** `player.coords` before `resolve_shot` (HCO/FT/FCP call sites). The contest coord loop now reads render-synced defenders. Frame-safe: `player.coords` and emitted coords are both display orientation (`_normalize_animation_coords_to_runtime_home` is a pass-through). Mirrors the Steal-FB/HCT pattern.

**NOTE — #5 is NOT covered by this:** the zone matchup reads `zone_defender_assignments_by_step` (a separate structure built from animator coords in animator.py:1912), not `player.coords`. Still open.

Separate handling:
- **#3/#4 rebounder** — relevant coord is the **post-shot pre-bounce** step (needs the outcome), not the shoot step → route rebound distances through the emitted `[bounce]` sub-step coords, not live `player.coords`.
- **#2 Covert Release** — either run `apply_coords` (currently skipped, phase_resolution.py:2028) or stop `resolve_shot` discarding `compute_fb_shot_geometry`'s render-matched contest.

**Caveat:** the pre-pass ~98% reproduces the late render (early/late context divergence, per Shot_Classification_UESS_Fix_Scope.md), so this lands ~94-98% render-synced, not exact. Same residual class as classification.

## Progress
- ✅ **#1 contest defenders** — FIXED (`_uess_sync_emitted_shot_coords`, HCO/FT/FCP). Contested-rate ~98.7%→96.7%; regression-clean.
- ✅ **#3/#4 rebounder + near-bounce pool** — COVERED by #1 (selection runs after the sync); severity revised (attribution, not possession — 0% possession flip measured).
- ✅ **#2 Covert Release block** (HIGH) — FIXED (`fb_geometry_contest_resolved` flag; `resolve_shot` honors CR's render-matched defender). Regression-clean.
- ⬜ **#5 zone matchup** (MED-HIGH) — `zone_defender_assignments_by_step` built from animator coords (animator.py:1912), not `player.coords`. Separate fix (animator-side). NEXT.
- ⬜ **#6 putback defender / OTB foul** (MED) — OREB-turn flow, own coord reads.
- ⬜ **#7 zone defense_score** (MED) — named-spot based (turn_manager.py:3407/5585).

All shift FG%/possession → land before shot-system re-tuning ([[project_shot_system_tuning]]).
