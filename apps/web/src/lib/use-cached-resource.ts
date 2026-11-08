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
    const raw = window.localStorage.getItem(`investintel:cache:v1:${key}`);
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

export function formatUpdatedAt(updatedAt: number | null): string {
  if (updatedAt === null) {
    return "";
  }
  const date = new Date(updatedAt);
  const timeStr = date.toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
  return `Cập nhật ${timeStr}`;
}

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
  options?: { maxAgeMs?: number }
): CachedResource<T> {
  const maxAge = options?.maxAgeMs ?? 60_000;
  const [reloadTrigger, setReloadTrigger] = useState(0);

  const [state, setState] = useState<InternalState<T>>(() => {
    const cached = key ? (memoryCache.get(key) as CacheEntry<T> | undefined) : undefined;
    return {
      key,
      data: cached ? cached.data : undefined,
      updatedAt: cached ? cached.updatedAt : null,
      error: null,
      isLoading: key !== null && !cached,
      isRevalidating: false,
    };
  });

  const [prevKey, setPrevKey] = useState(key);
  if (prevKey !== key) {
    setPrevKey(key);
    const cached = key ? (memoryCache.get(key) as CacheEntry<T> | undefined) : undefined;
    setState({
      key,
      data: cached ? cached.data : undefined,
      updatedAt: cached ? cached.updatedAt : null,
      error: null,
      isLoading: key !== null && !cached,
      isRevalidating: false,
    });
  }

  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);

  const reload = useCallback(() => {
    setReloadTrigger((prev) => prev + 1);
  }, []);

  useEffect(() => {
    if (key === null) {
      return;
    }

    let active = true;
    const controller = new AbortController();

    async function execute() {
      if (!key) return;

      // 1. Try resolving from localStorage if memory is empty
      let currentEntry = memoryCache.get(key) as CacheEntry<T> | undefined;
      if (!currentEntry) {
        const stored = readCachedValue<T>(key);
        if (stored) {
          currentEntry = stored;
          if (active) {
            setState((prev) => ({
              ...prev,
              data: stored.data,
              updatedAt: stored.updatedAt,
              isLoading: false,
            }));
          }
        }
      }

      // 2. Check freshness
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

      // 3. Revalidate / Fetch
      if (active) {
        setState((prev) => ({
          ...prev,
          isLoading: prev.data === undefined,
          isRevalidating: true,
        }));
      }

      try {
        let fetchPromise = inflightRequests.get(key) as Promise<T> | undefined;
        if (!fetchPromise) {
          fetchPromise = fetcherRef.current(controller.signal);
          inflightRequests.set(key, fetchPromise as Promise<unknown>);
        }

        const freshData = await fetchPromise;
        const now = Date.now();

        // Update memory
        const freshEntry: CacheEntry<T> = { data: freshData, updatedAt: now };
        memoryCache.set(key, freshEntry as CacheEntry<unknown>);

        // Update localStorage
        if (typeof window !== "undefined") {
          try {
            const serialized = JSON.stringify({ t: now, v: freshData });
            if (serialized.length <= 1_500_000) {
              window.localStorage.setItem(`investintel:cache:v1:${key}`, serialized);
            }
          } catch {
            // Ignore quota or serialization errors
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
        if (!active) return;
        if (controller.signal.aborted || (err instanceof Error && err.name === "AbortError")) {
          return;
        }

        const errorMessage = err instanceof Error ? err.message : String(err);
        setState((prev) => ({
          ...prev,
          error: errorMessage,
          isLoading: false,
          isRevalidating: false,
        }));
      } finally {
        inflightRequests.delete(key);
      }
    }

    void execute();

    return () => {
      active = false;
      controller.abort();
    };
  }, [key, maxAge, reloadTrigger]);

  return {
    data: state.data,
    error: state.error,
    isLoading: state.isLoading,
    isRevalidating: state.isRevalidating,
    updatedAt: state.updatedAt,
    reload,
  };
}
