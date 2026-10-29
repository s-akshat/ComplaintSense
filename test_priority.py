import os
import sys

# Let the tests find priority.py, which lives one folder up.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from priority import (
    calculate_priority_score,
    get_priority_level,
    validate_rating,
    is_emergency_category,
    evaluate_complaint,
    sort_complaints,
)


# ---- Score calculation ----

@pytest.mark.parametrize("urgency, severity, expected", [
    (1, 1, 1.0),
    (5, 5, 5.0),
    (3, 3, 3.0),
    (5, 1, 3.0),
    (2, 3, 2.5),
    (4, 5, 4.5),
])
def test_score_calculation(urgency, severity, expected):
    assert calculate_priority_score(urgency, severity) == expected


def test_score_accepts_numeric_strings_from_web_forms():
    assert calculate_priority_score("4", "2") == 3.0


# ---- Level boundaries ----

@pytest.mark.parametrize("score, expected", [
    (1.0, "LOW"),
    (1.5, "LOW"),
    (2.0, "MEDIUM"),
    (2.5, "MEDIUM"),
    (3.0, "HIGH"),
    (3.5, "HIGH"),
    (4.0, "CRITICAL"),
    (5.0, "CRITICAL"),
])
def test_level_boundaries(score, expected):
    assert get_priority_level(score) == expected


def test_level_rejects_out_of_range_score():
    with pytest.raises(ValueError):
        get_priority_level(0.5)
    with pytest.raises(ValueError):
        get_priority_level(5.5)


# ---- Invalid inputs ----

@pytest.mark.parametrize("bad", [0, 6, -1, 100, 2.5, "abc", "", None, True, [3]])
def test_invalid_ratings_rejected(bad):
    with pytest.raises(ValueError):
        validate_rating(bad, "urgency")


def test_invalid_urgency_or_severity_in_score():
    with pytest.raises(ValueError):
        calculate_priority_score(0, 3)
    with pytest.raises(ValueError):
        calculate_priority_score(3, 6)


# ---- Emergency categories ----

def test_emergency_category_flag():
    assert is_emergency_category("Security") is True
    assert is_emergency_category("  Fire Safety ") is True
    assert is_emergency_category("Furniture") is False
    assert is_emergency_category(None) is False


def test_low_score_emergency_still_flagged_for_review():
    result = evaluate_complaint(1, 1, "Security")
    assert result["priority_level"] == "LOW"
    assert result["needs_immediate_review"] is True


def test_evaluate_complaint_normal():
    result = evaluate_complaint(5, 4, "Water")
    assert result == {
        "priority_score": 4.5,
        "priority_level": "CRITICAL",
        "needs_immediate_review": False,
    }


# ---- Sorting and tie-breaker ----

def test_sort_highest_score_first_then_oldest():
    complaints = [
        {"id": "A", "priority_score": 3.0, "created_at": "2026-10-29 10:00:00"},
        {"id": "B", "priority_score": 5.0, "created_at": "2026-10-29 12:00:00"},
        {"id": "C", "priority_score": 3.0, "created_at": "2026-10-29 09:00:00"},
        {"id": "D", "priority_score": 4.0, "created_at": "2026-10-29 08:00:00"},
    ]
    ordered = [c["id"] for c in sort_complaints(complaints)]
    assert ordered == ["B", "D", "C", "A"]


def test_sort_does_not_change_original_list():
    complaints = [
        {"id": "A", "priority_score": 1.0, "created_at": "2026-10-29 10:00:00"},
        {"id": "B", "priority_score": 5.0, "created_at": "2026-10-29 11:00:00"},
    ]
    sort_complaints(complaints)
    assert complaints[0]["id"] == "A"


def test_sort_empty_list():
    assert sort_complaints([]) == []
