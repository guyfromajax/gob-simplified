import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_team_presentation_fallback_chooses_the_higher_contrast_brand_color():
    completed = subprocess.run(
        ["node", str(ROOT / "tests/js/runTeamPresentationColor.mjs")],
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(completed.stdout.strip().splitlines()[-1])

    assert result["readablePrimaryStaysPrimary"] == "#f79420"
    assert result["brighterSecondaryWinsFallback"] == "#f2c94c"
    # Lancaster: dark orange misses the existing threshold, but still contrasts
    # much better than its black secondary on the presentation background.
    assert result["darkerSecondaryLosesFallback"] == "#d24a1b"
    assert result["invalidPrimaryUsesSecondary"] == "#f2c94c"
