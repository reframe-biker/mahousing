"""
score.py — Grading engine for MA Housing Report Card

Converts raw numeric metrics (from the ingest modules) into letter grades
(A/B/C/D/F) for each grading dimension, then computes a composite grade.

Grading rubrics for Phase 1 dimensions:

  zoning         (pct_multifamily_permitted — % of permitted units in 5+ unit structures)
    A  > 40%     — strong revealed preference for multifamily
    B  25–40%
    C  10–25%
    D  2–10%
    F  < 2%
    null  fewer than 10 total permits over 3 years (low-sample towns)

  affordability  (rent_burden_pct — % of renters paying > 30% of income)
    A  < 20%
    B  20–30%
    C  30–40%
    D  40–50%
    F  > 50%

  production     (permits_per_1000_residents — annual housing units per 1,000 pop)
    A  > 5.0
    B  3.0–5.0
    C  1.5–3.0
    D  0.5–1.5
    F  < 0.5

  composite      Numeric average of all non-null dimension grades.
                 Null dimensions are excluded — not treated as F.
                 A=4, B=3, C=2, D=1, F=0. Rounded to nearest integer.

Phase 2/3 dimensions (mbta, votes, rep) are not scored here; they return None.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Mapping from letter grade to numeric value for composite calculation
_GRADE_TO_NUM: dict[str, float] = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0, "F": 0.0}
_NUM_TO_GRADE: dict[int, str] = {4: "A", 3: "B", 2: "C", 1: "D", 0: "F"}


def score_town(metrics: dict) -> dict:
    """
    Compute letter grades for a single municipality given its raw metrics.

    Args:
        metrics: Dict matching pipeline.schema.Metrics. All values may be None.
                 Expected keys: pct_multifamily_permitted, median_home_value,
                 rent_burden_pct, permits_per_1000_residents.

    Returns:
        Dict matching pipeline.schema.Grades. Keys: zoning, mbta, production,
        affordability, votes, rep, composite.
        Any dimension without data returns None (not "F").
    """
    zoning = _grade_zoning(metrics.get("pct_multifamily_permitted"))
    affordability = _grade_affordability(metrics.get("rent_burden_pct"))
    production = _grade_production(metrics.get("permits_per_1000_residents"))

    # mbta, votes, rep: not implemented in Phase 1
    mbta = None
    votes = None
    rep = None

    composite = _compute_composite([zoning, mbta, affordability, production, votes, rep])

    return {
        "zoning": zoning,
        "mbta": mbta,
        "production": production,
        "affordability": affordability,
        "votes": votes,
        "rep": rep,
        "composite": composite,
    }


def _grade_zoning(pct: float | None) -> str | None:
    """
    Grade zoning permissiveness based on the active zoning metric.

    Current metric (permits_proxy): % of permitted units in 5+ unit structures
    over the most recent 3 years.  Towns with fewer than 10 total permits pass
    None here and receive a null grade.

    A > 40%, B 25–40%, C 10–25%, D 2–10%, F < 2%
    """
    if pct is None:
        return None
    if pct > 40:
        return "A"
    if pct > 25:
        return "B"
    if pct > 10:
        return "C"
    if pct > 2:
        return "D"
    return "F"


def _grade_affordability(rent_burden_pct: float | None) -> str | None:
    """
    Grade affordability based on % of renter households that are cost-burdened (>30%).

    A < 20%, B 20–30%, C 30–40%, D 40–50%, F > 50%
    """
    if rent_burden_pct is None:
        return None
    if rent_burden_pct < 20:
        return "A"
    if rent_burden_pct < 30:
        return "B"
    if rent_burden_pct < 40:
        return "C"
    if rent_burden_pct < 50:
        return "D"
    return "F"


def _grade_production(permits_per_1000: float | None) -> str | None:
    """
    Grade housing production based on annual permits per 1,000 residents.

    A > 5.0, B 3.0–5.0, C 1.5–3.0, D 0.5–1.5, F < 0.5
    """
    if permits_per_1000 is None:
        return None
    if permits_per_1000 > 5.0:
        return "A"
    if permits_per_1000 > 3.0:
        return "B"
    if permits_per_1000 > 1.5:
        return "C"
    if permits_per_1000 > 0.5:
        return "D"
    return "F"


def _compute_composite(grades: list[str | None]) -> str | None:
    """
    Compute a composite letter grade as the simple average of non-null dimension grades.

    Args:
        grades: List of letter grade strings or None. None values are excluded.

    Returns:
        Composite letter grade, or None if no grades are available.
    """
    numeric = [_GRADE_TO_NUM[g] for g in grades if g is not None]
    if not numeric:
        return None
    avg = sum(numeric) / len(numeric)
    rounded = round(avg)
    # Clamp to valid range [0, 4] in case of floating point edge cases
    rounded = max(0, min(4, rounded))
    return _NUM_TO_GRADE[rounded]
