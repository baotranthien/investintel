"use client";

import Link from "next/link";
import React, { type JSX } from "react";
import {
  getLatestMacro,
  getMarketDashboard,
  getOpportunityScanner,
  type MacroLatest,
  type MacroSeriesLatest,
  type MarketDashboard,
  type MarketMetric,
  type OpportunityFilters,
  type OpportunityScanner,
} from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { Skeleton, SkeletonCard, SkeletonText } from "@/components/ui/skeleton";
import { useCachedResource, formatUpdatedAt } from "@/lib/use-cached-resource";
import DimensionalMarketRadar from "@/components/dimensional-market-radar";
import styles from "./page.module.css";

const emptyFilters: OpportunityFilters = {
  universe: "ALL",
  sector: "",
  horizon: "MEDIUM_TERM",
  scoreMin: "",
  riskMax: "",
  confidence: "",
  factor: "",
  valuationStatus: "",
};

function numberText(value: number | null, digits = 2): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: digits }).format(value);
}

function dateText(value: string | null): string {
  if (!value) return "Không có timestamp";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("vi-VN");
}

function formatRegimeName(regime: string | undefined): string {
  if (!regime || regime === "INSUFFICIENT_DATA") return "Chưa đủ dữ liệu tính toán";
  switch (regime) {
    case "BULL_CONFIRMED":
      return "Tăng trưởng xác nhận (Bull Confirmed)";
    case "ACCUMULATION":
      return "Tích lũy & Thu gom (Accumulation)";
    case "DISTRIBUTION":
      return "Phân phối / Rủi ro cao (Distribution)";
    case "BEAR_CONFIRMED":
      return "Xu hướng Giảm (Bear Confirmed)";
    case "HIGH_VOLATILITY":
      return "Biến động mạnh (High Volatility)";
    case "DEFENSIVE":
      return "Phòng thủ & Chọn lọc (Defensive)";
    default:
      return regime.replace(/_/g, " ");
  }
}

function Evidence({ metric }: { metric: MarketMetric }) {
  return (
    <details className={styles.evidence}>
      <summary>Bằng chứng & Nguồn số liệu</summary>
      <dl>
        <div>
          <dt>Loại xác thực</dt>
          <dd>DỮ LIỆU THỰC TẾ (FACT)</dd>
        </div>
        <div>
          <dt>Nguồn cấp</dt>
          <dd>{metric.source ?? "Không có source"}</dd>
        </div>
        <div>
          <dt>Gốc dữ liệu</dt>
          <dd>{metric.data_origin ?? "Không xác định"}</dd>
        </div>
        <div>
          <dt>Kỳ quan sát</dt>
          <dd>{metric.as_of_date ?? "Không có ngày"}</dd>
        </div>
        <div>
          <dt>Thời gian công bố</dt>
          <dd>{dateText(metric.published_at)}</dd>
        </div>
        <div>
          <dt>Thời gian lấy mẫu</dt>
          <dd>{dateText(metric.retrieved_at)}</dd>
        </div>
        {metric.note && (
          <div>
            <dt>Ghi chú</dt>
            <dd>{metric.note}</dd>
          </div>
        )}
      </dl>
    </details>
  );
}

function IndexCard({ item }: { item: MarketDashboard["indexes"][number] }) {
  const cleanId = item.symbol.toLowerCase().replace(/[^a-z0-9]/g, "");
  return (
    <article className={styles.indexCard} id={cleanId}>
      <div className={styles.indexLine}>
        <span className={styles.indexSymbol}>{item.symbol}</span>
        <StatusBadge status={item.metric.status} />
      </div>
      <h2 className={styles.indexName}>{item.name}</h2>
      <strong className={styles.indexValue}>{numberText(item.metric.value)}</strong>
      <p className={styles.indexDate}>
        {item.metric.as_of_date ?? item.metric.note ?? "Dữ liệu phiên hiện tại"}
      </p>
      <Evidence metric={item.metric} />
    </article>
  );
}

