"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  captureDecisionSnapshot,
  captureWatchlistSnapshot,
  createWatchlistItem,
  deleteWatchlistItem,
  getDecisionContext,
  getWatchlist,
  reviewWatchlistItem,
  patchWatchlistItem,
  type DecisionContext,
  type WatchlistItem,
} from "@/lib/api";
import styles from "./page.module.css";

type Resource = { state: "loading" } | { state: "ready"; rows: WatchlistItem[] } | { state: "error"; message: string };
type DecisionResource = { state: "idle" | "loading" } | { state: "ready"; data: DecisionContext } | { state: "error"; message: string };

function displayDate(value: string | null) {
  return value ? new Date(value).toLocaleDateString("vi-VN") : "N/A";
}
function Status({ value }: { value: string }) {
  const kind = value === "AVAILABLE" || value === "HIGH" ? styles.good : value === "STALE" || value === "PARTIAL" ? styles.warn : styles.missing;
  return <span className={`${styles.status} ${kind}`}>{value.replaceAll("_", " ")}</span>;
}

function present(value: unknown) {
  if (value === null || value === undefined) return "Unavailable";
  if (Array.isArray(value)) return value.length ? `${value.length} records` : "No records";
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    if ("status" in record && typeof record.status === "string") return record.status.replaceAll("_", " ");
    if ("regime" in record && typeof record.regime === "string") return record.regime.replaceAll("_", " ");
    return `${Object.keys(record).length} tracked fields`;
  }
  return String(value);
}

