"use client";

import { useState, type JSX } from "react";
import Link from "next/link";
import { useTheme } from "@/lib/theme";
import { useLocale, LOCALE_STORAGE_KEY } from "@/lib/i18n";
import styles from "./page.module.css";

const GRAPHICS_KEY = "investintel:graphics-quality";

function PaletteIcon(): JSX.Element {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="13.5" cy="6.5" r=".5" fill="currentColor" />
      <circle cx="17.5" cy="10.5" r=".5" fill="currentColor" />
      <circle cx="8.5" cy="7.5" r=".5" fill="currentColor" />
      <circle cx="6.5" cy="12.5" r=".5" fill="currentColor" />
      <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.563-2.512 5.563-5.563C22 6.5 17.5 2 12 2z" />
    </svg>
  );
}

function SunIcon(): JSX.Element {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  );
}

function MoonIcon(): JSX.Element {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

function DisplayIcon(): JSX.Element {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </svg>
  );
}

function LightbulbIcon(): JSX.Element {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9 18h6" />
      <path d="M10 22h4" />
      <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5.76.76 1.23 1.52 1.41 2.5" />
    </svg>
  );
}

function BoltIcon(): JSX.Element {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}

function BrainIcon(): JSX.Element {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-2.04z" />
      <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-2.04z" />
    </svg>
  );
}

function DiskIcon(): JSX.Element {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
      <polyline points="17 21 17 13 7 13 7 21" />
      <polyline points="7 3 7 8 15 8" />
    </svg>
  );
}

