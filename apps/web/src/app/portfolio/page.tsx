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
  getPortfolioTemplates,
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
import { StatusBadge } from "@/components/ui/status-badge";
import { SkeletonCard } from "@/components/ui/skeleton";
import { PortfolioTorus3D } from "@/components/three/portfolio-torus-3d";
import styles from "./page.module.css";



type Load<T> = { state: "loading" } | { state: "ready"; data: T } | { state: "error"; message: string };



function money(value: number | null | undefined) {

  return value === null || value === undefined ? "—" : `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(value)} VND`;

}

function pct(value: number | null | undefined) {

  return value === null || value === undefined ? "—" : `${(value * 100).toFixed(2)}%`;

}

function dateLabel(value: string | null | undefined) {

  if (!value) return "No date";

  return new Date(value).toLocaleDateString("vi-VN");

}

function Status({ value }: { value: string }) {
  const customLabel =
    value === "EMPTY"
      ? "Trống (chưa có vị thế)"
      : value === "INSUFFICIENT_DATA"
      ? "Chưa có dữ liệu"
      : undefined;
  return <StatusBadge status={value} label={customLabel} />;
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className={styles.error} role="alert">
      <strong>Hệ thống tạm thời chưa thể kết nối</strong>
      <span>{message}</span>
    </div>
  );
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

    getPortfolioTemplates(controller.signal).then((data) => setTemplates(data.templates ?? [])).catch(() => setTemplates([]));

    return () => controller.abort();

  }, [reload]);



  async function mutate(action: () => Promise<unknown>, success: string) {

    setBusy(true); setError(""); setNotice("");

    try { await action(); setNotice(success); setReload((value) => value + 1); }

    catch (e) { setError(e instanceof Error ? e.message : "Không thể lưu dữ liệu."); }

    finally { setBusy(false); }

  }



  async function addHolding(event: FormEvent<HTMLFormElement>) {

    event.preventDefault();

    const form = new FormData(event.currentTarget);

    const payload = Object.fromEntries(form.entries());

    await mutate(() => createPortfolioHolding(payload), "Holding đã được lưu.");

    event.currentTarget.reset();

  }



  async function addTransaction(event: FormEvent<HTMLFormElement>) {

    event.preventDefault();

    const form = new FormData(event.currentTarget);

    const payload = Object.fromEntries(form.entries());

    await mutate(() => createManualTransaction(payload), "Manual transaction record đã được lưu; holdings không tự thay đổi.");

    event.currentTarget.reset();

  }



  async function saveTargets() {

    await mutate(() => putPortfolioTargets(targetDraft), "Target allocation đã lưu.");

  }



  async function saveDca(event: FormEvent<HTMLFormElement>) {

    event.preventDefault();

    await mutate(() => putPortfolioDca({ monthly_amount: dcaAmount, core_pct: corePct, satellite_pct: satellitePct }), "DCA plan đã lưu.");

  }



  async function saveSettings(event: FormEvent<HTMLFormElement>) {

    event.preventDefault();

    const toRatio = (value: string) => value.trim() === "" ? null : Number(value) / 100;

    await mutate(() => patchPortfolioSettings({

      single_name_limit: toRatio(singleLimit),

      sector_limit: toRatio(sectorLimit),

      material_change_threshold: toRatio(changeThreshold),

    }), "Portfolio thresholds đã lưu.");

  }



  async function applyTemplate(id: string) {

    await mutate(() => applyPortfolioTemplate(id), "Personal template đã áp dụng làm target có thể chỉnh sửa.");

  }



  const dashboardData = dashboard.state === "ready" ? dashboard.data : null;

  return <div className={styles.page}>
    <header className={styles.header}>
      <div>
        <h1>Quản lý danh mục đầu tư</h1>
        <p>Theo dõi danh mục thủ công · Không liên kết tài khoản chứng khoán · Không đặt lệnh.</p>
      </div>
      <button className={styles.refresh} onClick={() => setReload((value) => value + 1)} type="button">↻ <span>Làm mới</span></button>
    </header>

    {notice && <p className={styles.notice} role="status">{notice}</p>}{error && <ErrorState message={error} />}

    {dashboard.state === "loading" && (
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px", margin: "20px 0" }}>
        <SkeletonCard height={110} />
        <SkeletonCard height={110} />
        <SkeletonCard height={110} />
        <SkeletonCard height={110} />
      </div>
    )}

    {dashboard.state === "error" && <ErrorState message={dashboard.message} />}

    {dashboardData && <>
      <section className={styles.overview}>
        <div><span>Tổng giá trị danh mục</span><strong>{dashboardData.summary.holdings_count === 0 ? "0 VND" : money(dashboardData.summary.total_value)}</strong><Status value={dashboardData.summary.holdings_count === 0 ? "EMPTY" : dashboardData.summary.value_status} /></div>
        <div><span>Tổng giá vốn đầu tư</span><strong>{money(dashboardData.summary.cost_basis)}</strong><small>{dashboardData.summary.holdings_count} vị thế nắm giữ · {dashboardData.summary.currency}</small></div>
        <div><span>Lãi / lỗ chưa thực hiện</span><strong className={dashboardData.summary.unrealized_pnl !== null && dashboardData.summary.unrealized_pnl >= 0 ? styles.positive : styles.negative}>{dashboardData.summary.holdings_count === 0 ? "0 VND" : money(dashboardData.summary.unrealized_pnl)}</strong><small>{dashboardData.summary.holdings_count === 0 ? "Chưa có vị thế" : "Chỉ tính khi mọi holding có giá"}</small></div>
        <div>
          <span>Chất lượng dữ liệu</span>
          <strong>
            {dashboardData.status === "AVAILABLE"
              ? "Sẵn sàng"
              : dashboardData.status === "PARTIAL"
              ? "Dữ liệu một phần"
              : "Chưa có vị thế"}
          </strong>
          <small>Tính đến {dateLabel(dashboardData.as_of_date)}</small>
        </div>
      </section>

      {dashboardData.concentration.warnings
        .filter((w) => !String(w.code).endsWith("_LIMIT_UNSET"))
        .map((warning, index) => {
          const code = String(warning.code);
          let text = String(warning.message ?? "Cảnh báo danh mục");
          if (code === "SINGLE_NAME_CONCENTRATION") {
            text = `Cảnh báo tỷ trọng: Cổ phiếu ${warning.symbol} chiếm ${(Number(warning.weight) * 100).toFixed(1)}% danh mục (vượt hạn mức ${(Number(warning.limit) * 100).toFixed(0)}%).`;
          } else if (code === "SECTOR_CONCENTRATION") {
            text = `Cảnh báo tập trung ngành: Ngành ${warning.sector} chiếm ${(Number(warning.weight) * 100).toFixed(1)}% danh mục (vượt hạn mức ${(Number(warning.limit) * 100).toFixed(0)}%).`;
          } else if (code === "MISSING_PRICE") {
            text = "Một số vị thế chưa có giá thị trường canonical.";
          } else if (code === "STALE_PRICE") {
            text = "Dữ liệu giá của một số vị thế đã cũ hơn 7 ngày.";
          }
          return (
            <p className={styles.warning} key={`${code}-${index}`}>
              ⚠️ {text}
            </p>
          );
        })}

      <section className={styles.section}>
        <header><div><h2>Danh sách cổ phiếu</h2></div><span>{dashboardData.holdings.length} vị thế</span></header>
        {dashboardData.holdings.length === 0 ? <p className={styles.empty}>Danh mục hiện chưa có cổ phiếu nào. Nhập thông tin vị thế mua bên dưới để bắt đầu theo dõi tỷ trọng, lãi/lỗ và rủi ro (ghi nhận thủ công, không đồng bộ tài khoản chứng khoán).</p> : <>
          <div className={styles.tableWrap}><table><thead><tr><th>Mã CP</th><th>Vai trò</th><th>Khối lượng</th><th>Giá vốn bình quân</th><th>Thị giá</th><th>Giá trị thị trường</th><th>Lãi / Lỗ</th><th>Tỷ trọng</th><th>Ngày cập nhật giá</th><th></th></tr></thead><tbody>{dashboardData.holdings.map((holding) => <tr key={holding.id}>
            <td><strong>{holding.symbol}</strong><small>{holding.name} · {holding.sector ?? "Chưa phân ngành"}</small></td>
            <td><select aria-label={`${holding.symbol} role`} value={holding.role} disabled={busy} onChange={(event) => void mutate(() => patchPortfolioHolding(holding.id, { role: event.target.value }), "Đã cập nhật vai trò vị thế.")}><option value="UNASSIGNED">Chưa phân loại</option><option value="CORE">Cốt lõi</option><option value="SATELLITE">Vệ tinh</option></select></td>
            <td>{holding.quantity}</td><td>{money(holding.average_cost)}</td><td>{holding.current_price === null ? "—" : money(holding.current_price)} <Status value={holding.price_status} /></td>
            <td>{money(holding.market_value)}</td>
            <td className={holding.unrealized_pnl !== null && holding.unrealized_pnl > 0 ? styles.positive : holding.unrealized_pnl !== null && holding.unrealized_pnl < 0 ? styles.negative : undefined}>
              {money(holding.unrealized_pnl)}
            </td>
            <td>{pct(holding.current_weight)}</td><td>{dateLabel(holding.price_as_of)}</td>
            <td><button className={styles.iconButton} title={`Xóa ${holding.symbol}`} aria-label={`Xóa ${holding.symbol}`} onClick={() => void mutate(() => deletePortfolioHolding(holding.id), `Đã xóa ${holding.symbol}.`)}>×</button></td>
          </tr>)}</tbody></table></div>
          <div className={styles.mobileHoldings}>{dashboardData.holdings.map((holding) => <article key={holding.id}><header><div><strong>{holding.symbol}</strong><small>{holding.name}</small></div><Status value={holding.price_status} /></header><div className={styles.mobileGrid}><span>Vai trò <b>{holding.role}</b></span><span>Khối lượng <b>{holding.quantity}</b></span><span>Giá vốn <b>{money(holding.average_cost)}</b></span><span>Giá trị TT <b>{money(holding.market_value)}</b></span><span>Tỷ trọng <b>{pct(holding.current_weight)}</b></span><span>Ngày giá <b>{dateLabel(holding.price_as_of)}</b></span></div><button onClick={() => void mutate(() => deletePortfolioHolding(holding.id), `Đã xóa ${holding.symbol}.`)}>Xóa vị thế</button></article>)}</div>
        </>}

        <form className={styles.form} onSubmit={addHolding}>
          <h3>+ Thêm vị thế mua thủ công</h3>
          <label>Mã cổ phiếu<input name="symbol" required maxLength={20} placeholder="VD: FPT, MWG" /></label>
          <label>Khối lượng<input name="quantity" required type="number" min="0.00000001" step="0.00000001" placeholder="VD: 1000" /></label>
          <label>Giá vốn bình quân (VND)<input name="average_cost" required type="number" min="0.000001" step="0.000001" placeholder="VD: 125000" /></label>
          <label>Ngày khớp lệnh<input name="acquisition_date" required type="date" max={new Date(Date.now() + 7 * 3600 * 1000).toISOString().slice(0, 10)} /></label>
          <label>Vai trò danh mục<select name="role" defaultValue="UNASSIGNED"><option value="UNASSIGNED">Chưa phân loại</option><option value="CORE">Cốt lõi</option><option value="SATELLITE">Vệ tinh</option></select></label>
          <label>Khung thời gian đầu tư<select name="horizon" defaultValue=""><option value="">Chưa thiết lập</option><option value="MEDIUM_TERM">Trung hạn (1–12 tháng)</option><option value="LONG_TERM">Dài hạn (3–10 năm)</option></select></label>
          <label className={styles.notesField}>Ghi chú cá nhân<input name="notes" maxLength={2000} placeholder="Luận điểm hoặc ghi chú cá nhân..." /></label>
          <button disabled={busy} type="submit">+ Thêm vào danh mục</button>
        </form>
      </section>

      <div className={styles.twoColumn}>
        <div className={styles.card}>
          <div className={styles.cardHeader}><h3>Tỷ trọng hiện tại</h3><Status value={dashboardData.allocation.status} /></div>
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
              <h3 style={{ margin: "0 0 4px" }}>Theo nhóm ngành</h3>
              {dashboardData.allocation.sector.length ? dashboardData.allocation.sector.map((item) => (
                <div className={styles.barRow} key={item.sector}>
                  <span>{item.sector}</span>
                  <div><i style={{ width: `${Math.max(0, Math.min(100, item.weight * 100))}%` }} /></div>
                  <b>{pct(item.weight)}</b>
                </div>
              )) : <p className={styles.empty}>Chưa có vị thế để phân bổ theo ngành.</p>}

              <h3 style={{ margin: "10px 0 4px" }}>Cốt lõi / Vệ tinh</h3>
              {dashboardData.allocation.core_satellite.length ? dashboardData.allocation.core_satellite.map((item) => (
                <div className={styles.barRow} key={item.role}>
                  <span>{item.role === "CORE" ? "Cốt lõi" : item.role === "SATELLITE" ? "Vệ tinh" : "Chưa phân loại"}</span>
                  <div><i style={{ width: `${Math.max(0, Math.min(100, item.weight * 100))}%` }} /></div>
                  <b>{pct(item.weight)}</b>
                </div>
              )) : <p className={styles.empty}>Chưa có dữ liệu phân bổ vai trò.</p>}
            </div>
          </div>
          <p className={styles.sectionNote}>Độ phơi nhiễm rủi ro / nhân tố: {dashboardData.risk_exposure.status} · {dashboardData.factor_exposure.status}.</p>
        </div>

        <div className={styles.card}>
          <div className={styles.cardHeader}><h3>Đánh giá từng vị thế</h3>{fit.state === "ready" && <Status value={fit.data.status} />}</div>
          {fit.state === "loading" && <p className={styles.state}>Đang tính toán mức độ phù hợp…</p>}{fit.state === "error" && <ErrorState message={fit.message} />}
          {fit.state === "ready" && fit.data.items.length === 0 && <p className={styles.empty}>Thêm vị thế vào danh mục để hệ thống đánh giá mức độ phù hợp.</p>}
          {fit.state === "ready" && fit.data.items.map((item) => <article className={styles.fitRow} key={item.symbol}><header><strong>{item.symbol}</strong><Status value={item.status} /></header><p>Vai trò {item.portfolio_role} · Hiện tại {pct(item.current_weight)} · Mục tiêu {pct(item.target_weight)}</p><p>Cơ hội {item.opportunity_score ?? "—"} · Độ tin cậy {item.confidence} · Rủi ro {item.risk_score ?? "—"}</p><small>{item.note}</small></article>)}
        </div>
      </div>

      <div className={styles.twoColumn}>
        <div className={styles.card}>
          <div className={styles.cardHeader}><h3>Mục tiêu & hạn mức</h3>{targets.state === "ready" && <Status value={targets.data.status} />}</div>
          {targets.state === "error" && <ErrorState message={targets.message} />}
          {targets.state === "ready" && <>
            {targetDraft.map((target, index) => <div className={styles.targetRow} key={`${target.symbol}-${index}`}><input aria-label={`Mã mục tiêu ${index + 1}`} value={target.symbol} placeholder="Mã CK" onChange={(event) => setTargetDraft((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, symbol: event.target.value.toUpperCase() } : row))} /><input aria-label={`Tỷ trọng mục tiêu ${index + 1}`} type="number" min="0" max="100" step="0.01" value={(target.target_weight * 100).toFixed(2)} onChange={(event) => setTargetDraft((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, target_weight: Number(event.target.value) / 100 } : row))} /><span>%</span><button className={styles.iconButton} aria-label={`Xóa mục tiêu ${target.symbol}`} onClick={() => setTargetDraft((rows) => rows.filter((_, rowIndex) => rowIndex !== index))}>×</button></div>)}
            <button className={styles.secondaryButton} onClick={() => setTargetDraft((rows) => [...rows, { symbol: "", target_weight: 0 }])}>+ Thêm mục tiêu</button>
            <div className={styles.buttonRow}><button disabled={busy} onClick={() => void saveTargets()}>Lưu mục tiêu phân bổ</button>{templates.map((template) => <button className={styles.secondaryButton} disabled={busy} key={template.id} title={template.note} onClick={() => void applyTemplate(template.id)}>{template.label}</button>)}</div>
          </>}

          <form className={styles.thresholdForm} onSubmit={saveSettings}>
            <h3>Hạn mức cảnh báo rủi ro cá nhân</h3>
            <label>Hạn mức tối đa 1 cổ phiếu (%)<input type="number" min="0" max="100" step="0.1" value={singleLimit} onChange={(event) => setSingleLimit(event.target.value)} placeholder="Chưa cấu hình (VD: 25)" /></label>
            <label>Hạn mức tối đa 1 ngành (%)<input type="number" min="0" max="100" step="0.1" value={sectorLimit} onChange={(event) => setSectorLimit(event.target.value)} placeholder="Chưa cấu hình (VD: 40)" /></label>
            <label>Ngưỡng cảnh báo biến động (%)<input type="number" min="0" max="100" step="0.1" value={changeThreshold} onChange={(event) => setChangeThreshold(event.target.value)} placeholder="Chưa cấu hình (VD: 10)" /></label>
            <button disabled={busy} type="submit">Lưu cấu hình hạn mức</button>
          </form>
        </div>

        <div className={styles.card}>
          <div className={styles.cardHeader}><h3>Kế hoạch tích lũy hàng tháng (DCA)</h3>{dca.state === "ready" && <Status value={dca.data.status} />}</div>
          {dca.state === "error" && <ErrorState message={dca.message} />}
          <form className={styles.dcaForm} onSubmit={saveDca}>
            <label>Số tiền tích lũy hàng tháng (VND)<input type="number" min="100000" step="50000" value={dcaAmount} onChange={(event) => setDcaAmount(Number(event.target.value))} required /></label>
            <label>Tỷ trọng cốt lõi (%)<input type="number" min="0" max="100" step="1" value={Math.round(corePct * 100)} onChange={(event) => setCorePct(Number(event.target.value) / 100)} required /></label>
            <label>Tỷ trọng vệ tinh (%)<input type="number" min="0" max="100" step="1" value={Math.round(satellitePct * 100)} onChange={(event) => setSatellitePct(Number(event.target.value) / 100)} required /></label>
            <button disabled={busy} type="submit">Lưu kế hoạch DCA</button>
          </form>
          {dca.state === "ready" && <div className={styles.dcaResult}><p>Cốt lõi: {pct(dca.data.core_pct)} · Vệ tinh: {pct(dca.data.satellite_pct)} · Dự phòng: {pct(dca.data.reserve_pct)}</p><strong>Chưa phân bổ / Dự phòng: {money(dca.data.unused_or_satellite_reserve)}</strong>{dca.data.routes.map((route) => <p key={route.symbol}>{route.symbol} · {money(route.amount)} · mục tiêu {pct(route.target_weight)} · {route.status}</p>)}<small>{dca.data.note}</small></div>}
          {dca.state === "error" && <p className={styles.sectionNote}>Số tiền ban đầu là cấu hình mẫu; hãy bấm Lưu để ghi nhận vĩnh viễn.</p>}
          <button className={styles.secondaryButton} disabled={busy} onClick={() => void mutate(() => createPortfolioSnapshot(), "Đã lưu snapshot phân bổ danh mục.")}>Lưu mốc quan sát phân bổ (Snapshot)</button>
        </div>
      </div>

      <section className={styles.section}>
        <header><div><h2>Lịch sử giao dịch</h2></div><span>Ghi nhận thủ công · Không đồng bộ tài khoản chứng khoán</span></header>
        <form className={styles.form} onSubmit={addTransaction}>
          <label>Mã cổ phiếu<input name="symbol" required placeholder="VD: FPT" /></label><label>Loại giao dịch<select name="transaction_type"><option value="BUY">Mua</option><option value="SELL">Bán</option><option value="DIVIDEND">Cổ tức</option><option value="FEE">Phí</option></select></label>
          <label>Khối lượng<input name="quantity" required type="number" min="0.00000001" step="0.00000001" placeholder="VD: 500" /></label><label>Đơn giá (VND)<input name="unit_price" required type="number" min="0.000001" step="0.000001" placeholder="VD: 130000" /></label>
          <label>Ngày giao dịch<input name="transaction_date" required type="date" max={new Date(Date.now() + 7 * 3600 * 1000).toISOString().slice(0, 10)} /></label><label>Ghi chú<input name="notes" placeholder="Ghi chú giao dịch..." /></label><button disabled={busy} type="submit">+ Ghi nhận giao dịch</button>
        </form>
        {transactions.state === "error" && <ErrorState message={transactions.message} />}
        {transactions.state === "ready" && transactions.data.length === 0 && <p className={styles.empty}>Chưa có giao dịch thủ công nào được ghi nhận.</p>}
        {transactions.state === "ready" && transactions.data.map((transaction, index) => <p className={styles.transactionRow} key={String(transaction.id ?? index)}>{String(transaction.transaction_date)} · {String(transaction.symbol)} · {String(transaction.transaction_type)} · KL: {Number(transaction.quantity).toLocaleString("vi-VN")} CP · Đơn giá: {money(Number(transaction.unit_price))} · THỦ CÔNG</p>)}
      </section>
    </>}
  </div>;

}
