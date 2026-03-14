"""
zoning.py — Zoning data router for MA Housing Report Card

Single entry point for zoning data regardless of which underlying source is
active. build.py imports get_zoning_data() from here; it never imports from
a specific source module directly.

TO SWITCH DATA SOURCES:
  Change ZONING_SOURCE below to "mapc" or "nza" and re-run the pipeline.
  No other files need to change.

OUTPUT CONTRACT:
  get_zoning_data() always returns a DataFrame with these columns:

    fips                     (str)
        10-digit county subdivision GEOID — joins to acs_df["geoid"] in build.py.

    pct_multifamily_permitted (float | None)
        The permissiveness score for this source.  None means the grade will
        be null for that municipality (insufficient data, not a failing grade).
        The column name is kept stable for schema compatibility even when the
        underlying metric is not a literal "by right" land-area share — see
        METHODOLOGY.md for the distinction.

    low_sample               (bool)
        True if the underlying data is thin enough that the grade should be
        treated cautiously.  build.py logs this count; score.py uses the None
        in pct_multifamily_permitted to produce a null grade.

    data_note                (str | None)
        Human-readable quality flag attached to this town's zoning grade.
        None means no quality issue detected.  Only the permits_proxy source
        currently populates this field (single-year spike detection).
        MAPC and NZA sources always return None here.

AVAILABLE SOURCES:
  "permits_proxy"  Census BPS permit mix over 3 years (interim, covers ~346 towns)
  "mapc"           MAPC Zoning Atlas v01 (Metro Boston only, ~101 towns)
  "nza"            National Zoning Atlas (stub — not yet available)
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# ── Active source ──────────────────────────────────────────────────────────────
# Change this constant to switch data sources.  Options: "permits_proxy" | "mapc" | "nza"
ZONING_SOURCE = "permits_proxy"  # interim — swap to "nza" when bulk data is available

_SOURCE_NOTES = {
    "permits_proxy": "interim — swap to nza when NZA bulk data is available",
    "mapc": "Metro Boston coverage only (~101 towns)",
    "nza": "full statewide coverage — requires NZA bulk data",
}


def get_zoning_data() -> pd.DataFrame:
    """
    Return zoning permissiveness data using the source configured in ZONING_SOURCE.

    See module docstring for the output contract all sources must satisfy.
    """
    note = _SOURCE_NOTES.get(ZONING_SOURCE, "")
    logger.info(f"Zoning source: {ZONING_SOURCE}  ({note})")

    if ZONING_SOURCE == "permits_proxy":
        from pipeline.ingest.zoning_permits_proxy import get_zoning_data as _fn
        return _fn()

    if ZONING_SOURCE == "mapc":
        from pipeline.ingest.zoning_atlas import get_zoning_data as _mapc_fn
        return _adapt_mapc(_mapc_fn())

    if ZONING_SOURCE == "nza":
        from pipeline.ingest.zoning_nza import get_zoning_data as _fn
        return _fn()

    raise ValueError(
        f"Unknown ZONING_SOURCE {ZONING_SOURCE!r}. "
        "Valid options: 'permits_proxy', 'mapc', 'nza'"
    )


def _adapt_mapc(mapc_df: pd.DataFrame) -> pd.DataFrame:
    """
    Adapt MAPC Zoning Atlas output (muni_name-keyed) to the standard fips contract.

    The MAPC module returns muni_name + pct_multifamily_permitted.
    build.py expects fips + pct_multifamily_permitted + low_sample.

    Resolution strategy: we cannot do name→FIPS lookup here without importing
    ACS data, so we return muni_name in the fips column and let build.py handle
    it via a name-based join fallback.  The caller (build.py) must detect this
    case; see the MAPC join note in build.py.

    In practice, switching to "mapc" is only useful for debugging Metro Boston
    coverage.  The default "permits_proxy" covers all 346 permit-reporting towns.
    """
    if mapc_df.empty:
        return pd.DataFrame(columns=["fips", "pct_multifamily_permitted", "low_sample", "data_note"])

    result = mapc_df.rename(columns={"muni_name": "fips"}).copy()
    result["low_sample"] = False
    result["data_note"] = None  # spike detection only applies to permits_proxy
    return result[["fips", "pct_multifamily_permitted", "low_sample", "data_note"]]
