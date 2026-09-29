"use client";

import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { ChevronLeftIcon } from "./icons";

export default function PageHeader({
  title,
  subtitle,
  onBack,
  badge,
  meta,
  action,
}: {
  title: string;
  subtitle?: string;
  onBack?: () => void;
  badge?: ReactNode;
  meta?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mb-8 flex flex-wrap items-start justify-between gap-4"
    >
      <div>
        <div className="flex flex-wrap items-center gap-3">
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="-ml-1 flex items-center gap-1.5 rounded p-1 text-sm font-medium text-slate-500 hover:text-ink-900"
            >
              <ChevronLeftIcon className="h-4 w-4" />
              Back
            </button>
          )}
          <h1 className="text-2xl font-semibold text-ink-900">{title}</h1>
          {badge}
          {meta}
        </div>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </motion.div>
  );
}
