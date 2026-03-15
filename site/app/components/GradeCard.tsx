import type { Grade } from "@/src/types/town";
import GradeBadge from "./GradeBadge";

interface GradeCardProps {
  dimension: string;
  grade: Grade;
  keyMetric: string | null;
  explanation: string;
  phase?: string | null;
  note?: string | null;
  sourceAttribution?: string | null;
  footerLink?: { href: string; label: string } | null;
}

export default function GradeCard({
  dimension,
  grade,
  keyMetric,
  explanation,
  phase,
  note,
  sourceAttribution,
  footerLink,
}: GradeCardProps) {
  const isPending = grade === null;

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
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3
              className="uppercase tracking-wide"
              style={{
                fontSize: "11px",
                fontWeight: 600,
                letterSpacing: "0.08em",
                color: isPending ? "var(--text-muted)" : "var(--text-secondary)",
              }}
            >
              {dimension}
            </h3>
            {phase && (
              <span
                className="font-mono"
                style={{ fontSize: "11px", color: "var(--text-muted)" }}
              >
                {phase}
              </span>
            )}
          </div>
          <GradeBadge grade={grade} size="md" />
        </div>

        {keyMetric && (
          <p
            className="text-sm font-mono"
            style={{ color: "var(--text-primary)" }}
          >
            {keyMetric}
          </p>
        )}

        <p
          className="text-xs leading-relaxed"
          style={{ color: "var(--text-muted)" }}
        >
          {explanation}
        </p>

        {sourceAttribution && (
          <p
            className="text-xs"
            style={{ color: "var(--text-muted)", fontStyle: "italic" }}
          >
            {sourceAttribution}
          </p>
        )}

        {footerLink && (
          <a
            href={footerLink.href}
            className="text-xs"
            style={{ color: "var(--accent)" }}
          >
            {footerLink.label} →
          </a>
        )}
      </div>

      {note && (
        <div
          className="flex items-start gap-2 px-4 py-2.5"
          style={{
            backgroundColor: "#fef3c7",
            borderTop: "1px solid #d97706",
          }}
        >
          <svg
            className="w-3.5 h-3.5 flex-shrink-0 mt-0.5"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
            style={{ color: "#92400e" }}
          >
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
              clipRule="evenodd"
            />
          </svg>
          <p className="text-xs leading-relaxed" style={{ color: "#92400e" }}>
            {note}
          </p>
        </div>
      )}
    </div>
  );
}
