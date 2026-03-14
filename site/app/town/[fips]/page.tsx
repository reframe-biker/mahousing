import fs from "fs";
import path from "path";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import type { TownRecord, Grade, MetricsMeta } from "@/src/types/town";
import GradeBadge, { gradeConfig } from "@/app/components/GradeBadge";
import GradeCard from "@/app/components/GradeCard";
import MbtaGradeCard from "@/app/components/MbtaGradeCard";
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

function loadMetricsMeta(): MetricsMeta {
  return JSON.parse(
    fs.readFileSync(path.join(DATA_DIR, "metrics.json"), "utf-8")
  ) as MetricsMeta;
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
  pct_multifamily_permitted: number;
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
    pct_multifamily_permitted: median(getValues("pct_multifamily_permitted")),
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
      t.metrics.pct_multifamily_permitted !== null
        ? `${t.metrics.pct_multifamily_permitted.toFixed(1)}% of permitted units are multifamily (5+ units)`
        : null,
    explanation:
      "Share of permitted housing units that are multifamily (5+ units), averaged over the most recent 3 years. Used as a revealed-preference measure of zoning permissiveness — towns that permit more multifamily in practice tend to have more permissive zoning codes. Low-permit towns (fewer than 10 total permits over 3 years) show N/A. This metric will be replaced with National Zoning Atlas data when available.",
    phase: null,
  },
  // MBTA card is rendered separately via MbtaGradeCard — placeholder kept for
  // iteration order but skipped in the render loop below.
  {
    dimension: "MBTA Communities Act",
    gradeKey: "mbta",
    getMetric: () => null,
    explanation: "",
    phase: null,
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
// Section heading style — data journalism label
// ---------------------------------------------------------------------------

const sectionHeadingStyle: React.CSSProperties = {
  fontSize: "11px",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  color: "var(--text-secondary)",
  marginBottom: "16px",
};

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
  const metricsMeta = loadMetricsMeta();

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
      text:
        ratio !== null
          ? `${town.name} issues ${town.metrics.permits_per_1000_residents.toFixed(2)} permits per 1,000 residents — ${fmtRatio(ratio)} the MA median of ${medians.permits_per_1000_residents.toFixed(2)}.`
          : `${town.name} issues ${town.metrics.permits_per_1000_residents.toFixed(2)} permits per 1,000 residents.`,
    });
  }
  if (
    town.metrics.pct_multifamily_permitted !== null &&
    medians.pct_multifamily_permitted > 0
  ) {
    const diff =
      town.metrics.pct_multifamily_permitted - medians.pct_multifamily_permitted;
    const dir = diff > 0 ? "above" : "below";
    comparisons.push({
      label: "Zoning permissiveness",
      text: `${fmtPct(town.metrics.pct_multifamily_permitted)} of permitted units in ${town.name} are multifamily — ${Math.abs(diff).toFixed(1)} percentage points ${dir} the MA median of ${fmtPct(medians.pct_multifamily_permitted)}.`,
    });
  }

  return (
    <main
      className="max-w-3xl mx-auto px-4 py-8 space-y-10"
      style={{ backgroundColor: "var(--bg-primary)" }}
    >
      {/* Back link */}
      <div>
        <a
          href="/"
          className="text-sm inline-flex items-center gap-1 transition-colors"
          style={{ color: "var(--accent)" }}
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
          <h1
            className="text-3xl"
            style={{ fontWeight: 600, color: "var(--text-primary)" }}
          >
            {town.name}
          </h1>
          <p className="mt-1" style={{ color: "var(--text-secondary)" }}>
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
            className="font-mono leading-none"
            style={{ fontSize: "72px", fontWeight: 700, color: config.text }}
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

        <p
          className="text-xs font-mono"
          style={{ color: "var(--text-muted)" }}
        >
          Data as of {town.updated_at}
        </p>
      </header>

      {/* Grade breakdown */}
      <section>
        <h2 style={sectionHeadingStyle}>Grade breakdown</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {GRADE_CARD_CONFIGS.map((cfg) => {
            // MBTA card uses a dedicated component with richer data
            if (cfg.gradeKey === "mbta") {
              return (
                <MbtaGradeCard
                  key="mbta"
                  grade={town.grades.mbta}
                  mbtaStatus={town.mbta_status}
                  mbtaDeadline={town.mbta_deadline}
                  mbtaActionDate={town.mbta_action_date}
                  description={metricsMeta["mbta_status"]?.description ?? ""}
                />
              );
            }

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
        <h2 style={sectionHeadingStyle}>Raw metrics</h2>
        <div
          className="rounded-lg px-2 py-1"
          style={{
            backgroundColor: "var(--bg-card)",
            border: "1px solid var(--border)",
          }}
        >
          <MetricsTable metrics={town.metrics} metricsMeta={metricsMeta} />
        </div>
      </section>

      {/* Context comparisons */}
      {comparisons.length > 0 && (
        <section>
          <h2 style={sectionHeadingStyle}>Statewide context</h2>
          <ul className="space-y-3">
            {comparisons.map((c) => (
              <li key={c.label} className="flex gap-3">
                <span
                  className="flex-shrink-0 w-1.5 h-1.5 rounded-full mt-2"
                  style={{ backgroundColor: "var(--text-muted)" }}
                />
                <p
                  className="text-sm leading-relaxed"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {c.text}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Share */}
      <section>
        <h2 style={sectionHeadingStyle}>Share this town&apos;s grades</h2>
        <ShareButton
          townName={town.name}
          grade={compositeGrade}
          keyStat={keyStat}
          url={shareUrl}
        />
      </section>

      {/* Footer */}
      <footer
        className="pt-6 text-xs text-center"
        style={{
          borderTop: "1px solid var(--border)",
          color: "var(--text-muted)",
        }}
      >
        <span>Built with public data · Updated weekly</span>
      </footer>
    </main>
  );
}
