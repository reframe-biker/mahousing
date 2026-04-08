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

**Key metric:** `pct_land_multifamily_byright` — the area-weighted percentage of residential zoned land in the municipality scored as follows per NZA district:
- `family4_treatment == "allowed"` → full credit (1.0) — district permits 4+ unit multifamily by right
- `family3_treatment == "allowed"` and f4 is not allowed → half credit (0.5) — district permits only 3-family by right
- `"hearing"` on either field → no credit (0.0) — discretionary approval is not by-right permission
- all other values → no credit (0.0)

Districts are area-weighted within each municipality to produce the final percentage.

**Coverage:** 244 of 351 municipalities are graded from NZA district data. The remaining 107 municipalities are graded using the permit mix proxy: share of permitted units in 5+ unit structures, averaged over 3 years of Census Building Permits Survey data. Towns with fewer than 10 total permits over 3 years receive a null grade.

**On hearing credit:** A zoning district that requires a special permit (planning board hearing) for multifamily housing receives no credit in this metric. The hearing process is a primary mechanism by which local officials delay or deny housing — we do not treat discretionary approval as equivalent to by-right permission.

**On rural and low-demand towns:** Zoning permissiveness is measured as a policy fact, not a demand signal. A town with low housing pressure may score F on zoning and face limited political consequence for it. The grades are most actionable for the 177 municipalities subject to the MBTA Communities Act, where an F reflects both a policy choice and a legal obligation. Non-MBTA towns are graded on the same scale for completeness and comparability, but their grades should be read in that context.

