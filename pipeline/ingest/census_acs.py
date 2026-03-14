"""
census_acs.py — US Census ACS ingest for MA Housing Report Card

Fetches 5-year ACS estimates for all MA county subdivisions (cities and towns)
via the Census Bureau REST API. Returns municipality-level metrics for:
  - Population (B01003)
  - Rent burden (B25070 — gross rent as % of household income)
  - Median home value (B25077)

Returns a DataFrame with one row per MA municipality. Rows with suppressed
or unavailable data have None in the affected metric columns.

Source: US Census Bureau American Community Survey (ACS) 5-year estimates
API docs: https://www.census.gov/data/developers/data-sets/acs-5year.html
"""

import logging
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Most recent ACS 5-year vintage to use. Update when new data is released.
ACS_YEAR = 2022

# MA state FIPS
MA_FIPS = "25"

# ACS table fields we need
_FIELDS = {
    "NAME": "name",
    "B01003_001E": "population",       # Total population
    "B25070_001E": "renters_total",    # Total renter households (rent burden denominator)
    "B25070_007E": "burden_30_34",     # 30.0–34.9% of income on rent
    "B25070_008E": "burden_35_39",     # 35.0–39.9%
    "B25070_009E": "burden_40_49",     # 40.0–49.9%
    "B25070_010E": "burden_50_plus",   # 50.0% or more
    "B25077_001E": "median_home_value",# Median owner-occupied home value ($)
}

# Census sentinel values for suppressed / not-computed data
_CENSUS_NULL = {-666666666, -999999999, -333333333, -222222222, -888888888}


def _safe_int(val: Any) -> int | None:
    """Convert Census API string value to int, returning None for sentinel values."""
    if val is None:
        return None
    try:
        v = int(val)
        return None if v in _CENSUS_NULL else v
    except (ValueError, TypeError):
        return None


def fetch_acs_data(api_key: str) -> pd.DataFrame:
    """
    Fetch ACS 5-year data for all MA county subdivisions.

    Args:
        api_key: Census Bureau API key (CENSUS_API_KEY env var).

    Returns:
        DataFrame with columns:
            geoid           (str)  10-digit county subdivision GEOID
            name            (str)  Municipality name (e.g. "Cambridge")
            county          (str)  County name (e.g. "Middlesex County")
            population      (int | None)
            rent_burden_pct (float | None)  % of renters paying >30% of income
            median_home_value (float | None)  ACS median owner-occupied home value ($)

    Raises:
        RuntimeError: if the Census API request fails.
    """
    fields = ",".join(_FIELDS.keys())
    url = (
        f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
        f"?get={fields}"
        f"&for=county+subdivision:*"
        f"&in=state:{MA_FIPS}+county:*"
        f"&key={api_key}"
    )

    logger.info(f"Fetching Census ACS {ACS_YEAR} 5-year data for MA county subdivisions…")
    resp = requests.get(url, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Census ACS API returned HTTP {resp.status_code}: {resp.text[:200]}"
        )

    raw = resp.json()  # List[List[str]]: first row is headers
    headers = raw[0]
    rows = raw[1:]
    logger.info(f"  Received {len(rows)} rows from Census API")

    records = []
    for row in rows:
        r = dict(zip(headers, row))

        # Build 10-digit GEOID: state + county + county subdivision
        geoid = r.get("state", "") + r.get("county", "") + r.get("county subdivision", "")

        # Parse name: "Abington town, Plymouth County, Massachusetts" → name + county
        raw_name = r.get("NAME", "")
        parts = [p.strip() for p in raw_name.split(",")]
        # Remove trailing " town" / " city" / " plantation" suffix for a clean name
        full_muni = parts[0] if parts else raw_name
        muni_name = _strip_suffix(full_muni)
        county_name = parts[1] if len(parts) > 1 else ""

        # Skip non-municipality entries (e.g. "County subdivisions not defined")
        if "not defined" in full_muni.lower() or "remainder" in full_muni.lower():
            continue

        population = _safe_int(r.get("B01003_001E"))
        renters_total = _safe_int(r.get("B25070_001E"))
        burden_30_34 = _safe_int(r.get("B25070_007E"))
        burden_35_39 = _safe_int(r.get("B25070_008E"))
        burden_40_49 = _safe_int(r.get("B25070_009E"))
        burden_50_plus = _safe_int(r.get("B25070_010E"))
        median_home_value_raw = _safe_int(r.get("B25077_001E"))

        # Compute rent burden pct: share of renters paying > 30% of income
        if (
            renters_total
            and renters_total > 0
            and all(
                x is not None
                for x in [burden_30_34, burden_35_39, burden_40_49, burden_50_plus]
            )
        ):
            cost_burdened = (
                burden_30_34 + burden_35_39 + burden_40_49 + burden_50_plus  # type: ignore[operator]
            )
            rent_burden_pct: float | None = round(cost_burdened / renters_total * 100, 1)
        else:
            rent_burden_pct = None

        median_home_value: float | None = (
            float(median_home_value_raw) if median_home_value_raw is not None else None
        )

        records.append(
            {
                "geoid": geoid,
                "name": muni_name,
                "name_raw": full_muni,
                "county": county_name,
                "population": population,
                "rent_burden_pct": rent_burden_pct,
                "median_home_value": median_home_value,
            }
        )

    df = pd.DataFrame(records)
    logger.info(
        f"  ACS: {len(df)} municipalities | "
        f"rent_burden non-null: {df['rent_burden_pct'].notna().sum()} | "
        f"home_value non-null: {df['median_home_value'].notna().sum()}"
    )
    return df


def _strip_suffix(name: str) -> str:
    """Remove Census geographic suffixes to get clean municipality names.

    'Cambridge city' → 'Cambridge'
    'Brookline town' → 'Brookline'
    'Gosnold town'   → 'Gosnold'
    """
    suffixes = (
        " town", " city", " plantation", " grant", " purchase",
        " gore", " district", " location",
    )
    lower = name.lower()
    for suffix in suffixes:
        if lower.endswith(suffix):
            return name[: -len(suffix)].strip()
    return name.strip()
