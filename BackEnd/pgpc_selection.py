"""
PGPC question selection: weighted sample 6–8 from qualified pool with vanilla (``always``) cap.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, MutableSequence, Optional, Sequence


def _is_vanilla(q: Dict[str, Any]) -> bool:
    trig = q.get("trigger")
    if not isinstance(trig, dict):
        return False
    return trig.get("condition") == "always"


def _question_weight(q: Dict[str, Any]) -> int:
    try:
        w = int(q.get("weight", 1) or 1)
    except (TypeError, ValueError):
        w = 1
    return max(1, w)


def _weighted_sample_without_replacement(
    population: Sequence[Dict[str, Any]],
    k: int,
    rng: random.Random,
) -> List[Dict[str, Any]]:
    """Take ``k`` distinct items; probability ∝ ``question['weight']`` (min 1)."""
    if k <= 0 or not population:
        return []
    items: List[Dict[str, Any]] = list(population)
    weights: List[int] = [_question_weight(q) for q in items]
    out: List[Dict[str, Any]] = []
    take = min(k, len(items))
    for _ in range(take):
        total = sum(weights)
        if total <= 0:
            break
        pick = rng.random() * total
        cum = 0
        chosen_idx = len(items) - 1
        for i, w in enumerate(weights):
            cum += w
            if pick < cum:
                chosen_idx = i
                break
        out.append(items.pop(chosen_idx))
        weights.pop(chosen_idx)
    return out


def select_pgpc_questions_for_session(
    qualified: List[Dict[str, Any]],
    *,
    rng: Optional[random.Random] = None,
) -> List[Dict[str, Any]]:
    """
    Choose up to ``random.randint(6, 8)`` questions, capped by ``len(qualified)``
    (no duplicate rows; if the pool is small, the session is shorter).

    Prefer non-vanilla, **weighted** by ``weight``. At most **3** ``always`` questions
    in the first vanilla fill; if still short of the target, pad with more vanilla
    (weighted) until the pool or target is exhausted.
    """
    if not qualified:
        return []
    r = rng or random.Random()
    target = r.randint(6, 8)
    n_eff = min(target, len(qualified))

    specific = [q for q in qualified if not _is_vanilla(q)]
    vanilla = [q for q in qualified if _is_vanilla(q)]

    want_spec = min(n_eff, len(specific))
    out = _weighted_sample_without_replacement(specific, want_spec, r)
    deficit = n_eff - len(out)
    if deficit <= 0:
        return out

    take_v = min(deficit, 3, len(vanilla))
    if take_v > 0:
        out.extend(_weighted_sample_without_replacement(vanilla, take_v, r))
    deficit = n_eff - len(out)

    remaining_vanilla = [q for q in vanilla if q not in out]
    if deficit > 0 and remaining_vanilla:
        out.extend(
            _weighted_sample_without_replacement(remaining_vanilla, deficit, r)
        )
    return out


def shuffle_answers_for_display(
    question: Dict[str, Any], rng: random.Random
) -> Dict[str, Any]:
    """Return a JSON-safe question dict with answers shuffled, letters A–D only.

    All options from the bank are still shuffled together; only the first four after
    the shuffle are returned (fifth and beyond omitted from this session). Source
    questions may keep five rows for future use.
    """
    letters: MutableSequence[str] = ["A", "B", "C", "D"]
    answers_in = list(question.get("answers") or [])
    rows: List[Dict[str, Any]] = []
    for a in answers_in:
        if isinstance(a, dict):
            rows.append(dict(a))
    rng.shuffle(rows)
    rows = rows[: len(letters)]
    out_answers: List[Dict[str, Any]] = []
    for i, a in enumerate(rows):
        letter = letters[i] if i < len(letters) else str(i)
        a["letter"] = letter
        out_answers.append(
            {
                "letter": letter,
                "text": str(a.get("text", "")),
                "archetype": a.get("archetype"),
            }
        )
    return {
        "id": question.get("id"),
        "text": question.get("text"),
        "player_slot": question.get("player_slot"),
        "category": question.get("category"),
        "answers": out_answers,
    }


__all__ = ["select_pgpc_questions_for_session", "shuffle_answers_for_display"]
