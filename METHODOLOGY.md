# Methodology — MA Housing Report Card

## Purpose

The MA Housing Report Card grades every municipality in Massachusetts on its housing policy record. The project's aim is to make the relationship between local land-use decisions and regional housing outcomes legible to journalists, advocates, and the officials who make those decisions.

Grades are derived entirely from public data. No subjective assessments are made by the project team. The data makes the argument.

---

## Grading Dimensions

Each municipality receives a letter grade (A–F) on six dimensions, plus a composite grade. A null grade ("N/A") means data has not yet been collected for that municipality — it is **not** equivalent to an F. All scoring formulas will be documented in full in this file before any grades are published.

### 1. Zoning Permissiveness

**Data source:** [MA Zoning Atlas 2023](https://zoningatlas.org), a district-level dataset of 2,291 zoning districts across Massachusetts. For the 107 municipalities not yet covered by the Zoning Atlas, the permit mix proxy is used as a fallback (see below).

**What the grade measures:** The share of a municipality's residential zoned land area where 3-family or larger multifamily housing is permitted by right — without requiring a planning board hearing or special permit.

**Key metric:** `pct_land_multifamily_byright` — the area-weighted percentage of residential zoned land in the municipality where `family3_treatment` or `family4_treatment` equals `"allowed"` in the NZA district data.

**Coverage:** 244 of 351 municipalities are graded from NZA district data. The remaining 107 municipalities are graded using the permit mix proxy: share of permitted units in 5+ unit structures, averaged over 3 years of Census Building Permits Survey data. Towns with fewer than 10 total permits over 3 years receive a null grade.

**On hearing credit:** A zoning district that requires a special permit (planning board hearing) for multifamily housing receives no credit in this metric. The hearing process is a primary mechanism by which local officials delay or deny housing — we do not treat discretionary approval as equivalent to by-right permission.

**On rural and low-demand towns:** Zoning permissiveness is measured as a policy fact, not a demand signal. A town with low housing pressure may score F on zoning and face limited political consequence for it. The grades are most actionable for the 177 municipalities subject to the MBTA Communities Act, where an F reflects both a policy choice and a legal obligation. Non-MBTA towns are graded on the same scale for completeness and comparability, but their grades should be read in that context.

**Scoring formula:**

| Grade | Threshold |
|-------|-----------|
| A | > 25% of residential land allows multifamily by right |
| B | 10–25% |
| C | 3–10% |
| D | 0.5–3% |
| F | < 0.5% |
| N/A | No residential zoning data available |

---

### Zoning metric — permit mix fallback

For the 107 municipalities not covered by the MA Zoning Atlas 2023, the zoning grade falls back to a permit mix proxy: the share of permitted housing units in structures of 5 or more units, averaged over the most recent 3 years of Census Building Permits Survey data.

This proxy measures output rather than policy — it reflects what developers built, not what the zoning code allows. Two known limitations apply to towns graded this way:

1. **It measures output, not policy.** A town with exclusionary zoning but permit volume from grandfathered or special-permit development will be graded more favorably than its code warrants.

2. **It overlaps with the Housing Production grade.** Both draw on BPS permit data. Towns with low permit volume may receive null grades on both dimensions.

As the National Zoning Atlas expands its Massachusetts coverage, these towns will be migrated to NZA-based grades automatically. To switch a town from proxy to NZA data, no code changes are required — the pipeline detects NZA coverage per municipality on each run.

---

### 2. MBTA Compliance

**Data source:** EOHLC "Compliance Status Sheet" CSV, downloaded from the EOHLC compliance tracking page.

**Current file:** `data/mbta_compliance_source.csv`, as of March 13, 2026.

**Source URL:** [https://www.mass.gov/info-details/multi-family-zoning-requirement-for-mbta-communities](https://www.mass.gov/info-details/multi-family-zoning-requirement-for-mbta-communities)

**Update process:** When EOHLC publishes a new compliance status CSV, replace `data/mbta_compliance_source.csv` and commit. The pipeline will automatically use the new data on the next run. No code changes are required.

**Current status as of March 13, 2026:** 144 compliant, 15 interim compliance, 7 conditional compliance, 11 non-compliant. Total: 177 subject municipalities. Attorney General Campbell filed suit against non-compliant towns on January 29, 2026.

**What the grade measures:** Whether a municipality subject to the MBTA Communities Act (M.G.L. c. 40A, § 3A) has adopted a compliant zoning district. The Act requires 177 communities to zone for multifamily housing by right near MBTA stations. Municipalities that are not subject to the Act are marked "exempt" and excluded from this grade dimension — they are not penalized.

**Key field:** `mbta_status` — one of `compliant`, `interim`, `non-compliant`, `pending`, or `exempt`.

**Scoring formula:**

| Grade | Status |
|-------|--------|
| A | `compliant` — municipality has adopted a compliant zoning district |
| B | `interim` — municipality has adopted an interim action plan |
| C | `pending` — municipality has submitted a plan under review |
| F | `non-compliant` — municipality has missed deadlines; may lose state grant funding |
| N/A | `exempt` — municipality is not subject to the Act (excluded from composite) |
| N/A | `null` — status not yet determined |

Exempt municipalities receive a null MBTA grade and are excluded from the composite calculation. They are not penalized for being outside the Act's scope.

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

## Data notes and quality flags

The pipeline automatically detects conditions that may reduce the reliability of a grade and attaches a plain-language note to the affected town record. Notes are additive transparency flags — the underlying grade is not changed or suppressed.

### Single-year permit spike (zoning grade)

**What it detects:** The pipeline flags the zoning grade with a note when all three of the following conditions hold:

1. A single calendar year accounts for more than 70% of the municipality's total permit activity over the 3-year window.
2. The 3-year total is fewer than 50 permits.
3. The municipality's population is under 15,000.

**Why this matters:** The zoning grade is based on the share of permitted units in 5+ unit structures. In towns with low overall permit volume, one large development (an assisted-living facility, an age-restricted apartment complex) can dominate the 3-year total and produce a grade that doesn't reflect the town's typical permitting behavior. The grade is based on real data — it is not wrong — but readers deserve to know the context.

**Why the population threshold exists:** For larger cities and towns, a low permit count is not a data quality concern — it is a genuine policy finding. A city of 20,000 or 40,000 people issuing few permits and little multifamily housing is behaving as its zoning code requires; flagging that as anomalous would obscure rather than clarify. The 15,000-resident threshold ensures the spike flag applies only to small towns where one atypical project can meaningfully distort a multi-year average.

**What the note says:** "Zoning grade driven primarily by a single year of permit activity — may not reflect the town's typical permitting pattern."

**Concrete example:** Dover, MA issued 0 multifamily permits in 2021, 0 in 2022, and 34 in 2023 (a single large project). Under the former permit mix proxy, this gave Dover an A zoning grade — a grade that would surprise anyone familiar with Dover's exclusionary zoning history. Dover is now graded from NZA district data (0.0% by-right multifamily land, grade F), which correctly reflects its zoning code. The spike flag remains active for the 107 towns still graded by the permit proxy.

**Where it appears:** The note is displayed on the town's profile page in an amber info box below the zoning grade card. It is also present in the town's JSON record at `data_notes.zoning`.

**Thresholds summary:** Single year share > 70% of 3-year total AND 3-year total < 50 permits AND population < 15,000.

---

## Null Grades

A null grade ("N/A") means that the data required to compute that grade has not yet been collected for that municipality. It is **not** a score of zero and should not be interpreted as a failing grade. Municipalities with N/A grades in a given dimension are excluded from rankings for that dimension.

---

## Methodology Feedback

Questions about methodology, corrections to underlying data, and suggestions for additional data sources are welcome. Please [open a GitHub issue](https://github.com/reframe-biker/mahousing/issues) with the label `methodology`.

Before any grades are published, the specific scoring formulas (cutoffs, weights, and benchmark values) will be posted for public comment.
