"use client";

import { FormEvent, startTransition, useEffect, useState } from "react";
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

type StatusResource = { state: "loading" } | { state: "ready"; value: AIStatus } | { state: "error"; message: string };

function Status({ value }: { value: string }) {
  const tone = value === "HEALTHY" || value === "AVAILABLE" ? styles.good : value === "DEGRADED" || value === "PARTIAL" ? styles.warn : styles.missing;
  return <span className={`${styles.status} ${tone}`}>{value.replaceAll("_", " ")}</span>;
}

function usageValue(value: unknown, divisor = 1) {
  return typeof value === "number" ? (value / divisor).toFixed(divisor === 1 ? 0 : 2) : "N/A";
}

export default function AIPage() {
  const [health, setHealth] = useState<StatusResource>({ state: "loading" });
  const [question, setQuestion] = useState("");
  const [symbol, setSymbol] = useState("");
  const [asOf, setAsOf] = useState("");
  const [selectedTools, setSelectedTools] = useState<AIToolName[]>(toolOptions.map((item) => item.name));
  const [answer, setAnswer] = useState<AIChatResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

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

  return <main className={styles.page}>
    <header className={styles.header}>
      <div><p className={styles.eyebrow}>LOCAL ANALYST / 6F</p><h1>AI Analyst <span>/ Trợ lý nghiên cứu</span></h1></div>
      <div className={styles.health} aria-live="polite">
        <span>OLLAMA</span><Status value={healthValue} />
        {health.state === "ready" && <small>{health.value.version ?? "Version unavailable"} / {health.value.configured_models?.primary ?? "Model not configured"} / {health.value.configured_model_loaded ? "model loaded" : "installed; cold start"}</small>}
        {health.state === "error" && <small>{health.message}</small>}
      </div>
    </header>

    <div className={styles.workspace}>
      <form className={styles.composer} onSubmit={ask}>
        <div className={styles.fieldRow}>
          <label>Mã cổ phiếu / Symbol<input value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} maxLength={20} placeholder="Không bắt buộc" /></label>
          <label>Ngày dữ liệu / As of<input type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} /></label>
        </div>
        <label>Câu hỏi / Question<textarea required minLength={2} maxLength={4000} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Hỏi về bằng chứng, thay đổi, định giá, rủi ro hoặc luận điểm..." /></label>
        <fieldset className={styles.toolScope}>
          <legend>Phạm vi công cụ / Data tools</legend>
          <div>{toolOptions.map((tool) => <label key={tool.name}>
            <input type="checkbox" checked={selectedTools.includes(tool.name)} onChange={() => toggleTool(tool.name)} />
            <span>{tool.label}</span>
          </label>)}</div>
        </fieldset>
        <button className={styles.submit} type="submit" disabled={busy || !question.trim() || selectedTools.length === 0}>
          {busy ? "Đang tổng hợp bằng chứng..." : "Hỏi AI Analyst"}
        </button>
        <p className={styles.localNote}>Local Ollama only / Dữ liệu danh mục không gửi tới dịch vụ LLM bên ngoài.</p>
      </form>

      <section className={styles.response} aria-live="polite">
        <header><h2>Phân tích / Analysis</h2>{answer && <Status value={answer.status} />}</header>
        {!answer && !error && <p className={styles.empty} role="status">Câu trả lời chỉ xuất hiện khi API cung cấp bằng chứng và mô hình khả dụng.</p>}
        {error && <div className={styles.error} role="alert"><strong>AI API unavailable</strong><span>{error}</span></div>}
        {answer && <>
          <p className={styles.answerText}>{answer.answer}</p>
          <div className={styles.metadata}>
            <span>{answer.model ?? "No model call"}</span><span>{answer.prompt_version}</span><span>As of {answer.as_of_date}</span>
            {typeof answer.usage.eval_count === "number" && <span>{usageValue(answer.usage.eval_count)} tokens</span>}
            {typeof answer.usage.total_duration_ns === "number" && <span>{usageValue(answer.usage.total_duration_ns, 1_000_000_000)} s</span>}
          </div>
          <section className={styles.claims}><h3>Claims / Luận cứ</h3>
            {answer.claims.length ? answer.claims.map((claim, index) => <article key={`${claim.claim_type}-${index}`}>
              <Status value={claim.claim_type} /><p>{claim.text}</p><small>{claim.citation_ids.join(", ") || "No citation"}</small>
            </article>) : <p className={styles.empty}>Không có claim được hỗ trợ.</p>}
          </section>
          {answer.uncertainty.length > 0 && <section className={styles.uncertainty}><h3>Thiếu dữ liệu / Uncertainty</h3>{answer.uncertainty.map((item, index) => <p key={index}>{item}</p>)}</section>}
          <details className={styles.citations} open={answer.citations.length > 0}>
            <summary>Evidence citations ({answer.citations.length})</summary>
            {answer.citations.map((citation) => <article key={citation.id}>
              <strong>{citation.id} / {citation.responsible_module}</strong><Status value={citation.freshness ?? "INSUFFICIENT_DATA"} />
              <p>{citation.source ?? "Source unavailable"} / {citation.data_origin ?? "Origin unavailable"}</p>
              <small>Observation {citation.observation_date ?? "N/A"} / publication {citation.publication_date ?? "N/A"}{citation.source_url ? ` / ${citation.source_url}` : ""}</small>
              {citation.note && <small>{citation.note}</small>}
            </article>)}
          </details>
        </>}
      </section>
    </div>
  </main>;
}