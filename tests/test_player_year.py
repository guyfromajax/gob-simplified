from BackEnd.utils.player_year import (
    format_player_year_abbrev,
    format_player_year_display,
    normalize_player_year,
)


def test_normalize_player_year_variants():
    assert normalize_player_year("senior") == "Senior"
    assert normalize_player_year("Senior") == "Senior"
    assert normalize_player_year("SR") == "Senior"
    assert normalize_player_year("freshman") == "Freshman"
    assert normalize_player_year("JH") == "JH"


def test_format_player_year_display():
    assert format_player_year_display("junior") == "JR"
    assert format_player_year_display("JH") == "JH"
    assert format_player_year_display("") == "--"


def test_format_player_year_abbrev():
    assert format_player_year_abbrev("Senior") == "SR"
    assert format_player_year_abbrev("sophomore") == "SO"
