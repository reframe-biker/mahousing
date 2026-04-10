"use client";

import { useState, useMemo, useEffect } from "react";
import type { TownRecord, MbtaStatus, Grade } from "@/src/types/town";
import GradeBadge from "@/app/components/GradeBadge";

// ---------------------------------------------------------------------------
// Types & constants
// ---------------------------------------------------------------------------

type StatusFilter = MbtaStatus | "all";
type SortKey = "status" | "name" | "grade" | "deadline" | "action";

const STATUS_ORDER: Record<NonNullable<MbtaStatus>, number> = {
  "non-compliant": 0,
  pending: 1,
  interim: 2,
  compliant: 3,
  exempt: 4,
};

const STATUS_LABEL: Record<NonNullable<MbtaStatus>, string> = {
  compliant: "Compliant",
  interim: "Interim",
  "non-compliant": "Non-compliant",
  pending: "Pending",
  exempt: "Exempt",
};

const STATUS_COLOR: Record<NonNullable<MbtaStatus>, string> = {
  compliant: "#2d6a4f",
  interim: "#52b788",
  pending: "#b38a00",
  "non-compliant": "#c1121f",
  exempt: "#9a9088",
};

const STATUS_BG_LIGHT: Record<string, string> = {
  compliant: "#e8f5f0",
  interim: "#edf7f2",
  pending: "#fdf8e4",
  "non-compliant": "#fce8e8",
  exempt: "#f0efee",
};

const STATUS_BG_DARK: Record<string, string> = {
  compliant: "#1a2e26",
  interim: "#1a2e26",
  pending: "#2a2200",
  "non-compliant": "#2e1a1a",
  exempt: "#2a2724",
};

function statusBg(status: string, isDark: boolean): string {
  return isDark ? (STATUS_BG_DARK[status] ?? "#2a2724") : (STATUS_BG_LIGHT[status] ?? "#f0efee");
}

