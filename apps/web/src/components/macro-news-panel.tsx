"use client";

import React, { useMemo, useState, type JSX } from "react";
import {
  getMacroNewsAnalysis,
  runMacroNewsPipeline,
  type MacroNewsAnalysisResponse,
  type MacroNewsCorrelationEvent,
  type MacroNewsPipelineRunResult,
} from "@/lib/api";
import { useLocale } from "@/lib/i18n";
import { useCachedResource } from "@/lib/use-cached-resource";
import { StatusBadge } from "@/components/ui/status-badge";
import { SkeletonCard } from "@/components/ui/skeleton";
import styles from "./macro-news-panel.module.css";

type FilterMode = "all" | "approved" | "needs_review";

function formatPct(value: number | null | undefined, digits = 2, signed = true): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  const num = Number(value);
  const sign = signed && num > 0 ? "+" : "";
  return `${sign}${num.toFixed(digits)}%`;
}

function tierBadgeClass(tier: number): string {
  if (tier === 1) return styles.tier1;
  if (tier === 2) return styles.tier2;
  return styles.tier3;
}

function tierLabel(tier: number, isEn: boolean): string {
  if (tier === 1) return isEn ? "Tier 1 · Gov" : "Tier 1 · Chính phủ";
  if (tier === 2) return isEn ? "Tier 2 · Macro" : "Tier 2 · Vĩ mô sâu";
  return isEn ? "Tier 3 · Market Press" : "Tier 3 · Tài chính";
}

function sentimentMeta(
  sentiment: string,
  isEn: boolean
): { label: string; cls: string } {
  const norm = (sentiment || "").toLowerCase();
  if (norm === "positive") {
    return { label: isEn ? "Bullish / Positive" : "Tích cực", cls: styles.sentimentPositive };
  }
  if (norm === "negative") {
    return { label: isEn ? "Bearish / Negative" : "Tiêu cực", cls: styles.sentimentNegative };
  }
  return { label: isEn ? "Mixed / Neutral" : "Trung lập / Phân hóa", cls: styles.sentimentNeutral };
}

