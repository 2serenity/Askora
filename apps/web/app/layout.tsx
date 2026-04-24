import type { Metadata } from "next";
import type { ReactNode } from "react";

import { SiteIntro } from "@/components/intro/site-intro";
import { QueryProvider } from "@/lib/query-provider";

import "./globals.css";

export const metadata: Metadata = {
  title: "Askora",
  description: "Askora — AI-ассистент запросов для аналитики без SQL",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body className="font-sans">
        <QueryProvider>
          {children}
          <SiteIntro />
        </QueryProvider>
      </body>
    </html>
  );
}
