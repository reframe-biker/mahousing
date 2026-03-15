"""
zoning_nza.py — National Zoning Atlas ingest for MA Housing Report Card

Computes pct_land_multifamily_byright per municipality from the NZA district-level
GeoJSON file (MA_Zoning_Atlas_2023.geojson, 2,291 features, 245 unique jurisdictions).

METRIC:
  pct_land_multifamily_byright = area-weighted share of residential zoned land
  where 3-family (family3) or larger multifamily (family4) housing is permitted
  by right or by special permit (partial credit).

  A  > 25%   — substantial by-right multifamily land
  B  10–25%
  C  3–10%
  D  0.5–3%
  F  < 0.5%
  null  town not in NZA and not covered by permit proxy fallback

DISTRICT FILTERING (applied before scoring):
  - overlay == 1         → excluded (would double-count base zone land)
  - extinct == 1         → excluded (defunct district)
  - published != 1       → excluded (NZA quality flag)
  - status != 'done'     → excluded (NZA completeness flag)
  - acres <= 0           → excluded (data error)

DISTRICT SCORING:
  - nonresidential_type set → None (excluded from residential land base entirely)
  - affordable_district == 1 → 0.0 (counts toward total acres, scores zero)
  - family4_treatment == "allowed" → 1.0
  - family3_treatment == "allowed" (f4 not allowed) → 0.5 (3-family only = partial credit)
  - "hearing" → 0.0 (special permits are a restriction mechanism, not credit)
  - otherwise → 0.0

JURISDICTION → FIPS JOIN:
  1. Exact name match against data/statewide.json
  2. Fuzzy fallback via thefuzz (token_sort_ratio >= 90)
  3. Unmatched jurisdictions are logged as warnings

FALLBACK:
  Towns not in the NZA fall back to the permit proxy
  (zoning_permits_proxy.py). These are treated as a second data source and
  merged into the final output so all 351 towns are covered.

OUTPUT CONTRACT (matches zoning.py router):
  fips                        (str)          10-digit county subdivision GEOID
  pct_land_multifamily_byright (float | None) % of residential land by-right MF;
                                             None = insufficient data
  low_sample                  (bool)         True if data quality is thin
  data_note                   (str | None)   Quality flag; None for NZA-sourced towns
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
from thefuzz import fuzz # type: ignore

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent.parent
_NZA_PATH = _REPO_ROOT / "data" / "MA_Zoning_Atlas_2023.geojson"
_STATEWIDE_PATH = _REPO_ROOT / "data" / "statewide.json"
_KNOWN_ERRORS_PATH = _REPO_ROOT / "data" / "zoning_nza_known_errors.json"

# Minimum fuzzy score for name → FIPS matching
_FUZZY_THRESHOLD = 90


def get_zoning_data() -> pd.DataFrame:
    """
    Load the NZA GeoJSON, score each district, aggregate to town level,
    join to FIPS codes, and merge in permit proxy fallback for uncovered towns.

    Returns:
        DataFrame with columns:
            fips                        (str)
            pct_land_multifamily_byright (float | None)
            low_sample                  (bool)
            data_note                   (str | None)
    """
    empty = pd.DataFrame(
        columns=["fips", "pct_land_multifamily_byright", "low_sample", "data_note", "zoning_source"]
    )

    # ── Load NZA GeoJSON ────────────────────────────────────────────────────────
    if not _NZA_PATH.exists():
        logger.error(
            f"NZA GeoJSON not found at {_NZA_PATH}. "
            "Falling back entirely to permit proxy."
        )
        return _permit_proxy_only()

    with open(_NZA_PATH, encoding="utf-8") as f:
        nza = json.load(f)

    features = nza.get("features", [])
    logger.info(f"NZA: loaded {len(features)} district features")

    # ── Build name → FIPS lookup ────────────────────────────────────────────────
    name_to_fips = _build_name_to_fips()
    if not name_to_fips:
        logger.error("Could not build name→FIPS lookup. Falling back to permit proxy.")
        return _permit_proxy_only()

    # ── Score districts ─────────────────────────────────────────────────────────
    records = []
    skipped = 0
    for feat in features:
        props = feat.get("properties", {})

        # Apply quality/completeness filters
        if props.get("overlay") == 1:
            skipped += 1
            continue
        if props.get("extinct") == 1:
            skipped += 1
            continue
        if props.get("published") != 1:
            skipped += 1
            continue
        if props.get("status") != "done":
            skipped += 1
            continue
        acres = props.get("acres") or 0
        if acres <= 0:
            skipped += 1
            continue

        score = _score_district(props)
        records.append({
            "jurisdiction": props.get("jurisdiction", ""),
            "acres": float(acres),
            "mf_score": score,
        })

    logger.info(
        f"NZA: {len(records)} districts kept, {skipped} filtered out "
        f"(overlay/extinct/unpublished/incomplete/zero-acres)"
    )

    if not records:
        logger.warning("NZA: no usable districts after filtering — falling back to permit proxy.")
        return _permit_proxy_only()

    districts_df = pd.DataFrame(records)

    # ── Aggregate to town level ─────────────────────────────────────────────────
    town_scores: dict[str, float | None] = {}
    for jurisdiction, group in districts_df.groupby("jurisdiction"):
        score = _aggregate_town(group)
        town_scores[jurisdiction] = score

    logger.info(
        f"NZA: {len(town_scores)} jurisdictions scored "
        f"({sum(v is not None for v in town_scores.values())} with data)"
    )

    # ── Map jurisdiction names → FIPS ───────────────────────────────────────────
    nza_rows = []
    unmatched = []
    for jurisdiction, score in town_scores.items():
        fips = _resolve_fips(jurisdiction, name_to_fips)
        if fips is None:
            unmatched.append(jurisdiction)
            continue
        nza_rows.append({
            "fips": fips,
            "pct_land_multifamily_byright": score,
            "low_sample": False,
            "data_note": None,
            "_source": "nza",
        })

    if unmatched:
        for name in sorted(unmatched):
            logger.warning(f"NZA: jurisdiction '{name}' could not be matched to a FIPS code — dropped")

    nza_df = pd.DataFrame(nza_rows) if nza_rows else pd.DataFrame(
        columns=["fips", "pct_land_multifamily_byright", "low_sample", "data_note", "_source"]
    )

    nza_fips = set(nza_df["fips"].tolist())
    logger.info(f"NZA: {len(nza_fips)} towns matched to FIPS codes")

    # ── Apply known error overrides ─────────────────────────────────────────────
    known_errors = _load_known_errors()
    if known_errors:
        overridden = 0
        for idx, row in nza_df.iterrows():
            if row["fips"] in known_errors:
                entry = known_errors[row["fips"]]
                if entry.get("treatment") == "null":
                    nza_df.at[idx, "pct_land_multifamily_byright"] = None
                    overridden += 1
                    logger.warning(
                        f"NZA: overriding {entry.get('town', row['fips'])} "
                        f"({row['fips']}) → null. Reason: {entry.get('reason', 'see known_errors file')}"
                    )
        if overridden:
            logger.info(f"NZA: {overridden} town(s) nulled due to known NZA coding errors")

    # ── Permit proxy fallback ───────────────────────────────────────────────────
    proxy_df = _get_proxy_fallback(nza_fips)

    # ── Combine ─────────────────────────────────────────────────────────────────
    combined = pd.concat([nza_df, proxy_df], ignore_index=True)
    combined = combined.rename(columns={"_source": "zoning_source"})

    nza_count = len(nza_df)
    proxy_count = len(proxy_df)
    logger.info(
        f"NZA final: {len(combined)} towns | "
        f"{nza_count} from NZA | "
        f"{proxy_count} from permit proxy fallback"
    )

    return combined[["fips", "pct_land_multifamily_byright", "low_sample", "data_note", "zoning_source"]]


# ── Known error overrides ────────────────────────────────────────────────────────

def _load_known_errors() -> dict[str, dict]:
    """
    Load known NZA coding errors for the current dataset file.
    Returns a dict of {fips: error_entry} for the current NZA filename,
    or an empty dict if the file doesn't exist or has no entry for this dataset.
    """
    if not _KNOWN_ERRORS_PATH.exists():
        return {}
    with open(_KNOWN_ERRORS_PATH, encoding="utf-8") as f:
        all_errors = json.load(f)
    dataset_key = _NZA_PATH.name
    dataset_errors = all_errors.get(dataset_key, {})
    return dataset_errors.get("towns", {})


# ── District scoring ────────────────────────────────────────────────────────────

def _score_district(props: dict) -> float | None:
    """
    Compute a [0.0, 1.0] permissiveness score for a single zoning district.

    Returns None to signal that the district is non-residential and should be
    excluded from the residential land base (denominator) entirely.

    affordable_district == 1 → included in denominator, scored 0.0
    nonresidential_type set  → None (excluded from denominator)
    family4_treatment == "allowed" → 1.0
    family3_treatment == "allowed" (f4 not allowed) → 0.5 (3-family only is partial credit)
    "hearing" → 0.0 (special permits are a restriction mechanism, not credit)
    anything else → 0.0
    """
    # Affordable districts count toward total residential acres but score 0.0
    if props.get("affordable_district") == 1:
        return 0.0

    # Non-residential land is excluded from the residential land base entirely
    if props.get("nonresidential_type"):
        return None

    f3 = props.get("family3_treatment")
    f4 = props.get("family4_treatment")

    return max(1.0 if f4 == "allowed" else 0.0,
               0.5 if f3 == "allowed" else 0.0)


# ── Town aggregation ────────────────────────────────────────────────────────────

def _aggregate_town(districts_df: pd.DataFrame) -> float | None:
    """
    Compute area-weighted average multifamily permissiveness score for one town.

    Districts with mf_score == None are excluded from the denominator (non-residential).
    Returns None if the town has no residential zoned land.
    The result is scaled to a 0–100 percentage.
    """
    residential = districts_df[districts_df["mf_score"].notna()].copy()
    if len(residential) == 0 or residential["acres"].sum() == 0:
        return None
    weighted = (residential["mf_score"] * residential["acres"]).sum()
    total_acres = residential["acres"].sum()
    return round((weighted / total_acres) * 100, 1)


# ── FIPS resolution ─────────────────────────────────────────────────────────────

def _build_name_to_fips() -> dict[str, str]:
    """Build a municipality name → FIPS dict from data/statewide.json."""
    if not _STATEWIDE_PATH.exists():
        logger.warning(f"statewide.json not found at {_STATEWIDE_PATH}")
        return {}
    with open(_STATEWIDE_PATH, encoding="utf-8") as f:
        towns = json.load(f)
    return {t["name"]: str(t["fips"]) for t in towns if "name" in t and "fips" in t}


def _resolve_fips(name: str, name_to_fips: dict[str, str]) -> str | None:
    """
    Resolve a NZA jurisdiction name to a FIPS code.

    1. Exact match.
    2. Fuzzy fallback using thefuzz token_sort_ratio with threshold >= 90.
    """
    # Exact match
    if name in name_to_fips:
        return name_to_fips[name]

    # Fuzzy fallback — token_set_ratio handles "Agawam" → "Agawam Town"
    # and "Norfolk (town)" → "Norfolk" correctly (subset relationships score ~100)
    best_score = 0
    best_fips = None
    best_match = None
    for pipeline_name, fips in name_to_fips.items():
        score = fuzz.token_set_ratio(name, pipeline_name)
        if score > best_score:
            best_score = score
            best_fips = fips
            best_match = pipeline_name

    if best_score >= _FUZZY_THRESHOLD:
        logger.info(
            f"NZA: fuzzy match '{name}' → '{best_match}' "
            f"(score={best_score}) → FIPS {best_fips}"
        )
        return best_fips

    return None


# ── Permit proxy fallback ───────────────────────────────────────────────────────

def _get_proxy_fallback(nza_fips: set[str]) -> pd.DataFrame:
    """
    Fetch permit proxy data for towns not covered by NZA.

    Renames pct_multifamily_permitted → pct_land_multifamily_byright so the
    column name is consistent with the NZA output.
    """
    try:
        from pipeline.ingest.zoning_permits_proxy import get_zoning_data as _proxy_fn
        proxy = _proxy_fn()
    except Exception as exc:
        logger.warning(f"NZA: permit proxy fallback failed ({exc}) — uncovered towns will have null grades")
        return pd.DataFrame(
            columns=["fips", "pct_land_multifamily_byright", "low_sample", "data_note", "_source"]
        )

    if proxy.empty:
        return pd.DataFrame(
            columns=["fips", "pct_land_multifamily_byright", "low_sample", "data_note", "_source"]
        )

    # Only keep towns not already covered by NZA
    fallback = proxy[~proxy["fips"].isin(nza_fips)].copy()
    fallback = fallback.rename(columns={"pct_multifamily_permitted": "pct_land_multifamily_byright"})
    fallback["_source"] = "proxy"

    logger.info(
        f"NZA: permit proxy fallback covers {len(fallback)} additional towns "
        f"(out of {len(proxy)} total in proxy dataset)"
    )
    return fallback[["fips", "pct_land_multifamily_byright", "low_sample", "data_note", "_source"]]


def _permit_proxy_only() -> pd.DataFrame:
    """Return permit proxy data for all towns (used when NZA file is unavailable)."""
    try:
        from pipeline.ingest.zoning_permits_proxy import get_zoning_data as _proxy_fn
        proxy = _proxy_fn()
        df = proxy.rename(columns={"pct_multifamily_permitted": "pct_land_multifamily_byright"})
        df["zoning_source"] = "proxy"
        return df
    except Exception as exc:
        logger.warning(f"Permit proxy also failed ({exc})")
        return pd.DataFrame(
            columns=["fips", "pct_land_multifamily_byright", "low_sample", "data_note", "zoning_source"]
        )
