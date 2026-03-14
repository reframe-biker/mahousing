import fs from "fs";
import path from "path";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import type { TownRecord, Grade } from "@/src/types/town";
import GradeBadge, { gradeConfig } from "@/app/components/GradeBadge";
import GradeCard from "@/app/components/GradeCard";
import MetricsTable from "@/app/components/MetricsTable";
import ShareButton from "@/app/components/ShareButton";

// ---------------------------------------------------------------------------
// Data helpers
// ---------------------------------------------------------------------------

const DATA_DIR = path.join(process.cwd(), "..", "data");

function loadTown(fips: string): TownRecord | null {
  const filePath = path.join(DATA_DIR, "towns", `${fips}.json`);
  if (!fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, "utf-8")) as TownRecord;
}

function loadStatewide(): TownRecord[] {
  return JSON.parse(
    fs.readFileSync(path.join(DATA_DIR, "statewide.json"), "utf-8")
  ) as TownRecord[];
}

function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}

interface StateMedians {
  median_home_value: number;
  rent_burden_pct: number;
  permits_per_1000_residents: number;
  pct_multifamily_by_right: number;
}

function computeStateMedians(towns: TownRecord[]): StateMedians {
  function getValues(key: keyof typeof towns[0]["metrics"]): number[] {
    return towns
      .map((t) => t.metrics[key])
      .filter((v): v is number => v !== null);
  }
  return {
    median_home_value: median(getValues("median_home_value")),
    rent_burden_pct: median(getValues("rent_burden_pct")),
    permits_per_1000_residents: median(getValues("permits_per_1000_residents")),
    pct_multifamily_by_right: median(getValues("pct_multifamily_by_right")),
  };
}

// ---------------------------------------------------------------------------
// Static generation
// ---------------------------------------------------------------------------

export async function generateStaticParams() {
  const townsDir = path.join(DATA_DIR, "towns");
  const files = fs.readdirSync(townsDir).filter((f) => f.endsWith(".json"));
  return files.map((f) => ({ fips: f.replace(".json", "") }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ fips: string }>;
}): Promise<Metadata> {
  const { fips } = await params;
  const town = loadTown(fips);
  if (!town) return { title: "Town not found — MA Housing Report Card" };
  const grade = town.grades.composite ?? "incomplete";
  return {
    title: `${town.name} — ${grade} — MA Housing Report Card`,
    description: `${town.name}, ${town.county}: composite grade ${grade} on housing policy. Population ${town.population?.toLocaleString()}.`,
  };
}

// ---------------------------------------------------------------------------
// Grade card configurations
// ---------------------------------------------------------------------------

interface GradeCardConfig {
  dimension: string;
  gradeKey: keyof TownRecord["grades"];
  getMetric: (t: TownRecord) => string | null;
  explanation: string;
  phase: string | null;
}

const GRADE_CARD_CONFIGS: GradeCardConfig[] = [
  {
    dimension: "Zoning permissiveness",
    gradeKey: "zoning",
    getMetric: (t) =>
      t.metrics.pct_multifamily_by_right !== null
        ? `${t.metrics.pct_multifamily_by_right.toFixed(1)}% of permitted units are multifamily (5+ units)`
        : null,
    explanation:
      "Share of permitted housing units that are multifamily (5+ units), averaged over the most recent 3 years. Used as a revealed-preference measure of zoning permissiveness — towns that permit more multifamily in practice tend to have more permissive zoning codes. Low-permit towns (fewer than 10 total permits over 3 years) show N/A. This metric will be replaced with National Zoning Atlas data when available.",
    phase: null,
  },
  {
    dimension: "MBTA Communities Act",
    gradeKey: "mbta",
    getMetric: () => null,
    explanation:
      "Compliance with the MBTA Communities Act, which requires 177 municipalities near transit to adopt zoning for multifamily housing. Non-compliance risks state funding eligibility.",
    phase: "Phase 3 — coming soon",
  },
  {
    dimension: "Housing production",
    gradeKey: "production",
    getMetric: (t) =>
      t.metrics.permits_per_1000_residents !== null
        ? `${t.metrics.permits_per_1000_residents.toFixed(2)} permits per 1,000 residents`
        : null,
    explanation:
      "Annual residential building permits per 1,000 residents, averaged over recent years. Measures whether the town is actually building housing relative to its existing population.",
    phase: null,
  },
  {
    dimension: "Affordability",
    gradeKey: "affordability",
    getMetric: (t) =>
      t.metrics.rent_burden_pct !== null
        ? `${t.metrics.rent_burden_pct.toFixed(1)}% of renters cost-burdened`
        : null,
    explanation:
      "Combines the share of renters paying more than 30% of income on rent and the median home value. High cost burden reflects a housing supply shortfall.",
    phase: null,
  },
  {
    dimension: "Town meeting votes",
    gradeKey: "votes",
    getMetric: () => null,
    explanation:
      "Track record of the town meeting or city council voting in favor of pro-housing zoning articles. Measures democratic accountability.",
    phase: "Phase 4 — coming soon",
  },
  {
    dimension: "State legislator record",
    gradeKey: "rep",
    getMetric: () => null,
    explanation:
      "Voting record of the municipality's state legislators on pro-housing bills at the State House.",
    phase: "Phase 4 — coming soon",
  },
];

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function fmtDollars(v: number): string {
  return "$" + Math.round(v).toLocaleString("en-US");
}

