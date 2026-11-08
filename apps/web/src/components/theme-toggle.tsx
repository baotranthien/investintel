"use client";

import Link from "next/link";
import { useTheme, type ThemePreference } from "@/lib/theme";
import styles from "./theme-toggle.module.css";

interface ThemeToggleProps {
  variant?: "header" | "drawer";
  showSettingsLink?: boolean;
}

export default function ThemeToggle({
  variant = "header",
  showSettingsLink = true,
}: ThemeToggleProps) {
  const { theme, setTheme, mounted } = useTheme();

  // Until mounted, default to system / prevent hydration mismatch
  const current = mounted ? theme : "system";

  const handleSelect = (pref: ThemePreference) => {
    setTheme(pref);
  };

  if (variant === "drawer") {
    return (
      <div className={styles.compactWrapper}>
        <div className={styles.compactControl} role="radiogroup" aria-label="Lựa chọn giao diện">
          <button
            type="button"
            role="radio"
            aria-checked={current === "light"}
            className={`${styles.compactBtn} ${current === "light" ? styles.compactBtnActive : ""}`}
            onClick={() => handleSelect("light")}
          >
            <span>☀️</span>
            <span>Sáng</span>
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={current === "dark"}
            className={`${styles.compactBtn} ${current === "dark" ? styles.compactBtnActive : ""}`}
            onClick={() => handleSelect("dark")}
          >
            <span>🌙</span>
            <span>Tối</span>
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={current === "system"}
            className={`${styles.compactBtn} ${current === "system" ? styles.compactBtnActive : ""}`}
            onClick={() => handleSelect("system")}
          >
            <span>🖥️</span>
            <span>Tự động</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.toggleWrapper}>
      <div
        className={styles.segmentedControl}
        role="radiogroup"
        aria-label="Tùy chọn giao diện (Sáng, Tối, Tự động)"
      >
        <button
          type="button"
          role="radio"
          aria-checked={current === "light"}
          aria-label="Chế độ Sáng"
          title="Chế độ Sáng (Light Mode)"
          className={`${styles.segmentButton} ${current === "light" ? styles.segmentActive : ""}`}
          onClick={() => handleSelect("light")}
        >
          <span className={styles.segmentIcon} aria-hidden="true">☀️</span>
          <span className={styles.segmentLabel}>Sáng</span>
        </button>

        <button
          type="button"
          role="radio"
          aria-checked={current === "dark"}
          aria-label="Chế độ Tối"
          title="Chế độ Tối (Dark Mode)"
          className={`${styles.segmentButton} ${current === "dark" ? styles.segmentActive : ""}`}
          onClick={() => handleSelect("dark")}
        >
          <span className={styles.segmentIcon} aria-hidden="true">🌙</span>
          <span className={styles.segmentLabel}>Tối</span>
        </button>

        <button
          type="button"
          role="radio"
          aria-checked={current === "system"}
          aria-label="Tự động theo hệ thống"
          title="Tự động theo hệ điều hành (System OS)"
          className={`${styles.segmentButton} ${current === "system" ? styles.segmentActive : ""}`}
          onClick={() => handleSelect("system")}
        >
          <span className={styles.segmentIcon} aria-hidden="true">🖥️</span>
          <span className={styles.segmentLabel}>Tự động</span>
        </button>
      </div>

      {showSettingsLink && (
        <Link
          href="/settings"
          className={styles.settingsLink}
          title="Tùy chọn & Cài đặt hệ thống (Settings)"
          aria-label="Cài đặt hệ thống"
        >
          ⚙️
        </Link>
      )}
    </div>
  );
}

