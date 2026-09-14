"""Zero-distance rattle hops must not take the step-end arrival-SFX fallback.

The FE guard lives in animationPlayback.js. This test pins the source
so a future edit cannot drop the kind check without failing here.
"""
from pathlib import Path


def test_rattle_hop_zero_distance_skips_arrival_fallback():
    src = (
        Path(__file__).resolve().parents[1]
        / "FrontEnd/static/js/phaser/animation/animationPlayback.js"
    ).read_text()
    assert 'hopKind !== "rattle_hop"' in src
    assert "tweenWouldEarlyReturn && hopKind !==" in src
