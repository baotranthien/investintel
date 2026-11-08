"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { SkeletonCard } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";

export default function ValuationDashboard() {
  const [symbol, setSymbol] = useState("FPT");
  const [valuationData, setValuationData] = useState<any>(null);
  const [factorData, setFactorData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const SYMBOLS = ["FPT", "VCB", "MBB", "MWG", "HPG"];

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError("");
      try {
        const valRes = await fetch(`/api/v1/valuation/${symbol}`);
        if (!valRes.ok) throw new Error("Failed to fetch valuation data");
        const valData = await valRes.json();
        
        const facRes = await fetch(`/api/v1/factors/${symbol}`);
        if (!facRes.ok) throw new Error("Failed to fetch factor data");
        const facData = await facRes.json();
        
        setValuationData(valData);
        setFactorData(facData);
      } catch (err: any) {
        setError(err.message || "An error occurred");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [symbol]);

  return (
    <div style={{ padding: "20px", maxWidth: "1200px", margin: "0 auto" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <div>
          <p style={{ margin: "0 0 4px 0", fontSize: "12px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--ink-muted)" }}>
            Mô hình định lượng · Phân tích cơ bản
          </p>
          <h1 style={{ fontSize: "1.8rem", color: "var(--text-primary)", margin: 0 }}>
            Mô hình định giá & phân tích nhân tố
          </h1>
        </div>
        <div>
          <select 
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            style={{
              padding: "8px 16px",
              background: "var(--bg-secondary)",
              color: "var(--text-primary)",
              border: "1px solid var(--border-color)",
              borderRadius: "4px",
              fontSize: "1rem"
            }}
          >
            {SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </header>

      {error && <div className="text-danger" style={{ marginBottom: "20px" }}>{error}</div>}
      
      {loading ? (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
          <SkeletonCard height={320} />
          <SkeletonCard height={320} />
        </div>
      ) : valuationData && factorData ? (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
          
          {/* VALUATION PANEL */}
          <div className="card">
            <h2 className="card-title">Định giá cổ phiếu (VND)</h2>
            <div style={{ marginBottom: "15px", fontSize: "1.2rem" }}>
              Thị giá hiện tại: <strong>{valuationData.price_as_of.toLocaleString()}</strong>
            </div>
            
            <div style={{ marginBottom: "20px" }}>
              <div style={{ marginBottom: "5px", color: "var(--text-secondary)" }}>Khoảng giá trị hợp lý:</div>
              <div style={{ display: "flex", justifyContent: "space-between", background: "var(--bg-secondary)", padding: "10px", borderRadius: "6px" }}>
                <div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Kịch bản thận trọng (Bear)</div>
                  <strong className="text-danger">{Math.round(valuationData.composite_fair_value.range.bear).toLocaleString()}</strong>
                </div>
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Kịch bản cơ sở (Base)</div>
                  <strong>{Math.round(valuationData.composite_fair_value.range.base).toLocaleString()}</strong>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Kịch bản khả quan (Bull)</div>
                  <strong className="text-success">{Math.round(valuationData.composite_fair_value.range.bull).toLocaleString()}</strong>
                </div>
              </div>
            </div>

            <div style={{ marginBottom: "15px" }}>
              <div style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                Độ tin cậy: <strong style={{ color: "var(--text-primary)" }}>{valuationData.composite_fair_value.confidence === "HIGH" ? "Cao" : valuationData.composite_fair_value.confidence === "MODERATE" ? "Khá" : valuationData.composite_fair_value.confidence}</strong>
              </div>
              {valuationData.composite_fair_value.method_disagreement && (
                <div className="text-danger" style={{ fontSize: "0.85rem", marginTop: "4px" }}>
                  Độ lệch phương pháp: {valuationData.composite_fair_value.disagreement_reason}
                </div>
              )}
            </div>

            <h3 style={{ fontSize: "1.1rem", marginBottom: "10px", marginTop: "20px", color: "var(--text-primary)" }}>Chi tiết từng phương pháp</h3>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border-color)", textAlign: "left" }}>
                  <th style={{ padding: "8px 0" }}>Phương pháp</th>
                  <th style={{ padding: "8px 0" }}>Giá trị hợp lý (Cơ sở)</th>
                  <th style={{ padding: "8px 0" }}>Tỷ trọng</th>
                </tr>
              </thead>
              <tbody>
                {valuationData.methods.map((m: any, idx: number) => (
                  <tr key={idx} style={{ borderBottom: "1px solid var(--border-color)" }}>
                    <td style={{ padding: "8px 0" }}>{m.method}</td>
                    <td style={{ padding: "8px 0" }}>{Math.round(m.fair_value.base).toLocaleString()}</td>
                    <td style={{ padding: "8px 0" }}>{(m.weight * 100).toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* FACTOR PANEL */}
          <div className="card">
            <h2 className="card-title">Hồ sơ nhân tố đầu tư</h2>
            
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "20px" }}>
              {[
                factorData.quality, 
                factorData.growth, 
                factorData.value, 
                factorData.dividend, 
                factorData.momentum, 
                factorData.defensive, 
                factorData.cyclical
              ].map(f => (
                <div key={f.name} style={{ background: "var(--bg-secondary)", padding: "10px", borderRadius: "6px" }}>
                  <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>{f.name}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <strong style={{ fontSize: "1.2rem" }}>{Math.round(f.score)}</strong>
                    <div style={{ flex: 1, height: "4px", background: "var(--border-color)", borderRadius: "2px", overflow: "hidden" }}>
                      <div style={{ width: `${f.score}%`, height: "100%", background: f.score > 70 ? "var(--accent-color)" : f.score < 40 ? "#ef4444" : "#8b5cf6" }} />
                    </div>
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                    {f.drivers[0]}
                  </div>
                </div>
              ))}
            </div>

            {factorData.conflicts.length > 0 && (
              <div style={{ background: "rgba(239, 68, 68, 0.1)", padding: "10px", borderRadius: "6px", border: "1px solid #ef4444" }}>
                <strong style={{ color: "#ef4444", fontSize: "0.9rem" }}>Xung đột giữa các nhân tố:</strong>
                <ul style={{ margin: "5px 0 0 20px", padding: 0, fontSize: "0.85rem", color: "var(--text-primary)" }}>
                  {factorData.conflicts.map((c: string, i: number) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          
        </div>
      ) : null}
      
    </div>
  );
}
