"use client";

import { useEffect, useState } from "react";
import { SkeletonCard } from "@/components/ui/skeleton";
import { useLocale, translateQuantEnum, type AppLocale } from "@/lib/i18n";
import styles from "./page.module.css";

interface ValuationRange {
  bear: number;
  base: number;
  bull: number;
}

interface CompositeFairValue {
  range: ValuationRange;
  confidence: string;
  method_disagreement?: boolean;
  disagreement_reason?: string;
}

interface ValuationMethodItem {
  method: string;
  fair_value: {
    base: number;
    bear?: number;
    bull?: number;
  };
  weight: number;
}

interface ValuationResponse {
  symbol: string;
  price_as_of: number;
  composite_fair_value: CompositeFairValue;
  methods: ValuationMethodItem[];
}

interface FactorItem {
  name: string;
  score: number;
  drivers: string[];
}

interface FactorResponse {
  symbol: string;
  quality: FactorItem;
  growth: FactorItem;
  value: FactorItem;
  dividend: FactorItem;
  momentum: FactorItem;
  defensive: FactorItem;
  cyclical: FactorItem;
  conflicts: string[];
}

function translateMethodName(method: string, locale: AppLocale): string {
  const isEn = locale === "en";
  const m = method.trim().toLowerCase();
  if (m.includes("dcf") || m.includes("cash flow")) {
    return isEn ? "DCF (Discounted Cash Flow)" : "Chiết khấu dòng tiền (DCF)";
  }
  if (m.includes("p/e") || m.includes("relative_pe") || m.includes("pe")) {
    return isEn ? "P/E Relative Multiple" : "Bội số định giá P/E";
  }
  if (m.includes("p/b") || m.includes("relative_pb") || m.includes("pb")) {
    return isEn ? "P/B Relative Multiple" : "Bội số giá trị sổ sách P/B";
  }
  if (m.includes("graham")) {
    return isEn ? "Benjamin Graham Net-Net" : "Mô hình định giá Graham";
  }
  if (m.includes("dividend") || m.includes("ddm")) {
    return isEn ? "Dividend Discount Model (DDM)" : "Chiết khấu cổ tức (DDM)";
  }
  if (m.includes("asset")) {
    return isEn ? "Asset-Based Revaluation" : "Định giá lại tài sản thuần";
  }
  return method;
}

function translateFactorName(key: string, rawName: string, locale: AppLocale): string {
  const isEn = locale === "en";
  const map: Record<string, { vi: string; en: string }> = {
    quality: { vi: "Chất lượng hoạt động", en: "Operational Quality" },
    growth: { vi: "Tăng trưởng doanh thu & LN", en: "Fundamental Growth" },
    value: { vi: "Định giá hấp dẫn", en: "Valuation Attractiveness" },
    dividend: { vi: "Tỷ suất cổ tức", en: "Dividend Yield & Safety" },
    momentum: { vi: "Động lượng giá & dòng tiền", en: "Price & Flow Momentum" },
    defensive: { vi: "Tính chất phòng thủ", en: "Defensive & Low Beta" },
    cyclical: { vi: "Tính chu kỳ kinh doanh", en: "Business Cyclicality" },
  };
  if (map[key]) {
    return isEn ? map[key].en : map[key].vi;
  }
  return rawName;
}

