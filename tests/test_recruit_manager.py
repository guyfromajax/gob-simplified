import json
from importlib import resources

from BackEnd.models.franchise_manager import RecruitManager


def test_recruit_manager_loads_default_names(monkeypatch):
    monkeypatch.delenv("FRANCHISE_NAMES_FILE", raising=False)
    rm = RecruitManager(db=None)
    resource_path = resources.files("BackEnd").joinpath("data", "names", "franchise_names.json")
    with resource_path.open("r") as f:
        payload = json.load(f)

    fallback_first = ["Jalen", "Marcus", "Tyrese", "Zion", "Cade"]
    fallback_last = ["Walker", "Jackson", "Robinson", "Wright", "Anderson"]

    assert rm.first_names == payload["first_names"]
    assert rm.last_names == payload["last_names"]
    assert rm.first_names != fallback_first
    assert rm.last_names != fallback_last
