"use client";

import { FormEvent, startTransition, useEffect, useMemo, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  getAIStatus,
  submitAIQuestion,
  type AIChatResponse,
  type AIStatus,
  type AIToolName,
} from "@/lib/api";
import styles from "./page.module.css";

const toolOptions: Array<{ name: AIToolName; label: string }> = [
  { name: "asset", label: "Tài sản / Asset" },
  { name: "fundamentals", label: "Cơ bản / Fundamentals" },
  { name: "valuation", label: "Định giá / Valuation" },
  { name: "factors", label: "Yếu tố / Factors" },
  { name: "risk", label: "Rủi ro / Risk" },
  { name: "macro", label: "Vĩ mô / Macro" },
  { name: "regime", label: "Chế độ thị trường / Regime" },
  { name: "events", label: "Sự kiện / Events" },
  { name: "opportunity", label: "Cơ hội / Opportunity" },
  { name: "portfolio", label: "Danh mục / Portfolio" },
  { name: "watchlist", label: "Theo dõi / Watchlist" },
  { name: "historical_snapshot", label: "Snapshot lịch sử / History" },
  { name: "evidence", label: "Bằng chứng / Evidence" },
  { name: "document_retrieval", label: "Tài liệu / Documents" },
];

const popularTickers = ["FPT", "MWG", "VCB", "HPG", "MBB", "TCB", "VNM", "BSR", "VHM", "SSI"];

const defaultMarketPrompts = [
  { label: "📈 Toàn cảnh thị trường", query: "Thị trường hôm nay thế nào và xu hướng dòng tiền ra sao?" },
  { label: "⭐ Cơ hội VN100 tốt nhất", query: "Những cổ phiếu nào đang có điểm cơ hội và định giá hấp dẫn nhất hiện nay?" },
  { label: "🏦 Nhóm Ngân hàng (VCB, TCB)", query: "Đánh giá triển vọng tăng trưởng và chất lượng tài sản nhóm ngân hàng VCB, TCB, MBB?" },
  { label: "💻 Triển vọng FPT", query: "Triển vọng và tiềm năng tăng trưởng của FPT trong các quý tới?" },
  { label: "🛒 Bán lẻ (MWG, VNM)", query: "Tình hình tài chính, biên lợi nhuận và định giá của MWG và VNM?" },
  { label: "👋 Hướng dẫn sử dụng", query: "Chào bạn, trợ lý AI Analyst có thể hỗ trợ nhà đầu tư phân tích những gì?" },
];

function getStockPrompts(symbol: string) {
  const sym = symbol.toUpperCase().trim();
  return [
    {
      label: `🎯 Cơ hội & Triển vọng ${sym}`,
      query: `Đánh giá tổng quan cơ hội đầu tư, điểm xếp hạng và triển vọng tăng trưởng của cổ phiếu ${sym}?`,
    },
    {
      label: `📊 Định giá P/E & Giá trị`,
      query: `Phân tích định giá P/E, P/B và tiềm năng upside/downside của cổ phiếu ${sym} hiện tại?`,
    },
    {
      label: `💰 Tài chính & Dòng tiền`,
      query: `Sức khỏe tài chính, biên lợi nhuận (ROE, ROA) và chất lượng dòng tiền hoạt động của ${sym} ra sao?`,
    },
    {
      label: `⚠️ Rủi ro & Bất lợi`,
      query: `Những yếu tố rủi ro chính, thách thức trong ngành và điểm cần lưu ý đối với ${sym} là gì?`,
    },
    {
      label: `🚀 Luận điểm Why Now`,
      query: `Luận điểm đầu tư chính và lý do tại sao nên quan sát hoặc mua tích lũy ${sym} ở thời điểm hiện tại?`,
    },
    {
      label: `⚖️ Cơ cấu nợ & An toàn`,
      query: `Cơ cấu nguồn vốn và mức độ an toàn nợ vay (D/E, Net Debt) của ${sym} như thế nào?`,
    },
  ];
}

type StatusResource = { state: "loading" } | { state: "ready"; value: AIStatus } | { state: "error"; message: string };

function Status({ value }: { value: string }) {
  const tone = value === "HEALTHY" || value === "AVAILABLE" ? styles.good : value === "DEGRADED" || value === "PARTIAL" ? styles.warn : styles.missing;
  return <span className={`${styles.status} ${tone}`}>{value.replaceAll("_", " ")}</span>;
}

function usageValue(value: unknown, divisor = 1) {
  return typeof value === "number" ? (value / divisor).toFixed(divisor === 1 ? 0 : 2) : "N/A";
}

