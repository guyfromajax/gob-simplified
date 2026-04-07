import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from BackEnd.constants import fast_break_play_types as fb_types


def test_non_dreb_fast_break_entry_stays_after_steal():
    key = fb_types.play_key_for_fast_break_entry(False, {"fast_break": {"triangle": 100}})
    assert key == fb_types.AFTER_STEAL


def test_dreb_fast_break_entry_uses_playbook_weights(monkeypatch):
    captured = {}

    def fake_choices(population, weights, k):
        captured["population"] = population
        captured["weights"] = weights
        captured["k"] = k
        return [fb_types.TRIANGLE]

    monkeypatch.setattr(fb_types.random, "choices", fake_choices)
    key = fb_types.play_key_for_fast_break_entry(
        True,
        {
            "fast_break": {
                "covert_release": 33,
                "rim_runner": 33,
                "triangle": 34,
            }
        },
    )

    assert key == fb_types.TRIANGLE
    assert captured["population"] == [
        fb_types.COVERT_RELEASE,
        fb_types.RIM_RUNNER,
        fb_types.TRIANGLE,
    ]
    assert captured["weights"] == [33, 33, 34]
    assert captured["k"] == 1


def test_dreb_fast_break_entry_falls_back_to_default_weights(monkeypatch):
    captured = {}

    def fake_choices(population, weights, k):
        captured["weights"] = weights
        return [fb_types.COVERT_RELEASE]

    monkeypatch.setattr(fb_types.random, "choices", fake_choices)
    key = fb_types.play_key_for_fast_break_entry(True, {"fast_break": {}})

    assert key == fb_types.COVERT_RELEASE
    assert captured["weights"] == [33, 33, 34]
