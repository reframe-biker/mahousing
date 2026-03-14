# MA Housing Report Card

A public data project that grades every Massachusetts municipality on its housing policy record. Grades are derived from publicly available data and updated weekly.

The project is designed to be a source of record for journalists, policy advocates, and local officials tracking housing production and zoning compliance across the Commonwealth — with particular focus on MBTA Communities Act implementation.

---

## Who This Is For

**Journalists and policy advocates** are the primary audience. Every grade links directly to its source data, every methodology decision is documented in [METHODOLOGY.md](METHODOLOGY.md), and the underlying JSON is freely accessible for download or API use. The goal is citable, reproducible data.

**Local elected officials** — planning board members, selectmen, city councilors — are a secondary audience. The grading system is designed to make the relationship between local land-use decisions and regional housing outcomes concrete and visible to people who face re-election.

**The general public** can browse grades and share results, but the site is optimized for the workflows of the first two groups.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Data pipeline | Python 3.12 (pandas, geopandas, census) |
| Data format | Static JSON files, committed to `data/` |
| Frontend | Next.js 14 (TypeScript, Tailwind CSS, App Router) |
| Hosting | TBD (Vercel or GitHub Pages) |
| Automation | GitHub Actions (weekly cron) |

The pipeline produces one JSON file per municipality at `data/towns/<fips>.json` and a combined `data/statewide.json`. The Next.js site reads those files at build time — there is no database or server-side API.

---

## Data Sources

| Source | Dimensions Powered |
|--------|-------------------|
| [MA Zoning Atlas](https://www.mapc.org/resource-library/massachusetts-zoning-atlas/) (MAPC) | Zoning Permissiveness |
| [US Census American Community Survey (ACS)](https://www.census.gov/programs-surveys/acs) | Affordability, Population |
| [Zillow Research](https://www.zillow.com/research/data/) | Affordability (home value index) |
| [Census Building Permits Survey](https://www.census.gov/construction/bps/) | Housing Production |

**Planned additions (later phases):**
- MBTA Communities Act compliance data (MA EOHLC / Attorney General)
- State legislator vote records (MA Legislature)
- Town meeting warrant article results

---

## Running the Pipeline Locally

```bash
# 1. Clone the repo
git clone https://github.com/reframe-biker/mahousing.git
cd mahousing

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r pipeline/requirements.txt

# 4. Copy the environment variables file and fill in your keys
cp .env.example .env
# Edit .env and add your CENSUS_API_KEY
# (get one free at https://api.census.gov/data/key_signup.html)

# 5. Run the pipeline (not yet implemented — Phase 1)
# python -m pipeline.build
```

---

## Running the Site Locally

```bash
cd site

# Install dependencies (first time only)
npm install

# Start the development server
npm run dev

# Open http://localhost:3000
```

---

## Project Structure

```
mahousing/
├── pipeline/
│   ├── ingest/         # One module per data source (Phase 1)
│   ├── schema.py       # Canonical data schema (TypedDict)
│   ├── score.py        # Grading engine stub
│   ├── build.py        # Pipeline orchestrator stub
│   └── requirements.txt
├── data/
│   ├── towns/          # Per-municipality JSON (auto-generated)
│   └── statewide.json  # All municipalities combined (auto-generated)
├── site/               # Next.js frontend
├── .github/workflows/  # GitHub Actions automation
├── .env.example
├── METHODOLOGY.md      # Full grading methodology
└── README.md
```

---

## Contributing

Contributions are welcome, particularly:

- **Data corrections:** If a municipality's grade appears to reflect an error in the underlying source data, please open an issue with a link to the authoritative source.
- **Methodology feedback:** See [METHODOLOGY.md](METHODOLOGY.md) for the grading methodology. Open an issue labeled `methodology` to suggest changes.
- **New data sources:** Proposals for additional public data sources that could inform grades, especially for the Town Meeting Voting Record and State Legislator Record dimensions.
- **Frontend improvements:** Bug reports and PRs for the Next.js site.

Please open a [GitHub issue](https://github.com/reframe-biker/mahousing/issues) before opening a pull request for significant changes.

---

## License

Data derived from public sources is subject to the terms of those sources. Project code is MIT licensed. See [LICENSE](LICENSE) for details.
