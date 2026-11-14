"use client";

import React, { type JSX } from "react";
import { getDataProviders, type DataProvider } from "@/lib/api";
import { StatusBadge } from "@/components/ui/status-badge";
import { SkeletonCard } from "@/components/ui/skeleton";
import { useCachedResource } from "@/lib/use-cached-resource";
import { useLocale } from "@/lib/i18n";
import styles from "./page.module.css";

export default function DataCenter(): JSX.Element {
  const { locale, t } = useLocale();
  const numLocale = locale === "en" ? "en-US" : "vi-VN";

  const resource = useCachedResource<DataProvider[]>(
    "data-center:providers",
    (signal) => getDataProviders(signal),
    { maxAgeMs: 60_000 }
  );

  const providers = resource.data ?? [];
  const loading = resource.isLoading && !resource.data;
  const error = resource.error && !resource.data;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>
            {t("Hạ tầng dữ liệu · Nguồn gốc & kiểm chứng", "Data Infrastructure · Lineage & Verification")}
          </p>
          <h1 className={styles.title}>
            {t("Chất lượng dữ liệu & nguồn gốc", "Data Quality & Lineage")}
          </h1>
          <p className={styles.subTitle}>
            {t(
              "Giám sát độ tươi, tính liên tục và lịch sử cập nhật của các cổng dữ liệu định lượng.",
              "Audit data freshness, continuity, and ingestion history across quantitative feeds."
            )}
          </p>
        </div>
      </header>

      {loading ? (
        <div className={styles.grid}>
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} height={200} />
          ))}
        </div>
      ) : error ? (
        <div className={styles.grid}>
          <div className={styles.errorBox}>
            <StatusBadge status="ERROR" label={t("Không thể tải cổng dữ liệu", "Unable to load data providers")} />
            <p className={styles.errorText}>
              {t("Đã xảy ra lỗi khi kết nối máy chủ: ", "Server connection error: ")}
              {resource.error}
            </p>
            <button
              type="button"
              className={styles.retryBtn}
              onClick={() => resource.reload()}
            >
              {t("↻ Tải lại danh sách", "↻ Reload Provider List")}
            </button>
          </div>
        </div>
      ) : providers.length === 0 ? (
        <div className={styles.grid}>
          <div className={styles.errorBox}>
            <StatusBadge status="WARNING" label={t("Chưa có dữ liệu", "No data available")} />
            <p className={styles.errorText}>
              {t("Không tìm thấy thông tin nhà cung cấp dữ liệu nào.", "No quantitative data providers found.")}
            </p>
            <button
              type="button"
              className={styles.retryBtn}
              onClick={() => resource.reload()}
            >
              {t("↻ Tải lại danh sách", "↻ Reload Provider List")}
            </button>
          </div>
        </div>
      ) : (
        <div className={styles.grid}>
          {providers.map((p) => (
            <article key={p.provider} className={styles.card}>
              <div className={styles.cardHeader}>
                <span className={styles.providerName}>{p.provider}</span>
                <StatusBadge status={p.status} />
              </div>

              <div className={styles.metaList}>
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>{t("Cập nhật gần nhất:", "Last Updated:")}</span>
                  <span className={`${styles.metaValue} tabular-nums`}>
                    {p.last_success
                      ? new Date(p.last_success).toLocaleString(numLocale)
                      : t("Chưa ghi nhận", "Never recorded")}
                  </span>
                </div>

                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>{t("Số bản ghi lần chạy cuối:", "Records Processed (Last Run):")}</span>
                  <span className={`${styles.metaValue} tabular-nums`}>
                    {p.records_last_run.toLocaleString(numLocale)}
                  </span>
                </div>

                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>{t("Độ tươi dữ liệu:", "Data Freshness:")}</span>
                  <span className={styles.metaValue}>{p.data_freshness}</span>
                </div>

                {p.requires && (
                  <div className={styles.metaRow}>
                    <span className={styles.metaLabel}>{t("Yêu cầu:", "Dependencies:")}</span>
                    <span className={styles.metaValue}>{p.requires}</span>
                  </div>
                )}
              </div>

              <button
                type="button"
                className={styles.actionButton}
                onClick={() =>
                  alert(
                    t(
                      "Tính năng kích hoạt thủ công chỉ khả dụng trong quyền quản trị nội bộ.",
                      "Manual sync trigger is restricted to internal administrative privileges."
                    )
                  )
                }
              >
                {t("Kích hoạt đồng bộ ngay", "Trigger Sync Now")}
              </button>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
