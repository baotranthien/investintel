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
  getWatchlistAvailableAssets,
  reviewWatchlistItem,
  patchWatchlistItem,
  type DecisionContext,
  type WatchlistItem,
  type WatchlistAvailableAsset,
} from "@/lib/api";
import { useLocale, translateQuantEnum, translateSectorName, translateResearchCopy, type AppLocale } from "@/lib/i18n";
import { StatusBadge } from "@/components/ui/status-badge";
import { SkeletonCard } from "@/components/ui/skeleton";
import styles from "./page.module.css";

type Resource = { state: "loading" } | { state: "ready"; rows: WatchlistItem[] } | { state: "error"; message: string };
type DecisionResource = { state: "idle" | "loading" } | { state: "ready"; data: DecisionContext } | { state: "error"; message: string };

function displayDate(value: string | null, locale: AppLocale = "vi") {
  return value ? new Date(value).toLocaleDateString(locale === "en" ? "en-US" : "vi-VN") : "N/A";
}

function Status({ value }: { value: string }) {
  return <StatusBadge status={value} />;
}

function present(value: unknown, locale: AppLocale = "vi") {
  if (value === null || value === undefined) return locale === "en" ? "Unavailable" : "Không khả dụng";
  if (Array.isArray(value)) {
    return value.length
      ? (locale === "en" ? `${value.length} records` : `${value.length} bản ghi`)
      : (locale === "en" ? "No records" : "Không có bản ghi");
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    if ("status" in record && typeof record.status === "string") return translateQuantEnum(record.status, locale);
    if ("regime" in record && typeof record.regime === "string") return translateQuantEnum(record.regime, locale);
    return locale === "en" ? `${Object.keys(record).length} tracked fields` : `${Object.keys(record).length} trường theo dõi`;
  }
  return String(value);
}

