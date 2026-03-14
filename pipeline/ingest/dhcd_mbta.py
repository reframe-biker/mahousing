"""
dhcd_mbta.py — EOHLC MBTA Communities Act compliance ingest

Reads the official EOHLC "Compliance Status Sheet" CSV
(data/mbta_compliance_source.csv) and returns a DataFrame with MBTA
Communities Act status for all 177 subject municipalities.

Primary source:
    data/mbta_compliance_source.csv
    Downloaded from the EOHLC compliance tracking page. To update,
    replace this file with the latest CSV from:
    https://www.mass.gov/info-details/multi-family-zoning-requirement-for-mbta-communities
    The pipeline will automatically use the new data on next run.

CSV columns used:
    Municipality         — town name (may have trailing spaces)
    Compliance Status    — "Compliant" | "Interim Compliance" |
                           "Conditional Compliance" | "Noncompliant"
    Compliance Deadlines — date string, e.g. "12/31/2024"

Status mapping to internal values:
    "Compliant"              → "compliant"
    "Interim Compliance"     → "interim"
    "Conditional Compliance" → "interim"  (treated same as interim)
    "Noncompliant"           → "non-compliant"

Towns not listed in the CSV are outside the scope of the Act and
will have mbta_status = null in the output (not "exempt").

Function signature:
    get_mbta_data(name_to_fips: dict[str, str] | None = None) -> pd.DataFrame

Returned DataFrame columns:
    fips: str                 — 10-digit MA county subdivision GEOID
    mbta_status: str          — "compliant" | "interim" | "non-compliant"
    mbta_deadline: str | None — ISO date (YYYY-MM-DD) or None
    mbta_action_date: str | None — always None (not in this CSV)

TODO (optional upgrade paths — not called by default):
    - ArcGIS REST API: EOHLC publishes a feature service at
      https://services1.arcgis.com/... that may expose live data.
    - mass.gov HTML scrape: the compliance page at
      https://www.mass.gov/info-details/multi-family-zoning-requirement-for-mbta-communities
      can be scraped with requests + BeautifulSoup when the CSV
      is not available. See git history for the scraper implementation.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Path to the authoritative EOHLC compliance CSV, relative to repo root
_SOURCE_CSV = Path(__file__).parent.parent.parent / "data" / "mbta_compliance_source.csv"
_SOURCE_DATE = "2026-03-13"  # update when replacing the CSV

# Map CSV status strings → internal canonical values
_STATUS_MAP: dict[str, str] = {
    "compliant": "compliant",
    "interim compliance": "interim",
    "conditional compliance": "interim",  # treated same as interim
    "noncompliant": "non-compliant",
}


def _parse_date(raw: str) -> str | None:
    """Parse a date string from the CSV; return ISO date or None."""
    raw = raw.strip()
    if not raw or raw in ("-", "N/A", "TBD"):
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    logger.warning(f"  MBTA: Could not parse date '{raw}'")
    return None


def _normalize_name(name: str) -> str:
    """Lowercase and strip for matching."""
    name = name.lower().strip()
    for suffix in (" town", " city", " village", " cdp"):
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    return name


def _match_names(
    csv_names: list[str],
    name_to_fips: dict[str, str],
    threshold: int = 85,
) -> dict[str, str]:
    """Fuzzy-match CSV town names to canonical MA names → FIPS codes."""
    norm_lookup: dict[str, str] = {
        _normalize_name(k): fips for k, fips in name_to_fips.items()
    }
    canonical_norms = list(norm_lookup.keys())

    result: dict[str, str] = {}
    unmatched: list[str] = []

    for raw_name in csv_names:
        norm = _normalize_name(raw_name)
        if norm in norm_lookup:
            result[raw_name] = norm_lookup[norm]
            continue
        try:
            from thefuzz import process as fuzz_process  # type: ignore

            match = fuzz_process.extractOne(norm, canonical_norms, score_cutoff=threshold)
            if match:
                result[raw_name] = norm_lookup[match[0]]
            else:
                unmatched.append(raw_name)
        except ImportError:
            unmatched.append(raw_name)

    if unmatched:
        logger.warning(
            f"  MBTA: {len(unmatched)} town(s) could not be matched to FIPS: "
            + ", ".join(sorted(unmatched))
        )

    return result


def get_mbta_data(name_to_fips: Optional[dict] = None) -> pd.DataFrame:
    """
    Load MBTA Communities Act compliance data from the EOHLC CSV.

    Args:
        name_to_fips: Optional dict mapping canonical town name → FIPS.
                      If None, the fips column will be empty strings.

    Returns:
        DataFrame with columns: fips, mbta_status, mbta_deadline,
        mbta_action_date. Returns empty DataFrame if CSV is missing.
    """
    empty = pd.DataFrame(
        columns=["fips", "mbta_status", "mbta_deadline", "mbta_action_date"]
    )

    if not _SOURCE_CSV.exists():
        logger.error(
            f"  MBTA: Source CSV not found at {_SOURCE_CSV}. "
            "Download from EOHLC and place at data/mbta_compliance_source.csv."
        )
        return empty

    try:
        df = pd.read_csv(_SOURCE_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    except Exception as exc:
        logger.error(f"  MBTA: Failed to read source CSV: {exc}")
        return empty

    # Validate expected columns
    required = {"Municipality", "Compliance Status", "Compliance Deadlines"}
    if not required.issubset(df.columns):
        missing = required - set(df.columns)
        logger.error(f"  MBTA: Source CSV missing columns: {missing}")
        return empty

    records: list[dict] = []
    skipped = 0

    for _, row in df.iterrows():
        name = row["Municipality"].strip()
        status_raw = row["Compliance Status"].strip().lower()
        deadline_raw = row["Compliance Deadlines"].strip()

        if not name:
            skipped += 1
            continue

        status = _STATUS_MAP.get(status_raw)
        if status is None:
            logger.warning(f"  MBTA: Unknown status '{row['Compliance Status'].strip()}' for {name} — skipping")
            skipped += 1
            continue

        records.append(
            {
                "name": name,
                "mbta_status": status,
                "mbta_deadline": _parse_date(deadline_raw),
                "mbta_action_date": None,  # not available in this CSV
            }
        )

    logger.info(
        f"  MBTA data: mbta_compliance_source.csv "
        f"({len(records)} towns, as of {_SOURCE_DATE})"
    )
    if skipped:
        logger.warning(f"  MBTA: {skipped} rows skipped (unknown status or blank name)")

    if not records:
        return empty

    # Match names → FIPS
    csv_names = [r["name"] for r in records]
    if name_to_fips:
        match_map = _match_names(csv_names, name_to_fips)
        matched = sum(1 for n in csv_names if n in match_map)
        unmatched_count = len(csv_names) - matched
        logger.info(
            f"  MBTA: {matched}/{len(csv_names)} towns matched to FIPS"
            + (f" ({unmatched_count} unmatched)" if unmatched_count else "")
        )
    else:
        match_map = {}
        logger.warning("  MBTA: name_to_fips not provided — fips column will be empty")

    rows_out = [
        {
            "fips": match_map.get(r["name"], ""),
            "mbta_status": r["mbta_status"],
            "mbta_deadline": r["mbta_deadline"],
            "mbta_action_date": r["mbta_action_date"],
            "_name": r["name"],
        }
        for r in records
    ]

    result = pd.DataFrame(rows_out)
    counts = result["mbta_status"].value_counts().to_dict()
    logger.info(
        "  MBTA: Status counts — "
        + ", ".join(f"{s}={counts.get(s, 0)}" for s in ("compliant", "interim", "non-compliant"))
    )
    return result
