"""
score.py — Grading engine for MA Housing Report Card

Converts raw numeric metrics (from the ingest modules) into letter grades
(A/B/C/D/F) for each grading dimension, then computes a composite grade.

Grading rubrics for Phase 1 dimensions:

  zoning         (pct_land_multifamily_byright — % of residential zoned land where 3+ family
                  housing is permitted by right; NZA 2023 with permit proxy fallback)
    A  > 25%     — substantial by-right multifamily land
    B  10–25%
    C  3–10%
    D  0.5–3%
    F  < 0.5%
    null  no residential zoning data for that municipality

  affordability  renter-share-weighted composite of rent burden and median home value
    rent_burden (pct renters paying >30%): A<20%, B 20–30%, C 30–40%, D 40–50%, F>50%
    median_home_value: A<$400k, B $400–600k, C $600–800k, D $800k–1.2M, F>$1.2M
    weight_rent = renter_share_pct / 100; weight_home = 1 - weight_rent
    composite numeric (A=4…F=0): ≥3.5→A, ≥2.5→B, ≥1.5→C, ≥0.5→D, <0.5→F

  production     (permits_per_1000_residents — annual housing units per 1,000 pop)
    A  > 5.0
    B  3.0–5.0
    C  1.5–3.0
    D  0.5–1.5
    F  < 0.5

  mbta           (mbta_status — DHCD compliance status string)
    A  "compliant"
    B  "interim"
    C  "pending"
    F  "non-compliant"
    null  "exempt" or None (excluded from composite — not penalized)

  composite      Numeric average of all non-null dimension grades.
                 Null dimensions are excluded — not treated as F.
                 Exempt MBTA towns (null mbta grade) are excluded from composite.
                 A=4, B=3, C=2, D=1, F=0. Rounded to nearest integer.

  legislators    (pooled lower-median of all reps + sens)
    A  ≥ 80%    — strongly pro-housing
    B  60–79%
    C  40–59%
    D  20–39%
    F  < 20%    — voted anti-housing on nearly all scored bills
    null  no legislators present for any scored vote

Phase 4 dimension (votes) is not scored here; it returns None.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Mapping from letter grade to numeric value for composite calculation
_GRADE_TO_NUM: dict[str, float] = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0, "F": 0.0}
_NUM_TO_GRADE: dict[int, str] = {4: "A", 3: "B", 2: "C", 1: "D", 0: "F"}


def score_town(
    metrics: dict,
    mbta_status: str | None = None,
    reps: list[dict] | None = None,
    sens: list[dict] | None = None,
) -> dict:
    """
    Compute letter grades for a single municipality given its raw metrics.

    Args:
        metrics: Dict matching pipeline.schema.Metrics. All values may be None.
                 Expected keys: pct_land_multifamily_byright, median_home_value,
                 rent_burden_pct, permits_per_1000_residents.
        mbta_status: MBTA Communities Act compliance status string, or None.
                     "compliant" | "interim" | "non-compliant" | "pending" |
                     "exempt" | None.
        reps: List of RepRecord dicts (from legislators.py), or None.
        sens: List of SenRecord dicts (from senate_rollcall_fetcher.py), or None.
              reps and sens are pooled together to derive the town-level
              legislators grade via lower-median across the combined set.

    Returns:
        Dict matching pipeline.schema.Grades. Keys: zoning, mbta, production,
        affordability, votes, legislators, composite.
        Any dimension without data returns None (not "F").
        Exempt MBTA towns get None for mbta grade (excluded from composite).
    """
    zoning = _grade_zoning(metrics.get("pct_land_multifamily_byright"))
    affordability = _grade_affordability(
        metrics.get("rent_burden_pct"),
        metrics.get("median_home_value"),
        metrics.get("renter_share_pct"),
    )
    production = _grade_production(metrics.get("permits_per_1000_residents"))
    mbta = _grade_mbta(mbta_status)

    # votes: not implemented until Phase 4b
    votes = None

    legislators = _grade_legislators(reps, sens)

    composite = _compute_composite([zoning, mbta, affordability, production, votes, legislators])

    return {
        "zoning": zoning,
        "mbta": mbta,
        "production": production,
        "affordability": affordability,
        "votes": votes,
        "legislators": legislators,
        "composite": composite,
    }


def _grade_mbta(status: str | None) -> str | None:
    """
    Grade MBTA Communities Act compliance.

    compliant     → A
    interim       → B
    pending       → C
    non-compliant → F
    exempt        → None (excluded from composite — not penalized)
    None          → None (data not yet available)
    """
    if status is None or status == "exempt":
        return None
    if status == "compliant":
        return "A"
    if status == "interim":
        return "B"
    if status == "pending":
        return "C"
    if status == "non-compliant":
        return "F"
    logger.warning(f"Unknown MBTA status '{status}' — returning None")
    return None


def _grade_zoning(pct: float | None) -> str | None:
    """
    Grade zoning permissiveness based on pct_land_multifamily_byright.

    Current metric (NZA 2023): area-weighted share of residential zoned land
    where 3+ family housing is permitted by right (or partial credit for
    special permit).  Calibrated for land-area-based data.

    A > 25%, B 10–25%, C 3–10%, D 0.5–3%, F < 0.5%
    null  no residential zoning data available
    """
    if pct is None:
        return None
    if pct > 25:
        return "A"
    if pct > 10:
        return "B"
    if pct > 3:
        return "C"
    if pct > 0.5:
        return "D"
    return "F"


def _grade_rent_burden(rent_burden_pct: float | None) -> str | None:
    """
    Grade rent affordability based on % of renter households that are cost-burdened (>30%).

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


