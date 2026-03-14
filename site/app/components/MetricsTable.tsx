import type { Metrics } from "@/src/types/town";

interface MetricRow {
  label: string;
  value: string;
  description: string;
}

function fmt(value: number | null, formatter: (v: number) => string): string {
  if (value === null) return "Not available";
  return formatter(value);
}

function formatDollars(v: number): string {
  return "$" + Math.round(v).toLocaleString("en-US");
}

function formatPct(v: number): string {
  return v.toFixed(1) + "%";
}

function formatPer1000(v: number): string {
  return v.toFixed(2) + " per 1,000 residents";
}

interface MetricsTableProps {
  metrics: Metrics;
}

export default function MetricsTable({ metrics }: MetricsTableProps) {
  const rows: MetricRow[] = [
    {
      label: "Land allowing multifamily by right",
      value: fmt(metrics.pct_multifamily_by_right, formatPct),
      description:
        "Share of the municipality's land area where multifamily housing can be built without a special permit. Higher means more permissive zoning. Source: MA Zoning Atlas (MAPC). Metro Boston coverage only.",
    },
    {
      label: "Median home value",
      value: fmt(metrics.median_home_value, formatDollars),
      description:
        "Median value of owner-occupied housing units. A proxy for housing cost and affordability pressure. Source: U.S. Census ACS 5-year estimates.",
    },
    {
      label: "Renters cost-burdened",
      value: fmt(metrics.rent_burden_pct, formatPct),
      description:
        "Share of renter households paying more than 30% of income on gross rent. High cost burden indicates housing supply shortfall. Source: U.S. Census ACS 5-year estimates.",
    },
    {
      label: "Permits per 1,000 residents",
      value: fmt(metrics.permits_per_1000_residents, formatPer1000),
      description:
        "Annual residential building permits averaged over the most recent multi-year period, normalized by population. Measures actual housing production. Source: Census Building Permits Survey.",
    },
  ];

  return (
    <div className="divide-y divide-gray-100">
      {rows.map((row) => (
        <div key={row.label} className="py-4 first:pt-0 last:pb-0">
          <div className="flex flex-col sm:flex-row sm:items-baseline sm:justify-between gap-1">
            <span className="text-sm font-medium text-gray-900">{row.label}</span>
            <span
              className={`text-sm font-semibold tabular-nums ${
                row.value === "Not available" ? "text-gray-400" : "text-gray-900"
              }`}
            >
              {row.value}
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1 leading-relaxed">
            {row.description}
          </p>
        </div>
      ))}
    </div>
  );
}
