"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  performanceController,
  type PerformanceMetrics,
  type QualityTier,
} from "./performance-controller";
import styles from "./three-quality-selector.module.css";

const OPTIONS: { tier: QualityTier; label: string; desc: string }[] = [
  {
    tier: "BALANCED",
    label: "Cân bằng (30 FPS)",
    desc: "Khuyến nghị RTX 3050 & chạy song song Ollama",
  },
  {
    tier: "HIGH",
    label: "Tối đa (60 FPS)",
    desc: "DPR 1.25, độ mượt cao nhất",
  },
  {
    tier: "LOW",
    label: "Tiết kiệm (15 FPS)",
    desc: "Giảm tải GPU tối đa",
  },
  {
    tier: "OFF",
    label: "Tắt 3D / Tĩnh",
    desc: "Chế độ tĩnh & giảm chuyển động",
  },
];

const DEFAULT_METRICS: PerformanceMetrics = {
  fps: 30,
  qualityTier: "BALANCED",
  effectiveTier: "BALANCED",
  isAiThrottled: false,
  isVisible: true,
  dpr: 1.0,
  frameBudgetMs: 1000 / 30,
};

export default function ThreeQualitySelector() {
  const [metrics, setMetrics] = useState<PerformanceMetrics>(DEFAULT_METRICS);
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Sync with client-side metrics after hydration
    setMetrics(performanceController.getMetrics());

    return performanceController.subscribe((m) => {
      setMetrics(m);
    });
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const currentLabel =
    metrics.effectiveTier === "OFF"
      ? "3D TĨNH"
      : metrics.isAiThrottled
      ? "3D 15FPS (AI)"
      : `3D ${metrics.effectiveTier}`;

  return (
    <div className={styles.wrapper} ref={dropdownRef}>
      <button
        type="button"
        className={styles.triggerButton}
        onClick={() => setIsOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        title="Tùy chỉnh đồ họa 3D Three.js & tốc độ khung hình"
        suppressHydrationWarning
      >
        <span
          className={styles.tierIndicator}
          data-tier={metrics.effectiveTier}
          data-ai={metrics.isAiThrottled}
          suppressHydrationWarning
        />
        <span className={styles.label} suppressHydrationWarning>{currentLabel}</span>
      </button>

      {isOpen && (
        <div className={styles.menu} role="listbox">
          <div className={styles.menuHeader}>
            <span className={styles.menuTitle}>ĐỒ HỌA 3D TERMINAL</span>
            <span className={styles.fpsDisplay}>{metrics.fps} FPS</span>
          </div>

          {OPTIONS.map((opt) => {
            const isSelected = metrics.qualityTier === opt.tier;
            return (
              <button
                key={opt.tier}
                type="button"
                role="option"
                aria-selected={isSelected}
                className={`${styles.menuOption} ${isSelected ? styles.selected : ""}`}
                onClick={() => {
                  performanceController.setQuality(opt.tier);
                  setIsOpen(false);
                }}
              >
                <div className={styles.optionMain}>
                  <strong className={styles.optionLabel}>{opt.label}</strong>
                  <span className={styles.optionDesc}>{opt.desc}</span>
                </div>
                {isSelected && <span className={styles.checkMark}>✓</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

