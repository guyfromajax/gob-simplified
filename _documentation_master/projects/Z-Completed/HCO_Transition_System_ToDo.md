# HCO Transition System — ToDo (non-PG initiator support)

## Problem

Every transition **into an HCO turn** must let the HCO play be **initiated by any
player** (not just the PG), using the existing `target_shooter` / `pos1..pos4` system.
Today most transitions force the entering pass to land on the **next offense's PG**,
which clobbers the playcall's real step-0 ball handler.

## How HCO already supports a non-PG initiator (no change needed here)

- A play stores **`target_shooter`** = a canonical lineup position. Skeleton steps are
  authored in aliases (`target_shooter`, `pos1..pos4`); at runtime
  `_build_set_play_alias_map` + `_apply_set_play_runtime_position_mapping`
  (`engine/phase_resolution.py`) remap them to canonical positions.
- The **step-0 initiator** is read from the skeleton via
  `get_ball_handler_from_skeleton(skeleton, off_lineup, step_index=0)` — the position
  whose step-0 action is `handle_ball` / `receive` (distinct from `roles.ball_handler`,
  which is the **shooter** / final-step BH).
- The HCO entry orchestrator (`engine/skeleton_step_emitter.py`) runs universally and
  routes Handoff / Kickout / Walk Up from `current_bh_id` (prior turn's
  `final_ball_handler_id`) → `step0_bh_id` (the skeleton initiator).

## Root cause of the PG-forcing behavior

1. `_maybe_stamp_hco_setup` (`models/game_manager.py`) stamps
   `hco_setup.inbound_pass { from_player_id = end-BH, to_player_id = <next-offense PG> }`
   on any turn that transitions to HCO when the end-BH ≠ PG.
2. `_apply_hco_setup_entry_ids` (`engine/skeleton_step_emitter.py`) then **overrides**
   the skeleton-derived `step0_bh_id` with that `to_player_id` (PG).

→ The hardcoded `to_player_id = PG` is the **only** thing forcing PG. The orchestrator
already knows the real initiator from the skeleton.

## Fix pattern (apply per transition type)

- Keep stamping the carrier: `final_ball_handler_id` = end-BH (universal) and/or
  `hco_setup.inbound_pass.from_player_id`.
- **Stop forcing the receiver to PG**: suppress / replace the hardcoded
  `to_player_id = PG` so `_apply_hco_setup_entry_ids` no longer overrides the
  skeleton-derived initiator. Let the orchestrator use
  `get_ball_handler_from_skeleton(..., step_index=0)`.
- The entry **step type** (Handoff / Kickout / Walk Up) is unaffected — only the
  **receiver identity** changes (now the real initiator).
- Regression-check the Reset / entry seam visuals for each path after the change.

## Transition types to upgrade

These currently flow through `_maybe_stamp_hco_setup` (PG-forcing) and need the fix:

| # | Transition | Notes |
|---|------------|-------|
| 1 | **DREB → HCO** | Rebounder ends with the ball; resets to PG today. |
| 2 | **Steal → HCO** | Stealer ends with the ball; resets to PG today. |
| 3 | **CR FB defensive stop → HCO** | Covert Release fast-break stop into HCO. |
| 4 | **RR FB hold-up / outlet-denied → HCO** | Rim Runner; also stamps locally in the RR emitter (redundant but identical payload). |
| 5 | **Any other turn type that sets `next_play_type = "HCO"`** | Audit for newly migrated sources; same fix applies. |

> Also confirm OREB → HCO (uses the Kickout entry primitive) honors the skeleton
> initiator, not a forced PG receiver.

## Out of scope here

- **HCT → HCO** is already specified to support a non-PG initiator — see
  `Dynamic_HCT_Turns.md` §7 "HCO transition branch — execution" and tracker item **D7**.
  The HCT path suppresses the PG override and uses the skeleton initiator; do **not**
  re-solve it here.

## Suggested approach

Rather than patch each call site, consider fixing centrally: make
`_apply_hco_setup_entry_ids` **not** override `step0_bh_id` when a skeleton-derived
initiator exists (i.e. only use `to_player_id` as a fallback when the skeleton yields
no step-0 BH). That single change would upgrade all transitions at once — validate
against each path above before adopting.
