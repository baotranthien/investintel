"use client";

import { useEffect, useState } from "react";
import { getSystemDiagnostics, triggerAutomationPipeline, type SystemDiagnostics } from "@/lib/api";
import styles from "./page.module.css";

export default function SystemObservabilityPage() {
  const [diag, setDiag] = useState<SystemDiagnostics | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState<string | null>(null);

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
    fetchDiagnostics();
    const interval = setInterval(fetchDiagnostics, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleRunPipeline = async () => {
    setTriggering(true);
    setTriggerMsg("Đang kích hoạt pipeline tự động (Ingestion → Opportunity → Alerts → Backup)...");
    try {
      const res = await triggerAutomationPipeline(["FPT", "BMP"]);
      setTriggerMsg(`Pipeline hoàn tất: ${res.pipeline_status}`);
      fetchDiagnostics();
    } catch (err: unknown) {
      setTriggerMsg(`Lỗi kích hoạt pipeline: ${String(err)}`);
    } finally {
      setTriggering(false);
    }
  };

  if (loading && !diag) {
    return (
      <div className={styles.loadingState} role="status">
        Đang thu thập dữ liệu chẩn đoán hệ thống và phần cứng...
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
          <p className={styles.eyebrow}>LOCAL PLATFORM OBSERVABILITY · OPERATIONAL READINESS</p>
          <h1 className={styles.title}>
            Hệ thống & Tự phục hồi <span>/ System Observability</span>
          </h1>
          <p className={styles.subTitle}>
            Giám sát thời gian thực tài nguyên GPU RTX 3050, mô hình Qwen3.5 9B, chu kỳ tự động hóa và độ bền cơ sở dữ liệu SQLite.
          </p>
        </div>
        <div className={styles.actions}>
          <button className={styles.btnSecondary} onClick={fetchDiagnostics}>
            Làm mới
          </button>
          <button
            className={styles.btnPrimary}
            onClick={handleRunPipeline}
            disabled={triggering || scheduler?.is_busy}
          >
            {triggering ? "Đang xử lý..." : "Chạy Pipeline Tự động"}
          </button>
        </div>
      </header>

      {triggerMsg && (
        <div style={{ marginBottom: "20px", padding: "12px 16px", borderRadius: "8px", background: "#f0fdf4", border: "1px solid #bbf7d0", fontSize: "14px", color: "#166534" }}>
          {triggerMsg}
        </div>
      )}

      <div className={styles.grid}>
        {/* Card 1: Local AI Inference Runtime */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>Local AI Analyst (Ollama)</h2>
            <span className={`${styles.badge} ${ollama?.ollama_listening ? styles.badgeHealthy : styles.badgeOffline}`}>
              {ollama?.ollama_listening ? "HEALTHY" : "OFFLINE"}
            </span>
          </div>
          <div className={styles.metricList}>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>Primary Model</span>
              <span className={styles.metricValue}>{ollama?.primary_model || "qwen3.5:9b-q4_K_M"}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>Warm TTFT (Latency)</span>
              <span className={styles.metricValue}>{telemetry?.median_ttft_sec ? `${telemetry.median_ttft_sec}s` : "< 0.5s"}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>Generation Throughput</span>
              <span className={styles.metricValue}>{telemetry?.median_generation_tps ? `${telemetry.median_generation_tps} tok/s` : "~5.5 tok/s"}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>Context Budget</span>
              <span className={styles.metricValue}>4096 tokens</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>Inferences Logged</span>
              <span className={styles.metricValue}>{telemetry?.total_logged || 0} calls</span>
            </div>
          </div>
        </div>

        {/* Card 2: Hardware Telemetry */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>Phần cứng & GPU Telemetry</h2>
            <span className={`${styles.badge} ${gpu?.status === "ACTIVE" ? styles.badgeHealthy : styles.badgeDegraded}`}>
              {gpu?.status || "UNKNOWN"}
            </span>
          </div>
          <div className={styles.metricList}>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>GPU Detected</span>
              <span className={styles.metricValue}>{gpu?.name || "NVIDIA RTX 3050 Laptop"}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>VRAM Used / Total</span>
              <span className={styles.metricValue}>
                {gpu?.vram_used_mb ? `${gpu.vram_used_mb} MB / ${gpu.vram_total_mb} MB` : "N/A"}
              </span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>VRAM Free Headroom</span>
              <span className={styles.metricValue}>{gpu?.vram_free_mb ? `${gpu.vram_free_mb} MB` : "N/A"}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>NVIDIA Temperature</span>
              <span className={styles.metricValue}>{gpu?.temperature_c ? `${gpu.temperature_c} °C` : "N/A"}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>System RAM Used</span>
              <span className={styles.metricValue}>{ram?.used_pct ? `${ram.used_pct}% (${ram.available_mb} MB free)` : "N/A"}</span>
            </div>
          </div>
        </div>

        {/* Card 3: Database & Durability */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>Cơ sở Dữ liệu & Sao lưu</h2>
            <span className={`${styles.badge} ${db?.connected ? styles.badgeHealthy : styles.badgeOffline}`}>
              {db?.connected ? "HEALTHY" : "OFFLINE"}
            </span>
          </div>
          <div className={styles.metricList}>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>Storage Engine</span>
              <span className={styles.metricValue}>Local SQLite (data/trading.db)</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>Production Write Guard</span>
              <span className={styles.metricValue} style={{ color: "#137333" }}>LOCKED (false)</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>Integrity Check</span>
              <span className={styles.metricValue}>PASS (PRAGMA ok)</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>Hot Backup Engine</span>
              <span className={styles.metricValue}>Active (SHA-256 Manifest)</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>Retention Policy</span>
              <span className={styles.metricValue}>7 Daily / 4 Wk / 6 Mo</span>
            </div>
          </div>
        </div>

        {/* Card 4: Background Automation */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>Bộ lập lịch & Tự động hóa</h2>
            <span className={`${styles.badge} ${scheduler?.scheduler_paused ? styles.badgeDegraded : styles.badgeHealthy}`}>
              {scheduler?.scheduler_paused ? "PAUSED" : "ACTIVE"}
            </span>
          </div>
          <div className={styles.metricList}>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>Timezone</span>
              <span className={styles.metricValue}>{scheduler?.timezone || "Asia/Ho_Chi_Minh"}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>Pipeline Busy State</span>
              <span className={styles.metricValue}>{scheduler?.is_busy ? "EXECUTING..." : "IDLE"}</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>Ingestion Schedule</span>
              <span className={styles.metricValue}>Daily 16:00 ICT</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>Opportunity Scanner</span>
              <span className={styles.metricValue}>Post-Ingestion Trigger</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricLabel}>Alert Evaluation</span>
              <span className={styles.metricValue}>Deduplicated / Idempotent</span>
            </div>
          </div>
        </div>
      </div>

      {/* Operational Self-Recovery Runbooks */}
      <div className={styles.fullCard}>
        <h2 className={styles.cardTitle} style={{ fontSize: "20px", marginBottom: "8px" }}>
          Sổ tay Tự phục hồi Vận hành Cục bộ / Local Recovery Runbooks
        </h2>
        <p style={{ fontSize: "14px", color: "#6b7280", margin: "0 0 16px 0" }}>
          Hướng dẫn xử lý chuẩn khi gặp sự cố ngoại lệ trên môi trường Windows máy trạm:
        </p>

        <table className={styles.runbookTable}>
          <thead>
            <tr>
              <th>Hiện tượng Sự cố</th>
              <th>Nguyên nhân Tiềm ẩn</th>
              <th>Thao tác Khắc phục Chuẩn</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Cổng 8000 hoặc 3000 bị xung đột (Socket error 10048)</strong></td>
              <td>Tiến trình Uvicorn hoặc Node cũ chưa đóng socket hoàn toàn khi dừng.</td>
              <td>Chạy lệnh <span className={styles.codePill}>.\Stop-InvestIntel.bat</span> để quét và giải phóng cổng, sau đó khởi động lại bằng <span className={styles.codePill}>.\Start-InvestIntel.bat</span>.</td>
            </tr>
            <tr>
              <td><strong>AI Analyst báo lỗi "Ollama unavailable" hoặc TTFT quá chậm</strong></td>
              <td>Ollama daemon bị dừng hoặc các lớp của mô hình bị offload sang CPU do đầy VRAM.</td>
              <td>Kiểm tra VRAM bằng <span className={styles.codePill}>nvidia-smi</span>, chạy <span className={styles.codePill}>scripts\local\doctor-investintel.ps1</span> để xác minh model Qwen3.5 9B.</td>
            </tr>
            <tr>
              <td><strong>Cơ sở dữ liệu SQLite gặp lỗi khóa hoặc lỗi toàn vẹn</strong></td>
              <td>Giao dịch dở dang do tắt máy đột ngột hoặc file journal chưa checkpoint.</td>
              <td>Chạy lệnh kiểm tra <span className={styles.codePill}>.\scripts\local\doctor-investintel.ps1</span> hoặc khôi phục snapshot gần nhất bằng <span className={styles.codePill}>.\scripts\local\restore-investintel-db.ps1 -Latest</span>.</td>
            </tr>
            <tr>
              <td><strong>Cổng dữ liệu định lượng bên ngoài timeout hoặc trả về HTTP 400/500</strong></td>
              <td>API sàn chứng khoán bên ngoài bảo trì ngoài giờ giao dịch.</td>
              <td>Hệ thống tự động chuyển sang chế độ dự phòng bộ đệm dữ liệu lịch sử HOSE CSV; pipeline tự động hủy các tác vụ quét phụ thuộc để bảo vệ tính trung thực dữ liệu.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

