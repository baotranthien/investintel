"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  applyPortfolioTemplate,
  createManualTransaction,
  createPortfolioHolding,
  createPortfolioSnapshot,
  deletePortfolioHolding,
  getManualTransactions,
  getPortfolio,
  getPortfolioDca,
  getPortfolioFit,
  getPortfolioSettings,
  getPortfolioTargets,
  patchPortfolioHolding,
  patchPortfolioSettings,
  putPortfolioDca,
  putPortfolioTargets,
  type DcaPlan,
  type PortfolioDashboard,
  type PortfolioFit,
  type PortfolioSettings,
  type PortfolioTargets,
} from "@/lib/api";
import styles from "./page.module.css";

type Load<T> = { state: "loading" } | { state: "ready"; data: T } | { state: "error"; message: string };

function money(value: number | null | undefined) {
  return value === null || value === undefined ? "â€”" : `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(value)} VND`;
}
function pct(value: number | null | undefined) {
  return value === null || value === undefined ? "â€”" : `${(value * 100).toFixed(2)}%`;
}
function dateLabel(value: string | null | undefined) {
  if (!value) return "No date";
  return new Date(value).toLocaleDateString("vi-VN");
}
function Status({ value }: { value: string }) {
  return <span className={`${styles.status} ${value === "AVAILABLE" ? styles.ok : value === "STALE" ? styles.warn : styles.missing}`}>{value.replaceAll("_", " ")}</span>;
}
function ErrorState({ message }: { message: string }) {
  return <div className={styles.error} role="alert"><strong>API khÃ´ng kháº£ dá»¥ng</strong><span>{message}</span></div>;
}

