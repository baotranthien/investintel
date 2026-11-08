"use client";

import { useEffect, useState, useSyncExternalStore, type JSX } from "react";
import { describeStatus } from "@/components/ui/status-badge";
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
  const isOnline = useSyncExternalStore(
    subscribeOnline,
    getOnlineSnapshot,
    getServerOnlineSnapshot
  );

  const [mounted, setMounted] = useState(false);
  const [time, setTime] = useState("");
  const [healthStatus, setHealthStatus] = useState<string | null>(null);
  const [latency, setLatency] = useState<number | null>(null);

  useEffect(() => {
    // Mark as mounted
    const mountTimeout = setTimeout(() => {
      setMounted(true);
    }, 0);

    // Clock
    const updateClock = () => {
      const now = new Date();
      setTime(
        now.toLocaleTimeString("vi-VN", {
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
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  const meta = describeStatus(healthStatus ?? (mounted ? "AVAILABLE" : null));

  return (
    <footer className={styles.statusBar} aria-label="Trạng thái hệ thống">
      <div className={styles.leftGroup}>
        <div className={styles.engineSection} title={meta.tooltip}>
          <span className={`${styles.dot} ${styles[meta.tone]}`} aria-hidden="true" />
          <span>Engine: {meta.label}</span>
        </div>
        <span className={styles.divider}>·</span>
        <span className="tabular-nums">
          API {latency !== null ? `${latency} ms` : "-- ms"}
        </span>
        <span className={styles.divider}>·</span>
        <span>Local-first</span>
      </div>

      <div className={styles.rightGroup}>
        {mounted && (
          <>
            <span>{isOnline ? "Trực tuyến" : "Ngoại tuyến"}</span>
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
