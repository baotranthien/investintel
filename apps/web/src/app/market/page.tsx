"use client";

import { useEffect, useState } from "react";
import {
  getLatestMacro,
  getMarketDashboard,
  getOpportunityScanner,
  type MacroLatest,
  type MacroSeriesLatest,
  type MarketDashboard,
  type MarketMetric,
  type OpportunityFilters,
  type OpportunityScanner,
} from "@/lib/api";
import styles from "./page.module.css";

type Resource<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; message: string };

const emptyFilters: OpportunityFilters = {
  universe: "ALL", sector: "", horizon: "MEDIUM_TERM", scoreMin: "",
  riskMax: "", confidence: "", factor: "", valuationStatus: "",
};

function displayStatus(status: string) {
  return status.replaceAll("_", " ");
}

function numberText(value: number | null, digits = 2) {
  return value === null || !Number.isFinite(value)
    ? "—"
    : new Intl.NumberFormat("vi-VN", { maximumFractionDigits: digits }).format(value);
}

function dateText(value: string | null) {
  if (!value) return "Không có timestamp";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("vi-VN");
}

function Status({ value }: { value: string }) {
  const style = value === "AVAILABLE" ? styles.good : value === "STALE" ? styles.warn : styles.missing;
  return <span className={`${styles.status} ${style}`}>{displayStatus(value)}</span>;
}

function ResourceState({ resource }: { resource: Resource<unknown> }) {
  if (resource.status === "loading") return <p className={styles.state} role="status">Đang tải từ API…</p>;
  if (resource.status === "error") return <div className={styles.error} role="alert"><strong>API không khả dụng</strong><span>{resource.message}</span></div>;
  return null;
}

function Evidence({ metric }: { metric: MarketMetric }) {
  return <details className={styles.evidence}>
    <summary>Evidence / Bằng chứng</summary>
    <dl>
      <div><dt>Claim type</dt><dd>FACT</dd></div>
      <div><dt>Source</dt><dd>{metric.source ?? "Không có source"}</dd></div>
      <div><dt>Data origin</dt><dd>{metric.data_origin ?? "Không xác định"}</dd></div>
      <div><dt>Observation</dt><dd>{metric.as_of_date ?? "Không có ngày"}</dd></div>
      <div><dt>Publication</dt><dd>{dateText(metric.published_at)}</dd></div>
      <div><dt>Retrieved</dt><dd>{dateText(metric.retrieved_at)}</dd></div>
      {metric.note && <div><dt>Note</dt><dd>{metric.note}</dd></div>}
    </dl>
  </details>;
}

function IndexCard({ item }: { item: MarketDashboard["indexes"][number] }) {
  return <article className={styles.indexCard}>
    <div className={styles.indexLine}><span>{item.symbol}</span><Status value={item.metric.status} /></div>
    <h2>{item.name}</h2>
    <strong className={styles.indexValue}>{numberText(item.metric.value)}</strong>
    <p>{item.metric.as_of_date ?? item.metric.note ?? "Không có dữ liệu"}</p>
    <Evidence metric={item.metric} />
  </article>;
}

function Metric({ title, metric }: { title: string; metric: MarketMetric }) {
  const unit = metric.unit === "percent_advancing" ? "% advancing"
    : metric.unit === "percent_20_sessions" ? "% / 20 phiên"
      : metric.unit === "VND" ? "VND" : "";
  return <article className={styles.metric}>
    <div className={styles.metricHeading}><span>{title}</span><Status value={metric.status} /></div>
    <strong>{metric.value === null ? "—" : numberText(metric.value)} <small>{unit}</small></strong>
    <p>{metric.as_of_date ?? metric.note ?? "Không có ngày"}</p>
    {metric.details.coverage !== undefined && <p>Coverage {numberText(Number(metric.details.coverage) * 100, 1)}% · ↑ {String(metric.details.advancing ?? 0)} · ↓ {String(metric.details.declining ?? 0)}</p>}
    <Evidence metric={metric} />
  </article>;
}

