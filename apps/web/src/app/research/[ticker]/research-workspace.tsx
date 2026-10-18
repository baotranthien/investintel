"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getResearchWorkspace,
  type ResearchMetric,
  type ResearchTimelineItem,
  type ResearchWorkspace,
} from "@/lib/api";
import styles from "./research-workspace.module.css";

const metricNames: Record<string, string> = {
  revenue: "Revenue / Doanh thu", net_income: "Earnings / Lợi nhuận", eps_ttm: "EPS TTM",
  revenue_yoy: "Revenue YoY", net_income_yoy: "Earnings YoY", eps_yoy: "EPS YoY",
  revenue_cagr_3y: "Revenue CAGR 3Y", revenue_cagr_5y: "Revenue CAGR 5Y", eps_cagr_3y: "EPS CAGR 3Y",
  gross_margin: "Gross margin", ebit_margin: "EBIT margin", ebitda_margin: "EBITDA margin", net_margin: "Net margin",
  roe: "ROE", roa: "ROA", roic: "ROIC", cash: "Cash", total_assets: "Total assets",
  total_liabilities: "Total liabilities", total_equity: "Total equity", de_ratio: "Debt / Equity",
  debt_to_assets: "Debt / Assets", net_debt_ebitda: "Net debt / EBITDA", current_ratio: "Current ratio",
  quick_ratio: "Quick ratio", interest_coverage: "Interest coverage", cfo: "Cash from operations",
  fcf: "Free cash flow", cfo_to_ni: "CFO / Net income", fcf_to_ni: "FCF / Net income",
  dso: "Days sales outstanding", dio: "Days inventory outstanding", dpo: "Days payable outstanding",
  ccc: "Cash conversion cycle", bvps: "Book value / share", pe: "P/E", pb: "P/B", ev_ebitda: "EV / EBITDA",
  peg: "PEG", dividend_yield: "Dividend yield", fcf_yield: "FCF yield", dcf: "DCF", residual_income: "Residual income", ddm: "DDM",
};

const evidenceNames: Record<string, string> = {
  FACT: "FACT / Dữ kiện", MODEL_OUTPUT: "MODEL OUTPUT / Kết quả mô hình",
  INTERPRETATION: "INTERPRETATION / Diễn giải", HYPOTHESIS: "HYPOTHESIS / Giả thuyết",
  UNCERTAINTY: "UNCERTAINTY / Chưa đủ bằng chứng",
};

function formatDate(value: string | null | undefined) {
  if (!value) return "Không có ngày";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString("vi-VN");
}

function formatNumber(value: number | null, unit?: string | null) {
  if (value === null || !Number.isFinite(value)) return "—";
  const text = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(value);
  return unit === "%" || unit === "VND/share" ? `${text}${unit === "%" ? "%" : " VND/cp"}` : unit === "BILLION_VND" ? `${text} tỷ VND` : unit === "multiple" ? `${text}×` : unit === "days" ? `${text} ngày` : `${text}${unit ? ` ${unit}` : ""}`;
}

function Status({ value }: { value: string }) {
  const cls = value === "AVAILABLE" || value === "FACT" ? styles.statusGood : value === "STALE" ? styles.statusWarn : styles.statusMissing;
  return <span className={`${styles.status} ${cls}`}>{value.replaceAll("_", " ")}</span>;
}

function EvidenceDetails({ evidence }: { evidence: ResearchMetric["evidence"] }) {
  return <details className={styles.evidence}>
    <summary>{evidenceNames[evidence.claim_type] ?? evidence.claim_type}</summary>
    <dl>
      <div><dt>Source</dt><dd>{evidence.source ?? "Không có source"}</dd></div>
      <div><dt>Observation</dt><dd>{formatDate(evidence.observation_date)}</dd></div>
      <div><dt>Publication</dt><dd>{formatDate(evidence.publication_date)}</dd></div>
      <div><dt>Retrieved</dt><dd>{formatDate(evidence.retrieved_at)}</dd></div>
      <div><dt>Origin</dt><dd>{evidence.data_origin ?? "Unknown"}</dd></div>
      {evidence.source_url && <div><dt>Source URL</dt><dd><a href={evidence.source_url} target="_blank" rel="noreferrer">Open source</a></dd></div>}
      {evidence.note && <div><dt>Note</dt><dd>{evidence.note}</dd></div>}
    </dl>
  </details>;
}

