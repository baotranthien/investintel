"use client";

import React from "react";
import Link from "next/link";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  AIChartSpec,
  AIComparisonTable,
  AIDocumentHighlight,
  AIQuickAction,
  AIStructuredDataSummary,
} from "@/lib/api";
import { useLocale, type AppLocale } from "@/lib/i18n";
import styles from "./ai-rich-cards.module.css";

interface AIRichCardsProps {
  summary: AIStructuredDataSummary;
}

function formatTooltipNum(val: unknown, unit?: string, locale: AppLocale = "vi"): string {
  if (typeof val !== "number" || Number.isNaN(val)) {
    return String(val ?? "N/A");
  }
  const numLocale = locale === "en" ? "en-US" : "vi-VN";
  const formatted =
    Math.abs(val) >= 1000
      ? val.toLocaleString(numLocale, { maximumFractionDigits: 0 })
      : val.toLocaleString(numLocale, { maximumFractionDigits: 2 });
  return unit ? `${formatted} ${unit}` : formatted;
}

function formatAxisCompact(val: number): string {
  if (Math.abs(val) >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
  if (Math.abs(val) >= 1_000) return `${(val / 1_000).toFixed(0)}k`;
  return String(val);
}

const VALUATION_BAR_COLORS: Record<string, string> = {
  spot: "#94A3B8",
  bear: "#F59E0B",
  base: "#10B981",
  bull: "#3B82F6",
};

const TOOLTIP_CONTENT_STYLE: React.CSSProperties = {
  backgroundColor: "var(--surface)",
  color: "var(--ink)",
  borderRadius: 10,
  border: "1px solid var(--line-strong)",
  fontSize: 12,
  boxShadow: "var(--shadow-sm)",
};

function renderChartCard(chart: AIChartSpec, locale: AppLocale = "vi") {
  if (!chart.data || chart.data.length === 0) return null;
  const isEn = locale === "en";
  const chartIdSafe = chart.id.replace(/[^a-zA-Z0-9_-]/g, "");

  return (
    <div key={chart.id} className={styles.chartCard}>
      <div className={styles.chartCardHeader}>
        <span className={styles.chartTitle}>{chart.title}</span>
        {chart.unit && <span className={styles.chartUnitPill}>{chart.unit}</span>}
      </div>

      <div className={styles.chartCanvasWrap}>
        <ResponsiveContainer width="100%" height="100%">
          {chart.type === "area" ? (
            <AreaChart data={chart.data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id={`grad-${chartIdSafe}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10B981" stopOpacity={0.28} />
                  <stop offset="95%" stopColor="#10B981" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10.5, fill: "var(--ink-muted)" }}
                axisLine={false}
                tickLine={false}
                minTickGap={18}
              />
              <YAxis
                tickFormatter={formatAxisCompact}
                tick={{ fontSize: 10.5, fill: "var(--ink-muted)" }}
                axisLine={false}
                tickLine={false}
                width={44}
                domain={["auto", "auto"]}
              />
              <Tooltip
                formatter={(val) => [
                  formatTooltipNum(val, chart.unit, locale),
                  isEn ? "Closing Price" : "Giá đóng cửa",
                ]}
                contentStyle={TOOLTIP_CONTENT_STYLE}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#10B981"
                strokeWidth={2}
                fill={`url(#grad-${chartIdSafe})`}
                isAnimationActive={false}
              />
            </AreaChart>
          ) : chart.type === "valuation_range" ? (
            <BarChart data={chart.data} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--ink-secondary)" }} axisLine={false} tickLine={false} />
              <YAxis
                tickFormatter={formatAxisCompact}
                tick={{ fontSize: 10.5, fill: "var(--ink-muted)" }}
                axisLine={false}
                tickLine={false}
                width={46}
              />
              <Tooltip
                formatter={(val) => [
                  formatTooltipNum(val, chart.unit, locale),
                  isEn ? "Fair Value" : "Giá trị",
                ]}
                contentStyle={TOOLTIP_CONTENT_STYLE}
              />
              {typeof chart.current_price === "number" && chart.current_price > 0 && (
                <ReferenceLine
                  y={chart.current_price}
                  stroke="var(--ink-secondary)"
                  strokeDasharray="4 4"
                  strokeOpacity={0.65}
                />
              )}
              <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={44} isAnimationActive={false}>
                {chart.data.map((entry, idx) => (
                  <Cell
                    key={`cell-${idx}`}
                    fill={VALUATION_BAR_COLORS[entry.kind || "base"] || "#3B82F6"}
                  />
                ))}
              </Bar>
            </BarChart>
          ) : chart.type === "grouped_bar" ? (
            <BarChart data={chart.data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 10.5, fill: "var(--ink-muted)" }} axisLine={false} tickLine={false} />
              <YAxis
                tickFormatter={formatAxisCompact}
                tick={{ fontSize: 10.5, fill: "var(--ink-muted)" }}
                axisLine={false}
                tickLine={false}
                width={44}
              />
              <Tooltip
                formatter={(val, name) => [
                  formatTooltipNum(val, chart.unit, locale),
                  name === "revenue"
                    ? (isEn ? "Revenue" : "Doanh thu")
                    : (isEn ? "Net Income" : "LN ròng"),
                ]}
                contentStyle={TOOLTIP_CONTENT_STYLE}
              />
              <Bar dataKey="revenue" name="revenue" fill="#38BDF8" radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
              <Bar dataKey="net_income" name="net_income" fill="#10B981" radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
            </BarChart>
          ) : (
            <BarChart data={chart.data} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 10.5, fill: "var(--ink-secondary)" }} axisLine={false} tickLine={false} />
              <YAxis
                tickFormatter={(val: number) =>
                  chart.unit ? `${formatAxisCompact(val)}${chart.unit}` : formatAxisCompact(val)
                }
                tick={{ fontSize: 10.5, fill: "var(--ink-muted)" }}
                axisLine={false}
                tickLine={false}
                width={42}
              />
              <Tooltip
                formatter={(val, name, item) => [
                  formatTooltipNum(
                    val,
                    (item?.payload as { unit?: string } | undefined)?.unit || chart.unit,
                    locale
                  ),
                  name === "a"
                    ? chart.symbols?.[0] || (isEn ? "Symbol A" : "Mã A")
                    : chart.symbols?.[1] || (isEn ? "Benchmark" : "Đối chứng"),
                ]}
                contentStyle={TOOLTIP_CONTENT_STYLE}
              />
              <Bar dataKey="a" name="a" fill="#10B981" radius={[4, 4, 0, 0]} maxBarSize={22} isAnimationActive={false} />
              <Bar dataKey="b" name="b" fill="#3B82F6" radius={[4, 4, 0, 0]} maxBarSize={22} isAnimationActive={false} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function AIRichCards({ summary }: AIRichCardsProps) {
  const { locale, t } = useLocale();
  const numLocale = locale === "en" ? "en-US" : "vi-VN";

  const charts = Array.isArray(summary.charts) ? (summary.charts as AIChartSpec[]) : [];
  const comparisonTable = summary.comparison_table as AIComparisonTable | null | undefined;
  const docHighlights = Array.isArray(summary.document_highlights)
    ? (summary.document_highlights as AIDocumentHighlight[])
    : [];
  const quickActions = Array.isArray(summary.quick_actions)
    ? (summary.quick_actions as AIQuickAction[])
    : [];

  if (
    charts.length === 0 &&
    (!comparisonTable || comparisonTable.rows.length === 0) &&
    docHighlights.length === 0 &&
    quickActions.length === 0
  ) {
    return null;
  }

  const ragMode = docHighlights[0]?.retrieval_mode || null;

  return (
    <div className={styles.richContainer}>
      {quickActions.length > 0 && (
        <div className={styles.actionsBar} aria-label={t("Điều hướng nhanh", "Quick navigation")}>
          {quickActions.map((act) => (
            <Link key={`${act.kind}-${act.href}`} href={act.href} className={styles.actionPill}>
              <span
                className={`${styles.actionKindDot} ${
                  act.kind === "valuation"
                    ? styles.actionKindValuation
                    : act.kind === "watchlist"
                    ? styles.actionKindWatchlist
                    : ""
                }`}
              />
              <span>{act.label}</span>
              <span aria-hidden="true">→</span>
            </Link>
          ))}
        </div>
      )}

      {charts.length > 0 && (
        <div className={styles.chartsGrid}>{charts.map((c) => renderChartCard(c, locale))}</div>
      )}

      {comparisonTable && comparisonTable.rows.length > 0 && comparisonTable.symbols.length >= 2 && (
        <div className={styles.tableCard}>
          <table className={styles.specTable}>
            <thead>
              <tr>
                <th>{t("Chỉ tiêu đối sánh", "Comparative Metric")}</th>
                {comparisonTable.symbols.map((sym) => (
                  <th key={sym} className={styles.numCol}>
                    {sym}
                  </th>
                ))}
                <th className={styles.numCol}>{t("Chênh lệch", "Variance")}</th>
              </tr>
            </thead>
            <tbody>
              {comparisonTable.rows.map((row) => (
                <tr key={row.metric}>
                  <td className={styles.specLabel}>
                    {row.label} {row.unit ? `(${row.unit})` : ""}
                  </td>
                  {comparisonTable.symbols.map((sym) => {
                    const val = row.values[sym];
                    return (
                      <td key={sym} className={styles.numCol}>
                        {val !== null && val !== undefined
                          ? val.toLocaleString(numLocale, { maximumFractionDigits: 2 })
                          : "—"}
                      </td>
                    );
                  })}
                  <td
                    className={`${styles.numCol} ${
                      typeof row.diff === "number"
                        ? row.diff >= 0
                          ? styles.diffPos
                          : styles.diffNeg
                        : ""
                    }`}
                  >
                    {typeof row.diff === "number"
                      ? `${row.diff >= 0 ? "+" : ""}${row.diff.toLocaleString(numLocale, { maximumFractionDigits: 2 })}`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {docHighlights.length > 0 && (
        <section className={styles.docsSection}>
          <div className={styles.docsHeader}>
            <span className={styles.docsTitle}>
              {t(
                `Trích lục Tài liệu & Nghị quyết (${docHighlights.length})`,
                `Filings & Regulatory Disclosures (${docHighlights.length})`
              )}
            </span>
            {ragMode && (
              <span className={styles.ragModeBadge}>
                {ragMode === "HYBRID_BM25_DENSE" ? "Hybrid BM25 + Vector RRF" : "BM25 Lexical"}
              </span>
            )}
          </div>

          <div className={styles.docsGrid}>
            {docHighlights.map((doc) => (
              <article key={doc.citation_id} className={styles.docCard}>
                <div className={styles.docMetaRow}>
                  {doc.ticker && <span className={styles.docTickerPill}>{doc.ticker}</span>}
                  {doc.page_reference && (
                    <span className={styles.docAnchorPill}>{doc.page_reference}</span>
                  )}
                  {doc.publication_date && (
                    <span className={styles.docAnchorPill}>{doc.publication_date}</span>
                  )}
                  {doc.is_synthetic && (
                    <span className={styles.docSyntheticPill}>
                      {t("Fixture nội bộ", "Internal Fixture")}
                    </span>
                  )}
                </div>
                <div className={styles.docSectionName}>
                  {doc.section || doc.title || doc.document_id}
                </div>
                {doc.chunk_type === "table" ? (
                  <pre className={styles.docTableSnippet}>{doc.snippet}</pre>
                ) : (
                  <p className={styles.docSnippet}>{doc.snippet}</p>
                )}
              </article>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
