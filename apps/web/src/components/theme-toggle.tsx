"use client";

import Link from "next/link";
import { useTheme } from "@/lib/theme";
import { useLocale } from "@/lib/i18n";
import styles from "./theme-toggle.module.css";

interface ThemeToggleProps {
  variant?: "header" | "drawer" | "gateway";
  showSettingsLink?: boolean;
}

function SunVectorIcon() {
  return (
    <svg
      width="13.5"
      height="13.5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.85"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2" />
      <path d="M12 19.5v2" />
      <path d="M5.28 5.28l1.42 1.42" />
      <path d="M17.3 17.3l1.42 1.42" />
      <path d="M2.5 12h2" />
      <path d="M19.5 12h2" />
      <path d="M5.28 18.72l1.42-1.42" />
      <path d="M17.3 6.7l1.42-1.42" />
    </svg>
  );
}

function MoonVectorIcon() {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.85"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M20.2 14.4A8.5 8.5 0 0 1 9.6 3.8a8.5 8.5 0 1 0 10.6 10.6Z" />
    </svg>
  );
}

function SlidersVectorIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <line x1="4" y1="7" x2="20" y2="7" />
      <line x1="4" y1="17" x2="20" y2="17" />
      <circle cx="9" cy="7" r="2.2" fill="var(--surface, #16181c)" />
      <circle cx="15" cy="17" r="2.2" fill="var(--surface, #16181c)" />
    </svg>
  );
}

export default function ThemeToggle({
  variant = "header",
  showSettingsLink = true,
}: ThemeToggleProps) {
  const { effectiveTheme, setTheme, mounted } = useTheme();
  const { t } = useLocale();

  const isDark = mounted ? effectiveTheme === "dark" : true;

  const handleToggle = () => {
    setTheme(isDark ? "light" : "dark");
  };

  const switchLabel = t(
    isDark ? "Chuyển sang giao diện Sáng" : "Chuyển sang giao diện Tối",
    isDark ? "Switch to Light Mode" : "Switch to Dark Mode"
  );

  const leverControl = (
    <button
      type="button"
      role="switch"
      aria-checked={isDark}
      aria-label={switchLabel}
      title={switchLabel}
      className={`${styles.leverSwitch} ${isDark ? styles.leverSwitchDark : ""}`}
      onClick={handleToggle}
    >
      <span className={styles.leverThumb} aria-hidden="true" />
      <span className={`${styles.iconSlot} ${!isDark ? styles.iconSlotActive : ""}`}>
        <SunVectorIcon />
      </span>
      <span className={`${styles.iconSlot} ${isDark ? styles.iconSlotActive : ""}`}>
        <MoonVectorIcon />
      </span>
    </button>
  );

  if (variant === "gateway") {
    return (
      <div className={styles.gatewayThemeWrap}>
        <button
          type="button"
          className={styles.gatewayToggleButton}
          onClick={handleToggle}
          aria-label={switchLabel}
          title={switchLabel}
          aria-pressed={!isDark}
        >
          {isDark ? <MoonVectorIcon /> : <SunVectorIcon />}
        </button>
      </div>
    );
  }

  if (variant === "drawer") {
    return (
      <div className={styles.drawerRow}>
        <span className={styles.drawerModeLabel}>
          {isDark ? t("Chế độ Tối", "Dark Mode") : t("Chế độ Sáng", "Light Mode")}
        </span>
        {leverControl}
      </div>
    );
  }

  return (
    <div className={styles.toggleWrapper}>
      {leverControl}
      {showSettingsLink && (
        <Link
          href="/settings"
          className={styles.settingsLink}
          title={t("Tùy chọn & Cài đặt hệ thống", "Workspace Preferences & Settings")}
          aria-label={t("Cài đặt hệ thống", "System Settings")}
        >
          <SlidersVectorIcon />
        </Link>
      )}
    </div>
  );
}
