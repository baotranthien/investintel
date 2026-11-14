"use client";

import React, { useEffect, useState } from "react";
import type { AIStreamStep } from "@/lib/api";
import { useLocale } from "@/lib/i18n";
import styles from "./apple-dynamic-island.module.css";

interface DynamicIslandProps {
  isStreaming: boolean;
  step: AIStreamStep | null;
  message: string;
  heartbeatCount: number;
  onCancel?: () => void;
}

export default function AppleDynamicIsland({
  isStreaming,
  step,
  message,
  heartbeatCount,
  onCancel,
}: DynamicIslandProps) {
  const { t } = useLocale();
  const [prevMessage, setPrevMessage] = useState(message);
  const [isTransitioning, setIsTransitioning] = useState(false);

  useEffect(() => {
    if (message !== prevMessage) {
      const startTimer = setTimeout(() => {
        setIsTransitioning(true);
      }, 0);
      const endTimer = setTimeout(() => {
        setPrevMessage(message);
        setIsTransitioning(false);
      }, 120);
      return () => {
        clearTimeout(startTimer);
        clearTimeout(endTimer);
      };
    }
  }, [message, prevMessage]);

  if (!isStreaming) return null;

  const stepMetaMap: Record<AIStreamStep, { label: string; phase: string; phaseNum: string }> = {
    fetching_data: {
      label: t("Trích xuất BCTC & Chuỗi giá định lượng", "Extracting Financial Statements & Price Series"),
      phase: "EXTRACTING",
      phaseNum: "01/03",
    },
    llm_reasoning: {
      label: t("Phân tích suy luận tài chính & định giá", "Financial Reasoning & Valuation Synthesis"),
      phase: "REASONING",
      phaseNum: "02/03",
    },
    validating: {
      label: t("Kiểm chứng đối chiếu chống Hallucination", "Audit Reconciling & Anti-Hallucination Check"),
      phase: "VALIDATING",
      phaseNum: "03/03",
    },
  };

  const currentMeta = step
    ? stepMetaMap[step]
    : {
        label: t("Đang khởi tạo kết nối SSE...", "Initializing SSE streaming connection..."),
        phase: "INITIALIZING",
        phaseNum: "00/03",
      };

  return (
    <aside className={styles.statusPill} role="status" aria-live="polite">
      {/* Pulsing Minimalist Dot */}
      <span className={styles.pulseDot} aria-hidden="true" />

      {/* Phase Label */}
      <span className={`${styles.phaseTag} tabular-nums`}>
        {currentMeta.phaseNum} · {currentMeta.phase}
      </span>

      <span className={styles.divider} aria-hidden="true">/</span>

      {/* Cross-fading Status Message */}
      <div className={`${styles.messageWrap} ${isTransitioning ? styles.messageMorphing : ""}`}>
        <strong className={styles.stepTitle}>{currentMeta.label}</strong>
        {message ? (
          <span className={styles.messageDetail}>— {message}</span>
        ) : null}
      </div>

      {/* Telemetry Right: Heartbeat Counter + Cancel */}
      <div className={styles.telemetryRight}>
        <span
          className={`${styles.heartbeatTime} tabular-nums`}
          title={t("Độ trễ nhịp tim kết nối SSE", "SSE Heartbeat latency")}
        >
          {heartbeatCount > 0 ? `${heartbeatCount * 3}s` : "0s"}
        </span>

        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className={styles.cancelBtn}
            title={t("Dừng luồng phản hồi", "Stop streaming response")}
            aria-label={t("Hủy tạo", "Cancel stream")}
          >
            ✕
          </button>
        )}
      </div>
    </aside>
  );
}