function DecisionBrief({ symbol }: { symbol: string }) {
  const [open, setOpen] = useState(false);
  const [resource, setResource] = useState<DecisionResource>({ state: "idle" });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [asOf, setAsOf] = useState("");

  async function loadContext() {
    setResource({ state: "loading" });
    setNotice("");
    try {
      setResource({ state: "ready", data: await getDecisionContext(symbol, asOf || undefined) });
    } catch (caught) {
      setResource({ state: "error", message: caught instanceof Error ? caught.message : "Decision API unavailable" });
    }
  }

  async function captureSnapshot() {
    setBusy(true);
    setNotice("");
    try {
      const receipt = await captureDecisionSnapshot(symbol, asOf || undefined);
      setNotice(`Snapshot ${receipt.id} saved for ${receipt.as_of_date}.`);
      await loadContext();
    } catch (caught) {
      setResource({ state: "error", message: caught instanceof Error ? caught.message : "Snapshot capture failed" });
    } finally {
      setBusy(false);
    }
  }

  function toggle() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    void loadContext();
  }

  return <div className={styles.decisionWrap}>
    <button className={styles.decisionToggle} type="button" aria-expanded={open} onClick={toggle}>
      {open ? "Ẩn / Hide brief" : "Bản phân tích / Decision brief"}
    </button>
    {open && <section className={styles.decisionBrief} aria-label={`${symbol} decision brief`}>
      <header className={styles.decisionHeader}>
        <div><h3>Bối cảnh quyết định / Decision context</h3><p>Evidence-linked view; not a trade instruction.</p></div>
        {resource.state === "ready" && <div className={styles.decisionActions}>
          <label>As-of date<input aria-label="As-of date" type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} /></label>
          <Status value={resource.data.decision_state} />
          <button type="button" disabled={busy} onClick={() => void loadContext()}>Làm mới / Refresh</button>
          <button type="button" disabled={busy} onClick={() => void captureSnapshot()}>{busy ? "Đang lưu..." : "Chụp snapshot / Capture"}</button>
        </div>}
      </header>
      {notice && <p className={styles.decisionNotice} role="status">{notice}</p>}
      {resource.state === "loading" && <p className={styles.empty} role="status">Loading decision context...</p>}
      {resource.state === "error" && <div className={styles.error} role="alert"><strong>Decision context unavailable</strong><span>{resource.message}</span></div>}
      {resource.state === "ready" && <>
        <p className={styles.decisionAsOf}>As of {displayDate(resource.data.as_of_date)}; evidence status <Status value={resource.data.decision_state} /></p>
        <div className={styles.decisionSection}>
          <h4>Thay đổi / What changed</h4>
          {resource.data.what_changed.map((change, index) => <div className={styles.decisionChange} key={`${change.metric ?? "change"}-${index}`}>
            <div><strong>{change.metric ?? "Snapshot comparison"}</strong><Status value={change.claim_type} /></div>
            <p>{present(change.before)} <span aria-hidden="true">-&gt;</span> {present(change.after)}</p>
            <small>{change.date} | {change.responsible_module} | {change.source ?? "source unavailable"}{change.magnitude ? ` | delta ${change.magnitude.absolute}${change.magnitude.relative_pct === null ? "" : ` (${change.magnitude.relative_pct.toFixed(2)}%)`}` : ""}</small>
          </div>)}
        </div>
        <div className={styles.decisionGrid}>
          <div className={styles.decisionSection}><h4>Vì sao lúc này / Why now</h4>{resource.data.why_now.map((claim, index) => <p key={`now-${index}`}><Status value={String(claim.claim_type ?? "UNCERTAINTY")} /> {String(claim.text ?? "No supported driver.")} <small>{String(claim.source ?? "")}</small></p>)}</div>
          <div className={styles.decisionSection}><h4>Vì sao chưa / Why not now</h4>{resource.data.why_not_now.map((claim, index) => <p key={`not-${index}`}><Status value={String(claim.claim_type ?? "UNCERTAINTY")} /> {String(claim.text ?? "No supported blocker.")} <small>{String(claim.source ?? "")}</small></p>)}</div>
          <div className={styles.decisionSection}><h4>Điều gì làm luận điểm sai / What would make me wrong</h4>{resource.data.what_would_make_me_wrong.length ? resource.data.what_would_make_me_wrong.map((item, index) => <p key={`wrong-${index}`}><Status value={String(item.type ?? "USER_DEFINED")} /> {String(item.condition ?? "Condition unavailable.")}</p>) : <p>No user-defined invalidation condition is recorded.</p>}</div>
          <div className={styles.decisionSection}><h4>Kịch bản / Scenario</h4>{Object.entries(resource.data.scenario).map(([name, scenario]) => <p key={name}><strong>{name.toUpperCase()}</strong> <Status value={scenario.status} /> {scenario.uncertainty ?? "No supported scenario range."}</p>)}</div>
        </div>
        <div className={styles.decisionSection}>
          <h4>Đóng góp riêng biệt / Explainability</h4>
          <div className={styles.contributionList}>{Object.entries(resource.data.explainability).map(([name, contribution]) => <div key={name}><strong>{name.replaceAll("_", " ")}</strong><Status value={contribution.status} /><span>{present(contribution.value)}</span></div>)}</div>
        </div>
        <details className={styles.decisionEvidence}>
          <summary>Sổ bằng chứng / Evidence register ({resource.data.evidence.length})</summary>
          {resource.data.evidence.length ? resource.data.evidence.map((item, index) => <p key={`evidence-${index}`}><Status value={String(item.claim_type ?? "UNCERTAINTY")} /><strong>{String(item.responsible_module ?? "source")}</strong> | {String(item.source ?? "source unavailable")} | observation {String(item.observation_date ?? "unavailable")} | publication {String(item.publication_date ?? "unavailable")} | freshness {String(item.freshness ?? "unavailable")} | {String(item.data_origin ?? "origin unavailable")}</p>) : <p>No evidence records are available.</p>}
        </details>
      </>}
    </section>}
  </div>;
}

