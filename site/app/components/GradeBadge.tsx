import type { Grade } from "@/src/types/town";

const GRADE_CONFIG: Record<
  NonNullable<Grade> | "null",
  { bg: string; text: string; label: string }
> = {
  A: { bg: "#2d6a4f", text: "#ffffff", label: "Excellent" },
  B: { bg: "#74c69d", text: "#1a3d2b", label: "Good" },
  C: { bg: "#ffd166", text: "#7a5c00", label: "Below average" },
  D: { bg: "#ef9a00", text: "#ffffff", label: "Poor" },
  F: { bg: "#e63946", text: "#ffffff", label: "Failing" },
  null: { bg: "#e8e8e8", text: "#888888", label: "No data yet" },
};

export function gradeConfig(grade: Grade) {
  return GRADE_CONFIG[grade ?? "null"];
}

interface GradeBadgeProps {
  grade: Grade;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
}

export default function GradeBadge({
  grade,
  size = "md",
  showLabel = false,
}: GradeBadgeProps) {
  const config = gradeConfig(grade);

  const sizeClasses = {
    sm: "w-8 h-8 text-sm font-bold",
    md: "w-12 h-12 text-xl font-bold",
    lg: "w-20 h-20 text-4xl font-bold",
  };

  return (
    <div className="flex items-center gap-2">
      <div
        className={`${sizeClasses[size]} rounded flex items-center justify-center flex-shrink-0`}
        style={{ backgroundColor: config.bg, color: config.text }}
        aria-label={`Grade ${grade ?? "not available"}`}
      >
        {grade ?? "–"}
      </div>
      {showLabel && (
        <span className="text-gray-600 text-sm">{config.label}</span>
      )}
    </div>
  );
}
