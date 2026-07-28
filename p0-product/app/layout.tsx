import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "首盾视觉自动化｜P0 联调原型",
  description: "产品、画布、任务中心与 AI 协作契约的最小闭环。",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
