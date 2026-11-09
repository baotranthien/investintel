"use client";

import React, { FormEvent, startTransition, useEffect, useMemo, useRef, useState, Suspense, type JSX } from "react";
import { useSearchParams } from "next/navigation";
import {
  getAIStatus,
  streamAIChat,
  type AIChatResponse,
  type AIClaim,
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
import { QuantCoreOrb3D } from "@/components/three/quant-core-orb-3d";
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

function renderClaimText(claim: AIClaim) {
  const text = claim.text;

  // 1. Phân tích kết luận khuyến nghị đầu tư (KẾT LUẬN & KHUYẾN NGHỊ ĐẦU TƯ)
  if (text.includes("KẾT LUẬN & KHUYẾN NGHỊ") || text.includes("KHUYẾN NGHỊ ĐẦU TƯ")) {
    const basisIdx = text.indexOf("Cơ sở định lượng:");
    const strategyIdx = text.indexOf("Chiến lược hành động:");

    let titlePart = text;
    let basisPart = "";
    let strategyPart = "";

    if (basisIdx !== -1) {
      titlePart = text.slice(0, basisIdx).trim().replace(/\.$/, "");
      if (strategyIdx !== -1) {
        basisPart = text.slice(basisIdx, strategyIdx).trim().replace(/\.$/, "");
        strategyPart = text.slice(strategyIdx).trim();
      } else {
        basisPart = text.slice(basisIdx).trim();
      }
    } else if (strategyIdx !== -1) {
      titlePart = text.slice(0, strategyIdx).trim().replace(/\.$/, "");
      strategyPart = text.slice(strategyIdx).trim();
    }

    return (
      <div className={styles.verdictContent}>
        <div className={styles.verdictTitle}>{titlePart}</div>
        {basisPart && (
          <p className={styles.verdictParagraph}>
            <span className={styles.verdictLead}>Cơ sở định lượng:</span>{" "}
            {basisPart.replace(/^Cơ sở định lượng:\s*/i, "")}
          </p>
        )}
        {strategyPart && (
          <p className={styles.verdictParagraph}>
            <span className={styles.verdictLead}>Chiến lược hành động:</span>{" "}
            {strategyPart.replace(/^Chiến lược hành động:\s*/i, "")}
          </p>
        )}
      </div>
    );
  }

  // 2. Phân tích lựa chọn ưu tiên so sánh đa mã (🏆 LỰA CHỌN ƯU TIÊN)
  if (text.includes("🏆 LỰA CHỌN ƯU TIÊN")) {
    const colonIdx = text.indexOf(":");
    if (colonIdx !== -1) {
      const title = text.slice(0, colonIdx + 1).trim();
      const body = text.slice(colonIdx + 1).trim();
      return (
        <div className={styles.verdictContent}>
          <div className={styles.verdictTitle}>{title}</div>
          <p className={styles.verdictParagraph}>{body}</p>
        </div>
      );
    }
  }

  // 3. Các claim thông thường (FACT / MODEL_OUTPUT khác): Trình bày thành đoạn văn nằm ngang full width
  return <p className={styles.claimText}>{text}</p>;
}

export type AIHistoryItem = {
  id: string;
  timestamp: number;
  symbol: string;
  question: string;
  answer: AIChatResponse;
};

export type AICurrentSession = {
  activeSymbol: string;
  question: string;
  answer: AIChatResponse | null;
  updatedAt: number;
};

const CURRENT_SESSION_KEY = "investintel:ai:current_session:v1";
const HISTORY_KEY = "investintel:ai:history:v1";

function readCurrentSession(): AICurrentSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(CURRENT_SESSION_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function writeCurrentSession(session: AICurrentSession): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(CURRENT_SESSION_KEY, JSON.stringify(session));
  } catch {}
}

function readHistory(): AIHistoryItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeHistory(items: AIHistoryItem[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, 30)));
  } catch {}
}

