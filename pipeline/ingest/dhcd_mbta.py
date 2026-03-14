"""
dhcd_mbta.py — EOHLC/DHCD MBTA Communities Act compliance ingest

Scrapes the MA Executive Office of Housing and Livable Communities (EOHLC)
compliance status page and returns a DataFrame with MBTA Communities Act
status for each subject municipality.

Source:
    https://www.mass.gov/info-details/multi-family-zoning-requirement-for-mbta-communities

The page lists the ~177 municipalities subject to the MBTA Communities Act.
Towns not appearing on that page are assumed exempt (not subject to the Act).

Data source priority:
    1. Live EOHLC/DHCD page (fetched on every pipeline run)
    2. data/mbta_status_override.csv fallback (used when live page is
       unavailable, e.g. local dev blocked by Cloudflare, or during outages)

Function signature:
    get_mbta_data(name_to_fips: dict[str, str] | None = None) -> pd.DataFrame

Returned DataFrame columns:
    fips: str                 — 10-digit MA county subdivision GEOID
    mbta_status: str          — "compliant" | "interim" | "non-compliant" |
                                "pending" | "exempt"
    mbta_deadline: str | None — ISO date (YYYY-MM-DD) or None
    mbta_action_date: str | None — ISO date of most recent town action, or None
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DHCD_URL = "https://www.mass.gov/info-details/multi-family-zoning-requirement-for-mbta-communities"
REQUEST_TIMEOUT = 30  # seconds

# Optional local override CSV — checked before live scraping.
# Format: name,mbta_status,mbta_deadline,mbta_action_date
# Status values: compliant | interim | non-compliant | pending | exempt
# Dates in YYYY-MM-DD or M/D/YYYY format, empty string for null.
# Update this file manually from the DHCD page when the live scrape is blocked.
_OVERRIDE_CSV = Path(__file__).parent.parent.parent / "data" / "mbta_status_override.csv"

# Map text patterns found on the DHCD page to canonical status values
_STATUS_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"non.?compliant", re.I), "non-compliant"),
    (re.compile(r"compliant", re.I), "compliant"),
    (re.compile(r"interim", re.I), "interim"),
    (re.compile(r"pending", re.I), "pending"),
    (re.compile(r"under review", re.I), "pending"),
    (re.compile(r"submitted", re.I), "pending"),
]


def _canonicalize_status(raw: str) -> str | None:
    """Map a raw status string from the DHCD page to a canonical value."""
    raw = raw.strip()
    for pattern, canonical in _STATUS_MAP:
        if pattern.search(raw):
            return canonical
    return None


def _normalize_name(name: str) -> str:
    """Lowercase, strip, remove common suffixes for fuzzy matching."""
    name = name.lower().strip()
    # Remove trailing "town", "city", "village" suffixes added by Census
    for suffix in (" town", " city", " village", " cdp"):
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    return name


def _parse_date(raw: str) -> str | None:
    """Try common date formats; return ISO date string or None."""
    raw = raw.strip()
    if not raw or raw in ("-", "N/A", "n/a", "TBD", "tbd"):
        return None
    for fmt in ("%m/%d/%Y", "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _match_names(
    scraped_names: list[str],
    name_to_fips: dict[str, str],
    threshold: int = 85,
) -> dict[str, str]:
    """
    Fuzzy-match scraped town names to canonical MA names.

    Returns a dict mapping scraped_name → fips for matched towns.
    """
    # Build a normalized lookup: normalized_canonical → fips
    norm_lookup: dict[str, str] = {
        _normalize_name(k): fips for k, fips in name_to_fips.items()
    }
    canonical_norms = list(norm_lookup.keys())

    result: dict[str, str] = {}
    unmatched: list[str] = []

    for raw_name in scraped_names:
        norm = _normalize_name(raw_name)

        # Exact match first
        if norm in norm_lookup:
            result[raw_name] = norm_lookup[norm]
            continue

        # Fuzzy match using thefuzz
        try:
            from thefuzz import process as fuzz_process  # type: ignore

            match = fuzz_process.extractOne(norm, canonical_norms, score_cutoff=threshold)
            if match:
                result[raw_name] = norm_lookup[match[0]]
            else:
                unmatched.append(raw_name)
        except ImportError:
            # thefuzz not installed — fall back to exact only
            unmatched.append(raw_name)

    if unmatched:
        logger.warning(
            f"  MBTA: {len(unmatched)} town(s) could not be matched to FIPS: "
            + ", ".join(sorted(unmatched)[:20])
            + ("…" if len(unmatched) > 20 else "")
        )

    return result


def _parse_table(soup: BeautifulSoup) -> list[dict]:
    """
    Attempt to parse an HTML table on the DHCD page.

    Looks for a <table> element with a header row containing 'municipality' or
    'community' and tries to extract status, deadline, and action date columns.

    Returns a list of dicts with keys: name, status_raw, deadline_raw, action_raw.
    """
    rows: list[dict] = []

    for table in soup.find_all("table"):
        # Find header row
        headers_raw = []
        thead = table.find("thead")
        if thead:
            headers_raw = [th.get_text(strip=True).lower() for th in thead.find_all(["th", "td"])]
        elif table.find("tr"):
            first_row = table.find("tr")
            headers_raw = [th.get_text(strip=True).lower() for th in first_row.find_all(["th", "td"])]

        if not headers_raw:
            continue

        # Check this table has a municipality/community column
        name_col = None
        for i, h in enumerate(headers_raw):
            if any(kw in h for kw in ("municipality", "community", "town", "city")):
                name_col = i
                break
        if name_col is None:
            continue

        # Find status, deadline, action date columns (best-effort)
        status_col = None
        deadline_col = None
        action_col = None
        for i, h in enumerate(headers_raw):
            if "status" in h and status_col is None:
                status_col = i
            if "deadline" in h and deadline_col is None:
                deadline_col = i
            if any(kw in h for kw in ("action", "date", "adopted", "approved")) and action_col is None:
                action_col = i

        # Parse data rows
        tbody = table.find("tbody") or table
        for tr in tbody.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if not cells or len(cells) <= name_col:
                continue
            name = cells[name_col]
            if not name or name.lower() in ("municipality", "community", "town"):
                continue  # skip header rows

            status_raw = cells[status_col] if status_col is not None and status_col < len(cells) else ""
            deadline_raw = cells[deadline_col] if deadline_col is not None and deadline_col < len(cells) else ""
            action_raw = cells[action_col] if action_col is not None and action_col < len(cells) else ""

            rows.append(
                {
                    "name": name,
                    "status_raw": status_raw,
                    "deadline_raw": deadline_raw,
                    "action_raw": action_raw,
                }
            )

        if rows:
            logger.info(f"  MBTA: Parsed {len(rows)} rows from table")
            return rows

    return rows


def _parse_sections(soup: BeautifulSoup) -> list[dict]:
    """
    Fallback: parse a section-based page where headings label status groups and
    lists below them contain town names.

    E.g.:
      <h2>Compliant</h2>
      <ul><li>Abington</li>…</ul>
    """
    rows: list[dict] = []
    current_status = None

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "li", "p"]):
        text = tag.get_text(strip=True)
        if tag.name in ("h1", "h2", "h3", "h4"):
            status = _canonicalize_status(text)
            if status:
                current_status = status
        elif tag.name in ("li", "p") and current_status:
            # Each <li> under a status heading is a town name
            name = text.strip()
            if name and len(name) > 2:
                rows.append(
                    {
                        "name": name,
                        "status_raw": current_status,
                        "deadline_raw": "",
                        "action_raw": "",
                    }
                )

    if rows:
        logger.info(f"  MBTA: Parsed {len(rows)} entries from sections")

    return rows


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def _fetch_page() -> BeautifulSoup | None:
    """Fetch the DHCD compliance page. Returns None on network/HTTP failure."""
    try:
        resp = requests.get(DHCD_URL, timeout=REQUEST_TIMEOUT, headers=_HEADERS)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as exc:
        logger.warning(f"  MBTA: Failed to fetch DHCD page: {exc}")
        return None


def _load_override_csv() -> pd.DataFrame | None:
    """Load the local override CSV fallback. Returns None if file not present."""
    if not _OVERRIDE_CSV.exists():
        return None
    try:
        df = pd.read_csv(_OVERRIDE_CSV, dtype=str).fillna("")
        required = {"name", "mbta_status"}
        if not required.issubset(df.columns):
            logger.warning(f"  MBTA: Override CSV missing required columns {required - set(df.columns)}")
            return None
        if "mbta_deadline" not in df.columns:
            df["mbta_deadline"] = ""
        if "mbta_action_date" not in df.columns:
            df["mbta_action_date"] = ""
        logger.info(f"  MBTA: Using local override CSV ({len(df)} rows): {_OVERRIDE_CSV}")
        return df
    except Exception as exc:
        logger.warning(f"  MBTA: Failed to load override CSV: {exc}")
        return None


def get_mbta_data(name_to_fips: Optional[dict] = None) -> pd.DataFrame:
    """
    Scrape DHCD compliance page and return MBTA status for each subject town.

    Args:
        name_to_fips: Optional dict mapping canonical town name → FIPS.
                      If None, returned DataFrame will have empty fips column
                      and build.py must join by name.

    Returns:
        DataFrame with columns:
            fips: str (may be empty string if name_to_fips not provided)
            mbta_status: str
            mbta_deadline: str | None
            mbta_action_date: str | None

        Returns empty DataFrame (correct columns) on scrape failure.
    """
    empty = pd.DataFrame(
        columns=["fips", "mbta_status", "mbta_deadline", "mbta_action_date"]
    )

    # Priority 1: live EOHLC/DHCD page
    soup = _fetch_page()
    if soup is not None:
        raw_rows = _parse_table(soup)
        if not raw_rows:
            raw_rows = _parse_sections(soup)
        if raw_rows:
            logger.info("  MBTA data: live DHCD page")
        else:
            logger.warning("  MBTA: Live page fetched but no rows parsed — falling back to override CSV")
            soup = None  # fall through to CSV

    # Priority 2: local override CSV (offline / Cloudflare-blocked environments)
    if soup is None:
        override_df = _load_override_csv()
        if override_df is None:
            logger.warning("  MBTA: No live data and no override CSV — returning empty")
            return empty
        logger.info("  MBTA data: override CSV fallback")
        raw_rows = [
            {
                "name": row["name"],
                "status_raw": row["mbta_status"],
                "deadline_raw": row.get("mbta_deadline", ""),
                "action_raw": row.get("mbta_action_date", ""),
            }
            for _, row in override_df.iterrows()
        ]

    # Resolve status for each row
    records: list[dict] = []
    for row in raw_rows:
        status = _canonicalize_status(row["status_raw"]) if row["status_raw"] else None
        # If no status column, the section heading already put the canonical value in status_raw
        if status is None and row["status_raw"] in ("compliant", "non-compliant", "interim", "pending", "exempt"):
            status = row["status_raw"]
        if status is None:
            continue

        deadline = _parse_date(row.get("deadline_raw", ""))
        action = _parse_date(row.get("action_raw", ""))
        records.append(
            {
                "name": row["name"],
                "mbta_status": status,
                "mbta_deadline": deadline,
                "mbta_action_date": action,
            }
        )

    if not records:
        logger.warning("  MBTA: No usable records after status parsing")
        return empty

    # Match names → FIPS
    scraped_names = [r["name"] for r in records]

    if name_to_fips:
        match_map = _match_names(scraped_names, name_to_fips)
        matched = sum(1 for n in scraped_names if n in match_map)
        unmatched = len(scraped_names) - matched
        logger.info(f"  MBTA: {matched}/{len(scraped_names)} towns matched to FIPS ({unmatched} unmatched)")
    else:
        match_map = {}
        logger.warning("  MBTA: name_to_fips not provided — fips column will be empty")

    rows_out: list[dict] = []
    for rec in records:
        fips = match_map.get(rec["name"], "")
        rows_out.append(
            {
                "fips": fips,
                "mbta_status": rec["mbta_status"],
                "mbta_deadline": rec["mbta_deadline"],
                "mbta_action_date": rec["mbta_action_date"],
                "_name": rec["name"],  # keep for name-based join if fips unavailable
            }
        )

    df = pd.DataFrame(rows_out)
    logger.info(
        f"  MBTA: {len(df)} subject towns scraped. "
        f"Status counts: "
        + ", ".join(
            f"{s}={n}"
            for s, n in df["mbta_status"].value_counts().items()
        )
    )
    return df
