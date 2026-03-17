"""
new_vote_notifier.py — Detects new MA House roll call PDFs for the current session.

Maintains a manifest of known PDF URLs at data/rollcall_cache/manifest.json.
On each run, fetches the current session (194) journal directory pages and
compares PDF links found against the manifest. If new PDFs are detected,
prints a clear alert, reads rollcall_inventory.json for housing-keyword hits,
and sends an email alert via Resend (if configured).

IMPORTANT: This module NEVER scores votes automatically. Any new roll call PDF
requires manual editorial review before adding to data/legislator_bill_list.json.

Email configuration (all optional — missing vars skip email silently):
    RESEND_API_KEY     Resend API key
    ALERT_EMAIL_TO     Recipient address
    ALERT_EMAIL_FROM   Sender address (must be a verified domain in Resend)

Usage:
    python -m pipeline.ingest.new_vote_notifier     # standalone
    check_for_new_pdfs()                             # from build.py
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Optional

import requests
from lxml import html

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent.parent
_CACHE_DIR = _REPO_ROOT / "data" / "rollcall_cache"
_MANIFEST_PATH = _CACHE_DIR / "manifest.json"
_INVENTORY_PATH = _REPO_ROOT / "data" / "rollcall_inventory.json"

_HOUSING_KEYWORDS = [
    "housing", "mbta", "40b", "adu", "zoning", "affordable",
    "chapter 40", "inclusionary",
]

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

        housing_hits = _find_housing_hits()
        _send_housing_alert(new_urls, housing_hits)
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


def _find_housing_hits() -> list[dict]:
    """
    Read data/rollcall_inventory.json and return entries whose motion text
    contains any housing-relevant keyword (case-insensitive).

    Returns an empty list if the inventory file does not exist or cannot be read.
    """
    if not _INVENTORY_PATH.exists():
        logger.warning("  Notifier: rollcall_inventory.json not found — skipping keyword scan")
        return []
    try:
        with open(_INVENTORY_PATH, encoding="utf-8") as f:
            inventory = json.load(f)
    except Exception as exc:
        logger.warning(f"  Notifier: could not read rollcall_inventory.json: {exc}")
        return []

    hits: list[dict] = []
    for entry in inventory:
        motion = (entry.get("motion") or "").lower()
        if any(kw in motion for kw in _HOUSING_KEYWORDS):
            hits.append(entry)
    return hits


def _build_email_body(new_pdf_urls: list[str], housing_hits: list[dict]) -> str:
    """Build the plain-text email body for a new-PDF alert."""
    lines: list[str] = ["New roll call PDFs detected in session 194:", ""]
    for url in new_pdf_urls:
        lines.append(f"  {url}")
    lines.append("")

    if housing_hits:
        lines.append(f"Housing-keyword matches in rollcall_inventory.json ({len(housing_hits)}):")
        lines.append("")
        for hit in housing_hits:
            lines.append(
                f"  RC#{hit.get('rc_number')}  "
                f"session={hit.get('session')}  year={hit.get('year')}  "
                f"yeas={hit.get('yeas')}  nays={hit.get('nays')}"
            )
            lines.append(f"    motion: {hit.get('motion')}")
        lines.append("")
    else:
        lines.append("No housing-keyword matches found in rollcall_inventory.json.")
        lines.append("")

    lines.append(
        "Review rollcall_inventory.json and add any relevant votes to "
        "data/legislator_bill_list.json. Do not score automatically."
    )
    return "\n".join(lines)


def _send_housing_alert(new_pdf_urls: list[str], housing_hits: list[dict]) -> None:
    """
    Send a Resend email listing new PDFs and any housing-keyword roll call hits.
    Silently skips if RESEND_API_KEY, ALERT_EMAIL_TO, or ALERT_EMAIL_FROM
    are not set.
    """
    api_key = os.environ.get("RESEND_API_KEY")
    to_email = os.environ.get("ALERT_EMAIL_TO")
    from_email = os.environ.get("ALERT_EMAIL_FROM")

    if not all([api_key, to_email, from_email]):
        logger.warning(
            "Email alert skipped — RESEND_API_KEY, ALERT_EMAIL_TO, or "
            "ALERT_EMAIL_FROM not set."
        )
        return

    try:
        import resend
    except ImportError:
        logger.warning("  Notifier: resend package not installed — email alert skipped")
        return

    try:
        resend.api_key = api_key
        resend.Emails.send({
            "from": from_email,
            "to": to_email,
            "subject": "MA Housing Report Card — New Roll Calls Detected",
            "text": _build_email_body(new_pdf_urls, housing_hits),
        })
        logger.info("Housing alert email sent via Resend")
    except Exception as exc:
        logger.warning(f"Failed to send alert email: {exc}")


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
