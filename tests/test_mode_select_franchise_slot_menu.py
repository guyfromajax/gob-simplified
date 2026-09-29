"""Delete stays a disclosure, not a control competing with Enter.

Ch7 moved the program slots out of mode-select.js into the Home Base module,
so these read js/shared/homeBase.js now. The rule they guard is older than the
rewrite: deleting a program is destructive and rare, so it hides behind a
menu, never sits in the door's action row, and never fires the door's own
navigation on the way.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "FrontEnd/static/js/shared/homeBase.js").read_text(encoding="utf-8")


def test_delete_action_lives_in_disclosure_panel_not_the_door():
    slots_start = JS.index("function slotsHtml(")
    slots_end = JS.index("function careerStripHtml(", slots_start)
    slot_markup = JS[slots_start:slots_end]

    # The trigger is a menu disclosure in the slot header.
    assert "data-hb-more" in slot_markup
    assert 'aria-haspopup="menu"' in slot_markup
    assert 'aria-expanded="false"' in slot_markup

    # Delete is never rendered with the slot; only openMenu() emits it.
    assert "data-hb-delete" not in slot_markup

    door_start = JS.index("function doorHtml(")
    door_end = JS.index("function vacantHtml(", door_start)
    assert "data-hb-delete" not in JS[door_start:door_end]

    menu_start = JS.index("function openMenu(")
    menu_end = JS.index("function confirmHost(", menu_start)
    assert "data-hb-delete" in JS[menu_start:menu_end]
    assert "pop.setAttribute('role', 'menu');" in JS[menu_start:menu_end]
    assert 'role="menuitem"' in JS[menu_start:menu_end]


def test_popover_escapes_the_card_by_construction():
    slots_start = JS.index("function slotsHtml(")
    slots_end = JS.index("function careerStripHtml(", slots_start)
    slot_markup = JS[slots_start:slots_end]

    # The old page clipped the popover inside the card and needed overflow and
    # border-radius overrides to let it out. Here the header holding the
    # trigger is a sibling of the door, so there is nothing to escape.
    header_at = slot_markup.index('<div class="slot-h">')
    door_at = slot_markup.index("doorHtml(slot)")
    assert header_at < door_at

    # And the panel mounts on the slot, not on the door.
    menu_start = JS.index("function openMenu(")
    assert "slot.appendChild(pop);" in JS[menu_start:JS.index("function confirmHost(", menu_start)]


def test_disclosure_behavior_protects_card_navigation_and_keyboard_focus():
    # Opening the menu must not bubble into the door's whole-card navigation.
    assert "if (more) { ev.preventDefault(); ev.stopPropagation(); openMenu(more); return; }" in JS

    # Escape closes the menu and hands focus back to the trigger that opened it.
    assert "if (ev.key === 'Escape' && openMenuSlot) { ev.preventDefault(); closeMenu(true); return; }" in JS
    assert 'root.querySelector(\'[data-hb-more][data-slot="\' + openMenuSlot + \'"]\')' in JS
    assert "if (back) back.focus();" in JS

    # Choosing Delete closes the menu before the confirm takes over.
    delete_at = JS.index("var del = t.closest('[data-hb-delete]');")
    assert "closeMenu(false);" in JS[delete_at:delete_at + 400]


def test_confirm_dialog_traps_focus_and_restores_it():
    assert "if (ev.key === 'Escape') { ev.preventDefault(); closeConfirm(); return; }" in JS
    assert "if (ev.key === 'Tab') { trapFocus(ev); }" in JS
    # Focus returns to whatever opened the dialog, if it is still on the page.
    assert "confirmReturnFocus = document.activeElement;" in JS
    assert "document.contains(confirmReturnFocus)" in JS
