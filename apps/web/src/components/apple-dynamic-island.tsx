"use client";

import React, { useEffect, useState } from "react";
import type { AIStreamStep } from "@/lib/api";
import styles from "./apple-dynamic-island.module.css";

interface DynamicIslandProps {
  isStreaming: boolean;
  step: AIStreamStep | null;
  message: string;
  heartbeatCount: number;
  onCancel?: () => void;
}

const STEP_METADATA: Record<AIStreamStep, { label: string; phase: string; phaseNum: string }> = {
  fetching_data: {
    label: "Trích xuất BCTC & Chuỗi giá định lượng",
    phase: "EXTRACTING",
    phaseNum: "01/03",
  },
  llm_reasoning: {
    label: "Phân tích suy luận tài chính & định giá",
    phase: "REASONING",
    phaseNum: "02/03",
  },
  validating: {
    label: "Kiểm chứng đối chiếu chống Hallucination",
    phase: "VALIDATING",
    phaseNum: "03/03",
  },
};

export default function AppleDynamicIsland({
  isStreaming,
  step,
  message,
  heartbeatCount,
  onCancel,
}: DynamicIslandProps) {
  const [prevMessage, setPrevMessage] = useState(message);
  const [isTransitioning, setIsTransitioning] = useState(false);

  useEffect(() => {
    if (message !== prevMessage) {
      setIsTransitioning(true);
      const timer = setTimeout(() => {
        setPrevMessage(message);
        setIsTransitioning(false);
      }, 120);
      return () => clearTimeout(timer);
    }
  }, [message, prevMessage]);

  if (!isStreaming) return null;

  const currentMeta = step
    ? STEP_METADATA[step]
    : { label: "Đang khởi tạo kết nối SSE...", phase: "INITIALIZING", phaseNum: "00/03" };

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
        <span className={`${styles.heartbeatTime} tabular-nums`} title="SSE Heartbeat latency">
          {heartbeatCount > 0 ? `${heartbeatCount * 3}s` : "0s"}
        </span>

        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className={styles.cancelBtn}
            title="Dừng luồng phản hồi"
            aria-label="Hủy tạo"
          >
            ✕
          </button>
        )}
      </div>
    </aside>
  );
}
