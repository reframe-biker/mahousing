"""
building_permits.py — Census Building Permits Survey ingest for MA Housing Report Card

Fetches annual residential building permit data for Massachusetts municipalities
from the Census Bureau Building Permits Survey (BPS) regional flat files.

File source: https://www2.census.gov/econ/bps/Place/Northeast%20Region/
Annual December files follow the naming convention ne{YY}12y.txt where YY is
the 2-digit year (e.g. ne2312y.txt for the full-year 2023 annual report).

These files cover all permit-issuing jurisdictions in the Northeast, which
includes all 351 MA cities and towns. MA rows are identified by state code "25".

Column layout (0-indexed, comma-separated):
  [0]  Survey Date (YYYYMM)
  [1]  State Code (FIPS)
  [2]  6-Digit ID
  [3]  County Code (3-digit FIPS county)
  [4]  Census Place Code
  [5]  FIPS Place Code
  [6]  FIPS MCD Code (5-digit county subdivision code — joins to ACS GEOID)
  [7]  Population
  ...
  [15] Number of Months Reported
  [16] Place Name
  [17] 1-unit Bldgs     [18] 1-unit Units     [19] 1-unit Value
  [20] 2-unit Bldgs     [21] 2-unit Units      [22] 2-unit Value
  [23] 3-4 unit Bldgs   [24] 3-4 unit Units    [25] 3-4 unit Value
  [26] 5+ unit Bldgs    [27] 5+ unit Units     [28] 5+ unit Value
  [29] 1-unit rep Bldgs [30] 1-unit rep Units  [31] 1-unit rep Value
  [32] 2-unit rep Bldgs [33] 2-unit rep Units  [34] 2-unit rep Value
  [35] 3-4 unit rep Bldgs [36] 3-4 unit rep Units [37] 3-4 unit rep Value
  [38] 5+ unit rep Bldgs  [39] 5+ unit rep Units  [40] 5+ unit rep Value

We use the raw (non-represented) unit counts [18,21,24,27] for the December
annual file, which contains the full-year cumulative data for most reporters.

GEOID construction: state_code (col 1) + county_code (col 3) + mcd_code (col 6)
= 10-digit county subdivision GEOID, which joins directly to the ACS GEOID.
"""

import logging

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Annual December BPS file for the Northeast region.
# The December annual file contains full-year cumulative permit counts.
# Update BPS_YEAR to use a more recent vintage when available.
BPS_YEAR = 2023
_BPS_URL = (
    f"https://www2.census.gov/econ/bps/Place/Northeast%20Region/"
    f"ne{str(BPS_YEAR)[2:]}12y.txt"
)

# MA state FIPS code as it appears in the BPS file (column 1)
_MA_STATE_CODE = "25"

# Column indices for the fields we need
_COL_STATE = 1
_COL_COUNTY = 3
_COL_MCD = 6         # FIPS MCD Code (county subdivision)
_COL_MONTHS = 15     # Number of months reported
_COL_NAME = 16       # Place name
_COL_UNITS_1 = 18    # 1-unit structures: total units
_COL_UNITS_2 = 21    # 2-unit structures: total units
_COL_UNITS_34 = 24   # 3-4 unit structures: total units
_COL_UNITS_5P = 27   # 5+ unit structures: total units

_REQUEST_TIMEOUT = 60


def fetch_permit_data(api_key: str | None = None) -> pd.DataFrame:
    """
    Download and parse the BPS Northeast annual flat file for MA municipalities.

    The api_key parameter is accepted for interface compatibility with other
    ingest modules but is not used — BPS flat files are publicly available
    without authentication.

    Returns:
        DataFrame with columns:
            geoid   (str)  10-digit county subdivision GEOID (joins to ACS)
            permits (int)  Total housing units authorized in BPS_YEAR

        Returns an empty DataFrame (with correct columns) if the download
        fails or no MA data is found.
    """
    raw = fetch_permit_breakdown(BPS_YEAR)
    if raw.empty:
        return pd.DataFrame(columns=["geoid", "permits"])
    return raw[["geoid", "permits"]]


