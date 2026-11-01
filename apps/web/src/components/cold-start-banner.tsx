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
    const timer = setTimeout(() => {
      checkHealth();
    }, 1500);

    return () => clearTimeout(timer);
  }, []);

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
        background: "#FEF7E0",
        borderBottom: "1px solid rgba(176, 96, 0, 0.2)",
        color: "#B06000",
        padding: "10px 24px",
        fontSize: "12.5px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexWrap: "wrap",
        gap: "12px",
        zIndex: 999,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <span style={{ fontSize: "14px" }}>⚡</span>
        <div>
          <strong style={{ fontWeight: 650 }}>Máy chủ đang khởi động (Render Cold Start)...</strong>
          <span style={{ color: "#78350F", marginLeft: "6px" }}>
            Quá trình có thể mất 30–50 giây. Dữ liệu của bạn được bảo toàn an toàn.
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
          background: "#1D1D1F",
          color: "#FFFFFF",
          border: "none",
          padding: "5px 14px",
          borderRadius: "999px",
          cursor: checking ? "wait" : "pointer",
          fontSize: "12px",
          fontWeight: 600,
          transition: "opacity 150ms ease",
          opacity: checking ? 0.6 : 1,
        }}
      >
        {checking ? "Đang kiểm tra..." : "Kiểm tra lại"}
      </button>
    </div>
  );
}