function AIPageContent() {
  const searchParams = useSearchParams();
  const urlSymbol = searchParams.get("symbol") || "";
  const urlQuery = searchParams.get("q") || "";

  const [health, setHealth] = useState<StatusResource>({ state: "loading" });
  const [question, setQuestion] = useState("");
  const [symbol, setSymbol] = useState("");
  const [asOf, setAsOf] = useState("");
  const [selectedTools, setSelectedTools] = useState<AIToolName[]>(toolOptions.map((item) => item.name));
  const [answer, setAnswer] = useState<AIChatResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Sync state when URL params change
  useEffect(() => {
    if (urlSymbol) {
      setSymbol(urlSymbol.toUpperCase().trim());
      if (urlQuery) {
        setQuestion(urlQuery);
      } else {
        setQuestion(`Đánh giá tổng quan cơ hội đầu tư, điểm xếp hạng và triển vọng tăng trưởng của cổ phiếu ${urlSymbol.toUpperCase().trim()}?`);
      }
    } else if (urlQuery) {
      setQuestion(urlQuery);
    }
  }, [urlSymbol, urlQuery]);

  useEffect(() => {
    const controller = new AbortController();
    getAIStatus(controller.signal)
      .then((value) => setHealth({ state: "ready", value }))
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setHealth({ state: "error", message: caught instanceof Error ? caught.message : "AI status unavailable" });
        }
      });
    return () => controller.abort();
  }, []);

  function toggleTool(tool: AIToolName) {
    setSelectedTools((current) => current.includes(tool)
      ? current.filter((item) => item !== tool)
      : [...current, tool]);
  }

  function handleSelectTicker(t: string) {
    const clean = t.toUpperCase().trim();
    setSymbol(clean);
    setQuestion(`Đánh giá tổng quan cơ hội đầu tư, điểm xếp hạng và triển vọng tăng trưởng của cổ phiếu ${clean}?`);
  }

  function handleClearTicker() {
    setSymbol("");
    setQuestion("");
  }

  const activeSymbol = symbol.trim().toUpperCase();

  const currentPrompts = useMemo(() => {
    if (activeSymbol) {
      return getStockPrompts(activeSymbol);
    }
    return defaultMarketPrompts;
  }, [activeSymbol]);

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setAnswer(null);
    try {
      const response = await submitAIQuestion({
        question: question.trim(),
        symbol: symbol.trim() || undefined,
        as_of_date: asOf || undefined,
        tool_names: selectedTools,
      });
      startTransition(() => setAnswer(response));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể kết nối AI API.");
    } finally {
      setBusy(false);
    }
  }

  const healthValue = health.state === "ready" ? health.value.status : health.state === "loading" ? "CHECKING" : "UNAVAILABLE";

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>LOCAL ANALYST / 6F</p>
          <h1>AI Analyst <span>/ Trợ lý nghiên cứu đầu tư</span></h1>
        </div>
        <div className={styles.health} aria-live="polite">
          <span>OLLAMA</span><Status value={healthValue} />
          {health.state === "ready" && (
            <small>
              {health.value.version ?? "Phiên bản không khả dụng"} / {health.value.configured_models?.primary ?? "Chưa cấu hình model"} / {health.value.configured_model_loaded ? "Model sẵn sàng" : "Chưa nạp vào VRAM"}
            </small>
          )}
          {health.state === "error" && <small>{health.message}</small>}
        </div>
      </header>

      <div className={styles.workspace}>
        <form className={styles.composer} onSubmit={ask}>
          {/* Active Stock Context Bar */}
          {activeSymbol ? (
            <div className={styles.activeStockBanner}>
              <div className={styles.bannerLeft}>
                <span>🎯 Đang phân tích mã:</span>
                <strong>{activeSymbol}</strong>
              </div>
              <div className={styles.bannerRight}>
                <Link href={`/research/${activeSymbol}`} className={styles.bannerLink} title="Xem báo cáo chi tiết">
                  Nghiên cứu {activeSymbol} →
                </Link>
                <button
                  type="button"
                  className={styles.bannerClearBtn}
                  onClick={handleClearTicker}
                  title="Xóa mã để hỏi toàn cảnh thị trường"
                >
                  ✕ Bỏ chọn
                </button>
              </div>
            </div>
          ) : null}

          {/* Quick Popular Ticker Selector */}
          <div className={styles.tickerSelectRow}>
            <span className={styles.tickerSelectLabel}>Chọn nhanh mã cổ phiếu theo dõi:</span>
            <div className={styles.tickerChips}>
              {popularTickers.map((t) => (
                <button
                  key={t}
                  type="button"
                  className={`${styles.tickerChip} ${activeSymbol === t ? styles.tickerChipActive : ""}`}
                  onClick={() => handleSelectTicker(t)}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.fieldRow}>
            <label>
              Mã cổ phiếu / Symbol
              <input
                value={symbol}
                onChange={(event) => setSymbol(event.target.value.toUpperCase())}
                maxLength={20}
                placeholder="Tự động nhận diện (VD: FPT, MWG...)"
              />
            </label>
            <label>
              Ngày dữ liệu / As of
              <input type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} />
            </label>
          </div>

          <label>
            Câu hỏi / Question
            <textarea
              required
              minLength={2}
              maxLength={4000}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder={activeSymbol ? `Nhập câu hỏi phân tích cho mã ${activeSymbol}...` : "Hỏi về bằng chứng, thay đổi, định giá, rủi ro hoặc luận điểm..."}
            />
          </label>

          {/* Dynamic Suggested Questions */}
          <div className={styles.quickQueryContainer}>
            <div className={styles.quickQueryHeader}>
              <span className={styles.quickQueryLabel}>
                {activeSymbol ? `Đề xuất câu hỏi cho ${activeSymbol}:` : "Gợi ý câu hỏi nhanh:"}
              </span>
              {activeSymbol && (
                <span className={styles.stockContextBadge}>Tùy biến theo {activeSymbol}</span>
              )}
            </div>
            <div className={styles.quickQueryChips}>
              {currentPrompts.map((item, idx) => (
                <button
                  key={idx}
                  type="button"
                  className={`${styles.quickChip} ${activeSymbol ? styles.stockQuickChip : ""}`}
                  onClick={() => setQuestion(item.query)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <fieldset className={styles.toolScope}>
            <legend>Phạm vi công cụ / Data tools</legend>
            <div>
              {toolOptions.map((tool) => (
                <label key={tool.name}>
                  <input
                    type="checkbox"
                    checked={selectedTools.includes(tool.name)}
                    onChange={() => toggleTool(tool.name)}
                  />
                  <span>{tool.label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <button
            className={styles.submit}
            type="submit"
            disabled={busy || !question.trim() || selectedTools.length === 0}
          >
            {busy ? "Đang tổng hợp bằng chứng từ dữ liệu..." : activeSymbol ? `Hỏi AI Analyst về ${activeSymbol}` : "Hỏi AI Analyst"}
          </button>
          <p className={styles.localNote}>
            Local Ollama only / Dữ liệu danh mục và truy vấn hoàn toàn bảo mật trên máy chủ nội bộ.
          </p>
        </form>

        <section className={styles.response} aria-live="polite">
          <header>
            <div className={styles.responseTitleGroup}>
              <h2>Phân tích / Analysis</h2>
              {answer?.symbol && <span className={styles.symbolBadge}>{answer.symbol}</span>}
            </div>
            {answer && <Status value={answer.status} />}
          </header>
          {!answer && !error && (
            <p className={styles.empty} role="status">
              {activeSymbol
                ? `Nhấn "Hỏi AI Analyst về ${activeSymbol}" để xem báo cáo phân tích tổng hợp kèm bằng chứng dữ liệu.`
                : "Chọn câu hỏi gợi ý hoặc nhập câu hỏi để nhận báo cáo phân tích từ AI."}
            </p>
          )}
          {error && (
            <div className={styles.error} role="alert">
              <strong>AI API không khả dụng</strong>
              <span>{error}</span>
            </div>
          )}
          {answer && (
            <>
              <p className={styles.answerText}>{answer.answer}</p>
              <div className={styles.metadata}>
                <span>{answer.model ?? "Không có cuộc gọi mô hình"}</span>
                <span>{answer.prompt_version}</span>
                <span>Tính đến ngày {answer.as_of_date}</span>
                {typeof answer.usage.eval_count === "number" && <span>{usageValue(answer.usage.eval_count)} tokens</span>}
                {typeof answer.usage.total_duration_ns === "number" && (
                  <span>{usageValue(answer.usage.total_duration_ns, 1_000_000_000)} s</span>
                )}
              </div>
              <section className={styles.claims}>
                <h3>Luận cứ / Claims ({answer.claims.length})</h3>
                {answer.claims.length ? (
                  answer.claims.map((claim, index) => (
                    <article key={`${claim.claim_type}-${index}`}>
                      <Status value={claim.claim_type} />
                      <p>{claim.text}</p>
                      <small>{claim.citation_ids.join(", ") || "Không có trích dẫn"}</small>
                    </article>
                  ))
                ) : (
                  <p className={styles.empty}>Không có claim được hỗ trợ.</p>
                )}
              </section>
              {answer.uncertainty.length > 0 && (
                <section className={styles.uncertainty}>
                  <h3>Dữ liệu chưa chắc chắn / Uncertainty</h3>
                  {answer.uncertainty.map((item, index) => (
                    <p key={index}>{item}</p>
                  ))}
                </section>
              )}
              <details className={styles.citations} open={answer.citations.length > 0}>
                <summary>Bằng chứng trích dẫn / Evidence citations ({answer.citations.length})</summary>
                {answer.citations.map((citation) => (
                  <article key={citation.id}>
                    <strong>
                      {citation.id} / {citation.responsible_module}
                    </strong>
                    <Status value={citation.freshness ?? "INSUFFICIENT_DATA"} />
                    <p>
                      {citation.source ?? "Nguồn không xác định"} / {citation.data_origin ?? "Gốc không xác định"}
                    </p>
                    <small>
                      Quan sát {citation.observation_date ?? "N/A"} / Công bố {citation.publication_date ?? "N/A"}
                      {citation.source_url ? ` / ${citation.source_url}` : ""}
                    </small>
                    {citation.note && <small>{citation.note}</small>}
                  </article>
                ))}
              </details>
            </>
          )}
        </section>
      </div>
    </main>
  );
}

export default function AIPage() {
  return (
    <Suspense fallback={<div className={styles.page}><p className={styles.empty}>Đang nạp AI Analyst...</p></div>}>
      <AIPageContent />
    </Suspense>
  );
}