def fetch_permit_breakdown(year: int) -> pd.DataFrame:
    """
    Download and parse one year of BPS data, returning per-structure-type unit counts.

    Used by zoning_permits_proxy to compute multifamily unit share across multiple years.

    Args:
        year: 4-digit calendar year (e.g. 2023). Must match an available BPS annual file.

    Returns:
        DataFrame with columns:
            geoid     (str)  10-digit county subdivision GEOID
            units_5p  (int)  Units in 5+ unit structures
            permits   (int)  Total units across all structure types

        Returns an empty DataFrame (with correct columns) on download failure.
    """
    url = (
        f"https://www2.census.gov/econ/bps/Place/Northeast%20Region/"
        f"ne{str(year)[2:]}12y.txt"
    )
    logger.info(f"Fetching Census BPS {year} annual data…")
    logger.info(f"  URL: {url}")

    try:
        resp = requests.get(url, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning(
            f"BPS {year} flat file download failed: {exc}\n"
            f"  Year {year} will be excluded from permit calculations."
        )
        return pd.DataFrame(columns=["geoid", "units_5p", "permits"])

    lines = resp.text.splitlines()
    data_lines = [l for l in lines[3:] if l.strip()]

    records = []
    skipped = 0
    non_ma_dropped = 0

    for line in data_lines:
        parts = line.split(",")
        if len(parts) < 28:
            skipped += 1
            continue

        # ── State FIPS filter ──────────────────────────────────────────────
        # BPS Northeast region files contain records for all states in the
        # region (CT, ME, MA, NH, NJ, NY, PA, RI, VT).  We keep only MA
        # (state FIPS 25).  Any row with a different state code is dropped
        # before GEOID construction so there is no risk of county/MCD codes
        # from another state colliding with a MA GEOID.
        state_code = parts[_COL_STATE].strip()
        if state_code != _MA_STATE_CODE:
            non_ma_dropped += 1
            continue

        county = parts[_COL_COUNTY].strip().zfill(3)
        mcd = parts[_COL_MCD].strip().zfill(5)

        if mcd == "00000":
            continue

        # Use state_code from the record (validated == _MA_STATE_CODE above)
        # rather than the hardcoded constant, so the GEOID is visibly derived
        # from the source data.
        geoid = state_code + county + mcd

        try:
            u1   = _safe_int(parts[_COL_UNITS_1])
            u2   = _safe_int(parts[_COL_UNITS_2])
            u34  = _safe_int(parts[_COL_UNITS_34])
            u5p  = _safe_int(parts[_COL_UNITS_5P])
        except Exception:
            skipped += 1
            continue

        records.append({
            "geoid":    geoid,
            "units_5p": u5p,
            "permits":  u1 + u2 + u34 + u5p,
        })

    df = pd.DataFrame(records) if records else pd.DataFrame(columns=["geoid", "units_5p", "permits"])
    logger.info(
        f"  BPS {year}: {len(df)} MA jurisdictions | "
        f"total units: {df['permits'].sum() if not df.empty else 0:,} | "
        f"non-MA rows dropped: {non_ma_dropped} | "
        f"malformed rows skipped: {skipped}"
    )

    # ── Diagnostic: log raw values for any GEOID flagged for inspection ───
    _log_diagnostic_geoids(df, year)

    return df


# GEOIDs to log in detail whenever their raw BPS data is parsed.
# Add a GEOID here to investigate anomalous permit values.
_DIAGNOSTIC_GEOIDS: dict[str, str] = {
    "2502117405": "Dover, MA",       # 2023 BPS shows 34 5+ unit permits — tracking
}


def _log_diagnostic_geoids(df: pd.DataFrame, year: int) -> None:
    """Log raw permit values for GEOIDs listed in _DIAGNOSTIC_GEOIDS."""
    if df.empty:
        return
    for geoid, label in _DIAGNOSTIC_GEOIDS.items():
        row = df[df["geoid"] == geoid]
        if row.empty:
            logger.debug(f"  Diagnostic [{label}] {geoid}: not present in {year} BPS data")
        else:
            r = row.iloc[0]
            logger.info(
                f"  Diagnostic [{label}] {geoid} in {year}: "
                f"units_5p={r['units_5p']}  total_permits={r['permits']}"
            )


def _safe_int(val: str) -> int:
    """Parse an integer from a BPS field, returning 0 for blank or invalid values."""
    try:
        return int(val.strip())
    except (ValueError, AttributeError):
        return 0
