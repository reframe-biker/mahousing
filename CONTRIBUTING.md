# Contributing to MA Housing Report Card

## Metric labels and descriptions

All metric field names, display labels, descriptions, units, and source
attributions are defined in **`pipeline/metrics.py`**. This is the single
source of truth. Never hardcode metric labels or descriptions in site
components.

If you add or rename a metric:

1. Update `pipeline/metrics.py`
2. Update `pipeline/schema.py` (Python TypedDict) and `site/src/types/town.ts` (TypeScript interface) to match
3. Run `python pipeline/build.py` from the repo root — this exports `data/metrics.json` and runs a validation step that warns if `metrics.py` and the data are out of sync
4. Run `npm run build` in `site/` to verify the site reflects the change

The pipeline will print a warning if `metrics.py` and the town data schema are
out of sync. Resolve any warnings before merging.

---

## Data pipeline

The pipeline lives in `pipeline/`. Entry point is `pipeline/build.py`.

```
python pipeline/build.py
```

Requires a Census API key. Copy `.env.example` to `.env` and set
`CENSUS_API_KEY`. Get a free key at https://api.census.gov/data/key_signup.html

Outputs:
- `data/towns/{fips}.json` — one record per municipality
- `data/statewide.json` — all records sorted by name
- `data/metrics.json` — metric metadata (auto-generated from `pipeline/metrics.py`)

---

## Large source data files

Some pipeline source files exceed GitHub's 100MB file size limit and are excluded from the repository via `.gitignore`. These files must be stored locally and are not committed.

| File | Location | Size | How to obtain |
|------|----------|------|---------------|
| `MA_Zoning_Atlas_2023.geojson` | `data/MA_Zoning_Atlas_2023.geojson` | ~606 MB | Contact zoningatlas.org for bulk MA data export |

The pipeline reads these files from the `data/` directory at runtime. If you are setting up the project on a new machine, you will need to obtain these files separately and place them in `data/` before running the pipeline.

**Do not attempt to commit these files.** `git add -A` or `git add data/` will stage them and the push will be rejected by GitHub. They are listed in `.gitignore` to prevent this, but if you add a new large source file, add it to `.gitignore` before staging.

---

## Site

The site is a Next.js 14 app in `site/`.

```
cd site
npm install
npm run dev     # local dev
npm run build   # production build (required before deploying)
```

The site reads from `data/` at build time via `fs.readFileSync`. Run the
pipeline before `npm run build` to ensure the site reflects the latest data.
