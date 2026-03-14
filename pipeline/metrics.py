"""
metrics.py — Single source of truth for metric metadata in MA Housing Report Card

This module defines METRICS, a dict mapping every metric field name to its
display label, description, data source, unit type, and directionality.

RULES:
  - Every key in METRICS must match a field in pipeline/schema.py:Metrics.
  - When a metric is added or renamed, update this file, run the pipeline
    (which exports data/metrics.json), then run `npm run build` in site/.
  - The pipeline validates that METRICS keys and schema keys are in sync.
  - Never hardcode metric labels or descriptions in site components —
    they must be read from data/metrics.json at build time.

See CONTRIBUTING.md for the full rule set.
"""

from __future__ import annotations

METRICS: dict[str, dict] = {
    "pct_multifamily_permitted": {
        "label": "Multifamily share of permitted units",
        "description": (
            "Share of permitted housing units that are multifamily (5+ units), "
            "averaged over the most recent 3 years. Used as a revealed-preference "
            "measure of zoning permissiveness. Towns with fewer than 10 total "
            "permits over 3 years show N/A. Will be replaced with National Zoning "
            "Atlas data when available."
        ),
        "source": "U.S. Census Building Permits Survey",
        "unit": "percent",
        "higher_is_better": True,
    },
    "median_home_value": {
        "label": "Median home value",
        "description": (
            "Median value of owner-occupied housing units. "
            "A proxy for housing cost and affordability pressure."
        ),
        "source": "U.S. Census ACS 5-year estimates",
        "unit": "dollars",
        "higher_is_better": False,
    },
    "rent_burden_pct": {
        "label": "Renters cost-burdened",
        "description": (
            "Share of renter households paying more than 30% of income on gross rent. "
            "High cost burden indicates housing supply shortfall."
        ),
        "source": "U.S. Census ACS 5-year estimates",
        "unit": "percent",
        "higher_is_better": False,
    },
    "permits_per_1000_residents": {
        "label": "Permits per 1,000 residents",
        "description": (
            "Annual residential building permits averaged over the most recent "
            "multi-year period, normalized by population. Measures actual housing "
            "production."
        ),
        "source": "U.S. Census Building Permits Survey",
        "unit": "rate",
        "higher_is_better": True,
    },
}
