"use client";

import { useState } from "react";
import { runBacktest, type BacktestResult } from "@/lib/api";

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
        body: JSON.stringify({ symbol })
      });
      const data = await res.json();
      setAnalysis(data.content || "Chưa có phản hồi từ mô hình.");
    } catch {
      setAnalysis("Lỗi: Không thể kết nối tới Local AI.");
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
      setDailyBrief("Lỗi: Không thể kết nối tới Local AI.");
    } finally {
      setLoading(false);
    }
  };

  const handleRunBacktest = async () => {
    setLoading(true);
    setBacktestError("");
    setBacktestResult(null);
    try {
      const symbols = universe.split(",").map(s => s.trim().toUpperCase()).filter(Boolean);
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
      setBacktestError(err instanceof Error ? err.message : "Lỗi khi chạy mô phỏng lịch sử.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "20px", maxWidth: "1200px", margin: "0 auto" }}>
      <h1 style={{ fontSize: "1.8rem", marginBottom: "8px", color: "var(--text-primary)" }}>
        Nghiên cứu & Mô phỏng Đầu tư (Research Desk)
      </h1>
      <p style={{ color: "var(--text-muted, #888)", marginBottom: "20px", fontSize: "0.95rem" }}>
        Phân tích bằng chứng điểm-thời-gian (Point-in-Time), kiểm thử lịch sử không rò rỉ dữ liệu (No Look-Ahead), và tổng hợp AI.
      </p>

      <div style={{ display: "flex", gap: "10px", marginBottom: "20px", flexWrap: "wrap" }}>
        <button 
          onClick={() => setActiveTab("stock")}
          style={{ padding: "8px 16px", background: activeTab === "stock" ? "var(--accent-color, #d85636)" : "var(--bg-secondary, #222)", color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}
        >
          Phân tích Cổ phiếu
        </button>
        <button 
          onClick={() => setActiveTab("daily")}
          style={{ padding: "8px 16px", background: activeTab === "daily" ? "var(--accent-color, #d85636)" : "var(--bg-secondary, #222)", color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}
        >
          Daily Market Brief
        </button>
        <button 
          onClick={() => setActiveTab("backtest")}
          style={{ padding: "8px 16px", background: activeTab === "backtest" ? "var(--accent-color, #d85636)" : "var(--bg-secondary, #222)", color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}
        >
          Kiểm thử Lịch sử (PIT Backtest)
        </button>
      </div>

      {activeTab === "stock" && (
        <div style={{ background: "var(--bg-secondary, #1a1a1a)", padding: "20px", borderRadius: "8px" }}>
          <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
            <input 
              type="text" 
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              placeholder="Nhập mã chứng khoán (VD: FPT)"
              style={{ padding: "8px", borderRadius: "4px", border: "1px solid var(--border-color, #444)", background: "var(--bg-primary, #111)", color: "var(--text-primary, #fff)" }}
            />
            <button 
              onClick={generateStockAnalysis}
              disabled={loading}
              style={{ padding: "8px 16px", background: "var(--success-color, #10b981)", color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}
            >
              {loading ? "Đang phân tích..." : "Phân tích bằng AI"}
            </button>
          </div>

          {analysis && (
            <div style={{ background: "var(--bg-primary, #111)", padding: "20px", borderRadius: "8px", whiteSpace: "pre-wrap", lineHeight: "1.6" }}>
              {analysis}
            </div>
          )}
        </div>
      )}

      {activeTab === "daily" && (
        <div style={{ background: "var(--bg-secondary, #1a1a1a)", padding: "20px", borderRadius: "8px" }}>
          <div style={{ marginBottom: "20px" }}>
            <button 
              onClick={generateDailyBrief}
              disabled={loading}
              style={{ padding: "8px 16px", background: "var(--success-color, #10b981)", color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}
            >
              {loading ? "Đang tổng hợp dữ liệu..." : "Tạo báo cáo Vĩ mô & Thị trường hôm nay"}
            </button>
          </div>

          {dailyBrief && (
            <div style={{ background: "var(--bg-primary, #111)", padding: "20px", borderRadius: "8px", whiteSpace: "pre-wrap", lineHeight: "1.6" }}>
              {dailyBrief}
            </div>
          )}
        </div>
      )}

      {activeTab === "backtest" && (
        <div style={{ background: "var(--bg-secondary, #1a1a1a)", padding: "20px", borderRadius: "8px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px", marginBottom: "20px" }}>
            <div>
              <label style={{ display: "block", marginBottom: "6px", fontSize: "0.85rem", color: "#aaa" }}>Vũ trụ đầu tư (Symbols):</label>
              <input 
                type="text" 
                value={universe}
                onChange={(e) => setUniverse(e.target.value)}
                style={{ width: "100%", padding: "8px", borderRadius: "4px", border: "1px solid var(--border-color, #444)", background: "var(--bg-primary, #111)", color: "#fff" }}
              />
            </div>
            <div>
              <label style={{ display: "block", marginBottom: "6px", fontSize: "0.85rem", color: "#aaa" }}>Từ ngày (Start date):</label>
              <input 
                type="date" 
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                style={{ width: "100%", padding: "8px", borderRadius: "4px", border: "1px solid var(--border-color, #444)", background: "var(--bg-primary, #111)", color: "#fff" }}
              />
            </div>
            <div>
              <label style={{ display: "block", marginBottom: "6px", fontSize: "0.85rem", color: "#aaa" }}>Đến ngày (End date):</label>
              <input 
                type="date" 
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                style={{ width: "100%", padding: "8px", borderRadius: "4px", border: "1px solid var(--border-color, #444)", background: "var(--bg-primary, #111)", color: "#fff" }}
              />
            </div>
            <div>
              <label style={{ display: "block", marginBottom: "6px", fontSize: "0.85rem", color: "#aaa" }}>Kỳ tái cân bằng (Horizon):</label>
              <select 
                value={horizon}
                onChange={(e) => setHorizon(e.target.value)}
                style={{ width: "100%", padding: "8px", borderRadius: "4px", border: "1px solid var(--border-color, #444)", background: "var(--bg-primary, #111)", color: "#fff" }}
              >
                <option value="1M">1 Tháng (1M / ~21 phiên)</option>
                <option value="3M">3 Tháng (3M / ~63 phiên)</option>
                <option value="6M">6 Tháng (6M / ~126 phiên)</option>
                <option value="1Y">1 Năm (1Y / ~252 phiên)</option>
              </select>
            </div>
            <div>
              <label style={{ display: "block", marginBottom: "6px", fontSize: "0.85rem", color: "#aaa" }}>Vốn ban đầu (VND):</label>
              <input 
                type="number" 
                value={initialCapital}
                onChange={(e) => setInitialCapital(e.target.value)}
                style={{ width: "100%", padding: "8px", borderRadius: "4px", border: "1px solid var(--border-color, #444)", background: "var(--bg-primary, #111)", color: "#fff" }}
              />
            </div>
          </div>

          <div style={{ display: "flex", gap: "10px", alignItems: "center", marginBottom: "20px" }}>
            <button 
              onClick={handleRunBacktest}
              disabled={loading}
              style={{ padding: "10px 24px", background: "var(--accent-color, #d85636)", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold" }}
            >
              {loading ? "Đang chạy mô phỏng..." : "Chạy Kiểm thử PIT Replay"}
            </button>
            <span style={{ fontSize: "0.85rem", color: "#888" }}>
              Bao gồm: 0.15% phí giao dịch, 0.10% thuế chuyển nhượng, 0.10% trượt giá.
            </span>
          </div>

          {backtestError && (
            <div style={{ padding: "12px", background: "#4a1515", color: "#ff8888", borderRadius: "4px", marginBottom: "16px" }}>
              {backtestError}
            </div>
          )}

          {backtestResult && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px", background: "#1a2a1a", border: "1px solid #2a5a2a", borderRadius: "6px", marginBottom: "16px" }}>
                <span>Trạng thái PIT Integrity: <strong>{String(backtestResult.look_ahead_audit.status)}</strong></span>
                <span>Số lỗi rò rỉ tương lai (Look-ahead violations): <strong>{Number(backtestResult.look_ahead_audit.violations)}</strong></span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "12px", marginBottom: "20px" }}>
                <div style={{ padding: "12px", background: "var(--bg-primary, #111)", borderRadius: "6px" }}>
                  <div style={{ fontSize: "0.8rem", color: "#888" }}>Tổng lợi nhuận ròng</div>
                  <div style={{ fontSize: "1.2rem", fontWeight: "bold", color: backtestResult.total_return >= 0 ? "#10b981" : "#ef4444" }}>
                    {(backtestResult.total_return * 100).toFixed(2)}%
                  </div>
                </div>
                <div style={{ padding: "12px", background: "var(--bg-primary, #111)", borderRadius: "6px" }}>
                  <div style={{ fontSize: "0.8rem", color: "#888" }}>Lợi nhuận Benchmark</div>
                  <div style={{ fontSize: "1.2rem", fontWeight: "bold" }}>
                    {(backtestResult.benchmark_return * 100).toFixed(2)}%
                  </div>
                </div>
                <div style={{ padding: "12px", background: "var(--bg-primary, #111)", borderRadius: "6px" }}>
                  <div style={{ fontSize: "0.8rem", color: "#888" }}>Alpha (vs Benchmark)</div>
                  <div style={{ fontSize: "1.2rem", fontWeight: "bold", color: backtestResult.alpha >= 0 ? "#10b981" : "#ef4444" }}>
                    {(backtestResult.alpha * 100).toFixed(2)}%
                  </div>
                </div>
                <div style={{ padding: "12px", background: "var(--bg-primary, #111)", borderRadius: "6px" }}>
                  <div style={{ fontSize: "0.8rem", color: "#888" }}>Max Drawdown</div>
                  <div style={{ fontSize: "1.2rem", fontWeight: "bold", color: "#ef4444" }}>
                    {(backtestResult.max_drawdown * 100).toFixed(2)}%
                  </div>
                </div>
                <div style={{ padding: "12px", background: "var(--bg-primary, #111)", borderRadius: "6px" }}>
                  <div style={{ fontSize: "0.8rem", color: "#888" }}>Sharpe Ratio</div>
                  <div style={{ fontSize: "1.2rem", fontWeight: "bold" }}>
                    {backtestResult.sharpe_ratio.toFixed(2)}
                  </div>
                </div>
                <div style={{ padding: "12px", background: "var(--bg-primary, #111)", borderRadius: "6px" }}>
                  <div style={{ fontSize: "0.8rem", color: "#888" }}>Tổng lệnh / Phí & Thuế</div>
                  <div style={{ fontSize: "1.1rem", fontWeight: "bold" }}>
                    {backtestResult.total_trades} lệnh | {Math.round(backtestResult.total_fees + backtestResult.total_taxes).toLocaleString()} VND
                  </div>
                </div>
              </div>

              {backtestResult.trades.length > 0 && (
                <div style={{ marginTop: "16px" }}>
                  <h3 style={{ fontSize: "1rem", marginBottom: "8px" }}>Nhật ký Giao dịch Tái cân bằng (Rebalance Log)</h3>
                  <div style={{ maxHeight: "240px", overflowY: "auto", border: "1px solid #333", borderRadius: "6px" }}>
                    <table style={{ width: "100%", fontSize: "0.85rem", borderCollapse: "collapse" }}>
                      <thead>
                        <tr style={{ background: "#222", textAlign: "left" }}>
                          <th style={{ padding: "8px" }}>Ngày</th>
                          <th style={{ padding: "8px" }}>Mã</th>
                          <th style={{ padding: "8px" }}>Lệnh</th>
                          <th style={{ padding: "8px" }}>Số lượng</th>
                          <th style={{ padding: "8px" }}>Giá</th>
                          <th style={{ padding: "8px" }}>Giá trị</th>
                          <th style={{ padding: "8px" }}>Phí + Thuế</th>
                        </tr>
                      </thead>
                      <tbody>
                        {backtestResult.trades.slice(0, 50).map((t, idx) => (
                          <tr key={idx} style={{ borderBottom: "1px solid #222" }}>
                            <td style={{ padding: "6px 8px" }}>{t.date}</td>
                            <td style={{ padding: "6px 8px", fontWeight: "bold" }}>{t.symbol}</td>
                            <td style={{ padding: "6px 8px", color: t.action === "BUY" ? "#10b981" : "#ef4444" }}>{t.action}</td>
                            <td style={{ padding: "6px 8px" }}>{t.shares.toLocaleString()}</td>
                            <td style={{ padding: "6px 8px" }}>{t.price.toLocaleString()}</td>
                            <td style={{ padding: "6px 8px" }}>{Math.round(t.value).toLocaleString()}</td>
                            <td style={{ padding: "6px 8px" }}>{Math.round(t.fee + t.tax).toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
