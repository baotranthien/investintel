"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  getResearchWorkspace,
  type ResearchMetric,
  type ResearchTimelineItem,
  type ResearchWorkspace,
} from "@/lib/api";
import { useLocale, translateQuantEnum, type AppLocale } from "@/lib/i18n";
import styles from "./research-workspace.module.css";

const metricNames: Record<string, { vi: string; en: string }> = {
  revenue: { vi: "Doanh thu (Revenue)", en: "Revenue" },
  net_income: { vi: "Lợi nhuận ròng (Net Income)", en: "Net Income" },
  eps_ttm: { vi: "EPS TTM (Thu nhập mỗi CP 12 tháng)", en: "EPS TTM (Trailing 12M EPS)" },
  revenue_yoy: { vi: "Tăng trưởng Doanh thu YoY (Revenue YoY)", en: "Revenue Growth YoY" },
  net_income_yoy: { vi: "Tăng trưởng Lợi nhuận YoY (Earnings YoY)", en: "Net Income Growth YoY" },
  eps_yoy: { vi: "Tăng trưởng EPS YoY", en: "EPS Growth YoY" },
  revenue_cagr_3y: { vi: "Tăng trưởng DT kép 3 năm (CAGR 3Y)", en: "Revenue 3Y CAGR" },
  revenue_cagr_5y: { vi: "Tăng trưởng DT kép 5 năm (CAGR 5Y)", en: "Revenue 5Y CAGR" },
  eps_cagr_3y: { vi: "Tăng trưởng EPS kép 3 năm (CAGR 3Y)", en: "EPS 3Y CAGR" },
  gross_margin: { vi: "Biên lợi nhuận gộp (Gross Margin)", en: "Gross Profit Margin" },
  ebit_margin: { vi: "Biên EBIT (EBIT Margin)", en: "EBIT Margin" },
  ebitda_margin: { vi: "Biên EBITDA (EBITDA Margin)", en: "EBITDA Margin" },
  net_margin: { vi: "Biên lợi nhuận ròng (Net Margin)", en: "Net Profit Margin" },
  roe: { vi: "ROE (Lợi nhuận trên vốn CSH)", en: "ROE (Return on Equity)" },
  roa: { vi: "ROA (Lợi nhuận trên tổng tài sản)", en: "ROA (Return on Assets)" },
  roic: { vi: "ROIC (Lợi nhuận trên vốn đầu tư)", en: "ROIC (Return on Invested Capital)" },
  cash: { vi: "Tiền & tương đương tiền (Cash)", en: "Cash & Cash Equivalents" },
  total_assets: { vi: "Tổng tài sản (Total Assets)", en: "Total Assets" },
  total_liabilities: { vi: "Nợ phải trả (Total Liabilities)", en: "Total Liabilities" },
  total_equity: { vi: "Vốn chủ sở hữu (Total Equity)", en: "Total Equity" },
  de_ratio: { vi: "Hệ số Nợ/Vốn CSH (Debt / Equity)", en: "Debt-to-Equity (D/E)" },
  debt_to_assets: { vi: "Nợ / Tổng tài sản (Debt / Assets)", en: "Debt-to-Assets" },
  net_debt_ebitda: { vi: "Nợ ròng / EBITDA (Net Debt / EBITDA)", en: "Net Debt / EBITDA" },
  current_ratio: { vi: "Hệ số thanh toán hiện hành (Current Ratio)", en: "Current Ratio" },
  quick_ratio: { vi: "Hệ số thanh toán nhanh (Quick Ratio)", en: "Quick Ratio" },
  interest_coverage: { vi: "Hệ số chi trả lãi vay (Interest Coverage)", en: "Interest Coverage Ratio" },
  cfo: { vi: "Dòng tiền từ hoạt động kinh doanh (CFO)", en: "Operating Cash Flow (CFO)" },
  fcf: { vi: "Dòng tiền tự do (FCF - Free Cash Flow)", en: "Free Cash Flow (FCF)" },
  cfo_to_ni: { vi: "Tỷ lệ CFO / Lợi nhuận ròng", en: "CFO-to-Net Income Ratio" },
  fcf_to_ni: { vi: "Tỷ lệ FCF / Lợi nhuận ròng", en: "FCF-to-Net Income Ratio" },
  dso: { vi: "Số ngày thu tiền bình quân (DSO)", en: "Days Sales Outstanding (DSO)" },
  dio: { vi: "Số ngày tồn kho bình quân (DIO)", en: "Days Inventory Outstanding (DIO)" },
  dpo: { vi: "Số ngày phải trả bình quân (DPO)", en: "Days Payables Outstanding (DPO)" },
  ccc: { vi: "Chu kỳ chuyển đổi tiền mặt (CCC)", en: "Cash Conversion Cycle (CCC)" },
  bvps: { vi: "Giá trị sổ sách mỗi CP (BVPS)", en: "Book Value Per Share (BVPS)" },
  pe: { vi: "P/E (Hệ số Giá / Lợi nhuận mỗi CP)", en: "Price-to-Earnings (P/E)" },
  pb: { vi: "P/B (Hệ số Giá / Giá trị sổ sách)", en: "Price-to-Book (P/B)" },
  ev_ebitda: { vi: "EV / EBITDA", en: "EV / EBITDA" },
  peg: { vi: "Hệ số PEG (P/E trên Tốc độ tăng trưởng)", en: "PEG Ratio" },
  dividend_yield: { vi: "Tỷ suất cổ tức (Dividend Yield)", en: "Dividend Yield" },
  fcf_yield: { vi: "Tỷ suất sinh dòng tiền tự do (FCF Yield)", en: "Free Cash Flow Yield" },
  dcf: { vi: "Định giá DCF (Chiết khấu dòng tiền)", en: "DCF Intrinsic Valuation" },
  residual_income: { vi: "Định giá Thu nhập thặng dư (Residual Income)", en: "Residual Income Model (RIM)" },
  ddm: { vi: "Định giá Chiết khấu cổ tức (DDM)", en: "Dividend Discount Model (DDM)" },
};