function MetricCard({ title, metric }: { title: string; metric: MarketMetric }) {
  const unit =
    metric.unit === "percent_advancing"
      ? "% mã tăng"
      : metric.unit === "percent_20_sessions"
      ? "% / 20 phiên"
      : metric.unit === "VND"
      ? "VNĐ"
      : "";

  return (
    <article className={styles.metric}>
      <div className={styles.metricHeading}>
        <span>{title}</span>
        <StatusBadge status={metric.status} />
      </div>
      <strong className={styles.metricValue}>
        {metric.value === null ? "—" : numberText(metric.value)} <small>{unit}</small>
      </strong>
      <p className={styles.metricDate}>{metric.as_of_date ?? metric.note ?? "Phiên gần nhất"}</p>
      {metric.details?.coverage !== undefined && (
        <div className={styles.breadthDetails}>
          <div className={styles.breadthCounts}>
            <span className={styles.advancingBadge}>↑ {String(metric.details.advancing ?? 0)} tăng</span>
            <span className={styles.decliningBadge}>↓ {String(metric.details.declining ?? 0)} giảm</span>
            {metric.details.unchanged !== undefined && (
              <span className={styles.unchangedBadge}>— {String(metric.details.unchanged)} tham chiếu</span>
            )}
          </div>
          <p className={styles.coverageText}>
            Độ phủ dữ liệu: {numberText(Number(metric.details.coverage) * 100, 1)}%
          </p>
        </div>
      )}
      <Evidence metric={metric} />
    </article>
  );
}

function MacroSeriesCard({ series }: { series: MacroSeriesLatest }) {
  return (
    <article className={styles.macroRow} key={series.series_id}>
      <div className={styles.macroHeading}>
        <div>
          <strong>{series.name}</strong>
          <span>
            {series.series_id} · Tần suất: {series.frequency}
          </span>
        </div>
        <StatusBadge status={series.status} />
      </div>
      <strong className={styles.macroValue}>
        {series.value === null ? "—" : numberText(series.value)} <small>{series.unit}</small>
      </strong>
      <p className={styles.macroDates}>
        Quan sát: {series.observation_date ?? "—"} · Công bố: {series.release_date ?? "—"}
      </p>
      <details className={styles.evidence}>
        <summary>Nguồn & Chứng thực</summary>
        <dl>
          <div>
            <dt>Nguồn dữ liệu</dt>
            <dd>{series.source ?? series.provider}</dd>
          </div>
          <div>
            <dt>Thời gian công bố</dt>
            <dd>{dateText(series.published_at)}</dd>
          </div>
          <div>
            <dt>Thu thập lúc</dt>
            <dd>{dateText(series.retrieved_at)}</dd>
          </div>
          <div>
            <dt>Gốc & Phân loại</dt>
            <dd>
              {series.data_origin ?? "Chính thức"} · {series.source_type ?? "Thống kê"}
            </dd>
          </div>
          {series.source_url && (
            <div>
              <dt>Liên kết nguồn</dt>
              <dd>
                <a href={series.source_url} target="_blank" rel="noreferrer">
                  Xem tài liệu gốc ↗
                </a>
              </dd>
            </div>
          )}
        </dl>
      </details>
    </article>
  );
}

