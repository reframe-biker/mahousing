"""
zoning_permits_proxy.py — Revealed-preference zoning metric for MA Housing Report Card

Computes a "revealed zoning permissiveness" score from Census Building Permits
Survey data. Used as an interim zoning metric while National Zoning Atlas bulk
data is being sought.

METRIC:
  pct_units_multifamily = (5+ unit permits) / (total permits) over 3 years

WHY THIS WORKS:
  A town's actual permit mix is revealed preference for how permissive its
  zoning is in practice. A town issuing 80% of permitted units in 5+ unit
  structures is functionally more permissive than one issuing 95% single-family
  permits, regardless of what the zoning code says on paper.

GRADE RUBRIC:
  A  > 40% of permitted units are in 5+ unit structures
  B  25–40%
  C  10–25%
  D  2–10%
  F  < 2%
  null  fewer than 10 total permits over 3 years (sample too thin)

SPIKE DETECTION:
  A data_note is attached when ALL THREE conditions hold:
    1. A single year accounts for > 70% of the town's 3-year permit total
    2. The 3-year total is < 50 permits
    3. The town's population is < 15,000  (filter applied in build.py after
       ACS join; for larger places a low permit count is a genuine finding)
  The grade is NOT changed — the note is for transparency only.
  See METHODOLOGY.md for the full explanation.

OUTPUT CONTRACT (shared by all zoning sources):
  fips                     (str)          10-digit county subdivision GEOID
  pct_multifamily_by_right (float | None) The permissiveness score (None = null grade)
  low_sample               (bool)         True if total permits < 10 over 3 years
  data_note                (str | None)   Human-readable quality flag; None if no issue

Note: the column is named pct_multifamily_by_right for schema compatibility
with pipeline/schema.py. The underlying metric is permit mix, not a by-right
land area share. See METHODOLOGY.md for the distinction.
"""

from __future__ import annotations

import logging

import pandas as pd

from pipeline.ingest.building_permits import BPS_YEAR, fetch_permit_breakdown

logger = logging.getLogger(__name__)

# Most recent 3 calendar years available in BPS
_BPS_YEARS = [BPS_YEAR, BPS_YEAR - 1, BPS_YEAR - 2]

# Minimum total permits over the 3-year window to produce a non-null grade
_MIN_PERMIT_THRESHOLD = 10

# Spike detection thresholds (conditions 1 and 2 of 3; condition 3 — population
# < 15,000 — is enforced in build.py after the ACS join supplies population data)
# _SPIKE_YEAR_SHARE_THRESHOLD: single year must be > this share of the 3yr total
# _SPIKE_MAX_TOTAL_PERMITS: only flag towns with fewer than this many total permits
#   (50 was chosen to include Dover, MA which has 43 total — 34 of them in 2023)
_SPIKE_YEAR_SHARE_THRESHOLD = 0.70
_SPIKE_MAX_TOTAL_PERMITS = 50

_SPIKE_NOTE = (
    "Zoning grade driven primarily by a single year of permit activity"
    " — may not reflect the town's typical permitting pattern."
)


def get_zoning_data() -> pd.DataFrame:
    """
    Compute revealed-preference zoning permissiveness from 3 years of BPS data.

    Fetches permit data for the 3 most recent available years, aggregates by
    municipality, computes the share of units in 5+ unit structures, and runs
    spike detection to flag towns where one year dominates.

    Returns:
        DataFrame with columns:
            fips                     (str)          10-digit GEOID
            pct_multifamily_by_right (float | None) Permissiveness score; None for low-sample towns
            low_sample               (bool)         True if fewer than 10 total permits
            data_note                (str | None)   Quality flag text; None if no issue detected

        Returns an empty DataFrame with correct columns if all fetches fail.
    """
    empty = pd.DataFrame(
        columns=["fips", "pct_multifamily_by_right", "low_sample", "data_note"]
    )

    frames: list[pd.DataFrame] = []
    for year in _BPS_YEARS:
        df = fetch_permit_breakdown(year)
        if not df.empty:
            frames.append(df)

    if not frames:
        logger.warning("Permits proxy: no BPS data loaded for any year — zoning grades will be null.")
        return empty

    logger.info(f"Permits proxy: aggregating {len(frames)} year(s) of BPS data ({_BPS_YEARS[:len(frames)]})")

    all_years = pd.concat(frames, ignore_index=True)

    # Max single-year permits per municipality (needed for spike detection).
    # Computed before the 3-year aggregation so we retain per-year resolution.
    max_year_permits = (
        all_years.groupby("geoid")["permits"]
        .max()
        .rename("max_year_permits")
    )

    # 3-year totals
    combined = (
        all_years
        .groupby("geoid", as_index=False)
        .agg(units_5p=("units_5p", "sum"), permits=("permits", "sum"))
    )

    # Join max single-year permits back onto the 3-year totals
    combined = combined.join(max_year_permits, on="geoid")

    # ── Low-sample flag ────────────────────────────────────────────────────
    combined["low_sample"] = combined["permits"] < _MIN_PERMIT_THRESHOLD

    # Compute ratio only for towns with sufficient sample
    ratio = (combined["units_5p"] / combined["permits"].replace(0, float("nan"))) * 100
    combined["pct_multifamily_by_right"] = ratio.where(~combined["low_sample"]).round(1)

    # ── Spike detection ────────────────────────────────────────────────────
    combined["max_single_year_share"] = (
        combined["max_year_permits"] / combined["permits"].replace(0, float("nan"))
    )

    spike_mask = (
        (combined["max_single_year_share"] > _SPIKE_YEAR_SHARE_THRESHOLD)
        & (combined["permits"] < _SPIKE_MAX_TOTAL_PERMITS)
        & ~combined["low_sample"]   # only flag towns that actually have a grade
    )

    combined["data_note"] = None
    combined.loc[spike_mask, "data_note"] = _SPIKE_NOTE

    # ── Logging ────────────────────────────────────────────────────────────
    non_null = combined["pct_multifamily_by_right"].notna().sum()
    low_sample_count = combined["low_sample"].sum()
    spike_count = spike_mask.sum()
    logger.info(
        f"  Permits proxy: {len(combined)} municipalities | "
        f"{non_null} with sufficient sample | "
        f"{low_sample_count} flagged low-sample (null grade) | "
        f"{spike_count} flagged single-year spike"
    )

    if spike_count > 0:
        spiked = combined.loc[spike_mask, ["geoid", "permits", "max_year_permits", "max_single_year_share"]]
        for _, row in spiked.iterrows():
            logger.info(
                f"    Spike: {row['geoid']}  total={int(row['permits'])}  "
                f"max_year={int(row['max_year_permits'])}  "
                f"share={row['max_single_year_share']:.0%}"
            )

    result = combined[
        ["geoid", "pct_multifamily_by_right", "low_sample", "data_note"]
    ].rename(columns={"geoid": "fips"})

    return result
