"use client";

import Link from "next/link";
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
  const [filters, setFilters] = useState<OpportunityFilters>(defaultFilters);
  const [data, setData] = useState<OpportunityScanner | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState<string>("");
  const [sortBy, setSortBy] = useState<string>("score_desc");
  const [viewMode, setViewMode] = useState<"cards" | "table">("cards");
  const [activeChip, setActiveChip] = useState<string>("all");

  const loadData = useCallback(async (currentFilters: OpportunityFilters) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getOpportunityScanner(currentFilters);
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tải dữ liệu bộ lọc cơ hội.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData(filters);
  }, [filters, loadData]);

  const handleFilterChange = <K extends keyof OpportunityFilters>(key: K, value: OpportunityFilters[K]) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const handleChipClick = (chip: string) => {
    setActiveChip(chip);
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
          <p className={styles.eyebrow}>Mô hình định lượng · Sàng lọc cơ hội đầu tư</p>
          <h1>Sàng lọc cơ hội đầu tư</h1>
          <p className={styles.subTitle}>
            Bộ lọc phát hiện cơ hội đầu tư dựa trên mô hình định lượng đa nhân tố (định giá, chất lượng tài chính ROE /
            tăng trưởng, vĩ mô và quản trị rủi ro). Mọi kết luận đều gắn liền với bằng chứng thực tế và nguồn dữ liệu.
          </p>
        </div>
        <div className={styles.headerActions}>
          <button
            type="button"
            className={styles.refreshBtn}
            onClick={() => loadData(filters)}
            title="Tải lại kết quả bộ lọc"
          >
            ↻ Làm mới
          </button>
          <Link href="/ai?q=Tổng quan các cổ phiếu có cơ hội đầu tư tốt nhất hiện nay" className={styles.aiLinkBtn}>
            ✦ Hỏi AI Analyst
          </Link>
        </div>
      </header>

      {/* Summary KPI Cards */}
      <section className={styles.statGrid}>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Tổng số cơ hội quét</span>
          <span className={styles.statValue}>{stats.total}</span>
          <span className={styles.statDesc}>Thuộc vũ trụ {filters.universe}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Điểm cơ hội cao nhất</span>
          <span className={styles.statValue}>{stats.topStock}</span>
          <span className={styles.statDesc}>Mô hình trung hạn (1-12 tháng)</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Điểm trung bình vũ trụ</span>
          <span className={styles.statValue}>{stats.avgScore}</span>
          <span className={styles.statDesc}>Thang điểm chuẩn hóa 0–100</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Độ phủ định giá</span>
          <span className={styles.statValue}>{stats.valCoverage}</span>
          <span className={styles.statDesc}>Dữ liệu P/E & BCTC xác thực</span>
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
              Tất cả
            </button>
            <button
              type="button"
              className={`${styles.chip} ${activeChip === "high_score" ? styles.chipActive : ""}`}
              onClick={() => handleChipClick("high_score")}
            >
              Điểm cao (≥ 50)
            </button>
            <button
              type="button"
              className={`${styles.chip} ${activeChip === "val_available" ? styles.chipActive : ""}`}
              onClick={() => handleChipClick("val_available")}
            >
              Định giá khả dụng
            </button>
            <button
              type="button"
              className={`${styles.chip} ${activeChip === "banking" ? styles.chipActive : ""}`}
              onClick={() => handleChipClick("banking")}
            >
              Ngành ngân hàng
            </button>
            <button
              type="button"
              className={`${styles.chip} ${activeChip === "technology" ? styles.chipActive : ""}`}
              onClick={() => handleChipClick("technology")}
            >
              Ngành công nghệ
            </button>
          </div>

          <div className={styles.searchWrap}>
            <span className={styles.searchIcon} aria-hidden="true">
              🔍
            </span>
            <input
              type="text"
              placeholder="Tìm theo mã hoặc tên (FPT, MWG...)"
              className={styles.searchBar}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        <div className={styles.filterControls}>
          <div className={styles.filterField}>
            <label>Vũ trụ đầu tư</label>
            <select
              value={filters.universe}
              onChange={(e) => handleFilterChange("universe", e.target.value as OpportunityFilters["universe"])}
            >
              <option value="VN100">VN100 (100 mã lớn nhất)</option>
              <option value="ALL">Tất cả tài sản</option>
              <option value="VN300">VN300</option>
            </select>
          </div>

          <div className={styles.filterField}>
            <label>Ngành nghề</label>
            <select value={filters.sector} onChange={(e) => handleFilterChange("sector", e.target.value)}>
              <option value="">Tất cả các ngành</option>
              {data?.sector_options?.map((sector) => (
                <option key={sector} value={sector}>
                  {sector}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.filterField}>
            <label>Khung thời gian</label>
            <select
              value={filters.horizon}
              onChange={(e) => handleFilterChange("horizon", e.target.value as OpportunityFilters["horizon"])}
            >
              <option value="MEDIUM_TERM">Trung hạn (1–12 tháng)</option>
              <option value="LONG_TERM">Dài hạn (3–10 năm)</option>
            </select>
          </div>

          <div className={styles.filterField}>
            <label>Điểm tối thiểu</label>
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
            <label>Độ tin cậy</label>
            <select value={filters.confidence} onChange={(e) => handleFilterChange("confidence", e.target.value)}>
              <option value="">Tất cả</option>
              <option value="HIGH">Cao</option>
              <option value="MODERATE">Khá</option>
              <option value="LOW">Thấp</option>
              <option value="INSUFFICIENT">Chưa đủ dữ liệu</option>
            </select>
          </div>

          <div className={styles.filterField}>
            <label>Sắp xếp theo</label>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
              <option value="score_desc">Điểm cơ hội (cao → thấp)</option>
              <option value="score_asc">Điểm cơ hội (thấp → cao)</option>
              <option value="roe_desc">ROE (cao → thấp)</option>
              <option value="symbol_asc">Mã cổ phiếu (A → Z)</option>
            </select>
          </div>
        </div>
      </section>

      {/* View Mode Bar */}
      <div className={styles.viewBar}>
        <span className={styles.resultCount}>
          Hiển thị <strong>{filteredAndSortedResults.length}</strong> cơ hội đủ điều kiện
          {data?.as_of_date && <> · Ngày tính toán: {data.as_of_date}</>}
        </span>
        <div className={styles.viewToggle}>
          <button
            type="button"
            className={`${styles.toggleBtn} ${viewMode === "cards" ? styles.toggleActive : ""}`}
            onClick={() => setViewMode("cards")}
          >
            ▦ Thẻ phân tích
          </button>
          <button
            type="button"
            className={`${styles.toggleBtn} ${viewMode === "table" ? styles.toggleActive : ""}`}
            onClick={() => setViewMode("table")}
          >
            ☰ Bảng dữ liệu
          </button>
        </div>
      </div>

      {/* Content Area */}
      {loading ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "16px", padding: "16px 0" }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} height={260} />
          ))}
        </div>
      ) : error ? (
        <div className={styles.errorState}>
          <h3>Không thể tải dữ liệu</h3>
          <p>{error}</p>
          <button type="button" className={styles.resetBtn} onClick={() => loadData(filters)}>
            Thử lại
          </button>
        </div>
      ) : filteredAndSortedResults.length === 0 ? (
        <div className={styles.emptyState}>
          <h3>Không tìm thấy cơ hội phù hợp</h3>
          <p>Không có cổ phiếu nào đáp ứng đầy đủ tiêu chí lọc hiện tại. Thử nới lỏng bộ lọc hoặc chọn "Tất cả".</p>
          <button
            type="button"
            className={styles.resetBtn}
            onClick={() => {
              setFilters(defaultFilters);
              setSearch("");
              setActiveChip("all");
            }}
          >
            Đặt lại bộ lọc mặc định
          </button>
        </div>
      ) : viewMode === "cards" ? (
        /* Card Grid View */
        <div className={styles.cardGrid}>
          {filteredAndSortedResults.map((item) => (
            <OpportunityCard key={item.symbol} item={item} />
          ))}
        </div>
      ) : (
        /* Table View */
        <div className={styles.tableWrap}>
          <table className={styles.dataTable}>
            <thead>
              <tr>
                <th>Mã CP</th>
                <th>Doanh nghiệp</th>
                <th>Ngành</th>
                <th>Điểm cơ hội</th>
                <th>Độ tin cậy</th>
                <th>Điểm rủi ro</th>
                <th>Trạng thái định giá</th>
                <th>ROE</th>
                <th>Luận điểm chính</th>
                <th>Thao tác</th>
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
                        ? "Khá"
                        : item.confidence === "HIGH"
                        ? "Cao"
                        : item.confidence === "LOW"
                        ? "Thấp"
                        : "Chưa đủ"}
                    </span>
                  </td>
                  <td>{item.risk_score !== null ? item.risk_score.toFixed(1) : "—"}</td>
                  <td>
                    <StatusBadge status={item.valuation_status} />
                  </td>
                  <td>
                    {item.factor_summary?.roe !== undefined && item.factor_summary?.roe !== null
                      ? `${(item.factor_summary.roe as number).toFixed(1)}%`
                      : "—"}
                  </td>
                  <td style={{ maxWidth: 260 }}>
                    {item.why_now && item.why_now.length > 0
                      ? item.why_now[0].description
                      : "Dữ liệu đang được phân tích."}
                  </td>
                  <td className={styles.tableActions}>
                    <Link
                      href={buildOpportunityAIUrl(item.symbol)}
                      className={styles.actionBtnAiSmall}
                      title={`Hỏi AI Analyst về mã ${item.symbol}`}
                    >
                      ✦ Hỏi AI
                    </Link>
                    <Link href={`/research/${item.symbol}`} className={styles.actionBtnPrimary}>
                      Nghiên cứu →
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