function formatHistoryTime(ts: number): string {
  const diff = Date.now() - ts;
  if (diff < 60_000) return "Vừa xong";
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)} phút trước`;
  const d = new Date(ts);
  return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
}

type StreamListener = {
  onStatusUpdate?: (step: AIStreamStep, message: string) => void;
  onSuccess?: (response: AIChatResponse) => void;
  onError?: (error: Error) => void;
  onBusyChange?: (busy: boolean) => void;
};

class AIBackgroundStreamManager {
  private controller: AbortController | null = null;
  private busy = false;
  private currentStep: AIStreamStep | null = null;
  private currentMessage = "";
  private activeSymbol = "";
  private currentQuestion = "";
  private listeners = new Set<StreamListener>();

  public isBusy(): boolean {
    return this.busy;
  }

  public getStatus() {
    return {
      busy: this.busy,
      step: this.currentStep,
      message: this.currentMessage,
      symbol: this.activeSymbol,
      question: this.currentQuestion,
    };
  }

  public subscribe(listener: StreamListener): () => void {
    this.listeners.add(listener);
    if (this.busy) {
      listener.onBusyChange?.(true);
      if (this.currentStep && this.currentMessage) {
        listener.onStatusUpdate?.(this.currentStep, this.currentMessage);
      }
    }
    return () => {
      this.listeners.delete(listener);
    };
  }

  public cancel(): void {
    if (this.controller) {
      this.controller.abort();
      this.controller = null;
    }
    this.busy = false;
    this.currentStep = null;
    this.currentMessage = "";
    for (const l of this.listeners) {
      l.onBusyChange?.(false);
      l.onStatusUpdate?.("fetching_data", "Đã hủy phân tích theo yêu cầu.");
    }
  }

  public async startStream(
    symbol: string,
    question: string,
    asOf: string,
    selectedTools: AIToolName[]
  ): Promise<void> {
    if (this.busy) return;

    this.busy = true;
    this.activeSymbol = symbol;
    this.currentQuestion = question;
    this.currentStep = "fetching_data";
    this.currentMessage = "Đang khởi tạo kết nối luồng phân tích...";
    this.controller = new AbortController();

    for (const l of this.listeners) {
      l.onBusyChange?.(true);
      l.onStatusUpdate?.(this.currentStep, this.currentMessage);
    }

    try {
      const finalResponse = await streamAIChat(
        {
          symbol: symbol.trim() || undefined,
          question: question.trim(),
          as_of_date: asOf || undefined,
          tool_names: selectedTools,
        },
        {
          onStatusUpdate: (step: AIStreamStep, msg: string) => {
            this.currentStep = step;
            this.currentMessage = msg;
            for (const l of this.listeners) {
              l.onStatusUpdate?.(step, msg);
            }
          },
          onResult: (resultData: AIChatResponse) => {
            writeCurrentSession({
              activeSymbol: resultData.symbol || symbol,
              question,
              answer: resultData,
              updatedAt: Date.now(),
            });
            for (const l of this.listeners) {
              l.onSuccess?.(resultData);
            }
          },
        },
        this.controller.signal
      );

      if (finalResponse) {
        writeCurrentSession({
          activeSymbol: finalResponse.symbol || symbol,
          question,
          answer: finalResponse,
          updatedAt: Date.now(),
        });

        const history = readHistory();
        const itemSymbol = finalResponse.symbol || symbol || "TOÀN CẢNH";
        const newItem: AIHistoryItem = {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          timestamp: Date.now(),
          symbol: itemSymbol,
          question,
          answer: finalResponse,
        };
        const filtered = history.filter(
          (h) => !(h.symbol === newItem.symbol && h.question.trim() === newItem.question.trim())
        );
        writeHistory([newItem, ...filtered]);

        for (const l of this.listeners) {
          l.onSuccess?.(finalResponse);
        }
      }
    } catch (err: unknown) {
      if ((err as Error)?.name !== "AbortError") {
        for (const l of this.listeners) {
          l.onError?.(err instanceof Error ? err : new Error(String(err)));
        }
      }
    } finally {
      this.busy = false;
      this.currentStep = null;
      this.currentMessage = "";
      this.controller = null;
      for (const l of this.listeners) {
        l.onBusyChange?.(false);
      }
    }
  }
}

const backgroundStream = new AIBackgroundStreamManager();

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
  const [history, setHistory] = useState<AIHistoryItem[]>([]);
  const [isClient, setIsClient] = useState(false);

  // Background fetch of AI Model Status via SWR Cache without blocking UI
  const { data: aiStatus, isLoading: isStatusLoading } = useCachedResource<AIStatus>(
    "ai-status",
    () => getAIStatus(),
    { maxAgeMs: 60_000 }
  );

  const answerSectionRef = useRef<HTMLElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Navigation tracking ref to ensure idempotency and prevent overwriting user edits
  const lastHandledKeyRef = useRef<string>("");
  const isMountedRef = useRef<boolean>(false);

  // 1. Initial client-side state hydration from localStorage
  useEffect(() => {
    setIsClient(true);
    const storedHistory = readHistory();
    setHistory(storedHistory);

    const session = readCurrentSession();
    const validTicker = normalizeTicker(symbolParam);

    // Case 1: URL has no specific ticker or question (e.g. user navigated from sidebar /ai or home)
    if (!validTicker && !qParam) {
      if (session && session.answer) {
        if (session.activeSymbol) setActiveSymbol(session.activeSymbol);
        if (session.question) setQuestion(session.question);
        setAnswer(session.answer);
        return;
      }
      if (storedHistory.length > 0 && storedHistory[0].answer) {
        const latest = storedHistory[0];
        setActiveSymbol(latest.symbol === "TOÀN CẢNH" ? "" : latest.symbol);
        setQuestion(latest.question);
        setAnswer(latest.answer);
        return;
      }
    }

    // Case 2: URL has a specific ticker (e.g. from /opportunities or query)
    if (validTicker) {
      // 2a: Check if current session matches this ticker
      if (
        session &&
        session.answer &&
        session.activeSymbol?.toUpperCase() === validTicker.toUpperCase()
      ) {
        setActiveSymbol(session.activeSymbol);
        if (session.question) setQuestion(session.question);
        setAnswer(session.answer);
        return;
      }

      // 2b: Check if history has a previous answer for this ticker
      const matched = storedHistory.find(
        (h) => h.symbol?.toUpperCase() === validTicker.toUpperCase()
      );
      if (matched && matched.answer) {
        setActiveSymbol(validTicker);
        setQuestion(matched.question);
        setAnswer(matched.answer);
        return;
      }
    }

    // Case 3: Fallback restore if session has any answer and no question in URL
    if (!qParam && session?.answer) {
      if (session.activeSymbol) setActiveSymbol(session.activeSymbol);
      if (session.question) setQuestion(session.question);
      setAnswer(session.answer);
    }
  }, []);

  // 1b. Auto-persist whenever answer, activeSymbol, or question updates
  useEffect(() => {
    if (!answer) return;

    const sym = answer.symbol || activeSymbol || "TOÀN CẢNH";
    const q = question.trim() || `Phân tích ${sym}`;

    writeCurrentSession({
      activeSymbol: sym === "TOÀN CẢNH" ? "" : sym,
      question: q,
      answer,
      updatedAt: Date.now(),
    });

    const currentHistory = readHistory();
    const existingIndex = currentHistory.findIndex(
      (h) =>
        h.symbol?.toUpperCase() === sym.toUpperCase() &&
        (h.question.trim() === q || h.answer.answer === answer.answer)
    );

    const newItem: AIHistoryItem = {
      id:
        existingIndex >= 0
          ? currentHistory[existingIndex].id
          : `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      timestamp: Date.now(),
      symbol: sym,
      question: q,
      answer,
    };

    const nextHistory = [
      newItem,
      ...currentHistory.filter((h) => h.id !== newItem.id),
    ].slice(0, 30);

    writeHistory(nextHistory);
    setHistory(nextHistory);
  }, [answer, activeSymbol, question]);

  // 2. Subscribe to background streaming runner
  useEffect(() => {
    const unsubscribe = backgroundStream.subscribe({
      onBusyChange: (isBusy) => {
        setBusy(isBusy);
      },
      onStatusUpdate: (step, msg) => {
        setStreamStep(step);
        setStreamMessage(msg);
      },
      onSuccess: (resp) => {
        startTransition(() => {
          setAnswer(resp);
          setHistory(readHistory());
          if (resp.symbol && !activeSymbol) {
            setActiveSymbol(resp.symbol);
          }
        });
        setTimeout(() => {
          answerSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 100);
      },
      onError: (err) => {
        setError(err.message || "Đã xảy ra lỗi không mong muốn");
      },
    });

    const currentStatus = backgroundStream.getStatus();
    if (currentStatus.busy) {
      setBusy(true);
      setStreamStep(currentStatus.step);
      setStreamMessage(currentStatus.message);
      if (currentStatus.symbol) setActiveSymbol(currentStatus.symbol);
      if (currentStatus.question) setQuestion(currentStatus.question);
    }

    return () => {
      unsubscribe();
    };
  }, [activeSymbol]);

  // 3. Handle client-side navigation transitions (e.g. clicking different opportunities while page is open)
  useEffect(() => {
    if (!isMountedRef.current) {
      isMountedRef.current = true;
      return;
    }

    const currentKey = `${symbolParam ?? ""}|${qParam ?? ""}|${sourceParam ?? ""}`;
    if (lastHandledKeyRef.current === currentKey) {
      return;
    }
    lastHandledKeyRef.current = currentKey;

    const validTicker = normalizeTicker(symbolParam);
    if (!validTicker && !qParam) {
      return;
    }

    const targetQuestion =
      validTicker && (sourceParam === "opportunities" || !qParam)
        ? buildOpportunityQuestion(validTicker)
        : (qParam?.trim() ?? "");

    if (validTicker) {
      setActiveSymbol(validTicker);
    }
    if (targetQuestion) {
      setQuestion(targetQuestion);
    }

    // Check if current_session already has an answer matching this ticker & question
    const session = readCurrentSession();
    if (
      session &&
      session.answer &&
      session.activeSymbol?.toUpperCase() === (validTicker || "").toUpperCase()
    ) {
      setAnswer(session.answer);
      setError(null);
      return;
    }

    // Check if history already has an answer matching this ticker & question
    const storedHistory = readHistory();
    const matched = storedHistory.find(
      (h) => h.symbol?.toUpperCase() === (validTicker || "").toUpperCase()
    );
    if (matched && matched.answer) {
      setAnswer(matched.answer);
      setError(null);
    } else {
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

  function handleSelectHistoryItem(item: AIHistoryItem) {
    setActiveSymbol(item.symbol === "TOÀN CẢNH" ? "" : item.symbol);
    setQuestion(item.question);
    setAnswer(item.answer);
    setError(null);
    writeCurrentSession({
      activeSymbol: item.symbol === "TOÀN CẢNH" ? "" : item.symbol,
      question: item.question,
      answer: item.answer,
      updatedAt: Date.now(),
    });
    setTimeout(() => {
      answerSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  }

  function handleDeleteHistoryItem(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    const next = history.filter((h) => h.id !== id);
    setHistory(next);
    writeHistory(next);
  }

  function handleClearAllHistory() {
    setHistory([]);
    writeHistory([]);
  }

  function toggleTool(name: AIToolName) {
    setSelectedTools((prev) => (prev.includes(name) ? prev.filter((item) => item !== name) : [...prev, name]));
  }

  function handleCancelStream() {
    backgroundStream.cancel();
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

    setError(null);
    setAnswer(null);

    await backgroundStream.startStream(activeSymbol, question, asOf, selectedTools);
  }

  return (
    <div className={styles.pageWrapper}>
      <div className={`${styles.centerContainer} ${answer ? styles.wideContainer : ""}`}>
        {/* 1. Header trang chuẩn mực PageHeader */}
        <PageHeader
          title="Trợ lý Nghiên cứu & Thẩm định Tài chính"
          description="Đối soát BCTC, định giá P/E, mô hình IAS 33 và độ nhạy vĩ mô — dựa 100% trên số liệu kiểm chứng, không bịa đặt thông tin."
          meta={
            <div style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
              <QuantCoreOrb3D
                status={busy ? "streaming" : isStatusLoading ? "checking" : aiStatus?.available ? "ready" : "idle"}
                size={26}
              />
              {isStatusLoading ? (
                <span className={styles.statusBadgeWrapper}>
                  <StatusBadge status="CHECKING" label="Đang kết nối mô hình..." />
                </span>
              ) : aiStatus ? (
              <span className={styles.statusBadgeWrapper}>
                {(() => {
                  const modelName = aiStatus.configured_models?.primary || "qwen3.5:9b-q4_K_M";
                  if (aiStatus.available) {
                    if (aiStatus.model_state === "LOADED") {
                      return (
                        <StatusBadge
                          status="HEALTHY"
                          label={`${modelName} · Sẵn sàng`}
                          title={`Mô hình ${modelName} đã nạp VRAM & sẵn sàng suy luận.`}
                        />
                      );
                    }
                    if (aiStatus.model_state === "STANDBY" || aiStatus.status === "DEGRADED") {
                      return (
                        <StatusBadge
                          status="AVAILABLE"
                          label={`${modelName} · Chế độ chờ`}
                          title={`Mô hình ${modelName} đã cài đặt cục bộ (sẵn sàng tự động nạp khi nhận câu hỏi).`}
                        />
                      );
                    }
                    return (
                      <StatusBadge
                        status="AVAILABLE"
                        label={modelName}
                        title="Mô hình cục bộ sẵn sàng"
                      />
                    );
                  }
                  return (
                    <StatusBadge
                      status="UNAVAILABLE"
                      label="AI Ngoại tuyến"
                      title={aiStatus.reason || "Dịch vụ AI chưa kết nối."}
                    />
                  );
                })()}
              </span>
            ) : (
              <span className={styles.statusBadgeWrapper}>
                <StatusBadge status="AVAILABLE" label="Local-First Model" />
              </span>
            )}
            </div>
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

        {/* 2.5 Lịch sử phân tích gần đây (Local-First Persistence Bar) */}
        {isClient && (
          <section className={styles.historySection}>
            <div className={styles.historyHeader}>
              <div className={styles.historyTitle}>
                <span>🕒 Lịch sử phân tích gần đây</span>
                <span className={styles.historyCountBadge}>{history.length}</span>
              </div>
              {history.length > 0 && (
                <button
                  type="button"
                  className={styles.historyClearBtn}
                  onClick={handleClearAllHistory}
                  title="Xóa toàn bộ lịch sử"
                >
                  Xóa tất cả
                </button>
              )}
            </div>

            {history.length > 0 ? (
              <div className={styles.historyList}>
                {history.map((item) => {
                  const isActive = Boolean(
                    answer &&
                    answer.answer === item.answer.answer &&
                    answer.symbol === item.answer.symbol
                  );
                  return (
                    <div
                      key={item.id}
                      className={`${styles.historyItem} ${isActive ? styles.historyItemActive : ""}`}
                      onClick={() => handleSelectHistoryItem(item)}
                      title={item.question}
                    >
                      <span className={styles.historyBadge}>{item.symbol}</span>
                      <div className={styles.historyContent}>
                        <span className={styles.historyQuestionText}>{item.question}</span>
                        <span className={styles.historyTimeText}>{formatHistoryTime(item.timestamp)}</span>
                      </div>
                      <button
                        type="button"
                        className={styles.historyDeleteBtn}
                        onClick={(e) => handleDeleteHistoryItem(e, item.id)}
                        title="Xóa mục này"
                      >
                        ✕
                      </button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className={styles.historyEmpty}>
                <span>Chưa có câu hỏi nào trong lịch sử. Khi bạn đặt câu hỏi và AI hoàn tất phân tích, kết quả sẽ tự động lưu vào đây để bạn bấm xem lại bất cứ lúc nào (kể cả khi chuyển trang).</span>
              </div>
            )}
          </section>
        )}

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
          <div className={styles.resultCard} style={{ borderColor: "var(--negative-border)" }}>
            <div style={{ color: "var(--negative)", fontSize: "14px", fontWeight: 600 }}>
              Không thể hoàn tất phân tích
            </div>
            <p style={{ margin: 0, fontSize: "13.5px", color: "var(--ink-secondary)" }}>{error}</p>
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
                      {answer.claims.map((claim, idx) => {
                        const isVerdict =
                          claim.claim_type === "MODEL_OUTPUT" &&
                          (claim.text.includes("KẾT LUẬN & KHUYẾN NGHỊ") ||
                            claim.text.includes("KHUYẾN NGHỊ ĐẦU TƯ") ||
                            claim.text.includes("LỰA CHỌN ƯU TIÊN"));
                        return (
                          <div
                            key={idx}
                            className={`${styles.claimRow} ${
                              claim.claim_type === "MODEL_OUTPUT" ? styles.claimRowModelOutput : ""
                            } ${isVerdict ? styles.claimRowVerdict : ""}`}
                          >
                            <div className={styles.claimHeader}>
                              <div className={styles.claimBadgeGroup}>
                                <span
                                  className={`${styles.claimTypeBadge} ${
                                    claim.claim_type === "MODEL_OUTPUT" ? styles.claimTypeBadgeModel : ""
                                  }`}
                                >
                                  {claim.claim_type}
                                </span>
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
                            <div className={styles.claimBodyWrapper}>
                              {renderClaimText(claim)}
                            </div>
                          </div>
                        );
                      })}
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
                  color: "var(--ink-muted)",
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
