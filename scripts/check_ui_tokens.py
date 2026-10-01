#!/usr/bin/env python3
"""Report raw colour and type literals outside css/gob-tokens.css.

Run from the repo root. Standard library only. No network.

    python scripts/check_ui_tokens.py
    python scripts/check_ui_tokens.py --strict
    python scripts/check_ui_tokens.py --strict --no-write

The default run always exits 0 and writes reports/ui-token-audit-2026-09-29.md.
``--no-write`` prints the summary and skips the report file (CI).
``--strict`` exits 1 when a *new-design* file has a colour-law hit that is
not on the allow-list. Legacy hits are reported and do not fail the gate.
Always exits 1 when ``franchise-command-center.css`` grows past the frozen
line / style-rule ceilings.

New surface: shell HTML (``gob-shell`` / ``gob-focus``, or a page listed in
``gobShell.js`` PAGES), ``css/gob-*.css`` except the advanced-topic
diagram sheet ``css/gob-advanced.css``, Chapter 7 chrome (``css/office-home.css``, ``css/home-base.css``,
``css/milestone-modal.css``, ``css/season-peak.css``,
``css/trophy-case.css``), recruiting hub CSS (``recruiting-spine.css``,
``recruiting-dock.css``, ``recruiting-signing.css``,
``recruiting-results-hub.css``), the migrated focus/module CSS in
``NEW_DESIGN_CSS`` (Prep training/report, Playbooks ``playbooks.css`` /
``css/playbook-tiles.css``, ``set-lineup.css``, ``box-score.css``,
``cut-players.css``, Game Plan ``game-plan.css``, Scouting
``scouting-report.css`` / ``css/prep-v2-scouting.css``, Team Builder
``team-builder.css``, tutorial / FTE modals and screens: Sammy, username,
walk-on, attribute tour, lineup modal, persona intro, pick opponent, tip-off,
``css/fte.css``, auth pages ``auth.css``, community pages ``css/community.css``, program select
``franchise-select-team.css``, play-flow ``training-playbooks.css`` /
``playbook-report.css`` / ``player-detail.css``), ``js/shared/gob*.js``, and
``js/shared/views/**``. Everything else under the scan root is legacy.
``css/gob-tokens.css`` is the token source and is not scanned.

Allow-list (green / orange / reward-gold):

* Green — Advance (``advance``, ``play-now``, ``gob-btn--gate``), positive
  data (``delta-up``, ``tier-green``, ``t-green``, ``is-up``, ``is-pos``,
  ``tsr-up``, ``risk-low``, ``rm-tile--keep``, ``data-band="high"``,
  chemistry ``.chem`` / ``.is-green``, board-gain bars, RT/attribute ramps
  ``.att-col`` / ``.att-bar`` / ``.gob-chg``), or a nearby
  ``/* colour-law: positive-data */`` comment.
* Orange — committed or saved (``save``, ``saved``, ``committed``,
  ``gob-btn--action``, ``toggle-btn.active``, ``.gated``, ``.td-gate``,
  ``.is-on``), attribute-ramp mid stops on ``.att-col`` / ``.att-bar``,
  or a nearby ``/* colour-law: committed */`` / ``/* colour-law: saved */``.
* Reward-gold — title medallions (``.med.gold``), season-peak glow / rule /
  confetti (``.pk``, ``.cf``), milestone accents (``.mm.is-gold``,
  ``.mm .med``), the exceptional-gain marker (``.xg``, ``.xg-key``,
  ``xgSweep``), Trophy Case words (``.gold-t``, ``.pk-f`` / ``.rv-f``
  emphasis), or a nearby ``/* colour-law: reward */``.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO / "FrontEnd" / "static"
DEFAULT_REPORT = REPO / "reports" / "ui-token-audit-2026-09-29.md"
TOKENS_REL = Path("css") / "gob-tokens.css"

# Brand anchors used when a tokens file does not define the name.
FALLBACK_HEX = {
    "--green": "#34EC27",
    "--orange": "#F79420",
    "--navy": "#27408E",
    "--navy-hi": "#4A6ED2",
    "--blue": "#4A90D9",
    "--tier-blue": "#6BA4E0",
    "--red": "#ff6d6d",
    "--yellow": "#FFD700",
    "--tier-metal": "#C79A5B",
    "--tier-metal-hi": "#EAC488",
    "--white": "#ffffff",
    "--black": "#000000",
}

FAMILY_ANCHORS = {
    "green": ("--green",),
    "orange": ("--orange",),
    "navy": ("--navy", "--navy-hi"),
    "blue": ("--blue", "--tier-blue"),
    "red": ("--red",),
    "gold": ("--yellow", "--tier-metal", "--tier-metal-hi"),
}
FAMILY_REFERENCE = {
    "green": "--green",
    "orange": "--orange",
    "navy": "--navy",
    "blue": "--blue",
    "red": "--red",
    "gold": "--yellow",
}
FAMILY_ORDER = ("green", "orange", "navy", "blue", "red", "white/grey", "gold", "other")
CHROMA_GREY = 14.0
FAMILY_MAX_DE = 42.0

# Custom-property definitions of the canonical tokens are copies, not uses.
DEFINITION_NAMES = frozenset(FAMILY_REFERENCE.values()) | frozenset(
    {"--delta-up", "--tier-green", "--navy-hi", "--tier-blue", "--tier-metal", "--tier-metal-hi",
     "--white", "--black"}
)

TYPE_ORDER = ("font-size", "font-weight", "letter-spacing", "font-family")
LAW_ORDER = ("green", "orange", "reward-gold")

GENERIC_FAMILIES = frozenset({
    "serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui",
    "ui-sans-serif", "ui-serif", "ui-monospace", "ui-rounded", "emoji", "math",
    "fangsong", "inherit", "unset", "initial", "revert", "revert-layer",
})

# CSS Color Level 4 named colours that show up as paints. Not an exhaustive
# keyword list of every non-colour ident; unknown words are ignored.
NAMED_COLORS = {
    "black": (0, 0, 0), "silver": (192, 192, 192), "gray": (128, 128, 128),
    "grey": (128, 128, 128), "white": (255, 255, 255), "maroon": (128, 0, 0),
    "red": (255, 0, 0), "purple": (128, 0, 128), "fuchsia": (255, 0, 255),
    "magenta": (255, 0, 255), "green": (0, 128, 0), "lime": (0, 255, 0),
    "olive": (128, 128, 0), "yellow": (255, 255, 0), "navy": (0, 0, 128),
    "blue": (0, 0, 255), "teal": (0, 128, 128), "aqua": (0, 255, 255),
    "cyan": (0, 255, 255), "orange": (255, 165, 0), "gold": (255, 215, 0),
    "aliceblue": (240, 248, 255), "antiquewhite": (250, 235, 215),
    "aquamarine": (127, 255, 212), "azure": (240, 255, 255), "beige": (245, 245, 220),
    "bisque": (255, 228, 196), "blanchedalmond": (255, 235, 205),
    "blueviolet": (138, 43, 226), "brown": (165, 42, 42), "burlywood": (222, 184, 135),
    "cadetblue": (95, 158, 160), "chartreuse": (127, 255, 0), "chocolate": (210, 105, 30),
    "coral": (255, 127, 80), "cornflowerblue": (100, 149, 237), "cornsilk": (255, 248, 220),
    "crimson": (220, 20, 60), "darkblue": (0, 0, 139), "darkcyan": (0, 139, 139),
    "darkgoldenrod": (184, 134, 11), "darkgray": (169, 169, 169), "darkgrey": (169, 169, 169),
    "darkgreen": (0, 100, 0), "darkkhaki": (189, 183, 107), "darkmagenta": (139, 0, 139),
    "darkolivegreen": (85, 107, 47), "darkorange": (255, 140, 0), "darkorchid": (153, 50, 204),
    "darkred": (139, 0, 0), "darksalmon": (233, 150, 122), "darkseagreen": (143, 188, 143),
    "darkslateblue": (72, 61, 139), "darkslategray": (47, 79, 79), "darkslategrey": (47, 79, 79),
    "darkturquoise": (0, 206, 209), "darkviolet": (148, 0, 211), "deeppink": (255, 20, 147),
    "deepskyblue": (0, 191, 255), "dimgray": (105, 105, 105), "dimgrey": (105, 105, 105),
    "dodgerblue": (30, 144, 255), "firebrick": (178, 34, 34), "floralwhite": (255, 250, 240),
    "forestgreen": (34, 139, 34), "gainsboro": (220, 220, 220), "ghostwhite": (248, 248, 255),
    "goldenrod": (218, 165, 32), "greenyellow": (173, 255, 47), "honeydew": (240, 255, 240),
    "hotpink": (255, 105, 180), "indianred": (205, 92, 92), "indigo": (75, 0, 130),
    "ivory": (255, 255, 240), "khaki": (240, 230, 140), "lavender": (230, 230, 250),
    "lavenderblush": (255, 240, 245), "lawngreen": (124, 252, 0), "lemonchiffon": (255, 250, 205),
    "lightblue": (173, 216, 230), "lightcoral": (240, 128, 128), "lightcyan": (224, 255, 255),
    "lightgoldenrodyellow": (250, 250, 210), "lightgray": (211, 211, 211),
    "lightgrey": (211, 211, 211), "lightgreen": (144, 238, 144), "lightpink": (255, 182, 193),
    "lightsalmon": (255, 160, 122), "lightseagreen": (32, 178, 170),
    "lightskyblue": (135, 206, 250), "lightslategray": (119, 136, 153),
    "lightslategrey": (119, 136, 153), "lightsteelblue": (176, 196, 222),
    "lightyellow": (255, 255, 224), "limegreen": (50, 205, 50), "linen": (250, 240, 230),
    "mediumaquamarine": (102, 205, 170), "mediumblue": (0, 0, 205),
    "mediumorchid": (186, 85, 211), "mediumpurple": (147, 112, 219),
    "mediumseagreen": (60, 179, 113), "mediumslateblue": (123, 104, 238),
    "mediumspringgreen": (0, 250, 154), "mediumturquoise": (72, 209, 204),
    "mediumvioletred": (199, 21, 133), "midnightblue": (25, 25, 112),
    "mintcream": (245, 255, 250), "mistyrose": (255, 228, 225), "moccasin": (255, 228, 181),
    "navajowhite": (255, 222, 173), "oldlace": (253, 245, 230), "olivedrab": (107, 142, 35),
    "orangered": (255, 69, 0), "orchid": (218, 112, 214), "palegoldenrod": (238, 232, 170),
    "palegreen": (152, 251, 152), "paleturquoise": (175, 238, 238),
    "palevioletred": (219, 112, 147), "papayawhip": (255, 239, 213), "peachpuff": (255, 218, 185),
    "peru": (205, 133, 63), "pink": (255, 192, 203), "plum": (221, 160, 221),
    "powderblue": (176, 224, 230), "rebeccapurple": (102, 51, 153), "rosybrown": (188, 143, 143),
    "royalblue": (65, 105, 225), "saddlebrown": (139, 69, 19), "salmon": (250, 128, 114),
    "sandybrown": (244, 164, 96), "seagreen": (46, 139, 87), "seashell": (255, 245, 238),
    "sienna": (160, 82, 45), "skyblue": (135, 206, 235), "slateblue": (106, 90, 205),
    "slategray": (112, 128, 144), "slategrey": (112, 128, 144), "snow": (255, 250, 250),
    "springgreen": (0, 255, 127), "steelblue": (70, 130, 180), "tan": (210, 180, 140),
    "thistle": (216, 191, 216), "tomato": (255, 99, 71), "turquoise": (64, 224, 208),
    "violet": (238, 130, 238), "wheat": (245, 222, 179), "whitesmoke": (245, 245, 245),
    "yellowgreen": (154, 205, 50),
}

HEX_RE = re.compile(
    r"(?<![\w-])#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9a-fA-F-])"
)
RGB_RE = re.compile(
    r"rgba?\(\s*([0-9.]+%?)\s*[, ]\s*([0-9.]+%?)\s*[, ]\s*([0-9.]+%?)\s*(?:[,/]\s*([0-9.]+%?))?\s*\)",
    re.IGNORECASE,
)
HSL_RE = re.compile(
    r"hsla?\(\s*(-?[0-9.]+)\s*[, ]\s*([0-9.]+%)\s*[, ]\s*([0-9.]+%)\s*(?:[,/]\s*([0-9.]+%?))?\s*\)",
    re.IGNORECASE,
)
DECL_RE = re.compile(r"(--)?([A-Za-z_][\w-]*)\s*:\s*([^;{}]+)")
NAMED_RE = re.compile(r"(?<![\w#-])([A-Za-z]{3,})(?![\w-])")
VAR_CALL_RE = re.compile(r"var\(")
STYLE_SIGNAL_RE = re.compile(
    r"style\s*=|\.style\.|cssText|setProperty\s*\(|"
    r"font-size\s*:|font-weight\s*:|letter-spacing\s*:|font-family\s*:|"
    r"(?:^|[^.\w])font\s*:|(?:^|[^.\w])color\s*:|background(?:-color)?\s*:",
    re.IGNORECASE,
)
JS_STYLE_ASSIGN_RE = re.compile(
    r"\.style\.([A-Za-z]+)\s*=\s*(['\"])(.*?)\2"
)
JS_SET_PROP_RE = re.compile(
    r"setProperty\(\s*(['\"])([\w-]+)\1\s*,\s*(['\"])(.*?)\3"
)
TAG_STYLE_RE = re.compile(
    r"<([a-zA-Z0-9]+)\b([^>]*?)\sstyle\s*=\s*(['\"])(.*?)\3",
    re.IGNORECASE | re.DOTALL,
)
STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.IGNORECASE | re.DOTALL)
CLASS_RE = re.compile(r"""class\s*=\s*(['"])(.*?)\1""", re.IGNORECASE | re.DOTALL)
REWARD_GOLD_RE = re.compile(r"--reward-gold\b")
ADVANCE_RE = re.compile(r"(?:^|[^a-z0-9])(?:advance|play-now|gob-btn--gate)(?:[^a-z0-9]|$)")
WIN_BADGE_RE = re.compile(r"(?:^|[^a-z0-9])(?:wl|win)(?:[^a-z0-9]|$)")
POSITIVE_SELECTOR_RE = re.compile(
    r"delta-up|tier-green|(?:^|[^a-z0-9])t-green(?:[^a-z0-9]|$)|"
    r"is-pos|is-up|tsr-up|risk-low|rm-tile--keep|board-gain|boardgain|"
    r"data-band=[\"']high[\"']|"
    r"(?:^|[^a-z0-9])(?:chem|meter)(?:[^a-z0-9]|$)|"
    r"is-green|gob-chg|(?:^|[^a-z0-9])(?:att-col|att-bar)(?:[^a-z0-9]|$)|"
    r"em_60_79|em_80_plus"
)
SAVE_RE = re.compile(
    r"(?:^|[^a-z0-9])(?:save|saved|committed|gob-btn--action|toggle-btn|"
    r"gated|td-gate|is-on|is-saved|is-committed)(?:[^a-z0-9]|$)"
)
RAMP_SELECTOR_RE = re.compile(r"(?:^|[^a-z0-9])(?:att-col|att-bar)(?:[^a-z0-9]|$)")
POSITIVE_VALUE_RE = re.compile(r"var\(\s*--(?:delta-up|tier-green)\b")
GREEN_VALUE_RE = re.compile(r"var\(\s*--green\b")
ORANGE_VALUE_RE = re.compile(r"var\(\s*--orange\b")
LAW_ANNOTATION_RE = re.compile(
    r"colour-law:\s*(positive-data|committed|saved|reward)\b", re.I
)
NEW_SURFACE_EXCLUDE = frozenset({
    "css/gob-advanced.css",
})
NEW_DESIGN_CSS = frozenset({
    "css/office-home.css",
    "css/home-base.css",
    "css/milestone-modal.css",
    "css/season-peak.css",
    "css/trophy-case.css",
    "recruiting-spine.css",
    "recruiting-dock.css",
    "recruiting-signing.css",
    "recruiting-results-hub.css",
    "training.css",
    "training-report.css",
    "css/training-newswire.css",
    "css/development-focus.css",
    "css/player-development-grid.css",
    "set-lineup.css",
    "playbooks.css",
    "css/playbook-tiles.css",
    "box-score.css",
    "cut-players.css",
    "game-plan.css",
    "scouting-report.css",
    "css/prep-v2-scouting.css",
    "team-builder.css",
    "css/auth-bar.css",
    "css/legal.css",
    "mode-select.css",
    "css/sammy-modal.css",
    "css/username-modal.css",
    "css/walk-on-welcome.css",
    "css/attribute-tour.css",
    "css/tutorial-lineup-modal.css",
    "css/tutorial-persona-intro.css",
    "css/tutorial-pick-opponent.css",
    "css/tutorial-tipoff.css",
    "css/fte.css",
    "auth.css",
    "css/community.css",
    "franchise-select-team.css",
    "training-playbooks.css",
    "playbook-report.css",
    "player-detail.css",
})

# Frozen leftover sheet. New rules belong in the view's own CSS.
# These ceilings may shrink; they must not grow.
FCC_CSS_REL = "franchise-command-center.css"
FCC_CSS_MAX_LINES = 2261
FCC_CSS_MAX_RULES = 293
REWARD_SELECTOR_RE = re.compile(
    r"med\.gold|"
    r"\.pk\b|\.pk-|"
    r"\.cf\b|"
    r"\.mm\.is-gold|\.mm\s+\.med|"
    r"(?:^|[^a-z0-9-])(?:xg|xg-key|xgsweep)(?:[^a-z0-9-]|$)|"
    r"gold-t|"
    r"\.pk-f|\.rv-f|"
    r"trophy-case",
    re.I,
)

CAMEL_PROP = {
    "color": "color",
    "backgroundColor": "background-color",
    "background": "background",
    "borderColor": "border-color",
    "fill": "fill",
    "stroke": "stroke",
    "fontSize": "font-size",
    "fontWeight": "font-weight",
    "letterSpacing": "letter-spacing",
    "fontFamily": "font-family",
    "font": "font",
    "boxShadow": "box-shadow",
    "textShadow": "text-shadow",
    "outlineColor": "outline-color",
    "caretColor": "caret-color",
}


@dataclass(frozen=True)
class Color:
    rgb: tuple[int, int, int]
    alpha: float = 1.0

    @property
    def lab(self) -> tuple[float, float, float]:
        return _rgb_to_lab(self.rgb)

    @property
    def chroma(self) -> float:
        _l, a, b = self.lab
        return (a * a + b * b) ** 0.5


@dataclass
class Hit:
    path: str
    line: int
    surface: str
    kind: str
    text: str
    detail: str = ""


@dataclass
class Audit:
    root: Path
    colours: list[Hit] = field(default_factory=list)
    types: list[Hit] = field(default_factory=list)
    laws: list[Hit] = field(default_factory=list)
    annotations: dict[str, dict[int, str]] = field(default_factory=dict)

    def colour_counts(self) -> dict[str, int]:
        counts = {name: 0 for name in FAMILY_ORDER}
        for hit in self.colours:
            counts[hit.kind] = counts.get(hit.kind, 0) + 1
        return counts

    def type_counts(self) -> dict[str, int]:
        counts = {name: 0 for name in TYPE_ORDER}
        for hit in self.types:
            counts[hit.kind] = counts.get(hit.kind, 0) + 1
        return counts

    def law_counts(self) -> dict[str, dict[str, int]]:
        out = {"new": {name: 0 for name in LAW_ORDER}, "legacy": {name: 0 for name in LAW_ORDER}}
        for hit in self.laws:
            bucket = out.get(hit.surface)
            if bucket is not None:
                bucket[hit.kind] = bucket.get(hit.kind, 0) + 1
        return out


def _srgb_channel(value: float) -> float:
    channel = value / 255.0
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _rgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    red, green, blue = (_srgb_channel(c) for c in rgb)
    x = (red * 0.4124564 + green * 0.3575761 + blue * 0.1804375) / 0.95047
    y = red * 0.2126729 + green * 0.7151522 + blue * 0.0721750
    z = (red * 0.0193339 + green * 0.1191920 + blue * 0.9503041) / 1.08883

    def pivot(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t) + (16 / 116)

    fx, fy, fz = pivot(x), pivot(y), pivot(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(left: Color, right: Color) -> float:
    l1, a1, b1 = left.lab
    l2, a2, b2 = right.lab
    return ((l1 - l2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2) ** 0.5


def _hue(color: Color) -> float:
    _light, a, b = color.lab
    return math.degrees(math.atan2(b, a)) % 360


def _hue_distance(left: Color, right: Color) -> float:
    delta = abs(_hue(left) - _hue(right)) % 360
    return min(delta, 360 - delta)


def _channel(text: str) -> int:
    if text.endswith("%"):
        return max(0, min(255, round(float(text[:-1]) * 2.55)))
    return max(0, min(255, round(float(text))))


def _alpha(text: str | None) -> float:
    if not text:
        return 1.0
    if text.endswith("%"):
        return max(0.0, min(1.0, float(text[:-1]) / 100.0))
    value = float(text)
    if value > 1:
        return max(0.0, min(1.0, value / 255.0))
    return max(0.0, min(1.0, value))


def _expand_hex(digits: str) -> Color:
    if len(digits) in (3, 4):
        digits = "".join(ch * 2 for ch in digits)
    red = int(digits[0:2], 16)
    green = int(digits[2:4], 16)
    blue = int(digits[4:6], 16)
    alpha = int(digits[6:8], 16) / 255.0 if len(digits) == 8 else 1.0
    return Color((red, green, blue), alpha)


def _hsl_to_rgb(hue: float, sat: float, light: float) -> tuple[int, int, int]:
    hue = hue % 360
    c = (1 - abs(2 * light - 1)) * sat
    x = c * (1 - abs((hue / 60) % 2 - 1))
    m = light - c / 2
    if hue < 60:
        red, green, blue = c, x, 0.0
    elif hue < 120:
        red, green, blue = x, c, 0.0
    elif hue < 180:
        red, green, blue = 0.0, c, x
    elif hue < 240:
        red, green, blue = 0.0, x, c
    elif hue < 300:
        red, green, blue = x, 0.0, c
    else:
        red, green, blue = c, 0.0, x
    return (
        round((red + m) * 255),
        round((green + m) * 255),
        round((blue + m) * 255),
    )


def parse_color(text: str) -> Color | None:
    raw = text.strip()
    hex_match = HEX_RE.fullmatch(raw)
    if hex_match:
        return _expand_hex(hex_match.group(1))
    rgb_match = RGB_RE.fullmatch(raw)
    if rgb_match:
        return Color(
            (_channel(rgb_match.group(1)), _channel(rgb_match.group(2)), _channel(rgb_match.group(3))),
            _alpha(rgb_match.group(4)),
        )
    hsl_match = HSL_RE.fullmatch(raw)
    if hsl_match:
        return Color(
            _hsl_to_rgb(
                float(hsl_match.group(1)),
                float(hsl_match.group(2)[:-1]) / 100.0,
                float(hsl_match.group(3)[:-1]) / 100.0,
            ),
            _alpha(hsl_match.group(4)),
        )
    named = NAMED_COLORS.get(raw.lower())
    if named:
        return Color(named, 1.0)
    return None


def _mask_comments(text: str, html: bool = False) -> str:
    def keep_newlines(match: re.Match[str]) -> str:
        return "".join("\n" if ch == "\n" else " " for ch in match.group(0))

    masked = re.sub(r"/\*.*?\*/", keep_newlines, text, flags=re.DOTALL)
    if html:
        masked = re.sub(r"<!--.*?-->", keep_newlines, masked, flags=re.DOTALL)
    return masked


def _mask_js_comments(text: str) -> str:
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch == "/" and nxt == "*":
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            out.extend("\n" if c == "\n" else " " for c in text[i:end])
            i = end
            continue
        if ch in "\"'`":
            out.append(ch)
            i += 1
            while i < n:
                out.append(text[i])
                if text[i] == "\\":
                    if i + 1 < n:
                        out.append(text[i + 1])
                        i += 2
                        continue
                if text[i] == ch:
                    i += 1
                    break
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, max(0, index)) + 1


def _strip_var_calls(value: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(value):
        if value.startswith("var(", i):
            depth = 0
            j = i
            while j < len(value):
                if value[j] == "(":
                    depth += 1
                elif value[j] == ")":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
            i = j
            continue
        out.append(value[i])
        i += 1
    return "".join(out)


def _outside_functions(value: str) -> str:
    """Drop var() and url() so named colours inside them are not paints."""
    out: list[str] = []
    i = 0
    lower = value.lower()
    while i < len(value):
        if lower.startswith("var(", i) or lower.startswith("url(", i):
            depth = 0
            j = i
            while j < len(value):
                if value[j] == "(":
                    depth += 1
                elif value[j] == ")":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
            out.append(" " * (j - i))
            i = j
            continue
        out.append(value[i])
        i += 1
    return "".join(out)


def load_tokens(path: Path | None) -> dict[str, Color]:
    raw: dict[str, str] = dict(FALLBACK_HEX)
    if path and path.is_file():
        text = _mask_comments(path.read_text(encoding="utf-8", errors="replace"))
        for match in re.finditer(r"(--[\w-]+)\s*:\s*([^;}+]+)", text):
            raw[match.group(1)] = match.group(2).strip()
    resolved: dict[str, Color] = {}
    pending = dict(raw)
    for _ in range(len(pending) + 1):
        progressed = False
        for name, value in list(pending.items()):
            if name in resolved:
                pending.pop(name, None)
                continue
            var_match = re.fullmatch(r"var\(\s*(--[\w-]+)\s*(?:,[^)]*)?\)", value.strip())
            if var_match:
                ref = var_match.group(1)
                if ref in resolved:
                    resolved[name] = resolved[ref]
                    pending.pop(name, None)
                    progressed = True
                continue
            color = parse_color(value.split()[0] if value.split() else value)
            # parse_color is fullmatch, so try the first token and function-shaped values.
            if color is None:
                color = _first_color(value)
            if color is not None:
                resolved[name] = color
                pending.pop(name, None)
                progressed = True
        if not progressed:
            break
    return resolved


def _first_color(value: str) -> Color | None:
    hex_match = HEX_RE.search(value)
    if hex_match:
        return _expand_hex(hex_match.group(1))
    rgb_match = RGB_RE.search(value)
    if rgb_match:
        return Color(
            (_channel(rgb_match.group(1)), _channel(rgb_match.group(2)), _channel(rgb_match.group(3))),
            _alpha(rgb_match.group(4)),
        )
    hsl_match = HSL_RE.search(value)
    if hsl_match:
        return Color(
            _hsl_to_rgb(
                float(hsl_match.group(1)),
                float(hsl_match.group(2)[:-1]) / 100.0,
                float(hsl_match.group(3)[:-1]) / 100.0,
            ),
            _alpha(hsl_match.group(4)),
        )
    return None


@dataclass
class Palette:
    tokens: dict[str, Color]
    families: dict[str, list[tuple[str, Color]]]

    def classify(self, color: Color) -> tuple[str, str, float]:
        """Return (family, reference token, distance from that reference).

        Near-duplicates share a hue with the brand token even when lightness
        differs (CSS ``green`` is a long way from ``--green`` in CIE76, and
        still belongs with the greens). Within that hue window the closest
        brand colour wins, so navy stays navy and gold stays gold.
        """
        best_family = "other"
        best_de = 10**9
        hue_family = ""
        hue_de = 10**9
        for family, anchors in self.families.items():
            if family == "white/grey" or not anchors:
                continue
            ref_name = FAMILY_REFERENCE[family]
            ref = self.tokens.get(ref_name) or anchors[0][1]
            distance = min(delta_e(color, anchor) for _name, anchor in anchors)
            if distance < best_de:
                best_de = distance
                best_family = family
            if (
                color.chroma >= 18
                and ref.chroma >= 18
                and _hue_distance(color, ref) <= 32
                and distance < hue_de
            ):
                hue_de = distance
                hue_family = family
        grey_name, grey_distance = self._nearest_grey(color)
        if color.chroma < CHROMA_GREY and (grey_distance <= best_de + 8 or best_de > FAMILY_MAX_DE):
            return "white/grey", grey_name, grey_distance
        chosen = hue_family or (best_family if best_de <= FAMILY_MAX_DE else "")
        if chosen:
            ref_name = FAMILY_REFERENCE[chosen]
            ref = self.tokens.get(ref_name)
            if ref is None and self.families.get(chosen):
                ref_name, ref = self.families[chosen][0]
            distance = delta_e(color, ref) if ref is not None else best_de
            return chosen, ref_name, distance
        if grey_distance <= 30 or color.chroma < CHROMA_GREY:
            return "white/grey", grey_name, grey_distance
        return "other", "", best_de

    def _nearest_grey(self, color: Color) -> tuple[str, float]:
        best_name = "--white"
        best = 10**9
        for name, anchor in self.families.get("white/grey", []):
            distance = delta_e(color, anchor) + abs(color.alpha - anchor.alpha) * 100
            if distance < best:
                best = distance
                best_name = name
        return best_name, best


def build_palette(tokens: dict[str, Color]) -> Palette:
    families: dict[str, list[tuple[str, Color]]] = {name: [] for name in FAMILY_ORDER if name != "other"}
    for family, names in FAMILY_ANCHORS.items():
        for name in names:
            color = tokens.get(name)
            if color is not None:
                families[family].append((name, color))
    ramp: list[tuple[str, Color]] = []
    seen: set[str] = set()
    for name, color in tokens.items():
        if name in seen:
            continue
        grey_name = (
            name.startswith(("--white", "--black", "--text-", "--bg", "--surface", "--line", "--scrim"))
            or color.chroma < CHROMA_GREY
        )
        chromatic = any(name == anchor for anchors in FAMILY_ANCHORS.values() for anchor in anchors)
        if grey_name and not chromatic:
            ramp.append((name, color))
            seen.add(name)
    if not ramp and "--white" in tokens:
        ramp.append(("--white", tokens["--white"]))
    families["white/grey"] = ramp
    return Palette(tokens, families)


def shell_pages(root: Path) -> set[str]:
    js = root / "js" / "shared" / "gobShell.js"
    if not js.is_file():
        return set()
    text = js.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"\bPAGES\s*=\s*\{(.*?)\n  \};", text, re.DOTALL)
    body = match.group(1) if match else ""
    return set(re.findall(r"""['\"]/([^'\"]+\.html)['\"]""", body))


def _collect_annotations(raw: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for index, line in enumerate(raw.splitlines(), 1):
        match = LAW_ANNOTATION_RE.search(line)
        if not match:
            continue
        kind = match.group(1).lower()
        if kind == "saved":
            kind = "committed"
        out[index] = kind
    return out


def _annotation_for(audit: Audit, path: str, line: int) -> str | None:
    by_line = audit.annotations.get(path) or {}
    for candidate in (line, line - 1, line - 2):
        if candidate in by_line:
            return by_line[candidate]
    return None


def is_new_surface(rel: Path, text: str, pages: set[str]) -> bool:
    posix = rel.as_posix()
    name = rel.name
    if posix in NEW_SURFACE_EXCLUDE:
        return False
    if posix.startswith("css/gob-") or posix in NEW_DESIGN_CSS:
        return True
    if posix.startswith("js/shared/views/"):
        return True
    if posix.startswith("js/shared/gob") and name.startswith("gob"):
        return True
    if rel.suffix.lower() == ".html":
        if name in pages:
            return True
        if re.search(r"<html\b[^>]*\b(?:gob-shell|gob-focus)\b", text, re.IGNORECASE):
            return True
    return False


def _iter_blocks(text: str, lo: int, hi: int):
    i = lo
    while i < hi:
        start = text.find("{", i, hi)
        if start < 0:
            break
        depth = 1
        j = start + 1
        while j < hi and depth:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        body_hi = j - 1
        if "{" in text[start + 1:body_hi]:
            yield from _iter_blocks(text, start + 1, body_hi)
        else:
            yield text[i:start], start + 1, body_hi
        i = j


def _colors_in(value: str) -> list[tuple[str, Color]]:
    found: list[tuple[str, Color]] = []
    consumed = [False] * len(value)

    def take(match: re.Match[str], label: str, color: Color) -> None:
        found.append((label, color))
        for index in range(match.start(), match.end()):
            if index < len(consumed):
                consumed[index] = True

    for match in HEX_RE.finditer(value):
        if value[max(0, match.start() - 4):match.start()].lower().endswith("url("):
            continue
        take(match, match.group(0), _expand_hex(match.group(1)))
    for match in RGB_RE.finditer(value):
        take(
            match,
            match.group(0),
            Color(
                (_channel(match.group(1)), _channel(match.group(2)), _channel(match.group(3))),
                _alpha(match.group(4)),
            ),
        )
    for match in HSL_RE.finditer(value):
        take(
            match,
            match.group(0),
            Color(
                _hsl_to_rgb(
                    float(match.group(1)),
                    float(match.group(2)[:-1]) / 100.0,
                    float(match.group(3)[:-1]) / 100.0,
                ),
                _alpha(match.group(4)),
            ),
        )
    visible = _outside_functions(value)
    for match in NAMED_RE.finditer(visible):
        if any(consumed[index] for index in range(match.start(), min(match.end(), len(consumed)))):
            continue
        name = match.group(1).lower()
        rgb = NAMED_COLORS.get(name)
        if rgb is None:
            continue
        found.append((match.group(1), Color(rgb, 1.0)))
    return found


def _distance_detail(family: str, ref: str, distance: float, color: Color, palette: Palette) -> str:
    if family == "white/grey":
        return f"ΔE {distance:.1f} from {ref}"
    if family == "other":
        return f"ΔE {distance:.1f} from the nearest brand token"
    detail = f"ΔE {distance:.1f} from {ref}"
    anchor = palette.tokens.get(ref)
    if anchor is not None and abs(color.alpha - anchor.alpha) > 0.02:
        detail += f", alpha {color.alpha:.2f}"
    return detail


def _type_kinds(prop: str, value: str) -> list[str]:
    outside = _strip_var_calls(value)
    kinds: list[str] = []
    prop_name = prop.lower()
    if prop_name in {"font-size", "font"} and re.search(
        r"\d+(\.\d+)?\s*(px|rem|em|%|ch|vw|vh|pt)\b", outside, re.IGNORECASE
    ):
        kinds.append("font-size")
    elif prop_name == "font-size" and re.search(r"\d", outside):
        kinds.append("font-size")
    if prop_name == "font-weight" and re.search(r"\b(\d{3}|bold|bolder|lighter|normal)\b", outside, re.IGNORECASE):
        kinds.append("font-weight")
    elif prop_name == "font" and re.search(r"\b(\d{3}|bold|bolder|lighter)\b", outside, re.IGNORECASE):
        kinds.append("font-weight")
    if prop_name == "letter-spacing" and re.search(
        r"[+-]?(?:\d+\.\d+|\d+|\.\d+)\s*(px|rem|em)\b", outside, re.IGNORECASE
    ):
        kinds.append("letter-spacing")
    if prop_name in {"font-family", "font"} and _family_is_literal(prop_name, value, outside):
        kinds.append("font-family")
    return kinds


def _family_is_literal(prop: str, value: str, outside: str) -> bool:
    if prop == "font":
        match = re.search(
            r"(?:[\d.]+(?:px|rem|em|%|ch|vw|vh|pt)?)\s*(?:/\s*[\d.]+%?)?\s+(.+)$",
            outside,
            re.IGNORECASE,
        )
        family = match.group(1) if match else ""
    else:
        family = outside
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]*", family)
    quoted = re.findall(r"""['\"][^'\"]+['\"]""", family)
    non_generic = [word for word in words if word.lower() not in GENERIC_FAMILIES]
    if quoted or non_generic:
        return True
    if "var(" not in value and words:
        return True
    return False


def _selector_text(raw: str) -> str:
    selector = raw.strip()
    if "}" in selector:
        selector = selector.rsplit("}", 1)[-1]
    selector = selector.strip()
    if selector.lower().startswith("@") and "{" not in raw:
        return selector
    return selector


def _green_allowed(selector: str, value: str, annotation: str | None = None) -> bool:
    if annotation == "positive-data":
        return True
    blob = selector.lower()
    if ADVANCE_RE.search(blob) or WIN_BADGE_RE.search(blob) or POSITIVE_SELECTOR_RE.search(blob):
        return True
    if POSITIVE_VALUE_RE.search(value) and not GREEN_VALUE_RE.search(value):
        return True
    return False


def _orange_allowed(selector: str, annotation: str | None = None) -> bool:
    if annotation in {"committed", "saved"}:
        return True
    blob = selector.lower()
    return bool(SAVE_RE.search(blob) or RAMP_SELECTOR_RE.search(blob))


def _reward_gold_allowed(selector: str, annotation: str | None = None) -> bool:
    if annotation == "reward":
        return True
    return bool(REWARD_SELECTOR_RE.search(selector or ""))


def _iter_blocks_inclusive(text: str, lo: int, hi: int):
    """Every CSS block, including ancestors (so @keyframes wraps `to`)."""
    i = lo
    while i < hi:
        start = text.find("{", i, hi)
        if start < 0:
            break
        depth = 1
        j = start + 1
        while j < hi and depth:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        body_hi = j - 1
        yield text[i:start], start + 1, body_hi
        if "{" in text[start + 1:body_hi]:
            yield from _iter_blocks_inclusive(text, start + 1, body_hi)
        i = j


def _selector_covering(text: str, index: int) -> str:
    covering: list[str] = []
    for selector_raw, body_lo, body_hi in _iter_blocks_inclusive(text, 0, len(text)):
        if body_lo <= index <= body_hi:
            covering.append(_selector_text(selector_raw))
    return " ".join(covering)


def _record_declaration(
    audit: Audit,
    palette: Palette,
    *,
    path: str,
    surface: str,
    text: str,
    index: int,
    prop: str,
    value: str,
    selector: str,
    skip_type: bool,
) -> None:
    prop_name = prop.lower()
    full_prop = prop.lower() if prop.startswith("--") else prop_name
    line = line_of(text, index)
    note = _annotation_for(audit, path, line)
    defining = full_prop in DEFINITION_NAMES
    for label, color in _colors_in(value):
        family, ref, distance = palette.classify(color)
        audit.colours.append(Hit(
            path, line, surface, family, label,
            _distance_detail(family, ref, distance, color, palette),
        ))
        if defining:
            continue
        if family == "green" and not _green_allowed(selector, value, note):
            audit.laws.append(Hit(
                path, line, surface, "green", label,
                f"{_selector_label(selector)} {_distance_detail(family, ref, distance, color, palette)}",
            ))
        elif family == "orange" and not _orange_allowed(selector, note):
            audit.laws.append(Hit(
                path, line, surface, "orange", label,
                f"{_selector_label(selector)} {_distance_detail(family, ref, distance, color, palette)}",
            ))
    if not defining and not _green_allowed(selector, value, note) and GREEN_VALUE_RE.search(value):
        audit.laws.append(Hit(path, line, surface, "green", "var(--green)", _selector_label(selector)))
    if not defining and not _orange_allowed(selector, note) and ORANGE_VALUE_RE.search(value):
        audit.laws.append(Hit(path, line, surface, "orange", "var(--orange)", _selector_label(selector)))
    if skip_type or full_prop not in {"font-size", "font-weight", "letter-spacing", "font-family", "font"}:
        return
    for kind in _type_kinds(full_prop, value):
        audit.types.append(Hit(path, line, surface, kind, value.strip(), full_prop))


def _selector_label(selector: str) -> str:
    cleaned = " ".join(selector.split())
    if not cleaned:
        return "(inline)"
    return cleaned[:180]


def _scan_css_range(
    audit: Audit,
    palette: Palette,
    *,
    path: str,
    surface: str,
    text: str,
    lo: int,
    hi: int,
) -> None:
    for selector_raw, body_lo, body_hi in _iter_blocks(text, lo, hi):
        selector = _selector_text(selector_raw)
        skip_type = selector.lower().startswith("@font-face")
        body = text[body_lo:body_hi]
        local = body_lo
        for match in DECL_RE.finditer(body):
            prefix = "--" if match.group(1) else ""
            prop = prefix + match.group(2)
            _record_declaration(
                audit, palette,
                path=path, surface=surface, text=text,
                index=local + match.start(),
                prop=prop, value=match.group(3),
                selector=selector, skip_type=skip_type,
            )


def _scan_style_attribute(
    audit: Audit,
    palette: Palette,
    *,
    path: str,
    surface: str,
    text: str,
    index: int,
    tag: str,
    attrs: str,
    value: str,
) -> None:
    classes = ""
    class_match = CLASS_RE.search(attrs)
    if class_match:
        classes = "." + ".".join(class_match.group(2).split())
    selector = f"{tag}{classes}" if classes else tag or "(inline)"
    for match in DECL_RE.finditer(value):
        prefix = "--" if match.group(1) else ""
        prop = prefix + match.group(2)
        _record_declaration(
            audit, palette,
            path=path, surface=surface, text=text,
            index=index + match.start(),
            prop=prop, value=match.group(3),
            selector=selector, skip_type=False,
        )


def _scan_js_line(
    audit: Audit,
    palette: Palette,
    *,
    path: str,
    surface: str,
    text: str,
    line_start: int,
    line: str,
) -> None:
    if not STYLE_SIGNAL_RE.search(line):
        return
    for match in TAG_STYLE_RE.finditer(line):
        _scan_style_attribute(
            audit, palette,
            path=path, surface=surface, text=text,
            index=line_start + match.start(4),
            tag=match.group(1), attrs=match.group(2), value=match.group(4),
        )
    for match in JS_STYLE_ASSIGN_RE.finditer(line):
        prop = CAMEL_PROP.get(match.group(1), match.group(1))
        _record_declaration(
            audit, palette,
            path=path, surface=surface, text=text,
            index=line_start + match.start(3),
            prop=prop, value=match.group(3),
            selector="(inline)", skip_type=False,
        )
    for match in JS_SET_PROP_RE.finditer(line):
        _record_declaration(
            audit, palette,
            path=path, surface=surface, text=text,
            index=line_start + match.start(4),
            prop=match.group(2), value=match.group(4),
            selector="(inline)", skip_type=False,
        )
    # Quoted style strings that are not a full tag: `color:#fff;font-size:13px`.
    if "style=" not in line.lower() and ".style." not in line and "setProperty" not in line:
        for match in DECL_RE.finditer(line):
            prefix = "--" if match.group(1) else ""
            prop = prefix + match.group(2)
            if prop.lower() not in {
                "color", "background", "background-color", "border", "border-color",
                "fill", "stroke", "box-shadow", "text-shadow", "outline", "outline-color",
                "font", "font-size", "font-weight", "letter-spacing", "font-family",
            } and not prop.startswith("--"):
                continue
            _record_declaration(
                audit, palette,
                path=path, surface=surface, text=text,
                index=line_start + match.start(),
                prop=prop, value=match.group(3),
                selector="(inline)", skip_type=False,
            )


def _scan_reward_gold(audit: Audit, path: str, surface: str, text: str) -> None:
    for match in REWARD_GOLD_RE.finditer(text):
        line = line_of(text, match.start())
        note = _annotation_for(audit, path, line)
        selector = _selector_covering(text, match.start())
        context = selector or text[max(0, match.start() - 80):match.start() + 80]
        if _reward_gold_allowed(context, note):
            continue
        audit.laws.append(Hit(
            path, line, surface, "reward-gold", "--reward-gold",
            _selector_label(selector) if selector else "token should be unused",
        ))


def _rel(root: Path, path: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def audit_tree(root: Path, tokens_path: Path | None = None) -> Audit:
    tokens_file = tokens_path
    if tokens_file is None:
        candidate = root / TOKENS_REL
        tokens_file = candidate if candidate.is_file() else None
    palette = build_palette(load_tokens(tokens_file))
    pages = shell_pages(root)
    audit = Audit(root=root)
    tokens_resolved = (root / TOKENS_REL).resolve() if (root / TOKENS_REL).is_file() else None
    if tokens_file and tokens_file.is_file():
        tokens_resolved = tokens_file.resolve()

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in {".css", ".html", ".js"}:
            continue
        if tokens_resolved is not None and path.resolve() == tokens_resolved:
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        rel_path = _rel(root, path)
        rel = rel_path.as_posix()
        audit.annotations[rel] = _collect_annotations(raw)
        surface = "new" if is_new_surface(rel_path, raw, pages) else "legacy"
        if suffix == ".css":
            masked = _mask_comments(raw)
            _scan_css_range(audit, palette, path=rel, surface=surface, text=masked, lo=0, hi=len(masked))
            _scan_reward_gold(audit, rel, surface, masked)
        elif suffix == ".html":
            masked = _mask_comments(raw, html=True)
            for match in STYLE_BLOCK_RE.finditer(masked):
                _scan_css_range(
                    audit, palette,
                    path=rel, surface=surface, text=masked,
                    lo=match.start(1), hi=match.end(1),
                )
            for match in TAG_STYLE_RE.finditer(masked):
                _scan_style_attribute(
                    audit, palette,
                    path=rel, surface=surface, text=masked,
                    index=match.start(4),
                    tag=match.group(1), attrs=match.group(2), value=match.group(4),
                )
            _scan_reward_gold(audit, rel, surface, masked)
        else:
            masked = _mask_js_comments(raw)
            cursor = 0
            for line in masked.splitlines(keepends=True):
                _scan_js_line(
                    audit, palette,
                    path=rel, surface=surface, text=masked,
                    line_start=cursor, line=line,
                )
                cursor += len(line)
            _scan_reward_gold(audit, rel, surface, masked)
    return audit


def _counts_by_file(audit: Audit) -> list[tuple[str, str, int, int, int]]:
    rows: dict[str, list] = {}
    for hit in (*audit.colours, *audit.types, *audit.laws):
        row = rows.setdefault(hit.path, [hit.surface, 0, 0, 0])
        row[0] = hit.surface
    for hit in audit.colours:
        rows[hit.path][1] += 1
    for hit in audit.types:
        rows[hit.path][2] += 1
    for hit in audit.laws:
        rows[hit.path][3] += 1
    ranked = [
        (path, surface, colours, types, laws)
        for path, (surface, colours, types, laws) in rows.items()
    ]
    ranked.sort(key=lambda item: (-(item[2] + item[3] + item[4]), item[0]))
    return ranked


def format_summary(audit: Audit) -> str:
    colour_counts = audit.colour_counts()
    type_counts = audit.type_counts()
    law = audit.law_counts()
    lines = ["Colour literals (outside css/gob-tokens.css)", ""]
    name_w = 12
    lines.append(f"  {'category':<{name_w}} {'count':>7}")
    for name in FAMILY_ORDER:
        lines.append(f"  {name:<{name_w}} {colour_counts.get(name, 0):>7}")
    lines.append(f"  {'total':<{name_w}} {sum(colour_counts.values()):>7}")
    lines.append("")
    lines.append("Type literals")
    lines.append("")
    lines.append(f"  {'category':<{name_w}} {'count':>7}")
    for name in TYPE_ORDER:
        lines.append(f"  {name:<{name_w}} {type_counts.get(name, 0):>7}")
    lines.append(f"  {'total':<{name_w}} {sum(type_counts.values()):>7}")
    lines.append("")
    lines.append("Colour-law hits")
    lines.append("")
    lines.append(f"  {'surface':<{name_w}} {'green':>7} {'orange':>7} {'reward-gold':>12} {'total':>7}")
    for surface in ("new", "legacy"):
        bucket = law[surface]
        total = sum(bucket.values())
        lines.append(
            f"  {surface:<{name_w}} {bucket.get('green', 0):>7} {bucket.get('orange', 0):>7} "
            f"{bucket.get('reward-gold', 0):>12} {total:>7}"
        )
    new_total = sum(law["new"].values())
    legacy_total = sum(law["legacy"].values())
    lines.append(
        f"  {'total':<{name_w}} {law['new']['green'] + law['legacy']['green']:>7} "
        f"{law['new']['orange'] + law['legacy']['orange']:>7} "
        f"{law['new']['reward-gold'] + law['legacy']['reward-gold']:>12} "
        f"{new_total + legacy_total:>7}"
    )
    lines.append("")
    lines.append("Top 20 files")
    lines.append("")
    header = f"  {'file':<52} {'surface':<8} {'colours':>8} {'type':>6} {'law':>6}"
    lines.append(header)
    for path, surface, colours, types, laws in _counts_by_file(audit)[:20]:
        shown = path if len(path) <= 52 else "…" + path[-51:]
        lines.append(f"  {shown:<52} {surface:<8} {colours:>8} {types:>6} {laws:>6}")
    if not _counts_by_file(audit):
        lines.append("  (none)")
    return "\n".join(lines)


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    def cell(value: str) -> str:
        return value.replace("|", "\\|")

    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        out.append("| " + " | ".join(cell(col) for col in row) + " |")
    return "\n".join(out)


def format_report(audit: Audit) -> str:
    colour_counts = audit.colour_counts()
    type_counts = audit.type_counts()
    law = audit.law_counts()
    parts = [
        "# UI token audit — 2026-09-29",
        "",
        "Report-only. Generated by `scripts/check_ui_tokens.py` from colour and type literals",
        "under `FrontEnd/static`. `css/gob-tokens.css` is the token source and is excluded",
        "from the literal scan. Exit code is 0. `--strict` exits 1 when a new-design",
        "file has a colour-law hit that is not on the allow-list. Legacy hits are",
        "reported only.",
        "",
        "## File split",
        "",
        "New: shell HTML (`gob-shell` / `gob-focus` on `<html>`, or a filename listed in",
        "`js/shared/gobShell.js` `PAGES`), `css/gob-*.css` except `gob-advanced.css`",
        "(advanced-topic diagrams), Chapter 7 chrome (`office-home`,",
        "`home-base`, `milestone-modal`, `season-peak`, `trophy-case`), recruiting hub CSS",
        "(`recruiting-spine.css`, `recruiting-dock.css`, `recruiting-signing.css`,",
        "`recruiting-results-hub.css`), `js/shared/gob*.js`,",
        "`js/shared/views/**`, training/report CSS, and Playbooks (`playbooks.css`,",
        "`css/playbook-tiles.css`), and the tutorial / FTE CSS in `NEW_DESIGN_CSS`.",
        "",
        "Legacy: every other scanned file. That is an old page or stylesheet still to migrate,",
        "not new code breaking the rules.",
        "",
        "## Summary",
        "",
        _md_table(
            ["Category", "Count"],
            [[name, str(colour_counts.get(name, 0))] for name in FAMILY_ORDER]
            + [["colour total", str(sum(colour_counts.values()))]]
            + [[name, str(type_counts.get(name, 0))] for name in TYPE_ORDER]
            + [["type total", str(sum(type_counts.values()))]]
            + [
                ["colour-law new", str(sum(law["new"].values()))],
                ["colour-law legacy", str(sum(law["legacy"].values()))],
                ["colour-law total", str(sum(law["new"].values()) + sum(law["legacy"].values()))],
            ],
        ),
        "",
        "Colour-law counts by kind:",
        "",
        _md_table(
            ["Surface", "Green", "Orange", "reward-gold", "Total"],
            [
                [
                    surface,
                    str(law[surface]["green"]),
                    str(law[surface]["orange"]),
                    str(law[surface]["reward-gold"]),
                    str(sum(law[surface].values())),
                ]
                for surface in ("new", "legacy")
            ],
        ),
        "",
        "## Top 20 files",
        "",
        _md_table(
            ["File", "Surface", "Colours", "Type", "Colour-law"],
            [
                [path, surface, str(colours), str(types), str(laws)]
                for path, surface, colours, types, laws in _counts_by_file(audit)[:20]
            ] or [["(none)", "", "0", "0", "0"]],
        ),
        "",
        "## Colour literals",
        "",
        "Each raw colour (`#hex`, `rgb` / `rgba` / `hsl` / `hsla`, or a named colour used as a paint)",
        "is grouped with the nearest brand family. Distance is CIE76 from the family's reference",
        "token (`--green`, `--orange`, `--navy`, `--blue`, `--red`, `--yellow` for gold).",
        "White and grey use the nearest ramp token, and that distance includes alpha so",
        "`rgba(255,255,255,.1)` lands on a `--white-*` stop rather than solid `--white`.",
        "",
    ]
    for family in FAMILY_ORDER:
        rows = [hit for hit in audit.colours if hit.kind == family]
        rows.sort(key=lambda hit: (hit.path, hit.line, hit.text))
        parts.append(f"### {family} ({len(rows)})")
        parts.append("")
        if not rows:
            parts.append("(none)")
            parts.append("")
            continue
        parts.append(_md_table(
            ["Literal", "Where", "Surface", "Distance"],
            [[hit.text, f"{hit.path}:{hit.line}", hit.surface, hit.detail] for hit in rows],
        ))
        parts.append("")
    parts.extend([
        "## Type literals",
        "",
        "`font-size`, `font-weight`, `letter-spacing`, and `font-family` values that are not",
        "`var(--fs-*)`, `var(--fw-*)`, `var(--tracking-*)`, `var(--font-body)`, or `var(--font-display)`.",
        "A generic fallback written next to one of those tokens is not listed. `@font-face` names are not listed.",
        "",
    ])
    for kind in TYPE_ORDER:
        rows = [hit for hit in audit.types if hit.kind == kind]
        rows.sort(key=lambda hit: (hit.path, hit.line, hit.text))
        parts.append(f"### {kind} ({len(rows)})")
        parts.append("")
        if not rows:
            parts.append("(none)")
            parts.append("")
            continue
        parts.append(_md_table(
            ["Value", "Property", "Where", "Surface"],
            [[hit.text, hit.detail, f"{hit.path}:{hit.line}", hit.surface] for hit in rows],
        ))
        parts.append("")
    parts.extend([
        "## Colour-law hits",
        "",
        "Green is allowed on Advance (`advance`, `play-now`, `gob-btn--gate`), on positive",
        "data (`delta-up`, `tier-green`, `t-green`, `is-up` / `is-pos` / `tsr-up`, chemistry",
        "and board-gain bars, RT/attribute ramps), or a nearby `/* colour-law: positive-data */`.",
        "Orange is allowed on committed/saved (`save`, `committed`, `gob-btn--action`,",
        "`.gated`, `.td-gate`) or `/* colour-law: committed */` / `/* colour-law: saved */`.",
        "`--reward-gold` is allowed on title medallions (`.med.gold`), season-peak glow /",
        "rule / confetti (`.pk`, `.cf`), milestone accents (`.mm.is-gold`, `.mm .med`),",
        "the exceptional-gain marker (`.xg`, `.xg-key`, `xgSweep`), Trophy Case words",
        "(`.gold-t`, `.pk-f` / `.rv-f`), or a nearby `/* colour-law: reward */`.",
        "Token redefinitions of `--green` / `--orange` are listed as literals above and",
        "are not law hits. `css/gob-advanced.css` holds the advanced-topic teaching",
        "diagrams and is not new-design.",
        "",
    ])
    for surface in ("new", "legacy"):
        rows = [hit for hit in audit.laws if hit.surface == surface]
        rows.sort(key=lambda hit: (hit.kind, hit.path, hit.line))
        parts.append(f"### {surface} ({len(rows)})")
        parts.append("")
        if not rows:
            parts.append("(none)")
            parts.append("")
            continue
        parts.append(_md_table(
            ["Kind", "Literal", "Where", "Context"],
            [[hit.kind, hit.text, f"{hit.path}:{hit.line}", hit.detail] for hit in rows],
        ))
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def _iter_css_preludes(text: str, lo: int, hi: int):
    i = lo
    while i < hi:
        while i < hi and text[i].isspace():
            i += 1
        if i >= hi:
            break
        start = text.find("{", i, hi)
        if start < 0:
            break
        depth = 1
        j = start + 1
        while j < hi and depth:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        yield text[i:start].strip(), start + 1, j - 1
        i = j


def count_css_style_rules(text: str) -> int:
    stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    at_re = re.compile(r"^@(\w+)")

    def walk(lo: int, hi: int) -> int:
        n = 0
        for prelude, body_lo, body_hi in _iter_css_preludes(stripped, lo, hi):
            match = at_re.match(prelude)
            if match and match.group(1).lower() in {"media", "supports"}:
                n += walk(body_lo, body_hi)
            elif match:
                continue
            else:
                n += 1
        return n

    return walk(0, len(stripped))


def check_fcc_css_freeze(root: Path) -> str | None:
    path = root / FCC_CSS_REL
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    lines = text.count("\n") + (0 if text.endswith("\n") else 1)
    rules = count_css_style_rules(text)
    grew = []
    if lines > FCC_CSS_MAX_LINES:
        grew.append(f"lines {lines} > {FCC_CSS_MAX_LINES}")
    if rules > FCC_CSS_MAX_RULES:
        grew.append(f"style rules {rules} > {FCC_CSS_MAX_RULES}")
    if not grew:
        return None
    return (
        f"{FCC_CSS_REL} is frozen (no new rules; put new styles in the view's own CSS): "
        + "; ".join(grew)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report UI colour and type token drift.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Directory to scan")
    parser.add_argument("--tokens", type=Path, default=None, help="Token CSS (default: <root>/css/gob-tokens.css)")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Markdown detail path")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when a new-design file has a colour-law hit off the allow-list",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print the summary only; do not write the audit report",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    tokens = args.tokens.resolve() if args.tokens else None
    audit = audit_tree(root, tokens)
    print(format_summary(audit))
    if not args.no_write:
        report_path = args.report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(format_report(audit), encoding="utf-8")
        print(f"\nFull detail: {report_path}")
    freeze = check_fcc_css_freeze(root)
    if freeze:
        print(freeze)
    new_hits = sum(audit.law_counts()["new"].values())
    if freeze:
        return 1
    if args.strict and new_hits:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
