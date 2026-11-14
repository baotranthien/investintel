"use client";

import Link from "next/link";
import React from "react";
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
import { useLocale, translateQuantEnum, type AppLocale } from "@/lib/i18n";
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

function numberText(value: number | null, digits = 2, locale: AppLocale = "vi"): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(locale === "en" ? "en-US" : "vi-VN", { maximumFractionDigits: digits }).format(value);
}

function dateText(value: string | null, locale: AppLocale = "vi"): string {
  if (!value) return locale === "en" ? "No timestamp" : "Không có timestamp";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString(locale === "en" ? "en-US" : "vi-VN");
}

function formatRegimeName(regime: string | undefined, locale: AppLocale = "vi"): string {
  if (!regime || regime === "INSUFFICIENT_DATA") {
    return locale === "en" ? "Insufficient Data for Model" : "Chưa đủ dữ liệu tính toán";
  }
  switch (regime) {
    case "BULL_CONFIRMED":
      return locale === "en" ? "Bull Confirmed (Uptrend)" : "Tăng trưởng xác nhận (Bull Confirmed)";
    case "ACCUMULATION":
      return locale === "en" ? "Accumulation & Inflows" : "Tích lũy & Thu gom (Accumulation)";
    case "DISTRIBUTION":
      return locale === "en" ? "Distribution / High Risk" : "Phân phối / Rủi ro cao (Distribution)";
    case "BEAR_CONFIRMED":
      return locale === "en" ? "Bear Confirmed (Downtrend)" : "Xu hướng Giảm (Bear Confirmed)";
    case "HIGH_VOLATILITY":
      return locale === "en" ? "High Volatility" : "Biến động mạnh (High Volatility)";
    case "DEFENSIVE":
      return locale === "en" ? "Defensive & Selective" : "Phòng thủ & Chọn lọc (Defensive)";
    default:
      return translateQuantEnum(regime, locale);
  }
}

function Evidence({ metric, locale }: { metric: MarketMetric; locale: AppLocale }) {
  return (
    <details className={styles.evidence}>
      <summary>{locale === "en" ? "Evidence & Data Provenance" : "Bằng chứng & Nguồn số liệu"}</summary>
      <dl>
        <div>
          <dt>{locale === "en" ? "Audit Classification" : "Loại xác thực"}</dt>
          <dd>{locale === "en" ? "EMPIRICAL FACT" : "DỮ LIỆU THỰC TẾ (FACT)"}</dd>
        </div>
        <div>
          <dt>{locale === "en" ? "Data Feed" : "Nguồn cấp"}</dt>
          <dd>{metric.source ?? (locale === "en" ? "No source" : "Không có source")}</dd>
        </div>
        <div>
          <dt>{locale === "en" ? "Origin" : "Gốc dữ liệu"}</dt>
          <dd>{metric.data_origin ?? (locale === "en" ? "Unspecified" : "Không xác định")}</dd>
        </div>
        <div>
          <dt>{locale === "en" ? "Observation Period" : "Kỳ quan sát"}</dt>
          <dd>{metric.as_of_date ?? (locale === "en" ? "No date" : "Không có ngày")}</dd>
        </div>
        <div>
          <dt>{locale === "en" ? "Published At" : "Thời gian công bố"}</dt>
          <dd>{dateText(metric.published_at, locale)}</dd>
        </div>
        <div>
          <dt>{locale === "en" ? "Sampled At" : "Thời gian lấy mẫu"}</dt>
          <dd>{dateText(metric.retrieved_at, locale)}</dd>
        </div>
        {metric.note && (
          <div>
            <dt>{locale === "en" ? "Notes" : "Ghi chú"}</dt>
            <dd>{metric.note}</dd>
          </div>
        )}
      </dl>
    </details>
  );
}

function IndexCard({ item, locale }: { item: MarketDashboard["indexes"][number]; locale: AppLocale }) {
  const cleanId = item.symbol.toLowerCase().replace(/[^a-z0-9]/g, "");
  return (
    <article className={styles.indexCard} id={cleanId}>
      <div className={styles.indexLine}>
        <span className={styles.indexSymbol}>{item.symbol}</span>
        <StatusBadge status={item.metric.status} />
      </div>
      <h2 className={styles.indexName}>{item.name}</h2>
      <strong className={styles.indexValue}>{numberText(item.metric.value, 2, locale)}</strong>
      <p className={styles.indexDate}>
        {item.metric.as_of_date ?? item.metric.note ?? (locale === "en" ? "Current session data" : "Dữ liệu phiên hiện tại")}
      </p>
      <Evidence metric={item.metric} locale={locale} />
    </article>
  );
}

