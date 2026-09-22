"""Local static serving: team art types + the Bebas Neue Pro OTFs that 404'd."""
from fastapi.testclient import TestClient

from BackEnd.api.api import app

client = TestClient(app)


def test_chapel_hill_team_art_types_are_local_files():
    paths = {
        "banner_card": "/images/teams/chapel_hill/chapel_hill_banner_card.webp",
        "banner_primary": "/images/teams/chapel_hill/chapel_hill_banner_primary.jpg",
        "court": "/images/teams/chapel_hill/chapel_hill_court.jpg",
        "logo_square": "/images/teams/chapel_hill/chapel_hill_logo_square.png",
    }
    for kind, path in paths.items():
        res = client.get(path, follow_redirects=True)
        assert res.status_code == 200, f"{kind} {path} -> {res.status_code}"
        assert res.headers.get("content-type", "").startswith("image/"), kind


def test_bebas_neue_pro_otf_is_served():
    res = client.get("/fonts/BebasNeuePro-Bold.otf", follow_redirects=True)
    assert res.status_code == 200
    assert "otf" in (res.headers.get("content-type") or "") or res.content[:4] != b"{\n"


def test_app_fonts_css_is_local():
    res = client.get("/fonts/app-fonts.css", follow_redirects=True)
    assert res.status_code == 200
    body = res.text
    assert "fonts.googleapis.com" not in body
    assert "fonts.gstatic.com" not in body
    assert "/fonts/google/" in body
