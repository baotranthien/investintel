"use client";

import { useEffect, useRef, useState, useMemo, type JSX } from "react";
import { useRouter } from "next/navigation";
import { getAssets, type AssetSummary } from "@/lib/api";
import { useCachedResource } from "@/lib/use-cached-resource";
import { appNavigation, getNavLabel } from "@/lib/navigation";
import { Skeleton } from "@/components/ui/skeleton";
import { setThemePreference } from "@/lib/theme";
import { useLocale, setLocalePreference } from "@/lib/i18n";
import styles from "./command-palette.module.css";

const POPULAR_SYMBOLS = ["FPT", "VCB", "HPG", "MBB", "MWG"];

function removeVietnameseDiacritics(str: string): string {
  return str
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/đ/g, "d")
    .replace(/Đ/g, "d");
}

function ActionIcon({ kind }: { kind: "dark" | "light" | "lang" | "settings" }) {
  if (kind === "dark") {
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M20.2 14.4A8.5 8.5 0 0 1 9.6 3.8a8.5 8.5 0 1 0 10.6 10.6Z" />
      </svg>
    );
  }
  if (kind === "light") {
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2.5v2M12 19.5v2M5.28 5.28l1.42 1.42M17.3 17.3l1.42 1.42M2.5 12h2M19.5 12h2M5.28 18.72l1.42-1.42M17.3 6.7l1.42-1.42" />
      </svg>
    );
  }
  if (kind === "lang") {
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <line x1="3.6" y1="9" x2="20.4" y2="9" />
        <line x1="3.6" y1="15" x2="20.4" y2="15" />
        <path d="M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" />
      </svg>
    );
  }
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="4" y1="7" x2="20" y2="7" />
      <line x1="4" y1="17" x2="20" y2="17" />
      <circle cx="9" cy="7" r="2.2" />
      <circle cx="15" cy="17" r="2.2" />
    </svg>
  );
}

type PaletteItem =
  | {
      id: string;
      group: "stock";
      symbol: string;
      name: string;
      exchange: string | null;
      action: () => void;
      actionAlt: () => void;
      actionResearch?: () => void;
    }
  | {
      id: string;
      group: "page";
      label: string;
      href: string;
      action: () => void;
    }
  | {
      id: string;
      group: "action";
      label: string;
      iconKind?: "dark" | "light" | "lang" | "settings";
      action: () => void;
    }
  | {
      id: string;
      group: "ai";
      query: string;
      action: () => void;
    };

