"""
Parse historical alpha OTP codes from used_otp_codes.md (migration only).
"""

from __future__ import annotations

import re
from pathlib import Path

OTP_CODE_PATTERN = re.compile(r"^([A-Z0-9]{10})(?:\s|$|\s-)")

DEFAULT_MARKDOWN_PATH = (
    Path(__file__).resolve().parents[2]
    / "_documentation_master"
    / "projects"
    / "used_otp_codes.md"
)


def parse_used_otp_codes_from_text(text: str) -> list[str]:
    """Extract unique 10-char OTP codes from markdown body text."""
    seen: set[str] = set()
    ordered: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = OTP_CODE_PATTERN.match(line)
        if not match:
            continue
        code = match.group(1)
        if code not in seen:
            seen.add(code)
            ordered.append(code)
    return ordered


def parse_used_otp_codes_from_file(path: Path | None = None) -> list[str]:
    markdown_path = path or DEFAULT_MARKDOWN_PATH
    text = markdown_path.read_text(encoding="utf-8")
    return parse_used_otp_codes_from_text(text)
