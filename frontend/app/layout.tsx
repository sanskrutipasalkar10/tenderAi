import { MotionConfig } from "framer-motion";
import type { Metadata } from "next";
import { DM_Sans, IBM_Plex_Mono, Manrope } from "next/font/google";
import "./globals.css";

// DM Sans (body/UI) + Manrope (font-display, headings) — the unified pair pulled from
// sanskrutipasalkar10/bid-analysis-studio (docs/DESIGN.md Revision 5), applied
// app-wide. IBM Plex Mono stays reserved for verifiable data (DESIGN.md's original,
// still-load-bearing distinction, unchanged across every revision).
const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Tender AI Platform",
  description:
    "Go/No-Go recommendation, synopsis, and page-cited risk list for Indian government tender documents — every claim traceable to its source page.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${dmSans.variable} ${manrope.variable} ${plexMono.variable} h-full`}>
      <body className="min-h-full antialiased">
        {/* Respects the OS-level "reduce motion" accessibility setting automatically —
            framer-motion does not do this on its own. */}
        <MotionConfig reducedMotion="user">{children}</MotionConfig>
      </body>
    </html>
  );
}
