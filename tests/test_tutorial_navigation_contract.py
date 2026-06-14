"""Static guards for the tutorial back-navigation contract."""

from pathlib import Path


ROOT = Path(__file__).parents[1]
NAV_SOURCE = ROOT / "FrontEnd/static/js/shared/gobTutorialNav.js"
HUB_SOURCE = ROOT / "FrontEnd/static/tutorial.html"


def test_external_entry_replaces_stale_tutorial_origin():
    source = NAV_SOURCE.read_text()
    remember_origin = source[
        source.index("function rememberOrigin()")
        : source.index("function consumeOrigin()")
    ]

    assert "if (ref && !fromTutorial)" in remember_origin
    assert "!sessionStorage.getItem(ORIGIN_KEY)" not in remember_origin
    assert "sessionStorage.setItem(ORIGIN_KEY, ref)" in remember_origin


def test_lesson_and_hub_back_actions_have_distinct_routes():
    source = NAV_SOURCE.read_text()
    go_back = source[
        source.index("function goBack()")
        : source.index("/* ---- icon library")
    ]

    assert 'if (!isTutorialHub())' in go_back
    assert "location.href = HUB" in go_back
    assert "var origin = consumeOrigin()" in go_back
    assert "location.href = origin" in go_back


def test_hub_exit_consumes_saved_origin():
    source = NAV_SOURCE.read_text()
    consume_origin = source[
        source.index("function consumeOrigin()")
        : source.index("function goBack()")
    ]

    assert "sessionStorage.removeItem(ORIGIN_KEY)" in consume_origin


def test_hub_and_lesson_labels_match_navigation_contract():
    nav_source = NAV_SOURCE.read_text()
    hub_source = HUB_SOURCE.read_text()

    assert "> Back</button>" in hub_source
    assert "Back To Tutorial Home" in nav_source
    assert "Back to game" not in hub_source
