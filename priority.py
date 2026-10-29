"""
priority.py - ComplainSense priority algorithm.

This is an EDUCATIONAL decision-support tool. It is NOT a validated safety
assessment. Complaints in emergency categories must get immediate human review
regardless of their calculated score, because urgency and severity are
self-reported by the person filing the complaint.
"""

# ---------- Constants (values that never change while the program runs) ----------

MIN_RATING = 1          # lowest allowed urgency / severity
MAX_RATING = 5          # highest allowed urgency / severity

URGENCY_WEIGHT = 0.5    # how much urgency counts in the score
SEVERITY_WEIGHT = 0.5   # how much severity counts in the score

# Thresholds: a score >= the number gives that level.
# Checked from highest to lowest, so order matters.
LEVEL_THRESHOLDS = [
    (4.0, "CRITICAL"),
    (3.0, "HIGH"),
    (2.0, "MEDIUM"),
    (1.0, "LOW"),
]

# Categories that always need a human to look at them straight away.
EMERGENCY_CATEGORIES = {"Security", "Fire Safety", "Medical", "Electrical Hazard"}


# ---------- Functions ----------

def validate_rating(value, name):
    """Check that a rating is a whole number from 1 to 5.

    Returns the rating as an int. Raises ValueError if it is invalid.
    `name` is only used to make the error message clear ("urgency" or "severity").
    """
    # bool is a subtype of int in Python (True == 1), so reject it explicitly.
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a whole number between {MIN_RATING} and {MAX_RATING}.")

    # Accept ints, and strings/floats that are exactly whole numbers (e.g. "4" from a web form).
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a whole number between {MIN_RATING} and {MAX_RATING}.")

    if number != int(number):
        raise ValueError(f"{name} must be a whole number between {MIN_RATING} and {MAX_RATING}.")

    number = int(number)
    if number < MIN_RATING or number > MAX_RATING:
        raise ValueError(f"{name} must be between {MIN_RATING} and {MAX_RATING}.")

    return number


def calculate_priority_score(urgency, severity):
    """Return the priority score: (urgency x 0.5) + (severity x 0.5)."""
    urgency = validate_rating(urgency, "urgency")
    severity = validate_rating(severity, "severity")
    return urgency * URGENCY_WEIGHT + severity * SEVERITY_WEIGHT


def get_priority_level(score):
    """Convert a numeric score into CRITICAL / HIGH / MEDIUM / LOW.

    Scores are multiples of 0.5, so the boundaries are exact.
    """
    if score < MIN_RATING or score > MAX_RATING:
        raise ValueError(f"score must be between {MIN_RATING} and {MAX_RATING}.")

    for threshold, level in LEVEL_THRESHOLDS:
        if score >= threshold:
            return level


def is_emergency_category(category):
    """True if this category needs immediate human review, whatever its score."""
    if not isinstance(category, str):
        return False
    return category.strip() in EMERGENCY_CATEGORIES


def evaluate_complaint(urgency, severity, category=""):
    """Run the whole algorithm and return the results as a dictionary."""
    score = calculate_priority_score(urgency, severity)
    return {
        "priority_score": score,
        "priority_level": get_priority_level(score),
        "needs_immediate_review": is_emergency_category(category),
    }


def sort_complaints(complaints):
    """Sort complaints: highest score first; for equal scores, oldest first.

    `complaints` is a list of dictionaries with keys 'priority_score'
    and 'created_at'. Returns a new sorted list.
    """
    # Sort by created_at (oldest first), then by score (highest first).
    # Python's sort is stable, so the second sort keeps the first order for ties.
    by_time = sorted(complaints, key=lambda c: c["created_at"])
    return sorted(by_time, key=lambda c: c["priority_score"], reverse=True)
