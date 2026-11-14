"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  getStockScreener,
  type ScreenedStock,
  type ScreenerFilterParams,
  type ScreenerResult,
} from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonTableRows } from "@/components/ui/skeleton";
import { MultiFactorCube3D } from "@/components/three/multi-factor-cube-3d";
import { useLocale, pickLocaleText, type AppLocale } from "@/lib/i18n";
import styles from "./page.module.css";

const defaultFilters: ScreenerFilterParams = {
  universe: "ALL",
  sector: "",
  pe_min: "",
  pe_max: "",
  pb_min: "",
  pb_max: "",
  roe_min: "",
  gross_margin_min: "",
  net_margin_min: "",
  de_ratio_max: "",
  current_ratio_min: "",
  margin_of_safety_min: "",
  market_cap_min_bil: "",
  limit: 50,
};

type PresetKey = "growth" | "value" | "defensive" | "margin";

interface PresetConfig {
  id: PresetKey;
  label: { vi: string; en: string };
  filters: Partial<ScreenerFilterParams>;
}

const PRESETS: PresetConfig[] = [
  {
    id: "growth",
    label: { vi: "⭐ Tăng trưởng chất lượng", en: "⭐ Quality Growth" },
    filters: {
      roe_min: "15",
      de_ratio_max: "1.2",
      gross_margin_min: "20",
    },
  },
  {
    id: "value",
    label: { vi: "💎 Định giá hấp dẫn", en: "💎 Undervalued Value" },
    filters: {
      pe_max: "12",
      pb_max: "1.5",
      roe_min: "12",
    },
  },
  {
    id: "defensive",
    label: { vi: "🛡️ Phòng thủ & Cổ tức", en: "🛡️ Defensive & Dividends" },
    filters: {
      de_ratio_max: "0.8",
      current_ratio_min: "1.5",
      market_cap_min_bil: "2000",
    },
  },
  {
    id: "margin",
    label: { vi: "🚀 Bứt phá biên lợi nhuận", en: "🚀 Margin Expansion" },
    filters: {
      net_margin_min: "15",
      gross_margin_min: "30",
    },
  },
];

function formatMoney(value: number | null, locale: AppLocale = "vi") {
  if (value === null || !Number.isFinite(value)) return "—";
  const num = new Intl.NumberFormat(locale === "en" ? "en-US" : "vi-VN", { maximumFractionDigits: 0 }).format(value);
  return locale === "en" ? `${num} VND` : `${num} ₫`;
}

function formatPercent(value: number | null) {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${value.toFixed(2)}%`;
}

function formatMultiple(value: number | null) {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${value.toFixed(2)}×`;
}

