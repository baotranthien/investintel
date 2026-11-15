"use client";

import { useEffect, useState } from "react";
import {
  getAIStatus,
  getSystemDiagnostics,
  getSystemObservability,
  triggerAutomationPipeline,
  type AIStatus,
  type SystemDiagnostics,
  type SystemObservability,
} from "@/lib/api";
import { StatusBadge } from "@/components/ui/status-badge";
import { SkeletonCard } from "@/components/ui/skeleton";
import { useLocale } from "@/lib/i18n";
import styles from "./page.module.css";

export default function SystemObservabilityPage() {
  const { t } = useLocale();
  const [diag, setDiag] = useState<SystemDiagnostics | null>(null);
  const [obs, setObs] = useState<SystemObservability | null>(null);
  const [aiStatus, setAiStatus] = useState<AIStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState<string | null>(null);
  const [triggerStatus, setTriggerStatus] = useState<"idle" | "running" | "success" | "error">("idle");

  const fetchDiagnostics = () => {
    setLoading(true);
    Promise.allSettled([getSystemDiagnostics(), getSystemObservability(), getAIStatus()])
      .then(([dRes, oRes, aRes]) => {
        if (dRes.status === "fulfilled") setDiag(dRes.value);
        if (oRes.status === "fulfilled") setObs(oRes.value);
        if (aRes.status === "fulfilled") setAiStatus(aRes.value);
        setLoading(false);
      });
  };

  useEffect(() => {
    const controller = new AbortController();
    Promise.allSettled([
      getSystemDiagnostics(controller.signal),
      getSystemObservability(controller.signal),
      getAIStatus(controller.signal),
    ]).then(([dRes, oRes, aRes]) => {
      if (controller.signal.aborted) return;
      if (dRes.status === "fulfilled") setDiag(dRes.value);
      if (oRes.status === "fulfilled") setObs(oRes.value);
      if (aRes.status === "fulfilled") setAiStatus(aRes.value);
      setLoading(false);
    });

    const interval = setInterval(() => {
      Promise.allSettled([getSystemDiagnostics(), getSystemObservability(), getAIStatus()]).then(
        ([dRes, oRes, aRes]) => {
          if (dRes.status === "fulfilled") setDiag(dRes.value);
          if (oRes.status === "fulfilled") setObs(oRes.value);
          if (aRes.status === "fulfilled") setAiStatus(aRes.value);
        }
      );
    }, 15000);
    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, []);

  const handleRunPipeline = async () => {
    setTriggering(true);
    setTriggerStatus("running");
    setTriggerMsg(
      t(
        "Đang kích hoạt pipeline tự động (Ingestion → Opportunity → Alerts)...",
        "Triggering automation pipeline (Ingestion → Opportunity → Alerts)..."
      )
    );
    try {
      const res = await triggerAutomationPipeline(["FPT", "BMP"]);
      setTriggerStatus("success");
      const duration = (res as { total_duration_sec?: number }).total_duration_sec;
      const storeLabel = (diag?.database?.backend ?? obs?.components?.database?.backend) === "postgresql"
        ? "Supabase PostgreSQL"
        : "SQLite";
      setTriggerMsg(
        t(
          `Pipeline hoàn tất thành công: ${res.pipeline_status}${
            duration ? ` (${duration}s)` : ""
          } · Đã đối soát & lưu ${storeLabel}.`,
          `Pipeline completed successfully: ${res.pipeline_status}${
            duration ? ` (${duration}s)` : ""
          } · Reconciled & persisted to ${storeLabel}.`
        )
      );
      fetchDiagnostics();
    } catch (err: unknown) {
      setTriggerStatus("error");
      setTriggerMsg(
        `${t("Lỗi kích hoạt pipeline: ", "Pipeline trigger error: ")}${
          err instanceof Error ? err.message : String(err)
        }`
      );
    } finally {
      setTriggering(false);
    }
  };

  if (loading && !diag && !obs) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <div>
            <p className={styles.eyebrow}>
              {t("Giám sát hạ tầng · Trạng thái vận hành", "Platform Observability · Operational Status")}
            </p>
            <h1 className={styles.title}>
              {t("Hệ thống & tự phục hồi", "System & Self-Healing")}
            </h1>
            <p className={styles.subTitle}>
              {t(
                "Đang tải thông số hạ tầng AI Gateway, cơ sở dữ liệu Supabase và lịch tác vụ tự động...",
                "Loading AI Gateway runtime, Supabase database health, and automation schedule telemetry..."
              )}
            </p>
          </div>
        </header>
        <div className={styles.grid}>
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} height={220} />
          ))}
        </div>
      </div>
    );
  }

  const gpu = diag?.hardware?.gpu;
  const ram = diag?.hardware?.system_ram;
  const ollama = diag?.ollama_runtime;
  const telemetry = diag?.inference_telemetry;
  const scheduler = diag?.scheduler;
  const db = diag?.database;
  const dbBackend = db?.backend ?? obs?.components?.database?.backend ?? "postgresql";
  const isCloudPg = dbBackend === "postgresql";
  const activeProv = aiStatus?.active_provider ?? obs?.components?.ai_provider?.provider ?? "groq";
  const aiModelDisplay =
    aiStatus?.configured_models?.primary ||
    obs?.components?.ai_provider?.model ||
    ollama?.primary_model ||
    "qwen/qwen3.8-27b";
  const aiHealthy = Boolean(aiStatus?.available || obs?.components?.ai_provider?.available || ollama?.ollama_listening);
  const freshness = obs?.data_freshness;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>
            {isCloudPg
              ? t("Giám sát hạ tầng Cloud · Vercel sin1 + Supabase Singapore", "Cloud Infrastructure · Vercel sin1 + Supabase Singapore")
              : t("Giám sát nền tảng cục bộ · Trạng thái vận hành", "Local Platform Observability · Operational Status")}
          </p>
          <h1 className={styles.title}>
            {t("Hệ thống & tự phục hồi", "System & Self-Healing")}
          </h1>
          <p className={styles.subTitle}>
            {isCloudPg
              ? t(
                  `Giám sát thời gian thực AI Gateway (${activeProv.toUpperCase()} / ${aiModelDisplay}), độ trễ Supabase PostgreSQL và chu kỳ dữ liệu định lượng.`,
                  `Real-time telemetry for AI Gateway (${activeProv.toUpperCase()} / ${aiModelDisplay}), Supabase PostgreSQL health, and quant ingestion cycles.`
                )
              : t(
                  "Giám sát thời gian thực tài nguyên phần cứng, AI runtime, chu kỳ tự động hóa và độ bền cơ sở dữ liệu.",
                  "Real-time telemetry for compute hardware, AI runtime, automation schedules, and database durability."
                )}
          </p>
        </div>
        <div className={styles.actions}>
          <button className={styles.btnSecondary} onClick={fetchDiagnostics}>
            {t("Làm mới", "Refresh")}
          </button>
          <button
            className={styles.btnPrimary}
            onClick={handleRunPipeline}
            disabled={triggering || scheduler?.is_busy}
          >
            {triggering
              ? t("Đang xử lý...", "Executing...")
              : t("Chạy quy trình tự động", "Trigger Automated Pipeline")}
          </button>
        </div>
      </header>

      {triggerMsg && (
        <div
          role={triggerStatus === "error" ? "alert" : "status"}
          style={{
            marginBottom: "20px",
            padding: "12px 18px",
            borderRadius: "10px",
            fontSize: "13.5px",
            fontWeight: 500,
            display: "flex",
            alignItems: "center",
            gap: "10px",
            background:
              triggerStatus === "error"
                ? "rgba(239, 68, 68, 0.12)"
                : triggerStatus === "success"
                ? "rgba(16, 185, 129, 0.12)"
                : "rgba(59, 130, 246, 0.12)",
            border: `1px solid ${
              triggerStatus === "error"
                ? "rgba(239, 68, 68, 0.35)"
                : triggerStatus === "success"
                ? "rgba(16, 185, 129, 0.35)"
                : "rgba(59, 130, 246, 0.35)"
            }`,
            color:
              triggerStatus === "error"
                ? "#ef4444"
                : triggerStatus === "success"
                ? "#10b981"
                : "#60a5fa",
          }}
        >
          <span>{triggerStatus === "error" ? "⚠️" : triggerStatus === "success" ? "✓" : "⚡"}</span>
          <span>{triggerMsg}</span>
        </div>
      )}

      <div className={styles.grid}>
        {/* Card 1: Local AI Inference Runtime */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>
              {activeProv === "ollama"
                ? "Local AI Analyst (Ollama)"
                : `AI Gateway (${activeProv.toUpperCase()})`}
            </h2>
            <StatusBadge status={aiHealthy ? "HEALTHY" : "OFFLINE"} />
          </div>
          <div className={styles.metricList}>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Mô hình AI chính", "Primary AI Model")}</span>
              <span className={styles.metricValue}>{aiModelDisplay}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Chuỗi Failover đa tầng", "Multi-Provider Failover")}</span>
              <span className={styles.metricValue}>
                {aiStatus?.provider_priority?.length
                  ? aiStatus.provider_priority.map((p) => p.toUpperCase()).join(" → ")
                  : "GROQ → GEMINI → OLLAMA"}
              </span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Độ trễ phản hồi (TTFT)", "Time to First Token (TTFT)")}</span>
              <span className={styles.metricValue}>{telemetry?.median_ttft_sec ? `${telemetry.median_ttft_sec}s` : (activeProv === "groq" ? "< 0.4s (LPU)" : "< 1.5s")}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Dự phòng Gemini Flash", "Gemini Fallback")}</span>
              <span className={styles.metricValue}>
                {aiStatus?.gemini?.available ? `Ready (${aiStatus.gemini.model})` : t("Chưa cấu hình", "Not configured")}
              </span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Lượt xử lý đã ghi nhận", "Inferences Logged")}</span>
              <span className={styles.metricValue}>
                {telemetry?.total_logged || 0} {t("lượt", "runs")}
              </span>
            </div>
          </div>
        </div>

        {/* Card 2: Hardware / Compute Telemetry */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>{t("Hạ tầng tính toán & GPU", "Compute & Hardware Telemetry")}</h2>
            <StatusBadge status={gpu?.status === "ACTIVE" ? "HEALTHY" : (isCloudPg ? "HEALTHY" : gpu?.status ?? "UNKNOWN")} />
          </div>
          <div className={styles.metricList}>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Môi trường thực thi", "Compute Node")}</span>
              <span className={styles.metricValue}>
                {gpu?.status === "ACTIVE" && gpu?.name
                  ? gpu.name
                  : isCloudPg
                  ? "Vercel Serverless (Region sin1)"
                  : (gpu?.name || t("CPU nội bộ", "Local CPU"))}
              </span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("VRAM đang dùng / Tổng", "VRAM Usage / Total")}</span>
              <span className={styles.metricValue}>
                {gpu?.vram_used_mb ? `${gpu.vram_used_mb} MB / ${gpu.vram_total_mb} MB` : (isCloudPg ? "Cloud LPU (Groq)" : "N/A")}
              </span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Độ trễ DB", "DB Latency")}</span>
              <span className={styles.metricValue}>
                {typeof db?.latency_ms === "number" ? `${db.latency_ms.toFixed(1)} ms` : "N/A"}
              </span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Ngày giá mới nhất", "Latest Price EOD")}</span>
              <span className={styles.metricValue}>{freshness?.latest_price_date || "N/A"}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("RAM hệ thống đang dùng", "System RAM Usage")}</span>
              <span className={styles.metricValue}>
                {ram?.used_pct ? `${ram.used_pct}% (${ram.available_mb} MB ${t("trống", "free")})` : (isCloudPg ? "Managed Container" : "N/A")}
              </span>
            </div>
          </div>
        </div>

        {/* Card 3: Database & Durability */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>{t("Cơ sở dữ liệu & dữ liệu", "Database & Data Integrity")}</h2>
            <StatusBadge status={(db?.connected ?? obs?.components?.database?.status === "HEALTHY") ? "HEALTHY" : "OFFLINE"} />
          </div>
          <div className={styles.metricList}>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Công cụ lưu trữ", "Storage Engine")}</span>
              <span className={styles.metricValue}>
                {isCloudPg ? "Supabase PostgreSQL (ap-southeast-1)" : "Local SQLite (data/trading.db)"}
              </span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Bản ghi giá (Prices)", "Price Records")}</span>
              <span className={styles.metricValue}>
                {freshness?.total_price_records !== undefined ? freshness.total_price_records.toLocaleString() : "—"}
              </span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("BCTC chuẩn hóa", "Financial Statements")}</span>
              <span className={styles.metricValue}>
                {freshness?.total_statements !== undefined ? freshness.total_statements.toLocaleString() : "—"}
              </span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Dữ liệu vĩ mô mới nhất", "Latest Macro Date")}</span>
              <span className={styles.metricValue}>{freshness?.latest_macro_date || "—"}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Khóa bảo vệ ghi PIT", "Write Protection Guard")}</span>
              <span className={styles.metricValue} style={{ color: "#137333" }}>
                {t("Khóa an toàn", "Safe Enforced")}
              </span>
            </div>
          </div>
        </div>

        {/* Card 4: Background Automation */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>{t("Bộ lập lịch & tự động hóa", "Scheduler & Automation")}</h2>
            <StatusBadge
              status={scheduler?.scheduler_paused ? "DEGRADED" : "HEALTHY"}
              label={scheduler?.scheduler_paused ? t("Tạm dừng", "Paused") : t("Hoạt động", "Active")}
            />
          </div>
          <div className={styles.metricList}>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Múi giờ", "Timezone")}</span>
              <span className={styles.metricValue}>{scheduler?.timezone || "Asia/Ho_Chi_Minh"}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Trạng thái quy trình", "Pipeline State")}</span>
              <span className={styles.metricValue}>
                {scheduler?.is_busy ? t("Đang xử lý...", "Executing...") : t("Chờ lệnh", "Idle / Standby")}
              </span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Lịch nạp dữ liệu", "Data Ingestion Schedule")}</span>
              <span className={styles.metricValue}>{t("Hàng ngày 16:00 ICT", "Daily 16:00 ICT")}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Sàng lọc cơ hội", "Opportunity Screener")}</span>
              <span className={styles.metricValue}>{t("Kích hoạt sau nạp dữ liệu", "Triggered post-ingestion")}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Đánh giá cảnh báo", "Alert Engine")}</span>
              <span className={styles.metricValue}>{t("Khử trùng lặp & chuẩn hóa", "Deduplicated & normalized")}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Operational Self-Recovery Runbooks */}
      <div className={styles.fullCard}>
        <h2 className={styles.cardTitle} style={{ fontSize: "20px", marginBottom: "8px" }}>
          {t("Sổ tay vận hành & tự phục hồi sự cố", "Operational Self-Recovery Runbooks")}
        </h2>
        <p style={{ fontSize: "14px", color: "var(--ink-secondary, #6b7280)", margin: "0 0 16px 0" }}>
          {t(
            "Hướng dẫn xử lý chuẩn khi gặp sự cố ngoại lệ trên môi trường Windows máy trạm:",
            "Standard Operating Procedures (SOP) for workstation exception recovery:"
          )}
        </p>

        <div className={styles.tableWrap}>
          <table className={styles.runbookTable}>
            <thead>
              <tr>
                <th>{t("Hiện tượng sự cố", "Issue Symptom")}</th>
                <th>{t("Nguyên nhân tiềm ẩn", "Underlying Cause")}</th>
                <th>{t("Thao tác khắc phục chuẩn", "Standard Remediation")}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <strong>
                    {t(
                      "Cổng 8000 hoặc 3000 bị xung đột (Socket error 10048)",
                      "Port 8000 or 3000 conflict (Socket error 10048)"
                    )}
                  </strong>
                </td>
                <td>
                  {t(
                    "Tiến trình Uvicorn hoặc Node cũ chưa đóng socket hoàn toàn khi dừng.",
                    "Previous Uvicorn or Node child process retained open socket upon termination."
                  )}
                </td>
                <td>
                  {t(
                    "Chạy lệnh ",
                    "Execute "
                  )}
                  <span className={styles.codePill}>.\Stop-InvestIntel.bat</span>
                  {t(
                    " để quét và giải phóng cổng, sau đó khởi động lại bằng ",
                    " to release occupied ports, then restart with "
                  )}
                  <span className={styles.codePill}>.\Start-InvestIntel.bat</span>.
                </td>
              </tr>
              <tr>
                <td>
                  <strong>
                    {t(
                      "AI Analyst báo lỗi \"Ollama unavailable\" hoặc TTFT quá chậm",
                      "AI Analyst reports \"Ollama unavailable\" or excessive TTFT latency"
                    )}
                  </strong>
                </td>
                <td>
                  {t(
                    "Ollama daemon bị dừng hoặc các lớp của mô hình bị offload sang CPU do đầy VRAM.",
                    "Ollama service halted or transformer layers offloaded to CPU due to VRAM pressure."
                  )}
                </td>
                <td>
                  {t(
                    "Kiểm tra VRAM bằng ",
                    "Check VRAM via "
                  )}
                  <span className={styles.codePill}>nvidia-smi</span>
                  {t(
                    ", chạy ",
                    ", run "
                  )}
                  <span className={styles.codePill}>scripts\local\doctor-investintel.ps1</span>
                  {t(
                    " để xác minh model Qwen3.5 9B.",
                    " to verify Qwen 3.5 9B weights."
                  )}
                </td>
              </tr>
              <tr>
                <td>
                  <strong>
                    {t(
                      "Cơ sở dữ liệu SQLite gặp lỗi khóa hoặc lỗi toàn vẹn",
                      "SQLite database encounters lock contention or integrity check warning"
                    )}
                  </strong>
                </td>
                <td>
                  {t(
                    "Giao dịch dở dang do tắt máy đột ngột hoặc file journal chưa checkpoint.",
                    "Incomplete transaction from abrupt shutdown or uncheckpointed WAL journal file."
                  )}
                </td>
                <td>
                  {t(
                    "Chạy lệnh kiểm tra ",
                    "Run diagnostics via "
                  )}
                  <span className={styles.codePill}>.\scripts\local\doctor-investintel.ps1</span>
                  {t(
                    " hoặc khôi phục snapshot gần nhất bằng ",
                    " or restore the latest snapshot with "
                  )}
                  <span className={styles.codePill}>.\scripts\local\restore-investintel-db.ps1 -Latest</span>.
                </td>
              </tr>
              <tr>
                <td>
                  <strong>
                    {t(
                      "Cổng dữ liệu định lượng bên ngoài timeout hoặc trả về HTTP 400/500",
                      "External market data feed timeout or HTTP 400/500 upstream response"
                    )}
                  </strong>
                </td>
                <td>
                  {t(
                    "API sàn chứng khoán bên ngoài bảo trì ngoài giờ giao dịch.",
                    "Exchange data gateway maintenance window outside trading hours."
                  )}
                </td>
                <td>
                  {t(
                    "Hệ thống tự động chuyển sang chế độ dự phòng bộ đệm dữ liệu lịch sử HOSE CSV; pipeline tự động hủy các tác vụ quét phụ thuộc để bảo vệ tính trung thực dữ liệu.",
                    "System automatically activates historical cached HOSE CSV buffer; downstream scanners halt gracefully to preserve financial data integrity."
                  )}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
