"use client";

import { useEffect, useState, useCallback, useSyncExternalStore } from "react";

export type ThemePreference = "system" | "light" | "dark";
export type EffectiveTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "investintel:theme:v1";
export const THEME_CHANGE_EVENT = "investintel:theme-change";

export function getSystemTheme(): EffectiveTheme {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function getThemePreference(): ThemePreference {
  if (typeof window === "undefined") return "system";
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch {
    // LocalStorage might be disabled or blocked
  }
  return "system";
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

// Hook to subscribe to theme state across components
export function useTheme() {
  const [theme, setThemeState] = useState<ThemePreference>("system");
  const [effectiveTheme, setEffectiveThemeState] = useState<EffectiveTheme>("light");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const initialPref = getThemePreference();
    const initialEffective = resolveEffectiveTheme(initialPref);
    setThemeState(initialPref);
    setEffectiveThemeState(initialEffective);
    applyThemeToDocument(initialPref);

    const handleCustomChange = (e: Event) => {
      const customEvent = e as CustomEvent<{ theme: ThemePreference; effectiveTheme: EffectiveTheme }>;
      if (customEvent.detail) {
        setThemeState(customEvent.detail.theme);
        setEffectiveThemeState(customEvent.detail.effectiveTheme);
      } else {
        const currentPref = getThemePreference();
        setThemeState(currentPref);
        setEffectiveThemeState(resolveEffectiveTheme(currentPref));
      }
    };

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleMediaChange = () => {
      const currentPref = getThemePreference();
      if (currentPref === "system") {
        const newEffective = mediaQuery.matches ? "dark" : "light";
        setEffectiveThemeState(newEffective);
        applyThemeToDocument("system");
      }
    };

    window.addEventListener(THEME_CHANGE_EVENT, handleCustomChange);
    mediaQuery.addEventListener("change", handleMediaChange);

    return () => {
      window.removeEventListener(THEME_CHANGE_EVENT, handleCustomChange);
      mediaQuery.removeEventListener("change", handleMediaChange);
    };
  }, []);

  const setTheme = useCallback((newTheme: ThemePreference) => {
    setThemePreference(newTheme);
    setThemeState(newTheme);
    setEffectiveThemeState(resolveEffectiveTheme(newTheme));
  }, []);

  return {
    theme,
    effectiveTheme,
    setTheme,
    mounted,
  };
}

