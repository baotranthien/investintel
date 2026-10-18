"use client";

import { useEffect, useState } from "react";

export default function DataCenter() {
  const [providers, setProviders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/data/providers")
      .then((res) => res.json())
      .then((data) => {
        setProviders(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to fetch providers", err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Đang tải dữ liệu...</div>;

  return (
    <div style={{ padding: "20px" }}>
      <h1 style={{ fontSize: "1.5rem", marginBottom: "20px", color: "var(--text-primary)" }}>
        Data Center / Trung tâm Dữ liệu
      </h1>
      
      <div className="dashboard-grid">
        {providers.map((p) => (
          <div key={p.provider} className="card">
            <div className="card-title">{p.provider}</div>
            
            <div style={{ marginBottom: "10px" }}>
              <strong>Status: </strong> 
              <span className={p.status === "IMPLEMENTED" ? "text-success" : "text-danger"}>
                {p.status}
              </span>
            </div>
            
            <div style={{ fontSize: "0.875rem", color: "var(--text-secondary)", marginBottom: "5px" }}>
              Last Success: {p.last_success || "N/A"}
            </div>
            
            <div style={{ fontSize: "0.875rem", color: "var(--text-secondary)", marginBottom: "5px" }}>
              Records: {p.records_last_run}
            </div>

            <div style={{ fontSize: "0.875rem", color: "var(--text-secondary)", marginBottom: "15px" }}>
              Freshness: {p.data_freshness}
            </div>

            <button 
              style={{
                background: "var(--accent-color)",
                color: "white",
                border: "none",
                padding: "8px 12px",
                borderRadius: "6px",
                cursor: "pointer",
                width: "100%"
              }}
              onClick={() => alert("This feature is for admin manual override only.")}
            >
              Run Now / Chạy ngay
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