export default function StockScreenerPage() {
  const router = useRouter();
  const { locale, t } = useLocale();
  const [filters, setFilters] = useState<ScreenerFilterParams>(defaultFilters);
  const [activePreset, setActivePreset] = useState<PresetKey | null>(null);
  const [result, setResult] = useState<ScreenerResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"table" | "cube">("table");

  const fetchResults = useCallback(async (params: ScreenerFilterParams) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getStockScreener(params);
      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : pickLocaleText(locale, "Không thể tải kết quả bộ lọc cổ phiếu.", "Unable to load stock screener results.")
      );
    } finally {
      setLoading(false);
    }
  }, [locale]);

  useEffect(() => {
    let active = true;
    getStockScreener(defaultFilters)
      .then((data) => {
        if (active) {
          setResult(data);
          setError(null);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : pickLocaleText(locale, "Không thể tải kết quả bộ lọc cổ phiếu.", "Unable to load stock screener results.")
          );
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [locale]);

  const handleTextChange = (field: keyof ScreenerFilterParams, value: string) => {
    setActivePreset(null);
    setFilters((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchResults(filters);
  };

  const handleReset = () => {
    setActivePreset(null);
    setFilters(defaultFilters);
    fetchResults(defaultFilters);
  };

  const handleApplyPreset = (preset: PresetConfig) => {
    setActivePreset(preset.id);
    const newFilters: ScreenerFilterParams = {
      ...defaultFilters,
      ...preset.filters,
    };
    setFilters(newFilters);
    fetchResults(newFilters);
  };

  const handleExportCsv = () => {
    const stocks = result?.matches ?? [];
    if (stocks.length === 0) return;

    const headers =
      locale === "en"
        ? [
            "Symbol",
            "Company Name",
            "Sector",
            "Current Price (VND)",
            "Market Cap (Billion VND)",
            "P/E",
            "P/B",
            "ROE (%)",
            "Gross Margin (%)",
            "Net Margin (%)",
            "D/E",
            "Current Ratio",
            "Margin of Safety (%)",
          ]
        : [
            "Mã CP",
            "Tên doanh nghiệp",
            "Ngành",
            "Giá hiện tại (VND)",
            "Vốn hóa (Tỷ VND)",
            "P/E",
            "P/B",
            "ROE (%)",
            "Biên lãi gộp (%)",
            "Biên lãi ròng (%)",
            "D/E",
            "Thanh toán HH",
            "Biên an toàn (%)",
          ];

    const escapeCell = (val: unknown) => {
      if (val === null || val === undefined) return "";
      const s = String(val);
      if (s.includes(",") || s.includes('"') || s.includes("\n")) {
        return `"${s.replace(/"/g, '""')}"`;
      }
      return s;
    };

    const rows = stocks.map((s) => [
      escapeCell(s.symbol),
      escapeCell(s.name),
      escapeCell(s.sector),
      escapeCell(s.current_price),
      escapeCell(s.market_cap_billion_vnd),
      escapeCell(s.pe),
      escapeCell(s.pb),
      escapeCell(s.roe),
      escapeCell(s.gross_margin),
      escapeCell(s.net_margin),
      escapeCell(s.de_ratio),
      escapeCell(s.current_ratio),
      escapeCell(s.margin_of_safety_pct),
    ]);

    const csvContent = "\uFEFF" + [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download =
      locale === "en"
        ? `screener_stocks_${new Date().toISOString().slice(0, 10)}.csv`
        : `bo_loc_co_phieu_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className={styles.page}>
      {/* 1. COMPACT PAGE HEADER */}
      <PageHeader
        title={t("Bộ lọc cổ phiếu định lượng", "Quantitative Stock Screener")}
        meta={
          <span className={styles.countBadge}>
            {loading ? t("Đang lọc...", "Filtering...") : result ? `${result.matched_count} / ${result.total_screened} ${t("mã", "stocks")}` : "—"}
          </span>
        }
        actions={
          <div className={styles.headerActions}>
            <button
              type="button"
              className={styles.btnSecondary}
              onClick={handleExportCsv}
              disabled={!result || result.matches.length === 0}
              title={t("Xuất bảng kết quả thành file CSV", "Export results table to CSV")}
            >
              📥 {t("Xuất CSV", "Export CSV")}
            </button>
            <button
              type="button"
              className={styles.btnSecondary}
              onClick={handleReset}
              title={t("Khôi phục các tiêu chí lọc về mặc định", "Reset all filter criteria to default")}
            >
              ↺ {t("Đặt lại", "Reset")}
            </button>
          </div>
        }
      />

      {/* 2. 1-CLICK STRATEGY PRESETS */}
      <div className={styles.presetSection} aria-label={t("Chiến lược định lượng mẫu", "Quantitative strategy presets")}>
        <span className={styles.presetLabel}>{t("Chiến lược mẫu:", "Strategy Presets:")}</span>
        <div className={styles.presetList}>
          {PRESETS.map((preset) => {
            const isActive = activePreset === preset.id;
            return (
              <button
                key={preset.id}
                type="button"
                className={`${styles.presetBtn}${isActive ? ` ${styles.presetBtnActive}` : ""}`}
                onClick={() => handleApplyPreset(preset)}
              >
                {preset.label[locale]}
              </button>
            );
          })}
        </div>
      </div>

      {/* 3. ALWAYS-VISIBLE FILTER CONTROLS */}
      <form className={styles.filterCard} onSubmit={handleSubmit}>
        <div className={styles.filterGrid}>
          <div className={styles.filterField}>
            <label htmlFor="universe">{t("Vũ trụ cổ phiếu", "Stock Universe")}</label>
            <select
              id="universe"
              value={filters.universe || "ALL"}
              onChange={(e) => handleTextChange("universe", e.target.value)}
            >
              <option value="ALL">{t("Tất cả (ALL)", "All Stocks (ALL)")}</option>
              <option value="VN30">VN30</option>
              <option value="VN100">VN100</option>
            </select>
          </div>

          <div className={styles.filterField}>
            <label htmlFor="sector">{t("Ngành (Sector)", "Industry Sector")}</label>
            <input
              id="sector"
              type="text"
              placeholder={t("VD: Materials, Banking", "e.g. Materials, Banking")}
              value={filters.sector || ""}
              onChange={(e) => handleTextChange("sector", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="pe_max">{t("P/E tối đa", "Max P/E")}</label>
            <input
              id="pe_max"
              type="number"
              step="0.5"
              placeholder={t("VD: 12", "e.g. 12")}
              value={filters.pe_max ?? ""}
              onChange={(e) => handleTextChange("pe_max", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="pb_max">{t("P/B tối đa", "Max P/B")}</label>
            <input
              id="pb_max"
              type="number"
              step="0.1"
              placeholder={t("VD: 1.5", "e.g. 1.5")}
              value={filters.pb_max ?? ""}
              onChange={(e) => handleTextChange("pb_max", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="roe_min">{t("ROE tối thiểu (%)", "Min ROE (%)")}</label>
            <input
              id="roe_min"
              type="number"
              step="1"
              placeholder={t("VD: 15", "e.g. 15")}
              value={filters.roe_min ?? ""}
              onChange={(e) => handleTextChange("roe_min", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="gross_margin_min">{t("Biên lãi gộp Min (%)", "Min Gross Margin (%)")}</label>
            <input
              id="gross_margin_min"
              type="number"
              step="1"
              placeholder={t("VD: 20", "e.g. 20")}
              value={filters.gross_margin_min ?? ""}
              onChange={(e) => handleTextChange("gross_margin_min", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="net_margin_min">{t("Biên lãi ròng Min (%)", "Min Net Margin (%)")}</label>
            <input
              id="net_margin_min"
              type="number"
              step="1"
              placeholder={t("VD: 15", "e.g. 15")}
              value={filters.net_margin_min ?? ""}
              onChange={(e) => handleTextChange("net_margin_min", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="de_ratio_max">{t("Nợ / Vốn CSH tối đa (D/E)", "Max Debt / Equity (D/E)")}</label>
            <input
              id="de_ratio_max"
              type="number"
              step="0.1"
              placeholder={t("VD: 1.2", "e.g. 1.2")}
              value={filters.de_ratio_max ?? ""}
              onChange={(e) => handleTextChange("de_ratio_max", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="current_ratio_min">{t("Thanh toán hiện hành Min", "Min Current Ratio")}</label>
            <input
              id="current_ratio_min"
              type="number"
              step="0.1"
              placeholder={t("VD: 1.5", "e.g. 1.5")}
              value={filters.current_ratio_min ?? ""}
              onChange={(e) => handleTextChange("current_ratio_min", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="market_cap_min_bil">{t("Vốn hóa Min (Tỷ VND)", "Min Market Cap (Billion VND)")}</label>
            <input
              id="market_cap_min_bil"
              type="number"
              step="500"
              placeholder={t("VD: 2000", "e.g. 2000")}
              value={filters.market_cap_min_bil ?? ""}
              onChange={(e) => handleTextChange("market_cap_min_bil", e.target.value)}
            />
          </div>
        </div>

        <div className={styles.filterActions}>
          <button type="button" className={styles.btnReset} onClick={handleReset}>
            {t("Xóa tiêu chí", "Clear Filters")}
          </button>
          <button type="submit" className={styles.btnPrimary} disabled={loading}>
            {loading ? t("Đang lọc...", "Filtering...") : t("Áp dụng bộ lọc", "Apply Screener")}
          </button>
        </div>
      </form>

      {error && <div className={styles.errorBanner}>{error}</div>}

      {/* 4. RESULTS VIEW SWITCHER & CONTENT */}
      <div className={styles.viewBar}>
        <div className={styles.resultSummary}>
          <span className={styles.resultCount}>
            {t("Tìm thấy", "Found")} <strong>{result?.matches.length ?? 0}</strong> {t("mã thỏa mãn tiêu chí", "equities matching criteria")}
          </span>
          {result?.as_of_date && (
            <span className={styles.resultDate}>· {t("Kỳ số liệu:", "Period:")} {result.as_of_date}</span>
          )}
        </div>
        <div className={styles.viewToggleGroup}>
          <button
            type="button"
            className={`${styles.viewToggleBtn} ${viewMode === "table" ? styles.viewToggleBtnActive : ""}`}
            onClick={() => setViewMode("table")}
          >
            ☰ {t("Bảng dữ liệu", "Data Table")} ({result?.matches.length ?? 0})
          </button>
          <button
            type="button"
            className={`${styles.viewToggleBtn} ${viewMode === "cube" ? styles.viewToggleBtnActive : ""}`}
            onClick={() => setViewMode("cube")}
            disabled={!result || result.matches.length === 0}
          >
            🧊 {t("Không gian 3D", "3D Space")}
          </button>
        </div>
      </div>

      {viewMode === "cube" && result && result.matches.length > 0 && (
        <div className={styles.cubeContainer}>
          <div className={styles.cubeHeader}>
            <div className={styles.cubeTitleGroup}>
              <h3 className={styles.cubeTitle}>{t("Không gian Đa nhân tố 3D (Multi-Factor Scatter)", "3D Multi-Factor Scatter Space")}</h3>
              <p className={styles.cubeSubtitle}>
                {t(
                  "Trục X: Định giá P/E · Trục Y: Chất lượng ROE · Trục Z: Động lượng RS",
                  "X-Axis: P/E Valuation · Y-Axis: ROE Quality · Z-Axis: RS Momentum"
                )}
              </p>
            </div>
            <span className={styles.cubeHint}>
              {t(
                "Kéo chuột để xoay 3D · Hover để xem chỉ số · Lăn chuột để cuộn xuống bảng dữ liệu",
                "Drag to rotate 3D · Hover to inspect metrics · Scroll to navigate data table"
              )}
            </span>
          </div>
          <MultiFactorCube3D
            variant="full"
            height={440}
            style={{ width: "100%" }}
            data={result.matches.slice(0, 45).map((s) => ({
              symbol: s.symbol,
              name: s.name,
              pe: s.pe ? Math.max(-0.85, Math.min(0.85, (16 - s.pe) / 12)) : 0,
              roe: s.roe ? Math.max(-0.85, Math.min(0.85, (s.roe - 15) / 15)) : 0,
              rs: s.margin_of_safety_pct ? Math.max(-0.85, Math.min(0.85, s.margin_of_safety_pct / 50)) : 0.2,
              score: Math.round(s.roe ? Math.min(95, Math.max(50, s.roe * 2.5 + 30)) : 70),
              sector: s.sector,
            }))}
            onSelectStock={(sym) => router.push(`/ai?symbol=${encodeURIComponent(sym)}`)}
          />
        </div>
      )}

      {/* RESULTS TABLE */}
      <div className={styles.tableCard}>
        <div className={styles.tableScroll}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>{t("Mã CP", "Symbol")}</th>
                <th>{t("Ngành", "Sector")}</th>
                <th>{t("Giá hiện tại", "Current Price")}</th>
                <th>{t("Vốn hóa (Tỷ)", "Mkt Cap (Bil)")}</th>
                <th>P/E</th>
                <th>P/B</th>
                <th>ROE</th>
                <th>{t("Biên Gộp", "Gross Margin")}</th>
                <th>{t("Biên Ròng", "Net Margin")}</th>
                <th>D/E</th>
                <th>{t("Thanh toán HH", "Current Ratio")}</th>
                <th>{t("Biên an toàn", "Safety Margin")}</th>
                <th>{t("Thao tác", "Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <SkeletonTableRows rows={8} columns={13} />
              ) : result && result.matches.length > 0 ? (
                result.matches.map((stock: ScreenedStock) => (
                  <tr key={stock.symbol}>
                    <td className={styles.tickerCell}>
                      <Link href={`/ai?symbol=${encodeURIComponent(stock.symbol)}`}>
                        <strong>{stock.symbol}</strong>
                      </Link>
                      <span>{stock.name}</span>
                    </td>
                    <td>
                      <span className={styles.badge}>{stock.sector}</span>
                    </td>
                    <td>{formatMoney(stock.current_price, locale)}</td>
                    <td>
                      {stock.market_cap_billion_vnd
                        ? `${stock.market_cap_billion_vnd.toLocaleString(locale === "en" ? "en-US" : "vi-VN")} ${t("Tỷ", "B")}`
                        : "—"}
                    </td>
                    <td>{formatMultiple(stock.pe)}</td>
                    <td>{formatMultiple(stock.pb)}</td>
                    <td>
                      <strong>{formatPercent(stock.roe)}</strong>
                    </td>
                    <td>{formatPercent(stock.gross_margin)}</td>
                    <td>{formatPercent(stock.net_margin)}</td>
                    <td>{formatMultiple(stock.de_ratio)}</td>
                    <td>{formatMultiple(stock.current_ratio)}</td>
                    <td>
                      {stock.margin_of_safety_pct !== null ? (
                        <span
                          className={`${styles.badge} ${
                            stock.margin_of_safety_pct >= 0 ? styles.goodBadge : ""
                          }`}
                        >
                          {stock.margin_of_safety_pct >= 0 ? "+" : ""}
                          {stock.margin_of_safety_pct}%
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      <Link
                        className={styles.aiLink}
                        href={`/ai?symbol=${stock.symbol}&q=${encodeURIComponent(
                          locale === "en"
                            ? `Valuation and financial health analysis for ${stock.symbol}?`
                            : `Phân tích định giá và sức khỏe tài chính của ${stock.symbol}?`
                        )}`}
                        title={
                          locale === "en"
                            ? `Analyze valuation and financial health of ${stock.symbol}`
                            : `Phân tích định giá và sức khỏe tài chính của ${stock.symbol}`
                        }
                      >
                        ✦ {t("Phân tích AI", "AI Analysis")}
                      </Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={13} className={styles.emptyTd}>
                    <div className={styles.emptyState}>
                      <h3>{t("Không tìm thấy cổ phiếu nào", "No Equities Found")}</h3>
                      <p>
                        {t(
                          "Không có mã cổ phiếu nào đáp ứng đồng thời tất cả các tiêu chí lọc đã chọn. Hãy thử nới lỏng các ngưỡng sàng lọc hoặc bấm vào một trong các chiến lược mẫu phía trên.",
                          "No stocks currently satisfy all selected filter criteria simultaneously. Try relaxing your threshold values or selecting one of the strategy presets above."
                        )}
                      </p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
