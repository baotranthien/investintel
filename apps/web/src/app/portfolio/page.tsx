"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  applyPortfolioTemplate,
  createManualTransaction,
  createPortfolioHolding,
  createPortfolioSnapshot,
  deletePortfolioHolding,
  getAssets,
  getManualTransactions,
  getPortfolio,
  getPortfolioDca,
  getPortfolioFit,
  getPortfolioSettings,
  getPortfolioTargets,
  getPortfolioTemplates,
  patchPortfolioHolding,
  patchPortfolioSettings,
  putPortfolioDca,
  putPortfolioTargets,
  seedDemoPortfolio,
  type AssetSummary,
  type DcaPlan,
  type PortfolioDashboard,
  type PortfolioFit,
  type PortfolioSettings,
  type PortfolioTargets,
} from "@/lib/api";
import { useLocale, translateQuantEnum, translateSectorName, type AppLocale } from "@/lib/i18n";
import { StatusBadge } from "@/components/ui/status-badge";
import { SkeletonCard } from "@/components/ui/skeleton";
import { PortfolioTorus3D } from "@/components/three/portfolio-torus-3d";
import styles from "./page.module.css";

type Load<T> = { state: "loading" } | { state: "ready"; data: T } | { state: "error"; message: string };

const POPULAR_TICKERS = ["FPT", "VCB", "MWG", "HPG", "ACB", "SSI", "GAS", "VNM"];

function money(value: number | null | undefined, locale: AppLocale = "vi") {
  if (value === null || value === undefined) return "—";
  const localeStr = locale === "en" ? "en-US" : "vi-VN";
  return `${new Intl.NumberFormat(localeStr, { maximumFractionDigits: 0 }).format(value)} VND`;
}

function compactMoney(value: number | null | undefined, locale: AppLocale = "vi"): string | null {
  if (value === null || value === undefined || Math.abs(value) < 1_000_000) return null;
  const absVal = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  const fmt = (n: number) => n.toLocaleString(locale === "en" ? "en-US" : "vi-VN", { maximumFractionDigits: 2 });
  if (absVal >= 1_000_000_000) {
    return `${sign}≈ ${fmt(absVal / 1_000_000_000)} ${locale === "en" ? "B VND" : "tỷ VND"}`;
  }
  return `${sign}≈ ${fmt(absVal / 1_000_000)} ${locale === "en" ? "M VND" : "tr VND"}`;
}

function pct(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : `${(value * 100).toFixed(2)}%`;
}

function dateLabel(value: string | null | undefined, locale: AppLocale = "vi") {
  if (!value) return locale === "en" ? "No date" : "Chưa có ngày";
  return new Date(value).toLocaleDateString(locale === "en" ? "en-US" : "vi-VN");
}

function Status({ value, locale }: { value: string; locale: AppLocale }) {
  const customLabel =
    value === "EMPTY"
      ? (locale === "en" ? "Empty (No holdings)" : "Trống (chưa có vị thế)")
      : value === "INSUFFICIENT_DATA"
      ? (locale === "en" ? "Insufficient data" : "Chưa có dữ liệu")
      : undefined;
  return <StatusBadge status={value} label={customLabel} />;
}

function ErrorState({ message, locale }: { message: string; locale: AppLocale }) {
  return (
    <div className={styles.error} role="alert">
      <strong>{locale === "en" ? "System connection temporarily unavailable" : "Hệ thống tạm thời chưa thể kết nối"}</strong>
      <span>{message}</span>
    </div>
  );
}

const MAX_DATE_LIMIT = new Date(Date.now() + 7 * 3600 * 1000).toISOString().slice(0, 10);
const TODAY_ISO = MAX_DATE_LIMIT;