function Regime({ market }: { market: MarketDashboard }) {
  const regime = market.market_regime;
  return <section className={styles.panel}>
    <header className={styles.sectionHeading}>
      <div><p className={styles.eyebrow}>MODEL OUTPUT · MarketRegimeEngine</p><h2>Market Regime / Trạng thái thị trường</h2></div>
      <Status value={regime.regime === "INSUFFICIENT_DATA" ? regime.regime : market.status} />
    </header>
    <div className={styles.regimeLine}>
      <strong>{regime.regime}</strong>
      <span>Confidence / Độ tin cậy <b>{numberText(regime.confidence * 100, 0)}%</b></span>
      <span>Coverage <b>{regime.data_coverage === null ? "—" : `${numberText(regime.data_coverage * 100, 1)}%`}</b></span>
    </div>
    <p className={styles.muted}>Last updated / Cập nhật: {regime.as_of ?? "Không có"} · {regime.model_version}</p>
    <div className={styles.signalGrid}>
      <div><h3>Supporting signals / Hỗ trợ</h3>{regime.supporting_signals.length ? <ul>{regime.supporting_signals.map((signal) => <li key={signal}>{signal}</li>)}</ul> : <p>INSUFFICIENT_DATA · Chưa có tín hiệu</p>}</div>
      <div><h3>Conflicting signals / Xung đột</h3>{regime.conflicting_signals.length ? <ul>{regime.conflicting_signals.map((signal) => <li key={signal}>{signal}</li>)}</ul> : <p>{regime.regime === "INSUFFICIENT_DATA" ? "Chưa thể đánh giá khi thiếu dữ liệu." : "Không có tín hiệu xung đột được báo cáo."}</p>}</div>
    </div>
    {regime.historical_context.length > 0 && <p className={styles.muted}>Historical context: {regime.historical_context.join(" · ")}</p>}
  </section>;
}

function MacroGroup({ region, rows }: { region: string; rows: MacroSeriesLatest[] }) {
  return <section className={styles.macroGroup}>
    <header><p className={styles.eyebrow}>MACRO / VĨ MÔ</p><h3>{region}</h3></header>
    {rows.length === 0 ? <p className={styles.state}>Chưa có series đăng ký.</p> : rows.map((series) => <article className={styles.macroRow} key={series.series_id}>
      <div className={styles.macroHeading}><div><strong>{series.name}</strong><span>{series.series_id} · {series.frequency}</span></div><Status value={series.status} /></div>
      <strong className={styles.macroValue}>{series.value === null ? "—" : numberText(series.value)} <small>{series.unit}</small></strong>
      <p><b>FACT</b> · Observation {series.observation_date ?? "—"} · Release {series.release_date ?? "—"}</p>
      <details className={styles.evidence}><summary>Source / Provenance</summary><dl>
        <div><dt>Source</dt><dd>{series.source ?? series.provider}</dd></div>
        <div><dt>Publication</dt><dd>{dateText(series.published_at)}</dd></div>
        <div><dt>Retrieved</dt><dd>{dateText(series.retrieved_at)}</dd></div>
        <div><dt>Claim type</dt><dd>{series.value === null ? "UNCERTAINTY" : "FACT"}</dd></div>
        <div><dt>Origin</dt><dd>{series.data_origin ?? "Unknown"} · {series.source_type ?? "source type unknown"}</dd></div>
        {series.source_url && <div><dt>Source URL</dt><dd>{series.source_url}</dd></div>}
      </dl></details>
    </article>)}
  </section>;
}

