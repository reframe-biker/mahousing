import type { Grade, MbtaStatus } from "@/src/types/town";
import GradeBadge from "./GradeBadge";

const DHCD_URL =
  "https://www.mass.gov/info-details/multi-family-zoning-requirement-for-mbta-communities";

const STATUS_LABEL: Record<NonNullable<MbtaStatus>, string> = {
  compliant: "Compliant — zoning adopted",
  interim: "Interim action plan adopted",
  "non-compliant": "Non-compliant — funding at risk",
  pending: "Plan submitted, under review",
  exempt: "Not subject to MBTA Communities Act",
};

function formatDate(iso: string): string {
  // "2024-12-31" → "Dec 31, 2024"
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

interface Props {
  grade: Grade;
  mbtaStatus: MbtaStatus;
  mbtaDeadline: string | null;
  mbtaActionDate: string | null;
  description: string;
}

export default function MbtaGradeCard({
  grade,
  mbtaStatus,
  mbtaDeadline,
  mbtaActionDate,
  description,
}: Props) {
  const isPending = grade === null;
  const statusLabel =
    mbtaStatus != null
      ? (STATUS_LABEL[mbtaStatus] ?? mbtaStatus)
      : "Not subject to MBTA Communities Act";

  return (
    <div
      className="rounded-lg flex flex-col gap-0 overflow-hidden"
      style={
        isPending
          ? {
              backgroundColor: "var(--bg-secondary)",
              border: "1px solid var(--border-subtle)",
              opacity: 0.8,
            }
          : {
              backgroundColor: "var(--bg-card)",
              border: "1px solid var(--border)",
            }
      }
    >
      <div className="p-4 flex flex-col gap-3">
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <h3
            className="uppercase tracking-wide"
            style={{
              fontSize: "11px",
              fontWeight: 600,
              letterSpacing: "0.08em",
              color: isPending ? "var(--text-muted)" : "var(--text-secondary)",
            }}
          >
            MBTA Communities Act
          </h3>
          <GradeBadge grade={grade} size="md" />
        </div>

        {/* Status label */}
        <p
          className="text-sm font-mono"
          style={{ color: "var(--text-primary)" }}
        >
          {statusLabel}
        </p>

        {/* Dates */}
        {(mbtaDeadline || mbtaActionDate) && (
          <div className="flex flex-col gap-1">
            {mbtaDeadline && (
              <p
                className="text-xs font-mono"
                style={{ color: "var(--text-secondary)" }}
              >
                Deadline: {formatDate(mbtaDeadline)}
              </p>
            )}
            {mbtaActionDate && (
              <p
                className="text-xs font-mono"
                style={{ color: "var(--text-secondary)" }}
              >
                Last action: {formatDate(mbtaActionDate)}
              </p>
            )}
          </div>
        )}

        {/* Description from metrics.json */}
        {description && (
          <p
            className="text-xs leading-relaxed"
            style={{ color: "var(--text-muted)" }}
          >
            {description}
          </p>
        )}

        {/* DHCD source link */}
        <a
          href={DHCD_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs"
          style={{ color: "var(--text-secondary)" }}
        >
          DHCD compliance status
          <svg
            className="w-3 h-3"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M4.25 5.5a.75.75 0 00-.75.75v8.5c0 .414.336.75.75.75h8.5a.75.75 0 00.75-.75v-4a.75.75 0 011.5 0v4A2.25 2.25 0 0112.75 17h-8.5A2.25 2.25 0 012 14.75v-8.5A2.25 2.25 0 014.25 4h5a.75.75 0 010 1.5h-5z"
              clipRule="evenodd"
            />
            <path
              fillRule="evenodd"
              d="M6.194 12.753a.75.75 0 001.06.053L16.5 4.44v2.81a.75.75 0 001.5 0v-4.5a.75.75 0 00-.75-.75h-4.5a.75.75 0 000 1.5h2.553l-9.056 8.194a.75.75 0 00-.053 1.06z"
              clipRule="evenodd"
            />
          </svg>
        </a>
      </div>
    </div>
  );
}
