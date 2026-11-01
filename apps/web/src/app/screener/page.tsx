"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  getStockScreener,
  type ScreenedStock,
  type ScreenerFilterParams,
  type ScreenerResult,
} from "@/lib/api";
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
  }, []);

  const handleTextChange = (field: keyof ScreenerFilterParams, value: string) => {
    setFilters((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchResults(filters);
  };

  const handleReset = () => {
    setFilters(defaultFilters);
    fetchResults(defaultFilters);
  };

  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Phase 5A · Quantitative Stock Screener</p>
          <h1>Bộ Lọc Cổ Phiếu Định Lượng</h1>
          <p className={styles.subTitle}>
            Sàng lọc đa chiều theo định giá P/E, P/B, hiệu quả sinh lời ROE, biên lợi nhuận, cấu trúc vốn D/E và tỷ lệ thanh toán dựa trên dữ liệu báo cáo tài chính chuẩn mực.
          </p>
        </div>
      </header>

      {/* FILTER CONTROLS */}
      <form className={styles.filterCard} onSubmit={handleSubmit}>
        <div className={styles.filterGrid}>
          <div className={styles.filterField}>
            <label htmlFor="universe">Vũ trụ cổ phiếu (Universe)</label>
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
              placeholder="VD: Materials, Banking, Technology"
              value={filters.sector || ""}
              onChange={(e) => handleTextChange("sector", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="pe_max">P/E tối đa (Max P/E)</label>
            <input
              id="pe_max"
              type="number"
              step="0.5"
              placeholder="VD: 20"
              value={filters.pe_max || ""}
              onChange={(e) => handleTextChange("pe_max", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="roe_min">ROE tối thiểu (% Min ROE)</label>
            <input
              id="roe_min"
              type="number"
              step="1"
              placeholder="VD: 15"
              value={filters.roe_min || ""}
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
              value={filters.gross_margin_min || ""}
              onChange={(e) => handleTextChange("gross_margin_min", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="de_ratio_max">Nợ / Vốn CSH tối đa (Max D/E)</label>
            <input
              id="de_ratio_max"
              type="number"
              step="0.1"
              placeholder="VD: 1.5"
              value={filters.de_ratio_max || ""}
              onChange={(e) => handleTextChange("de_ratio_max", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="current_ratio_min">Tỷ lệ thanh toán hiện hành Min</label>
            <input
              id="current_ratio_min"
              type="number"
              step="0.1"
              placeholder="VD: 1.2"
              value={filters.current_ratio_min || ""}
              onChange={(e) => handleTextChange("current_ratio_min", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label htmlFor="market_cap_min_bil">Vốn hóa Min (Tỷ VND)</label>
            <input
              id="market_cap_min_bil"
              type="number"
              step="500"
              placeholder="VD: 1000"
              value={filters.market_cap_min_bil || ""}
              onChange={(e) => handleTextChange("market_cap_min_bil", e.target.value)}
            />
          </div>
        </div>

        <div className={styles.filterActions}>
          <button type="button" className={styles.btnReset} onClick={handleReset}>
            Đặt lại bộ lọc
          </button>
          <button type="submit" className={styles.btnPrimary}>
            Áp dụng bộ lọc
          </button>
        </div>
      </form>

      {/* RESULTS META */}
      <div className={styles.resultsMeta}>
        <span>
          {loading
            ? "Đang tính toán tiêu chí sàng lọc..."
            : result
            ? `Tìm thấy ${result.matched_count} / ${result.total_screened} mã thỏa điều kiện (Dữ liệu ngày ${result.as_of_date})`
            : "Chưa có kết quả"}
        </span>
      </div>

      {error && <div className={styles.errorBanner}>{error}</div>}

      {/* RESULTS TABLE */}
      <div className={styles.tableCard}>
        {loading ? (
          <div className={styles.loadingState}>Đang sàng lọc dữ liệu tài chính...</div>
        ) : result && result.matches.length > 0 ? (
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
                {result.matches.map((stock: ScreenedStock) => (
                  <tr key={stock.symbol}>
                    <td className={styles.tickerCell}>
                      <Link href={`/research/${stock.symbol}`}>
                        <strong>{stock.symbol}</strong>
                      </Link>
                      <span>{stock.name}</span>
                    </td>
                    <td><span className={styles.badge}>{stock.sector}</span></td>
                    <td>{formatMoney(stock.current_price)}</td>
                    <td>{stock.market_cap_billion_vnd ? `${stock.market_cap_billion_vnd.toLocaleString("vi-VN")} Tỷ` : "—"}</td>
                    <td>{formatMultiple(stock.pe)}</td>
                    <td>{formatMultiple(stock.pb)}</td>
                    <td><strong>{formatPercent(stock.roe)}</strong></td>
                    <td>{formatPercent(stock.gross_margin)}</td>
                    <td>{formatPercent(stock.net_margin)}</td>
                    <td>{formatMultiple(stock.de_ratio)}</td>
                    <td>{formatMultiple(stock.current_ratio)}</td>
                    <td>
                      {stock.margin_of_safety_pct !== null ? (
                        <span className={`${styles.badge} ${stock.margin_of_safety_pct >= 0 ? styles.goodBadge : ""}`}>
                          {stock.margin_of_safety_pct >= 0 ? "+" : ""}{stock.margin_of_safety_pct}%
                        </span>
                      ) : "—"}
                    </td>
                    <td>
                      <Link href={`/ai?symbol=${stock.symbol}&q=${encodeURIComponent(`Phân tích định giá và sức khỏe tài chính của ${stock.symbol}?`)}`}>
                        ✦ Phân tích AI
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className={styles.emptyState}>
            <h3>Không tìm thấy cổ phiếu nào</h3>
            <p>Không có mã cổ phiếu nào đáp ứng đồng thời tất cả các tiêu chí lọc đã chọn. Hãy thử nới lỏng các ngưỡng sàng lọc.</p>
          </div>
        )}
      </div>
    </div>
  );
}

