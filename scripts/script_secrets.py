"""External secret-file boundary for local operational scripts."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
R2_CONFIG_PATH = Path.home() / ".config" / "gob" / "r2.env"
R2_KEYS = (
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_ENDPOINT",
    "R2_BUCKET",
)


class ScriptSecretError(RuntimeError):
    """Raised when script-only secret configuration is missing or unsafe."""


def _mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def _parse_external_file(path: Path) -> dict[str, str]:
    if not path.is_absolute():
        raise ScriptSecretError(f"Secret file path must be absolute: {path}")
    if path.is_symlink() or not path.is_file():
        raise ScriptSecretError(f"Missing regular external secret file: {path}")
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        pass
    else:
        raise ScriptSecretError(f"Secret file must live outside the repository: {resolved}")
    mode = _mode(resolved)
    if mode != 0o600:
        raise ScriptSecretError(
            f"Secret file must have mode 0600; found {mode:04o} at {resolved}"
        )

    values: dict[str, str] = {}
    for raw_line in resolved.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ScriptSecretError(f"Malformed secret-file line in {resolved}")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_r2_credentials(path: Path | None = None) -> dict[str, str]:
    """Return complete R2 credentials from process env or external mode-0600 file."""
    process_values = {key: str(os.environ.get(key) or "").strip() for key in R2_KEYS}
    present = [key for key, value in process_values.items() if value]
    if present:
        missing = [key for key, value in process_values.items() if not value]
        if missing:
            raise ScriptSecretError(
                "Partial R2 process configuration; missing: " + ", ".join(missing)
            )
        return process_values

    config_path = path or R2_CONFIG_PATH
    values = _parse_external_file(config_path)
    missing = [
        key
        for key in R2_KEYS
        if not values.get(key) or values[key].strip().upper() == "REPLACE_ME"
    ]
    if missing:
        raise ScriptSecretError(
            f"Missing R2 values in {config_path}: " + ", ".join(missing)
        )
    return {key: values[key] for key in R2_KEYS}
