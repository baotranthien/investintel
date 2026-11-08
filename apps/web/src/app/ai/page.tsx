"use client";

import React, { FormEvent, startTransition, useEffect, useMemo, useRef, useState, Suspense, type JSX } from "react";
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
import { Skeleton, SkeletonCard, SkeletonText } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { PageHeader } from "@/components/ui/page-header";
import { useCachedResource } from "@/lib/use-cached-resource";
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

type StarterPromptItem = {
  icon: string;
  tag: string;
  symbol: string;
  title: string;
  query: string;
  desc: string;
};

const defaultStarterPrompts: StarterPromptItem[] = [
  {
    icon: "🎯",
    tag: "Chất lượng lợi nhuận",
    symbol: "FPT",
    title: "Chất lượng LN & Dòng tiền FPT",
    query: "Phân tích chất lượng lợi nhuận và dòng tiền HĐKD của FPT quý gần nhất",
    desc: "Đối soát LNTT so với Dòng tiền thuần từ HĐKD (OCF) và các khoản phải thu",
  },
  {
    icon: "⚖️",
    tag: "Đối sánh ngành thép",
    symbol: "HPG",
    title: "Biên LN & Nợ vay HPG vs HSG",
    query: "So sánh biên lợi nhuận và cấu trúc nợ vay giữa HPG và HSG",
    desc: "So sánh biên gộp, tỷ lệ nợ vay trên vốn chủ sở hữu (D/E) và chi phí lãi vay",
  },
  {
    icon: "⚠️",
    tag: "Tầm soát rủi ro BCTC",
    symbol: "NVL",
    title: "Tầm soát rủi ro Bảng CĐKT NVL",
    query: "Tầm soát các dấu hiệu rủi ro trên Bảng cân đối kế toán của NVL",
    desc: "Kiểm tra áp lực nợ vay ngắn hạn, áp lực trái phiếu và tính thanh khoản tài sản",
  },
  {
    icon: "📊",
    tag: "Định giá lịch sử 5 năm",
    symbol: "VCB",
    title: "Định giá P/E & P/B 5 năm VCB",
    query: "Đánh giá định giá P/E và P/B hiện tại của VCB so với trung bình 5 năm",
    desc: "Đo lường độ lệch chuẩn định giá P/E, P/B và biên độ an toàn theo dữ liệu lịch sử",
  },
];

