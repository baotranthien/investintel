"use client";

import React, { FormEvent, startTransition, useEffect, useMemo, useRef, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  getAIStatus,
  streamAIChat,
  type AIChatResponse,
  type AICitation,
  type AIStatus,
  type AIStreamStep,
  type AIToolName,
} from "@/lib/api";
import AppleCitationPill from "@/components/apple-citation-pill";
import AppleSmartFallback from "@/components/apple-smart-fallback";
import { normalizeTicker, buildOpportunityQuestion } from "@/lib/ai-handoff";
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

const popularTickers = ["FPT", "MWG", "VCB", "MBB", "TCB", "PLX", "HPG", "VNM", "BSR", "SSI"];

const defaultMarketPrompts = [
  { label: "📈 Toàn cảnh thị trường & dòng tiền", query: "Thị trường hôm nay thế nào và xu hướng dòng tiền ra sao?" },
  { label: "⭐ Cơ hội VN100 hấp dẫn nhất", query: "Những cổ phiếu nào đang có điểm cơ hội và định giá hấp dẫn nhất hiện nay?" },
  { label: "🏦 So sánh NIM & NPL (MBB, VCB)", query: "So sánh NIM, tăng trưởng tín dụng và CASA giữa MBB và VCB?" },
  { label: "💻 Triển vọng & Định giá FPT", query: "Triển vọng và tiềm năng tăng trưởng định giá P/E của FPT trong các quý tới?" },
  { label: "🛢️ Tương quan PLX & Giá dầu", query: "Phân tích mối tương quan giữa doanh thu PLX và biến động giá dầu Brent/WTI?" },
  { label: "🛒 Bán lẻ (MWG, VNM)", query: "Tình hình tài chính, biên lợi nhuận và định giá của MWG và VNM?" },
];

function getStockPrompts(symbol: string) {
  const sym = symbol.toUpperCase().trim();
  return [
    {
      label: `🎯 Cơ hội & Triển vọng ${sym}`,
      query: `Đánh giá tổng quan cơ hội đầu tư, điểm xếp hạng và triển vọng tăng trưởng của cổ phiếu ${sym}?`,
    },
    {
      label: `📊 Định giá P/E & P/B`,
      query: `Phân tích định giá P/E, P/B và tiềm năng upside/downside của cổ phiếu ${sym} hiện tại?`,
    },
    {
      label: `💰 Biên lợi nhuận & Dòng tiền`,
      query: `Sức khỏe tài chính, biên lợi nhuận (ROE, ROA) và chất lượng dòng tiền hoạt động của ${sym} ra sao?`,
    },
    {
      label: `⚠️ Rủi ro & Lưu ý chính`,
      query: `Những yếu tố rủi ro chính, thách thức trong ngành và điểm cần lưu ý đối với ${sym} là gì?`,
    },
    {
      label: `⚖️ Cơ cấu nợ & Khả năng chi trả`,
      query: `Cơ cấu nguồn vốn và mức độ an toàn nợ vay (D/E, Net Debt) của ${sym} như thế nào?`,
    },
  ];
}

type StatusResource = { state: "loading" } | { state: "ready"; value: AIStatus } | { state: "error"; message: string };

function usageValue(value: unknown, divisor = 1) {
  return typeof value === "number" ? (value / divisor).toFixed(divisor === 1 ? 0 : 2) : "N/A";
}

function renderAnswerWithCitations(text: string, citations: AICitation[]) {
  const citationMap = new Map(citations.map((c) => [c.id.toUpperCase(), c]));
  const regex = /\[(?:Evidence:\s*)?(E\d{3}(?:,\s*(?:Evidence:\s*)?E\d{3})*)\]/gi;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const rawIds = match[1];
    const ids = rawIds.split(",").map((s) => s.replace(/Evidence:\s*/i, "").trim().toUpperCase());
    parts.push(
      <span key={match.index} style={{ display: "inline-flex", gap: "4px", margin: "0 2px" }}>
        {ids.map((id) => (
          <AppleCitationPill key={id} id={id} citation={citationMap.get(id)} />
        ))}
      </span>
    );
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}

