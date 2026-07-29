"""Pass-2-step-2 wiring gates: the growth profile survives a rollover, nobody
develops twice, and the offseason event tracks the ladder. Pure (no DB)."""
import inspect
import random

import pytest

from BackEnd.utils import player_development as dev
from BackEnd.utils.player_generation import JH_ANCHOR_BY_TIER


def _fpd_from_player(pl: dict) -> dict:
    """Shape an in-memory career player as an FPD document (what finish_season
    forward-copies), carrying the development pointer fields."""
    return {
        "player_id": "p1",
        "meta": {"first_name": "Test", "last_name": "Player",
                 "height": pl["height"], "weight": pl["weight"], "year": pl["class_year"]},
        "attributes": dict(pl["attributes"]),
        "position_ratings": dict(pl["position_ratings"]),
        "development": pl["development"],
        "entry_tier": pl["tier"],
        "position_intent": pl["position"],
    }


def test_development_survives_rollover():
    """NON-NEGOTIABLE: a player's development profile is intact after a rollover
    and does not re-roll — same peaks, same timing, same ch_seed."""
    rng = random.Random(1)
    pl = dev.simulate_career("SF", "Good", 72, rng)
    # Snapshot his frozen profile, then simulate the FR->SO rollover step.
    doc = _fpd_from_player(pl)
    doc["meta"]["year"] = "sophomore"
    before = dict(doc["development"])
    result = dev.develop_rollover(doc, "sophomore", random.Random(2))
    assert result["development"]["peak_count"] == before["peak_count"]
    assert result["development"]["peak_rungs"] == before["peak_rungs"]
    assert result["development"]["family_timing"] == before["family_timing"]
    assert result["development"]["ch_seed"] == before["ch_seed"]
    assert result["backfilled"] is False  # already had a profile → not re-rolled


def test_lazy_backfill_rolls_once_on_remaining_rungs():
    """A legacy doc with NO development gets one rolled + returned to persist; peaks
    land only on remaining rungs; a second pass with the persisted profile does not
    re-roll (career-stable)."""
    doc = {
        "player_id": "legacy", "meta": {"height": 79, "weight": 210, "year": "junior"},
        "attributes": {"anchor_CH": 90, "CH": 90, "SC": 50, "SH": 50, "ID": 50, "OD": 50,
                       "PS": 50, "BH": 50, "RB": 50, "ST": 50, "AG": 50, "IQ": 50, "FT": 50, "ND": 50},
        "position_ratings": {"PG": 30, "SG": 35, "SF": 55, "PF": 40, "C": 30},
        # no development / entry_tier / position_intent
    }
    r1 = dev.develop_rollover(doc, "junior", random.Random(5))
    assert r1["backfilled"] is True
    assert r1["development"] is not None
    # rolling onto JR → remaining rungs are JR, SR; no peak may sit on FR/SO.
    assert all(rr in ("JR", "SR") for rr in r1["development"]["peak_rungs"])
    # persist it, roll again → uses stored profile, no re-roll.
    doc["development"] = r1["development"]
    doc["entry_tier"] = r1["entry_tier"]
    doc["position_intent"] = r1["position_intent"]
    r2 = dev.develop_rollover(doc, "junior", random.Random(6))
    assert r2["backfilled"] is False
    assert r2["development"]["peak_rungs"] == r1["development"]["peak_rungs"]


def test_offseason_hits_ladder_not_doubled():
    """The offseason event is the SOLE grower: a 0-peak Average player rolling onto
    each rung lands on the ladder RT, not the ladder + a leftover camp bonus."""
    rng = random.Random(0)
    # Force 0 peaks by driving develop_one_offseason directly on a fresh JH player.
    pl = dev.init_career("SG", "Average", 3, rng)[0]  # low CH → likely 0-1 peaks
    profile = dict(pl["development"]); profile["peak_rungs"] = []  # pin 0-peak
    anchor = JH_ANCHOR_BY_TIER["Average"]
    ladder = {"FR": anchor * 1.17, "SO": anchor * 1.37, "JR": anchor * 1.52, "SR": anchor * 1.70}
    player = {"attributes": dict(pl["attributes"]), "height": pl["height"], "weight": pl["weight"],
              "position": "SG", "training_position": "SG", "jh_anchor": anchor,
              "position_ratings": dict(pl["position_ratings"])}
    for rung in dev.RUNG_TRANSITIONS:
        dev.develop_one_offseason(player, rung, profile, random.Random(9))
        # within a couple RT of the 0-peak ladder — no doubled growth on top
        assert abs(player["position_ratings"]["SG"] - round(ladder[rung])) <= 3, rung


def test_camp_growth_calls_removed_from_training_path():
    """No double-develop: the offseason event owns the CH bonus, year bonus and
    FR/SO HT/WT, so the training-camp path must no longer call any of them."""
    from BackEnd.models import training_execution_v2 as tev
    src = inspect.getsource(tev.apply_training_points)
    for gone in ("_apply_training_camp_bonus(",
                 "_apply_training_camp_height_weight_bonuses("):
        assert gone not in src, f"camp still calls {gone} — players would develop twice"


def test_weekly_decay_reduced():
    """In-season decay came down substantially (§7.2) — no year worse than -2/attr."""
    from BackEnd.models.training_execution_v2 import PRE_TRAINING_DECAY_BY_YEAR
    for year, (lo, hi) in PRE_TRAINING_DECAY_BY_YEAR.items():
        assert lo >= -2, year
        assert hi <= 0, year
