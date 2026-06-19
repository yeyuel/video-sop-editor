import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Video SOP Editor",
  description: "Travel short-video director assistant"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