const evidenceNames: Record<string, { vi: string; en: string }> = {
  FACT: { vi: "FACT / Dữ kiện BCTC", en: "FACT / Canonical Filing Data" },
  MODEL_OUTPUT: { vi: "MODEL OUTPUT / Kết quả mô hình định lượng", en: "MODEL OUTPUT / Quantitative Model Output" },
  INTERPRETATION: { vi: "INTERPRETATION / Diễn giải phân tích", en: "INTERPRETATION / Analyst Assessment" },
  HYPOTHESIS: { vi: "HYPOTHESIS / Giả thuyết kiểm định", en: "HYPOTHESIS / Empirical Hypothesis" },
  UNCERTAINTY: { vi: "UNCERTAINTY / Chưa đủ bằng chứng", en: "UNCERTAINTY / Inconclusive Evidence" },
};

function getMetricName(key: string, locale: AppLocale): string {
  const found = metricNames[key];
  if (found) return locale === "en" ? found.en : found.vi;
  return key.replaceAll("_", " ");
}

function getEvidenceName(claimType: string, locale: AppLocale): string {
  const found = evidenceNames[claimType];
  if (found) return locale === "en" ? found.en : found.vi;
  return claimType;
}

function formatDate(value: string | null | undefined, locale: AppLocale = "vi") {
  if (!value) return locale === "en" ? "No date" : "Không có ngày";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString(locale === "en" ? "en-US" : "vi-VN");
}

function formatNumber(value: number | null, unit?: string | null, locale: AppLocale = "vi") {
  if (value === null || !Number.isFinite(value)) return "—";
  const text = new Intl.NumberFormat(locale === "en" ? "en-US" : "vi-VN", { maximumFractionDigits: 2 }).format(value);
  if (unit === "%") return `${text}%`;
  if (unit === "VND/share") return locale === "en" ? `${text} VND/share` : `${text} VND/cp`;
  if (unit === "BILLION_VND") return locale === "en" ? `${text}B VND` : `${text} tỷ VND`;
  if (unit === "multiple") return `${text}×`;
  if (unit === "days") return locale === "en" ? `${text} days` : `${text} ngày`;
  return `${text}${unit ? ` ${unit}` : ""}`;
}

function Status({ value, locale }: { value: string; locale: AppLocale }) {
  const cls =
    value === "AVAILABLE" || value === "FACT"
      ? styles.statusGood
      : value === "STALE"
      ? styles.statusWarn
      : styles.statusMissing;
  return <span className={`${styles.status} ${cls}`}>{translateQuantEnum(value, locale)}</span>;
}