export default function MarketPage() {
  const marketRes = useCachedResource<MarketDashboard>(
    "market:dashboard",
    (signal) => getMarketDashboard(signal),
    { maxAgeMs: 60_000 }
  );

  const macroRes = useCachedResource<MacroLatest>(
    "market:macro",
    (signal) => getLatestMacro(signal),
    { maxAgeMs: 5 * 60_000 }
  );

  const oppsRes = useCachedResource<OpportunityScanner>(
    "market:opps-top",
    (signal) => getOpportunityScanner(emptyFilters, signal),
    { maxAgeMs: 5 * 60_000 }
  );

  const isAnyRevalidating =
    marketRes.isRevalidating || macroRes.isRevalidating || oppsRes.isRevalidating;

  const handleRefreshAll = () => {
    marketRes.reload();
    macroRes.reload();
    oppsRes.reload();
  };

  const market = marketRes.data;
  const macro = macroRes.data;
  const opps = oppsRes.data;

  // Extract top sector candidates from opportunity scanner
  const topSectors = opps?.sector_options?.slice(0, 5) ?? [];
  const topOpportunities = (opps?.results ?? [])
    .filter((o) => o.opportunity_score !== null && o.opportunity_score > 60)
    .slice(0, 4);

  return (
    <div className={styles.page}>
      {/* 1. COMPACT PAGE HEADER WITH CACHE TIME & REFRESH ACTION */}
      <PageHeader
        title="Thị trường"
        description="Giám sát đa chiều: Chỉ số & Độ rộng dòng tiền · Trạng thái Regime · Vĩ mô & Sự kiện trọng yếu"
        meta={
          <div className={styles.headerMeta}>
            <StatusBadge
              status={
                market?.status ?? (marketRes.isLoading ? "LOADING" : "AVAILABLE")
              }
            />
            {marketRes.updatedAt && (
              <span className={styles.updatedTime}>{formatUpdatedAt(marketRes.updatedAt)}</span>
            )}
            {market?.as_of_date && (
              <span className={styles.asOfDate}>Phiên: {market.as_of_date}</span>
            )}
          </div>
        }
        actions={
          <button
            type="button"
            className={styles.refresh}
            onClick={handleRefreshAll}
            disabled={isAnyRevalidating}
            title="Làm mới dữ liệu từ máy chủ"
          >
            <span className={isAnyRevalidating ? styles.spinning : ""}>↻</span>
            <span>{isAnyRevalidating ? "Đang đồng bộ..." : "Làm mới"}</span>
          </button>
        }
      />

      {/* ERROR BANNERS (IF OCCURRED) */}
      {marketRes.error && (
        <div className={styles.errorAlert} role="alert">
          <strong>Lỗi đồng bộ Thị trường:</strong> {marketRes.error}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TRỤ CỘT 1: CHỈ SỐ & ĐỘ RỘNG DÒNG TIỀN (INDICES & BREADTH)                 */}
      {/* ========================================================================= */}
      <section id="indices" className={styles.pillarSection} aria-label="Trụ cột 1: Chỉ số và Độ rộng dòng tiền">
        <header className={styles.pillarHeader}>
          <div className={styles.pillarTitleRow}>
            <h2>Chỉ số & Độ rộng Dòng tiền</h2>
            {market && <StatusBadge status={market.status} />}
          </div>
        </header>

        {/* 1A. BENCHMARK INDICES CARDS */}
        <div className={styles.indexGrid} aria-label="Các chỉ số thị trường chính">
          {market ? (
            market.indexes.map((item) => <IndexCard item={item} key={item.symbol} />)
          ) : marketRes.isLoading ? (
            <>
              <div className={styles.indexSkeletonCard}>
                <Skeleton width="40%" height={16} radius={6} />
                <Skeleton width="70%" height={28} radius={6} />
                <Skeleton width="50%" height={12} radius={4} />
              </div>
              <div className={styles.indexSkeletonCard}>
                <Skeleton width="40%" height={16} radius={6} />
                <Skeleton width="70%" height={28} radius={6} />
                <Skeleton width="50%" height={12} radius={4} />
              </div>
              <div className={styles.indexSkeletonCard}>
                <Skeleton width="40%" height={16} radius={6} />
                <Skeleton width="70%" height={28} radius={6} />
                <Skeleton width="50%" height={12} radius={4} />
              </div>
            </>
          ) : (
            <div className={styles.emptyBox} style={{ gridColumn: "1 / -1" }}>
              <StatusBadge status="ERROR" label="Lỗi tải chỉ số" />
              <p>{marketRes.error || "Không thể tải dữ liệu chỉ số thị trường."}</p>
              <button
                type="button"
                className={styles.refresh}
                onClick={() => marketRes.reload()}
              >
                ↻ Thử lại
              </button>
            </div>
          )}
        </div>

        {/* 1B. LIQUIDITY, BREADTH, MOMENTUM & FOREIGN FLOW METRICS */}
        <div id="breadth" className={styles.metricGrid} aria-label="Các chỉ báo thanh khoản và dòng tiền">
          {market ? (
            <>
              <MetricCard title="Độ rộng Thị trường (Breadth)" metric={market.breadth} />
              <MetricCard title="Thanh khoản Toàn sàn (Liquidity)" metric={market.liquidity} />
              <MetricCard title="Động lượng Xu hướng (Momentum)" metric={market.momentum} />
              <MetricCard title="Giao dịch Khối ngoại (Foreign Flow)" metric={market.foreign_flow} />
            </>
          ) : marketRes.isLoading ? (
            <>
              <SkeletonCard height={130} />
              <SkeletonCard height={130} />
              <SkeletonCard height={130} />
              <SkeletonCard height={130} />
            </>
          ) : (
            <div className={styles.emptyBox} style={{ gridColumn: "1 / -1" }}>
              <StatusBadge status="ERROR" label="Lỗi tải chỉ báo" />
              <p>{marketRes.error || "Không thể tải dữ liệu độ rộng và thanh khoản."}</p>
              <button
                type="button"
                className={styles.refresh}
                onClick={() => marketRes.reload()}
              >
                ↻ Thử lại
              </button>
            </div>
          )}
        </div>
      </section>

      {/* ========================================================================= */}
      {/* TRỤ CỘT 2: TRẠNG THÁI THỊ TRƯỜNG (MARKET REGIME & RADAR)                  */}
      {/* ========================================================================= */}
      <section id="regime" className={styles.pillarSection} aria-label="Trụ cột 2: Trạng thái Thị trường">
        <header className={styles.pillarHeader}>
          <div className={styles.pillarTitleRow}>
            <h2>Trạng thái Thị trường & Cơ hội</h2>
            {market && (
              <StatusBadge
                status={
                  market.market_regime.regime === "INSUFFICIENT_DATA"
                    ? "INSUFFICIENT_DATA"
                    : market.status
                }
              />
            )}
          </div>
        </header>

        {/* 2A. DIMENSIONAL RADAR STRIP */}
        {market ? (
          <DimensionalMarketRadar
            indexes={market.indexes}
            regime={market.market_regime}
            breadth={market.breadth}
          />
        ) : marketRes.isLoading ? (
          <div className={styles.radarSkeleton}>
            <Skeleton width="30%" height={20} radius={6} />
            <Skeleton width="60%" height={14} radius={4} />
          </div>
        ) : (
          <div className={styles.emptyBox}>
            <StatusBadge status="WARNING" label="Radar không khả dụng" />
            <p>Không có dữ liệu radar thị trường.</p>
          </div>
        )}

        {/* 2B. REGIME REPORT + OPPORTUNITY SUMMARY CARD (SIDE-BY-SIDE GRID) */}
        <div className={styles.regimeSplitGrid}>
          {/* REGIME DETAILS PANEL */}
          <article className={styles.panel}>
            <div className={styles.panelHeader}>
              <div>
                <h3 className={styles.regimeTitle}>
                  {market
                    ? formatRegimeName(market.market_regime.regime)
                    : marketRes.isLoading
                    ? "Đang tính toán..."
                    : "Không thể xác định"}
                </h3>
              </div>
              {market && (
                <StatusBadge
                  status={
                    market.market_regime.regime === "INSUFFICIENT_DATA"
                      ? "INSUFFICIENT_DATA"
                      : "AVAILABLE"
                  }
                />
              )}
            </div>

            {market ? (
              <>
                <div className={styles.regimeLine}>
                  <div className={styles.regimeStat}>
                    <span>Độ tin cậy mô hình:</span>
                    <strong>{numberText(market.market_regime.confidence * 100, 0)}%</strong>
                  </div>
                  <div className={styles.regimeStat}>
                    <span>Độ phủ dữ liệu BCTC & Giá:</span>
                    <strong>
                      {market.market_regime.data_coverage === null
                        ? "—"
                        : `${numberText(market.market_regime.data_coverage * 100, 1)}%`}
                    </strong>
                  </div>
                </div>

                <p className={styles.modelMeta}>
                  Phiên phân tích: {market.market_regime.as_of ?? market.as_of_date} · Phiên bản:{" "}
                  {market.market_regime.model_version}
                </p>

                <div className={styles.signalGrid}>
                  <div className={styles.signalCol}>
                    <h4 className={styles.signalHeadingSuccess}>Tín hiệu hỗ trợ xu hướng</h4>
                    {market.market_regime.supporting_signals.length > 0 ? (
                      <ul className={styles.signalList}>
                        {market.market_regime.supporting_signals.map((sig) => (
                          <li key={sig}>{sig}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className={styles.mutedText}>Chưa ghi nhận tín hiệu hỗ trợ xác nhận.</p>
                    )}
                  </div>

                  <div className={styles.signalCol}>
                    <h4 className={styles.signalHeadingWarning}>Cảnh báo rủi ro & Tín hiệu xung đột</h4>
                    {market.market_regime.conflicting_signals.length > 0 ? (
                      <ul className={styles.signalList}>
                        {market.market_regime.conflicting_signals.map((sig) => (
                          <li key={sig}>{sig}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className={styles.mutedText}>
                        {market.market_regime.regime === "INSUFFICIENT_DATA"
                          ? "Cần thêm dữ liệu giao dịch để phân tích rủi ro xung đột."
                          : "Không có tín hiệu xung đột bất thường."}
                      </p>
                    )}
                  </div>
                </div>

                {market.market_regime.historical_context.length > 0 && (
                  <div className={styles.historyContext}>
                    <strong>Bối cảnh lịch sử:</strong>{" "}
                    {market.market_regime.historical_context.join(" · ")}
                  </div>
                )}
              </>
            ) : marketRes.isLoading ? (
              <div className={styles.panelSkeleton}>
                <SkeletonText lines={4} gap={10} />
              </div>
            ) : (
              <div className={styles.emptyBox}>
                <StatusBadge status="ERROR" label="Lỗi mô hình Regime" />
                <p>{marketRes.error || "Không thể tải dữ liệu trạng thái thị trường."}</p>
                <button
                  type="button"
                  className={styles.refresh}
                  onClick={() => marketRes.reload()}
                >
                  ↻ Thử lại
                </button>
              </div>
            )}
          </article>

          {/* 2C. COMPACT OPPORTUNITY SCANNER SUMMARY CARD */}
          <article className={`${styles.panel} ${styles.opportunityCard}`}>
            <div className={styles.panelHeader}>
              <div>
                <h3 className={styles.regimeTitle}>Top ngành hút dòng tiền hôm nay</h3>
              </div>
              <StatusBadge status={opps?.status ?? (oppsRes.isLoading ? "LOADING" : "AVAILABLE")} />
            </div>

            <p className={styles.oppsDesc}>
              Hệ thống lọc cơ hội đa nhân tố (Factor, Quality, Valuation) sàng lọc tự động theo các
              nhóm ngành dẫn dắt.
            </p>

            {opps ? (
              <div className={styles.oppsBody}>
                {topSectors.length > 0 && (
                  <div className={styles.sectorChips}>
                    <span className={styles.chipLabel}>Ngành trọng điểm:</span>
                    <div className={styles.chipRow}>
                      {topSectors.map((sector) => (
                        <span key={sector} className={styles.sectorChip}>
                          {sector}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {topOpportunities.length > 0 ? (
                  <div className={styles.topStockList}>
                    <span className={styles.chipLabel}>Cổ phiếu điểm cơ hội cao:</span>
                    <div className={styles.stockItemGrid}>
                      {topOpportunities.map((stock) => (
                        <div key={stock.symbol} className={styles.stockMiniCard}>
                          <div className={styles.stockMiniHeader}>
                            <strong>{stock.symbol}</strong>
                            <span className={styles.scorePill}>
                              {stock.opportunity_score}/100
                            </span>
                          </div>
                          <span className={styles.stockMiniSector}>{stock.sector ?? stock.name}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className={styles.emptyOppsNote}>
                    Chưa có mã vượt ngưỡng sàng lọc khắt khe trong phiên.
                  </div>
                )}

                <div className={styles.oppsActionRow}>
                  <Link href="/opportunities" className={styles.btnExplore}>
                    Khám phá toàn bộ cơ hội (Opportunities) →
                  </Link>
                </div>
              </div>
            ) : oppsRes.isLoading ? (
              <div className={styles.panelSkeleton}>
                <SkeletonText lines={3} gap={10} />
                <Skeleton height={36} radius={8} />
              </div>
            ) : (
              <div className={styles.emptyBox}>
                <StatusBadge status="ERROR" label="Lỗi tải cơ hội" />
                <p>{oppsRes.error || "Không thể tải dữ liệu sàng lọc cơ hội."}</p>
                <button
                  type="button"
                  className={styles.refresh}
                  onClick={() => oppsRes.reload()}
                >
                  ↻ Thử lại
                </button>
              </div>
            )}
          </article>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* TRỤ CỘT 3: CHỈ BÁO VĨ MÔ & SỰ KIỆN TRỌNG YẾU (MACRO & EVENTS)             */}
      {/* ========================================================================= */}
      <section className={styles.pillarSection} aria-label="Trụ cột 3: Vĩ mô và Sự kiện">
        <header className={styles.pillarHeader}>
          <div className={styles.pillarTitleRow}>
            <h2>Chỉ báo Vĩ mô & Sự kiện Trọng yếu</h2>
            {macro && <StatusBadge status={macro.status} />}
          </div>
        </header>

        <div className={styles.macroEventsGrid}>
          {/* 3A. MACRO INDICATORS (VIETNAM & GLOBAL) */}
          <article className={styles.panel}>
            <div className={styles.panelHeader}>
              <div>
                <h3 className={styles.regimeTitle}>Chỉ báo Vĩ mô Trọng yếu</h3>
              </div>
              {macro && <StatusBadge status={macro.status} />}
            </div>

            {macro ? (
              <div className={styles.macroGroupWrap}>
                {(
                  Object.entries(macro.regions) as Array<
                    [MacroSeriesLatest["region"], MacroSeriesLatest[]]
                  >
                )
                  .filter(([region, rows]) =>
                    region === "VIETNAM" || region === "US"
                      ? rows.length > 0
                      : rows.some((series) => series.value !== null)
                  )
                  .map(([region, rows]) => (
                    <div key={region} className={styles.macroRegionBlock}>
                      <h4 className={styles.regionTitle}>
                        {region === "VIETNAM"
                          ? "🇻🇳 Việt Nam (CPI, GDP, Lãi suất, Tỷ giá)"
                          : region === "US"
                          ? "🇺🇸 Hoa Kỳ & Quốc tế (Fed Rate, CPI)"
                          : region}
                      </h4>
                      <div className={styles.macroSeriesGrid}>
                        {rows.map((series) => (
                          <MacroSeriesCard key={series.series_id} series={series} />
                        ))}
                      </div>
                    </div>
                  ))}

                {Object.values(macro.regions).every(
                  (rows) => rows.length === 0 || rows.every((s) => s.value === null)
                ) && (
                  <div className={styles.emptyBox}>
                    <StatusBadge status="INSUFFICIENT_DATA" />
                    <p>Chưa có dữ liệu quan sát vĩ mô khả dụng từ các nguồn cấp chính thống.</p>
                  </div>
                )}
              </div>
            ) : macroRes.isLoading ? (
              <div className={styles.macroSeriesGrid}>
                <SkeletonCard height={120} />
                <SkeletonCard height={120} />
                <SkeletonCard height={120} />
                <SkeletonCard height={120} />
              </div>
            ) : (
              <div className={styles.emptyBox}>
                <StatusBadge status="ERROR" label="Lỗi tải vĩ mô" />
                <p>{macroRes.error || "Không thể tải dữ liệu chỉ báo vĩ mô."}</p>
                <button
                  type="button"
                  className={styles.refresh}
                  onClick={() => macroRes.reload()}
                >
                  ↻ Thử lại
                </button>
              </div>
            )}
          </article>

          {/* 3B. CANONICAL MARKET EVENTS (SBV/FED, CORPORATE & POLICY) */}
          <article className={styles.panel}>
            <div className={styles.panelHeader}>
              <div>
                <h3 className={styles.regimeTitle}>Sự kiện Thị trường Trọng yếu</h3>
              </div>
              {market && <StatusBadge status={market.events_status} />}
            </div>

            {market ? (
              market.major_events.length > 0 ? (
                <div className={styles.eventList}>
                  {market.major_events.map((event) => (
                    <article key={event.id} className={styles.eventCard}>
                      <div className={styles.eventTop}>
                        <strong className={styles.eventTitle}>{event.title}</strong>
                        <StatusBadge status={event.materiality} />
                      </div>
                      <p className={styles.eventMeta}>
                        Phân loại: <b>{event.event_type}</b> · Mức độ tác động:{" "}
                        <b>{numberText(event.severity, 0)}/10</b> · Ngày:{" "}
                        {dateText(event.published_at)}
                      </p>
                      <details className={styles.evidence}>
                        <summary>Hồ sơ chứng thực & Tài liệu</summary>
                        <dl>
                          <div>
                            <dt>Nguồn cấp</dt>
                            <dd>{event.source ?? "Cổng thông tin chính thức"}</dd>
                          </div>
                          <div>
                            <dt>Văn bản liên quan</dt>
                            <dd>
                              {event.source_documents.length
                                ? event.source_documents.join(" · ")
                                : "Chưa có văn bản đính kèm"}
                            </dd>
                          </div>
                        </dl>
                      </details>
                    </article>
                  ))}
                </div>
              ) : (
                <div className={styles.emptyBox}>
                  <StatusBadge status="AVAILABLE" label="Bình thường" />
                  <p>Không có sự kiện bất thường hoặc biến động chính sách đặc biệt trong phiên.</p>
                </div>
              )
            ) : marketRes.isLoading ? (
              <div className={styles.eventSkeletonList}>
                <SkeletonCard height={100} />
                <SkeletonCard height={100} />
              </div>
            ) : (
              <div className={styles.emptyBox}>
                <StatusBadge status="ERROR" label="Lỗi tải sự kiện" />
                <p>{marketRes.error || "Không thể tải dữ liệu sự kiện trọng yếu."}</p>
                <button
                  type="button"
                  className={styles.refresh}
                  onClick={() => marketRes.reload()}
                >
                  ↻ Thử lại
                </button>
              </div>
            )}
          </article>
        </div>
      </section>

      {/* FOOTER */}
      <footer className={styles.footer}>
        Dữ liệu thị trường và chỉ số vĩ mô được xác thực nguồn độc lập · Cập nhật tự động định kỳ · Hệ thống thông minh InvestIntel
      </footer>
    </div>
  );
}
