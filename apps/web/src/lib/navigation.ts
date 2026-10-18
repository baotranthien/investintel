export type AppNavigationItem = {
  href: string;
  label: string;
  shortLabel: string;
  group: "workspace" | "research" | "system";
};

export const appNavigation: AppNavigationItem[] = [
  { href: "/", label: "Tổng quan", shortLabel: "Home", group: "workspace" },
  { href: "/market", label: "Thị trường", shortLabel: "Market", group: "workspace" },
  { href: "/opportunities", label: "Cơ hội", shortLabel: "Cơ hội", group: "workspace" },
  { href: "/portfolio", label: "Danh mục", shortLabel: "Danh mục", group: "workspace" },
  { href: "/watchlist", label: "Theo dõi", shortLabel: "Theo dõi", group: "workspace" },
  { href: "/research", label: "Nghiên cứu", shortLabel: "Research", group: "research" },
  { href: "/ai", label: "AI Analyst", shortLabel: "AI", group: "research" },
  { href: "/data-center", label: "Chất lượng dữ liệu", shortLabel: "Dữ liệu", group: "system" },
  { href: "/settings", label: "Cài đặt", shortLabel: "Cài đặt", group: "system" },
];

export const sectionDescriptions: Record<string, { title: string; english: string; milestone: string }> = {
  market: { title: "Thị trường", english: "Market", milestone: "6B" },
  opportunities: { title: "Cơ hội", english: "Opportunities", milestone: "6B" },
  portfolio: { title: "Danh mục", english: "Portfolio", milestone: "6D" },
  watchlist: { title: "Theo dõi", english: "Watchlist", milestone: "6D" },
  ai: { title: "AI Analyst", english: "Local research assistant", milestone: "6F" },
  settings: { title: "Cài đặt", english: "Settings", milestone: "6A" },
};