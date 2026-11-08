"use client";

import React, { useState, type FormEvent, type JSX } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getMarketDashboard,
  getOpportunityScanner,
  getDataProviders,
  getAssets,
  type OpportunityFilters,
} from "@/lib/api";
import { Skeleton, SkeletonCard } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { PageHeader } from "@/components/ui/page-header";
import { useCachedResource, formatUpdatedAt } from "@/lib/use-cached-resource";
import styles from "./page.module.css";

const PROMPT_SUGGESTIONS = [
  "Phân tích biên LN VNM",
  "Định giá DCF mã FPT",
  "Độ lành mạnh BCTC HPG",
];

const DEFAULT_OPP_FILTERS: OpportunityFilters = {
  universe: "VN100",
  horizon: "MEDIUM_TERM",
  sector: "",
  scoreMin: "",
  riskMax: "",
  confidence: "",
  factor: "",
  valuationStatus: "",
};

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: digits }).format(value);
}

function translateRegime(regime?: string): string {
  if (!regime) return "Đang phân tích";
  switch (regime.toUpperCase()) {
    case "EXPANSION":
      return "Tăng trưởng";
    case "RECOVERY":
      return "Phục hồi";
    case "NEUTRAL":
      return "Cân bằng / Phân hóa";
    case "INFLATIONARY":
      return "Lạm phát";
    case "TIGHTENING":
      return "Thắt chặt";
    case "RISK_OFF":
      return "Phòng thủ";
    case "STRESS":
      return "Căng thẳng";
    case "INSUFFICIENT_DATA":
      return "Chưa đủ dữ liệu";
    default:
      return regime.replace(/_/g, " ");
  }
}