**On known NZA coding errors:** The pipeline maintains a file (`data/zoning_nza_known_errors.json`) of municipalities where the NZA 2023 district data has been confirmed as miscoded through manual bylaw review. Confirmed towns receive a null zoning grade rather than a misleading score. As of the current dataset, two towns are flagged: Rochester (Agricultural-Residential district coded as allowing multifamily by right; the bylaw's permitted uses list contains only single-family dwellings) and Ayer (A1 and A2 residential districts coded as allowing multifamily by right; the use table shows Special Permit from Planning Board required). These entries are keyed to the 2023 dataset filename and will be automatically disregarded when an updated NZA dataset is used.

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

**Data sources:** [US Census American Community Survey (ACS)](https://www.census.gov/programs-surveys/acs) 5-year estimates — tables B25070 (rent burden), B25077 (median home value), B25003 (housing tenure/renter share).

**What the grade measures:** The degree to which housing in the municipality is accessible at median regional incomes. The grade is a renter-share-weighted composite of rent burden and median home value — capturing both active cost burden on existing renters and passive exclusion via high prices.

**Key metrics:** `rent_burden_pct`, `median_home_value`, `renter_share_pct`.

**Scoring formula:**

The affordability grade is a renter-share-weighted composite of two metrics: rent burden and median home value. This approach captures both active cost burden (renters paying too much) and passive exclusion (prices so high that lower-income households cannot enter the town at all).

**Step 1 — Grade each component:**

Rent burden (share of renters paying >30% of gross income on rent):

| Grade | Threshold |
|---|---|
| A | < 20% of renters cost-burdened |
| B | 20–30% |
| C | 30–40% |
| D | 40–50% |
| F | > 50% |

Median home value:

| Grade | Threshold |
|---|---|
| A | < $400,000 |
| B | $400,000 – $600,000 |
| C | $600,000 – $800,000 |
| D | $800,000 – $1,200,000 |
| F | > $1,200,000 |

Home value thresholds are calibrated to the Massachusetts distribution (2023 ACS): state median $564k, 25th percentile $421k, 75th percentile $757k, 90th percentile $1.03M.

**Step 2 — Weight by renter share:**

The two component grades are converted to a 0–4 numeric scale (A=4, B=3, C=2, D=1, F=0), then combined using the municipality's renter share as a weight:

```
weight_rent = renter_share_pct / 100
weight_home = 1 − weight_rent
composite = (weight_rent × rent_burden_score) + (weight_home × home_value_score)
```

The composite numeric score is converted back to a letter grade (≥3.5→A, ≥2.5→B, ≥1.5→C, ≥0.5→D, <0.5→F).

If renter share data is unavailable, equal weights (0.5/0.5) are used as a fallback.

**Why this matters:** Towns with very low renter shares (under 5–10%) often have rent burden numbers based on small samples of wealthy renters, producing misleadingly high affordability grades. Dover, for example, has a 3% renter share and a median home value over $1.7M — its grade correctly reflects its exclusionary price level rather than the experience of its handful of renters.

---

### 5. Town Meeting Voting Record

**Data source:** Municipal records, warrant articles, and vote tallies compiled from town meeting minutes and published town reports. This data will be collected manually or via partnership with advocacy organizations for Phase 2.

**What the grade measures:** How a municipality's town meeting (or city council) has voted on housing-related articles — zoning amendments, accessory dwelling unit bylaws, inclusionary zoning, and similar measures — over a rolling multi-year window.

**Key metric:** Vote outcomes on housing-related articles; will be scored on a pass/fail basis per article with weighting for article significance.

**Scoring formula:** TBD. Will be documented here before publication.

**Current status:** Data collection methodology not yet finalized. This dimension will show N/A for all municipalities until Phase 2.

---

### 6. State Legislator Record (Phase 4a House + Phase 4d Senate)

**Scope:** Both chambers are scored. House representatives are scored from combined annual roll call PDFs. Senate senators are scored from LegiScan API roll call data. The town-level `legislators` grade is the lower-median across all House representatives and Senate senators whose districts overlap the municipality.

#### 6a. MA House (Phase 4a)

**Data sources:** MA Legislature combined annual roll call PDFs (auto-downloaded); MA Legislature CoSponsor AJAX API (fetched live each build); Open States MA legislator CSV (manual update each new General Court); Census TIGER SLDL 2024 shapefile (manual update ~every 10 years).

**What the grade measures:** The housing production voting record of each state House representative whose district overlaps the municipality, scored across a curated set of roll call votes and co-sponsorship opportunities. Municipalities with a single House district display one representative. Cities that span multiple districts (Boston: 16, Springfield: 5, Worcester: 5) display all representatives individually. The town-level rep grade is the median grade across all representatives — a town is not penalized for having one poor-scoring rep among many strong ones, nor rewarded for one strong rep among many poor ones. The bill list (`data/legislator_bill_list.json`) is an editorial curation of the most significant housing production votes. New votes are never added automatically — every addition is a manual editorial decision.

**Geographic assignment:** Each municipality is assigned to one or more House districts via an area-based spatial intersection between MA county subdivision boundaries (Census TIGER COUSUB 2024) and House district polygons (Census TIGER SLDL 2024). The intersection uses a tiered overlap threshold: same-county district assignments require at least 1% area overlap (preserving multi-district cities like Boston); cross-county district assignments require at least 15% area overlap (filtering boundary artifacts while preserving genuine cross-county districts like Bolton, a Worcester County town entirely within the 3rd Middlesex district). The mapping is cached at `data/town_district_map.json` and rebuilt only when deleted (next redistricting ~2031). Boston has 16 House districts; 79 of MA's 351 municipalities span more than one district.

**Scoring formula:**

For each scored action:
- `type=rollcall, pro_housing_vote="yea"`: rep earns points if they voted Y
- `type=rollcall, pro_housing_vote="nay"`: rep earns points if they voted N (defeating an anti-housing amendment)
- `type=cosponsor`: rep earns points if their full name appears in the bill's cosponsor list

```
pct_score = earned_points / max_points × 100
```

<!-- LEGISLATOR_BILL_LIST_START -->
<!-- auto-generated by pipeline/build.py on each run — do not edit manually -->
Current scored actions (9 roll call votes and 2 co-sponsorship checks, max 21 points):

| Action | Type | Session | Description | Pro-housing vote | Weight | Rationale |
|--------|------|---------|-------------|-----------------|--------|-----------|
| RC#117 | Roll call | 193rd (2024) | H4707 final passage — Affordable Homes Act, 145-13 | YEA | 3 | Most important single vote. Final passage of the Affordable Homes Act. |
| RC#199 | Roll call | 193rd (2024) | H4977 conference report — enacted version of Affordable Homes Act, 128-24 | YEA | 3 | The actual law. Conference committee report accepted before sending to governor. |
| RC#110 | Roll call | 193rd (2024) | Amendment 29 — Lombardo: exempt 40B-compliant towns from MBTA Communities Act, defeated 27-131 | NAY | 2 | Anti-housing weakening attempt targeting MBTA Communities enforcement. NAY = pro-housing. |
| RC#111 | Roll call | 193rd (2024) | Amendment 129 — Jones (Minority Leader): make MBTA Communities evasion easier, defeated 32-126 | NAY | 2 | Anti-housing weakening attempt from Minority Leader. NAY = pro-housing. |
| RC#113 | Roll call | 193rd (2024) | Consolidated A — preserve ADU by-right language, passed 130-28 | YEA | 2 | ADU by-right is core housing production. YEA = pro-housing. |
| RC#114 | Roll call | 193rd (2024) | Amendment 348 — Frost: count mobile homes toward 40B threshold, defeated 30-127 | NAY | 1 | NIMBY tactic to inflate 40B numbers and resist new development. NAY = pro-housing. |
| H1379 | Co-sponsorship check | 193rd | YIMBY Act (193rd) — An Act to promote Yes in My Backyard, 33 cosponsors | Co-sponsor | 1 | Proactive co-sponsorship of comprehensive zoning reform bill. |
| RC#35 | Roll call | 194th (2025) | Amendment #1643 — repeal Chapter 40B affordable housing law, defeated 26-130 | NAY | 2 | Chapter 40B is the Commonwealth's primary affordable housing production tool. Repeal attempt defeated. NAY = pro-housing. |
| RC#38 | Roll call | 194th (2025) | Amendment #606 — limit grant funding to encourage MBTA Communities compliance, defeated 28-128 | NAY | 2 | Would have let non-compliant towns avoid funding consequences. NAY = pro-housing. |
| RC#39 | Roll call | 194th (2025) | Amendment #311 — eliminate AG enforcement of MBTA Communities Act, defeated 30-126 | NAY | 2 | Would have stripped the Attorney General's authority to enforce MBTA Communities zoning law. NAY = pro-housing. |
| H1572 | Co-sponsorship check | 194th | YIMBY Act (194th) — current session, ~20 cosponsors as of March 2026 | Co-sponsor | 1 | Live political signal. Co-sponsoring the active YIMBY bill right now. |
<!-- LEGISLATOR_BILL_LIST_END -->

**Grading rubric:**

| Grade | Threshold | Interpretation |
|-------|-----------|----------------|
| A | ≥ 80% | Strongly pro-housing |
| B | 60–79% | Generally pro-housing |
| C | 40–59% | Mixed record |
| D | 20–39% | Generally anti-housing |
| F | < 20% | Voted anti-housing on nearly all scored bills |
| N/A | null | Rep not present for any scored vote |

**Null vs. F:** `null` and `F` mean different things. `null` means the representative was not present for any scored vote — either a vacant seat, an unmatched district, or a representative whose name could not be matched in the roll call PDFs. This is **not** an F grade. An F means the representative was present and voted anti-housing across all scored bills.

Representatives are scored only on votes that occurred during their term in office. A representative elected in November 2024 who took office January 1, 2025 is not penalized for 193rd session votes cast by their predecessor — they are scored only on 194th General Court actions. Each representative's percentage is calculated against their own available total, so scores are comparable across reps with different tenure.

**Explicitly excluded votes:**

- **RC#115 (Consolidated B / TOPA):** Tenant Opportunity to Purchase Act provisions. This is a tenant protection policy, not a housing production measure. Candidate for a future "stability" scoring axis.
- **RC#112 (veterans housing preference):** Passed 158–0 (unanimous). Zero signal — excludes no one from a pro-housing or anti-housing grouping.
- **RC#116 (Consolidated C, earmarks):** Near-unanimous, low signal.
- **RC#43–57 (2023 supplemental budget housing line items):** Appropriations axis, not housing production policy.
- **2023 roll calls generally:** All 70 roll calls from the 193rd session 2023 were reviewed. No housing production votes were found.

**Data sources:**

| Source | What it provides | Auth required | Update cadence |
|--------|-----------------|---------------|----------------|
| malegislature.gov Journal PDFs | Roll call votes | None (verify=False) | Auto-downloaded by pipeline |
| malegislature.gov CoSponsor API | Cosponsor lists | One header (`X-Requested-With`) | Fetched live each build |
| Open States ma.csv | Legislator names, districts | Browser download | Manual, each new General Court |
| Census TIGER SLDL 2024 | House district boundaries | None | Manual, ~every 10 years |

**Known data gaps:**

- **1st Franklin and 5th Essex districts:** Two TIGER districts have no matching Open States district. Towns in these districts receive null grades — this is expected and not a pipeline error.
- **Open States CSV had 158/160 seats filled** at time of download (2 vacancies). The 2 vacant-seat towns receive null grades. This is correct — vacant seats have no scoring record.
- **193rd session reps who lost seats:** Some representative last names in 193rd roll call PDFs do not appear in the current (194th session) CSV. These names are logged at INFO level and not scored — they held seats in 2023–2024 but not in the current legislature.

**New vote detection:** On each build run, `new_vote_notifier.py` checks the current session journal directory for new combined PDF URLs and alerts if any are found. A new PDF alert does **not** trigger automatic scoring — it is an editorial notice to review the journal and determine whether any votes merit inclusion in the bill list.

---

#### 6b. MA Senate (Phase 4d)

**Data source:** [LegiScan API](https://legiscan.com/legiscan) — `getRollCall` and `getPerson` endpoints. Responses are cached locally in `data/rollcall_cache/senate/`. API key required (`LEGISCAN_API_KEY` environment variable).

**Geographic assignment:** Each municipality is assigned to one or more Senate districts via area-based spatial intersection between MA county subdivision boundaries (Census TIGER COUSUB 2024) and Senate district polygons (Census TIGER SLDU 2024). Same tiered overlap threshold as House: 1% same-county, 15% cross-county. The mapping is cached at `data/town_senate_district_map.json`. Most municipalities have one Senate district. Cities like Boston have 6.

**Bill list:** `data/senate_bill_list.json` — 2 roll call votes, max 4 points. The MA Senate is a heavily Democratic chamber; the vast majority of housing votes pass unanimously or near-unanimously and provide no signal for distinguishing senators. The 2 scored votes are contested amendments forced to a roll call by the Republican minority and confirmed by CHAPA (Citizens' Housing and Planning Association) as anti-housing:

| Roll call | Bill | Session | Description | Pro-housing vote | Weight |
|-----------|------|---------|-------------|-----------------|--------|
| 1461314 | S2834 Amd 25 | 193rd (2024) | Anti-MBTA Communities amendment — adds unnecessary appeal criteria to MBTA Communities Act | NAY | 2 |
| 1602789 | S3 Amd 13 | 194th (2025) | Anti-MBTA Communities amendment — same amendment pattern, FY2026 budget debate | NAY | 2 |

Both votes are anti-housing amendments: voting **YEA** is anti-housing; voting **NAY** is pro-housing. A senator who voted NAY on both earns 100%.

**Name matching:** Senator names from the Open States CSV (`current_chamber == "upper"`) are matched to LegiScan `people_id` values by exact last name, with fuzzy fallback (token sort ratio ≥ 85). The matched `people_id` is used to look up the senator's vote in each roll call.

**Session boundary logic:** Senators whose `people_id` does not appear in any 193rd session roll call are treated as 2025 entrants and scored only on 194th General Court actions. This prevents newly elected senators from being penalized for votes cast by their predecessors.

**Grading rubric:** Same as House — A ≥ 80%, B 60–79%, C 40–59%, D 20–39%, F < 20%, null = not present for any scored vote.

**Why only 2 votes:** The H4977 final Senate passage (37-2, roll call 1463317) was excluded as too lopsided to differentiate senators. All other housing votes in the 193rd and 194th Senate sessions passed unanimously or near-unanimously. The FY2025 budget (S4) and FY2026 budget (S3) were each reviewed for all contested roll calls; only the MBTA Communities Act amendments met the threshold for inclusion.

---

#### 6c. Town-level legislators grade

The town-level `legislators` grade is derived from **House representatives only**. Senate senators are displayed on the town profile for informational context but do not feed the composite grade.

**Rationale:** House representatives are the most locally accountable legislators — each district covers a single town or a small part of one, and constituents can most directly pressure or replace their House rep. Senate districts span many municipalities (often 10–20 towns), diluting accountability. A senator's vote record reflects regional, not town-level, responsiveness. Using only House reps makes the grade a direct signal about the legislators a town's voters can hold accountable at the ballot box.

The grade takes the **lower median** across all House representatives whose districts overlap the municipality (A=4, B=3, C=2, D=1, F=0). With an even number of reps, the lower of the two middle values is used — a town is not rewarded for one strong rep among many poor ones.

| Reps in district | Lower-median index |
|-----------------|-------------------|
| 1 | 0 (the sole rep) |
| 2 | 0 (lower of the two) |
| 3 | 1 (middle) |
| N | floor((N−1)/2) |

Boston, for example, has 16 House representatives. Its `legislators` grade is the value at sorted index 7.

A town whose House district has no matched representative (vacant seat, or a district with no Open States record such as the 1st Franklin or 5th Essex districts) receives a null legislators grade regardless of its senator's record.

---

## Composite Grade

The composite grade is a weighted average of all applicable dimensions for a given municipality. Dimensions for which a municipality has a null grade are excluded from the composite calculation — they do not count as zeros. For the legislator dimension, the town-level grade used in the composite is the lower-median grade across the municipality's House representatives only (A=4, B=3, C=2, D=1, F=0) — see Section 6c for the formula. The weights assigned to each dimension, and the rationale for those weights, will be documented here before any composite grades are published.

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