function fmtPct(v: number): string {
  return v.toFixed(1) + "%";
}

function fmtRatio(v: number): string {
  return v.toFixed(1) + "x";
}

function buildShareKeyStat(town: TownRecord): string {
  if (town.metrics.permits_per_1000_residents !== null) {
    return `${fmtPct(town.metrics.permits_per_1000_residents)} permits per 1,000 residents.`;
  }
  if (town.metrics.rent_burden_pct !== null) {
    return `${fmtPct(town.metrics.rent_burden_pct)} of renters are cost-burdened.`;
  }
  return `Population: ${town.population?.toLocaleString() ?? "unknown"}.`;
}

function gradeLabel(grade: Grade): string {
  const map: Record<NonNullable<Grade>, string> = {
    A: "Excellent",
    B: "Good",
    C: "Below average",
    D: "Poor",
    F: "Failing",
  };
  if (grade === null) return "Incomplete";
  return map[grade] ?? grade;
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

const SITE_BASE_URL = "https://mahousing.org"; // canonical domain placeholder

export default async function TownPage({
  params,
}: {
  params: Promise<{ fips: string }>;
}) {
  const { fips } = await params;
  const town = loadTown(fips);
  if (!town) notFound();

  const statewide = loadStatewide();
  const medians = computeStateMedians(statewide);

  const compositeGrade = town.grades.composite;
  const config = gradeConfig(compositeGrade);
  const shareUrl = `${SITE_BASE_URL}/town/${fips}`;
  const keyStat = buildShareKeyStat(town);

  // Build context comparisons
  type Comparison = { label: string; text: string };
  const comparisons: Comparison[] = [];

  if (town.metrics.median_home_value !== null && medians.median_home_value > 0) {
    const ratio = town.metrics.median_home_value / medians.median_home_value;
    comparisons.push({
      label: "Median home value",
      text: `${town.name}'s median home value (${fmtDollars(town.metrics.median_home_value)}) is ${fmtRatio(ratio)} the MA median of ${fmtDollars(medians.median_home_value)}.`,
    });
  }
  if (town.metrics.rent_burden_pct !== null) {
    const diff = town.metrics.rent_burden_pct - medians.rent_burden_pct;
    const dir = diff > 0 ? "above" : "below";
    comparisons.push({
      label: "Renter cost burden",
      text: `${fmtPct(town.metrics.rent_burden_pct)} of ${town.name} renters are cost-burdened — ${Math.abs(diff).toFixed(1)} percentage points ${dir} the MA median of ${fmtPct(medians.rent_burden_pct)}.`,
    });
  }
  if (town.metrics.permits_per_1000_residents !== null) {
    const ratio =
      medians.permits_per_1000_residents > 0
        ? town.metrics.permits_per_1000_residents /
          medians.permits_per_1000_residents
        : null;
    comparisons.push({
      label: "Housing production",
      text: ratio !== null
        ? `${town.name} issues ${town.metrics.permits_per_1000_residents.toFixed(2)} permits per 1,000 residents — ${fmtRatio(ratio)} the MA median of ${medians.permits_per_1000_residents.toFixed(2)}.`
        : `${town.name} issues ${town.metrics.permits_per_1000_residents.toFixed(2)} permits per 1,000 residents.`,
    });
  }
  if (
    town.metrics.pct_multifamily_by_right !== null &&
    medians.pct_multifamily_by_right > 0
  ) {
    const diff =
      town.metrics.pct_multifamily_by_right - medians.pct_multifamily_by_right;
    const dir = diff > 0 ? "above" : "below";
    comparisons.push({
      label: "Zoning permissiveness",
      text: `${fmtPct(town.metrics.pct_multifamily_by_right)} of ${town.name}'s land allows multifamily by right — ${Math.abs(diff).toFixed(1)} percentage points ${dir} the Metro Boston median of ${fmtPct(medians.pct_multifamily_by_right)}.`,
    });
  }

  return (
    <main className="max-w-3xl mx-auto px-4 py-8 space-y-10">
      {/* Back link */}
      <div>
        <a
          href="/"
          className="text-sm text-gray-500 hover:text-gray-900 inline-flex items-center gap-1 transition-colors"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M15 19l-7-7 7-7"
            />
          </svg>
          Statewide map
        </a>
      </div>

      {/* Header */}
      <header className="space-y-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{town.name}</h1>
          <p className="text-gray-500 mt-1">
            {town.county}
            {town.population != null && (
              <> &middot; Pop. {town.population.toLocaleString()}</>
            )}
          </p>
        </div>

        {/* Composite grade hero */}
        <div
          className="inline-flex items-center gap-4 px-5 py-4 rounded-lg"
          style={{ backgroundColor: config.bg }}
        >
          <span
            className="text-6xl font-bold leading-none"
            style={{ color: config.text }}
          >
            {compositeGrade ?? "–"}
          </span>
          <div>
            <p
              className="text-lg font-semibold leading-tight"
              style={{ color: config.text }}
            >
              {compositeGrade
                ? `${compositeGrade} — ${gradeLabel(compositeGrade)}`
                : "Incomplete"}
            </p>
            <p
              className="text-sm mt-0.5 opacity-80"
              style={{ color: config.text }}
            >
              Composite housing grade
            </p>
          </div>
        </div>

        <p className="text-xs text-gray-400">
          Data as of {town.updated_at}
        </p>
      </header>

      {/* Grade breakdown */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Grade breakdown
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {GRADE_CARD_CONFIGS.map((cfg) => {
            const grade = town.grades[cfg.gradeKey];
            const keyMetric = cfg.getMetric(town);
            const note =
              cfg.gradeKey === "zoning"
                ? (town.data_notes?.zoning ?? null)
                : null;
            return (
              <GradeCard
                key={cfg.gradeKey}
                dimension={cfg.dimension}
                grade={grade}
                keyMetric={keyMetric}
                explanation={cfg.explanation}
                phase={grade === null ? cfg.phase : null}
                note={note}
              />
            );
          })}
        </div>
      </section>

      {/* Raw metrics */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Raw metrics
        </h2>
        <div className="bg-white border border-gray-200 rounded-lg px-5 py-2">
          <MetricsTable metrics={town.metrics} />
        </div>
      </section>

      {/* Context comparisons */}
      {comparisons.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Statewide context
          </h2>
          <ul className="space-y-3">
            {comparisons.map((c) => (
              <li key={c.label} className="flex gap-3">
                <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-gray-400 mt-2" />
                <p className="text-sm text-gray-700 leading-relaxed">{c.text}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Share */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Share this town&apos;s grades
        </h2>
        <ShareButton
          townName={town.name}
          grade={compositeGrade}
          keyStat={keyStat}
          url={shareUrl}
        />
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-100 pt-6 text-xs text-gray-400 space-y-1">
        <p>
          <a
            href="https://github.com/reframe-biker/mahousing/blob/main/METHODOLOGY.md"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-gray-600"
          >
            Methodology
          </a>{" "}
          &middot;{" "}
          <a
            href="https://github.com/reframe-biker/mahousing"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-gray-600"
          >
            GitHub
          </a>
        </p>
        <p>Built with public data. Updated weekly.</p>
      </footer>
    </main>
  );
}
