import type { MetricGrade } from "./channelMetrics";
import { metricPillClass } from "./channelMetrics";

export function MetricPill({ value, grade }: { value: string; grade: MetricGrade }) {
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${metricPillClass(grade)}`}>{value}</span>;
}