function EvidenceDetails({ evidence, locale }: { evidence: ResearchMetric["evidence"]; locale: AppLocale }) {
  return (
    <details className={styles.evidence}>
      <summary>{getEvidenceName(evidence.claim_type, locale)}</summary>
      <dl>
        <div>
          <dt>{locale === "en" ? "Source" : "Nguồn dữ liệu"}</dt>
          <dd>{evidence.source ?? (locale === "en" ? "No source linked" : "Không có nguồn")}</dd>
        </div>
        <div>
          <dt>{locale === "en" ? "Observation Date" : "Ngày quan sát"}</dt>
          <dd>{formatDate(evidence.observation_date, locale)}</dd>
        </div>
        <div>
          <dt>{locale === "en" ? "Publication Date" : "Ngày công bố"}</dt>
          <dd>{formatDate(evidence.publication_date, locale)}</dd>
        </div>
        <div>
          <dt>{locale === "en" ? "Retrieved At" : "Thời điểm thu thập"}</dt>
          <dd>{formatDate(evidence.retrieved_at, locale)}</dd>
        </div>
        <div>
          <dt>{locale === "en" ? "Origin" : "Nguồn gốc"}</dt>
          <dd>{evidence.data_origin ?? "Unknown"}</dd>
        </div>
        {evidence.source_url && (
          <div>
            <dt>{locale === "en" ? "Source URL" : "Liên kết gốc"}</dt>
            <dd>
              <a href={evidence.source_url} target="_blank" rel="noreferrer">
                {locale === "en" ? "View source filing" : "Xem nguồn công bố"}
              </a>
            </dd>
          </div>
        )}
        {evidence.note && (
          <div>
            <dt>{locale === "en" ? "Notes" : "Ghi chú"}</dt>
            <dd>{evidence.note}</dd>
          </div>
        )}
      </dl>
    </details>
  );
}

function MetricTable({
  metrics,
  keys,
  locale,
}: {
  metrics: Record<string, ResearchMetric>;
  keys?: string[];
  locale: AppLocale;
}) {
  const entries = Object.entries(metrics).filter(([key]) => !keys || keys.includes(key));
  if (!entries.length) {
    return (
      <p className={styles.emptyText}>
        {locale === "en" ? "No metrics available from canonical data." : "Chưa có chỉ số khả dụng từ dữ liệu chuẩn hóa."}
      </p>
    );
  }
  return (
    <div className={styles.metricList}>
      {entries.map(([key, metric]) => (
        <article className={styles.metricRow} key={key}>
          <div>
            <strong>{getMetricName(key, locale)}</strong>
            <small>
              {metric.period ?? (locale === "en" ? "Period unavailable" : "Kỳ chưa xác định")}
              {metric.calculation ? ` · ${metric.calculation}` : ""}
            </small>
          </div>
          <div className={styles.metricValue}>
            <b>{formatNumber(metric.value, metric.unit, locale)}</b>
            <Status value={metric.status} locale={locale} />
          </div>
          <EvidenceDetails evidence={metric.evidence} locale={locale} />
        </article>
      ))}
    </div>
  );
}