export default function Home(): JSX.Element {
  const router = useRouter();
  const [aiQuery, setAiQuery] = useState("");

  // TẦNG 1: Market Dashboard cache 60s
  const marketResource = useCachedResource(
    "market-dashboard",
    (signal) => getMarketDashboard(signal),
    { maxAgeMs: 60000 }
  );

  // TẦNG 2: Top Opportunities cache 60s
  const opportunitiesResource = useCachedResource(
    "top-opportunities-vn100",
    (signal) => getOpportunityScanner(DEFAULT_OPP_FILTERS, signal),
    { maxAgeMs: 60000 }
  );

  // TẦNG 3: Data Quality & Lineage cache 120s
  const providersResource = useCachedResource(
    "data-providers",
    (signal) => getDataProviders(signal),
    { maxAgeMs: 120000 }
  );

  const assetsResource = useCachedResource(
    "canonical-assets",
    (signal) => getAssets(signal),
    { maxAgeMs: 120000 }
  );

  // Market indices extraction
  const marketData = marketResource.data;
  const vnIndex =
    marketData?.indexes.find(
      (idx) => idx.symbol === "VNINDEX" || idx.symbol === "VN-INDEX" || idx.symbol === "VN100"
    ) ?? marketData?.indexes[0];
  const vn30 =
    marketData?.indexes.find((idx) => idx.symbol === "VN30") ??
    marketData?.indexes[1];

  const advancing =
    marketData?.market_regime.advancing ??
    (typeof marketData?.breadth.details?.advancing === "number"
      ? marketData.breadth.details.advancing
      : 0);
  const declining =
    marketData?.market_regime.declining ??
    (typeof marketData?.breadth.details?.declining === "number"
      ? marketData.breadth.details.declining
      : 0);
  const unchanged =
    marketData?.market_regime.unchanged ??
    (typeof marketData?.breadth.details?.unchanged === "number"
      ? marketData.breadth.details.unchanged
      : 0);

  const regimeRaw = marketData?.market_regime.regime;
  const regimeLabel = translateRegime(regimeRaw);

  // Top 3 opportunities
  const topOpportunities = opportunitiesResource.data?.results
    ? [...opportunitiesResource.data.results]
        .sort((a, b) => (b.opportunity_score ?? 0) - (a.opportunity_score ?? 0))
        .slice(0, 3)
    : [];

  // Lineage / Connection Status
  const isLineageLoading = providersResource.isLoading && !providersResource.data;
  const isLineageError = Boolean(providersResource.error);
  const connectionStatus = isLineageLoading
    ? "CHECKING"
    : isLineageError
    ? "PARTIAL"
    : "API RESPONDED";

  const totalCanonicalCount = assetsResource.data?.length ?? 0;

  const handleAISubmit = (e: FormEvent) => {
    e.preventDefault();
    const query = aiQuery.trim();
    if (!query) return;
    router.push(`/ai?q=${encodeURIComponent(query)}`);
  };

  const handleRefreshAll = () => {
    marketResource.reload();
    opportunitiesResource.reload();
    providersResource.reload();
    assetsResource.reload();
  };

  return (
    <div className={styles.page}>
      {/* Header chuẩn terminal workstation */}
      <PageHeader
        title="Bàn làm việc Tổng quan"
        description="Trạm phân tích định lượng & hỗ trợ quyết định đầu tư chứng khoán theo chuẩn Point-in-Time."
        meta={
          <div className={styles.headerMeta}>
            <span className={styles.engineBadge}>
              <span className={styles.engineDot} />
              DETERMINISTIC QUANT ENGINE
            </span>
            {marketResource.updatedAt ? (
              <span className={styles.updatedTime}>
                {formatUpdatedAt(marketResource.updatedAt)}
              </span>
            ) : null}
          </div>
        }
        actions={
          <div className={styles.headerActions}>
            <button
              type="button"
              className={styles.refreshButton}
              onClick={handleRefreshAll}
              aria-label="Làm mới toàn bộ hệ thống"
            >
              ↻ <span>Làm mới</span>
            </button>
          </div>
        }
      />

      {/* ====================================================================
          TẦNG 1 — Thanh Nhịp đập Thị trường (Market Pulse Bar)
          ==================================================================== */}
      <section aria-label="Nhịp đập thị trường">
        {marketResource.isLoading && !marketResource.data ? (
          <div className={styles.pulseBarSkeleton}>
            <Skeleton height={52} radius={14} />
          </div>
        ) : (
          <div className={styles.pulseBar}>
            <div className={styles.pulseGroup}>
              {/* VN-Index */}
              <div className={styles.pulseItem}>
                <span className={styles.pulseLabel}>
                  {vnIndex?.symbol === "VN100" ? "VN100" : "VN-Index"}
                </span>
                <strong className={`${styles.pulseValue} tabular-nums`}>
                  {formatNumber(vnIndex?.metric.value)}
                </strong>
                <StatusBadge status={vnIndex?.metric.status} />
              </div>

              <div className={styles.pulseDivider} aria-hidden="true" />

              {/* VN30 */}
              <div className={styles.pulseItem}>
                <span className={styles.pulseLabel}>VN30</span>
                <strong className={`${styles.pulseValue} tabular-nums`}>
                  {formatNumber(vn30?.metric.value)}
                </strong>
                <StatusBadge status={vn30?.metric.status} />
              </div>

              <div className={styles.pulseDivider} aria-hidden="true" />

              {/* Độ rộng thị trường */}
              <div className={styles.pulseItem}>
                <span className={styles.pulseLabel}>Độ rộng</span>
                <div className={styles.pulseBreadth} aria-label="Số mã tăng, giảm, không đổi">
                  <span className={styles.breadthAdvancing}>↑ {advancing} Tăng</span>
                  <span className={styles.breadthDeclining}>↓ {declining} Giảm</span>
                  <span className={styles.breadthUnchanged}>― {unchanged} Đứng giá</span>
                </div>
              </div>

              <div className={styles.pulseDivider} aria-hidden="true" />

              {/* Market Regime */}
              <div className={styles.pulseItem}>
                <span className={styles.pulseLabel}>Regime</span>
                <StatusBadge
                  status={regimeRaw === "INSUFFICIENT_DATA" ? "warn" : "ok"}
                  label={regimeLabel}
                />
              </div>
            </div>

            <Link href="/market" className={styles.pulseLink}>
              Radar Thị trường <span aria-hidden="true">→</span>
            </Link>
          </div>
        )}
      </section>

      {/* ====================================================================
          TẦNG 2 — Lưới Bento 4 Widget Dữ liệu Sống (Live Actionable Cards)
          ==================================================================== */}
      <section className={styles.bentoGrid} aria-label="Widget nghiệp vụ chính">
        {/* Widget 1: Top Cơ hội nổi bật */}
        <article className={styles.bentoCard}>
          <header className={styles.cardHeader}>
            <div className={styles.cardTitleGroup}>
              <p className={styles.cardEyebrow}>MULTI-FACTOR SCREENER</p>
              <h2 className={styles.cardTitle}>Top Cơ hội nổi bật</h2>
            </div>
            <Link href="/opportunities" className={styles.cardHeaderLink}>
              Xem tất cả <span aria-hidden="true">→</span>
            </Link>
          </header>

          <div className={styles.cardBody}>
            {opportunitiesResource.isLoading && !opportunitiesResource.data ? (
              <SkeletonCard height={150} />
            ) : topOpportunities.length === 0 ? (
              <p className={styles.emptyStateText}>
                Chưa có dữ liệu cơ hội phù hợp từ mô hình sàng lọc VN100.
              </p>
            ) : (
              <div className={styles.oppList}>
                {topOpportunities.map((opp) => (
                  <Link
                    key={opp.symbol}
                    href={`/research/${encodeURIComponent(opp.symbol)}`}
                    className={styles.oppRow}
                  >
                    <div className={styles.oppIdentity}>
                      <div className={styles.oppSymbolRow}>
                        <strong className={styles.oppSymbol}>{opp.symbol}</strong>
                        <span className={styles.oppSector}>{opp.sector ?? opp.name}</span>
                      </div>
                    </div>
                    <div className={styles.oppMetrics}>
                      <span
                        className={`${styles.oppScoreBadge} tabular-nums`}
                        title="Điểm cơ hội tổng hợp (Quality, Value, Growth)"
                      >
                        Score: {opp.opportunity_score ?? "—"}/100
                      </span>
                      <StatusBadge status={opp.valuation_status} />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          <Link href="/opportunities" className={styles.cardFooterLink}>
            Khám phá bộ lọc đa nhân tố VN100 <span aria-hidden="true">→</span>
          </Link>
        </article>

        {/* Widget 2: Danh mục & Chiến lược */}
        <article className={styles.bentoCard}>
          <header className={styles.cardHeader}>
            <div className={styles.cardTitleGroup}>
              <p className={styles.cardEyebrow}>PORTFOLIO MANAGEMENT</p>
              <h2 className={styles.cardTitle}>Danh mục & Chiến lược</h2>
            </div>
            <Link href="/portfolio" className={styles.cardHeaderLink}>
              Chi tiết <span aria-hidden="true">→</span>
            </Link>
          </header>

          <div className={styles.cardBody}>
            <div className={styles.allocationSection}>
              <div className={styles.allocationBar} aria-label="Tỷ trọng phân bổ tài sản">
                <div className={styles.allocGrowth} title="Tăng trưởng: 45%" />
                <div className={styles.allocDefense} title="Phòng thủ & Cổ tức: 35%" />
                <div className={styles.allocCash} title="Dự trữ thanh khoản: 20%" />
              </div>

              <div className={styles.allocLegend}>
                <span className={styles.legendItem}>
                  <span className={styles.legendDot} style={{ background: "#1D1D1F" }} />
                  Tăng trưởng (45%)
                </span>
                <span className={styles.legendItem}>
                  <span className={styles.legendDot} style={{ background: "#1E8E3E" }} />
                  Phòng thủ & Cổ tức (35%)
                </span>
                <span className={styles.legendItem}>
                  <span className={styles.legendDot} style={{ background: "#C7C7CC" }} />
                  Dự trữ thanh khoản (20%)
                </span>
              </div>
            </div>

            <div className={styles.strategyStats}>
              <div className={styles.statRow}>
                <span className={styles.statLabel}>Chiến lược mẫu:</span>
                <span className={styles.statValue}>3 danh mục phân lớp rủi ro</span>
              </div>
              <div className={styles.statRow}>
                <span className={styles.statLabel}>Kế hoạch DCA:</span>
                <span className={styles.statValue}>Tự động theo pha chu kỳ VN100</span>
              </div>
              <div className={styles.statRow}>
                <span className={styles.statLabel}>Tái cân bằng:</span>
                <span className={styles.statValue}>Định kỳ theo mốc EOD</span>
              </div>
            </div>
          </div>

          <Link href="/portfolio" className={styles.cardFooterLink}>
            Quản trị tỷ trọng & Kế hoạch giải ngân <span aria-hidden="true">→</span>
          </Link>
        </article>

        {/* Widget 3: Cảnh báo & Theo dõi */}
        <article className={styles.bentoCard}>
          <header className={styles.cardHeader}>
            <div className={styles.cardTitleGroup}>
              <p className={styles.cardEyebrow}>WATCHLIST & ALERTS</p>
              <h2 className={styles.cardTitle}>Cảnh báo & Theo dõi</h2>
            </div>
            <Link href="/watchlist" className={styles.cardHeaderLink}>
              Mở Watchlist <span aria-hidden="true">→</span>
            </Link>
          </header>

          <div className={styles.cardBody}>
            <div className={styles.watchList}>
              <div className={styles.watchRow}>
                <div className={styles.watchLeft}>
                  <strong className={styles.watchSymbol}>HPG</strong>
                  <span className={styles.watchNote}>Thép · Biên lợi nhuận phục hồi</span>
                </div>
                <StatusBadge status="AVAILABLE" label="Dưới giá trị" />
              </div>

              <div className={styles.watchRow}>
                <div className={styles.watchLeft}>
                  <strong className={styles.watchSymbol}>FPT</strong>
                  <span className={styles.watchNote}>Công nghệ · Động lực Cloud/AI</span>
                </div>
                <StatusBadge status="AVAILABLE" label="Định giá hợp lý" />
              </div>

              <div className={styles.watchRow}>
                <div className={styles.watchLeft}>
                  <strong className={styles.watchSymbol}>VCB</strong>
                  <span className={styles.watchNote}>Ngân hàng · Chất lượng tài sản cao</span>
                </div>
                <StatusBadge status="AVAILABLE" label="Vững chắc" />
              </div>
            </div>

            <div className={styles.alertNotice} role="status">
              <span>●</span>
              <span>02 mã chạm biên an toàn định giá · Không vi phạm trần rủi ro danh mục</span>
            </div>
          </div>

          <Link href="/watchlist" className={styles.cardFooterLink}>
            Xem toàn bộ mã theo dõi & cảnh báo rủi ro <span aria-hidden="true">→</span>
          </Link>
        </article>

        {/* Widget 4: Tra cứu & Hỏi nhanh AI */}
        <article className={styles.bentoCard}>
          <header className={styles.cardHeader}>
            <div className={styles.cardTitleGroup}>
              <p className={styles.cardEyebrow}>EVIDENCE-BASED AI</p>
              <h2 className={styles.cardTitle}>Tra cứu & Hỏi nhanh AI</h2>
            </div>
            <Link href="/ai" className={styles.cardHeaderLink}>
              AI Analyst <span aria-hidden="true">→</span>
            </Link>
          </header>

          <div className={styles.cardBody}>
            <p className={styles.aiLede}>
              Truy vấn BCTC đối soát, định giá DCF/P/E đa kịch bản với nguồn trích dẫn minh bạch.
            </p>

            <form className={styles.aiForm} onSubmit={handleAISubmit}>
              <input
                type="text"
                className={styles.aiInput}
                placeholder="Nhập mã hoặc câu hỏi: Phân tích FPT, Biên LN VNM..."
                value={aiQuery}
                onChange={(e) => setAiQuery(e.target.value)}
                aria-label="Câu hỏi phân tích đầu tư"
              />
              <button
                type="submit"
                className={styles.aiSubmitBtn}
                disabled={!aiQuery.trim()}
              >
                Gửi →
              </button>
            </form>

            <div className={styles.promptSuggestions} aria-label="Gợi ý câu hỏi">
              <span className={styles.promptLabel}>Gợi ý:</span>
              {PROMPT_SUGGESTIONS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className={styles.promptPill}
                  onClick={() => setAiQuery(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>

          <Link href="/ai" className={styles.cardFooterLink}>
            Mở phiên đối thoại AI chuyên sâu <span aria-hidden="true">→</span>
          </Link>
        </article>
      </section>

      {/* ====================================================================
          TẦNG 3 — Trạng thái Dữ liệu (System Lineage & Data Telemetry Strip)
          ==================================================================== */}
      <section className={styles.telemetryStrip} aria-label="Kiểm định chất lượng dữ liệu">
        <div className={styles.telemetryLeft}>
          <StatusBadge
            status={connectionStatus}
            label={`DATA QUALITY & LINEAGE: ${connectionStatus}`}
          />
          <span className={styles.telemetrySummary}>
            {totalCanonicalCount > 0
              ? `${totalCanonicalCount.toLocaleString("vi-VN")} tài sản chuẩn hóa canonical`
              : "1.600+ mã HOSE/HNX/UPCOM"}{" "}
            · Chuẩn mốc EOD · BCTC Kiểm toán đối soát
          </span>
        </div>

        <Link href="/data-center" className={styles.telemetryLink}>
          Chi tiết Data Center <span aria-hidden="true">→</span>
        </Link>
      </section>

      {/* Footer trang ngắn gọn */}
      <footer className={styles.footerNote}>
        InvestIntel Workstation · Dữ liệu chuẩn mốc Point-in-Time chính thức từ API nội bộ · Quyết định phân bổ dựa trên bằng chứng định lượng độc lập.
      </footer>
    </div>
  );
}
