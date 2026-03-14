"""
zoning_atlas.py — MA Zoning Atlas ingest for MA Housing Report Card

Fetches zoning district data from the MAPC Massachusetts Zoning Atlas
(v01) and computes, for each municipality, the percentage of mapped
land area where multifamily housing is permitted by right — without any
special permit or discretionary approval.

Source: Massachusetts Zoning Atlas, Metropolitan Area Planning Council (MAPC)
URL:    https://geo.mapc.org/server/rest/services/gisdata/Zoning_Atlas_v01/MapServer
Data page: https://zoningatlas.mapc.org/

COVERAGE NOTE:
The MAPC Zoning Atlas v01 covers approximately 101 cities and towns in
Metropolitan Boston, not all 351 MA municipalities. Towns outside Metro Boston
will have null zoning grades until a statewide dataset is available.

The National Zoning Atlas (zoningatlas.org) covers all 351 municipalities but
does not currently provide a public bulk download API. MAPC's v01 is used
for Phase 1.

FIELD NOTES:
  muni        — Municipality name (e.g. "Cambridge")
  mulfam2     — Multifamily (2-unit) permission code:
                  0 = not allowed
                  1 = allowed by right
                  2 = allowed by special permit only
  Shape_Area  — Polygon area in the service's native CRS (MA State Plane, meters)

METRIC:
  pct_multifamily_by_right = (sum of area where mulfam2 == 1) /
                              (sum of total district area) * 100

Note: mulfam2 tracks 2-unit (duplex) permissions. The v01 schema does not
include a separate field for 3+ unit buildings. Phase 2 will evaluate
whether the v02 schema adds larger multifamily fields; for now, duplex
by-right is used as a proxy for zoning permissiveness.
"""

import io
import logging
import os

import geopandas as gpd
import pandas as pd
import requests

logger = logging.getLogger(__name__)

# MAPC Zoning Atlas v01 — zoning_full layer (Layer 2)
# Override via ZONING_ATLAS_URL environment variable if the endpoint changes.
_DEFAULT_URL = (
    "https://geo.mapc.org/server/rest/services/gisdata/Zoning_Atlas_v01/MapServer/2/query"
    "?where=1%3D1&outFields=muni%2CShape_Area%2Cmulfam2&returnGeometry=false&f=json"
)

# Field names in the MAPC Zoning Atlas v01
_MUNI_FIELD = "muni"
_MF_BYRIGHT_FIELD = "mulfam2"
_AREA_FIELD = "Shape_Area"    # native CRS area in square meters (MA State Plane)

# Value in mulfam2 that means "allowed by right"
_BY_RIGHT_CODE = 1

# Maximum features per ArcGIS REST page (service default is 2000; we paginate defensively)
_PAGE_SIZE = 2000

_REQUEST_TIMEOUT = 60


def fetch_zoning_data(url: str | None = None) -> pd.DataFrame:
    """
    Fetch MAPC Zoning Atlas v01 data and compute pct_multifamily_by_right per municipality.

    Args:
        url: ArcGIS REST query URL. Defaults to ZONING_ATLAS_URL environment
             variable, then the hardcoded MAPC endpoint.

    Returns:
        DataFrame with columns:
            muni_name                (str)   Municipality name (un-normalized)
            pct_multifamily_by_right (float) % of district area allowing duplex by right

        Returns an empty DataFrame (with correct columns) if the data cannot
        be fetched or parsed. The pipeline continues with null zoning grades.

        Coverage: approximately 101 municipalities in Metro Boston.
        Municipalities outside this coverage will not appear in the result and
        will receive null zoning grades.
    """
    base_url = url or os.environ.get("ZONING_ATLAS_URL", _DEFAULT_URL)
    logger.info(f"Fetching MA Zoning Atlas from MAPC geo server…")

    all_records = _paginate(base_url)
    if not all_records:
        return pd.DataFrame(columns=["muni_name", "pct_multifamily_by_right"])

    df = pd.DataFrame(all_records)
    logger.info(f"  Loaded {len(df)} zoning district records across {df[_MUNI_FIELD].nunique()} municipalities")

    return _compute_pct(df)


def _paginate(base_url: str) -> list[dict]:
    """Download all features from the ArcGIS REST service with offset pagination."""
    all_records = []
    offset = 0

    while True:
        paginated_url = f"{base_url}&resultOffset={offset}&resultRecordCount={_PAGE_SIZE}"
        try:
            resp = requests.get(paginated_url, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as exc:
            if offset == 0:
                logger.warning(
                    f"Zoning Atlas fetch failed: {exc}\n"
                    f"  All municipalities will have null zoning grades.\n"
                    f"  To fix: check ZONING_ATLAS_URL or contact MAPC (zoning@mapc.org)."
                )
            else:
                logger.warning(f"Zoning Atlas pagination stopped at offset {offset}: {exc}")
            break

        data = resp.json()

        if "error" in data:
            logger.warning(
                f"Zoning Atlas API error at offset {offset}: {data['error']}\n"
                f"  All municipalities will have null zoning grades."
            )
            break

        features = data.get("features", [])
        if not features:
            break  # No more data

        for feat in features:
            attrs = feat.get("attributes", {})
            all_records.append(attrs)

        logger.debug(f"  Fetched {len(features)} records at offset {offset} (total so far: {len(all_records)})")

        if len(features) < _PAGE_SIZE:
            break  # Last page

        offset += _PAGE_SIZE

    return all_records


def _compute_pct(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute pct_multifamily_by_right per municipality from the raw feature table.

    A district contributes to the "by-right" numerator if mulfam2 == 1.
    The denominator is the total area of all districts in the municipality.
    """
    if _MUNI_FIELD not in df.columns or _AREA_FIELD not in df.columns or _MF_BYRIGHT_FIELD not in df.columns:
        logger.warning(
            f"Zoning Atlas: expected columns ({_MUNI_FIELD}, {_AREA_FIELD}, {_MF_BYRIGHT_FIELD}) "
            f"not found. Actual columns: {list(df.columns)}"
        )
        return pd.DataFrame(columns=["muni_name", "pct_multifamily_by_right"])

    df = df[[_MUNI_FIELD, _AREA_FIELD, _MF_BYRIGHT_FIELD]].copy()
    df[_AREA_FIELD] = pd.to_numeric(df[_AREA_FIELD], errors="coerce").fillna(0)

    # Total area per municipality
    total_area = df.groupby(_MUNI_FIELD)[_AREA_FIELD].sum()

    # Area where multifamily is by right
    mf_byright = (
        df[df[_MF_BYRIGHT_FIELD] == _BY_RIGHT_CODE]
        .groupby(_MUNI_FIELD)[_AREA_FIELD]
        .sum()
    )

    summary = pd.DataFrame({"total_area": total_area, "mf_area": mf_byright}).fillna(0)
    summary["pct_multifamily_by_right"] = (
        (summary["mf_area"] / summary["total_area"].replace(0, float("nan"))) * 100
    ).round(1)

    result = summary[["pct_multifamily_by_right"]].reset_index()
    result = result.rename(columns={_MUNI_FIELD: "muni_name"})

    by_right_count = (result["pct_multifamily_by_right"] > 0).sum()
    logger.info(
        f"  Zoning Atlas: {len(result)} municipalities with data | "
        f"{by_right_count} have any by-right multifamily area"
    )
    return result