export function MacroNewsPanel({
  compact = false,
  onAskAboutEvent,
}: {
  compact?: boolean;
  onAskAboutEvent?: (question: string, primarySymbol?: string) => void;
}): JSX.Element {
  const { locale, t } = useLocale();
  const isEn = locale === "en";
  const [filterMode, setFilterMode] = useState<FilterMode>("all");
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<MacroNewsPipelineRunResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const newsRes = useCachedResource<MacroNewsAnalysisResponse>(
    "macro-news-analysis-all-v1",
    (signal) => getMacroNewsAnalysis(false, 24, signal),
    { maxAgeMs: 60 * 1000 }
  );

  const serverEvents = newsRes.data?.events;
  const serverCounts = newsRes.data?.counts;
  const events = useMemo(() => serverEvents ?? [], [serverEvents]);
  const counts = useMemo(() => {
    if (serverCounts) {
      return serverCounts;
    }
    const approved = events.filter((e) => e.validation?.approved_for_ai).length;
    return {
      total: events.length,
      approved,
      needs_review: Math.max(0, events.length - approved),
    };
  }, [events, serverCounts]);

  const filteredEvents = useMemo(() => {
    if (filterMode === "approved") {
      return events.filter((e) => e.validation?.approved_for_ai);
    }
    if (filterMode === "needs_review") {
      return events.filter((e) => !e.validation?.approved_for_ai);
    }
    return events;
  }, [events, filterMode]);

  async function handleRunPipeline() {
    setRunning(true);
    setRunError(null);
    try {
      const res = await runMacroNewsPipeline(true, true);
      setRunResult(res);
      newsRes.reload();
    } catch (err) {
      setRunError(
        err instanceof Error
          ? err.message
          : t("Không thể chạy pipeline tin vĩ mô 17:30.", "Failed to execute 17:30 macro news pipeline.")
      );
    } finally {
      setRunning(false);
    }
  }

  function handleAskClick(ev: MacroNewsCorrelationEvent) {
    if (!onAskAboutEvent) return;
    const primarySym = ev.stock_market_correlation.affected_symbols?.[0] || "VN100";
    const prompt = isEn
      ? `Analyze how the validated macro event "${ev.title}" (${ev.source_domain}, Trust ${ev.source_trust_level}/10) impacts ${primarySym} and related sectors.`
      : `Phân tích tác động của tin vĩ mô 17:30 đã kiểm chứng "${ev.title}" (${ev.source_domain}, Trust ${ev.source_trust_level}/10) tới cổ phiếu ${primarySym} và các nhóm ngành liên quan.`;
    onAskAboutEvent(prompt, primarySym === "VN100" ? "" : primarySym);
  }

  return (
    <section
      className={`${styles.panel}${compact ? ` ${styles.compactPanel}` : ""}`}
      aria-label={t("Tin Vĩ Mô 17:30 & Kiểm Chứng Backtest", "17:30 Macro News & Backtest Validation")}
    >
      <header className={styles.header}>
        <div className={styles.titleGroup}>
          <div className={styles.titleRow}>
            <h3 className={styles.title}>
              {t(
                "Tin Vĩ Mô 17:30 & Kiểm Chứng Backtest (Pillar 7)",
                "17:30 ICT Official Macro News & Backtest Validation"
              )}
            </h3>
            <span className={styles.schedulePill}>
              17:30 ICT · {newsRes.data?.date || "Latest"}
            </span>
            <StatusBadge
              status={counts.approved > 0 ? "APPROVED" : "NEEDS_REVIEW"}
              label={
                counts.approved > 0
                  ? t(`${counts.approved} Tin Đã Duyệt AI`, `${counts.approved} Approved for AI`)
                  : t("Đang rà soát", "Pending Validation")
              }
            />
          </div>
          <p className={styles.subtitle}>
            {t(
              "Tổng hợp tự động 3 nhóm nguồn chính thống (NHNN/GSO/BTC, VnEconomy/Đầu tư, CafeF/Vietstock) → Trích xuất tương quan Gemini JSON → Đối chiếu lịch sử VN100 T+1/T+5 trước khi đưa vào AI.",
              "Automated 3-tier official crawl (Gov Portals, Deep Macro, Financial Press) → Gemini structured JSON correlation → Server-side VN100 T+1/T+5 historical backtest gate."
            )}
          </p>
        </div>

        <div className={styles.actions}>
          <button
            type="button"
            className={styles.refreshBtn}
            onClick={() => newsRes.reload()}
            disabled={newsRes.isRevalidating || running}
          >
            {newsRes.isRevalidating ? t("Đang tải...", "Refreshing...") : t("↻ Làm mới", "↻ Refresh")}
          </button>
          <button
            type="button"
            className={styles.runBtn}
            onClick={handleRunPipeline}
            disabled={running}
          >
            {running
              ? t("Đang quét & kiểm chứng...", "Crawling & Validating...")
              : t("⚡ Quét tin 17:30 & Backtest", "⚡ Run 17:30 Scan & Backtest")}
          </button>
        </div>
      </header>

      {runResult && (
        <div className={styles.runBanner}>
          {t(
            `Đã hoàn tất quét ngày ${runResult.date}: thu thập ${runResult.crawled_count} bài, ${runResult.approved_count} tin Đạt Duyệt (Approved), ${runResult.needs_review_count} tin Cần rà soát (${runResult.gemini_used ? `Gemini: ${runResult.gemini_model || "enabled"}` : "Rule fallback"}).`,
            `Scan completed for ${runResult.date}: crawled ${runResult.crawled_count} articles, ${runResult.approved_count} Approved, ${runResult.needs_review_count} Needs Review (${runResult.gemini_used ? `Gemini: ${runResult.gemini_model || "enabled"}` : "Deterministic extraction"}).`
          )}
        </div>
      )}

      {runError && <div className={styles.runBannerError}>{runError}</div>}

      <div className={styles.toolbar}>
        <div className={styles.filterGroup} role="tablist" aria-label={t("Lọc trạng thái kiểm chứng", "Validation filter")}>
          <button
            type="button"
            role="tab"
            aria-selected={filterMode === "all"}
            className={`${styles.filterTab} ${filterMode === "all" ? styles.filterTabActive : ""}`}
            onClick={() => setFilterMode("all")}
          >
            {t(`Tất cả (${counts.total})`, `All (${counts.total})`)}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={filterMode === "approved"}
            className={`${styles.filterTab} ${filterMode === "approved" ? styles.filterTabActive : ""}`}
            onClick={() => setFilterMode("approved")}
          >
            {t(`Đã duyệt AI (${counts.approved})`, `Approved (${counts.approved})`)}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={filterMode === "needs_review"}
            className={`${styles.filterTab} ${filterMode === "needs_review" ? styles.filterTabActive : ""}`}
            onClick={() => setFilterMode("needs_review")}
          >
            {t(`Cần rà soát (${counts.needs_review})`, `Needs Review (${counts.needs_review})`)}
          </button>
        </div>

        <div className={styles.tierLegend}>
          <span>{t("Tier 1: Cổng NN (10/10)", "Tier 1: Gov (10/10)")}</span>
          <span>·</span>
          <span>{t("Tier 2: Vĩ mô sâu (8/10)", "Tier 2: Macro (8/10)")}</span>
          <span>·</span>
          <span>{t("Tier 3: Chứng khoán (6–7/10)", "Tier 3: Press (6–7/10)")}</span>
        </div>
      </div>

      {newsRes.isLoading && events.length === 0 ? (
        <div className={styles.skeletonGrid}>
          <SkeletonCard height={180} />
          <SkeletonCard height={180} />
        </div>
      ) : newsRes.error && events.length === 0 ? (
        <div className={styles.emptyBox}>
          <StatusBadge status="ERROR" label={t("Lỗi tải log 17:30", "17:30 Log Load Error")} />
          <span>{newsRes.error}</span>
          <button type="button" className={styles.refreshBtn} onClick={() => newsRes.reload()}>
            {t("↻ Thử lại", "↻ Retry")}
          </button>
        </div>
      ) : filteredEvents.length === 0 ? (
        <div className={styles.emptyBox}>
          <StatusBadge status="NEEDS_REVIEW" />
          <span>
            {t(
              "Không có sự kiện nào trong bộ lọc hiện tại. Bấm 'Quét tin 17:30 & Backtest' để thu thập và kiểm chứng mới.",
              "No events match the selected filter. Click 'Run 17:30 Scan & Backtest' to collect and validate fresh official news."
            )}
          </span>
        </div>
      ) : (
        <div className={styles.eventsGrid}>
          {filteredEvents.map((ev) => {
            const sMeta = sentimentMeta(ev.stock_market_correlation?.sentiment, isEn);
            const hitPct =
              ev.validation?.historical_hit_rate !== null &&
              ev.validation?.historical_hit_rate !== undefined
                ? ev.validation.historical_hit_rate * 100
                : null;
            const confPct = (ev.ai_confidence_score ?? 0) * 100;
            const isApproved = Boolean(ev.validation?.approved_for_ai);

            return (
              <article
                key={ev.id}
                className={`${styles.eventCard} ${isApproved ? styles.eventCardApproved : styles.eventCardReview}`}
              >
                <div className={styles.cardTop}>
                  <div className={styles.sourceBadges}>
                    <span className={`${styles.tierBadge} ${tierBadgeClass(ev.source_tier)}`}>
                      {tierLabel(ev.source_tier, isEn)}
                    </span>
                    <span className={styles.domainTag}>{ev.source_domain}</span>
                    <span className={styles.trustTag}>Trust {ev.source_trust_level}/10</span>
                  </div>
                  <StatusBadge status={ev.validation?.status || "PENDING"} />
                </div>

                <a
                  href={ev.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.eventTitleLink}
                >
                  {ev.title} ↗
                </a>

                <div className={styles.correlationRow}>
                  <span className={`${styles.sentimentChip} ${sMeta.cls}`}>{sMeta.label}</span>
                  <span className={styles.typeChip}>
                    {ev.stock_market_correlation?.type === "indirect"
                      ? t("Tác động gián tiếp", "Indirect")
                      : t("Tác động trực tiếp", "Direct")}
                  </span>
                  {ev.date && <span className={styles.domainTag}>{ev.date}</span>}
                </div>

                <p className={styles.impactText}>
                  <strong>{t("Tác động vĩ mô:", "Macro impact:")}</strong> {ev.macro_impact}
                </p>

                <p className={styles.analysisText}>
                  {ev.stock_market_correlation?.analysis}
                </p>

                {(ev.stock_market_correlation?.affected_sectors?.length > 0 ||
                  ev.stock_market_correlation?.affected_symbols?.length > 0) && (
                  <div className={styles.chipsWrap}>
                    {ev.stock_market_correlation.affected_sectors?.map((sec) => (
                      <span key={sec} className={styles.sectorChip}>
                        {sec}
                      </span>
                    ))}
                    {ev.stock_market_correlation.affected_symbols?.map((sym) => (
                      <span key={sym} className={styles.symbolChip}>
                        {sym}
                      </span>
                    ))}
                  </div>
                )}

                <div className={styles.metricsStrip}>
                  <div className={styles.metricCell}>
                    <span className={styles.metricLabel}>Gemini Conf</span>
                    <span className={styles.metricVal}>{confPct.toFixed(0)}%</span>
                  </div>
                  <div className={styles.metricCell}>
                    <span className={styles.metricLabel}>Backtest Hit</span>
                    <span
                      className={`${styles.metricVal} ${
                        hitPct !== null && hitPct >= 50 ? styles.metricPositive : styles.metricNegative
                      }`}
                    >
                      {hitPct !== null ? `${hitPct.toFixed(1)}%` : "—"} (n={ev.validation?.sample_size ?? 0})
                    </span>
                  </div>
                  <div className={styles.metricCell}>
                    <span className={styles.metricLabel}>T+1 Avg</span>
                    <span
                      className={`${styles.metricVal} ${
                        (ev.validation?.avg_1d_return_pct ?? 0) >= 0
                          ? styles.metricPositive
                          : styles.metricNegative
                      }`}
                    >
                      {formatPct(ev.validation?.avg_1d_return_pct)}
                    </span>
                  </div>
                  <div className={styles.metricCell}>
                    <span className={styles.metricLabel}>T+5 Avg</span>
                    <span
                      className={`${styles.metricVal} ${
                        (ev.validation?.avg_5d_return_pct ?? 0) >= 0
                          ? styles.metricPositive
                          : styles.metricNegative
                      }`}
                    >
                      {formatPct(ev.validation?.avg_5d_return_pct)}
                    </span>
                  </div>
                </div>

                {ev.validation?.notes && (
                  <p className={styles.validationNote}>
                    <strong>{t("Kiểm chứng:", "Validation:")}</strong> {ev.validation.notes}
                  </p>
                )}

                <div className={styles.cardFooter}>
                  <details className={styles.jsonDetails}>
                    <summary>
                      {t("Xem JSON Gemini & Validation", "Inspect Gemini JSON & Backtest")}
                    </summary>
                    <pre className={styles.jsonPre}>
                      {JSON.stringify(
                        ev.raw_gemini_json || {
                          title: ev.title,
                          url: ev.url,
                          source_trust_level: ev.source_trust_level,
                          macro_impact: ev.macro_impact,
                          stock_market_correlation: ev.stock_market_correlation,
                          ai_confidence_score: ev.ai_confidence_score,
                          validation: ev.validation,
                        },
                        null,
                        2
                      )}
                    </pre>
                  </details>

                  {onAskAboutEvent && (
                    <button
                      type="button"
                      className={styles.askBtn}
                      onClick={() => handleAskClick(ev)}
                    >
                      {t("✦ Hỏi AI về sự kiện này", "✦ Ask AI about this event")}
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