function Opportunity({
  resource, filters, busy, onChange,
}: {
  resource: Resource<OpportunityScanner>;
  filters: OpportunityFilters;
  busy: boolean;
  onChange: <K extends keyof OpportunityFilters>(key: K, value: OpportunityFilters[K]) => void;
}) {
  const sectors = resource.status === "ready" ? resource.data.sector_options : [];
  return <section className={styles.panel}>
    <header className={styles.sectionHeading}>
      <div><p className={styles.eyebrow}>MODEL OUTPUT · OpportunityEngine</p><h2>Opportunity Scanner / Bộ lọc cơ hội</h2></div>
      {busy && <span className={styles.muted} role="status">Đang cập nhật…</span>}
    </header>
    <div className={styles.filters}>
      <label>Universe<select value={filters.universe} onChange={(event) => onChange("universe", event.target.value as OpportunityFilters["universe"])}><option value="ALL">Tất cả tài sản</option><option value="VN100">VN100</option><option value="VN300">VN300</option></select></label>
      <label>Sector<select value={filters.sector} onChange={(event) => onChange("sector", event.target.value)}><option value="">Tất cả ngành</option>{sectors.map((sector) => <option key={sector} value={sector}>{sector}</option>)}</select></label>
      <label>Horizon<select value={filters.horizon} onChange={(event) => onChange("horizon", event.target.value as OpportunityFilters["horizon"])}><option value="MEDIUM_TERM">1–12 tháng</option><option value="LONG_TERM">3–10 năm</option></select></label>
      <label>Score min<input aria-label="Opportunity score tối thiểu" type="number" min="0" max="100" value={filters.scoreMin} onChange={(event) => onChange("scoreMin", event.target.value)} /></label>
      <label>Risk max<input aria-label="Risk tối đa" type="number" min="0" max="100" value={filters.riskMax} onChange={(event) => onChange("riskMax", event.target.value)} /></label>
      <label>Confidence<select value={filters.confidence} onChange={(event) => onChange("confidence", event.target.value)}><option value="">Tất cả</option><option>HIGH</option><option>MODERATE</option><option>LOW</option><option>INSUFFICIENT</option></select></label>
      <label>Factor<select value={filters.factor} onChange={(event) => onChange("factor", event.target.value)}><option value="">Tất cả factors</option>{["QUALITY", "GROWTH", "VALUE", "DIVIDEND", "MOMENTUM", "DEFENSIVE", "CYCLICAL"].map((factor) => <option key={factor}>{factor}</option>)}</select></label>
      <label>Valuation<select value={filters.valuationStatus} onChange={(event) => onChange("valuationStatus", event.target.value)}><option value="">Tất cả trạng thái</option><option value="AVAILABLE">AVAILABLE</option><option value="INSUFFICIENT_DATA">INSUFFICIENT_DATA</option></select></label>
    </div>
    <ResourceState resource={resource} />
    {resource.status === "ready" && <>
      {resource.data.note && <p className={styles.filterWarning}>{resource.data.note}</p>}
      {resource.data.unavailable_filters.map((filter) => <p className={styles.filterError} key={filter}>{filter}</p>)}
      {resource.data.results.length === 0 ? <div className={styles.empty}><Status value={resource.data.status} /><p>Không có kết quả đủ dữ liệu với filters hiện tại.</p></div> : <>
        <div className={styles.tableWrap}><table className={styles.scannerTable}>
          <thead><tr><th>Asset</th><th>Opportunity</th><th>Confidence</th><th>Risk</th><th>Valuation</th><th>Factor</th><th>Freshness</th><th>Evidence</th></tr></thead>
          <tbody>{resource.data.results.map((item) => <tr key={item.symbol}>
            <td><strong>{item.symbol}</strong><span>{item.name}</span></td>
            <td>{item.opportunity_score === null ? <Status value={item.data_status} /> : numberText(item.opportunity_score)}</td>
            <td>{item.confidence}</td><td>{item.risk_score === null ? "—" : numberText(item.risk_score)}</td>
            <td>{item.valuation_status}</td><td>{item.factor_status}</td>
            <td><Status value={item.data_freshness.status} /><small>{item.data_freshness.as_of_date ?? "No date"}</small></td>
            <td><details className={styles.evidence}><summary>Claims</summary><dl>
              <div><dt>Claim type</dt><dd>UNCERTAINTY</dd></div>
              <div><dt>Why now</dt><dd>{item.why_now?.length ? item.why_now.map((claim) => claim.description).join(" · ") : "Chưa có engine evidence."}</dd></div>
              <div><dt>Why not now</dt><dd>{item.why_not_now?.length ? item.why_not_now.map((claim) => claim.description).join(" · ") : "Chưa có engine evidence."}</dd></div>
              <div><dt>Factor summary</dt><dd>{item.factor_summary ? JSON.stringify(item.factor_summary) : "INSUFFICIENT_DATA"}</dd></div>
              <div><dt>What could go wrong</dt><dd>{item.what_could_go_wrong?.length ? item.what_could_go_wrong.join(" · ") : "Chưa có evidence gắn với tài sản."}</dd></div>
              <div><dt>Source / date</dt><dd>{item.data_freshness.source ?? "Không có source"} · {item.data_freshness.as_of_date ?? "Không có ngày"}</dd></div>
            </dl></details></td>
          </tr>)}</tbody>
        </table></div>
        <div className={styles.mobileItems}>{resource.data.results.map((item) => <article key={item.symbol}>
          <div><strong>{item.symbol}</strong><span>{item.name}</span></div><Status value={item.data_status} />
          <dl><div><dt>Confidence</dt><dd>{item.confidence}</dd></div><div><dt>Risk</dt><dd>{item.risk_score === null ? "—" : numberText(item.risk_score)}</dd></div><div><dt>Valuation</dt><dd>{item.valuation_status}</dd></div><div><dt>Factor</dt><dd>{item.factor_status}</dd></div></dl>
          <details className={styles.evidence}><summary>Evidence / Bằng chứng</summary><dl>
            <div><dt>Claim type</dt><dd>UNCERTAINTY</dd></div>
            <div><dt>Why now</dt><dd>{item.why_now?.length ? item.why_now.map((claim) => claim.description).join(" · ") : "Chưa có engine evidence."}</dd></div>
            <div><dt>Why not now</dt><dd>{item.why_not_now?.length ? item.why_not_now.map((claim) => claim.description).join(" · ") : "Chưa có engine evidence."}</dd></div>
            <div><dt>Factor summary</dt><dd>{item.factor_summary ? JSON.stringify(item.factor_summary) : "INSUFFICIENT_DATA"}</dd></div>
            <div><dt>What could go wrong</dt><dd>{item.what_could_go_wrong?.length ? item.what_could_go_wrong.join(" · ") : "Chưa có evidence gắn với tài sản."}</dd></div>
            <div><dt>Source / date</dt><dd>{item.data_freshness.source ?? "Không có source"} · {item.data_freshness.as_of_date ?? "Không có ngày"}</dd></div>
          </dl></details>
        </article>)}</div>
      </>}
    </>}
  </section>;
}

