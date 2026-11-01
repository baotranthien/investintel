"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getAssets, getDataProviders, type AssetSummary, type DataProvider } from "@/lib/api";
import styles from "./page.module.css";

type LoadState<T> =
  | { status: "loading" }
  | { status: "loaded"; data: T }
  | { status: "error"; message: string };

function useDashboardData() {
  const [providers, setProviders] = useState<LoadState<DataProvider[]>>({ status: "loading" });
  const [assets, setAssets] = useState<LoadState<AssetSummary[]>>({ status: "loading" });
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    getDataProviders(controller.signal)
      .then((data) => setProviders({ status: "loaded", data }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setProviders({ status: "error", message: error instanceof Error ? error.message : "Không thể tải trạng thái nguồn dữ liệu." });
        }
      });

    getAssets(controller.signal)
      .then((data) => setAssets({ status: "loaded", data }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setAssets({ status: "error", message: error instanceof Error ? error.message : "Không thể tải danh sách tài sản." });
        }
      });

    return () => controller.abort();
  }, [refresh]);

  const reload = () => {
    setProviders({ status: "loading" });
    setAssets({ status: "loading" });
    setRefresh((value) => value + 1);
  };

  return { providers, assets, reload };
}

function ProviderState({ state }: { state: LoadState<DataProvider[]> }) {
  if (state.status === "loading") return <p className={styles.stateMessage} role="status">Đang kiểm tra kết nối nguồn dữ liệu…</p>;
  if (state.status === "error") {
    return <div className={styles.errorState} role="alert"><strong>Không thể xác nhận trạng thái nguồn</strong><span>{state.message}</span></div>;
  }
  if (state.data.length === 0) return <p className={styles.stateMessage}>API chưa trả về nguồn dữ liệu nào.</p>;

  return (
    <div className={styles.providerList}>
      {state.data.map((provider) => (
        <article className={styles.providerRow} key={provider.provider}>
          <div className={styles.providerIdentity}>
            <span className={`${styles.statusMark} ${provider.last_success ? styles.statusKnown : ""}`} aria-hidden="true" />
            <div className={styles.providerNameBlock}>
              <strong className={styles.providerTitle}>{provider.provider}</strong>
              <span className={styles.providerReason}>{provider.reason || provider.requires || "Nguồn dữ liệu đã kiểm định"}</span>
            </div>
          </div>
          <div className={styles.providerStatus}>
            <span className={styles.providerBadge}>{provider.status}</span>
            <span className={`${styles.providerDate} tabular-nums`}>
              {provider.last_success ? `Cập nhật: ${new Date(provider.last_success).toLocaleDateString("vi-VN")}` : provider.data_freshness}
            </span>
          </div>
        </article>
      ))}
    </div>
  );
}

function AssetState({ state }: { state: LoadState<AssetSummary[]> }) {
  if (state.status === "loading") return <p className={styles.stateMessage} role="status">Đang tải danh mục tài sản…</p>;
  if (state.status === "error") {
    return <div className={styles.errorState} role="alert"><strong>Danh sách tài sản chưa khả dụng</strong><span>{state.message}</span></div>;
  }
  if (state.data.length === 0) return <p className={styles.stateMessage}>Chưa có tài sản canonical trong API.</p>;

  const byType = state.data.reduce<Record<string, number>>((counts, asset) => {
    counts[asset.asset_type] = (counts[asset.asset_type] ?? 0) + 1;
    return counts;
  }, {});

  return (
    <div className={styles.assetContainer}>
      <div className={styles.assetCountHero}>
        <strong className={`${styles.assetTotalNum} tabular-nums`}>{state.data.length}</strong>
        <span className={styles.assetTotalLabel}>Tài sản thuộc Không gian Chuẩn hóa (Canonical Universe)</span>
      </div>
      <div className={styles.assetTypesGrid}>
        {Object.entries(byType).map(([type, count]) => (
          <div className={styles.assetTypeCard} key={type}>
            <span className={styles.assetTypeKey}>{type.replaceAll("_", " ")}</span>
            <strong className={`${styles.assetTypeVal} tabular-nums`}>{count}</strong>
          </div>
        ))}
      </div>
      <p className={styles.coverageNote}>
        Số lượng tài sản được lọc chặt chẽ theo tiêu chuẩn thanh khoản và chất lượng công bố BCTC HOSE/HNX.
      </p>
    </div>
  );
}

