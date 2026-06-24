from BackEnd.models.logger import Logger
from BackEnd.models.rebound_manager import ReboundManager
from BackEnd.models.playbook_manager import PlaybookManager
from BackEnd.models.animator import Animator
import math
import random
import json
import logging
import uuid
from BackEnd.db import players_collection, teams_collection, plays_collection
from BackEnd.models.player import Player, player_to_dict

# ✅ PERFORMANCE: Cache plays by (play_type, play_focus) so we don't hit DB every turn (~200+ turns/quarter)
_plays_by_type_focus_cache: dict[tuple[str, str | None], list] = {}
# Cache play doc by name (for override lookup and HCO logic) to avoid repeated find_one
_play_doc_by_name_cache: dict[str, dict | None] = {}
from collections import defaultdict
from BackEnd.playcall_skeletons.inside_skeletons import INSIDE_SCENES
from BackEnd.constants import ACTIONS
from BackEnd.constants import (
    PLAYCALL_ATTRIBUTE_WEIGHTS,
    POSITION_LIST,
    STRATEGY_CALL_DICTS,
    STRATEGY_DEFENSE_ZONE_SENTINEL,
    TEMPO_PASS_DICT,
    MALLEABLE_ATTRS,
    HOME_RIM_COORDS,
    AWAY_RIM_COORDS,
    MADE_SHOT_SWEET_SPOT_HOME_RIM,
    MADE_SHOT_SWEET_SPOT_AWAY_RIM,
)
from BackEnd.utils.shared import (
    weighted_random_from_dict,
    generate_pass_chain,
    get_team_thresholds,
    get_foul_and_turnover_positions,
    get_name_safe,
    get_player_position,
    serialize_lineup,
    getAwayTeamCoords,
)
from BackEnd.utils.playbook_settings_utils import resolve_playbook_percentage
from BackEnd.utils.defense_utils import defender_player_from_random_slot_fallback
from BackEnd.utils.defense_identity import (
    DEFENSE_ID_TO_PLAYBOOK_ZONE_KEY,
    PLAYBOOK_ZONE_KEY_TO_DEFENSE_ID,
    defense_display_name,
    defense_scouting_row_key,
    defense_zone_shell_variant,
    offense_vs_key_from_defense_input,
)
from BackEnd.utils.position_snapshot_ledger import (
    attach_position_snapshots,
    build_phase_post_stopper_snapshot,
)
from BackEnd.utils.shared_defense import (
    get_defender_coords
)
from BackEnd.engine.phase_resolution import (
    resolve_fast_break_logic, 
    resolve_free_throw_logic, 
    resolve_turnover_logic, 
    calculate_foul_turnover,
    resolve_full_court_press_logic,
    resolve_half_court_trap_logic
)
from typing import TYPE_CHECKING, Any, Dict, Optional
if TYPE_CHECKING:
    from BackEnd.models.game_manager import GameManager


def attach_putback_shot_sfx_fields(turn_payload, oreb_event):
    """Mirror HCO shot SFX metadata on OREB putback turns for launch stingers."""
    if not isinstance(turn_payload, dict) or not isinstance(oreb_event, dict):
        return
    if oreb_event.get("event_type") != "PUTBACK_ATTEMPT":
        return
    pre_defense = oreb_event.get("shot_score_pre_defense")
    if pre_defense is None:
        return
    shot_type = oreb_event.get("shot_type") or "inside"
    defense_sfx = oreb_event.get("shot_defense_score_for_sfx", 0)
    turn_payload["shot_type"] = shot_type
    turn_payload["shot_score_pre_defense"] = pre_defense
    turn_payload["shot_defense_score_for_sfx"] = defense_sfx
    turn_payload["sfx"] = {
        "shot_type": shot_type,
        "shot_score_pre_defense": pre_defense,
        "shot_defense_score_for_sfx": defense_sfx,
    }


