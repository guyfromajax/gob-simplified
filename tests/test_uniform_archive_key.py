"""Contract for the cross-franchise uniform archive key.

The key must be determined by exactly what determines the painted pixels — the
portrait (image_id) and the team's look (primary, secondary, mascot) — and by
nothing else. These assertions encode the two failure modes that motivated the
design:

  1. Keying by player_id repaints a byte-identical image per franchise, forever.
  2. Keying by colour alone collapses teams that share a palette but not a mascot,
     serving the wrong wordmark. Measured on the live league: 128 teams occupy only
     34 distinct palettes, so colour-only keying would mis-serve 94 of them.
"""
import pytest

from BackEnd.utils.uniform_archive import (
    UNIFORM_KEY_LEN,
    color_key,
    uniform_key,
    uniform_object_key,
)

IID = "61461c69-efe8-44bb-8087-8bafc6edadf6"


def test_formatting_differences_do_not_fork_the_key():
    """'#1C2A44' and '1c2a44' paint the same image and must share one object."""
    assert uniform_key(IID, "#1C2A44", "#C8A951", "Wildcats") == uniform_key(
        IID, "1c2a44", "c8a951", "  wildcats "
    )


def test_same_palette_different_mascot_are_distinct():
    """The mascot is stamped into the jersey, so it must be part of the identity."""
    a = uniform_key(IID, "#2a2168", "#f2d045", "Knights")
    b = uniform_key(IID, "#2a2168", "#f2d045", "Warriors")
    assert a != b


def test_same_palette_and_mascot_share_one_object():
    """Identical pixels SHOULD share — two 'Knights' on one palette is not a bug."""
    a = uniform_key(IID, "#2a2168", "#f2d045", "Knights")
    b = uniform_key(IID, "#2a2168", "#f2d045", "knights")
    assert a == b


@pytest.mark.parametrize(
    "primary,secondary,mascot",
    [("#7c2b24", "#f2d045", "Knights"), ("#2a2168", "#e39649", "Knights")],
)
def test_recolour_forks_the_key(primary, secondary, mascot):
    """A Team Builder rebrand must produce a NEW object, never reuse the stale one.

    The legacy players/master/<player_id>.png key had no colour component, so both
    paint paths skipped on exists() and a rebranded team kept old colours forever.
    """
    base = uniform_key(IID, "#2a2168", "#f2d045", "Knights")
    assert uniform_key(IID, primary, secondary, mascot) != base


def test_different_portrait_forks_the_key():
    other = "42fe2984-a157-46fa-886d-1d853ad1b6ee"
    assert uniform_key(IID, "#2a2168", "#f2d045", "Knights") != uniform_key(
        other, "#2a2168", "#f2d045", "Knights"
    )


def test_player_id_is_not_an_input():
    """Whoever wears it cannot affect the key — that is the entire point."""
    assert uniform_key(IID, "#2a2168", "#f2d045", "Knights").startswith(IID + "__")


def test_unpaintable_inputs_return_none():
    assert uniform_key(None, "#2a2168", "#f2d045", "Knights") is None
    assert uniform_key("", "#2a2168", "#f2d045", "Knights") is None
    assert uniform_key(IID, "not-a-colour", "#f2d045", "Knights") is None


def test_key_shape():
    k = uniform_key(IID, "#2a2168", "#f2d045", "Knights")
    assert k.count("__") == 1
    assert len(k.split("__")[1]) == UNIFORM_KEY_LEN
    assert uniform_object_key(k) == f"uniforms/{k}.png"


def test_missing_secondary_is_tolerated_but_distinct():
    """Secondary may be absent; that is a different look, not the same one."""
    assert uniform_key(IID, "#2a2168", None, "Knights") != uniform_key(
        IID, "#2a2168", "#f2d045", "Knights"
    )


def test_color_key_is_pinned_and_process_stable():
    """sha256-based, not hash() — PYTHONHASHSEED must never reach an object key.

    Pinned to a literal because the key is a STORAGE ADDRESS: if this value ever
    changes, every archived object is orphaned and the whole league silently
    repaints. A failure here means someone altered the hash basis or normalisation.
    """
    assert color_key("#2a2168", "#f2d045", "Knights") == "626fc38a5722"
    assert len(color_key("#2a2168", "#f2d045", "Knights")) == UNIFORM_KEY_LEN
