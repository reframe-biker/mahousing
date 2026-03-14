"""
score.py — Grading engine for MA Housing Report Card

This module will be implemented in Phase 1. Its responsibilities:

1. Accept a town's raw metrics dict (populated by the ingest modules) and
   produce a grades dict with letter grades (A/B/C/D/F) for each of the
   six grading dimensions:
     - zoning:        Zoning Permissiveness (MA Zoning Atlas)
     - mbta:          MBTA Communities Act compliance status
     - production:    Housing Production rate (Census Building Permits)
     - affordability: Affordability burden (Census ACS / Zillow)
     - votes:         Town Meeting voting record on housing articles
     - rep:           State legislator housing vote record (future phase)
     - composite:     Weighted composite of all applicable dimensions

2. For each dimension, apply a scoring formula that converts one or more
   raw numeric metrics into a percentile rank among all 351 MA municipalities,
   then maps that rank to a letter grade using cutoffs defined in a config file.
   Scoring formulas are documented in METHODOLOGY.md and will be finalized
   before any grades are published.

3. Handle missing data gracefully: if a required metric is None, the
   corresponding grade should be None (not zero). Null grades are displayed
   as "N/A" in the UI, not as an F.

4. Emit a grades dict conforming to the schema defined in schema.py.

Usage (future):
    from pipeline.score import score_town
    from pipeline.schema import TownRecord

    grades = score_town(metrics)
"""


def score_town(metrics: dict) -> dict:
    """
    Compute letter grades for a single town given its raw metrics.

    Args:
        metrics: Dict of raw numeric metrics as defined in TownRecord["metrics"].

    Returns:
        Dict of grade values as defined in TownRecord["grades"].

    Not yet implemented — returns all-None grades until Phase 1.
    """
    raise NotImplementedError("score_town will be implemented in Phase 1.")
