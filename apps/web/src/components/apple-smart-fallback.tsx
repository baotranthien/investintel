"use client";

import React from "react";
import styles from "./apple-smart-fallback.module.css";

interface SmartFallbackProps {
  summary?: Record<string, unknown> | null;
  metadataFlags?: Record<string, unknown> | null;
  isFallbackMode?: boolean;
}

interface DiffComparison {
  metric: string;
  symbol_a: string;
  symbol_b: string;
  value_a: number | null;
  value_b: number | null;
  difference: number | null;
  unit?: string;
}

interface PearsonComparison {
  series_x: string;
  series_y: string;
  correlation: number | null;
}

function formatMetricValue(val: number | null | undefined, metric: string): string {
  if (val === null || val === undefined || isNaN(val)) return "N/A";
  const mLower = metric.toLowerCase();
  if (mLower.includes("nim") || mLower.includes("casa") || mLower.includes("npl") || mLower.includes("growth") || mLower.includes("margin") || mLower.includes("tăng trưởng")) {
    return `${(val * 100).toFixed(2)}%`;
  }
  if (mLower.includes("pe") || mLower.includes("pb") || mLower.includes("p/e") || mLower.includes("p/b")) {
    return `${val.toFixed(2)}x`;
  }
  if (Math.abs(val) >= 1_000_000_000) {
    return `${(val / 1_000_000_000).toFixed(2)}B`;
  }
  return val.toLocaleString("vi-VN", { maximumFractionDigits: 2 });
}