class TurnManager:
    def __init__(self, game_manager: "GameManager"):
        self.game = game_manager
        self.logger = Logger()
        self.rebound_manager = ReboundManager(self.game)
        self.playbook_manager = PlaybookManager(self.game.offense_team)
        self.animator = Animator(self.game)
        self._ensure_lineup_fields()

    def _ensure_lineup_fields(self):
        for team in [self.game.home_team, self.game.away_team]:
            for player in team.lineup.values():
                if not hasattr(player, "player_id"):
                    setattr(player, "player_id", str(id(player)))
                if not hasattr(player, "coords"):
                    setattr(player, "coords", {"x": 25, "y": 50})

    def _compute_real_time_elapsed_ms(self, result: dict) -> int:
        """
        Compute total wall clock animation duration in ms for this turn.
        Formula: (game_time_elapsed * 350) + fixed_phases_ms
        Clock runs through fixed phases except: announcement holds, rim hold on makes,
        OPENING_TIP initial_hold. Used by frontend to interpolate clock display.
        """
        game_time_elapsed = int(result.get("time_elapsed", 0) or 0)
        movement_ms = game_time_elapsed * 350

        result_type = (result.get("result_type") or "").strip()
        points = int(result.get("points", 0) or 0)
        is_make = points > 0 or result_type == "MAKE"
        is_fast_break = result.get("fast_break") is True or result_type == "FAST_BREAK"

        fixed_ms = 0

        # Zero-elapsed turns: clock does not move
        if result_type in ("FREE_THROW", "SIDE_INBOUND", "TIMEOUT"):
            return 0
        if result_type == "BASELINE_INBOUND" and game_time_elapsed <= 0:
            return 0

        if result_type == "DEFENSIVE_STOP":
            # Announcement hold only; 500ms real, 0 game time (do not expire game time)
            fixed_ms = 500 if is_fast_break else 0

        elif result_type in ("MAKE", "MISS", "BLOCK"):
            if is_fast_break:
                # pass 250ms + outlet move 300ms + shot 350ms; rim excluded on make
                fixed_ms = 900 if is_make else 1900  # 900 + 1000 rim on miss
            else:
                # HCO / FCP / HCT: pass or steal 150ms; rim 1000ms on miss only
                # OPTION_B: add Xms to game_time_elapsed if upgrading to full end-to-end precision (currently excluded to preserve game balance)
                fixed_ms = 150 if is_make else 1150

        elif result_type == "FINAL_HOLD":
            # OPTION_B: add Xms to game_time_elapsed if upgrading to full end-to-end precision (currently excluded to preserve game balance)
            fixed_ms = 1800  # holdClockOutMs

        elif result_type in ("OREB_KICKOUT", "PUTBACK_MAKE", "PUTBACK_MISS"):
            # OPTION_B: add Xms to game_time_elapsed if upgrading to full end-to-end precision (currently excluded to preserve game balance)
            if result_type == "PUTBACK_MAKE":
                fixed_ms = 800   # rebound_move + attach_delay; rim excluded
            elif result_type == "PUTBACK_MISS":
                fixed_ms = 1800  # rebound_move + attach_delay + rim_hold
            else:
                fixed_ms = 800   # OREB_KICKOUT

        elif result_type == "FOUL":
            fixed_ms = 0

        elif result_type == "OPENING_TIP":
            # OPTION_B: add Xms to game_time_elapsed if upgrading to full end-to-end precision (currently excluded to preserve game balance)
            fixed_ms = 400  # apex_delay + pass_delay; initial_hold excluded

        else:
            # STEAL, DEAD BALL, TURNOVER, CHARGE, etc.
            fixed_ms = 0

        return movement_ms + fixed_ms

    def _resolve_clock_authority_mode(self, game_state: dict) -> str:
        raw_mode = str(game_state.get("uess_clock_authority_mode", "warn") or "warn").strip().lower()
        if raw_mode in {"observe", "warn", "throw", "off"}:
            return raw_mode
        return "warn"

    def _resolve_clock_elapsed_authority(self, game_state: dict) -> str:
        raw_mode = str(game_state.get("uess_clock_elapsed_authority", "ledger") or "ledger").strip().lower()
        if raw_mode in {"legacy", "ledger"}:
            return raw_mode
        return "ledger"

    def _resolve_ownership_contract_mode(self, game_state: dict) -> str:
        raw_mode = str(game_state.get("uess_ownership_contract_mode", "warn") or "warn").strip().lower()
        if raw_mode in {"off", "observe", "warn", "throw"}:
            return raw_mode
        return "warn"

    def _attach_clock_contract(
        self,
        result: dict,
        clock_start: int,
        shot_clock_start: int,
        game_state: dict,
        source: str,
    ) -> None:
        """Attach authoritative clock contract fields to a turn result dict."""
        clock_end = int(game_state.get("time_remaining", 0))
        sc_end = int(game_state.get("shot_clock_remaining", 30))
        sc_reset_reason = result.get("shot_clock_reset_reason")
        sc_reset = bool(sc_reset_reason) or sc_end > shot_clock_start or (
            sc_end == 30 and clock_start != clock_end
        )
        result["clock_start"] = clock_start
        result["clock_end"] = clock_end
        result["shot_clock_start"] = shot_clock_start
        result["shot_clock_end"] = sc_end
        result["shot_clock_reset"] = bool(sc_reset)
        if sc_reset_reason:
            result["shot_clock_reset_reason"] = str(sc_reset_reason)
        result["clock_contract_source"] = source
        result["real_time_elapsed_ms"] = self._compute_real_time_elapsed_ms(result)
        clock_authority_mode = self._resolve_clock_authority_mode(game_state)
        elapsed_authority = self._resolve_clock_elapsed_authority(game_state)
        result["uess_clock_authority_mode"] = clock_authority_mode
        result["uess_clock_elapsed_authority"] = elapsed_authority
        result["clock_event_ledger"] = self._build_clock_event_ledger(
            result=result,
            clock_start=clock_start,
            clock_end=clock_end,
            shot_clock_start=shot_clock_start,
            shot_clock_end=sc_end,
            shot_clock_reset=bool(sc_reset),
        )
        self._attach_clock_elapsed_observe_reconciliation(
            result=result,
            game_state=game_state,
            mode=clock_authority_mode,
            elapsed_authority=elapsed_authority,
        )
        logging.debug(
            "⏱️ [CLOCK CONTRACT] type=%s source=%s "
            "clock=%d→%d elapsed=%d sc=%d→%d reset=%s",
            result.get("result_type", "UNKNOWN"),
            source,
            clock_start,
            clock_end,
            clock_start - clock_end,
            shot_clock_start,
            sc_end,
            sc_reset,
        )

    def _get_clock_reconciliation_tolerance_seconds(self, game_state: dict) -> float:
        raw = game_state.get("uess_clock_recon_tolerance_seconds", 0.10)
        try:
            tol = float(raw)
        except (TypeError, ValueError):
            tol = 0.10
        return max(0.0, tol)

    def _derive_elapsed_from_clock_event_ledger(self, events: list[dict]) -> int:
        if not isinstance(events, list):
            return 0
        derived_elapsed = 0
        for row in events:
            if not isinstance(row, dict):
                continue
            if row.get("event_type") != "game_clock_stop":
                continue
            try:
                before = int(row.get("game_clock_before", 0) or 0)
                after = int(row.get("game_clock_after", 0) or 0)
            except (TypeError, ValueError):
                continue
            derived_elapsed += max(0, before - after)
        return int(derived_elapsed)

    def _attach_clock_elapsed_observe_reconciliation(
        self,
        *,
        result: dict,
        game_state: dict,
        mode: str = "observe",
        elapsed_authority: str = "legacy",
    ) -> None:
        """Clock reconciliation compare with mode-based backend enforcement."""
        legacy_elapsed = int(result.get("time_elapsed", 0) or 0)
        ledger_elapsed = self._derive_elapsed_from_clock_event_ledger(
            result.get("clock_event_ledger", [])
        )
        delta_seconds = ledger_elapsed - legacy_elapsed
        tolerance = self._get_clock_reconciliation_tolerance_seconds(game_state)
        within_tolerance = abs(delta_seconds) <= tolerance
        normalized_mode = mode if mode in {"observe", "warn", "throw", "off"} else "observe"
        normalized_elapsed_authority = (
            elapsed_authority if elapsed_authority in {"legacy", "ledger"} else "legacy"
        )

        if normalized_elapsed_authority == "ledger":
            result["time_elapsed"] = int(ledger_elapsed)

        result["uess_clock_elapsed_game_seconds"] = int(ledger_elapsed)
        result["uess_clock_elapsed_legacy_game_seconds"] = int(legacy_elapsed)
        result["uess_clock_elapsed_delta_seconds"] = int(delta_seconds)
        result["uess_clock_elapsed_observe_within_tolerance"] = bool(within_tolerance)
        result["uess_clock_reconciliation"] = {
            "mode": normalized_mode,
            "elapsed_authority": normalized_elapsed_authority,
            "ledger_elapsed_game_seconds": int(ledger_elapsed),
            "legacy_elapsed_game_seconds": int(legacy_elapsed),
            "delta_seconds": int(delta_seconds),
            "tolerance_seconds": float(tolerance),
            "within_tolerance": bool(within_tolerance),
        }

        if within_tolerance or normalized_mode in {"observe", "off"}:
            return

        message = (
            "[CLOCK CONTRACT] backend reconciliation fail "
            f"(mode={normalized_mode}, result={result.get('result_type')}, "
            f"ledgerElapsed={ledger_elapsed}, legacyElapsed={legacy_elapsed}, "
            f"deltaSeconds={delta_seconds}, toleranceSeconds={tolerance})"
        )

        if normalized_mode == "warn":
            logging.warning("⚠️ %s", message)
            return

        if normalized_mode == "throw":
            raise ValueError(message)

    def _clock_stop_reason(self, result: dict) -> str:
        result_type = str(result.get("result_type") or "").upper()
        if result_type == "TIMEOUT":
            return "timeout"
        if result_type == "FOUL":
            return "foul"
        if result_type in {"DEAD BALL", "TURNOVER", "CHARGE"}:
            return "dead_ball_turnover"
        if result_type == "MAKE":
            return "made_basket"
        return "turn_boundary"

    def _shot_clock_stop_reason(self, result: dict) -> str:
        result_type = str(result.get("result_type") or "").upper()
        if result_type in {"MAKE", "MISS", "BLOCK"}:
            return "shot_detach"
        if result_type == "FOUL":
            return "foul"
        if result_type in {"DEAD BALL", "TURNOVER", "CHARGE"}:
            return "dead_ball_turnover"
        return "turn_boundary"

    def _build_clock_event_ledger(
        self,
        *,
        result: dict,
        clock_start: int,
        clock_end: int,
        shot_clock_start: int,
        shot_clock_end: int,
        shot_clock_reset: bool,
    ) -> list[dict]:
        """Build observe-mode clock event ledger rows for this turn."""
        turn_id = result.get("turn_count") or result.get("id")
        game_elapsed = max(0, int(clock_start) - int(clock_end))
        shot_elapsed = max(0, int(shot_clock_start) - int(shot_clock_end))
        events: list[dict] = []

        def append_event(event_type: str, reason: str, ts_game_seconds: int) -> None:
            events.append(
                {
                    "event_id": f"clk-{uuid.uuid4().hex[:12]}",
                    "turn_id": turn_id,
                    "event_type": event_type,
                    "reason": reason,
                    "game_clock_before": int(clock_start),
                    "game_clock_after": int(clock_end),
                    "shot_clock_before": int(shot_clock_start),
                    "shot_clock_after": int(shot_clock_end),
                    "timestamp_game_seconds": int(ts_game_seconds),
                }
            )

        if game_elapsed > 0:
            append_event("game_clock_start", "live_ball_window", int(clock_start))
            append_event("game_clock_stop", self._clock_stop_reason(result), int(clock_end))
        else:
            append_event("game_clock_stop", self._clock_stop_reason(result), int(clock_start))

        if shot_elapsed > 0:
            append_event("shot_clock_start", "live_possession_window", int(shot_clock_start))
            append_event(
                "shot_clock_stop",
                self._shot_clock_stop_reason(result),
                int(shot_clock_end),
            )
        else:
            append_event(
                "shot_clock_stop",
                self._shot_clock_stop_reason(result),
                int(shot_clock_start),
            )

        if shot_clock_reset:
            append_event(
                "shot_clock_reset",
                str(result.get("shot_clock_reset_reason") or "turn_policy_reset"),
                int(clock_end),
            )

        if int(clock_end) <= 0:
            append_event("period_end", "game_clock_zero", 0)

        if int(result.get("points", 0) or 0) > 0 or str(result.get("result_type") or "").upper() == "MAKE":
            append_event("basket_counted", "scoring_result", int(clock_end))

        possession_team_id = (
            result.get("possession_team_id")
            or result.get("offense_team_id")
            or self.game.game_state.get("offense_team")
        )
        append_event("possession_committed", "turn_close", int(clock_end))
        events[-1]["possession_team_id"] = possession_team_id

        return events

    def _attach_uess_ownership_contract(self, result: dict) -> None:
        """Attach observational ownership/pass-lifecycle contract fields."""
        steps = result.get("steps")
        owner_by_step = result.get("ball_owner_by_step")
        applicable = isinstance(steps, list) and len(steps) > 0 and isinstance(owner_by_step, list)

        pass_events = []
        if isinstance(steps, list):
            for step_index, step in enumerate(steps):
                if not isinstance(step, dict):
                    continue
                for event in step.get("events", []) or []:
                    if not isinstance(event, dict):
                        continue
                    if str(event.get("type") or "").lower().strip() != "pass":
                        continue
                    passer = event.get("by")
                    receiver = event.get("to")
                    pass_events.append(
                        {
                            "step_index": int(step_index),
                            "passer_pos": passer if isinstance(passer, str) else None,
                            "receiver_pos": receiver if isinstance(receiver, str) else None,
                        }
                    )

        owner_seq = owner_by_step if isinstance(owner_by_step, list) else []
        terminal_owner = None
        for owner in reversed(owner_seq):
            if isinstance(owner, str) and owner.strip():
                terminal_owner = owner
                break

        valid_receipt_count = 0
        for row in pass_events:
            receiver = row.get("receiver_pos")
            step_index = int(row.get("step_index") or 0)
            if not isinstance(receiver, str) or not receiver:
                continue
            if any(owner_seq[idx] == receiver for idx in range(step_index, len(owner_seq))):
                valid_receipt_count += 1

        pass_count = len(pass_events)
        game_state = getattr(getattr(self, "game", None), "game_state", {}) or {}
        ownership_mode = self._resolve_ownership_contract_mode(game_state)
        result["uess_ownership_contract_mode"] = ownership_mode
        contract = {
            "applicable": bool(applicable),
            "mode": ownership_mode,
            "pass_event_count": int(pass_count),
            "pass_receipt_valid_count": int(valid_receipt_count),
            "pass_lifecycle_valid": bool(pass_count == 0 or valid_receipt_count == pass_count),
            "terminal_owner_pos": terminal_owner,
            "next_play_type": result.get("next_play_type"),
            "result_type": result.get("result_type"),
        }
        if pass_count > 0:
            contract["pass_events"] = pass_events
        result["uess_ownership_contract"] = contract

        if ownership_mode in {"warn", "throw"} and contract["applicable"] and not contract["pass_lifecycle_valid"]:
            message = (
                "[UESS ownership contract] pass lifecycle invalid "
                f"(mode={ownership_mode}, result={result.get('result_type')}, next={result.get('next_play_type')}, "
                f"passEventCount={contract['pass_event_count']}, validReceiptCount={contract['pass_receipt_valid_count']}, "
                f"terminalOwner={contract['terminal_owner_pos']})"
            )
            if ownership_mode == "throw":
                raise ValueError(message)
            logging.warning(
                "⚠️ [UESS ownership contract] pass lifecycle invalid (result=%s, next=%s, "
                "passEventCount=%s, validReceiptCount=%s, terminalOwner=%s)",
                result.get("result_type"),
                result.get("next_play_type"),
                contract["pass_event_count"],
                contract["pass_receipt_valid_count"],
                contract["terminal_owner_pos"],
            )

    def _inbound_setup_coords_from_dest(
        self,
        o_dest: Dict[str, Any],
        d_dest: Dict[str, Any],
        off_lineup: Dict[str, Any],
        def_lineup: Dict[str, Any],
    ) -> Dict[str, Dict[str, float]]:
        setup_coords: Dict[str, Dict[str, float]] = {}
        for pos, coord in (o_dest or {}).items():
            player = off_lineup.get(pos)
            pid = getattr(player, "player_id", None)
            if pid is not None and isinstance(coord, dict):
                setup_coords[str(pid)] = {"x": float(coord.get("x", 0)), "y": float(coord.get("y", 0))}
        for pos, coord in (d_dest or {}).items():
            player = def_lineup.get(pos)
            pid = getattr(player, "player_id", None)
            if pid is not None and isinstance(coord, dict):
                setup_coords[str(pid)] = {"x": float(coord.get("x", 0)), "y": float(coord.get("y", 0))}
        return setup_coords

    def _resolve_inbound_prior_seam(
        self,
        prior_turn: Optional[Dict[str, Any]],
    ) -> tuple:
        """Resolve prior-end coords + BH for SIP/BIP bridge emission."""
        game = self.game
        game_state = getattr(game, "game_state", {}) or {}

        if isinstance(prior_turn, dict):
            prior_fc = prior_turn.get("final_coords")
            if isinstance(prior_fc, dict) and len(prior_fc) >= 8:
                return prior_fc, prior_turn.get("final_ball_handler_id")

        if game_state.get("inbound_seam_from_triangle"):
            from BackEnd.utils.player_entry import build_triangle_entrance_coords

            triangle = build_triangle_entrance_coords(game)
            bh = game_state.get("timeout_seam_ball_handler_id")
            return triangle, bh

        return {}, None

    def _stamp_inbound_hco_handoff(self, payload: Dict[str, Any], sf_id: str, pg_id: str) -> None:
        """Stamp fields the HCO entry orchestrator reads on the following turn."""
        next_route = payload.get("next_play_type") or payload.get("next_turn") or "HCO"
        payload["next_play_type"] = next_route
        payload.setdefault("next_turn", next_route)
        payload["hco_setup"] = {
            "inbound_pass": {
                "from_player_id": str(sf_id),
                "to_player_id": str(pg_id),
            }
        }

    def setup_side_inbound(self):
        """
        Prepare coordinates for a sideline inbound following a dead-ball
        turnover or a non-shooting foul with no free throws.

        Returns a payload describing offensive and defensive destination
        coordinates which the front-end can use to animate the inbound
        sequence.
        """

        game = self.game
        offense_team = game.offense_team
        defense_team = game.defense_team
        aggression = defense_team.strategy_calls.get("aggression_call", "normal")
        is_away_offense = offense_team.team_id == game.away_team.team_id

        self.logger.log("sideInbound:start")

        # Sideline spot for the inbounder (SF). These coordinates assume the
        # home team is on offense. They will be mirrored if the away team has
        # the ball. Y=51 is out of bounds at the top of the court.
        inbound_spot_home = {"x": 47, "y": 48}

        # Destination ranges for other offensive players (home orientation).
        home_ranges = {
            "PG": {"x": (50, 54), "y": (37, 43)},
            "SG": {"x": (55, 64), "y": (18, 32)},
            "PF": {"x": (65, 80), "y": (26, 36)},
            "C":  {"x": (65, 80), "y": (14, 24)},
        }

        o_dest_home = {}
        for pos, ranges in home_ranges.items():
            o_dest_home[pos] = {
                "x": random.randint(*ranges["x"]),
                "y": random.randint(*ranges["y"]),
            }
            self.logger.log(f"destAssigned:{pos}")

        # Inbounder (SF) stays at the inbound spot
        o_dest_home["SF"] = inbound_spot_home.copy()

        # Flip offensive coordinates if the away team has possession
        o_dest = getAwayTeamCoords(o_dest_home.copy()) if is_away_offense else o_dest_home

        # Determine ball-handler (PG) coordinates in actual orientation
        bh_coords = o_dest["PG"]

        # --- Defensive positioning ---
        # Fixed positions for home team defense (when home is defending)
        self.logger.log("defenseUpdate:start")
        d_dest_home = {
            "PG": {"x": 60, "y": 25},
            "SG": {"x": 64, "y": 33},
            "SF": {"x": 66, "y": 17},
            "PF": {"x": 80, "y": 25},
            "C": {"x": 85, "y": 28}
        }
        
        # Flip defensive coordinates if away team is defending (home team has ball)
        d_dest = getAwayTeamCoords(d_dest_home.copy()) if is_away_offense else d_dest_home
        self.logger.log("defenseUpdate:end")

        from BackEnd.constants import SITUATIONAL_SIP_RECEIVER_POS
        receiver_pos = SITUATIONAL_SIP_RECEIVER_POS
        payload = {
            "result_type": "SIDE_INBOUND",
            "time_elapsed": 0,
            "ball_spot": getAwayTeamCoords({"tmp": inbound_spot_home})["tmp"] if is_away_offense else inbound_spot_home,
            "oDestinations": o_dest,
            "dDestinations": d_dest,
            "receiver_pos": receiver_pos,  # for situational Force Foul (pass receiver)
            "offense_team_id": offense_team.team_id,  # ✅ SS&S: Team on offense during this turn
            "current_turn": "SIDE_INBOUND",  # ✅ SS&S: Explicit turn type
            "next_turn": "HCO",  # ✅ SS&S: Always transitions to HCO after side inbound
            "next_play_type": "HCO",
            "possession_team_id": offense_team.team_id,  # ✅ TODO: Remove (backwards compatibility)
            "quarter": self.game.quarter,
        }

        from BackEnd.utils.position_snapshot_ledger import (
            attach_position_snapshots,
            build_inbound_destinations_snapshot,
        )

        sip_snap = build_inbound_destinations_snapshot(
            game,
            offense_team.lineup,
            defense_team.lineup,
            o_dest,
            d_dest,
            "SIDE_INBOUND",
            "sip_inbound_setup",
        )
        attach_position_snapshots(payload, [sip_snap])

        # Emit unified animation_steps. SIP is a 2-step turn (mirror of BIP):
        # Step 1 = setup walk-in (all 10 players to SIP destinations; ball
        # travels from prior BH coord to SF at shot speed). Step 2 = inbound
        # pass (SF→PG; all others stationary). No game-clock burn — clock
        # fields are pinned to turn-start on every step.
        try:
            from BackEnd.utils.transition_bridge import build_sip_animation_steps

            sf_player = offense_team.lineup.get("SF")
            pg_player = offense_team.lineup.get("PG")
            sf_id = str(getattr(sf_player, "player_id", "") or "")
            pg_id = str(getattr(pg_player, "player_id", "") or "")

            setup_coords = self._inbound_setup_coords_from_dest(
                o_dest, d_dest, offense_team.lineup, defense_team.lineup
            )

            prior_turns = getattr(game, "turns", None) or []
            prior_turn = prior_turns[-1] if prior_turns else None
            prior_final_coords, prior_final_bh_id = self._resolve_inbound_prior_seam(prior_turn)

            clock_state = getattr(game, "game_state", {}) or {}
            clock_r = float(clock_state.get("time_remaining", 0) or 0)
            shot_r = float(clock_state.get("shot_clock_remaining", 0) or 0)

            if sf_id and pg_id and prior_final_coords and setup_coords:
                anim_steps = build_sip_animation_steps(
                    off_lineup=offense_team.lineup,
                    def_lineup=defense_team.lineup,
                    prior_final_coords=prior_final_coords,
                    prior_final_ball_handler_id=prior_final_bh_id,
                    setup_coords=setup_coords,
                    sf_id=sf_id,
                    pg_id=pg_id,
                    clock_remaining_at_start=clock_r,
                    shot_clock_remaining_at_start=shot_r,
                )
                if anim_steps:
                    payload["animation_steps"] = anim_steps
                    self._stamp_inbound_hco_handoff(payload, sf_id, pg_id)
        except Exception as e:
            import logging
            logging.warning("build_sip_animation_steps failed: %s", e)

        return payload

    def _build_fcp_setup_positions(
        self,
        *,
        is_away_offense: bool,
        offense_chemistry: int,
        current_pg_y: int,
    ):
        """Build randomized BIP-end positions for an FCP turn (offense + defense).

        Offense: SF uses chemistry-aware inbound y (HCO BIP logic). PG x from
        ``FCP_OFFENSE_SETUP_RANGES``; PG y = SF y + randint(-6, 6). SG/PF/C
        from ``FCP_OFFENSE_SETUP_RANGES``.

        Defense ranges per ``FCP_DEFENSE_SETUP_RANGES`` (all 5 positions —
        replaces the legacy `get_defender_coords`-derived layout for FCP only).

        Coords are generated in HOME orientation. Caller flips via
        ``getAwayTeamCoords`` if away offense.

        Collision resolution: any pair landing on the exact same (x, y) is
        broken by moving one randomly-chosen player by exactly
        ``FCP_SETUP_COLLISION_OFFSET_GRID`` grid spots in a random direction.
        The moved player ends up that distance from BOTH their original
        coord AND the other colliding player. Re-checked iteratively (≤10
        rounds) in case the move creates a new exact collision.

        Returns ``(o_dest_home, d_dest_home, inbound_spot_home)``.
        """
        from BackEnd.constants import (
            FCP_OFFENSE_SETUP_RANGES,
            FCP_DEFENSE_SETUP_RANGES,
            FCP_SETUP_COLLISION_OFFSET_GRID,
        )

        # --- SF (dynamic inbound, chemistry-aware y) ---
        # Mirrors HCO BIP's SF logic. SF x is fixed at the inbound baseline
        # (home: x=3); chemistry-aware y_range biased toward PG side when
        # team chemistry is high.
        sf_x = 3  # home-orientation baseline
        if offense_chemistry > 15:
            sf_y_range = (25, 35) if current_pg_y > 24 else (15, 25)
        else:
            sf_y_range = (15, 35)
        sf_y = random.randint(*sf_y_range)

        o_dest_home = {"SF": {"x": float(sf_x), "y": float(sf_y)}}
        pg_ranges = FCP_OFFENSE_SETUP_RANGES["PG"]
        o_dest_home["PG"] = {
            "x": float(random.randint(*pg_ranges["x"])),
            "y": float(max(1, min(49, sf_y + random.randint(-6, 6)))),
        }
        sg_ranges = FCP_OFFENSE_SETUP_RANGES["SG"]
        o_dest_home["SG"] = {
            "x": float(random.randint(*sg_ranges["x"])),
            "y": float(random.randint(*sg_ranges["y"])),
        }
        for pos in ("PF", "C"):
            ranges = FCP_OFFENSE_SETUP_RANGES[pos]
            o_dest_home[pos] = {
                "x": float(random.randint(*ranges["x"])),
                "y": float(random.randint(*ranges["y"])),
            }

        d_dest_home = {}
        for pos, ranges in FCP_DEFENSE_SETUP_RANGES.items():
            d_dest_home[pos] = {
                "x": float(random.randint(*ranges["x"])),
                "y": float(random.randint(*ranges["y"])),
            }

        # --- Collision resolution ---
        # "On top of each other" = exact same (x, y). Tag each coord with a
        # team prefix so the loop can update the right dict.
        def _tagged_items():
            return (
                [(("off", pos), coord) for pos, coord in o_dest_home.items()]
                + [(("def", pos), coord) for pos, coord in d_dest_home.items()]
            )

        for _ in range(10):  # iterate in case a move creates a new collision
            items = _tagged_items()
            collision = None
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    a_coord = items[i][1]
                    b_coord = items[j][1]
                    if a_coord["x"] == b_coord["x"] and a_coord["y"] == b_coord["y"]:
                        collision = (items[i], items[j])
                        break
                if collision:
                    break
            if not collision:
                break
            chosen_tag, chosen_coord = random.choice(collision)
            theta = random.uniform(0.0, 2.0 * math.pi)
            offset = float(FCP_SETUP_COLLISION_OFFSET_GRID)
            new_coord = {
                "x": chosen_coord["x"] + offset * math.cos(theta),
                "y": chosen_coord["y"] + offset * math.sin(theta),
            }
            team_key, pos = chosen_tag
            if team_key == "off":
                o_dest_home[pos] = new_coord
            else:
                d_dest_home[pos] = new_coord

        # Ball spot at SF's inbound coord (home orientation; caller flips).
        inbound_spot_home = dict(o_dest_home["SF"])
        return o_dest_home, d_dest_home, inbound_spot_home

    def setup_baseline_inbound(self, next_defensive_setup=None):
        """
        Prepare coordinates for a baseline inbound following a made shot.
        The opposing team gets the ball and starts their possession from the baseline.

        Args:
            next_defensive_setup: Optional defensive pressure type ("FCP" or "HCT") 
                                  that will be applied after the inbound pass.

        Returns a payload describing offensive and defensive destination
        coordinates which the front-end can use to animate the inbound
        sequence.
        """

        game = self.game
        offense_team = game.offense_team
        defense_team = game.defense_team
        aggression = defense_team.strategy_calls.get("aggression_call", "normal")
        is_away_offense = offense_team.team_id == game.away_team.team_id

        self.logger.log("baselineInbound:start")

        # Define ball spot for inbounder (used in payload regardless of pressure type)
        # ✅ FIX: Inbound spot should be at edge of baseline, not center court
        # Home orientation uses left baseline (x=3), away uses right baseline (x=97 after flip)
        inbound_spot_home = {"x": 3, "y": 25}  # Left baseline (home orientation)

        # FCP setup: randomized per-position ranges with chemistry-aware
        # dynamic SF inbound y (see FCP_HCT_System.md → "FCP Starting
        # Alignment"). Defenders use their own randomized ranges (no longer
        # derived via `get_defender_coords`).
        # HCT setup: legacy static `HCT_SETUP_POSITIONS` mapping.
        setup_locations = None
        fcp_helper_outputs = None
        if next_defensive_setup == "FCP":
            offense_attrs = offense_team.team_attributes or {}
            offense_chemistry = int(offense_attrs.get("team_chemistry", 15) or 15)
            current_pg = offense_team.lineup.get("PG")
            current_pg_y = 25
            if getattr(current_pg, "coords", None):
                current_pg_y = int(current_pg.coords.get("y", 25) or 25)
            fcp_helper_outputs = self._build_fcp_setup_positions(
                is_away_offense=is_away_offense,
                offense_chemistry=offense_chemistry,
                current_pg_y=current_pg_y,
            )
            setup_locations = "FCP_RANDOMIZED"  # sentinel — triggers downstream branches
        elif next_defensive_setup == "HCT":
            from BackEnd.constants import HCT_SETUP_POSITIONS, HCO_STRING_SPOTS
            setup_locations = HCT_SETUP_POSITIONS

        if setup_locations:
            from BackEnd.constants import HCO_STRING_SPOTS
            if next_defensive_setup == "FCP":
                o_dest_home, d_dest_home_fcp, inbound_spot_home = fcp_helper_outputs
                for pos in o_dest_home:
                    self.logger.log(f"destAssigned:{pos}")
            else:
                # HCT (legacy static mapping)
                o_dest_home = {}
                for pos, location in setup_locations.items():
                    coords = HCO_STRING_SPOTS.get(location, {"x": 50, "y": 25})
                    o_dest_home[pos] = coords.copy()
                    self.logger.log(f"destAssigned:{pos}")
                sf_location = setup_locations.get("SF", "inbound_left")
                inbound_spot_home = HCO_STRING_SPOTS.get(sf_location, {"x": 50, "y": 25})

            # Flip offensive coordinates if the away team has possession.
            o_dest = getAwayTeamCoords(o_dest_home.copy()) if is_away_offense else o_dest_home
        else:
            # HCO-only baseline inbound setup uses explicit BIP targets.
            offense_attrs = offense_team.team_attributes or {}
            defense_attrs = defense_team.team_attributes or {}
            offense_chemistry = int(offense_attrs.get("team_chemistry", 15) or 15)
            defense_execution = int(defense_attrs.get("defense_execution", 0) or 0)

            offense_basket = HOME_RIM_COORDS if not is_away_offense else AWAY_RIM_COORDS
            inbound_spot = {"x": 3, "y": 25} if not is_away_offense else {"x": 97, "y": 25}

            current_pg = offense_team.lineup.get("PG")
            current_pg_y = 25
            if getattr(current_pg, "coords", None):
                current_pg_y = int(current_pg.coords.get("y", 25) or 25)

            if offense_chemistry > 15:
                sf_y_range = (25, 35) if current_pg_y > 24 else (15, 25)
            else:
                sf_y_range = (15, 35)

            sf_y = random.randint(*sf_y_range)
            sf_x = inbound_spot["x"]

            pg_x_offset = random.randint(9, 15)
            pg_y_offset = random.randint(-3, 3)
            pg_x = sf_x + pg_x_offset if not is_away_offense else sf_x - pg_x_offset
            pg_y = max(1, min(49, sf_y + pg_y_offset))

            def offense_half_court_target():
                if not is_away_offense:
                    x = random.randint(offense_basket["x"] - 25, offense_basket["x"] - 5)
                else:
                    x = random.randint(offense_basket["x"] + 5, offense_basket["x"] + 25)
                y = random.randint(
                    max(1, offense_basket["y"] - 20),
                    min(49, offense_basket["y"] + 20),
                )
                return {"x": x, "y": y}

            o_dest = {
                "SF": {"x": sf_x, "y": sf_y},
                "PG": {"x": pg_x, "y": pg_y},
                "SG": offense_half_court_target(),
                "PF": offense_half_court_target(),
                "C": offense_half_court_target(),
            }

            lane_target_count = 5 if defense_execution > 5 else 4 if defense_execution > 0 else 2
            defender_positions = [pos for pos in defense_team.lineup.keys() if pos in {"PG", "SG", "SF", "PF", "C"}]
            lane_positions = set(random.sample(defender_positions, min(lane_target_count, len(defender_positions))))

            d_dest = {}
            for pos in defender_positions:
                if pos in lane_positions:
                    x = random.randint(74, 87) if not is_away_offense else random.randint(14, 27)
                    y = random.randint(19, 32)
                else:
                    x = random.randint(62, 87) if not is_away_offense else random.randint(14, 39)
                    y = random.randint(10, 30)
                d_dest[pos] = {"x": x, "y": y}

            bh_coords = o_dest["PG"]
            inbound_spot_home = inbound_spot.copy()

        # Determine ball-handler (PG) coordinates in actual orientation
        bh_coords = o_dest["PG"]

        # --- Defensive positioning ---
        # PHASE 6: Use new unified defender coordinate system
        # get_defender_coords handles coordinate orientation automatically
        if setup_locations:
            self.logger.log("defenseUpdate:start")
            if next_defensive_setup == "HCT":
                # HCT-specific: defenders plant on the opposite half from the
                # inbound (PG at center court, others at HCT_STANDARD_NORMAL
                # centroids). This matches dynamic HCT step 0's expected
                # defender starting alignment so BIP→HCT has no teleport.
                from BackEnd.engine.dynamic_hct import (
                    hct_initial_defender_coords,
                )
                d_dest = hct_initial_defender_coords(is_away_offense)
            elif next_defensive_setup == "FCP":
                # FCP-specific: defenders use the same randomized-range
                # alignment generated alongside the offense in
                # `_build_fcp_setup_positions`. Flip for away offense.
                d_dest = (
                    getAwayTeamCoords(dict(d_dest_home_fcp))
                    if is_away_offense
                    else dict(d_dest_home_fcp)
                )
            else:
                d_dest = {}
                for pos, defender in defense_team.lineup.items():
                    if pos == "PG":
                        d_coords = get_defender_coords(
                            bh_coords,
                            is_away_offense,
                            aggression,
                            "baseline_inbound",
                            None,
                            is_ball_handler=True
                        )
                        d_dest[pos] = d_coords
                    elif pos in o_dest:
                        o_coords = o_dest[pos]
                        o_spot = "key"
                        d_coords = get_defender_coords(
                            o_coords,
                            is_away_offense,
                            aggression,
                            o_spot,
                            bh_coords,
                            is_ball_handler=False,
                            ball_spot="baseline_inbound"
                        )
                        d_dest[pos] = d_coords
            self.logger.log("defenseUpdate:end")

        from BackEnd.constants import SITUATIONAL_BIP_RECEIVER_POS
        payload = {
            "result_type": "BASELINE_INBOUND",
            "time_elapsed": 0,
            "ball_spot": getAwayTeamCoords({"tmp": inbound_spot_home})["tmp"] if (setup_locations and is_away_offense) else inbound_spot_home,
            "oDestinations": o_dest,
            "dDestinations": d_dest,
            "receiver_pos": SITUATIONAL_BIP_RECEIVER_POS,  # for situational Force Foul (pass receiver)
            "offense_team_id": offense_team.team_id,  # ✅ SS&S: Use offense_team_id (not possession_team_id)
            "turn_type": "BASELINE_INBOUND",  # Back-compat marker for post-BIP pressure slicing.
            "current_turn": "BASELINE_INBOUND",  # ✅ SS&S: Explicit turn type
            "quarter": self.game.quarter,
            "next_play_type": next_defensive_setup if next_defensive_setup else "HCO",  # ✅ Explicit routing
            "next_turn": next_defensive_setup if next_defensive_setup else "HCO",  # ✅ SS&S: Explicit next turn
        }
        
        # Include next_defensive_setup if provided (for FCP/HCT pressure)
        if next_defensive_setup:
            payload["next_defensive_setup"] = next_defensive_setup

            if next_defensive_setup == "HCT":
                # Dynamic HCT bypasses the MongoDB skeleton entirely — use the
                # already-computed o_dest (HCT_SETUP_POSITIONS, flipped for
                # away offense) so frontend runInboundSetup tweens to the
                # same authored spots as handleBaselineInbound. Pulling from
                # the legacy skeleton's step 0 here would override authored
                # spots and cause BH hold drift. See Dynamic_HCT_Turns.md.
                payload["offense_setup_positions"] = {
                    pos: {"coords": coords} for pos, coords in o_dest.items()
                }
            elif next_defensive_setup == "FCP":
                # FCP randomized BIP setup: source from o_dest (per-position
                # ranges with collision avoidance, generated above) — NOT
                # from skeleton step 0. Players will animate from these
                # BIP-end coords toward the first post-inbound skeleton
                # step at archetype rate; non-gate movers freeze at the
                # interrupted coord (§9.5) — no teleport.
                payload["offense_setup_positions"] = {
                    pos: {"coords": coords} for pos, coords in o_dest.items()
                }
            else:
                # Other future pressure types: keep skeleton step 0 positions
                # as the source of offense setup.
                from BackEnd.engine.phase_resolution import get_skeleton_for_turn
                skeleton = get_skeleton_for_turn("HCO", next_defensive_setup, self.game)
                if skeleton and "steps" in skeleton and len(skeleton.get("steps", [])) > 0:
                    step_0 = skeleton["steps"][0]
                    if "pos_actions" in step_0 and step_0["pos_actions"]:
                        payload["offense_setup_positions"] = step_0["pos_actions"]

        from BackEnd.utils.position_snapshot_ledger import (
            attach_position_snapshots,
            build_inbound_destinations_snapshot,
        )

        bip_snap = build_inbound_destinations_snapshot(
            game,
            offense_team.lineup,
            defense_team.lineup,
            o_dest,
            d_dest,
            "BASELINE_INBOUND",
            "bip_inbound_setup",
        )
        attach_position_snapshots(payload, [bip_snap])

        # Emit unified animation_steps. BIP is now a 2-step turn:
        # Step 1 = setup walk-in (SF carries ball to baseline; everyone moves
        # to BIP destinations). Step 2 = inbound pass (SF→PG; other 8 continue
        # toward Step 1 destinations). See transition_bridge.build_bip_animation_steps.
        try:
            from BackEnd.utils.transition_bridge import (
                build_bip_animation_steps,
                build_sip_animation_steps,
            )

            sf_player = offense_team.lineup.get("SF")
            pg_player = offense_team.lineup.get("PG")
            sf_id = str(getattr(sf_player, "player_id", "") or "")
            pg_id = str(getattr(pg_player, "player_id", "") or "")

            setup_coords = self._inbound_setup_coords_from_dest(
                o_dest, d_dest, offense_team.lineup, defense_team.lineup
            )

            prior_turns = getattr(game, "turns", None) or []
            prior_turn = prior_turns[-1] if prior_turns else None
            prior_final_coords, prior_final_bh_id = self._resolve_inbound_prior_seam(prior_turn)

            clock_state = getattr(game, "game_state", {}) or {}
            clock_r = float(clock_state.get("time_remaining", 0) or 0)
            shot_r = float(clock_state.get("shot_clock_remaining", 0) or 0)

            use_triangle_seam = bool((game.game_state or {}).get("inbound_seam_from_triangle"))

            if sf_id and pg_id and prior_final_coords and setup_coords:
                anim_steps = None
                if use_triangle_seam:
                    # Quarter/timeout break: 3-step walk/hold/pass from triangle
                    # (same structure as SIP — no rim pickup).
                    anim_steps = build_sip_animation_steps(
                        off_lineup=offense_team.lineup,
                        def_lineup=defense_team.lineup,
                        prior_final_coords=prior_final_coords,
                        prior_final_ball_handler_id=prior_final_bh_id,
                        setup_coords=setup_coords,
                        sf_id=sf_id,
                        pg_id=pg_id,
                        clock_remaining_at_start=clock_r,
                        shot_clock_remaining_at_start=shot_r,
                    )
                else:
                    # Made-shot / live-play BIP: 4-step rim pickup sequence.
                    ball_start_coord = (
                        dict(MADE_SHOT_SWEET_SPOT_AWAY_RIM)
                        if not is_away_offense
                        else dict(MADE_SHOT_SWEET_SPOT_HOME_RIM)
                    )
                    anim_steps = build_bip_animation_steps(
                        off_lineup=offense_team.lineup,
                        def_lineup=defense_team.lineup,
                        prior_final_coords=prior_final_coords,
                        setup_coords=setup_coords,
                        sf_id=sf_id,
                        pg_id=pg_id,
                        ball_start_coord=ball_start_coord,
                        is_fast_break_after_make=False,
                        fcp_setup=next_defensive_setup == "FCP",
                        clock_remaining_at_start=clock_r,
                        shot_clock_remaining_at_start=shot_r,
                    )
                if anim_steps:
                    payload["animation_steps"] = anim_steps
                    self._stamp_inbound_hco_handoff(payload, sf_id, pg_id)
        except Exception as e:
            import logging
            logging.warning("build_bip_animation_steps failed: %s", e)

        return payload

    def run_micro_turn(self):
        # Increment micro turn counter
        self.game.micro_turn_count += 1

        def convert_players(obj):
            """Recursively replace Player objects with serializable dicts."""
            if isinstance(obj, Player):
                return player_to_dict(obj)
            if isinstance(obj, list):
                return [convert_players(x) for x in obj]
            if isinstance(obj, dict):
                return {k: convert_players(v) for k, v in obj.items()}
            return obj

        # Snapshot player stats to compute deltas after the turn
        pre_stats = {}
        for team in (self.game.home_team, self.game.away_team):
            for player in team.get_all_players():
                pre_stats[player.player_id] = player.stats["game"].copy()

        # STEP 1: Set strategy calls (tempo + aggression)
        self.set_strategy_calls()
        
        # ✅ Situational Logic (Q4/OT): tempo and temp overrides (revert when situation ends)
        from BackEnd.utils import situational_logic as sl
        game_state = self.game.game_state
        time_remaining = game_state.get("time_remaining")
        quarter = getattr(self.game, "quarter", None)
        if sl.is_situational_active(quarter) and time_remaining is not None:
            if sl.is_slow_it_down(self.game, time_remaining):
                self.game.offense_team.strategy_calls["tempo_call"] = "slow"
                game_state["_situational_fast_break_override_team_id"] = self.game.offense_team.team_id
            else:
                game_state.pop("_situational_fast_break_override_team_id", None)
            if sl.is_quick_shot(self.game, time_remaining):
                self.game.offense_team.strategy_calls["tempo_call"] = "fast"
                game_state["_situational_quick_shot_fcp_hct_override"] = True
            else:
                game_state.pop("_situational_quick_shot_fcp_hct_override", None)
        else:
            game_state.pop("_situational_fast_break_override_team_id", None)
            game_state.pop("_situational_quick_shot_fcp_hct_override", None)
        
        # ✅ LOG: Check for Playcall Center overrides at start of turn
        # ✅ PERFORMANCE: Skip Playcall Center checks during full simulation (full_sim=True)
        # Playcall Center is user-specific UI feature, not needed when simming games
        is_full_simulation = self.game.game_state.get("_is_full_simulation", False)
        
        # ✅ SS&S: Use game_state["user_team_side"] instead of is_user_team flag (more reliable, persists to DB)
        user_team_side = self.game.game_state.get("user_team_side")
        user_team = None
        if user_team_side == "home":
            user_team = self.game.home_team
        elif user_team_side == "away":
            user_team = self.game.away_team
        
        # Only check Playcall Center overrides if not in full simulation mode
        if user_team and not is_full_simulation:
            offense_override = user_team.strategy_calls.get("offense_call")
            defense_override = user_team.strategy_calls.get("defense_call")
            aggression_override = user_team.strategy_calls.get("aggression_override")
            
            offense_source = "PLAYCALL CENTER" if offense_override else "STANDARD LOGIC"
            defense_source = "PLAYCALL CENTER" if defense_override else "STANDARD LOGIC"
            aggression_source = "PLAYCALL CENTER" if aggression_override else "STANDARD LOGIC"
        # else: skip override check (full sim or no user_team)

        # ✅ DEBUG: Log offensive_state transition (previous turn → current turn)
        # This is the critical transition point where offensive_state determines routing
        state = self.game.game_state.get("offensive_state", "HCO")
        # Use len(turns) + 1 to match frontend turnCount (1-based, accounts for current turn being added)
        turn_num = len(self.game.turns) + 1
        from BackEnd.constants import DEBUG
        time_remaining = self.game.game_state.get("clock", "N/A")
        
        # Get previous turn's offensive_state (stored in game_state for tracking)
        previous_state = self.game.game_state.get("_previous_offensive_state", "N/A (first turn)")
        
        # ✅ PERFORMANCE: Skip verbose logging during full simulations (hundreds of turns per quarter)
        # Keep logging for turn-by-turn mode where users need debug info
        if not is_full_simulation:
            logging.info(f"🔄 [OFFENSIVE_STATE TRANSITION] Turn #{turn_num} - BEFORE ROUTING", {
                "turn_number": turn_num,
                "previous_offensive_state": previous_state,
                "current_offensive_state": state,
                "time_remaining": time_remaining,
                "offense_team": self.game.offense_team.name,
                "defense_team": self.game.defense_team.name,
                "transition": f"{previous_state} → {state}",
                "note": "This is the offensive_state that determines routing for this turn"
            })
        
        # Store current state as previous for next turn
        self.game.game_state["_previous_offensive_state"] = state
        
        # Create debug string for frontend display
        debug_turn_start = f"***** RUN TURN, turn number: {turn_num}, time remaining: {time_remaining}, offensive state: {state} *****"
        # ✅ PERFORMANCE: Skip turn header log during full simulations
        if not is_full_simulation:
            logging.info(debug_turn_start)
        # if state in ["HCO", "HALF_COURT"]:
        #     print(f"{self.game.offense_team.name}: {self.game.game_state['current_playcall']}")
        #     print(f"{self.game.defense_team.name}: {self.game.game_state['defense_playcall']}")

        # STEP 3: Route based on offensive state
        result = None
        from BackEnd.utils import situational_logic as sl
        shot_clock_remaining = int(game_state.get("shot_clock_remaining", min(30, int(game_state.get("time_remaining", 30) or 30))))
        game_clock_remaining = int(game_state.get("time_remaining", 0) or 0)

        # Defensive scrub: free_throws_remaining can occasionally leak across non-FT turns.
        # Keep FT state only when there is coherent FT context.
        free_throws_remaining = int(game_state.get("free_throws_remaining", 0) or 0)
        if free_throws_remaining > 0:
            timeout_next_play_type = str(game_state.get("timeout_next_play_type") or "").upper()
            last_turn = self.game.turns[-1] if self.game.turns and isinstance(self.game.turns[-1], dict) else {}
            last_turn_next_play = str(last_turn.get("next_play_type") or "").upper()
            last_turn_current = str(last_turn.get("current_turn") or "").upper()
            has_ft_context = (
                str(state).upper() == "FREE_THROW"
                or timeout_next_play_type == "FREE_THROW"
                or last_turn_next_play == "FREE_THROW"
                or last_turn_current == "FREE_THROW"
            )
            if not has_ft_context:
                logging.warning(
                    "🧭 [FT SCRUB TRACE] Clearing stale free_throws_remaining=%s state=%s timeout_next_play_type=%s last_turn_current=%s last_turn_next_play=%s",
                    free_throws_remaining,
                    state,
                    timeout_next_play_type,
                    last_turn_current,
                    last_turn_next_play,
                )
                game_state["free_throws_remaining"] = 0
                game_state["one_and_one"] = False

        # ✅ Final Turn (Q4/OT): clear "triggered" flag when quarter/period changes so each period gets one chance
        quarter = getattr(self.game, "quarter", None)
        if game_state.get("_last_final_turn_quarter") != quarter:
            game_state["_last_final_turn_quarter"] = quarter
            game_state["final_turn_triggered_this_period"] = False

        # ✅ Final Turn (Phase 6): first possession with time_remaining <= 30s triggers Final Turn (all quarters + OT).
        # OREB and Fast Break: excluded by design — state must be HCO, HCT, or FCP. The *next* turn after OREB/FB
        # (when time is still <= 30 and quarter >= 4) is the one evaluated for Final Turn.
        time_remaining_sec = game_state.get("time_remaining")
        final_turn_eligible = (
            quarter is not None
            and time_remaining_sec is not None
            and int(time_remaining_sec) <= 30
            and state != "FAST_BREAK"
            and state in ("HCO", "HCT", "FCP")
            and not game_state.get("final_turn_triggered_this_period")
        )
        if final_turn_eligible:
            game_state["final_turn_triggered_this_period"] = True
            if quarter >= 4:
                # Q4/OT: decide subtype (FINAL_HOLD, Force Foul, Quick Shot, or normal final shot)
                slow = sl.is_slow_it_down(self.game, time_remaining_sec)
                quick = sl.is_quick_shot(self.game, time_remaining_sec)
                force_foul = sl.should_force_foul(self.game, time_remaining_sec)
                if slow and not force_foul:
                    # FINAL_HOLD: hold until 0, no shot, no fouls/turnovers
                    result = self._build_final_hold_result(time_remaining_sec)
                elif slow and force_foul:
                    # Phase 6 edge case: Slow It Down + Force Foul — execute Force Foul (existing logic).
                    # No special Final Turn alignment for this possession; victim = current ball handler / PG.
                    sl.log_force_foul_debug(
                        self.game,
                        "FINAL_TURN_TRIGGER",
                        time_remaining=time_remaining_sec,
                        note="slow+force_foul → _execute_final_turn_force_foul",
                    )
                    result = self._execute_final_turn_force_foul()
                elif quick:
                    # Normal Quick Shot turn — fall through to state routing (don't set result)
                    pass
                else:
                    # Normal final shot (trailing/tied): use Final Turn play execution (Phase 2)
                    game_state["final_turn_shot_this_turn"] = True
            else:
                # Qs 1–3: Final Turn shot (same play execution as Q4 "normal" final shot)
                game_state["final_turn_shot_this_turn"] = True

        # ✅ Situational Logic: Force Foul after BIP/SIP — execute first so it runs regardless of next step (HCO, HCT, FCP)
        from BackEnd.engine.phase_resolution import (
            resolve_non_shooting_foul,
            select_defender_closest_to_victim,
        )
        pending_foul = self.game.game_state.pop("situational_force_foul_pending", None)
        if pending_foul:
            victim_id = pending_foul.get("victim_id")
            victim_coords = pending_foul.get("victim_coords") or {"x": 50, "y": 25}
            off_lineup = self.game.offense_team.lineup
            def_lineup = self.game.defense_team.lineup
            victim = None
            for p in off_lineup.values():
                if p and getattr(p, "player_id", None) == victim_id:
                    victim = p
                    break
            if victim and def_lineup:
                d_dest = pending_foul.get("defender_coords_by_pos")
                foul_player = select_defender_closest_to_victim(victim_coords, def_lineup, d_dest)
                if foul_player:
                    sl.log_force_foul_debug(
                        self.game,
                        "INBOUND_PENDING_EXECUTE",
                        time_remaining=game_state.get("time_remaining"),
                        fouler=foul_player,
                        victim=victim,
                        note="situational_force_foul_pending popped",
                    )
                    roles = {
                        "ball_handler": victim,
                        "defender": foul_player,
                        "foul_player": foul_player,
                        "shooter": victim,
                        "screener": None,
                        "passer": None,
                    }
                    self.game.game_state["foul_team"] = "DEFENSE"
                    result = resolve_non_shooting_foul(
                        roles, self.game, time_elapsed_override=sl.force_foul_time_elapsed()
                    )
                    result["offense_team_id"] = self.game.offense_team.team_id
                    result["current_turn"] = "HCO"
                    result["quick_foul"] = True  # Situational Force Foul → frontend announces "Quick Foul"
                    if isinstance(victim_coords, dict):
                        victim.coords = {
                            "x": float(victim_coords.get("x", 50)),
                            "y": float(victim_coords.get("y", 25)),
                        }
                    attach_position_snapshots(
                        result,
                        [
                            build_phase_post_stopper_snapshot(
                                self.game,
                                off_lineup,
                                def_lineup,
                                None,
                                roles,
                                "HCO",
                                "non_shooting_foul",
                                "hco_situational_force_foul_inbound",
                            )
                        ],
                    )

        clock_enforced_states = ("HCO", "FCP", "HCT", "FAST_BREAK")

        low_clock_branch = None

        if result is not None:
            pass  # Force Foul already handled; skip state routing (HCO/HCT/FCP)
        elif state in clock_enforced_states and game_clock_remaining <= 0:
            # At exact 0 game clock, do not run a normal possession.
            # This should terminally hand control back to API quarter-end handling.
            result = self._build_final_hold_result(0)
            result["text"] = "Clock expires before a shot."
            result["forced_shot"] = False
            low_clock_branch = "GAME_CLOCK_LE_0_FINAL_HOLD"
        elif state in clock_enforced_states and shot_clock_remaining <= 0:
            # At exact 0 shot clock: temporary 50/50 behavior.
            # 1) Forced shot path
            # 2) Shot clock violation path
            if random.random() < 0.5:
                result = self._execute_forced_shot(state)
                low_clock_branch = "SHOT_CLOCK_LE_0_FORCED_SHOT"
            else:
                result = self._build_shot_clock_violation_result(state)
                low_clock_branch = "SHOT_CLOCK_LE_0_VIOLATION"
        elif state in clock_enforced_states and game_clock_remaining <= 1:
            # Game clock precedence: force final-turn shot execution at 1 or 0 seconds.
            result = self.resolve_final_turn_shot()
            result["forced_shot"] = True
            result["forced_shot_reason"] = "GAME_CLOCK"
            low_clock_branch = "GAME_CLOCK_LE_1_FORCED_SHOT"
        elif state in clock_enforced_states and shot_clock_remaining <= 1:
            # Force shot-clock attempt at 1 or 0 seconds.
            result = self._execute_forced_shot(state)
            low_clock_branch = "SHOT_CLOCK_LE_1_FORCED_SHOT"
        elif state == "FREE_THROW":
            result = self.resolve_free_throw()
            if isinstance(result, dict):
                try:
                    from BackEnd.engine.ft_step_emitter import build_ft_animation_steps

                    anim_steps = build_ft_animation_steps(result, self.game)
                    if anim_steps:
                        result["animation_steps"] = anim_steps
                except Exception as e:
                    logging.warning("build_ft_animation_steps failed: %s", e)
        elif state == "FAST_BREAK":
            self.logger.log("fb:start")
            self.game.game_state["fastBreakInProgress"] = True
            result = resolve_fast_break_logic(self.game)
        elif state == "FCP":
            self.logger.log("fcp:start")
            result = resolve_full_court_press_logic(self.game)
            # Dynamic FCP returns skeleton:{} — use the FCP-specific emitter when
            # intermediate loop data is present; fall back to legacy skeleton emitter.
            if isinstance(result, dict) and "animation_steps" not in result:
                try:
                    if result.get("fcp_loop_segments"):
                        from BackEnd.engine.dynamic_fcp_step_emitter import (
                            build_dynamic_fcp_animation_steps,
                        )

                        anim_steps = build_dynamic_fcp_animation_steps(
                            result, self.game
                        )
                    else:
                        from BackEnd.engine.skeleton_step_emitter import (
                            build_skeleton_animation_steps,
                        )

                        anim_steps = build_skeleton_animation_steps(
                            result, self.game, turn_type="FCP"
                        )
                    if anim_steps is not None:
                        result["animation_steps"] = anim_steps
                        fcp_result_type = (result.get("result_type") or "").upper()
                        if fcp_result_type in ("MAKE", "MISS", "BLOCK") and anim_steps:
                            first_clock = (anim_steps[0].get("start") or {}).get("clock") or {}
                            last_clock = (anim_steps[-1].get("end") or {}).get("clock") or {}
                            cs_start = first_clock.get("clock_remaining")
                            cs_end = last_clock.get("clock_remaining")
                            if cs_start is not None and cs_end is not None:
                                schema_game_burn = max(0.0, float(cs_start) - float(cs_end))
                                result["time_elapsed"] = int(round(schema_game_burn))
                    elif result.get("fcp_loop_segments"):
                        from BackEnd.engine.fcp_step_trace import log_fcp_emitter_bail

                        log_fcp_emitter_bail(
                            "build_dynamic_fcp_animation_steps returned None",
                            segment_count=len(result.get("fcp_loop_segments") or []),
                            result_type=result.get("result_type"),
                        )
                except Exception as e:
                    logging.warning(
                        "build_dynamic_fcp_animation_steps (FCP) failed: %s", e
                    )
        elif state == "HCT":
            self.logger.log("hct:start")
            result = resolve_half_court_trap_logic(self.game)
            # Parallel-build: stamp unified animation_steps for HCT. Dynamic
            # HCT returns skeleton:{} so the standard skeleton emitter bails;
            # use the dynamic-specific helper. Static HCT (legacy) is wired
            # internally by resolve_half_court_trap_logic.
            if isinstance(result, dict) and "animation_steps" not in result:
                try:
                    from BackEnd.engine.dynamic_hct_step_emitter import (
                        build_dynamic_hct_animation_steps,
                    )
                    anim_steps = build_dynamic_hct_animation_steps(result, self.game)
                    if anim_steps is not None:
                        result["animation_steps"] = anim_steps
                        # Align time_elapsed with the schema's game-clock burn
                        # for MAKE/MISS/BLOCK HCT shot turns (§7 fast break),
                        # mirroring the FCP realignment above — the legacy
                        # step_clock_seconds sum omits the [ball_flight] +
                        # [bounce] sub-step durations.
                        hct_result_type = (result.get("result_type") or "").upper()
                        if hct_result_type in ("MAKE", "MISS", "BLOCK") and anim_steps:
                            first_clock = (anim_steps[0].get("start") or {}).get("clock") or {}
                            last_clock = (anim_steps[-1].get("end") or {}).get("clock") or {}
                            cs_start = first_clock.get("clock_remaining")
                            cs_end = last_clock.get("clock_remaining")
                            if cs_start is not None and cs_end is not None:
                                schema_game_burn = max(0.0, float(cs_start) - float(cs_end))
                                result["time_elapsed"] = int(round(schema_game_burn))
                except Exception as e:
                    logging.warning(
                        "build_dynamic_hct_animation_steps failed: %s", e
                    )
        else:
            # HCO: normal half-court offense (Force Foul after DREB is now handled at DREB time in game_manager)
            if result is not None:
                # Force Foul result already set; skip set_playcalls and resolve_half_court_offense
                pass
            else:
                calls = self.set_playcalls()
                self.game.game_state["current_playcall"] = calls["offense"]
                self.game.game_state["defense_playcall"] = calls["defense"]
            
                # Track defensive playcall usage
                def_team = self.game.defense_team
                defense_playcall = calls["defense"]  # canonical row key, e.g. man, 2-3-zone
                tracking_name = defense_scouting_row_key(defense_playcall)
                if tracking_name in def_team.scouting_data["defense"]:
                    # Get offensive play type and focus for granular tracking
                    # ✅ SS&S: Use offense_play_type as single source of truth (works for both user overrides and normal selection)
                    offense_play_type_raw = calls.get("offense_play_type", "")
                    offense_play_type = offense_play_type_raw.lower() if offense_play_type_raw else ""
                    offense_focus = calls.get("offense_focus", "")  # "inside", "attack", "outside"
                    
                    # Normalize play type (set_play -> set) to match phase_resolution.py
                    if offense_play_type == "set_play":
                        offense_play_type = "set"
                    
                    def_team.scouting_data["defense"][tracking_name]["used"] += 1
                    def_team.scouting_data["defense"][tracking_name]["game_stats"]["used"] += 1
                    
                    # Track granular usage by play type
                    if offense_play_type == "motion":
                        def_team.scouting_data["defense"][tracking_name]["game_stats"]["vs_motion"]["attempts"] += 1
                    elif offense_play_type == "set":
                        def_team.scouting_data["defense"][tracking_name]["game_stats"]["vs_set"]["attempts"] += 1
                    
                    # Track granular usage by focus type
                    if offense_focus in ["inside", "attack", "outside"]:
                        def_team.scouting_data["defense"][tracking_name]["game_stats"][f"vs_{offense_focus}"]["attempts"] += 1
                        
                        # Track combination of play type + focus
                        if offense_play_type == "motion":
                            def_team.scouting_data["defense"][tracking_name]["game_stats"][f"vs_motion_{offense_focus}"]["attempts"] += 1
                        elif offense_play_type == "set":
                            def_team.scouting_data["defense"][tracking_name]["game_stats"][f"vs_set_{offense_focus}"]["attempts"] += 1
                
                # Calculate EV (Expected Value) for the playcall matchup
                ev = self.calculate_ev(
                    offensive_playcall=calls["offense"],
                    defensive_playcall=calls["defense"],
                    offensive_lineup=self.game.offense_team.lineup,
                    defensive_lineup=self.game.defense_team.lineup,
                    offensive_team=self.game.offense_team,
                    defensive_team=self.game.defense_team
                )
                
                # Store EV score in scouting data
                self._store_ev_score(ev, calls, self.game.offense_team, self.game.defense_team)
                
                # Final Turn shot uses dedicated resolver (Phase 2 will add alignment + shot); for now stub to normal HCO
                if game_state.pop("final_turn_shot_this_turn", False):
                    result = self.resolve_final_turn_shot()
                else:
                    result = self.resolve_half_court_offense()
                # Add playcalls to result for frontend display
                # ✅ FIX 2: Use current_playcall from game_state (may be overridden for Motion plays)
                # This ensures Motion play overrides (like "3-2 Motion") are reflected in the result
                result["offensive_playcall"] = self.game.game_state.get("current_playcall", calls["offense"])
                result["defensive_playcall"] = calls["defense"]
                result["defensive_playcall_display"] = defense_display_name(calls["defense"])
                # ✅ PERFORMANCE: Skip playcall logging during full simulations
                if not is_full_simulation:
                    offense_name = calls["offense"]
                    defense_name = calls["defense"]
                    logging.info(f"🎮 [PLAYCALL RESULT] Added to result: offensive_playcall='{offense_name}', defensive_playcall='{defense_name}'")
                # ✅ SS&S: Set offense_override_cleared flag from calls (overrides default False)
                result["offense_override_cleared"] = calls.get("offense_override_cleared", False)
                
                # Add play type and focus for frontend display
                # ✅ SS&S: Use offense_play_type as single source of truth (works for both user overrides and normal selection)
                offense_play_type = calls.get("offense_play_type", None)
                # Capitalize for display (Motion/Set) if we have a value, otherwise use "-"
                result["offensive_play_type"] = offense_play_type.title() if offense_play_type else "-"
                result["offensive_play_focus"] = calls.get("offense_focus", None)
                result["defensive_play_type"] = calls.get("defense_type", "-")
                result["defensive_play_focus"] = calls.get("defense_focus", None)
                
                # Add EV to result for frontend display
                result["ev"] = ev

                # Situational Logic (Q4/OT): flags for HCO turn-start announcements (Slow It Down / Quick Shot)
                from BackEnd.utils import situational_logic as sl
                time_remaining = self.game.game_state.get("time_remaining")
                result["slow_it_down"] = sl.is_slow_it_down(self.game, time_remaining)
                result["quick_shot"] = sl.is_quick_shot(self.game, time_remaining)

        # ✅ SS&S: Set offense_team_id (single source of truth)
        # This represents the team on offense DURING this turn (for animations)
        result["offense_team_id"] = self.game.offense_team.team_id
        # ✅ REMOVED: possession_team_id (fully migrated to offense_team_id in SS&S refactor)
        
        # ✅ SS&S: Initialize offense_override_cleared flag (starts False, set to True if user override was used and cleared)
        # Only initialize if not already set (HCO turns set it from calls, other turn types default to False)
        if "offense_override_cleared" not in result:
            result["offense_override_cleared"] = False
        
        # ✅ SS&S: Set current_turn from the state we used for routing (start of turn), not post-handler state.
        # Handlers update offensive_state for the *next* turn; current_turn must reflect the turn we just ran.
        result["current_turn"] = state  # HCO, FCP, HCT, FAST_BREAK, FREE_THROW, or OREB

        # ✅ SS&S: Copy next_play_type to next_turn for explicit naming
        if "next_play_type" in result and result["next_play_type"]:
            result["next_turn"] = result["next_play_type"]

        # STEP 4: Final updates (clock, logs, animation)
        try:
            self.update_clock_and_possession(result)
            self.logger.log_turn_result(result)
            
            # ✅ DEBUG: Log offensive_state after handler execution (current turn → next turn)
            # This shows what offensive_state will be for the NEXT turn
            final_state = self.game.game_state.get("offensive_state", "HCO")
            next_play_type = result.get("next_play_type", "None")
            result_type = result.get("result_type", "N/A")
            
            # ✅ PERFORMANCE: Skip verbose logging during full simulations
            if not is_full_simulation:
                logging.info(f"🔄 [OFFENSIVE_STATE TRANSITION] Turn #{turn_num} - AFTER HANDLER", {
                    "turn_number": turn_num,
                    "result_type": result_type,
                    "current_offensive_state": state,  # State used for routing this turn
                    "next_offensive_state": final_state,  # State that will be used for next turn
                    "next_play_type": next_play_type,  # Informational only (not used for routing)
                    "transition": f"{state} → {final_state}",
                    "state_changed": state != final_state,
                    "offense_team": self.game.offense_team.name,
                    "defense_team": self.game.defense_team.name,
                    "note": "Handler may have changed offensive_state for next turn"
                })
            # ✅ DEBUG: Log fast break data if present (to verify it's being preserved)
            if result.get("fast_break") or result.get("result_type") == "DEFENSIVE_STOP":
                import json
                debug_data = {
                    "result_type": result.get("result_type"),
                    "fast_break": result.get("fast_break"),
                    "has_roles": "roles" in result,
                    "outlet_passer": result.get("roles", {}).get("outlet_passer") if result.get("roles") else None,
                    "outlet_receiver": result.get("roles", {}).get("outlet_receiver") if result.get("roles") else None,
                    "ball_handler_id": getattr(result.get("ball_handler"), "player_id", None) if result.get("ball_handler") else None,
                    "has_animations": len(result.get("animations", [])) > 0,
                    "animation_count": len(result.get("animations", [])),
                    "rebounderId": result.get("rebounderId"),  # ✅ Add rebounderId to debug output
                    "rebound_type": result.get("rebound_type")  # ✅ Add rebound_type to debug output
                }
                # Debug log removed to declutter output
            
            # ✅ PERFORMANCE: Skip verbose logging during full simulations
            # Note: Keeping this log for backward compatibility in turn-by-turn mode, but the detailed log above is more useful
            if not is_full_simulation:
                logging.info(f"🔄 [OFFENSIVE_STATE TRANSITION] Turn #{turn_num} Complete", {
                    "turn_number": turn_num,
                    "result_type": result_type,
                    "previous_offensive_state": state,  # State at start of this turn
                    "next_offensive_state": final_state,  # State for next turn (set by handler)
                    "next_play_type": next_play_type,  # Informational only (not used for routing)
                    "transition": f"{state} → {final_state}",
                    "state_changed": state != final_state,
                    "offense_team": self.game.offense_team.name,
                    "defense_team": self.game.defense_team.name,
                    "note": "next_offensive_state is what will be used to route the NEXT turn"
                })
            
            # ✅ REMOVED: Overwrite logic that was causing transition bugs
            # 
            # Rationale: Handlers (shot_manager, phase_resolution, etc.) are the source of truth for offensive_state.
            # They explicitly set offensive_state when needed (e.g., "FREE_THROW" for AND-1, "FAST_BREAK" for steals).
            # 
            # next_play_type is informational only (for frontend display/logging), not for routing.
            # If a handler doesn't set offensive_state, that's a bug in the handler, not something we should patch here.
            # 
            # This restores the previous transition system behavior where handlers control state transitions.
            # 
            # Examples of handlers setting offensive_state:
            # - shot_manager.py line 351: Sets "FREE_THROW" for AND-1
            # - shot_manager.py line 372: Sets pressure_type for made shots
            # - shot_manager.py line 405: Sets "FREE_THROW" for missed shots with fouls
            # - phase_resolution.py line 585: Sets pressure_type after free throw
            # - phase_resolution.py line 698: Sets "FAST_BREAK" for steals
            # - phase_resolution.py line 714: Sets "HCO" for dead ball turnovers
                
        finally:
            if state == "FAST_BREAK":
                self.logger.log("fb:end")
                self.game.game_state["fastBreakInProgress"] = False
        # If animations weren't assigned yet (e.g. fast break, free throw), use fallback.
        # Skip the fallback entirely when the turn already has schema-native
        # ``animation_steps`` (HCO / HCT / DREB / FB-migrated turns): those turns
        # are rendered by the new playback engine and do not need legacy
        # ``animations[]``. Phase 2 of HCO UESS migration drops the legacy field
        # from HCO turn_result; this gate prevents the fallback from re-stamping it.
        has_animation_steps = isinstance(result.get("animation_steps"), list) and len(result["animation_steps"]) > 0
        if "animations" not in result and not has_animation_steps:
            # Phase 5: Final Turn shot — use skeleton_to_animations for play execution (BH/shooter movement, then shot)
            if result.get("final_turn") and result.get("skeleton"):
                from BackEnd.models.animator import Animator
                animator = Animator(self.game)
                off_lineup = self.game.offense_team.lineup
                def_lineup = self.game.defense_team.lineup
                result["animations"] = animator.skeleton_to_animations(
                    result["skeleton"], off_lineup, def_lineup, add_defenders=True, is_fcp=False, is_hct=False
                )
            else:
                roles = result.get("roles")
                if roles:
                    # ✅ FIX: Reconstruct player references if they're missing from serializable_roles
                    # serializable_roles may not include Player objects, but capture_halfcourt_animation needs them
                    if "shooter" not in roles and result.get("shooter"):
                        roles["shooter"] = result["shooter"]
                    if "ball_handler" not in roles and result.get("ball_handler"):
                        roles["ball_handler"] = result["ball_handler"]

                    from BackEnd.models.animator import Animator
                    animator = Animator(self.game)
                    result["animations"] = animator.capture_halfcourt_animation(
                        roles=roles,
                        event_step=result.get("event_step")
                    )
                else:
                    result["animations"] = []  # No animation possible (e.g., free throw or turnover with no roles)
        # ✅ REMOVED: possession_team_id is now set BEFORE update_clock_and_possession (line 373)
        # This ensures it represents the team on offense DURING the turn, not after any flips

        if "roles" in result:
            result["roles"] = convert_players(result["roles"])

        for key in [
            "ball_handler",
            "shooter",
            "passer",
            "screener",
            "defender",
            "stealer_name",
            "victim_name",
        ]:
            if key in result:
                result[key] = get_name_safe(result[key])
        for key in [
            "ball_handler",
            "shooter",
            "shooter_id",
            "screener",
            "passer",
            "defender",
            "stealer_name",
            "victim_name",
            "stealer_id",
            "victim_id",
        ]:
            if key in result:
                val = result[key]
                if hasattr(val, "name"):
                    result[key] = val.name
                elif hasattr(val, "player_id"):  # fallback to player_id
                    result[key] = val.player_id
                else:
                    result[key] = str(val)  # final fallback (safe for non-class data)

        # Use len(turns) + 1 to match frontend turnCount (1-based, accounts for current turn being added)
        result["turn_count"] = len(self.game.turns) + 1
        # result["possession_team_id"] = self.game.offense_team.team_id
        # Player.coords sync: GameManager._append_turn → sync_lineup_coords_from_turn

        # Print turn result summary for debugging
        # Use len(turns) + 1 to match frontend turnCount (1-based, accounts for current turn being added)
        turn_num = len(self.game.turns) + 1
        result_type = result.get("result_type", "N/A")
        next_play_type = result.get("next_play_type", "None")
        next_defensive_setup = result.get("next_defensive_setup", "None")
        text = result.get("text", "")
        possession_flips = result.get("possession_flips", False)
        from BackEnd.constants import DEBUG
        
        # Create debug string for frontend display
        offense_team_id = result.get("offense_team_id", "None")
        # When the next play is a Fast Break, also surface the FB play key
        # (covert_release / rim_runner / triangle / etc.) so logs explicitly
        # show which FB variant fired. Pulls from the current turn's
        # `fast_break_play` (set on the FB-producing turn) AND the upcoming
        # turn's `pending_dreb_fb_play_key` (set during shot resolution for
        # DREB → FB transitions, popped when the FB turn resolves).
        next_play_type_str = str(next_play_type) if next_play_type else "None"
        if next_play_type == "FAST_BREAK":
            fb_play = (
                result.get("fast_break_play")
                or self.game.game_state.get("pending_dreb_fb_play_key")
                or "?"
            )
            next_play_type_str = f"{next_play_type} ({fb_play})"
        debug_turn_result = f"Turn {turn_num} RESULT: {result_type} | Offense: {offense_team_id} | Next: {next_play_type_str} | Defense Setup: {next_defensive_setup} | Possession Flips: {possession_flips}"
        
        if DEBUG:
            print(debug_turn_result)
        
        # Add debug info to result for frontend display
        result["debug_turn_start"] = debug_turn_start
        result["debug_turn_result"] = debug_turn_result
        
        # self._print_turn_summary(result, state)

        result["home_lineup"] = serialize_lineup(self.game.home_team.lineup)
        result["away_lineup"] = serialize_lineup(self.game.away_team.lineup)

        result["score"] = dict(self.game.score)

        # Include current team stats for frontend updates (from scouting_data)
        result["team_stats"] = {
            self.game.home_team.name: {
                "offense": self.game.home_team.scouting_data.get("offense", {}),
                "defense": self.game.home_team.scouting_data.get("defense", {})
            },
            self.game.away_team.name: {
                "offense": self.game.away_team.scouting_data.get("offense", {}),
                "defense": self.game.away_team.scouting_data.get("defense", {})
            }
        }
        
        # Include cumulative team stats (from all players) for S1 tab
        # Update team stats before sending
        self.game.update_team_stats()
        result["team_totals"] = {
            self.game.home_team.name: self.game.home_team.get_team_game_stats(),
            self.game.away_team.name: self.game.away_team.get_team_game_stats()
        }
        
        # Include play data for tooltips (effectiveness and tracking)
        result["team_plays"] = {
            self.game.home_team.name: list(self.game.home_team.plays.values()),
            self.game.away_team.name: list(self.game.away_team.plays.values())
        }

        # Compute stat deltas for each player
        # Exclude REB from deltas since it's automatically calculated from OREB + DREB
        # Exclude Outlet_Score_List since it's a list, not a numeric stat
        # The frontend will calculate REB from OREB + DREB to avoid double-counting
        deltas = {}
        for team in (self.game.home_team, self.game.away_team):
            for player in team.get_all_players():
                prev = pre_stats.get(player.player_id, {})
                diff = {}
                for stat in player.stats["game"]:
                    if stat == "REB" or stat == "Outlet_Score_List" or stat == "Shot_Result_List":
                        continue  # Skip REB (calculated) and Outlet_Score_List (list, not numeric)
                    current_val = player.stats["game"].get(stat, 0)
                    prev_val = prev.get(stat, 0)
                    delta = current_val - prev_val
                    if delta != 0:
                        diff[stat] = delta
                if diff:
                    deltas[player.player_id] = {"team": team.name, "stats": diff}
                    
                    # ✅ COMMENTED OUT: Assist/rebound debug logs (cluttering transition debugging)
                    # if "AST" in diff and result.get("result_type") in ["MAKE", "MISS"]:
                    #     logging.info(f"🎯 ASSIST DELTA: {get_name_safe(player)} has AST in deltas: {diff}, result_type={result.get('result_type')}")
                    
                    # ✅ COMMENTED OUT: Free throw rebound debug logs
                    # if result.get("result_type") == "FREE_THROW" and ("OREB" in diff or "DREB" in diff):
                    #     logging.info(f"🏀 Free Throw Turn Deltas: {get_name_safe(player)} has rebound in deltas: {diff}")
        
        # ✅ COMMENTED OUT: Free throw rebound debug logging
        # if result.get("result_type") == "FREE_THROW" and result.get("rebound_type"):
        #     rebounder_id = result.get("rebounderId")
        #     logging.info(f"🏀 Free Throw Turn - rebound_type={result.get('rebound_type')}, rebounderId={rebounder_id}")
        #     if rebounder_id:
        #         if rebounder_id in deltas:
        #             logging.info(f"🏀 Free Throw Turn - Rebounder {rebounder_id} found in deltas: {deltas[rebounder_id]}")
        #         else:
        #             logging.warning(f"⚠️ Free Throw Turn - Rebounder {rebounder_id} NOT found in deltas. Available player_ids: {list(deltas.keys())}")
        #             if rebounder_id in pre_stats:
        #                 prev_reb = pre_stats[rebounder_id].get(result.get("rebound_type"), 0)
        #                 for team in (self.game.home_team, self.game.away_team):
        #                     for player in team.get_all_players():
        #                         if player.player_id == rebounder_id:
        #                             current_reb = player.stats["game"].get(result.get("rebound_type"), 0)
        #                             logging.warning(f"⚠️ Free Throw Turn - Rebounder stats mismatch: prev={prev_reb}, current={current_reb}, should_diff={current_reb - prev_reb}, player_name={get_name_safe(player)}")
        #                             if current_reb != prev_reb:
        #                                 expected_diff = {result.get("rebound_type"): current_reb - prev_reb}
        #                                 logging.error(f"❌ Free Throw Turn - Rebound stat recorded but NOT in deltas! Expected: {expected_diff}, Player: {get_name_safe(player)}")
        #                             break
        #             else:
        #                 logging.warning(f"⚠️ Free Throw Turn - Rebounder {rebounder_id} not found in pre_stats")
        
        result["deltas"] = deltas
        
        # ✅ COMMENTED OUT: Assist debug logging
        # if result.get("result_type") == "MAKE":
        #     has_ast_in_deltas = any("AST" in delta.get("stats", {}) for delta in deltas.values())
        #     if has_ast_in_deltas:
        #         ast_players = []
        #         for pid, delta in deltas.items():
        #             if "AST" in delta.get("stats", {}):
        #                 for team in (self.game.home_team, self.game.away_team):
        #                     player = team.get_player_by_id(pid)
        #                     if player:
        #                         ast_players.append(get_name_safe(player))
        #                         break
        #         logging.info(f"🎯 ASSIST CHECK: Made shot - AST found in deltas for: {', '.join(ast_players) if ast_players else 'unknown'}")
        #     else:
        #         delta_summary = {pid: list(d.get("stats", {}).keys()) for pid, d in deltas.items()}
        #         logging.warning(f"⚠️ ASSIST CHECK: Made shot - NO AST found in deltas! Deltas: {delta_summary}")
        
        # ✅ COMMENTED OUT: Free throw rebound deltas debug logging
        # if result.get("result_type") == "FREE_THROW" and result.get("rebound_type"):
        #     rebounder_id = result.get("rebounderId")
        #     if rebounder_id and rebounder_id in deltas:
        #         rebounder_deltas = deltas[rebounder_id].get("stats", {})
        #         logging.info(f"🏀 Free Throw Turn Result: rebound_type={result.get('rebound_type')}, rebounderId={rebounder_id}, deltas={rebounder_deltas}")
        #     else:
        #         logging.warn(f"⚠️ Free Throw Rebound Missing in Deltas: rebound_type={result.get('rebound_type')}, rebounderId={rebounder_id}, deltas_keys={list(deltas.keys())}")
        
        # Include current energy levels for all active players (for frontend fatigue display)
        player_energy = {}
        for team in (self.game.home_team, self.game.away_team):
            for pos, player in team.lineup.items():
                if player is None:
                    continue  # Skip None players in lineup
                player_energy[player.player_id] = {
                    "NG": player.attributes.get("NG", 1.0),
                    "team": team.name
                }
        result["player_energy"] = player_energy
        
        if low_clock_branch:
            logging.warning(
                "🧭 [ZERO CLOCK TRACE] run_micro_turn branch=%s state=%s game_clock_remaining=%s shot_clock_remaining=%s result_type=%s next_play_type=%s next_turn=%s",
                low_clock_branch,
                state,
                game_clock_remaining,
                shot_clock_remaining,
                result.get("result_type") if isinstance(result, dict) else None,
                result.get("next_play_type") if isinstance(result, dict) else None,
                result.get("next_turn") if isinstance(result, dict) else None,
            )
        elif state in clock_enforced_states and (game_clock_remaining <= 2 or shot_clock_remaining <= 2):
            logging.warning(
                "🧭 [ZERO CLOCK TRACE] run_micro_turn near-zero NO_BRANCH state=%s game_clock_remaining=%s shot_clock_remaining=%s",
                state,
                game_clock_remaining,
                shot_clock_remaining,
            )

        # Include strategy calls for frontend strategy bars (actual calls, not settings)
        result["offense_tempo_call"] = self.game.offense_team.strategy_calls.get("tempo_call", "normal")
        result["offense_aggression_call"] = self.game.offense_team.strategy_calls.get("aggression_call", "normal")
        result["defense_tempo_call"] = self.game.defense_team.strategy_calls.get("tempo_call", "normal")
        result["defense_aggression_call"] = self.game.defense_team.strategy_calls.get("aggression_call", "normal")
        
        # Reconcile player point totals with the authoritative team score.
        # Clients should treat ``turn.score`` and ``turn.deltas`` as canonical
        # and never re-apply ``turn.points`` to avoid double counting. To guard
        # against any desync, compare the team score against the sum of player
        # PTS at the end of a possession or quarter and push a corrective delta
        # if they differ.
        self._reconcile_player_points(result)

        # Sync and expose fouls/clock/quarter for live scoreboard updates
        self.game.game_state["team_fouls"] = {
            self.game.home_team.name: self.game.home_team.team_fouls,
            self.game.away_team.name: self.game.away_team.team_fouls,
        }
        result["homeFouls"] = self.game.home_team.team_fouls
        result["awayFouls"] = self.game.away_team.team_fouls
        
        result["clock"] = self.game.game_state["clock"]
        result["shot_clock_remaining"] = self.game.game_state.get("shot_clock_remaining", 30)
        result["quarter"] = self.game.game_state["quarter"]
        result["period_label"] = self.game.game_state.get("period_label")
        # Ensure no Player objects remain in the result payload
        result = convert_players(result)

        # Ensure every turn has text for the in-game text scroll
        if not result.get("text") or result.get("text").strip() == "":
            result["text"] = "No text in this turn"

        # ✅ FIX 1: Add offense_team_id to ALL results (SS&S possession system)
        # This is the authoritative team on offense DURING this turn (before any possession flips)
        # Frontend reads this value and displays it (no flip logic in frontend)
        result["offense_team_id"] = self.game.offense_team.team_id

        # print(f"inside run_micro_turn result: {result}")
        
        return result

    def _build_shot_clock_violation_result(self, current_state):
        offense_team = self.game.offense_team
        defense_team = self.game.defense_team
        return {
            "result_type": "DEAD BALL",
            "text": "Shot Clock Violation",
            "turnover_type": "SHOT_CLOCK",
            "time_elapsed": 0,
            "possession_flips": True,
            "next_play_type": "SIDE_INBOUND",
            "next_turn": "SIDE_INBOUND",
            "offense_team_id": offense_team.team_id,
            "defense_team_id": defense_team.team_id,
            "current_turn": current_state,
            "forced_shot": False,
            "events": [],
        }

    def _coords_to_nearest_spot(self, coords):
        from BackEnd.constants import HCO_STRING_SPOTS
        if not isinstance(coords, dict):
            return "key"
        x = coords.get("x")
        y = coords.get("y")
        if x is None or y is None:
            return "key"
        best_spot = "key"
        best_dist = float("inf")
        for spot, s_coords in HCO_STRING_SPOTS.items():
            dx = (s_coords.get("x", 50) - x)
            dy = (s_coords.get("y", 25) - y)
            dist = (dx * dx) + (dy * dy)
            if dist < best_dist:
                best_dist = dist
                best_spot = spot
        return best_spot

    def _execute_forced_shot(self, current_state):
        from BackEnd.constants import ACTIONS, POSITION_LIST
        from BackEnd.utils.shared import get_player_position
        from BackEnd.engine.phase_resolution import select_defender_closest_to_victim

        off_lineup = self.game.offense_team.lineup
        def_lineup = self.game.defense_team.lineup
        ball_handler = self.game.game_state.get("last_ball_handler")
        if not ball_handler:
            ball_handler = off_lineup.get("PG") or next((p for p in off_lineup.values() if p), None)

        if not ball_handler:
            return self._build_shot_clock_violation_result(current_state)

        shooter = ball_handler
        shooter_pos = get_player_position(off_lineup, shooter) or "PG"
        shooter_coords = getattr(shooter, "coords", {"x": 50, "y": 25}) or {"x": 50, "y": 25}
        shooter_spot = self._coords_to_nearest_spot(shooter_coords)
        defender = select_defender_closest_to_victim(shooter_coords, def_lineup, None) if def_lineup else None

        step0 = {"timestamp": 0, "pos_actions": {}}
        step1 = {"timestamp": 300, "pos_actions": {}}
        for pos in POSITION_LIST:
            if pos == shooter_pos:
                step0["pos_actions"][pos] = {"action": ACTIONS["HANDLE"], "location": shooter_spot}
                step1["pos_actions"][pos] = {"action": ACTIONS["SHOOT"], "location": shooter_spot}
            else:
                step0["pos_actions"][pos] = {"action": "stand", "location": "key"}
                step1["pos_actions"][pos] = {"action": "stand", "location": "key"}

        roles = {
            "skeleton": {"steps": [step0, step1]},
            "steps": [step0, step1],
            "ball_handler": ball_handler,
            "shooter": shooter,
            "passer": None,
            "screener": None,
            "defender": defender,
            "shot_type": "inside" if shooter_spot.lower() in ("lower lowpost", "lower midpost", "upper lowpost", "upper midpost", "midlane", "basketspot") else "outside",
            "forced_shot": True,
            "shooter_location": shooter_spot,
        }
        from BackEnd.utils.position_snapshot_ledger import (
            attach_position_snapshots,
            build_skeleton_pre_resolve_shot_snapshot,
        )

        sc_snap = build_skeleton_pre_resolve_shot_snapshot(
            self.game,
            off_lineup,
            def_lineup,
            roles.get("skeleton"),
            roles,
            "HCO",
            "shot_clock_forced_shot",
        )
        result = self.game.shot_manager.resolve_shot(roles)
        attach_position_snapshots(result, [sc_snap])
        result["forced_shot"] = True
        result["forced_shot_reason"] = "SHOT_CLOCK"
        return result

    def _coerce_hco_defense_id(self, raw: str | None) -> str | None:
        """Normalize picks to `scouting_data['defense']` row keys (man, 2-3-zone, ...)."""
        from BackEnd.utils.defense_identity import canonical_scouting_defense_key, resolve_to_defense_id

        if not raw or not isinstance(raw, str):
            return None
        s = raw.strip()
        if not s:
            return None
        if s in ("Zone", "zone", STRATEGY_DEFENSE_ZONE_SENTINEL):
            return self._select_zone_defense_with_playbook_weights()
        ck = canonical_scouting_defense_key(s)
        if ck:
            return ck
        rid = resolve_to_defense_id(s)
        if rid:
            ck2 = canonical_scouting_defense_key(rid)
            if ck2:
                return ck2
        return s

    def set_playcalls(self):
        """
        Two-level play selection system:
        Level 1: Determine motion vs set play based on offense setting
        Level 2: Determine play focus (inside/attack/outside) based on weighted settings
        
        User overrides take precedence for turn-by-turn gameplay.
        """
        
        # ✅ SS&S: Check for user-set calls in team.strategy_calls
        # If offense_call is not None, use it and clear after use
        # If None, use normal selection process
        # ✅ SS&S: Use game_state["user_team_side"] instead of is_user_team flag (more reliable, persists to DB)
        offense_call = None
        user_team_side = self.game.game_state.get("user_team_side")
        is_offense_user = (user_team_side == "home" and self.game.offense_team.is_home_team) or (user_team_side == "away" and not self.game.offense_team.is_home_team)
        
        logging.debug(f"🎮 [PLAYCALL CHECK] Checking for overrides in set_playcalls()")
        logging.debug(f"   - Offense team: {self.game.offense_team.name} (team_id: {self.game.offense_team.team_id}, object_id: {id(self.game.offense_team)}, is_home_team: {self.game.offense_team.is_home_team})")
        # logging.debug(f"   - Home team: {self.game.home_team.name} (team_id: {self.game.home_team.team_id}, object_id: {id(self.game.home_team)})")
        # logging.debug(f"   - Away team: {self.game.away_team.name} (team_id: {self.game.away_team.team_id}, object_id: {id(self.game.away_team)})")
        logging.debug(f"   - user_team_side={user_team_side}, is_offense_user={is_offense_user}")
        logging.debug(f"   - game_object_id: {id(self.game)}")
        if is_offense_user:
            offense_call = self.game.offense_team.strategy_calls.get("offense_call")
            logging.debug(f"🎮 [PLAYCALL CHECK] Checking offense_team.strategy_calls for offense_call")
            logging.debug(f"   - offense_call value: {offense_call}, type: {type(offense_call)}")
            logging.debug(f"   - Full strategy_calls: {self.game.offense_team.strategy_calls}")
            logging.debug(f"   - Team object_id: {id(self.game.offense_team)}")
            if offense_call:
                logging.debug(f"🎮 [PLAYCALL CHECK] ✅ Found user offense call: '{offense_call}'")
            else:
                logging.debug(f"🎮 [PLAYCALL CHECK] ❌ No user offense call found (offense_call is None)")
        else:
            logging.debug(f"🎮 [PLAYCALL DEBUG] Offense team {self.game.offense_team.name} is NOT user team (user_team_side={user_team_side}), skipping offense_call check")
        
        # Check if user team has defense_call set (regardless of current offense/defense)
        # Defense override can be set when user is on offense (for next time they're on defense)
        defense_call = None
        user_team = None
        if user_team_side == "home":
            user_team = self.game.home_team
        elif user_team_side == "away":
            user_team = self.game.away_team
        
        if user_team:
            defense_call = user_team.strategy_calls.get("defense_call")
            logging.debug(f"🎮 [PLAYCALL CHECK] Checking user_team.strategy_calls for defense_call")
            logging.debug(f"   - User team: {user_team.name} (team_id: {user_team.team_id}, object_id: {id(user_team)})")
            logging.debug(f"   - defense_call value: {defense_call}, type: {type(defense_call)}")
            logging.debug(f"   - Full strategy_calls: {user_team.strategy_calls}")
            if defense_call:
                logging.debug(f"🎮 [PLAYCALL CHECK] ✅ Found user defense call: '{defense_call}'")
            else:
                logging.debug(f"🎮 [PLAYCALL CHECK] ❌ No user defense call found (defense_call is None)")
        else:
            logging.debug(f"🎮 [PLAYCALL CHECK] ❌ No user team found (user_team_side={user_team_side}), skipping defense_call check")
        
        # Legacy support: Also check game_state for backward compatibility (will be removed)
        user_offense = self.game.game_state.get("user_offense_override") or offense_call
        user_defense = self.game.game_state.get("user_defense_override") or defense_call
        
        # If user provided an offense call, use the specific play name
        if user_offense:
            # User now provides specific play name (e.g., "3-2 Motion", "Base Post Play")
            chosen_playcall = user_offense
            
            # ✅ LOUD DEBUG: Compare selected vs used playcall (BEFORE clearing)
            stored_call = None
            if is_offense_user:
                stored_call = self.game.offense_team.strategy_calls.get("offense_call")
            
            if stored_call == chosen_playcall:
                logging.info("🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢")
                logging.info("🟢 [PLAYCALL MATCH] TRUE - Selected playcall matches used playcall!")
                logging.info(f"🟢 Selected: '{stored_call}' | Used: '{chosen_playcall}'")
                logging.info("🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢")
            else:
                logging.warning("🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴")
                logging.warning("🔴 [PLAYCALL MATCH] FALSE - Selected playcall does NOT match used playcall!")
                logging.warning(f"🔴 Selected: '{stored_call}' | Used: '{chosen_playcall}'")
                logging.warning("🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴")
            
            logging.info(f"🎮 [PLAYCALL USED] User offense call being used in HCO turn: '{chosen_playcall}' for {self.game.offense_team.name}")
            logging.info(f"🎮 [PLAYCALL] Using user offense call: {chosen_playcall} (clearing offense_call after use)")
            
            # ✅ SS&S: Clear offense_call from strategy_calls after use (prevents carryover to next turn)
            offense_override_cleared = False
            if is_offense_user:
                old_override = self.game.offense_team.strategy_calls.get("offense_call")
                self.game.offense_team.strategy_calls["offense_call"] = None
                logging.warning(f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴")
                logging.warning(f"🔴 [OVERRIDE CLEARED] Offense override CLEARED after use!")
                logging.warning(f"🔴   Team: {self.game.offense_team.name} (team_id: {self.game.offense_team.team_id})")
                logging.warning(f"🔴   Override that was cleared: '{old_override}'")
                logging.warning(f"🔴   Playcall that was used: '{chosen_playcall}'")
                logging.warning(f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴")
                # ✅ SS&S: Set flag to notify frontend that override was cleared (for button un-highlighting)
                offense_override_cleared = True
            self.game.game_state["user_offense_override"] = None  # Legacy clear
            
            # Lookup play details from database to get play_type and play_focus (cached by name)
            if chosen_playcall not in _play_doc_by_name_cache:
                _play_doc_by_name_cache[chosen_playcall] = plays_collection.find_one({"name": chosen_playcall})
            play_doc = _play_doc_by_name_cache[chosen_playcall]
            
            # 🔍 DEBUG: Log play document lookup for override
            logging.warning(f"🔍 [PLAYCALL OVERRIDE DEBUG] Looking up play: '{chosen_playcall}'")
            logging.warning(f"🔍 [PLAYCALL OVERRIDE DEBUG] Play document found: {play_doc is not None}")
            if play_doc:
                chosen_play_type = play_doc.get("play_type", "motion")
                user_focus = play_doc.get("play_focus", "inside")
                logging.warning(f"🔍 [PLAYCALL OVERRIDE DEBUG] Play document data: play_type='{chosen_play_type}', play_focus='{user_focus}'")
            else:
                # Fallback if play not found
                logging.warning(f"⚠️ [PLAYCALL OVERRIDE] Play '{chosen_playcall}' not found in database, using fallback")
                chosen_play_type = "motion"
                user_focus = "inside"
                logging.warning(f"🔍 [PLAYCALL OVERRIDE DEBUG] Using fallback: play_type='{chosen_play_type}', play_focus='{user_focus}'")
            
            # Still need to choose defense normally
            if user_defense:
                chosen_defense = self._coerce_hco_defense_id(user_defense)
                # ✅ PERSISTENT: Don't clear defense_call - keep it until user manually clears
                self.game.game_state["user_defense_override"] = None  # Legacy clear
                logging.info(f"🎮 [PLAYCALL] Using user defense call: {chosen_defense} (defense_team={self.game.defense_team.name}, persistent until manually cleared)")
            else:
                logging.info(f"🎮 [PLAYCALL DEBUG] No user_defense override found (user_defense={user_defense}), will use normal selection or check strategy_calls")
                # No user defense override - choose defense normally
                defense_setting = self.game.defense_team.strategy_settings.get("defense", 2)
                pick = random.choice(STRATEGY_CALL_DICTS["defense"][defense_setting])
                if pick == STRATEGY_DEFENSE_ZONE_SENTINEL:
                    chosen_defense = self._select_zone_defense_with_playbook_weights()
                else:
                    chosen_defense = pick
            
            # ✅ FIX: Record offensive playcall attempt tracking (same as normal path)
            # This was being skipped due to early return, causing override stats not to be tracked
            try:
                # Normalize type/focus labels
                play_type_label = "Motion" if chosen_play_type == "motion" else ("Set" if chosen_play_type == "set_play" else None)
                focus_label = user_focus if user_focus in ["inside", "attack", "outside"] else None
                if play_type_label and focus_label:
                    pc = self.game.offense_team.scouting_data["offense"]["Playcalls"]
                    # Use chosen_defense for granular tracking
                    defense_playcall = chosen_defense  # Use the defense we just determined
                    from BackEnd.utils.defense_utils import is_zone_defense

                    vs_key = offense_vs_key_from_defense_input(defense_playcall)
                else:
                    vs_key = None
                
                # ✅ MOTION OFFENSE: Attempt tracking moved to phase_resolution.py (after shot resolution)
                # For Motion plays, we need to track attempts using the actual shot type, not the intended focus
                # Set Plays: Track attempts here using intended focus (before shot resolution)
                if play_type_label == "Set":
                    # Motion/Set overall + focus
                    pc[play_type_label]["overall"]["attempts"] += 1
                    pc[play_type_label][focus_label]["attempts"] += 1
                    
                    # Track granular attempts against defensive playcall
                    if vs_key:
                        # Overall attempts vs defense
                        if vs_key in pc[play_type_label]["overall"]:
                            pc[play_type_label]["overall"][vs_key]["attempts"] += 1
                        # Focus attempts vs defense
                        if vs_key in pc[play_type_label][focus_label]:
                            pc[play_type_label][focus_label][vs_key]["attempts"] += 1
                        
                        # Track aggregate vs_zone for any zone type
                        if is_zone_defense(defense_playcall) and "vs_zone" in pc[play_type_label]["overall"]:
                            pc[play_type_label]["overall"]["vs_zone"]["attempts"] += 1
                            pc[play_type_label][focus_label]["vs_zone"]["attempts"] += 1
                    
                    # Cumulative by focus
                    pc["Cumulative"][focus_label]["attempts"] += 1
                # Motion plays: Attempts tracked in phase_resolution.py after shot resolution (using actual shot type)
                
                # Track last play run for this category (for tooltips)
                    category_key = f"{play_type_label.lower()}_{focus_label}"
                    self.game.offense_team.scouting_data["offense"]["last_play_by_category"][category_key] = chosen_playcall
            except Exception as e:
                # Silently handle errors to avoid disrupting gameplay
                logging.warning(f"⚠️ [PLAYCALL TRACKING] Error tracking override offense stats: {e}")
            
            # ✅ FIX: Set offense_play_type in game_state BEFORE returning (needed for resolve_half_court_offense_logic)
            # This ensures that when resolve_half_court_offense_logic() reads game_state["offense_play_type"],
            # it gets the correct value ("set_play" or "motion") instead of defaulting to empty/motion
            logging.warning(f"🔍 [SET_PLAYCALLS DEBUG] Setting game_state['offense_play_type'] = '{chosen_play_type}' (OVERRIDE PATH)")
            logging.warning(f"🔍 [SET_PLAYCALLS DEBUG] Setting game_state['offense_play_focus'] = '{user_focus}' (OVERRIDE PATH)")
            self.game.game_state["offense_play_type"] = chosen_play_type
            self.game.game_state["offense_play_focus"] = user_focus
            
            # Return early with user's choices
            logging.info(f"🎮 [PLAYCALL RETURN] Returning user playcall: offense='{chosen_playcall}', defense='{chosen_defense}'")
            return {
                "offense": chosen_playcall,
                "defense": chosen_defense,
                "offense_play_type": chosen_play_type,  # ✅ SS&S: Single source of truth for play type ("motion" or "set_play")
                "offense_focus": user_focus,
                "defense_type": defense_display_name(chosen_defense) if chosen_defense else "-",
                "defense_focus": None,
                "offense_override_cleared": offense_override_cleared  # ✅ SS&S: Flag for frontend button un-highlighting
            }
        
        # If only defense call (user on offense, setting defense for next possession)
        if user_defense:
            chosen_defense = self._coerce_hco_defense_id(user_defense)
            # ✅ PERSISTENT: Don't clear defense_call - keep it until user manually clears
            self.game.game_state["user_defense_override"] = None  # Legacy
            logging.info(f"🎮 [PLAYCALL] Using user defense call: {chosen_defense} (persistent until manually cleared)")
        else:
            # No override, choose defense normally (will be set below)
            chosen_defense = None
        
        # Level 1/2: Play type + focus (situational Q4/OT overrides normal selection)
        from BackEnd.utils import situational_logic as sl
        time_remaining = self.game.game_state.get("time_remaining")
        quarter = getattr(self.game, "quarter", None)
        slow_it_down = sl.is_situational_active(quarter) and sl.is_slow_it_down(self.game, time_remaining)
        quick_shot = sl.is_situational_active(quarter) and sl.is_quick_shot(self.game, time_remaining)

        if slow_it_down:
            chosen_play_type = "motion"
            chosen_focus = self._choose_focus_from_strategy_settings()
            matching_plays = self._get_plays_by_type_and_focus(chosen_play_type, chosen_focus)
            if not matching_plays:
                print("⚠️ No motion plays found for Slow It Down, using fallback")
                chosen_playcall = "Inside"
            else:
                chosen_playcall = self._select_motion_play_situational_slow(matching_plays)["name"]
        elif quick_shot:
            chosen_play_type = "set_play"
            chosen_focus = "outside"
            matching_plays = self._get_plays_by_type_and_focus(chosen_play_type, chosen_focus)
            if not matching_plays:
                print("⚠️ No outside set plays found for Quick Shot, using fallback")
                chosen_playcall = "Inside"
            else:
                chosen_playcall = self._select_set_play_situational_quick_shot(matching_plays)["name"]
        else:
            offense_setting = self.game.offense_team.strategy_settings.get("offense", 2)
            play_type_weights = {
                0: {"motion": 100, "set_play": 0},
                1: {"motion": 75, "set_play": 25},
                2: {"motion": 50, "set_play": 50},
                3: {"motion": 25, "set_play": 75},
                4: {"motion": 0, "set_play": 100},
            }
            weights = play_type_weights.get(offense_setting, {"motion": 50, "set_play": 50})
            chosen_play_type = weighted_random_from_dict(weights)
            chosen_focus = self._choose_focus_from_strategy_settings()
            matching_plays = self._get_plays_by_type_and_focus(chosen_play_type, chosen_focus)
            if not matching_plays:
                print(
                    f"⚠️ No plays found for {chosen_play_type}"
                    f"{'/' + chosen_focus if chosen_play_type != 'motion' else ''}, using fallback"
                )
                chosen_playcall = "Inside"
            else:
                selected_play = self._select_play_with_playbook_weights(
                    matching_plays, chosen_play_type, chosen_focus
                )
                chosen_playcall = selected_play["name"]
        
        # Defense setting - use override if set, otherwise choose normally
        # NOTE: This must happen BEFORE offense attempt tracking so we know the correct defense
        if chosen_defense is None:  # Not set by user override above
            # ✅ SS&S: Check for defense_call in user_team.strategy_calls (regardless of current offense/defense)
            # Defense override can be set when user is on offense (for next time they're on defense)
            logging.info(f"🎮 [PLAYCALL DEBUG] chosen_defense is None, checking defense_call in user_team.strategy_calls")
            user_team = self.game.home_team if self.game.home_team.is_user_team else (self.game.away_team if self.game.away_team.is_user_team else None)
            if user_team:
                defense_call = user_team.strategy_calls.get("defense_call")
                logging.info(f"🎮 [PLAYCALL DEBUG] defense_call from user_team ({user_team.name}) strategy_calls: {defense_call}")
                if defense_call:
                    chosen_defense = self._coerce_hco_defense_id(defense_call)
                    # ✅ PERSISTENT: Don't clear defense_call - keep it until user manually clears
                    logging.info(f"🎮 [PLAYCALL] Using user defense call: {chosen_defense} (persistent until manually cleared)")
                else:
                    logging.info(f"🎮 [PLAYCALL DEBUG] defense_call is None or empty, will use normal selection")
            else:
                logging.info(f"🎮 [PLAYCALL DEBUG] No user team found, skipping defense_call check")
            
            # If still no override, use normal process
            if chosen_defense is None:
                defense_setting = self.game.defense_team.strategy_settings.get("defense", 2)
                logging.info(f"🎮 [PLAYCALL DEBUG] Using normal defense selection (defense_setting={defense_setting})")
                pick = random.choice(STRATEGY_CALL_DICTS["defense"][defense_setting])
                logging.info(f"🎮 [PLAYCALL DEBUG] Normal selection chose: {pick}")
                if pick == STRATEGY_DEFENSE_ZONE_SENTINEL:
                    chosen_defense = self._select_zone_defense_with_playbook_weights()
                    logging.info(f"🎮 [PLAYCALL DEBUG] Expanded zone sentinel to: {chosen_defense}")
                else:
                    chosen_defense = pick
        
        # Record playcall attempt under new buckets
        try:
            # Normalize type/focus labels
            play_type_label = "Motion" if chosen_play_type == "motion" else ("Set" if chosen_play_type == "set_play" else None)
            focus_label = chosen_focus if chosen_focus in ["inside", "attack", "outside"] else None
            if play_type_label and focus_label:
                pc = self.game.offense_team.scouting_data["offense"]["Playcalls"]
                # Use chosen_defense for granular tracking (not from game_state, which isn't set yet)
                defense_playcall = chosen_defense  # Use the defense we just determined
                from BackEnd.utils.defense_utils import is_zone_defense

                vs_key = offense_vs_key_from_defense_input(defense_playcall)
                
                # ✅ MOTION OFFENSE: Attempt tracking moved to phase_resolution.py (after shot resolution)
                # For Motion plays, we need to track attempts using the actual shot type, not the intended focus
                # Set Plays: Track attempts here using intended focus (before shot resolution)
                if play_type_label == "Set":
                    # Motion/Set overall + focus
                    pc[play_type_label]["overall"]["attempts"] += 1
                    pc[play_type_label][focus_label]["attempts"] += 1
                    
                    # Track granular attempts against defensive playcall
                    if vs_key:
                        # Overall attempts vs defense
                        if vs_key in pc[play_type_label]["overall"]:
                            pc[play_type_label]["overall"][vs_key]["attempts"] += 1
                        # Focus attempts vs defense
                        if vs_key in pc[play_type_label][focus_label]:
                            pc[play_type_label][focus_label][vs_key]["attempts"] += 1
                        
                        # Track aggregate vs_zone for any zone type
                        if is_zone_defense(defense_playcall) and "vs_zone" in pc[play_type_label]["overall"]:
                            pc[play_type_label]["overall"]["vs_zone"]["attempts"] += 1
                            pc[play_type_label][focus_label]["vs_zone"]["attempts"] += 1
                    
                    # Cumulative by focus
                    pc["Cumulative"][focus_label]["attempts"] += 1
                # Motion plays: Attempts tracked in phase_resolution.py after shot resolution (using actual shot type)
                
                # Track last play run for this category (for tooltips)
                category_key = f"{play_type_label.lower()}_{focus_label}"
                self.game.offense_team.scouting_data["offense"]["last_play_by_category"][category_key] = chosen_playcall
        except Exception:
            pass

        # Persist play type/focus to game_state for later success attribution
        # 🔍 DEBUG: Log when offense_play_type is set
        # logging.warning(f"🔍 [SET_PLAYCALLS DEBUG] Setting game_state['offense_play_type'] = '{chosen_play_type}'")
        # logging.warning(f"🔍 [SET_PLAYCALLS DEBUG] Setting game_state['offense_play_focus'] = '{chosen_focus}'")
        # logging.warning(f"🔍 [SET_PLAYCALLS DEBUG] Current playcall: '{calls.get('offense') if 'calls' in locals() else 'N/A'}'")
        self.game.game_state["offense_play_type"] = chosen_play_type
        self.game.game_state["offense_play_focus"] = chosen_focus
        
        # Legacy trackers removed from incrementing to avoid serving old structure

        return {
            "offense": chosen_playcall,
            "defense": chosen_defense,
            "offense_play_type": chosen_play_type if chosen_play_type else None,  # ✅ SS&S: Single source of truth for play type ("motion" or "set_play")
            "offense_focus": chosen_focus if chosen_focus else None,
            "defense_type": defense_display_name(chosen_defense) if chosen_defense else "-",
            "defense_focus": None,
            "offense_override_cleared": False  # ✅ SS&S: Normal path - no override cleared
        }

    def _load_playbook_settings(self, team_id):
        """
        Load playbook settings from GameManager (single source of truth during gameplay).
        Falls back to DB only if GameManager doesn't have settings.
        Returns dict with play percentages or None if not found/not user team.
        """
        # ✅ SS&S: GameManager is single source of truth during gameplay
        # Check GameManager first, only fall back to DB if not found
        
        offense_team = self.game.offense_team
        defense_team = self.game.defense_team

        # ✅ STEP 1: Check GameManager first (single source of truth during gameplay)
        # Empty dict {} means "no settings configured" which is valid - return it to avoid DB lookup.
        # CPU teams may now carry customized playbook_settings too, so do not gate this by is_user_team.
        if str(team_id) == str(getattr(offense_team, "team_id", None)):
            has_attr = hasattr(offense_team, 'playbook_settings')
            logging.warning(f"🔴🔴🔴 [DIAG] _load_playbook_settings OFFENSE: hasattr={has_attr}, team={offense_team.name}, team_id={getattr(offense_team, 'team_id', 'NO_ID')}")
            if has_attr:
                attr_value = getattr(offense_team, 'playbook_settings', None)
                pc_count = len((attr_value.get("pc_order", {}) or {}).get("offense", [])) if attr_value else 0
                logging.warning(f"✅ [LOAD PLAYBOOK] Using GameManager for offense team: pc_order.offense={pc_count}, value_type={type(attr_value)}")
                return attr_value or {}  # Return empty dict if None (shouldn't happen after fix)
            else:
                logging.error(f"🔴🔴🔴 [DIAG] OFFENSE TEAM MISSING playbook_settings ATTRIBUTE! team={offense_team.name}, dir(team)={[x for x in dir(offense_team) if not x.startswith('_')][:10]}")
        elif str(team_id) == str(getattr(defense_team, "team_id", None)):
            has_attr = hasattr(defense_team, 'playbook_settings')
            logging.warning(f"🔴🔴🔴 [DIAG] _load_playbook_settings DEFENSE: hasattr={has_attr}, team={defense_team.name}, team_id={getattr(defense_team, 'team_id', 'NO_ID')}")
            if has_attr:
                attr_value = getattr(defense_team, 'playbook_settings', None)
                pc_count = len((attr_value.get("pc_order", {}) or {}).get("defense", [])) if attr_value else 0
                logging.warning(f"✅ [LOAD PLAYBOOK] Using GameManager for defense team: pc_order.defense={pc_count}, value_type={type(attr_value)}")
                return attr_value or {}  # Return empty dict if None (shouldn't happen after fix)
            else:
                logging.error(f"🔴🔴🔴 [DIAG] DEFENSE TEAM MISSING playbook_settings ATTRIBUTE! team={defense_team.name}, dir(team)={[x for x in dir(defense_team) if not x.startswith('_')][:10]}")
        else:
            return None
        
        # ✅ STEP 2: Fall back to DB if GameManager doesn't have settings (shouldn't happen, but safety net)
        is_offense_team = str(team_id) == str(getattr(offense_team, "team_id", None))
        is_defense_team = str(team_id) == str(getattr(defense_team, "team_id", None))
        logging.error(f"🔴🔴🔴 [DIAG] FALLING BACK TO DB - GameManager missing playbook_settings! offense_team={is_offense_team}, defense_team={is_defense_team}")
        from BackEnd.db import games_collection, tournaments_collection, franchises_collection
        from bson import ObjectId
        
        # Get game document
        game_id = getattr(self.game, 'game_id', None)
        if not game_id:
            logging.warning(f"⚠️ [LOAD PLAYBOOK] No game_id, cannot load from DB")
            return None
        
        try:
            # ✅ FIX: Try both UUID string and ObjectId formats for game_id
            game_doc = games_collection.find_one({"_id": game_id})
            if not game_doc:
                try:
                    game_doc = games_collection.find_one({"_id": ObjectId(game_id)})
                except:
                    pass
            
            if not game_doc:
                logging.warning(f"⚠️ [LOAD PLAYBOOK] Game document not found: game_id={game_id}")
                return None
            
            # Check if this is a tournament or franchise game
            mode = game_doc.get("mode", "single")
            doc_id = game_id
            
            if mode == "tournament":
                tournament_id = game_doc.get("tournament_id")
                if tournament_id:
                    doc_id = tournament_id
                    collection = tournaments_collection
                else:
                    collection = games_collection
            elif mode == "franchise":
                franchise_id = game_doc.get("franchise_id")
                if franchise_id:
                    doc_id = franchise_id
                    collection = franchises_collection
                else:
                    collection = games_collection
            else:
                collection = games_collection
            
            # Load document
            if doc_id != game_id:
                doc = collection.find_one({"_id": ObjectId(doc_id)})
            else:
                doc = game_doc
            
            if not doc:
                logging.warning(f"⚠️ [LOAD PLAYBOOK] Mode document not found: mode={mode}, doc_id={doc_id}")
                return None
            
            # ✅ PHASE 1.1: Resolve team_id to match document key format
            # For single game mode, team_id might need resolution from team name
            resolved_team_id = team_id
            if mode == "single":
                teams_obj = doc.get("teams", {})
                # team_id is already from TeamManager.team_id, which should be correct
                # But check if it exists in document (it should if saved correctly)
                if team_id not in teams_obj:
                    # Try to find by team name (fallback for legacy data)
                    offense_team_name = offense_team.name
                    for tid in teams_obj.keys():
                        team_obj = teams_obj.get(tid, {})
                        if team_obj.get("name") == offense_team_name:
                            resolved_team_id = tid
                            logging.warning(f"⚠️ [LOAD PLAYBOOK] Resolved team_id from name: {team_id} → {resolved_team_id}")
                            break

            # WIRED: DB fallback used when GameManager doesn't have playbook_settings (e.g. edge cases during gameplay).
            # Franchise: read from game doc's teams (in-game saves write here; franchise_teams was legacy and is no longer used).
            lookup_doc = game_doc if mode == "franchise" else doc
            teams_obj_lookup = lookup_doc.get("teams", {})

            # Get playbook settings for the appropriate team
            if is_offense_team:
                team_obj = teams_obj_lookup.get(resolved_team_id, {})
                playbook_settings = team_obj.get("playbook_settings")
                if playbook_settings:
                    logging.warning(f"✅ [LOAD PLAYBOOK] Loaded playbook_settings for offense team: team_id={resolved_team_id}")
                else:
                    logging.warning(f"⚠️ [LOAD PLAYBOOK] No playbook_settings found for offense team: team_id={resolved_team_id}")
                return playbook_settings
            elif is_defense_team:
                # For defense, we need the defense team's ID
                def_team_id = defense_team.team_id
                resolved_def_team_id = def_team_id
                if mode == "single":
                    teams_obj = doc.get("teams", {})
                    if def_team_id not in teams_obj:
                        # Try to find by team name (fallback for legacy data)
                        defense_team_name = defense_team.name
                        for tid in teams_obj.keys():
                            team_obj = teams_obj.get(tid, {})
                            if team_obj.get("name") == defense_team_name:
                                resolved_def_team_id = tid
                                logging.warning(f"⚠️ [LOAD PLAYBOOK] Resolved defense team_id from name: {def_team_id} → {resolved_def_team_id}")
                                break
                # Same lookup_doc/teams_obj_lookup as offense (franchise uses game_doc.teams)
                team_obj = teams_obj_lookup.get(resolved_def_team_id, {})
                playbook_settings = team_obj.get("playbook_settings")
                if playbook_settings:
                    logging.warning(f"⚠️ [LOAD PLAYBOOK] Fallback to DB for defense team: team_id={resolved_def_team_id} (GameManager should have settings)")
                    # ✅ SS&S: Apply to GameManager so future calls use GameManager
                    defense_team.playbook_settings = playbook_settings
                else:
                    logging.warning(f"⚠️ [LOAD PLAYBOOK] No playbook_settings found in DB for defense team: team_id={resolved_def_team_id}")
                return playbook_settings
        except Exception as e:
            logging.warning(f"⚠️ Error loading playbook settings: {e}")
            return None
        
        return None

    def _choose_focus_from_strategy_settings(self) -> str:
        """Level-2 focus from offense inside/attack/outside strategy sliders."""
        inside_val = self.game.offense_team.strategy_settings.get("inside", 2)
        attack_val = self.game.offense_team.strategy_settings.get("attack", 2)
        outside_val = self.game.offense_team.strategy_settings.get("outside", 2)
        total = inside_val + attack_val + outside_val
        if total == 0:
            return "inside"
        roll = random.randint(1, total)
        if roll <= inside_val:
            return "inside"
        if roll <= inside_val + attack_val:
            return "attack"
        return "outside"

    def _get_plays_by_type_and_focus(self, play_type: str, play_focus: str | None) -> list:
        """Cached plays query; motion ignores play_focus."""
        cache_key = (play_type, play_focus if play_type != "motion" else None)
        if cache_key not in _plays_by_type_focus_cache:
            if play_type == "motion":
                query = {"play_type": play_type}
            else:
                query = {"play_type": play_type, "play_focus": play_focus}
            _plays_by_type_focus_cache[cache_key] = list(plays_collection.find(query))
        return _plays_by_type_focus_cache[cache_key]

    def _select_motion_play_situational_slow(self, matching_plays: list) -> dict:
        """
        Slow It Down (Q4/OT): motion only — weighted by playbook motion percentages when any > 0,
        otherwise uniform random among all motion plays.
        """
        valid_plays = [p for p in matching_plays if p.get("name") != "To Be Added"]
        if not valid_plays:
            valid_plays = matching_plays

        playbook_settings = self._load_playbook_settings(self.game.offense_team.team_id)
        weights = {}
        if playbook_settings:
            for play in valid_plays:
                play_name = play.get("name")
                play_id = play.get("play_id") or play.get("_id")
                percentage = resolve_playbook_percentage(
                    playbook_settings.get("motion", {}),
                    play_id=play_id,
                    play_name=play_name,
                    default=0,
                )
                if percentage > 0:
                    weights[play_name] = percentage

        if weights:
            selected_name = weighted_random_from_dict(weights)
            for play in valid_plays:
                if play.get("name") == selected_name:
                    return play

        return random.choice(valid_plays)

    def _select_set_play_situational_quick_shot(self, matching_plays: list) -> dict:
        """Quick Shot (Q4/OT): outside set plays only, uniform random (ignores playbook settings)."""
        valid_plays = [p for p in matching_plays if p.get("name") != "To Be Added"]
        if not valid_plays:
            valid_plays = matching_plays
        return random.choice(valid_plays)

    def _select_play_with_playbook_weights(self, matching_plays, play_type, play_focus=None):
        """
        Select a play using weighted random based on playbook settings.
        Falls back to equal weights if no settings exist or for CPU teams.
        Excludes "To Be Added" plays.
        """
        # Filter out "To Be Added" plays
        valid_plays = [p for p in matching_plays if p.get("name") != "To Be Added"]
        if not valid_plays:
            # Fallback to all plays if somehow all are "To Be Added"
            valid_plays = matching_plays
        
        # Load playbook settings
        team_id = self.game.offense_team.team_id
        playbook_settings = self._load_playbook_settings(team_id)
        
        # Build weights dict
        weights = {}
        for play in valid_plays:
            play_name = play.get("name")
            play_id = play.get("play_id") or play.get("_id")
            
            if playbook_settings:
                # Get percentage from playbook settings
                if play_type == "motion":
                    percentage = resolve_playbook_percentage(
                        playbook_settings.get("motion", {}),
                        play_id=play_id,
                        play_name=play_name,
                        default=0,
                    )
                elif play_type == "set_play":
                    set_playbook = playbook_settings.get("set_plays", {})
                    if not set_playbook:
                        focus_key = f"set_play_{play_focus}" if play_focus else "set_play_inside"
                        set_playbook = playbook_settings.get(focus_key, {})
                    percentage = resolve_playbook_percentage(
                        set_playbook,
                        play_id=play_id,
                        play_name=play_name,
                        default=0,
                    )
                else:
                    percentage = 0
                
                if percentage > 0:
                    weights[play_name] = percentage
            else:
                # Equal weights (fallback or CPU team)
                weights[play_name] = 1
        
        if not weights:
            # Fallback to equal weights if no valid weights found
            weights = {p.get("name"): 1 for p in valid_plays}
        
        # Select using weighted random
        selected_name = weighted_random_from_dict(weights)
        
        # Find and return the selected play
        for play in valid_plays:
            if play.get("name") == selected_name:
                return play
        
        # Fallback
        return valid_plays[0] if valid_plays else matching_plays[0]

    def _select_zone_defense_with_playbook_weights(self):
        """
        Select a zone defense type using weighted random based on playbook settings.
        Falls back to equal weights if no settings exist or for CPU teams.
        Returns canonical `defense_id` row keys: 2-3-zone, 3-2-zone, 1-3-1-zone.
        """
        zone_ids = list(PLAYBOOK_ZONE_KEY_TO_DEFENSE_ID.values())

        defense_team = self.game.defense_team
        team_id = defense_team.team_id
        playbook_settings = self._load_playbook_settings(team_id)

        if playbook_settings:
            zone_settings = playbook_settings.get("zone_defense", {})
            weights = {}
            for zid in zone_ids:
                pb_key = DEFENSE_ID_TO_PLAYBOOK_ZONE_KEY.get(zid)
                percentage = 0
                if pb_key:
                    percentage = zone_settings.get(pb_key, 0)
                if not percentage:
                    percentage = zone_settings.get(zid, 0)
                if not percentage and pb_key:
                    from BackEnd.utils.playbook_settings_utils import ZONE_DEFENSE_ID_TO_NAME

                    legacy_name = ZONE_DEFENSE_ID_TO_NAME.get(pb_key)
                    if legacy_name:
                        percentage = zone_settings.get(legacy_name, 0)
                if percentage > 0:
                    weights[zid] = percentage

            if weights:
                return weighted_random_from_dict(weights)

        return random.choice(zone_ids)

    def set_strategy_calls(self):
        # Ensure strategy_settings are initialized for both teams (but don't overwrite existing settings)
        # Only initialize if it's completely missing (None), not if it's an empty dict
        # ✅ TRACE: Log current strategy_settings state before checking (potential overwrite point)
        trace_id = f"set_calls_{getattr(self.game, 'game_id', 'no_id')}_{getattr(self.game, 'quarter', '?')}"
        
        offense_has_settings = hasattr(self.game.offense_team, 'strategy_settings') and self.game.offense_team.strategy_settings is not None
        offense_is_empty = isinstance(self.game.offense_team.strategy_settings, dict) and len(self.game.offense_team.strategy_settings) == 0
        offense_is_user = self.game.offense_team.is_user_team
        if not offense_has_settings:
            self.game.offense_team.strategy_settings = self.game.offense_team._init_strategy_settings()
        elif offense_is_empty:
            self.game.offense_team.strategy_settings = self.game.offense_team._init_strategy_settings()
        
        defense_has_settings = hasattr(self.game.defense_team, 'strategy_settings') and self.game.defense_team.strategy_settings is not None
        defense_is_empty = isinstance(self.game.defense_team.strategy_settings, dict) and len(self.game.defense_team.strategy_settings) == 0
        
        if not defense_has_settings:
            self.game.defense_team.strategy_settings = self.game.defense_team._init_strategy_settings()
        elif defense_is_empty:
            self.game.defense_team.strategy_settings = self.game.defense_team._init_strategy_settings()
        
        # 🐛 DEBUG: Log strategy settings being used
        # ✅ COMMENTED OUT: Strategy settings logs (cluttering transition debugging)
        # logging.warning(f"🔧 [SET STRATEGY CALLS] Offense: {self.game.offense_team.name}, Defense: {self.game.defense_team.name}")
        # logging.warning(f"   - Offense strategy_settings: {self.game.offense_team.strategy_settings}")
        # logging.warning(f"   - Defense strategy_settings: {self.game.defense_team.strategy_settings}")
        
        # ✅ SS&S: Ensure strategy_calls dictionaries exist (but don't overwrite if already initialized)
        # strategy_calls is initialized in TeamManager.__init__ with override fields
        # Only initialize if completely missing (shouldn't happen, but defensive check)
        if not hasattr(self.game.offense_team, 'strategy_calls') or self.game.offense_team.strategy_calls is None:
            self.game.offense_team.strategy_calls = {
                "offense_call": None,
                "defense_call": None,
                "aggression_override": None,
                "tempo_override": None,
                "press_override": None,
                "trap_override": None,
            }
        if not hasattr(self.game.defense_team, 'strategy_calls') or self.game.defense_team.strategy_calls is None:
            self.game.defense_team.strategy_calls = {
                "offense_call": None,
                "defense_call": None,
                "aggression_override": None,
                "tempo_override": None,
                "press_override": None,
                "trap_override": None,
            }

        # Set tempo/aggression calls (string values for time elapsed and foul calculations)
        # ✅ SS&S: Check for overrides in team.strategy_calls first
        # ✅ SS&S: Use game_state["user_team_side"] instead of is_user_team flag (more reliable, persists to DB)
        user_team_side = self.game.game_state.get("user_team_side")
        is_offense_user = (user_team_side == "home" and self.game.offense_team.is_home_team) or (user_team_side == "away" and not self.game.offense_team.is_home_team)
        
        if is_offense_user:
            tempo_override = self.game.offense_team.strategy_calls.get("tempo_override")
            if tempo_override:
                self.game.offense_team.strategy_calls["tempo_call"] = tempo_override
                # Clear override after use
                old_tempo_override = self.game.offense_team.strategy_calls.get("tempo_override")
                self.game.offense_team.strategy_calls["tempo_override"] = None
                logging.warning(f"🔴 [OVERRIDE CLEARED] Tempo override CLEARED after use: '{old_tempo_override}' for {self.game.offense_team.name}")
                logging.info(f"🎮 [PLAYCALL OVERRIDE] Using tempo override: {tempo_override}")
            else:
                tempo_setting = self.game.offense_team.strategy_settings.get("tempo", 2)
                self.game.offense_team.strategy_calls["tempo_call"] = random.choice(STRATEGY_CALL_DICTS["tempo"][tempo_setting])
        else:
            tempo_setting = self.game.offense_team.strategy_settings.get("tempo", 2)
            self.game.offense_team.strategy_calls["tempo_call"] = random.choice(STRATEGY_CALL_DICTS["tempo"][tempo_setting])
        
        # ✅ Aggression is NOT rolled per turn. It is rolled per BREAK (game start, quarter
        # break, timeout, foul-out) into strategy_calls["aggression_roll"] by
        # GameManager.roll_aggression_calls(), and persists until the next break. Each turn we
        # only RESOLVE the effective aggression_call for both teams:
        #   - the user team's persistent aggression_override (Playcall Center) if set, else
        #   - the team's persisted aggression_roll (fresh roll as a defensive fallback if missing).
        # The override stays immediate (takes effect the next turn) and is universally persistent
        # across offense/defense until the user clears it or a break clears it. See
        # Turn_by_Turn_System.md and Playcall_Center.md.
        # ✅ SS&S: Use game_state["user_team_side"] instead of is_user_team flag (more reliable, persists to DB)
        user_team = None
        if user_team_side == "home":
            user_team = self.game.home_team
        elif user_team_side == "away":
            user_team = self.game.away_team

        aggression_override = user_team.strategy_calls.get("aggression_override") if user_team else None

        for team in (self.game.offense_team, self.game.defense_team):
            calls = team.strategy_calls
            base_roll = calls.get("aggression_roll")
            if base_roll is None:
                # Defensive fallback: no break-roll yet (e.g. a turn before any break hook ran) →
                # roll once now so we never emit a flat "normal" by accident.
                aggression_setting = team.strategy_settings.get("aggression", 2)
                choices = STRATEGY_CALL_DICTS["aggression"].get(aggression_setting, STRATEGY_CALL_DICTS["aggression"][2])
                base_roll = random.choice(choices)
                calls["aggression_roll"] = base_roll
            is_user_team = user_team is not None and str(team.team_id) == str(user_team.team_id)
            if is_user_team and aggression_override:
                calls["aggression_call"] = aggression_override
            else:
                calls["aggression_call"] = base_roll
        
        # NOTE: rebounding and defense tempo for fast break release are now read directly 
        # from strategy_settings (numeric 0-4) in shot_manager.py - no string conversion needed
        


    
    def calculate_ev(self, offensive_playcall, defensive_playcall, offensive_lineup, defensive_lineup, offensive_team, defensive_team):
        """
        Calculate Expected Value (EV) for the playcall matchup.
        
        Args:
            offensive_playcall (str): Offensive playcall (e.g., "Motion - Inside Focus")
            defensive_playcall (str): Defensive playcall (e.g., "Man", "2-3 Zone", "3-2 Zone", "1-3-1 Zone")
            offensive_lineup (dict): Offensive lineup {pos: player}
            defensive_lineup (dict): Defensive lineup {pos: player}
            offensive_team: Offensive team object with attributes
            defensive_team: Defensive team object with attributes
        
        Returns:
            float: EV percentage from -99.0 to 99.0
                Positive: Offensive advantage
                Negative: Defensive advantage
        """
        import random
        
        # Implement EV calculation
        from BackEnd.db import plays_collection
        from BackEnd.engine.phase_resolution import get_hco_skeleton
        from BackEnd.utils.shared_defense import (
            _get_23_zone_boundaries,
            _get_32_zone_boundaries,
            _get_131_zone_boundaries,
            _point_in_zone
        )
        from BackEnd.constants import HCO_STRING_SPOTS
        from BackEnd.utils.shared import get_away_player_coords
        
        # Step 1: Get play type and focus from playcall (cached by name)
        if offensive_playcall not in _play_doc_by_name_cache:
            _play_doc_by_name_cache[offensive_playcall] = plays_collection.find_one({"name": offensive_playcall})
        play_doc = _play_doc_by_name_cache[offensive_playcall]
        if not play_doc:
            return 0.0
        
        play_type = play_doc.get("play_type", "motion")
        
        # ✅ FIX: For Motion plays, use game_state["offense_play_focus"] (chosen focus)
        # For Set Plays, use play_doc.get("play_focus") (intended focus from database)
        # Motion plays have play_focus = null in database, but focus is chosen before execution
        if play_type == "motion":
            play_focus = self.game.game_state.get("offense_play_focus", "inside")
        else:
            play_focus = play_doc.get("play_focus", "inside")
        
        # ✅ FIX: Normalize play_focus to ensure it's always one of the expected values
        if play_focus not in ["inside", "attack", "outside"]:
            play_focus = "inside"  # Default fallback
        
        # Step 2: Get successful variant skeleton to find projected shooter and passer
        successful_skeleton = get_hco_skeleton(None, self.game, lean_score=1.0)
        if not successful_skeleton or "steps" not in successful_skeleton:
            return 0.0
        
        steps = successful_skeleton.get("steps", [])
        if not steps:
            return 0.0
        
        # Extract projected shooter and passer
        projected_shooter_pos = None
        projected_passer_pos = None
        
        final_step = steps[-1]
        for pos, action_info in final_step.get("pos_actions", {}).items():
            if action_info.get("action", "").lower() == "shoot":
                projected_shooter_pos = pos
                break
        
        if projected_shooter_pos:
            shot_step_index = len(steps) - 1
            for step_index in range(shot_step_index - 1, max(0, shot_step_index - 5) - 1, -1):
                if step_index < 0:
                    break
                step = steps[step_index]
                pos_actions = step.get("pos_actions", {})
                shooter_action_info = pos_actions.get(projected_shooter_pos)
                if shooter_action_info and shooter_action_info.get("action", "").lower() == "receive":
                    for pos, action_info in pos_actions.items():
                        if pos != projected_shooter_pos and action_info.get("action", "").lower() == "pass":
                            projected_passer_pos = pos
                            break
                    if projected_passer_pos:
                        break
        
        # Step 3: Calculate offense score
        offense_score = 0.0
        
        if play_type == "motion":
            total_sc = sum(player.attributes.get("SC", 50) for player in offensive_lineup.values() if player)
            total_st = sum(player.attributes.get("ST", 50) for player in offensive_lineup.values() if player)
            total_ag = sum(player.attributes.get("AG", 50) for player in offensive_lineup.values() if player)
            total_sh = sum(player.attributes.get("SH", 50) for player in offensive_lineup.values() if player)
            
            if play_focus == "inside":
                offense_score = (total_sc + total_st * 0.5) / 5
            elif play_focus == "attack":
                offense_score = (total_sc + total_ag * 0.5) / 5
            elif play_focus == "outside":
                offense_score = (total_sh * 1.5) / 5
        else:  # set_play
            shooter = offensive_lineup.get(projected_shooter_pos) if projected_shooter_pos else None
            passer = offensive_lineup.get(projected_passer_pos) if projected_passer_pos else None
            
            if not shooter:
                return 0.0
            
            shooter_sc = shooter.attributes.get("SC", 50)
            shooter_st = shooter.attributes.get("ST", 50)
            shooter_ag = shooter.attributes.get("AG", 50)
            shooter_sh = shooter.attributes.get("SH", 50)
            
            if play_focus == "inside":
                if passer:
                    offense_score = shooter_sc + shooter_st * 0.25 + passer.attributes.get("PS", 50) * 0.25
                else:
                    offense_score = shooter_sc + shooter_st * 0.5
            elif play_focus == "attack":
                if passer:
                    offense_score = shooter_sc + shooter_ag * 0.25 + passer.attributes.get("PS", 50) * 0.25
                else:
                    offense_score = shooter_sc + shooter_ag * 0.5
            elif play_focus == "outside":
                if passer:
                    offense_score = shooter_sh * 1.25 + passer.attributes.get("IQ", 50) * 0.25
                else:
                    offense_score = shooter_sh * 1.5
        
        # Step 4: Calculate defense score
        from BackEnd.utils.defense_utils import is_zone_defense

        defense_score = 0.0
        def_row = defense_scouting_row_key(defensive_playcall)

        if def_row == "man":
            if play_type == "motion":
                total_id = sum(player.attributes.get("ID", 50) for player in defensive_lineup.values() if player)
                total_st = sum(player.attributes.get("ST", 50) for player in defensive_lineup.values() if player)
                defense_score = (total_id + total_st * 0.5) / 5
            else:  # set_play
                defender = defensive_lineup.get(projected_shooter_pos) if projected_shooter_pos else None
                if not defender:
                    defense_score = 0.0
                else:
                    def_id = defender.attributes.get("ID", 50)
                    def_od = defender.attributes.get("OD", 50)
                    def_ag = defender.attributes.get("AG", 50)
                    def_st = defender.attributes.get("ST", 50)
                    
                    if play_focus == "inside":
                        defense_score = def_id + def_st * 0.25
                    elif play_focus == "attack":
                        defense_score = def_id + def_ag * 0.25
                    elif play_focus == "outside":
                        defense_score = def_od * 1.25
        elif is_zone_defense(defensive_playcall):
            # Zone defense: team_d + 0.5 * player_d
            zone_team_d_values = {
                "2-3-zone": {"inside": 80, "attack": 40, "outside": 5},
                "3-2-zone": {"inside": 10, "attack": 30, "outside": 80},
                "1-3-1-zone": {"inside": 20, "attack": 60, "outside": 20}
            }
            team_d = zone_team_d_values.get(def_row, {}).get(play_focus, 0)
            
            shooter_spot = "key"
            if steps and projected_shooter_pos:
                final_step = steps[-1]
                shooter_action = final_step.get("pos_actions", {}).get(projected_shooter_pos, {})
                shooter_spot = shooter_action.get("location") or shooter_action.get("spot") or "key"
            
            shooter_coords = HCO_STRING_SPOTS.get(shooter_spot, {"x": 50, "y": 25})
            is_away_offense = self.game.offense_team.team_id == self.game.away_team.team_id
            if is_away_offense:
                shooter_coords = get_away_player_coords(shooter_coords)
            
            zv = defense_zone_shell_variant(defensive_playcall) or "23"
            if zv == "32":
                zone_boundaries = _get_32_zone_boundaries(shooter_spot, is_away_offense)
            elif zv == "131":
                zone_boundaries = _get_131_zone_boundaries(shooter_spot, is_away_offense)
            else:
                zone_boundaries = _get_23_zone_boundaries(shooter_spot, is_away_offense)
            
            zone_defender_pos = None
            for def_pos in ["PG", "SG", "SF", "PF", "C"]:
                if def_pos in defensive_lineup and def_pos in zone_boundaries:
                    zone_coords = zone_boundaries[def_pos]
                    if _point_in_zone(shooter_coords, zone_coords, False):
                        zone_defender_pos = def_pos
                        break
            
            if not zone_defender_pos:
                min_dist = float('inf')
                for def_pos in ["PG", "SG", "SF", "PF", "C"]:
                    if def_pos in defensive_lineup and def_pos in zone_boundaries:
                        zone_coords = zone_boundaries[def_pos]
                        if zone_coords:
                            avg_x = sum(c[0] for c in zone_coords) / len(zone_coords)
                            avg_y = sum(c[1] for c in zone_coords) / len(zone_coords)
                            zone_center = {"x": avg_x, "y": avg_y}
                            dist = ((shooter_coords["x"] - zone_center["x"]) ** 2 + 
                                   (shooter_coords["y"] - zone_center["y"]) ** 2) ** 0.5
                            if dist < min_dist:
                                min_dist = dist
                                zone_defender_pos = def_pos
                
                if not zone_defender_pos:
                    zone_defender_pos = "C"
            
            zone_defender = defensive_lineup.get(zone_defender_pos) if zone_defender_pos else None
            if not zone_defender:
                player_d = 0.0
            else:
                def_id = zone_defender.attributes.get("ID", 50)
                def_od = zone_defender.attributes.get("OD", 50)
                def_ag = zone_defender.attributes.get("AG", 50)
                def_st = zone_defender.attributes.get("ST", 50)
                
                # ✅ FIX: Initialize player_d with a default value in case play_focus is unexpected
                if play_focus == "inside":
                    player_d = def_id + def_st * 0.25
                elif play_focus == "attack":
                    player_d = def_id + def_ag * 0.25
                elif play_focus == "outside":
                    player_d = def_od * 1.25
                else:
                    # Default fallback if play_focus is unexpected (shouldn't happen, but safe)
                    player_d = def_id + def_st * 0.25
            
            if zv == "131":
                player_d *= 1.15
            
            defense_score = team_d + 0.5 * player_d
        
        # Step 5: Calculate EV = (offense - defense) * 2, capped at ±99%
        ev_diff = offense_score - defense_score
        ev_percentage = ev_diff * 2.0
        
        if ev_percentage > 99.0:
            ev_percentage = 99.0
        elif ev_percentage < -99.0:
            ev_percentage = -99.0
        
        return ev_percentage
    
    def _store_ev_score(self, ev, calls, offense_team, defense_team):
        """
        Store EV score in offense and defense scouting data.
        
        Args:
            ev (float): EV percentage from -99.0 to 99.0
            calls (dict): Playcall information with offense_play_type, offense_focus, defense_playcall
            offense_team: Offensive team object
            defense_team: Defensive team object
        """
        try:
            # Get play type and focus
            # ✅ FIX: Use "offense_play_type" to match the key used in set_playcalls() and elsewhere
            offense_play_type = calls.get("offense_play_type", "").lower()
            offense_focus = calls.get("offense_focus", "")
            defense_playcall = calls.get("defense", "")
            
            # Normalize play type
            if offense_play_type == "set_play":
                offense_play_type = "set"
            
            # Store in offense scouting data
            if offense_play_type in ["motion", "set"] and offense_focus in ["inside", "attack", "outside"]:
                play_type_label = "Motion" if offense_play_type == "motion" else "Set"
                pc = offense_team.scouting_data["offense"]["Playcalls"]
                
                vs_key = offense_vs_key_from_defense_input(defense_playcall)
                
                # Store EV in overall and focus buckets
                if "ev_scores" not in pc[play_type_label]["overall"]:
                    pc[play_type_label]["overall"]["ev_scores"] = []
                if "ev_scores" not in pc[play_type_label][offense_focus]:
                    pc[play_type_label][offense_focus]["ev_scores"] = []
                
                pc[play_type_label]["overall"]["ev_scores"].append(ev)
                pc[play_type_label][offense_focus]["ev_scores"].append(ev)
                
                # Store EV in vs_* buckets
                if vs_key and vs_key in pc[play_type_label]["overall"]:
                    if "ev_scores" not in pc[play_type_label]["overall"][vs_key]:
                        pc[play_type_label]["overall"][vs_key]["ev_scores"] = []
                    pc[play_type_label]["overall"][vs_key]["ev_scores"].append(ev)
                
                if vs_key and vs_key in pc[play_type_label][offense_focus]:
                    if "ev_scores" not in pc[play_type_label][offense_focus][vs_key]:
                        pc[play_type_label][offense_focus][vs_key]["ev_scores"] = []
                    pc[play_type_label][offense_focus][vs_key]["ev_scores"].append(ev)
                
                # Store in vs_zone aggregate if zone defense
                from BackEnd.utils.defense_utils import is_zone_defense
                if is_zone_defense(defense_playcall) and "vs_zone" in pc[play_type_label]["overall"]:
                    if "ev_scores" not in pc[play_type_label]["overall"]["vs_zone"]:
                        pc[play_type_label]["overall"]["vs_zone"]["ev_scores"] = []
                    if "ev_scores" not in pc[play_type_label][offense_focus]["vs_zone"]:
                        pc[play_type_label][offense_focus]["vs_zone"]["ev_scores"] = []
                    pc[play_type_label]["overall"]["vs_zone"]["ev_scores"].append(ev)
                    pc[play_type_label][offense_focus]["vs_zone"]["ev_scores"].append(ev)
                
                # Store in Cumulative
                if "ev_scores" not in pc["Cumulative"][offense_focus]:
                    pc["Cumulative"][offense_focus]["ev_scores"] = []
                pc["Cumulative"][offense_focus]["ev_scores"].append(ev)
            
            # Store in defense scouting data
            def_row = defense_scouting_row_key(defense_playcall)
            if def_row in defense_team.scouting_data["defense"]:
                def_data = defense_team.scouting_data["defense"][def_row]
                game_stats = def_data.get("game_stats", {})
                
                # Store EV in top-level game_stats
                if "ev_scores" not in game_stats:
                    game_stats["ev_scores"] = []
                game_stats["ev_scores"].append(ev)
                
                # Store EV in vs_* buckets
                if offense_play_type == "motion":
                    if "ev_scores" not in game_stats.get("vs_motion", {}):
                        game_stats.setdefault("vs_motion", {})["ev_scores"] = []
                    game_stats["vs_motion"]["ev_scores"].append(ev)
                elif offense_play_type == "set":
                    if "ev_scores" not in game_stats.get("vs_set", {}):
                        game_stats.setdefault("vs_set", {})["ev_scores"] = []
                    game_stats["vs_set"]["ev_scores"].append(ev)
                
                if offense_focus in ["inside", "attack", "outside"]:
                    vs_focus_key = f"vs_{offense_focus}"
                    if "ev_scores" not in game_stats.get(vs_focus_key, {}):
                        game_stats.setdefault(vs_focus_key, {})["ev_scores"] = []
                    game_stats[vs_focus_key]["ev_scores"].append(ev)
                    
                    # Store in combination buckets
                    if offense_play_type == "motion":
                        combo_key = f"vs_motion_{offense_focus}"
                        if "ev_scores" not in game_stats.get(combo_key, {}):
                            game_stats.setdefault(combo_key, {})["ev_scores"] = []
                        game_stats[combo_key]["ev_scores"].append(ev)
                    elif offense_play_type == "set":
                        combo_key = f"vs_set_{offense_focus}"
                        if "ev_scores" not in game_stats.get(combo_key, {}):
                            game_stats.setdefault(combo_key, {})["ev_scores"] = []
                        game_stats[combo_key]["ev_scores"].append(ev)
        except Exception as e:
            # Silently handle errors to avoid disrupting gameplay
            pass
    
    def resolve_half_court_offense(self):
        from BackEnd.engine.phase_resolution import resolve_half_court_offense_logic
        result = resolve_half_court_offense_logic(self.game)
        self._emit_hco_animation_steps(result)
        return result

    def _emit_hco_animation_steps(self, result):
        """Single injection point for HCO-tagged turn results — both the normal
        ``resolve_half_court_offense`` path and the ``resolve_final_turn_shot``
        path (≤30s Final Shot variant) route through here so every HCO turn
        carries a unified ``animation_steps`` payload.

        Mechanics:
          - Boundary-stamps ``current_turn="HCO"`` (stopper paths — FOUL /
            STEAL / DEAD_BALL_TURNOVER — would otherwise reach the FE with
            ``current_turn=None`` and fail the schema-playback gate).
          - Emits ``animation_steps`` via ``build_skeleton_animation_steps``.
          - Aligns ``time_elapsed`` with the schema's game-clock burn for
            MAKE/MISS/BLOCK — *except* for Final Shot results, which
            explicitly set ``time_elapsed = time_remaining`` so the quarter
            clock runs out (see
            ``resolve_final_turn_shot_logic`` in ``phase_resolution.py``).
          - Defensive: emitter failure does not block the existing payload.
        """
        if not isinstance(result, dict):
            return
        result.setdefault("current_turn", "HCO")
        try:
            from BackEnd.engine.skeleton_step_emitter import (
                build_skeleton_animation_steps,
            )
            anim_steps = build_skeleton_animation_steps(result, self.game)
            if anim_steps is None:
                return
            result["animation_steps"] = anim_steps
            # Skip the schema-burn time_elapsed override for Final Shot —
            # those turns deliberately burn the entire remaining quarter
            # clock (``time_remaining``) regardless of natural step T.
            if result.get("final_turn") is True:
                return
            # Align result["time_elapsed"] with the schema's total
            # game-clock burn for MAKE/MISS/BLOCK. The legacy
            # step_clock_seconds-based time_elapsed counts only
            # skeleton-step durations; the [ball_flight] + [bounce]
            # sub-steps add ball-arc + bounce game-sec that must
            # also decrement the game clock (shot clock is pinned
            # across those sub-steps — handled separately via
            # ``_shot_detach_elapsed_seconds``).
            result_type_for_te = (result.get("result_type") or "").upper()
            if result_type_for_te in ("MAKE", "MISS", "BLOCK") and anim_steps:
                first_clock = (anim_steps[0].get("start") or {}).get("clock") or {}
                last_clock = (anim_steps[-1].get("end") or {}).get("clock") or {}
                cs_start = first_clock.get("clock_remaining")
                cs_end = last_clock.get("clock_remaining")
                if cs_start is not None and cs_end is not None:
                    schema_game_burn = max(0.0, float(cs_start) - float(cs_end))
                    result["time_elapsed"] = int(round(schema_game_burn))
        except Exception as e:
            logging.warning(
                "build_skeleton_animation_steps (HCO) failed: %s", e
            )

    def resolve_final_turn_shot(self):
        """Final Turn shot (≤30s): alignment (Phase 2) + shot execution (Phase 3)."""
        from BackEnd.engine.phase_resolution import resolve_final_turn_shot_logic
        o_dest, position_to_spot, bh_pos = self._build_final_turn_offense_alignment()
        d_dest, zone_playcall = self._build_final_turn_defense_alignment()
        self.game.game_state["defense_playcall"] = zone_playcall
        result = resolve_final_turn_shot_logic(
            self.game, o_dest, d_dest, position_to_spot, bh_pos
        )
        self._emit_hco_animation_steps(result)
        return result

    def _build_final_turn_offense_alignment(self):
        """Final Turn offense: BH 60% PG / 30% SG / 10% SF; PG/SG deep wings; SF/PF corners; C key.
        Returns display-oriented (oDestinations, position_to_spot, bh_pos). Spot names remain
        home-authored skeleton inputs; only the emitted coordinate map is mirrored for away offense."""
        from BackEnd.constants import HCO_STRING_SPOTS
        from BackEnd.utils.shared import get_away_player_coords
        game = self.game
        off_team = game.offense_team
        off_lineup = off_team.lineup
        is_away_offense = off_team.team_id == game.away_team.team_id
        # Ball handler position: 60% PG, 30% SG, 10% SF
        r = random.random()
        bh_pos = "PG" if r < 0.60 else ("SG" if r < 0.90 else "SF")
        # Deep wings (random order for PG/SG)
        wings = ["deep upper wing", "deep lower wing"]
        random.shuffle(wings)
        pg_wing, sg_wing = wings[0], wings[1]
        # Corners: one upper, one lower from {upper corner, lower corner, upper midCorner, lower midCorner}
        upper_spots = ["upper corner", "upper midCorner"]
        lower_spots = ["lower corner", "lower midCorner"]
        random.shuffle(upper_spots)
        random.shuffle(lower_spots)
        sf_spot = upper_spots[0]
        pf_spot = lower_spots[0]
        if random.random() < 0.5:
            sf_spot, pf_spot = pf_spot, sf_spot  # swap so one upper one lower
        position_to_spot = {"C": "key"}
        if bh_pos == "SF":
            position_to_spot["SF"] = pg_wing
            position_to_spot["SG"] = sg_wing
            position_to_spot["PG"] = random.choice(upper_spots)
            position_to_spot["PF"] = random.choice(lower_spots)
        else:
            position_to_spot["PG"] = pg_wing
            position_to_spot["SG"] = sg_wing
            position_to_spot["SF"] = sf_spot
            position_to_spot["PF"] = pf_spot
        o_destinations = {}
        for pos in ["PG", "SG", "SF", "PF", "C"]:
            spot = position_to_spot.get(pos, "key")
            coords = HCO_STRING_SPOTS.get(spot, {"x": 64, "y": 25})
            o_destinations[pos] = (
                get_away_player_coords(coords) if is_away_offense else dict(coords)
            )
        return (o_destinations, position_to_spot, bh_pos)

    def _build_final_turn_defense_alignment(self):
        """Final Turn defense: 50/50 2-3 or 3-2 zone, ball-at-key positions. Returns (dDestinations, zone_playcall).
        Destinations are emitted in final display orientation for the current offense.
        PG anchors at topLane (not key) so the point defender sits above the lane."""
        from BackEnd.constants import HCO_STRING_SPOTS
        from BackEnd.utils.shared import get_away_player_coords
        from BackEnd.utils.shared_defense import ZONE_23_NORMAL, ZONE_32_NORMAL
        game = self.game
        def_team = game.defense_team
        is_away_offense = game.offense_team.team_id == game.away_team.team_id
        zone_playcall = random.choice(["2-3-zone", "3-2-zone"])
        zone_map = ZONE_23_NORMAL if zone_playcall == "2-3-zone" else ZONE_32_NORMAL
        d_destinations = {}
        for pos, spots in zone_map.items():
            spot = spots[0] if spots else "key"
            if pos == "PG" and spot == "key":
                spot = "topLane"
            coords = HCO_STRING_SPOTS.get(spot, {"x": 64, "y": 25})
            d_destinations[pos] = (
                get_away_player_coords(coords) if is_away_offense else dict(coords)
            )
        return (d_destinations, zone_playcall)

    def _build_final_hold_result(self, time_remaining_sec):
        """Build FINAL_HOLD result: time_elapsed = time_remaining, no shot, no fouls/turnovers. Quarter ends after."""
        return {
            "result_type": "FINAL_HOLD",
            "current_turn": "HCO",
            "time_elapsed": int(time_remaining_sec),
            "offense_team_id": self.game.offense_team.team_id,
            "possession_flips": False,
            "text": "Hold for final shot.",
            "next_play_type": None,
            "next_turn": None,
        }

    def _execute_final_turn_force_foul(self):
        """Edge case: Slow It Down + Force Foul at Final Turn time. Victim = PG (ball handler)."""
        from BackEnd.utils import situational_logic as sl
        from BackEnd.engine.phase_resolution import (
            defender_coords_by_pos_from_lineup,
            grid_coords_from_player,
            resolve_non_shooting_foul,
            select_defender_closest_to_victim,
        )
        off_lineup = self.game.offense_team.lineup
        def_lineup = self.game.defense_team.lineup
        victim = off_lineup.get("PG") or next((p for p in off_lineup.values() if p), None)
        if not victim or not def_lineup:
            return None
        victim_coords = grid_coords_from_player(victim)
        d_dest = defender_coords_by_pos_from_lineup(def_lineup)
        foul_player = select_defender_closest_to_victim(victim_coords, def_lineup, d_dest)
        if not foul_player:
            return None
        sl.log_force_foul_debug(
            self.game,
            "FINAL_TURN_EXECUTE",
            time_remaining=self.game.game_state.get("time_remaining"),
            fouler=foul_player,
            victim=victim,
            note="offense has possession (PG victim)",
        )
        self.game.game_state["foul_team"] = "DEFENSE"
        roles = {
            "ball_handler": victim,
            "defender": foul_player,
            "foul_player": foul_player,
            "shooter": victim,
            "screener": None,
            "passer": None,
        }
        result = resolve_non_shooting_foul(
            roles, self.game, time_elapsed_override=sl.force_foul_time_elapsed()
        )
        result["offense_team_id"] = self.game.offense_team.team_id
        result["current_turn"] = "HCO"
        result["quick_foul"] = True
        result["force_foul_final_turn"] = True
        result["victim_id"] = getattr(victim, "player_id", None)
        victim.coords = dict(victim_coords)
        attach_position_snapshots(
            result,
            [
                build_phase_post_stopper_snapshot(
                    self.game,
                    off_lineup,
                    def_lineup,
                    None,
                    roles,
                    "HCO",
                    "non_shooting_foul",
                    "hco_force_foul_final_turn",
                )
            ],
        )
        return result

    def resolve_fast_break(self):
        return resolve_fast_break_logic(self.game) 

    def resolve_free_throw(self):
        return resolve_free_throw_logic(self.game)
    
    def resolve_turnover(self):
        return resolve_turnover_logic(self.game)
    
    def setup_timeout_turn(self, timeout_reason="USER", calling_team=None, foul_out_player=None, foul_out_context=None):
        """
        Create a TIMEOUT turn payload.
        
        Args:
            timeout_reason: "USER", "COMPUTER", "FOUL_OUT", or "QUARTER_END"
            calling_team: Team object that called the timeout (for USER/COMPUTER)
            foul_out_player: Player object that fouled out (for FOUL_OUT)
            foul_out_context: Dict with foul context for FOUL_OUT (foul_type, is_shooting_foul, is_bonus, next_play_type, shooter)
        
        Returns:
            dict: Timeout turn payload with next_play_type determined based on game state
        """
        game = self.game
        game_state = game.game_state
        
        # ✅ FOUL OUT: Determine next_play_type based on foul context (SS&S)
        if timeout_reason == "FOUL_OUT" and foul_out_context:
            # Use foul context to determine next play type
            next_play_type = foul_out_context.get("next_play_type", "SIDE_INBOUND")
            logging.info(f"✅ FOUL OUT: next_play_type from context: {next_play_type}")
            
            # Store shooter for free throw resume if applicable
            if next_play_type == "FREE_THROW" and foul_out_context.get("shooter"):
                game_state["shooter"] = foul_out_context["shooter"]
                logging.info(f"✅ FOUL OUT: Stored shooter for free throw: {getattr(foul_out_context['shooter'], 'name', 'Unknown')}")
        elif game_state.get("free_throws_remaining", 0) > 0:
            # Regular timeout with free throws pending
            next_play_type = "FREE_THROW"
        else:
            # Regular timeout or foul out without context (fallback)
            next_play_type = "SIDE_INBOUND"
        
        # Store next_play_type in game_state for resume
        game_state["timeout_next_play_type"] = next_play_type
        
        # Build timeout turn payload
        payload = {
            "result_type": "TIMEOUT",
            "current_turn": "TIMEOUT",
            "timeout_reason": timeout_reason,
            "next_play_type": next_play_type,
            "next_turn": next_play_type,
            "offense_team_id": game.offense_team.team_id,
            "quarter": game.quarter,
            "text": self._get_timeout_text(timeout_reason, calling_team, foul_out_player),
            "time_elapsed": 0,  # Timeouts don't consume game time
            "possession_flips": False,
        }
        
        # Add timeout calling team info
        if calling_team:
            payload["timeout_calling_team"] = {
                "name": calling_team.name,
                "team_id": calling_team.team_id,
            }
            # Reduce timeout count if user or computer called it
            if timeout_reason in ["USER", "COMPUTER"]:
                if calling_team.timeouts > 0:
                    calling_team.timeouts -= 1
                    logging.info(f"⏸️ TIMEOUT: {calling_team.name} called timeout. Remaining: {calling_team.timeouts}")
        
        # Add foul out player info (include photo so frontend can show player image)
        if foul_out_player:
            payload["foul_out_player"] = {
                "name": getattr(foul_out_player, "name", "Unknown"),
                "player_id": getattr(foul_out_player, "player_id", None),
                "team": getattr(foul_out_player, "team", None),
                "photo": getattr(foul_out_player, "photo", None),
            }
        
        # Add current timeout counts for frontend display
        payload["home_team_timeouts"] = getattr(game.home_team, 'timeouts', 4)
        payload["away_team_timeouts"] = getattr(game.away_team, 'timeouts', 4)
        
        return payload
    
    def _get_timeout_text(self, timeout_reason, calling_team, foul_out_player):
        """Generate timeout announcement text."""
        if timeout_reason == "FOUL_OUT":
            player_name = getattr(foul_out_player, "name", "Unknown") if foul_out_player else "Unknown"
            return f"{player_name} has fouled out! Timeout called for lineup adjustment."
        elif timeout_reason == "USER":
            team_name = calling_team.name if calling_team else "Team"
            return f"{team_name} calls a timeout!"
        elif timeout_reason == "COMPUTER":
            team_name = calling_team.name if calling_team else "Team"
            return f"{team_name} Calls a Timeout"
        elif timeout_reason == "QUARTER_END":
            return "End of quarter timeout."
        else:
            return "Timeout called."
    
    def can_call_timeout(self, team):
        """Check if a team has timeouts remaining."""
        return getattr(team, 'timeouts', 4) > 0
    
    def should_computer_call_timeout(self, computer_team, turn_type):
        """
        Check if computer team should call timeout during BIP/SIP turn.
        
        Args:
            computer_team: TeamManager instance for the computer team
            turn_type: "BASELINE_INBOUND" or "SIDE_INBOUND"
        
        Returns:
            bool: True if computer should call timeout, False otherwise
        """
        game = self.game
        game_state = game.game_state
        is_full_simulation = game_state.get("_is_full_simulation", False)
        
        logging.debug(f"🔍 [COMPUTER TIMEOUT CHECK] Team: {computer_team.name}, Turn Type: {turn_type}, Quarter: {game.quarter}")
        
        # Only check during BIP/SIP turns
        if turn_type not in ["BASELINE_INBOUND", "SIDE_INBOUND"]:
            logging.debug(f"🔍 [COMPUTER TIMEOUT CHECK] Skipping - invalid turn type: {turn_type}")
            return False
        
        # In Play Quarter (turn-by-turn), user teams can only call timeouts manually via the timeout button.
        # In full simulation (Sim Quarter / Sim Full Game), we allow the user team to use the same
        # timeout logic as computer teams, silently inside the sim (no UX interruption).
        if computer_team.is_user_team and not is_full_simulation:
            logging.debug(f"🔍 [COMPUTER TIMEOUT CHECK] Skipping - user team in turn-by-turn mode: {computer_team.name}")
            return False
        
        # Check if team has timeouts remaining
        if not self.can_call_timeout(computer_team):
            logging.debug(f"🔍 [COMPUTER TIMEOUT CHECK] Skipping - no timeouts remaining: {computer_team.name} (remaining: {computer_team.timeouts})")
            return False
        
        # Initialize computer timeout tracking in game_state
        if "computer_timeouts" not in game_state:
            game_state["computer_timeouts"] = {}
        if computer_team.name not in game_state["computer_timeouts"]:
            game_state["computer_timeouts"][computer_team.name] = {}
        
        quarter = game.quarter
        team_timeouts = game_state["computer_timeouts"][computer_team.name]
        
        # Initialize quarter tracking
        if quarter not in team_timeouts:
            team_timeouts[quarter] = {
                "count": 0,
                "checked_conditions": set()
            }
        
        quarter_data = team_timeouts[quarter]
        
        # Check max timeouts per quarter
        # Q1-Q2: Maximum 1 timeout per quarter
        # Q3: Maximum = remaining timeouts - 1 when quarter starts
        # Q4: Maximum = remaining timeouts when quarter starts
        if quarter <= 2:
            max_timeouts = 1
        elif quarter == 3:
            max_timeouts = max(0, computer_team.timeouts - 1)  # Ensure non-negative
        else:  # Q4
            max_timeouts = computer_team.timeouts
        
        if quarter_data["count"] >= max_timeouts:
            logging.debug(f"🔍 [COMPUTER TIMEOUT CHECK] Skipping - max timeouts reached: {computer_team.name} Q{quarter} (count: {quarter_data['count']}, max: {max_timeouts})")
            return False  # Already at max for this quarter
        
        time_remaining = game_state.get("time_remaining", 0)
        
        # Q4: Computer cannot call timeout until time remaining is under 4 minutes
        if quarter == 4 and time_remaining >= 240:
            logging.debug(f"🔍 [COMPUTER TIMEOUT CHECK] Skipping - Q4 time gate: time_remaining ({time_remaining}s) >= 240s (4:00)")
            return False
        
        logging.debug(f"🔍 [COMPUTER TIMEOUT CHECK] Evaluating conditions for {computer_team.name} Q{quarter} (current count: {quarter_data['count']}, max: {max_timeouts})")
        
        # ✅ FIX: Only check players in the active lineup (not all players on the team)
        # This aligns with autoset lineup logic - we only care about players currently playing
        active_players = [player for player in computer_team.lineup.values() if player is not None]
        
        # Check conditions (each only checks once per occurrence)
        checked = quarter_data["checked_conditions"]
        
        # ========== FOUL CONDITIONS (Quarter-Specific) ==========
        
        # Q1: Player foul logic
        if quarter == 1:
            # Condition 1: Player with 3 fouls - 100% chance
            for player in active_players:
                fouls = player.get_stat("F", "game")
                condition_key = f"3_fouls_{player.player_id}"
                if fouls == 3 and condition_key not in checked:
                    checked.add(condition_key)
                    logging.debug(f"✅ [COMPUTER TIMEOUT] Q1 Condition met: {player.get_name()} has 3 fouls (100% chance)")
                    return True  # 100% chance
            
            # Condition 2: Player with 2 fouls - 30% chance
            for player in active_players:
                fouls = player.get_stat("F", "game")
                condition_key = f"2_fouls_{player.player_id}"
                if fouls == 2 and condition_key not in checked:
                    checked.add(condition_key)
                    roll = random.random()
                    if roll < 0.30:
                        logging.debug(f"✅ [COMPUTER TIMEOUT] Q1 Condition met: {player.get_name()} has 2 fouls (30% chance, rolled {roll:.2f})")
                        return True
                    else:
                        logging.debug(f"🔍 [COMPUTER TIMEOUT] Q1 Condition checked: {player.get_name()} has 2 fouls (30% chance, rolled {roll:.2f} - no timeout)")
        
        # Q2: Player foul logic (no time gate)
        elif quarter == 2:
            # Condition 1: Player with 4 fouls - 100% chance
            for player in active_players:
                fouls = player.get_stat("F", "game")
                condition_key = f"4_fouls_{player.player_id}"
                if fouls == 4 and condition_key not in checked:
                    checked.add(condition_key)
                    logging.debug(f"✅ [COMPUTER TIMEOUT] Q2 Condition met: {player.get_name()} has 4 fouls (100% chance)")
                    return True  # 100% chance
            
            # Condition 2: Player with 3 fouls - 90% chance
            for player in active_players:
                fouls = player.get_stat("F", "game")
                condition_key = f"3_fouls_{player.player_id}"
                if fouls == 3 and condition_key not in checked:
                    checked.add(condition_key)
                    roll = random.random()
                    if roll < 0.90:
                        logging.debug(f"✅ [COMPUTER TIMEOUT] Q2 Condition met: {player.get_name()} has 3 fouls (90% chance, rolled {roll:.2f})")
                        return True
                    else:
                        logging.debug(f"🔍 [COMPUTER TIMEOUT] Q2 Condition checked: {player.get_name()} has 3 fouls (90% chance, rolled {roll:.2f} - no timeout)")
        
        # Q3: Player foul logic (only if time_remaining <= 240 seconds / 4:00)
        elif quarter == 3:
            if time_remaining <= 240:
                # Condition 1: Player with 4 fouls - 100% chance
                for player in active_players:
                    fouls = player.get_stat("F", "game")
                    condition_key = f"4_fouls_{player.player_id}"
                    if fouls == 4 and condition_key not in checked:
                        checked.add(condition_key)
                        logging.debug(f"✅ [COMPUTER TIMEOUT] Q3 Condition met: {player.get_name()} has 4 fouls (100% chance)")
                        return True  # 100% chance
                
                # Condition 2: Player with 3 fouls - 90% chance
                for player in active_players:
                    fouls = player.get_stat("F", "game")
                    condition_key = f"3_fouls_{player.player_id}"
                    if fouls == 3 and condition_key not in checked:
                        checked.add(condition_key)
                        roll = random.random()
                        if roll < 0.90:
                            logging.debug(f"✅ [COMPUTER TIMEOUT] Q3 Condition met: {player.get_name()} has 3 fouls (90% chance, rolled {roll:.2f})")
                            return True
                        else:
                            logging.debug(f"🔍 [COMPUTER TIMEOUT] Q3 Condition checked: {player.get_name()} has 3 fouls (90% chance, rolled {roll:.2f} - no timeout)")
            else:
                logging.debug(f"🔍 [COMPUTER TIMEOUT] Q3 Skipping foul check - time_remaining ({time_remaining}s) > 240s (4:00)")
        
        # Q4: Player foul logic (only if time_remaining > 60 seconds)
        elif quarter == 4:
            if time_remaining > 60:
                # Condition: Player with 4 fouls - 90% chance
                for player in active_players:
                    fouls = player.get_stat("F", "game")
                    condition_key = f"4_fouls_{player.player_id}"
                    if fouls == 4 and condition_key not in checked:
                        checked.add(condition_key)
                        roll = random.random()
                        if roll < 0.90:
                            logging.debug(f"✅ [COMPUTER TIMEOUT] Q4 Condition met: {player.get_name()} has 4 fouls (90% chance, rolled {roll:.2f}, time_remaining: {time_remaining}s)")
                            return True
                        else:
                            logging.debug(f"🔍 [COMPUTER TIMEOUT] Q4 Condition checked: {player.get_name()} has 4 fouls (90% chance, rolled {roll:.2f} - no timeout, time_remaining: {time_remaining}s)")
            else:
                logging.debug(f"🔍 [COMPUTER TIMEOUT] Q4 Skipping foul check - time_remaining ({time_remaining}s) <= 60s")
        
        # ========== ENERGY CONDITIONS (All Quarters Q1-Q4) ==========
        # Q1-Q2: thresholds 80% / 70% / 60%. Q3-Q4: thresholds 75% / 65% / 55% (5% lower).
        if quarter in [3, 4]:
            thresh_80, thresh_70, thresh_60 = 0.75, 0.65, 0.55
        else:
            thresh_80, thresh_70, thresh_60 = 0.80, 0.70, 0.60
        
        # Count players below each threshold (only from active lineup)
        players_below_80 = [p for p in active_players if p.attributes.get("NG", 1.0) < thresh_80]
        players_below_70 = [p for p in active_players if p.attributes.get("NG", 1.0) < thresh_70]
        players_below_60 = [p for p in active_players if p.attributes.get("NG", 1.0) < thresh_60]
        count_80 = len(players_below_80)
        count_70 = len(players_below_70)
        count_60 = len(players_below_60)
        
        # Condition 3: 3 players < high threshold (80% or 75%) - 50% chance
        condition_key = "3_players_80_ng"
        if count_80 >= 3 and condition_key not in checked:
            checked.add(condition_key)
            roll = random.random()
            if roll < 0.50:
                logging.debug(f"✅ [COMPUTER TIMEOUT] Energy condition met: 3 players < {int(thresh_80*100)}% NG (50% chance, rolled {roll:.2f})")
                return True
            else:
                logging.debug(f"🔍 [COMPUTER TIMEOUT] Energy condition checked: 3 players < {int(thresh_80*100)}% NG (50% chance, rolled {roll:.2f} - no timeout)")
        
        # Condition 4: 4 players < high threshold - 75% chance
        condition_key = "4_players_80_ng"
        if count_80 >= 4 and condition_key not in checked:
            checked.add(condition_key)
            roll = random.random()
            if roll < 0.75:
                logging.debug(f"✅ [COMPUTER TIMEOUT] Energy condition met: 4 players < {int(thresh_80*100)}% NG (75% chance, rolled {roll:.2f})")
                return True
            else:
                logging.debug(f"🔍 [COMPUTER TIMEOUT] Energy condition checked: 4 players < {int(thresh_80*100)}% NG (75% chance, rolled {roll:.2f} - no timeout)")
        
        # Condition 5: 5 players < high threshold - 90% chance
        condition_key = "5_players_80_ng"
        if count_80 >= 5 and condition_key not in checked:
            checked.add(condition_key)
            roll = random.random()
            if roll < 0.90:
                logging.debug(f"✅ [COMPUTER TIMEOUT] Energy condition met: 5 players < {int(thresh_80*100)}% NG (90% chance, rolled {roll:.2f})")
                return True
            else:
                logging.debug(f"🔍 [COMPUTER TIMEOUT] Energy condition checked: 5 players < {int(thresh_80*100)}% NG (90% chance, rolled {roll:.2f} - no timeout)")
        
        # Condition 6: 3 players < mid threshold (70% or 65%) - 80% chance
        condition_key = "3_players_70_ng"
        if count_70 >= 3 and condition_key not in checked:
            checked.add(condition_key)
            roll = random.random()
            if roll < 0.80:
                logging.debug(f"✅ [COMPUTER TIMEOUT] Energy condition met: 3 players < {int(thresh_70*100)}% NG (80% chance, rolled {roll:.2f})")
                return True
            else:
                logging.debug(f"🔍 [COMPUTER TIMEOUT] Energy condition checked: 3 players < {int(thresh_70*100)}% NG (80% chance, rolled {roll:.2f} - no timeout)")
        
        # Condition 7: 4 players < mid threshold - 90% chance
        condition_key = "4_players_70_ng"
        if count_70 >= 4 and condition_key not in checked:
            checked.add(condition_key)
            roll = random.random()
            if roll < 0.90:
                logging.debug(f"✅ [COMPUTER TIMEOUT] Energy condition met: 4 players < {int(thresh_70*100)}% NG (90% chance, rolled {roll:.2f})")
                return True
            else:
                logging.debug(f"🔍 [COMPUTER TIMEOUT] Energy condition checked: 4 players < {int(thresh_70*100)}% NG (90% chance, rolled {roll:.2f} - no timeout)")
        
        # Condition 8: 5 players < mid threshold - 95% chance
        condition_key = "5_players_70_ng"
        if count_70 >= 5 and condition_key not in checked:
            checked.add(condition_key)
            roll = random.random()
            if roll < 0.95:
                logging.debug(f"✅ [COMPUTER TIMEOUT] Energy condition met: 5 players < {int(thresh_70*100)}% NG (95% chance, rolled {roll:.2f})")
                return True
            else:
                logging.debug(f"🔍 [COMPUTER TIMEOUT] Energy condition checked: 5 players < {int(thresh_70*100)}% NG (95% chance, rolled {roll:.2f} - no timeout)")
        
        # Condition 9: 3 players < low threshold (60% or 55%) - 100% chance
        condition_key = "3_players_60_ng"
        if count_60 >= 3 and condition_key not in checked:
            checked.add(condition_key)
            logging.debug(f"✅ [COMPUTER TIMEOUT] Energy condition met: 3 players < {int(thresh_60*100)}% NG (100% chance)")
            return True  # 100% chance
        
        logging.debug(f"🔍 [COMPUTER TIMEOUT] No conditions met for {computer_team.name} Q{quarter}")
        return False

    def _stamp_oreb_animation_steps(self, result):
        """For OREB-typed results (PUTBACK_MAKE / PUTBACK_MISS / OREB_KICKOUT),
        build the UESS ``animation_steps`` payload and realign
        ``result["time_elapsed"]`` from the schema's total game-clock burn.
        Idempotent + a no-op for any other result_type (e.g., OTB_FOUL).

        For PUTBACK_MISS, also stamps top-level ``ball_bounce_x/y`` from
        ``result["ballSpot"]`` (the second-bounce coords) so:
          1. The OREB emitter's ``[bounce]`` step can target it.
          2. ``game_manager._build_dreb_turn_from_miss`` (extended to fire
             on PUTBACK_MISS) can read it when chaining into a DREB turn.
        And sets ``next_play_type = "HCO"`` if not already set (e.g., not
        overridden to ``FREE_THROW`` by a shooting foul on the putback).
        """
        if not isinstance(result, dict):
            return result
        result_type = (result.get("result_type") or "").upper()
        if result_type not in ("PUTBACK_MAKE", "PUTBACK_MISS", "OREB_KICKOUT"):
            return result

        if result_type == "PUTBACK_MISS":
            ballspot = result.get("ballSpot")
            if isinstance(ballspot, dict):
                bsx = ballspot.get("x")
                bsy = ballspot.get("y")
                if bsx is not None and "ball_bounce_x" not in result:
                    result["ball_bounce_x"] = float(bsx)
                if bsy is not None and "ball_bounce_y" not in result:
                    result["ball_bounce_y"] = float(bsy)
            if not result.get("next_play_type"):
                result["next_play_type"] = "HCO"

        try:
            from BackEnd.engine.oreb_step_emitter import build_oreb_animation_steps
            anim_steps = build_oreb_animation_steps(result, self.game)
            if anim_steps is not None:
                result["animation_steps"] = anim_steps
                # Align result["time_elapsed"] with the schema's total
                # game-clock burn (mirrors the HCO/FCP realignment).
                if anim_steps:
                    first_clock = (anim_steps[0].get("start") or {}).get("clock") or {}
                    last_clock = (anim_steps[-1].get("end") or {}).get("clock") or {}
                    cs_start = first_clock.get("clock_remaining")
                    cs_end = last_clock.get("clock_remaining")
                    if cs_start is not None and cs_end is not None:
                        schema_game_burn = max(0.0, float(cs_start) - float(cs_end))
                        result["time_elapsed"] = int(round(schema_game_burn))
        except Exception as e:
            logging.warning("build_oreb_animation_steps failed: %s", e)
        return result

    def resolve_offensive_rebound_turn(self):
        """
        Process an offensive rebound as a separate turn.
        This is called after a MISS turn that had an OREB.
        
        Returns a turn result for: PUTBACK_MAKE, PUTBACK_MISS, or KICKOUT
        """
        from BackEnd.utils.shared import resolve_offensive_rebound, get_name_safe, unpack_game_context, serialize_lineup
        from BackEnd.models.shot_manager import ShotManager
        
        pending_oreb = self.game.game_state.get("pending_oreb")
        if not pending_oreb:
            return None
        
        rebounder = pending_oreb.get("rebounder")
        rebounder_id = pending_oreb.get("rebounder_id")
        from_block = pending_oreb.get("from_block", False)
        rebounder_name = get_name_safe(rebounder) if rebounder else "UNKNOWN"
        
        # Clear the pending OREB immediately (before processing)
        # If this OREB results in another OREB, it will be set again
        self.game.game_state["pending_oreb"] = None
        
        # Capture player stats before OREB resolution (for deltas)
        pre_stats = {}
        for team in (self.game.home_team, self.game.away_team):
            for player in team.get_all_players():
                pre_stats[player.player_id] = dict(player.stats["game"])
        
        rebounder = pending_oreb["rebounder"]
        game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(self.game)

        # Shot-clock gate (Shot_Clock_System.md § Shot clock 0 → dead-ball turnover):
        # The OREB possession needs enough carried shot clock to reach a shot. If
        # the shot clock is at/near 0 entering the OREB turn, the possession is
        # killed as a dead-ball (shot-clock) turnover BEFORE any putback / kickout
        # / block→HCO handoff — a clean turnover, never HCO's 50/50. Unified ~2s
        # window covers both the putback and block→HCO paths, and catches the
        # clock expiring mid-progression before the next shot.
        entry_shot_clock = int(
            game_state.get(
                "shot_clock_remaining",
                min(30, int(game_state.get("time_remaining", 480) or 0)),
            ) or 0
        )
        OREB_MIN_SHOT_CLOCK_FOR_ATTEMPT = 2  # ≤ this can't reach a shot → turnover
        if entry_shot_clock <= OREB_MIN_SHOT_CLOCK_FOR_ATTEMPT:
            # Credit the offensive rebound only if the shot clock was > 0 at the
            # start of the OREB turn (the board was secured with time on the
            # clock). It was recorded upstream on the block/miss turn, so uncredit
            # it here when the clock had already expired.
            if entry_shot_clock <= 0 and rebounder is not None:
                try:
                    rebounder.record_stat("OREB", -1)
                except Exception:
                    pass
            self.game.update_team_stats()
            sc_violation = self._build_shot_clock_violation_result("OREB")
            sc_violation["rebounderId"] = getattr(rebounder, "player_id", None)
            sc_violation["quarter"] = self.game.quarter
            sc_violation["deltas"] = {}
            sc_violation["player_energy"] = {
                p.player_id: {"NG": p.attributes.get("NG", 1.0), "team": t.name}
                for t in (self.game.home_team, self.game.away_team)
                for _pos, p in t.lineup.items()
                if p
            }
            sc_violation["score"] = dict(self.game.score)
            sc_violation["home_lineup"] = serialize_lineup(self.game.home_team.lineup)
            sc_violation["away_lineup"] = serialize_lineup(self.game.away_team.lineup)
            sc_violation["team_totals"] = {
                self.game.home_team.name: self.game.home_team.get_team_game_stats(),
                self.game.away_team.name: self.game.away_team.get_team_game_stats(),
            }
            return self._stamp_oreb_animation_steps(sc_violation)

        # OREB after block: go straight to HCO, no putback attempt (SS&S: one place to enforce)
        if from_block:
            game_state["offensive_state"] = "HCO"
            deltas = {}
            for team in (self.game.home_team, self.game.away_team):
                for player in team.get_all_players():
                    prev = pre_stats.get(player.player_id, {})
                    diff = {}
                    for stat in player.stats["game"]:
                        if stat == "REB" or stat == "Outlet_Score_List" or stat == "Shot_Result_List":
                            continue
                        current_val = player.stats["game"].get(stat, 0)
                        prev_val = prev.get(stat, 0)
                        delta = current_val - prev_val
                        if delta != 0:
                            diff[stat] = delta
                    if diff:
                        deltas[player.player_id] = {"team": team.name, "stats": diff}
            player_energy = {}
            for team in (self.game.home_team, self.game.away_team):
                for pos, player in team.lineup.items():
                    player_energy[player.player_id] = {
                        "NG": player.attributes.get("NG", 1.0),
                        "team": team.name
                    }
            self.game.update_team_stats()
            # OREB reset: capture the board and let the following HCO entry
            # route from the rebounder to the play's real step-0 initiator.
            _base = 3
            _oreb_te = round(_base)
            from BackEnd.utils.position_snapshot_ledger import (
                attach_position_snapshots,
                build_oreb_kickout_snapshot,
            )

            block_payload = {
                "result_type": "OREB_KICKOUT",
                "ball_handler": getattr(rebounder, "player_id", None),
                "text": f"{rebounder_name} secures the rebound after the block. Reset to half-court.",
                "possession_flips": False,
                "time_elapsed": _oreb_te,
                "oreb_hold_seconds": _oreb_te - 1,
                "oreb_action_seconds": 1,
                "offense_team_id": self.game.offense_team.team_id,
                "current_turn": "OREB",
                "next_play_type": "HCO",
                "next_turn": "HCO",
                "animations": [],
                "rebounderId": getattr(rebounder, "player_id", None),
                "pgId": None,
                "kickout_deferred_to_hco_entry": True,
                "quarter": self.game.quarter,
                "deltas": deltas,
                "player_energy": player_energy,
                "score": dict(self.game.score),
                "home_lineup": serialize_lineup(self.game.home_team.lineup),
                "away_lineup": serialize_lineup(self.game.away_team.lineup),
                "team_totals": {
                    self.game.home_team.name: self.game.home_team.get_team_game_stats(),
                    self.game.away_team.name: self.game.away_team.get_team_game_stats()
                },
                "team_stats": {
                    self.game.home_team.name: {
                        "offense": self.game.home_team.scouting_data.get("offense", {}),
                        "defense": self.game.home_team.scouting_data.get("defense", {}),
                    },
                    self.game.away_team.name: {
                        "offense": self.game.away_team.scouting_data.get("offense", {}),
                        "defense": self.game.away_team.scouting_data.get("defense", {}),
                    }
                },
            }
            attach_position_snapshots(
                block_payload,
                [build_oreb_kickout_snapshot(self.game, off_lineup, def_lineup)],
            )
            return self._stamp_oreb_animation_steps(block_payload)
        
        # Resolve what happens with the offensive rebound
        oreb_event = resolve_offensive_rebound(self.game, rebounder)

        if oreb_event.get("event_type") == "OTB_FOUL":
            from BackEnd.engine.phase_resolution import resolve_non_shooting_foul

            foul_player = (
                off_team.get_player_by_id(str(oreb_event.get("foul_player_id")))
                or def_team.get_player_by_id(str(oreb_event.get("foul_player_id")))
            )
            victim = (
                off_team.get_player_by_id(str(oreb_event.get("victim_id")))
                or def_team.get_player_by_id(str(oreb_event.get("victim_id")))
            )
            if foul_player and victim:
                self.game.game_state["foul_team"] = oreb_event.get("foul_team", "OFFENSE")
                foul_result = resolve_non_shooting_foul(
                    {
                        "ball_handler": victim,
                        "defender": foul_player if oreb_event.get("foul_team") == "DEFENSE" else None,
                        "foul_player": foul_player,
                        "shooter": victim,
                        "screener": None,
                        "passer": None,
                    },
                    self.game,
                    time_elapsed_override=oreb_event.get("timeElapsed"),
                )
                # OREB foul turns are returned directly to the API response, so they must not
                # carry raw Player objects from resolve_non_shooting_foul().
                foul_result["ball_handler"] = getattr(victim, "player_id", None)
                foul_result["shooter"] = getattr(victim, "player_id", None)
                foul_result["defender"] = (
                    getattr(foul_player, "player_id", None)
                    if oreb_event.get("foul_team") == "DEFENSE"
                    else None
                )
                foul_result["screener"] = None
                foul_result["passer"] = None
                foul_result["otb_foul"] = True
                foul_result["text"] = "Over the back!"
                foul_result["current_turn"] = "OREB"
                if oreb_event.get("position_snapshots"):
                    foul_result["position_snapshots"] = oreb_event["position_snapshots"]
                return foul_result
        
        if oreb_event["event_type"] == "PUTBACK_ATTEMPT":
            self.logger.log("putbackStart")
            self.logger.log(oreb_event["result"].lower())
            # OREB: collapse+attach 3 game s; rebounder then acts (putback)
            _oreb_te = 3

            # Build roles for the putback shot (for animation and three-point determination)
            # Putback shots don't have a skeleton, so we'll use current coords
            defender_id = oreb_event.get("defenderId")
            defender = None
            if defender_id is not None:
                defender = def_team.get_player_by_id(str(defender_id))
            if defender is None:
                defender = next((p for p in def_lineup.values() if p is not None), None)
            
            putback_roles = {
                "shooter": rebounder,
                "ball_handler": rebounder,
                "defender": defender,
                "passer": None,
                "screener": None,
                "steps": [],  # No skeleton for putbacks
            }
            
            if oreb_event["result"] == "MAKE":
                # OREB putback and-one: resolver sets FREE_THROW + foul fields together; if next_play_type
                # is missing or still BIP, Pattern A would synthesize an extra BASELINE_INBOUND before FTs.
                raw_next = oreb_event.get("next_play_type")
                ft_rem = int(oreb_event.get("free_throws_remaining", 0) or 0)
                putback_shooting_foul_fts = bool(oreb_event.get("foul_player_id")) and (
                    ft_rem > 0
                    or bool(oreb_event.get("has_and_one"))
                    or game_state.get("offensive_state") == "FREE_THROW"
                )
                if raw_next == "FREE_THROW" or putback_shooting_foul_fts:
                    putback_next_play = "FREE_THROW"
                elif raw_next not in (None, ""):
                    putback_next_play = raw_next
                else:
                    putback_next_play = "BASELINE_INBOUND"

                is_and_one = putback_next_play == "FREE_THROW"
                text = (
                    f"{get_name_safe(rebounder)} goes back up, scores, and gets fouled!"
                    if is_and_one
                    else f"{get_name_safe(rebounder)} goes back up and puts it in!"
                )
                possession_flips = not is_and_one
                # Check for defensive pressure opportunity (FCP/HCT) after putback make
                if is_and_one:
                    pressure_type = None
                    next_defensive_setup = None
                else:
                    pressure_type = self.determine_defensive_pressure_type()
                    game_state["offensive_state"] = pressure_type
                    next_defensive_setup = pressure_type
                
                shooter_team_id = getattr(rebounder, "team_id", None) or off_team.team_id
                # print(f"🏀 PUTBACK_MAKE: shooter={get_name_safe(rebounder)} team_id={shooter_team_id} off_team={off_team.name}")
                
                # Compute stat deltas (same as run_micro_turn)
                deltas = {}
                for team in (self.game.home_team, self.game.away_team):
                    for player in team.get_all_players():
                        prev = pre_stats.get(player.player_id, {})
                        diff = {}
                        for stat in player.stats["game"]:
                            if stat == "REB" or stat == "Outlet_Score_List" or stat == "Shot_Result_List":
                                continue  # Skip REB (calculated) and Outlet_Score_List (list, not numeric)
                            current_val = player.stats["game"].get(stat, 0)
                            prev_val = prev.get(stat, 0)
                            delta = current_val - prev_val
                            if delta != 0:
                                diff[stat] = delta
                        if diff:
                            deltas[player.player_id] = {"team": team.name, "stats": diff}
                
                # Include current energy levels
                player_energy = {}
                for team in (self.game.home_team, self.game.away_team):
                    for pos, player in team.lineup.items():
                        player_energy[player.player_id] = {
                            "NG": player.attributes.get("NG", 1.0),
                            "team": team.name
                        }
                
                # Update team stats before sending
                self.game.update_team_stats()
                
                pm = {
                    "result_type": "PUTBACK_MAKE",
                    "ball_handler": getattr(rebounder, "player_id", None),
                    "shooter": getattr(rebounder, "player_id", None),
                    "shooter_team_id": shooter_team_id,
                    "defender": getattr(defender, "player_id", None),
                    "text": text,
                    "possession_flips": possession_flips,
                    "time_elapsed": _oreb_te,
                    "oreb_hold_seconds": _oreb_te - 1,
                    "oreb_action_seconds": 1,
                    "points": oreb_event.get("points", 2),
                    "scoring_team": off_team.name,
                    "offense_team_id": off_team.team_id,  # ✅ SS&S: Add offense_team_id to all results
                    "current_turn": "OREB",  # ✅ SS&S: Explicit turn type
                    "next_play_type": putback_next_play,
                    "next_turn": putback_next_play,
                    "next_defensive_setup": pressure_type,
                    "animations": [],  # Putbacks use simple animation, not skeleton
                    "rebounderId": getattr(rebounder, "player_id", None),
                    "quarter": self.game.quarter,
                    # Add fields needed by frontend for stat display
                    "deltas": deltas,
                    "player_energy": player_energy,
                    "score": dict(self.game.score),
                    "home_lineup": serialize_lineup(self.game.home_team.lineup),
                    "away_lineup": serialize_lineup(self.game.away_team.lineup),
                    "team_totals": {
                        self.game.home_team.name: self.game.home_team.get_team_game_stats(),
                        self.game.away_team.name: self.game.away_team.get_team_game_stats()
                    },
                    "team_stats": {
                        self.game.home_team.name: {
                            "offense": self.game.home_team.scouting_data.get("offense", {}),
                            "defense": self.game.home_team.scouting_data.get("defense", {})
                        },
                        self.game.away_team.name: {
                            "offense": self.game.away_team.scouting_data.get("offense", {}),
                            "defense": self.game.away_team.scouting_data.get("defense", {})
                        }
                    },
                }
                if oreb_event.get("foul_player_id"):
                    pm["foul_player_id"] = oreb_event["foul_player_id"]
                    pm["foul_team"] = oreb_event.get("foul_team")
                    pm["free_throws_remaining"] = oreb_event.get("free_throws_remaining", 0)
                    pm["has_and_one"] = oreb_event.get("has_and_one", False)
                    if oreb_event.get("fouled_out"):
                        pm["fouled_out"] = True
                        pm["foul_out_player"] = oreb_event.get("foul_out_player")
                        pm["foul_count"] = oreb_event.get("foul_count")
                if oreb_event.get("position_snapshots"):
                    pm["position_snapshots"] = oreb_event["position_snapshots"]
                attach_putback_shot_sfx_fields(pm, oreb_event)
                # Forward shot variant + rattle/backboard extras to the
                # PUTBACK_MAKE turn so the FE renders the variant-driven
                # rim effects (resolved in ``resolve_offensive_rebound``).
                if oreb_event.get("shot_variant") and "shot_variant" not in pm:
                    pm["shot_variant"] = oreb_event["shot_variant"]
                for _vk in (
                    "shot_variant_rattle_start",
                    "shot_variant_rattle_progression",
                    "shot_variant_backboard_y_offset",
                    "shot_variant_backboard_miss_rim_offset_x",
                    "shot_variant_backboard_miss_rim_offset_y",
                    "shot_variant_bank_miss_sfx_file",
                ):
                    if _vk in oreb_event and _vk not in pm:
                        pm[_vk] = oreb_event[_vk]
                return self._stamp_oreb_animation_steps(pm)
            else:
                # Putback missed - check for rebound
                text = f"{get_name_safe(rebounder)} goes back up but misses."
                
                # Initialize possession_flips based on rebound type
                possession_flips = False
                
                shooter_team_id = getattr(rebounder, "team_id", None) or off_team.team_id
                # print(f"🏀 PUTBACK_MISS: shooter={get_name_safe(rebounder)} rebounder.team_id={getattr(rebounder, 'team_id', None)} off_team.team_id={off_team.team_id} off_team.name={off_team.name} final_shooter_team_id={shooter_team_id}")
                
                result = {
                    "result_type": "PUTBACK_MISS",
                    "ball_handler": getattr(rebounder, "player_id", None),
                    "shooter": getattr(rebounder, "player_id", None),
                    "shooter_team_id": shooter_team_id,
                    "defender": getattr(defender, "player_id", None),
                    "text": text,
                    "possession_flips": possession_flips,  # Will be updated based on rebound type
                    "time_elapsed": _oreb_te,
                    "oreb_hold_seconds": _oreb_te - 1,
                    "oreb_action_seconds": 1,
                    "offense_team_id": off_team.team_id,  # ✅ SS&S: Add offense_team_id to all results
                    "current_turn": "OREB",  # ✅ SS&S: Explicit turn type
                    "animations": [],
                    "rebounderId": getattr(rebounder, "player_id", None),
                    "quarter": self.game.quarter,
                }
                if oreb_event.get("foul_player_id"):
                    result["foul_player_id"] = oreb_event["foul_player_id"]
                    result["foul_team"] = oreb_event.get("foul_team")
                    result["next_play_type"] = oreb_event.get("next_play_type")
                    result["free_throws_remaining"] = oreb_event.get("free_throws_remaining", 0)
                    if oreb_event.get("fouled_out"):
                        result["fouled_out"] = True
                        result["foul_out_player"] = oreb_event.get("foul_out_player")
                        result["foul_count"] = oreb_event.get("foul_count")
                
                # Check if there's another rebound
                if oreb_event.get("rebound"):
                    rebound_data = oreb_event["rebound"]
                    rebound_type = rebound_data.get("rebound_type", "DREB")
                    result["rebound_type"] = rebound_type
                    result["rebounderId"] = rebound_data.get("rebounderId")
                    result["ballSpot"] = rebound_data.get("ballSpot")  # Add ballSpot for frontend animation
                    result["offense_rebounders"] = rebound_data.get("offense_rebounders") or []
                    result["defense_rebounders"] = rebound_data.get("defense_rebounders") or []
                    
                    # Set possession flip based on rebound type
                    possession_flips = (rebound_type == "DREB")
                    result["possession_flips"] = possession_flips
                    
                    rebounder_id = rebound_data.get("rebounderId")
                    rebound_type = rebound_data.get("rebound_type", "DREB")
                    # Normalize ID for robust lookup (str comparison avoids type mismatch)
                    rebounder_id_str = str(rebounder_id) if rebounder_id is not None else None
                    if rebounder_id_str is None:
                        logging.warning(f"⚠️ [PUTBACK MISS => REBOUND] rebounderId is None, cannot look up rebounder")
                    new_rebounder = None
                    players_searched = 0
                    for player in list(off_team.get_all_players()) + list(def_team.get_all_players()):
                        players_searched += 1
                        player_id = getattr(player, "player_id", None)
                        if player_id is not None and str(player_id) == rebounder_id_str:
                            new_rebounder = player
                            logging.info(f"✅ [PUTBACK MISS => REBOUND] Found rebounder: {get_name_safe(player)} (ID: {player_id}), Type: {rebound_type}")
                            break
                    # Fallback: look up by ID in case iteration missed (e.g. key type)
                    if new_rebounder is None and rebounder_id_str:
                        new_rebounder = off_team.get_player_by_id(rebounder_id_str) or def_team.get_player_by_id(rebounder_id_str)
                        if new_rebounder:
                            logging.info(f"✅ [PUTBACK MISS => REBOUND] Found rebounder via get_player_by_id: {get_name_safe(new_rebounder)}")
                    if new_rebounder is None and rebounder_id_str:
                        logging.warning(f"⚠️ [PUTBACK MISS => REBOUND] Could not find rebounder with ID={rebounder_id_str} after searching {players_searched} players")
                    # Stat already recorded in shared.py on canonical roster player; no re-record here (avoids double-count)
                    if new_rebounder:
                        text += f" {get_name_safe(new_rebounder)} grabs the rebound."
                        result["text"] = text
                    
                    # If it's another OREB, set pending for next turn
                    if rebound_type == "OREB" and new_rebounder:
                        new_rebounder_name = get_name_safe(new_rebounder)
                        oreb_stat = new_rebounder.stats["game"].get("OREB", 0)
                        # ✅ DEBUG: Log player object info to verify it's the same object
                        new_rebounder_team = getattr(new_rebounder, "team", None)
                        new_rebounder_team_id = getattr(new_rebounder, "team_id", None)
                        logging.warning(f"🔁 [PUTBACK MISS => REBOUND] Setting pending_oreb for next turn: {new_rebounder_name} (ID: {rebounder_id}), Current OREB: {oreb_stat}, team={new_rebounder_team}, team_id={new_rebounder_team_id}, object_id={id(new_rebounder)}")
                        game_state["pending_oreb"] = {
                            "rebounder": new_rebounder,
                            "rebounder_id": rebounder_id,
                        }
                    elif rebound_type == "OREB" and new_rebounder is None:
                        logging.error(f"❌ [PUTBACK MISS => REBOUND] Cannot set pending_oreb - rebounder not found! ID: {rebounder_id}, Type: {rebound_type}")
                    elif rebound_data.get("rebound_type") == "DREB":
                        # Defensive rebound - preserve next_play_type from original shot
                        # FB eligibility + play key are set on the miss shot turn (`pending_dreb_fb_play_key` / offensive_state).
                        # Don't recalculate here.
                        next_play_type = game_state.get("offensive_state", "HCO")
                        result["next_play_type"] = next_play_type
                
                # Compute stat deltas (same as run_micro_turn)
                # Exclude REB from deltas since it's automatically calculated from OREB + DREB
                # The frontend will calculate REB from OREB + DREB to avoid double-counting
                deltas = {}
                for team in (self.game.home_team, self.game.away_team):
                    for player in team.get_all_players():
                        prev = pre_stats.get(player.player_id, {})
                        diff = {}
                        for stat in player.stats["game"]:
                            if stat == "REB" or stat == "Outlet_Score_List" or stat == "Shot_Result_List":
                                continue  # Skip REB (calculated) and Outlet_Score_List (list, not numeric)
                            current_val = player.stats["game"].get(stat, 0)
                            prev_val = prev.get(stat, 0)
                            delta = current_val - prev_val
                            if delta != 0:
                                diff[stat] = delta
                                # 🔍 DEBUG: Log OREB/DREB deltas specifically
                                if stat in {"OREB", "DREB"}:
                                    logging.warning(f"🔍 [DELTA COMPUTATION] {get_name_safe(player)} (ID: {player.player_id}), Object ID: {id(player)}, "
                                                  f"Stat: {stat}, Prev: {prev_val}, Current: {current_val}, Delta: {delta}")
                        if diff:
                            deltas[player.player_id] = {"team": team.name, "stats": diff}
                
                # Include current energy levels
                player_energy = {}
                for team in (self.game.home_team, self.game.away_team):
                    for pos, player in team.lineup.items():
                        player_energy[player.player_id] = {
                            "NG": player.attributes.get("NG", 1.0),
                            "team": team.name
                        }
                
                # Update team stats before sending
                self.game.update_team_stats()
                
                # Add fields needed by frontend for stat display
                result["deltas"] = deltas
                result["player_energy"] = player_energy
                result["score"] = dict(self.game.score)
                result["home_lineup"] = serialize_lineup(self.game.home_team.lineup)
                result["away_lineup"] = serialize_lineup(self.game.away_team.lineup)
                result["team_totals"] = {
                    self.game.home_team.name: self.game.home_team.get_team_game_stats(),
                    self.game.away_team.name: self.game.away_team.get_team_game_stats()
                }
                result["team_stats"] = {
                    self.game.home_team.name: {
                        "offense": self.game.home_team.scouting_data.get("offense", {}),
                        "defense": self.game.home_team.scouting_data.get("defense", {})
                    },
                    self.game.away_team.name: {
                        "offense": self.game.away_team.scouting_data.get("offense", {}),
                        "defense": self.game.away_team.scouting_data.get("defense", {})
                    }
                }
                
                if oreb_event.get("position_snapshots"):
                    result["position_snapshots"] = oreb_event["position_snapshots"]
                attach_putback_shot_sfx_fields(result, oreb_event)
                # Forward shot variant + rattle/backboard extras.
                if oreb_event.get("shot_variant") and "shot_variant" not in result:
                    result["shot_variant"] = oreb_event["shot_variant"]
                for _vk in (
                    "shot_variant_rattle_start",
                    "shot_variant_rattle_progression",
                    "shot_variant_backboard_y_offset",
                    "shot_variant_backboard_miss_rim_offset_x",
                    "shot_variant_backboard_miss_rim_offset_y",
                    "shot_variant_bank_miss_sfx_file",
                ):
                    if _vk in oreb_event and _vk not in result:
                        result[_vk] = oreb_event[_vk]
                return self._stamp_oreb_animation_steps(result)
        
        else:
            # Kickout
            self.logger.log("kickoutStart")
            text = f"{get_name_safe(rebounder)} secures the offensive rebound to reset."
            game_state["offensive_state"] = "HCO"
            
            # Compute stat deltas (same as run_micro_turn)
            deltas = {}
            for team in (self.game.home_team, self.game.away_team):
                for player in team.get_all_players():
                    prev = pre_stats.get(player.player_id, {})
                    diff = {}
                    for stat in player.stats["game"]:
                        if stat == "REB" or stat == "Outlet_Score_List" or stat == "Shot_Result_List":
                            continue  # Skip REB (calculated) and Outlet_Score_List (list, not numeric)
                        current_val = player.stats["game"].get(stat, 0)
                        prev_val = prev.get(stat, 0)
                        delta = current_val - prev_val
                        if delta != 0:
                            diff[stat] = delta
                    if diff:
                        deltas[player.player_id] = {"team": team.name, "stats": diff}
            
            # Include current energy levels
            player_energy = {}
            for team in (self.game.home_team, self.game.away_team):
                for pos, player in team.lineup.items():
                    player_energy[player.player_id] = {
                        "NG": player.attributes.get("NG", 1.0),
                        "team": team.name
                    }
            
            # Update team stats before sending
            self.game.update_team_stats()
            # OREB reset: capture the board and let the following HCO entry
            # route from the rebounder to the play's real step-0 initiator.
            _base_kickout = 3
            _oreb_te_kickout = round(_base_kickout)
            kick_payload = {
                "result_type": "OREB_KICKOUT",
                "ball_handler": getattr(rebounder, "player_id", None),
                "text": text,
                "possession_flips": False,
                "time_elapsed": _oreb_te_kickout,
                "oreb_hold_seconds": _oreb_te_kickout - 1,
                "oreb_action_seconds": 1,
                "offense_team_id": self.game.offense_team.team_id,  # ✅ SS&S: Add offense_team_id to all results
                "current_turn": "OREB",  # ✅ SS&S: Explicit turn type
                "next_play_type": "HCO",
                "next_turn": "HCO",  # ✅ SS&S: Kickouts continue to HCO
                "animations": [],
                "rebounderId": getattr(rebounder, "player_id", None),
                "pgId": None,
                "kickout_deferred_to_hco_entry": True,
                "quarter": self.game.quarter,
                # Add fields needed by frontend for stat display
                "deltas": deltas,
                "player_energy": player_energy,
                "score": dict(self.game.score),
                "home_lineup": serialize_lineup(self.game.home_team.lineup),
                "away_lineup": serialize_lineup(self.game.away_team.lineup),
                "team_totals": {
                    self.game.home_team.name: self.game.home_team.get_team_game_stats(),
                    self.game.away_team.name: self.game.away_team.get_team_game_stats()
                },
                "team_stats": {
                    self.game.home_team.name: {
                        "offense": self.game.home_team.scouting_data.get("offense", {}),
                        "defense": self.game.home_team.scouting_data.get("defense", {})
                    },
                    self.game.away_team.name: {
                        "offense": self.game.away_team.scouting_data.get("offense", {}),
                        "defense": self.game.away_team.scouting_data.get("defense", {})
                    }
                },
            }
            if oreb_event.get("position_snapshots"):
                kick_payload["position_snapshots"] = oreb_event["position_snapshots"]
            return self._stamp_oreb_animation_steps(kick_payload)

    def update_clock_and_possession(self, result):
        _cc_clock_start = int(self.game.game_state.get("time_remaining", 0))
        _cc_sc_start = int(self.game.game_state.get("shot_clock_remaining", 30))

        def _is_no_impact_turn(turn_result):
            no_impact_types = {"FREE_THROW", "SIDE_INBOUND", "BASELINE_INBOUND", "TIMEOUT"}
            rt = turn_result.get("result_type")
            if rt in no_impact_types:
                return True
            te = turn_result.get("time_elapsed", 0)
            return int(te or 0) == 0 and rt in {"SIDE_INBOUND", "BASELINE_INBOUND"}

        def _is_shot_attempt(turn_result):
            return turn_result.get("result_type") in {"MAKE", "MISS", "BLOCK"} or (
                turn_result.get("result_type") == "FOUL"
                and (
                    int(turn_result.get("free_throws_remaining", 0) or 0) > 0
                    or turn_result.get("next_play_type") == "FREE_THROW"
                )
            )

        def _shot_detach_elapsed_seconds(turn_result, fallback_elapsed):
            """
            Resolve the live-possession seconds consumed before shot detach.

            When step timing exists, shot detach occurs at resolution_step_index, so the
            shot clock should burn only the executed step time through that boundary while
            the game clock may continue running through the remainder of the turn.
            """
            raw_steps = turn_result.get("step_clock_seconds")
            if not isinstance(raw_steps, list) or not raw_steps:
                return int(fallback_elapsed)
            try:
                step_clock_seconds = [max(0, int(sec or 0)) for sec in raw_steps]
            except (TypeError, ValueError):
                return int(fallback_elapsed)

            max_index = len(step_clock_seconds) - 1
            raw_index = turn_result.get("resolution_step_index")
            try:
                resolution_step_index = int(raw_index)
            except (TypeError, ValueError):
                resolution_step_index = max_index
            resolution_step_index = max(0, min(max_index, resolution_step_index))
            return int(sum(step_clock_seconds[: resolution_step_index + 1]))

        def _should_reset_shot_clock(turn_result):
            rt = turn_result.get("result_type")
            raw_foul_team = str(turn_result.get("foul_type") or turn_result.get("foul_team") or "").upper()
            is_defensive_foul = raw_foul_team in {"DEFENSIVE", "DEFENSE", "D_FOUL"}
            next_play_type = str(turn_result.get("next_play_type") or turn_result.get("next_turn") or "").upper()
            rebound_type = str(turn_result.get("rebound_type") or "").upper()
            possession_flips = bool(turn_result.get("possession_flips"))
            free_throws_remaining = int(turn_result.get("free_throws_remaining", 0) or 0)
            # Rule 1: possession change resets shot clock.
            if possession_flips and rt != "TIMEOUT":
                return True
            # Rule 2: non-shooting defensive foul into SIDE_INBOUND resets even without possession flip.
            if (
                rt == "FOUL"
                and is_defensive_foul
                and next_play_type in {"SIDE_INBOUND", "SIP"}
                and not possession_flips
                and free_throws_remaining <= 0
            ):
                return True
            # Rule 3: offensive rebound possession renewal resets — EXCEPT a
            # blocked shot that is offensive-rebounded. A BLOCK already stops the
            # shot clock at the block, and the ensuing OREB (putback OR kickout)
            # continues from the remaining time with NO reset (Shot_Clock_System.md
            # § Shot clock reset instances). MISS/FREE_THROW → OREB still reset.
            if rt == "OREB":
                return True
            if rebound_type == "OREB" and rt in {"MISS", "FREE_THROW"}:
                return True
            return False

        def _current_turn_shot_clock_reset_reason(turn_result):
            return None

        game_remaining_before = int(self.game.game_state.get("time_remaining", 0) or 0)
        shot_remaining_before = int(
            self.game.game_state.get(
                "shot_clock_remaining",
                min(30, game_remaining_before),
            ) or 0
        )

        raw_time_elapsed = int(result.get("time_elapsed", 0) or 0)
        impact_turn = not _is_no_impact_turn(result)
        if impact_turn:
            effective_game_elapsed = max(0, min(raw_time_elapsed, game_remaining_before))
        else:
            effective_game_elapsed = 0

        if not impact_turn:
            shot_elapsed = 0
        elif _is_shot_attempt(result):
            shot_elapsed = _shot_detach_elapsed_seconds(result, effective_game_elapsed)
        else:
            shot_elapsed = effective_game_elapsed
        shot_elapsed = max(0, min(int(shot_elapsed), shot_remaining_before, effective_game_elapsed))

        result["time_elapsed"] = effective_game_elapsed
        self.game.game_state["time_remaining"] -= effective_game_elapsed

        # Clamp to 0
        if self.game.game_state["time_remaining"] < 0:
            self.game.game_state["time_remaining"] = 0

        clock_end = int(self.game.game_state.get("time_remaining", 0))

        # Universal clock authority:
        # - game clock burns only live-ball elapsed for this turn
        # - shot clock burns until detach/stop event, then remains stopped
        # - clock-dead turns preserve the visible shot clock value for this turn
        current_turn_shot_clock_reset_reason = _current_turn_shot_clock_reset_reason(result)

        if impact_turn:
            raw_shot_end = max(0, _cc_sc_start - shot_elapsed)
        elif current_turn_shot_clock_reset_reason:
            raw_shot_end = min(30, clock_end)
        else:
            raw_shot_end = _cc_sc_start

        self.game.game_state["shot_clock_remaining"] = raw_shot_end
        if current_turn_shot_clock_reset_reason:
            result["shot_clock_reset_reason"] = current_turn_shot_clock_reset_reason

        # Shot clock violations are now resolved via the stopper system (phase_resolution) before we get here;
        # we no longer overwrite the result when raw_shot_end == 0.

        # Convert to clock display (e.g., 400 → "6:40")
        minutes = self.game.game_state["time_remaining"] // 60
        seconds = self.game.game_state["time_remaining"] % 60
        self.game.game_state["clock"] = f"{minutes}:{seconds:02d}"

        # ✅ Track MIN (minutes played) for all active players
        # Only track if effective_game_elapsed > 0 (skip timeouts and other 0-time turns)
        if effective_game_elapsed > 0:
            for team in [self.game.home_team, self.game.away_team]:
                for position, player in team.lineup.items():
                    if player:  # Skip None slots (empty lineup positions)
                        player.stats["game"]["MIN"] += effective_game_elapsed

        # Attach contract while game_state still has raw_shot_end (current turn's end).
        # Contract must show derived shot_clock_end so frontend animates start→end during this turn.
        self._attach_clock_contract(
            result,
            clock_start=_cc_clock_start,
            shot_clock_start=_cc_sc_start,
            game_state=self.game.game_state,
            source=f"ucp:{result.get('result_type', 'UNKNOWN')}",
        )
        self._attach_uess_ownership_contract(result)

        # Reset only affects NEXT turn: set shot_clock_remaining=30 so next turn's _cc_sc_start is 30.
        if _should_reset_shot_clock(result):
            self.game.game_state["shot_clock_remaining"] = min(30, clock_end)

        # ✅ REMOVED: Possession flips now handled in game_manager (Fixes 2-4)
        # This old flip caused double-flipping with the new system
        # Fixes 2-4 in game_manager.py handle all possession flips BEFORE creating next turns
        # if result.get("possession_flips"):
        #     self.game.switch_possession()

    def _reconcile_player_points(self, result):
        """Ensure summed player PTS match the official team score.

        This check runs when a possession ends or the quarter expires. If the
        total points recorded across players for a team does not match the
        team's score, a corrective delta is added and the discrepancy is
        logged. This prevents clients from double counting when ``turn.points``
        is present in the payload.
        """
        possession_end = result.get("possession_flips")
        quarter_end = self.game.game_state.get("time_remaining", 0) == 0
        if not (possession_end or quarter_end):
            return

        for team in (self.game.home_team, self.game.away_team):
            team_score = self.game.score[team.name]
            total_pts = sum(
                player.stats["game"].get("PTS", 0) for player in team.get_all_players()
            )
            if total_pts == team_score:
                continue

            diff = team_score - total_pts
            # Log the discrepancy for debugging/auditing purposes
            self.logger.log(f"ptsReconcile:{team.name}:{total_pts}->{team_score}")

            # Choose a player to receive the adjustment. Prefer the players on
            # the floor (``team.lineup``) so the correction reflects what
            # viewers see.  Fall back to the full roster for edge cases where
            # the lineup has not yet been populated.
            players = list(team.lineup.values()) or list(team.get_all_players())
            if not players:
                continue  # nothing we can do
            player = players[0]
            player.stats["game"]["PTS"] = player.stats["game"].get("PTS", 0) + diff

            # Reflect the correction in the deltas payload
            deltas = result.setdefault("deltas", {})
            entry = deltas.setdefault(player.player_id, {"team": team.name, "stats": {}})
            entry["stats"]["PTS"] = entry["stats"].get("PTS", 0) + diff

    def derive_passer_from_steps(self, steps, shooter_pos):
        """
        Derive passer from skeleton steps using the same criteria as Set Plays.
        
        Criteria:
        1. Last player to make a pass to the shooter
        2. Pass and receive happened in the same step
        3. Pass was within 5 steps of the shot
        
        Args:
            steps: List of skeleton steps
            shooter_pos: Position of the shooter (e.g., "PG", "SG")
        
        Returns:
            passer_pos: Position of the passer, or None if no valid passer found
        """
        if not shooter_pos or not steps:
            return None
        
        passer_pos = None
        shot_step_index = len(steps) - 1
        last_pass_step_index = None
        
        # Find the last step where shooter received a pass (within last 5 steps)
        search_start = max(0, shot_step_index - 5)
        for step_index in range(shot_step_index - 1, search_start - 1, -1):
            if step_index < 0:
                break
            
            step = steps[step_index]
            pos_actions = step.get("pos_actions", {})
            
            # Check if shooter has "receive" action in this step
            shooter_action_info = pos_actions.get(shooter_pos)
            if shooter_action_info:
                shooter_action = shooter_action_info.get("action", "").lower()
                
                if shooter_action == "receive":
                    # Shooter received the ball - now find who passed it
                    for pos, action_info in pos_actions.items():
                        if pos == shooter_pos:
                            continue  # Skip shooter themselves
                        
                        action = action_info.get("action", "").lower()
                        if action == "pass":
                            # Found a pass in the same step as shooter receiving
                            last_pass_step_index = step_index
                            passer_pos = pos
                            break
                    
                    # If we found a pass, stop searching (we want the LAST pass to the shooter)
                    if last_pass_step_index is not None:
                        break
        
        # Verify the pass was within 5 steps of the shot
        if last_pass_step_index is not None:
            steps_from_shot = shot_step_index - last_pass_step_index
            if steps_from_shot <= 5:
                return passer_pos  # Valid passer found
            else:
                return None  # Pass too far, no assist
        else:
            return None  # No pass found, no assist

    def assign_roles(self, off_call="INSIDE", def_call="MAN", skeleton=None):
        from BackEnd.utils.shared import get_name_safe
        
        game = self.game
        game_state = game.game_state
        off_team = game.offense_team
        def_team = game.defense_team
        off_lineup = off_team.lineup
        def_lineup = def_team.lineup
        tempo_call = off_team.strategy_calls["tempo_call"]
        
        # Log lineup state to diagnose KeyError
        # ✅ COMMENTED OUT: assign_roles log (cluttering transition debugging)
        # logging.info(f"🏀 assign_roles: offense_team={off_team.name} ({'HOME' if off_team.is_home_team else 'AWAY'}), offense_lineup_keys={list(off_lineup.keys()) if off_lineup else 'EMPTY'}, defense_team={def_team.name} ({'HOME' if def_team.is_home_team else 'AWAY'}), defense_lineup_keys={list(def_lineup.keys()) if def_lineup else 'EMPTY'}")

        # --- Step 1: Pick scene based on playcall
        from BackEnd.playcall_skeletons.outside_skeletons import OUTSIDE_SCENES
        from BackEnd.playcall_skeletons.attack_skeletons import ATTACK_SCENES
        from BackEnd.playcall_skeletons.set_play_skeletons import SET_PLAY_SCENES
        from BackEnd.playcall_skeletons.freelance_skeletons import FREELANCE_SCENES
        from BackEnd.playcall_skeletons.base_skeletons import BASE_SCENES
        
        def derive_roles_from_steps(steps, off_lineup):
            """
            Derive shooter, passer, screener from the skeleton steps.
            Optimized to focus on final steps for turn-level roles (backend logic).
            Still tracks ball ownership per step for animation (frontend).
            """
            from BackEnd.constants import HCO_STRING_SPOTS
            
            shooter_pos = None
            screener_pos = None
            passer_pos = None
            ball_owner_by_step = []
            ball_handler_coords_by_step = []

            # Track ball ownership through all steps (needed for frontend animation)
            current_owner_pos = None
            for step in steps:
                pos_actions = step.get("pos_actions", {})
                step_owner = None
                step_coords = {"x": 50, "y": 25}  # Default center court
                
                # Find who has ball at this step
                for pos, action_info in pos_actions.items():
                    action = (action_info.get("action") or "").lower().strip()
                    
                    if action in ["handle_ball", "receive", "shoot", "pass"]:
                        step_owner = pos
                        # MongoDB skeletons use "location", old skeletons use "spot"
                        location_key = action_info.get("location") or action_info.get("spot", "key")
                        step_coords = HCO_STRING_SPOTS.get(location_key, {"x": 50, "y": 25})
                        
                        if action == "receive":
                            current_owner_pos = pos
                        elif action == "handle_ball":
                            if current_owner_pos is None:
                                current_owner_pos = pos
                        elif action == "shoot":
                            # Shooter has ball at this step; track so stopper/empty-step fallback credits them
                            current_owner_pos = pos
                        
                        break
                
                ball_owner_by_step.append(step_owner or current_owner_pos)
                ball_handler_coords_by_step.append(step_coords)
            
            # === TURN-LEVEL ROLES (for backend shot calculation) ===
            # Extract from final steps only - much simpler and more accurate
            # Debug logging removed - was cluttering logs
            
            if not steps:
                return {
                    "shooter_pos": None,
                    "screener_pos": "PF",
                    "passer_pos": None,
                    "ball_owner_by_step": ball_owner_by_step,
                    "ball_handler_coords_by_step": ball_handler_coords_by_step
                }
            
            # 1. Get SHOOTER from final step
            final_step = steps[-1]
            for pos, action_info in final_step.get("pos_actions", {}).items():
                action = action_info.get("action", "").lower()
                if action == "shoot":
                    shooter_pos = pos
                    break
            
            # Also check events in final step
            if not shooter_pos:
                for event in final_step.get("events", []):
                    if event.get("type") == "shot":
                        shooter_pos = event.get("by")
                        break
            
            # Fallback: use final ball handler
            if not shooter_pos and ball_owner_by_step:
                final_owner = ball_owner_by_step[-1]
                shooter_pos = final_owner if isinstance(final_owner, str) else None
            
            # 2. Get PASSER using the same logic as Motion plays (reuse helper method)
            #    Criteria: a) Last pass to shooter, b) Pass/receive in same step, c) Within 5 steps
            passer_pos = self.derive_passer_from_steps(steps, shooter_pos)
            
            # print(f"🎯 ASSIST DEBUG: Final passer_pos={passer_pos}")
            
            # 3. Get SCREENER - find last screen that helped the shooter
            if shooter_pos:
                for step in reversed(steps):
                    for event in step.get("events", []):
                        if event.get("type") == "screen" and event.get("for") == shooter_pos:
                            screener_pos = event.get("by")
                            break
                    if screener_pos:
                        break
            
            # Fallback screener
            if not screener_pos:
                screener_pos = "PF"
            
            return {
                "shooter_pos": shooter_pos,
                "screener_pos": screener_pos,
                "passer_pos": passer_pos,
                "ball_owner_by_step": ball_owner_by_step,
                "ball_handler_coords_by_step": ball_handler_coords_by_step
            }
        
        # Use provided skeleton from MongoDB if available, otherwise fall back to old system
        if skeleton and "steps" in skeleton:
            # Use the MongoDB skeleton - animate all steps (tempo no longer affects HCO step count)
            steps = skeleton["steps"]
        else:
            # Fallback to old hardcoded skeleton system
            playcall_scenes_map = {
                "Inside": INSIDE_SCENES,
                "Outside": OUTSIDE_SCENES,
                "Attack": ATTACK_SCENES,
                "Set": SET_PLAY_SCENES,
                "Freelance": FREELANCE_SCENES,
                "Base": BASE_SCENES
            }
            
            scenes_list = playcall_scenes_map.get(off_call, INSIDE_SCENES)
            scene = random.choice(scenes_list)
            # print(f"🎬 assign_roles using '{off_call}' skeleton with {len(scene['steps'])} steps")
            
            tempo_to_steps = {"slow": 7, "normal": 5, "fast": 4}
            requested = tempo_to_steps.get(tempo_call.lower(), len(scene["steps"]))

            # Always include the final shot step
            if requested >= len(scene["steps"]):
                steps = scene["steps"]
            else:
                steps = scene["steps"][:requested - 1] + [scene["steps"][-1]]

        # --- Step 2: Initialize outputs
        action_timeline = defaultdict(list)
        touch_counts = defaultdict(int)

        # --- Step 3: Build action timeline + touch counts
        for step_index, step in enumerate(steps):
            pos_actions = step["pos_actions"]
            events = step.get("events", [])

            for pos, action_info in pos_actions.items():
                if pos not in off_lineup:
                    logging.error(f"❌ assign_roles KeyError: position '{pos}' not in offense_lineup. offense_team={off_team.name}, offense_lineup_keys={list(off_lineup.keys()) if off_lineup else 'EMPTY'}")
                    raise KeyError(f"Position '{pos}' not found in offense lineup for {off_team.name}. Available positions: {list(off_lineup.keys()) if off_lineup else 'EMPTY'}")
                player = off_lineup[pos]
                action = action_info["action"]
                # MongoDB skeletons use "location", old skeletons use "spot"
                location_key = action_info.get("location") or action_info.get("spot")
                action_timeline[player].append((step["timestamp"], action, location_key))

                # Count touch if action involves ball
                if action in [ACTIONS["HANDLE"], ACTIONS["PASS"], ACTIONS["RECEIVE"], ACTIONS["SHOOT"]]:
                    touch_counts[player] += 1

            for event in events:
                event_type = event.get("type")
                if event_type == "pass":
                    passer_pos = event.get("from")
                    receiver_pos = event.get("to")
                    if passer_pos in off_lineup and receiver_pos in off_lineup:
                        passer = off_lineup[passer_pos]
                        receiver = off_lineup[receiver_pos]
                        touch_counts[passer] += 1
                        touch_counts[receiver] += 1
                elif event_type == "shot":
                    shooter_pos = event.get("by")
                    # Final-turn helper skeletons can emit {"type":"shot"} without "by".
                    # Fall back to the shooter action in this step.
                    if shooter_pos not in off_lineup:
                        for pos, action_info in pos_actions.items():
                            if action_info.get("action") == ACTIONS["SHOOT"]:
                                shooter_pos = pos
                                break
                    if shooter_pos in off_lineup:
                        shooter = off_lineup[shooter_pos]
                        touch_counts[shooter] += 1
                    else:
                        logging.warning(
                            "🧭 [FINAL TURN TRACE] assign_roles shot event missing valid shooter mapping; event=%s step_index=%s",
                            event,
                            step_index,
                        )

        # --- Step 4: Derive primary roles from steps (optimized - uses final steps only)
        derived_roles = derive_roles_from_steps(steps, off_lineup)
        
        shooter_pos = derived_roles["shooter_pos"]
        screener_pos = derived_roles["screener_pos"]
        passer_pos = derived_roles["passer_pos"]
        
        # Override passer if it conflicts with shooter/screener
        if passer_pos in [shooter_pos, screener_pos]:
            # ✅ COMMENTED OUT: Assist debug logs (cluttering transition debugging)
            # logging.info(f"🎯 ASSIST DEBUG: Passer conflicts with shooter/screener, setting to None (passer_pos={passer_pos}, shooter_pos={shooter_pos}, screener_pos={screener_pos})")
            passer_pos = None

        # Determine shot defender based on defense type
        from BackEnd.utils.defense_utils import is_zone_defense
        second_defender_pos = None  # Initialize second defender position
        if is_zone_defense(game_state.get("defense_playcall", "man")):
            # For zone defense: find defender whose zone contains the shooter
            from BackEnd.utils.shared_defense import _get_23_zone_boundaries, _get_32_zone_boundaries, _get_131_zone_boundaries, _point_in_zone
            from BackEnd.constants import HCO_STRING_SPOTS
            from BackEnd.utils.shared import get_away_player_coords
            
            # Get shooter's spot from final step (where they shoot)
            shooter_spot = "key"  # Default fallback
            if steps and shooter_pos:
                final_step = steps[-1]
                shooter_action = final_step.get("pos_actions", {}).get(shooter_pos, {})
                shooter_spot = shooter_action.get("location") or shooter_action.get("spot") or "key"
            
            # Get shooter's coordinates
            shooter_coords = HCO_STRING_SPOTS.get(shooter_spot, {"x": 50, "y": 25})
            
            # Determine court orientation (away team is on offense if offense team ID matches away team ID)
            game = self.game
            is_away_offense = game.offense_team.team_id == game.away_team.team_id
            if is_away_offense:
                shooter_coords = get_away_player_coords(shooter_coords)
            
            # Determine ball location for zone shift (use ball handler's location from steps)
            ball_spot = "key"  # Default fallback
            ball_handler_pos = None
            for step in steps:
                pos_actions = step.get("pos_actions", {})
                for pos, action_info in pos_actions.items():
                    action = action_info.get("action", "")
                    if action in ["handle_ball", "shoot"]:
                        ball_handler_pos = pos
                        ball_spot = action_info.get("location") or action_info.get("spot") or "key"
                        break
                if ball_handler_pos:
                    break
            
            # Get zone boundaries based on ball location (applies shifts)
            # Check if it's 2-3 or 3-2 zone and use appropriate function
            defense_playcall = game_state.get("defense_playcall", "man")
            zv = defense_zone_shell_variant(defense_playcall) or "23"
            if zv == "32":
                zone_boundaries = _get_32_zone_boundaries(ball_spot, is_away_offense)
            elif zv == "131":
                zone_boundaries = _get_131_zone_boundaries(ball_spot, is_away_offense)
            else:
                zone_boundaries = _get_23_zone_boundaries(ball_spot, is_away_offense)
            
            # Find which defender's zone contains the shooter (check for multiple defenders)
            defender_positions = []
            for def_pos in ["PG", "SG", "SF", "PF", "C"]:
                if def_pos in def_lineup and def_pos in zone_boundaries:
                    zone_coords = zone_boundaries[def_pos]
                    if _point_in_zone(shooter_coords, zone_coords, False):
                        defender_positions.append(def_pos)
            
            # If shooter has two defenders, store both; otherwise use single defender
            if len(defender_positions) >= 2:
                defender_pos = defender_positions[0]  # Primary defender
                second_defender_pos = defender_positions[1]  # Second defender
            elif len(defender_positions) == 1:
                defender_pos = defender_positions[0]
                second_defender_pos = None
            else:
                defender_pos = None
                second_defender_pos = None
            
            # Fallback: if shooter not in any zone, use closest defender
            if not defender_pos:
                # Find defender whose zone center is closest to shooter
                min_dist = float('inf')
                for def_pos in ["PG", "SG", "SF", "PF", "C"]:
                    if def_pos in def_lineup and def_pos in zone_boundaries:
                        zone_coords = zone_boundaries[def_pos]
                        if zone_coords:
                            # Calculate zone center
                            avg_x = sum(c[0] for c in zone_coords) / len(zone_coords)
                            avg_y = sum(c[1] for c in zone_coords) / len(zone_coords)
                            zone_center = {"x": avg_x, "y": avg_y}
                            
                            # Calculate distance
                            dist = ((shooter_coords["x"] - zone_center["x"]) ** 2 + 
                                   (shooter_coords["y"] - zone_center["y"]) ** 2) ** 0.5
                            if dist < min_dist:
                                min_dist = dist
                                defender_pos = def_pos
                
                if not defender_pos:
                    # Final fallback: random defender
                    defender_pos = random.choice(list(def_lineup))
        else:
            # Man-to-man: use matchups for the defending team (user vs computer)
            from BackEnd.utils.man_defense_matchups import get_defender_position_for_man_defense
            defending_team_is_user = getattr(self.game.defense_team, "is_user_team", False)
            defender_pos = get_defender_position_for_man_defense(
                shooter_pos, self.game.game_state, defending_team_is_user=defending_team_is_user
            )

        # --- Step 5: Lookup player objects
        shooter = off_lineup.get(shooter_pos) if shooter_pos else off_lineup["PG"]  # Fallback to PG
        screener = off_lineup.get(screener_pos) if screener_pos else off_lineup["PF"]  # Fallback to PF
        passer = off_lineup.get(passer_pos) if passer_pos else None
        defender = (
            def_lineup.get(defender_pos)
            if defender_pos
            else defender_player_from_random_slot_fallback(def_lineup)
        )
        second_defender = def_lineup.get(second_defender_pos) if second_defender_pos and second_defender_pos in def_lineup else None
        
        # Debug logging for passer assignment
        if passer:
            # ✅ COMMENTED OUT: Assist debug logs (cluttering transition debugging)
            # logging.info(f"🎯 ASSIST DEBUG: passer_pos={passer_pos}, passer={get_name_safe(passer)}, shooter={get_name_safe(shooter)}")
            pass  # Debug logging commented out
        else:
            # logging.info(f"🎯 ASSIST DEBUG: No passer found (passer_pos={passer_pos}, shooter={get_name_safe(shooter)})")
            pass  # Debug logging commented out

        return {
            "shooter": shooter,
            "shooter_pos": shooter_pos,
            "screener": screener,
            "screener_pos": screener_pos,
            "ball_handler": shooter,
            "ball_handler_pos": shooter_pos,
            "passer": passer,
            "passer_pos": passer_pos,
            "defender": defender,
            "defender_pos": defender_pos,
            "second_defender": second_defender,  # Second defender if shooter has two defenders in zone
            "second_defender_pos": second_defender_pos,
            "steps": steps,
            "skeleton": skeleton,  # Include skeleton for variant info
            "action_timeline": action_timeline,
            "touch_counts": touch_counts,
            "ball_owner_by_step": derived_roles["ball_owner_by_step"],
            "ball_handler_coords_by_step": derived_roles["ball_handler_coords_by_step"]
        }
    
    def determine_event_type(self, roles):
        game = self.game
        game_state = game.game_state
        off_team = game.offense_team
        def_team = game.defense_team
        def_lineup = def_team.lineup
        off_lineup = off_team.lineup
        defense_call = game_state["defense_playcall"]
        action_timeline = roles["action_timeline"]
        touch_counts = roles["touch_counts"]
        steps = roles["steps"]

        # Step 1: Decay energy for all players
        for player in off_lineup.values():
            if hasattr(player, "decay_energy") and hasattr(player, "get_fatigue_decay_amount"):
                player.decay_energy(player.get_fatigue_decay_amount())
        for player in def_lineup.values():
            if hasattr(player, "decay_energy") and hasattr(player, "get_fatigue_decay_amount"):
                player.decay_energy(player.get_fatigue_decay_amount())

        # Step 2: Calculate score for each potential turnover candidate
        turnover_risks = []
        for player, touches in touch_counts.items():
            if touches == 0:
                continue

            attr = player.attributes
            bh_score = (
                attr["BH"] * 0.5 +
                attr["AG"] * 0.2 +
                attr["IQ"] * 0.2 +
                attr["CH"] * 0.1
            ) * random.randint(1, 6)

            def_pos = get_player_position(off_lineup, player)
            from BackEnd.utils.defense_utils import is_zone_defense
            defender = def_lineup.get(def_pos) if not is_zone_defense(defense_call) else random.choice(list(def_lineup.values()))
            
            # Handle case where defender is None (no defender assigned)
            if defender is None:
                pressure = 0
            else:
                def_attr = defender.attributes
            pressure = (
                def_attr["OD"] * 0.3 +
                def_attr["AG"] * 0.3 +
                def_attr["IQ"] * 0.2 +
                def_attr["CH"] * 0.2
            ) * random.randint(1, 6)
            if is_zone_defense(defense_call):
                pressure *= 0.9

            score = bh_score - pressure - (touches * 2)
            turnover_risks.append((score, player, defender))

        # Step 3: Calculate foul risks
        foul_risks = []
        for step_index, step in enumerate(steps):
            for pos, action_data in step["pos_actions"].items():
                action = action_data["action"]
                if action not in ["screen", "post_up", "handle_ball"]:
                    continue  # Only consider foul-prone actions

                offender = off_lineup[pos]
                from BackEnd.utils.defense_utils import is_zone_defense
                defender = def_lineup.get(pos) if not is_zone_defense(defense_call) else random.choice([p for p in def_lineup.values() if p is not None])
                o_attr = offender.attributes

                # Handle case where defender is None (no defender assigned)
                if defender is None:
                    d_score = 0
                else:
                    d_attr = defender.attributes
                d_score = (d_attr["IQ"] * 0.3 + d_attr["CH"] * 0.3 + d_attr["AG"] * 0.2 + d_attr["OD"] * 0.2) * random.randint(1, 6)
                o_score = (o_attr["IQ"] * 0.3 + o_attr["CH"] * 0.3 + o_attr["AG"] * 0.2 + o_attr["ST"] * 0.2) * random.randint(1, 6)

                # Slightly bias toward foul when high activity + tempo
                foul_margin = o_score - d_score
                if foul_margin < off_team.team_attributes["fight"] * 0.7:
                    foul_risks.append(("O_FOUL", step_index, offender, defender))
                elif d_score < def_team.team_attributes["fight"] * 1.3:
                    foul_risks.append(("D_FOUL", step_index, offender, defender))

        # Step 4: Decide event
        turnover_risks.sort(key=lambda x: x[0])
        foul_risks.sort(key=lambda x: x[1])  # prioritize earlier fouls

        if turnover_risks and turnover_risks[0][0] < off_team.team_attributes["discipline"]:
            _, player, defender = turnover_risks[0]
            roles["event_step"] = None  # You could optionally track when
            roles["turnover_player"] = player
            roles["turnover_defender"] = defender
            roles["ball_handler"] = player
            return "TURNOVER"

        elif foul_risks:
            foul_type, step_index, offender, defender = foul_risks[0]
            roles["event_step"] = step_index
            roles["foul_player"] = defender if foul_type == "D_FOUL" else offender
            return foul_type

        # No event = clean possession
        return "SHOT"

    def determine_defensive_pressure_type(self):
        """
        Determine the defensive setup ('FCP', 'HCT', or 'HCO') for the next
        possession AND, when it is FCP or HCT, pick which press/trap play runs.

        SS&S choke point: rather than duplicating the play pick at the ~6
        callers that set ``offensive_state`` from this return value, we select it
        ONCE here and sync into ``game_state["fcp_press_play"]`` /
        ``game_state["hct_trap_play"]`` so downstream engines use the same value.
        Mirrors the Fast Break select-once → stash → consume-with-fallback shape.
        """
        pressure_type = self._select_defensive_pressure_type()

        # After a made shot possession flips: the team that just scored
        # (currently offense_team) becomes the defense.
        press_trap_team = self.game.offense_team
        playbook_settings = getattr(press_trap_team, "playbook_settings", None)

        if pressure_type == "FCP":
            from BackEnd.constants.fcp_press_play_types import play_key_for_fcp_press

            self.game.game_state["fcp_press_play"] = play_key_for_fcp_press(
                playbook_settings
            )
        elif pressure_type == "HCT":
            from BackEnd.constants.hct_trap_play_types import play_key_for_hct_trap

            self.game.game_state["hct_trap_play"] = play_key_for_hct_trap(
                playbook_settings
            )

        return pressure_type

    def _select_defensive_pressure_type(self):
        """
        Determine if defensive team should attempt FCP or HCT after a made shot.
        Returns 'FCP', 'HCT', or 'HCO' based on strategy settings and random rolls.
        
        NOTE: After a made shot, possession will flip. The team that just scored
        (currently offense_team) will become the defense team. So we use offense_team's
        settings, not defense_team's settings.
        """
        # After a made shot, possession will flip. The team that just scored
        # (currently offense_team) will become the defense team and apply pressure.
        def_team = self.game.offense_team
        
        # ✅ Situational Logic (Q4/OT): Quick Shot overrides defense FCP/HCT to 0
        if self.game.game_state.get("_situational_quick_shot_fcp_hct_override"):
            return "HCO"
        
        # ✅ Playcall Center: If user's team is applying pressure, honor press_trap_override
        user_team_side = self.game.game_state.get("user_team_side")
        is_user_team = (user_team_side == "home" and def_team.is_home_team) or (user_team_side == "away" and not def_team.is_home_team)
        if is_user_team:
            pt_override = def_team.strategy_calls.get("press_trap_override")
            if pt_override == "press":
                return "FCP"
            if pt_override == "trap":
                return "HCT"
            if pt_override == "none":
                return "HCO"
        
        # Ensure strategy_settings is initialized (but don't overwrite existing settings)
        # Only initialize if it's completely missing (None), not if it's an empty dict
        if not hasattr(def_team, 'strategy_settings') or def_team.strategy_settings is None:
            logging.warning(f"⚠️ [STRATEGY SETTINGS] {def_team.name} missing strategy_settings, initializing with defaults")
            def_team.strategy_settings = def_team._init_strategy_settings()
        elif isinstance(def_team.strategy_settings, dict) and len(def_team.strategy_settings) == 0:
            logging.warning(f"⚠️ [STRATEGY SETTINGS] {def_team.name} has empty strategy_settings dict, initializing with defaults")
            def_team.strategy_settings = def_team._init_strategy_settings()
        
        # Get strategy settings - explicitly check for 0 values
        hct_value = def_team.strategy_settings.get("hc_trap", 0)
        fcp_value = def_team.strategy_settings.get("fc_press", 0)
        
        # 🐛 DEBUG: Log strategy settings being used
        # ✅ COMMENTED OUT: Defensive pressure logs (cluttering transition debugging)
        # logging.warning(f"🛡️ [DEFENSIVE PRESSURE] {def_team.name} - HCT={hct_value}, FCP={fcp_value}")
        # logging.warning(f"   - Full strategy_settings: {def_team.strategy_settings}")
        # logging.warning(f"   - HCT type: {type(hct_value)}, FCP type: {type(fcp_value)}")
        # logging.warning(f"   - HCT == 0: {hct_value == 0}, FCP == 0: {fcp_value == 0}")
        
        # If both are 0, default to HCO (no pressure)
        # CRITICAL: Check for 0 explicitly - if user set both to 0, they want NO pressure
        if hct_value == 0 and fcp_value == 0:
            # logging.warning(f"   - ✅ Both HCT and FCP are 0, returning HCO (no pressure)")
            return "HCO"
        
        # Remove any strategy with value 0 from consideration
        # CRITICAL: Only add strategies if their values are > 0
        # If user set hc_trap=0 and fc_press=0, neither should be added to strategies dict
        strategies = {"HCO": 8}
        hco_removed = False
        
        # Only add HCT if value is > 0 (user wants it enabled)
        if hct_value and hct_value > 0:
            strategies["HCT"] = hct_value
            if hct_value == 4:
                strategies.pop("HCO", None)  # Remove HCO entirely, don't set to 0
                hco_removed = True
            elif not hco_removed:
                strategies["HCO"] = max(0, strategies["HCO"] - hct_value)
        else:
            # logging.warning(f"   - ⚠️ HCT value is {hct_value} (0 or invalid), NOT adding to strategies")
            pass  # HCT logging commented out
        
        # Only add FCP if value is > 0 (user wants it enabled)
        if fcp_value and fcp_value > 0:
            strategies["FCP"] = fcp_value
            if fcp_value == 4:
                strategies.pop("HCO", None)  # Remove HCO entirely, don't set to 0
                hco_removed = True
            elif not hco_removed:
                strategies["HCO"] = max(0, strategies.get("HCO", 8) - fcp_value)
        else:
            logging.warning(f"   - ⚠️ FCP value is {fcp_value} (0 or invalid), NOT adding to strategies")
        
        # Remove any strategies with value 0 from consideration
        strategies = {k: v for k, v in strategies.items() if v > 0}

        # If only one strategy available, use it
        if len(strategies) == 1:
            selected_strategy = list(strategies.keys())[0]
        else:
            # Weighted random selection between all available strategies
            total_value = sum(strategies.values())
            rand = random.randint(1, 100)
            
            cumulative = 0
            for strategy, value in strategies.items():
                chance = (value / total_value) * 100
                cumulative += chance
                if rand <= cumulative:
                    selected_strategy = strategy
                    break
            else:
                # Fallback to last strategy (shouldn't happen, but safety)
                selected_strategy = list(strategies.keys())[-1]
        
        # Return the selected strategy (no execution roll - weighted selection is the final decision)
        # print(f"🛡️ DEFENSIVE PRESSURE RESULT: Selected {selected_strategy} (strategies={strategies})")
        return selected_strategy
    
    def _print_turn_summary(self, result, offensive_state):
        """Print a clean summary of the turn for debugging."""
        print("\n" + "="*80)
        print(f"TURN #{result.get('turn_count', 0)} SUMMARY")
        print("="*80)
        print(f"Offensive State: {offensive_state}")
        print(f"Result Type: {result.get('result_type', 'N/A')}")
        print(f"Text: {result.get('text', 'N/A')}")
        print(f"Possession Flips: {result.get('possession_flips', False)}")
        
        # Animation data summary
        animations = result.get('animations', [])
        skeleton = result.get('skeleton', {})
        
        print(f"\nAnimation Data for turn {result.get('turn_count', 0)} {offensive_state}:")
        print(f"  - Animations array: {len(animations)} players")
        if skeleton and 'steps' in skeleton:
            print(f"  - Skeleton steps: {len(skeleton['steps'])} timestamps")
        else:
            print(f"  - Skeleton: None")
        
        # Roles summary
        roles = result.get('roles', {})
        if roles:
            print(f"\nRoles:")
            for role_name, role_value in roles.items():
                if role_name in ['offense', 'defense']:
                    print(f"  - {role_name}: {len(role_value) if isinstance(role_value, list) else role_value}")
                else:
                    print(f"  - {role_name}: {role_value}")
        
        # Key player info
        print(f"\nKey Players:")
        for key in ['ball_handler', 'shooter', 'passer', 'defender']:
            if key in result and result[key]:
                print(f"  - {key}: {result[key]}")
        
        print("="*80 + "\n")
