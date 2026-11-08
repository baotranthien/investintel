export type AppNavigationItem = {
  href: string;
  label: string;
  shortLabel: string;
  group: "workspace" | "research" | "system";
};

export const appNavigation: AppNavigationItem[] = [
  { href: "/", label: "Tổng quan", shortLabel: "Tổng quan", group: "workspace" },
  { href: "/market", label: "Thị trường", shortLabel: "Thị trường", group: "workspace" },
  { href: "/opportunities", label: "Cơ hội", shortLabel: "Cơ hội", group: "workspace" },
  { href: "/portfolio", label: "Danh mục", shortLabel: "Danh mục", group: "workspace" },
  { href: "/watchlist", label: "Theo dõi", shortLabel: "Theo dõi", group: "workspace" },
  { href: "/research", label: "Nghiên cứu", shortLabel: "Nghiên cứu", group: "research" },
  { href: "/screener", label: "Bộ lọc cổ phiếu", shortLabel: "Bộ lọc", group: "research" },
  { href: "/ai", label: "AI Analyst", shortLabel: "AI", group: "research" },
  { href: "/data-center", label: "Chất lượng dữ liệu", shortLabel: "Dữ liệu", group: "system" },
  { href: "/system", label: "Hệ thống & tự phục hồi", shortLabel: "Hệ thống", group: "system" },
  { href: "/settings", label: "Cài đặt", shortLabel: "Cài đặt", group: "system" },
];

export const sectionDescriptions: Record<string, { title: string; english: string; milestone: string }> = {
  market: { title: "Thị trường", english: "Market", milestone: "6B" },
  opportunities: { title: "Cơ hội", english: "Opportunities", milestone: "6B" },
  portfolio: { title: "Danh mục", english: "Portfolio", milestone: "6D" },
  watchlist: { title: "Theo dõi", english: "Watchlist", milestone: "6D" },
  screener: { title: "Bộ lọc cổ phiếu", english: "Stock Screener", milestone: "5A" },
  ai: { title: "AI Analyst", english: "Local research assistant", milestone: "6F" },
  system: { title: "Hệ thống & Tự phục hồi", english: "System Observability", milestone: "6F" },
  settings: { title: "Cài đặt", english: "Settings", milestone: "6A" },
};

export type MobileNavItem = {
  href: string;
  label: string;
  matches: string[];
  subTabs?: { href: string; label: string }[];
};

export const mobilePrimaryNav: MobileNavItem[] = [
  { href: "/", label: "Tổng quan", matches: ["/"] },
  { href: "/market", label: "Thị trường", matches: ["/market"] },
  {
    href: "/opportunities",
    label: "Sàng lọc",
    matches: ["/opportunities", "/screener"],
    subTabs: [
      { href: "/opportunities", label: "Cơ hội" },
      { href: "/screener", label: "Bộ lọc" },
    ],
  },
  {
    href: "/portfolio",
    label: "Danh mục",
    matches: ["/portfolio", "/watchlist"],
    subTabs: [
      { href: "/portfolio", label: "Danh mục" },
      { href: "/watchlist", label: "Theo dõi" },
    ],
  },
  { href: "/ai", label: "AI", matches: ["/ai"] },
];

export const mobileDrawerNav: { href: string; label: string }[] = [
  { href: "/research", label: "Nghiên cứu" },
  { href: "/screener", label: "Bộ lọc cổ phiếu" },
  { href: "/watchlist", label: "Theo dõi" },
  { href: "/data-center", label: "Chất lượng dữ liệu" },
  { href: "/system", label: "Hệ thống & tự phục hồi" },
  { href: "/settings", label: "Cài đặt" },
];
