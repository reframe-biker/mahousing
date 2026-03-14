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
from pipeline.ingest.zillow import fetch_zillow_data
from pipeline.ingest.zoning import get_zoning_data
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
        zoning_cols = ["fips", "pct_multifamily_by_right"]
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
        matched = acs_df["pct_multifamily_by_right"].notna().sum()
        logger.info(f"  Zoning: {matched}/{len(acs_df)} municipalities matched")
    else:
        acs_df["pct_multifamily_by_right"] = None
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

    # ── Step 5: Summary ────────────────────────────────────────────────────────

    logger.info("=" * 60)
    logger.info("PIPELINE SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Total municipalities:   {len(town_records)}")
    logger.info(f"  Errors (skipped):       {errors}")
    logger.info("")

    _print_dimension_summary(town_records)

    logger.info("")
    logger.info(f"  Output: {STATEWIDE_PATH}")
    logger.info(f"  Output: {TOWNS_DIR}/<fips>.json  ({len(town_records)} files)")
    logger.info("=" * 60)


def _build_record(row: pd.Series, today: str) -> dict:
    """Build a TownRecord dict from a merged DataFrame row."""
    pct_mf = _to_float(row.get("pct_multifamily_by_right"))
    rent_burden = _to_float(row.get("rent_burden_pct"))
    permits_per_1000 = _to_float(row.get("permits_per_1000_residents"))
    home_value = _to_float(row.get("final_home_value"))

    metrics = {
        "pct_multifamily_by_right": pct_mf,
        "median_home_value": home_value,
        "rent_burden_pct": rent_burden,
        "permits_per_1000_residents": permits_per_1000,
    }

    grades = score_town(metrics)

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
        "mbta_status": None,  # Phase 2
        "updated_at": today,
    }


def _print_dimension_summary(records: list[dict]) -> None:
    """Print per-dimension grade distribution and null counts."""
    dimensions = ["zoning", "mbta", "production", "affordability", "votes", "rep", "composite"]
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


if __name__ == "__main__":
    main()
