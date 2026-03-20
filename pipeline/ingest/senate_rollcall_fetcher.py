"""
senate_rollcall_fetcher.py — LegiScan-based Senate vote fetcher for MA Housing Report Card

Phase 4d: MA Senate scoring via LegiScan roll call API.

Unlike the House fetcher (which parses combined annual PDFs), the Senate fetcher
calls the LegiScan API using roll_call_id values from data/senate_bill_list.json.

DATA FLOW:
  1. Load data/senate_bill_list.json (2 rollcall entries, keyed by roll_call_id)
  2. Call LegiScan getRollCall for each roll_call_id → {people_id: vote_text}
  3. Call LegiScan getPerson for each people_id → full name
  4. Cache both responses in data/rollcall_cache/senate/
  5. Load ma_legislators.csv filtered to "upper" chamber (Senate)
  6. Match each senator by name to a people_id (exact last-name, then fuzzy)
  7. Score each senator: earned points / max points × 100
  8. Session boundary: senators not in any 193rd roll call are treated as
     2025 entrants and scored only on 194th session actions
  9. Map towns to scores via data/town_senate_district_map.json

API:
  LEGISCAN_API_KEY env var required for live fetches.
  Missing key → falls back to cached responses only.

GRADING RUBRIC (same as House):
  A ≥ 80%, B 60–79%, C 40–59%, D 20–39%, F < 20%, null = not present
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

import pandas as pd
from thefuzz import fuzz  # type: ignore

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent.parent
_DATA_DIR = _REPO_ROOT / "data"
_SENATE_BILL_LIST = _DATA_DIR / "senate_bill_list.json"
_TOWN_SENATE_DISTRICT_MAP = _DATA_DIR / "town_senate_district_map.json"
_LEGISLATORS_CSV = _DATA_DIR / "ma_legislators.csv"
_CACHE_DIR = _DATA_DIR / "rollcall_cache" / "senate"

_LEGISCAN_BASE = "https://api.legiscan.com/?key={key}&op={op}&id={id}"
_FUZZY_THRESHOLD = 85


# ── LegiScan API helpers ──────────────────────────────────────────────────────

def _get_api_key() -> str | None:
    return os.environ.get("LEGISCAN_API_KEY", "").strip() or None


def _legiscan_get(op: str, entity_id: int, cache_path: Path) -> dict | None:
    """Fetch a LegiScan API response, returning cached result if available."""
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    api_key = _get_api_key()
    if not api_key:
        logger.warning(f"LEGISCAN_API_KEY not set — cannot fetch {op}/{entity_id}")
        return None

    url = _LEGISCAN_BASE.format(key=api_key, op=op, id=entity_id)
    try:
        result = subprocess.run(
            ["curl", "-s", url],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
    except Exception as exc:
        logger.warning(f"LegiScan {op}/{entity_id} fetch failed: {exc}")
        return None

    if data.get("status") != "OK":
        logger.warning(
            f"LegiScan {op}/{entity_id} returned status={data.get('status')}"
        )
        return None

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data


def _fetch_rollcall(roll_call_id: int) -> dict | None:
    cache_path = _CACHE_DIR / f"rollcall_{roll_call_id}.json"
    return _legiscan_get("getRollCall", roll_call_id, cache_path)


def _fetch_person(people_id: int) -> dict | None:
    cache_path = _CACHE_DIR / f"person_{people_id}.json"
    return _legiscan_get("getPerson", people_id, cache_path)


def _resolve_name(people_id: int) -> str | None:
    """Return a senator's full name from their LegiScan people_id."""
    data = _fetch_person(people_id)
    if not data:
        return None
    person = data.get("person", {})
    first = person.get("first_name", "").strip()
    last = person.get("last_name", "").strip()
    if not last:
        return None
    return f"{first} {last}".strip() if first else last


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_bill_list() -> list[dict]:
    with open(_SENATE_BILL_LIST, encoding="utf-8") as f:
        data = json.load(f)
    return data["bills"]


def _load_senators() -> dict[str, dict]:
    """
    Load ma_legislators.csv and return {district_name: row_dict} for Senate members.

    current_chamber == "upper" identifies senators.
    """
    if not _LEGISLATORS_CSV.exists():
        raise FileNotFoundError(
            f"Legislators CSV not found: {_LEGISLATORS_CSV}. "
            "Download from https://data.openstates.org/people/current/ma.csv"
        )
    df = pd.read_csv(_LEGISLATORS_CSV, dtype=str, keep_default_na=False)
    senate = df[df["current_chamber"].str.strip().str.lower() == "upper"]
    logger.info(f"Senate: loaded {len(senate)} senators from CSV")

    result: dict[str, dict] = {}
    for _, row in senate.iterrows():
        district = str(row.get("current_district", "")).strip()
        if district:
            result[district] = row.to_dict()
    return result


