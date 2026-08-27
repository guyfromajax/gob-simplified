"""Backend-owned foul / turnover freeze announcements for Fast Break terminal turns.

UESS-compliant: the backend stamps a **blocking** ``step.end.announcement``
(``style: "primary"``, ``hold_ms: ANNOUNCEMENT_FREEZE_HOLD_MS``) on the terminal Fast Break step, so the
frontend simply renders it and freezes play — no frontend decision-making. This
mirrors the dead-ball-fumble pattern in ``dead_ball_fumble.py``.

The matching legacy frontend turn-end callouts
(``turnPreparation.announceTurnEnd``) are suppressed via flags stamped on the
turn result (``suppress_turn_prep_turnover_announce`` /
``suppress_turn_prep_foul_announce``) so there is no double banner.

Foul flavor language lives in ``foul_announcement_language.py`` (the single
source of truth, role-aware); dead-ball turnover text is owned here. Both are
backend-selected and deterministic per turn.

Scope (see Fast_Break_System.md / Announcement_System.md):
  * ``CHARGE``           — offensive foul on the drive → "CHARGE!"
  * ``FOUL`` (OFFENSE)   — non-shooting offensive foul → weighted offensive text
  * ``FOUL`` (DEFENSE)   — non-shooting defensive foul → weighted defensive text
  * ``DEAD BALL`` / ``TURNOVER`` (non-steal) → "Travel!" / "Double Dribble!" / typed

Shooting fouls (and-1 makes / shooting-foul-on-miss) are NOT handled here — they
live on MAKE/MISS turns with their own announcements. Batted-OOB (offense
retains) is intentionally excluded.
"""

from __future__ import annotations

from BackEnd.utils.sim_random import sim_rng as _random_module
from typing import Any, Dict, List, Optional

from BackEnd.constants.announcement_constants import ANNOUNCEMENT_FREEZE_HOLD_MS
from BackEnd.engine.foul_announcement_language import (
    pick_defensive_foul_text,
    pick_offensive_foul_text,
)

FB_TERMINAL_ANNOUNCE_HOLD_MS = ANNOUNCEMENT_FREEZE_HOLD_MS
_FOUL_WHISTLE_SFX = "whistle-1-lowervol.wav"
_CHARGE_SFX = ["whistle-1-lowervol.wav", "duke-charging.wav"]

_TURNOVER_TYPE_TEXT = {
    "TRAVEL": "Travel!",
    "DOUBLE_DRIBBLE": "Double Dribble!",
    "OUT_OF_BOUNDS": "OUT OF BOUNDS!",
    "BAD_PASS": "BAD PASS!",
    "SHOT_CLOCK": "Shot Clock Violation!",
    "TEN_SECOND": "10-Second Violation!",
    "OVER_BACK": "Over & Back!",
}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()



def _pick_turnover_text(turn_result: Dict[str, Any], rng) -> str:
    turnover_type = turn_result.get("turnover_type")
    if turnover_type:
        return _TURNOVER_TYPE_TEXT.get(str(turnover_type), "TURNOVER!")
    # Dead-ball turnover with no explicit type → Travel! / Double Dribble! (50/50).
    return "Travel!" if rng.random() < 0.5 else "Double Dribble!"


def _player_data(pid: Optional[str]) -> Optional[Dict[str, Any]]:
    if not pid:
        return None
    return {"playerId": str(pid)}


def _is_steal_turnover(turn_result: Dict[str, Any]) -> bool:
    if turn_result.get("stealer_id"):
        return True
    text = _norm(turn_result.get("text"))
    return "steal" in text or "intercept" in text


def build_fb_terminal_announcement(
    turn_result: Dict[str, Any],
    *,
    is_away_offense: bool,
    rng=_random_module,
) -> Optional[Dict[str, Any]]:
    """Build the blocking terminal announcement for an FB foul/charge/turnover
    turn, or ``None`` when the turn is out of scope.

    ``team`` follows the frontend convention: offensive fouls / charges color to
    the defending side (defense "benefits"); defensive fouls and turnovers color
    to the offense side.
    """
    result_type = (turn_result.get("result_type") or "").upper()
    offense_side = "away" if is_away_offense else "home"
    defense_side = "home" if is_away_offense else "away"

    # Batted-OOB is a dead ball where the offense RETAINS — not a turnover.
    if turn_result.get("bat_oob") or turn_result.get("rim_runner_bat_oob"):
        return None

    if result_type == "CHARGE":
        fouler = turn_result.get("foul_player_id") or turn_result.get("shooter_id")
        return _announcement("CHARGE!", defense_side, fouler, _CHARGE_SFX)

    if result_type == "FOUL":
        foul_team = (turn_result.get("foul_team") or "").upper()
        fouler = turn_result.get("foul_player_id")
        if foul_team == "OFFENSE":
            text = pick_offensive_foul_text(turn_result, rng)
            team = defense_side
        else:
            text = pick_defensive_foul_text(
                turn_result,
                is_on_ball=bool(turn_result.get("foul_is_on_ball", True)),
                rng=rng,
            )
            team = offense_side
        return _announcement(text, team, fouler, _FOUL_WHISTLE_SFX)

    if result_type in ("DEAD BALL", "TURNOVER"):
        if _is_steal_turnover(turn_result):
            return None
        text = _pick_turnover_text(turn_result, rng)
        victim = (
            turn_result.get("victim_id")
            or turn_result.get("shooter_id")
            or _safe_id(turn_result.get("ball_handler"))
        )
        sfx = "whistle-3.mp3" if text == "Shot Clock Violation!" else _FOUL_WHISTLE_SFX
        return _announcement(text, offense_side, victim, sfx)

    return None


def _announcement(text: str, team: str, player_id: Optional[str], sfx) -> Dict[str, Any]:
    return {
        "text": text,
        "team": team,
        "style": "primary",
        "hold_ms": FB_TERMINAL_ANNOUNCE_HOLD_MS,
        "player_data": _player_data(player_id),
        "meta": {"sfx": sfx},
    }


def stamp_fb_terminal_freeze(
    turn_result: Dict[str, Any],
    steps: Optional[List[Dict[str, Any]]],
    *,
    is_away_offense: bool,
    rng=_random_module,
) -> bool:
    """Stamp a blocking foul/turnover announcement on the terminal FB step and
    suppress the duplicate legacy frontend callout. Returns ``True`` if stamped.

    Idempotent and non-clobbering: no-op when there are no steps, the turn is
    out of scope, or the terminal step already carries an announcement.
    """
    if not steps:
        return False
    ann = build_fb_terminal_announcement(
        turn_result, is_away_offense=is_away_offense, rng=rng
    )
    if ann is None:
        return False
    last = steps[-1]
    end = last.get("end") if isinstance(last, dict) else None
    if not isinstance(end, dict):
        return False
    if end.get("announcement"):
        return False
    end["announcement"] = ann

    result_type = (turn_result.get("result_type") or "").upper()
    if result_type in ("DEAD BALL", "TURNOVER"):
        turn_result["suppress_turn_prep_turnover_announce"] = True
    else:
        turn_result["suppress_turn_prep_foul_announce"] = True
    return True


def _safe_id(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    pid = getattr(obj, "player_id", None)
    return str(pid) if pid else None
