import type { Grade } from "@/src/types/town";

// Pre-computed: color hex + RGB components for opacity calculations
const GRADE_CONFIG: Record<
  NonNullable<Grade> | "null",
  { color: string; rgb: string; label: string }
> = {
  A:    { color: "#2d6a4f", rgb: "45,106,79",    label: "Excellent" },
  B:    { color: "#52b788", rgb: "82,183,136",   label: "Good" },
  C:    { color: "#e9c46a", rgb: "233,196,106",  label: "Below average" },
  D:    { color: "#e07b39", rgb: "224,123,57",   label: "Poor" },
  F:    { color: "#c1121f", rgb: "193,18,31",    label: "Failing" },
  null: { color: "#9a9088", rgb: "154,144,136",  label: "No data yet" },
};

export function gradeConfig(grade: Grade) {
  const { color, rgb, label } = GRADE_CONFIG[grade ?? "null"];
  return {
    color,
    label,
    // Hero section (town page): card bg at 15% opacity, text = grade color
    bg: `rgba(${rgb},0.15)`,
    text: color,
    // Badge-specific
    badgeBg: `rgba(${rgb},0.20)`,
    badgeBorder: `rgba(${rgb},0.40)`,
    badgeShadow: `rgba(${rgb},0.15)`,
  };
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
    sm: "w-8 h-8 text-sm",
    md: "w-12 h-12 text-xl",
    lg: "w-20 h-20 text-4xl",
  };

  return (
    <div className="flex items-center gap-2">
      <div
        className={`${sizeClasses[size]} rounded flex items-center justify-center flex-shrink-0 font-mono font-bold`}
        style={{
          backgroundColor: config.badgeBg,
          border: `1px solid ${config.badgeBorder}`,
          color: config.color,
        }}
        aria-label={`Grade ${grade ?? "not available"}`}
      >
        {grade ?? "–"}
      </div>
      {showLabel && (
        <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
          {config.label}
        </span>
      )}
    </div>
  );
}
