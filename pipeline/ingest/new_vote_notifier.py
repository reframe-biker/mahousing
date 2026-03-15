"""
new_vote_notifier.py — Detects new MA House roll call PDFs for the current session.

Maintains a manifest of known PDF URLs at data/rollcall_cache/manifest.json.
On each run, fetches the current session (194) journal directory pages and
compares PDF links found against the manifest. If new PDFs are detected,
prints a clear alert and updates the manifest.

IMPORTANT: This module NEVER scores votes automatically. Any new roll call PDF
requires manual editorial review before adding to data/legislator_bill_list.json.

Usage:
    python -m pipeline.ingest.new_vote_notifier     # standalone
    check_for_new_pdfs()                             # from build.py
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

import requests
from lxml import html

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent.parent
_CACHE_DIR = _REPO_ROOT / "data" / "rollcall_cache"
_MANIFEST_PATH = _CACHE_DIR / "manifest.json"

CURRENT_SESSION = "194"
_JOURNAL_BASE = "https://malegislature.gov/Journal/House"


def check_for_new_pdfs() -> list[str]:
    """
    Check for new roll call PDFs in the current session (194).

    Returns a list of newly detected PDF URLs (empty if none found).
    Prints alerts to stdout for any new PDFs detected.
    Updates the manifest to record newly found PDFs.
    """
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest()
    known_urls: set[str] = set(manifest.get("known_pdf_urls", []))

    current_urls = _find_current_session_pdfs()
    new_urls = [url for url in current_urls if url not in known_urls]

    if new_urls:
        for url in new_urls:
            print(
                f"\n{'='*70}\n"
                f"NEW ROLL CALL PDF DETECTED: {url}\n"
                f"Review the journal and add any housing-relevant votes to\n"
                f"data/legislator_bill_list.json if appropriate. Editorial\n"
                f"scoring decision is manual — do not add votes automatically.\n"
                f"{'='*70}\n"
            )
            logger.warning(f"NEW ROLL CALL PDF: {url}")

        # Update manifest with newly found PDFs
        manifest["known_pdf_urls"] = sorted(known_urls | set(new_urls))
        manifest["last_checked"] = date.today().isoformat()
        _save_manifest(manifest)
        logger.info(f"Manifest updated: {len(new_urls)} new PDF(s) added")
    else:
        logger.info(f"No new roll call PDFs for session {CURRENT_SESSION}")
        manifest["last_checked"] = date.today().isoformat()
        _save_manifest(manifest)

    return new_urls


def _find_current_session_pdfs() -> list[str]:
    """
    Fetch the current session journal directory and find all combined PDF URLs.

    Checks both the current year and previous year for the current session,
    since the session spans multiple calendar years.
    """
    today = date.today()
    years_to_check = sorted({today.year, today.year - 1})
    found_urls: list[str] = []

    for year in years_to_check:
        page_url = f"{_JOURNAL_BASE}/{CURRENT_SESSION}/{year}/RollCalls"
        try:
            resp = requests.get(page_url, verify=False, timeout=30)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
        except Exception as exc:
            logger.warning(f"  Notifier: could not fetch {page_url}: {exc}")
            continue

        tree = html.fromstring(resp.content)
        links = tree.xpath("//a/@href")
        pdf_links = [
            lnk for lnk in links
            if isinstance(lnk, str) and lnk.lower().endswith(".pdf")
        ]

        for lnk in pdf_links:
            if lnk.startswith("/"):
                lnk = "https://malegislature.gov" + lnk
            elif not lnk.startswith("http"):
                lnk = f"{_JOURNAL_BASE}/{CURRENT_SESSION}/{year}/{lnk}"
            if lnk not in found_urls:
                found_urls.append(lnk)

    return found_urls


def _load_manifest() -> dict:
    if _MANIFEST_PATH.exists():
        try:
            with open(_MANIFEST_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning(f"  Notifier: could not read manifest ({exc}); starting fresh")
    return {"known_pdf_urls": [], "last_checked": None}


def _save_manifest(manifest: dict) -> None:
    _MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    new = check_for_new_pdfs()
    if new:
        print(f"\n{len(new)} new PDF(s) detected. Review and update legislator_bill_list.json.")
        sys.exit(1)  # non-zero so CI can catch it
    else:
        print("No new roll call PDFs detected.")
        sys.exit(0)
