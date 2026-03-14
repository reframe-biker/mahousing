# Methodology — MA Housing Report Card

## Purpose

The MA Housing Report Card grades every municipality in Massachusetts on its housing policy record. The project's aim is to make the relationship between local land-use decisions and regional housing outcomes legible to journalists, advocates, and the officials who make those decisions.

Grades are derived entirely from public data. No subjective assessments are made by the project team. The data makes the argument.

---

## Grading Dimensions

Each municipality receives a letter grade (A–F) on six dimensions, plus a composite grade. A null grade ("N/A") means data has not yet been collected for that municipality — it is **not** equivalent to an F. All scoring formulas will be documented in full in this file before any grades are published.

### 1. Zoning Permissiveness

**Data source (current):** [US Census Bureau Building Permits Survey](https://www.census.gov/construction/bps/), 3-year aggregate.

**What the grade measures:** The share of permitted housing units that were in structures of 5 or more units, averaged over the most recent 3 years of available data. This is a revealed-preference measure of zoning permissiveness — a town that issues 80% of its permitted units as multifamily is functionally more permissive than one issuing 95% single-family permits, regardless of what the zoning code says on paper.

**Key metric:** `pct_multifamily_by_right` — in the current implementation, this field holds the share of permitted units in 5+ unit structures (not a literal by-right land-area share). The column name is stable for schema compatibility.

**Coverage:** Towns with fewer than 10 total permitted units over 3 years receive a null grade rather than a potentially misleading grade from a thin sample. Coverage is approximately 320–346 of 351 municipalities depending on the year range.

**Scoring formula:**

| Grade | Threshold |
|-------|-----------|
| A | > 40% of permitted units are in 5+ unit structures |
| B | 25–40% |
| C | 10–25% |
| D | 2–10% |
| F | < 2% |
| N/A | Fewer than 10 total permits over 3 years |

---

### Zoning metric — current approach and roadmap

The zoning grade currently uses permit mix as a revealed-preference proxy. This is an interim approach with two known limitations:

1. **It measures output, not policy.** A town with exclusionary zoning but high permit volume from grandfathered or special-permit development will be graded more favorably than its code warrants. This is a known bias.

2. **It overlaps with the Housing Production grade.** Both grades draw on BPS permit data, though through different lenses (production = total rate; zoning = multifamily share). Towns with low permit volume may receive null grades on both dimensions.

**Why this approach?** The MAPC Zoning Atlas v01 covers approximately 101 cities and towns in Metropolitan Boston. The [National Zoning Atlas](https://zoningatlas.org) (NZA) provides full statewide coverage with explicit by-right multifamily fields, but bulk download access for Massachusetts data is not yet publicly available.

**Upgrade path:** When NZA bulk data is available, set `ZONING_SOURCE = "nza"` in `pipeline/ingest/zoning.py` and implement `pipeline/ingest/zoning_nza.py`. No other files need to change. The output contract (columns `fips`, `pct_multifamily_by_right`, `low_sample`) is documented at the top of `pipeline/ingest/zoning.py`.

---

### 2. MBTA Compliance

**Data source:** MA Executive Office of Housing and Livable Communities (EOHLC) via the DHCD compliance status page.

**Source URL:** [https://www.mass.gov/info-details/multi-family-zoning-requirement-for-mbta-communities](https://www.mass.gov/info-details/multi-family-zoning-requirement-for-mbta-communities)

**Update frequency:** Weekly, via the GitHub Actions pipeline. On each run, the pipeline fetches the live EOHLC compliance page and writes updated status to each town's JSON record. If the live page is unavailable (e.g., during local development where Cloudflare may block automated requests), the pipeline falls back to `data/mbta_status_override.csv`.

**Fallback:** `data/mbta_status_override.csv` — a manually maintained CSV used when the live page cannot be reached. This file should be updated from the EOHLC page whenever the live scrape is blocked for an extended period.

**Current status as of January 2026:** 133 municipalities compliant, 7 conditional compliance, 12 non-compliant (Attorney General Campbell filed suit against non-compliant towns on January 29, 2026), remainder pending review or not yet subject.

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

**Concrete example:** Dover, MA issued 0 multifamily permits in 2021, 0 in 2022, and 34 in 2023 (a single large project). This gives Dover an A zoning grade based on 79% multifamily share — a grade that would surprise anyone familiar with Dover's exclusionary zoning history. The grade reflects what Dover actually permitted, but the note signals that this single year is driving the result.

**Where it appears:** The note is displayed on the town's profile page in an amber info box below the zoning grade card. It is also present in the town's JSON record at `data_notes.zoning`.

**Thresholds summary:** Single year share > 70% of 3-year total AND 3-year total < 50 permits AND population < 15,000.

---

## Null Grades

A null grade ("N/A") means that the data required to compute that grade has not yet been collected for that municipality. It is **not** a score of zero and should not be interpreted as a failing grade. Municipalities with N/A grades in a given dimension are excluded from rankings for that dimension.

---

## Methodology Feedback

Questions about methodology, corrections to underlying data, and suggestions for additional data sources are welcome. Please [open a GitHub issue](https://github.com/reframe-biker/mahousing/issues) with the label `methodology`.

Before any grades are published, the specific scoring formulas (cutoffs, weights, and benchmark values) will be posted for public comment.
