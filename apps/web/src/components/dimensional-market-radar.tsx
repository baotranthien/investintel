"use client";

import React from "react";
import type { MarketDashboard } from "@/lib/api";
import styles from "./dimensional-market-radar.module.css";

interface DimensionalMarketRadarProps {
  indexes: MarketDashboard["indexes"];
  regime: MarketDashboard["market_regime"];
  breadth: MarketDashboard["breadth"];
}

function formatNumber(val: number | null, digits = 2) {
  if (val === null || !Number.isFinite(val)) return "—";
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: digits }).format(val);
}

export default function DimensionalMarketRadar({
  indexes,
  regime,
  breadth,
}: DimensionalMarketRadarProps) {
  const advancing = Number(breadth?.details?.advancing ?? 0);
  const declining = Number(breadth?.details?.declining ?? 0);
  const total = Math.max(advancing + declining, 1);
  const advancingPct = Math.round((advancing / total) * 100);
  const decliningPct = 100 - advancingPct;

  return (
    <section className={styles.summaryStrip} aria-label="Tóm tắt trạng thái thị trường">
      {/* Index Metrics Cluster */}
      <div className={styles.indexCluster}>
        {indexes.map((idx, i) => (
          <div key={idx.symbol} className={`${styles.indexItem} ${i === 0 ? styles.primaryIndexItem : ""}`}>
            <div className={styles.indexMeta}>
              <span className={styles.indexSymbol}>{idx.symbol}</span>
              <span className={`${styles.indexStatus} tabular-nums`}>
                {idx.metric?.status === "AVAILABLE" ? "Khả dụng" : idx.metric?.status ?? "—"}
              </span>
            </div>
            <div className={styles.indexPriceRow}>
              <strong className={`${styles.indexValue} tabular-nums`}>
                {formatNumber(idx.metric?.value)}
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
          <span className={styles.breadthLabel}>Độ rộng thị trường</span>
          <div className={styles.breadthStats}>
            <span className={`${styles.advancingCount} tabular-nums`}>↑ {advancing} mã tăng ({advancingPct}%)</span>
            <span className={styles.statDot} aria-hidden="true">·</span>
            <span className={`${styles.decliningCount} tabular-nums`}>↓ {declining} mã giảm ({decliningPct}%)</span>
          </div>
        </div>
        <div className={styles.breadthTrack} aria-label={`Tỉ lệ: ${advancingPct}% tăng, ${decliningPct}% giảm`}>
          <div className={styles.advancingFill} style={{ width: `${advancingPct}%` }} />
          <div className={styles.decliningFill} style={{ width: `${decliningPct}%` }} />
        </div>
      </div>

      <div className={styles.divider} aria-hidden="true" />

      {/* Market Regime Badge */}
      <div className={styles.regimeCluster}>
        <span className={styles.regimeLabel}>Chế độ thị trường</span>
        <div className={styles.regimePill}>
          <span className={styles.regimeDot} aria-hidden="true" />
          <strong className={styles.regimeName}>{regime?.regime ?? "UNKNOWN"}</strong>
          <span className={`${styles.regimeConfidence} tabular-nums`}>
            {regime ? `${Math.round(regime.confidence * 100)}%` : ""}
          </span>
        </div>
      </div>
    </section>
  );
}