# ── Vote data fetching ────────────────────────────────────────────────────────

def _fetch_all_vote_data(
    bill_list: list[dict],
) -> tuple[dict[tuple[str, int], dict[int, str]], dict[int, str]]:
    """
    Fetch and cache vote data for all rollcall entries in the senate bill list.

    Returns:
        votes_by_bill: {(session, roll_call_id): {people_id: vote_text}}
        people_id_to_name: {people_id: full_name}
    """
    votes_by_bill: dict[tuple[str, int], dict[int, str]] = {}
    people_id_to_name: dict[int, str] = {}

    for bill in bill_list:
        if bill.get("type") != "rollcall":
            continue
        session = str(bill["session"])
        roll_call_id = int(bill["roll_call_id"])
        key = (session, roll_call_id)

        data = _fetch_rollcall(roll_call_id)
        if not data:
            logger.warning(f"  No data for roll_call_id={roll_call_id} — skipping")
            votes_by_bill[key] = {}
            continue

        rc = data.get("roll_call", {})
        votes_raw = rc.get("votes", [])
        votes: dict[int, str] = {}
        for v in votes_raw:
            pid = int(v["people_id"])
            vote_text = str(v["vote_text"])
            votes[pid] = vote_text
            if pid not in people_id_to_name:
                name = _resolve_name(pid)
                if name:
                    people_id_to_name[pid] = name

        votes_by_bill[key] = votes
        yea_count = sum(1 for v in votes_raw if v["vote_text"] == "Yea")
        nay_count = sum(1 for v in votes_raw if v["vote_text"] == "Nay")
        logger.info(
            f"  Roll call {roll_call_id} (session {session}): "
            f"{len(votes)} votes, {yea_count} Yea, {nay_count} Nay"
        )

    return votes_by_bill, people_id_to_name


# ── Senator → people_id matching ─────────────────────────────────────────────

def _match_senator_to_people_id(
    family_name: str,
    given_name: str,
    people_id_to_name: dict[int, str],
) -> Optional[int]:
    """
    Match a senator from the CSV to a LegiScan people_id.

    Strategy:
      1. Exact last-name match (case-insensitive)
      2. Fuzzy full-name match (token_sort_ratio >= 85)
    """
    upper_family = family_name.upper()
    full_name = f"{given_name} {family_name}".strip()

    # Exact last-name match
    for pid, name in people_id_to_name.items():
        parts = name.split()
        if parts and parts[-1].upper() == upper_family:
            return pid

    # Fuzzy full-name match
    best_score = 0
    best_pid = None
    candidates: list[tuple[int, str]] = []

    for pid, name in people_id_to_name.items():
        score = fuzz.token_sort_ratio(full_name.upper(), name.upper())
        if score > best_score:
            best_score = score
            best_pid = pid
        if score >= _FUZZY_THRESHOLD:
            candidates.append((pid, name))

    if len(candidates) == 1:
        return candidates[0][0]
    if len(candidates) > 1:
        logger.warning(
            f"Ambiguous senator match for '{family_name}': {[n for _, n in candidates]} — skipping"
        )
        return None
    if best_pid and best_score >= _FUZZY_THRESHOLD:
        return best_pid

    return None


# ── Scoring ───────────────────────────────────────────────────────────────────

def _pct_to_grade(pct: float) -> str:
    if pct >= 80: return "A"
    if pct >= 60: return "B"
    if pct >= 40: return "C"
    if pct >= 20: return "D"
    return "F"


