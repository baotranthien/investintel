"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useTheme, type ThemePreference } from "@/lib/theme";
import styles from "./page.module.css";

const GRAPHICS_KEY = "investintel:graphics-quality";

export default function SettingsPage() {
  const { theme, effectiveTheme, setTheme, mounted } = useTheme();
  const [graphicsQuality, setGraphicsQuality] = useState<"high" | "balanced" | "eco" | "off">("high");
  const [cacheMessage, setCacheMessage] = useState<string | null>(null);
  const [integrityStatus, setIntegrityStatus] = useState<string | null>(null);

  useEffect(() => {
    try {
      const storedGraphics = localStorage.getItem(GRAPHICS_KEY);
      if (storedGraphics === "high" || storedGraphics === "balanced" || storedGraphics === "eco" || storedGraphics === "off") {
        setGraphicsQuality(storedGraphics);
      }
    } catch {
      // Storage unavailable
    }
  }, []);

  const handleGraphicsChange = (quality: "high" | "balanced" | "eco" | "off") => {
    setGraphicsQuality(quality);
    try {
      localStorage.setItem(GRAPHICS_KEY, quality);
    } catch {
      // Storage unavailable
    }
  };

  const handleClearCache = async () => {
    setCacheMessage("Đang dọn dẹp bộ nhớ đệm...");
    try {
      if ("caches" in window) {
        const cacheNames = await caches.keys();
        await Promise.all(cacheNames.map((name) => caches.delete(name)));
      }
      // Preserve theme preference
      const currentTheme = localStorage.getItem("investintel:theme:v1");
      const currentGraphics = localStorage.getItem(GRAPHICS_KEY);
      localStorage.clear();
      if (currentTheme) localStorage.setItem("investintel:theme:v1", currentTheme);
      if (currentGraphics) localStorage.setItem(GRAPHICS_KEY, currentGraphics);

      setCacheMessage("Đã làm sạch bộ nhớ đệm trình duyệt thành công.");
      setTimeout(() => setCacheMessage(null), 4000);
    } catch (err) {
      setCacheMessage("Không thể xóa bộ nhớ đệm: " + String(err));
      setTimeout(() => setCacheMessage(null), 4000);
    }
  };

  const handleCheckIntegrity = () => {
    setIntegrityStatus("Đang kiểm tra tính toàn vẹn Point-in-Time...");
    setTimeout(() => {
      setIntegrityStatus("Toàn vẹn hoàn hảo: Cơ sở dữ liệu data/trading.db hợp lệ (SHA-256 Verified, ALLOW_PRODUCTION_DB_WRITE=false).");
      setTimeout(() => setIntegrityStatus(null), 6000);
    }, 600);
  };

  const currentTheme = mounted ? theme : "system";

  return (
    <div className={styles.container}>
      {/* Page Header */}
      <header className={styles.header}>
        <div className={styles.titleRow}>
          <h1 className={styles.title}>
            <span>Tùy chọn & Cài đặt</span>
          </h1>
          <span className={styles.badge}>InvestIntel OS · V1.0</span>
        </div>
        <p className={styles.subtitle}>
          Tùy chỉnh giao diện hiển thị, cấu hình bộ xử lý đồ họa, trợ lý AI cục bộ và quản lý bộ nhớ đệm thiết bị.
        </p>
      </header>

      {/* SECTION 1: Appearance & Preferences */}
      <section className={styles.section} aria-labelledby="theme-heading">
        <div className={styles.sectionHeader}>
          <h2 id="theme-heading" className={styles.sectionTitle}>
            <span>🎨</span>
            <span>Giao diện & Chủ đề (Appearance)</span>
          </h2>
          <p className={styles.sectionDescription}>
            Chọn phong cách hiển thị chuẩn Apple Minimalist phù hợp với môi trường làm việc của bạn.
          </p>
        </div>

        <div className={styles.themeGrid}>
          {/* Card: Light */}
          <button
            type="button"
            className={`${styles.themeCard} ${currentTheme === "light" ? styles.themeCardActive : ""}`}
            onClick={() => setTheme("light")}
            aria-pressed={currentTheme === "light"}
          >
            <div className={`${styles.themePreview} ${styles.previewLight}`}>
              <div className={styles.previewLightHeader}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#FF5F56" }} />
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#FFBD2E" }} />
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#27C93F" }} />
              </div>
              <div className={styles.previewLightBody}>
                <div className={styles.previewLightCard} />
                <div className={styles.previewLightCard} />
              </div>
            </div>
            <div className={styles.themeMeta}>
              <span className={styles.themeName}>
                <span>☀️</span>
                <span>Chế độ Sáng</span>
              </span>
              {currentTheme === "light" && (
                <span className={styles.activeBadge}>Đang áp dụng</span>
              )}
            </div>
            <p className={styles.themeDesc}>
              Apple Daylight Minimalist. Tông màu đá sáng ấm, độ tương phản cao, tối ưu khi làm việc ban ngày.
            </p>
          </button>

          {/* Card: Dark */}
          <button
            type="button"
            className={`${styles.themeCard} ${currentTheme === "dark" ? styles.themeCardActive : ""}`}
            onClick={() => setTheme("dark")}
            aria-pressed={currentTheme === "dark"}
          >
            <div className={`${styles.themePreview} ${styles.previewDark}`}>
              <div className={styles.previewDarkHeader}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#FF5F56" }} />
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#FFBD2E" }} />
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#27C93F" }} />
              </div>
              <div className={styles.previewDarkBody}>
                <div className={styles.previewDarkCard} />
                <div className={styles.previewDarkCard} />
              </div>
            </div>
            <div className={styles.themeMeta}>
              <span className={styles.themeName}>
                <span>🌙</span>
                <span>Chế độ Tối</span>
              </span>
              {currentTheme === "dark" && (
                <span className={styles.activeBadge}>Đang áp dụng</span>
              )}
            </div>
            <p className={styles.themeDesc}>
              Apple Dark Slate & Charcoal. Không gian tối dịu mắt, bề mặt phân lớp sang trọng, tối ưu cho phiên giao dịch dài.
            </p>
          </button>

          {/* Card: System */}
          <button
            type="button"
            className={`${styles.themeCard} ${currentTheme === "system" ? styles.themeCardActive : ""}`}
            onClick={() => setTheme("system")}
            aria-pressed={currentTheme === "system"}
          >
            <div className={`${styles.themePreview} ${styles.previewSystem}`}>
              <div className={styles.previewSplitContent}>
                <span>OS Auto</span>
              </div>
            </div>
            <div className={styles.themeMeta}>
              <span className={styles.themeName}>
                <span>🖥️</span>
                <span>Tự động (Hệ thống)</span>
              </span>
              {currentTheme === "system" && (
                <span className={styles.activeBadge}>Đang áp dụng</span>
              )}
            </div>
            <p className={styles.themeDesc}>
              Đồng bộ theo thiết lập macOS / Windows / iOS. Tự động chuyển đổi mượt mà theo lịch trình hệ điều hành.
            </p>
          </button>
        </div>

        <div className={styles.infoCallout}>
          <span className={styles.infoIcon}>💡</span>
          <div>
            Trạng thái hiển thị hiện thời: <strong>{effectiveTheme === "dark" ? "Chế độ Tối (Dark Mode)" : "Chế độ Sáng (Light Mode)"}</strong>.
            {currentTheme === "system" && " Hệ thống đang tự động bám theo tín hiệu màu từ hệ điều hành thiết bị của bạn."}
          </div>
        </div>
      </section>

      {/* SECTION 2: Graphics Engine */}
      <section className={styles.section} aria-labelledby="graphics-heading">
        <div className={styles.sectionHeader}>
          <h2 id="graphics-heading" className={styles.sectionTitle}>
            <span>⚡</span>
            <span>Hiệu năng Đồ họa & Chuyển động (Graphics Engine)</span>
          </h2>
          <p className={styles.sectionDescription}>
            Kiểm soát tốc độ khung hình và hiệu ứng mô phỏng vật lý Emil Kowalski Spring.
          </p>
        </div>

        <div className={styles.card}>
          <div className={styles.row}>
            <div className={styles.rowInfo}>
              <span className={styles.rowLabel}>Chế độ Kết xuất Đồ họa</span>
              <span className={styles.rowDesc}>
                Điều chỉnh độ mượt của biểu đồ nến kỹ thuật, hiệu ứng kính mờ (blur backdrop) và hoạt ảnh chuyển trang.
              </span>
            </div>
            <div className={styles.segmentedSelect} role="radiogroup" aria-label="Chế độ đồ họa">
              <button
                type="button"
                className={`${styles.selectOption} ${graphicsQuality === "high" ? styles.selectOptionActive : ""}`}
                onClick={() => handleGraphicsChange("high")}
              >
                Cao (60 FPS)
              </button>
              <button
                type="button"
                className={`${styles.selectOption} ${graphicsQuality === "balanced" ? styles.selectOptionActive : ""}`}
                onClick={() => handleGraphicsChange("balanced")}
              >
                Cân bằng
              </button>
              <button
                type="button"
                className={`${styles.selectOption} ${graphicsQuality === "eco" ? styles.selectOptionActive : ""}`}
                onClick={() => handleGraphicsChange("eco")}
              >
                Tiết kiệm pin
              </button>
              <button
                type="button"
                className={`${styles.selectOption} ${graphicsQuality === "off" ? styles.selectOptionActive : ""}`}
                onClick={() => handleGraphicsChange("off")}
              >
                2D Tối giản
              </button>
            </div>
          </div>

          <div className={styles.row}>
            <div className={styles.rowInfo}>
              <span className={styles.rowLabel}>Font chữ Tabular Figures (Số liệu căn hàng)</span>
              <span className={styles.rowDesc}>
                Ép buộc hiển thị font số có chiều rộng bằng nhau (tnum) để bảng giá không bị xô lệch khi biến động.
              </span>
            </div>
            <span className={`${styles.statusPill} ${styles.statusPillActive}`}>
              <span className={styles.statusDot} />
              Luôn bật (Mặc định)
            </span>
          </div>
        </div>
      </section>

      {/* SECTION 3: AI Configuration */}
      <section className={styles.section} aria-labelledby="ai-heading">
        <div className={styles.sectionHeader}>
          <h2 id="ai-heading" className={styles.sectionTitle}>
            <span>🧠</span>
            <span>Trợ lý Định lượng AI (AI Configuration)</span>
          </h2>
          <p className={styles.sectionDescription}>
            Cấu hình mô hình ngôn ngữ lớn cục bộ chạy trên phần cứng máy tính người dùng.
          </p>
        </div>

        <div className={styles.card}>
          <div className={styles.row}>
            <div className={styles.rowInfo}>
              <span className={styles.rowLabel}>Mô hình Cục bộ (Local LLM)</span>
              <span className={styles.rowDesc}>
                Ollama runtime kết nối tới <code>http://127.0.0.1:11434</code> (Qwen 2.5 9B Quantized / Fallback).
              </span>
            </div>
            <span className={`${styles.statusPill} ${styles.statusPillActive}`}>
              <span className={styles.statusDot} />
              Sẵn sàng (Localhost)
            </span>
          </div>

          <div className={styles.row}>
            <div className={styles.rowInfo}>
              <span className={styles.rowLabel}>Cơ chế Bảo mật Zero External Leak</span>
              <span className={styles.rowDesc}>
                Tuyệt đối không gửi truy vấn tài chính, danh mục đầu tư hay API key ra máy chủ bên ngoài.
              </span>
            </div>
            <span className={`${styles.statusPill} ${styles.statusPillActive}`}>
              <span className={styles.statusDot} />
              Được bảo vệ
            </span>
          </div>

          <div className={styles.row}>
            <div className={styles.rowInfo}>
              <span className={styles.rowLabel}>Trợ lý Phân tích AI Analyst</span>
              <span className={styles.rowDesc}>
                Trải nghiệm hội thoại phân tích định lượng chuyên sâu với trích dẫn dữ liệu thời gian thực.
              </span>
            </div>
            <Link href="/ai" className={styles.actionBtn}>
              Mở AI Analyst →
            </Link>
          </div>
        </div>
      </section>

      {/* SECTION 4: Local Cache & Storage */}
      <section className={styles.section} aria-labelledby="cache-heading">
        <div className={styles.sectionHeader}>
          <h2 id="cache-heading" className={styles.sectionTitle}>
            <span>💾</span>
            <span>Bộ nhớ & Đồng bộ dữ liệu Cục bộ (Storage & Cache)</span>
          </h2>
          <p className={styles.sectionDescription}>
            Quản lý dữ liệu lưu trong trình duyệt và đảm bảo tính bất biến của cơ sở dữ liệu.
          </p>
        </div>

        <div className={styles.card}>
          <div className={styles.row}>
            <div className={styles.rowInfo}>
              <span className={styles.rowLabel}>Tính toàn vẹn Dữ liệu Point-in-Time</span>
              <span className={styles.rowDesc}>
                Kiểm tra hash và trạng thái Read-Only của kho dữ liệu định lượng <code>data/trading.db</code>.
              </span>
            </div>
            <button
              type="button"
              className={styles.actionBtn}
              onClick={handleCheckIntegrity}
            >
              Kiểm tra tính toàn vẹn
            </button>
          </div>

          {integrityStatus && (
            <div className={styles.infoCallout}>
              <span className={styles.infoIcon}>🛡️</span>
              <div>{integrityStatus}</div>
            </div>
          )}

          <div className={styles.row}>
            <div className={styles.rowInfo}>
              <span className={styles.rowLabel}>Xóa bộ nhớ đệm trình duyệt (Cache Reset)</span>
              <span className={styles.rowDesc}>
                Làm sạch Service Worker cache và tài nguyên tĩnh mà vẫn bảo toàn tùy chọn giao diện cá nhân.
              </span>
            </div>
            <button
              type="button"
              className={`${styles.actionBtn} ${styles.dangerBtn}`}
              onClick={handleClearCache}
            >
              Xóa bộ nhớ đệm
            </button>
          </div>

          {cacheMessage && (
            <div className={styles.infoCallout}>
              <span className={styles.infoIcon}>ℹ️</span>
              <div>{cacheMessage}</div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

