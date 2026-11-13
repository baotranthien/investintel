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
    var theme = (stored === "light" || stored === "dark" || stored === "system") ? stored : "dark";
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
      </body>
    </html>
  );
}
