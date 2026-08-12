"""TEAM_BUILDER_ENABLED authoring gate."""
from __future__ import annotations

from fastapi.testclient import TestClient

from BackEnd.api import api
from BackEnd.utils.team_builder_feature import team_builder_enabled


client = TestClient(api.app)


def test_team_builder_enabled_defaults_true(monkeypatch):
    monkeypatch.delenv("TEAM_BUILDER_ENABLED", raising=False)
    assert team_builder_enabled() is True


def test_team_builder_enabled_false_aliases(monkeypatch):
    for value in ("0", "false", "FALSE", "no", "off"):
        monkeypatch.setenv("TEAM_BUILDER_ENABLED", value)
        assert team_builder_enabled() is False, value


def test_team_builder_enabled_true_aliases(monkeypatch):
    for value in ("1", "true", "yes", "on", "weird"):
        monkeypatch.setenv("TEAM_BUILDER_ENABLED", value)
        assert team_builder_enabled() is True, value


def test_app_config_exposes_flag(monkeypatch):
    monkeypatch.setenv("TEAM_BUILDER_ENABLED", "false")
    res = client.get("/app-config")
    assert res.status_code == 200
    assert res.json().get("teamBuilderEnabled") is False


def test_team_builder_routes_404_when_disabled(monkeypatch):
    monkeypatch.setenv("TEAM_BUILDER_ENABLED", "false")
    res = client.get("/franchise/team-builder/league-context")
    assert res.status_code == 404
    assert "not available" in str(res.json().get("detail", "")).lower()


def test_team_builder_routes_not_feature_flag_404_when_enabled(monkeypatch):
    monkeypatch.setenv("TEAM_BUILDER_ENABLED", "true")
    res = client.get("/franchise/team-builder/league-context")
    # Auth may reject the call; the feature-flag middleware must not.
    if res.status_code == 404:
        assert "not available" not in str(res.json().get("detail", "")).lower()
