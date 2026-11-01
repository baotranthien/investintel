"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { appNavigation } from "@/lib/navigation";
import ColdStartBanner from "./cold-start-banner";
import styles from "./app-shell.module.css";

const groupLabels = {
  workspace: "KHÔNG GIAN LÀM VIỆC",
  research: "TRUNG TÂM PHÂN TÍCH",
  system: "HỆ THỐNG & NGUỒN",
};

const mobileItems = appNavigation.filter((item) =>
  ["/", "/market", "/opportunities", "/portfolio", "/watchlist", "/ai"].includes(item.href),
);

function isActivePath(pathname: string, href: string) {
  return href === "/" ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
}

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const currentItem = appNavigation.find((item) => isActivePath(pathname, item.href));
  const [isOnline, setIsOnline] = useState(true);
  const [currentTime, setCurrentTime] = useState("");

  useEffect(() => {
    if (typeof window !== "undefined") {
      setIsOnline(navigator.onLine);
      const handleOnline = () => setIsOnline(true);
      const handleOffline = () => setIsOnline(false);

      window.addEventListener("online", handleOnline);
      window.addEventListener("offline", handleOffline);

      const updateClock = () => {
        const now = new Date();
        setCurrentTime(
          now.toLocaleTimeString("vi-VN", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false,
          }) + " ICT"
        );
      };
      updateClock();
      const timer = setInterval(updateClock, 1000);

      if ("serviceWorker" in navigator) {
        navigator.serviceWorker.register("/sw.js").catch((err) => {
          console.warn("Service worker registration error:", err);
        });
      }

      return () => {
        window.removeEventListener("online", handleOnline);
        window.removeEventListener("offline", handleOffline);
        clearInterval(timer);
      };
    }
  }, [pathname]);

  return (
    <div className={styles.frame}>
      <div style={{ gridColumn: "1 / -1", width: "100%" }}>
        <ColdStartBanner />
        {!isOnline && (
          <div className={styles.offlineBanner} role="status">
            <span className={styles.offlineIcon}>⚠️</span>
            <span>
              <strong>Chế độ Ngoại tuyến (Offline):</strong> Mất kết nối mạng. Hệ thống sử dụng bộ nhớ đệm cục bộ và bảo lưu mốc quan sát điểm-thời-gian gần nhất.
            </span>
          </div>
        )}
      </div>

      <aside className={styles.sidebar} aria-label="Điều hướng chính">
        <div className={styles.sidebarHeader}>
          <Link className={styles.brand} href="/" aria-label="InvestIntel Terminal, về trang chủ">
            <div className={styles.brandMark} aria-hidden="true">
              <span className={styles.brandInitial}>I</span>
              <span className={styles.brandPulse} />
            </div>
            <div className={styles.brandInfo}>
              <strong className={styles.brandName}>InvestIntel</strong>
              <span className={styles.brandSub}>PRECISION TERMINAL</span>
            </div>
          </Link>

          <div className={styles.systemStatusStrip} title="Local-first deterministic financial engine">
            <span className={styles.statusDot} aria-hidden="true" />
            <span className={styles.statusLabel}>ENGINE ONLINE</span>
            <span className={styles.statusEngineVersion}>v2.5</span>
          </div>
        </div>

        <nav className={styles.desktopNav}>
          {(["workspace", "research", "system"] as const).map((group) => (
            <div className={styles.navGroup} key={group}>
              <p className={styles.groupLabel}>{groupLabels[group]}</p>
              {appNavigation.filter((item) => item.group === group).map((item) => {
                const active = isActivePath(pathname, item.href);
                return (
                  <Link
                    aria-current={active ? "page" : undefined}
                    className={`${styles.navItem} ${active ? styles.active : ""}`}
                    href={item.href}
                    key={item.href}
                  >
                    <span aria-hidden="true" className={styles.navMarker} />
                    <span className={styles.navLabel}>{item.label}</span>
                    {item.href === "/ai" && (
                      <span className={styles.aiPillBadge}>STREAM</span>
                    )}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        <div className={styles.sidebarFooter}>
          <div className={styles.creedBox}>
            <span className={styles.creedRule} />
            <p className={styles.creedLine1}>Quant engine calculates.</p>
            <p className={styles.creedLine2}>AI explains with evidence.</p>
          </div>
          <div className={styles.privacyAssurance}>
            <span className={styles.lockIcon}>🛡️</span>
            <span>100% Local-First Engine</span>
          </div>
        </div>
      </aside>

      <div className={styles.mainColumn}>
        <header className={styles.topbar}>
          <div className={styles.breadcrumb}>
            <span className={styles.breadcrumbRoot}>INVESTINTEL</span>
            <span className={styles.breadcrumbDivider} aria-hidden="true">/</span>
            <span className={styles.breadcrumbGroup}>
              {currentItem?.group ? groupLabels[currentItem.group] : "TRUNG TÂM"}
            </span>
            <span className={styles.breadcrumbDivider} aria-hidden="true">/</span>
            <strong className={styles.breadcrumbCurrent}>{currentItem?.label ?? "Tài sản"}</strong>
          </div>

          <div className={styles.topbarTelemetry}>
            {currentTime && (
              <span className={`${styles.clockPill} tabular-nums`} title="Giờ thị trường">
                <span className={styles.clockDot} />
                {currentTime}
              </span>
            )}
            <div className={styles.privateSecurityBadge}>
              <span className={styles.securityDot} />
              <span>ZERO EXTERNAL LEAK</span>
            </div>
          </div>
        </header>

        <main className={styles.content} id="main-content">{children}</main>

        <nav aria-label="Điều hướng di động" className={styles.mobileNav}>
          {mobileItems.map((item) => (
            <Link
              aria-current={isActivePath(pathname, item.href) ? "page" : undefined}
              className={`${styles.mobileItem} ${isActivePath(pathname, item.href) ? styles.mobileActive : ""}`}
              href={item.href}
              key={item.href}
            >
              <span aria-hidden="true" className={styles.mobileMarker} />
              <span>{item.shortLabel}</span>
            </Link>
          ))}
        </nav>
      </div>
    </div>
  );
}
