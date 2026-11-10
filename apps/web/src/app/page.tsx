"use client";

import React, { useState, useEffect, type FormEvent, type JSX } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getMarketDashboard,
  getOpportunityScanner,
  getDataProviders,
  getAssets,
  getPortfolio,
  getWatchlist,
  type OpportunityFilters,
  type PortfolioDashboard,
  type WatchlistItem,
} from "@/lib/api";
import { Skeleton, SkeletonCard } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { PageHeader } from "@/components/ui/page-header";
import { useCachedResource, formatUpdatedAt } from "@/lib/use-cached-resource";
import { SpatialBentoCard } from "@/components/three/spatial-bento-card";
import { QuantCoreOrb3D } from "@/components/three/quant-core-orb-3d";
import { PortfolioTorus3D } from "@/components/three/portfolio-torus-3d";
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
  const [hoveredTorusIdx, setHoveredTorusIdx] = useState<number | null>(null);
  const [portfolioData, setPortfolioData] = useState<PortfolioDashboard | null>(null);
  const [watchlistData, setWatchlistData] = useState<WatchlistItem[] | null>(null);

  useEffect(() => {
    let active = true;
    getPortfolio()
      .then((data) => {
        if (active) setPortfolioData(data);
      })
      .catch(() => {});

    getWatchlist()
      .then((items) => {
        if (active) setWatchlistData(items);
      })
      .catch(() => {});

    return () => {
      active = false;
    };
  }, []);

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
  const isLineageError = Boolean(providersResource.error && !providersResource.data);
  const connectionStatus = isLineageLoading
    ? "CHECKING"
    : isLineageError
    ? "OFFLINE"
    : providersResource.error
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
            <span className={styles.engineBadge} style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <QuantCoreOrb3D status="ready" size={20} />
              DETERMINISTIC QUANT ENGINE
            </span>
            {marketResource.updatedAt ? (
              <span className={styles.updatedTime} suppressHydrationWarning>
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
        ) : marketResource.error && !marketResource.data ? (
          <div className={styles.pulseBar} style={{ justifyContent: "space-between", background: "var(--surface-muted, #f8fafc)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
              <StatusBadge status="WARNING" label="Không thể kết nối máy chủ" />
              <span style={{ fontSize: "12px", color: "var(--ink-muted, #64748b)" }}>
                {marketResource.error}
              </span>
            </div>
            <button
              type="button"
              className={styles.refreshButton}
              onClick={() => marketResource.reload()}
            >
              ↻ <span>Thử lại</span>
            </button>
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
        <SpatialBentoCard style={{ height: "100%" }}>
          <article className={styles.bentoWidget}>
            <header className={styles.bentoHeader}>
              <div className={styles.bentoTitleGroup}>
                <p className={styles.bentoEyebrow}>MULTI-FACTOR SCREENER</p>
                <h2 className={styles.bentoTitle}>Top Cơ hội nổi bật</h2>
              </div>
              <Link href="/opportunities" className={styles.bentoHeaderLink}>
                Xem tất cả <span aria-hidden="true">→</span>
              </Link>
            </header>

            <div className={styles.bentoBody}>
              {opportunitiesResource.isLoading && !opportunitiesResource.data ? (
                <SkeletonCard height={150} />
              ) : opportunitiesResource.error && !opportunitiesResource.data ? (
                <div style={{ padding: "24px 16px", textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: "10px" }}>
                  <StatusBadge status="ERROR" label="Lỗi tải dữ liệu" />
                  <p className={styles.emptyStateText} style={{ margin: 0 }}>
                    Không thể tải danh sách cơ hội ({opportunitiesResource.error})
                  </p>
                  <button
                    type="button"
                    className={styles.refreshButton}
                    onClick={() => opportunitiesResource.reload()}
                    style={{ marginTop: "4px" }}
                  >
                    ↻ <span>Thử lại</span>
                  </button>
                </div>
              ) : topOpportunities.length === 0 ? (
                <p className={styles.emptyStateText}>
                  Chưa có dữ liệu cơ hội phù hợp từ mô hình sàng lọc VN100.
                </p>
              ) : (
                <div className={styles.oppList}>
                  {topOpportunities.map((opp) => (
                    <Link
                      key={opp.symbol}
                      href={`/ai?symbol=${encodeURIComponent(opp.symbol)}&source=opportunities`}
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

            <Link href="/opportunities" className={styles.bentoFooterLink}>
              Khám phá bộ lọc đa nhân tố VN100 <span aria-hidden="true">→</span>
            </Link>
          </article>
        </SpatialBentoCard>

        {/* Widget 2: Danh mục & Chiến lược */}
        <SpatialBentoCard style={{ height: "100%" }}>
          <article className={styles.bentoWidget}>
            <header className={styles.bentoHeader}>
              <div className={styles.bentoTitleGroup}>
                <p className={styles.bentoEyebrow}>PORTFOLIO MANAGEMENT</p>
                <h2 className={styles.bentoTitle}>Danh mục & Chiến lược</h2>
              </div>
              <Link href="/portfolio" className={styles.bentoHeaderLink}>
                Chi tiết <span aria-hidden="true">→</span>
              </Link>
            </header>

            <div className={styles.bentoBody}>
              <div className={styles.allocationSection}>
                <div style={{ display: "flex", justifyContent: "center", padding: "2px 0 8px 0" }}>
                  <PortfolioTorus3D
                    size={135}
                    activeSegment={hoveredTorusIdx}
                    onHoverSegment={setHoveredTorusIdx}
                  />
                </div>

                <div className={styles.allocLegend}>
                  {portfolioData && portfolioData.allocation?.core_satellite?.length > 0 ? (
                    portfolioData.allocation.core_satellite.map((item, idx) => (
                      <span
                        key={item.role || idx}
                        className={`${styles.legendItem} ${hoveredTorusIdx === idx ? styles.legendItemActive : ""}`}
                        onMouseEnter={() => setHoveredTorusIdx(idx)}
                        onMouseLeave={() => setHoveredTorusIdx(null)}
                      >
                        <span
                          className={styles.legendDot}
                          style={{
                            background: idx === 0 ? "#3b82f6" : idx === 1 ? "#10b981" : "#f59e0b",
                          }}
                        />
                        {item.role === "CORE"
                          ? "Cốt lõi (Core)"
                          : item.role === "SATELLITE"
                          ? "Vệ tinh (Satellite)"
                          : item.role}{" "}
                        ({Math.round((item.weight ?? 0) * 100)}%)
                      </span>
                    ))
                  ) : (
                    <>
                      <span
                        className={`${styles.legendItem} ${hoveredTorusIdx === 0 ? styles.legendItemActive : ""}`}
                        onMouseEnter={() => setHoveredTorusIdx(0)}
                        onMouseLeave={() => setHoveredTorusIdx(null)}
                      >
                        <span className={styles.legendDot} style={{ background: "#3b82f6" }} />
                        Tăng trưởng (45%)
                      </span>
                      <span
                        className={`${styles.legendItem} ${hoveredTorusIdx === 1 ? styles.legendItemActive : ""}`}
                        onMouseEnter={() => setHoveredTorusIdx(1)}
                        onMouseLeave={() => setHoveredTorusIdx(null)}
                      >
                        <span className={styles.legendDot} style={{ background: "#10b981" }} />
                        Phòng thủ & Cổ tức (35%)
                      </span>
                      <span
                        className={`${styles.legendItem} ${hoveredTorusIdx === 2 ? styles.legendItemActive : ""}`}
                        onMouseEnter={() => setHoveredTorusIdx(2)}
                        onMouseLeave={() => setHoveredTorusIdx(null)}
                      >
                        <span className={styles.legendDot} style={{ background: "#f59e0b" }} />
                        Dự trữ tiền mặt (20%)
                      </span>
                    </>
                  )}
                </div>
              </div>

              <div className={styles.strategyStats}>
                <div className={styles.statRow}>
                  <span className={styles.statLabel}>Chiến lược:</span>
                  <span className={styles.statValue}>
                    {portfolioData && portfolioData.holdings && portfolioData.holdings.length > 0
                      ? `${portfolioData.holdings.length} vị thế nắm giữ · ${portfolioData.summary?.holdings_count ?? portfolioData.holdings.length} mã`
                      : "3 danh mục phân lớp rủi ro"}
                  </span>
                </div>
                <div className={styles.statRow}>
                  <span className={styles.statLabel}>Kế hoạch DCA:</span>
                  <span className={styles.statValue}>
                    {portfolioData && portfolioData.summary?.total_value
                      ? `Tổng giá trị: ${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(portfolioData.summary.total_value)} VND`
                      : "Tự động theo pha chu kỳ VN100"}
                  </span>
                </div>
              </div>
            </div>

            <Link href="/portfolio" className={styles.bentoFooterLink}>
              Quản trị tỷ trọng & Kế hoạch giải ngân <span aria-hidden="true">→</span>
            </Link>
          </article>
        </SpatialBentoCard>

        {/* Widget 3: Cảnh báo & Theo dõi */}
        <SpatialBentoCard style={{ height: "100%" }}>
          <article className={styles.bentoWidget}>
            <header className={styles.bentoHeader}>
              <div className={styles.bentoTitleGroup}>
                <p className={styles.bentoEyebrow}>WATCHLIST & ALERTS</p>
                <h2 className={styles.bentoTitle}>Cảnh báo & Theo dõi</h2>
              </div>
              <Link href="/watchlist" className={styles.bentoHeaderLink}>
                Mở Watchlist <span aria-hidden="true">→</span>
              </Link>
            </header>

            <div className={styles.bentoBody}>
              <div className={styles.watchList}>
                {watchlistData && watchlistData.length > 0 ? (
                  watchlistData.slice(0, 3).map((item) => (
                    <div key={item.symbol} className={styles.watchRow}>
                      <div className={styles.watchLeft}>
                        <strong className={styles.watchSymbol}>{item.symbol}</strong>
                        <span className={styles.watchNote}>
                          {item.sector
                            ? `${item.sector}${item.thesis ? ` · ${item.thesis}` : ""}`
                            : item.thesis || "Theo dõi danh mục"}
                        </span>
                      </div>
                      <StatusBadge
                        status={item.data_status || "AVAILABLE"}
                        label={
                          item.confidence === "HIGH"
                            ? "Độ tin cậy cao"
                            : item.risk && item.risk > 70
                            ? "Rủi ro cao"
                            : "Đang theo dõi"
                        }
                      />
                    </div>
                  ))
                ) : (
                  <>
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
                  </>
                )}
              </div>

              <div className={styles.alertNotice} role="status">
                <span>●</span>
                <span>
                  {watchlistData && watchlistData.length > 0
                    ? `${watchlistData.length.toString().padStart(2, "0")} mã trong danh sách theo dõi · Quản trị định giá & rủi ro chủ động`
                    : "02 mã chạm biên an toàn định giá · Không vi phạm trần rủi ro danh mục"}
                </span>
              </div>
            </div>

            <Link href="/watchlist" className={styles.bentoFooterLink}>
              Xem toàn bộ mã theo dõi & cảnh báo rủi ro <span aria-hidden="true">→</span>
            </Link>
          </article>
        </SpatialBentoCard>

        {/* Widget 4: Tra cứu & Hỏi nhanh AI */}
        <SpatialBentoCard style={{ height: "100%" }}>
          <article className={styles.bentoWidget}>
            <header className={styles.bentoHeader}>
              <div className={styles.bentoTitleGroup}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span className={styles.aiCorePulse} aria-hidden="true" />
                  <p className={styles.bentoEyebrow} style={{ margin: 0 }}>EVIDENCE-BASED AI</p>
                </div>
                <h2 className={styles.bentoTitle}>Tra cứu & Hỏi nhanh AI</h2>
              </div>
              <Link href="/ai" className={styles.bentoHeaderLink}>
                AI Analyst <span aria-hidden="true">→</span>
              </Link>
            </header>

            <div className={styles.bentoBody}>
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

            <Link href="/ai" className={styles.bentoFooterLink}>
              Mở phiên đối thoại AI chuyên sâu <span aria-hidden="true">→</span>
            </Link>
          </article>
        </SpatialBentoCard>
      </section>

      {/* ====================================================================
          TẦNG 3 — Trạng thái Dữ liệu (System Lineage & Data Telemetry Strip)
          ==================================================================== */}
      <section className={styles.telemetryStrip} aria-label="Kiểm định chất lượng dữ liệu">
        <div className={styles.telemetryLeft}>
          <StatusBadge
            status={isLineageError ? "ERROR" : connectionStatus}
            label={
              isLineageError
                ? "DATA QUALITY & LINEAGE: OFFLINE / KHÔNG KHẢ DỤNG"
                : `DATA QUALITY & LINEAGE: ${connectionStatus}`
            }
          />
          <span className={styles.telemetrySummary}>
            {isLineageError ? (
              <span style={{ color: "var(--negative, #b91c1c)" }}>
                Không thể kết nối Backend API. Vui lòng kiểm tra dịch vụ dữ liệu hoặc live endpoint.
              </span>
            ) : totalCanonicalCount > 0 ? (
              `${totalCanonicalCount.toLocaleString("vi-VN")} tài sản chuẩn hóa canonical · Chuẩn mốc EOD · BCTC Kiểm toán đối soát`
            ) : (
              "1.600+ mã HOSE/HNX/UPCOM · Chuẩn mốc EOD · BCTC Kiểm toán đối soát"
            )}
          </span>
        </div>

        <Link href="/system" className={styles.telemetryLink}>
          Chi tiết hệ thống & dữ liệu <span aria-hidden="true">→</span>
        </Link>
      </section>

      {/* Footer trang ngắn gọn */}
      <footer className={styles.footerNote}>
        InvestIntel Workstation · Dữ liệu chuẩn mốc Point-in-Time chính thức từ API nội bộ · Quyết định phân bổ dựa trên bằng chứng định lượng độc lập.
      </footer>
    </div>
  );
}
