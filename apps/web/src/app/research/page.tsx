"use client";

import Link from "next/link";
import { useState } from "react";
import { runBacktest, type BacktestResult } from "@/lib/api";
import styles from "./page.module.css";

const POPULAR_TICKERS = ["FPT", "MWG", "VCB", "HPG", "MBB", "TCB", "VHM", "BSR"];

export default function ResearchAnalyst() {
  const [symbol, setSymbol] = useState("FPT");
  const [analysis, setAnalysis] = useState("");
  const [dailyBrief, setDailyBrief] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"stock" | "daily" | "backtest">("stock");

  // Backtest state
  const [universe, setUniverse] = useState("FPT, HPG, MBB, MWG, VCB");
  const [startDate, setStartDate] = useState("2023-01-01");
  const [endDate, setEndDate] = useState("2024-01-01");
  const [horizon, setHorizon] = useState("1M");
  const [benchmark, setBenchmark] = useState("VNINDEX");
  const [initialCapital, setInitialCapital] = useState("100000000");
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [backtestError, setBacktestError] = useState("");

  const generateStockAnalysis = async () => {
    setLoading(true);
    setAnalysis("");
    try {
      const res = await fetch("/api/v1/ai/stock-analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: symbol.toUpperCase() }),
      });
      const data = await res.json();
      setAnalysis(data.content || "Chưa có phản hồi từ mô hình.");
    } catch {
      setAnalysis("Lỗi: Không thể kết nối tới Local AI Analyst.");
    } finally {
      setLoading(false);
    }
  };

  const generateDailyBrief = async () => {
    setLoading(true);
    setDailyBrief("");
    try {
      const res = await fetch("/api/v1/ai/daily-brief", { method: "POST" });
      const data = await res.json();
      setDailyBrief(data.content || "Chưa có phản hồi từ mô hình.");
    } catch {
      setDailyBrief("Lỗi: Không thể kết nối tới Local AI Analyst.");
    } finally {
      setLoading(false);
    }
  };

  const handleRunBacktest = async () => {
    setLoading(true);
    setBacktestError("");
    setBacktestResult(null);
    try {
      const symbols = universe
        .split(",")
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean);
      const res = await runBacktest({
        universe: symbols,
        start_date: startDate,
        end_date: endDate,
        horizon,
        benchmark,
        initial_capital: parseFloat(initialCapital) || 100_000_000,
        transaction_cost_pct: 0.0015,
        tax_pct: 0.001,
        slippage_pct: 0.001,
      });
      setBacktestResult(res);
    } catch (err: unknown) {
      setBacktestError(err instanceof Error ? err.message : "Lỗi khi chạy mô phỏng kiểm thử lịch sử.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>RESEARCH DESK · BÀN NGHIÊN CỨU & KIỂM THỬ</p>
          <h1>Nghiên cứu & Mô phỏng Đầu tư (Research & PIT Backtest)</h1>
          <p className={styles.subTitle}>
            Không gian phân tích chứng cứ điểm-thời-gian (Point-in-Time), kiểm thử lịch sử không rò rỉ dữ liệu tương lai
            (No Look-Ahead bias), và tổng hợp phân tích từ AI Analyst.
          </p>
        </div>
      </header>

      {/* Tabs */}
      <nav className={styles.tabs} aria-label="Khu vực nghiên cứu">
        <button
          type="button"
          onClick={() => setActiveTab("stock")}
          className={`${styles.tabBtn} ${activeTab === "stock" ? styles.tabActive : ""}`}
        >
          Phân tích Cổ phiếu (Stock Research)
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("daily")}
          className={`${styles.tabBtn} ${activeTab === "daily" ? styles.tabActive : ""}`}
        >
          Bản tin Thị trường Hàng ngày (Daily Brief)
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("backtest")}
          className={`${styles.tabBtn} ${activeTab === "backtest" ? styles.tabActive : ""}`}
        >
          Kiểm thử Lịch sử (PIT Backtest)
        </button>
      </nav>

      {/* Tab 1: Stock Research */}
      {activeTab === "stock" && (
        <section className={styles.panel}>
          <div className={styles.inputRow}>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              placeholder="Nhập mã chứng khoán (VD: FPT, MWG, VCB)"
              className={styles.textInput}
            />
            <button
              type="button"
              onClick={generateStockAnalysis}
              disabled={loading || !symbol.trim()}
              className={styles.actionBtn}
            >
              {loading ? "Đang phân tích..." : "✦ Phân tích bằng AI"}
            </button>
            <Link
              href={`/research/${symbol.trim() || "FPT"}`}
              className={styles.actionBtn}
              style={{ background: "var(--ink)", textDecoration: "none" }}
            >
              Xem Không gian Nghiên cứu Workspace →
            </Link>
          </div>

          <div className={styles.quickTickers}>
            <span>Mã phổ biến:</span>
            {POPULAR_TICKERS.map((t) => (
              <button
                key={t}
                type="button"
                className={styles.tickerLink}
                onClick={() => setSymbol(t)}
                style={{ cursor: "pointer" }}
              >
                {t}
              </button>
            ))}
          </div>

          {analysis && (
            <div className={styles.resultBox}>
              <strong style={{ display: "block", marginBottom: "8px", color: "var(--positive)" }}>
                KẾT QUẢ PHÂN TÍCH TỔNG HỢP ({symbol}):
              </strong>
              {analysis}
            </div>
          )}
        </section>
      )}

      {/* Tab 2: Daily Brief */}
      {activeTab === "daily" && (
        <section className={styles.panel}>
          <div className={styles.inputRow}>
            <button
              type="button"
              onClick={generateDailyBrief}
              disabled={loading}
              className={styles.actionBtn}
            >
              {loading ? "Đang tổng hợp dữ liệu..." : "✦ Tạo Báo cáo Vĩ mô & Thị trường Hôm nay"}
            </button>
          </div>

          {dailyBrief && (
            <div className={styles.resultBox}>
              <strong style={{ display: "block", marginBottom: "8px", color: "var(--positive)" }}>
                BẢN TIN VĨ MÔ & THỊ TRƯỜNG:
              </strong>
              {dailyBrief}
            </div>
          )}
        </section>
      )}

      {/* Tab 3: Backtest */}
      {activeTab === "backtest" && (
        <section className={styles.panel}>
          <div className={styles.backtestGrid}>
            <div className={styles.field}>
              <label>Vũ trụ đầu tư (Universe Symbols)</label>
              <input
                type="text"
                value={universe}
                onChange={(e) => setUniverse(e.target.value)}
                placeholder="FPT, HPG, MBB, MWG, VCB"
              />
            </div>
            <div className={styles.field}>
              <label>Từ ngày (Start date)</label>
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className={styles.field}>
              <label>Đến ngày (End date)</label>
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
            <div className={styles.field}>
              <label>Kỳ tái cân bằng (Horizon)</label>
              <select value={horizon} onChange={(e) => setHorizon(e.target.value)}>
                <option value="1M">1 Tháng (1M / ~21 phiên)</option>
                <option value="3M">3 Tháng (3M / ~63 phiên)</option>
                <option value="6M">6 Tháng (6M / ~126 phiên)</option>
                <option value="1Y">1 Năm (1Y / ~252 phiên)</option>
              </select>
            </div>
            <div className={styles.field}>
              <label>Vốn ban đầu (Initial Capital - VND)</label>
              <input
                type="number"
                value={initialCapital}
                onChange={(e) => setInitialCapital(e.target.value)}
              />
            </div>
          </div>

          <div className={styles.inputRow}>
            <button
              type="button"
              onClick={handleRunBacktest}
              disabled={loading}
              className={styles.actionBtn}
            >
              {loading ? "Đang chạy mô phỏng..." : "▶ Chạy Kiểm thử PIT Replay"}
            </button>
            <span style={{ fontSize: "12px", color: "var(--ink-muted)" }}>
              Chi phí giả định: 0.15% phí giao dịch, 0.10% thuế chuyển nhượng, 0.10% trượt giá (slippage).
            </span>
          </div>

          {backtestError && <div className={styles.errorBox}>{backtestError}</div>}

          {backtestResult && (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div className={styles.backtestStatus}>
                <span>
                  Trạng thái Toàn vẹn Dữ liệu (PIT Integrity):{" "}
                  <strong>{String(backtestResult.look_ahead_audit.status)}</strong>
                </span>
                <span>
                  Số lỗi rò rỉ tương lai (Look-ahead violations):{" "}
                  <strong>{Number(backtestResult.look_ahead_audit.violations)}</strong>
                </span>
              </div>

              <div className={styles.kpiGrid}>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Tổng lợi nhuận ròng (Total Return)</span>
                  <span
                    className={`${styles.kpiValue} ${
                      backtestResult.total_return >= 0 ? styles.kpiGreen : styles.kpiRed
                    }`}
                  >
                    {(backtestResult.total_return * 100).toFixed(2)}%
                  </span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Lợi nhuận Benchmark (VN-Index)</span>
                  <span className={styles.kpiValue}>
                    {(backtestResult.benchmark_return * 100).toFixed(2)}%
                  </span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Alpha (Chênh lệch vs Benchmark)</span>
                  <span
                    className={`${styles.kpiValue} ${
                      backtestResult.alpha >= 0 ? styles.kpiGreen : styles.kpiRed
                    }`}
                  >
                    {(backtestResult.alpha * 100).toFixed(2)}%
                  </span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Mức sụt giảm tối đa (Max Drawdown)</span>
                  <span className={`${styles.kpiValue} ${styles.kpiRed}`}>
                    {(backtestResult.max_drawdown * 100).toFixed(2)}%
                  </span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Hệ số Sharpe (Sharpe Ratio)</span>
                  <span className={styles.kpiValue}>{backtestResult.sharpe_ratio.toFixed(2)}</span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>Tổng lệnh & Chi phí (Trades & Fees)</span>
                  <span className={styles.kpiValue} style={{ fontSize: "16px" }}>
                    {backtestResult.total_trades} lệnh |{" "}
                    {Math.round(backtestResult.total_fees + backtestResult.total_taxes).toLocaleString(
                      "vi-VN"
                    )}{" "}
                    VND
                  </span>
                </div>
              </div>

              {backtestResult.trades.length > 0 && (
                <div>
                  <h3 style={{ fontSize: "14px", marginBottom: "8px", color: "var(--ink)" }}>
                    Nhật ký Giao dịch Tái cân bằng (Rebalance Ledger)
                  </h3>
                  <div className={styles.tableWrap}>
                    <table className={styles.dataTable}>
                      <thead>
                        <tr>
                          <th>Ngày (Date)</th>
                          <th>Mã (Symbol)</th>
                          <th>Lệnh (Action)</th>
                          <th>Số lượng (Shares)</th>
                          <th>Giá khớp (Price)</th>
                          <th>Giá trị (Value)</th>
                          <th>Phí + Thuế (Costs)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {backtestResult.trades.slice(0, 50).map((t, idx) => (
                          <tr key={idx}>
                            <td>{t.date}</td>
                            <td>
                              <strong>{t.symbol}</strong>
                            </td>
                            <td
                              style={{
                                color: t.action === "BUY" ? "var(--positive)" : "var(--negative)",
                                fontWeight: 700,
                              }}
                            >
                              {t.action === "BUY" ? "MUA (BUY)" : "BÁN (SELL)"}
                            </td>
                            <td>{t.shares.toLocaleString("vi-VN")}</td>
                            <td>{t.price.toLocaleString("vi-VN")} VND</td>
                            <td>{Math.round(t.value).toLocaleString("vi-VN")} VND</td>
                            <td>{Math.round(t.fee + t.tax).toLocaleString("vi-VN")} VND</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
