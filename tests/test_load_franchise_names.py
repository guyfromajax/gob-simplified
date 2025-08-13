import json
import logging

import pytest

from BackEnd.models.franchise_manager import load_franchise_names


def test_load_franchise_names_env_override(tmp_path, monkeypatch, caplog):
    data = {"first_names": ["Alpha"], "last_names": ["Beta"]}
    file = tmp_path / "names.json"
    file.write_text(json.dumps(data))
    monkeypatch.setenv("FRANCHISE_NAMES_FILE", str(file))
    caplog.set_level(logging.INFO)

    first, last = load_franchise_names()

    assert first == ["Alpha"]
    assert last == ["Beta"]
    assert str(file.resolve()) in caplog.text


def test_load_franchise_names_missing_file(monkeypatch, caplog):
    monkeypatch.setenv("FRANCHISE_NAMES_FILE", "/no/such/file.json")
    caplog.set_level(logging.WARNING)
    with pytest.raises(FileNotFoundError):
        load_franchise_names()
    assert "not found" in caplog.text


def test_load_franchise_names_invalid_json(tmp_path, monkeypatch, caplog):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not json")
    monkeypatch.setenv("FRANCHISE_NAMES_FILE", str(bad_file))
    caplog.set_level(logging.WARNING)
    with pytest.raises(ValueError):
        load_franchise_names()
    assert "Failed to parse franchise names JSON" in caplog.text
