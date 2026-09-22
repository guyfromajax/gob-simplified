"""Arm-gap counterfactuals (diagnostic, harness only). Wraps the equiv-v3 worker.

CF_CLOCK=1   HCO time_elapsed keeps its pre-emit (sim-path) value: undoes the played-only
             "UESS §5 clock authority" realignment in TurnManager._emit_hco_animation_steps.
CF_COORDS=1  played coord writers that sim lacks are removed: apply_coords_from_animations_list
             and _uess_sync_emitted_shot_coords are no-ops, and sync_lineup_coords_from_turn
             ignores animation_steps/animations on HCO turns (overlay maps still apply, as on sim). With the emitted sync gone, the HCO contest also
             falls back to the StepState grid, as on sim.
Output: same row shape as the worker, plus the flags.
"""
import os, sys, json
REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
import scratch_equiv3_fbdedupe as W
from BackEnd.models.turn_manager import TurnManager

CF_CLOCK = os.environ.get("CF_CLOCK") == "1"
CF_COORDS = os.environ.get("CF_COORDS") == "1"

if CF_CLOCK:
    _emit = TurnManager._emit_hco_animation_steps
    def _emit_keep_clock(self, result):
        had = isinstance(result, dict) and "time_elapsed" in result
        te = result.get("time_elapsed") if had else None
        out = _emit(self, result)
        if had:
            result["time_elapsed"] = te
        return out
    TurnManager._emit_hco_animation_steps = _emit_keep_clock

if CF_COORDS:
    from BackEnd.utils import shared as SH
    from BackEnd.engine import phase_resolution as PR
    from BackEnd.engine import rim_runner_fast_break as RRF
    from BackEnd.models import game_manager as GMM
    for mod in (SH, PR, RRF):
        mod.apply_coords_from_animations_list = lambda *a, **k: None
    PR._uess_sync_emitted_shot_coords = lambda *a, **k: None
    _sync = SH.sync_lineup_coords_from_turn

    def _sync_like_sim(game, turn_result):
        # HCO turns: drop only the render payload, keep the overlay maps sim also writes.
        if isinstance(turn_result, dict) and str(turn_result.get("current_turn") or "").upper() == "HCO":
            turn_result = {k: v for k, v in turn_result.items() if k not in ("animation_steps", "animations")}
        return _sync(game, turn_result)
    SH.sync_lineup_coords_from_turn = _sync_like_sim
    GMM.sync_lineup_coords_from_turn = _sync_like_sim

if __name__ == "__main__":
    W._install_defense_census()
    rows = W.run_arm(W.ARM == "played")
    for r in rows:
        r["cf_clock"], r["cf_coords"] = CF_CLOCK, CF_COORDS
    json.dump({"rows": {"%s_%s" % (W.COND, W.ARM): rows}}, open(W.OUT, "w"), indent=1)
    print(W.ARM, rows[0]["seed"], rows[0]["points_per_team"], rows[0]["possessions"])
