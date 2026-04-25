/**
 * Chart payloads from `buildTransactionHistoryAnalytics` (backend / Recharts-friendly).
 */

export type LineSeriesPoint = { x: string; y: number };

export type LineSeriesSpec = {
  name: string;
  color?: string;
  points: LineSeriesPoint[];
};

export type ChartDatum = {
  name: string;
  value: number;
  color?: string;
};

export type AnalyticsChartSpec = {
  key: string;
  title: string;
  type: "line" | "bar" | "pie" | "donut" | "horizontalBar";
  description?: string;
  data?: ChartDatum[];
  x_axis_key?: string;
  series?: LineSeriesSpec[];
};

export function isAnalyticsChartSpec(v: unknown): v is AnalyticsChartSpec {
  if (!v || typeof v !== "object") return false;
  const o = v as Record<string, unknown>;
  return (
    typeof o.key === "string" &&
    typeof o.title === "string" &&
    typeof o.type === "string" &&
    ["line", "bar", "pie", "donut", "horizontalBar"].includes(o.type)
  );
}

export function normalizeChartsPayload(raw: unknown): AnalyticsChartSpec[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter(isAnalyticsChartSpec);
}
