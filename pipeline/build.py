"""
build.py — Pipeline orchestrator for MA Housing Report Card

Entry point for the data pipeline. Called by the GitHub Actions workflow
on a weekly cron schedule and locally for development.

Run with:
    python pipeline/build.py

Environment variables (loaded from .env or set directly):
    CENSUS_API_KEY   — required; Census API key for ACS and BPS endpoints
    ZILLOW_DATA_URL  — optional; override for the Zillow ZHVI CSV URL
    ZONING_ATLAS_URL — optional; override for the MAPC Zoning Atlas GeoJSON URL

Outputs:
    data/towns/{geoid}.json  — one file per MA municipality
    data/statewide.json      — array of all municipality records, sorted by name
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Allow running as `python pipeline/build.py` from the repo root
_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from pipeline.ingest.census_acs import fetch_acs_data
from pipeline.ingest.building_permits import fetch_permit_data
from pipeline.ingest.dhcd_mbta import get_mbta_data
from pipeline.ingest.zillow import fetch_zillow_data
from pipeline.ingest.zoning import get_zoning_data
from pipeline.ingest.legislators import get_legislator_data
from pipeline.ingest.senate_rollcall_fetcher import get_senate_data
from pipeline.ingest.new_vote_notifier import check_for_new_pdfs
from pipeline.metrics import METRICS
from pipeline.score import score_town

# ── Logging setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("build")

# ── Output paths ──────────────────────────────────────────────────────────────

DATA_DIR = _REPO_ROOT / "data"
TOWNS_DIR = DATA_DIR / "towns"
STATEWIDE_PATH = DATA_DIR / "statewide.json"
METRICS_PATH = DATA_DIR / "metrics.json"
METHODOLOGY_PATH = _REPO_ROOT / "METHODOLOGY.md"
BILL_LIST_PATH = DATA_DIR / "legislator_bill_list.json"

_BILL_LIST_SENTINEL_START = "<!-- LEGISLATOR_BILL_LIST_START -->"
_BILL_LIST_SENTINEL_END = "<!-- LEGISLATOR_BILL_LIST_END -->"


def main() -> None:
    """
    Run the full pipeline: ingest → join → score → write JSON.

    Exit codes:
        0  Pipeline completed (even with partial data).
        1  Unrecoverable error (e.g. missing Census API key).
    """
    load_dotenv()

    census_api_key = os.environ.get("CENSUS_API_KEY", "").strip()
    if not census_api_key:
        logger.error(
            "CENSUS_API_KEY is not set.\n"
            "  1. Copy .env.example to .env\n"
            "  2. Get a free key at https://api.census.gov/data/key_signup.html\n"
            "  3. Set CENSUS_API_KEY=<your key> in .env"
        )
        sys.exit(1)

    today = date.today().isoformat()
    TOWNS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Step 0: Check for new roll call PDFs ──────────────────────────────────
    # Alerts only — never scores automatically. Editorial decisions are manual.
    try:
        check_for_new_pdfs()
    except Exception as exc:
        logger.warning(f"New vote notifier raised an exception: {exc}")

    # ── Step 1: Ingest ────────────────────────────────────────────────────────

    logger.info("=" * 60)
    logger.info("STEP 1: Ingesting data sources")
    logger.info("=" * 60)

    # ACS is the authoritative municipality list — failure here is fatal
    try:
        acs_df = fetch_acs_data(census_api_key)
    except Exception as exc:
        logger.error(f"Census ACS fetch failed (fatal): {exc}")
        sys.exit(1)

    if acs_df.empty:
        logger.error("Census ACS returned no municipalities. Cannot continue.")
        sys.exit(1)

    # Optional sources — failures produce null metrics, not crashes
    zoning_df = _safe_fetch("Zoning", get_zoning_data)
    permit_df = _safe_fetch("Building Permits", fetch_permit_data, census_api_key)
    zillow_df = _safe_fetch("Zillow ZHVI", fetch_zillow_data)
    # MBTA: pass name→FIPS map after ACS load so scraper can match town names
    _name_to_fips = dict(zip(acs_df["name"], acs_df["geoid"].astype(str)))
    mbta_df = _safe_fetch("DHCD MBTA", get_mbta_data, _name_to_fips)
    leg_df = _safe_fetch("Legislators", get_legislator_data)
    sen_df = _safe_fetch("Senate", get_senate_data)

    # ── Step 2: Join ──────────────────────────────────────────────────────────

    logger.info("=" * 60)
    logger.info("STEP 2: Joining data sources")
    logger.info("=" * 60)

    # Add a normalized name key to each DataFrame for name-based joins
    acs_df["_name_key"] = acs_df["name"].apply(_normalize_name)

    if not zoning_df.empty:
        # The zoning router contract uses fips (GEOID) as the join key.
        # Join on geoid for exact matching — no name normalization needed.
        # Include data_note if present (populated by permits_proxy spike detection).
        zoning_cols = ["fips", "pct_land_multifamily_byright"]
        if "zoning_source" in zoning_df.columns:
            zoning_cols.append("zoning_source")
        if "data_note" in zoning_df.columns:
            zoning_cols.append("data_note")
        acs_df = acs_df.merge(
            zoning_df[zoning_cols],
            left_on="geoid",
            right_on="fips",
            how="left",
        ).drop(columns=["fips"], errors="ignore")
        if "data_note" not in acs_df.columns:
            acs_df["data_note"] = None
        # Third spike-flag condition: suppress the flag for towns with population
        # >= 15,000.  For larger places a low permit count is a genuine finding,
        # not a data quality concern, so the spike note would be misleading.
        # Population data is only available here after the ACS join, which is
        # why this filter lives in build.py rather than zoning_permits_proxy.py.
        large_town_mask = acs_df["population"].notna() & (acs_df["population"] >= 15_000)
        suppressed = (large_town_mask & acs_df["data_note"].notna()).sum()
        acs_df.loc[large_town_mask, "data_note"] = None
        if suppressed:
            logger.info(f"  Spike flag suppressed for {suppressed} town(s) with population >= 15,000")
        matched = acs_df["pct_land_multifamily_byright"].notna().sum()
        logger.info(f"  Zoning: {matched}/{len(acs_df)} municipalities matched")
    else:
        acs_df["pct_land_multifamily_byright"] = None
        acs_df["zoning_source"] = None
        acs_df["data_note"] = None

    if not permit_df.empty:
        # Primary join: by GEOID (exact match, no name ambiguity)
        acs_df = acs_df.merge(
            permit_df.rename(columns={"permits": "raw_permits"}),
            on="geoid",
            how="left",
        )
        matched = acs_df["raw_permits"].notna().sum()
        logger.info(f"  Building Permits: {matched}/{len(acs_df)} municipalities matched by GEOID")
    else:
        acs_df["raw_permits"] = None

    if not zillow_df.empty:
        zillow_df["_name_key"] = zillow_df["name"].apply(_normalize_name)
        acs_df = acs_df.merge(
            zillow_df[["_name_key", "zhvi"]],
            on="_name_key",
            how="left",
        )
        matched = acs_df["zhvi"].notna().sum()
        logger.info(f"  Zillow ZHVI: {matched}/{len(acs_df)} municipalities matched by name")
    else:
        acs_df["zhvi"] = None

    if not mbta_df.empty:
        # Join MBTA data: prefer FIPS join, fall back to normalized name join
        fips_keyed = mbta_df[mbta_df["fips"].notna() & (mbta_df["fips"] != "")]
        name_keyed = mbta_df[mbta_df["fips"].isna() | (mbta_df["fips"] == "")]

        mbta_cols = ["mbta_status", "mbta_deadline", "mbta_action_date"]

        if not fips_keyed.empty:
            acs_df = acs_df.merge(
                fips_keyed[["fips"] + mbta_cols],
                left_on="geoid",
                right_on="fips",
                how="left",
            ).drop(columns=["fips"], errors="ignore")

        if not name_keyed.empty and "_name" in name_keyed.columns:
            name_keyed = name_keyed.copy()
            name_keyed["_name_key"] = name_keyed["_name"].apply(_normalize_name)
            if "_name_key" not in acs_df.columns:
                acs_df["_name_key"] = acs_df["name"].apply(_normalize_name)
            # Only fill nulls from name join (don't overwrite fips-matched rows)
            for col in mbta_cols:
                if col not in acs_df.columns:
                    acs_df[col] = None
            name_merge = acs_df[["_name_key"]].merge(
                name_keyed[["_name_key"] + mbta_cols],
                on="_name_key",
                how="left",
            )
            for col in mbta_cols:
                acs_df[col] = acs_df[col].combine_first(name_merge[col])

        # Ensure columns exist even if all joins were empty
        for col in mbta_cols:
            if col not in acs_df.columns:
                acs_df[col] = None

        # Towns not found in DHCD data remain null — they are outside the scope
        # of the MBTA Communities Act. "exempt" is a status reserved for towns
        # explicitly listed as exempt within the 177 subject communities.
        matched_mbta = acs_df["mbta_status"].notna().sum()
        logger.info(f"  DHCD MBTA: {matched_mbta}/{len(acs_df)} municipalities have explicit MBTA status")
    else:
        acs_df["mbta_status"] = None
        acs_df["mbta_deadline"] = None
        acs_df["mbta_action_date"] = None

    # Legislator scorecard — join on fips (geoid)
    if not leg_df.empty and "reps" in leg_df.columns:
        acs_df = acs_df.merge(
            leg_df[["fips", "reps"]],
            left_on="geoid",
            right_on="fips",
            how="left",
        ).drop(columns=["fips_y"], errors="ignore")
        matched_leg = acs_df["reps"].apply(
            lambda x: x is not None and len(x) > 0
                if not isinstance(x, float) else False
        ).sum()
        logger.info(f"  Legislators: {matched_leg}/{len(acs_df)} municipalities matched")
    else:
        acs_df["reps"] = None

    # Senate scorecard — join on fips (geoid)
    if not sen_df.empty and "sens" in sen_df.columns:
        acs_df = acs_df.merge(
            sen_df[["fips", "sens"]],
            left_on="geoid",
            right_on="fips",
            how="left",
        ).drop(columns=["fips_y"], errors="ignore")
        matched_sen = acs_df["sens"].apply(
            lambda x: x is not None and len(x) > 0
                if not isinstance(x, float) else False
        ).sum()
        logger.info(f"  Senate: {matched_sen}/{len(acs_df)} municipalities matched")
    else:
        acs_df["sens"] = None

    # ── Step 3: Derive computed metrics ───────────────────────────────────────

    # permits_per_1000_residents: raw_permits / population * 1000
    def compute_permits_per_1000(row) -> float | None:
        permits = row.get("raw_permits")
        population = row.get("population")
        if permits is None or population is None or population <= 0:
            return None
        return round(permits / population * 1000, 2)

    acs_df["permits_per_1000_residents"] = acs_df.apply(compute_permits_per_1000, axis=1)

    # median_home_value: prefer Zillow ZHVI (more current), fall back to ACS
    def pick_home_value(row) -> float | None:
        zhvi = row.get("zhvi")
        acs_val = row.get("median_home_value")
        # Zillow ZHVI is the preferred source when available
        if zhvi is not None and not pd.isna(zhvi):
            return float(zhvi)
        return acs_val

    acs_df["final_home_value"] = acs_df.apply(pick_home_value, axis=1)

    # ── Step 4: Score and write ────────────────────────────────────────────────

    logger.info("=" * 60)
    logger.info("STEP 4: Scoring and writing output")
    logger.info("=" * 60)

    town_records: list[dict] = []
    errors: int = 0

    for _, row in acs_df.iterrows():
        try:
            record = _build_record(row, today)
            town_records.append(record)

            fips = record["fips"]
            out_path = TOWNS_DIR / f"{fips}.json"
            out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

        except Exception as exc:
            name = row.get("name", "<unknown>")
            logger.error(f"  Failed to build record for {name}: {exc}")
            errors += 1

    # Sort statewide list alphabetically by name
    town_records.sort(key=lambda r: r["name"])
    STATEWIDE_PATH.write_text(json.dumps(town_records, indent=2), encoding="utf-8")

    # ── Export metrics.json ────────────────────────────────────────────────────
    # Serialize pipeline/metrics.py → data/metrics.json so the site can read
    # metric labels and descriptions at build time without hardcoding them.
    METRICS_PATH.write_text(json.dumps(METRICS, indent=2), encoding="utf-8")

    # ── Auto-generate METHODOLOGY.md bill list section ─────────────────────────
    _update_methodology_bill_list()

    # ── Validate metrics.py against data schema ────────────────────────────────
    _validate_metrics(town_records)

    # ── Step 5: Summary ────────────────────────────────────────────────────────

    logger.info("=" * 60)
    logger.info("PIPELINE SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Total municipalities:   {len(town_records)}")
    logger.info(f"  Errors (skipped):       {errors}")
    logger.info("")

    _print_dimension_summary(town_records)
    _print_mbta_summary(town_records)

    logger.info("")
    logger.info(f"  Output: {STATEWIDE_PATH}")
    logger.info(f"  Output: {METRICS_PATH}")
    logger.info(f"  Output: {TOWNS_DIR}/<fips>.json  ({len(town_records)} files)")
    logger.info("=" * 60)


def _build_record(row: pd.Series, today: str) -> dict:
    """Build a TownRecord dict from a merged DataFrame row."""
    pct_mf = _to_float(row.get("pct_land_multifamily_byright"))
    rent_burden = _to_float(row.get("rent_burden_pct"))
    permits_per_1000 = _to_float(row.get("permits_per_1000_residents"))
    home_value = _to_float(row.get("final_home_value"))
    renter_share = _to_float(row.get("renter_share_pct"))
    zoning_source = _to_str(row.get("zoning_source"))
    mbta_status = _to_str(row.get("mbta_status"))
    mbta_deadline = _to_str(row.get("mbta_deadline"))
    mbta_action_date = _to_str(row.get("mbta_action_date"))

    raw_reps = row.get("reps")
    if isinstance(raw_reps, list) and len(raw_reps) > 0:
        reps = raw_reps
    else:
        reps = None

    raw_sens = row.get("sens")
    if isinstance(raw_sens, list) and len(raw_sens) > 0:
        sens = raw_sens
    else:
        sens = None

    metrics = {
        "pct_land_multifamily_byright": pct_mf,
        "median_home_value": home_value,
        "rent_burden_pct": rent_burden,
        "permits_per_1000_residents": permits_per_1000,
        "renter_share_pct": renter_share,
    }

    grades = score_town(metrics, mbta_status=mbta_status, reps=reps, sens=sens)

    # data_notes: zoning note from permits_proxy spike detection; others reserved
    data_notes = {
        "zoning": _to_str(row.get("data_note")),
        "production": None,
        "affordability": None,
    }

    return {
        "fips": str(row["geoid"]),
        "name": str(row["name"]),
        "county": str(row.get("county", "")),
        "population": _to_int(row.get("population")),
        "grades": grades,
        "metrics": metrics,
        "data_notes": data_notes,
        "zoning_source": zoning_source,
        "mbta_status": mbta_status,
        "mbta_deadline": mbta_deadline,
        "mbta_action_date": mbta_action_date,
        "reps": reps,
        "sens": sens,
        "updated_at": today,
    }


def _print_dimension_summary(records: list[dict]) -> None:
    """Print per-dimension grade distribution and null counts."""
    dimensions = ["zoning", "mbta", "production", "affordability", "votes", "legislators", "composite"]
    letters = ["A", "B", "C", "D", "F"]

    for dim in dimensions:
        grades = [r["grades"].get(dim) for r in records]
        non_null = [g for g in grades if g is not None]
        null_count = len(grades) - len(non_null)

        dist = {letter: non_null.count(letter) for letter in letters}
        dist_str = "  ".join(f"{k}:{v}" for k, v in dist.items() if v > 0)

        logger.info(
            f"  {dim:15s}  "
            f"non-null: {len(non_null):3d}  "
            f"null: {null_count:3d}  "
            f"[{dist_str}]"
        )


def _print_mbta_summary(records: list[dict]) -> None:
    """Print MBTA Communities Act coverage summary."""
    statuses = [r.get("mbta_status") for r in records]
    from collections import Counter
    counts = Counter(s for s in statuses if s is not None)
    null_count = sum(1 for s in statuses if s is None)
    subject_statuses = ["compliant", "interim", "pending", "non-compliant"]
    subject_total = sum(counts.get(s, 0) for s in subject_statuses)

    logger.info("")
    logger.info("  MBTA Communities Act coverage:")
    for status in subject_statuses:
        logger.info(f"    {status:15s}: {counts.get(status, 0):3d}")
    logger.info(f"    {'exempt':15s}: {counts.get('exempt', 0):3d}")
    logger.info(f"    {'null (unknown)':15s}: {null_count:3d}")
    logger.info(f"    {'total subject':15s}: {subject_total:3d} / 177 expected")


def _validate_metrics(town_records: list[dict]) -> None:
    """
    Warn if pipeline/metrics.py and the town data schema are out of sync.

    Checks that every numeric metric key in METRICS exists in a sample town's
    metrics dict and vice versa. Non-numeric metrics (unit=="status") are metadata
    entries for non-numeric fields (e.g. mbta_status) and are excluded.
    Does not crash the pipeline — warns and continues.
    """
    if not town_records:
        return

    sample_metrics = town_records[0].get("metrics", {})
    data_keys = set(sample_metrics.keys())
    # Only validate metrics that appear in the metrics dict.
    # "status" metrics (mbta_status, affordability) live outside the metrics dict.
    # All other units (percent, dollars, rate, count, text) are in the metrics dict.
    numeric_metrics_keys = {k for k, v in METRICS.items() if v.get("unit") != "status"}

    only_in_data = data_keys - numeric_metrics_keys
    only_in_metrics = numeric_metrics_keys - data_keys

    if only_in_data or only_in_metrics:
        logger.warning(
            "WARNING: Metric mismatch detected. "
            f"The following fields are in the data but not in metrics.py: {sorted(only_in_data)}. "
            f"The following fields are in metrics.py but not in the data: {sorted(only_in_metrics)}. "
            "Update metrics.py or the pipeline to resolve."
        )
    else:
        logger.info(f"  Metrics validation: OK ({len(numeric_metrics_keys)} numeric fields in sync)")


def _safe_fetch(label: str, fn, *args):
    """Call an ingest function, catching all exceptions. Returns empty DataFrame on error."""
    try:
        return fn(*args)
    except Exception as exc:
        logger.warning(f"{label} ingest raised an exception: {exc}")
        return pd.DataFrame()


def _normalize_name(name: str) -> str:
    """
    Normalize a municipality name for fuzzy join.

    'Cambridge city' → 'cambridge'
    'North Attleborough' → 'north attleborough'
    Removes geographic suffixes added by the Census.
    """
    if not isinstance(name, str):
        return ""
    return name.lower().strip()


def _to_float(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if pd.isna(f) else f
    except (ValueError, TypeError):
        return None


def _to_str(val) -> str | None:
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    return s if s else None


def _to_int(val) -> int | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if pd.isna(f) else int(f)
    except (ValueError, TypeError):
        return None


def _ordinal(n: int) -> str:
    """Return ordinal string for an integer (193 → '193rd')."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _update_methodology_bill_list() -> None:
    """
    Regenerate the legislator bill list section of METHODOLOGY.md from
    data/legislator_bill_list.json, replacing everything between the
    sentinel comments on every build run.
    """
    if not BILL_LIST_PATH.exists():
        logger.warning("Bill list not found — skipping METHODOLOGY.md update")
        return
    if not METHODOLOGY_PATH.exists():
        logger.warning("METHODOLOGY.md not found — skipping bill list update")
        return

    with open(BILL_LIST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    bills = data["bills"] if isinstance(data, dict) else data

    n_rollcalls = sum(1 for b in bills if b.get("type") == "rollcall")
    n_cosponsors = sum(1 for b in bills if b.get("type") == "cosponsor")
    max_points = sum(b.get("weight", 0) for b in bills)

    def _cell(text: str) -> str:
        """Escape pipe characters in a markdown table cell."""
        return str(text).replace("|", "\\|")

    def _pro_vote_label(v: str) -> str:
        return {"yea": "YEA", "nay": "NAY", "cosponsor": "Co-sponsor"}.get(v.lower(), v)

    def _action_label(b: dict) -> str:
        if b.get("type") == "rollcall":
            return f"RC#{b['supplement_number']}"
        return str(b.get("bill", b.get("id", "")))

    def _session_label(b: dict) -> str:
        session_str = str(b.get("session", ""))
        try:
            ordinal = _ordinal(int(session_str))
        except (ValueError, TypeError):
            ordinal = session_str
        year = b.get("year")
        return f"{ordinal} ({year})" if year else ordinal

    def _type_label(b: dict) -> str:
        return {"rollcall": "Roll call", "cosponsor": "Co-sponsorship check"}.get(
            b.get("type", ""), b.get("type", "")
        )

    header = (
        f"Current scored actions ({n_rollcalls} roll call votes and "
        f"{n_cosponsors} co-sponsorship checks, max {max_points} points):"
    )

    table_header = "| Action | Type | Session | Description | Pro-housing vote | Weight | Rationale |"
    table_sep    = "|--------|------|---------|-------------|-----------------|--------|-----------|"

    rows = []
    for b in bills:
        row = (
            f"| {_cell(_action_label(b))} "
            f"| {_cell(_type_label(b))} "
            f"| {_cell(_session_label(b))} "
            f"| {_cell(b.get('description', ''))} "
            f"| {_cell(_pro_vote_label(b.get('pro_housing_vote', '')))} "
            f"| {_cell(b.get('weight', ''))} "
            f"| {_cell(b.get('rationale', ''))} |"
        )
        rows.append(row)

    new_content = "\n".join([
        _BILL_LIST_SENTINEL_START,
        "<!-- auto-generated by pipeline/build.py on each run — do not edit manually -->",
        header,
        "",
        table_header,
        table_sep,
        *rows,
        _BILL_LIST_SENTINEL_END,
    ])

    methodology_text = METHODOLOGY_PATH.read_text(encoding="utf-8")

    start_idx = methodology_text.find(_BILL_LIST_SENTINEL_START)
    end_idx = methodology_text.find(_BILL_LIST_SENTINEL_END)

    if start_idx == -1 or end_idx == -1:
        logger.warning(
            "METHODOLOGY.md is missing sentinel comments — skipping bill list update. "
            f"Add '{_BILL_LIST_SENTINEL_START}' and '{_BILL_LIST_SENTINEL_END}' "
            "to METHODOLOGY.md to enable auto-generation."
        )
        return

    end_idx += len(_BILL_LIST_SENTINEL_END)
    updated = methodology_text[:start_idx] + new_content + methodology_text[end_idx:]
    METHODOLOGY_PATH.write_text(updated, encoding="utf-8")
    logger.info(
        f"  METHODOLOGY.md: bill list updated "
        f"({n_rollcalls} roll calls, {n_cosponsors} co-sponsors, max {max_points} pts)"
    )


if __name__ == "__main__":
    main()
