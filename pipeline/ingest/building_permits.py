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
    logger.info(f"Fetching Census BPS {BPS_YEAR} annual data from Northeast region file…")
    logger.info(f"  URL: {_BPS_URL}")

    try:
        resp = requests.get(_BPS_URL, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning(
            f"BPS flat file download failed: {exc}\n"
            f"  All municipalities will have null production grades."
        )
        return pd.DataFrame(columns=["geoid", "permits"])

    lines = resp.text.splitlines()

    # First 2 lines are a two-row header; skip them (plus the blank 3rd line)
    data_lines = [l for l in lines[3:] if l.strip()]

    records = []
    skipped = 0

    for line in data_lines:
        parts = line.split(",")
        if len(parts) < 28:
            skipped += 1
            continue

        state_code = parts[_COL_STATE].strip()
        if state_code != _MA_STATE_CODE:
            continue

        county = parts[_COL_COUNTY].strip().zfill(3)
        mcd = parts[_COL_MCD].strip().zfill(5)

        # Skip rows where MCD is "00000" (place-only records with no MCD)
        if mcd == "00000":
            continue

        geoid = _MA_STATE_CODE + county + mcd

        try:
            units = (
                _safe_int(parts[_COL_UNITS_1])
                + _safe_int(parts[_COL_UNITS_2])
                + _safe_int(parts[_COL_UNITS_34])
                + _safe_int(parts[_COL_UNITS_5P])
            )
        except Exception:
            skipped += 1
            continue

        records.append({"geoid": geoid, "permits": units})

    df = pd.DataFrame(records) if records else pd.DataFrame(columns=["geoid", "permits"])
    logger.info(
        f"  BPS: {len(df)} MA jurisdictions | "
        f"total units authorized: {df['permits'].sum() if not df.empty else 0:,} | "
        f"skipped rows: {skipped}"
    )
    return df


def _safe_int(val: str) -> int:
    """Parse an integer from a BPS field, returning 0 for blank or invalid values."""
    try:
        return int(val.strip())
    except (ValueError, AttributeError):
        return 0