def _score_senator(
    sen_row: dict,
    bill_list: list[dict],
    votes_by_bill: dict[tuple[str, int], dict[int, str]],
    people_id_to_name: dict[int, str],
    all_193_pids: frozenset[int],
) -> dict:
    """
    Compute a senator's housing score across eligible bills.

    Session boundary: senators whose people_id does not appear in any 193rd
    session roll call are treated as 2025 entrants and scored only on 194th
    session actions.
    """
    sen_name = str(sen_row.get("name", "")).strip()
    family_name = str(sen_row.get("family_name", "")).strip()
    given_name = str(sen_row.get("given_name", "")).strip()

    null_result = {
        "sen_name": sen_name,
        "sen_pct_score": None,
        "sen_bills_scored": None,
        "sen_bills_available": None,
        "sen_sessions_scored": None,
    }

    people_id = _match_senator_to_people_id(family_name, given_name, people_id_to_name)
    served_in_193 = people_id is not None and people_id in all_193_pids

    earned = 0.0
    possible = 0.0
    scored_count = 0
    eligible_count = 0
    sessions_scored: set[str] = set()

    for bill in bill_list:
        if bill.get("type") != "rollcall":
            continue
        session = str(bill.get("session", ""))
        weight = float(bill.get("weight", 1))
        roll_call_id = int(bill["roll_call_id"])
        pro_housing_vote = str(bill.get("pro_housing_vote", "yea")).lower()
        key = (session, roll_call_id)

        # Session boundary: skip 193rd bills for 2025 entrants
        if session == "193" and not served_in_193:
            continue

        eligible_count += 1
        votes = votes_by_bill.get(key, {})
        if not votes or people_id is None:
            continue

        vote_text = votes.get(people_id)
        if vote_text is None:
            # Senator absent from this roll call
            continue

        possible += weight
        scored_count += 1
        sessions_scored.add(session)

        is_pro = (
            (pro_housing_vote == "yea" and vote_text == "Yea") or
            (pro_housing_vote == "nay" and vote_text == "Nay")
        )
        if is_pro:
            earned += weight

    if possible == 0:
        return null_result

    pct_score = round(earned / possible * 100, 1)
    return {
        "sen_name": sen_name,
        "sen_pct_score": pct_score,
        "sen_bills_scored": scored_count,
        "sen_bills_available": eligible_count,
        "sen_sessions_scored": sorted(sessions_scored),
    }


# ── Main entry point ──────────────────────────────────────────────────────────

def get_senate_data() -> pd.DataFrame:
    """
    Return a DataFrame with senator scorecard data for each MA municipality.

    Columns:
        fips  (str)        10-digit town GEOID
        sens  (list|None)  list of SenRecord dicts, or None if no senators matched

    Requires LEGISCAN_API_KEY env var for live fetches; falls back to cache only.
    """
    if not _SENATE_BILL_LIST.exists():
        logger.warning(
            f"Senate bill list not found: {_SENATE_BILL_LIST} — skipping senate scoring"
        )
        return pd.DataFrame(columns=["fips", "sens"])

    if not _TOWN_SENATE_DISTRICT_MAP.exists():
        logger.warning(
            f"Town senate district map not found: {_TOWN_SENATE_DISTRICT_MAP} — skipping senate scoring"
        )
        return pd.DataFrame(columns=["fips", "sens"])

    # Load town → senate district map
    with open(_TOWN_SENATE_DISTRICT_MAP, encoding="utf-8") as f:
        town_senate_district_map: dict[str, list[str]] = json.load(f)

    senators = _load_senators()
    bill_list = _load_bill_list()
    logger.info(f"Senate bill list: {len(bill_list)} entries")

    # Fetch vote data from LegiScan (cached)
    votes_by_bill, people_id_to_name = _fetch_all_vote_data(bill_list)
    logger.info(f"Senate: resolved {len(people_id_to_name)} senator names from LegiScan")

    # Session boundary: build set of people_ids in any 193rd roll call
    all_193_pids: frozenset[int] = frozenset(
        pid
        for (session, _rc_id), votes in votes_by_bill.items()
        if session == "193"
        for pid in votes.keys()
    )
    logger.info(
        f"Senate: {len(all_193_pids)} senators found in 193rd session roll calls"
    )

    # Score each senator
    scores: dict[str, dict] = {}  # district_name → score dict
    for district, sen_row in senators.items():
        score = _score_senator(
            sen_row, bill_list, votes_by_bill, people_id_to_name, all_193_pids
        )
        scores[district] = score

    # Map towns to senator scores
    records: list[dict] = []
    for fips, districts in town_senate_district_map.items():
        sen_records = []
        for district in districts:
            if district in scores:
                score = scores[district]
                if score["sen_pct_score"] is not None:
                    sen_records.append({
                        "name": score["sen_name"],
                        "district": district,
                        "pct_score": score["sen_pct_score"],
                        "grade": _pct_to_grade(score["sen_pct_score"]),
                        "bills_scored": score["sen_bills_scored"],
                        "bills_available": score["sen_bills_available"],
                        "sessions_scored": score["sen_sessions_scored"],
                    })
        records.append({
            "fips": fips,
            "sens": sen_records if sen_records else None,
        })

    df = pd.DataFrame(records)
    scored = df["sens"].apply(
        lambda x: isinstance(x, list) and len(x) > 0
    ).sum()
    logger.info(
        f"Senate: {scored}/{len(df)} towns have at least one scored senator "
        f"({len(df) - scored} null — vacancies or unmatched districts)"
    )
    return df
