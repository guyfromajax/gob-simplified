"""Short copy lines for loading UX between user training and distant CPU phases."""

from __future__ import annotations

from typing import Any, List, Mapping

from BackEnd.models.training_notes import NSS


def build_training_loading_highlights(training_report: Mapping[str, Any] | None) -> List[str]:
    """Derive a small list of human-readable lines from a stored or in-memory training report."""
    if not training_report:
        return []
    out: List[str] = []

    notes = training_report.get("training_notes") or []
    for block in notes:
        if isinstance(block, dict):
            title = (block.get("title") or "").strip()
            body = (block.get("body") or "").strip()
            if not title:
                continue
            if not body or body in ("None", NSS):
                continue
            out.append(f"{title}: {body}")
        elif isinstance(block, str):
            s = block.strip()
            if s:
                out.append(s)

    player_logs = training_report.get("player_logs") or training_report.get("player_changes") or {}
    if isinstance(player_logs, dict):
        for player_name in sorted(player_logs.keys(), key=lambda k: str(k).lower()):
            changes = player_logs.get(player_name)
            if not isinstance(changes, dict):
                continue
            sh_delta = changes.get("SH")
            if sh_delta is None:
                continue
            try:
                d = int(sh_delta)
            except (TypeError, ValueError):
                continue
            if d == 0:
                continue
            name = str(player_name).strip()
            if not name:
                continue
            if d > 0:
                out.append(f"{name} is shooting well in practice")
            else:
                out.append(f"{name} is shooting poorly in practice")

    cf = training_report.get("coaching_focus") or {}
    if isinstance(cf, dict):
        leaf = (cf.get("leaf_display_name") or "").strip()
        if leaf:
            out.append(f"Coaching focus: {leaf}")

    pec = training_report.get("plays_effectiveness_changes") or {}
    if isinstance(pec, dict) and pec:
        ranked = sorted(
            ((str(k), int(v)) for k, v in pec.items() if isinstance(v, (int, float)) and int(v) != 0),
            key=lambda t: -abs(t[1]),
        )
        for play_key, delta in ranked[:2]:
            sign = "+" if delta > 0 else ""
            out.append(f"Play effectiveness {play_key}: {sign}{delta}")

    dec = training_report.get("defenses_effectiveness_changes") or {}
    if isinstance(dec, dict) and dec:
        ranked = sorted(
            ((str(k), int(v)) for k, v in dec.items() if isinstance(v, (int, float)) and int(v) != 0),
            key=lambda t: -abs(t[1]),
        )
        for name, delta in ranked[:2]:
            sign = "+" if delta > 0 else ""
            out.append(f"Defense {name}: {sign}{delta}")

    # De-dupe while preserving order
    seen: set[str] = set()
    unique: List[str] = []
    for line in out:
        if line in seen:
            continue
        seen.add(line)
        unique.append(line)
    return unique[:24]
