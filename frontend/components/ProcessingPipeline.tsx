"use client";

import { motion } from "framer-motion";
import Card from "./ui/Card";
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
      <Card tone="danger">
        <p className="text-sm font-semibold text-severity-high">Processing failed</p>
        <p className="mt-1 text-sm text-slate-600">
          Something went wrong while processing this document. Try re-uploading it, or contact
          support if the problem persists.
        </p>
      </Card>
    );
  }

  const activeIndex = stepIndexForStatus(status.status);
  const progressPct = STEPS.length > 1 ? activeIndex / (STEPS.length - 1) : 0;
  const chunkProgress =
    status.chunks_total > 0 ? Math.min(1, status.chunks_mapped / status.chunks_total) : null;
  const moduleProgress = status.modules_ready.length / 3;

  return (
    <Card padding="lg">
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
          {(status.status === "extracting" || status.status === "extracted") && (
            // Three honest counters rather than a single "X/Y" fraction (docs/
            // DECISIONS.md) — once a hyperlinked document's pages start getting
            // appended, pages_processed legitimately exceeds the uploaded PDF's own
            // page count, and total_pages itself only becomes the final combined
            // count once every link has been fetched. A fraction against either
            // number reads as broken ("48/6 pages processed") during that window;
            // three separately-labeled counts never lie about what's known yet.
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <StatBlock
                label="Main document"
                value={`${status.main_document_pages} page${status.main_document_pages === 1 ? "" : "s"}`}
              />
              <StatBlock
                label="Linked documents found"
                value={String(status.linked_documents_found)}
              />
              <StatBlock label="Total pages extracted" value={String(status.pages_processed)} />
            </div>
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
    </Card>
  );
}

function StatBlock({ label, value }: { label: string; value: string }) {
  return (
    <Card tone="subtle" padding="sm" className="px-4 py-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="data-mono mt-1 text-lg font-semibold text-ink-900">{value}</p>
    </Card>
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
