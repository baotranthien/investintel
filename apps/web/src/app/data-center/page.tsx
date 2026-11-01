"use client";

import { useEffect, useState } from "react";
import { getDataProviders, type DataProvider } from "@/lib/api";
import styles from "./page.module.css";

export default function DataCenter() {
  const [providers, setProviders] = useState<DataProvider[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    getDataProviders(controller.signal)
      .then((data) => {
        setProviders(data);
        setLoading(false);
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          console.error("Failed to fetch providers", err);
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, []);

  if (loading) {
    return (
      <div className={styles.loadingState} role="status">
        Đang kiểm tra kết nối nguồn dữ liệu định lượng...
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>DATA INFRASTRUCTURE · SOURCE PROVENANCE</p>
          <h1 className={styles.title}>
            Chất lượng Dữ liệu <span>/ Data Center</span>
          </h1>
          <p className={styles.subTitle}>
            Giám sát độ tươi, tính liên tục và lịch sử cập nhật của các cổng dữ liệu định lượng.
          </p>
        </div>
      </header>

      <div className={styles.grid}>
        {providers.map((p) => {
          const isGood = p.status === "IMPLEMENTED" || p.status === "AVAILABLE";
          return (
            <article key={p.provider} className={styles.card}>
              <div className={styles.cardHeader}>
                <span className={styles.providerName}>{p.provider}</span>
                <span
                  className={`${styles.statusBadge} ${
                    isGood ? styles.statusGood : styles.statusWarn
                  }`}
                >
                  {p.status}
                </span>
              </div>

              <div className={styles.metaList}>
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>Cập nhật gần nhất:</span>
                  <span className={`${styles.metaValue} tabular-nums`}>
                    {p.last_success
                      ? new Date(p.last_success).toLocaleString("vi-VN")
                      : "Chưa ghi nhận"}
                  </span>
                </div>

                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>Số bản ghi lần chạy cuối:</span>
                  <span className={`${styles.metaValue} tabular-nums`}>
                    {p.records_last_run.toLocaleString("vi-VN")}
                  </span>
                </div>

                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>Độ tươi (Freshness):</span>
                  <span className={styles.metaValue}>{p.data_freshness}</span>
                </div>

                {p.requires && (
                  <div className={styles.metaRow}>
                    <span className={styles.metaLabel}>Yêu cầu:</span>
                    <span className={styles.metaValue}>{p.requires}</span>
                  </div>
                )}
              </div>

              <button
                type="button"
                className={styles.actionButton}
                onClick={() => alert("Tính năng kích hoạt thủ công chỉ khả dụng trong quyền quản trị nội bộ.")}
              >
                Kích hoạt đồng bộ / Run Now
              </button>
            </article>
          );
        })}
      </div>
    </div>
  );
}