export default function PortfolioPage() {
  const { locale, t } = useLocale();

  const [dashboard, setDashboard] = useState<Load<PortfolioDashboard>>({ state: "loading" });
  const [, setSettings] = useState<Load<PortfolioSettings>>({ state: "loading" });
  const [targets, setTargets] = useState<Load<PortfolioTargets>>({ state: "loading" });
  const [dca, setDca] = useState<Load<DcaPlan>>({ state: "loading" });
  const [fit, setFit] = useState<Load<PortfolioFit>>({ state: "loading" });
  const [transactions, setTransactions] = useState<Load<Array<Record<string, unknown>>>>({ state: "loading" });
  const [templates, setTemplates] = useState<Array<{ id: string; label: string; note: string }>>([]);
  const [assets, setAssets] = useState<AssetSummary[]>([]);
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
  const holdingSymbolRef = useRef<HTMLInputElement>(null);
  const txSymbolRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const controller = new AbortController();

    getAssets(controller.signal)
      .then((data) => setAssets(Array.isArray(data) ? data : []))
      .catch(() => setAssets([]));

    getPortfolio(controller.signal)
      .then((data) => setDashboard({ state: "ready", data }))
      .catch((e: unknown) => !controller.signal.aborted && setDashboard({ state: "error", message: e instanceof Error ? e.message : "Portfolio API error" }));

    getPortfolioSettings(controller.signal)
      .then((data) => {
        setSettings({ state: "ready", data });
        setSingleLimit(data.single_name_limit === null ? "" : String(data.single_name_limit * 100));
        setSectorLimit(data.sector_limit === null ? "" : String(data.sector_limit * 100));
        setChangeThreshold(data.material_change_threshold === null ? "" : String(data.material_change_threshold * 100));
      })
      .catch((e: unknown) => !controller.signal.aborted && setSettings({ state: "error", message: e instanceof Error ? e.message : "Settings API error" }));

    getPortfolioTargets(controller.signal)
      .then((data) => {
        setTargets({ state: "ready", data });
        setTargetDraft(data.targets);
      })
      .catch((e: unknown) => !controller.signal.aborted && setTargets({ state: "error", message: e instanceof Error ? e.message : "Targets API error" }));

    getPortfolioDca(controller.signal)
      .then((data) => {
        setDca({ state: "ready", data });
        setDcaAmount(data.monthly_amount);
        setCorePct(data.core_pct);
        setSatellitePct(data.satellite_pct);
      })
      .catch((e: unknown) => !controller.signal.aborted && setDca({ state: "error", message: e instanceof Error ? e.message : "DCA API error" }));

    getPortfolioFit(controller.signal)
      .then((data) => setFit({ state: "ready", data }))
      .catch((e: unknown) => !controller.signal.aborted && setFit({ state: "error", message: e instanceof Error ? e.message : "Fit API error" }));

    getManualTransactions(controller.signal)
      .then((data) => setTransactions({ state: "ready", data: data.transactions }))
      .catch((e: unknown) => !controller.signal.aborted && setTransactions({ state: "error", message: e instanceof Error ? e.message : "Transactions API error" }));

    getPortfolioTemplates(controller.signal)
      .then((data) => setTemplates(data.templates ?? []))
      .catch(() => setTemplates([]));

    return () => controller.abort();
  }, [reload]);

  async function mutate(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(success);
      setReload((value) => value + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("Không thể lưu dữ liệu.", "Failed to save data."));
    } finally {
      setBusy(false);
    }
  }

  async function addHolding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = Object.fromEntries(form.entries());
    await mutate(() => createPortfolioHolding(payload), t("Vị thế đã được lưu.", "Holding saved successfully."));
    event.currentTarget.reset();
  }

  async function addTransaction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = Object.fromEntries(form.entries());
    await mutate(
      () => createManualTransaction(payload),
      t("Giao dịch thủ công đã được ghi nhận; vị thế không tự động thay đổi.", "Manual transaction logged; holdings do not change automatically.")
    );
    event.currentTarget.reset();
  }

  async function saveTargets() {
    await mutate(() => putPortfolioTargets(targetDraft), t("Mục tiêu phân bổ đã lưu.", "Target allocation saved."));
  }

  async function saveDca(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await mutate(
      () => putPortfolioDca({ monthly_amount: dcaAmount, core_pct: corePct, satellite_pct: satellitePct }),
      t("Kế hoạch DCA đã lưu.", "DCA plan saved.")
    );
  }

  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const toRatio = (value: string) => (value.trim() === "" ? null : Number(value) / 100);
    await mutate(
      () =>
        patchPortfolioSettings({
          single_name_limit: toRatio(singleLimit),
          sector_limit: toRatio(sectorLimit),
          material_change_threshold: toRatio(changeThreshold),
        }),
      t("Hạn mức danh mục đã lưu.", "Portfolio risk limits saved.")
    );
  }

  async function applyTemplate(id: string) {
    await mutate(
      () => applyPortfolioTemplate(id),
      t("Mẫu danh mục đã áp dụng làm mục tiêu có thể chỉnh sửa.", "Portfolio template applied as editable target allocation.")
    );
  }

  async function seedSamplePortfolio() {
    await mutate(
      () => seedDemoPortfolio(true),
      t(
        "Đã nạp danh mục mẫu VN100 (FPT, VCB, MWG, HPG) từ cơ sở dữ liệu.",
        "Loaded VN100 sample portfolio (FPT, VCB, MWG, HPG) from database."
      )
    );
  }

  const dashboardData = dashboard.state === "ready" ? dashboard.data : null;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>{t("Quản lý danh mục đầu tư", "Portfolio Management")}</h1>
          <p>{t("Theo dõi danh mục thủ công · Không liên kết tài khoản chứng khoán · Không đặt lệnh.", "Manual portfolio tracking · No brokerage connection · No order execution.")}</p>
        </div>
        <div className={styles.headerActions}>
          <button
            className={styles.secondaryButton}
            disabled={busy}
            onClick={() => void seedSamplePortfolio()}
            type="button"
          >
            <span>{t("Nạp danh mục mẫu VN100", "Load Sample VN100 Portfolio")}</span>
          </button>
          <button className={styles.refresh} onClick={() => setReload((value) => value + 1)} type="button">
            ↻ <span>{t("Làm mới", "Refresh")}</span>
          </button>
        </div>
      </header>

      {notice && <p className={styles.notice} role="status">{notice}</p>}
      {error && <ErrorState message={error} locale={locale} />}

      {dashboard.state === "loading" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px", margin: "20px 0" }}>
          <SkeletonCard height={110} />
          <SkeletonCard height={110} />
          <SkeletonCard height={110} />
          <SkeletonCard height={110} />
        </div>
      )}

      {dashboard.state === "error" && <ErrorState message={dashboard.message} locale={locale} />}

      {dashboardData && (
        <>
          <section className={styles.overview}>
            <div>
              <span>{t("Tổng giá trị danh mục", "Total Portfolio Value")}</span>
              <strong>{dashboardData.summary.holdings_count === 0 ? "0 VND" : money(dashboardData.summary.total_value, locale)}</strong>
              {compactMoney(dashboardData.summary.total_value, locale) && (
                <small className={styles.compactSub}>{compactMoney(dashboardData.summary.total_value, locale)}</small>
              )}
              <Status value={dashboardData.summary.holdings_count === 0 ? "EMPTY" : dashboardData.summary.value_status} locale={locale} />
            </div>
            <div>
              <span>{t("Tổng giá vốn đầu tư", "Total Cost Basis")}</span>
              <strong>{money(dashboardData.summary.cost_basis, locale)}</strong>
              {compactMoney(dashboardData.summary.cost_basis, locale) && (
                <small className={styles.compactSub}>{compactMoney(dashboardData.summary.cost_basis, locale)}</small>
              )}
              <small>{dashboardData.summary.holdings_count} {t("vị thế nắm giữ", "holdings")} · {dashboardData.summary.currency}</small>
            </div>
            <div>
              <span>{t("Lãi / lỗ chưa thực hiện", "Unrealized P&L")}</span>
              <div style={{ display: "flex", alignItems: "baseline", gap: "8px", flexWrap: "wrap" }}>
                <strong className={dashboardData.summary.unrealized_pnl !== null && dashboardData.summary.unrealized_pnl >= 0 ? styles.positive : styles.negative}>
                  {dashboardData.summary.holdings_count === 0 ? "0 VND" : money(dashboardData.summary.unrealized_pnl, locale)}
                </strong>
                {dashboardData.summary.cost_basis && dashboardData.summary.unrealized_pnl !== null && dashboardData.summary.cost_basis > 0 && (
                  <span className={dashboardData.summary.unrealized_pnl >= 0 ? "badge-pill-up" : "badge-pill-down"}>
                    {dashboardData.summary.unrealized_pnl >= 0 ? "↗ +" : "↘ "}
                    {pct(dashboardData.summary.unrealized_pnl / dashboardData.summary.cost_basis)}
                  </span>
                )}
              </div>
              <small>{dashboardData.summary.holdings_count === 0 ? t("Chưa có vị thế", "No holdings") : t("Chỉ tính khi mọi holding có giá", "Calculated only when all holdings have prices")}</small>
            </div>
            <div>
              <span>{t("Chất lượng & Rủi ro", "Data & Portfolio Risk")}</span>
              <strong>
                {dashboardData.status === "AVAILABLE"
                  ? t("Sẵn sàng", "Available")
                  : dashboardData.status === "PARTIAL"
                  ? t("Dữ liệu một phần", "Partial Data")
                  : t("Chưa có vị thế", "No Holdings")}
              </strong>
              <small>
                {dashboardData.risk_exposure.status === "AVAILABLE" && dashboardData.risk_exposure.value !== null
                  ? `${t("Rủi ro DM", "Portfolio Risk")}: ${dashboardData.risk_exposure.value}/100 · `
                  : ""}
                {t("Tính đến", "As of")} {dateLabel(dashboardData.as_of_date, locale)}
              </small>
            </div>
          </section>

          <datalist id="vn100-tickers-list">
            {assets.map((asset) => (
              <option key={asset.symbol} value={asset.symbol}>
                {asset.name} ({asset.exchange ?? "HOSE"})
              </option>
            ))}
          </datalist>

          {dashboardData.concentration.warnings
            .filter((w) => !String(w.code).endsWith("_LIMIT_UNSET"))
            .map((warning, index) => {
              const code = String(warning.code);
              let text = String(warning.message ?? t("Cảnh báo danh mục", "Portfolio alert"));
              if (code === "SINGLE_NAME_CONCENTRATION") {
                text = locale === "en"
                  ? `Concentration alert: Stock ${warning.symbol} accounts for ${(Number(warning.weight) * 100).toFixed(1)}% of portfolio (exceeds limit ${(Number(warning.limit) * 100).toFixed(0)}%).`
                  : `Cảnh báo tỷ trọng: Cổ phiếu ${warning.symbol} chiếm ${(Number(warning.weight) * 100).toFixed(1)}% danh mục (vượt hạn mức ${(Number(warning.limit) * 100).toFixed(0)}%).`;
              } else if (code === "SECTOR_CONCENTRATION") {
                text = locale === "en"
                  ? `Sector concentration alert: Sector ${warning.sector} accounts for ${(Number(warning.weight) * 100).toFixed(1)}% of portfolio (exceeds limit ${(Number(warning.limit) * 100).toFixed(0)}%).`
                  : `Cảnh báo tập trung ngành: Ngành ${warning.sector} chiếm ${(Number(warning.weight) * 100).toFixed(1)}% danh mục (vượt hạn mức ${(Number(warning.limit) * 100).toFixed(0)}%).`;
              } else if (code === "MISSING_PRICE") {
                text = t("Một số vị thế chưa có giá thị trường canonical.", "Some holdings lack canonical market prices.");
              } else if (code === "STALE_PRICE") {
                text = t("Dữ liệu giá của một số vị thế đã cũ hơn 7 ngày.", "Price data for some holdings is older than 7 days.");
              }
              return (
                <p className={styles.warning} key={`${code}-${index}`}>
                  ⚠️ {text}
                </p>
              );
            })}

          <section className={styles.section}>
            <header>
              <div>
                <h2>{t("Danh sách cổ phiếu", "Portfolio Holdings")}</h2>
              </div>
              <span>{dashboardData.holdings.length} {t("vị thế", "holdings")}</span>
            </header>
            {dashboardData.holdings.length === 0 ? (
              <div className={styles.empty}>
                <p style={{ margin: 0 }}>
                  {t(
                    "Danh mục hiện chưa có cổ phiếu nào. Nhập thông tin vị thế mua bên dưới hoặc nạp nhanh bộ dữ liệu mẫu VN100 để bắt đầu theo dõi tỷ trọng, lãi/lỗ và rủi ro (ghi nhận thủ công, không đồng bộ tài khoản chứng khoán).",
                    "No holdings in portfolio yet. Enter a position below or load the sample VN100 dataset to begin tracking allocation weights, P&L, and risk exposures (manual entry, no brokerage sync)."
                  )}
                </p>
                <div className={styles.emptyActions}>
                  <button
                    className={styles.primaryButton}
                    disabled={busy}
                    onClick={() => void seedSamplePortfolio()}
                    type="button"
                  >
                    {t("Nạp danh mục mẫu VN100", "Load Sample VN100 Portfolio")}
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className={styles.tableWrap}>
                  <table>
                    <thead>
                      <tr>
                        <th>{t("Mã CP", "Ticker")}</th>
                        <th>{t("Vai trò", "Role")}</th>
                        <th>{t("Khối lượng", "Shares / Qty")}</th>
                        <th>{t("Giá vốn bình quân", "Avg Cost")}</th>
                        <th>{t("Thị giá", "Market Price")}</th>
                        <th>{t("Giá trị thị trường", "Market Value")}</th>
                        <th>{t("Lãi / Lỗ", "Unrealized P&L")}</th>
                        <th>{t("Tỷ trọng", "Weight")}</th>
                        <th>{t("Ngày cập nhật giá", "Price As-Of")}</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboardData.holdings.map((holding) => (
                        <tr key={holding.id}>
                          <td>
                            <Link href={`/research/${encodeURIComponent(holding.symbol)}`} className={styles.tickerLink}>
                              <strong>{holding.symbol}</strong>
                            </Link>
                            <small>{holding.name} · {translateSectorName(holding.sector, locale)}</small>
                          </td>
                          <td>
                            <select
                              aria-label={`${holding.symbol} role`}
                              value={holding.role}
                              disabled={busy}
                              onChange={(event) =>
                                void mutate(
                                  () => patchPortfolioHolding(holding.id, { role: event.target.value }),
                                  t("Đã cập nhật vai trò vị thế.", "Holding role updated.")
                                )
                              }
                            >
                              <option value="UNASSIGNED">{t("Chưa phân loại", "Unassigned")}</option>
                              <option value="CORE">{t("Cốt lõi", "Core")}</option>
                              <option value="SATELLITE">{t("Vệ tinh", "Satellite")}</option>
                            </select>
                          </td>
                          <td>{holding.quantity}</td>
                          <td>{money(holding.average_cost, locale)}</td>
                          <td>
                            {holding.current_price === null ? "—" : money(holding.current_price, locale)} <Status value={holding.price_status} locale={locale} />
                          </td>
                          <td>{money(holding.market_value, locale)}</td>
                          <td className={holding.unrealized_pnl !== null && holding.unrealized_pnl > 0 ? styles.positive : holding.unrealized_pnl !== null && holding.unrealized_pnl < 0 ? styles.negative : undefined}>
                            {money(holding.unrealized_pnl, locale)}
                          </td>
                          <td>{pct(holding.current_weight)}</td>
                          <td>{dateLabel(holding.price_as_of, locale)}</td>
                          <td>
                            <button
                              className={styles.iconButton}
                              title={t(`Xóa ${holding.symbol}`, `Remove ${holding.symbol}`)}
                              aria-label={t(`Xóa ${holding.symbol}`, `Remove ${holding.symbol}`)}
                              onClick={() => void mutate(() => deletePortfolioHolding(holding.id), t(`Đã xóa ${holding.symbol}.`, `Removed ${holding.symbol}.`))}
                            >
                              ×
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className={styles.mobileHoldings}>
                  {dashboardData.holdings.map((holding) => (
                    <article key={holding.id}>
                      <header>
                        <div>
                          <Link href={`/research/${encodeURIComponent(holding.symbol)}`} className={styles.tickerLink}>
                            <strong>{holding.symbol}</strong>
                          </Link>
                          <small>{holding.name}</small>
                        </div>
                        <Status value={holding.price_status} locale={locale} />
                      </header>
                      <div className={styles.mobileGrid}>
                        <span>{t("Vai trò", "Role")} <b>{holding.role === "CORE" ? t("Cốt lõi", "Core") : holding.role === "SATELLITE" ? t("Vệ tinh", "Satellite") : t("Chưa phân loại", "Unassigned")}</b></span>
                        <span>{t("Khối lượng", "Shares")} <b>{holding.quantity}</b></span>
                        <span>{t("Giá vốn", "Avg Cost")} <b>{money(holding.average_cost, locale)}</b></span>
                        <span>{t("Giá trị TT", "Market Value")} <b>{money(holding.market_value, locale)}</b></span>
                        <span>{t("Tỷ trọng", "Weight")} <b>{pct(holding.current_weight)}</b></span>
                        <span>{t("Ngày giá", "Price Date")} <b>{dateLabel(holding.price_as_of, locale)}</b></span>
                      </div>
                      <button onClick={() => void mutate(() => deletePortfolioHolding(holding.id), t(`Đã xóa ${holding.symbol}.`, `Removed ${holding.symbol}.`))}>
                        {t("Xóa vị thế", "Remove Position")}
                      </button>
                    </article>
                  ))}
                </div>
              </>
            )}

            <form className={styles.form} onSubmit={addHolding}>
              <div className={styles.formTopRow}>
                <h3>{t("+ Thêm vị thế mua thủ công", "+ Add Position Manually")}</h3>
                <div className={styles.quickTickers} role="group" aria-label={t("Chọn nhanh mã VN100", "Quick-select VN100 tickers")}>
                  <span>{t("Chọn nhanh:", "Quick pick:")}</span>
                  {POPULAR_TICKERS.map((sym) => (
                    <button
                      key={sym}
                      type="button"
                      className={styles.tickerChip}
                      onClick={() => {
                        if (holdingSymbolRef.current) {
                          holdingSymbolRef.current.value = sym;
                          holdingSymbolRef.current.focus();
                        }
                      }}
                    >
                      {sym}
                    </button>
                  ))}
                </div>
              </div>
              <label>
                {t("Mã cổ phiếu", "Ticker Symbol")}
                <input
                  ref={holdingSymbolRef}
                  name="symbol"
                  list="vn100-tickers-list"
                  required
                  maxLength={20}
                  placeholder={t("VD: FPT, MWG", "e.g. FPT, MWG")}
                />
              </label>
              <label>
                {t("Khối lượng", "Shares / Quantity")}
                <input name="quantity" required type="number" min="0.00000001" step="0.00000001" placeholder={t("VD: 1000", "e.g. 1000")} />
              </label>
              <label>
                {t("Giá vốn bình quân (VND)", "Average Cost (VND)")}
                <input name="average_cost" required type="number" min="0.000001" step="0.000001" placeholder={t("VD: 125000", "e.g. 125000")} />
              </label>
              <label>
                {t("Ngày khớp lệnh", "Acquisition Date")}
                <input name="acquisition_date" required type="date" defaultValue={TODAY_ISO} max={MAX_DATE_LIMIT} />
              </label>
              <label>
                {t("Vai trò danh mục", "Portfolio Role")}
                <select name="role" defaultValue="UNASSIGNED">
                  <option value="UNASSIGNED">{t("Chưa phân loại", "Unassigned")}</option>
                  <option value="CORE">{t("Cốt lõi", "Core")}</option>
                  <option value="SATELLITE">{t("Vệ tinh", "Satellite")}</option>
                </select>
              </label>
              <label>
                {t("Khung thời gian đầu tư", "Investment Horizon")}
                <select name="horizon" defaultValue="">
                  <option value="">{t("Chưa thiết lập", "Not set")}</option>
                  <option value="MEDIUM_TERM">{t("Trung hạn (1–12 tháng)", "Medium-Term (1–12M)")}</option>
                  <option value="LONG_TERM">{t("Dài hạn (3–10 năm)", "Long-Term (3–10Y)")}</option>
                </select>
              </label>
              <label>
                {t("Ghi chú cá nhân", "Personal Notes")}
                <input name="notes" maxLength={2000} placeholder={t("Luận điểm hoặc ghi chú cá nhân...", "Investment thesis or personal notes...")} />
              </label>
              <button disabled={busy} type="submit">{t("+ Thêm vào danh mục", "+ Add to Portfolio")}</button>
            </form>
          </section>

          <div className={styles.twoColumn}>
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <h3>{t("Tỷ trọng hiện tại", "Current Allocation")}</h3>
                <Status value={dashboardData.allocation.status} locale={locale} />
              </div>
              <div className={styles.allocationCardGrid}>
                <div className={styles.allocationTorusWrapper}>
                  <PortfolioTorus3D
                    size={185}
                    data={dashboardData.allocation.sector.length > 0 ? dashboardData.allocation.sector.map((s, idx) => ({
                      id: s.sector,
                      label: s.sector,
                      value: Math.round(s.weight * 100),
                      color: ["#3b82f6", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6", "#06b6d4"][idx % 6],
                    })) : undefined}
                  />
                </div>
                <div className={styles.allocationBarsWrapper}>
                  <h3 style={{ margin: "0 0 4px" }}>{t("Theo nhóm ngành", "By Sector")}</h3>
                  {dashboardData.allocation.sector.length ? (
                    dashboardData.allocation.sector.map((item) => (
                      <div className={styles.barRow} key={item.sector}>
                        <span>{item.sector}</span>
                        <div><i style={{ width: `${Math.max(0, Math.min(100, item.weight * 100))}%` }} /></div>
                        <b>{pct(item.weight)}</b>
                      </div>
                    ))
                  ) : (
                    <p className={styles.empty}>{t("Chưa có vị thế để phân bổ theo ngành.", "No holdings for sector breakdown.")}</p>
                  )}

                  <h3 style={{ margin: "10px 0 4px" }}>{t("Cốt lõi / Vệ tinh", "Core / Satellite")}</h3>
                  {dashboardData.allocation.core_satellite.length ? (
                    dashboardData.allocation.core_satellite.map((item) => (
                      <div className={styles.barRow} key={item.role}>
                        <span>{item.role === "CORE" ? t("Cốt lõi", "Core") : item.role === "SATELLITE" ? t("Vệ tinh", "Satellite") : t("Chưa phân loại", "Unassigned")}</span>
                        <div><i style={{ width: `${Math.max(0, Math.min(100, item.weight * 100))}%` }} /></div>
                        <b>{pct(item.weight)}</b>
                      </div>
                    ))
                  ) : (
                    <p className={styles.empty}>{t("Chưa có dữ liệu phân bổ vai trò.", "No role allocation data available.")}</p>
                  )}
                </div>
              </div>
              <div className={styles.quantExposurePanel}>
                <div className={styles.quantExposureGrid}>
                  <div className={styles.quantMetric}>
                    <span>{t("Rủi ro gia quyền danh mục", "Weighted Portfolio Risk")}</span>
                    <strong>
                      {dashboardData.risk_exposure.value !== null ? `${dashboardData.risk_exposure.value}/100` : translateQuantEnum(dashboardData.risk_exposure.status, locale)}
                    </strong>
                  </div>
                  <div className={styles.quantMetric}>
                    <span>{t("Điểm nhân tố tổng hợp", "Composite Factor Score")}</span>
                    <strong>
                      {dashboardData.factor_exposure.value !== null ? `${dashboardData.factor_exposure.value}/100` : translateQuantEnum(dashboardData.factor_exposure.status, locale)}
                    </strong>
                  </div>
                </div>
                {dashboardData.factor_exposure.profile && Object.keys(dashboardData.factor_exposure.profile).length > 0 && (
                  <div className={styles.factorProfileList}>
                    {Object.entries(dashboardData.factor_exposure.profile).map(([fname, fscore]) => (
                      <div className={styles.barRow} key={fname}>
                        <span style={{ textTransform: "capitalize" }}>{fname}</span>
                        <div><i style={{ width: `${Math.max(0, Math.min(100, Number(fscore)))}%` }} /></div>
                        <b>{Number(fscore).toFixed(1)}</b>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <h3>{t("Đánh giá từng vị thế", "Position Fit Assessment")}</h3>
                {fit.state === "ready" && <Status value={fit.data.status} locale={locale} />}
              </div>
              {fit.state === "loading" && <p className={styles.state}>{t("Đang tính toán mức độ phù hợp…", "Evaluating strategic fit…")}</p>}
              {fit.state === "error" && <ErrorState message={fit.message} locale={locale} />}
              {fit.state === "ready" && fit.data.items.length === 0 && (
                <p className={styles.empty}>{t("Thêm vị thế vào danh mục để hệ thống đánh giá mức độ phù hợp.", "Add holdings to your portfolio to evaluate strategic fit.")}</p>
              )}
              {fit.state === "ready" &&
                fit.data.items.map((item) => (
                  <div className={styles.fitRow} key={item.symbol}>
                    <header className={styles.fitHeader}>
                      <Link href={`/research/${encodeURIComponent(item.symbol)}`} className={styles.tickerLink}>
                        <strong>{item.symbol}</strong>
                      </Link>
                      <Status value={item.status} locale={locale} />
                    </header>
                    <p>
                      {t("Vai trò", "Role")} {item.portfolio_role === "CORE" ? t("Cốt lõi", "Core") : item.portfolio_role === "SATELLITE" ? t("Vệ tinh", "Satellite") : t("Chưa phân loại", "Unassigned")} · {t("Hiện tại", "Current")} {pct(item.current_weight)} · {t("Mục tiêu", "Target")} {pct(item.target_weight)}
                    </p>
                    <p>
                      {t("Cơ hội", "Opportunity")} {item.opportunity_score ?? "—"} · {t("Độ tin cậy", "Confidence")} {translateQuantEnum(item.confidence, locale)} · {t("Rủi ro", "Risk")} {item.risk_score ?? "—"}
                    </p>
                    <div className={styles.fitBadges}>
                      <span className={styles.fitTag}>{t("Rủi ro vị thế", "Risk")}: {translateQuantEnum(item.risk_overlap, locale)}</span>
                      <span className={styles.fitTag}>{t("Phân tán ngành", "Concentration")}: {translateQuantEnum(item.factor_overlap, locale)}</span>
                      <span className={styles.fitTag}>{t("Khung T/G", "Horizon")}: {translateQuantEnum(item.horizon_compatibility, locale)}</span>
                    </div>
                    <small>{item.note}</small>
                  </div>
                ))}
            </div>
          </div>

          <div className={styles.twoColumn}>
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <h3>{t("Mục tiêu & hạn mức", "Target Allocation & Limits")}</h3>
                {targets.state === "ready" && <Status value={targets.data.status} locale={locale} />}
              </div>
              {targets.state === "error" && <ErrorState message={targets.message} locale={locale} />}
              {targets.state === "ready" && (
                <>
                  {targetDraft.map((target, index) => (
                    <div className={styles.targetRow} key={`${target.symbol}-${index}`}>
                      <input
                        aria-label={t(`Mã mục tiêu ${index + 1}`, `Target symbol ${index + 1}`)}
                        list="vn100-tickers-list"
                        value={target.symbol}
                        placeholder={t("Mã CK", "Ticker")}
                        onChange={(event) =>
                          setTargetDraft((rows) =>
                            rows.map((row, rowIndex) => (rowIndex === index ? { ...row, symbol: event.target.value.toUpperCase() } : row))
                          )
                        }
                      />
                      <input
                        aria-label={t(`Tỷ trọng mục tiêu ${index + 1}`, `Target weight ${index + 1}`)}
                        type="number"
                        min="0"
                        max="100"
                        step="0.01"
                        value={(target.target_weight * 100).toFixed(2)}
                        onChange={(event) =>
                          setTargetDraft((rows) =>
                            rows.map((row, rowIndex) => (rowIndex === index ? { ...row, target_weight: Number(event.target.value) / 100 } : row))
                          )
                        }
                      />
                      <span>%</span>
                      <button
                        className={styles.iconButton}
                        aria-label={t(`Xóa mục tiêu ${target.symbol}`, `Remove target ${target.symbol}`)}
                        onClick={() => setTargetDraft((rows) => rows.filter((_, rowIndex) => rowIndex !== index))}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                  <button className={styles.secondaryButton} onClick={() => setTargetDraft((rows) => [...rows, { symbol: "", target_weight: 0 }])}>
                    {t("+ Thêm mục tiêu", "+ Add Target")}
                  </button>
                  <div className={styles.buttonRow}>
                    <button disabled={busy} onClick={() => void saveTargets()}>
                      {t("Lưu mục tiêu phân bổ", "Save Target Allocation")}
                    </button>
                    {templates.map((template) => {
                      const localizedLabel = template.label.includes(" / ")
                        ? locale === "en"
                          ? template.label.split(" / ")[0]
                          : template.label.split(" / ")[1]
                        : template.label;
                      return (
                        <button
                          className={styles.secondaryButton}
                          disabled={busy}
                          key={template.id}
                          title={template.note}
                          onClick={() => void applyTemplate(template.id)}
                        >
                          {localizedLabel}
                        </button>
                      );
                    })}
                  </div>
                </>
              )}

              <form className={styles.thresholdForm} onSubmit={saveSettings}>
                <h3>{t("Hạn mức cảnh báo rủi ro cá nhân", "Personal Risk Limits & Thresholds")}</h3>
                <label>
                  {t("Hạn mức tối đa 1 cổ phiếu (%)", "Single-Stock Limit (%)")}
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    value={singleLimit}
                    onChange={(event) => setSingleLimit(event.target.value)}
                    placeholder={t("Chưa cấu hình (VD: 25)", "Not set (e.g. 25)")}
                  />
                </label>
                <label>
                  {t("Hạn mức tối đa 1 ngành (%)", "Sector Limit (%)")}
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    value={sectorLimit}
                    onChange={(event) => setSectorLimit(event.target.value)}
                    placeholder={t("Chưa cấu hình (VD: 40)", "Not set (e.g. 40)")}
                  />
                </label>
                <label>
                  {t("Ngưỡng cảnh báo biến động (%)", "Material Change Alert Threshold (%)")}
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    value={changeThreshold}
                    onChange={(event) => setChangeThreshold(event.target.value)}
                    placeholder={t("Chưa cấu hình (VD: 10)", "Not set (e.g. 10)")}
                  />
                </label>
                <button disabled={busy} type="submit">{t("Lưu cấu hình hạn mức", "Save Risk Limits")}</button>
              </form>
            </div>

            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <h3>{t("Kế hoạch tích lũy hàng tháng (DCA)", "Monthly DCA Accumulation Plan")}</h3>
                {dca.state === "ready" && <Status value={dca.data.status} locale={locale} />}
              </div>
              {dca.state === "error" && <ErrorState message={dca.message} locale={locale} />}
              <form className={styles.dcaForm} onSubmit={saveDca}>
                <label>
                  {t("Số tiền tích lũy hàng tháng (VND)", "Monthly Accumulation Amount (VND)")}
                  <input type="number" min="100000" step="50000" value={dcaAmount} onChange={(event) => setDcaAmount(Number(event.target.value))} required />
                </label>
                <label>
                  {t("Tỷ trọng cốt lõi (%)", "Core Target Weight (%)")}
                  <input type="number" min="0" max="100" step="1" value={Math.round(corePct * 100)} onChange={(event) => setCorePct(Number(event.target.value) / 100)} required />
                </label>
                <label>
                  {t("Tỷ trọng vệ tinh (%)", "Satellite Target Weight (%)")}
                  <input type="number" min="0" max="100" step="1" value={Math.round(satellitePct * 100)} onChange={(event) => setSatellitePct(Number(event.target.value) / 100)} required />
                </label>
                <button disabled={busy} type="submit">{t("Lưu kế hoạch DCA", "Save DCA Plan")}</button>
              </form>
              {dca.state === "ready" && (
                <div className={styles.dcaResult}>
                  <p>
                    {t("Cốt lõi", "Core")}: {pct(dca.data.core_pct)} · {t("Vệ tinh", "Satellite")}: {pct(dca.data.satellite_pct)} · {t("Dự phòng", "Reserve")}: {pct(dca.data.reserve_pct)}
                  </p>
                  <strong>{t("Chưa phân bổ / Dự phòng", "Unallocated / Reserve")}: {money(dca.data.unused_or_satellite_reserve, locale)}</strong>
                  {dca.data.routes.map((route) => (
                    <p key={route.symbol}>
                      {route.symbol} · {money(route.amount, locale)} · {t("mục tiêu", "target")} {pct(route.target_weight)} · {translateQuantEnum(route.status, locale)}
                    </p>
                  ))}
                  <small>{dca.data.note}</small>
                </div>
              )}
              {dca.state === "error" && (
                <p className={styles.sectionNote}>
                  {t("Số tiền ban đầu là cấu hình mẫu; hãy bấm Lưu để ghi nhận vĩnh viễn.", "Initial amount is a template preset; click Save to persist your plan.")}
                </p>
              )}
              <button
                className={`${styles.secondaryButton} ${styles.dcaFooterBtn}`}
                disabled={busy}
                onClick={() => void mutate(() => createPortfolioSnapshot(), t("Đã lưu snapshot phân bổ danh mục.", "Portfolio allocation snapshot saved."))}
              >
                {t("Lưu mốc quan sát phân bổ (Snapshot)", "Save Allocation Snapshot")}
              </button>
            </div>
          </div>

          <section className={styles.section}>
            <header>
              <div>
                <h2>{t("Lịch sử giao dịch", "Transaction History")}</h2>
              </div>
              <span>{t("Ghi nhận thủ công · Không đồng bộ tài khoản chứng khoán", "Manual recording · No brokerage synchronization")}</span>
            </header>
            <form className={styles.form} onSubmit={addTransaction}>
              <label>
                {t("Mã cổ phiếu", "Ticker Symbol")}
                <input ref={txSymbolRef} name="symbol" list="vn100-tickers-list" required placeholder={t("VD: FPT", "e.g. FPT")} />
              </label>
              <label>
                {t("Loại giao dịch", "Transaction Type")}
                <select name="transaction_type">
                  <option value="BUY">{t("Mua", "Buy")}</option>
                  <option value="SELL">{t("Bán", "Sell")}</option>
                  <option value="DIVIDEND">{t("Cổ tức", "Dividend")}</option>
                  <option value="FEE">{t("Phí", "Fee")}</option>
                </select>
              </label>
              <label>
                {t("Khối lượng", "Shares / Quantity")}
                <input name="quantity" required type="number" min="0.00000001" step="0.00000001" placeholder={t("VD: 500", "e.g. 500")} />
              </label>
              <label>
                {t("Đơn giá (VND)", "Unit Price (VND)")}
                <input name="unit_price" required type="number" min="0.000001" step="0.000001" placeholder={t("VD: 130000", "e.g. 130000")} />
              </label>
              <label>
                {t("Ngày giao dịch", "Transaction Date")}
                <input name="transaction_date" required type="date" defaultValue={TODAY_ISO} max={MAX_DATE_LIMIT} />
              </label>
              <label className={styles.notesField}>
                {t("Ghi chú", "Notes")}
                <input name="notes" placeholder={t("Ghi chú giao dịch...", "Transaction notes...")} />
              </label>
              <button disabled={busy} type="submit">{t("+ Ghi nhận giao dịch", "+ Log Transaction")}</button>
            </form>
            {transactions.state === "error" && <ErrorState message={transactions.message} locale={locale} />}
            {transactions.state === "ready" && transactions.data.length === 0 && (
              <p className={styles.empty}>{t("Chưa có giao dịch thủ công nào được ghi nhận.", "No manual transactions recorded yet.")}</p>
            )}
            {transactions.state === "ready" &&
              transactions.data.map((transaction, index) => {
                const txType = String(transaction.transaction_type);
                const txTypeLabel =
                  txType === "BUY"
                    ? t("Mua", "Buy")
                    : txType === "SELL"
                    ? t("Bán", "Sell")
                    : txType === "DIVIDEND"
                    ? t("Cổ tức", "Dividend")
                    : txType === "FEE"
                    ? t("Phí", "Fee")
                    : txType;
                return (
                  <p className={styles.transactionRow} key={String(transaction.id ?? index)}>
                    {String(transaction.transaction_date)} · {String(transaction.symbol)} · {txTypeLabel} · {t("KL", "Qty")}:{" "}
                    {Number(transaction.quantity).toLocaleString(locale === "en" ? "en-US" : "vi-VN")} {t("CP", "shares")} · {t("Đơn giá", "Price")}:{" "}
                    {money(Number(transaction.unit_price), locale)} · {t("THỦ CÔNG", "MANUAL")}
                  </p>
                );
              })}
          </section>
        </>
      )}
    </div>
  );
}
