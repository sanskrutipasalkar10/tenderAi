import { MotionConfig } from "framer-motion";
import type { Metadata } from "next";
import { IBM_Plex_Mono, Manrope } from "next/font/google";
import "./globals.css";

// Manrope — a precise geometric-humanist grotesk (see DESIGN.md's ContraVault-inspired
// revision): tighter letterforms and a genuine medium weight read as more
// "engineering-grade" at large heading sizes than IBM Plex Sans's more mechanical
// forms. IBM Plex Mono stays reserved for verifiable data (DESIGN.md's original,
// still-load-bearing distinction).
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
    <html lang="en" className={`${manrope.variable} ${plexMono.variable} h-full`}>
      <body className="min-h-full antialiased">
        {/* Respects the OS-level "reduce motion" accessibility setting automatically —
            framer-motion does not do this on its own. */}
        <MotionConfig reducedMotion="user">{children}</MotionConfig>
      </body>
    </html>
  );
}