function DecisionBrief({ symbol, locale }: { symbol: string; locale: AppLocale }) {
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
      setResource({
        state: "error",
        message: caught instanceof Error ? caught.message : (locale === "en" ? "Unable to load decision context." : "Không thể kết nối bối cảnh quyết định."),
      });
    }
  }

  async function captureSnapshot() {
    setBusy(true);
    setNotice("");
    try {
      const receipt = await captureDecisionSnapshot(symbol, asOf || undefined);
      setNotice(
        locale === "en"
          ? `Saved snapshot ${receipt.id} for ${receipt.as_of_date}.`
          : `Đã lưu snapshot ${receipt.id} cho ngày ${receipt.as_of_date}.`
      );
      await loadContext();
    } catch (caught) {
      setResource({
        state: "error",
        message: caught instanceof Error ? caught.message : (locale === "en" ? "Failed to save snapshot." : "Lưu snapshot thất bại."),
      });
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

  return (
    <div className={styles.decisionWrap}>
      <button className={styles.decisionToggle} type="button" aria-expanded={open} onClick={toggle}>
        {open ? (locale === "en" ? "Hide Decision Context" : "Ẩn bối cảnh quyết định") : (locale === "en" ? "View Decision Context" : "Xem bối cảnh quyết định")}
      </button>
      {open && (
        <section className={styles.decisionBrief} aria-label={`${symbol} decision brief`}>
          <header className={styles.decisionHeader}>
            <div>
              <h3>{locale === "en" ? "Decision Context" : "Bối cảnh quyết định"}</h3>
              <p>{locale === "en" ? "Fact-anchored perspective verified with empirical data; not investment advice." : "Góc nhìn gắn liền với dữ liệu kiểm chứng; không phải khuyến nghị giao dịch."}</p>
            </div>
            {resource.state === "ready" && (
              <div className={styles.decisionActions}>
                <label>
                  {locale === "en" ? "As-Of Date" : "Ngày dữ liệu"}
                  <input aria-label={locale === "en" ? "As-Of Date" : "Ngày dữ liệu"} type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} />
                </label>
                <Status value={resource.data.decision_state} />
                <button type="button" disabled={busy} onClick={() => void loadContext()}>
                  {locale === "en" ? "Refresh" : "Làm mới"}
                </button>
                <button type="button" disabled={busy} onClick={() => void captureSnapshot()}>
                  {busy ? (locale === "en" ? "Saving..." : "Đang lưu...") : (locale === "en" ? "Save Snapshot" : "Lưu snapshot")}
                </button>
              </div>
            )}
          </header>
          {notice && <p className={styles.decisionNotice} role="status">{notice}</p>}
          {resource.state === "loading" && <p className={styles.empty} role="status">{locale === "en" ? "Loading decision context..." : "Đang tải bối cảnh quyết định..."}</p>}
          {resource.state === "error" && (
            <div className={styles.error} role="alert">
              <strong>{locale === "en" ? "Unable to connect to decision context" : "Không thể kết nối bối cảnh quyết định"}</strong>
              <span>{resource.message}</span>
            </div>
          )}
          {resource.state === "ready" && (
            <>
              <p className={styles.decisionAsOf}>
                {locale === "en" ? "As of" : "Tính đến"} {displayDate(resource.data.as_of_date, locale)} · {locale === "en" ? "Data Status" : "Trạng thái dữ liệu"} <Status value={resource.data.decision_state} />
              </p>
              <div className={styles.decisionSection}>
                <h4>{locale === "en" ? "Recent Metric Changes" : "Biến động gần nhất"}</h4>
                {resource.data.what_changed.map((change, index) => (
                  <div className={styles.decisionChange} key={`${change.metric ?? "change"}-${index}`}>
                    <div>
                      <strong>{change.metric ?? (locale === "en" ? "Observation milestone comparison" : "So sánh mốc quan sát")}</strong>
                      <Status value={change.claim_type} />
                    </div>
                    <p>
                      {present(change.before, locale)} <span aria-hidden="true">-&gt;</span> {present(change.after, locale)}
                    </p>
                    <small>
                      {change.date} | {change.responsible_module} | {change.source ?? (locale === "en" ? "source unavailable" : "nguồn không khả dụng")}
                      {change.magnitude ? ` | ${locale === "en" ? "diff" : "chênh lệch"} ${change.magnitude.absolute}${change.magnitude.relative_pct === null ? "" : ` (${change.magnitude.relative_pct.toFixed(2)}%)`}` : ""}
                    </small>
                  </div>
                ))}
              </div>
              <div className={styles.decisionGrid}>
                <div className={styles.decisionSection}>
                  <h4>{locale === "en" ? "Catalysts & Growth Drivers" : "Động lực thúc đẩy"}</h4>
                  {resource.data.why_now.map((claim, index) => (
                    <p key={`now-${index}`}>
                      <Status value={String(claim.claim_type ?? "UNCERTAINTY")} /> {String(claim.text ?? (locale === "en" ? "No catalyst recorded." : "Chưa có động lực hỗ trợ."))} <small>{String(claim.source ?? "")}</small>
                    </p>
                  ))}
                </div>
                <div className={styles.decisionSection}>
                  <h4>{locale === "en" ? "Headwinds & Downside Risks" : "Rủi ro & rào cản"}</h4>
                  {resource.data.why_not_now.map((claim, index) => (
                    <p key={`not-${index}`}>
                      <Status value={String(claim.claim_type ?? "UNCERTAINTY")} /> {String(claim.text ?? (locale === "en" ? "No downside barrier recorded." : "Chưa có rào cản ghi nhận."))} <small>{String(claim.source ?? "")}</small>
                    </p>
                  ))}
                </div>
                <div className={styles.decisionSection}>
                  <h4>{locale === "en" ? "Thesis Invalidation Conditions" : "Điều kiện vô hiệu hóa luận điểm"}</h4>
                  {resource.data.what_would_make_me_wrong.length ? (
                    resource.data.what_would_make_me_wrong.map((item, index) => (
                      <p key={`wrong-${index}`}>
                        <Status value={String(item.type ?? "USER_DEFINED")} /> {String(item.condition ?? (locale === "en" ? "Condition unavailable." : "Điều kiện không khả dụng."))}
                      </p>
                    ))
                  ) : (
                    <p>{locale === "en" ? "No invalidation conditions defined." : "Chưa thiết lập điều kiện vô hiệu hóa luận điểm."}</p>
                  )}
                </div>
                <div className={styles.decisionSection}>
                  <h4>{locale === "en" ? "Scenario Analysis" : "Kịch bản dự báo"}</h4>
                  {Object.entries(resource.data.scenario).map(([name, scenario]) => (
                    <p key={name}>
                      <strong>{name.toUpperCase()}</strong> <Status value={scenario.status} /> {scenario.uncertainty ?? (locale === "en" ? "No scenario interval available." : "Chưa có khoảng kịch bản hỗ trợ.")}
                    </p>
                  ))}
                </div>
              </div>
              <div className={styles.decisionSection}>
                <h4>{locale === "en" ? "Factor Contributions" : "Đóng góp từ các nhân tố"}</h4>
                <div className={styles.contributionList}>
                  {Object.entries(resource.data.explainability).map(([name, contribution]) => (
                    <div key={name}>
                      <strong>{name.replaceAll("_", " ")}</strong>
                      <Status value={contribution.status} />
                      <span>{present(contribution.value, locale)}</span>
                    </div>
                  ))}
                </div>
              </div>
              <details className={styles.decisionEvidence}>
                <summary>
                  {locale === "en" ? `Evidence Log (${resource.data.evidence.length})` : `Nhật ký dữ liệu kiểm chứng (${resource.data.evidence.length})`}
                </summary>
                {resource.data.evidence.length ? (
                  resource.data.evidence.map((item, index) => (
                    <p key={`evidence-${index}`}>
                      <Status value={String(item.claim_type ?? "UNCERTAINTY")} />
                      <strong>{String(item.responsible_module ?? "source")}</strong> | {String(item.source ?? (locale === "en" ? "source unavailable" : "nguồn không khả dụng"))} | {locale === "en" ? "observed" : "quan sát"} {String(item.observation_date ?? "—")} | {locale === "en" ? "published" : "công bố"} {String(item.publication_date ?? "—")} | {locale === "en" ? "latency" : "độ trễ"} {String(item.freshness ?? "—")} | {String(item.data_origin ?? "—")}
                    </p>
                  ))
                ) : (
                  <p>{locale === "en" ? "No evidence records available." : "Không có bản ghi dữ liệu kiểm chứng nào."}</p>
                )}
              </details>
            </>
          )}
        </section>
      )}
    </div>
  );
}

