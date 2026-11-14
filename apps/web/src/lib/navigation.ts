import type { AppLocale } from "./i18n";

export type AppNavigationItem = {
  href: string;
  label: string;
  labelEn: string;
  shortLabel: string;
  shortLabelEn: string;
  group: "workspace" | "research" | "system";
};

export const appNavigation: AppNavigationItem[] = [
  {
    href: "/",
    label: "Tổng quan",
    labelEn: "Overview",
    shortLabel: "Tổng quan",
    shortLabelEn: "Overview",
    group: "workspace",
  },
  {
    href: "/market",
    label: "Thị trường",
    labelEn: "Market",
    shortLabel: "Thị trường",
    shortLabelEn: "Market",
    group: "workspace",
  },
  {
    href: "/opportunities",
    label: "Cơ hội",
    labelEn: "Opportunities",
    shortLabel: "Cơ hội",
    shortLabelEn: "Signals",
    group: "workspace",
  },
  {
    href: "/portfolio",
    label: "Danh mục",
    labelEn: "Portfolio",
    shortLabel: "Danh mục",
    shortLabelEn: "Portfolio",
    group: "workspace",
  },
  {
    href: "/watchlist",
    label: "Theo dõi",
    labelEn: "Watchlist",
    shortLabel: "Theo dõi",
    shortLabelEn: "Watchlist",
    group: "workspace",
  },
  {
    href: "/screener",
    label: "Bộ lọc cổ phiếu",
    labelEn: "Stock Screener",
    shortLabel: "Bộ lọc",
    shortLabelEn: "Screener",
    group: "research",
  },
  {
    href: "/ai",
    label: "Trợ lý AI",
    labelEn: "AI Analyst",
    shortLabel: "AI",
    shortLabelEn: "AI",
    group: "research",
  },
  {
    href: "/system",
    label: "Hệ thống & tự phục hồi",
    labelEn: "System & Diagnostics",
    shortLabel: "Hệ thống",
    shortLabelEn: "System",
    group: "system",
  },
  {
    href: "/settings",
    label: "Cài đặt",
    labelEn: "Settings",
    shortLabel: "Cài đặt",
    shortLabelEn: "Settings",
    group: "system",
  },
];

export function getNavLabel(item: AppNavigationItem, locale: AppLocale): string {
  return locale === "en" ? item.labelEn : item.label;
}

export const sectionDescriptions: Record<string, { title: string; english: string; milestone: string }> = {
  market: { title: "Thị trường", english: "Market", milestone: "6B" },
  opportunities: { title: "Cơ hội", english: "Opportunities", milestone: "6B" },
  portfolio: { title: "Danh mục", english: "Portfolio", milestone: "6D" },
  watchlist: { title: "Theo dõi", english: "Watchlist", milestone: "6D" },
  screener: { title: "Bộ lọc cổ phiếu", english: "Stock Screener", milestone: "5A" },
  ai: { title: "Trợ lý AI", english: "AI Analyst", milestone: "6F" },
  system: { title: "Hệ thống & Tự phục hồi", english: "System Observability", milestone: "6F" },
  settings: { title: "Cài đặt", english: "Settings", milestone: "6A" },
};

export type MobileNavItem = {
  href: string;
  label: string;
  labelEn: string;
  matches: string[];
  subTabs?: { href: string; label: string; labelEn: string }[];
};

export const mobilePrimaryNav: MobileNavItem[] = [
  { href: "/", label: "Tổng quan", labelEn: "Overview", matches: ["/"] },
  { href: "/market", label: "Thị trường", labelEn: "Market", matches: ["/market"] },
  {
    href: "/opportunities",
    label: "Sàng lọc",
    labelEn: "Screen",
    matches: ["/opportunities", "/screener"],
    subTabs: [
      { href: "/opportunities", label: "Cơ hội", labelEn: "Opportunities" },
      { href: "/screener", label: "Bộ lọc", labelEn: "Screener" },
    ],
  },
  {
    href: "/portfolio",
    label: "Danh mục",
    labelEn: "Portfolio",
    matches: ["/portfolio", "/watchlist"],
    subTabs: [
      { href: "/portfolio", label: "Danh mục", labelEn: "Portfolio" },
      { href: "/watchlist", label: "Theo dõi", labelEn: "Watchlist" },
    ],
  },
  { href: "/ai", label: "AI", labelEn: "AI", matches: ["/ai"] },
];

export const mobileDrawerNav: { href: string; label: string; labelEn: string }[] = [
  { href: "/screener", label: "Bộ lọc cổ phiếu", labelEn: "Stock Screener" },
  { href: "/watchlist", label: "Theo dõi", labelEn: "Watchlist" },
  { href: "/system", label: "Hệ thống & tự phục hồi", labelEn: "System & Diagnostics" },
  { href: "/settings", label: "Cài đặt", labelEn: "Settings" },
];
