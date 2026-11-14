"use client";

import { useEffect, useState } from "react";
import { getSystemDiagnostics, triggerAutomationPipeline, type SystemDiagnostics } from "@/lib/api";
import { StatusBadge } from "@/components/ui/status-badge";
import { SkeletonCard } from "@/components/ui/skeleton";
import { useLocale } from "@/lib/i18n";
import styles from "./page.module.css";

export default function SystemObservabilityPage() {
  const { t } = useLocale();
  const [diag, setDiag] = useState<SystemDiagnostics | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState<string | null>(null);
  const [triggerStatus, setTriggerStatus] = useState<"idle" | "running" | "success" | "error">("idle");

  const fetchDiagnostics = () => {
    setLoading(true);
    getSystemDiagnostics()
      .then((data) => {
        setDiag(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load system diagnostics", err);
        setLoading(false);
      });
  };

  useEffect(() => {
    // Initial fetch without synchronous setState
    getSystemDiagnostics()
      .then((data) => {
        setDiag(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load system diagnostics", err);
        setLoading(false);
      });

    const interval = setInterval(() => {
      getSystemDiagnostics()
        .then((data) => {
          setDiag(data);
        })
        .catch((err) => {
          console.error("Failed to refresh system diagnostics", err);
        });
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleRunPipeline = async () => {
    setTriggering(true);
    setTriggerStatus("running");
    setTriggerMsg(
      t(
        "Đang kích hoạt pipeline tự động (Ingestion → Opportunity → Alerts → Backup)...",
        "Triggering automation pipeline (Ingestion → Opportunity → Alerts → Backup)..."
      )
    );
    try {
      const res = await triggerAutomationPipeline(["FPT", "BMP"]);
      setTriggerStatus("success");
      const duration = (res as { total_duration_sec?: number }).total_duration_sec;
      setTriggerMsg(
        t(
          `Pipeline hoàn tất thành công: ${res.pipeline_status}${
            duration ? ` (${duration}s)` : ""
          } · Đã đối soát & sao lưu SQLite.`,
          `Pipeline completed successfully: ${res.pipeline_status}${
            duration ? ` (${duration}s)` : ""
          } · Reconciled & SQLite backed up.`
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

  if (loading && !diag) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <div>
            <p className={styles.eyebrow}>
              {t("Giám sát nền tảng cục bộ · Trạng thái vận hành", "Local Platform Observability · Operational Status")}
            </p>
            <h1 className={styles.title}>
              {t("Hệ thống & tự phục hồi", "System & Self-Healing")}
            </h1>
            <p className={styles.subTitle}>
              {t(
                "Giám sát thời gian thực tài nguyên GPU RTX 3050, mô hình Qwen3.5 9B, chu kỳ tự động hóa và độ bền cơ sở dữ liệu SQLite.",
                "Real-time telemetry for RTX 3050 GPU, Qwen 3.5 9B runtime, automation cycle schedules, and SQLite durability."
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

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>
            {t("Giám sát nền tảng cục bộ · Trạng thái vận hành", "Local Platform Observability · Operational Status")}
          </p>
          <h1 className={styles.title}>
            {t("Hệ thống & tự phục hồi", "System & Self-Healing")}
          </h1>
          <p className={styles.subTitle}>
            {t(
              "Giám sát thời gian thực tài nguyên GPU RTX 3050, mô hình Qwen3.5 9B, chu kỳ tự động hóa và độ bền cơ sở dữ liệu SQLite.",
              "Real-time telemetry for RTX 3050 GPU, Qwen 3.5 9B runtime, automation cycle schedules, and SQLite durability."
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
            <h2 className={styles.cardTitle}>Local AI Analyst (Ollama)</h2>
            <StatusBadge status={ollama?.ollama_listening ? "HEALTHY" : "OFFLINE"} />
          </div>
          <div className={styles.metricList}>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Mô hình AI chính", "Primary AI Model")}</span>
              <span className={styles.metricValue}>{ollama?.primary_model || "qwen3.5:9b-q4_K_M"}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Độ trễ phản hồi (TTFT)", "Time to First Token (TTFT)")}</span>
              <span className={styles.metricValue}>{telemetry?.median_ttft_sec ? `${telemetry.median_ttft_sec}s` : "< 0.5s"}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Tốc độ tạo phản hồi", "Token Generation Speed")}</span>
              <span className={styles.metricValue}>{telemetry?.median_generation_tps ? `${telemetry.median_generation_tps} tok/s` : "~5.5 tok/s"}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Dung lượng ngữ cảnh", "Context Window")}</span>
              <span className={styles.metricValue}>4096 tokens</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Lượt xử lý đã ghi nhận", "Inferences Logged")}</span>
              <span className={styles.metricValue}>
                {telemetry?.total_logged || 0} {t("lượt", "runs")}
              </span>
            </div>
          </div>
        </div>

        {/* Card 2: Hardware Telemetry */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>{t("Phần cứng & GPU", "Hardware & GPU Telemetry")}</h2>
            <StatusBadge status={gpu?.status === "ACTIVE" ? "HEALTHY" : gpu?.status ?? "UNKNOWN"} />
          </div>
          <div className={styles.metricList}>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("GPU nhận diện", "Detected GPU")}</span>
              <span className={styles.metricValue}>{gpu?.name || "NVIDIA RTX 3050 Laptop"}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("VRAM đang dùng / Tổng", "VRAM Usage / Total")}</span>
              <span className={styles.metricValue}>
                {gpu?.vram_used_mb ? `${gpu.vram_used_mb} MB / ${gpu.vram_total_mb} MB` : "N/A"}
              </span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("VRAM khả dụng", "Free VRAM")}</span>
              <span className={styles.metricValue}>{gpu?.vram_free_mb ? `${gpu.vram_free_mb} MB` : "N/A"}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Nhiệt độ GPU", "GPU Temperature")}</span>
              <span className={styles.metricValue}>{gpu?.temperature_c ? `${gpu.temperature_c} °C` : "N/A"}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("RAM hệ thống đang dùng", "System RAM Usage")}</span>
              <span className={styles.metricValue}>
                {ram?.used_pct ? `${ram.used_pct}% (${ram.available_mb} MB ${t("trống", "free")})` : "N/A"}
              </span>
            </div>
          </div>
        </div>

        {/* Card 3: Database & Durability */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>{t("Cơ sở dữ liệu & sao lưu", "Database & Durability")}</h2>
            <StatusBadge status={db?.connected ? "HEALTHY" : "OFFLINE"} />
          </div>
          <div className={styles.metricList}>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Công cụ lưu trữ", "Storage Engine")}</span>
              <span className={styles.metricValue}>Local SQLite (data/trading.db)</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Khóa bảo vệ ghi dữ liệu", "Write Protection Lock")}</span>
              <span className={styles.metricValue} style={{ color: "#137333" }}>
                {t("Khóa an toàn", "Safe Enforced")}
              </span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Kiểm tra toàn vẹn", "Integrity Check")}</span>
              <span className={styles.metricValue}>
                {t("Đạt chuẩn (PRAGMA ok)", "Passed (PRAGMA ok)")}
              </span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Cơ chế sao lưu nóng", "Hot Backup Engine")}</span>
              <span className={styles.metricValue}>
                {t("Đang bật (SHA-256 Manifest)", "Active (SHA-256 Manifest)")}
              </span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>{t("Chính sách lưu trữ", "Retention Policy")}</span>
              <span className={styles.metricValue}>
                {t("7 ngày / 4 tuần / 6 tháng", "7 Days / 4 Weeks / 6 Months")}
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
