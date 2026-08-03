from BackEnd.utils import rt_display


def test_rt_letter_grade_boundaries():
    expected = {
        -1: "F",
        39: "F",
        40: "C",
        49: "C",
        50: "C+",
        59: "C+",
        60: "B",
        69: "B",
        70: "B+",
        79: "B+",
        80: "A",
        89: "A",
        90: "A+",
        99: "A+",
        100: "A++",
        115: "A++",
    }
    assert {value: rt_display.rt_letter_grade(value) for value in expected} == expected


def test_rt_letter_grade_handles_missing_and_decimal_values():
    assert rt_display.rt_letter_grade(None) == "--"
    assert rt_display.rt_letter_grade("") == "--"
    assert rt_display.rt_letter_grade("not-a-rating") == "--"
    assert rt_display.rt_letter_grade(79.9) == "B+"


def test_numeric_rollback_mode(monkeypatch):
    monkeypatch.setattr(rt_display, "RT_DISPLAY_MODE", "number")
    assert rt_display.format_rt_display(84) == "84"
    assert rt_display.format_rt_display(84.5) == "84.5"
    assert rt_display.format_rt_display(None) == "--"
