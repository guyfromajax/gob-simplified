"""
Step-by-step FCP coordinate trace for dynamic press playtesting.

Logs each FCP animation/engine step with per-player start → destination → end
coords. Toggle ``LOG_FCP_STEP_COORDS`` off when done debugging.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

POSITIONS = ("PG", "SG", "SF", "PF", "C")

# Set False to silence FCP step traces in server logs / stdout.
LOG_FCP_STEP_COORDS = True


def _fmt_xy(c: Optional[Dict[str, Any]]) -> str:
    if not c:
        return "(  -,  -)"
    return f"({int(round(c['x'])):>3},{int(round(c['y'])):>3})"


def _player_id(lineup: Dict[str, Any], pos: str) -> Optional[str]:
    player = lineup.get(pos)
    if player is None:
        return None
    pid = getattr(player, "player_id", None)
    return str(pid) if pid is not None else None


class FcpStepTracer:
    """Engine-side trace: one log block per loop segment appended."""

    def __init__(
        self,
        off_lineup: Dict[str, Any],
        def_lineup: Dict[str, Any],
        bh_pos: str,
    ) -> None:
        self.step = 0
        self.bh_pos = bh_pos.upper()
        self._labels: Dict[str, str] = {}
        for pos in POSITIONS:
            pid = _player_id(off_lineup, pos)
            if pid:
                self._labels[pid] = f"OFF {pos}"
        for pos in POSITIONS:
            pid = _player_id(def_lineup, pos)
            if pid:
                self._labels[pid] = f"DEF {pos}"

    @staticmethod
    def snap_coords(
        off_coords: Dict[str, Dict[str, int]],
        def_coords: Dict[str, Dict[str, int]],
    ) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Dict[str, int]]]:
        return (
            {p: dict(off_coords[p]) for p in POSITIONS},
            {p: dict(def_coords[p]) for p in POSITIONS},
        )

    def log_turn_start(
        self,
        off_coords: Dict[str, Dict[str, int]],
        def_coords: Dict[str, Dict[str, int]],
        *,
        off_agg: str = "",
        def_agg: str = "",
    ) -> None:
        if not LOG_FCP_STEP_COORDS:
            return
        lines = ["[FCP STEP TRACE] Turn start (BIP-end seed coords)"]
        if off_agg or def_agg:
            lines.append(f"  aggression: offense={off_agg or '?'} defense={def_agg or '?'}")
        lines.extend(self._pos_lines(off_coords, def_coords, None, None))
        _emit(lines)

    def log_engine_step(
        self,
        label: str,
        reason: str,
        snap_off: Dict[str, Dict[str, int]],
        snap_def: Dict[str, Dict[str, int]],
        end_off: Dict[str, Dict[str, int]],
        end_def: Dict[str, Dict[str, int]],
        *,
        dest_off: Optional[Dict[str, Dict[str, int]]] = None,
        dest_def: Optional[Dict[str, Dict[str, int]]] = None,
        gate: Optional[Tuple[str, str]] = None,
        seconds: Optional[float] = None,
        note: str = "",
    ) -> None:
        if not LOG_FCP_STEP_COORDS:
            return
        self.step += 1
        header = f"Step {self.step} FCP: {label}  [{reason}]"
        if gate:
            header += f"  gate={gate[0]}:{gate[1]}"
        if seconds is not None:
            header += f"  T={seconds:.2f}s"
        if note:
            header += f"  ({note})"
        lines = [f"[FCP STEP TRACE] {header}"]
        lines.extend(
            self._pos_lines(snap_off, snap_def, end_off, end_def, dest_off, dest_def)
        )
        _emit(lines)

    def _pos_lines(
        self,
        start_off: Dict[str, Dict[str, int]],
        start_def: Dict[str, Dict[str, int]],
        end_off: Optional[Dict[str, Dict[str, int]]],
        end_def: Optional[Dict[str, Dict[str, int]]],
        dest_off: Optional[Dict[str, Dict[str, int]]] = None,
        dest_def: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> List[str]:
        lines: List[str] = []
        for side, prefix, start, end, dest in (
            ("off", "OFF", start_off, end_off, dest_off),
            ("def", "DEF", start_def, end_def, dest_def),
        ):
            for pos in POSITIONS:
                s = start.get(pos) if start else None
                e = end.get(pos) if end else s
                d = (dest or end or start or {}).get(pos) if dest or end or start else None
                mark = ""
                if pos == self.bh_pos and side == "off":
                    mark = " *BH*"
                elif pos == "PG" and side == "def":
                    mark = " *on-ball*"
                if end is None:
                    lines.append(f"      {prefix} {pos}{mark}: {_fmt_xy(s)}")
                elif dest is not None:
                    d = dest.get(pos)
                    lines.append(
                        f"      {prefix} {pos}{mark}: start {_fmt_xy(s)}"
                        f"  ->  dest {_fmt_xy(d)}"
                        f"  ->  end {_fmt_xy(e)}"
                    )
                else:
                    lines.append(
                        f"      {prefix} {pos}{mark}: start {_fmt_xy(s)}"
                        f"  ->  end {_fmt_xy(e)}"
                    )
        return lines


def log_emitter_step_trace(
    steps: List[Any],
    loop_segments: List[Dict[str, Any]],
    prior_final_coords: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    *,
    skip_walk_up: bool,
) -> None:
    """Emitter-side trace: rendered start → destination → end per schema step."""
    if not LOG_FCP_STEP_COORDS:
        return
    pid_label: Dict[str, str] = {}
    for pos in POSITIONS:
        pid = _player_id(off_lineup, pos)
        if pid:
            pid_label[pid] = f"OFF {pos}"
    for pos in POSITIONS:
        pid = _player_id(def_lineup, pos)
        if pid:
            pid_label[pid] = f"DEF {pos}"

    lines: List[str] = [
        f"[FCP EMITTER TRACE] {len(steps)} schema steps"
        f" ({'no walk-up' if skip_walk_up else 'with walk-up'})",
    ]
    prev_end: Dict[str, Any] = dict(prior_final_coords or {})
    n_loop = len(loop_segments)
    for idx, step in enumerate(steps):
        start = (step.get("start") or {}).get("coords") or {}
        end = (step.get("end") or {}).get("coords") or {}
        destinations = (step.get("start") or {}).get("destination") or {}
        if skip_walk_up:
            step_num = idx + 1
            if idx < n_loop:
                seg = loop_segments[idx]
                label = seg.get("step_label") or seg.get("reason") or "loop step"
            else:
                label = "shot / post-shot sub-step"
        else:
            step_num = idx + 1
            if idx == 0:
                label = "walk-up (skipped for FCP)" if skip_walk_up else "walk-up"
            elif idx <= n_loop:
                seg = loop_segments[idx - 1]
                label = seg.get("step_label") or seg.get("reason") or "loop step"
            else:
                label = "shot / post-shot sub-step"

        lines.append(f"  Step {step_num} FCP (emitter): {label}")
        for pid, lab in sorted(pid_label.items(), key=lambda x: x[1]):
            dest = destinations.get(pid) or end.get(pid)
            lines.append(
                f"      {lab}: start {_fmt_xy(prev_end.get(pid))}"
                f"  ->  dest {_fmt_xy(dest)}"
                f"  ->  end {_fmt_xy(end.get(pid))}"
            )
        prev_end = end
    _emit(lines)


def log_fcp_emitter_bail(reason: str, **details: Any) -> None:
    if not LOG_FCP_STEP_COORDS:
        return
    parts = [f"[FCP EMITTER TRACE] BAIL: {reason}"]
    for key, val in details.items():
        parts.append(f"  {key}={val!r}")
    _emit(parts)


def _emit(lines: List[str]) -> None:
    print("\n".join(lines), flush=True)
