"use client";

import { useEffect, useRef, useState, useMemo, type JSX } from "react";
import { useRouter } from "next/navigation";
import { getAssets, type AssetSummary } from "@/lib/api";
import { useCachedResource } from "@/lib/use-cached-resource";
import { appNavigation } from "@/lib/navigation";
import { Skeleton } from "@/components/ui/skeleton";
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

type PaletteItem =
  | {
      id: string;
      group: "stock";
      symbol: string;
      name: string;
      exchange: string | null;
      action: () => void;
      actionAlt: () => void;
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
  const inputRef = useRef<HTMLInputElement>(null);
  const previousActiveElementRef = useRef<HTMLElement | null>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  // Synchronize state during render instead of cascading effects
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

  // Track previous active element and autofocus when opened
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

    if (!trimmedQuery) {
      // 1. Popular stocks
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
            router.push(`/research/${sym}`);
            onClose();
          },
          actionAlt: () => {
            router.push(`/ai?symbol=${sym}`);
            onClose();
          },
        });
      }

      // 2. All pages
      for (const nav of appNavigation) {
        result.push({
          id: `page-${nav.href}`,
          group: "page",
          label: nav.label,
          href: nav.href,
          action: () => {
            router.push(nav.href);
            onClose();
          },
        });
      }

      return result;
    }

    // When query is non-empty:
    // a) Stocks matching query (priority: symbol startsWith -> symbol contains -> name contains)
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
            router.push(`/research/${s.symbol}`);
            onClose();
          },
          actionAlt: () => {
            router.push(`/ai?symbol=${s.symbol}`);
            onClose();
          },
        });
      }
    }

    // b) Pages matching query
    for (const nav of appNavigation) {
      const normLabel = removeVietnameseDiacritics(nav.label);
      const normShort = removeVietnameseDiacritics(nav.shortLabel);
      if (normLabel.includes(normQuery) || normShort.includes(normQuery)) {
        result.push({
          id: `page-${nav.href}`,
          group: "page",
          label: nav.label,
          href: nav.href,
          action: () => {
            router.push(nav.href);
            onClose();
          },
        });
      }
    }

    // c) Ask AI option
    result.push({
      id: `ai-ask`,
      group: "ai",
      query: trimmedQuery,
      action: () => {
        router.push(`/ai?q=${encodeURIComponent(trimmedQuery)}`);
        onClose();
      },
    });

    return result;
  }, [open, query, assets.data, router, onClose]);

  // Scroll active item into view
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
        aria-label="Tìm kiếm nhanh"
        className={styles.dialog}
        onKeyDown={handleKeyDown}
      >
        <div className={styles.searchHeader}>
          <span className={styles.searchIcon} aria-hidden="true">
            🔍
          </span>
          <input
            ref={inputRef}
            type="text"
            className={styles.input}
            placeholder="Tìm mã cổ phiếu, trang hoặc hỏi AI…"
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
            aria-label="Đóng tìm kiếm"
          >
            Esc
          </button>
        </div>

        <ul id="palette-listbox" role="listbox" className={styles.list} ref={listRef}>
          {/* STOCKS GROUP */}
          <div className={styles.groupHeader}>
            {query.trim() ? "Cổ phiếu" : "Mã phổ biến"}
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
              Không tải được danh sách mã — vẫn có thể hỏi AI.
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
                    <button
                      type="button"
                      className={styles.askAiBtn}
                      onClick={(e) => {
                        e.stopPropagation();
                        item.actionAlt();
                      }}
                      title="Hỏi AI Analyst về mã này"
                    >
                      Hỏi AI
                    </button>
                  </div>
                </li>
              );
            }

            return null;
          })}

          {/* PAGES GROUP */}
          {items.some((i) => i.group === "page") && (
            <>
              <div className={styles.groupHeader}>Trang</div>
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

          {/* AI QUERY GROUP */}
          {items.some((i) => i.group === "ai") && (
            <>
              <div className={styles.groupHeader}>Trợ lý AI</div>
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
                      <span aria-hidden="true">✨</span>
                      <span>Hỏi AI Analyst: “{item.query}”</span>
                    </div>
                  </li>
                );
              })}
            </>
          )}
        </ul>

        <div className={styles.footer}>
          <span>↑↓ di chuyển · Enter mở · Shift+Enter hỏi AI · Esc đóng</span>
        </div>
      </div>
    </div>
  );
}
