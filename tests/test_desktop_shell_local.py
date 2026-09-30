"""Desktop splash and crash screens stay local — no remote URLs."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"
REMOTE_MARKERS = (
    "http://",
    "https://",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "//cdn",
)


def _assert_local(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for marker in REMOTE_MARKERS:
        assert marker not in text, f"{path.name} references {marker}"
    assert "assets/BebasNeuePro-Bold.otf" in text
    assert "assets/Barlow-latin.woff2" in text
    assert "assets/geekedout_logo.png" in text


def test_splash_html_has_no_remote_urls():
    _assert_local(DESKTOP / "splash.html")
    assert (DESKTOP / "assets" / "BebasNeuePro-Bold.otf").is_file()
    assert (DESKTOP / "assets" / "Barlow-latin.woff2").is_file()
    assert (DESKTOP / "assets" / "geekedout_logo.png").is_file()


def test_error_html_has_no_remote_urls():
    _assert_local(DESKTOP / "error.html")
    assert "The game engine stopped" in (DESKTOP / "error.html").read_text(encoding="utf-8")
