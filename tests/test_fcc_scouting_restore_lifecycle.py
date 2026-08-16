from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FCC_JS = ROOT / "FrontEnd" / "static" / "franchise-command-center.js"


def test_restored_scouting_tab_waits_for_fcc_initialization():
    """A URL-restored coaches tab must not race asynchronous FCC hydration."""
    source = FCC_JS.read_text(encoding="utf-8")

    startup_assignment = "fccInitializationPromise = init();"
    tab_initialization = "CommandCenterTabs.initCommandCenterTabs({"
    scouting_wait = "await fccInitializationPromise;"
    opponent_resolution = (
        "resolveUpcomingOpponentFromMatchup(commandCenterTopDataCache)"
    )

    assert startup_assignment in source
    assert scouting_wait in source
    assert source.index(startup_assignment) < source.index(tab_initialization)

    scouting_function = source[source.index("async function renderScoutingTab()") :]
    assert scouting_function.index(scouting_wait) < scouting_function.index(
        opponent_resolution
    )
