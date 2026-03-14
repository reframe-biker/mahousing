"""
zillow.py — Zillow ZHVI ingest for MA Housing Report Card

Downloads the Zillow Home Value Index (ZHVI) city-level time series CSV and
extracts the most recent month's value for Massachusetts municipalities.
The ZHVI represents the typical home value (smoothed, seasonally adjusted)
for the middle tier (33rd–67th percentile) of single-family residences and
condos/co-ops.

The join to MA municipalities is name-based (Zillow city name → Census
municipality name). Because Zillow's city boundaries do not always match
Census county subdivision boundaries, the join is best-effort:
  - Matches are logged.
  - Mismatches result in a null median_home_value from Zillow (the ACS
    estimate is used instead).
  - A summary of match rate is logged at the end.

If the Zillow URL is unreachable or the CSV format changes, this module
returns an empty DataFrame and the pipeline continues without Zillow data.

Source: Zillow Research — ZHVI All Homes (SFR, Condo/Co-op), Time Series,
Smoothed, Seasonally Adjusted, City level
Data: https://www.zillow.com/research/data/
"""

import io
import logging
import os

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Zillow city-level ZHVI CSV (all homes, middle tier, smoothed + seasonally adjusted)
# Override via ZILLOW_DATA_URL environment variable.
_DEFAULT_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/"
    "City_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)

_REQUEST_TIMEOUT = 60  # seconds


def fetch_zillow_data(url: str | None = None) -> pd.DataFrame:
    """
    Download and parse the Zillow ZHVI city-level CSV for Massachusetts.

    Args:
        url: Direct URL to the Zillow ZHVI CSV. Defaults to ZILLOW_DATA_URL
             environment variable, then the hardcoded Zillow static URL.

    Returns:
        DataFrame with columns:
            name  (str)    Municipality name (un-normalized, from Zillow)
            zhvi  (float)  Most recent month's ZHVI value in USD

        Returns an empty DataFrame (with the correct columns) if the download
        fails or MA rows cannot be found. The pipeline continues without
        Zillow data; median_home_value falls back to the ACS estimate.
    """
    url = url or os.environ.get("ZILLOW_DATA_URL", _DEFAULT_URL)
    logger.info(f"Fetching Zillow ZHVI from:\n  {url}")

    try:
        resp = requests.get(url, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning(
            f"Zillow fetch failed: {exc}\n"
            f"  median_home_value will use Census ACS estimates only."
        )
        return pd.DataFrame(columns=["name", "zhvi"])

    try:
        df = pd.read_csv(io.BytesIO(resp.content))
    except Exception as exc:
        logger.warning(f"Zillow CSV parse failed: {exc}")
        return pd.DataFrame(columns=["name", "zhvi"])

    logger.info(f"  Downloaded {len(df)} rows, {len(df.columns)} columns")

    # Filter to Massachusetts
    state_col = _find_state_col(df)
    if state_col is None:
        logger.warning(
            f"Zillow: cannot identify state column. "
            f"Columns: {list(df.columns[:10])}…"
        )
        return pd.DataFrame(columns=["name", "zhvi"])

    ma_df = df[df[state_col].str.upper() == "MA"].copy()
    logger.info(f"  {len(ma_df)} MA rows found")

    if ma_df.empty:
        logger.warning("Zillow: no Massachusetts rows found in the CSV.")
        return pd.DataFrame(columns=["name", "zhvi"])

    # Identify the city/region name column
    name_col = _find_name_col(df)
    if name_col is None:
        logger.warning(f"Zillow: cannot identify city name column. Columns: {list(df.columns[:10])}…")
        return pd.DataFrame(columns=["name", "zhvi"])

    # The date columns are named like "2024-01-31". Find the most recent one.
    date_cols = _find_date_columns(df)
    if not date_cols:
        logger.warning("Zillow: cannot identify date columns in the CSV.")
        return pd.DataFrame(columns=["name", "zhvi"])

    latest_col = sorted(date_cols)[-1]
    logger.info(f"  Using most recent date column: {latest_col}")

    result = ma_df[[name_col, latest_col]].copy()
    result = result.rename(columns={name_col: "name", latest_col: "zhvi"})
    result = result.dropna(subset=["zhvi"])
    result["zhvi"] = pd.to_numeric(result["zhvi"], errors="coerce")
    result = result.dropna(subset=["zhvi"])

    logger.info(f"  Zillow: {len(result)} MA municipalities with ZHVI data")
    return result.reset_index(drop=True)


def _find_state_col(df: pd.DataFrame) -> str | None:
    """Return the column name for the state abbreviation field."""
    candidates = ["State", "state", "StateName", "state_name", "ST"]
    for c in candidates:
        if c in df.columns:
            return c
    # Try case-insensitive search
    lower_map = {col.lower(): col for col in df.columns}
    for c in ["state", "statename", "st"]:
        if c in lower_map:
            return lower_map[c]
    return None


def _find_name_col(df: pd.DataFrame) -> str | None:
    """Return the column name for the city/region name field."""
    candidates = ["RegionName", "regionname", "CityName", "city", "City", "Region"]
    for c in candidates:
        if c in df.columns:
            return c
    lower_map = {col.lower(): col for col in df.columns}
    for c in ["regionname", "cityname", "city", "region"]:
        if c in lower_map:
            return lower_map[c]
    return None


def _find_date_columns(df: pd.DataFrame) -> list[str]:
    """Return column names that look like ISO date strings (YYYY-MM-DD)."""
    import re
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    return [col for col in df.columns if date_pattern.match(str(col))]