export default function MarketPage() {
  const [market, setMarket] = useState<Resource<MarketDashboard>>({ status: "loading" });
  const [macro, setMacro] = useState<Resource<MacroLatest>>({ status: "loading" });
  const [scanner, setScanner] = useState<Resource<OpportunityScanner>>({ status: "loading" });
  const [filters, setFilters] = useState(emptyFilters);
  const [scannerBusy, setScannerBusy] = useState(true);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getMarketDashboard(controller.signal).then((data) => setMarket({ status: "ready", data })).catch((error: unknown) => {
      if (!controller.signal.aborted) setMarket({ status: "error", message: error instanceof Error ? error.message : "Market API error" });
    });
    getLatestMacro(controller.signal).then((data) => setMacro({ status: "ready", data })).catch((error: unknown) => {
      if (!controller.signal.aborted) setMacro({ status: "error", message: error instanceof Error ? error.message : "Macro API error" });
    });
    return () => controller.abort();
  }, [refresh]);

  useEffect(() => {
    const controller = new AbortController();
    getOpportunityScanner(filters, controller.signal).then((data) => setScanner({ status: "ready", data })).catch((error: unknown) => {
      if (!controller.signal.aborted) setScanner({ status: "error", message: error instanceof Error ? error.message : "Opportunity API error" });
    }).finally(() => {
      if (!controller.signal.aborted) setScannerBusy(false);
    });
    return () => controller.abort();
  }, [filters, refresh]);

  function changeFilter<K extends keyof OpportunityFilters>(key: K, value: OpportunityFilters[K]) {
    setScannerBusy(true);
    setFilters((current) => ({ ...current, [key]: value }));
  }

  function reload() {
    setMarket({ status: "loading" });
    setMacro({ status: "loading" });
    setScanner({ status: "loading" });
    setScannerBusy(true);
    setRefresh((value) => value + 1);
  }

  return <div className={styles.page}>
    <header className={styles.pageHeader}>
      <div><p className={styles.eyebrow}>PHASE 6B · MARKET INTELLIGENCE</p><h1>Thị trường <span>/ Market</span></h1><p>Overview · Regime · Macro · Opportunity. Mỗi kết luận gắn với dữ liệu và nguồn.</p></div>
      <button type="button" aria-label="Tải lại market data" className={styles.refresh} onClick={reload}>↻ <span>Làm mới</span></button>
    </header>

    {market.status === "ready" && <div className={styles.marketMeta}><Status value={market.data.status} /><span>Market as of {market.data.as_of_date}</span></div>}
    <section className={styles.indexGrid} aria-label="Market overview indices">
      {market.status === "loading" && <p className={styles.state} role="status">Đang tải index quotes…</p>}
      {market.status === "error" && <ResourceState resource={market} />}
      {market.status === "ready" && market.data.indexes.map((item) => <IndexCard item={item} key={item.symbol} />)}
    </section>

    <div className={styles.primaryGrid}>
      <div>{market.status === "loading" ? <section className={styles.panel}><p className={styles.state} role="status">Đang tính market regime…</p></section>
        : market.status === "error" ? <section className={styles.panel}><ResourceState resource={market} /></section>
          : <Regime market={market.data} />}</div>
      <section className={styles.metricGrid}>
        {market.status === "ready" ? <>
          <Metric title="Breadth / Độ rộng" metric={market.data.breadth} />
          <Metric title="Momentum / Động lượng" metric={market.data.momentum} />
          <Metric title="Liquidity / Thanh khoản" metric={market.data.liquidity} />
          <Metric title="Foreign flow / Khối ngoại" metric={market.data.foreign_flow} />
        </> : <ResourceState resource={market} />}
      </section>
    </div>

    <section className={styles.panel}>
      <header className={styles.sectionHeading}><div><p className={styles.eyebrow}>OBSERVATIONS · SOURCE-BOUND</p><h2>Macro / Vĩ mô</h2></div>{macro.status === "ready" && <Status value={macro.data.status} />}</header>
      <ResourceState resource={macro} />
      {macro.status === "ready" && <div className={styles.macroGrid}>
        {(Object.entries(macro.data.regions) as Array<[MacroSeriesLatest["region"], MacroSeriesLatest[]]>).filter(([region, rows]) => (region === "VIETNAM" || region === "US") ? rows.length > 0 : rows.some((series) => series.value !== null)).map(([region, rows]) => <MacroGroup key={region} region={region} rows={rows} />)}
        {Object.values(macro.data.regions).every((rows) => rows.length === 0 || rows.every((series) => series.value === null)) && <div className={styles.empty}><Status value="INSUFFICIENT_DATA" /><p>Chưa có macro observation khả dụng từ nguồn đã đăng ký.</p></div>}
      </div>}
    </section>

    <Opportunity resource={scanner} filters={filters} busy={scannerBusy} onChange={changeFilter} />

    <section className={styles.panel}>
      <header className={styles.sectionHeading}><div><p className={styles.eyebrow}>CANONICAL EVENT RECORDS</p><h2>Major market events / Sự kiện trọng yếu</h2></div>{market.status === "ready" && <Status value={market.data.events_status} />}</header>
      {market.status === "loading" && <p className={styles.state} role="status">Đang tải event records…</p>}
      {market.status === "error" && <ResourceState resource={market} />}
      {market.status === "ready" && market.data.major_events.length === 0 && <div className={styles.empty}><Status value={market.data.events_status} /><p>Không có major event record đủ điều kiện.</p></div>}
      {market.status === "ready" && market.data.major_events.length > 0 && <div className={styles.eventList}>{market.data.major_events.map((event) => <article key={event.id}>
        <div className={styles.macroHeading}><strong>{event.title}</strong><Status value={event.materiality} /></div>
        <p><b>FACT</b> · {event.event_type} · Severity {numberText(event.severity, 0)} · Published {dateText(event.published_at)}</p>
        <details className={styles.evidence}><summary>Evidence / Nguồn</summary><dl><div><dt>Source</dt><dd>{event.source ?? "Source chưa liên kết"}</dd></div><div><dt>Documents</dt><dd>{event.source_documents.length ? event.source_documents.join(" · ") : "Không có source document"}</dd></div></dl></details>
      </article>)}</div>}
    </section>
    <footer className={styles.footer}>`STALE`, `INSUFFICIENT_DATA` và provenance được giữ nguyên như API trả về. Không hiển thị số thay thế.</footer>
  </div>;
}