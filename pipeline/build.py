"""
build.py — Pipeline orchestrator for MA Housing Report Card

This module will be implemented in Phase 1. It is the main entry point for
the data pipeline and is called by the GitHub Actions workflow on a weekly
cron schedule.

Responsibilities:

1. Coordinate all ingest modules under pipeline/ingest/ to fetch or download
   fresh data from each source (MA Zoning Atlas, Census ACS, Census Building
   Permits Survey, Zillow Research, and — in later phases — MBTA compliance
   records and legislative vote data).

2. For each of the 351 MA municipalities, assemble a raw metrics dict from
   the ingested data, call score.score_town() to produce grades, and produce
   a TownRecord (per schema.py) with an updated `updated_at` timestamp.

3. Write each town's record to data/towns/<fips>.json, where <fips> is the
   town's 5-digit MA FIPS code.

4. Aggregate all town records into data/statewide.json, which the Next.js
   frontend reads to render the full municipality list and map view.

5. Log a summary of the run (towns updated, towns skipped due to missing data,
   any source fetch errors) to stdout so GitHub Actions can surface failures.

Usage:
    python -m pipeline.build

Environment variables (see .env.example):
    CENSUS_API_KEY   — required for Census ACS and Building Permits endpoints
    ZILLOW_DATA_URL  — URL to Zillow's publicly posted research data CSV
"""


def main() -> None:
    """
    Run the full pipeline: ingest → score → write output JSON files.

    Not yet implemented — will be built out in Phase 1.
    """
    raise NotImplementedError("build.main() will be implemented in Phase 1.")


if __name__ == "__main__":
    main()
