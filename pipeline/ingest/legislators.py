"""
legislators.py — State legislator housing scorecard for MA Housing Report Card

Phase 4a: MA House of Representatives only. Senate uses a different PDF
format (per-journal-date rather than combined annual) and is Phase 4b.

BUILD SEQUENCE:
  1. Build data/town_district_map.json (spatial join — slow, cached)
     Maps 10-digit town GEOID → House district name.
     Guard: skip if file already exists.
     # Rebuild after redistricting (~2031): delete this file to trigger rebuild

  2. Load legislators from data/ma_legislators.csv (Open States export).
     Filter to current_chamber == "lower". 158 members (2 vacancies expected).
     Two towns with vacant seats will receive null grades — this is correct.

  3. Fetch vote data:
     - type=rollcall: parse combined annual PDF, look up by supplement_number
     - type=cosponsor: GET CoSponsor API, extract full names

  4. Score each legislator:
     Earned points / eligible points × 100 = pct_score
     Session filtering: reps are scored only on votes during their term.
     Reps with no 193rd session votes in any PDF are treated as 2025 entrants
     and are only scored on 194th session actions.
     Grading: A≥80, B 60-79, C 40-59, D 20-39, F<20, null=not present

  5. Return DataFrame with fips + rep columns for build.py to merge.
     Also writes data/rollcall_inventory.json as a side effect.

KNOWN DATA GAPS (expected, not errors):
  - 2 towns in 1st Franklin district: no TIGER match → null grade
  - 2 towns in 5th Essex district: no TIGER match → null grade
  - 2 vacant seats in CSV (158/160): those towns get null grade
  - 193rd session reps who lost seats: unmatched from 193rd PDFs → logged
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from lxml import html # type: ignore
from thefuzz import fuzz  # type: ignore

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent.parent
_DATA_DIR = _REPO_ROOT / "data"
_TOWNS_GEOJSON = _DATA_DIR / "ma-towns.geojson"
_TIGER_SLDL = _DATA_DIR / "tl_2024_25_sldl.shp"
_TOWN_DISTRICT_MAP = _DATA_DIR / "town_district_map.json"
_LEGISLATORS_CSV = _DATA_DIR / "ma_legislators.csv"
_BILL_LIST = _DATA_DIR / "legislator_bill_list.json"
_ROLLCALL_INVENTORY = _DATA_DIR / "rollcall_inventory.json"

_FUZZY_THRESHOLD = 85
_COSPONSOR_HEADER = {"X-Requested-With": "XMLHttpRequest"}

# ── TIGER district name normalization ─────────────────────────────────────────

TIGER_ALIASES = {
    "Barnstable-Dukes-Nantucket": "Barnstable, Dukes and Nantucket",
}

# TIGER districts that don't match any Open States district — expected gaps.
# Towns in these districts receive null grades.
_UNMATCHED_TIGER_DISTRICTS = {"1st Franklin", "5th Essex"}

# ── First-initial disambiguation ──────────────────────────────────────────────
# When multiple reps share a surname the PDF appends a first initial (Moran)
# or a comma+initial (Rogers). The PDF parser uppercases these verbatim, so
# keys must match the exact uppercased form produced by leg_house_votes.py.
#
# Format: pdf_name_upper → (family_name, given_name_initial)
#
# Moran: Frank (17th Essex), Mike (18th Suffolk), John (9th Suffolk) — 193rd/194th
# Rogers: Dave (24th Middlesex), John (12th Norfolk) — 193rd/194th
DISAMBIGUATE: dict[str, tuple[str, str]] = {
    "MORAN F.": ("Moran", "F"),
    "MORAN M.": ("Moran", "M"),
    "MORAN J.": ("Moran", "J"),
    "ROGERS, D.": ("Rogers", "D"),
    "ROGERS, J.": ("Rogers", "J"),
}

# Families covered by DISAMBIGUATE — never fall through to ambiguous fuzzy match.
_DISAMBIGUATED_FAMILIES: frozenset[str] = frozenset(
    fam.upper() for fam, _ in DISAMBIGUATE.values()
)


# ── Main entry point ──────────────────────────────────────────────────────────

def get_legislator_data() -> pd.DataFrame:
    """
    Return a DataFrame with rep scorecard data for each MA municipality.

    Columns:
        fips                (str)        10-digit town GEOID
        rep_name            (str|None)   legislator full name
        rep_pct_score       (float|None) 0–100 pct of pro-housing points earned
        rep_bills_scored    (int|None)   number of bills with a scoreable vote
        rep_bills_available (int|None)   number of bills eligible for this rep
        rep_sessions_scored (list|None)  session strings rep was scored in

    Side effect: writes data/rollcall_inventory.json
    """
    # ── Step 1: Build town → district map ─────────────────────────────────────
    town_district_map = _ensure_town_district_map()

    # ── Step 2: Load legislators ───────────────────────────────────────────────
    legislators = _load_legislators()
    logger.info(f"Legislators: loaded {len(legislators)} House members")

    # ── Step 3: Load bill list ─────────────────────────────────────────────────
    bill_list = _load_bill_list()
    logger.info(f"Bill list: {len(bill_list)} entries")

    # ── Step 4: Fetch all vote data ────────────────────────────────────────────
    rollcall_data, parsed_pdfs = _fetch_rollcall_data(bill_list)
    cosponsor_data = _fetch_cosponsor_data(bill_list)

    # ── Step 4b: Write roll call inventory ────────────────────────────────────
    _write_rollcall_inventory(parsed_pdfs)

    # ── Step 4c: Build set of names appearing in any 193rd roll call ──────────
    # Used as a fallback to detect 2025 entrants (no term-start date in CSV).
    all_193_voters: frozenset[str] = frozenset(
        name
        for (session, _year), rc_data_dict in parsed_pdfs.items()
        if session == "193"
        for rc_data in rc_data_dict.values()
        for name in rc_data.get("votes", {}).keys()
    )
    logger.info(
        f"Legislators: {len(all_193_voters)} unique names found in 193rd session PDFs"
    )

    # ── Step 5: Score each legislator ─────────────────────────────────────────
    scores: dict[str, dict] = {}  # district_name → score dict
    for district, rep_row in legislators.items():
        family_name = str(rep_row.get("family_name", "")).strip()
        given_name = str(rep_row.get("given_name", "")).strip()
        served_in_193 = _rep_served_in_193(family_name, given_name, all_193_voters)
        score = _score_rep(rep_row, bill_list, rollcall_data, cosponsor_data, served_in_193)
        scores[district] = score

    # ── Step 6: Map towns to scores via town_district_map ─────────────────────
    records: list[dict] = []
    for fips, district in town_district_map.items():
        if district is None or district not in scores:
            records.append({
                "fips": fips,
                "rep_name": None,
                "rep_pct_score": None,
                "rep_bills_scored": None,
                "rep_bills_available": None,
                "rep_sessions_scored": None,
            })
        else:
            score = scores[district]
            records.append({
                "fips": fips,
                "rep_name": score["rep_name"],
                "rep_pct_score": score["rep_pct_score"],
                "rep_bills_scored": score["rep_bills_scored"],
                "rep_bills_available": score["rep_bills_available"],
                "rep_sessions_scored": score["rep_sessions_scored"],
            })

    df = pd.DataFrame(records)
    scored = df["rep_pct_score"].notna().sum()
    logger.info(
        f"Legislators: scored {scored}/{len(df)} towns "
        f"({len(df) - scored} null — vacancies or unmatched districts)"
    )
    return df


# ── Step 1: Town → district spatial join ─────────────────────────────────────

def _ensure_town_district_map() -> dict[str, Optional[str]]:
    """
    Load or build the town GEOID → House district name map.

    If data/town_district_map.json already exists, load and return it.
    Otherwise, run the spatial join (slow: ~30s) and write the file.

    # Rebuild after redistricting (~2031): delete this file to trigger rebuild
    """
    if _TOWN_DISTRICT_MAP.exists():
        logger.info("Town-district map: loading from cache")
        with open(_TOWN_DISTRICT_MAP, encoding="utf-8") as f:
            return json.load(f)

    logger.info("Town-district map: building via spatial join (one-time, slow)")
    result = _build_town_district_map()

    _TOWN_DISTRICT_MAP.write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    logger.info(f"Town-district map: written to {_TOWN_DISTRICT_MAP}")
    return result


def _build_town_district_map() -> dict[str, Optional[str]]:
    """
    Spatial join: MA town centroids × TIGER SLDL district polygons.

    Returns {fips_string: district_name_or_None, ...}
    """
    try:
        import geopandas as gpd
        from shapely.geometry import Point
    except ImportError as exc:
        raise ImportError("geopandas and shapely are required for spatial join") from exc

    if not _TOWNS_GEOJSON.exists():
        raise FileNotFoundError(f"MA towns GeoJSON not found: {_TOWNS_GEOJSON}")
    if not _TIGER_SLDL.exists():
        raise FileNotFoundError(
            f"TIGER SLDL shapefile not found: {_TIGER_SLDL}\n"
            "Download tl_2024_25_sldl.zip from https://www.census.gov/cgi-bin/geo/shapefiles/ "
            "(State Legislative Districts → MA) and place in data/."
        )

    # Load town polygons
    towns_gdf = gpd.read_file(str(_TOWNS_GEOJSON))
    if towns_gdf.crs is None:
        towns_gdf = towns_gdf.set_crs("EPSG:4326")
    else:
        towns_gdf = towns_gdf.to_crs("EPSG:4326")

    # Compute centroids (in same CRS)
    centroids = towns_gdf.copy()
    centroids["geometry"] = towns_gdf.geometry.centroid
    centroids = centroids[["GEOID", "geometry"]].copy()

    # Load TIGER SLDL districts
    tiger_gdf = gpd.read_file(str(_TIGER_SLDL))
    tiger_gdf = tiger_gdf.to_crs("EPSG:4326")

    # Filter out ZZZ placeholder
    tiger_gdf = tiger_gdf[tiger_gdf["NAMELSAD"] != "ZZZ"].copy()

    # Normalize district names
    tiger_gdf["district_name"] = tiger_gdf["NAMELSAD"].apply(_normalize_tiger_district)

    # Spatial join: centroid point within district polygon
    centroids_gdf = gpd.GeoDataFrame(centroids, geometry="geometry", crs="EPSG:4326")
    joined = gpd.sjoin(
        centroids_gdf,
        tiger_gdf[["district_name", "geometry"]],
        how="left",
        predicate="within",
    )

    # Build result dict
    result: dict[str, Optional[str]] = {}
    unmatched_fips: list[str] = []

    for _, row in joined.iterrows():
        fips = str(row["GEOID"])
        district = row.get("district_name")

        if pd.isna(district) or district is None:
            result[fips] = None
            unmatched_fips.append(fips)
        else:
            district = str(district)
            if district in _UNMATCHED_TIGER_DISTRICTS:
                logger.warning(
                    f"Town FIPS {fips} maps to '{district}', which has no Open States "
                    f"counterpart — this is expected, town will get null grade"
                )
                result[fips] = None
            else:
                result[fips] = district

    if unmatched_fips:
        logger.warning(
            f"Spatial join: {len(unmatched_fips)} towns had no centroid-in-polygon match "
            f"(boundary cases or data gaps): {unmatched_fips[:10]}"
        )

    matched = sum(1 for v in result.values() if v is not None)
    logger.info(f"Spatial join: {matched}/{len(result)} towns matched to a district")
    return result


def _normalize_tiger_district(namelsad: str) -> str:
    """Normalize TIGER NAMELSAD to Open States district name format."""
    name = namelsad.replace(" District", "")
    return TIGER_ALIASES.get(name, name)


# ── Step 2: Load legislators ──────────────────────────────────────────────────

def _load_legislators() -> dict[str, dict]:
    """
    Load ma_legislators.csv and return {district_name: row_dict} for House members.

    The CSV has 158 lower-chamber members (2 seats vacant at download time).
    Towns in vacant-seat districts will get null grades — this is expected and correct.
    """
    if not _LEGISLATORS_CSV.exists():
        raise FileNotFoundError(
            f"Legislators CSV not found: {_LEGISLATORS_CSV}. "
            "Download from https://data.openstates.org/people/current/ma.csv"
        )

    df = pd.read_csv(_LEGISLATORS_CSV, dtype=str, keep_default_na=False)
    house = df[df["current_chamber"].str.strip().str.lower() == "lower"]
    logger.info(f"Legislators: {len(house)} House members in CSV")

    result: dict[str, dict] = {}
    for _, row in house.iterrows():
        district = str(row.get("current_district", "")).strip()
        if district:
            result[district] = row.to_dict()
    return result


# ── Step 3: Fetch vote data ───────────────────────────────────────────────────

def _load_bill_list() -> list[dict]:
    with open(_BILL_LIST, encoding="utf-8") as f:
        data = json.load(f)
        return data["bills"]


def _fetch_rollcall_data(
    bill_list: list[dict],
) -> tuple[dict[tuple[str, int, int], dict[str, str]], dict[tuple[str, int], dict[int, dict]]]:
    """
    Fetch and parse roll call PDFs for all rollcall entries in the bill list.

    Returns:
        (rollcall_data, parsed_pdfs) where:
          rollcall_data: {(session, year, supplement_number): {UPPERCASE_NAME: vote_char}}
          parsed_pdfs:   {(session, year): {rc_num: {"bill":..., "motion":..., ..., "votes":{...}}}}
    """
    from pipeline.ingest.rollcall_fetcher import get_rollcall_pdf
    from pipeline.ingest.leg_house_votes import parse_rollcall_pdf

    # Group by (session, year) to avoid re-downloading the same PDF
    session_year_pairs: dict[tuple[str, int], None] = {}
    for bill in bill_list:
        if bill.get("type") == "rollcall":
            key = (str(bill["session"]), int(bill["year"]))
            session_year_pairs[key] = None

    # Parse each PDF once, cache results in memory
    parsed_pdfs: dict[tuple[str, int], dict[int, dict]] = {}
    for session, year in session_year_pairs:
        pdf_path = get_rollcall_pdf(session, year)
        if pdf_path is None:
            logger.warning(f"  Could not get PDF for session {session}/{year}")
            parsed_pdfs[(session, year)] = {}
            continue
        try:
            parsed_pdfs[(session, year)] = parse_rollcall_pdf(pdf_path)
        except Exception as exc:
            logger.error(f"  Failed to parse PDF for session {session}/{year}: {exc}")
            parsed_pdfs[(session, year)] = {}

    # Build flat lookup: (session, year, supplement_number) → vote dict
    result: dict[tuple[str, int, int], dict[str, str]] = {}
    for bill in bill_list:
        if bill.get("type") != "rollcall":
            continue
        session = str(bill["session"])
        year = int(bill["year"])
        rc_num = int(bill["supplement_number"])
        pdf_data = parsed_pdfs.get((session, year), {})
        rc_data = pdf_data.get(rc_num, {})
        votes_for_rc = rc_data.get("votes", {}) if rc_data else {}
        if not votes_for_rc:
            logger.warning(
                f"  Roll call RC#{rc_num} not found in session {session}/{year} PDF "
                f"({len(pdf_data)} roll calls available in that PDF)"
            )
        result[(session, year, rc_num)] = votes_for_rc

    return result, parsed_pdfs


def _fetch_cosponsor_data(bill_list: list[dict]) -> dict[tuple[str, str], set[str]]:
    """
    Fetch cosponsor lists for all cosponsor entries in the bill list.

    Uses the MA Legislature CoSponsor AJAX endpoint:
    GET https://malegislature.gov/Bills/{session}/{bill}/CoSponsor
    Header: X-Requested-With: XMLHttpRequest

    Returns:
        {(session, bill): frozenset_of_full_names}
    """
    result: dict[tuple[str, str], set[str]] = {}
    for bill in bill_list:
        if bill.get("type") != "cosponsor":
            continue
        session = str(bill["session"])
        bill_id = str(bill["bill"])
        key = (session, bill_id)

        url = f"https://malegislature.gov/Bills/{session}/{bill_id}/CoSponsor"
        try:
            resp = requests.get(
                url,
                headers=_COSPONSOR_HEADER,
                verify=False,
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning(f"  CoSponsor fetch failed for {bill_id} ({session}): {exc}")
            result[key] = set()
            continue

        names = _parse_cosponsor_response(resp.content)
        result[key] = names
        logger.info(f"  CoSponsor {bill_id} ({session}): {len(names)} cosponsors")

    return result


def _parse_cosponsor_response(content: bytes) -> set[str]:
    """
    Parse the CoSponsor AJAX HTML response.

    Expects: <table><tbody><tr><td>Full Name</td>...</tr>...</tbody></table>
    Returns: set of full name strings.
    """
    try:
        tree = html.fromstring(content)
        rows = tree.xpath("//tbody/tr")
        names: set[str] = set()
        for row in rows:
            tds = row.xpath("td")
            if tds:
                name = tds[0].text_content().strip()
                if name:
                    names.add(name)
        return names
    except Exception as exc:
        logger.warning(f"  Could not parse cosponsor response: {exc}")
        return set()


def _write_rollcall_inventory(
    parsed_pdfs: dict[tuple[str, int], dict[int, dict]]
) -> None:
    """
    Write data/rollcall_inventory.json — all parsed roll calls sorted by
    session, year, rc_number. Metadata only (no individual votes).

    This file is the editorial research tool: search it for "MBTA" or "40B"
    or "housing" to surface candidate votes without manual PDF review.
    """
    inventory: list[dict] = []
    for (session, year), rc_data_dict in parsed_pdfs.items():
        for rc_num, rc_data in rc_data_dict.items():
            inventory.append({
                "session": session,
                "year": year,
                "rc_number": rc_num,
                "bill": rc_data.get("bill"),
                "motion": rc_data.get("motion"),
                "date": rc_data.get("date"),
                "yeas": rc_data.get("yeas", 0),
                "nays": rc_data.get("nays", 0),
                "nvs": rc_data.get("nvs", 0),
            })

    inventory.sort(key=lambda r: (r["session"], r["year"], r["rc_number"]))

    _ROLLCALL_INVENTORY.write_text(
        json.dumps(inventory, indent=2), encoding="utf-8"
    )
    logger.info(f"  Roll call inventory: {len(inventory)} entries written to {_ROLLCALL_INVENTORY}")


# ── Session boundary detection ────────────────────────────────────────────────

def _rep_served_in_193(
    family_name: str,
    given_name: str,
    all_193_voters: frozenset[str],
) -> bool:
    """
    Return True if this rep's name appears in any 193rd session roll call.

    Uses the same name-matching logic as _find_rep_vote: DISAMBIGUATE map first,
    then exact match, then fuzzy fallback.

    A rep with no match in 193rd PDFs is treated as a 2025 entrant and will
    only be scored on 194th session actions.
    """
    upper_family = family_name.upper()
    upper_given = given_name[0].upper() if given_name else ""

    # Check DISAMBIGUATE first (for Morans, Rogers, etc.)
    for pdf_name, (dis_family, dis_initial) in DISAMBIGUATE.items():
        if dis_family.upper() == upper_family and dis_initial.upper() == upper_given:
            return pdf_name in all_193_voters

    # If this family requires disambiguation but found no DISAMBIGUATE match
    if upper_family in _DISAMBIGUATED_FAMILIES:
        return False

    # Exact match
    if upper_family in all_193_voters:
        return True

    # Period-stripped variant
    if upper_family.rstrip(".") in all_193_voters:
        return True

    # Fuzzy fallback
    for voter in all_193_voters:
        if fuzz.token_sort_ratio(upper_family, voter) >= _FUZZY_THRESHOLD:
            return True

    return False


# ── Step 4: Score a single legislator ────────────────────────────────────────

def _score_rep(
    rep_row: dict,
    bill_list: list[dict],
    rollcall_data: dict[tuple[str, int, int], dict[str, str]],
    cosponsor_data: dict[tuple[str, str], set[str]],
    served_in_193: bool,
) -> dict:
    """
    Compute a rep's housing score across eligible bills in the bill list.

    Session filtering: bills from session "193" are skipped for reps who did
    not appear in any 193rd roll call (2025 entrants). This prevents newly
    elected reps from being penalized for votes cast by their predecessors.

    Returns a dict with keys: rep_name, rep_pct_score, rep_bills_scored,
    rep_bills_available, rep_sessions_scored. All numeric fields are None if
    rep was not present for any scored vote.
    """
    rep_name = str(rep_row.get("name", "")).strip()
    family_name = str(rep_row.get("family_name", "")).strip()
    given_name = str(rep_row.get("given_name", "")).strip()

    null_result = {
        "rep_name": rep_name,
        "rep_pct_score": None,
        "rep_bills_scored": None,
        "rep_bills_available": None,
        "rep_sessions_scored": None,
    }

    earned = 0.0
    possible = 0.0
    scored_count = 0
    eligible_count = 0
    sessions_scored: set[str] = set()

    for bill in bill_list:
        bill_type = bill.get("type")
        weight = float(bill.get("weight", 1))
        session = str(bill.get("session", ""))

        # Session filtering: skip 193rd bills for 2025 entrants
        if session == "193" and not served_in_193:
            continue

        eligible_count += 1

        if bill_type == "rollcall":
            year = int(bill["year"])
            rc_num = int(bill["supplement_number"])
            pro_housing_vote = str(bill.get("pro_housing_vote", "yea")).lower()

            votes_for_rc = rollcall_data.get((session, year, rc_num), {})
            if not votes_for_rc:
                # PDF not available — skip this bill for this rep
                continue

            vote_char = _find_rep_vote(family_name, given_name, votes_for_rc)
            if vote_char is None:
                # Rep not found in this roll call (absent, former rep, etc.)
                continue

            # Rep is present — this bill is scoreable
            possible += weight
            scored_count += 1
            sessions_scored.add(session)

            is_pro = _is_pro_housing_vote(vote_char, pro_housing_vote)
            if is_pro:
                earned += weight

        elif bill_type == "cosponsor":
            bill_id = str(bill["bill"])
            cosponsor_set = cosponsor_data.get((session, bill_id), set())

            # Cosponsor check: rep's full name must appear in cosponsor set
            is_cosponsor = rep_name in cosponsor_set
            possible += weight
            scored_count += 1
            sessions_scored.add(session)
            if is_cosponsor:
                earned += weight

    if possible == 0:
        return null_result

    pct_score = round(earned / possible * 100, 1)
    return {
        "rep_name": rep_name,
        "rep_pct_score": pct_score,
        "rep_bills_scored": scored_count,
        "rep_bills_available": eligible_count,
        "rep_sessions_scored": sorted(sessions_scored),
    }


def _find_rep_vote(
    family_name: str,
    given_name: str,
    votes_for_rc: dict[str, str],
) -> Optional[str]:
    """
    Find a rep's vote character in a roll call vote dict.

    Roll call PDFs use uppercase last names (possibly with first initials for
    disambiguation). Matching strategy:
      1. Check DISAMBIGUATE map for multi-Moran situations
      2. Exact match on uppercased family_name
      3. Fuzzy fallback (token_sort_ratio >= 85)
      4. If still ambiguous (>1 match), log WARNING and return None

    Returns: "Y", "N", "X", "P", or None (not found).
    """
    upper_family = family_name.upper()
    upper_given_initial = given_name[0].upper() if given_name else ""

    # Step 1: Check for disambiguation — only relevant for Morans
    # (any pdf_name that maps to this family_name + given_name initial)
    for pdf_name, (dis_family, dis_initial) in DISAMBIGUATE.items():
        if (dis_family.upper() == upper_family and
                dis_initial.upper() == upper_given_initial):
            if pdf_name in votes_for_rc:
                return votes_for_rc[pdf_name]

    # If this family name requires disambiguation but Step 1 found no match,
    # don't fall through to exact/fuzzy (which would be ambiguous — skip instead).
    if upper_family in _DISAMBIGUATED_FAMILIES:
        logger.warning(
            f"Disambiguation: no PDF key found for {family_name} {given_name} "
            f"(initial '{upper_given_initial}') — skipping this vote"
        )
        return None

    # Step 2: Exact match on uppercased family_name
    if upper_family in votes_for_rc:
        return votes_for_rc[upper_family]

    # Check with period-stripped variants
    upper_family_clean = upper_family.rstrip(".")
    if upper_family_clean in votes_for_rc:
        return votes_for_rc[upper_family_clean]

    # Step 3: Fuzzy fallback
    best_score = 0
    best_key = None
    candidates: list[str] = []
    for pdf_name in votes_for_rc:
        score = fuzz.token_sort_ratio(upper_family, pdf_name)
        if score > best_score:
            best_score = score
            best_key = pdf_name
        if score >= _FUZZY_THRESHOLD:
            candidates.append(pdf_name)

    if len(candidates) > 1:
        logger.warning(
            f"Ambiguous fuzzy match for '{family_name}': {candidates} — skipping"
        )
        return None

    if best_key and best_score >= _FUZZY_THRESHOLD:
        return votes_for_rc[best_key]

    return None


def _is_pro_housing_vote(vote_char: str, pro_housing_vote: str) -> bool:
    """
    Return True if the rep's vote character counts as a pro-housing vote.

    For pro_housing_vote == "yea": Y or P (P is sometimes a misread Y) → pro
    For pro_housing_vote == "nay": N → pro
    """
    if pro_housing_vote == "yea":
        return vote_char in ("Y", "P")
    elif pro_housing_vote == "nay":
        return vote_char == "N"
    return False
