"use client";

import { useEffect, useState, useSyncExternalStore, type JSX } from "react";
import { describeStatus } from "@/components/ui/status-badge";
import { useLocale } from "@/lib/i18n";
import styles from "./status-bar.module.css";

function subscribeOnline(callback: () => void) {
  window.addEventListener("online", callback);
  window.addEventListener("offline", callback);
  return () => {
    window.removeEventListener("online", callback);
    window.removeEventListener("offline", callback);
  };
}

function getOnlineSnapshot() {
  return navigator.onLine;
}

function getServerOnlineSnapshot() {
  return true;
}

export function StatusBar(): JSX.Element {
  const { locale, t } = useLocale();
  const isOnline = useSyncExternalStore(
    subscribeOnline,
    getOnlineSnapshot,
    getServerOnlineSnapshot
  );

  const [mounted, setMounted] = useState(false);
  const [time, setTime] = useState("");
  const [healthStatus, setHealthStatus] = useState<string | null>(null);
  const [latency, setLatency] = useState<number | null>(null);
  const [mouseCoord, setMouseCoord] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const mountTimeout = setTimeout(() => {
      setMounted(true);
    }, 0);

    // Mouse coordinates tracker
    let rafId: number;
    const onMove = (e: MouseEvent) => {
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        setMouseCoord({ x: e.clientX, y: e.clientY });
      });
    };
    window.addEventListener("mousemove", onMove, { passive: true });

    // Clock
    const updateClock = () => {
      const now = new Date();
      setTime(
        now.toLocaleTimeString(locale === "en" ? "en-GB" : "vi-VN", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        }) + " ICT"
      );
    };

    updateClock();
    const clockTimer = setInterval(updateClock, 1000);

    // Health polling
    let active = true;
    const checkHealth = async () => {
      if (document.hidden) return;

      const startTime = performance.now();
      try {
        const res = await fetch("/api/v1/health", { cache: "no-store" });
        const endTime = performance.now();
        if (!active) return;

        setLatency(Math.round(endTime - startTime));
        if (res.ok) {
          const json = await res.json().catch(() => null);
          setHealthStatus(json?.status ?? "AVAILABLE");
        } else {
          setHealthStatus("DEGRADED");
        }
      } catch {
        if (!active) return;
        setLatency(null);
        setHealthStatus("UNAVAILABLE");
      }
    };

    void checkHealth();
    const pollInterval = setInterval(() => {
      void checkHealth();
    }, 60_000);

    const onVisibility = () => {
      if (!document.hidden) {
        void checkHealth();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      active = false;
      clearTimeout(mountTimeout);
      clearInterval(clockTimer);
      clearInterval(pollInterval);
      cancelAnimationFrame(rafId);
      window.removeEventListener("mousemove", onMove);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [locale]);

  const meta = describeStatus(healthStatus ?? (mounted ? "AVAILABLE" : null), locale);

  return (
    <footer className={styles.statusBar} aria-label={t("Trạng thái hệ thống", "System telemetry")}>
      <div className={styles.leftGroup}>
        <div className={styles.engineSection} title={meta.tooltip}>
          <span className={`${styles.dot} ${styles[meta.tone]}`} aria-hidden="true" />
          <span>{t("Hệ thống", "Engine")}: {meta.label}</span>
        </div>
        <span className={styles.divider}>·</span>
        <div className={styles.latencyGroup}>
          <svg
            width="24"
            height="10"
            viewBox="0 0 24 10"
            fill="none"
            className={styles.ecgWave}
            aria-hidden="true"
          >
            <path
              d="M1 5 L5 5 L7 2 L9 8 L12 1 L14 9 L16 5 L23 5"
              stroke="var(--finotive-emerald, #10B981)"
              strokeWidth="1.25"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span className="tabular-nums">
            API {latency !== null ? `${latency} ms` : "-- ms"}
          </span>
        </div>
        <span className={styles.divider}>·</span>
        <span>{t("Xử lý cục bộ", "Local-first")}</span>
        <span className={styles.divider}>·</span>
        <span className={styles.coordDisplay}>
          COORD X: {mouseCoord.x.toString().padStart(4, "0")} {"//"} Y: {mouseCoord.y.toString().padStart(4, "0")}
        </span>
      </div>

      <div className={styles.rightGroup}>
        {mounted && (
          <>
            <span>{isOnline ? t("Trực tuyến", "Online") : t("Ngoại tuyến", "Offline")}</span>
            {time && (
              <>
                <span className={styles.divider}>·</span>
                <span className="tabular-nums">{time}</span>
              </>
            )}
          </>
        )}
      </div>
    </footer>
  );
}
