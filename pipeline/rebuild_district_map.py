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

# Minimum overlap fraction: a district must cover at least this share of a
# municipality's area to be included. Filters out tiny slivers from boundary
# imprecision (e.g. a district that technically clips 0.1% of a town corner).
MIN_OVERLAP_FRACTION = 0.01  # 1%


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
    joined = joined.merge(
        places[["GEOID", "place_area"]].rename(columns={"GEOID": "GEOID_place"}),
        on="GEOID_place",
        how="left",
    )
    joined["overlap_frac"] = joined["intersect_area"] / joined["place_area"]

    # Drop slivers
    joined = joined[joined["overlap_frac"] >= MIN_OVERLAP_FRACTION]

    # Clean district name
    joined["district_name"] = joined["NAMELSAD"].apply(_clean_district_name)

    # ── Build the output map ──────────────────────────────────────────────────
    print("Building output map...")

    # Full 10-digit place GEOID: state(2) + county(3) + place(5)
    # The TIGER place file GEOID field is already the full 7-digit place code.
    # Prepend state FIPS "25" to get the 10-digit key matching the existing map.
    # Actually: Census place GEOIDs in the place shapefile are already 7 chars
    # (state 2 + place 5). The existing map keys are 10 chars. Let's check:
    # existing key example: "2500103690" = "25" + "001" + "03690"?
    # That looks like state(2) + county(3) + tract(5) ... but there are exactly
    # 351 = number of MA municipalities. So they must be place GEOIDs.
    # Census place GEOID = state(2) + place(5) = 7 digits. But keys are 10 digits.
    # The extra 3 digits suggest these are COUSUB (county subdivision) GEOIDs:
    # state(2) + county(3) + cousub(5) = 10 digits. Use COUSUB shapefile instead
    # if place shapefile GEOIDs don't match. See note at bottom.

    district_map: dict[str, list[str]] = {}

    for _, row in joined.iterrows():
        geoid = str(row.get("GEOID_place", row.get("GEOID", "")))
        district = row["district_name"]
        if geoid not in district_map:
            district_map[geoid] = []
        if district not in district_map[geoid]:
            district_map[geoid].append(district)

    # Sort district lists for deterministic output
    for geoid in district_map:
        district_map[geoid].sort()

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
