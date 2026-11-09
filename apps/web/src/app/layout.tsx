import type { Metadata } from "next";
import AppShell from "@/components/app-shell";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "InvestIntel | Đầu tư có bằng chứng",
    template: "%s | InvestIntel",
  },
  description: "Nền tảng nghiên cứu đầu tư cá nhân, ưu tiên dữ liệu và bằng chứng.",
  manifest: "/manifest.json",
  applicationName: "InvestIntel",
};

const themeInitializerScript = `(function() {
  try {
    var stored = localStorage.getItem("investintel:theme:v1");
    var theme = (stored === "light" || stored === "dark" || stored === "system") ? stored : "system";
    var systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    var effectiveTheme = theme === "system" ? (systemDark ? "dark" : "light") : theme;
    var root = document.documentElement;
    root.setAttribute("data-theme", theme);
    root.setAttribute("data-effective-theme", effectiveTheme);
    root.style.colorScheme = effectiveTheme;
  } catch (e) {}
})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{ __html: themeInitializerScript }}
        />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      {/* impeccable-live-start */}
<script src="http://localhost:8400/live.js?token=ed9aae1b-fe34-4177-9d08-4b742b8dbfb3"></script>
{/* impeccable-live-end */}
</body>
    </html>
  );
}