function ClaimList({ claims, locale }: { claims: Array<Record<string, unknown>>; locale: AppLocale }) {
  if (!claims.length) {
    return <p className={styles.emptyText}>{locale === "en" ? "No claims recorded." : "Không có luận cứ ghi nhận."}</p>;
  }
  return (
    <ul className={styles.claimList}>
      {claims.map((claim, index) => {
        const type = String(claim.claim_type ?? "UNCERTAINTY");
        const changeText = claim.metric
          ? `${getMetricName(String(claim.metric), locale)} · ${String(claim.before)} → ${String(claim.current)}`
          : null;
        const text = String(claim.text ?? claim.description ?? changeText ?? "");
        return (
          <li key={`${type}-${index}`}>
            <Status value={type} locale={locale} />
            <span>{text}</span>
            {claim.source ? (
              <small>
                {String(claim.source)} · {formatDate(String(claim.publication_date ?? ""), locale)}
              </small>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

function Timeline({ items, locale }: { items: ResearchTimelineItem[]; locale: AppLocale }) {
  if (!items.length) {
    return (
      <p className={styles.emptyText}>
        {locale === "en"
          ? "No timeline events or financial revisions with linked evidence."
          : "Chưa có sự kiện hoặc mốc điều chỉnh BCTC có bằng chứng kiểm định."}
      </p>
    );
  }
  return (
    <ol className={styles.timeline}>
      {items.map((item) => (
        <li key={item.id}>
          <time>{formatDate(item.date, locale)}</time>
          <div className={styles.timelineBody}>
            <div className={styles.timelineHead}>
              <strong>{item.title}</strong>
              <Status value={item.status} locale={locale} />
            </div>
            {item.before !== null && (
              <p>
                {locale === "en" ? "Before" : "Trước"} <b>{item.before}</b> <span aria-hidden="true">→</span>{" "}
                {locale === "en" ? "Current" : "Hiện tại"} <b>{item.current}</b>
              </p>
            )}
            <small>
              {item.kind} · {item.evidence.source ?? (locale === "en" ? "Source unavailable" : "Nguồn không khả dụng")}
            </small>
            <details className={styles.evidence}>
              <summary>{getEvidenceName(item.evidence.claim_type, locale)}</summary>
              <dl>
                <div>
                  <dt>{locale === "en" ? "Source" : "Nguồn"}</dt>
                  <dd>{item.evidence.source ?? (locale === "en" ? "No source linked" : "Chưa có nguồn")}</dd>
                </div>
                <div>
                  <dt>{locale === "en" ? "Publication" : "Ngày công bố"}</dt>
                  <dd>{formatDate(item.evidence.publication_date, locale)}</dd>
                </div>
                <div>
                  <dt>{locale === "en" ? "Origin" : "Nguồn gốc"}</dt>
                  <dd>{item.evidence.data_origin ?? "Unknown"}</dd>
                </div>
                {item.evidence.note && (
                  <div>
                    <dt>{locale === "en" ? "Notes" : "Ghi chú"}</dt>
                    <dd>{item.evidence.note}</dd>
                  </div>
                )}
              </dl>
            </details>
          </div>
        </li>
      ))}
    </ol>
  );
}

function ResearchContent({ data, locale }: { data: ResearchWorkspace; locale: AppLocale }) {
  const history = data.fundamentals.history;
  const metricGroups = [
    {
      title: locale === "en" ? "Income & Per Share Metrics" : "Thu nhập & Chỉ số trên mỗi cổ phiếu",
      keys: ["revenue", "net_income", "eps_ttm", "revenue_yoy", "net_income_yoy", "eps_yoy", "revenue_cagr_3y", "revenue_cagr_5y", "eps_cagr_3y"],
    },
    {
      title: locale === "en" ? "Margins & Returns" : "Biên lợi nhuận & Hiệu quả sinh lời",
      keys: ["gross_margin", "ebit_margin", "ebitda_margin", "net_margin", "roe", "roa", "roic"],
    },
    {
      title: locale === "en" ? "Balance Sheet & Solvency" : "Bảng cân đối & Khả năng thanh toán",
      keys: ["cash", "total_assets", "total_liabilities", "total_equity", "de_ratio", "debt_to_assets", "net_debt_ebitda", "current_ratio", "quick_ratio", "interest_coverage"],
    },
    {
      title: locale === "en" ? "Cash Flow & Working Capital" : "Dòng tiền & Vốn lưu động",
      keys: ["cfo", "fcf", "cfo_to_ni", "fcf_to_ni", "dso", "dio", "dpo", "ccc"],
    },
  ];

  return (
    <>
      <section className={styles.overview} id="overview">
        <div className={styles.assetIdentity}>
          <p className={styles.eyebrow}>
            ASSET RESEARCH · {data.asset.exchange ?? (locale === "en" ? "EXCHANGE UNAVAILABLE" : "SÀN CHƯA XÁC ĐỊNH")}
          </p>
          <h1>
            {data.asset.symbol}
            <span>{data.asset.name}</span>
          </h1>
          <p>
            {data.asset.sector} · {data.asset.asset_type} · {data.asset.currency}
          </p>
        </div>
        <div className={styles.quoteBlock}>
          <span>{locale === "en" ? "Market Price" : "Thị giá"}</span>
          <strong>{data.price.value === null ? "—" : formatNumber(data.price.value, "VND", locale)}</strong>
          <small>
            {formatDate(data.price.as_of_date, locale)} · <Status value={data.price.status} locale={locale} />
          </small>
          <small>
            {data.price.source ?? (locale === "en" ? "No price source" : "Không có nguồn giá")} · {data.price.data_origin}
          </small>
          <Link
            href={`/ai?symbol=${encodeURIComponent(data.asset.symbol)}&q=${encodeURIComponent(
              locale === "en"
                ? `Evaluate investment opportunity and outlook for ${data.asset.symbol}?`
                : `Đánh giá cơ hội đầu tư và triển vọng của cổ phiếu ${data.asset.symbol}?`
            )}`}
            className={styles.askAiLink}
            title={locale === "en" ? `Ask AI Analyst about ${data.asset.symbol}` : `Hỏi AI Analyst về ${data.asset.symbol}`}
          >
            ✦ {locale === "en" ? `Ask AI about ${data.asset.symbol} →` : `Hỏi AI về ${data.asset.symbol} →`}
          </Link>
        </div>
        <div className={styles.summaryStats}>
          <div>
            <span>{locale === "en" ? "Opportunity Score" : "Điểm Cơ hội (Opportunity)"}</span>
            <b>{data.opportunity.score === null ? "—" : formatNumber(data.opportunity.score, null, locale)}</b>
            <Status value={data.opportunity.status} locale={locale} />
          </div>
          <div>
            <span>{locale === "en" ? "Confidence" : "Độ tin cậy (Confidence)"}</span>
            <b>{translateQuantEnum(data.opportunity.confidence, locale)}</b>
          </div>
          <div>
            <span>{locale === "en" ? "Risk Score" : "Rủi ro (Risk Score)"}</span>
            <b>{data.risk.overall_score === null ? "—" : formatNumber(data.risk.overall_score, null, locale)}</b>
            <Status value={data.risk.status} locale={locale} />
          </div>
          <div>
            <span>{locale === "en" ? "Investment Horizon" : "Thời hạn (Horizon)"}</span>
            <b>
              {data.opportunity.horizon === "MEDIUM_TERM"
                ? (locale === "en" ? "Medium-Term (1-12M)" : "Trung hạn (1-12T)")
                : data.opportunity.horizon === "LONG_TERM"
                ? (locale === "en" ? "Long-Term (3-10Y)" : "Dài hạn (3-10N)")
                : translateQuantEnum(data.opportunity.horizon, locale)}
            </b>
          </div>
          <div>
            <span>{locale === "en" ? "Data Quality" : "Chất lượng dữ liệu"}</span>
            <b>{data.data_quality.status}</b>
            <small>
              {locale === "en"
                ? `${data.data_quality.history_depth_years}Y history · as of ${formatDate(data.as_of_date, locale)}`
                : `Lịch sử ${data.data_quality.history_depth_years} năm · tính đến ${formatDate(data.as_of_date, locale)}`}
            </small>
          </div>
        </div>
      </section>

      <nav className={styles.sectionNav} aria-label={locale === "en" ? "Research sections" : "Các mục nghiên cứu"}>
        {[
          { id: "fundamentals", label: locale === "en" ? "Fundamentals" : "Báo cáo Tài chính (Fundamentals)" },
          { id: "sector", label: locale === "en" ? "Sector Analysis" : "Phân tích Ngành (Sector)" },
          { id: "valuation", label: locale === "en" ? "Valuation" : "Định giá (Valuation)" },
          { id: "factors", label: locale === "en" ? "Factors" : "Nhân tố (Factors)" },
          { id: "risk", label: locale === "en" ? "Risk Management" : "Quản trị Rủi ro (Risk)" },
          { id: "events", label: locale === "en" ? "Events & Filings" : "Sự kiện & BCTC (Events)" },
          { id: "summary", label: locale === "en" ? "Research Summary" : "Tổng hợp Luận điểm (Summary)" },
        ].map((section) => (
          <a href={`#${section.id}`} key={section.id}>
            {section.label}
          </a>
        ))}
      </nav>

      <section className={styles.section} id="fundamentals">
        <header className={styles.sectionHeader}>
          <div>
            <p className={styles.eyebrow}>CANONICAL FINANCIAL STATEMENTS</p>
            <h2>{locale === "en" ? "Fundamentals & Key Financials" : "Chỉ số tài chính cơ bản"}</h2>
          </div>
          <Status value={data.fundamentals.status} locale={locale} />
        </header>
        <p className={styles.sectionNote}>
          {locale === "en" ? "Period" : "Kỳ"} {data.fundamentals.period ?? "—"} · TTM{" "}
          {data.fundamentals.ttm_available ? (locale === "en" ? "available" : "khả dụng") : (locale === "en" ? "INSUFFICIENT_DATA" : "CHƯA ĐỦ DỮ LIỆU")} ·{" "}
          {locale === "en" ? "Published through" : "Công bố tính đến"} {formatDate(data.fundamentals.latest_publication_date, locale)} ·{" "}
          {data.fundamentals.sources.join(", ") || (locale === "en" ? "No source" : "Chưa có nguồn")}
        </p>
        <div className={styles.fundamentalGroups}>
          {metricGroups.map((group) => (
            <div className={styles.metricGroup} key={group.title}>
              <h3>{group.title}</h3>
              <MetricTable metrics={data.fundamentals.metrics} keys={group.keys} locale={locale} />
            </div>
          ))}
        </div>
        {data.fundamentals.earnings_quality && (
          <details className={styles.disclosure}>
            <summary>{locale === "en" ? "Earnings quality & financial health" : "Chất lượng lợi nhuận & sức khỏe tài chính"}</summary>
            <pre>
              {JSON.stringify(
                {
                  earnings_quality: data.fundamentals.earnings_quality,
                  financial_health: data.fundamentals.financial_health,
                  quality_flags: data.fundamentals.quality_flags,
                },
                null,
                2
              )}
            </pre>
          </details>
        )}
        {history.length >= 2 && (
          <div className={styles.historyTable}>
            <h3>{locale === "en" ? "Financial History" : "Lịch sử tài chính"}</h3>
            <div className={styles.tableScroll}>
              <table>
                <thead>
                  <tr>
                    <th>{locale === "en" ? "Period" : "Kỳ BCTC"}</th>
                    <th>{locale === "en" ? "Revenue" : "Doanh thu"}</th>
                    <th>{locale === "en" ? "Net Earnings" : "Lợi nhuận ròng"}</th>
                    <th>EPS</th>
                    <th>{locale === "en" ? "Published" : "Ngày công bố"}</th>
                    <th>{locale === "en" ? "Source" : "Nguồn dữ liệu"}</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((row, index) => (
                    <tr key={`${row.fiscal_year}-${row.fiscal_quarter ?? "A"}-${index}`}>
                      <td>
                        {row.fiscal_year ?? "—"}
                        {row.period_type === "QUARTERLY" ? ` Q${row.fiscal_quarter ?? "?"}` : ""}
                      </td>
                      <td>{formatNumber(row.revenue, "BILLION_VND", locale)}</td>
                      <td>{formatNumber(row.earnings, "BILLION_VND", locale)}</td>
                      <td>{formatNumber(row.eps, "VND/share", locale)}</td>
                      <td>{formatDate(row.publication_date, locale)}</td>
                      <td>{row.source ?? (locale === "en" ? "Untraced" : "Không xác định")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
        {history.length < 2 && (
          <p className={styles.emptyText}>
            {locale === "en"
              ? "Trend history unavailable: fewer than two canonical periods."
              : "Chưa có biểu đồ lịch sử: ít hơn hai kỳ báo cáo chuẩn hóa."}
          </p>
        )}
      </section>

      <section className={styles.section} id="sector">
        <header className={styles.sectionHeader}>
          <div>
            <p className={styles.eyebrow}>SECTOR MODEL · {data.sector_analysis.sector}</p>
            <h2>{locale === "en" ? "Sector Comparison & Benchmarks" : "Phân tích & So sánh ngành"}</h2>
          </div>
          <Status value={data.sector_analysis.status} locale={locale} />
        </header>
        <p className={styles.sectionNote}>
          {locale === "en" ? "Applicable:" : "Áp dụng:"} {data.sector_analysis.applicable_metrics.join(" · ") || "—"}
        </p>
        <p className={styles.sectionNote}>
          {locale === "en" ? "Not applicable:" : "Không áp dụng:"} {data.sector_analysis.not_applicable_metrics.join(" · ") || "—"}
        </p>
        {data.sector_analysis.notes.map((note) => (
          <p className={styles.sectionNote} key={note}>
            {note}
          </p>
        ))}
        <MetricTable metrics={data.sector_analysis.metrics} locale={locale} />
      </section>

      <section className={styles.section} id="valuation">
        <header className={styles.sectionHeader}>
          <div>
            <p className={styles.eyebrow}>VALUATION ENGINE OUTPUT</p>
            <h2>{locale === "en" ? "Intrinsic & Relative Valuation" : "Định giá Doanh nghiệp"}</h2>
          </div>
          <Status value={data.valuation.status} locale={locale} />
        </header>
        <MetricTable metrics={data.valuation.metrics} locale={locale} />
        <div className={styles.uncertainty}>
          <strong>
            {locale === "en" ? "Fair value range / Bear · Base · Bull:" : "Khoảng định giá hợp lý / Thận trọng · Cơ sở · Lạc quan:"}{" "}
            {data.valuation.fair_value
              ? `${formatNumber(data.valuation.fair_value.bear, "VND", locale)} · ${formatNumber(
                  data.valuation.fair_value.base,
                  "VND",
                  locale
                )} · ${formatNumber(data.valuation.fair_value.bull, "VND", locale)}`
              : (locale === "en" ? "INSUFFICIENT_DATA" : "CHƯA ĐỦ DỮ LIỆU")}
          </strong>
          <ul>
            {data.valuation.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      </section>

      <section className={styles.section} id="factors">
        <header className={styles.sectionHeader}>
          <div>
            <p className={styles.eyebrow}>FACTOR ENGINE</p>
            <h2>{locale === "en" ? "Multi-Factor Exposures" : "Mô hình đa nhân tố"}</h2>
          </div>
          <Status value={data.factors.status} locale={locale} />
        </header>
        <div className={styles.factorGrid}>
          {Object.entries(data.factors.scores).map(([name, metric]) => (
            <article key={name}>
              <span>{name}</span>
              <strong>{formatNumber(metric.value, metric.unit, locale)}</strong>
              <Status value={metric.status} locale={locale} />
              <EvidenceDetails evidence={metric.evidence} locale={locale} />
            </article>
          ))}
        </div>
        <p className={styles.sectionNote}>
          {locale === "en" ? "Supporting:" : "Hỗ trợ:"}{" "}
          {data.factors.supporting.join(" · ") || (locale === "en" ? "No factor evidence." : "Chưa có bằng chứng nhân tố.")} ·{" "}
          {locale === "en" ? "Contradicting:" : "Bất lợi:"}{" "}
          {data.factors.contradicting.join(" · ") || (locale === "en" ? "No factor evidence." : "Chưa có bằng chứng nhân tố.")}
        </p>
      </section>

      <section className={styles.section} id="risk">
        <header className={styles.sectionHeader}>
          <div>
            <p className={styles.eyebrow}>RISK ENGINE · 10 CATEGORIES</p>
            <h2>{locale === "en" ? "Risk Analysis & Breakdown" : "Phân tích & Đo lường rủi ro"}</h2>
          </div>
          <Status value={data.risk.status} locale={locale} />
        </header>
        <div className={styles.riskGrid}>
          {data.risk.categories.map((category) => (
            <article key={category.name}>
              <strong>{category.name}</strong>
              <span>{category.value === null ? "—" : formatNumber(category.value, null, locale)}</span>
              <Status value={category.status} locale={locale} />
              <small>{category.drivers.join(" · ") || (locale === "en" ? "No evidence-backed driver." : "Không có động lực kiểm chứng.")}</small>
            </article>
          ))}
        </div>
        <p className={styles.warning}>{data.risk.missing_data_warning}</p>
        <div className={styles.macroSensitivity}>
          <h3>{locale === "en" ? "Macro Sensitivity" : "Độ nhạy vĩ mô"}</h3>
          <Status value={data.macro_sensitivity.status} locale={locale} />
          <p>{data.macro_sensitivity.note}</p>
        </div>
      </section>

      <section className={styles.section} id="events">
        <header className={styles.sectionHeader}>
          <div>
            <p className={styles.eyebrow}>CANONICAL EVENTS & CORPORATE ACTIONS</p>
            <h2>{locale === "en" ? "Corporate Actions & Event Timeline" : "Sự kiện & Dòng thời gian doanh nghiệp"}</h2>
          </div>
          <Status value={data.events.length || data.timeline.length ? "AVAILABLE" : "INSUFFICIENT_DATA"} locale={locale} />
        </header>
        <Timeline items={data.timeline} locale={locale} />
        {data.events.length > 0 && (
          <div className={styles.eventRecords}>
            {data.events.map((event) => (
              <details className={styles.eventItem} key={String(event.id)}>
                <summary>
                  {String(event.title)} · {String(event.event_type)} · {formatDate(String(event.published_at ?? ""), locale)}
                </summary>
                <p>{String(event.description)}</p>
                <pre>{JSON.stringify(event.evidence, null, 2)}</pre>
              </details>
            ))}
          </div>
        )}
      </section>

      <section className={styles.section} id="summary">
        <header className={styles.sectionHeader}>
          <div>
            <p className={styles.eyebrow}>ENGINE & EVIDENCE ONLY · NO AI</p>
            <h2>{locale === "en" ? "Evidence-Anchored Research Summary" : "Tóm tắt kết quả nghiên cứu kiểm chứng"}</h2>
          </div>
        </header>
        <div className={styles.summaryGrid}>
          <div>
            <h3>{locale === "en" ? "What Changed" : "Biến động gần nhất"}</h3>
            <ClaimList claims={data.research_summary.what_changed} locale={locale} />
          </div>
          <div>
            <h3>{locale === "en" ? "Why Now (Catalysts)" : "Động lực thúc đẩy (Why Now)"}</h3>
            <ClaimList claims={data.research_summary.why_now} locale={locale} />
          </div>
          <div>
            <h3>{locale === "en" ? "Why Not Now (Risks)" : "Rào cản & Rủi ro (Why Not Now)"}</h3>
            <ClaimList claims={data.research_summary.why_not_now} locale={locale} />
          </div>
          <div>
            <h3>{locale === "en" ? "What Would Make Me Wrong" : "Điều kiện vô hiệu hóa luận điểm"}</h3>
            <ClaimList claims={data.research_summary.what_would_make_me_wrong} locale={locale} />
          </div>
        </div>
      </section>
    </>
  );
}

export default function ResearchWorkspaceClient({ symbol }: { symbol: string }) {
  const router = useRouter();
  const { locale, t } = useLocale();
  const [resource, setResource] = useState<
    | { status: "loading" }
    | { status: "ready"; data: ResearchWorkspace }
    | { status: "error"; message: string; notFound: boolean }
  >({ status: "loading" });
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getResearchWorkspace(symbol, undefined, controller.signal)
      .then((data) => setResource({ status: "ready", data }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        const notFound = typeof error === "object" && error !== null && "status" in error && error.status === 404;
        setResource({
          status: "error",
          message: error instanceof Error ? error.message : t("Research API không khả dụng.", "Research API unavailable."),
          notFound,
        });
      });
    return () => controller.abort();
  }, [symbol, reload, t]);

  if (resource.status === "loading") {
    return (
      <div className={styles.stateBlock} role="status">
        {t(`Đang tải canonical research data cho ${symbol}…`, `Loading canonical research data for ${symbol}…`)}
      </div>
    );
  }

  if (resource.status === "error") {
    return (
      <div className={styles.stateBlock} role="alert">
        <strong>
          {resource.notFound
            ? t("Không tìm thấy asset", "Asset not found")
            : t("Research API không khả dụng", "Research API unavailable")}
        </strong>
        <span>{resource.message}</span>
        <div>
          <button onClick={() => setReload((value) => value + 1)}>{t("Thử lại", "Retry")}</button>
          <button onClick={() => router.push("/research")}>{t("Về trang nghiên cứu", "Research Home")}</button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.workspace}>
      <div className={styles.workspaceMeta}>
        <Status value={resource.data.status} locale={locale} />
        <span>
          {t("TÍNH ĐẾN", "AS OF")} {formatDate(resource.data.as_of_date, locale)}
        </span>
        <button onClick={() => setReload((value) => value + 1)}>
          ↻ <span>{t("Làm mới", "Refresh")}</span>
        </button>
      </div>
      <ResearchContent data={resource.data} locale={locale} />
    </div>
  );
}
