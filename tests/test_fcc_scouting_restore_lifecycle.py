from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCOUTING_VIEW = ROOT / "FrontEnd" / "static" / "js" / "shared" / "views" / "scoutingView.js"
FCC_JS = ROOT / "FrontEnd" / "static" / "franchise-command-center.js"


def test_scouting_view_waits_for_fcc_initialization():
    """Prep scouting must not race asynchronous FCC hydration."""
    source = SCOUTING_VIEW.read_text(encoding="utf-8")
    fcc = FCC_JS.read_text(encoding="utf-8")

    assert "fccInitializationPromise = init();" in fcc
    assert "whenReady: () => fccInitializationPromise" in fcc
    assert "waitFcc" in source
    assert "prep.whenReady" in source
    assert source.index("waitFcc") < source.index("resolveOpponent")