export default function PortfolioPage() {
  const [dashboard, setDashboard] = useState<Load<PortfolioDashboard>>({ state: "loading" });
  const [settings, setSettings] = useState<Load<PortfolioSettings>>({ state: "loading" });
  const [targets, setTargets] = useState<Load<PortfolioTargets>>({ state: "loading" });
  const [dca, setDca] = useState<Load<DcaPlan>>({ state: "loading" });
  const [fit, setFit] = useState<Load<PortfolioFit>>({ state: "loading" });
  const [transactions, setTransactions] = useState<Load<Array<Record<string, unknown>>>>({ state: "loading" });
  const [templates, setTemplates] = useState<Array<{ id: string; label: string; note: string }>>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [targetDraft, setTargetDraft] = useState<Array<{ symbol: string; target_weight: number }>>([]);
  const [dcaAmount, setDcaAmount] = useState(350000);
  const [corePct, setCorePct] = useState(0.75);
  const [satellitePct, setSatellitePct] = useState(0.25);
  const [singleLimit, setSingleLimit] = useState("");
  const [sectorLimit, setSectorLimit] = useState("");
  const [changeThreshold, setChangeThreshold] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    getPortfolio(controller.signal).then((data) => setDashboard({ state: "ready", data })).catch((e: unknown) => !controller.signal.aborted && setDashboard({ state: "error", message: e instanceof Error ? e.message : "Portfolio API error" }));
    getPortfolioSettings(controller.signal).then((data) => {
      setSettings({ state: "ready", data });
      setSingleLimit(data.single_name_limit === null ? "" : String(data.single_name_limit * 100));
      setSectorLimit(data.sector_limit === null ? "" : String(data.sector_limit * 100));
      setChangeThreshold(data.material_change_threshold === null ? "" : String(data.material_change_threshold * 100));
    }).catch((e: unknown) => !controller.signal.aborted && setSettings({ state: "error", message: e instanceof Error ? e.message : "Settings API error" }));
    getPortfolioTargets(controller.signal).then((data) => {
      setTargets({ state: "ready", data });
      setTargetDraft(data.targets);
    }).catch((e: unknown) => !controller.signal.aborted && setTargets({ state: "error", message: e instanceof Error ? e.message : "Targets API error" }));
    getPortfolioDca(controller.signal).then((data) => {
      setDca({ state: "ready", data });
      setDcaAmount(data.monthly_amount);
      setCorePct(data.core_pct);
      setSatellitePct(data.satellite_pct);
    }).catch((e: unknown) => !controller.signal.aborted && setDca({ state: "error", message: e instanceof Error ? e.message : "DCA API error" }));
    getPortfolioFit(controller.signal).then((data) => setFit({ state: "ready", data })).catch((e: unknown) => !controller.signal.aborted && setFit({ state: "error", message: e instanceof Error ? e.message : "Fit API error" }));
    getManualTransactions(controller.signal).then((data) => setTransactions({ state: "ready", data: data.transactions })).catch((e: unknown) => !controller.signal.aborted && setTransactions({ state: "error", message: e instanceof Error ? e.message : "Transactions API error" }));
    fetch("/api/v1/portfolio/templates", { cache: "no-store", signal: controller.signal }).then((response) => response.ok ? response.json() : Promise.reject(new Error("Template API error"))).then((data) => setTemplates(data.templates ?? [])).catch(() => setTemplates([]));
    return () => controller.abort();
  }, [reload]);

  async function mutate(action: () => Promise<unknown>, success: string) {
    setBusy(true); setError(""); setNotice("");
    try { await action(); setNotice(success); setReload((value) => value + 1); }
    catch (e) { setError(e instanceof Error ? e.message : "KhÃ´ng thá»ƒ lÆ°u dá»¯ liá»‡u."); }
    finally { setBusy(false); }
  }

  async function addHolding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = Object.fromEntries(form.entries());
    await mutate(() => createPortfolioHolding(payload), "Holding Ä‘Ã£ Ä‘Æ°á»£c lÆ°u.");
    event.currentTarget.reset();
  }

  async function addTransaction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = Object.fromEntries(form.entries());
    await mutate(() => createManualTransaction(payload), "Manual transaction record Ä‘Ã£ Ä‘Æ°á»£c lÆ°u; holdings khÃ´ng tá»± thay Ä‘á»•i.");
    event.currentTarget.reset();
  }

  async function saveTargets() {
    await mutate(() => putPortfolioTargets(targetDraft), "Target allocation Ä‘Ã£ lÆ°u.");
  }

  async function saveDca(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await mutate(() => putPortfolioDca({ monthly_amount: dcaAmount, core_pct: corePct, satellite_pct: satellitePct }), "DCA plan Ä‘Ã£ lÆ°u.");
  }

  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const toRatio = (value: string) => value.trim() === "" ? null : Number(value) / 100;
    await mutate(() => patchPortfolioSettings({
      single_name_limit: toRatio(singleLimit),
      sector_limit: toRatio(sectorLimit),
      material_change_threshold: toRatio(changeThreshold),
    }), "Portfolio thresholds Ä‘Ã£ lÆ°u.");
  }

  async function applyTemplate(id: string) {
    await mutate(() => applyPortfolioTemplate(id), "Personal template Ä‘Ã£ Ã¡p dá»¥ng lÃ m target cÃ³ thá»ƒ chá»‰nh sá»­a.");
  }

  const dashboardData = dashboard.state === "ready" ? dashboard.data : null;
  return <div className={styles.page}>
    <header className={styles.header}>
      <div><p className={styles.eyebrow}>PHASE 6D Â· LOCAL PERSONAL WORKSPACE</p><h1>Danh má»¥c <span>/ Portfolio</span></h1><p>Manual tracking only Â· khÃ´ng broker Â· khÃ´ng Ä‘áº·t lá»‡nh.</p></div>
      <button className={styles.refresh} onClick={() => setReload((value) => value + 1)} type="button">â†» <span>LÃ m má»›i</span></button>
    </header>
    {notice && <p className={styles.notice} role="status">{notice}</p>}{error && <ErrorState message={error} />}
    {dashboard.state === "loading" && <p className={styles.state} role="status">Äang táº£i portfolio tá»« APIâ€¦</p>}
    {dashboard.state === "error" && <ErrorState message={dashboard.message} />}
    {dashboardData && <>
      <section className={styles.overview}>
        <div><span>Total value / Tá»•ng giÃ¡ trá»‹</span><strong>{money(dashboardData.summary.total_value)}</strong><Status value={dashboardData.summary.value_status} /></div>
        <div><span>Cost basis / GiÃ¡ vá»‘n</span><strong>{money(dashboardData.summary.cost_basis)}</strong><small>{dashboardData.summary.holdings_count} holdings Â· {dashboardData.summary.currency}</small></div>
        <div><span>Unrealized P/L</span><strong className={dashboardData.summary.unrealized_pnl !== null && dashboardData.summary.unrealized_pnl >= 0 ? styles.positive : styles.negative}>{money(dashboardData.summary.unrealized_pnl)}</strong><small>Chá»‰ tÃ­nh khi má»i holding cÃ³ price</small></div>
        <div><span>Data quality</span><strong>{dashboardData.status}</strong><small>As of {dateLabel(dashboardData.as_of_date)}</small></div>
      </section>
      {dashboardData.concentration.warnings.map((warning, index) => <p className={styles.warning} key={`${String(warning.code)}-${index}`}>{String(warning.code).replaceAll("_", " ")} Â· {String(warning.message ?? warning.symbol ?? warning.sector ?? "Threshold warning")}</p>)}

      <section className={styles.section}>
        <header><div><p className={styles.eyebrow}>POSITIONS</p><h2>Holdings</h2></div><span>{dashboardData.holdings.length} entries</span></header>
        {dashboardData.holdings.length === 0 ? <p className={styles.empty}>ChÆ°a cÃ³ holding. ThÃªm vá»‹ tháº¿ Ä‘Ã£ nháº­p thá»§ cÃ´ng; khÃ´ng Ä‘á»“ng bá»™ broker.</p> : <>
          <div className={styles.tableWrap}><table><thead><tr><th>Asset</th><th>Role</th><th>Quantity</th><th>Avg cost</th><th>Price</th><th>Value</th><th>P/L</th><th>Weight</th><th>Price date</th><th></th></tr></thead><tbody>{dashboardData.holdings.map((holding) => <tr key={holding.id}>
            <td><strong>{holding.symbol}</strong><small>{holding.name} Â· {holding.sector ?? "Sector n/a"}</small></td>
            <td><select aria-label={`${holding.symbol} role`} value={holding.role} disabled={busy} onChange={(event) => void mutate(() => patchPortfolioHolding(holding.id, { role: event.target.value }), "Portfolio role updated.")}><option value="UNASSIGNED">Unassigned</option><option value="CORE">Core</option><option value="SATELLITE">Satellite</option></select></td>
            <td>{holding.quantity}</td><td>{money(holding.average_cost)}</td><td>{holding.current_price === null ? "â€”" : money(holding.current_price)} <Status value={holding.price_status} /></td>
            <td>{money(holding.market_value)}</td><td>{money(holding.unrealized_pnl)}</td><td>{pct(holding.current_weight)}</td><td>{dateLabel(holding.price_as_of)}</td>
            <td><button className={styles.iconButton} title={`Remove ${holding.symbol}`} aria-label={`Remove ${holding.symbol}`} onClick={() => void mutate(() => deletePortfolioHolding(holding.id), `${holding.symbol} removed.`)}>Ã—</button></td>
          </tr>)}</tbody></table></div>
          <div className={styles.mobileHoldings}>{dashboardData.holdings.map((holding) => <article key={holding.id}><header><div><strong>{holding.symbol}</strong><small>{holding.name}</small></div><Status value={holding.price_status} /></header><div className={styles.mobileGrid}><span>Role <b>{holding.role}</b></span><span>Quantity <b>{holding.quantity}</b></span><span>Avg cost <b>{money(holding.average_cost)}</b></span><span>Current value <b>{money(holding.market_value)}</b></span><span>Weight <b>{pct(holding.current_weight)}</b></span><span>Price date <b>{dateLabel(holding.price_as_of)}</b></span></div><button onClick={() => void mutate(() => deletePortfolioHolding(holding.id), `${holding.symbol} removed.`)}>Remove position</button></article>)}</div>
        </>}
        <form className={styles.form} onSubmit={addHolding}>
          <h3>Add manual holding</h3>
          <label>Symbol<input name="symbol" required maxLength={20} placeholder="e.g. FPT" /></label>
          <label>Quantity<input name="quantity" required type="number" min="0.00000001" step="0.00000001" /></label>
          <label>Average cost (VND)<input name="average_cost" required type="number" min="0.000001" step="0.000001" /></label>
          <label>Acquisition date<input name="acquisition_date" required type="date" max={new Date().toISOString().slice(0, 10)} /></label>
          <label>Role<select name="role" defaultValue="UNASSIGNED"><option value="UNASSIGNED">Unassigned</option><option value="CORE">Core</option><option value="SATELLITE">Satellite</option></select></label>
          <label>Horizon<select name="horizon" defaultValue=""><option value="">Not set</option><option value="MEDIUM_TERM">1â€“12 months</option><option value="LONG_TERM">3â€“10 years</option></select></label>
          <label className={styles.notesField}>Notes<input name="notes" maxLength={2000} /></label>
          <button disabled={busy} type="submit">Add holding</button>
        </form>
      </section>

      <div className={styles.twoColumn}>
        <section className={styles.section}>
          <header><div><p className={styles.eyebrow}>ALLOCATION</p><h2>Current mix</h2></div><Status value={dashboardData.allocation.status} /></header>
          <h3>By sector</h3>
          {dashboardData.allocation.sector.length ? dashboardData.allocation.sector.map((item) => <div className={styles.barRow} key={item.sector}><span>{item.sector}</span><div><i style={{ width: `${Math.max(0, Math.min(100, item.weight * 100))}%` }} /></div><b>{pct(item.weight)}</b></div>) : <p className={styles.empty}>Sector weights unavailable until all holding prices are known.</p>}
          <h3>Core / Satellite / Unassigned</h3>
          {dashboardData.allocation.core_satellite.length ? dashboardData.allocation.core_satellite.map((item) => <div className={styles.barRow} key={item.role}><span>{item.role}</span><div><i style={{ width: `${Math.max(0, Math.min(100, item.weight * 100))}%` }} /></div><b>{pct(item.weight)}</b></div>) : <p className={styles.empty}>No normalized role mix available.</p>}
          <p className={styles.sectionNote}>Risk/factor exposures: {dashboardData.risk_exposure.status} Â· {dashboardData.factor_exposure.status}. No proxy scores are substituted.</p>
        </section>

        <section className={styles.section}>
          <header><div><p className={styles.eyebrow}>PORTFOLIO FIT</p><h2>Fit by holding</h2></div>{fit.state === "ready" && <Status value={fit.data.status} />}</header>
          {fit.state === "loading" && <p className={styles.state}>Loading fitâ€¦</p>}{fit.state === "error" && <ErrorState message={fit.message} />}
          {fit.state === "ready" && fit.data.items.length === 0 && <p className={styles.empty}>Add a holding to evaluate its portfolio fit.</p>}
          {fit.state === "ready" && fit.data.items.map((item) => <article className={styles.fitRow} key={item.symbol}><header><strong>{item.symbol}</strong><Status value={item.status} /></header><p>Role {item.portfolio_role} Â· current {pct(item.current_weight)} Â· target {pct(item.target_weight)}</p><p>Opportunity {item.opportunity_score ?? "â€”"} Â· Confidence {item.confidence} Â· Risk {item.risk_score ?? "â€”"}</p><small>{item.note}</small></article>)}
        </section>
      </div>

      <div className={styles.twoColumn}>
        <section className={styles.section}>
          <header><div><p className={styles.eyebrow}>TARGET ALLOCATION</p><h2>Targets & concentration</h2></div>{targets.state === "ready" && <Status value={targets.data.status} />}</header>
          {targets.state === "error" && <ErrorState message={targets.message} />}
          {targets.state === "ready" && <>
            {targetDraft.map((target, index) => <div className={styles.targetRow} key={`${target.symbol}-${index}`}><input aria-label={`Target symbol ${index + 1}`} value={target.symbol} onChange={(event) => setTargetDraft((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, symbol: event.target.value.toUpperCase() } : row))} /><input aria-label={`Target weight ${index + 1}`} type="number" min="0" max="100" step="0.01" value={(target.target_weight * 100).toFixed(2)} onChange={(event) => setTargetDraft((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, target_weight: Number(event.target.value) / 100 } : row))} /><span>%</span><button className={styles.iconButton} aria-label={`Remove target ${target.symbol}`} onClick={() => setTargetDraft((rows) => rows.filter((_, rowIndex) => rowIndex !== index))}>Ã—</button></div>)}
            <button className={styles.secondaryButton} onClick={() => setTargetDraft((rows) => [...rows, { symbol: "", target_weight: 0 }])}>Add target</button>
            <div className={styles.buttonRow}><button disabled={busy} onClick={() => void saveTargets()}>Save targets</button>{templates.map((template) => <button className={styles.secondaryButton} disabled={busy} key={template.id} title={template.note} onClick={() => void applyTemplate(template.id)}>{template.label}</button>)}</div>
          </>}
          <form className={styles.thresholdForm} onSubmit={saveSettings}>
            <h3>Personal thresholds Â· unset means no warning classification</h3>
            <label>Single-name limit %<input type="number" min="0" max="100" step="0.1" value={singleLimit} onChange={(event) => setSingleLimit(event.target.value)} placeholder="Not configured" /></label>
            <label>Sector limit %<input type="number" min="0" max="100" step="0.1" value={sectorLimit} onChange={(event) => setSectorLimit(event.target.value)} placeholder="Not configured" /></label>
            <label>Material-change threshold %<input type="number" min="0" max="100" step="0.1" value={changeThreshold} onChange={(event) => setChangeThreshold(event.target.value)} placeholder="Not configured" /></label>
            <button disabled={busy} type="submit">Save thresholds</button>
          </form>
        </section>

        <section className={styles.section}>
          <header><div><p className={styles.eyebrow}>MONTHLY CONTRIBUTION</p><h2>Personal DCA</h2></div>{dca.state === "ready" && <Status value={dca.data.status} />}</header>
          {dca.state === "error" && <ErrorState message={dca.message} />}
          <form className={styles.dcaForm} onSubmit={saveDca}>
            <label>Monthly amount (VND)<input type="number" min="300000" max="400000" step="10000" value={dcaAmount} onChange={(event) => setDcaAmount(Number(event.target.value))} required /></label>
            <label>Core portion %<input type="number" min="0" max="100" step="1" value={Math.round(corePct * 100)} onChange={(event) => setCorePct(Number(event.target.value) / 100)} required /></label>
            <label>Satellite portion %<input type="number" min="0" max="100" step="1" value={Math.round(satellitePct * 100)} onChange={(event) => setSatellitePct(Number(event.target.value) / 100)} required /></label>
            <button disabled={busy} type="submit">Save DCA plan</button>
          </form>
          {dca.state === "ready" && <div className={styles.dcaResult}><p>Core {pct(dca.data.core_pct)} Â· Satellite {pct(dca.data.satellite_pct)} Â· Reserve {pct(dca.data.reserve_pct)}</p><strong>Unused / reserve Â· {money(dca.data.unused_or_satellite_reserve)}</strong>{dca.data.routes.map((route) => <p key={route.symbol}>{route.symbol} Â· {money(route.amount)} Â· target {pct(route.target_weight)} Â· {route.status}</p>)}<small>{dca.data.note}</small></div>}
          {dca.state === "error" && <p className={styles.sectionNote}>The displayed initial amount is a personal editable demo setting; save it to persist.</p>}
          <button className={styles.secondaryButton} disabled={busy} onClick={() => void mutate(() => createPortfolioSnapshot(), "Portfolio snapshot captured.")}>Capture allocation snapshot</button>
        </section>
      </div>

      <section className={styles.section}>
        <header><div><p className={styles.eyebrow}>MANUAL LEDGER</p><h2>Transaction records</h2></div><span>No broker synchronization</span></header>
        <form className={styles.form} onSubmit={addTransaction}>
          <label>Symbol<input name="symbol" required /></label><label>Type<select name="transaction_type"><option>BUY</option><option>SELL</option><option>DIVIDEND</option><option>FEE</option></select></label>
          <label>Quantity<input name="quantity" required type="number" min="0.00000001" step="0.00000001" /></label><label>Unit price (VND)<input name="unit_price" required type="number" min="0.000001" step="0.000001" /></label>
          <label>Date<input name="transaction_date" required type="date" max={new Date().toISOString().slice(0, 10)} /></label><label>Notes<input name="notes" /></label><button disabled={busy} type="submit">Record manually</button>
        </form>
        {transactions.state === "error" && <ErrorState message={transactions.message} />}
        {transactions.state === "ready" && transactions.data.length === 0 && <p className={styles.empty}>No manual transaction records.</p>}
        {transactions.state === "ready" && transactions.data.map((transaction, index) => <p className={styles.transactionRow} key={String(transaction.id ?? index)}>{String(transaction.transaction_date)} Â· {String(transaction.symbol)} Â· {String(transaction.transaction_type)} Â· {money(Number(transaction.unit_price))} Â· MANUAL</p>)}
      </section>
    </>}
  </div>;
}
