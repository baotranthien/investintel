"use client";

import Link from "next/link";
import { useState } from "react";
import { runBacktest, type BacktestResult } from "@/lib/api";
import { useLocale } from "@/lib/i18n";
import { StatusBadge } from "@/components/ui/status-badge";
import styles from "./page.module.css";

const POPULAR_TICKERS = ["FPT", "MWG", "VCB", "HPG", "MBB", "TCB", "VHM", "BSR"];

export default function ResearchAnalyst() {
  const { locale, t } = useLocale();

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
  const [benchmark] = useState("VNINDEX");
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
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        const detail =
          errorData.detail ||
          errorData.message ||
          (locale === "en" ? `HTTP error ${res.status}: ${res.statusText}` : `Lỗi HTTP ${res.status}: ${res.statusText}`);
        setAnalysis(t(`Lỗi phân tích: ${detail}`, `Analysis error: ${detail}`));
        return;
      }
      const data = await res.json();
      setAnalysis(data.content || t("Chưa có phản hồi từ mô hình.", "No response received from model."));
    } catch (err: unknown) {
      setAnalysis(
        t(
          `Lỗi: ${err instanceof Error ? err.message : "Không thể kết nối tới Local AI Analyst."}`,
          `Error: ${err instanceof Error ? err.message : "Unable to connect to Local AI Analyst."}`
        )
      );
    } finally {
      setLoading(false);
    }
  };

  const generateDailyBrief = async () => {
    setLoading(true);
    setDailyBrief("");
    try {
      const res = await fetch("/api/v1/ai/daily-brief", { method: "POST" });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        const detail =
          errorData.detail ||
          errorData.message ||
          (locale === "en" ? `HTTP error ${res.status}: ${res.statusText}` : `Lỗi HTTP ${res.status}: ${res.statusText}`);
        setDailyBrief(t(`Lỗi tạo bản tin: ${detail}`, `Brief generation error: ${detail}`));
        return;
      }
      const data = await res.json();
      setDailyBrief(data.content || t("Chưa có phản hồi từ mô hình.", "No response received from model."));
    } catch (err: unknown) {
      setDailyBrief(
        t(
          `Lỗi: ${err instanceof Error ? err.message : "Không thể kết nối tới Local AI Analyst."}`,
          `Error: ${err instanceof Error ? err.message : "Unable to connect to Local AI Analyst."}`
        )
      );
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
      setBacktestError(
        err instanceof Error
          ? err.message
          : t("Lỗi khi chạy mô phỏng kiểm thử lịch sử.", "Error executing historical backtest simulation.")
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>{t("Bàn nghiên cứu & kiểm thử", "Research Desk & Backtesting")}</p>
          <h1>{t("Nghiên cứu & mô phỏng đầu tư", "Investment Research & Simulation")}</h1>
          <p className={styles.subTitle}>
            {t(
              "Không gian phân tích chứng cứ điểm-thời-gian (Point-in-Time), kiểm thử lịch sử không rò rỉ dữ liệu tương lai (no look-ahead bias), và tổng hợp phân tích từ AI Analyst.",
              "Point-in-Time evidence-based research workspace with strict no look-ahead bias backtesting and integrated AI Analyst synthesis."
            )}
          </p>
        </div>
      </header>

      {/* Tabs */}
      <nav className={styles.tabs} aria-label={t("Khu vực nghiên cứu", "Research workspace navigation")}>
        <button
          type="button"
          onClick={() => setActiveTab("stock")}
          className={`${styles.tabBtn} ${activeTab === "stock" ? styles.tabActive : ""}`}
        >
          {t("Phân tích cổ phiếu", "Single-Stock Research")}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("daily")}
          className={`${styles.tabBtn} ${activeTab === "daily" ? styles.tabActive : ""}`}
        >
          {t("Bản tin thị trường hàng ngày", "Daily Market Brief")}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("backtest")}
          className={`${styles.tabBtn} ${activeTab === "backtest" ? styles.tabActive : ""}`}
        >
          {t("Kiểm thử lịch sử (Backtest)", "Strategy Backtest")}
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
              placeholder={t("Nhập mã chứng khoán (VD: FPT, MWG, VCB)", "Enter ticker symbol (e.g. FPT, MWG, VCB)")}
              className={styles.textInput}
            />
            <button
              type="button"
              onClick={generateStockAnalysis}
              disabled={loading || !symbol.trim()}
              className={styles.actionBtn}
            >
              {loading ? t("Đang phân tích...", "Analyzing...") : t("✦ Phân tích bằng AI", "✦ Analyze with AI")}
            </button>
            <Link
              href={`/ai?symbol=${encodeURIComponent(symbol.trim() || "FPT")}`}
              className={styles.actionBtn}
              style={{ background: "var(--ink)", textDecoration: "none" }}
            >
              {t("Mở AI Analyst thẩm định chi tiết →", "Open AI Analyst Deep Dive →")}
            </Link>
          </div>

          <div className={styles.quickTickers}>
            <span>{t("Mã phổ biến:", "Popular Tickers:")}</span>
            {POPULAR_TICKERS.map((tItem) => (
              <button
                key={tItem}
                type="button"
                className={styles.tickerLink}
                onClick={() => setSymbol(tItem)}
                style={{ cursor: "pointer" }}
              >
                {tItem}
              </button>
            ))}
          </div>

          {analysis && (
            <div className={styles.resultBox}>
              <strong style={{ display: "block", marginBottom: "8px", color: "var(--positive)" }}>
                {t(`Kết quả phân tích tổng hợp (${symbol}):`, `Synthesized Research Brief (${symbol}):`)}
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
              {loading
                ? t("Đang tổng hợp dữ liệu...", "Synthesizing macro data...")
                : t("✦ Tạo báo cáo vĩ mô & thị trường hôm nay", "✦ Generate Daily Macro & Market Brief")}
            </button>
          </div>

          {dailyBrief && (
            <div className={styles.resultBox}>
              <strong style={{ display: "block", marginBottom: "8px", color: "var(--positive)" }}>
                {t("Bản tin vĩ mô & thị trường:", "Daily Macro & Market Intelligence:")}
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
              <label>{t("Vũ trụ đầu tư", "Investment Universe")}</label>
              <input
                type="text"
                value={universe}
                onChange={(e) => setUniverse(e.target.value)}
                placeholder="FPT, HPG, MBB, MWG, VCB"
              />
            </div>
            <div className={styles.field}>
              <label>{t("Từ ngày", "Start Date")}</label>
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className={styles.field}>
              <label>{t("Đến ngày", "End Date")}</label>
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
            <div className={styles.field}>
              <label>{t("Kỳ tái cân bằng", "Rebalancing Horizon")}</label>
              <select value={horizon} onChange={(e) => setHorizon(e.target.value)}>
                <option value="1M">{t("1 tháng (~21 phiên)", "1 Month (~21 Sessions)")}</option>
                <option value="3M">{t("3 tháng (~63 phiên)", "3 Months (~63 Sessions)")}</option>
                <option value="6M">{t("6 tháng (~126 phiên)", "6 Months (~126 Sessions)")}</option>
                <option value="1Y">{t("1 năm (~252 phiên)", "1 Year (~252 Sessions)")}</option>
              </select>
            </div>
            <div className={styles.field}>
              <label>{t("Vốn ban đầu (VND)", "Initial Capital (VND)")}</label>
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
              {loading ? t("Đang chạy mô phỏng...", "Running simulation...") : t("▶ Chạy kiểm thử lịch sử", "▶ Execute Backtest")}
            </button>
            <span style={{ fontSize: "12px", color: "var(--ink-muted)" }}>
              {t(
                "Chi phí giả định: 0.15% phí giao dịch, 0.10% thuế chuyển nhượng, 0.10% trượt giá (slippage).",
                "Assumed frictions: 0.15% brokerage commission, 0.10% transaction tax, 0.10% slippage."
              )}
            </span>
          </div>

          {backtestError && <div className={styles.errorBox}>{backtestError}</div>}

          {backtestResult && (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div className={styles.backtestStatus}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
                  {t("Trạng thái toàn vẹn dữ liệu:", "Data Integrity Audit:")}{" "}
                  <StatusBadge status={String(backtestResult.look_ahead_audit.status)} />
                </span>
                <span>
                  {t("Lỗi rò rỉ tương lai:", "Look-Ahead Violations:")}{" "}
                  <strong>{Number(backtestResult.look_ahead_audit.violations)}</strong>
                </span>
              </div>

              <div className={styles.kpiGrid}>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>{t("Tổng lợi nhuận ròng", "Cumulative Net Return")}</span>
                  <span
                    className={`${styles.kpiValue} ${
                      backtestResult.total_return >= 0 ? styles.kpiGreen : styles.kpiRed
                    }`}
                  >
                    {(backtestResult.total_return * 100).toFixed(2)}%
                  </span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>{t("Lợi nhuận VN-Index", "VN-Index Benchmark Return")}</span>
                  <span className={styles.kpiValue}>
                    {(backtestResult.benchmark_return * 100).toFixed(2)}%
                  </span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>{t("Alpha (vượt trội thị trường)", "Alpha (Excess Return)")}</span>
                  <span
                    className={`${styles.kpiValue} ${
                      backtestResult.alpha >= 0 ? styles.kpiGreen : styles.kpiRed
                    }`}
                  >
                    {(backtestResult.alpha * 100).toFixed(2)}%
                  </span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>{t("Mức sụt giảm tối đa (MDD)", "Max Drawdown (MDD)")}</span>
                  <span className={`${styles.kpiValue} ${styles.kpiRed}`}>
                    {(backtestResult.max_drawdown * 100).toFixed(2)}%
                  </span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>{t("Hệ số Sharpe", "Sharpe Ratio")}</span>
                  <span className={styles.kpiValue}>{backtestResult.sharpe_ratio.toFixed(2)}</span>
                </div>
                <div className={styles.kpiCard}>
                  <span className={styles.kpiLabel}>{t("Tổng số lệnh & chi phí", "Trades & Frictions")}</span>
                  <span className={styles.kpiValue} style={{ fontSize: "16px" }}>
                    {backtestResult.total_trades} {t("lệnh", "trades")} |{" "}
                    {Math.round(backtestResult.total_fees + backtestResult.total_taxes).toLocaleString(
                      locale === "en" ? "en-US" : "vi-VN"
                    )}{" "}
                    VND
                  </span>
                </div>
              </div>

              {backtestResult.trades.length > 0 && (
                <div>
                  <h3 style={{ fontSize: "14px", marginBottom: "8px", color: "var(--ink)" }}>
                    {t("Nhật ký giao dịch tái cân bằng", "Rebalance Execution Log")}
                  </h3>
                  <div className={styles.tableWrap}>
                    <table className={styles.dataTable}>
                      <thead>
                        <tr>
                          <th>{t("Ngày", "Date")}</th>
                          <th>{t("Mã CP", "Ticker")}</th>
                          <th>{t("Loại lệnh", "Order Side")}</th>
                          <th>{t("Khối lượng", "Shares")}</th>
                          <th>{t("Giá khớp", "Exec Price")}</th>
                          <th>{t("Giá trị", "Gross Value")}</th>
                          <th>{t("Phí & thuế", "Fees & Taxes")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {backtestResult.trades.slice(0, 50).map((tItem, idx) => (
                          <tr key={idx}>
                            <td>{tItem.date}</td>
                            <td>
                              <strong>{tItem.symbol}</strong>
                            </td>
                            <td
                              style={{
                                color: tItem.action === "BUY" ? "var(--positive)" : "var(--negative)",
                                fontWeight: 700,
                              }}
                            >
                              {tItem.action === "BUY" ? t("Mua", "Buy") : t("Bán", "Sell")}
                            </td>
                            <td>{tItem.shares.toLocaleString(locale === "en" ? "en-US" : "vi-VN")}</td>
                            <td>{tItem.price.toLocaleString(locale === "en" ? "en-US" : "vi-VN")} VND</td>
                            <td>{Math.round(tItem.value).toLocaleString(locale === "en" ? "en-US" : "vi-VN")} VND</td>
                            <td>{Math.round(tItem.fee + tItem.tax).toLocaleString(locale === "en" ? "en-US" : "vi-VN")} VND</td>
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
