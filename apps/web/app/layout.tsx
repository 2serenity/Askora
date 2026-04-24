import type { Metadata } from "next";
import { Manrope, Source_Serif_4 } from "next/font/google";
import type { ReactNode } from "react";

import { SiteIntro } from "@/components/intro/site-intro";
import { QueryProvider } from "@/lib/query-provider";

import "./globals.css";

const manrope = Manrope({
  subsets: ["latin", "cyrillic"],
  variable: "--font-manrope",
});

const sourceSerif = Source_Serif_4({
  subsets: ["latin", "cyrillic"],
  variable: "--font-display",
});

export const metadata: Metadata = {
  title: "Askora",
  description: "Askora — AI-ассистент запросов для аналитики без SQL",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body className={`${manrope.variable} ${sourceSerif.variable} font-sans`}>
        <QueryProvider>
          {children}
          <SiteIntro />
        </QueryProvider>
      </body>
    </html>
  );
}
