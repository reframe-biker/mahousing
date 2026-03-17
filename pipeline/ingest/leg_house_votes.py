"""
leg_house_votes.py — MA House roll call PDF parser for the Report Card pipeline.

Parses the combined annual roll call PDFs from the MA Legislature Journal.
Each page contains one roll call in a 4-column grid layout:

    Y  Mr. Speaker   Y  Elliott       Y  Lipper-Garabedian  Y  Sousa
    Y  Moran M.      Y  Farley-Bouvier Y  Livingstone        Y  Stanley

PRIMARY ENTRY POINT:
    parse_rollcall_pdf(pdf_path) -> dict[int, dict]

    Returns {supplement_number: {
        "bill": str|None,
        "motion": str|None,
        "date": str|None,
        "yeas": int,
        "nays": int,
        "nvs": int,
        "votes": {"UPPERCASED_NAME": "Y"|"N"|"X"|"P", ...}
    }, ...}

    supplement_number is the roll call number (e.g., 117).
    Names are uppercased as they appear in the PDF — typically last names only,
    occasionally with first initial appended (e.g., "MORAN F").
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Matches a vote token and the name that follows it.
# Uses \s+ (not \s{2,}) because the last column before EOL has only 1 space.
# After-vote entries like --Jones-- are pre-processed to strip the dashes.
_VOTE_RE = re.compile(
    r"([YNXP])\s+([A-Za-z][A-Za-z'\u2019\-.,\s]+?)(?=\s+[YNXP]\s|\s*$)"
)

# Roll call number line: "No. 117   145 YEAS   13 NAYS   1 N/V"
_RC_NUM_RE = re.compile(r"\bNo\.\s+(\d+)\b")

# Vote totals
_YEAS_RE = re.compile(r"\b(\d+)\s+YEAS\b", re.IGNORECASE)
_NAYS_RE = re.compile(r"\b(\d+)\s+NAYS\b", re.IGNORECASE)
_NVS_RE = re.compile(r"\b(\d+)\s+N/V\b", re.IGNORECASE)

# Bill number: "H. 4707", "H.4707", "S. 4000", etc.
_BILL_RE = re.compile(r"\b([HS]\.\s*\d+)\b")

# Motion text: appears after bill number on the header line
# "H. 4000 On adoption of amendment #1643" → "On adoption of amendment #1643"
_INLINE_MOTION_RE = re.compile(
    r"[HS]\.\s*\d+\s+((?:On|Amendment)\s+.+?)(?:\s{4,}|\s*$)",
    re.IGNORECASE,
)

# Date patterns: MM/DD/YYYY or "Month DD, YYYY"
_DATE_SLASH_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")
_DATE_MDY_RE = re.compile(r"([A-Z][a-z]+\s+\d{1,2},?\s*\d{4})")

# Lines to skip entirely (headers, separators, metadata)
_SKIP_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"MASSACHUSETTS HOUSE OF REPRESENTATIVES",
        r"^\s*Yea and Nay",
        r"^\s*\d{1,3}\s+YEAS",
        r"^\s*\d{1,3}\s+NAYS",
        r"^\s*\d{1,3}\s+N/V",
        r"^\s*={3,}",          # separator lines
        r"^\s*\f",             # form feed
        r"^\s*$",              # blank lines
        r"^\s*\d{1,2}:\d{2}",  # timestamp lines (HH:MM)
    ]
]


def _should_skip(line: str) -> bool:
    return any(p.search(line) for p in _SKIP_PATTERNS)


def _strip_after_vote_markers(line: str) -> str:
    """Convert '--Jones--' → 'Jones' so the name matches the regex character class."""
    return re.sub(r"--([A-Za-z][A-Za-z'\-.,\s]*?)--", r"\1", line)


def _extract_totals(line: str, meta: dict) -> None:
    """Extract YEAS/NAYS/N/V counts from a line into meta dict."""
    m = _YEAS_RE.search(line)
    if m:
        meta["yeas"] = int(m.group(1))
    m = _NAYS_RE.search(line)
    if m:
        meta["nays"] = int(m.group(1))
    m = _NVS_RE.search(line)
    if m:
        meta["nvs"] = int(m.group(1))


def _extract_date(line: str, meta: dict) -> None:
    """Try to extract a date from a line into meta["date"] as ISO YYYY-MM-DD."""
    m = _DATE_SLASH_RE.search(line)
    if m:
        try:
            dt = datetime.strptime(m.group(1), "%m/%d/%Y")
            meta["date"] = dt.strftime("%Y-%m-%d")
            return
        except ValueError:
            pass
    m = _DATE_MDY_RE.search(line)
    if m:
        text = m.group(1).strip()
        normalized = " ".join(text.replace(",", " ").split()[:3])
        for fmt in ("%B %d %Y", "%b %d %Y"):
            try:
                dt = datetime.strptime(normalized, fmt)
                meta["date"] = dt.strftime("%Y-%m-%d")
                return
            except ValueError:
                continue


def _parse_page(page_text: str) -> tuple[int | None, dict, dict[str, str]]:
    """
    Parse a single roll call page.

    PDF header structure (typical):
        Line: "H. 4000 On adoption of amendment #1643"     ← bill + motion
        Line: "Yea and Nay                  04/29/2025 12:33 PM"  ← date
        Line: "No. 35   26 YEAS   130 NAYS   2 N/V"        ← rc_number + totals

    Metadata extraction runs on ALL lines (before and after rc_number is found)
    so we capture bill/motion/date that appear before the "No." line.

    Returns (rc_number, metadata, votes) where:
        rc_number: int supplement number, or None if not found
        metadata: dict with keys bill, motion, date, yeas, nays, nvs
        votes: {UPPERCASE_NAME: vote_char}
    """
    rc_number: int | None = None
    votes: dict[str, str] = {}
    meta: dict = {"bill": None, "motion": None, "date": None, "yeas": 0, "nays": 0, "nvs": 0}

    for raw_line in page_text.splitlines():
        # Always extract metadata from every line (header lines come before "No.")
        _extract_totals(raw_line, meta)

        if meta["bill"] is None or meta["motion"] is None:
            mm = _INLINE_MOTION_RE.search(raw_line)
            if mm:
                if meta["bill"] is None:
                    bm = _BILL_RE.search(raw_line)
                    if bm:
                        meta["bill"] = bm.group(1)
                if meta["motion"] is None:
                    meta["motion"] = mm.group(1).strip()

        if meta["bill"] is None:
            bm = _BILL_RE.search(raw_line)
            if bm:
                meta["bill"] = bm.group(1)

        if meta["date"] is None:
            _extract_date(raw_line, meta)

        # Locate the roll call number
        if rc_number is None:
            m = _RC_NUM_RE.search(raw_line)
            if m:
                rc_number = int(m.group(1))
                continue  # "No." line is not a vote line

        if _should_skip(raw_line):
            continue

        line = _strip_after_vote_markers(raw_line)

        for vote_char, name in _VOTE_RE.findall(line):
            name = name.strip()
            if name:
                votes[name.upper()] = vote_char

    return rc_number, meta, votes


def parse_rollcall_pdf(pdf_path: str | Path) -> dict[int, dict]:
    """
    Parse a MA House combined annual roll call PDF.

    Args:
        pdf_path: Path to the combined annual PDF (e.g., combined2024_RollCalls_193.pdf).

    Returns:
        Dict mapping roll call supplement number → {
            "bill": str|None,
            "motion": str|None,
            "date": str|None,
            "yeas": int,
            "nays": int,
            "nvs": int,
            "votes": {"UPPERCASE_NAME": vote_char, ...}
        }
        vote_char is one of: "Y" (yea), "N" (nay), "X" (absent/not voting), "P" (present).

    Notes:
        - Names in "votes" are uppercased as they appear in the PDF.
        - Some entries use first-initial disambiguation: "MORAN F", "MORAN M", "MORAN J".
        - Pages without a recognizable roll call number are skipped.
        - An empty dict is returned if the PDF cannot be parsed.
    """
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError(
            "pdfplumber is required for PDF parsing. "
            "Install with: pip install pdfplumber"
        ) from exc

    logger.info(f"Parsing roll call PDF: {pdf_path}")

    results: dict[int, dict] = {}
    skipped = 0

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text(layout=True) or ""
                rc_number, meta, votes = _parse_page(page_text)

                if rc_number is None:
                    skipped += 1
                    continue

                if not votes:
                    logger.warning(f"  RC#{rc_number}: no votes parsed — skipped")
                    skipped += 1
                    continue

                if rc_number in results:
                    # Some roll calls span multiple pages — merge votes, keep existing meta
                    results[rc_number]["votes"].update(votes)
                else:
                    results[rc_number] = {**meta, "votes": votes}

    except Exception as exc:
        logger.error(f"Failed to parse {pdf_path}: {exc}")
        return {}

    logger.info(
        f"  Parsed {len(results)} roll calls from {Path(pdf_path).name} "
        f"({skipped} pages skipped)"
    )
    return results
