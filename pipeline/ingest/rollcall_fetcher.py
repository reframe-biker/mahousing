"""
rollcall_fetcher.py — Automated MA House roll call PDF downloader with caching.

Downloads the combined annual roll call PDFs from the MA Legislature Journal.
PDFs are cached at data/rollcall_cache/combined{year}_RollCalls_{session}.pdf.

Caching strategy:
  - Closed sessions (session != "194"): use cached PDF if it exists; never
    re-download. These PDFs are finalized once the session ends.
  - Current session ("194"): always re-download on each build run. New roll
    calls are appended throughout the session.

PDF URL:
  GET https://malegislature.gov/Journal/House/{session}/{year}/RollCalls
  This URL serves the combined annual PDF directly (not an HTML page).
  The response is validated by checking Content-Type or the %PDF magic bytes.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent.parent
_CACHE_DIR = _REPO_ROOT / "data" / "rollcall_cache"
_BILL_LIST_PATH = _REPO_ROOT / "data" / "legislator_bill_list.json"

CURRENT_SESSION = "194"

# Journal base URL
_JOURNAL_BASE = "https://malegislature.gov/Journal/House"


def get_rollcall_pdf(session: str, year: int) -> Optional[Path]:
    """
    Return a local path to the combined roll call PDF for (session, year).

    Downloads if necessary according to the caching strategy above.
    Returns None if the PDF cannot be found or downloaded.
    """
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _CACHE_DIR / f"combined{year}_RollCalls_{session}.pdf"

    # Closed sessions: use cache if available; never re-download
    if session != CURRENT_SESSION and cache_path.exists():
        logger.info(f"  Roll calls: using cached PDF for session {session}/{year}")
        return cache_path

    # Current session or cache miss: fetch fresh copy
    pdf_url = f"{_JOURNAL_BASE}/{session}/{year}/RollCalls"
    logger.info(f"  Roll calls: downloading {pdf_url}")
    try:
        resp = requests.get(pdf_url, verify=False, timeout=120, stream=True)
        resp.raise_for_status()

        # Validate that the response is actually a PDF
        content_type = resp.headers.get("Content-Type", "")
        # Read the first chunk to check magic bytes
        first_chunk = next(resp.iter_content(chunk_size=65536), b"")
        if "application/pdf" not in content_type and not first_chunk.startswith(b"%PDF"):
            logger.warning(
                f"  Roll calls: response for session {session}/{year} is not a PDF "
                f"(Content-Type: {content_type!r}) — the URL may have returned HTML"
            )
            if cache_path.exists():
                logger.warning(f"  Roll calls: using stale cache for session {session}/{year}")
                return cache_path
            return None

        with open(cache_path, "wb") as f:
            f.write(first_chunk)
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
        logger.info(f"  Roll calls: saved to {cache_path}")
        return cache_path
    except Exception as exc:
        logger.error(f"  Roll calls: download failed for session {session}/{year}: {exc}")
        if cache_path.exists():
            logger.warning(f"  Roll calls: using stale cache for session {session}/{year}")
            return cache_path
        return None


def derive_session_year_pairs() -> list[tuple[str, int]]:
    """
    Read data/legislator_bill_list.json and extract unique (session, year) pairs
    from all type=rollcall entries. Used by the pipeline to know which PDFs to fetch.
    """
    if not _BILL_LIST_PATH.exists():
        logger.warning(f"Bill list not found at {_BILL_LIST_PATH}")
        return []

    with open(_BILL_LIST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    bill_list = data["bills"] if isinstance(data, dict) else data

    pairs: set[tuple[str, int]] = set()
    for bill in bill_list:
        if bill.get("type") == "rollcall":
            session = str(bill.get("session", ""))
            year = int(bill.get("year", 0))
            if session and year:
                pairs.add((session, year))

    return sorted(pairs)


def get_current_session_pairs() -> list[tuple[str, int]]:
    """
    Always include the current session + current calendar year as a
    fetch target, even if no votes from that year are in the bill list.
    Ensures the roll call inventory stays current without requiring a
    placeholder entry to trigger the download.
    """
    return [(CURRENT_SESSION, date.today().year)]
