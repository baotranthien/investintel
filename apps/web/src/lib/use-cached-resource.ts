"use client";

import { useState, useEffect, useRef, useCallback } from "react";

export type CachedResource<T> = {
  data: T | undefined;
  error: string | null;
  isLoading: boolean;
  isRevalidating: boolean;
  updatedAt: number | null;
  reload: () => void;
};

type CacheEntry<T> = {
  data: T;
  updatedAt: number;
};

const memoryCache = new Map<string, CacheEntry<unknown>>();
const inflightRequests = new Map<string, Promise<unknown>>();

export function readCachedValue<T>(key: string): { data: T; updatedAt: number } | undefined {
  if (typeof window === "undefined" || !key) {
    return undefined;
  }

  const mem = memoryCache.get(key);
  if (mem) {
    return { data: mem.data as T, updatedAt: mem.updatedAt };
  }

  try {
    const raw = window.localStorage.getItem(`investintel:cache:v2:${key}`);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed.t === "number" && "v" in parsed) {
        const entry: CacheEntry<T> = { data: parsed.v as T, updatedAt: parsed.t };
        memoryCache.set(key, entry as CacheEntry<unknown>);
        return entry;
      }
    }
  } catch {
    // Ignore storage errors
  }

  return undefined;
}

export function formatUpdatedAt(
  updatedAt: number | null,
  locale: "vi" | "en" = "vi"
): string {
  if (updatedAt === null) {
    return "";
  }
  const date = new Date(updatedAt);
  const timeStr = date.toLocaleTimeString(locale === "en" ? "en-GB" : "vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
  return locale === "en" ? `Updated ${timeStr}` : `Cập nhật ${timeStr}`;
}

export type UseCachedResourceOptions = {
  maxAgeMs?: number;
  timeoutMs?: number;
};

type InternalState<T> = {
  key: string | null;
  data: T | undefined;
  updatedAt: number | null;
  error: string | null;
  isLoading: boolean;
  isRevalidating: boolean;
};

export function useCachedResource<T>(
  key: string | null,
  fetcher: (signal: AbortSignal) => Promise<T>,
  options?: UseCachedResourceOptions
): CachedResource<T> {
  const maxAge = options?.maxAgeMs ?? 60_000;
  const timeoutMs = options?.timeoutMs ?? 25_000;
  const [reloadTrigger, setReloadTrigger] = useState(0);

  // Khởi tạo state đồng nhất giữa SSR và Client để triệt tiêu 100% Hydration Mismatch
  const [state, setState] = useState<InternalState<T>>({
    key,
    data: undefined,
    updatedAt: null,
    error: null,
    isLoading: key !== null,
    isRevalidating: false,
  });

  const [prevKey, setPrevKey] = useState(key);
  if (prevKey !== key) {
    setPrevKey(key);
    setState({
      key,
      data: undefined,
      updatedAt: null,
      error: null,
      isLoading: key !== null,
      isRevalidating: false,
    });
  }

  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);

  const reload = useCallback(() => {
    if (key) {
      inflightRequests.delete(key);
    }
    setReloadTrigger((prev) => prev + 1);
  }, [key]);

  useEffect(() => {
    if (key === null) {
      return;
    }

    let active = true;
    let retryTimeoutId: ReturnType<typeof setTimeout> | null = null;

    async function execute(retryCount = 0) {
      if (!key || !active) return;

      // 1. Kiểm tra cache (memoryCache trước, localStorage sau)
      let currentEntry = memoryCache.get(key) as CacheEntry<T> | undefined;
      if (!currentEntry) {
        const stored = readCachedValue<T>(key);
        if (stored) {
          currentEntry = stored;
        }
      }

      if (currentEntry && active) {
        setState((prev) => ({
          ...prev,
          data: currentEntry.data,
          updatedAt: currentEntry.updatedAt,
          isLoading: false,
        }));
      }

      // 2. Kiểm tra độ tươi của dữ liệu
      const isForce = reloadTrigger > 0;
      const isStale = !currentEntry || Date.now() - currentEntry.updatedAt > maxAge;

      if (!isStale && !isForce) {
        if (active) {
          setState((prev) => ({
            ...prev,
            isLoading: false,
            isRevalidating: false,
          }));
        }
        return;
      }

      // 3. Đánh dấu trạng thái loading / revalidating
      if (active) {
        setState((prev) => ({
          ...prev,
          isLoading: prev.data === undefined,
          isRevalidating: true,
        }));
      }

      try {
        // Tạo request độc lập với timeout riêng, không bị React StrictMode abort làm chết request
        let fetchPromise = inflightRequests.get(key) as Promise<T> | undefined;
        if (!fetchPromise) {
          const reqController = new AbortController();
          const reqTimeout = setTimeout(() => {
            reqController.abort(new Error("Hết thời gian chờ phản hồi từ máy chủ (Timeout)"));
          }, timeoutMs);

          fetchPromise = fetcherRef.current(reqController.signal)
            .finally(() => {
              clearTimeout(reqTimeout);
              inflightRequests.delete(key);
            });
          inflightRequests.set(key, fetchPromise as Promise<unknown>);
        }

        const freshData = await fetchPromise;

        const now = Date.now();
        const freshEntry: CacheEntry<T> = { data: freshData, updatedAt: now };
        memoryCache.set(key, freshEntry as CacheEntry<unknown>);

        if (typeof window !== "undefined") {
          try {
            const serialized = JSON.stringify({ t: now, v: freshData });
            if (serialized.length <= 1_500_000) {
              window.localStorage.setItem(`investintel:cache:v2:${key}`, serialized);
            }
          } catch {
            // Ignore storage errors
          }
        }

        if (active) {
          setState({
            key,
            data: freshData,
            updatedAt: now,
            error: null,
            isLoading: false,
            isRevalidating: false,
          });
        }
      } catch (err: unknown) {
        inflightRequests.delete(key);

        if (!active) return;

        // Nếu lỗi kết nối (Backend đang khởi động): tự động thử lại sau 1s (tối đa 2 lần)
        const isNetworkError =
          err instanceof TypeError &&
          (err.message.includes("fetch") || err.message.includes("network") || err.message.includes("Failed to fetch"));
        if (isNetworkError && retryCount < 2) {
          retryTimeoutId = setTimeout(() => {
            if (active) {
              void execute(retryCount + 1);
            }
          }, 800 * (retryCount + 1));
          return;
        }

        const errorMessage =
          err instanceof Error
            ? err.message
            : String(err);

        // TUYỆT ĐỐI KHÔNG ĐỂ isLoading: true TREO VÔ HẠN
        setState((prev) => ({
          ...prev,
          error: errorMessage,
          isLoading: false,
          isRevalidating: false,
        }));
      }
    }

    void execute();

    return () => {
      active = false;
      if (retryTimeoutId) {
        clearTimeout(retryTimeoutId);
        retryTimeoutId = null;
      }
    };
  }, [key, maxAge, timeoutMs, reloadTrigger]);

  return {
    data: state.data,
    error: state.error,
    isLoading: state.isLoading,
    isRevalidating: state.isRevalidating,
    updatedAt: state.updatedAt,
    reload,
  };
}
