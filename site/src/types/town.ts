/**
 * Canonical TypeScript types for MA Housing Report Card town records.
 *
 * This file mirrors the Python schema defined in pipeline/schema.py.
 * All frontend components that consume town data must use these types.
 *
 * A null value in any grade or metric field means the data has not yet
 * been collected for that municipality. It is NOT equivalent to an F or zero.
 * The UI must display null grades as "N/A".
 */

/** Valid letter grades. null means data not yet collected — not an F. */
export type Grade = "A" | "B" | "C" | "D" | "F" | null;

/** MBTA Communities Act compliance status. */
export type MbtaStatus = "compliant" | "non-compliant" | "exempt" | null;

export interface Grades {
  /** Zoning Permissiveness — share of land area permitting multifamily by right (MA Zoning Atlas) */
  zoning: Grade;
  /** MBTA Communities Act compliance status */
  mbta: Grade;
  /** Housing Production rate — permits per 1,000 residents (Census Building Permits) */
  production: Grade;
  /** Affordability burden — rent burden + median home value (Census ACS + Zillow) */
  affordability: Grade;
  /** Town Meeting voting record on housing articles */
  votes: Grade;
  /** State legislator housing vote record (future phase) */
  rep: Grade;
  /** Weighted composite of all applicable dimensions */
  composite: Grade;
}

export interface Metrics {
  /**
   * Percentage of the municipality's land area where multifamily housing
   * is permitted by right (no special permit required). Range: 0–100.
   * Source: MA Zoning Atlas (MAPC).
   */
  pct_multifamily_by_right: number | null;

  /**
   * Median owner-occupied home value in USD.
   * Source: US Census ACS 5-year estimates.
   */
  median_home_value: number | null;

  /**
   * Percentage of renter households paying more than 30% of income on
   * gross rent (cost-burdened renters). Range: 0–100.
   * Source: US Census ACS 5-year estimates.
   */
  rent_burden_pct: number | null;

  /**
   * Annual residential building permits issued per 1,000 residents,
   * averaged over the most recent available multi-year period.
   * Source: Census Building Permits Survey.
   */
  permits_per_1000_residents: number | null;
}

export interface TownRecord {
  /** 5-digit MA FIPS code (e.g., "25001" for Barnstable County). Unique identifier. */
  fips: string;

  /** Municipality name as it appears in Census data (e.g., "Brookline"). */
  name: string;

  /** County name (e.g., "Norfolk"). */
  county: string;

  /** Total population from most recent Census ACS 5-year estimate. */
  population: number | null;

  /** Letter grades for each grading dimension. */
  grades: Grades;

  /** Raw numeric metrics underlying the grades. */
  metrics: Metrics;

  /**
   * MBTA Communities Act compliance status:
   *   "compliant"     — municipality has adopted a compliant zoning district
   *   "non-compliant" — municipality is subject to the Act and has not complied
   *   "exempt"        — municipality is not subject to the Act
   *   null            — status not yet determined
   */
  mbta_status: MbtaStatus;

  /** ISO 8601 date string of when this record was last updated by the pipeline (e.g., "2025-03-13"). */
  updated_at: string;
}
