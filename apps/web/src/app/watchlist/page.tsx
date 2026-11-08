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
import { StatusBadge } from "@/components/ui/status-badge";
import { SkeletonCard } from "@/components/ui/skeleton";
import styles from "./page.module.css";

type Resource = { state: "loading" } | { state: "ready"; rows: WatchlistItem[] } | { state: "error"; message: string };
type DecisionResource = { state: "idle" | "loading" } | { state: "ready"; data: DecisionContext } | { state: "error"; message: string };

function displayDate(value: string | null) {
  return value ? new Date(value).toLocaleDateString("vi-VN") : "N/A";
}
function Status({ value }: { value: string }) {
  return <StatusBadge status={value} />;
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
      setResource({ state: "error", message: caught instanceof Error ? caught.message : "Không thể kết nối bối cảnh quyết định." });
    }
  }

  async function captureSnapshot() {
    setBusy(true);
    setNotice("");
    try {
      const receipt = await captureDecisionSnapshot(symbol, asOf || undefined);
      setNotice(`Đã lưu snapshot ${receipt.id} cho ngày ${receipt.as_of_date}.`);
      await loadContext();
    } catch (caught) {
      setResource({ state: "error", message: caught instanceof Error ? caught.message : "Lưu snapshot thất bại." });
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
      {open ? "Ẩn bối cảnh quyết định" : "Xem bối cảnh quyết định"}
    </button>
    {open && <section className={styles.decisionBrief} aria-label={`${symbol} decision brief`}>
      <header className={styles.decisionHeader}>
        <div><h3>Bối cảnh quyết định</h3><p>Góc nhìn gắn liền với dữ liệu kiểm chứng; không phải khuyến nghị giao dịch.</p></div>
        {resource.state === "ready" && <div className={styles.decisionActions}>
          <label>Ngày dữ liệu<input aria-label="Ngày dữ liệu" type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} /></label>
          <Status value={resource.data.decision_state} />
          <button type="button" disabled={busy} onClick={() => void loadContext()}>Làm mới</button>
          <button type="button" disabled={busy} onClick={() => void captureSnapshot()}>{busy ? "Đang lưu..." : "Lưu snapshot"}</button>
        </div>}
      </header>
      {notice && <p className={styles.decisionNotice} role="status">{notice}</p>}
      {resource.state === "loading" && <p className={styles.empty} role="status">Đang tải bối cảnh quyết định...</p>}
      {resource.state === "error" && <div className={styles.error} role="alert"><strong>Không thể kết nối bối cảnh quyết định</strong><span>{resource.message}</span></div>}
      {resource.state === "ready" && <>
        <p className={styles.decisionAsOf}>Tính đến {displayDate(resource.data.as_of_date)} · Trạng thái dữ liệu <Status value={resource.data.decision_state} /></p>
        <div className={styles.decisionSection}>
          <h4>Biến động gần nhất</h4>
          {resource.data.what_changed.map((change, index) => <div className={styles.decisionChange} key={`${change.metric ?? "change"}-${index}`}>
            <div><strong>{change.metric ?? "So sánh mốc quan sát"}</strong><Status value={change.claim_type} /></div>
            <p>{present(change.before)} <span aria-hidden="true">-&gt;</span> {present(change.after)}</p>
            <small>{change.date} | {change.responsible_module} | {change.source ?? "nguồn không khả dụng"}{change.magnitude ? ` | chênh lệch ${change.magnitude.absolute}${change.magnitude.relative_pct === null ? "" : ` (${change.magnitude.relative_pct.toFixed(2)}%)`}` : ""}</small>
          </div>)}
        </div>
        <div className={styles.decisionGrid}>
          <div className={styles.decisionSection}><h4>Động lực thúc đẩy</h4>{resource.data.why_now.map((claim, index) => <p key={`now-${index}`}><Status value={String(claim.claim_type ?? "UNCERTAINTY")} /> {String(claim.text ?? "Chưa có động lực hỗ trợ.")} <small>{String(claim.source ?? "")}</small></p>)}</div>
          <div className={styles.decisionSection}><h4>Rủi ro & rào cản</h4>{resource.data.why_not_now.map((claim, index) => <p key={`not-${index}`}><Status value={String(claim.claim_type ?? "UNCERTAINTY")} /> {String(claim.text ?? "Chưa có rào cản ghi nhận.")} <small>{String(claim.source ?? "")}</small></p>)}</div>
          <div className={styles.decisionSection}><h4>Điều kiện vô hiệu hóa luận điểm</h4>{resource.data.what_would_make_me_wrong.length ? resource.data.what_would_make_me_wrong.map((item, index) => <p key={`wrong-${index}`}><Status value={String(item.type ?? "USER_DEFINED")} /> {String(item.condition ?? "Điều kiện không khả dụng.")}</p>) : <p>Chưa thiết lập điều kiện vô hiệu hóa luận điểm.</p>}</div>
          <div className={styles.decisionSection}><h4>Kịch bản dự báo</h4>{Object.entries(resource.data.scenario).map(([name, scenario]) => <p key={name}><strong>{name.toUpperCase()}</strong> <Status value={scenario.status} /> {scenario.uncertainty ?? "Chưa có khoảng kịch bản hỗ trợ."}</p>)}</div>
        </div>
        <div className={styles.decisionSection}>
          <h4>Đóng góp từ các nhân tố</h4>
          <div className={styles.contributionList}>{Object.entries(resource.data.explainability).map(([name, contribution]) => <div key={name}><strong>{name.replaceAll("_", " ")}</strong><Status value={contribution.status} /><span>{present(contribution.value)}</span></div>)}</div>
        </div>
        <details className={styles.decisionEvidence}>
          <summary>Nhật ký dữ liệu kiểm chứng ({resource.data.evidence.length})</summary>
          {resource.data.evidence.length ? resource.data.evidence.map((item, index) => <p key={`evidence-${index}`}><Status value={String(item.claim_type ?? "UNCERTAINTY")} /><strong>{String(item.responsible_module ?? "source")}</strong> | {String(item.source ?? "nguồn không khả dụng")} | quan sát {String(item.observation_date ?? "—")} | công bố {String(item.publication_date ?? "—")} | độ trễ {String(item.freshness ?? "—")} | {String(item.data_origin ?? "—")}</p>) : <p>Không có bản ghi dữ liệu kiểm chứng nào.</p>}
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
    <header className={styles.header}><div><p className={styles.eyebrow}>Nghiên cứu & theo dõi cá nhân</p><h1>Danh sách theo dõi</h1><p>Nghiên cứu cá nhân dựa trên dữ liệu có nguồn kiểm chứng.</p></div><button className={styles.refresh} aria-label="Làm mới danh sách" title="Làm mới danh sách" onClick={() => setReload((value) => value + 1)}>↻ <span>Làm mới</span></button></header>
    {notice && <p className={styles.notice} role="status">{notice}</p>}{error && <div className={styles.error} role="alert"><strong>Thao tác không thành công</strong><span>{error}</span></div>}

    <section className={styles.section}>
      <header><div><p className={styles.eyebrow}>Luận điểm đầu tư</p><h2>Thêm cổ phiếu vào danh sách theo dõi</h2></div></header>
      <form className={styles.addForm} onSubmit={addItem}>
        <label>Mã cổ phiếu<input name="symbol" required maxLength={20} placeholder="VD: FPT" /></label>
        <label>Khung thời gian<select name="horizon" defaultValue=""><option value="">Chưa thiết lập</option><option value="MEDIUM_TERM">Trung hạn (1–12 tháng)</option><option value="LONG_TERM">Dài hạn (3–10 năm)</option></select></label>
        <label>Luận điểm đầu tư<input name="thesis" maxLength={4000} placeholder="Luận điểm đầu tư chính..." /></label>
        <label>Điều kiện vô hiệu hóa<input name="invalidation" maxLength={4000} placeholder="Điều kiện gì khiến bạn từ bỏ luận điểm?" /></label>
        <button disabled={busyId === "create"} type="submit">+ Thêm cổ phiếu</button>
      </form>
    </section>

    <section className={styles.section}>
      <header><div><p className={styles.eyebrow}>Dữ liệu theo dõi</p><h2>Các cổ phiếu đang theo dõi</h2></div><span>{resource.state === "ready" ? `Hiển thị ${rows.length} / ${resource.rows.length} mã` : ""}</span></header>
      <div className={styles.filters}>
        <label>Tìm kiếm<input value={symbolFilter} onChange={(event) => setSymbolFilter(event.target.value)} placeholder="Mã hoặc tên công ty..." /></label>
        <label>Khung thời gian<select value={horizonFilter} onChange={(event) => setHorizonFilter(event.target.value)}><option value="">Tất cả khung thời gian</option><option value="MEDIUM_TERM">Trung hạn (1–12 tháng)</option><option value="LONG_TERM">Dài hạn (3–10 năm)</option></select></label>
        <label>Trạng thái dữ liệu<select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="">Tất cả trạng thái</option><option value="AVAILABLE">Khả dụng</option><option value="PARTIAL">Một phần</option><option value="INSUFFICIENT_DATA">Chưa có dữ liệu</option></select></label>
        <label>Sắp xếp<select value={sortBy} onChange={(event) => setSortBy(event.target.value)}><option value="changed">Thay đổi gần nhất</option><option value="symbol">Mã cổ phiếu (A-Z)</option><option value="opportunity">Điểm cơ hội (cao-thấp)</option></select></label>
      </div>
      {resource.state === "loading" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px", margin: "16px 0" }}>
          <SkeletonCard height={160} />
          <SkeletonCard height={160} />
        </div>
      )}
      {resource.state === "error" && <div className={styles.error} role="alert"><strong>Không thể kết nối API theo dõi</strong><span>{resource.message}</span></div>}
      {resource.state === "ready" && rows.length === 0 && <p className={styles.empty}>{resource.rows.length ? "Không có mã nào phù hợp với bộ lọc." : "Danh sách theo dõi hiện đang trống. Hãy thêm mã đầu tiên ở biểu mẫu phía trên."}</p>}
      {resource.state === "ready" && rows.map((item) => <article className={styles.watchItem} key={item.id}>
        <header className={styles.itemHeader}><div><p className={styles.symbolLine}><Link href={`/research/${encodeURIComponent(item.symbol)}`}>{item.symbol}</Link><Status value={item.data_status} /></p><strong>{item.name}</strong><small>{item.sector ?? "Chưa phân ngành"} / {item.horizon === "MEDIUM_TERM" ? "Trung hạn" : item.horizon === "LONG_TERM" ? "Dài hạn" : "Chưa đặt thời hạn"}</small></div><div className={styles.actions}><button disabled={busyId === item.id} onClick={() => void perform(item.id, () => reviewWatchlistItem(item.id), "Đã cập nhật ngày xem xét.")}>Đã xem xét</button><button disabled={busyId === item.id} onClick={() => void perform(item.id, () => captureWatchlistSnapshot(item.id), "Đã lưu snapshot mốc quan sát.")}>Lưu snapshot</button><button className={styles.remove} disabled={busyId === item.id} onClick={() => void perform(item.id, () => deleteWatchlistItem(item.id), `Đã xóa ${item.symbol}.`)}>Xóa</button></div></header>
        <div className={styles.metrics}><div><span>Điểm cơ hội</span><b>{item.opportunity ?? "—"}</b></div><div><span>Độ tin cậy</span><b>{item.confidence === "HIGH" ? "Cao" : item.confidence === "MODERATE" ? "Khá" : item.confidence === "LOW" ? "Thấp" : item.confidence}</b></div><div><span>Điểm rủi ro</span><b>{item.risk ?? "—"}</b></div><div><span>Định giá P/E</span><b>{item.valuation?.pe?.value ?? "—"}</b></div><div><span>Độ trễ dữ liệu</span><b><Status value={item.data_freshness.status} /> {displayDate(item.data_freshness.as_of_date)}</b></div></div>
        <div className={styles.thesisGrid}>
          <div><h3>Luận điểm đầu tư</h3><p>{item.thesis || "Chưa có luận điểm."}</p></div>
          <div><h3>Động lực thúc đẩy</h3><p>{item.why_now.length ? item.why_now.map((claim) => String(claim.description ?? claim.text ?? "")).join(" / ") : "Chưa có luận cứ tích cực được ghi nhận."}</p></div>
          <div><h3>Rủi ro & rào cản</h3><p>{item.why_not_now.length ? item.why_not_now.map((claim) => String(claim.description ?? claim.text ?? "")).join(" / ") : "Chưa có luận cứ được ghi nhận."}</p></div>
          <div><h3>Điều kiện vô hiệu hóa</h3><p>{item.invalidation || "Chưa đặt điều kiện vô hiệu."}</p></div>
        </div>
        {item.changes.length > 0 && <div className={styles.changes}><h3>Biến động trước / sau</h3>{item.changes.map((change, index) => <p key={`${String(change.type)}-${index}`}><Status value={String(change.materiality)} /><b>{String(change.type)}</b> / {String(change.before ?? "N/A")} -&gt; {String(change.after ?? "N/A")} / nguồn {String((change.evidence as Record<string, unknown> | undefined)?.source ?? "không khả dụng")}</p>)}</div>}
        <DecisionBrief symbol={item.symbol} />
        <details className={styles.editDetails}><summary>Chỉnh sửa luận điểm (bắt buộc nêu lý do)</summary><form className={styles.editForm} onSubmit={(event) => void editThesis(event, item)}>
          <label>Luận điểm đầu tư<textarea name="thesis" defaultValue={item.thesis ?? ""} maxLength={4000} /></label>
          <label>Khung thời gian<select name="horizon" defaultValue={item.horizon ?? ""}><option value="">Chưa thiết lập</option><option value="MEDIUM_TERM">1 đến 12 tháng (Trung hạn)</option><option value="LONG_TERM">3 đến 10 năm (Dài hạn)</option></select></label>
          <label>Điều kiện vô hiệu hóa<textarea name="invalidation" defaultValue={item.invalidation ?? ""} maxLength={4000} /></label>
          <label>Lý do điều chỉnh (bắt buộc)<input name="change_reason" required placeholder="Căn cứ hoặc lý do điều chỉnh..." /></label>
          <button disabled={busyId === item.id} type="submit">Lưu cập nhật</button>
        </form></details>
        <footer>Xem xét gần nhất: {displayDate(item.last_reviewed_at)} · Thay đổi gần nhất: {displayDate(item.last_changed_at)} · Nguồn: {item.data_freshness.source ?? "Không khả dụng"}</footer>
      </article>)}
    </section>
  </div>;
}
