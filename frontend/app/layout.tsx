import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";

import { LlmRetryBanner } from "@/components/llm-retry-banner";

import "./globals.css";

const sans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap"
});

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
      <body className={`${sans.variable} font-sans antialiased`}>
        {children}
        <LlmRetryBanner />
      </body>
    </html>
  );
}
