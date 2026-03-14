# Methodology — MA Housing Report Card

## Purpose

The MA Housing Report Card grades every municipality in Massachusetts on its housing policy record. The project's aim is to make the relationship between local land-use decisions and regional housing outcomes legible to journalists, advocates, and the officials who make those decisions.

Grades are derived entirely from public data. No subjective assessments are made by the project team. The data makes the argument.

---

## Grading Dimensions

Each municipality receives a letter grade (A–F) on six dimensions, plus a composite grade. A null grade ("N/A") means data has not yet been collected for that municipality — it is **not** equivalent to an F. All scoring formulas will be documented in full in this file before any grades are published.

### 1. Zoning Permissiveness

**Data source:** [MA Zoning Atlas](https://www.mapc.org/resource-library/massachusetts-zoning-atlas/) (Metropolitan Area Planning Council)

**What the grade measures:** The share of a municipality's developable land area where multifamily housing is permitted by right — meaning no discretionary special permit, variance, or board approval is required. A higher share of by-right multifamily zoning indicates a more permissive regulatory environment for housing construction.

**Key metric:** `pct_multifamily_by_right` — percentage of land area zoned for multifamily housing by right.

**Scoring formula:** TBD. Will be documented here before publication. The formula will rank all 351 municipalities on this metric and assign grades based on percentile cutoffs.

---

### 2. MBTA Compliance

**Data source:** Massachusetts Executive Office of Housing and Livable Communities (EOHLC) compliance tracking; Attorney General enforcement records.

**What the grade measures:** Whether a municipality subject to the MBTA Communities Act (M.G.L. c. 40A, § 3A) has adopted a compliant zoning district. The Act requires 177 communities to zone for multifamily housing by right near MBTA stations. Municipalities that are not subject to the Act are marked "exempt" and excluded from this grade.

**Key field:** `mbta_status` — one of `compliant`, `non-compliant`, or `exempt`.

**Scoring formula:** TBD. Will be documented here before publication. Because compliance is largely binary (a municipality has either adopted a compliant district or it has not), this grade will reflect both compliance status and the degree of compliance (e.g., whether the adopted district meets minimum density requirements or merely the floor).

---

### 3. Housing Production

**Data source:** [US Census Bureau Building Permits Survey](https://www.census.gov/construction/bps/)

**What the grade measures:** The rate of residential building permits issued relative to the municipality's existing population. This is a proxy for whether a municipality is adding housing at a rate consistent with regional demand. A municipality can have permissive zoning on paper but still produce very little housing; this dimension captures actual output.

**Key metric:** `permits_per_1000_residents` — annual residential permits per 1,000 residents, averaged over the most recent available multi-year period.

**Scoring formula:** TBD. Will be documented here before publication. The formula will adjust for municipality size to avoid penalizing small towns with small absolute permit counts.

---

### 4. Affordability

**Data source:** [US Census American Community Survey (ACS)](https://www.census.gov/programs-surveys/acs) 5-year estimates; [Zillow Research](https://www.zillow.com/research/data/) (median home value index).

**What the grade measures:** The degree to which housing in the municipality is accessible at median regional incomes. Two metrics are combined: the share of renter households that are cost-burdened (paying more than 30% of income on gross rent), and median owner-occupied home value relative to the regional median.

**Key metrics:** `rent_burden_pct`, `median_home_value`.

**Scoring formula:** TBD. Will be documented here before publication. The weighting between renter burden and home value, and the benchmarks used for comparison, will be specified before any grades are published.

---

### 5. Town Meeting Voting Record

**Data source:** Municipal records, warrant articles, and vote tallies compiled from town meeting minutes and published town reports. This data will be collected manually or via partnership with advocacy organizations for Phase 2.

**What the grade measures:** How a municipality's town meeting (or city council) has voted on housing-related articles — zoning amendments, accessory dwelling unit bylaws, inclusionary zoning, and similar measures — over a rolling multi-year window.

**Key metric:** Vote outcomes on housing-related articles; will be scored on a pass/fail basis per article with weighting for article significance.

**Scoring formula:** TBD. Will be documented here before publication.

**Current status:** Data collection methodology not yet finalized. This dimension will show N/A for all municipalities until Phase 2.

---

### 6. State Legislator Record

**Data source:** Massachusetts Legislature roll call votes; bill co-sponsorship records from the MA Legislature website and advocacy organization scorecards (e.g., CHAPA, Abundant Housing MA).

**What the grade measures:** The housing voting record of the state representative(s) and senator(s) who represent each municipality, on bills related to zoning, housing production, and tenant protections heard in the current and prior legislative session.

**Note:** Because multiple legislators may represent portions of a single municipality, the scoring methodology for multi-district municipalities will be documented before this grade is published.

**Scoring formula:** TBD. Will be documented here before publication.

**Current status:** Data collection methodology not yet finalized. This dimension will show N/A for all municipalities until a future phase.

---

## Composite Grade

The composite grade is a weighted average of all applicable dimensions for a given municipality. Dimensions for which a municipality has a null grade are excluded from the composite calculation — they do not count as zeros. The weights assigned to each dimension, and the rationale for those weights, will be documented here before any composite grades are published.

---

## Data Freshness

The pipeline that produces this data runs on a weekly automated schedule via GitHub Actions. Each run fetches the latest available data from each source and updates the JSON files that power the site. The `updated_at` field on each municipality record reflects the date of the most recent pipeline run, not the date the underlying source data was collected. Source data freshness varies by dataset (e.g., Census ACS estimates are updated annually; building permit data is available monthly).

All source data used by this project is publicly available at no cost.

---

## Null Grades

A null grade ("N/A") means that the data required to compute that grade has not yet been collected for that municipality. It is **not** a score of zero and should not be interpreted as a failing grade. Municipalities with N/A grades in a given dimension are excluded from rankings for that dimension.

---

## Methodology Feedback

Questions about methodology, corrections to underlying data, and suggestions for additional data sources are welcome. Please [open a GitHub issue](https://github.com/your-org/mahousing/issues) with the label `methodology`.

Before any grades are published, the specific scoring formulas (cutoffs, weights, and benchmark values) will be posted for public comment.
