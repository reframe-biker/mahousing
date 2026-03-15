"""
leg_house_votes.py — MA House roll call PDF parser for the Report Card pipeline.

Parses the combined annual roll call PDFs from the MA Legislature Journal.
Each page contains one roll call in a 4-column grid layout:

    Y  Mr. Speaker   Y  Elliott       Y  Lipper-Garabedian  Y  Sousa
    Y  Moran M.      Y  Farley-Bouvier Y  Livingstone        Y  Stanley

PRIMARY ENTRY POINT:
    parse_rollcall_pdf(pdf_path) -> dict[int, dict[str, str]]

    Returns {supplement_number: {"UPPERCASED_NAME": "Y"|"N"|"X"|"P", ...}, ...}

    supplement_number is the roll call number (e.g., 117).
    Names are uppercased as they appear in the PDF — typically last names only,
    occasionally with first initial appended (e.g., "MORAN F").
"""

from __future__ import annotations

import logging
import re
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


def _parse_page(page_text: str) -> tuple[int | None, dict[str, str]]:
    """
    Parse a single roll call page.

    Returns (rc_number, {UPPERCASE_NAME: vote_char}) or (None, {}) if the
    page does not contain a recognizable roll call.
    """
    rc_number: int | None = None
    votes: dict[str, str] = {}

    for raw_line in page_text.splitlines():
        # Extract roll call number if not yet found
        if rc_number is None:
            m = _RC_NUM_RE.search(raw_line)
            if m:
                rc_number = int(m.group(1))
                continue

        if _should_skip(raw_line):
            continue

        line = _strip_after_vote_markers(raw_line)

        for vote_char, name in _VOTE_RE.findall(line):
            name = name.strip()
            if name:
                votes[name.upper()] = vote_char

    return rc_number, votes


def parse_rollcall_pdf(pdf_path: str | Path) -> dict[int, dict[str, str]]:
    """
    Parse a MA House combined annual roll call PDF.

    Args:
        pdf_path: Path to the combined annual PDF (e.g., combined2024_RollCalls_193.pdf).

    Returns:
        Dict mapping roll call supplement number → {UPPERCASE_NAME: vote_char}.
        vote_char is one of: "Y" (yea), "N" (nay), "X" (absent/not voting), "P" (present).

        Example:
            {117: {"JONES": "Y", "SMITH": "N", "MORAN F": "Y", ...}, ...}

    Notes:
        - Names are uppercased as they appear in the PDF (typically last names).
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

    results: dict[int, dict[str, str]] = {}
    skipped = 0

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text(layout=True) or ""
                rc_number, votes = _parse_page(page_text)

                if rc_number is None:
                    skipped += 1
                    continue

                if not votes:
                    logger.warning(f"  RC#{rc_number}: no votes parsed — skipped")
                    skipped += 1
                    continue

                if rc_number in results:
                    # Some roll calls span multiple pages — merge
                    results[rc_number].update(votes)
                else:
                    results[rc_number] = votes

    except Exception as exc:
        logger.error(f"Failed to parse {pdf_path}: {exc}")
        return {}

    logger.info(
        f"  Parsed {len(results)} roll calls from {Path(pdf_path).name} "
        f"({skipped} pages skipped)"
    )
    return results
