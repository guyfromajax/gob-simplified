"""Team-id maps are identity; one build per finalize / persist batch."""

from __future__ import annotations

from bson import ObjectId

from BackEnd.utils import stat_updater


def test_maps_built_once_inside_finalize_scope(monkeypatch):
    fid = ObjectId()
    calls = {"n": 0}

    def fake(_franchise_id):
        calls["n"] += 1
        return ({"Lancaster": "1"}, {"LANCASTER": "1"})

    monkeypatch.setattr(stat_updater, "_build_franchise_team_maps_from_ftd_uncached", fake)
    with stat_updater.franchise_team_maps_scope():
        a = stat_updater._build_franchise_team_maps_from_ftd(fid)
        b = stat_updater._build_franchise_team_maps_from_ftd(str(fid))
        c = stat_updater._build_franchise_team_maps_from_ftd(fid)
    assert calls["n"] == 1
    assert a == b == c


def test_maps_rebuild_without_scope(monkeypatch):
    fid = ObjectId()
    calls = {"n": 0}

    def fake(_franchise_id):
        calls["n"] += 1
        return ({}, {})

    monkeypatch.setattr(stat_updater, "_build_franchise_team_maps_from_ftd_uncached", fake)
    stat_updater._build_franchise_team_maps_from_ftd(fid)
    stat_updater._build_franchise_team_maps_from_ftd(fid)
    assert calls["n"] == 2
