import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import { Providers } from "@/app/providers";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "CivicPulse AI — See it. Report it. Track it. Resolve it.",
    template: "%s · CivicPulse AI",
  },
  description:
    "Report public infrastructure problems in seconds. AI helps prepare your complaint, find the responsible department, and track progress toward resolution.",
};

export const viewport: Viewport = {
  themeColor: "#12324A",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full`}>
      <body className="flex min-h-full flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
