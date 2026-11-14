"use client";

import { useLocale } from "@/lib/i18n";
import styles from "./language-toggle.module.css";

interface LanguageToggleProps {
  variant?: "header" | "drawer" | "gateway";
}

export default function LanguageToggle({ variant = "header" }: LanguageToggleProps) {
  const { locale, toggleLocale, mounted, t } = useLocale();

  const currentLocale = mounted ? locale : "vi";
  const isVi = currentLocale === "vi";

  const ariaLabel = t(
    "Chuyển ngôn ngữ giao diện (EN / VI)",
    "Switch interface language (EN / VI)"
  );
  const titleText = t(
    isVi ? "Đang hiển thị Tiếng Việt — nhấn để chuyển sang English" : "Switch to Tiếng Việt",
    isVi ? "Switch to English" : "Currently English — click to switch to Tiếng Việt"
  );

  const switchButton = (
    <button
      type="button"
      role="switch"
      aria-checked={isVi}
      aria-label={ariaLabel}
      title={titleText}
      data-testid={variant === "gateway" ? "gateway-language-toggle" : "language-toggle"}
      className={[
        styles.langSwitch,
        isVi ? styles.langSwitchVi : "",
        variant === "gateway" ? styles.gatewayLangSwitch : "",
      ]
        .filter(Boolean)
        .join(" ")}
      onClick={toggleLocale}
    >
      <span className={styles.langThumb} aria-hidden="true" />
      <span className={`${styles.langCode} ${!isVi ? styles.langCodeActive : ""}`}>EN</span>
      <span className={`${styles.langCode} ${isVi ? styles.langCodeActive : ""}`}>VI</span>
    </button>
  );

  if (variant === "drawer") {
    return (
      <div className={styles.drawerRow}>
        <span className={styles.drawerLabel}>
          {t("Ngôn ngữ (EN / VI)", "Language (EN / VI)")}
        </span>
        {switchButton}
      </div>
    );
  }

  return switchButton;
}