function getTickerStarterPrompts(sym: string): StarterPromptItem[] {
  const symbol = sym.toUpperCase().trim();
  return [
    {
      icon: "🎯",
      tag: "Chất lượng lợi nhuận",
      symbol,
      title: `Chất lượng LN & Dòng tiền ${symbol}`,
      query: `Phân tích chất lượng lợi nhuận và dòng tiền HĐKD của ${symbol} quý gần nhất`,
      desc: `Kiểm tra tương quan OCF với LNTT và chất lượng các khoản phải thu của ${symbol}`,
    },
    {
      icon: "⚖️",
      tag: "Biên LN & Cấu trúc nợ",
      symbol,
      title: `Biên LN & Cấu trúc nợ ${symbol}`,
      query: `So sánh biên lợi nhuận và cấu trúc nợ vay giữa ${symbol} và doanh nghiệp cùng ngành`,
      desc: `Phân tích cơ cấu nguồn vốn, tỷ lệ D/E và biên lợi nhuận hoạt động của ${symbol}`,
    },
    {
      icon: "⚠️",
      tag: "Tầm soát rủi ro BCTC",
      symbol,
      title: `Tầm soát rủi ro Bảng CĐKT ${symbol}`,
      query: `Tầm soát các dấu hiệu rủi ro trên Bảng cân đối kế toán của ${symbol}`,
      desc: `Rà soát các khoản nợ ngắn hạn, hàng tồn kho và các khoản mục bất thường`,
    },
    {
      icon: "📊",
      tag: "Định giá lịch sử 5 năm",
      symbol,
      title: `Định giá P/E & P/B 5 năm ${symbol}`,
      query: `Đánh giá định giá P/E và P/B hiện tại của ${symbol} so với trung bình 5 năm`,
      desc: `Xác định định giá P/E, P/B hiện tại đang cao hơn hay thấp hơn trung bình 5 năm`,
    },
  ];
}

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
  const [asOf] = useState("");
  const [selectedTools, setSelectedTools] = useState<AIToolName[]>(toolOptions.map((t) => t.name));
  const [busy, setBusy] = useState(false);
  const [, setStreamStep] = useState<AIStreamStep | null>(null);
  const [streamMessage, setStreamMessage] = useState("");
  const [answer, setAnswer] = useState<AIChatResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Background fetch of AI Model Status via SWR Cache without blocking UI
  const { data: aiStatus, isLoading: isStatusLoading } = useCachedResource<AIStatus>(
    "ai-status",
    () => getAIStatus(),
    { maxAgeMs: 60_000 }
  );

  const abortControllerRef = useRef<AbortController | null>(null);
  const answerSectionRef = useRef<HTMLElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Navigation tracking ref to ensure idempotency and prevent overwriting user edits
  const lastHandledKeyRef = useRef<string>(
    symbolParam || qParam || sourceParam
      ? `${symbolParam ?? ""}|${qParam ?? ""}|${sourceParam ?? ""}`
      : ""
  );

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

  const currentStarterPrompts = useMemo(() => {
    return activeSymbol ? getTickerStarterPrompts(activeSymbol) : defaultStarterPrompts;
  }, [activeSymbol]);

  const currentPrompts = useMemo(() => {
    return activeSymbol ? getStockPrompts(activeSymbol) : defaultMarketPrompts;
  }, [activeSymbol]);

  function handleSelectTicker(t: string) {
    const nextTicker = activeSymbol === t ? "" : t;
    setActiveSymbol(nextTicker);
    setQuestion("");
    setAnswer(null);
  }

  function handleSelectStarterPrompt(p: StarterPromptItem) {
    if (p.symbol && (!activeSymbol || activeSymbol !== p.symbol)) {
      setActiveSymbol(p.symbol);
    }
    setQuestion(p.query);
    textareaRef.current?.focus();
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

  function handleResetQuestion() {
    setAnswer(null);
    setError(null);
    setQuestion("");
    textareaRef.current?.focus();
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
      <div className={`${styles.centerContainer} ${answer ? styles.wideContainer : ""}`}>
        {/* 1. Header trang chuẩn mực PageHeader */}
        <PageHeader
          title="Trợ lý Nghiên cứu & Thẩm định Tài chính"
          description="Đối soát BCTC, định giá P/E, mô hình IAS 33 và độ nhạy vĩ mô — dựa 100% trên số liệu kiểm chứng, không bịa đặt thông tin."
          meta={
            isStatusLoading ? (
              <span className={styles.statusBadgeWrapper}>
                <StatusBadge status="CHECKING" label="Đang kết nối mô hình..." />
              </span>
            ) : aiStatus ? (
              <span className={styles.statusBadgeWrapper}>
                <StatusBadge
                  status={aiStatus.status}
                  label={aiStatus.configured_models?.primary || "Mô hình sẵn sàng"}
                  title={`Trạng thái: ${aiStatus.status}`}
                />
              </span>
            ) : (
              <span className={styles.statusBadgeWrapper}>
                <StatusBadge status="AVAILABLE" label="Local-First Model" />
              </span>
            )
          }
        />

        {/* 2. Dải chọn mã cổ phiếu & Gợi ý nhanh */}
        <section className={styles.suggestionsSection}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "8px" }}>
            <span className={styles.suggestionsLabel}>Mã cổ phiếu tiêu biểu</span>
            {activeSymbol && (
              <button
                type="button"
                className={styles.resetQuestionBtn}
                onClick={() => {
                  setActiveSymbol("");
                  setQuestion("");
                }}
              >
                Xóa bộ lọc mã ({activeSymbol})
              </button>
            )}
          </div>
          <div className={styles.suggestionPills}>
            {popularTickers.map((t) => (
              <button
                key={t}
                type="button"
                className={`${styles.suggestionPill} ${activeSymbol === t ? styles.suggestionPillActive : ""}`}
                onClick={() => handleSelectTicker(t)}
              >
                {t}
              </button>
            ))}
            {activeSymbol && !popularTickers.includes(activeSymbol) && (
              <button
                type="button"
                className={`${styles.suggestionPill} ${styles.suggestionPillActive}`}
                onClick={() => handleSelectTicker(activeSymbol)}
              >
                {activeSymbol}
              </button>
            )}
          </div>
        </section>

        {/* 3. Bốn Gợi ý Phân tích Mẫu (4 Starter Prompts) Nổi bật khi màn hình chờ */}
        {!answer && !busy && (
          <section className={styles.starterSection}>
            <div className={styles.starterHeader}>
              <span className={styles.starterTitleLabel}>
                {activeSymbol ? `Gợi ý phân tích chuyên sâu cho ${activeSymbol}` : "Gợi ý phân tích mẫu nổi bật"}
              </span>
            </div>
            <div className={styles.starterGrid}>
              {currentStarterPrompts.map((item, idx) => (
                <button
                  key={idx}
                  type="button"
                  className={styles.starterCard}
                  onClick={() => handleSelectStarterPrompt(item)}
                >
                  <div className={styles.starterCardTop}>
                    <span className={styles.starterIcon}>{item.icon}</span>
                    <span className={styles.starterTag}>{item.tag}</span>
                    <span className={styles.starterSymbolBadge}>{item.symbol}</span>
                  </div>
                  <div className={styles.starterTitle}>{item.title}</div>
                  <div className={styles.starterQuery}>"{item.query}"</div>
                  <div className={styles.starterDesc}>{item.desc}</div>
                </button>
              ))}
            </div>

            {/* Câu hỏi gợi ý bổ sung */}
            <div style={{ marginTop: "8px", display: "flex", flexDirection: "column", gap: "8px" }}>
              <span className={styles.suggestionsLabel}>
                {activeSymbol ? `Chủ đề khác liên quan đến ${activeSymbol}` : "Chủ đề phân tích thị trường"}
              </span>
              <div className={styles.suggestionPills}>
                {currentPrompts.map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className={styles.suggestionPill}
                    onClick={() => {
                      setQuestion(item.query);
                      textareaRef.current?.focus();
                    }}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* 4. Khung Phạm vi công cụ (Collapsible Tool Scope) */}
        <section className={styles.scopeCard}>
          <div className={styles.scopeHeader}>
            <span className={styles.scopeTitle}>
              Phạm vi công cụ phân tích ({selectedTools.length}/{toolOptions.length})
            </span>
            <div className={styles.scopeActions}>
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

        {/* 5. Thông báo lỗi nếu có */}
        {error && (
          <div className={styles.resultCard} style={{ borderColor: "rgba(217, 48, 37, 0.25)" }}>
            <div style={{ color: "#D93025", fontSize: "14px", fontWeight: 600 }}>
              Không thể hoàn tất phân tích
            </div>
            <p style={{ margin: 0, fontSize: "13.5px", color: "#6E6E73" }}>{error}</p>
          </div>
        )}

        {/* 6. Trạng thái Loading lúc đang gửi yêu cầu (Skeleton Feedback) */}
        {busy && !answer && (
          <div className={styles.loadingAnswerCard}>
            <div className={styles.loadingHeader}>
              <div className={styles.loadingHeaderInfo}>
                <div className={styles.pulseDot} />
                <span>{streamMessage || "AI đang tổng hợp và đối soát dữ liệu BCTC..."}</span>
              </div>
              <button type="button" onClick={handleCancelStream} className={styles.cancelBtn}>
                ✕ Hủy phân tích
              </button>
            </div>
            <SkeletonCard />
            <div style={{ marginTop: "12px" }}>
              <SkeletonText lines={4} lastLineWidth="65%" />
            </div>
          </div>
        )}

        {/* 7. Bố cục 2 Cột Desktop (Chat 60% + Evidence 40% Split View) */}
        {answer && (
          <div className={styles.splitLayout}>
            {/* Cột Trái (60%): Phân tích AI, Mệnh đề đối soát, Trích dẫn inline */}
            <section className={styles.leftColumn}>
              <article ref={answerSectionRef} className={styles.resultCard}>
                <header className={styles.resultHeader}>
                  <div className={styles.resultHeaderLeft}>
                    <StatusBadge
                      status={answer.status}
                      label={answer.symbol ? `MÃ: ${answer.symbol}` : "TOÀN CẢNH"}
                    />
                    <StatusBadge status={answer.status} />
                    {Boolean(answer.metadata_flags?.ias33_adjusted) && (
                      <span className={styles.iasWarningBadge}>⚠️ IAS 33 ADJUSTED</span>
                    )}
                    {Boolean(
                      answer.symbol === "VNINDEX" ||
                        answer.citations?.some(
                          (c) => c.note?.includes("Proxy") || c.note?.includes("đại diện")
                        )
                    ) && (
                      <span className={styles.proxyBadge}>
                        ⚠️ BỐI CẢNH ĐẠI DIỆN / PROXY CONTEXT (VN100)
                      </span>
                    )}
                  </div>
                  <div className={styles.resultHeaderRight}>
                    <span>{answer.model || "qwen3.5:9b-q4_K_M"}</span>
                    {answer.usage?.total_duration ? (
                      <span>· {usageValue(answer.usage.total_duration, 1e9)}s</span>
                    ) : null}
                    <button
                      type="button"
                      className={styles.resetQuestionBtn}
                      onClick={handleResetQuestion}
                      title="Đặt câu hỏi mới"
                    >
                      + Câu hỏi mới
                    </button>
                  </div>
                </header>

                {/* Banner tiến trình SSE nếu đang chạy */}
                {busy && (
                  <div className={styles.streamProgressBanner}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <div className={styles.pulseDot} />
                      <span>{streamMessage || "AI đang tiến hành phân tích và đối soát..."}</span>
                    </div>
                    <button type="button" onClick={handleCancelStream} className={styles.cancelButton}>
                      ✕ Hủy
                    </button>
                  </div>
                )}

                {/* Nội dung phản hồi AI với Citation Pills */}
                <div className={styles.answerProse}>
                  {renderAnswerWithCitations(answer.answer, answer.citations || [])}
                </div>

                {/* Danh sách mệnh đề đối soát (Claims Section) */}
                {answer.claims && answer.claims.length > 0 && (
                  <div className={styles.claimsSection}>
                    <span className={styles.sectionTitle}>
                      Mệnh đề phân tích đã đối soát ({answer.claims.length})
                    </span>
                    <div className={styles.claimsList}>
                      {answer.claims.map((claim, idx) => (
                        <div key={idx} className={styles.claimRow}>
                          <div className={styles.claimContent}>
                            <span className={styles.claimTypeBadge}>{claim.claim_type}</span>
                            <p className={styles.claimText}>{claim.text}</p>
                          </div>
                          {claim.citation_ids && claim.citation_ids.length > 0 && (
                            <div className={styles.claimPills}>
                              {claim.citation_ids.map((id) => (
                                <AppleCitationPill
                                  key={id}
                                  id={id}
                                  citation={answer.citations?.find(
                                    (c) => c.id.toUpperCase() === id.toUpperCase()
                                  )}
                                />
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Lưu ý dữ liệu & Rủi ro */}
                {answer.uncertainty && answer.uncertainty.length > 0 && (
                  <div className={styles.uncertaintySection}>
                    <span className={styles.sectionTitle}>
                      Lưu ý dữ liệu & Rủi ro ({answer.uncertainty.length})
                    </span>
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
            </section>

            {/* Cột Phải (40%): Bằng chứng kiểm định & BCTC đối chứng */}
            <aside className={styles.rightColumn}>
              {/* Header Cột Phải */}
              <div className={styles.evidenceHeaderCard}>
                <div className={styles.evidenceHeaderTop}>
                  <span className={styles.evidenceIcon}>📋</span>
                  <div>
                    <h2 className={styles.evidenceTitle}>Bằng chứng &amp; Số liệu Đối chứng</h2>
                    <p className={styles.evidenceSubtitle}>
                      Kiểm định trực tiếp từ BCTC &amp; Nguồn dữ liệu số hóa
                    </p>
                  </div>
                </div>
                <div className={styles.evidenceMetaTags}>
                  <span className={styles.evidenceCountBadge}>
                    {answer.citations?.length || 0} Bằng chứng
                  </span>
                  {Boolean(answer.metadata_flags?.ias33_adjusted) && (
                    <span className={styles.iasEvidenceBadge}>⚠️ IAS 33 Adjusted</span>
                  )}
                  {Boolean(answer.metadata_flags?.eps_is_estimate) && (
                    <span className={styles.iasEvidenceBadge}>ⓘ EPS ước lượng (IAS 33)</span>
                  )}
                </div>
              </div>

              {/* Bảng số liệu BCTC & Fallback Thông minh */}
              {(answer.status === "PARTIAL_DATA_ONLY" || answer.structured_data_summary) && (
                <AppleSmartFallback
                  summary={answer.structured_data_summary}
                  metadataFlags={answer.metadata_flags}
                  isFallbackMode={answer.status === "PARTIAL_DATA_ONLY"}
                />
              )}

              {/* Danh sách Bằng chứng / Citations đối soát chi tiết */}
              {answer.citations && answer.citations.length > 0 ? (
                <div className={styles.evidenceList}>
                  <span className={styles.sectionTitle}>
                    Nguồn trích dẫn BCTC &amp; Hồ sơ ({answer.citations.length})
                  </span>
                  {answer.citations.map((c) => (
                    <div key={c.id} className={styles.evidenceCard}>
                      <div className={styles.evidenceCardHeader}>
                        <span className={styles.evidenceIdBadge}>{c.id}</span>
                        <span className={styles.evidenceModule}>{c.responsible_module}</span>
                        {c.freshness && (
                          <span className={styles.evidenceFreshness}>{c.freshness}</span>
                        )}
                      </div>
                      {c.note && <p className={styles.evidenceNote}>{c.note}</p>}
                      <div className={styles.evidenceFooter}>
                        {c.source && (
                          <span className={styles.evidenceSource}>
                            Nguồn: <strong>{c.source}</strong>
                          </span>
                        )}
                        {c.publication_date && (
                          <span className={styles.evidenceDate}>
                            Kỳ/Ngày: {c.publication_date}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className={styles.evidenceEmpty}>
                  <span>Chưa có trích dẫn BCTC riêng lẻ</span>
                </div>
              )}
            </aside>
          </div>
        )}
      </div>

      {/* 8. Thanh Nhập Liệu Nổi ở Đáy (Sticky Bottom Floating Dock) */}
      <div className={styles.bottomDock}>
        <div className={`${styles.dockInner} ${answer ? styles.dockInnerWide : ""}`}>
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
              ref={textareaRef}
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

/**
 * Fallback App Shell tĩnh hiển thị ngay lập tức khi hydration/SSR khởi tạo
 * Loại bỏ hoàn toàn màn hình trắng "Đang chuẩn bị không gian làm việc..."
 */
function AIShellFallback(): JSX.Element {
  return (
    <div className={styles.pageWrapper}>
      <div className={styles.centerContainer}>
        <PageHeader
          title="Trợ lý Nghiên cứu & Thẩm định Tài chính"
          description="Đối soát BCTC, định giá P/E, mô hình IAS 33 và độ nhạy vĩ mô — dựa 100% trên số liệu kiểm chứng, không bịa đặt thông tin."
          meta={
            <span className={styles.statusBadgeWrapper}>
              <StatusBadge status="CHECKING" label="Đang kết nối mô hình..." />
            </span>
          }
        />

        <section className={styles.starterSection}>
          <div className={styles.starterHeader}>
            <span className={styles.starterTitleLabel}>Gợi ý phân tích mẫu nổi bật</span>
          </div>
          <div className={styles.starterGrid}>
            {defaultStarterPrompts.map((item, idx) => (
              <div key={idx} className={styles.starterCard}>
                <div className={styles.starterCardTop}>
                  <span className={styles.starterIcon}>{item.icon}</span>
                  <span className={styles.starterTag}>{item.tag}</span>
                  <span className={styles.starterSymbolBadge}>{item.symbol}</span>
                </div>
                <div className={styles.starterTitle}>{item.title}</div>
                <div className={styles.starterQuery}>"{item.query}"</div>
                <div className={styles.starterDesc}>{item.desc}</div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className={styles.bottomDock}>
        <div className={styles.dockInner}>
          <div className={styles.promptBox}>
            <input
              type="text"
              className={styles.tickerInput}
              placeholder="MÃ CP"
              readOnly
            />
            <textarea
              className={styles.promptTextarea}
              rows={1}
              placeholder="Hỏi AI về cổ phiếu, định giá P/E, BCTC, vĩ mô..."
              readOnly
            />
            <button type="button" className={styles.submitBtn} disabled>
              Gửi câu hỏi
            </button>
          </div>
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
    <Suspense fallback={<AIShellFallback />}>
      <AIWorkspaceContent />
    </Suspense>
  );
}
