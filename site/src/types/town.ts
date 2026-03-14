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
export type MbtaStatus =
  | "compliant"
  | "interim"
  | "non-compliant"
  | "pending"
  | "exempt"
  | null;

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
   * Share of permitted housing units that are multifamily (5+ units),
   * averaged over the most recent 3 years of Census BPS data.
   * Used as a revealed-preference proxy for zoning permissiveness. Range: 0–100.
   * Source: U.S. Census Building Permits Survey.
   */
  pct_multifamily_permitted: number | null;

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

/**
 * Data quality notes for individual grading dimensions.
 *
 * A non-null note means the pipeline detected a condition worth surfacing
 * to the reader. The grade itself is NOT changed — these are transparency
 * flags only. Display them near the relevant grade card.
 */
export interface DataNotes {
  /**
   * Set when a single calendar year drives more than 70% of a small town's
   * 3-year permit total (single-year spike detection).
   */
  zoning: string | null;
  /** Reserved for future production quality flags. Always null for now. */
  production: string | null;
  /** Reserved for future affordability quality flags. Always null for now. */
  affordability: string | null;
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
   * Data quality notes attached to specific grading dimensions.
   * Null if the record predates this field (older pipeline output).
   * Use optional chaining: town.data_notes?.zoning
   */
  data_notes: DataNotes | null;

  /**
   * MBTA Communities Act compliance status:
   *   "compliant"     — municipality has adopted a compliant zoning district
   *   "interim"       — municipality has adopted an interim action plan
   *   "non-compliant" — municipality is subject to the Act and has not complied
   *   "pending"       — municipality has submitted a plan under review
   *   "exempt"        — municipality is not subject to the Act
   *   null            — status not yet determined
   */
  mbta_status: MbtaStatus;

  /**
   * Deadline date for MBTA Communities Act compliance (ISO date string YYYY-MM-DD),
   * or null if not subject to the Act or no deadline published.
   */
  mbta_deadline: string | null;

  /**
   * Date of the municipality's most recent action toward compliance
   * (ISO date string YYYY-MM-DD), or null if no action taken or not applicable.
   */
  mbta_action_date: string | null;

  /** ISO 8601 date string of when this record was last updated by the pipeline (e.g., "2025-03-13"). */
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Metrics metadata — mirrors pipeline/metrics.py and data/metrics.json
// ---------------------------------------------------------------------------

export type MetricUnit = "percent" | "dollars" | "rate" | "status";

/**
 * Display metadata for a single metric field.
 * Sourced from data/metrics.json (generated by the pipeline from pipeline/metrics.py).
 * Never hardcode these in site components — always read from metrics.json at build time.
 */
export interface MetricMeta {
  label: string;
  description: string;
  source: string;
  unit: MetricUnit;
  higher_is_better: boolean;
}

/** All metric metadata keyed by metric field name. Matches the keys of Metrics. */
export type MetricsMeta = Record<string, MetricMeta>;
