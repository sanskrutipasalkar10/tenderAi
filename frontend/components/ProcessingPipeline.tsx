"use client";

import { motion } from "framer-motion";
import type { DocumentStatus, DocumentStatusResponse } from "@/lib/types";

interface StepDef {
  key: string;
  label: string;
  detail: string;
  statuses: DocumentStatus[];
}

const STEPS: StepDef[] = [
  { key: "uploaded", label: "Uploaded", detail: "File received", statuses: ["uploaded"] },
  {
    key: "classifying",
    label: "Classifying pages",
    detail: "Native text, scanned, or table",
    statuses: ["classifying"],
  },
  {
    key: "extracting",
    label: "Extracting content",
    detail: "Every page, in full",
    statuses: ["extracting", "extracted"],
  },
  {
    key: "analyzing",
    label: "Analyzing",
    detail: "Go/No-Go, synopsis, risk",
    statuses: ["analyzing"],
  },
  { key: "ready", label: "Ready", detail: "Analysis complete", statuses: ["ready"] },
];

function stepIndexForStatus(status: DocumentStatus): number {
  const i = STEPS.findIndex((s) => s.statuses.includes(status));
  return i === -1 ? 0 : i;
}

/** Live view of the backend pipeline's real, persisted status (`documents.status` —
 * CLAUDE.md hard rule 5: task state is explicit in Postgres, never only in-memory) —
 * polled by the parent and rendered here, so a page reload or a back/forward
 * navigation always re-syncs to the server's actual progress rather than trusting
 * stale client state. */
export default function ProcessingPipeline({ status }: { status: DocumentStatusResponse }) {
  if (status.status === "failed") {
    return (
      <div className="rounded-md border border-severity-high/30 bg-severity-high/5 p-6">
        <p className="text-sm font-semibold text-severity-high">Processing failed</p>
        <p className="mt-1 text-sm text-slate-600">
          Something went wrong while processing this document. Try re-uploading it, or contact
          support if the problem persists.
        </p>
      </div>
    );
  }

  const activeIndex = stepIndexForStatus(status.status);
  const progressPct = STEPS.length > 1 ? activeIndex / (STEPS.length - 1) : 0;
  const pageProgress =
    status.total_pages && status.total_pages > 0
      ? Math.min(1, status.pages_processed / status.total_pages)
      : null;
  const chunkProgress =
    status.chunks_total > 0 ? Math.min(1, status.chunks_mapped / status.chunks_total) : null;
  const moduleProgress = status.modules_ready.length / 3;

  return (
    <div className="rounded-md border border-slate-200 bg-white p-6 sm:p-8">
      <div className="relative">
        <div className="absolute top-5 right-0 left-0 hidden h-0.5 bg-slate-100 sm:block" />
        <motion.div
          className="absolute top-5 left-0 hidden h-0.5 bg-accent sm:block"
          initial={{ width: 0 }}
          animate={{ width: `${progressPct * 100}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
        <div className="relative grid grid-cols-1 gap-6 sm:grid-cols-5 sm:gap-2">
          {STEPS.map((step, i) => {
            const isComplete = i < activeIndex || status.status === "ready";
            const isActive = i === activeIndex && status.status !== "ready";
            return (
              <div key={step.key} className="flex items-center gap-3 sm:flex-col sm:items-center sm:text-center">
                <div className="relative flex h-8 w-8 flex-none items-center justify-center sm:h-10 sm:w-10">
                  {i < STEPS.length - 1 && (
                    <div
                      className={`absolute top-8 left-1/2 h-6 w-0.5 -translate-x-1/2 sm:hidden ${
                        isComplete ? "bg-accent" : "bg-slate-100"
                      }`}
                    />
                  )}
                  {isActive && (
                    <motion.span
                      className="absolute inset-0 rounded-full bg-accent/20"
                      animate={{ scale: [1, 1.4, 1], opacity: [0.6, 0, 0.6] }}
                      transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
                    />
                  )}
                  <motion.div
                    initial={false}
                    animate={{
                      backgroundColor: isComplete ? "var(--color-accent)" : isActive ? "var(--color-accent)" : "#ffffff",
                      borderColor: isComplete || isActive ? "var(--color-accent)" : "var(--color-slate-300, #cbd5e1)",
                    }}
                    className="relative z-10 flex h-8 w-8 items-center justify-center rounded-full border-2 sm:h-10 sm:w-10"
                  >
                    {isComplete ? (
                      <motion.svg
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ type: "spring", stiffness: 400, damping: 20 }}
                        viewBox="0 0 20 20"
                        fill="none"
                        className="h-4 w-4 text-white"
                      >
                        <path
                          d="M4 10.5l3.5 3.5L16 5.5"
                          stroke="currentColor"
                          strokeWidth={2}
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </motion.svg>
                    ) : isActive ? (
                      <span className="h-2.5 w-2.5 rounded-full bg-white" />
                    ) : (
                      <span className="data-mono text-xs text-slate-400">{i + 1}</span>
                    )}
                  </motion.div>
                </div>
                <div className="sm:mt-1">
                  <p
                    className={`text-sm font-medium ${
                      isActive || isComplete ? "text-ink-900" : "text-slate-400"
                    }`}
                  >
                    {step.label}
                  </p>
                  <p className="text-xs text-slate-400">{step.detail}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {status.status !== "ready" && (
        <div className="mt-8 space-y-5">
          {pageProgress !== null && (status.status === "extracting" || status.status === "extracted") && (
            <ProgressBar
              label="Pages extracted"
              value={status.pages_processed}
              total={status.total_pages ?? 0}
              fraction={pageProgress}
            />
          )}
          {status.status === "analyzing" && chunkProgress !== null && (
            <ProgressBar
              label="Chunks mapped"
              value={status.chunks_mapped}
              total={status.chunks_total}
              fraction={chunkProgress}
            />
          )}
          {status.status === "analyzing" && (
            <ProgressBar
              label="Modules ready"
              value={status.modules_ready.length}
              total={3}
              fraction={moduleProgress}
            />
          )}
        </div>
      )}
    </div>
  );
}

function ProgressBar({
  label,
  value,
  total,
  fraction,
}: {
  label: string;
  value: number;
  total: number;
  fraction: number;
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-xs text-slate-500">
        <span>{label}</span>
        <span className="data-mono">
          {value} / {total}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
        <motion.div
          className="h-full rounded-full bg-accent"
          initial={{ width: 0 }}
          animate={{ width: `${fraction * 100}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}
