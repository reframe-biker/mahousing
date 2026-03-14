import type { Metrics, MetricsMeta } from "@/src/types/town";

// Formatters keyed by the `unit` field from metrics.json.
// Presentation logic lives here; labels and descriptions come from props.
const FORMATTERS: Record<string, (v: number) => string> = {
  percent: (v) => v.toFixed(1) + "%",
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
    <div className="divide-y divide-gray-100">
      {Object.entries(metricsMeta).map(([key, meta]) => {
        const value = metrics[key as keyof Metrics];
        return (
          <div key={key} className="py-4 first:pt-0 last:pb-0">
            <div className="flex flex-col sm:flex-row sm:items-baseline sm:justify-between gap-1">
              <span className="text-sm font-medium text-gray-900">{meta.label}</span>
              <span
                className={`text-sm font-semibold tabular-nums ${
                  value === null ? "text-gray-400" : "text-gray-900"
                }`}
              >
                {fmt(value, meta.unit)}
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-1 leading-relaxed">
              {meta.description}
            </p>
          </div>
        );
      })}
    </div>
  );
}