const GRADE_TO_NUM: Record<NonNullable<Grade>, number> = {
  A: 4,
  B: 3,
  C: 2,
  D: 1,
  F: 0,
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MbtaBadge({ status, isDark }: { status: NonNullable<MbtaStatus>; isDark: boolean }) {
  return (
    <span
      className="inline-block px-2 py-0.5 rounded text-xs font-mono font-medium"
      style={{
        color: STATUS_COLOR[status],
        backgroundColor: statusBg(status, isDark),
        border: `1px solid ${STATUS_COLOR[status]}44`,
      }}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// ---------------------------------------------------------------------------
// Main client component
// ---------------------------------------------------------------------------

interface Props {
  towns: TownRecord[];
  updatedAt: string;
}

export default function MbtaClient({ towns, updatedAt }: Props) {
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [sort, setSort] = useState<SortKey>("status");
  const [sortAsc, setSortAsc] = useState(true);
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    setIsDark(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsDark(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const counts = useMemo(() => {
    const c: Partial<Record<NonNullable<MbtaStatus>, number>> = {};
    for (const t of towns) {
      if (t.mbta_status) c[t.mbta_status] = (c[t.mbta_status] ?? 0) + 1;
    }
    return c;
  }, [towns]);

  const filtered = useMemo(() => {
    let list =
      filter === "all" ? towns : towns.filter((t) => t.mbta_status === filter);

    list = [...list].sort((a, b) => {
      let cmp = 0;
      if (sort === "status") {
        cmp =
          (STATUS_ORDER[a.mbta_status ?? "exempt"] ?? 99) -
          (STATUS_ORDER[b.mbta_status ?? "exempt"] ?? 99);
      } else if (sort === "name") {
        cmp = a.name.localeCompare(b.name);
      } else if (sort === "grade") {
        const ag = a.grades.composite ? GRADE_TO_NUM[a.grades.composite] : -1;
        const bg = b.grades.composite ? GRADE_TO_NUM[b.grades.composite] : -1;
        cmp = ag - bg;
      } else if (sort === "deadline") {
        cmp = (a.mbta_deadline ?? "").localeCompare(b.mbta_deadline ?? "");
      } else if (sort === "action") {
        cmp = (a.mbta_action_date ?? "").localeCompare(
          b.mbta_action_date ?? ""
        );
      }
      return sortAsc ? cmp : -cmp;
    });

    return list;
  }, [towns, filter, sort, sortAsc]);

  function handleSort(key: SortKey) {
    if (sort === key) {
      setSortAsc((p) => !p);
    } else {
      setSort(key);
      setSortAsc(true);
    }
  }

  function downloadCsv() {
    const header = [
      "Town",
      "County",
      "MBTA Status",
      "Housing Grade",
      "Last Action",
      "Deadline",
    ];
    const rows = filtered.map((t) => [
      t.name,
      t.county,
      t.mbta_status ?? "",
      t.grades.composite ?? "",
      t.mbta_action_date ?? "",
      t.mbta_deadline ?? "",
    ]);
    const csv = [header, ...rows]
      .map((r) =>
        r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")
      )
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "mbta-communities.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const thStyle: React.CSSProperties = {
    padding: "8px 12px",
    textAlign: "left",
    fontSize: "11px",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--text-muted)",
    borderBottom: "1px solid var(--border)",
    cursor: "pointer",
    userSelect: "none",
    whiteSpace: "nowrap",
  };

  const tdStyle: React.CSSProperties = {
    padding: "10px 12px",
    fontSize: "14px",
    color: "var(--text-primary)",
    borderBottom: "1px solid var(--border-subtle)",
    verticalAlign: "middle",
  };

  const subjectStatuses: NonNullable<MbtaStatus>[] = [
    "non-compliant",
    "pending",
    "interim",
    "compliant",
  ];

  return (
    <>
      {/* Summary filter bar */}
      <div className="flex flex-wrap gap-2 mb-6">
        <button
          onClick={() => setFilter("all")}
          className="px-3 py-1.5 rounded text-sm font-medium"
          style={{
            backgroundColor:
              filter === "all" ? "var(--text-primary)" : "var(--bg-secondary)",
            color: filter === "all" ? "var(--bg-primary)" : "var(--text-primary)",
            border: "1px solid var(--border)",
          }}
        >
          All ({towns.length})
        </button>
        {subjectStatuses.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className="px-3 py-1.5 rounded text-sm font-medium"
            style={{
              backgroundColor: filter === s ? STATUS_COLOR[s] : statusBg(s, isDark),
              color: filter === s ? "var(--bg-primary)" : STATUS_COLOR[s],
              border: `1px solid ${STATUS_COLOR[s]}44`,
            }}
          >
            {STATUS_LABEL[s]} ({counts[s] ?? 0})
          </button>
        ))}
        <button
          onClick={() => setFilter("exempt")}
          className="px-3 py-1.5 rounded text-sm font-medium"
          style={{
            backgroundColor:
              filter === "exempt" ? STATUS_COLOR["exempt"] : statusBg("exempt", isDark),
            color: filter === "exempt" ? "var(--bg-primary)" : STATUS_COLOR["exempt"],
            border: `1px solid ${STATUS_COLOR["exempt"]}44`,
          }}
        >
          Exempt ({counts["exempt"] ?? 0})
        </button>
      </div>

      {/* Count + download */}
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Showing {filtered.length}{" "}
          {filtered.length !== 1 ? "municipalities" : "municipality"}
        </p>
        <button
          onClick={downloadCsv}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium"
          style={{
            backgroundColor: "var(--bg-secondary)",
            border: "1px solid var(--border)",
            color: "var(--text-primary)",
          }}
        >
          <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z"
              clipRule="evenodd"
            />
          </svg>
          Download CSV
        </button>
      </div>

      {/* Table */}
      <div
        className="rounded-lg overflow-hidden"
        style={{ border: "1px solid var(--border)" }}
      >
        <div className="overflow-x-auto">
          <table className="w-full" style={{ borderCollapse: "collapse" }}>
            <thead style={{ backgroundColor: "var(--bg-secondary)" }}>
              <tr>
                <th style={thStyle} onClick={() => handleSort("name")}>
                  Town{sort === "name" ? (sortAsc ? " ↑" : " ↓") : ""}
                </th>
                <th style={{ ...thStyle, cursor: "default" }}>County</th>
                <th style={thStyle} onClick={() => handleSort("status")}>
                  MBTA Status
                  {sort === "status" ? (sortAsc ? " ↑" : " ↓") : ""}
                </th>
                <th style={thStyle} onClick={() => handleSort("grade")}>
                  Housing Grade
                  {sort === "grade" ? (sortAsc ? " ↑" : " ↓") : ""}
                </th>
                <th style={thStyle} onClick={() => handleSort("deadline")}>
                  Deadline
                  {sort === "deadline" ? (sortAsc ? " ↑" : " ↓") : ""}
                </th>
              </tr>
            </thead>
            <tbody style={{ backgroundColor: "var(--bg-card)" }}>
              {filtered.map((town) => (
                <tr
                  key={town.fips}
                  style={{ transition: "background-color 0.1s" }}
                  onMouseEnter={(e) => {
                    (
                      e.currentTarget as HTMLTableRowElement
                    ).style.backgroundColor = "var(--bg-secondary)";
                  }}
                  onMouseLeave={(e) => {
                    (
                      e.currentTarget as HTMLTableRowElement
                    ).style.backgroundColor = "var(--bg-card)";
                  }}
                >
                  <td style={tdStyle}>
                    <a
                      href={`/town/${town.fips}`}
                      style={{
                        color: "var(--accent)",
                        fontWeight: 500,
                        textDecoration: "none",
                      }}
                    >
                      {town.name}
                    </a>
                  </td>
                  <td style={{ ...tdStyle, color: "var(--text-secondary)" }}>
                    {town.county}
                  </td>
                  <td style={tdStyle}>
                    {town.mbta_status ? (
                      <MbtaBadge status={town.mbta_status} isDark={isDark} />
                    ) : (
                      <span style={{ color: "var(--text-muted)" }}>—</span>
                    )}
                  </td>
                  <td style={tdStyle}>
                    <GradeBadge grade={town.grades.composite} size="sm" />
                  </td>
                  <td
                    style={{
                      ...tdStyle,
                      fontFamily: "var(--font-dm-mono), monospace",
                      fontSize: "13px",
                      color: "var(--text-secondary)",
                    }}
                  >
                    {formatDate(town.mbta_deadline)}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    style={{
                      ...tdStyle,
                      textAlign: "center",
                      color: "var(--text-muted)",
                      padding: "32px",
                    }}
                  >
                    No municipalities match this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <p
        className="mt-4 text-xs font-mono"
        style={{ color: "var(--text-muted)" }}
      >
        Data as of {updatedAt} · Source:{" "}
        <a
          href="https://www.mass.gov/info-details/mbta-communities-compliance-status"
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: "var(--text-secondary)" }}
        >
          DHCD compliance status
        </a>
      </p>
    </>
  );
}
