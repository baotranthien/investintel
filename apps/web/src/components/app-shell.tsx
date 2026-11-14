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
  getNavLabel,
} from "@/lib/navigation";
import { useLocale } from "@/lib/i18n";
import { StatusBar } from "./status-bar";
import { TacticalGateway } from "./gateway/tactical-gateway";
import CommandPalette from "./command-palette";
import ThemeToggle from "./theme-toggle";
import LanguageToggle from "./language-toggle";
import styles from "./app-shell.module.css";

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

function SearchVectorIcon({ size = 14 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.1"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function MenuVectorIcon() {
  return (
    <svg
      width="17"
      height="17"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <line x1="4" y1="8" x2="20" y2="8" />
      <line x1="4" y1="16" x2="20" y2="16" />
    </svg>
  );
}

export default function AppShell({ children }: { children: ReactNode }): JSX.Element {
  const pathname = usePathname();
  const { locale, t } = useLocale();
  const currentItem = appNavigation.find((item) => isRouteActive(pathname, item.href));

  const groupLabels = {
    workspace: t("Không gian làm việc", "Workspace"),
    research: t("Trung tâm phân tích", "Research Hub"),
    system: t("Hệ thống & nguồn", "System & Feeds"),
  };

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

  const handleOpenGateway = () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem("investintel:gateway:connected");
      window.sessionStorage.removeItem("investintel:gateway:connected");
      document.documentElement.setAttribute("data-gateway-active", "true");
      window.dispatchEvent(new CustomEvent("investintel:open-gateway"));
    }
  };

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
      if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
        return;
      }

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
    <div className={styles.frame} data-app-shell-frame="true">
      {!isOnline && (
        <div style={{ gridColumn: "1 / -1", width: "100%" }}>
          <div className={styles.offlineBanner} role="status">
            <span className={styles.offlineIcon} aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
            </span>
            <span>
              <strong>{t("Chế độ Ngoại tuyến (Offline):", "Offline Mode:")}</strong>{" "}
              {t(
                "Mất kết nối mạng. Hệ thống sử dụng bộ nhớ đệm cục bộ và bảo lưu mốc quan sát điểm-thời-gian gần nhất.",
                "Network disconnected. Using cached workspace state and preserving latest Point-in-Time cutoff."
              )}
            </span>
          </div>
        </div>
      )}

      <aside className={styles.sidebar} aria-label={t("Điều hướng chính", "Primary navigation")}>
        <div className={styles.sidebarHeader}>
          <Link className={styles.brand} href="/" aria-label={t("InvestIntel, về trang chủ", "InvestIntel, home")}>
            <div className={styles.brandMark} aria-hidden="true">
              <span className={styles.brandInitial}>I</span>
              <span className={styles.brandPulse} />
            </div>
            <div className={styles.brandInfo}>
              <strong className={styles.brandName}>InvestIntel</strong>
              <span className={styles.brandSub}>{t("Nghiên cứu đầu tư", "Equity Research")}</span>
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
                      <span className={styles.navLabel}>{getNavLabel(item, locale)}</span>
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
          <button
            type="button"
            className={styles.creedBox}
            onClick={handleOpenGateway}
            title={t(
              "Mở màn hình trải nghiệm 3D Gateway Scrollytelling",
              "Launch 3D Gateway interactive experience"
            )}
            aria-label={t("Mở cổng Gateway 3D", "Open 3D Gateway")}
          >
            <div className={styles.creedHeader}>
              <span className={styles.creedIcon} aria-hidden="true">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                </svg>
              </span>
              <strong className={styles.creedTitle}>
                {t("Động cơ Định lượng", "Quant Engine Active")}
              </strong>
              <span className={styles.creedPulse} aria-hidden="true" />
            </div>
            <p className={styles.creedLine1}>
              {t("Tính toán định lượng minh bạch", "Deterministic Calculations")}
            </p>
            <p className={styles.creedLine2}>
              {t("AI diễn giải kèm bằng chứng gốc", "AI Explains with Evidence")}
            </p>
            <div className={styles.creedActionBadge}>
              <span className={styles.creedActionText}>
                {t("[ ⏻ MỞ CỔNG GATEWAY 3D ]", "[ ⏻ LAUNCH GATEWAY 3D ]")}
              </span>
              <span className={styles.creedActionArrow} aria-hidden="true">→</span>
            </div>
          </button>
        </div>
      </aside>

      <div className={styles.mainColumn}>
        <div className="ambient-emerald-glow" aria-hidden="true" />
        <header className={styles.topbar}>
          {/* Column 1: Breadcrumb */}
          <div className={styles.breadcrumb}>
            <span className={styles.breadcrumbRoot}>InvestIntel</span>
            <span className={styles.breadcrumbDivider} aria-hidden="true">/</span>
            <span className={styles.breadcrumbGroup}>
              {currentItem?.group ? groupLabels[currentItem.group] : t("Trung tâm", "Workspace")}
            </span>
            <span className={styles.breadcrumbDivider} aria-hidden="true">/</span>
            <strong className={styles.breadcrumbCurrent}>
              {currentItem ? getNavLabel(currentItem, locale) : t("Tài sản", "Asset")}
            </strong>
          </div>

          {/* Mobile Header Left (Brand Mark) */}
          <div className={styles.mobileHeaderLeft}>
            <Link href="/" aria-label={t("InvestIntel, về trang chủ", "InvestIntel, home")} className={styles.mobileBrandMark}>
              <span>I</span>
            </Link>
          </div>

          {/* Column 2: Search Trigger Button for Command Palette */}
          <button
            type="button"
            className={styles.searchTrigger}
            onClick={() => setPaletteOpen(true)}
            aria-label={t("Mở tìm kiếm nhanh", "Open command palette")}
          >
            <span className={styles.searchTriggerIcon} aria-hidden="true">
              <SearchVectorIcon size={14} />
            </span>
            <span className={styles.searchTriggerText}>
              {t("Tìm mã cổ phiếu, lệnh hoặc hỏi AI…", "Search ticker, command, or ask AI…")}
            </span>
            <kbd className={styles.searchTriggerKbd}>{isMac ? "⌘ + K" : "Ctrl + K"}</kbd>
          </button>

          {/* Mobile Header Right (Search Icon + Menu Button) */}
          <div className={styles.mobileHeaderRight}>
            <button
              type="button"
              className={styles.mobileIconBtn}
              onClick={() => setPaletteOpen(true)}
              aria-label={t("Tìm kiếm", "Search")}
            >
              <SearchVectorIcon size={16} />
            </button>
            <button
              ref={menuButtonRef}
              type="button"
              className={styles.mobileIconBtn}
              onClick={() => setDrawerOpen(true)}
              aria-label={t("Mở menu", "Open navigation menu")}
              aria-expanded={drawerOpen}
            >
              <MenuVectorIcon />
            </button>
          </div>

          {/* Column 3: Language & Theme Instrument Cluster on Desktop */}
          <div className={styles.topbarRight}>
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </header>

        <main className={styles.content} id="main-content">
          {currentSubTabNav?.subTabs && (
            <nav aria-label={t("Chuyển nhanh", "Quick tabs")} className={styles.mobileSubTabs}>
              {currentSubTabNav.subTabs.map((sub) => {
                const isSubActive = pathname === sub.href;
                return (
                  <Link
                    key={sub.href}
                    href={sub.href}
                    aria-current={isSubActive ? "page" : undefined}
                    className={`${styles.subTabItem} ${isSubActive ? styles.subTabActive : ""}`}
                  >
                    {locale === "en" ? sub.labelEn : sub.label}
                  </Link>
                );
              })}
            </nav>
          )}

          <div key={pathname} className={styles.pageTransitionStage}>
            {children}
          </div>
        </main>

        {/* Mobile Primary Bottom Navigation (5 items) */}
        <nav aria-label={t("Điều hướng di động", "Mobile navigation")} className={styles.mobileNav}>
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
                <span>{locale === "en" ? item.labelEn : item.label}</span>
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
            aria-label={t("Menu điều hướng", "Navigation menu")}
            tabIndex={-1}
            className={styles.drawer}
          >
            <div className={styles.drawerHeader}>
              <span className={styles.drawerTitle}>{t("Menu điều hướng", "Navigation")}</span>
              <button
                type="button"
                className={styles.drawerCloseBtn}
                onClick={() => setDrawerOpen(false)}
                aria-label={t("Đóng menu", "Close menu")}
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
                    {locale === "en" ? item.labelEn : item.label}
                  </Link>
                );
              })}
            </nav>

            <div className={styles.drawerGatewaySection}>
              <button
                type="button"
                className={styles.drawerGatewayBtn}
                onClick={() => {
                  setDrawerOpen(false);
                  handleOpenGateway();
                }}
              >
                {t("⏻ Mở Cổng Gateway 3D", "⏻ Open 3D Gateway")}
              </button>
            </div>

            <div className={styles.drawerThemeSection}>
              <span className={styles.drawerSectionLabel}>
                {t("Ngôn ngữ & Giao diện", "Language & Theme")}
              </span>
              <LanguageToggle variant="drawer" />
              <ThemeToggle variant="drawer" />
            </div>
          </div>
        </div>
      )}

      {/* Global Tactical Scrollytelling 3D Gateway */}
      <TacticalGateway />

      {/* Command Palette */}
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