def _grade_home_value(median_home_value: float | None) -> str | None:
    """
    Grade affordability based on median owner-occupied home value.

    Lower values are better (inverse grading).
    A < $400k, B $400–600k, C $600–800k, D $800k–$1.2M, F > $1.2M
    """
    if median_home_value is None:
        return None
    if median_home_value < 400_000:
        return "A"
    if median_home_value < 600_000:
        return "B"
    if median_home_value < 800_000:
        return "C"
    if median_home_value < 1_200_000:
        return "D"
    return "F"


def _grade_affordability(
    rent_burden_pct: float | None,
    median_home_value: float | None,
    renter_share_pct: float | None,
) -> str | None:
    """
    Composite affordability grade: renter-share-weighted combination of rent
    burden and median home value grades.

    weight_rent = renter_share_pct / 100 (0.5 fallback if data unavailable)
    weight_home = 1 - weight_rent
    composite (A=4…F=0): ≥3.5→A, ≥2.5→B, ≥1.5→C, ≥0.5→D, <0.5→F
    """
    GRADE_NUM = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}

    rent_grade = _grade_rent_burden(rent_burden_pct)
    home_grade = _grade_home_value(median_home_value)

    if rent_grade is None and home_grade is None:
        return None

    if renter_share_pct is None:
        weight_rent = 0.5
    else:
        weight_rent = renter_share_pct / 100
    weight_home = 1 - weight_rent

    if rent_grade is None:
        numeric = GRADE_NUM[home_grade]  # type: ignore[index]
    elif home_grade is None:
        numeric = GRADE_NUM[rent_grade]
    else:
        numeric = (weight_rent * GRADE_NUM[rent_grade] +
                   weight_home * GRADE_NUM[home_grade])

    if numeric >= 3.5:
        return "A"
    if numeric >= 2.5:
        return "B"
    if numeric >= 1.5:
        return "C"
    if numeric >= 0.5:
        return "D"
    return "F"


def _grade_legislators(
    reps: list[dict] | None,
    sens: list[dict] | None,
) -> str | None:
    """
    Derive the town-level legislators grade from the combined pool of
    RepRecords and SenRecords.

    Uses lower median: with N legislators, takes sorted(grades)[floor(N/2)].
    Returns None if both reps and sens are None or empty.
    """
    import math
    combined: list[dict] = []
    if reps:
        combined.extend(reps)
    if sens:
        combined.extend(sens)
    if not combined:
        return None
    grade_scores = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
    scores = [grade_scores[r["grade"]] for r in combined
              if r.get("grade") in grade_scores]
    if not scores:
        return None
    median_score = sorted(scores)[math.floor(len(scores) / 2)]
    score_to_grade = {4: "A", 3: "B", 2: "C", 1: "D", 0: "F"}
    return score_to_grade[median_score]


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
