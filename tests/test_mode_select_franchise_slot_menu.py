from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "FrontEnd/static/mode-select.js").read_text(encoding="utf-8")
CSS = (ROOT / "FrontEnd/static/mode-select.css").read_text(encoding="utf-8")


def test_delete_action_lives_in_disclosure_panel_not_action_rail():
    menu_start = JS.index("'<div class=\"franchise-slot-menu\"")
    content_start = JS.index("'<div class=\"franchise-card-content\"")
    actions_start = JS.index("'<div class=\"franchise-card-actions\"")
    actions_end = JS.index("'</div>' +", actions_start)

    assert menu_start < content_start
    assert 'data-action=\"slot-menu\"' in JS[menu_start:content_start]
    assert 'aria-controls=\"franchise-slot-menu-pop-' in JS[menu_start:content_start]
    assert 'aria-haspopup=\"true\"' not in JS[menu_start:content_start]
    assert 'data-action=\"delete-franchise\"' in JS[menu_start:content_start]
    assert 'data-action=\"delete-franchise\"' not in JS[actions_start:actions_end]


def test_disclosure_behavior_protects_card_navigation_and_keyboard_focus():
    assert "event.stopPropagation();" in JS
    assert "if (event.target.closest('.franchise-slot-menu')) return;" in JS
    assert "if (event.key !== 'Escape') return;" in JS
    assert "if (trigger) trigger.focus();" in JS
    assert "closeAllSlotMenus();\n  pendingDeleteFranchise" in JS


def test_popover_can_escape_card_without_exposing_square_scrim():
    assert "body.mode-select-page .franchise-home-card-active {" in CSS
    assert "overflow: visible;" in CSS
    assert "border-radius: inherit;" in CSS
    assert "body.mode-select-page .franchise-slot-menu.is-open .franchise-slot-menu-pop" in CSS
    assert "padding-right: 42px;" in CSS
