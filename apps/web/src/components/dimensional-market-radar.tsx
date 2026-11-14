"use client";

import React from "react";
import type { MarketDashboard } from "@/lib/api";
import { useLocale, translateQuantEnum, type AppLocale } from "@/lib/i18n";
import styles from "./dimensional-market-radar.module.css";

interface DimensionalMarketRadarProps {
  indexes: MarketDashboard["indexes"];
  regime: MarketDashboard["market_regime"];
  breadth: MarketDashboard["breadth"];
}

function formatNumber(val: number | null, digits = 2, locale: AppLocale = "vi") {
  if (val === null || !Number.isFinite(val)) return "—";
  const numLocale = locale === "en" ? "en-US" : "vi-VN";
  return new Intl.NumberFormat(numLocale, { maximumFractionDigits: digits }).format(val);
}

export default function DimensionalMarketRadar({
  indexes,
  regime,
  breadth,
}: DimensionalMarketRadarProps) {
  const { locale, t } = useLocale();

  const advancing = Number(breadth?.details?.advancing ?? 0);
  const declining = Number(breadth?.details?.declining ?? 0);
  const total = Math.max(advancing + declining, 1);
  const advancingPct = Math.round((advancing / total) * 100);
  const decliningPct = 100 - advancingPct;

  return (
    <section className={styles.summaryStrip} aria-label={t("Tóm tắt trạng thái thị trường", "Market status summary")}>
      {/* Index Metrics Cluster */}
      <div className={styles.indexCluster}>
        {indexes.map((idx, i) => (
          <div key={idx.symbol} className={`${styles.indexItem} ${i === 0 ? styles.primaryIndexItem : ""}`}>
            <div className={styles.indexMeta}>
              <span className={styles.indexSymbol}>{idx.symbol}</span>
              <span className={`${styles.indexStatus} tabular-nums`}>
                {idx.metric?.status === "AVAILABLE" ? t("Khả dụng", "Available") : idx.metric?.status ?? "—"}
              </span>
            </div>
            <div className={styles.indexPriceRow}>
              <strong className={`${styles.indexValue} tabular-nums`}>
                {formatNumber(idx.metric?.value, 2, locale)}
              </strong>
              <span className={styles.indexUnit}>PTS</span>
            </div>
          </div>
        ))}
      </div>

      <div className={styles.divider} aria-hidden="true" />

      {/* Market Breadth Minimalist Visualizer */}
      <div className={styles.breadthCluster}>
        <div className={styles.breadthMetaRow}>
          <span className={styles.breadthLabel}>{t("Độ rộng thị trường", "Market Breadth")}</span>
          <div className={styles.breadthStats}>
            <span className={`${styles.advancingCount} tabular-nums`}>
              {t(`↑ ${advancing} mã tăng (${advancingPct}%)`, `↑ ${advancing} Advancing (${advancingPct}%)`)}
            </span>
            <span className={styles.statDot} aria-hidden="true">·</span>
            <span className={`${styles.decliningCount} tabular-nums`}>
              {t(`↓ ${declining} mã giảm (${decliningPct}%)`, `↓ ${declining} Declining (${decliningPct}%)`)}
            </span>
          </div>
        </div>
        <div
          className={styles.breadthTrack}
          aria-label={t(
            `Tỉ lệ: ${advancingPct}% tăng, ${decliningPct}% giảm`,
            `Ratio: ${advancingPct}% advancing, ${decliningPct}% declining`
          )}
        >
          <div className={styles.advancingFill} style={{ width: `${advancingPct}%` }} />
          <div className={styles.decliningFill} style={{ width: `${decliningPct}%` }} />
        </div>
      </div>

      <div className={styles.divider} aria-hidden="true" />

      {/* Market Regime Badge */}
      <div className={styles.regimeCluster}>
        <span className={styles.regimeLabel}>{t("Chế độ thị trường", "Market Regime")}</span>
        <div className={styles.regimePill}>
          <span className={styles.regimeDot} aria-hidden="true" />
          <strong className={styles.regimeName}>
            {translateQuantEnum(regime?.regime, locale)}
          </strong>
          <span className={`${styles.regimeConfidence} tabular-nums`}>
            {regime ? `${Math.round(regime.confidence * 100)}%` : ""}
          </span>
        </div>
      </div>
    </section>
  );
}