export default function Home() {
  const { providers, assets, reload } = useDashboardData();
  const loadedCount = Number(providers.status === "loaded") + Number(assets.status === "loaded");
  const errorCount = Number(providers.status === "error") + Number(assets.status === "error");
  const connectionStatus = errorCount === 2 ? "UNAVAILABLE" : errorCount > 0 ? "PARTIAL" : loadedCount === 2 ? "API RESPONDED" : "CHECKING";

  return (
    <div className={styles.page}>
      {/* 1. Confident Whitespace Hero */}
      <section className={styles.heroSection}>
        <div className={styles.heroContent}>
          <p className={styles.eyebrow}>INVESTINTEL · RESEARCH WORKSTATION</p>
          <h1 className={styles.heroTitle}>
            Đầu tư bắt đầu từ bằng chứng.
          </h1>
          <p className={styles.heroLede}>
            Mô hình định lượng tính toán độc lập. AI tổng hợp và diễn giải có nguồn dẫn chứng minh bạch. Quyết định phân bổ luôn thuộc về nhà đầu tư.
          </p>
        </div>
        <button className={styles.refreshButton} onClick={reload} type="button" aria-label="Làm mới trạng thái">
          ↻ <span>Làm mới hệ thống</span>
        </button>
      </section>

      {/* 2. System Quality Telemetry Strip */}
      <section className={styles.telemetryRibbon} aria-label="Trạng thái nền tảng">
        <div className={styles.ribbonLeft}>
          <span className={styles.ribbonLabel}>DATA QUALITY & LINEAGE</span>
          <strong className={styles.ribbonValue}>{connectionStatus}</strong>
        </div>
        <div className={styles.ribbonRight}>
          Mỗi chỉ số được kiểm chứng qua thời điểm quan sát, đơn vị công bố và phương pháp tính toán chuẩn mực.
        </div>
      </section>

      {/* 3. Research Pathways (Principle Four: Storytelling) */}
      <section className={styles.pathwaysSection}>
        <div className={styles.sectionHeaderRow}>
          <div>
            <p className={styles.eyebrow}>RESEARCH WORKFLOW</p>
            <h2 className={styles.sectionTitle}>Quy trình Nghiên cứu Đầu tư</h2>
          </div>
          <span className={styles.workflowTag}>FOUNDATION · PHASE 6B</span>
        </div>

        <div className={styles.pathwayCards}>
          <Link href="/market" className={styles.pathwayCard}>
            <div className={styles.cardStepNumber}>01</div>
            <strong className={styles.cardTitle}>Toàn cảnh Thị trường</strong>
            <p className={styles.cardDesc}>Market Regime, độ rộng dòng tiền và bối cảnh vĩ mô SBV/Fed.</p>
            <span className={styles.cardArrow} aria-hidden="true">→</span>
          </Link>

          <Link href="/opportunities" className={styles.pathwayCard}>
            <div className={styles.cardStepNumber}>02</div>
            <strong className={styles.cardTitle}>Sàng lọc Cơ hội</strong>
            <p className={styles.cardDesc}>Quét đa nhân tố Quality, Growth, Value, Dividend với phân loại rủi ro.</p>
            <span className={styles.cardArrow} aria-hidden="true">→</span>
          </Link>

          <Link href="/ai" className={`${styles.pathwayCard} ${styles.pathwayHighlight}`}>
            <div className={styles.cardStepNumber}>03</div>
            <strong className={styles.cardTitle}>Trợ lý AI Analyst</strong>
            <p className={styles.cardDesc}>Phân tích chuyên sâu BCTC, đối chiếu chống sai lệch và trích dẫn bằng chứng.</p>
            <span className={styles.cardArrow} aria-hidden="true">→</span>
          </Link>

          <Link href="/portfolio" className={styles.pathwayCard}>
            <div className={styles.cardStepNumber}>04</div>
            <strong className={styles.cardTitle}>Danh mục & Chiến lược</strong>
            <p className={styles.cardDesc}>Quản trị tỷ trọng phân bổ tài sản phòng thủ, tăng trưởng và kế hoạch DCA.</p>
            <span className={styles.cardArrow} aria-hidden="true">→</span>
          </Link>
        </div>
      </section>

      {/* 4. Structured but Exploratory Layout: Data Infrastructure */}
      <div className={styles.infrastructureGrid}>
        <section className={styles.dataPanel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.eyebrow}>DATA SOURCES</p>
              <h2 className={styles.panelTitle}>Nguồn dữ liệu kiểm định</h2>
            </div>
            <Link href="/data-center" className={styles.panelLink}>
              Data Center <span aria-hidden="true">→</span>
            </Link>
          </header>
          <ProviderState state={providers} />
        </section>

        <section className={styles.universePanel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.eyebrow}>CANONICAL COVERAGE</p>
              <h2 className={styles.panelTitle}>Phạm vi Tài sản Chuẩn hóa</h2>
            </div>
          </header>
          <AssetState state={assets} />
        </section>
      </div>

      <footer className={styles.footerNote}>
        {loadedCount === 2
          ? "Toàn bộ dữ liệu hiển thị theo mốc điểm-thời-gian (Point-in-Time) chính thức từ API nội bộ InvestIntel. Không sử dụng số liệu suy đoán."
          : "Hệ thống đang kiểm tra kết nối API. Mọi dữ liệu hiển thị đều bảo lưu tính toàn vẹn nguồn gốc."}
      </footer>
    </div>
  );
}
