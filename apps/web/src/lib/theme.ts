"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";

export type ThemePreference = "system" | "light" | "dark";
export type EffectiveTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "investintel:theme:v1";
export const THEME_CHANGE_EVENT = "investintel:theme-change";

export function getSystemTheme(): EffectiveTheme {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function getThemePreference(): ThemePreference {
  if (typeof window === "undefined") return "dark";
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch {
    // LocalStorage might be disabled or blocked
  }
  return "dark";
}

export function resolveEffectiveTheme(pref: ThemePreference): EffectiveTheme {
  if (pref === "system") {
    return getSystemTheme();
  }
  return pref;
}

export function applyThemeToDocument(pref: ThemePreference): EffectiveTheme {
  if (typeof document === "undefined") return "light";

  const effectiveTheme = resolveEffectiveTheme(pref);
  const root = document.documentElement;

  root.setAttribute("data-theme", pref);
  root.setAttribute("data-effective-theme", effectiveTheme);
  root.style.colorScheme = effectiveTheme;

  return effectiveTheme;
}

export function setThemePreference(theme: ThemePreference): void {
  if (typeof window === "undefined") return;

  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Ignore storage errors in private browsing
  }

  const effectiveTheme = applyThemeToDocument(theme);

  window.dispatchEvent(
    new CustomEvent(THEME_CHANGE_EVENT, {
      detail: { theme, effectiveTheme },
    })
  );
}

function subscribeTheme(callback: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

  const handleCustomChange = () => callback();
  const handleMediaChange = () => {
    if (getThemePreference() === "system") {
      applyThemeToDocument("system");
      callback();
    }
  };
  const handleStorage = (e: StorageEvent) => {
    if (e.key === THEME_STORAGE_KEY || e.key === null) {
      applyThemeToDocument(getThemePreference());
      callback();
    }
  };

  window.addEventListener(THEME_CHANGE_EVENT, handleCustomChange);
  window.addEventListener("storage", handleStorage);
  mediaQuery.addEventListener("change", handleMediaChange);
  return () => {
    window.removeEventListener(THEME_CHANGE_EVENT, handleCustomChange);
    window.removeEventListener("storage", handleStorage);
    mediaQuery.removeEventListener("change", handleMediaChange);
  };
}

function getThemeSnapshot(): ThemePreference {
  return getThemePreference();
}

function getServerThemeSnapshot(): ThemePreference {
  return "dark";
}

function getEffectiveThemeSnapshot(): EffectiveTheme {
  return resolveEffectiveTheme(getThemePreference());
}

function getServerEffectiveThemeSnapshot(): EffectiveTheme {
  return "dark";
}

function subscribeMounted(): () => void {
  return () => {};
}

function getClientMounted(): boolean {
  return true;
}

function getServerMounted(): boolean {
  return false;
}

// Hook to subscribe to theme state across components
export function useTheme() {
  const theme = useSyncExternalStore(
    subscribeTheme,
    getThemeSnapshot,
    getServerThemeSnapshot
  );
  const effectiveTheme = useSyncExternalStore(
    subscribeTheme,
    getEffectiveThemeSnapshot,
    getServerEffectiveThemeSnapshot
  );
  const mounted = useSyncExternalStore(
    subscribeMounted,
    getClientMounted,
    getServerMounted
  );

  useEffect(() => {
    applyThemeToDocument(theme);
  }, [theme]);

  const setTheme = useCallback((newTheme: ThemePreference) => {
    setThemePreference(newTheme);
  }, []);

  return {
    theme,
    effectiveTheme,
    setTheme,
    mounted,
  };
}