export default function AppleSmartFallback({ summary, metadataFlags, isFallbackMode = true }: SmartFallbackProps) {
  if (!summary) return null;

  const comparisons = (summary.comparisons as Record<string, unknown>) || {};
  const symbolsData = (summary.symbols as Record<string, { metrics?: Record<string, unknown>; calculated_indicators?: Record<string, unknown> }>) || {};
  const epsIsEstimate = Boolean(metadataFlags?.eps_is_estimate);

  const diffItems: DiffComparison[] = [];
  let pearsonItem: PearsonComparison | null = null;

  for (const [key, val] of Object.entries(comparisons)) {
    if (!val || typeof val !== "object") continue;
    const v = val as Record<string, unknown>;
    if ("correlation" in v) {
      pearsonItem = {
        series_x: String(v.series_x || "Chuỗi X"),
        series_y: String(v.series_y || "Chuỗi Y"),
        correlation: typeof v.correlation === "number" ? v.correlation : null,
      };
    } else if ("difference" in v || "symbol_a" in v) {
      diffItems.push({
        metric: String(v.metric || key.replace("_diff", "").toUpperCase()),
        symbol_a: String(v.symbol_a || "Tài sản A"),
        symbol_b: String(v.symbol_b || "Tài sản B"),
        value_a: typeof v.value_a === "number" ? v.value_a : null,
        value_b: typeof v.value_b === "number" ? v.value_b : null,
        difference: typeof v.difference === "number" ? v.difference : null,
      });
    }
  }

  return (
    <div className={styles.fallbackContainer}>
      {/* Apple-grade Security Notice Header: Render ONLY when in explicit fallback mode */}
      {isFallbackMode && (
        <div className={styles.banner}>
          <div className={styles.bannerIconWrapper}>
            <span className={styles.bannerIcon}>🛡️</span>
          </div>
          <div className={styles.bannerContent}>
            <div className={styles.bannerHeaderRow}>
              <span className={styles.bannerBadge}>Chế độ Dữ liệu Đối chứng Chuẩn xác</span>
              {epsIsEstimate && (
                <span
                  className={styles.epsEstimatePill}
                  title="Số liệu EPS được tính dựa trên Khối lượng Cổ phiếu Lưu hành Cuối kỳ (theo chuẩn mực IAS 33)"
                >
                  ⓘ EPS ước tính (KLCP cuối kỳ - IAS 33)
                </span>
              )}
            </div>
            <p className={styles.bannerMessage}>
              AI tự động chuyển sang chế độ Dữ liệu Đối chứng Chuẩn xác để đảm bảo an toàn số liệu và ngăn ngừa Hallucination.
            </p>
          </div>
        </div>
      )}

      {/* Bento Grid: Financial Comparisons */}
      {diffItems.length > 0 && (
        <section className={styles.bentoSection}>
          <div className={styles.sectionHeader}>
            <h3>Đối sánh Chỉ số Tài chính (Comparative Metrics)</h3>
            <span className={styles.sectionSub}>Tính toán trực tiếp từ BCTC kiểm toán đã chuẩn hóa</span>
          </div>

          <div className={styles.comparisonsGrid}>
            {diffItems.map((item, idx) => {
              const diffVal = item.difference ?? 0;
              const isPositive = diffVal > 0;
              const maxVal = Math.max(Math.abs(item.value_a ?? 0), Math.abs(item.value_b ?? 0), 0.0001);
              const barAPct = Math.min(100, Math.round(((Math.abs(item.value_a ?? 0)) / maxVal) * 100));
              const barBPct = Math.min(100, Math.round(((Math.abs(item.value_b ?? 0)) / maxVal) * 100));

              return (
                <article key={idx} className={styles.bentoCard}>
                  <div className={styles.cardHeader}>
                    <span className={styles.metricTitle}>{item.metric}</span>
                    <span
                      className={`${styles.deltaBadge} tabular-nums ${
                        isPositive ? styles.deltaPositive : styles.deltaNegative
                      }`}
                    >
                      {isPositive ? "+" : ""}
                      {formatMetricValue(item.difference, item.metric)}
                    </span>
                  </div>

                  <div className={styles.comparisonBars}>
                    {/* Row A */}
                    <div className={styles.entityRow}>
                      <span className={styles.symbolTag}>{item.symbol_a}</span>
                      <div className={styles.barTrack}>
                        <div
                          className={`${styles.barFill} ${styles.barA}`}
                          style={{ width: `${barAPct}%` }}
                        />
                      </div>
                      <span className={`${styles.entityValue} tabular-nums`}>
                        {formatMetricValue(item.value_a, item.metric)}
                      </span>
                    </div>

                    {/* Row B */}
                    <div className={styles.entityRow}>
                      <span className={styles.symbolTag}>{item.symbol_b}</span>
                      <div className={styles.barTrack}>
                        <div
                          className={`${styles.barFill} ${styles.barB}`}
                          style={{ width: `${barBPct}%` }}
                        />
                      </div>
                      <span className={`${styles.entityValue} tabular-nums`}>
                        {formatMetricValue(item.value_b, item.metric)}
                      </span>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}

      {/* Pearson Oil/Macro Correlation Bento Card */}
      {pearsonItem && (
        <section className={styles.bentoSection}>
          <div className={styles.sectionHeader}>
            <h3>Hệ số Tương quan Chuỗi thời gian (Pearson Correlation)</h3>
            <span className={styles.sectionSub}>Kiểm định mức độ phụ thuộc giữa doanh thu và giá hàng hóa vĩ mô</span>
          </div>

          <div className={styles.bentoCard}>
            <div className={styles.pearsonCardContent}>
              <div className={styles.pearsonStat}>
                <span className={styles.pearsonLabel}>Hệ số tương quan r</span>
                <span className={`${styles.pearsonValue} tabular-nums`}>
                  {pearsonItem.correlation !== null ? pearsonItem.correlation.toFixed(4) : "N/A"}
                </span>
                <span className={styles.pearsonStatus}>
                  {pearsonItem.correlation !== null && Math.abs(pearsonItem.correlation) >= 0.7
                    ? "Tương quan mạnh (Strong Correlation)"
                    : pearsonItem.correlation !== null && Math.abs(pearsonItem.correlation) >= 0.4
                    ? "Tương quan trung bình"
                    : "Tương quan yếu hoặc không phụ thuộc"}
                </span>
              </div>

              <div className={styles.pearsonVisual}>
                <div className={styles.seriesLine}>
                  <span className={styles.seriesBullet}>●</span>
                  <span className={styles.seriesName}>{pearsonItem.series_x}</span>
                </div>
                <div className={styles.seriesDivider}>↔</div>
                <div className={styles.seriesLine}>
                  <span className={`${styles.seriesBullet} ${styles.seriesBulletY}`}>●</span>
                  <span className={styles.seriesName}>{pearsonItem.series_y}</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Structured Multi-Symbol Financial Cards */}
      {Object.keys(symbolsData).length > 0 && (
        <section className={styles.bentoSection}>
          <div className={styles.sectionHeader}>
            <h3>Dữ liệu Đối chứng Chuẩn xác (Reference Benchmark Data)</h3>
            <span className={styles.sectionSub}>Dữ liệu chuẩn hóa trích xuất trực tiếp từ Báo cáo Tài chính đối soát độc lập, không phải suy luận AI</span>
          </div>

          <div className={styles.symbolsGrid}>
            {Object.entries(symbolsData).map(([sym, data]) => {
              const allMetrics = { ...(data.metrics || {}), ...(data.calculated_indicators || {}) };
              const metricEntries = Object.entries(allMetrics);
              if (metricEntries.length === 0) return null;

              return (
                <div key={sym} className={styles.bentoCard}>
                  <div className={styles.symbolCardHeader}>
                    <span className={styles.cardSymbolTitle}>{sym}</span>
                    <span className={styles.cardMetricCount}>
                      {metricEntries.length} chỉ số
                    </span>
                  </div>

                  <div className={styles.metricList}>
                    {metricEntries.map(([k, v]) => (
                      <div key={k} className={styles.metricRow}>
                        <span className={styles.metricKey}>
                          {k.replace(/_/g, " ").toUpperCase()}
                        </span>
                        <span className={`${styles.metricVal} tabular-nums`}>
                          {typeof v === "number"
                            ? formatMetricValue(v, k)
                            : typeof v === "object" && v !== null && "value" in v
                            ? formatMetricValue((v as Record<string, unknown>).value as number, k)
                            : String(v ?? "N/A")}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