function MetricCard({ title, metric, locale }: { title: string; metric: MarketMetric; locale: AppLocale }) {
  const unit =
    metric.unit === "percent_advancing"
      ? (locale === "en" ? "% advancing" : "% mã tăng")
      : metric.unit === "percent_20_sessions"
      ? (locale === "en" ? "% / 20 sessions" : "% / 20 phiên")
      : metric.unit === "VND"
      ? (locale === "en" ? "VND" : "VNĐ")
      : "";

  return (
    <article className={styles.metric}>
      <div className={styles.metricHeading}>
        <span>{title}</span>
        <StatusBadge status={metric.status} />
      </div>
      <strong className={styles.metricValue}>
        {metric.value === null ? "—" : numberText(metric.value, 2, locale)} <small>{unit}</small>
      </strong>
      <p className={styles.metricDate}>{metric.as_of_date ?? metric.note ?? (locale === "en" ? "Latest session" : "Phiên gần nhất")}</p>
      {metric.details?.coverage !== undefined && (
        <div className={styles.breadthDetails}>
          <div className={styles.breadthCounts}>
            <span className={styles.advancingBadge}>↑ {String(metric.details.advancing ?? 0)} {locale === "en" ? "advancing" : "tăng"}</span>
            <span className={styles.decliningBadge}>↓ {String(metric.details.declining ?? 0)} {locale === "en" ? "declining" : "giảm"}</span>
            {metric.details.unchanged !== undefined && (
              <span className={styles.unchangedBadge}>— {String(metric.details.unchanged)} {locale === "en" ? "unchanged" : "tham chiếu"}</span>
            )}
          </div>
          <p className={styles.coverageText}>
            {locale === "en" ? "Data Coverage:" : "Độ phủ dữ liệu:"} {numberText(Number(metric.details.coverage) * 100, 1, locale)}%
          </p>
        </div>
      )}
      <Evidence metric={metric} locale={locale} />
    </article>
  );
}

