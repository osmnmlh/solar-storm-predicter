import { ReactNode } from "react";

interface MetricCardProps {
  title: string;
  value: string;
  subValue?: string;
  icon?: ReactNode;
}

export function MetricCard({ title, value, subValue, icon }: MetricCardProps) {
  return (
    <article className="metric-card reveal-rise">
      <header className="metric-head">
        <span>{title}</span>
        {icon}
      </header>
      <strong className="metric-value">{value}</strong>
      {subValue ? <p className="metric-subvalue">{subValue}</p> : null}
    </article>
  );
}
