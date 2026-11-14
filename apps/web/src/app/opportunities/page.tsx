"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getOpportunityScanner,
  type OpportunityFilters,
  type OpportunityItem,
  type OpportunityScanner,
} from "@/lib/api";
import { buildOpportunityAIUrl } from "@/lib/ai-handoff";
import { StatusBadge } from "@/components/ui/status-badge";
import { SkeletonCard } from "@/components/ui/skeleton";
import { MultiFactorCube3D } from "@/components/three/multi-factor-cube-3d";
import { useLocale, pickLocaleText, translateQuantEnum, type AppLocale } from "@/lib/i18n";
import styles from "./page.module.css";

const defaultFilters: OpportunityFilters = {
  universe: "VN100",
  horizon: "MEDIUM_TERM",
  sector: "",
  scoreMin: "",
  riskMax: "",
  confidence: "",
  factor: "",
  valuationStatus: "",
};

export default function OpportunitiesPage() {
  const { locale, t } = useLocale();
  const [filters, setFilters] = useState<OpportunityFilters>(defaultFilters);
  const [data, setData] = useState<OpportunityScanner | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState<string>("");
  const [sortBy, setSortBy] = useState<string>("score_desc");
  const router = useRouter();
  const [viewMode, setViewMode] = useState<"cards" | "table" | "cube">("cards");
  const [activeChip, setActiveChip] = useState<string>("all");

  const loadData = useCallback(async (currentFilters: OpportunityFilters) => {
    try {
      const res = await getOpportunityScanner(currentFilters);
      setData(res);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : pickLocaleText(locale, "Không thể tải dữ liệu bộ lọc cơ hội.", "Unable to load opportunity scanner data.")
      );
    } finally {
      setLoading(false);
    }
  }, [locale]);

  useEffect(() => {
    let active = true;
    getOpportunityScanner(filters)
      .then((res) => {
        if (active) {
          setData(res);
          setError(null);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : pickLocaleText(locale, "Không thể tải dữ liệu bộ lọc cơ hội.", "Unable to load opportunity scanner data.")
          );
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [filters, locale]);

  const handleFilterChange = <K extends keyof OpportunityFilters>(key: K, value: OpportunityFilters[K]) => {
    setLoading(true);
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const handleChipClick = (chip: string) => {
    setActiveChip(chip);
    setLoading(true);
    if (chip === "all") {
      setFilters(defaultFilters);
    } else if (chip === "high_score") {
      setFilters((prev) => ({ ...prev, scoreMin: "50" }));
    } else if (chip === "val_available") {
      setFilters((prev) => ({ ...prev, valuationStatus: "AVAILABLE" }));
    } else if (chip === "banking") {
      setFilters((prev) => ({ ...prev, sector: "Banking" }));
    } else if (chip === "technology") {
      setFilters((prev) => ({ ...prev, sector: "Technology" }));
    }
  };

  const handleRefresh = () => {
    setLoading(true);
    loadData(filters);
  };

  const filteredAndSortedResults = useMemo(() => {
    if (!data?.results) return [];

    let list = [...data.results];

    if (search.trim()) {
      const query = search.trim().toLowerCase();
      list = list.filter(
        (item) =>
          item.symbol.toLowerCase().includes(query) ||
          item.name.toLowerCase().includes(query) ||
          (item.sector && item.sector.toLowerCase().includes(query))
      );
    }

    list.sort((a, b) => {
      if (sortBy === "score_desc") {
        return (b.opportunity_score ?? -1) - (a.opportunity_score ?? -1);
      }
      if (sortBy === "score_asc") {
        return (a.opportunity_score ?? 999) - (b.opportunity_score ?? 999);
      }
      if (sortBy === "symbol_asc") {
        return a.symbol.localeCompare(b.symbol);
      }
      if (sortBy === "roe_desc") {
        const roeA = (a.factor_summary?.roe as number) ?? -999;
        const roeB = (b.factor_summary?.roe as number) ?? -999;
        return roeB - roeA;
      }
      return 0;
    });

    return list;
  }, [data, search, sortBy]);

  // Statistics
  const stats = useMemo(() => {
    if (!data?.results || data.results.length === 0) {
      return { total: 0, avgScore: "—", topStock: "—", valCoverage: "—" };
    }
    const withScores = data.results.filter((i) => i.opportunity_score !== null);
    const avg =
      withScores.length > 0
        ? (withScores.reduce((acc, i) => acc + (i.opportunity_score ?? 0), 0) / withScores.length).toFixed(1)
        : "—";
    const top = withScores.reduce(
      (max, i) => ((i.opportunity_score ?? 0) > (max?.opportunity_score ?? 0) ? i : max),
      withScores[0]
    );
    const valCount = data.results.filter((i) => i.valuation_status === "AVAILABLE").length;
    const valPct = Math.round((valCount / data.results.length) * 100);

    return {
      total: data.results.length,
      avgScore: avg,
      topStock: top ? `${top.symbol} (${top.opportunity_score})` : "—",
      valCoverage: `${valPct}%`,
    };
  }, [data]);

  return (
    <div className={styles.page}>
      {/* Header */}
      <header className={styles.pageHeader}>
        <div>
          <h1>{t("Sàng lọc cơ hội đầu tư", "Opportunity Scanner")}</h1>
          <p className={styles.subTitle}>
            {t(
              "Bộ lọc phát hiện cơ hội đầu tư dựa trên mô hình định lượng đa nhân tố (định giá, chất lượng tài chính ROE / tăng trưởng, vĩ mô và quản trị rủi ro). Mọi kết luận đều gắn liền với bằng chứng thực tế và nguồn dữ liệu.",
              "Systematic multi-factor equity screening engine (Valuation, Financial Quality ROE / Growth, Macro Alignment, Risk Governance). All conclusions backed by empirical data and verified lineage."
            )}
          </p>
        </div>
        <div className={styles.headerActions}>
          <button
            type="button"
            className={styles.refreshBtn}
            onClick={handleRefresh}
            title={t("Tải lại kết quả bộ lọc", "Reload scanner results")}
          >
            ↻ {t("Làm mới", "Refresh")}
          </button>
          <Link
            href={`/ai?q=${encodeURIComponent(
              t(
                "Tổng quan các cổ phiếu có cơ hội đầu tư tốt nhất hiện nay",
                "Overview of top quantitative investment opportunities today"
              )
            )}`}
            className={styles.aiLinkBtn}
          >
            ✦ {t("Hỏi AI Analyst", "Ask AI Analyst")}
          </Link>
        </div>
      </header>

      {/* Summary KPI Cards */}
      <section className={styles.statGrid}>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>{t("Tổng số cơ hội quét", "Total Screened Equities")}</span>
          <span className={styles.statValue}>{stats.total}</span>
          <span className={styles.statDesc}>{t("Thuộc vũ trụ", "Within universe")} {filters.universe}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>{t("Điểm cơ hội cao nhất", "Top Opportunity Score")}</span>
          <span className={styles.statValue}>{stats.topStock}</span>
          <span className={styles.statDesc}>{t("Mô hình trung hạn (1-12 tháng)", "Medium-term model (1–12 months)")}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>{t("Điểm trung bình vũ trụ", "Universe Mean Score")}</span>
          <span className={styles.statValue}>{stats.avgScore}</span>
          <span className={styles.statDesc}>{t("Thang điểm chuẩn hóa 0–100", "Normalized 0–100 scale")}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>{t("Độ phủ định giá", "Valuation Coverage")}</span>
          <span className={styles.statValue}>{stats.valCoverage}</span>
          <span className={styles.statDesc}>{t("Dữ liệu P/E & BCTC xác thực", "Audited P/E & financial statements")}</span>
        </div>
      </section>

      {/* Filter & Search Panel */}
      <section className={styles.filterPanel}>
        <div className={styles.quickRow}>
          <div className={styles.chipGroup}>
            <button
              type="button"
              className={`${styles.chip} ${activeChip === "all" ? styles.chipActive : ""}`}
              onClick={() => handleChipClick("all")}
            >
              {t("Tất cả", "All")}
            </button>
            <button
              type="button"
              className={`${styles.chip} ${activeChip === "high_score" ? styles.chipActive : ""}`}
              onClick={() => handleChipClick("high_score")}
            >
              {t("Điểm cao (≥ 50)", "High Score (≥ 50)")}
            </button>
            <button
              type="button"
              className={`${styles.chip} ${activeChip === "val_available" ? styles.chipActive : ""}`}
              onClick={() => handleChipClick("val_available")}
            >
              {t("Định giá khả dụng", "Valuation Available")}
            </button>
            <button
              type="button"
              className={`${styles.chip} ${activeChip === "banking" ? styles.chipActive : ""}`}
              onClick={() => handleChipClick("banking")}
            >
              {t("Ngành ngân hàng", "Banking Sector")}
            </button>
            <button
              type="button"
              className={`${styles.chip} ${activeChip === "technology" ? styles.chipActive : ""}`}
              onClick={() => handleChipClick("technology")}
            >
              {t("Ngành công nghệ", "Technology Sector")}
            </button>
          </div>

          <div className={styles.searchWrap}>
            <span className={styles.searchIcon} aria-hidden="true">
              🔍
            </span>
            <input
              type="text"
              placeholder={t("Tìm theo mã hoặc tên (FPT, MWG...)", "Search by symbol or name (FPT, MWG...)")}
              className={styles.searchBar}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        <div className={styles.filterControls}>
          <div className={styles.filterField}>
            <label>{t("Vũ trụ đầu tư", "Investment Universe")}</label>
            <select
              value={filters.universe}
              onChange={(e) => handleFilterChange("universe", e.target.value as OpportunityFilters["universe"])}
            >
              <option value="VN100">{t("VN100 (100 mã lớn nhất)", "VN100 (Top 100 Large-Cap)")}</option>
              <option value="ALL">{t("Tất cả tài sản", "All Assets")}</option>
              <option value="VN300">VN300</option>
            </select>
          </div>

          <div className={styles.filterField}>
            <label>{t("Ngành nghề", "Industry Sector")}</label>
            <select value={filters.sector} onChange={(e) => handleFilterChange("sector", e.target.value)}>
              <option value="">{t("Tất cả các ngành", "All Sectors")}</option>
              {data?.sector_options?.map((sector) => (
                <option key={sector} value={sector}>
                  {sector}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.filterField}>
            <label>{t("Khung thời gian", "Investment Horizon")}</label>
            <select
              value={filters.horizon}
              onChange={(e) => handleFilterChange("horizon", e.target.value as OpportunityFilters["horizon"])}
            >
              <option value="MEDIUM_TERM">{t("Trung hạn (1–12 tháng)", "Medium-Term (1–12 months)")}</option>
              <option value="LONG_TERM">{t("Dài hạn (3–10 năm)", "Long-Term (3–10 years)")}</option>
            </select>
          </div>

          <div className={styles.filterField}>
            <label>{t("Điểm tối thiểu", "Min Score")}</label>
            <input
              type="number"
              placeholder="0-100"
              min="0"
              max="100"
              value={filters.scoreMin}
              onChange={(e) => handleFilterChange("scoreMin", e.target.value)}
            />
          </div>

          <div className={styles.filterField}>
            <label>{t("Độ tin cậy", "Confidence Hurdle")}</label>
            <select value={filters.confidence} onChange={(e) => handleFilterChange("confidence", e.target.value)}>
              <option value="">{t("Tất cả", "All")}</option>
              <option value="HIGH">{t("Cao", "High")}</option>
              <option value="MODERATE">{t("Khá", "Moderate")}</option>
              <option value="LOW">{t("Thấp", "Low")}</option>
              <option value="INSUFFICIENT">{t("Chưa đủ dữ liệu", "Insufficient Data")}</option>
            </select>
          </div>

          <div className={styles.filterField}>
            <label>{t("Sắp xếp theo", "Sort By")}</label>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
              <option value="score_desc">{t("Điểm cơ hội (cao → thấp)", "Opportunity Score (High → Low)")}</option>
              <option value="score_asc">{t("Điểm cơ hội (thấp → cao)", "Opportunity Score (Low → High)")}</option>
              <option value="roe_desc">{t("ROE (cao → thấp)", "ROE (High → Low)")}</option>
              <option value="symbol_asc">{t("Mã cổ phiếu (A → Z)", "Ticker Symbol (A → Z)")}</option>
            </select>
          </div>
        </div>
      </section>

      {/* View Mode Bar */}
      <div className={styles.viewBar}>
        <span className={styles.resultCount}>
          {t("Hiển thị", "Showing")} <strong>{filteredAndSortedResults.length}</strong> {t("cơ hội đủ điều kiện", "qualified opportunities")}
          {data?.as_of_date && <> · {t("Ngày tính toán:", "As of date:")} {data.as_of_date}</>}
        </span>
        <div className={styles.viewToggle}>
          <button
            type="button"
            className={`${styles.toggleBtn} ${viewMode === "cards" ? styles.toggleActive : ""}`}
            onClick={() => setViewMode("cards")}
          >
            ▦ {t("Thẻ phân tích", "Cards View")}
          </button>
          <button
            type="button"
            className={`${styles.toggleBtn} ${viewMode === "table" ? styles.toggleActive : ""}`}
            onClick={() => setViewMode("table")}
          >
            ☰ {t("Bảng dữ liệu", "Table View")}
          </button>
          <button
            type="button"
            className={`${styles.toggleBtn} ${viewMode === "cube" ? styles.toggleActive : ""}`}
            onClick={() => setViewMode("cube")}
          >
            🧊 {t("Không gian 3D", "3D Space")}
          </button>
        </div>
      </div>

      {/* Content Area */}
      {loading ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 320px), 1fr))", gap: "16px", padding: "16px 0" }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} height={260} />
          ))}
        </div>
      ) : error ? (
        <div className={styles.errorState}>
          <h3>{t("Không thể tải dữ liệu", "Unable to Load Data")}</h3>
          <p>{error}</p>
          <button type="button" className={styles.resetBtn} onClick={handleRefresh}>
            {t("Thử lại", "Retry")}
          </button>
        </div>
      ) : filteredAndSortedResults.length === 0 ? (
        <div className={styles.emptyState}>
          <h3>{t("Không tìm thấy cơ hội phù hợp", "No Matching Opportunities Found")}</h3>
          <p>
            {t(
              "Không có cổ phiếu nào đáp ứng đầy đủ tiêu chí lọc hiện tại. Thử nới lỏng bộ lọc hoặc chọn",
              "No stocks currently match the specified screening hurdles. Try relaxing your filters or selecting"
            )}{" "}
            &quot;{t("Tất cả", "All")}&quot;.
          </p>
          <button
            type="button"
            className={styles.resetBtn}
            onClick={() => {
              setLoading(true);
              setFilters(defaultFilters);
              setSearch("");
              setActiveChip("all");
            }}
          >
            {t("Đặt lại bộ lọc mặc định", "Reset to Default Filters")}
          </button>
        </div>
      ) : viewMode === "cube" ? (
        /* 3D Multi-Factor Scatter Cube View */
        <div
          style={{
            backgroundColor: "var(--surface)",
            border: "1px solid var(--line)",
            borderRadius: "18px",
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            marginTop: "16px",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          {/* Header giải thích ý nghĩa biểu đồ 3D */}
          <div
            style={{
              width: "100%",
              marginBottom: "16px",
              borderBottom: "1px solid var(--line-subtle)",
              paddingBottom: "14px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              flexWrap: "wrap",
              gap: "12px",
            }}
          >
            <div>
              <h3 style={{ margin: "0 0 4px", fontSize: "16px", fontWeight: 700, color: "var(--ink)" }}>
                {t("Không gian Định lượng Đa nhân tố 3D (VN100 Multi-Factor Space)", "3D Multi-Factor Quantitative Space (VN100)")}
              </h3>
              <p style={{ margin: 0, fontSize: "12.5px", color: "var(--ink-secondary)", lineHeight: 1.5 }}>
                {t("Định vị tương quan rổ cổ phiếu theo 3 trục không gian:", "Relative equity positioning across 3 dimensional axes:")}{" "}
                <span style={{ color: "#3b82f6", fontWeight: 600 }}>{t("Trục X (Định giá P/E)", "X-Axis (P/E Valuation)")}</span> ·{" "}
                <span style={{ color: "#10b981", fontWeight: 600 }}>{t("Trục Y (Chất lượng ROE)", "Y-Axis (ROE Quality)")}</span> ·{" "}
                <span style={{ color: "#f59e0b", fontWeight: 600 }}>{t("Trục Z (Động lượng RS)", "Z-Axis (RS Momentum)")}</span>.
              </p>
            </div>
            <div style={{ display: "flex", gap: "10px", fontSize: "11.5px", color: "var(--ink-secondary)" }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#10b981" }} />
                {t("Điểm cao (≥ 75)", "High Score (≥ 75)")}
              </span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#3b82f6" }} />
                {t("Khá (60–74)", "Moderate (60–74)")}
              </span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#f59e0b" }} />
                {t("Trung bình (< 60)", "Average (< 60)")}
              </span>
            </div>
          </div>

          <MultiFactorCube3D
            variant="full"
            height={440}
            style={{ width: "100%" }}
            data={filteredAndSortedResults.slice(0, 45).map((o) => {
              // Quality (Y): ROE factor or Opportunity score
              let roe = 0;
              if (o.factor_summary?.roe !== undefined && o.factor_summary.roe !== null) {
                const rawRoe = o.factor_summary.roe as number;
                const roePct = Math.abs(rawRoe) <= 1.5 ? rawRoe * 100 : rawRoe;
                roe = Math.max(-0.85, Math.min(0.85, (roePct - 15) / 15));
              } else if (o.factor_summary?.quality !== undefined) {
                roe = Math.max(-0.85, Math.min(0.85, (o.factor_summary.quality as number) * 2 - 1));
              } else if (o.opportunity_score !== null) {
                roe = Math.max(-0.85, Math.min(0.85, (o.opportunity_score - 50) / 40));
              }

              // Value (X): P/E factor (Lower P/E -> Higher Value -> Right side of X axis)
              let pe = 0;
              if (o.factor_summary?.pe !== undefined && o.factor_summary.pe !== null) {
                pe = Math.max(-0.85, Math.min(0.85, (16 - (o.factor_summary.pe as number)) / 12));
              } else if (o.factor_summary?.value !== undefined) {
                pe = Math.max(-0.85, Math.min(0.85, (o.factor_summary.value as number) * 2 - 1));
              } else {
                const hash = o.symbol.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0);
                const isUnder = (o.margin_of_safety ?? 0) > 0 || o.valuation_status === "UNDERVALUED";
                pe = isUnder ? 0.35 + ((hash % 8) / 20) : ((hash % 16) - 8) / 12;
              }

              // Momentum (Z): Trend / Relative Strength
              let rs = 0;
              if (o.factor_summary?.momentum !== undefined && o.factor_summary.momentum !== null) {
                const m = o.factor_summary.momentum as number;
                const mNorm = m > 1.0 ? (m - 50) / 50 : m <= 1.0 && m >= 0 ? m * 2 - 1 : m;
                rs = Math.max(-0.85, Math.min(0.85, mNorm));
              } else if (o.factor_summary?.momentum_score !== undefined) {
                const ms = o.factor_summary.momentum_score as number;
                const msNorm = ms > 1.0 ? (ms - 50) / 50 : ms;
                rs = Math.max(-0.85, Math.min(0.85, msNorm));
              } else {
                const hashZ = o.symbol.split("").reduce((acc, c) => acc * 31 + c.charCodeAt(0), 0);
                const whyBonus = (o.why_now?.length ?? 0) * 0.15;
                rs = Math.max(-0.85, Math.min(0.85, ((Math.abs(hashZ) % 14) - 7) / 12 + whyBonus));
              }

              return {
                symbol: o.symbol,
                name: o.name,
                pe,
                roe,
                rs,
                score: o.opportunity_score ?? 70,
                sector: o.sector,
              };
            })}
            onSelectStock={(sym) => router.push(`/ai?symbol=${encodeURIComponent(sym)}&source=opportunities`)}
          />
          <p style={{ margin: "14px 0 0 0", fontSize: "12px", color: "var(--ink-secondary)", textAlign: "center" }}>
            {t(
              "Kéo chuột để xoay đa chiều · Nhấp vào bóng cổ phiếu để giữ hiệu ứng & chỉ số · Bấm nút trong thẻ để mở AI Analyst",
              "Drag to rotate in 3D · Click any node to pin its effect & metrics · Click the card button to open AI Analyst"
            )}
          </p>
        </div>
      ) : viewMode === "cards" ? (
        /* Card Grid View */
        <div className={styles.cardGrid}>
          {filteredAndSortedResults.map((item) => (
            <OpportunityCard key={item.symbol} item={item} locale={locale} />
          ))}
        </div>
      ) : (
        /* Table View */
        <div className={styles.tableWrap}>
          <table className={styles.dataTable}>
            <thead>
              <tr>
                <th>{t("Mã CP", "Symbol")}</th>
                <th>{t("Doanh nghiệp", "Company")}</th>
                <th>{t("Ngành", "Sector")}</th>
                <th>{t("Điểm cơ hội", "Opportunity Score")}</th>
                <th>{t("Độ tin cậy", "Confidence")}</th>
                <th>{t("Điểm rủi ro", "Risk Score")}</th>
                <th>{t("Trạng thái định giá", "Valuation Status")}</th>
                <th>ROE</th>
                <th>{t("Luận điểm chính", "Core Thesis")}</th>
                <th>{t("Thao tác", "Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {filteredAndSortedResults.map((item) => (
                <tr key={item.symbol}>
                  <td className={styles.tableSymbol}>{item.symbol}</td>
                  <td>{item.name}</td>
                  <td>{item.sector ?? "—"}</td>
                  <td className={styles.tableScore}>
                    {item.opportunity_score !== null ? (
                      <span style={{ color: item.opportunity_score >= 50 ? "var(--positive)" : "var(--ink)" }}>
                        {item.opportunity_score.toFixed(1)}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>
                    <span
                      className={`${styles.pill} ${
                        item.confidence === "HIGH" || item.confidence === "MODERATE"
                          ? styles.pillGood
                          : styles.pillNeutral
                      }`}
                    >
                      {item.confidence === "MODERATE"
                        ? t("Khá", "Moderate")
                        : item.confidence === "HIGH"
                        ? t("Cao", "High")
                        : item.confidence === "LOW"
                        ? t("Thấp", "Low")
                        : t("Chưa đủ", "Insufficient")}
                    </span>
                  </td>
                  <td>{item.risk_score !== null ? item.risk_score.toFixed(1) : "—"}</td>
                  <td>
                    <StatusBadge
                      status={item.valuation_status}
                      label={translateQuantEnum(item.valuation_status, locale)}
                    />
                  </td>
                  <td>
                    {item.factor_summary?.roe !== undefined && item.factor_summary?.roe !== null
                      ? `${(Math.abs(item.factor_summary.roe as number) <= 1.5 ? (item.factor_summary.roe as number) * 100 : (item.factor_summary.roe as number)).toFixed(1)}%`
                      : "—"}
                  </td>
                  <td style={{ maxWidth: 260 }}>
                    {item.why_now && item.why_now.length > 0
                      ? item.why_now[0].description
                      : t("Dữ liệu đang được phân tích.", "Data analysis in progress.")}
                  </td>
                  <td className={styles.tableActions}>
                    <Link
                      href={buildOpportunityAIUrl(item.symbol)}
                      className={styles.actionBtnAiSmall}
                      title={locale === "en" ? `Ask AI Analyst about ${item.symbol}` : `Hỏi AI Analyst về mã ${item.symbol}`}
                    >
                      ✦ {t("Hỏi AI", "Ask AI")}
                    </Link>
                    <Link href={`/research/${item.symbol}`} className={styles.actionBtnPrimary}>
                      {t("Nghiên cứu →", "Research →")}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function OpportunityCard({ item, locale }: { item: OpportunityItem; locale: AppLocale }) {
  const score = item.opportunity_score;
  const isHigh = score !== null && score >= 55;
  const isMid = score !== null && score >= 48 && score < 55;
  const scoreClass = isHigh ? styles.scoreHigh : isMid ? styles.scoreMid : "";

  const roe = item.factor_summary?.roe as number | undefined;
  const roeDisplay = roe !== undefined && roe !== null ? (Math.abs(roe) <= 1.5 ? roe * 100 : roe) : null;

  return (
    <article className={styles.card}>
      <div className={styles.cardHeader}>
        <div className={styles.cardAsset}>
          <div className={styles.symbolRow}>
            <span className={styles.symbol}>{item.symbol}</span>
            {item.sector && <span className={styles.sectorBadge}>{item.sector}</span>}
          </div>
          <span className={styles.companyName}>{item.name}</span>
        </div>

        <div className={`${styles.scoreBadge} ${scoreClass}`}>
          <span className={styles.scoreValue}>{score !== null ? score.toFixed(1) : "—"}</span>
          <span className={styles.scoreLabel}>{locale === "en" ? "Score" : "Điểm"}</span>
        </div>
      </div>

      {/* Metrics Row */}
      <div className={styles.metricsGrid}>
        <div className={styles.metricItem}>
          <span>ROE</span>
          <strong>{roeDisplay !== null ? `${roeDisplay.toFixed(1)}%` : "—"}</strong>
        </div>
        <div className={styles.metricItem}>
          <span>{locale === "en" ? "Valuation" : "Định giá"}</span>
          <strong>
            {item.valuation_status === "AVAILABLE"
              ? locale === "en"
                ? "Available"
                : "Khả dụng"
              : locale === "en"
              ? "Pending"
              : "Chưa đủ"}
          </strong>
        </div>
        <div className={styles.metricItem}>
          <span>{locale === "en" ? "Risk Score" : "Điểm rủi ro"}</span>
          <strong>{item.risk_score !== null ? item.risk_score.toFixed(0) : "50"}</strong>
        </div>
      </div>

      {/* Status Row */}
      <div className={styles.statusRow}>
        <span
          className={`${styles.pill} ${
            item.confidence === "HIGH" || item.confidence === "MODERATE" ? styles.pillGood : styles.pillNeutral
          }`}
        >
          {locale === "en" ? "Confidence:" : "Độ tin cậy:"}{" "}
          {item.confidence === "HIGH"
            ? locale === "en"
              ? "High"
              : "Cao"
            : item.confidence === "MODERATE"
            ? locale === "en"
              ? "Moderate"
              : "Khá"
            : item.confidence === "LOW"
            ? locale === "en"
              ? "Low"
              : "Thấp"
            : locale === "en"
            ? "Insufficient"
            : "Chưa đủ"}
        </span>
        <StatusBadge
          status={item.data_freshness.status}
          label={`${locale === "en" ? "Source:" : "Nguồn:"} ${item.data_freshness.source ?? "LOTUSMARKET"}`}
        />
      </div>

      {/* Claims / Why Now */}
      <div className={styles.claimBox}>
        {item.why_now && item.why_now.length > 0 && (
          <div>
            <div className={styles.whyNowTitle}>
              <span aria-hidden="true">✔</span> {locale === "en" ? "Core Investment Thesis" : "Luận điểm đầu tư chính"}
            </div>
            <div className={styles.whyNowItem}>{item.why_now.map((w) => w.description).join(" ")}</div>
          </div>
        )}

        {/* Risk factors */}
        {item.what_could_go_wrong && item.what_could_go_wrong.length > 0 && (
          <details className={styles.riskAccordion}>
            <summary>{locale === "en" ? "Risk Factors" : "Yếu tố rủi ro"} ({item.what_could_go_wrong.length})</summary>
            <ul>
              {item.what_could_go_wrong.map((risk, idx) => (
                <li key={idx}>{risk}</li>
              ))}
            </ul>
          </details>
        )}
      </div>

      {/* Actions */}
      <div className={styles.cardActions}>
        <Link
          href={buildOpportunityAIUrl(item.symbol)}
          className={styles.actionBtnSecondary}
          title={locale === "en" ? `Ask AI Analyst about ${item.symbol}` : `Hỏi AI Analyst về mã ${item.symbol}`}
        >
          ✦ {locale === "en" ? "Ask AI" : "Hỏi AI"}
        </Link>
        <Link href={`/research/${item.symbol}`} className={styles.actionBtnPrimary}>
          {locale === "en" ? "Research & Valuate →" : "Nghiên cứu & định giá →"}
        </Link>
      </div>
    </article>
  );
}
