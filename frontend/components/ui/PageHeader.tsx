"use client";

import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { ChevronLeftIcon } from "./icons";

/** The full-bleed bordered hero header every authenticated page opens with
 * (docs/DESIGN.md Revision 5) — an eyebrow label, a font-display title, an optional
 * subtitle/back-link/badge, and a trailing action, inside a bg-surface section that
 * spans the viewport before the contained body content below it. */
export default function PageHeader({
  eyebrow,
  title,
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
              <h1 className="max-w-4xl wrap-break-word font-display text-4xl font-semibold leading-tight md:text-[48px]">
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
