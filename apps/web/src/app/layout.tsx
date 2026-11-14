import type { Metadata, Viewport } from "next";
import AppShell from "@/components/app-shell";
import "./globals.css";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  interactiveWidget: "resizes-content",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#F5F5F7" },
    { media: "(prefers-color-scheme: dark)", color: "#121316" },
  ],
};

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
    var storedLocale = localStorage.getItem("investintel:locale:v1");
    var locale = (storedLocale === "en" || storedLocale === "vi") ? storedLocale : "vi";
    var root = document.documentElement;
    root.setAttribute("data-theme", theme);
    root.setAttribute("data-effective-theme", effectiveTheme);
    root.setAttribute("data-locale", locale);
    root.lang = locale;
    root.style.colorScheme = effectiveTheme;

    var params = new URLSearchParams(window.location.search);
    var forceGw = params.get("gateway") === "1" || params.get("scrolly") === "1";
    var connected =
      localStorage.getItem("investintel:gateway:connected") === "true" ||
      sessionStorage.getItem("investintel:gateway:connected") === "true";
    if (forceGw || !connected) {
      root.setAttribute("data-gateway-active", "true");
    } else {
      root.removeAttribute("data-gateway-active");
    }
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
