import type { Metrics, MetricsMeta } from "@/src/types/town";

// Formatters keyed by the `unit` field from metrics.json.
// Presentation logic lives here; labels and descriptions come from props.
const FORMATTERS: Record<string, (v: number) => string> = {
  percent: (v) => v.toFixed(1) + "%",
  pct: (v) => v.toFixed(1) + "%",
  dollars: (v) => "$" + Math.round(v).toLocaleString("en-US"),
  rate: (v) => v.toFixed(2) + " per 1,000 residents",
};

function fmt(value: number | null, unit: string): string {
  if (value === null) return "Not available";
  const formatter = FORMATTERS[unit];
  return formatter ? formatter(value) : String(value);
}

interface MetricsTableProps {
  metrics: Metrics;
  metricsMeta: MetricsMeta;
}

export default function MetricsTable({ metrics, metricsMeta }: MetricsTableProps) {
  return (
    <div>
      {Object.entries(metricsMeta).filter(([, meta]) => meta.unit !== "status" && meta.display !== false).map(([key, meta], idx) => {
        const value = metrics[key as keyof Metrics];
        const isEven = idx % 2 === 1;
        return (
          <div
            key={key}
            className="py-4 first:pt-3 last:pb-3 px-1"
            style={
              isEven
                ? { backgroundColor: "rgba(242,240,236,0.6)" }
                : undefined
            }
          >
            <div className="flex flex-col sm:flex-row sm:items-baseline sm:justify-between gap-1">
              <span
                className="text-sm"
                style={{ color: "var(--text-secondary)" }}
              >
                {meta.label}
              </span>
              <span
                className="text-sm font-mono tabular-nums text-right"
                style={{
                  color: value === null ? "var(--text-muted)" : "var(--text-primary)",
                  fontWeight: value === null ? 400 : 500,
                }}
              >
                {typeof value === "string" ? value : fmt(value, meta.unit)}
              </span>
            </div>
            <p
              className="text-xs mt-1 leading-relaxed"
              style={{ fontSize: "13px", color: "var(--text-muted)" }}
            >
              {meta.description}
            </p>
          </div>
        );
      })}
    </div>
  );
}
