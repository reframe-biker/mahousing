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
    "pct_land_multifamily_byright": {
        "label": "Multifamily land share",
        "description": (
            "Share of residential zoned land where 3-family or larger multifamily housing "
            "is permitted by right — no planning board hearing required. Derived from MA "
            "Zoning Atlas 2023 district data. For the 107 towns not yet covered by the "
            "Zoning Atlas, this reflects permit mix (share of permitted units that are "
            "multifamily) as a fallback."
        ),
        "unit": "percent",
        "source": "MA Zoning Atlas (NZA) 2023",
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
    "mbta_status": {
        "label": "MBTA Communities compliance",
        "description": (
            "Whether the municipality has complied with the MBTA Communities Act, "
            "which requires towns served by the MBTA to zone for multifamily housing "
            "by right near transit. Non-compliant towns lose access to certain state "
            "grant programs."
        ),
        "source": "MA Dept of Housing and Community Development (DHCD)",
        "unit": "status",
        "higher_is_better": True,
    },
}