export default function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}): JSX.Element | null {
  const router = useRouter();
  const { locale, t } = useLocale();
  const inputRef = useRef<HTMLInputElement>(null);
  const previousActiveElementRef = useRef<HTMLElement | null>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  const [prevOpen, setPrevOpen] = useState(open);
  if (prevOpen !== open) {
    setPrevOpen(open);
    if (open) {
      setQuery("");
      setSelectedIndex(0);
    }
  }

  const [prevQuery, setPrevQuery] = useState(query);
  if (prevQuery !== query) {
    setPrevQuery(query);
    setSelectedIndex(0);
  }

  const assets = useCachedResource(open ? "assets" : null, (s) => getAssets(s), {
    maxAgeMs: 10 * 60_000,
  });

  useEffect(() => {
    if (open) {
      previousActiveElementRef.current = document.activeElement as HTMLElement | null;

      const focusTimer = setTimeout(() => {
        inputRef.current?.focus();
      }, 20);

      return () => {
        clearTimeout(focusTimer);
        previousActiveElementRef.current?.focus();
      };
    }
  }, [open]);

  const items = useMemo<PaletteItem[]>(() => {
    if (!open) return [];

    const trimmedQuery = query.trim();
    const normQuery = removeVietnameseDiacritics(trimmedQuery);
    const result: PaletteItem[] = [];

    const quickActions = [
      {
        id: "action-theme-dark",
        label: t("Chuyển giao diện: Chế độ Tối", "Switch Theme: Dark Mode"),
        iconKind: "dark" as const,
        keywords: ["toi", "dark", "giao dien", "theme", "night", "den"],
        action: () => {
          setThemePreference("dark");
          onClose();
        },
      },
      {
        id: "action-theme-light",
        label: t("Chuyển giao diện: Chế độ Sáng", "Switch Theme: Light Mode"),
        iconKind: "light" as const,
        keywords: ["sang", "light", "giao dien", "theme", "day", "trang"],
        action: () => {
          setThemePreference("light");
          onClose();
        },
      },
      {
        id: "action-locale-toggle",
        label:
          locale === "en"
            ? "Switch Language: Tiếng Việt (VI)"
            : "Chuyển ngôn ngữ: English (EN)",
        iconKind: "lang" as const,
        keywords: ["en", "vi", "language", "ngon ngu", "english", "viet", "tieng anh"],
        action: () => {
          setLocalePreference(locale === "en" ? "vi" : "en");
          onClose();
        },
      },
      {
        id: "action-settings-page",
        label: t("Cài đặt & Tùy chọn hệ thống", "Workspace Preferences & Settings"),
        iconKind: "settings" as const,
        keywords: ["cai dat", "tuy chon", "preference", "settings", "cau hinh"],
        action: () => {
          router.push("/settings");
          onClose();
        },
      },
    ];

    if (!trimmedQuery) {
      const assetMap = new Map<string, AssetSummary>();
      if (assets.data) {
        for (const a of assets.data) {
          assetMap.set(a.symbol.toUpperCase(), a);
        }
      }

      for (const sym of POPULAR_SYMBOLS) {
        const found = assetMap.get(sym);
        result.push({
          id: `stock-${sym}`,
          group: "stock",
          symbol: sym,
          name: found ? found.name : sym,
          exchange: found ? found.exchange : "HOSE",
          action: () => {
            router.push(`/ai?symbol=${encodeURIComponent(sym)}`);
            onClose();
          },
          actionAlt: () => {
            router.push(`/market?symbol=${encodeURIComponent(sym)}`);
            onClose();
          },
          actionResearch: () => {
            router.push(`/research/${encodeURIComponent(sym)}`);
            onClose();
          },
        });
      }

      for (const nav of appNavigation) {
        result.push({
          id: `page-${nav.href}`,
          group: "page",
          label: getNavLabel(nav, locale),
          href: nav.href,
          action: () => {
            router.push(nav.href);
            onClose();
          },
        });
      }

      for (const act of quickActions) {
        result.push({
          id: act.id,
          group: "action",
          label: act.label,
          iconKind: act.iconKind,
          action: act.action,
        });
      }

      return result;
    }

    if (assets.data) {
      const startsWithMatches: AssetSummary[] = [];
      const containsSymbolMatches: AssetSummary[] = [];
      const containsNameMatches: AssetSummary[] = [];

      for (const asset of assets.data) {
        const normSym = removeVietnameseDiacritics(asset.symbol);
        const normName = removeVietnameseDiacritics(asset.name);

        if (normSym.startsWith(normQuery)) {
          startsWithMatches.push(asset);
        } else if (normSym.includes(normQuery)) {
          containsSymbolMatches.push(asset);
        } else if (normName.includes(normQuery)) {
          containsNameMatches.push(asset);
        }
      }

      const matchedStocks = [
        ...startsWithMatches,
        ...containsSymbolMatches,
        ...containsNameMatches,
      ].slice(0, 8);

      for (const s of matchedStocks) {
        result.push({
          id: `stock-${s.symbol}`,
          group: "stock",
          symbol: s.symbol,
          name: s.name,
          exchange: s.exchange,
          action: () => {
            router.push(`/ai?symbol=${encodeURIComponent(s.symbol)}`);
            onClose();
          },
          actionAlt: () => {
            router.push(`/market?symbol=${encodeURIComponent(s.symbol)}`);
            onClose();
          },
          actionResearch: () => {
            router.push(`/research/${encodeURIComponent(s.symbol)}`);
            onClose();
          },
        });
      }
    }

    for (const nav of appNavigation) {
      const displayLabel = getNavLabel(nav, locale);
      const normVi = removeVietnameseDiacritics(nav.label);
      const normEn = removeVietnameseDiacritics(nav.labelEn);
      if (normVi.includes(normQuery) || normEn.includes(normQuery)) {
        result.push({
          id: `page-${nav.href}`,
          group: "page",
          label: displayLabel,
          href: nav.href,
          action: () => {
            router.push(nav.href);
            onClose();
          },
        });
      }
    }

    for (const act of quickActions) {
      const normActLabel = removeVietnameseDiacritics(act.label);
      const matchKeyword = act.keywords.some((k) => normQuery.includes(k) || k.includes(normQuery));
      if (normActLabel.includes(normQuery) || matchKeyword) {
        result.push({
          id: act.id,
          group: "action",
          label: act.label,
          iconKind: act.iconKind,
          action: act.action,
        });
      }
    }

    result.push({
      id: "ai-ask",
      group: "ai",
      query: trimmedQuery,
      action: () => {
        router.push(`/ai?q=${encodeURIComponent(trimmedQuery)}`);
        onClose();
      },
    });

    return result;
  }, [open, query, assets.data, router, onClose, locale, t]);

  useEffect(() => {
    if (!listRef.current) return;
    const activeEl = listRef.current.querySelector<HTMLElement>("[aria-selected='true']");
    if (activeEl) {
      activeEl.scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex]);

  if (!open) {
    return null;
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
      return;
    }

    if (items.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % items.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + items.length) % items.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const current = items[selectedIndex];
      if (!current) return;

      if (e.shiftKey && current.group === "stock") {
        current.actionAlt();
      } else {
        current.action();
      }
    }
  };

  const activeItem = items[selectedIndex];

  return (
    <div
      className={styles.overlay}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t("Tìm kiếm nhanh", "Quick command search")}
        className={styles.dialog}
        onKeyDown={handleKeyDown}
      >
        <div className={styles.searchHeader}>
          <span className={styles.searchIcon} aria-hidden="true">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </span>
          <input
            ref={inputRef}
            type="text"
            className={styles.input}
            placeholder={t(
              "Tìm mã cổ phiếu, trang hoặc hỏi AI…",
              "Search ticker, route, or ask AI Analyst…"
            )}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            role="combobox"
            aria-expanded="true"
            aria-controls="palette-listbox"
            aria-activedescendant={activeItem ? activeItem.id : undefined}
          />
          <button
            type="button"
            className={styles.closeButton}
            onClick={onClose}
            aria-label={t("Đóng tìm kiếm", "Close search")}
          >
            Esc
          </button>
        </div>

        <ul id="palette-listbox" role="listbox" className={styles.list} ref={listRef}>
          <div className={styles.groupHeader}>
            {query.trim()
              ? t("Cổ phiếu", "Equities")
              : t("Mã phổ biến", "Popular Tickers")}
          </div>

          {assets.isLoading && !assets.data && (
            <div className={styles.skeletonGroup}>
              <Skeleton height={28} radius={6} />
              <Skeleton height={28} radius={6} />
              <Skeleton height={28} radius={6} />
            </div>
          )}

          {assets.error && (
            <div className={styles.errorText}>
              {t(
                "Không tải được danh sách mã — vẫn có thể hỏi AI.",
                "Unable to load asset directory — AI Analyst remains available."
              )}
            </div>
          )}

          {items.map((item, index) => {
            const isSelected = index === selectedIndex;

            if (item.group === "stock") {
              return (
                <li
                  id={item.id}
                  key={item.id}
                  role="option"
                  aria-selected={isSelected}
                  className={`${styles.item} ${isSelected ? styles.itemSelected : ""}`}
                  onClick={item.action}
                  onMouseEnter={() => setSelectedIndex(index)}
                >
                  <div className={styles.itemLeft}>
                    <span className={styles.itemSymbol}>{item.symbol}</span>
                    <span className={styles.itemName}>{item.name}</span>
                  </div>
                  <div className={styles.itemRight}>
                    {item.exchange && (
                      <span className={styles.exchangeTag}>{item.exchange}</span>
                    )}
                    {item.actionResearch && (
                      <button
                        type="button"
                        className={styles.askAiBtn}
                        onClick={(e) => {
                          e.stopPropagation();
                          item.actionResearch?.();
                        }}
                        title={t("Mở trang Nghiên cứu chuyên sâu cho mã này", "Open Research Workspace for this ticker")}
                      >
                        {t("Nghiên cứu", "Research")}
                      </button>
                    )}
                    <button
                      type="button"
                      className={styles.askAiBtn}
                      onClick={(e) => {
                        e.stopPropagation();
                        item.actionAlt();
                      }}
                      title={t("Mở trang Thị trường cho mã này", "Open Market view for this ticker")}
                    >
                      {t("Thị trường", "Market")}
                    </button>
                  </div>
                </li>
              );
            }

            return null;
          })}

          {items.some((i) => i.group === "page") && (
            <>
              <div className={styles.groupHeader}>{t("Trang", "Workspaces")}</div>
              {items.map((item, index) => {
                if (item.group !== "page") return null;
                const isSelected = index === selectedIndex;
                return (
                  <li
                    id={item.id}
                    key={item.id}
                    role="option"
                    aria-selected={isSelected}
                    className={`${styles.item} ${isSelected ? styles.itemSelected : ""}`}
                    onClick={item.action}
                    onMouseEnter={() => setSelectedIndex(index)}
                  >
                    <div className={styles.itemLeft}>
                      <span className={styles.itemName}>{item.label}</span>
                    </div>
                  </li>
                );
              })}
            </>
          )}

          {items.some((i) => i.group === "action") && (
            <>
              <div className={styles.groupHeader}>
                {t("Giao diện & Cài đặt", "Appearance & Preferences")}
              </div>
              {items.map((item, index) => {
                if (item.group !== "action") return null;
                const isSelected = index === selectedIndex;
                return (
                  <li
                    id={item.id}
                    key={item.id}
                    role="option"
                    aria-selected={isSelected}
                    className={`${styles.item} ${isSelected ? styles.itemSelected : ""}`}
                    onClick={item.action}
                    onMouseEnter={() => setSelectedIndex(index)}
                  >
                    <div className={styles.itemLeft}>
                      {item.iconKind && (
                        <span
                          style={{ display: "inline-flex", marginRight: "8px", opacity: 0.75 }}
                          aria-hidden="true"
                        >
                          <ActionIcon kind={item.iconKind} />
                        </span>
                      )}
                      <span className={styles.itemName}>{item.label}</span>
                    </div>
                  </li>
                );
              })}
            </>
          )}

          {items.some((i) => i.group === "ai") && (
            <>
              <div className={styles.groupHeader}>{t("Trợ lý AI", "AI Analyst")}</div>
              {items.map((item, index) => {
                if (item.group !== "ai") return null;
                const isSelected = index === selectedIndex;
                return (
                  <li
                    id={item.id}
                    key={item.id}
                    role="option"
                    aria-selected={isSelected}
                    className={`${styles.item} ${isSelected ? styles.itemSelected : ""}`}
                    onClick={item.action}
                    onMouseEnter={() => setSelectedIndex(index)}
                  >
                    <div className={styles.aiItem}>
                      <span aria-hidden="true">→</span>
                      <span>
                        {t("Hỏi Trợ lý AI:", "Ask AI Analyst:")} “{item.query}”
                      </span>
                    </div>
                  </li>
                );
              })}
            </>
          )}
        </ul>

        <div className={styles.footer}>
          <span>
            {t(
              "↑↓ di chuyển · Enter mở · Shift+Enter thị trường · Esc đóng",
              "↑↓ navigate · Enter open · Shift+Enter market · Esc close"
            )}
          </span>
        </div>
      </div>
    </div>
  );
}