function AIWorkspaceContent() {
  const searchParams = useSearchParams();

  // 1. Read incoming navigation context
  const symbolParam = searchParams.get("symbol") || searchParams.get("ticker");
  const qParam = searchParams.get("q") || searchParams.get("question");
  const sourceParam = searchParams.get("source");

  // 2. Validate and normalize ticker
  const initialValidTicker = normalizeTicker(symbolParam);

  // 3. Compute initial question from query context
  const initialQuestion = useMemo(() => {
    if (initialValidTicker) {
      if (sourceParam === "opportunities" || !qParam) {
        return buildOpportunityQuestion(initialValidTicker);
      }
      return qParam.trim();
    }
    if (qParam) {
      return qParam.trim();
    }
    return "";
  }, []);

  const [activeSymbol, setActiveSymbol] = useState<string>(initialValidTicker ?? "");
  const [question, setQuestion] = useState<string>(initialQuestion);
  const [asOf, setAsOf] = useState("");
  const [selectedTools, setSelectedTools] = useState<AIToolName[]>(toolOptions.map((t) => t.name));
  const [busy, setBusy] = useState(false);
  const [streamStep, setStreamStep] = useState<AIStreamStep | null>(null);
  const [streamMessage, setStreamMessage] = useState("");
  const [answer, setAnswer] = useState<AIChatResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<StatusResource>({ state: "loading" });

  const abortControllerRef = useRef<AbortController | null>(null);
  const answerSectionRef = useRef<HTMLElement>(null);

  // Navigation tracking ref to ensure idempotency and prevent overwriting user edits
  const lastHandledKeyRef = useRef<string>(
    symbolParam || qParam || sourceParam
      ? `${symbolParam ?? ""}|${qParam ?? ""}|${sourceParam ?? ""}`
      : ""
  );

  useEffect(() => {
    let cancelled = false;
    getAIStatus()
      .then((data) => {
        if (!cancelled) setHealth({ state: "ready", value: data });
      })
      .catch((err) => {
        if (!cancelled) setHealth({ state: "error", message: err.message || "Failed to load status" });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Handle client-side navigation transitions (e.g. clicking different opportunities)
  useEffect(() => {
    const currentKey = `${symbolParam ?? ""}|${qParam ?? ""}|${sourceParam ?? ""}`;

    // If searchParams haven't changed since last handoff, don't overwrite user edits
    if (lastHandledKeyRef.current === currentKey) {
      return;
    }
    lastHandledKeyRef.current = currentKey;

    const validTicker = normalizeTicker(symbolParam);

    // If neither ticker nor question is present in URL (e.g. direct navigation to /ai),
    // preserve any existing state so we never overwrite what user has started writing.
    if (!validTicker && !qParam) {
      return;
    }

    if (validTicker) {
      setActiveSymbol(validTicker);
      const targetQuestion =
        sourceParam === "opportunities" || !qParam
          ? buildOpportunityQuestion(validTicker)
          : qParam.trim();
      setQuestion(targetQuestion);
      setAnswer(null);
      setError(null);
    } else if (qParam) {
      setQuestion(qParam.trim());
      setAnswer(null);
      setError(null);
    }
  }, [symbolParam, qParam, sourceParam]);

  const currentPrompts = useMemo(() => {
    return activeSymbol ? getStockPrompts(activeSymbol) : defaultMarketPrompts;
  }, [activeSymbol]);

  function handleSelectTicker(t: string) {
    const nextTicker = activeSymbol === t ? "" : t;
    setActiveSymbol(nextTicker);
    setQuestion("");
    setAnswer(null);
  }

  function toggleTool(name: AIToolName) {
    setSelectedTools((prev) => (prev.includes(name) ? prev.filter((item) => item !== name) : [...prev, name]));
  }

  function handleCancelStream() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setBusy(false);
    setStreamStep(null);
    setStreamMessage("");
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    if (busy || !question.trim()) return;

    setBusy(true);
    setStreamStep("fetching_data");
    setStreamMessage("Đang khởi tạo kết nối luồng phân tích...");
    setError(null);
    setAnswer(null);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const finalResponse = await streamAIChat(
        {
          symbol: activeSymbol.trim() || undefined,
          question: question.trim(),
          as_of_date: asOf || undefined,
          tool_names: selectedTools,
        },
        {
          onStatusUpdate: (step: AIStreamStep, msg: string) => {
            setStreamStep(step);
            setStreamMessage(msg);
          },
        },
        controller.signal
      );

      startTransition(() => {
        if (finalResponse) {
          setAnswer(finalResponse);
          if (finalResponse.symbol && !activeSymbol) {
            setActiveSymbol(finalResponse.symbol);
          }
        }
      });

      setTimeout(() => {
        answerSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    } catch (err: unknown) {
      if ((err as Error)?.name === "AbortError") {
        setStreamMessage("Đã hủy phân tích theo yêu cầu.");
      } else {
        setError(err instanceof Error ? err.message : "Đã xảy ra lỗi không mong muốn");
      }
    } finally {
      setBusy(false);
      setStreamStep(null);
      setStreamMessage("");
      abortControllerRef.current = null;
    }
  }

  return (
    <div className={styles.pageWrapper}>
      <div className={styles.centerContainer}>
        {/* 1. Header giới thiệu (Centered Hero) */}
        <section className={styles.heroSection}>
          <div className={styles.heroBadge}>
            <span className={styles.pulseDot} />
            <span>AI INVESTMENT RESEARCH · LOCAL FIRST</span>
            {health.state === "ready" && (
              <span style={{ opacity: 0.7 }}>· {health.value.configured_models?.primary ?? "qwen3.5:9b-q4_K_M"}</span>
            )}
          </div>
          <h1 className={styles.heroTitle}>Trợ lý Nghiên cứu &amp; Thẩm định Tài chính</h1>
          <p className={styles.heroSubtitle}>
            Đối soát BCTC, định giá P/E, mô hình IAS 33 và độ nhạy vĩ mô — dựa 100% trên số liệu kiểm chứng, không bịa đặt thông tin.
          </p>
        </section>

        {/* 2. Dải chọn mã cổ phiếu & Câu hỏi gợi ý (Horizontal Pills) */}
        <section className={styles.suggestionsSection}>
          <span className={styles.suggestionsLabel}>Mã cổ phiếu tiêu biểu</span>
          <div className={styles.suggestionPills}>
            {popularTickers.map((t) => (
              <button
                key={t}
                type="button"
                className={styles.suggestionPill}
                style={
                  activeSymbol === t
                    ? { backgroundColor: "#1D1D1F", color: "#FFFFFF", borderColor: "#1D1D1F" }
                    : undefined
                }
                onClick={() => handleSelectTicker(t)}
              >
                {t}
              </button>
            ))}
            {activeSymbol && !popularTickers.includes(activeSymbol) && (
              <button
                type="button"
                className={styles.suggestionPill}
                style={{ backgroundColor: "#1D1D1F", color: "#FFFFFF", borderColor: "#1D1D1F" }}
                onClick={() => handleSelectTicker(activeSymbol)}
              >
                {activeSymbol}
              </button>
            )}
          </div>

          <span className={styles.suggestionsLabel}>
            {activeSymbol ? `Gợi ý câu hỏi cho ${activeSymbol}` : "Gợi ý phân tích nhanh"}
          </span>
          <div className={styles.suggestionPills}>
            {currentPrompts.map((item, idx) => (
              <button
                key={idx}
                type="button"
                className={styles.suggestionPill}
                onClick={() => setQuestion(item.query)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </section>

        {/* 3. Khung Phạm vi công cụ (Collapsible / Clean White Card) */}
        <section className={styles.scopeCard}>
          <div className={styles.scopeHeader}>
            <span className={styles.scopeTitle}>
              Phạm vi công cụ phân tích ({selectedTools.length}/{toolOptions.length})
            </span>
            <div style={{ display: "flex", gap: "6px" }}>
              <button
                type="button"
                className={styles.suggestionPill}
                style={{ padding: "4px 10px", fontSize: "11px" }}
                onClick={() => setSelectedTools(toolOptions.map((t) => t.name))}
              >
                Tất cả
              </button>
              <button
                type="button"
                className={styles.suggestionPill}
                style={{ padding: "4px 10px", fontSize: "11px" }}
                onClick={() => setSelectedTools([])}
              >
                Bỏ chọn
              </button>
            </div>
          </div>
          <div className={styles.scopeGrid}>
            {toolOptions.map((tool) => (
              <label key={tool.name} className={styles.scopeItem}>
                <input
                  type="checkbox"
                  className={styles.scopeCheckbox}
                  checked={selectedTools.includes(tool.name)}
                  onChange={() => toggleTool(tool.name)}
                />
                <span>{tool.label}</span>
              </label>
            ))}
          </div>
        </section>

        {/* 4. Khu vực Hiển thị Kết quả AI (Editorial Reading Canvas) */}
        {error && (
          <div className={styles.resultCard} style={{ borderColor: "rgba(217, 48, 37, 0.25)" }}>
            <div style={{ color: "#D93025", fontSize: "14px", fontWeight: 600 }}>
              Không thể hoàn tất phân tích
            </div>
            <p style={{ margin: 0, fontSize: "13.5px", color: "#6E6E73" }}>{error}</p>
          </div>
        )}

        {answer && (
          <article ref={answerSectionRef} className={styles.resultCard}>
            <header className={styles.resultHeader}>
              <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                <span className={styles.statusBadge}>
                  {answer.symbol ? `MÃ: ${answer.symbol}` : "TOÀN CẢNH"}
                </span>
                <span className={styles.statusBadge}>
                  {answer.status?.replace(/_/g, " ") || "HOÀN TẤT"}
                </span>
                {Boolean(answer.metadata_flags?.ias33_adjusted) && (
                  <span className={styles.iasWarningBadge}>⚠️ IAS 33 ADJUSTED</span>
                )}
                {Boolean(answer.symbol === "VNINDEX" || answer.citations?.some((c) => c.note?.includes("Proxy") || c.note?.includes("đại diện"))) && (
                  <span className={styles.iasWarningBadge} style={{ background: "rgba(255, 149, 0, 0.12)", color: "#c96500", border: "1px solid rgba(255, 149, 0, 0.3)" }}>
                    ⚠️ BỐI CẢNH ĐẠI DIỆN / PROXY CONTEXT (VN100)
                  </span>
                )}
              </div>
              <div style={{ fontSize: "12px", color: "#6E6E73", display: "flex", gap: "10px", alignItems: "center" }}>
                <span>{answer.model || "qwen3.5:9b-q4_K_M"}</span>
                {answer.usage?.total_duration ? (
                  <span>· {usageValue(answer.usage.total_duration, 1e9)}s</span>
                ) : null}
              </div>
            </header>

            <div className={styles.answerProse}>
              {renderAnswerWithCitations(answer.answer, answer.citations || [])}
            </div>

            {(answer.status === "PARTIAL_DATA_ONLY" || answer.structured_data_summary) && (
              <AppleSmartFallback
                summary={answer.structured_data_summary}
                metadataFlags={answer.metadata_flags}
                isFallbackMode={answer.status === "PARTIAL_DATA_ONLY"}
              />
            )}

            {answer.claims && answer.claims.length > 0 && (
              <div className={styles.claimsSection}>
                <span className={styles.suggestionsLabel}>MỆNH ĐỀ PHÂN TÍCH ĐÃ ĐỐI SOÁT ({answer.claims.length})</span>
                {answer.claims.map((claim, idx) => (
                  <div key={idx} className={styles.claimRow}>
                    <div>
                      <strong style={{ fontSize: "11px", color: "#6E6E73", textTransform: "uppercase", display: "block", marginBottom: "2px" }}>
                        {claim.claim_type}
                      </strong>
                      <span>{claim.text}</span>
                    </div>
                    {claim.citation_ids && claim.citation_ids.length > 0 && (
                      <div style={{ display: "inline-flex", gap: "4px", flexShrink: 0 }}>
                        {claim.citation_ids.map((id) => (
                          <AppleCitationPill
                            key={id}
                            id={id}
                            citation={answer.citations?.find((c) => c.id.toUpperCase() === id.toUpperCase())}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {answer.uncertainty && answer.uncertainty.length > 0 && (
              <div className={styles.uncertaintySection}>
                <span className={styles.suggestionsLabel}>LƯU Ý DỮ LIỆU & RỦI RO ({answer.uncertainty.length})</span>
                <ul className={styles.uncertaintyList}>
                  {answer.uncertainty.map((item, idx) => (
                    <li key={idx} className={styles.uncertaintyItem}>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </article>
        )}
      </div>

      {/* 5. Thanh Nhập Liệu Nổi ở Đáy (Sticky Bottom Floating Dock) */}
      <div className={styles.bottomDock}>
        <div className={styles.dockInner}>
          {busy && (
            <div className={styles.sseStatusPill}>
              <div className={styles.pulseDot} />
              <span>{streamMessage || "AI đang phân tích..."}</span>
              <button
                type="button"
                onClick={handleCancelStream}
                style={{
                  background: "none",
                  border: "none",
                  color: "#86868B",
                  cursor: "pointer",
                  fontSize: "13px",
                  marginLeft: "4px",
                  padding: "0 4px",
                }}
                title="Hủy phân tích"
              >
                ✕
              </button>
            </div>
          )}

          <form className={styles.promptBox} onSubmit={ask}>
            <input
              type="text"
              className={styles.tickerInput}
              placeholder="MÃ CP"
              maxLength={10}
              value={activeSymbol}
              onChange={(e) => {
                const val = e.target.value.toUpperCase();
                setActiveSymbol(val);
              }}
              title="Mã cổ phiếu (để trống nếu hỏi toàn cảnh)"
            />

            <textarea
              className={styles.promptTextarea}
              rows={1}
              placeholder={
                activeSymbol
                  ? `Hỏi chuyên sâu về mã ${activeSymbol} (P/E, biên LN, nợ vay, rủi ro)...`
                  : "Hỏi AI về cổ phiếu, định giá P/E, BCTC, vĩ mô..."
              }
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  if (question.trim() && !busy) {
                    ask(e);
                  }
                }
              }}
              required
            />

            <button
              type="submit"
              className={styles.submitBtn}
              disabled={busy || !question.trim() || selectedTools.length === 0}
            >
              {busy ? "Đang xử lý…" : "Gửi câu hỏi"}
            </button>
          </form>

          <p className={styles.disclaimerText}>
            Dữ liệu đối soát 100% cục bộ (Local-First). Không gửi dữ liệu nội bộ ra bên ngoài.
          </p>
        </div>
      </div>
    </div>
  );
}

export default function AIResearchPage() {
  return (
    <Suspense
      fallback={
        <div className={styles.pageWrapper}>
          <div className={styles.centerContainer}>
            <p className={styles.heroSubtitle}>Đang chuẩn bị không gian làm việc...</p>
          </div>
        </div>
      }
    >
      <AIWorkspaceContent />
    </Suspense>
  );
}
