"""
schema.py — Data schema for MA Housing Report Card town records

Defines the canonical shape of a town JSON file using TypedDict.
All ingest, scoring, and build modules must produce and consume data
conforming to this schema. The TypeScript equivalent lives at
site/src/types/town.ts.

A null value in any grade or metric field means the data has not yet
been collected for that municipality. It does NOT represent a score of
zero or an F. The UI must display null grades as "N/A".
"""

from typing import Literal, TypedDict


# Valid letter grades. None means data not yet collected.
Grade = Literal["A", "B", "C", "D", "F"] | None

# Valid MBTA Communities Act compliance statuses.
MbtaStatus = Literal["compliant", "interim", "non-compliant", "pending", "exempt"] | None


class Grades(TypedDict):
    """
    Letter grades for each grading dimension.

    Each grade is A/B/C/D/F or None. None means data not yet available —
    not a failing grade. Scoring formulas for each dimension are documented
    in METHODOLOGY.md and will be finalized before any grades are published.
    """
    zoning: Grade          # Zoning Permissiveness (MA Zoning Atlas / MAPC)
    mbta: Grade            # MBTA Communities Act compliance
    production: Grade      # Housing Production rate (Census Building Permits)
    affordability: Grade   # Affordability burden (Census ACS + Zillow)
    votes: Grade           # Town Meeting voting record on housing articles
    rep: Grade             # State legislator housing vote record (future phase)
    composite: Grade       # Weighted composite of all applicable dimensions


class Metrics(TypedDict):
    """
    Raw numeric metrics underlying the grades.

    All values are floats (or None if not yet collected). These are the
    direct outputs of the ingest modules before scoring is applied.
    """
    pct_land_multifamily_byright: float | None
    """
    Area-weighted share of residential zoned land (in acres) where 3-family
    (family3) or larger multifamily (family4) housing is permitted by right.
    Source: MA Zoning Atlas 2023 (NZA) with Census BPS permit proxy fallback
    for towns not covered by the NZA.
    Range: 0.0–100.0.
    """

    median_home_value: float | None
    """
    Median owner-occupied home value in USD. Sourced from US Census
    American Community Survey (ACS) 5-year estimates.
    """

    rent_burden_pct: float | None
    """
    Percentage of renter households paying more than 30% of income on
    gross rent (cost-burdened renters). Sourced from Census ACS.
    Range: 0.0–100.0.
    """

    permits_per_1000_residents: float | None
    """
    Annual residential building permits issued per 1,000 residents.
    Sourced from the Census Building Permits Survey. Higher values
    indicate greater housing production relative to existing population.
    """


class DataNotes(TypedDict):
    """
    Human-readable data quality notes attached to specific grading dimensions.

    A non-null note means the pipeline detected a condition that may affect
    the reliability of that dimension's grade.  The grade itself is NOT
    changed — notes are additive transparency flags only.

    Currently only zoning notes are generated (single-year permit spike
    detection in zoning_permits_proxy.py).  production and affordability
    are reserved for future use.
    """
    zoning: str | None
    """
    Set when a single calendar year accounts for more than 70% of a small
    town's 3-year permit total (spike detection in zoning_permits_proxy.py).
    """

    production: str | None
    """Reserved for future production-grade quality flags. Always None for now."""

    affordability: str | None
    """Reserved for future affordability-grade quality flags. Always None for now."""


class TownRecord(TypedDict):
    """
    Canonical shape of a town JSON file at data/towns/<fips>.json.

    This is the unit of data that the pipeline produces and the frontend
    consumes. Every field marked as `| None` will be null in the JSON
    when data is not yet available.
    """
    fips: str
    """5-digit MA FIPS code (e.g., '25001' for Barnstable County). Unique identifier."""

    name: str
    """Municipality name as it appears in Census data (e.g., 'Brookline')."""

    county: str
    """County name (e.g., 'Norfolk')."""

    population: int | None
    """Total population from most recent Census ACS 5-year estimate."""

    grades: Grades
    """Letter grades for each grading dimension. See Grades."""

    metrics: Metrics
    """Raw numeric metrics underlying the grades. See Metrics."""

    data_notes: DataNotes
    """
    Data quality notes for individual grading dimensions. Fields are None
    when no quality issue was detected. See DataNotes.
    """

    mbta_status: MbtaStatus
    """
    MBTA Communities Act compliance status. One of:
      'compliant'     — municipality has adopted a compliant zoning district
      'interim'       — municipality has adopted an interim action plan
      'non-compliant' — municipality is subject to the Act and has not complied
      'pending'       — municipality has submitted a plan under review
      'exempt'        — municipality is not subject to the Act
      None            — status not yet determined
    """

    mbta_deadline: str | None
    """
    Deadline date for MBTA Communities Act compliance (ISO date string YYYY-MM-DD),
    or None if not subject to the Act or no deadline published.
    """

    mbta_action_date: str | None
    """
    Date of the municipality's most recent action toward compliance
    (ISO date string YYYY-MM-DD), or None if no action taken or not applicable.
    """

    updated_at: str
    """ISO 8601 date string of when this record was last updated by the pipeline (e.g., '2025-03-13')."""