export default function ValuationDashboard() {
  const { locale, t } = useLocale();
  const numLocale = locale === "en" ? "en-US" : "vi-VN";

  const [symbol, setSymbol] = useState("FPT");
  const [valuationData, setValuationData] = useState<ValuationResponse | null>(null);
  const [factorData, setFactorData] = useState<FactorResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const SYMBOLS = ["FPT", "VCB", "MBB", "MWG", "HPG"];

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError("");
      try {
        const valRes = await fetch(`/api/v1/valuation/${symbol}`);
        if (!valRes.ok) throw new Error(t("Không thể tải dữ liệu định giá.", "Failed to fetch valuation data."));
        const valData = (await valRes.json()) as ValuationResponse;

        const facRes = await fetch(`/api/v1/factors/${symbol}`);
        if (!facRes.ok) throw new Error(t("Không thể tải hồ sơ nhân tố.", "Failed to fetch factor profile."));
        const facData = (await facRes.json()) as FactorResponse;

        setValuationData(valData);
        setFactorData(facData);
      } catch (err: unknown) {
        setError(
          err instanceof Error
            ? err.message
            : t("Đã xảy ra lỗi không xác định.", "An unknown error occurred.")
        );
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [symbol, t]);

  const factorList = factorData
    ? [
        { key: "quality", ...factorData.quality },
        { key: "growth", ...factorData.growth },
        { key: "value", ...factorData.value },
        { key: "dividend", ...factorData.dividend },
        { key: "momentum", ...factorData.momentum },
        { key: "defensive", ...factorData.defensive },
        { key: "cyclical", ...factorData.cyclical },
      ]
    : [];

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>
            {t("Mô hình định lượng · Phân tích cơ bản", "Quantitative Models · Fundamental Valuation")}
          </p>
          <h1 className={styles.title}>
            {t("Mô hình định giá & phân tích nhân tố", "Valuation Models & Factor Profiling")}
          </h1>
        </div>
        <div>
          <select
            aria-label={t("Chọn mã cổ phiếu", "Select ticker symbol")}
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className={styles.symbolSelect}
          >
            {SYMBOLS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </header>

      {error && <div className="text-danger" style={{ marginBottom: "20px" }}>{error}</div>}

      {loading ? (
        <div className={styles.mainGrid}>
          <SkeletonCard height={320} />
          <SkeletonCard height={320} />
        </div>
      ) : valuationData && factorData ? (
        <div className={styles.mainGrid}>
          {/* VALUATION PANEL */}
          <div className={`card ${styles.panelCard}`}>
            <h2 className="card-title">{t("Định giá cổ phiếu (VND)", "Equity Valuation (VND)")}</h2>
            <div style={{ marginBottom: "15px", fontSize: "1.2rem" }}>
              {t("Thị giá hiện tại: ", "Current Market Price: ")}
              <strong className="tabular-nums">
                {valuationData.price_as_of.toLocaleString(numLocale)} VND
              </strong>
            </div>

            <div style={{ marginBottom: "20px" }}>
              <div style={{ marginBottom: "5px", color: "var(--text-secondary)" }}>
                {t("Khoảng giá trị hợp lý:", "Fair Value Interval:")}
              </div>
              <div className={styles.rangeBox}>
                <div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    {t("Kịch bản thận trọng (Bear)", "Bear Case")}
                  </div>
                  <strong className="text-danger tabular-nums">
                    {Math.round(valuationData.composite_fair_value.range.bear).toLocaleString(numLocale)}
                  </strong>
                </div>
                <div className={styles.rangeColCenter}>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    {t("Kịch bản cơ sở (Base)", "Base Case")}
                  </div>
                  <strong className="tabular-nums">
                    {Math.round(valuationData.composite_fair_value.range.base).toLocaleString(numLocale)}
                  </strong>
                </div>
                <div className={styles.rangeColRight}>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    {t("Kịch bản khả quan (Bull)", "Bull Case")}
                  </div>
                  <strong className="text-success tabular-nums">
                    {Math.round(valuationData.composite_fair_value.range.bull).toLocaleString(numLocale)}
                  </strong>
                </div>
              </div>
            </div>

            <div style={{ marginBottom: "15px" }}>
              <div style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                {t("Độ tin cậy: ", "Model Confidence: ")}
                <strong style={{ color: "var(--text-primary)" }}>
                  {translateQuantEnum(valuationData.composite_fair_value.confidence, locale)}
                </strong>
              </div>
              {valuationData.composite_fair_value.method_disagreement && (
                <div className="text-danger" style={{ fontSize: "0.85rem", marginTop: "4px" }}>
                  {t("Độ lệch phương pháp: ", "Method Divergence: ")}
                  {valuationData.composite_fair_value.disagreement_reason}
                </div>
              )}
            </div>

            <h3 style={{ fontSize: "1.1rem", marginBottom: "10px", marginTop: "20px", color: "var(--text-primary)" }}>
              {t("Chi tiết từng phương pháp", "Valuation Method Breakdown")}
            </h3>
            <div className={styles.tableWrap}>
              <table className={styles.methodTable}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border-color)", textAlign: "left" }}>
                    <th style={{ padding: "8px 0" }}>{t("Phương pháp", "Methodology")}</th>
                    <th style={{ padding: "8px 0" }}>{t("Giá trị hợp lý (Cơ sở)", "Fair Value (Base)")}</th>
                    <th style={{ padding: "8px 0" }}>{t("Tỷ trọng", "Weight")}</th>
                  </tr>
                </thead>
                <tbody>
                  {valuationData.methods.map((m, idx) => (
                    <tr key={idx} style={{ borderBottom: "1px solid var(--border-color)" }}>
                      <td style={{ padding: "8px 0" }}>{translateMethodName(m.method, locale)}</td>
                      <td style={{ padding: "8px 0" }} className="tabular-nums">
                        {Math.round(m.fair_value.base).toLocaleString(numLocale)}
                      </td>
                      <td style={{ padding: "8px 0" }} className="tabular-nums">
                        {(m.weight * 100).toFixed(0)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* FACTOR PANEL */}
          <div className={`card ${styles.panelCard}`}>
            <h2 className="card-title">{t("Hồ sơ nhân tố đầu tư", "Investment Factor Profile")}</h2>

            <div className={styles.factorGrid}>
              {factorList.map((f, idx) => {
                const isOrphanLast =
                  factorList.length % 3 === 1 && idx === factorList.length - 1;
                return (
                  <div
                    key={f.key}
                    className={`${styles.factorItem} ${isOrphanLast ? styles.factorCardFull : ""}`}
                  >
                    <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                      {translateFactorName(f.key, f.name, locale)}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <strong style={{ fontSize: "1.2rem" }} className="tabular-nums">
                        {Math.round(f.score)}
                      </strong>
                      <div style={{ flex: 1, height: "4px", background: "var(--border-color)", borderRadius: "2px", overflow: "hidden" }}>
                        <div
                          style={{
                            width: `${Math.min(100, Math.max(0, f.score))}%`,
                            height: "100%",
                            background: f.score > 70 ? "var(--accent-color)" : f.score < 40 ? "#ef4444" : "#8b5cf6",
                          }}
                        />
                      </div>
                    </div>
                    {f.drivers && f.drivers.length > 0 && (
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                        {f.drivers[0]}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {factorData.conflicts && factorData.conflicts.length > 0 && (
              <div style={{ marginTop: "14px", background: "rgba(239, 68, 68, 0.1)", padding: "10px", borderRadius: "6px", border: "1px solid #ef4444" }}>
                <strong style={{ color: "#ef4444", fontSize: "0.9rem" }}>
                  {t("Xung đột giữa các nhân tố:", "Factor Conflicts & Divergence:")}
                </strong>
                <ul style={{ margin: "5px 0 0 20px", padding: 0, fontSize: "0.85rem", color: "var(--text-primary)" }}>
                  {factorData.conflicts.map((c: string, i: number) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