function MetricTable({ metrics, keys }: { metrics: Record<string, ResearchMetric>; keys?: string[] }) {
  const entries = Object.entries(metrics).filter(([key]) => !keys || keys.includes(key));
  if (!entries.length) return <p className={styles.emptyText}>Chưa có metric khả dụng từ canonical data.</p>;
  return <div className={styles.metricList}>
    {entries.map(([key, metric]) => <article className={styles.metricRow} key={key}>
      <div><strong>{metricNames[key] ?? key.replaceAll("_", " ")}</strong><small>{metric.period ?? "Period unavailable"}{metric.calculation ? ` · ${metric.calculation}` : ""}</small></div>
      <div className={styles.metricValue}><b>{formatNumber(metric.value, metric.unit)}</b><Status value={metric.status} /></div>
      <EvidenceDetails evidence={metric.evidence} />
    </article>)}
  </div>;
}

function ClaimList({ claims }: { claims: Array<Record<string, unknown>> }) {
  if (!claims.length) return <p className={styles.emptyText}>Không có claim.</p>;
  return <ul className={styles.claimList}>{claims.map((claim, index) => {
    const type = String(claim.claim_type ?? "UNCERTAINTY");
    const changeText = claim.metric
      ? `${metricNames[String(claim.metric)] ?? String(claim.metric)} · ${String(claim.before)} → ${String(claim.current)}`
      : null;
    const text = String(claim.text ?? claim.description ?? changeText ?? "");
    return <li key={`${type}-${index}`}><Status value={type} /><span>{text}</span>{claim.source ? <small>{String(claim.source)} · {formatDate(String(claim.publication_date ?? ""))}</small> : null}</li>;
  })}</ul>;
}

function Timeline({ items }: { items: ResearchTimelineItem[] }) {
  if (!items.length) return <p className={styles.emptyText}>Chưa có event hoặc financial revision timeline có evidence.</p>;
  return <ol className={styles.timeline}>
    {items.map((item) => <li key={item.id}>
      <time>{formatDate(item.date)}</time>
      <div className={styles.timelineBody}>
        <div className={styles.timelineHead}><strong>{item.title}</strong><Status value={item.status} /></div>
        {item.before !== null && <p>Before <b>{item.before}</b> <span aria-hidden="true">→</span> Current <b>{item.current}</b></p>}
        <small>{item.kind} · {item.evidence.source ?? "Source unavailable"}</small>
        <details className={styles.evidence}><summary>{evidenceNames[item.evidence.claim_type] ?? item.evidence.claim_type}</summary><dl>
          <div><dt>Source</dt><dd>{item.evidence.source ?? "No source linked"}</dd></div>
          <div><dt>Publication</dt><dd>{formatDate(item.evidence.publication_date)}</dd></div>
          <div><dt>Origin</dt><dd>{item.evidence.data_origin ?? "Unknown"}</dd></div>
          {item.evidence.note && <div><dt>Note</dt><dd>{item.evidence.note}</dd></div>}
        </dl></details>
      </div>
    </li>)}
  </ol>;
}

