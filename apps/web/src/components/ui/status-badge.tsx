"use client";

import React, { type JSX } from "react";
import { useLocale, type AppLocale } from "@/lib/i18n";
import styles from "./status-badge.module.css";

export type DataStatusTone = "ok" | "warn" | "muted" | "error" | "info";

export function describeStatus(
  code: string | null | undefined,
  locale: AppLocale = "vi"
): {
  label: string;
  tone: DataStatusTone;
  tooltip: string;
} {
  const isEn = locale === "en";
  if (!code || !code.trim()) {
    return { label: isEn ? "Unknown" : "Không rõ", tone: "muted", tooltip: "" };
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
        label: isEn ? "Operational" : "Sẵn sàng",
        tone: "ok",
        tooltip: isEn
          ? "Dataset verified and synchronized to latest Point-in-Time cutoff."
          : "Dữ liệu đã được kiểm chứng và cập nhật.",
      };
    case "STALE":
      return {
        label: isEn ? "Stale Feed" : "Dữ liệu trễ",
        tone: "warn",
        tooltip: isEn
          ? "Not updated in the latest session; figures remain accurate as of displayed cutoff."
          : "Dữ liệu chưa được cập nhật trong kỳ gần nhất; con số vẫn đúng tại mốc thời gian hiển thị.",
      };
    case "INSUFFICIENT_DATA":
      return {
        label: isEn ? "Insufficient Filings" : "Chưa đủ dữ liệu BCTC",
        tone: "muted",
        tooltip: isEn
          ? "Not enough historical reporting periods to compute this metric reliably."
          : "Chưa có đủ kỳ báo cáo tài chính để tính chỉ số này.",
      };
    case "NOT_CONFIGURED":
    case "NOT_IMPLEMENTED":
      return {
        label: isEn ? "Unconfigured" : "Chưa kết nối",
        tone: "muted",
        tooltip: isEn
          ? "This data feed is not currently configured."
          : "Nguồn dữ liệu này chưa được cấu hình.",
      };
    case "PARTIAL":
    case "PARTIAL_DATA_ONLY":
    case "DEGRADED":
      return {
        label: isEn ? "Partial Coverage" : "Dữ liệu một phần",
        tone: "warn",
        tooltip: isEn
          ? "Only partial dataset coverage is currently available."
          : "Chỉ một phần dữ liệu khả dụng.",
      };
    case "BLOCKED":
    case "ERROR":
    case "FAILED":
    case "UNAVAILABLE":
      return {
        label: isEn ? "Unavailable" : "Không khả dụng",
        tone: "error",
        tooltip: isEn
          ? "Unable to retrieve telemetry from this data source."
          : "Không thể lấy dữ liệu từ nguồn này.",
      };
    case "LOADING":
    case "CHECKING":
    case "RUNNING":
      return {
        label: isEn ? "Syncing" : "Đang đồng bộ",
        tone: "info",
        tooltip: isEn ? "Fetching latest telemetry." : "Đang lấy dữ liệu mới nhất.",
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
  const { locale } = useLocale();
  const meta = describeStatus(status, locale);
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
