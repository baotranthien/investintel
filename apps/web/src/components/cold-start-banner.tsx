"use client";

import { useEffect, useState } from "react";

export default function ColdStartBanner() {
  const [isWaking, setIsWaking] = useState(false);
  const [checking, setChecking] = useState(false);
  const [attempt, setAttempt] = useState(0);

  const checkHealth = async () => {
    setChecking(true);
    try {
      const res = await fetch("/api/v1/health", { cache: "no-store", credentials: "include" });
      if (res.ok) {
        setIsWaking(false);
      } else {
        setIsWaking(true);
      }
    } catch {
      setIsWaking(true);
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    // Check initial connectivity quietly
    const timer = setTimeout(() => {
      checkHealth();
    }, 1500);

    return () => clearTimeout(timer);
  }, []);

  // When waking, poll every 8 seconds up to 6 times
  useEffect(() => {
    if (!isWaking || attempt >= 6) return;
    const interval = setInterval(() => {
      setAttempt((prev) => prev + 1);
      checkHealth();
    }, 8000);
    return () => clearInterval(interval);
  }, [isWaking, attempt]);

  if (!isWaking) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        background: "linear-gradient(90deg, #1e293b 0%, #0f172a 100%)",
        borderBottom: "1px solid #334155",
        color: "#f8fafc",
        padding: "10px 16px",
        fontSize: "0.875rem",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexWrap: "wrap",
        gap: "8px",
        zIndex: 999,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <span style={{ fontSize: "1.1rem" }}>⚡</span>
        <div>
          <strong>Máy chủ đang thức giấc (Render Free Cold Start)...</strong>
          <span style={{ color: "#94a3b8", marginLeft: "6px" }}>
            Quá trình khởi động container miễn phí có thể mất 30–50 giây. Dữ liệu của bạn được bảo toàn nguyên vẹn.
          </span>
        </div>
      </div>
      <button
        type="button"
        onClick={() => {
          setAttempt(0);
          checkHealth();
        }}
        disabled={checking}
        style={{
          background: "#3b82f6",
          color: "#fff",
          border: "none",
          padding: "6px 12px",
          borderRadius: "4px",
          cursor: checking ? "wait" : "pointer",
          fontSize: "0.8rem",
          fontWeight: 500,
        }}
      >
        {checking ? "Đang kiểm tra..." : "Kiểm tra lại"}
      </button>
    </div>
  );
}
