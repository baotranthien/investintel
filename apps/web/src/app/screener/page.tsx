"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  getStockScreener,
  type ScreenedStock,
  type ScreenerFilterParams,
  type ScreenerResult,
} from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonTableRows } from "@/components/ui/skeleton";
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
  label: string;
  filters: Partial<ScreenerFilterParams>;
}

const PRESETS: PresetConfig[] = [
  {
    id: "growth",
    label: "⭐ Tăng trưởng chất lượng",
    filters: {
      roe_min: "15",
      de_ratio_max: "1.2",
      gross_margin_min: "20",
    },
  },
  {
    id: "value",
    label: "💎 Định giá hấp dẫn",
    filters: {
      pe_max: "12",
      pb_max: "1.5",
      roe_min: "12",
    },
  },
  {
    id: "defensive",
    label: "🛡️ Phòng thủ & Cổ tức",
    filters: {
      de_ratio_max: "0.8",
      current_ratio_min: "1.5",
      market_cap_min_bil: "2000",
    },
  },
  {
    id: "margin",
    label: "🚀 Bứt phá biên lợi nhuận",
    filters: {
      net_margin_min: "15",
      gross_margin_min: "30",
    },
  },
];

function formatMoney(value: number | null) {
  if (value === null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(value) + " ₫";
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
  const [filters, setFilters] = useState<ScreenerFilterParams>(defaultFilters);
  const [activePreset, setActivePreset] = useState<PresetKey | null>(null);
  const [result, setResult] = useState<ScreenerResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchResults = useCallback(async (params: ScreenerFilterParams) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getStockScreener(params);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tải kết quả bộ lọc cổ phiếu.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchResults(filters);
  }, []); // Run on initial mount

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

    const headers = [
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
    link.download = `screener_stocks_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className={styles.page}>
      {/* 1. COMPACT PAGE HEADER */}
      <PageHeader
        title="Bộ lọc cổ phiếu định lượng"
        meta={
          <span className={styles.countBadge}>
            {loading ? "Đang lọc..." : result ? `${result.matched_count} / ${result.total_screened} mã` : "—"}
          </span>
        }
        actions={
          <div className={styles.headerActions}>
            <button
              type="button"
              className={styles.btnSecondary}
              onClick={handleExportCsv}
              disabled={!result || result.matches.length === 0}
              title="Xuất bảng kết quả thành file CSV"
            >
              📥 Xuất CSV
            </button>
            <button
              type="button"
              className={styles.btnSecondary}
              onClick={handleReset}
              title="Khôi phục các tiêu chí lọc về mặc định"
            >
              ↺ Đặt lại
            </button>
          </div>
        }
      />

      {/* 2. 1-CLICK STRATEGY PRESETS */}
      <div className={styles.presetSection} aria-label="Chiến lược định lượng mẫu">
        <span className={styles.presetLabel}>Chiến lược mẫu:</span>
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
                {preset.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 3. ALWAYS-VISIBLE FILTER CONTROLS */}
      <form className={styles.filterCard} onSubmit={handleSubmit}>
        <div className={styles.filterGrid}>
          <div className={styles.filterField}>
            <label htmlFor="universe">Vũ trụ cổ phiếu</label>
            <select
              id="universe"
              value={filters.universe || "ALL"}
              onChange={(e) => handleTextChange("universe", e.target.value)}
            >
              <option value="ALL">Tất cả (ALL)</option>
              <option value="VN30">VN30</option>
              <option value="VN100">VN100</option>
            </select>
          </div>

          <div className={styles.filterField}>
            <label htmlFor="sector">Ngành (Sector)</label>
            <input
              id="sector"
              type="text"
              placeholder="VD: Materials, Banking"
              value={filters.sector || ""}
              onChange={(e) => handleTextChange("sector", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="pe_max">P/E tối đa</label>
            <input
              id="pe_max"
              type="number"
              step="0.5"
              placeholder="VD: 12"
              value={filters.pe_max ?? ""}
              onChange={(e) => handleTextChange("pe_max", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="pb_max">P/B tối đa</label>
            <input
              id="pb_max"
              type="number"
              step="0.1"
              placeholder="VD: 1.5"
              value={filters.pb_max ?? ""}
              onChange={(e) => handleTextChange("pb_max", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="roe_min">ROE tối thiểu (%)</label>
            <input
              id="roe_min"
              type="number"
              step="1"
              placeholder="VD: 15"
              value={filters.roe_min ?? ""}
              onChange={(e) => handleTextChange("roe_min", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="gross_margin_min">Biên lãi gộp Min (%)</label>
            <input
              id="gross_margin_min"
              type="number"
              step="1"
              placeholder="VD: 20"
              value={filters.gross_margin_min ?? ""}
              onChange={(e) => handleTextChange("gross_margin_min", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="net_margin_min">Biên lãi ròng Min (%)</label>
            <input
              id="net_margin_min"
              type="number"
              step="1"
              placeholder="VD: 15"
              value={filters.net_margin_min ?? ""}
              onChange={(e) => handleTextChange("net_margin_min", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="de_ratio_max">Nợ / Vốn CSH tối đa (D/E)</label>
            <input
              id="de_ratio_max"
              type="number"
              step="0.1"
              placeholder="VD: 1.2"
              value={filters.de_ratio_max ?? ""}
              onChange={(e) => handleTextChange("de_ratio_max", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="current_ratio_min">Thanh toán hiện hành Min</label>
            <input
              id="current_ratio_min"
              type="number"
              step="0.1"
              placeholder="VD: 1.5"
              value={filters.current_ratio_min ?? ""}
              onChange={(e) => handleTextChange("current_ratio_min", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="market_cap_min_bil">Vốn hóa Min (Tỷ VND)</label>
            <input
              id="market_cap_min_bil"
              type="number"
              step="500"
              placeholder="VD: 2000"
              value={filters.market_cap_min_bil ?? ""}
              onChange={(e) => handleTextChange("market_cap_min_bil", e.target.value)}
            />
          </div>
        </div>

        <div className={styles.filterActions}>
          <button type="button" className={styles.btnReset} onClick={handleReset}>
            Xóa tiêu chí
          </button>
          <button type="submit" className={styles.btnPrimary} disabled={loading}>
            {loading ? "Đang lọc..." : "Áp dụng bộ lọc"}
          </button>
        </div>
      </form>

      {error && <div className={styles.errorBanner}>{error}</div>}

      {/* 4. RESULTS TABLE (ALWAYS STRUCTURED, SKELETON ROWS WHILE LOADING) */}
      <div className={styles.tableCard}>
        <div className={styles.tableScroll}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Mã CP</th>
                <th>Ngành</th>
                <th>Giá hiện tại</th>
                <th>Vốn hóa (Tỷ)</th>
                <th>P/E</th>
                <th>P/B</th>
                <th>ROE</th>
                <th>Biên Gộp</th>
                <th>Biên Ròng</th>
                <th>D/E</th>
                <th>Thanh toán HH</th>
                <th>Biên an toàn</th>
                <th>Thao tác</th>
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
                    <td>{formatMoney(stock.current_price)}</td>
                    <td>
                      {stock.market_cap_billion_vnd
                        ? `${stock.market_cap_billion_vnd.toLocaleString("vi-VN")} Tỷ`
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
                          `Phân tích định giá và sức khỏe tài chính của ${stock.symbol}?`
                        )}`}
                      >
                        ✦ Phân tích AI
                      </Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={13} className={styles.emptyTd}>
                    <div className={styles.emptyState}>
                      <h3>Không tìm thấy cổ phiếu nào</h3>
                      <p>
                        Không có mã cổ phiếu nào đáp ứng đồng thời tất cả các tiêu chí lọc đã chọn.
                        Hãy thử nới lỏng các ngưỡng sàng lọc hoặc bấm vào một trong các chiến lược mẫu phía trên.
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
