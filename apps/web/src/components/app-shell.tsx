"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { appNavigation } from "@/lib/navigation";
import { getAuthSession, logoutUser } from "@/lib/api";
import ColdStartBanner from "./cold-start-banner";
import styles from "./app-shell.module.css";

const groupLabels = {
  workspace: "KHÔNG GIAN",
  research: "PHÂN TÍCH",
  system: "HỆ THỐNG",
};

const mobileItems = appNavigation.filter((item) =>
  ["/", "/market", "/opportunities", "/portfolio", "/watchlist"].includes(item.href),
);

function isActivePath(pathname: string, href: string) {
  return href === "/" ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
}

export default function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const currentItem = appNavigation.find((item) => isActivePath(pathname, item.href));
  const [isOnline, setIsOnline] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setIsOnline(navigator.onLine);
      const handleOnline = () => setIsOnline(true);
      const handleOffline = () => setIsOnline(false);

      window.addEventListener("online", handleOnline);
      window.addEventListener("offline", handleOffline);

      // Check session status quietly
      getAuthSession()
        .then((s) => setIsAuthenticated(s.authenticated))
        .catch(() => setIsAuthenticated(false));

      if ("serviceWorker" in navigator) {
        navigator.serviceWorker.register("/sw.js").catch((err) => {
          console.warn("Service worker registration error:", err);
        });
      }

      return () => {
        window.removeEventListener("online", handleOnline);
        window.removeEventListener("offline", handleOffline);
      };
    }
  }, [pathname]);

  const handleLogout = async () => {
    try {
      await logoutUser();
      setIsAuthenticated(false);
      router.push("/login");
      router.refresh();
    } catch {
      router.push("/login");
    }
  };

  return (
    <div className={styles.frame}>
      <div style={{ gridColumn: "1 / -1", width: "100%" }}>
        <ColdStartBanner />
        {!isOnline && (
          <div style={{ background: "#78350f", color: "#fef3c7", padding: "8px 16px", textAlign: "center", fontSize: "0.85rem", zIndex: 100 }}>
            ⚠️ <strong>Chế độ Ngoại tuyến (Offline):</strong> Thiết bị mất kết nối mạng. Hệ thống sử dụng bộ nhớ đệm cục bộ và bảo lưu mốc quan sát điểm-thời-gian gần nhất.
          </div>
        )}
      </div>
      <aside className={styles.sidebar} aria-label="Điều hướng chính">
        <Link className={styles.brand} href="/" aria-label="InvestIntel, về tổng quan">
          <span className={styles.brandMark} aria-hidden="true">I</span>
          <span>
            <strong>InvestIntel</strong>
            <small>RESEARCH DESK</small>
          </span>
        </Link>

        <nav className={styles.desktopNav}>
          {(["workspace", "research", "system"] as const).map((group) => (
            <div className={styles.navGroup} key={group}>
              <p className={styles.groupLabel}>{groupLabels[group]}</p>
              {appNavigation.filter((item) => item.group === group).map((item) => (
                <Link
                  aria-current={isActivePath(pathname, item.href) ? "page" : undefined}
                  className={`${styles.navItem} ${isActivePath(pathname, item.href) ? styles.active : ""}`}
                  href={item.href}
                  key={item.href}
                >
                  <span aria-hidden="true" className={styles.navMarker} />
                  {item.label}
                </Link>
              ))}
            </div>
          ))}
        </nav>

        <div className={styles.sidebarNote}>
          <span className={styles.noteRule} />
          <p>Quant engine calculates.</p>
          <p>AI explains with evidence.</p>
        </div>
      </aside>

      <div className={styles.mainColumn}>
        <header className={styles.topbar}>
          <div className={styles.breadcrumb}>
            <span>INVESTINTEL</span>
            <span aria-hidden="true">/</span>
            <strong>{currentItem?.label ?? "Tài sản"}</strong>
          </div>
          <div className={styles.topbarMeta}>
            <span className={styles.privateLabel}>CÁ NHÂN · LOCAL-FIRST</span>
            {isAuthenticated === true ? (
              <button
                type="button"
                onClick={handleLogout}
                style={{
                  background: "transparent",
                  border: "1px solid #475569",
                  color: "#cbd5e1",
                  borderRadius: "4px",
                  padding: "4px 8px",
                  fontSize: "0.75rem",
                  cursor: "pointer",
                }}
              >
                Đăng xuất
              </button>
            ) : isAuthenticated === false ? (
              <Link
                href="/login"
                style={{
                  background: "#2563eb",
                  color: "#fff",
                  borderRadius: "4px",
                  padding: "4px 8px",
                  fontSize: "0.75rem",
                  textDecoration: "none",
                  fontWeight: 500,
                }}
              >
                Đăng nhập
              </Link>
            ) : null}
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