export default function WatchlistPage() {
  const [resource, setResource] = useState<Resource>({ state: "loading" });
  const [symbolFilter, setSymbolFilter] = useState("");
  const [horizonFilter, setHorizonFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sortBy, setSortBy] = useState("changed");
  const [reload, setReload] = useState(0);
  const [busyId, setBusyId] = useState<number | "create" | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    getWatchlist(controller.signal).then((rows) => setResource({ state: "ready", rows })).catch((caught: unknown) => {
      if (!controller.signal.aborted) setResource({ state: "error", message: caught instanceof Error ? caught.message : "Watchlist API error" });
    });
    return () => controller.abort();
  }, [reload]);

  const rows = useMemo(() => {
    if (resource.state !== "ready") return [];
    const filtered = resource.rows.filter((item) => {
      if (symbolFilter && !`${item.symbol} ${item.name}`.toLowerCase().includes(symbolFilter.toLowerCase())) return false;
      if (horizonFilter && item.horizon !== horizonFilter) return false;
      if (statusFilter && item.data_status !== statusFilter) return false;
      return true;
    });
    return filtered.sort((a, b) => sortBy === "symbol" ? a.symbol.localeCompare(b.symbol) : sortBy === "opportunity" ? (b.opportunity ?? -1) - (a.opportunity ?? -1) : b.last_changed_at.localeCompare(a.last_changed_at));
  }, [resource, symbolFilter, horizonFilter, statusFilter, sortBy]);

  async function perform(id: number | "create", operation: () => Promise<unknown>, success: string) {
    setBusyId(id); setError(""); setNotice("");
    try { await operation(); setNotice(success); setReload((value) => value + 1); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Không thể hoàn thành thao tác."); }
    finally { setBusyId(null); }
  }

  async function addItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const payload = Object.fromEntries(values.entries());
    await perform("create", () => createWatchlistItem(payload), "Đã thêm mã vào danh sách theo dõi.");
    form.reset();
  }

  async function editThesis(event: FormEvent<HTMLFormElement>, item: WatchlistItem) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    await perform(item.id, () => patchWatchlistItem(item.id, {
      thesis: String(values.get("thesis") ?? ""),
      horizon: String(values.get("horizon") ?? "") || null,
      invalidation: String(values.get("invalidation") ?? "") || null,
      change_reason: String(values.get("change_reason") ?? ""),
    }), "Đã lưu thay đổi luận điểm kèm lý do.");
  }

  return <div className={styles.page}>
    <header className={styles.header}><div><p className={styles.eyebrow}>LOCAL RESEARCH TRACKER</p><h1>Theo dõi <span>/ Watchlist</span></h1><p>Nghiên cứu cá nhân dựa trên dữ liệu có nguồn.</p></div><button className={styles.refresh} aria-label="Làm mới danh sách" title="Làm mới danh sách" onClick={() => setReload((value) => value + 1)}>↻ <span>Làm mới</span></button></header>
    {notice && <p className={styles.notice} role="status">{notice}</p>}{error && <div className={styles.error} role="alert"><strong>API operation failed</strong><span>{error}</span></div>}

    <section className={styles.section}>
      <header><div><p className={styles.eyebrow}>MANUAL THESIS</p><h2>Add to watchlist</h2></div></header>
      <form className={styles.addForm} onSubmit={addItem}>
        <label>Symbol<input name="symbol" required maxLength={20} placeholder="Ticker" /></label>
        <label>Horizon<select name="horizon" defaultValue=""><option value="">Not set</option><option value="MEDIUM_TERM">1 to 12 months</option><option value="LONG_TERM">3 to 10 years</option></select></label>
        <label>Thesis<input name="thesis" maxLength={4000} placeholder="Optional current thesis" /></label>
        <label>Invalidation<input name="invalidation" maxLength={4000} placeholder="What would change your view?" /></label>
        <button disabled={busyId === "create"} type="submit">Add asset</button>
      </form>
    </section>

    <section className={styles.section}>
      <header><div><p className={styles.eyebrow}>CANONICAL ASSET DATA</p><h2>Watchlist entries</h2></div><span>{resource.state === "ready" ? `${rows.length} shown / ${resource.rows.length} total` : ""}</span></header>
      <div className={styles.filters}>
        <label>Search<input value={symbolFilter} onChange={(event) => setSymbolFilter(event.target.value)} placeholder="Ticker or name" /></label>
        <label>Horizon<select value={horizonFilter} onChange={(event) => setHorizonFilter(event.target.value)}><option value="">All horizons</option><option value="MEDIUM_TERM">1 to 12 months</option><option value="LONG_TERM">3 to 10 years</option></select></label>
        <label>Data state<select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="">All states</option><option value="AVAILABLE">AVAILABLE</option><option value="PARTIAL">PARTIAL</option><option value="INSUFFICIENT_DATA">INSUFFICIENT_DATA</option></select></label>
        <label>Sort<select value={sortBy} onChange={(event) => setSortBy(event.target.value)}><option value="changed">Last changed</option><option value="symbol">Symbol</option><option value="opportunity">Opportunity score</option></select></label>
      </div>
      {resource.state === "loading" && <p className={styles.empty} role="status">Loading watchlist from API...</p>}
      {resource.state === "error" && <div className={styles.error} role="alert"><strong>Watchlist API unavailable</strong><span>{resource.message}</span></div>}
      {resource.state === "ready" && rows.length === 0 && <p className={styles.empty}>{resource.rows.length ? "No entries match the current filters." : "Watchlist is empty. No sample assets are inserted."}</p>}
      {resource.state === "ready" && rows.map((item) => <article className={styles.watchItem} key={item.id}>
        <header className={styles.itemHeader}><div><p className={styles.symbolLine}><Link href={`/research/${encodeURIComponent(item.symbol)}`}>{item.symbol}</Link><Status value={item.data_status} /></p><strong>{item.name}</strong><small>{item.sector ?? "Sector unavailable"} / {item.horizon ?? "Horizon not set"}</small></div><div className={styles.actions}><button disabled={busyId === item.id} onClick={() => void perform(item.id, () => reviewWatchlistItem(item.id), "Review date updated.")}>Reviewed</button><button disabled={busyId === item.id} onClick={() => void perform(item.id, () => captureWatchlistSnapshot(item.id), "Evidence snapshot captured.")}>Capture snapshot</button><button className={styles.remove} disabled={busyId === item.id} onClick={() => void perform(item.id, () => deleteWatchlistItem(item.id), "Removed from watchlist.")}>Remove</button></div></header>
        <div className={styles.metrics}><div><span>Opportunity</span><b>{item.opportunity ?? "N/A"}</b></div><div><span>Confidence</span><b>{item.confidence}</b></div><div><span>Risk</span><b>{item.risk ?? "N/A"}</b></div><div><span>Valuation</span><b>{item.valuation?.pe?.value ?? "N/A"}</b></div><div><span>Price freshness</span><b><Status value={item.data_freshness.status} /> {displayDate(item.data_freshness.as_of_date)}</b></div></div>
        <div className={styles.thesisGrid}>
          <div><h3>Luận điểm / Thesis</h3><p>{item.thesis || "Chưa có luận điểm."}</p></div>
          <div><h3>Vì sao lúc này / Why now</h3><p>{item.why_now.length ? item.why_now.map((claim) => String(claim.description ?? claim.text ?? "")).join(" / ") : "INSUFFICIENT_DATA / Chưa có luận cứ tích cực được hỗ trợ."}</p></div>
          <div><h3>Vì sao chưa / Why not now</h3><p>{item.why_not_now.length ? item.why_not_now.map((claim) => String(claim.description ?? claim.text ?? "")).join(" / ") : "Chưa có luận cứ được hỗ trợ."}</p></div>
          <div><h3>Điều kiện vô hiệu / Invalidation</h3><p>{item.invalidation || "Chưa đặt điều kiện vô hiệu."}</p></div>
        </div>
        {item.changes.length > 0 && <div className={styles.changes}><h3>Before / After</h3>{item.changes.map((change, index) => <p key={`${String(change.type)}-${index}`}><Status value={String(change.materiality)} /><b>{String(change.type)}</b> / {String(change.before ?? "N/A")} -&gt; {String(change.after ?? "N/A")} / source {String((change.evidence as Record<string, unknown> | undefined)?.source ?? "unavailable")}</p>)}</div>}
        <DecisionBrief symbol={item.symbol} />
        <details className={styles.editDetails}><summary>Edit thesis / rationale required</summary><form className={styles.editForm} onSubmit={(event) => void editThesis(event, item)}>
          <label>Thesis<textarea name="thesis" defaultValue={item.thesis ?? ""} maxLength={4000} /></label>
          <label>Horizon<select name="horizon" defaultValue={item.horizon ?? ""}><option value="">Not set</option><option value="MEDIUM_TERM">1 to 12 months</option><option value="LONG_TERM">3 to 10 years</option></select></label>
          <label>Invalidation<textarea name="invalidation" defaultValue={item.invalidation ?? ""} maxLength={4000} /></label>
          <label>Reason for change<input name="change_reason" required placeholder="Evidence or reason for the revision" /></label>
          <button disabled={busyId === item.id} type="submit">Save revision</button>
        </form></details>
        <footer>Last reviewed {displayDate(item.last_reviewed_at)} / Last changed {displayDate(item.last_changed_at)} / source {item.data_freshness.source ?? "unavailable"}</footer>
      </article>)}
    </section>
  </div>;
}