function MacroSeriesCard({
  series,
  locale,
  extraClass,
}: {
  series: MacroSeriesLatest;
  locale: AppLocale;
  extraClass?: string;
}) {
  return (
    <article
      className={`${styles.macroRow} ${extraClass ?? ""}`}
      key={series.series_id}
    >
      <div className={styles.macroHeading}>
        <div>
          <strong>{series.name}</strong>
          <span>
            {series.series_id} · {locale === "en" ? "Frequency:" : "Tần suất:"} {series.frequency}
          </span>
        </div>
        <StatusBadge status={series.status} />
      </div>
      <strong className={styles.macroValue}>
        {series.value === null ? "—" : numberText(series.value, 2, locale)} <small>{series.unit}</small>
      </strong>
      <p className={styles.macroDates}>
        {locale === "en" ? "Observation:" : "Quan sát:"} {series.observation_date ?? "—"} · {locale === "en" ? "Released:" : "Công bố:"} {series.release_date ?? "—"}
      </p>
      <details className={styles.evidence}>
        <summary>{locale === "en" ? "Provenance & Audit" : "Nguồn & Chứng thực"}</summary>
        <dl>
          <div>
            <dt>{locale === "en" ? "Data Source" : "Nguồn dữ liệu"}</dt>
            <dd>{series.source ?? series.provider}</dd>
          </div>
          <div>
            <dt>{locale === "en" ? "Published At" : "Thời gian công bố"}</dt>
            <dd>{dateText(series.published_at, locale)}</dd>
          </div>
          <div>
            <dt>{locale === "en" ? "Retrieved At" : "Thu thập lúc"}</dt>
            <dd>{dateText(series.retrieved_at, locale)}</dd>
          </div>
          <div>
            <dt>{locale === "en" ? "Origin & Classification" : "Gốc & Phân loại"}</dt>
            <dd>
              {series.data_origin ?? (locale === "en" ? "Official" : "Chính thức")} · {series.source_type ?? (locale === "en" ? "Statistical" : "Thống kê")}
            </dd>
          </div>
          {series.source_url && (
            <div>
              <dt>{locale === "en" ? "Source Link" : "Liên kết nguồn"}</dt>
              <dd>
                <a href={series.source_url} target="_blank" rel="noreferrer">
                  {locale === "en" ? "View original document ↗" : "Xem tài liệu gốc ↗"}
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
  const { locale, t } = useLocale();

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
        title={t("Thị trường", "Market Overview")}
        description={t(
          "Giám sát đa chiều: Chỉ số & Độ rộng dòng tiền · Trạng thái Regime · Vĩ mô & Sự kiện trọng yếu",
          "Multi-dimensional surveillance: Indices & Breadth · Regime Dynamics · Macro & Canonical Events"
        )}
        meta={
          <div className={styles.headerMeta}>
            <StatusBadge
              status={
                market?.status ?? (marketRes.isLoading ? "LOADING" : "AVAILABLE")
              }
            />
            {marketRes.updatedAt && (
              <span className={styles.updatedTime}>{formatUpdatedAt(marketRes.updatedAt, locale)}</span>
            )}
            {market?.as_of_date && (
              <span className={styles.asOfDate}>{t("Phiên:", "Session:")} {market.as_of_date}</span>
            )}
          </div>
        }
        actions={
          <button
            type="button"
            className={styles.refresh}
            onClick={handleRefreshAll}
            disabled={isAnyRevalidating}
            title={t("Làm mới dữ liệu từ máy chủ", "Refresh data from server")}
          >
            <span className={isAnyRevalidating ? styles.spinning : ""}>↻</span>
            <span>{isAnyRevalidating ? t("Đang đồng bộ...", "Syncing...") : t("Làm mới", "Refresh")}</span>
          </button>
        }
      />

      {/* ERROR BANNERS (IF OCCURRED) */}
      {marketRes.error && (
        <div className={styles.errorAlert} role="alert">
          <strong>{t("Lỗi đồng bộ Thị trường:", "Market Sync Error:")}</strong> {marketRes.error}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TRỤ CỘT 1: CHỈ SỐ & ĐỘ RỘNG DÒNG TIỀN (INDICES & BREADTH)                 */}
      {/* ========================================================================= */}
      <section id="indices" className={styles.pillarSection} aria-label={t("Trụ cột 1: Chỉ số và Độ rộng dòng tiền", "Pillar 1: Indices and Market Breadth")}>
        <header className={styles.pillarHeader}>
          <div className={styles.pillarTitleRow}>
            <h2>{t("Chỉ số & Độ rộng Dòng tiền", "Benchmark Indices & Liquidity Breadth")}</h2>
            {market && <StatusBadge status={market.status} />}
          </div>
        </header>

        {/* 1A. BENCHMARK INDICES CARDS */}
        <div className={styles.indexGrid} aria-label={t("Các chỉ số thị trường chính", "Core market benchmark indices")}>
          {market ? (
            market.indexes.map((item) => <IndexCard item={item} locale={locale} key={item.symbol} />)
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
              <StatusBadge status="ERROR" label={t("Lỗi tải chỉ số", "Index Load Error")} />
              <p>{marketRes.error || t("Không thể tải dữ liệu chỉ số thị trường.", "Unable to load market index data.")}</p>
              <button
                type="button"
                className={styles.refresh}
                onClick={() => marketRes.reload()}
              >
                ↻ {t("Thử lại", "Retry")}
              </button>
            </div>
          )}
        </div>

        {/* 1B. LIQUIDITY, BREADTH, MOMENTUM & FOREIGN FLOW METRICS */}
        <div id="breadth" className={styles.metricGrid} aria-label={t("Các chỉ báo thanh khoản và dòng tiền", "Liquidity and flow indicators")}>
          {market ? (
            <>
              <MetricCard title={t("Độ rộng Thị trường (Breadth)", "Market Breadth")} metric={market.breadth} locale={locale} />
              <MetricCard title={t("Thanh khoản Toàn sàn (Liquidity)", "Market Liquidity")} metric={market.liquidity} locale={locale} />
              <MetricCard title={t("Động lượng Xu hướng (Momentum)", "Trend Momentum")} metric={market.momentum} locale={locale} />
              <MetricCard title={t("Giao dịch Khối ngoại (Foreign Flow)", "Foreign Investor Flow")} metric={market.foreign_flow} locale={locale} />
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
              <StatusBadge status="ERROR" label={t("Lỗi tải chỉ báo", "Metric Load Error")} />
              <p>{marketRes.error || t("Không thể tải dữ liệu độ rộng và thanh khoản.", "Unable to load breadth and liquidity metrics.")}</p>
              <button
                type="button"
                className={styles.refresh}
                onClick={() => marketRes.reload()}
              >
                ↻ {t("Thử lại", "Retry")}
              </button>
            </div>
          )}
        </div>
      </section>

      {/* ========================================================================= */}
      {/* TRỤ CỘT 2: TRẠNG THÁI THỊ TRƯỜNG (MARKET REGIME & RADAR)                  */}
      {/* ========================================================================= */}
      <section id="regime" className={styles.pillarSection} aria-label={t("Trụ cột 2: Trạng thái Thị trường", "Pillar 2: Market Regime")}>
        <header className={styles.pillarHeader}>
          <div className={styles.pillarTitleRow}>
            <h2>{t("Trạng thái Thị trường & Cơ hội", "Market Regime & Alpha Opportunities")}</h2>
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
            <StatusBadge status="WARNING" label={t("Radar không khả dụng", "Radar Unavailable")} />
            <p>{t("Không có dữ liệu radar thị trường.", "No market radar data available.")}</p>
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
                    ? formatRegimeName(market.market_regime.regime, locale)
                    : marketRes.isLoading
                    ? t("Đang tính toán...", "Computing...")
                    : t("Không thể xác định", "Indeterminate")}
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
                    <span>{t("Độ tin cậy mô hình:", "Model Confidence:")}</span>
                    <strong>{numberText(market.market_regime.confidence * 100, 0, locale)}%</strong>
                  </div>
                  <div className={styles.regimeStat}>
                    <span>{t("Độ phủ dữ liệu BCTC & Giá:", "Financials & Price Coverage:")}</span>
                    <strong>
                      {market.market_regime.data_coverage === null
                        ? "—"
                        : `${numberText(market.market_regime.data_coverage * 100, 1, locale)}%`}
                    </strong>
                  </div>
                </div>

                <p className={styles.modelMeta}>
                  {t("Phiên phân tích:", "Analysis Session:")} {market.market_regime.as_of ?? market.as_of_date} · {t("Phiên bản:", "Version:")}{" "}
                  {market.market_regime.model_version}
                </p>

                <div className={styles.signalGrid}>
                  <div className={styles.signalCol}>
                    <h4 className={styles.signalHeadingSuccess}>{t("Tín hiệu hỗ trợ xu hướng", "Supporting Trend Signals")}</h4>
                    {market.market_regime.supporting_signals.length > 0 ? (
                      <ul className={styles.signalList}>
                        {market.market_regime.supporting_signals.map((sig) => (
                          <li key={sig}>{sig}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className={styles.mutedText}>{t("Chưa ghi nhận tín hiệu hỗ trợ xác nhận.", "No supporting trend signals confirmed.")}</p>
                    )}
                  </div>

                  <div className={styles.signalCol}>
                    <h4 className={styles.signalHeadingWarning}>{t("Cảnh báo rủi ro & Tín hiệu xung đột", "Risk Warnings & Conflicting Signals")}</h4>
                    {market.market_regime.conflicting_signals.length > 0 ? (
                      <ul className={styles.signalList}>
                        {market.market_regime.conflicting_signals.map((sig) => (
                          <li key={sig}>{sig}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className={styles.mutedText}>
                        {market.market_regime.regime === "INSUFFICIENT_DATA"
                          ? t("Cần thêm dữ liệu giao dịch để phân tích rủi ro xung đột.", "Additional trading sessions required to assess conflicting risks.")
                          : t("Không có tín hiệu xung đột bất thường.", "No anomalous conflicting signals detected.")}
                      </p>
                    )}
                  </div>
                </div>

                {market.market_regime.historical_context.length > 0 && (
                  <div className={styles.historyContext}>
                    <strong>{t("Bối cảnh lịch sử:", "Historical Context:")}</strong>{" "}
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
                <StatusBadge status="ERROR" label={t("Lỗi mô hình Regime", "Regime Model Error")} />
                <p>{marketRes.error || t("Không thể tải dữ liệu trạng thái thị trường.", "Unable to load market regime state.")}</p>
                <button
                  type="button"
                  className={styles.refresh}
                  onClick={() => marketRes.reload()}
                >
                  ↻ {t("Thử lại", "Retry")}
                </button>
              </div>
            )}
          </article>

          {/* 2C. COMPACT OPPORTUNITY SCANNER SUMMARY CARD */}
          <article className={`${styles.panel} ${styles.opportunityCard}`}>
            <div className={styles.panelHeader}>
              <div>
                <h3 className={styles.regimeTitle}>{t("Top ngành hút dòng tiền hôm nay", "Top Sector Inflow Leaders Today")}</h3>
              </div>
              <StatusBadge status={opps?.status ?? (oppsRes.isLoading ? "LOADING" : "AVAILABLE")} />
            </div>

            <p className={styles.oppsDesc}>
              {t(
                "Hệ thống lọc cơ hội đa nhân tố (Factor, Quality, Valuation) sàng lọc tự động theo các nhóm ngành dẫn dắt.",
                "Multi-factor quantitative screening (Factor, Quality, Valuation) dynamically tracked across leading industry sectors."
              )}
            </p>

            {opps ? (
              <div className={styles.oppsBody}>
                {topSectors.length > 0 && (
                  <div className={styles.sectorChips}>
                    <span className={styles.chipLabel}>{t("Ngành trọng điểm:", "Key Sectors:")}</span>
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
                    <span className={styles.chipLabel}>{t("Cổ phiếu điểm cơ hội cao:", "High Opportunity Equities:")}</span>
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
                    {t("Chưa có mã vượt ngưỡng sàng lọc khắt khe trong phiên.", "No equities currently exceed the strict hurdle rate for this session.")}
                  </div>
                )}

                <div className={styles.oppsActionRow}>
                  <Link href="/opportunities" className={styles.btnExplore}>
                    {t("Khám phá toàn bộ cơ hội (Opportunities) →", "Explore All Opportunities →")}
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
                <StatusBadge status="ERROR" label={t("Lỗi tải cơ hội", "Opportunity Load Error")} />
                <p>{oppsRes.error || t("Không thể tải dữ liệu sàng lọc cơ hội.", "Unable to load opportunity scanner data.")}</p>
                <button
                  type="button"
                  className={styles.refresh}
                  onClick={() => oppsRes.reload()}
                >
                  ↻ {t("Thử lại", "Retry")}
                </button>
              </div>
            )}
          </article>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* TRỤ CỘT 3: CHỈ BÁO VĨ MÔ & SỰ KIỆN TRỌNG YẾU (MACRO & EVENTS)             */}
      {/* ========================================================================= */}
      <section className={styles.pillarSection} aria-label={t("Trụ cột 3: Vĩ mô và Sự kiện", "Pillar 3: Macro & Canonical Events")}>
        <header className={styles.pillarHeader}>
          <div className={styles.pillarTitleRow}>
            <h2>{t("Chỉ báo Vĩ mô & Sự kiện Trọng yếu", "Macroeconomic Indicators & Material Events")}</h2>
            {macro && <StatusBadge status={macro.status} />}
          </div>
        </header>

        <div className={styles.macroEventsGrid}>
          {/* 3A. MACRO INDICATORS (VIETNAM & GLOBAL) */}
          <article className={styles.panel}>
            <div className={styles.panelHeader}>
              <div>
                <h3 className={styles.regimeTitle}>{t("Chỉ báo Vĩ mô Trọng yếu", "Core Macroeconomic Indicators")}</h3>
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
                          ? t("🇻🇳 Việt Nam (CPI, GDP, Lãi suất, Tỷ giá)", "🇻🇳 Vietnam (CPI, GDP, Interest Rates, FX)")
                          : region === "US"
                          ? t("🇺🇸 Hoa Kỳ & Quốc tế (Fed Rate, CPI)", "🇺🇸 US & Global (Fed Funds Rate, CPI)")
                          : region}
                      </h4>
                      <div
                        className={`${styles.macroSeriesGrid} ${
                          rows.length === 2 || rows.length === 4 || rows.length % 3 === 2
                            ? styles.macroSeriesTwoCol
                            : ""
                        }`}
                      >
                        {rows.map((series, idx) => {
                          const usesTwoCols =
                            rows.length === 2 || rows.length === 4 || rows.length % 3 === 2;
                          const hasOrphanLast =
                            rows.length > 1 &&
                            idx === rows.length - 1 &&
                            (usesTwoCols ? rows.length % 2 === 1 : rows.length % 3 === 1);
                          return (
                            <MacroSeriesCard
                              key={series.series_id}
                              series={series}
                              locale={locale}
                              extraClass={hasOrphanLast ? styles.macroRowFull : undefined}
                            />
                          );
                        })}
                      </div>
                    </div>
                  ))}

                {Object.values(macro.regions).every(
                  (rows) => rows.length === 0 || rows.every((s) => s.value === null)
                ) && (
                  <div className={styles.emptyBox}>
                    <StatusBadge status="INSUFFICIENT_DATA" />
                    <p>{t("Chưa có dữ liệu quan sát vĩ mô khả dụng từ các nguồn cấp chính thống.", "No empirical macroeconomic data currently available from primary sources.")}</p>
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
                <StatusBadge status="ERROR" label={t("Lỗi tải vĩ mô", "Macro Load Error")} />
                <p>{macroRes.error || t("Không thể tải dữ liệu chỉ báo vĩ mô.", "Unable to load macroeconomic indicators.")}</p>
                <button
                  type="button"
                  className={styles.refresh}
                  onClick={() => macroRes.reload()}
                >
                  ↻ {t("Thử lại", "Retry")}
                </button>
              </div>
            )}
          </article>

          {/* 3B. CANONICAL MARKET EVENTS (SBV/FED, CORPORATE & POLICY) */}
          <article className={styles.panel}>
            <div className={styles.panelHeader}>
              <div>
                <h3 className={styles.regimeTitle}>{t("Sự kiện Thị trường Trọng yếu", "Material Market & Policy Events")}</h3>
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
                        {t("Phân loại:", "Type:")} <b>{event.event_type}</b> · {t("Mức độ tác động:", "Impact Severity:")}{" "}
                        <b>{numberText(event.severity, 0, locale)}/10</b> · {t("Ngày:", "Date:")}{" "}
                        {dateText(event.published_at, locale)}
                      </p>
                      <details className={styles.evidence}>
                        <summary>{t("Hồ sơ chứng thực & Tài liệu", "Audit Dossier & Documentation")}</summary>
                        <dl>
                          <div>
                            <dt>{t("Nguồn cấp", "Data Feed")}</dt>
                            <dd>{event.source ?? t("Cổng thông tin chính thức", "Official Regulatory Portal")}</dd>
                          </div>
                          <div>
                            <dt>{t("Văn bản liên quan", "Related Documents")}</dt>
                            <dd>
                              {event.source_documents.length
                                ? event.source_documents.join(" · ")
                                : t("Chưa có văn bản đính kèm", "No attached documents")}
                            </dd>
                          </div>
                        </dl>
                      </details>
                    </article>
                  ))}
                </div>
              ) : (
                <div className={styles.emptyBox}>
                  <StatusBadge status="AVAILABLE" label={t("Bình thường", "Normal")} />
                  <p>{t("Không có sự kiện bất thường hoặc biến động chính sách đặc biệt trong phiên.", "No abnormal market shocks or extraordinary policy shifts recorded for this session.")}</p>
                </div>
              )
            ) : marketRes.isLoading ? (
              <div className={styles.eventSkeletonList}>
                <SkeletonCard height={100} />
                <SkeletonCard height={100} />
              </div>
            ) : (
              <div className={styles.emptyBox}>
                <StatusBadge status="ERROR" label={t("Lỗi tải sự kiện", "Event Load Error")} />
                <p>{marketRes.error || t("Không thể tải dữ liệu sự kiện trọng yếu.", "Unable to load material market events.")}</p>
                <button
                  type="button"
                  className={styles.refresh}
                  onClick={() => marketRes.reload()}
                >
                  ↻ {t("Thử lại", "Retry")}
                </button>
              </div>
            )}
          </article>
        </div>
      </section>

      {/* FOOTER */}
      <footer className={styles.footer}>
        {t(
          "Dữ liệu thị trường và chỉ số vĩ mô được xác thực nguồn độc lập · Cập nhật tự động định kỳ · Hệ thống thông minh InvestIntel",
          "Market benchmarks and macro indicators independently verified · Periodically refreshed · InvestIntel Workstation"
        )}
      </footer>
    </div>
  );
}
