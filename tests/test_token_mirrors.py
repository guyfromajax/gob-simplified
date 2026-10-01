"""Token hygiene (2026-10-01): a value that also lives outside gob-tokens.css must equal the token.

Scripts that need a concrete colour (canvas, colour maths) and sheets that can be
injected into pages without .gob keep the value as a literal or a var() fallback.
These tests stop the copies drifting from the token file.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "FrontEnd" / "static"
TOKENS_CSS = (STATIC / "css" / "gob-tokens.css").read_text()


def _base_block(text: str) -> str:
    start = text.index(".gob,.gob-scope,.auth-bar,.site-footer{")
    end = text.index("\n}", start)
    return text[start:end]


def _tokens() -> dict:
    block = re.sub(r"/\*.*?\*/", "", _base_block(TOKENS_CSS), flags=re.S)
    out = {}
    for name, value in re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", block):
        out[name] = value.strip()
    return out


TOKENS = _tokens()


def _resolve(name: str) -> str:
    value = TOKENS[name]
    seen = set()
    while True:
        match = re.fullmatch(r"var\((--[a-z0-9-]+)\)", value)
        if not match or match.group(1) in seen:
            return value
        seen.add(match.group(1))
        value = TOKENS[match.group(1)]


def _norm(value: str) -> str:
    """Compare CSS values by meaning: case, spaces, quotes and number spelling ignored."""
    text = value.strip().lower().replace('"', "'")
    text = re.sub(r"\s+", "", text)
    return re.sub(r"\d*\.\d+|\d+", lambda m: repr(float(m.group(0))), text)


def test_rt_bands_equal_their_tokens():
    src = (STATIC / "js" / "shared" / "rtBucket.js").read_text()
    bands = re.findall(r"className: '(rt-[a-z]+)', color: '(#[0-9A-Fa-f]{6})', token: '(--[a-z-]+)'", src)
    assert len(bands) == 9
    by_class = {cls: (color, token) for cls, color, token in bands}
    assert {cls: tok for cls, (_, tok) in by_class.items()} == {
        "rt-elite": "--blue", "rt-high": "--tier-green", "rt-mid": "--tier-yellow", "rt-low": "--tier-red",
    }
    for cls, color, token in bands:
        assert _norm(color) == _norm(_resolve(token)), f"{cls}: {color} is not {token}"
    # The CSS variable is written as var(token, literal), never the bare literal.
    assert "'var(' + band.token + ', ' + band.color + ')'" in src


def test_rt_elite_keeps_the_blue_it_always_painted():
    """--tier-blue is a brighter step. Moving RT A onto it is a visible change, not hygiene."""
    assert _norm(_resolve("--blue")) == _norm("#4A90D9")
    assert _norm(_resolve("--tier-blue")) != _norm(_resolve("--blue"))


def test_position_colours_equal_their_tokens():
    shared = (STATIC / "js" / "phaser" / "utils" / "matchupsUiShared.js").read_text()
    block = shared[shared.index("export const POSITION_COLORS"):]
    block = block[: block.index("});")]
    literal = dict(re.findall(r"\b(PG|SG|SF|PF|C):\s*\"(#[0-9A-Fa-f]{6})\"", block))
    assert set(literal) == {"PG", "SG", "SF", "PF", "C"}
    for pos, color in literal.items():
        assert _norm(color) == _norm(_resolve(f"--pos-{pos.lower()}")), pos

    sim = (STATIC / "js" / "phaser" / "utils" / "simGamePresentation.js").read_text()
    posc = {pos: (token, fallback) for pos, token, fallback in
            re.findall(r"\b(PG|SG|SF|PF|C): 'var\((--pos-[a-z]+), (#[0-9A-Fa-f]{6})\)'", sim)}
    assert set(posc) == {"PG", "SG", "SF", "PF", "C"}
    for pos, (token, fallback) in posc.items():
        assert token == f"--pos-{pos.lower()}"
        assert _norm(fallback) == _norm(_resolve(token)), pos


def _fallback_pairs(css: str):
    """Yield (token, fallback) for every var(--token, fallback), with nested parentheses."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for match in re.finditer(r"var\((--[a-z0-9-]+)\s*,", css):
        depth, i = 1, match.end()
        while depth and i < len(css):
            depth += {"(": 1, ")": -1}.get(css[i], 0)
            i += 1
        yield match.group(1), css[match.end(): i - 1].strip()


def test_injected_sheets_fall_back_to_the_token_value():
    for rel in ("css/gob-buttons.css", "css/rt-buckets.css"):
        pairs = list(_fallback_pairs((STATIC / rel).read_text()))
        assert pairs, rel
        for token, fallback in pairs:
            assert token in TOKENS, f"{rel}: {token} is not a token"
            assert _norm(fallback) == _norm(_resolve(token)), f"{rel}: {token} falls back to {fallback}"


def test_button_sheet_has_no_colour_the_tokens_cover():
    css = re.sub(r"/\*.*?\*/", "", (STATIC / "css" / "gob-buttons.css").read_text(), flags=re.S)
    # Outside var() fallbacks, the only literals left are the three with no token.
    bare = re.sub(r"var\([^()]*(?:\([^()]*\)[^()]*)*\)", "", css)
    literals = sorted(set(m.lower() for m in re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)", bare)))
    assert literals == ["#15181f", "#4dff3f", "#ffa84a", "rgba(255, 255, 255, 0.85)"]


def test_navy_aliases_are_tokens_and_only_tokens():
    for name in ("--you", "--you-soft", "--you-line", "--you-ink"):
        assert name in TOKENS
    assert _norm(TOKENS["--you"]) == _norm("var(--navy)")
    assert _norm(TOKENS["--you-soft"]) == _norm("color-mix(in srgb,var(--navy) 28%,transparent)")
    assert _norm(TOKENS["--you-line"]) == _norm("color-mix(in srgb,var(--navy) 55%,transparent)")
    assert _norm(TOKENS["--you-ink"]) == _norm("color-mix(in srgb,var(--text-100) 82%,var(--navy))")
    spine = re.sub(r"/\*.*?\*/", "", (STATIC / "recruiting-spine.css").read_text(), flags=re.S)
    assert not re.search(r"--you(-soft|-line|-ink)?\s*:", spine)
    assert spine.count("var(--you") >= 15


def test_tier_digit_comment_states_the_real_rule():
    assert "0–16" not in TOKENS_CSS
    assert "floor(raw / 10), no upper cap" in TOKENS_CSS
    display = (STATIC / "js" / "utils" / "attributeDisplay.js").read_text()
    assert "return Math.floor(n / 10);" in display
    assert "Math.min" not in display


def test_repo_instructions_point_the_colour_law_at_the_styleguide():
    text = (ROOT / "CLAUDE.md").read_text()
    assert "Styleguide.md#colour-law" in text
    assert "Colour law, SFX routing" not in text
