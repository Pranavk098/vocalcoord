"""HOS tier boundary tests — safety-critical branching logic, highest risk-per-line-of-test
in the repo per the audit. Pins the exact tier at each of the five threshold values plus
one value just below each, since off-by-one errors here are the ones most likely to slip
past a human reviewer (`<` vs `<=`)."""
from backend.agents.wellness_copilot import _evaluate_hos


def _tier(hos: float) -> str:
    _, status, _ = _evaluate_hos(hos)
    return status


def test_just_below_critical_threshold():
    assert _tier(0.99) == "CRITICAL"


def test_exactly_one_hour_is_severe_not_critical():
    assert _tier(1.0) == "SEVERE"


def test_just_below_severe_threshold():
    assert _tier(1.99) == "SEVERE"


def test_exactly_two_hours_is_caution_not_severe():
    assert _tier(2.0) == "CAUTION"


def test_just_below_caution_threshold():
    assert _tier(3.49) == "CAUTION"


def test_exactly_three_point_five_is_watch_not_caution():
    assert _tier(3.5) == "WATCH"


def test_just_below_watch_threshold():
    assert _tier(5.99) == "WATCH"


def test_exactly_six_hours_is_clear_not_watch():
    assert _tier(6.0) == "CLEAR"


def test_well_above_six_hours_is_clear():
    assert _tier(11.0) == "CLEAR"


def test_zero_hours_is_critical():
    assert _tier(0.0) == "CRITICAL"