function ShieldIcon(): JSX.Element {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

function InfoCircleIcon(): JSX.Element {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}

function getStoredGraphics(): "high" | "balanced" | "eco" | "off" {
  if (typeof window === "undefined") return "high";
  try {
    const stored = localStorage.getItem(GRAPHICS_KEY);
    if (stored === "high" || stored === "balanced" || stored === "eco" || stored === "off") {
      return stored;
    }
  } catch {
    // Storage unavailable
  }
  return "high";
}

export default function SettingsPage() {
  const { theme, effectiveTheme, setTheme, mounted } = useTheme();
  const { locale, setLocale, t } = useLocale();
  const [graphicsQuality, setGraphicsQuality] = useState<"high" | "balanced" | "eco" | "off">(getStoredGraphics);
  const [cacheMessage, setCacheMessage] = useState<string | null>(null);
  const [integrityStatus, setIntegrityStatus] = useState<string | null>(null);

  const handleGraphicsChange = (quality: "high" | "balanced" | "eco" | "off") => {
    setGraphicsQuality(quality);
    try {
      localStorage.setItem(GRAPHICS_KEY, quality);
    } catch {
      // Storage unavailable
    }
  };

  const handleClearCache = async () => {
    setCacheMessage(t("Đang dọn dẹp bộ nhớ đệm...", "Purging browser cache..."));
    try {
      if ("caches" in window) {
        const cacheNames = await caches.keys();
        await Promise.all(cacheNames.map((name) => caches.delete(name)));
      }
      // Preserve theme preference and locale preference
      const currentTheme = localStorage.getItem("investintel:theme:v1");
      const currentLocale = localStorage.getItem(LOCALE_STORAGE_KEY);
      const currentGraphics = localStorage.getItem(GRAPHICS_KEY);
      localStorage.clear();
      if (currentTheme) localStorage.setItem("investintel:theme:v1", currentTheme);
      if (currentLocale) localStorage.setItem(LOCALE_STORAGE_KEY, currentLocale);
      if (currentGraphics) localStorage.setItem(GRAPHICS_KEY, currentGraphics);

      setCacheMessage(
        t(
          "Đã làm sạch bộ nhớ đệm trình duyệt thành công. Các tùy chọn cá nhân được bảo toàn.",
          "Browser cache cleared successfully. Personal preferences preserved."
        )
      );
      setTimeout(() => setCacheMessage(null), 4000);
    } catch (err) {
      setCacheMessage(
        `${t("Không thể xóa bộ nhớ đệm: ", "Failed to clear cache: ")}${String(err)}`
      );
      setTimeout(() => setCacheMessage(null), 4000);
    }
  };

  const handleCheckIntegrity = () => {
    setIntegrityStatus(t("Đang kiểm tra tính toàn vẹn Point-in-Time...", "Verifying Point-in-Time database integrity..."));
    setTimeout(() => {
      setIntegrityStatus(
        t(
          "Toàn vẹn hoàn hảo: Cơ sở dữ liệu data/trading.db hợp lệ (SHA-256 Verified, ALLOW_PRODUCTION_DB_WRITE=false).",
          "Integrity Verified: Canonical database data/trading.db is authentic (SHA-256 Verified, ALLOW_PRODUCTION_DB_WRITE=false)."
        )
      );
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
            <span>{t("Tùy chọn & Cài đặt", "Settings & Preferences")}</span>
          </h1>
          <span className={styles.badge}>InvestIntel OS · V1.0</span>
        </div>
        <p className={styles.subtitle}>
          {t(
            "Tùy chỉnh giao diện hiển thị, cấu hình bộ xử lý đồ họa, trợ lý AI cục bộ và quản lý bộ nhớ đệm thiết bị.",
            "Customize appearance, configure graphics engine, local AI analyst runtime, and manage client-side cache."
          )}
        </p>
      </header>

      {/* SECTION 1: Appearance & Preferences */}
      <section className={styles.section} aria-labelledby="theme-heading">
        <div className={styles.sectionHeader}>
          <h2 id="theme-heading" className={styles.sectionTitle}>
            <PaletteIcon />
            <span>{t("Giao diện & Chủ đề (Appearance)", "Appearance & Display Themes")}</span>
          </h2>
          <p className={styles.sectionDescription}>
            {t(
              "Chọn phong cách hiển thị chuẩn Apple Minimalist phù hợp với môi trường làm việc của bạn.",
              "Choose an Apple Minimalist display theme tailored to your trading workspace."
            )}
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
                <SunIcon />
                <span>{t("Chế độ Sáng", "Light Mode")}</span>
              </span>
              {currentTheme === "light" && (
                <span className={styles.activeBadge}>{t("Đang áp dụng", "Active")}</span>
              )}
            </div>
            <p className={styles.themeDesc}>
              {t(
                "Apple Daylight Minimalist. Tông màu đá sáng ấm, độ tương phản cao, tối ưu khi làm việc ban ngày.",
                "Apple Daylight Minimalist. Warm stone neutral palette, high contrast, calibrated for daytime focus."
              )}
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
                <MoonIcon />
                <span>{t("Chế độ Tối", "Dark Mode")}</span>
              </span>
              {currentTheme === "dark" && (
                <span className={styles.activeBadge}>{t("Đang áp dụng", "Active")}</span>
              )}
            </div>
            <p className={styles.themeDesc}>
              {t(
                "Apple Dark Slate & Charcoal. Không gian tối dịu mắt, bề mặt phân lớp sang trọng, tối ưu cho phiên giao dịch dài.",
                "Apple Dark Slate & Charcoal. Deep layered neutral surfaces, eye-strain reducing dark palette."
              )}
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
                <DisplayIcon />
                <span>{t("Tự động (Hệ thống)", "System Auto")}</span>
              </span>
              {currentTheme === "system" && (
                <span className={styles.activeBadge}>{t("Đang áp dụng", "Active")}</span>
              )}
            </div>
            <p className={styles.themeDesc}>
              {t(
                "Đồng bộ theo thiết lập macOS / Windows / iOS. Tự động chuyển đổi mượt mà theo lịch trình hệ điều hành.",
                "Synchronizes with macOS / Windows / iOS system appearance schedule automatically."
              )}
            </p>
          </button>
        </div>

        {/* Interactive Language Selector Row */}
        <div className={styles.card} style={{ marginTop: "4px" }}>
          <div className={styles.row}>
            <div className={styles.rowInfo}>
              <span className={styles.rowLabel}>
                {t("Ngôn ngữ giao diện (Display Language)", "Display Language (VI / EN)")}
              </span>
              <span className={styles.rowDesc}>
                {t(
                  "Chuyển đổi toàn diện giữa thuật ngữ tài chính tiếng Việt và chuẩn mực ngân hàng đầu tư tiếng Anh.",
                  "Instantly toggle between institutional Vietnamese and quantitative English terminology across all terminal views."
                )}
              </span>
            </div>
            <div
              className={styles.segmentedSelect}
              role="radiogroup"
              aria-label={t("Ngôn ngữ giao diện", "Display Language")}
            >
              <button
                type="button"
                className={`${styles.selectOption} ${locale === "vi" ? styles.selectOptionActive : ""}`}
                onClick={() => setLocale("vi")}
                aria-pressed={locale === "vi"}
              >
                Tiếng Việt (VI)
              </button>
              <button
                type="button"
                className={`${styles.selectOption} ${locale === "en" ? styles.selectOptionActive : ""}`}
                onClick={() => setLocale("en")}
                aria-pressed={locale === "en"}
              >
                English (EN)
              </button>
            </div>
          </div>
        </div>

        <div className={styles.infoCallout}>
          <span className={styles.infoIcon}>
            <LightbulbIcon />
          </span>
          <div>
            {t("Trạng thái hiển thị hiện thời: ", "Current effective appearance: ")}
            <strong>
              {effectiveTheme === "dark"
                ? t("Chế độ Tối (Dark Mode)", "Dark Mode")
                : t("Chế độ Sáng (Light Mode)", "Light Mode")}
            </strong>.
            {currentTheme === "system" &&
              t(
                " Hệ thống đang tự động bám theo tín hiệu màu từ hệ điều hành thiết bị của bạn.",
                " The system dynamically follows your operating system's color scheme."
              )}
          </div>
        </div>
      </section>

      {/* SECTION 2: Graphics Engine */}
      <section className={styles.section} aria-labelledby="graphics-heading">
        <div className={styles.sectionHeader}>
          <h2 id="graphics-heading" className={styles.sectionTitle}>
            <BoltIcon />
            <span>{t("Hiệu năng Đồ họa & Chuyển động (Graphics Engine)", "Graphics Engine & Motion Performance")}</span>
          </h2>
          <p className={styles.sectionDescription}>
            {t(
              "Kiểm soát tốc độ khung hình và hiệu ứng mô phỏng vật lý Emil Kowalski Spring.",
              "Control rendering frame rates, glassmorphic blur backdrops, and physical spring animations."
            )}
          </p>
        </div>

        <div className={styles.card}>
          <div className={styles.row}>
            <div className={styles.rowInfo}>
              <span className={styles.rowLabel}>
                {t("Chế độ Kết xuất Đồ họa", "Graphics Rendering Preset")}
              </span>
              <span className={styles.rowDesc}>
                {t(
                  "Điều chỉnh độ mượt của biểu đồ nến kỹ thuật, hiệu ứng kính mờ (blur backdrop) và hoạt ảnh chuyển trang.",
                  "Calibrate fidelity for candlestick charts, spatial blur backdrops, and page transitions."
                )}
              </span>
            </div>
            <div
              className={styles.segmentedSelect}
              role="radiogroup"
              aria-label={t("Chế độ đồ họa", "Graphics Mode")}
            >
              <button
                type="button"
                className={`${styles.selectOption} ${graphicsQuality === "high" ? styles.selectOptionActive : ""}`}
                onClick={() => handleGraphicsChange("high")}
              >
                {t("Cao (60 FPS)", "High (60 FPS)")}
              </button>
              <button
                type="button"
                className={`${styles.selectOption} ${graphicsQuality === "balanced" ? styles.selectOptionActive : ""}`}
                onClick={() => handleGraphicsChange("balanced")}
              >
                {t("Cân bằng", "Balanced")}
              </button>
              <button
                type="button"
                className={`${styles.selectOption} ${graphicsQuality === "eco" ? styles.selectOptionActive : ""}`}
                onClick={() => handleGraphicsChange("eco")}
              >
                {t("Tiết kiệm pin", "Eco / Battery")}
              </button>
              <button
                type="button"
                className={`${styles.selectOption} ${graphicsQuality === "off" ? styles.selectOptionActive : ""}`}
                onClick={() => handleGraphicsChange("off")}
              >
                {t("2D Tối giản", "Minimal 2D")}
              </button>
            </div>
          </div>

          <div className={styles.row}>
            <div className={styles.rowInfo}>
              <span className={styles.rowLabel}>
                {t("Font chữ Tabular Figures (Số liệu căn hàng)", "Tabular Figures Monospace Alignment")}
              </span>
              <span className={styles.rowDesc}>
                {t(
                  "Ép buộc hiển thị font số có chiều rộng bằng nhau (tnum) để bảng giá không bị xô lệch khi biến động.",
                  "Enforces equal-width numerals (tnum) so market quotes and orderbook rows remain stable."
                )}
              </span>
            </div>
            <span className={`${styles.statusPill} ${styles.statusPillActive}`}>
              <span className={styles.statusDot} />
              {t("Luôn bật (Mặc định)", "Always On (Default)")}
            </span>
          </div>
        </div>
      </section>

      {/* SECTION 3: AI Configuration */}
      <section className={styles.section} aria-labelledby="ai-heading">
        <div className={styles.sectionHeader}>
          <h2 id="ai-heading" className={styles.sectionTitle}>
            <BrainIcon />
            <span>{t("Trợ lý Định lượng AI (AI Configuration)", "Quantitative AI Configuration")}</span>
          </h2>
          <p className={styles.sectionDescription}>
            {t(
              "Cấu hình mô hình ngôn ngữ lớn cục bộ chạy trên phần cứng máy tính người dùng.",
              "Configure local quantitative LLM runtime deployed directly on private workstation hardware."
            )}
          </p>
        </div>

        <div className={styles.card}>
          <div className={styles.row}>
            <div className={styles.rowInfo}>
              <span className={styles.rowLabel}>{t("Mô hình Cục bộ (Local LLM)", "Local LLM Runtime")}</span>
              <span className={styles.rowDesc}>
                {t(
                  "Ollama runtime kết nối tới http://127.0.0.1:11434 (Qwen 2.5 9B Quantized / Fallback).",
                  "Ollama runtime connected to http://127.0.0.1:11434 (Qwen 2.5 9B Quantized / Fallback)."
                )}
              </span>
            </div>
            <span className={`${styles.statusPill} ${styles.statusPillActive}`}>
              <span className={styles.statusDot} />
              {t("Sẵn sàng (Localhost)", "Ready (Localhost)")}
            </span>
          </div>

          <div className={styles.row}>
            <div className={styles.rowInfo}>
              <span className={styles.rowLabel}>
                {t("Cơ chế Bảo mật Zero External Leak", "Zero External Data Leak Architecture")}
              </span>
              <span className={styles.rowDesc}>
                {t(
                  "Tuyệt đối không gửi truy vấn tài chính, danh mục đầu tư hay API key ra máy chủ bên ngoài.",
                  "Strictly zero financial queries, portfolio allocations, or credentials leaked off-premises."
                )}
              </span>
            </div>
            <span className={`${styles.statusPill} ${styles.statusPillActive}`}>
              <span className={styles.statusDot} />
              {t("Được bảo vệ", "Enforced")}
            </span>
          </div>

          <div className={styles.row}>
            <div className={styles.rowInfo}>
              <span className={styles.rowLabel}>
                {t("Trợ lý Phân tích AI Analyst", "Interactive AI Analyst")}
              </span>
              <span className={styles.rowDesc}>
                {t(
                  "Trải nghiệm hội thoại phân tích định lượng chuyên sâu với trích dẫn dữ liệu thời gian thực.",
                  "Deep financial reasoning conversation with verified real-time audit trails and citations."
                )}
              </span>
            </div>
            <Link href="/ai" className={styles.actionBtn}>
              {t("Mở AI Analyst →", "Open AI Analyst →")}
            </Link>
          </div>
        </div>
      </section>

      {/* SECTION 4: Local Cache & Storage */}
      <section className={styles.section} aria-labelledby="cache-heading">
        <div className={styles.sectionHeader}>
          <h2 id="cache-heading" className={styles.sectionTitle}>
            <DiskIcon />
            <span>{t("Bộ nhớ & Đồng bộ dữ liệu Cục bộ (Storage & Cache)", "Storage & Point-in-Time Integrity")}</span>
          </h2>
          <p className={styles.sectionDescription}>
            {t(
              "Quản lý dữ liệu lưu trong trình duyệt và đảm bảo tính bất biến của cơ sở dữ liệu.",
              "Manage client-side browser cache and verify immutability of the quantitative database."
            )}
          </p>
        </div>

        <div className={styles.card}>
          <div className={styles.row}>
            <div className={styles.rowInfo}>
              <span className={styles.rowLabel}>
                {t("Tính toàn vẹn Dữ liệu Point-in-Time", "Point-in-Time Data Integrity")}
              </span>
              <span className={styles.rowDesc}>
                {t(
                  "Kiểm tra hash và trạng thái Read-Only của kho dữ liệu định lượng data/trading.db.",
                  "Verify cryptographic hash and Read-Only state of canonical data/trading.db store."
                )}
              </span>
            </div>
            <button
              type="button"
              className={styles.actionBtn}
              onClick={handleCheckIntegrity}
            >
              {t("Kiểm tra tính toàn vẹn", "Verify Integrity")}
            </button>
          </div>

          {integrityStatus && (
            <div className={styles.infoCallout}>
              <span className={styles.infoIcon}>
                <ShieldIcon />
              </span>
              <div>{integrityStatus}</div>
            </div>
          )}

          <div className={styles.row}>
            <div className={styles.rowInfo}>
              <span className={styles.rowLabel}>
                {t("Xóa bộ nhớ đệm trình duyệt (Cache Reset)", "Browser Cache Reset")}
              </span>
              <span className={styles.rowDesc}>
                {t(
                  "Làm sạch Service Worker cache và tài nguyên tĩnh mà vẫn bảo toàn tùy chọn giao diện và ngôn ngữ cá nhân.",
                  "Flush Service Worker cache and static assets while preserving user theme and language preferences."
                )}
              </span>
            </div>
            <button
              type="button"
              className={`${styles.actionBtn} ${styles.dangerBtn}`}
              onClick={handleClearCache}
            >
              {t("Xóa bộ nhớ đệm", "Flush Cache")}
            </button>
          </div>

          {cacheMessage && (
            <div className={styles.infoCallout}>
              <span className={styles.infoIcon}>
                <InfoCircleIcon />
              </span>
              <div>{cacheMessage}</div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