function OpportunityCard({ item }: { item: OpportunityItem }) {
  const score = item.opportunity_score;
  const isHigh = score !== null && score >= 55;
  const isMid = score !== null && score >= 48 && score < 55;
  const scoreClass = isHigh ? styles.scoreHigh : isMid ? styles.scoreMid : "";

  const roe = item.factor_summary?.roe as number | undefined;

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
          <span className={styles.scoreLabel}>Điểm</span>
        </div>
      </div>

      {/* Metrics Row */}
      <div className={styles.metricsGrid}>
        <div className={styles.metricItem}>
          <span>ROE</span>
          <strong>{roe !== undefined && roe !== null ? `${roe.toFixed(1)}%` : "—"}</strong>
        </div>
        <div className={styles.metricItem}>
          <span>Định giá</span>
          <strong>{item.valuation_status === "AVAILABLE" ? "Khả dụng" : "Chưa đủ"}</strong>
        </div>
        <div className={styles.metricItem}>
          <span>Điểm rủi ro</span>
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
          Độ tin cậy: {item.confidence === "HIGH" ? "Cao" : item.confidence === "MODERATE" ? "Khá" : item.confidence === "LOW" ? "Thấp" : "Chưa đủ"}
        </span>
        <StatusBadge status={item.data_freshness.status} label={`Nguồn: ${item.data_freshness.source ?? "LOTUSMARKET"}`} />
      </div>

      {/* Claims / Why Now */}
      <div className={styles.claimBox}>
        {item.why_now && item.why_now.length > 0 && (
          <div>
            <div className={styles.whyNowTitle}>
              <span aria-hidden="true">✔</span> Luận điểm đầu tư chính
            </div>
            <div className={styles.whyNowItem}>{item.why_now.map((w) => w.description).join(" ")}</div>
          </div>
        )}

        {/* Risk factors */}
        {item.what_could_go_wrong && item.what_could_go_wrong.length > 0 && (
          <details className={styles.riskAccordion}>
            <summary>Yếu tố rủi ro ({item.what_could_go_wrong.length})</summary>
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
          title={`Hỏi AI Analyst về mã ${item.symbol}`}
        >
          ✦ Hỏi AI
        </Link>
        <Link href={`/research/${item.symbol}`} className={styles.actionBtnPrimary}>
          Nghiên cứu chi tiết →
        </Link>
      </div>
    </article>
  );
}
