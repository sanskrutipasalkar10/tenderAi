"use client";

import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { ChevronLeftIcon } from "./icons";

/** The full-bleed bordered hero header every authenticated page opens with
 * (docs/DESIGN.md Revision 5) — an eyebrow label, a font-display title, an optional
 * subtitle/back-link/badge, and a trailing action, inside a bg-surface section that
 * spans the viewport before the contained body content below it. */
const TITLE_SIZE = {
  // The default everywhere else — short, static page titles ("Tender dashboard").
  lg: "text-4xl md:text-[48px]",
  // For dynamic, often-long titles (a real uploaded filename) — the same size reads
  // fine for "Tender dashboard" but overwhelms the header once it's a 30+ character
  // filename instead.
  md: "text-2xl md:text-[32px]",
};

export default function PageHeader({
  eyebrow,
  title,
  titleSize = "lg",
  accentPeriod = true,
  subtitle,
  onBack,
  backLabel = "Back",
  badge,
  meta,
  action,
}: {
  eyebrow?: string;
  title: string;
  titleSize?: keyof typeof TITLE_SIZE;
  /** Appends a primary-colored "." after the title, matching the pulled design's
   * static page titles ("Tender dashboard.") — turned off for dynamic titles like a
   * tender's real filename, where an appended period would misleadingly change it. */
  accentPeriod?: boolean;
  subtitle?: string;
  onBack?: () => void;
  backLabel?: string;
  badge?: ReactNode;
  meta?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="border-b border-border bg-surface">
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="mx-auto max-w-305 px-5 pb-9 pt-12 md:px-8 md:pt-15"
      >
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="mb-8 inline-flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-primary"
          >
            <ChevronLeftIcon className="h-4 w-4" />
            {backLabel}
          </button>
        )}
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            {eyebrow && <p className="eyebrow mb-3">{eyebrow}</p>}
            <div className="flex flex-wrap items-center gap-3">
              <h1
                className={`max-w-4xl wrap-break-word font-display font-semibold leading-tight ${TITLE_SIZE[titleSize]}`}
              >
                {title}
                {accentPeriod && <span className="text-primary">.</span>}
              </h1>
              {badge}
              {meta}
            </div>
            {subtitle && <p className="mt-3 max-w-xl text-base text-muted-foreground">{subtitle}</p>}
          </div>
          {action}
        </div>
      </motion.div>
    </section>
  );
}
