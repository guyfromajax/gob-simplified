"""Split-phase franchise training state helpers."""

from BackEnd.utils.franchise_training_state import (
    franchise_training_fully_complete_for_week,
    franchise_user_training_applied_for_week,
)


def test_legacy_single_shot_fully_complete():
    ts = {"training_completed": True, "week": 3}
    assert franchise_training_fully_complete_for_week(ts, 3) is True
    assert franchise_user_training_applied_for_week(ts, 3) is False


def test_split_path_not_complete_until_cpu_training():
    ts = {
        "training_completed": False,
        "week": 2,
        "user_training_applied_week": 2,
    }
    assert franchise_training_fully_complete_for_week(ts, 2) is False
    assert franchise_user_training_applied_for_week(ts, 2) is True

    ts_done = {
        **ts,
        "training_completed": True,
        "cpu_training_complete_week": 2,
    }
    assert franchise_training_fully_complete_for_week(ts_done, 2) is True


def test_week_mismatch_not_complete():
    ts = {"training_completed": True, "week": 2, "user_training_applied_week": 2, "cpu_training_complete_week": 2}
    assert franchise_training_fully_complete_for_week(ts, 3) is False


def test_retired_cpu_completion_field_is_not_authoritative():
    ts = {
        "training_completed": True,
        "week": 2,
        "user_training_applied_week": 2,
        "cpu_distant_complete_week": 2,
    }
    assert franchise_training_fully_complete_for_week(ts, 2) is False


def test_only_neutral_cpu_training_route_is_registered():
    from BackEnd.api.api import app

    # Use FastAPI's public, fully-expanded route schema.  Inspecting app.routes is
    # version-dependent: some Starlette releases retain included routers as
    # pathless container objects instead of flattening their child routes.
    paths = set(app.openapi().get("paths", {}))
    assert "/franchise/run-training/cpu-train" in paths
    assert "/franchise/run-training/distant-cpu" not in paths
