import type { Grade } from "@/src/types/town";
import GradeBadge from "./GradeBadge";

interface GradeCardProps {
  dimension: string;
  grade: Grade;
  keyMetric: string | null;
  explanation: string;
  phase?: string | null;
  note?: string | null;
}

export default function GradeCard({
  dimension,
  grade,
  keyMetric,
  explanation,
  phase,
  note,
}: GradeCardProps) {
  const isPending = grade === null;

  return (
    <div
      className={`rounded-lg border flex flex-col gap-0 overflow-hidden ${
        isPending
          ? "bg-gray-50 border-gray-200 opacity-75"
          : "bg-white border-gray-200"
      }`}
    >
      <div className="p-4 flex flex-col gap-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3 className="font-semibold text-gray-900 text-sm uppercase tracking-wide">
              {dimension}
            </h3>
            {phase && (
              <span className="text-xs text-gray-400 font-medium">{phase}</span>
            )}
          </div>
          <GradeBadge grade={grade} size="md" />
        </div>

        {keyMetric && (
          <p className="text-sm font-medium text-gray-800">{keyMetric}</p>
        )}

        <p className="text-xs text-gray-500 leading-relaxed">{explanation}</p>
      </div>

      {note && (
        <div className="flex items-start gap-2 px-4 py-2.5 bg-amber-50 border-t border-amber-200">
          <svg
            className="w-3.5 h-3.5 text-amber-600 flex-shrink-0 mt-0.5"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
              clipRule="evenodd"
            />
          </svg>
          <p className="text-xs text-amber-800 leading-relaxed">{note}</p>
        </div>
      )}
    </div>
  );
}
