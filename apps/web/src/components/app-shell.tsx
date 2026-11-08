"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  useEffect,
  useState,
  useRef,
  useSyncExternalStore,
  type ReactNode,
  type JSX,
} from "react";
import {
  appNavigation,
  mobilePrimaryNav,
  mobileDrawerNav,
} from "@/lib/navigation";
import ColdStartBanner from "./cold-start-banner";
import { StatusBar } from "./status-bar";
import CommandPalette from "./command-palette";
import ThemeToggle from "./theme-toggle";
import styles from "./app-shell.module.css";

const groupLabels = {
  workspace: "Không gian làm việc",
  research: "Trung tâm phân tích",
  system: "Hệ thống & nguồn",
};

function isRouteActive(pathname: string, href: string) {
  return href === "/" ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
}

function isMatchActive(pathname: string, matches: string[]) {
  return matches.some((m) =>
    m === "/" ? pathname === "/" : pathname === m || pathname.startsWith(`${m}/`)
  );
}

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

function subscribePlatform() {
  return () => {};
}

function getMacSnapshot() {
  return /(Mac|iPhone|iPod|iPad)/i.test(navigator.platform || navigator.userAgent);
}

function getServerMacSnapshot() {
  return false;
}

export default function AppShell({ children }: { children: ReactNode }): JSX.Element {
  const pathname = usePathname();
  const currentItem = appNavigation.find((item) => isRouteActive(pathname, item.href));

  const isOnline = useSyncExternalStore(
    subscribeOnline,
    getOnlineSnapshot,
    getServerOnlineSnapshot
  );

  const isMac = useSyncExternalStore(
    subscribePlatform,
    getMacSnapshot,
    getServerMacSnapshot
  );

  const [paletteOpen, setPaletteOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Close drawer when pathname changes during render
  const [prevPathname, setPrevPathname] = useState(pathname);
  if (prevPathname !== pathname) {
    setPrevPathname(pathname);
    setDrawerOpen(false);
  }

  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLDivElement>(null);

  // Register service worker after mount
  useEffect(() => {
    if (typeof window !== "undefined" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch((err) => {
        console.warn("Service worker registration error:", err);
      });
    }
  }, []);

  // Global shortcuts for Command Palette (Ctrl+K / Cmd+K and '/')
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Toggle palette on Ctrl+K / Cmd+K
      if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
        return;
      }

      // Open palette on '/' if not inside editable elements
      if (e.key === "/" && !paletteOpen && !drawerOpen) {
        const target = e.target as HTMLElement | null;
        if (target) {
          const tagName = target.tagName.toLowerCase();
          const isEditable =
            target.isContentEditable ||
            tagName === "input" ||
            tagName === "textarea" ||
            tagName === "select";
          if (!isEditable) {
            e.preventDefault();
            setPaletteOpen(true);
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [paletteOpen, drawerOpen]);

  // Lock body scroll and manage focus when drawer is open
  useEffect(() => {
    if (drawerOpen) {
      document.body.style.overflow = "hidden";
      drawerRef.current?.focus();
      const menuBtn = menuButtonRef.current;

      const handleDrawerKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
          e.preventDefault();
          setDrawerOpen(false);
        }
      };

      window.addEventListener("keydown", handleDrawerKeyDown);
      return () => {
        document.body.style.overflow = "";
        window.removeEventListener("keydown", handleDrawerKeyDown);
        menuBtn?.focus();
      };
    }
  }, [drawerOpen]);

  // Check if current page belongs to a primary nav item with subTabs
  const currentSubTabNav = mobilePrimaryNav.find(
    (item) => item.subTabs && isMatchActive(pathname, item.matches)
  );

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
          <Link className={styles.brand} href="/" aria-label="InvestIntel, về trang chủ">
            <div className={styles.brandMark} aria-hidden="true">
              <span className={styles.brandInitial}>I</span>
              <span className={styles.brandPulse} />
            </div>
            <div className={styles.brandInfo}>
              <strong className={styles.brandName}>InvestIntel</strong>
              <span className={styles.brandSub}>Nghiên cứu đầu tư</span>
            </div>
          </Link>
        </div>

        <nav className={styles.desktopNav}>
          {(["workspace", "research", "system"] as const).map((group) => (
            <div className={styles.navGroup} key={group}>
              <p className={styles.groupLabel}>{groupLabels[group]}</p>
              {appNavigation
                .filter((item) => item.group === group)
                .map((item) => {
                  const active = isRouteActive(pathname, item.href);
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
        </div>
      </aside>

      <div className={styles.mainColumn}>
        <header className={styles.topbar}>
          {/* Column 1: Breadcrumb (sentence case) */}
          <div className={styles.breadcrumb}>
            <span className={styles.breadcrumbRoot}>InvestIntel</span>
            <span className={styles.breadcrumbDivider} aria-hidden="true">/</span>
            <span className={styles.breadcrumbGroup}>
              {currentItem?.group ? groupLabels[currentItem.group] : "Trung tâm"}
            </span>
            <span className={styles.breadcrumbDivider} aria-hidden="true">/</span>
            <strong className={styles.breadcrumbCurrent}>{currentItem?.label ?? "Tài sản"}</strong>
          </div>

          {/* Mobile Header Left (Brand Mark) */}
          <div className={styles.mobileHeaderLeft}>
            <Link href="/" aria-label="InvestIntel, về trang chủ" className={styles.mobileBrandMark}>
              <span>I</span>
            </Link>
          </div>

          {/* Column 2: Search Trigger Button for Command Palette */}
          <button
            type="button"
            className={styles.searchTrigger}
            onClick={() => setPaletteOpen(true)}
            aria-label="Mở tìm kiếm nhanh"
          >
            <span className={styles.searchTriggerIcon} aria-hidden="true">🔍</span>
            <span className={styles.searchTriggerText}>Tìm mã cổ phiếu, trang hoặc hỏi AI…</span>
            <kbd className={styles.searchTriggerKbd}>{isMac ? "⌘K" : "Ctrl K"}</kbd>
          </button>

          {/* Mobile Header Right (Search Icon + Menu Button) */}
          <div className={styles.mobileHeaderRight}>
            <button
              type="button"
              className={styles.mobileIconBtn}
              onClick={() => setPaletteOpen(true)}
              aria-label="Tìm kiếm"
            >
              🔍
            </button>
            <button
              ref={menuButtonRef}
              type="button"
              className={styles.mobileIconBtn}
              onClick={() => setDrawerOpen(true)}
              aria-label="Mở menu"
              aria-expanded={drawerOpen}
            >
              ☰
            </button>
          </div>

          {/* Column 3: Theme Switcher & Preferences on Desktop */}
          <div className={styles.topbarRight}>
            <ThemeToggle />
          </div>
        </header>

        <main className={styles.content} id="main-content">
          {/* Sub tabs on mobile if current section has subTabs */}
          {currentSubTabNav?.subTabs && (
            <nav aria-label="Chuyển nhanh" className={styles.mobileSubTabs}>
              {currentSubTabNav.subTabs.map((sub) => {
                const isSubActive = pathname === sub.href;
                return (
                  <Link
                    key={sub.href}
                    href={sub.href}
                    aria-current={isSubActive ? "page" : undefined}
                    className={`${styles.subTabItem} ${isSubActive ? styles.subTabActive : ""}`}
                  >
                    {sub.label}
                  </Link>
                );
              })}
            </nav>
          )}

          {children}
        </main>

        {/* Mobile Primary Bottom Navigation (5 items) */}
        <nav aria-label="Điều hướng di động" className={styles.mobileNav}>
          {mobilePrimaryNav.map((item) => {
            const active = isMatchActive(pathname, item.matches);
            return (
              <Link
                aria-current={active ? "page" : undefined}
                className={`${styles.mobileItem} ${active ? styles.mobileActive : ""}`}
                href={item.href}
                key={item.href}
              >
                <span aria-hidden="true" className={styles.mobileMarker} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Desktop Status Bar */}
        <StatusBar />
      </div>

      {/* Mobile Drawer */}
      {drawerOpen && (
        <div
          className={styles.drawerOverlay}
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setDrawerOpen(false);
            }
          }}
        >
          <div
            ref={drawerRef}
            role="dialog"
            aria-modal="true"
            aria-label="Menu điều hướng"
            tabIndex={-1}
            className={styles.drawer}
          >
            <div className={styles.drawerHeader}>
              <span className={styles.drawerTitle}>Menu điều hướng</span>
              <button
                type="button"
                className={styles.drawerCloseBtn}
                onClick={() => setDrawerOpen(false)}
                aria-label="Đóng menu"
              >
                ✕
              </button>
            </div>
            <nav className={styles.drawerNav}>
              {mobileDrawerNav.map((item) => {
                const active = isRouteActive(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={`${styles.drawerItem} ${active ? styles.drawerActive : ""}`}
                    onClick={() => setDrawerOpen(false)}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            <div className={styles.drawerThemeSection}>
              <span className={styles.drawerSectionLabel}>Giao diện (Theme)</span>
              <ThemeToggle variant="drawer" />
            </div>
          </div>
        </div>
      )}

      {/* Command Palette */}
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
