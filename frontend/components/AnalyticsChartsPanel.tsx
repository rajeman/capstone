"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { AnalyticsChartSpec, LineSeriesSpec } from "../lib/analyticsChartTypes";

type AnalyticsChartsPanelProps = {
  charts: AnalyticsChartSpec[];
};

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);
}

function mergeLineSeries(series: LineSeriesSpec[]): Array<Record<string, string | number>> {
  const rows = new Map<string, Record<string, string | number>>();
  for (const s of series) {
    for (const p of s.points) {
      const row = rows.get(p.x) ?? { x: p.x };
      row[s.name] = p.y;
      rows.set(p.x, row);
    }
  }
  return Array.from(rows.values()).sort((a, b) => String(a.x).localeCompare(String(b.x)));
}

function ChartCard({ chart }: { chart: AnalyticsChartSpec }) {
  const description = chart.description ? (
    <p className="mb-2 text-[11px] text-gray-500 dark:text-gray-400">{chart.description}</p>
  ) : null;

  if (chart.type === "line" && chart.series?.length) {
    const data = mergeLineSeries(chart.series);
    return (
      <div className="mb-5 min-w-0 rounded-xl border border-blue-100/80 bg-white/80 p-3 dark:border-gray-700 dark:bg-gray-900/50">
        <h4 className="mb-1 text-sm font-semibold text-gray-800 dark:text-gray-100">{chart.title}</h4>
        {description}
        <div className="h-56 w-full min-w-0">
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="x" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `$${v}`} />
              <Tooltip formatter={(v) => formatCurrency(Number(v))} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {chart.series.map((s) => (
                <Line
                  key={s.name}
                  dataKey={s.name}
                  type="monotone"
                  stroke={s.color || "#3B82F6"}
                  strokeWidth={2}
                  dot={{ r: 2 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  if ((chart.type === "bar" || chart.type === "horizontalBar") && chart.data?.length) {
    const horizontal = chart.type === "horizontalBar";
    return (
      <div className="mb-5 min-w-0 rounded-xl border border-blue-100/80 bg-white/80 p-3 dark:border-gray-700 dark:bg-gray-900/50">
        <h4 className="mb-1 text-sm font-semibold text-gray-800 dark:text-gray-100">{chart.title}</h4>
        {description}
        <div className="h-56 w-full min-w-0">
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <BarChart data={chart.data} layout={horizontal ? "vertical" : "horizontal"}>
              <CartesianGrid strokeDasharray="3 3" />
              {horizontal ? (
                <>
                  <XAxis type="number" tickFormatter={(v) => `$${v}`} tick={{ fontSize: 10 }} />
                  <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 9 }} />
                </>
              ) : (
                <>
                  <XAxis dataKey="name" tick={{ fontSize: 9 }} angle={-20} textAnchor="end" height={52} />
                  <YAxis tickFormatter={(v) => `$${v}`} tick={{ fontSize: 10 }} />
                </>
              )}
              <Tooltip formatter={(v) => formatCurrency(Number(v))} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {chart.data.map((row, idx) => (
                  <Cell key={`${chart.key}-${idx}`} fill={row.color || "#3B82F6"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  if ((chart.type === "pie" || chart.type === "donut") && chart.data?.length) {
    return (
      <div className="mb-5 min-w-0 rounded-xl border border-blue-100/80 bg-white/80 p-3 dark:border-gray-700 dark:bg-gray-900/50">
        <h4 className="mb-1 text-sm font-semibold text-gray-800 dark:text-gray-100">{chart.title}</h4>
        {description}
        <div className="h-56 w-full min-w-0">
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <PieChart>
              <Pie
                data={chart.data}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={74}
                innerRadius={chart.type === "donut" ? 44 : 0}
                label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
              >
                {chart.data.map((row, idx) => (
                  <Cell key={`${chart.key}-${idx}`} fill={row.color || "#3B82F6"} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => formatCurrency(Number(v))} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  return null;
}

export function AnalyticsChartsPanel({ charts }: AnalyticsChartsPanelProps) {
  if (!charts.length) return null;
  return (
    <div className="mt-5 min-w-0 border-t border-blue-100/80 pt-4 dark:border-gray-700/80">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
        Charts
      </p>
      {charts.map((chart) => (
        <ChartCard key={chart.key} chart={chart} />
      ))}
    </div>
  );
}
