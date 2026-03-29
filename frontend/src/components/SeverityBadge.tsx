type SeverityLevel = "calm" | "minor" | "moderate" | "strong" | "severe" | "extreme" | "critical" | "unknown";

interface SeverityBadgeProps {
  level: SeverityLevel;
}

const levelToLabel: Record<SeverityLevel, string> = {
  calm: "Calm",
  minor: "Minor",
  moderate: "Moderate",
  strong: "Strong",
  severe: "Severe",
  extreme: "Extreme",
  critical: "Critical",
  unknown: "Unknown",
};

export function SeverityBadge({ level }: SeverityBadgeProps) {
  return (
    <span className={`severity-badge severity-${level}`}>
      {levelToLabel[level]}
    </span>
  );
}
