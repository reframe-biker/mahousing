"""
zoning_nza.py — National Zoning Atlas ingest stub for MA Housing Report Card

STUB — not yet implemented.

When bulk data is available from the National Zoning Atlas (zoningatlas.org),
this module will replace zoning_permits_proxy as the default zoning source.
To activate it: set ZONING_SOURCE = "nza" in pipeline/ingest/zoning.py.

WHAT THIS WILL INGEST:
  The NZA provides parcel-level or district-level zoning data for all 351 MA
  municipalities, including explicit fields for multifamily-by-right permissions.
  Unlike the MAPC Zoning Atlas v01, NZA covers all of Massachusetts — not just
  Metro Boston.

REQUIRED OUTPUT CONTRACT:
  get_zoning_data() must return a DataFrame with these columns:

    fips                     (str)          10-digit county subdivision GEOID
    pct_multifamily_permitted (float | None) % of land (or equivalent metric)
                                            permitting multifamily by right;
                                            None = insufficient data for that town
    low_sample               (bool)         True if data coverage is thin enough
                                            that the grade should be treated
                                            cautiously (e.g., < 50% of parcels
                                            have zoning codes resolved)

DATA ACQUISITION STATUS:
  Bulk download API not yet publicly available as of 2026-03.
  Contact: info@zoningatlas.org
  Tracking issue: https://github.com/reframe-biker/mahousing/issues — add issue #
"""

from __future__ import annotations

import pandas as pd


def get_zoning_data() -> pd.DataFrame:
    """
    Fetch National Zoning Atlas data for MA municipalities.

    NOT YET IMPLEMENTED. Raises NotImplementedError.

    When implemented, returns:
        DataFrame with columns: fips (str), pct_multifamily_permitted (float|None),
        low_sample (bool). See module docstring for full contract.
    """
    raise NotImplementedError(
        "National Zoning Atlas ingest is not yet implemented.\n"
        "Set ZONING_SOURCE = 'permits_proxy' or 'mapc' in pipeline/ingest/zoning.py."
    )
