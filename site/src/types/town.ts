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
  /** State legislator housing vote record (House + Senate combined) */
  legislators: Grade;
  /** Weighted composite of all applicable dimensions */
  composite: Grade;
}

export interface RepRecord {
  /** Full name of the representative. */
  name: string | null;
  /** House district name (e.g. "3rd Berkshire"). */
  district: string;
  /** Percentage of pro-housing points earned (0-100). */
  pct_score: number | null;
  /** Letter grade derived from pct_score. */
  grade: Grade;
  /** Number of bills for which rep cast a scoreable vote. */
  bills_scored: number | null;
  /** Total bills eligible for this rep given their term. */
  bills_available: number | null;
  /** Session strings rep was scored in, e.g. ["193", "194"]. */
  sessions_scored: string[] | null;
}

export interface SenRecord {
  /** Full name of the senator. */
  name: string | null;
  /** Senate district name (e.g. "Cape and Islands"). */
  district: string;
  /** Percentage of pro-housing points earned (0-100). */
  pct_score: number | null;
  /** Letter grade derived from pct_score. */
  grade: Grade;
  /** Number of bills for which senator cast a scoreable vote. */
  bills_scored: number | null;
  /** Total bills eligible for this senator given their term. */
  bills_available: number | null;
  /** Session strings senator was scored in, e.g. ["193", "194"]. */
  sessions_scored: string[] | null;
}

export interface Metrics {
  /**
   * Area-weighted share of residential zoned land where 3+ family housing is
   * permitted by right. Range: 0–100.
   * Source: MA Zoning Atlas (NZA) 2023, with Census BPS permit proxy fallback.
   */
  pct_land_multifamily_byright: number | null;

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

  /**
   * Percentage of occupied housing units that are renter-occupied.
   * Range: 0–100.
   * Source: US Census ACS 5-year estimates (B25003).
   */
  renter_share_pct: number | null;

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
   * Data source used for the zoning grade:
   *   "nza"   — graded from MA Zoning Atlas 2023 district data
   *   "proxy" — graded from Census BPS permit mix proxy (town not yet in NZA)
   *   null    — no zoning grade available
   */
  zoning_source: 'nza' | 'proxy' | null;

  /**
   * Whether any residential zoning district in the town permits 4+ unit housing by right.
   *   true  — at least one NZA district has family4_treatment == "allowed"
   *   false — all residential districts cap at 3-family or less (grade capped at B)
   *   null  — unknown; town is graded from permit proxy, no district-level data
   */
  has_f4_allowed: boolean | null;

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

  /**
   * List of House representative score records for this municipality.
   * One entry per district overlapping this town. null if no reps matched.
   * Most towns have one entry. Cities like Boston have ~16.
   */
  reps: RepRecord[] | null;

  /**
   * List of Senate senator score records for this municipality.
   * One entry per Senate district overlapping this town. null if no senators matched.
   * Most towns have one senator. Cities like Boston have 6.
   */
  sens: SenRecord[] | null;

  /** ISO 8601 date string of when this record was last updated by the pipeline (e.g., "2025-03-13"). */
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Metrics metadata — mirrors pipeline/metrics.py and data/metrics.json
// ---------------------------------------------------------------------------

export type MetricUnit = "percent" | "dollars" | "rate" | "status" | "count" | "text";

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
  /** When false, the metric is hidden from the raw metrics display on town pages. Defaults to true. */
  display?: boolean;
}

/** All metric metadata keyed by metric field name. Matches the keys of Metrics. */
export type MetricsMeta = Record<string, MetricMeta>;
