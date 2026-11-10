"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [authRequired, setAuthRequired] = useState(true);

  useEffect(() => {
    // Check if session is already active or if auth is not configured
    fetch("/api/v1/auth/session")
      .then((res) => res.json())
      .then((data) => {
        if (data.authenticated) {
          router.replace("/");
        } else if (data.reason === "auth_unconfigured") {
          setAuthRequired(false);
        }
      })
      .catch(() => {
        // Fallback for offline or local mode
      });
  }, [router]);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    if (!password) return;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Đăng nhập không thành công.");
      }

      router.replace("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Lỗi xác thực.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "80vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "24px",
    }}>
      <div style={{
        maxWidth: "400px",
        width: "100%",
        background: "var(--card-bg, #12141a)",
        border: "1px solid var(--border-color, rgba(255, 255, 255, 0.08))",
        borderRadius: "16px",
        padding: "32px",
        boxShadow: "0 8px 32px rgba(0, 0, 0, 0.4)",
      }}>
        <div style={{ textAlign: "center", marginBottom: "28px" }}>
          <h1 style={{ fontSize: "22px", fontWeight: 700, margin: "0 0 8px 0", color: "var(--ink-primary, #ffffff)" }}>
            InvestIntel Terminal
          </h1>
          <p style={{ fontSize: "13px", color: "var(--ink-secondary, #9ca3af)", margin: 0 }}>
            Hệ thống phân tích đầu tư thể chế cá nhân
          </p>
        </div>

        {error && (
          <div style={{
            background: "rgba(239, 68, 68, 0.12)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            color: "#f87171",
            padding: "10px 14px",
            borderRadius: "8px",
            fontSize: "13px",
            marginBottom: "20px",
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div>
            <label style={{ display: "block", fontSize: "12px", color: "var(--ink-secondary, #9ca3af)", marginBottom: "6px" }}>
              Mật khẩu truy cập
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Nhập mật khẩu..."
              required
              disabled={loading}
              style={{
                width: "100%",
                padding: "10px 14px",
                borderRadius: "8px",
                border: "1px solid var(--border-color, rgba(255, 255, 255, 0.15))",
                background: "rgba(255, 255, 255, 0.04)",
                color: "#ffffff",
                fontSize: "14px",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              padding: "11px 16px",
              borderRadius: "8px",
              border: "none",
              background: "var(--accent-primary, #3b82f6)",
              color: "#ffffff",
              fontWeight: 600,
              fontSize: "14px",
              cursor: loading ? "not-allowed" : "pointer",
              opacity: loading ? 0.7 : 1,
              transition: "opacity 0.2s",
            }}
          >
            {loading ? "Đang xác thực..." : "Đăng nhập"}
          </button>
        </form>

        <div style={{ marginTop: "24px", textAlign: "center", borderTop: "1px solid var(--border-color, rgba(255, 255, 255, 0.08))", paddingTop: "16px" }}>
          {!authRequired && (
            <p style={{ fontSize: "12px", color: "var(--ink-tertiary, #6b7280)", margin: "0 0 10px 0" }}>
              Chế độ cục bộ (không bật mật khẩu máy trạm)
            </p>
          )}
          <Link
            href="/"
            style={{
              fontSize: "13px",
              color: "var(--ink-secondary, #9ca3af)",
              textDecoration: "none",
            }}
          >
            ← Quay lại Bàn làm việc
          </Link>
        </div>
      </div>
    </div>
  );
}
