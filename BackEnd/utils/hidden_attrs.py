"""Hidden player attributes: used by the engine, never shown or sent to the browser.

CH is hidden. The engine, training and the database keep using it; no screen may
display it and no client payload may carry it. Routers whose payloads reach the
browser use ``HiddenAttrsJSONResponse`` as their default response class, so a new
route is covered without anyone remembering to strip it.

The court's own game routes (``/api/init-game``, ``/api/simulate-turn``,
``/roster/{team}`` ...) are not covered: the Phaser client still reads CH to pick
the pass-receive sound. See UX_System.md, "CH is hidden".
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from fastapi.responses import JSONResponse

HIDDEN_ATTRS = ("CH",)
# The attribute, its anchor, and the frozen copy the growth profile keeps (``development.ch_seed``).
HIDDEN_ATTR_KEYS = frozenset(
    {key for attr in HIDDEN_ATTRS for key in (attr, f"anchor_{attr}")} | {"ch_seed"}
)

# A row that names its attribute in one of these fields ({"attribute": "CH", "from": 4, "to": 5}).
_ROW_ATTR_FIELDS = ("attribute", "attr", "attr_key", "attribute_key")
# A list of bare strings is an attribute-key list when it holds several of these.
_KNOWN_ATTR_CODES = frozenset({"SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ"})


# --- copy written before the attribute was hidden --------------------------------------------
# A story stored in a save can still name it ("His strongest gains were in Shooting and
# Clutch."). The stored story is never rewritten; the name is taken out as it is served.
HIDDEN_ATTR_LABELS = ("Clutch",)
# The attribute names generated copy uses (franchise_routes.NEWS_ATTRIBUTE_FULL_NAMES).
VISIBLE_ATTR_LABELS = (
    "Scoring", "Shooting", "Inside Defense", "Outside Defense", "Passing", "Ball Handling",
    "Rebounding", "Strength", "Agility", "Free Throws", "Endurance", "Basketball IQ",
)
_LABEL = "|".join(re.escape(label) for label in sorted(HIDDEN_ATTR_LABELS + VISIBLE_ATTR_LABELS, key=len, reverse=True))
_SEPARATOR = r"(?:, and |, | and )"
# Two or more attribute names in a row: "Shooting and Clutch", "Scoring, Clutch, and Passing".
_ATTR_LIST = re.compile(rf"(?<![A-Za-z])(?:{_LABEL})(?:{_SEPARATOR}(?:{_LABEL}))+(?![A-Za-z])")
# The one clause that can name it alone: drop the whole sentence when nothing else is left.
_GAINS_ONLY_HIDDEN = re.compile(
    r"\s*[^.!?\s][^.!?]*\bstrongest gains were in (?:%s)\." % "|".join(re.escape(label) for label in HIDDEN_ATTR_LABELS)
)


def _join_with_and(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return items[0] + " and " + items[1]
    return ", ".join(items[:-1]) + ", and " + items[-1]


def scrub_hidden_attr_copy(text: str) -> str:
    """``text`` without the hidden attribute's name where it is listed as an attribute.

    Only attribute lists are touched: a list of attribute names loses the hidden one and
    is re-joined, and a "strongest gains were in <hidden>." sentence is dropped. The
    ordinary word (late-game "clutch" in callouts and press-conference questions) is
    not an attribute list and is left alone.
    """
    if not any(label in text for label in HIDDEN_ATTR_LABELS):
        return text

    def _relist(match: re.Match) -> str:
        items = re.split(_SEPARATOR, match.group(0))
        kept = [item for item in items if item not in HIDDEN_ATTR_LABELS]
        return _join_with_and(kept) if len(kept) != len(items) else match.group(0)

    out = _GAINS_ONLY_HIDDEN.sub("", _ATTR_LIST.sub(_relist, text))
    # A dropped first sentence leaves the next one's leading space behind.
    return out if text[:1].isspace() else out.lstrip()


def is_hidden_attr(key: Any) -> bool:
    return isinstance(key, str) and key in HIDDEN_ATTR_KEYS


def visible_attr_keys(keys: Iterable[str]) -> list[str]:
    """``keys`` without the hidden ones, order kept."""
    return [key for key in keys if not is_hidden_attr(key)]


def _names_hidden_attr(row: dict) -> bool:
    return any(is_hidden_attr(row.get(field)) for field in _ROW_ATTR_FIELDS)


def _is_attr_key_list(items: list) -> bool:
    codes = [item for item in items if isinstance(item, str)]
    return len(codes) == len(items) and len(_KNOWN_ATTR_CODES.intersection(codes)) >= 3


def strip_hidden_attrs(value: Any) -> Any:
    """A copy of a JSON-ready value with every hidden attribute removed, copy included.

    Never mutates ``value``: route payloads share objects with documents the engine
    reads and saves, and those must keep the attribute.
    """
    if isinstance(value, dict):
        return {
            key: strip_hidden_attrs(item)
            for key, item in value.items()
            if not is_hidden_attr(key)
        }
    if isinstance(value, (list, tuple)):
        items = list(value)
        key_list = _is_attr_key_list(items)
        out = []
        for item in items:
            if isinstance(item, dict) and _names_hidden_attr(item):
                continue
            if key_list and is_hidden_attr(item):
                continue
            out.append(strip_hidden_attrs(item))
        return out
    if isinstance(value, str):
        return scrub_hidden_attr_copy(value)
    return value


class HiddenAttrsJSONResponse(JSONResponse):
    """JSON response that never carries a hidden attribute."""

    def render(self, content: Any) -> bytes:
        return super().render(strip_hidden_attrs(content))
