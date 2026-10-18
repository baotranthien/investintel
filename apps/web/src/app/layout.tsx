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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
