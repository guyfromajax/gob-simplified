"""Single bundle-root for source checkouts and Nuitka standalone.

Nuitka compiles modules into the binary and does not create ``services/`` or
other package directories. ``__file__ + '../assets/...'`` then fails
``os.path.exists`` because the kernel will not walk a missing component.
Resolve everything from one root that exists in both modes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _compiled() -> bool:
    return bool(getattr(sys, "frozen", False) or getattr(sys, "__compiled__", None))


def bundle_root() -> Path:
    override = os.environ.get("GOB_BUNDLE_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    if _compiled():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundle_path(*parts: str | os.PathLike[str]) -> Path:
    return bundle_root().joinpath(*parts)
