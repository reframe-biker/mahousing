"""
rebuild_district_map.py — Rebuild data/town_district_map.json as one-to-many.

Fixes the bug where multi-district cities (Boston, Cambridge, Springfield, etc.)
were assigned only one House district. The new map stores a list of districts
per municipality instead of a single string.

BEFORE:
    "2502507000": "7th Suffolk"

AFTER:
    "2502507000": ["1st Suffolk", "2nd Suffolk", ..., "19th Suffolk"]

Usage (run from repo root):
    python pipeline/rebuild_district_map.py

Requirements:
    pip install geopandas shapely

Inputs (both gitignored — must be present locally):
    - TIGER SLDL shapefile:  tl_2024_25_sldl.shp  (and .dbf, .shx, .prj)
    - Census place shapefile: tl_2024_25_place.shp
      Download from: https://www2.census.gov/geo/tiger/TIGER2024/PLACE/tl_2024_25_place.zip

Output:
    data/town_district_map.json  (committed to repo)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
OUT_PATH = DATA_DIR / "town_district_map.json"

# TIGER shapefiles — gitignored, must be present locally
# Place the SLDL shapefile anywhere and update this path, or put it in the
# default location used by the original build script.
SLDL_SHP = REPO_ROOT / "data" / "tl_2024_25_sldl.shp"

# Census county subdivision shapefile — needed to get municipality polygons.
# GEOIDs are state(2)+county(3)+cousub(5) = 10 digits, matching town_district_map.json keys.
# Download: https://www2.census.gov/geo/tiger/TIGER2024/COUSUB/tl_2024_25_cousub.zip
PLACE_SHP = REPO_ROOT / "data" / "tl_2024_25_cousub.shp"

# ── GEOID overrides for consolidated city-towns ───────────────────────────────
#
# Four MA towns were reclassified as consolidated city-towns (CLASSFP=C5) in
# the 2024 COUSUB shapefile, which gave them new COUSUBFP codes.  Their JSON
# files in data/towns/ still carry the pre-reclassification FIPS.  We keep
# the JSON filenames and fips fields unchanged; instead we remap the shapefile
# GEOID back to the legacy fips in the output map.
#
# Format:  old_json_fips  →  new_shapefile_geoid
GEOID_OVERRIDES: dict[str, str] = {
    "2500901260": "2500901185",  # Amesbury city
    "2500940710": "2500940675",  # Methuen city
    "2501519370": "2501519365",  # Easthampton city
    "2501773440": "2501773405",  # Watertown city
}

# Overlap thresholds — two-tier to handle same-county vs. cross-county cases:
#
#   SAME_COUNTY_MIN (1%):   keeps all same-county assignments, including large
#     cities where each district covers only a small fraction of the city area
#     (e.g. Boston's 16 Suffolk districts, each ~2–43% of the city).
#
#   CROSS_COUNTY_MIN (15%): filters cross-county artifacts (Lynn/2nd Suffolk
#     at 11.6%) while keeping genuine cross-county assignments (Bolton is 100%
#     within 3rd Middlesex even though Bolton is in Worcester County).
#
# The Barnstable-Dukes-Nantucket district spans three counties and is exempt
# from the cross-county threshold by name.
SAME_COUNTY_MIN = 0.01   # 1%
CROSS_COUNTY_MIN = 0.15  # 15%


def _clean_district_name(namelsad: str) -> str:
    """
    Convert TIGER NAMELSAD to the short form used in the existing map.

    '3rd Barnstable District' -> '3rd Barnstable'
    'Barnstable, Dukes and Nantucket District' -> 'Barnstable, Dukes and Nantucket'
    """
    return re.sub(r"\s+District$", "", namelsad.strip())


def main() -> None:
    # ── Load shapefiles ───────────────────────────────────────────────────────

    if not SLDL_SHP.exists():
        raise FileNotFoundError(
            f"SLDL shapefile not found: {SLDL_SHP}\n"
            "Place tl_2024_25_sldl.shp (and .dbf, .shx, .prj) in data/.\n"
            "Download from: https://www2.census.gov/geo/tiger/TIGER2024/SLDL/tl_2024_25_sldl.zip"
        )
    if not PLACE_SHP.exists():
        raise FileNotFoundError(
            f"COUSUB shapefile not found: {PLACE_SHP}\n"
            "Download from:\n"
            "  https://www2.census.gov/geo/tiger/TIGER2024/COUSUB/tl_2024_25_cousub.zip\n"
            "and place tl_2024_25_cousub.shp (and .dbf, .shx, .prj) in data/."
        )

    print("Loading SLDL shapefile...")
    districts = gpd.read_file(SLDL_SHP)
    print(f"  {len(districts)} House districts loaded")

    print("Loading Census place shapefile...")
    places = gpd.read_file(PLACE_SHP)
    places = places[places["COUSUBFP"] != "00000"]  # drop "county subdivisions not defined" placeholders
    print(f"  {len(places)} Census places loaded")

    # ── Reproject to a MA planar CRS for accurate area calculations ───────────
    # EPSG:26986 = NAD83 / Massachusetts Mainland (meters)
    print("Reprojecting to EPSG:26986...")
    districts = districts.to_crs(epsg=26986)
    places = places.to_crs(epsg=26986)

    # ── Compute place areas before the join ───────────────────────────────────
    places = places.copy()
    places["place_area"] = places.geometry.area

    # ── Spatial join: intersect every place with every overlapping district ───
    print("Running spatial join (intersection)...")
    joined = gpd.overlay(places, districts, how="intersection", keep_geom_type=False)

    # Area of each intersection piece
    joined["intersect_area"] = joined.geometry.area

    # Fraction of the place's total area covered by this district
    # place_area carries through the overlay — no re-merge needed
    joined["overlap_frac"] = joined["intersect_area"] / joined["place_area"]

    # ── Tiered overlap filter ─────────────────────────────────────────────────
    # Same-county assignments: low threshold (1%) — keeps large cities where
    # each district covers a small fraction of the city (e.g. Boston).
    # Cross-county assignments: high threshold (15%) — drops boundary artifacts
    # (Lynn/2nd Suffolk at 11.6%) while keeping genuine cross-county cases
    # (Bolton/3rd Middlesex at 100%).
    COUNTY_FIPS_TO_NAME = {
        "001": "Barnstable", "003": "Berkshire", "005": "Bristol",
        "007": "Dukes",      "009": "Essex",     "011": "Franklin",
        "013": "Hampden",    "015": "Hampshire",  "017": "Middlesex",
        "019": "Nantucket",  "021": "Norfolk",    "023": "Plymouth",
        "025": "Suffolk",    "027": "Worcester",
    }

    def _threshold(row) -> float:
        district_name = str(row["NAMELSAD_2"])
        if "Barnstable, Dukes and Nantucket" in district_name:
            return SAME_COUNTY_MIN
        county_fips = str(row["COUNTYFP"]).zfill(3)
        expected = COUNTY_FIPS_TO_NAME.get(county_fips, "")
        if expected and expected in district_name:
            return SAME_COUNTY_MIN   # same-county assignment
        return CROSS_COUNTY_MIN     # cross-county — apply stricter threshold

    joined["_threshold"] = joined.apply(_threshold, axis=1)
    above = joined[joined["overlap_frac"] >= joined["_threshold"]]

    # ── Fallback: towns with no district above threshold ──────────────────────
    # For any GEOID that was filtered out entirely, assign the single district
    # with the highest overlap_frac (best available match) and log a warning.
    all_geoids = set(joined["GEOID_1"].astype(str))
    kept_geoids = set(above["GEOID_1"].astype(str))
    fallback_geoids = all_geoids - kept_geoids

    if fallback_geoids:
        print(f"  Warning: {len(fallback_geoids)} town(s) had no district above threshold — using best-overlap fallback:")
        fallback_rows = []
        for geoid in sorted(fallback_geoids):
            candidates = joined[joined["GEOID_1"].astype(str) == geoid]
            best = candidates.loc[candidates["overlap_frac"].idxmax()]
            district = _clean_district_name(str(best["NAMELSAD_2"]))
            frac = best["overlap_frac"]
            print(f"    {geoid}: {district} ({frac:.1%} overlap)")
            fallback_rows.append(best)
        fallback_df = gpd.GeoDataFrame(fallback_rows, crs=joined.crs)
        joined = gpd.GeoDataFrame(
            pd.concat([above, fallback_df], ignore_index=True), crs=joined.crs
        )
    else:
        joined = above

    # ── Build the output map ──────────────────────────────────────────────────
    print("Building output map...")

    # After gpd.overlay(), duplicate column names are suffixed _1 (places) and _2 (districts).
    # GEOID_1 = COUSUB GEOID (10-digit: state+county+cousub), NAMELSAD_2 = district name.

    district_map: dict[str, list[str]] = {}

    for _, row in joined.iterrows():
        geoid = str(row["GEOID_1"])
        district = _clean_district_name(str(row["NAMELSAD_2"]))
        if geoid not in district_map:
            district_map[geoid] = []
        if district not in district_map[geoid]:
            district_map[geoid].append(district)

    # Sort district lists for deterministic output
    for geoid in district_map:
        district_map[geoid].sort()

    # ── Apply GEOID overrides (consolidated city-towns) ───────────────────────
    # Replace each new shapefile GEOID key with the legacy fips used by the JSON
    # files, so downstream consumers find entries under the expected key.
    for old_fips, new_geoid in GEOID_OVERRIDES.items():
        if new_geoid in district_map:
            district_map[old_fips] = district_map.pop(new_geoid)
            print(f"  GEOID override applied: {new_geoid} → {old_fips}")
        else:
            print(f"  Warning: GEOID override for {old_fips} — shapefile GEOID {new_geoid} not found in join results")

    # ── Write output ──────────────────────────────────────────────────────────
    OUT_PATH.write_text(json.dumps(district_map, indent=2, sort_keys=True), encoding="utf-8")

    # ── Print summary ─────────────────────────────────────────────────────────
    multi = {k: v for k, v in district_map.items() if len(v) > 1}
    single = {k: v for k, v in district_map.items() if len(v) == 1}
    null_places = 351 - len(district_map)  # places with no district match

    print(f"\nDone. Written to {OUT_PATH}")
    print(f"  Total municipalities mapped: {len(district_map)}")
    print(f"  Single-district towns:       {len(single)}")
    print(f"  Multi-district towns:        {len(multi)}")
    print(f"  Unmatched (no district):     {null_places}")
    print()
    print("Multi-district municipalities:")
    for geoid, districts in sorted(multi.items(), key=lambda x: -len(x[1])):
        print(f"  {geoid}: {districts}")


if __name__ == "__main__":
    main()


# ── IMPORTANT NOTE ON GEOID FORMAT ────────────────────────────────────────────
#
# The existing town_district_map.json uses 10-digit keys like "2500103690".
# These are Census COUNTY SUBDIVISION (COUSUB) GEOIDs:
#   state(2) + county(3) + cousub(5) = 10 digits
#
# MA municipalities map cleanly to county subdivisions (each town is its own
# cousub). The TIGER file for this is:
#   https://www2.census.gov/geo/tiger/TIGER2024/COUSUB/tl_2024_25_cousub.zip
#
# If you use the PLACE shapefile instead, GEOIDs will be 7 digits and won't
# match the existing keys. Use the COUSUB shapefile for the places input.
#
# Download:
#   https://www2.census.gov/geo/tiger/TIGER2024/COUSUB/tl_2024_25_cousub.zip
# Then update PLACE_SHP above to point to tl_2024_25_cousub.shp.