export default function WatchlistPage() {
  const { locale, t } = useLocale();

  const [resource, setResource] = useState<Resource>({ state: "loading" });
  const [availableAssets, setAvailableAssets] = useState<WatchlistAvailableAsset[]>([]);
  const [selectedAssetSymbol, setSelectedAssetSymbol] = useState("");
  const [formSymbol, setFormSymbol] = useState("");
  const [formHorizon, setFormHorizon] = useState("LONG_TERM");
  const [formThesis, setFormThesis] = useState("");
  const [formInvalidation, setFormInvalidation] = useState("");
  const [selectedWatchFilter, setSelectedWatchFilter] = useState("");
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
    getWatchlist(controller.signal)
      .then((rows) => setResource({ state: "ready", rows }))
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setResource({ state: "error", message: caught instanceof Error ? caught.message : "Watchlist API error" });
        }
      });

    getWatchlistAvailableAssets(controller.signal)
      .then((assets) => setAvailableAssets(assets))
      .catch(() => {});

    return () => controller.abort();
  }, [reload]);

  function handleSelectAvailable(symbol: string) {
    setSelectedAssetSymbol(symbol);
    setFormSymbol(symbol);
    const found = availableAssets.find((a) => a.symbol === symbol);
    if (found) {
      if (!formThesis || formThesis.includes("— Doanh nghiệp") || formThesis.includes("— High-conviction")) {
        setFormThesis(
          locale === "en"
            ? `${found.name} (${found.symbol}) — High-conviction company in ${found.sector || "core"} sector, maintaining robust operational efficiency and sustainable growth.`
            : `${found.name} (${found.symbol}) — Doanh nghiệp tiềm năng ngành ${found.sector || "chủ lực"}, duy trì hiệu quả hoạt động và đà tăng trưởng bền vững.`
        );
      }
      if (!formInvalidation || formInvalidation.includes("ROE suy giảm") || formInvalidation.includes("ROE drops below")) {
        setFormInvalidation(
          locale === "en"
            ? "ROE drops below 15% or net earnings contract for 2 consecutive quarters; D/E leverage exceeds 1.5x."
            : "ROE suy giảm xuống dưới 15% hoặc tăng trưởng LNST âm 2 quý liên tiếp; Tỷ lệ nợ D/E vượt quá 1.5x."
        );
      }
      setFormHorizon("LONG_TERM");
    }
  }

  const rows = useMemo(() => {
    if (resource.state !== "ready") return [];
    const filtered = resource.rows.filter((item) => {
      if (symbolFilter && !`${item.symbol} ${item.name}`.toLowerCase().includes(symbolFilter.toLowerCase())) {
        return false;
      }
      if (horizonFilter && item.horizon !== horizonFilter) return false;
      if (statusFilter && item.data_status !== statusFilter) return false;
      return true;
    });
    return filtered.sort((a, b) =>
      sortBy === "symbol"
        ? a.symbol.localeCompare(b.symbol)
        : sortBy === "opportunity"
        ? (b.opportunity ?? -1) - (a.opportunity ?? -1)
        : b.last_changed_at.localeCompare(a.last_changed_at)
    );
  }, [resource, symbolFilter, horizonFilter, statusFilter, sortBy]);

  async function perform(id: number | "create", operation: () => Promise<unknown>, success: string) {
    setBusyId(id);
    setError("");
    setNotice("");
    try {
      await operation();
      setNotice(success);
      setReload((value) => value + 1);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("Không thể hoàn thành thao tác.", "Failed to complete operation."));
    } finally {
      setBusyId(null);
    }
  }

  async function addItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = {
      symbol: formSymbol.trim().toUpperCase(),
      horizon: formHorizon || null,
      thesis: formThesis.trim() || undefined,
      invalidation: formInvalidation.trim() || undefined,
    };
    await perform("create", () => createWatchlistItem(payload), t("Đã thêm mã vào danh sách theo dõi.", "Added stock to watchlist."));
    setFormSymbol("");
    setSelectedAssetSymbol("");
    setFormThesis("");
    setFormInvalidation("");
  }

  async function editThesis(event: FormEvent<HTMLFormElement>, item: WatchlistItem) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    await perform(
      item.id,
      () =>
        patchWatchlistItem(item.id, {
          thesis: String(values.get("thesis") ?? ""),
          horizon: String(values.get("horizon") ?? "") || null,
          invalidation: String(values.get("invalidation") ?? "") || null,
          change_reason: String(values.get("change_reason") ?? ""),
        }),
      t("Đã lưu thay đổi luận điểm kèm lý do.", "Thesis revision saved with reason.")
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>{t("Danh sách theo dõi", "Watchlist")}</h1>
          <p>{t("Nghiên cứu danh mục cá nhân dựa trên dữ liệu định lượng và nguồn kiểm chứng độc lập.", "Personal investment watchlist anchored by quantitative metrics and independent verification.")}</p>
        </div>
        <button
          className={styles.refresh}
          aria-label={t("Làm mới danh sách", "Refresh watchlist")}
          title={t("Làm mới danh sách", "Refresh watchlist")}
          onClick={() => setReload((value) => value + 1)}
        >
          ↻ <span>{t("Làm mới", "Refresh")}</span>
        </button>
      </header>
      {notice && <p className={styles.notice} role="status">{notice}</p>}
      {error && (
        <div className={styles.error} role="alert">
          <strong>{t("Thao tác không thành công", "Operation Failed")}</strong>
          <span>{error}</span>
        </div>
      )}

      <section className={styles.section}>
        <header>
          <div>
            <h2>{t("Thêm cổ phiếu vào danh sách theo dõi", "Add Stock to Watchlist")}</h2>
          </div>
        </header>
        <form className={styles.addForm} onSubmit={addItem}>
          <label>
            {t("Chọn từ cổ phiếu có sẵn", "Select from available assets")}
            <select
              value={selectedAssetSymbol}
              onChange={(event) => handleSelectAvailable(event.target.value)}
            >
              <option value="">
                {t(`-- Chọn mã cổ phiếu (${availableAssets.length} mã) --`, `-- Select ticker (${availableAssets.length} available) --`)}
              </option>
              {availableAssets.map((asset) => (
                <option key={asset.symbol} value={asset.symbol} disabled={asset.is_in_watchlist}>
                  {asset.symbol} — {asset.name} ({asset.sector}){asset.is_in_watchlist ? t(" [Đã theo dõi]", " [In Watchlist]") : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("Mã cổ phiếu", "Ticker Symbol")}
            <input
              name="symbol"
              required
              maxLength={20}
              value={formSymbol}
              onChange={(event) => {
                const val = event.target.value.toUpperCase();
                setFormSymbol(val);
                setSelectedAssetSymbol(val);
              }}
              placeholder={t("VD: FPT", "e.g. FPT")}
            />
          </label>
          <label>
            {t("Khung thời gian", "Investment Horizon")}
            <select name="horizon" value={formHorizon} onChange={(event) => setFormHorizon(event.target.value)}>
              <option value="">{t("Chưa thiết lập", "Not set")}</option>
              <option value="MEDIUM_TERM">{t("Trung hạn (1–12 tháng)", "Medium-Term (1–12M)")}</option>
              <option value="LONG_TERM">{t("Dài hạn (3–10 năm)", "Long-Term (3–10Y)")}</option>
            </select>
          </label>
          <label>
            {t("Luận điểm đầu tư", "Investment Thesis")}
            <input
              name="thesis"
              maxLength={4000}
              value={formThesis}
              onChange={(event) => setFormThesis(event.target.value)}
              placeholder={t("Luận điểm đầu tư chính...", "Core investment thesis...")}
            />
          </label>
          <label>
            {t("Điều kiện vô hiệu hóa", "Thesis Invalidation")}
            <input
              name="invalidation"
              maxLength={4000}
              value={formInvalidation}
              onChange={(event) => setFormInvalidation(event.target.value)}
              placeholder={t("Điều kiện gì khiến bạn từ bỏ luận điểm?", "What conditions would invalidate this thesis?")}
            />
          </label>
          <button disabled={busyId === "create" || !formSymbol.trim()} type="submit">
            {t("+ Thêm cổ phiếu", "+ Add Stock")}
          </button>
        </form>
      </section>

      <section className={styles.section}>
        <header>
          <div>
            <h2>{t("Các cổ phiếu đang theo dõi", "Monitored Holdings & Ideas")}</h2>
          </div>
          <span>{resource.state === "ready" ? t(`Hiển thị ${rows.length} / ${resource.rows.length} mã`, `Displaying ${rows.length} / ${resource.rows.length} tickers`) : ""}</span>
        </header>
        <div className={styles.filters}>
          <label>
            {t("Chọn cổ phiếu theo dõi", "Select Monitored Stock")}
            <select
              value={selectedWatchFilter}
              onChange={(event) => {
                const sym = event.target.value;
                setSelectedWatchFilter(sym);
                setSymbolFilter(sym);
              }}
            >
              <option value="">
                {t(
                  `Tất cả cổ phiếu đang theo dõi (${resource.state === "ready" ? resource.rows.length : 0} mã)`,
                  `All monitored stocks (${resource.state === "ready" ? resource.rows.length : 0} tickers)`
                )}
              </option>
              {resource.state === "ready" &&
                resource.rows.map((item) => (
                  <option key={item.id} value={item.symbol}>
                    {item.symbol} — {item.name}
                  </option>
                ))}
            </select>
          </label>
          <label>
            {t("Tìm kiếm", "Search")}
            <input
              value={symbolFilter}
              onChange={(event) => {
                setSymbolFilter(event.target.value);
                if (selectedWatchFilter && event.target.value !== selectedWatchFilter) {
                  setSelectedWatchFilter("");
                }
              }}
              placeholder={t("Mã hoặc tên công ty...", "Ticker or company name...")}
            />
          </label>
          <label>
            {t("Khung thời gian", "Investment Horizon")}
            <select value={horizonFilter} onChange={(event) => setHorizonFilter(event.target.value)}>
              <option value="">{t("Tất cả khung thời gian", "All Horizons")}</option>
              <option value="MEDIUM_TERM">{t("Trung hạn (1–12 tháng)", "Medium-Term (1–12M)")}</option>
              <option value="LONG_TERM">{t("Dài hạn (3–10 năm)", "Long-Term (3–10Y)")}</option>
            </select>
          </label>
          <label>
            {t("Trạng thái dữ liệu", "Data Status")}
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">{t("Tất cả trạng thái", "All Statuses")}</option>
              <option value="AVAILABLE">{t("Khả dụng", "Available")}</option>
              <option value="PARTIAL">{t("Một phần", "Partial")}</option>
              <option value="INSUFFICIENT_DATA">{t("Chưa có dữ liệu", "Insufficient Data")}</option>
            </select>
          </label>
          <label>
            {t("Sắp xếp", "Sort By")}
            <select value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
              <option value="changed">{t("Thay đổi gần nhất", "Recently Changed")}</option>
              <option value="symbol">{t("Mã cổ phiếu (A-Z)", "Ticker (A-Z)")}</option>
              <option value="opportunity">{t("Điểm cơ hội (cao-thấp)", "Opportunity Score (High-Low)")}</option>
            </select>
          </label>
        </div>
        {resource.state === "loading" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px", margin: "16px 0" }}>
            <SkeletonCard height={160} />
            <SkeletonCard height={160} />
          </div>
        )}
        {resource.state === "error" && (
          <div className={styles.error} role="alert">
            <strong>{t("Không thể kết nối API theo dõi", "Unable to Connect to Watchlist API")}</strong>
            <span>{resource.message}</span>
          </div>
        )}
        {resource.state === "ready" && rows.length === 0 && (
          <p className={styles.empty}>
            {resource.rows.length
              ? t("Không có mã nào phù hợp với bộ lọc.", "No stocks match the selected filters.")
              : t("Danh sách theo dõi hiện đang trống. Hãy thêm mã đầu tiên ở biểu mẫu phía trên.", "Your watchlist is empty. Add your first stock using the form above.")}
          </p>
        )}
        {resource.state === "ready" &&
          rows.map((item) => {
            const confDisplay = translateQuantEnum(item.confidence, locale);

            const fairVal = item.valuation?.fair_value?.value;
            const mosVal = item.valuation?.margin_of_safety?.value;
            const pbVal = item.valuation?.pb?.value;
            const roeVal = item.valuation?.roe?.value;
            const peVal = item.valuation?.pe?.value;
            const sectorLabel = item.sector
              ? translateSectorName(item.sector, locale)
              : t("Chưa phân ngành", "Unclassified");
            const invalidationConditions = (item.invalidation ?? "")
              .split(/[;\n]+/)
              .map((s) => translateResearchCopy(s.trim(), locale).replace(/\.$/, ""))
              .filter(Boolean);

            return (
              <article className={styles.watchItem} key={item.id}>
                <header className={styles.itemHeader}>
                  <div>
                    <p className={styles.symbolLine}>
                      <Link href={`/ai?symbol=${encodeURIComponent(item.symbol)}`}>{item.symbol}</Link>
                      <Status value={item.data_status} />
                    </p>
                    <strong>{item.name}</strong>
                    <small>
                      {sectorLabel} /{" "}
                      {item.horizon === "MEDIUM_TERM"
                        ? t("Trung hạn", "Medium-Term")
                        : item.horizon === "LONG_TERM"
                        ? t("Dài hạn", "Long-Term")
                        : t("Chưa đặt thời hạn", "Horizon not set")}
                    </small>
                  </div>
                  <div className={styles.actions}>
                    <button
                      disabled={busyId === item.id}
                      onClick={() => void perform(item.id, () => reviewWatchlistItem(item.id), t("Đã cập nhật ngày xem xét.", "Review date updated."))}
                    >
                      {t("Đã xem xét", "Reviewed")}
                    </button>
                    <button
                      disabled={busyId === item.id}
                      onClick={() => void perform(item.id, () => captureWatchlistSnapshot(item.id), t("Đã lưu snapshot mốc quan sát.", "Watchlist snapshot captured."))}
                    >
                      {t("Lưu snapshot", "Save Snapshot")}
                    </button>
                    <button
                      className={styles.remove}
                      disabled={busyId === item.id}
                      onClick={() => void perform(item.id, () => deleteWatchlistItem(item.id), t(`Đã xóa ${item.symbol}.`, `Removed ${item.symbol}.`))}
                    >
                      {t("Xóa", "Remove")}
                    </button>
                  </div>
                </header>
                <div className={styles.metrics}>
                  <div>
                    <span>{t("Điểm cơ hội", "Opportunity Score")}</span>
                    <b>{item.opportunity !== null && item.opportunity !== undefined ? `${item.opportunity}/100` : "—"}</b>
                  </div>
                  <div>
                    <span>{t("Độ tin cậy", "Confidence")}</span>
                    <b>{confDisplay}</b>
                  </div>
                  <div>
                    <span>{t("Điểm rủi ro", "Risk Score")}</span>
                    <b>{item.risk !== null && item.risk !== undefined ? `${item.risk}/100` : "—"}</b>
                  </div>
                  <div>
                    <span>{t("Định giá P/E", "P/E Ratio")}</span>
                    <b>{item.valuation?.pe?.value ? `${Number(item.valuation.pe.value).toFixed(1)}x` : "—"}</b>
                  </div>
                  <div>
                    <span>{t("Giá hợp lý", "Fair Value")}</span>
                    <b>
                      {fairVal
                        ? `${Number(fairVal).toLocaleString(locale === "en" ? "en-US" : "vi-VN")} ${locale === "en" ? "VND" : "đ"}`
                        : mosVal !== undefined && mosVal !== null
                        ? `${(Number(mosVal) * 100).toFixed(1)}% MoS`
                        : "—"}
                    </b>
                  </div>
                  <div>
                    <span>{t("Độ trễ dữ liệu", "Data Freshness")}</span>
                    <b>
                      <Status value={item.data_freshness.status} /> {displayDate(item.data_freshness.as_of_date, locale)}
                    </b>
                  </div>
                </div>
                <div className={styles.thesisGrid}>
                  <div className={styles.thesisFullCard}>
                    <div className={styles.thesisCardHead}>
                      <h3>{t("Luận điểm đầu tư", "Investment Thesis")}</h3>
                      <div className={styles.thesisMetricStrip}>
                        {peVal !== null && peVal !== undefined && (
                          <span className={styles.thesisMetricChip}>P/E {Number(peVal).toFixed(1)}x</span>
                        )}
                        {pbVal !== null && pbVal !== undefined && (
                          <span className={styles.thesisMetricChip}>P/B {Number(pbVal).toFixed(2)}x</span>
                        )}
                        {roeVal !== null && roeVal !== undefined && (
                          <span className={styles.thesisMetricChip}>ROE {Number(roeVal).toFixed(1)}%</span>
                        )}
                        {mosVal !== null && mosVal !== undefined && (
                          <span
                            className={`${styles.thesisMetricChip} ${
                              Number(mosVal) >= 0 ? styles.thesisMetricPos : styles.thesisMetricNeg
                            }`}
                          >
                            MoS {Number(mosVal) >= 0 ? "+" : ""}{(Number(mosVal) * 100).toFixed(1)}%
                          </span>
                        )}
                      </div>
                    </div>
                    <p className={styles.thesisLeadText}>
                      {item.thesis
                        ? translateResearchCopy(item.thesis, locale)
                        : t("Chưa có luận điểm.", "No thesis provided.")}
                    </p>
                  </div>
                  <div>
                    <h3>{t("Động lực thúc đẩy", "Catalysts & Drivers")}</h3>
                    <div className={styles.claimList}>
                      {item.why_now.length ? (
                        item.why_now.map((claim, idx) => (
                          <div key={`wn-${idx}`} className={styles.claimItem}>
                            <span className={styles.bulletPositive}>✓</span>
                            <span>{translateResearchCopy(String(claim.description ?? claim.text ?? ""), locale)}</span>
                          </div>
                        ))
                      ) : (
                        <p>{t("Chưa có luận cứ tích cực được ghi nhận.", "No positive catalysts recorded.")}</p>
                      )}
                    </div>
                  </div>
                  <div>
                    <h3>{t("Rủi ro & rào cản", "Risks & Headwinds")}</h3>
                    <div className={styles.claimList}>
                      {item.why_not_now.length ? (
                        item.why_not_now.map((claim, idx) => (
                          <div key={`wnn-${idx}`} className={styles.claimItem}>
                            <span className={styles.bulletRisk}>⚠</span>
                            <span>{translateResearchCopy(String(claim.description ?? claim.text ?? ""), locale)}</span>
                          </div>
                        ))
                      ) : (
                        <p>{t("Chưa có luận cứ được ghi nhận.", "No risk factors recorded.")}</p>
                      )}
                    </div>
                  </div>
                  <div className={styles.invalidationCard}>
                    <div className={styles.thesisCardHead}>
                      <h3>{t("Điều kiện vô hiệu hóa", "Invalidation Triggers")}</h3>
                      <div className={styles.invalidationActions}>
                        <Link href={`/research/${encodeURIComponent(item.symbol)}`} className={styles.quickNavLink}>
                          {t(`Nghiên cứu ${item.symbol}`, `Research ${item.symbol}`)} →
                        </Link>
                        <Link href={`/valuation?symbol=${encodeURIComponent(item.symbol)}`} className={styles.quickNavLink}>
                          {t("Định giá", "Valuation")} →
                        </Link>
                      </div>
                    </div>
                    {invalidationConditions.length > 0 ? (
                      <div
                        className={`${styles.invalidationList} ${
                          invalidationConditions.length === 1
                            ? styles.invalidationListSingle
                            : invalidationConditions.length === 2
                              ? styles.invalidationListPair
                              : ""
                        }`}
                      >
                        {invalidationConditions.map((cond, idx) => (
                          <div key={`inv-${idx}`} className={styles.invalidationItem}>
                            <span className={styles.bulletInvalid} aria-hidden="true">⊘</span>
                            <span>{cond}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p>{t("Chưa đặt điều kiện vô hiệu.", "No invalidation conditions set.")}</p>
                    )}
                  </div>
                </div>
                {item.changes.length > 0 && (
                  <div className={styles.changes}>
                    <h3>{t("Biến động trước / sau", "Historical Metric Deltas")}</h3>
                    {item.changes.map((change, index) => (
                      <p key={`${String(change.type)}-${index}`}>
                        <Status value={String(change.materiality)} />
                        <b>{String(change.type)}</b> / {String(change.before ?? "N/A")} -&gt; {String(change.after ?? "N/A")} / {t("nguồn", "source")}{" "}
                        {String((change.evidence as Record<string, unknown> | undefined)?.source ?? (locale === "en" ? "unavailable" : "không khả dụng"))}
                      </p>
                    ))}
                  </div>
                )}
                <DecisionBrief symbol={item.symbol} locale={locale} />
                <details className={styles.editDetails}>
                  <summary>{t("Chỉnh sửa luận điểm (bắt buộc nêu lý do)", "Edit Thesis (Reason Required)")}</summary>
                  <form className={styles.editForm} onSubmit={(event) => void editThesis(event, item)}>
                    <label>
                      {t("Luận điểm đầu tư", "Investment Thesis")}
                      <textarea name="thesis" defaultValue={item.thesis ?? ""} maxLength={4000} />
                    </label>
                    <label>
                      {t("Khung thời gian", "Investment Horizon")}
                      <select name="horizon" defaultValue={item.horizon ?? ""}>
                        <option value="">{t("Chưa thiết lập", "Not set")}</option>
                        <option value="MEDIUM_TERM">{t("1 đến 12 tháng (Trung hạn)", "1 to 12 Months (Medium-Term)")}</option>
                        <option value="LONG_TERM">{t("3 đến 10 năm (Dài hạn)", "3 to 10 Years (Long-Term)")}</option>
                      </select>
                    </label>
                    <label>
                      {t("Điều kiện vô hiệu hóa", "Thesis Invalidation")}
                      <textarea name="invalidation" defaultValue={item.invalidation ?? ""} maxLength={4000} />
                    </label>
                    <label>
                      {t("Lý do điều chỉnh (bắt buộc)", "Revision Reason (Required)")}
                      <input name="change_reason" required placeholder={t("Căn cứ hoặc lý do điều chỉnh...", "Reason or basis for adjustment...")} />
                    </label>
                    <button disabled={busyId === item.id} type="submit">
                      {t("Lưu cập nhật", "Save Changes")}
                    </button>
                  </form>
                </details>
                <footer>
                  {t("Xem xét gần nhất", "Last reviewed")}: {displayDate(item.last_reviewed_at, locale)} · {t("Thay đổi gần nhất", "Last changed")}: {displayDate(item.last_changed_at, locale)} · {t("Nguồn", "Source")}: {item.data_freshness.source ?? (locale === "en" ? "Unavailable" : "Không khả dụng")}
                </footer>
              </article>
            );
          })}
      </section>
    </div>
  );
}