function ResearchContent({ data }: { data: ResearchWorkspace }) {
  const history = data.fundamentals.history;
  const metricGroups = [
    { title: "Income & per share / Thu nhập", keys: ["revenue", "net_income", "eps_ttm", "revenue_yoy", "net_income_yoy", "eps_yoy", "revenue_cagr_3y", "revenue_cagr_5y", "eps_cagr_3y"] },
    { title: "Margins & returns / Biên lợi nhuận", keys: ["gross_margin", "ebit_margin", "ebitda_margin", "net_margin", "roe", "roa", "roic"] },
    { title: "Balance sheet / Bảng cân đối", keys: ["cash", "total_assets", "total_liabilities", "total_equity", "de_ratio", "debt_to_assets", "net_debt_ebitda", "current_ratio", "quick_ratio", "interest_coverage"] },
    { title: "Cash flow & working capital / Dòng tiền", keys: ["cfo", "fcf", "cfo_to_ni", "fcf_to_ni", "dso", "dio", "dpo", "ccc"] },
  ];

  return <>
    <section className={styles.overview} id="overview">
      <div className={styles.assetIdentity}>
        <p className={styles.eyebrow}>ASSET RESEARCH · {data.asset.exchange ?? "EXCHANGE UNAVAILABLE"}</p>
        <h1>{data.asset.symbol}<span>{data.asset.name}</span></h1>
        <p>{data.asset.sector} · {data.asset.asset_type} · {data.asset.currency}</p>
      </div>
      <div className={styles.quoteBlock}>
        <span>Price / Giá</span><strong>{data.price.value === null ? "—" : formatNumber(data.price.value, "VND")}</strong>
        <small>{formatDate(data.price.as_of_date)} · <Status value={data.price.status} /></small>
        <small>{data.price.source ?? "Không có nguồn giá"} · {data.price.data_origin}</small>
      </div>
      <div className={styles.summaryStats}>
        <div><span>Opportunity</span><b>{data.opportunity.score === null ? "—" : formatNumber(data.opportunity.score)}</b><Status value={data.opportunity.status} /></div>
        <div><span>Confidence</span><b>{data.opportunity.confidence}</b></div>
        <div><span>Risk</span><b>{data.risk.overall_score === null ? "—" : formatNumber(data.risk.overall_score)}</b><Status value={data.risk.status} /></div>
        <div><span>Horizon</span><b>{data.opportunity.horizon.replaceAll("_", " ")}</b></div>
        <div><span>Data quality</span><b>{data.data_quality.status}</b><small>History {data.data_quality.history_depth_years}Y · as of {formatDate(data.as_of_date)}</small></div>
      </div>
    </section>

    <nav className={styles.sectionNav} aria-label="Research sections">
      {["fundamentals", "sector", "valuation", "factors", "risk", "events", "summary"].map((section) => <a href={`#${section}`} key={section}>{section.replaceAll("_", " ")}</a>)}
    </nav>

    <section className={styles.section} id="fundamentals">
      <header className={styles.sectionHeader}><div><p className={styles.eyebrow}>CANONICAL FINANCIAL STATEMENTS</p><h2>Fundamentals / Cơ bản</h2></div><Status value={data.fundamentals.status} /></header>
      <p className={styles.sectionNote}>Period {data.fundamentals.period ?? "—"} · TTM {data.fundamentals.ttm_available ? "available" : "INSUFFICIENT_DATA"} · Published through {formatDate(data.fundamentals.latest_publication_date)} · {data.fundamentals.sources.join(", ") || "No source"}</p>
      <div className={styles.fundamentalGroups}>{metricGroups.map((group) => <div className={styles.metricGroup} key={group.title}><h3>{group.title}</h3><MetricTable metrics={data.fundamentals.metrics} keys={group.keys} /></div>)}</div>
      {data.fundamentals.earnings_quality && <details className={styles.disclosure}><summary>Earnings quality & financial health</summary><pre>{JSON.stringify({ earnings_quality: data.fundamentals.earnings_quality, financial_health: data.fundamentals.financial_health, quality_flags: data.fundamentals.quality_flags }, null, 2)}</pre></details>}
      {history.length >= 2 && <div className={styles.historyTable}><h3>Financial history / Lịch sử tài chính</h3><div className={styles.tableScroll}><table><thead><tr><th>Period</th><th>Revenue</th><th>Earnings</th><th>EPS</th><th>Published</th><th>Source</th></tr></thead><tbody>{history.map((row, index) => <tr key={`${row.fiscal_year}-${row.fiscal_quarter ?? "A"}-${index}`}><td>{row.fiscal_year ?? "—"}{row.period_type === "QUARTERLY" ? ` Q${row.fiscal_quarter ?? "?"}` : ""}</td><td>{formatNumber(row.revenue, "BILLION_VND")}</td><td>{formatNumber(row.earnings, "BILLION_VND")}</td><td>{formatNumber(row.eps, "VND/share")}</td><td>{formatDate(row.publication_date)}</td><td>{row.source ?? "Untraced"}</td></tr>)}</tbody></table></div></div>}
      {history.length < 2 && <p className={styles.emptyText}>Trend chart/history unavailable: fewer than two canonical periods.</p>}
    </section>

    <section className={styles.section} id="sector">
      <header className={styles.sectionHeader}><div><p className={styles.eyebrow}>SECTOR MODEL · {data.sector_analysis.sector}</p><h2>Sector analysis / Phân tích ngành</h2></div><Status value={data.sector_analysis.status} /></header>
      <p className={styles.sectionNote}>Applicable: {data.sector_analysis.applicable_metrics.join(" · ") || "—"}</p>
      <p className={styles.sectionNote}>Not applicable: {data.sector_analysis.not_applicable_metrics.join(" · ") || "—"}</p>
      {data.sector_analysis.notes.map((note) => <p className={styles.sectionNote} key={note}>{note}</p>)}
      <MetricTable metrics={data.sector_analysis.metrics} />
    </section>

    <section className={styles.section} id="valuation">
      <header className={styles.sectionHeader}><div><p className={styles.eyebrow}>VALUATION ENGINE OUTPUT</p><h2>Valuation / Định giá</h2></div><Status value={data.valuation.status} /></header>
      <MetricTable metrics={data.valuation.metrics} />
      <div className={styles.uncertainty}><strong>Fair value range / Bear · Base · Bull: {data.valuation.fair_value ? `${formatNumber(data.valuation.fair_value.bear, "VND")} · ${formatNumber(data.valuation.fair_value.base, "VND")} · ${formatNumber(data.valuation.fair_value.bull, "VND")}` : "INSUFFICIENT_DATA"}</strong><ul>{data.valuation.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></div>
    </section>

    <section className={styles.section} id="factors">
      <header className={styles.sectionHeader}><div><p className={styles.eyebrow}>FACTOR ENGINE</p><h2>Factors / Yếu tố</h2></div><Status value={data.factors.status} /></header>
      <div className={styles.factorGrid}>{Object.entries(data.factors.scores).map(([name, metric]) => <article key={name}><span>{name}</span><strong>{formatNumber(metric.value, metric.unit)}</strong><Status value={metric.status} /><EvidenceDetails evidence={metric.evidence} /></article>)}</div>
      <p className={styles.sectionNote}>Supporting: {data.factors.supporting.join(" · ") || "Chưa có factor evidence."} · Contradicting: {data.factors.contradicting.join(" · ") || "Chưa có factor evidence."}</p>
    </section>

    <section className={styles.section} id="risk">
      <header className={styles.sectionHeader}><div><p className={styles.eyebrow}>RISK ENGINE · 10 CATEGORIES</p><h2>Risk / Rủi ro</h2></div><Status value={data.risk.status} /></header>
      <div className={styles.riskGrid}>{data.risk.categories.map((category) => <article key={category.name}><strong>{category.name}</strong><span>{category.value === null ? "—" : formatNumber(category.value)}</span><Status value={category.status} /><small>{category.drivers.join(" · ") || "No evidence-backed driver."}</small></article>)}</div>
      <p className={styles.warning}>{data.risk.missing_data_warning}</p>
      <div className={styles.macroSensitivity}><h3>Macro Sensitivity / Độ nhạy vĩ mô</h3><Status value={data.macro_sensitivity.status} /><p>{data.macro_sensitivity.note}</p></div>
    </section>

    <section className={styles.section} id="events">
      <header className={styles.sectionHeader}><div><p className={styles.eyebrow}>CANONICAL EVENTS & CORPORATE ACTIONS</p><h2>Events / Sự kiện & Timeline</h2></div><Status value={data.events.length || data.timeline.length ? "AVAILABLE" : "INSUFFICIENT_DATA"} /></header>
      <Timeline items={data.timeline} />
      {data.events.length > 0 && <div className={styles.eventRecords}>{data.events.map((event) => <details className={styles.eventItem} key={String(event.id)}><summary>{String(event.title)} · {String(event.event_type)} · {formatDate(String(event.published_at ?? ""))}</summary><p>{String(event.description)}</p><pre>{JSON.stringify(event.evidence, null, 2)}</pre></details>)}</div>}
    </section>

    <section className={styles.section} id="summary">
      <header className={styles.sectionHeader}><div><p className={styles.eyebrow}>ENGINE & EVIDENCE ONLY · NO AI</p><h2>Research summary / Tóm tắt nghiên cứu</h2></div></header>
      <div className={styles.summaryGrid}>
        <div><h3>What Changed</h3><ClaimList claims={data.research_summary.what_changed} /></div>
        <div><h3>Why Now</h3><ClaimList claims={data.research_summary.why_now} /></div>
        <div><h3>Why Not Now</h3><ClaimList claims={data.research_summary.why_not_now} /></div>
        <div><h3>What Would Make Me Wrong</h3><ClaimList claims={data.research_summary.what_would_make_me_wrong} /></div>
      </div>
    </section>
  </>;
}

export default function ResearchWorkspaceClient({ symbol }: { symbol: string }) {
  const router = useRouter();
  const [resource, setResource] = useState<{ status: "loading" } | { status: "ready"; data: ResearchWorkspace } | { status: "error"; message: string; notFound: boolean }>({ status: "loading" });
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getResearchWorkspace(symbol, undefined, controller.signal).then((data) => setResource({ status: "ready", data })).catch((error: unknown) => {
      if (controller.signal.aborted) return;
      const notFound = typeof error === "object" && error !== null && "status" in error && error.status === 404;
      setResource({ status: "error", message: error instanceof Error ? error.message : "Research API không khả dụng.", notFound });
    });
    return () => controller.abort();
  }, [symbol, reload]);

  if (resource.status === "loading") return <div className={styles.stateBlock} role="status">Đang tải canonical research data cho {symbol}…</div>;
  if (resource.status === "error") return <div className={styles.stateBlock} role="alert"><strong>{resource.notFound ? "Không tìm thấy asset" : "Research API không khả dụng"}</strong><span>{resource.message}</span><div><button onClick={() => setReload((value) => value + 1)}>Thử lại</button><button onClick={() => router.push("/research")}>Research home</button></div></div>;

  return <div className={styles.workspace}>
    <div className={styles.workspaceMeta}><Status value={resource.data.status} /><span>AS OF {formatDate(resource.data.as_of_date)}</span><button onClick={() => setReload((value) => value + 1)}>↻ <span>Làm mới</span></button></div>
    <ResearchContent data={resource.data} />
  </div>;
}
