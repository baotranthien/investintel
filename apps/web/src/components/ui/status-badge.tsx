import React, { type JSX } from "react";
import styles from "./status-badge.module.css";

export type DataStatusTone = "ok" | "warn" | "muted" | "error" | "info";

export function describeStatus(code: string | null | undefined): {
  label: string;
  tone: DataStatusTone;
  tooltip: string;
} {
  if (!code || !code.trim()) {
    return { label: "Không rõ", tone: "muted", tooltip: "" };
  }

  const normalized = code.trim().toUpperCase();

  switch (normalized) {
    case "AVAILABLE":
    case "SUCCESS":
    case "OK":
    case "FRESH":
    case "RECENT":
    case "HEALTHY":
    case "API RESPONDED":
      return {
        label: "Sẵn sàng",
        tone: "ok",
        tooltip: "Dữ liệu đã được kiểm chứng và cập nhật.",
      };
    case "STALE":
      return {
        label: "Dữ liệu trễ",
        tone: "warn",
        tooltip: "Dữ liệu chưa được cập nhật trong kỳ gần nhất; con số vẫn đúng tại mốc thời gian hiển thị.",
      };
    case "INSUFFICIENT_DATA":
      return {
        label: "Chưa đủ dữ liệu BCTC",
        tone: "muted",
        tooltip: "Chưa có đủ kỳ báo cáo tài chính để tính chỉ số này.",
      };
    case "NOT_CONFIGURED":
    case "NOT_IMPLEMENTED":
      return {
        label: "Chưa kết nối",
        tone: "muted",
        tooltip: "Nguồn dữ liệu này chưa được cấu hình.",
      };
    case "PARTIAL":
    case "PARTIAL_DATA_ONLY":
    case "DEGRADED":
      return {
        label: "Dữ liệu một phần",
        tone: "warn",
        tooltip: "Chỉ một phần dữ liệu khả dụng.",
      };
    case "BLOCKED":
    case "ERROR":
    case "FAILED":
    case "UNAVAILABLE":
      return {
        label: "Không khả dụng",
        tone: "error",
        tooltip: "Không thể lấy dữ liệu từ nguồn này.",
      };
    case "LOADING":
    case "CHECKING":
    case "RUNNING":
      return {
        label: "Đang đồng bộ",
        tone: "info",
        tooltip: "Đang lấy dữ liệu mới nhất.",
      };
    default: {
      const raw = code.trim().replace(/_/g, " ").toLowerCase();
      const humanized = raw ? raw.charAt(0).toUpperCase() + raw.slice(1) : "";
      return {
        label: humanized,
        tone: "muted",
        tooltip: "",
      };
    }
  }
}

export function StatusBadge({
  status,
  label,
  title,
  className,
}: {
  status: string | null | undefined;
  label?: string;
  title?: string;
  className?: string;
}): JSX.Element {
  const meta = describeStatus(status);
  const displayLabel = label ?? meta.label;
  const displayTooltip = title ?? meta.tooltip;

  return (
    <span
      title={displayTooltip || undefined}
      className={`${styles.badge} ${styles[meta.tone]}${className ? ` ${className}` : ""}`}
    >
      <span className={styles.dot} aria-hidden="true" />
      <span>{displayLabel}</span>
    </span>
  );
}
