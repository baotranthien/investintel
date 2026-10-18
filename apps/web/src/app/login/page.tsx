"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { loginUser } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password.trim()) return;

    setLoading(true);
    setError(null);

    try {
      await loginUser(password);
      router.push("/");
      router.refresh();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Đăng nhập không thành công. Vui lòng kiểm tra lại mật khẩu.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "70vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "400px",
          background: "#1e293b",
          border: "1px solid #334155",
          borderRadius: "8px",
          padding: "32px",
          boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.3)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#f8fafc", margin: "0 0 8px 0" }}>
            InvestIntel
          </h1>
          <p style={{ fontSize: "0.875rem", color: "#94a3b8", margin: 0 }}>
            Xác thực tài khoản cá nhân để truy cập dữ liệu tài chính
          </p>
        </div>

        {error && (
          <div
            role="alert"
            style={{
              background: "#450a0a",
              border: "1px solid #7f1d1d",
              color: "#fca5a5",
              padding: "12px",
              borderRadius: "6px",
              fontSize: "0.875rem",
              marginBottom: "20px",
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "20px" }}>
            <label
              htmlFor="auth-password"
              style={{
                display: "block",
                fontSize: "0.85rem",
                color: "#cbd5e1",
                marginBottom: "8px",
                fontWeight: 500,
              }}
            >
              Mật khẩu ứng dụng
            </label>
            <input
              id="auth-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Nhập mật khẩu cá nhân..."
              required
              disabled={loading}
              style={{
                width: "100%",
                padding: "10px 14px",
                background: "#0f172a",
                border: "1px solid #475569",
                borderRadius: "6px",
                color: "#f8fafc",
                fontSize: "0.95rem",
                boxSizing: "border-box",
              }}
            />
          </div>

          <button
            type="submit"
            disabled={loading || !password.trim()}
            style={{
              width: "100%",
              padding: "12px",
              background: loading ? "#64748b" : "#2563eb",
              color: "#ffffff",
              border: "none",
              borderRadius: "6px",
              fontSize: "0.95rem",
              fontWeight: 600,
              cursor: loading ? "wait" : "pointer",
              transition: "background 0.2s",
            }}
          >
            {loading ? "Đang xác thực..." : "Đăng nhập an toàn"}
          </button>
        </form>

        <p
          style={{
            fontSize: "0.75rem",
            color: "#64748b",
            textAlign: "center",
            marginTop: "24px",
            lineHeight: 1.5,
          }}
        >
          Phiên làm việc được mã hóa và bảo vệ qua cookie HttpOnly SameSite=Strict.
        </p>
      </div>
    </div>
  );
}
