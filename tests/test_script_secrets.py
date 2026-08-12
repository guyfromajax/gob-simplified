from pathlib import Path

import pytest

from scripts.script_secrets import R2_KEYS, ScriptSecretError, load_r2_credentials


def _clear_r2(monkeypatch) -> None:
    for key in R2_KEYS:
        monkeypatch.delenv(key, raising=False)


def _values() -> dict[str, str]:
    return {
        "R2_ACCESS_KEY_ID": "access-placeholder",
        "R2_SECRET_ACCESS_KEY": "secret-placeholder",
        "R2_ENDPOINT": "https://example.invalid",
        "R2_BUCKET": "bucket-placeholder",
    }


def _write(path: Path, values: dict[str, str], mode: int = 0o600) -> None:
    path.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()) + "\n",
        encoding="utf-8",
    )
    path.chmod(mode)


def test_complete_process_configuration_wins(monkeypatch, tmp_path: Path):
    values = _values()
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    assert load_r2_credentials(tmp_path / "missing.env") == values


def test_partial_process_configuration_fails_closed(monkeypatch):
    _clear_r2(monkeypatch)
    monkeypatch.setenv("R2_BUCKET", "only-one")

    with pytest.raises(ScriptSecretError, match="Partial R2 process configuration"):
        load_r2_credentials()


def test_external_mode_0600_configuration_loads(monkeypatch, tmp_path: Path):
    _clear_r2(monkeypatch)
    path = tmp_path / "r2.env"
    values = _values()
    _write(path, values)

    assert load_r2_credentials(path) == values


def test_external_configuration_rejects_unsafe_permissions(monkeypatch, tmp_path: Path):
    _clear_r2(monkeypatch)
    path = tmp_path / "r2.env"
    _write(path, _values(), mode=0o644)

    with pytest.raises(ScriptSecretError, match="mode 0600"):
        load_r2_credentials(path)


def test_external_configuration_rejects_repository_path(monkeypatch):
    _clear_r2(monkeypatch)
    path = Path(__file__).resolve().parents[1] / "tmp" / "r2-test.env"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _write(path, _values())
        with pytest.raises(ScriptSecretError, match="outside the repository"):
            load_r2_credentials(path)
    finally:
        path.unlink(missing_ok=True)

