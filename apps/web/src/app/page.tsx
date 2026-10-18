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
  if (state.status === "loading") return <p className={styles.stateMessage} role="status">Đang kiểm tra nguồn dữ liệu…</p>;
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
            <div><strong>{provider.provider}</strong><span>{provider.reason || provider.requires || "Nguồn đã đăng ký"}</span></div>
          </div>
          <div className={styles.providerStatus}>
            <strong>{provider.status}</strong>
            <span>{provider.last_success ? `Thành công gần nhất · ${new Date(provider.last_success).toLocaleString("vi-VN")}` : provider.data_freshness}</span>
          </div>
        </article>
      ))}
    </div>
  );
}

function AssetState({ state }: { state: LoadState<AssetSummary[]> }) {
  if (state.status === "loading") return <p className={styles.stateMessage} role="status">Đang tải danh sách tài sản…</p>;
  if (state.status === "error") {
    return <div className={styles.errorState} role="alert"><strong>Danh sách tài sản chưa khả dụng</strong><span>{state.message}</span></div>;
  }
  if (state.data.length === 0) return <p className={styles.stateMessage}>Chưa có tài sản canonical trong API.</p>;

  const byType = state.data.reduce<Record<string, number>>((counts, asset) => {
    counts[asset.asset_type] = (counts[asset.asset_type] ?? 0) + 1;
    return counts;
  }, {});

  return (
    <>
      <div className={styles.assetCount}><strong>{state.data.length}</strong><span>tài sản được API trả về</span></div>
      <div className={styles.assetTypes}>
        {Object.entries(byType).map(([type, count]) => <div className={styles.assetType} key={type}><span>{type.replaceAll("_", " ")}</span><strong>{count}</strong></div>)}
      </div>
      <p className={styles.coverageNote}>Số lượng tài sản không đại diện cho độ phủ dữ liệu tài chính hoặc dữ liệu live.</p>
    </>
  );
}

export default function Home() {
  const { providers, assets, reload } = useDashboardData();
  const loadedCount = Number(providers.status === "loaded") + Number(assets.status === "loaded");
  const errorCount = Number(providers.status === "error") + Number(assets.status === "error");
  const connectionStatus = errorCount === 2 ? "UNAVAILABLE" : errorCount > 0 ? "PARTIAL" : loadedCount === 2 ? "API RESPONDED" : "CHECKING";

  return (
    <div className={styles.page}>
      <section className={styles.intro}>
        <div>
          <p className={styles.eyebrow}>PERSONAL INVESTMENT INTELLIGENCE</p>
          <h1>Đầu tư bắt đầu<br /><em>từ bằng chứng.</em></h1>
          <p className={styles.lede}>Quant engine calculates. AI explains and synthesizes. Quyết định luôn thuộc về bạn.</p>
        </div>
        <button className={styles.refreshButton} onClick={reload} type="button" aria-label="Tải lại dữ liệu">↻ <span>Tải lại dữ liệu</span></button>
      </section>

      <section className={styles.systemStrip} aria-label="Trạng thái nền tảng">
        <div><span className={styles.stripLabel}>DATA QUALITY / CHẤT LƯỢNG DỮ LIỆU</span><strong className={styles.stripValue}>{connectionStatus}</strong></div>
        <div className={styles.stripAside}>Mỗi con số cần source, thời điểm và context.</div>
      </section>

      <div className={styles.overviewGrid}>
        <section className={styles.dataPanel}>
          <header className={styles.panelHeader}>
            <div><p className={styles.eyebrow}>CONNECTIONS</p><h2>Nguồn dữ liệu</h2></div>
            <Link href="/data-center" className={styles.panelLink}>Chi tiết <span aria-hidden="true">→</span></Link>
          </header>
          <ProviderState state={providers} />
        </section>

        <section className={styles.universePanel}>
          <p className={styles.eyebrow}>CANONICAL UNIVERSE</p>
          <h2>Phạm vi tài sản</h2>
          <AssetState state={assets} />
        </section>
      </div>

      <section className={styles.routeSection}>
        <div className={styles.routeHeading}><div><p className={styles.eyebrow}>RESEARCH WORKSPACE</p><h2>Không gian nghiên cứu</h2></div><span>FOUNDATION</span></div>
        <div className={styles.routeLinks}>
          <Link href="/market"><span>01</span><strong>Thị trường</strong><small>Market / Regime</small><b aria-hidden="true">↗</b></Link>
          <Link href="/opportunities"><span>02</span><strong>Cơ hội</strong><small>Opportunity scanner</small><b aria-hidden="true">↗</b></Link>
          <Link href="/portfolio"><span>03</span><strong>Danh mục</strong><small>Portfolio / DCA</small><b aria-hidden="true">↗</b></Link>
          <Link href="/watchlist"><span>04</span><strong>Theo dõi</strong><small>Thesis monitor</small><b aria-hidden="true">↗</b></Link>
        </div>
      </section>

      <footer className={styles.footerNote}>{loadedCount === 2 ? "Dữ liệu lấy từ API hiện tại; trạng thái nguồn được giữ nguyên như backend trả về." : "Chưa có xác nhận đầy đủ từ API. Không hiển thị dữ liệu thay thế."}</footer>
    </div>
  );
}
