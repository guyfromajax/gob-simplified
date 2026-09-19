import importlib

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from BackEnd.local_identity import LOCAL_USER_ID
from BackEnd.loopback_app import configure_loopback
from BackEnd.loopback_env import is_loopback
from BackEnd.pool_policy import desktop_worker_count
from BackEnd.runtime_paths import bundle_path, bundle_root
from BackEnd.utils.auth import get_current_user


def test_flask_app_is_deleted():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("BackEnd.flask_app")


def test_bundle_root_honors_override(monkeypatch, tmp_path):
    monkeypatch.setenv("GOB_BUNDLE_ROOT", str(tmp_path))
    assert bundle_root() == tmp_path.resolve()
    font = bundle_path("BackEnd", "assets", "fonts", "LiberationSans-Bold.ttf")
    assert font == tmp_path.resolve() / "BackEnd" / "assets" / "fonts" / "LiberationSans-Bold.ttf"


def test_bundled_font_exists_in_source_tree():
    font = bundle_path("BackEnd", "assets", "fonts", "LiberationSans-Bold.ttf")
    assert font.is_file(), font


def test_names_and_walk_on_manifests_resolve():
    assert bundle_path("BackEnd", "data", "walk_on_portraits_manifest.json").is_file()
    names = bundle_path("BackEnd", "data", "names")
    assert names.is_dir()


def test_desktop_pool_policy_reserves_live_game_cores():
    assert desktop_worker_count(cores=4, ram_mb=8192) == 2
    assert desktop_worker_count(cores=8, ram_mb=16384) == 4
    assert desktop_worker_count(cores=2, ram_mb=4096) == 1
    assert desktop_worker_count(cores=32, ram_mb=65536) == 4


def test_pool_env_override_wins(monkeypatch):
    from BackEnd.utils.cpu_week_pool import pool_worker_count

    monkeypatch.setenv("FRANCHISE_CPU_SIM_POOL_WORKERS", "3")
    assert pool_worker_count() == 3


def test_local_principal_override_does_not_strip_depends():
    app = FastAPI()

    @app.get("/who")
    async def who(user=Depends(get_current_user)):
        return user

    configure_loopback(app)
    body = TestClient(app).get("/who").json()
    assert body["user_id"] == LOCAL_USER_ID
    assert body["email"] == "local@desktop"


def test_health_loopback_fields(monkeypatch):
    monkeypatch.setenv("GOB_LOOPBACK", "1")
    from BackEnd.api._bootstrap import health_check

    body = health_check()
    assert body["status"] == "healthy"
    assert body["profile"] == "loopback"
    assert body["ready"] is True
    assert body["persistence"] == "sqlite" or body["persistence"]


def test_is_loopback_reads_profile(monkeypatch):
    monkeypatch.delenv("GOB_LOOPBACK", raising=False)
    monkeypatch.setenv("GOB_BUILD_PROFILE", "desktop")
    assert is_loopback() is True
