"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { use, useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import CompanyChecklistView from "@/components/CompanyChecklistView";
import GoNoGoCard from "@/components/GoNoGoCard";
import ProcessingLog from "@/components/ProcessingLog";
import ProcessingPipeline from "@/components/ProcessingPipeline";
import RiskList from "@/components/RiskList";
import SynopsisView from "@/components/SynopsisView";
import { StatusBadge } from "@/components/badges";
import { ApiError, getAllAnalysis, getDocumentStatus } from "@/lib/api";
import type {
  AnalysisModule,
  DocumentAnalysisResponse,
  DocumentStatusResponse,
  GoNoGoResult,
  RiskFinderResult,
  SynopsisResult,
} from "@/lib/types";

// "company_checklist" is a UI-only tab, not a real AnalysisModule — it has no
// dedicated backend endpoint, it just renders a different view of the already-fetched
// go_no_go analysis (CompanyChecklistView).
type UiTab = AnalysisModule | "company_checklist";

const TABS: { module: UiTab; label: string }[] = [
  { module: "go_no_go", label: "Go / No-Go" },
  { module: "synopsis", label: "Synopsis" },
  { module: "company_checklist", label: "Company Checklist" },
  { module: "risk_finder", label: "Risk Finder" },
];

const POLL_INTERVAL_MS = 4000;
const TERMINAL_STATUSES = new Set(["ready", "failed"]);

export default function DocumentDetailPage(props: PageProps<"/documents/[id]">) {
  const { id: documentId } = use(props.params);

  return (
    <AppShell>
      <DocumentDetail documentId={documentId} />
    </AppShell>
  );
}

function DocumentDetail({ documentId }: { documentId: string }) {
  const router = useRouter();
  const [status, setStatus] = useState<DocumentStatusResponse | null>(null);
  const [analyses, setAnalyses] = useState<DocumentAnalysisResponse[]>([]);
  const [activeTab, setActiveTab] = useState<UiTab>("go_no_go");
  const [error, setError] = useState<string | null>(null);
  const wasReady = useRef(false);

  // Polls the real, persisted backend status (never trusts client-held state — a back/
  // forward navigation or a page reload always re-syncs to what the server actually
  // recorded, per CLAUDE.md hard rule 5). Stops once the pipeline reaches a terminal
  // state so an already-finished document doesn't poll forever.
  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const s = await getDocumentStatus(documentId);
        if (cancelled) return;
        setStatus(s);
        // A transient poll failure (e.g. the DB connection blipping) shouldn't leave a
        // permanent error banner once a later poll succeeds — the pipeline itself kept
        // making real progress the whole time, per the status this just received.
        setError(null);
        if (s.status === "ready" && !wasReady.current) {
          wasReady.current = true;
          getAllAnalysis(documentId)
            .then((a) => !cancelled && setAnalyses(a))
            .catch(() => {});
        }
        if (TERMINAL_STATUSES.has(s.status)) {
          clearInterval(interval);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Load failed");
      }
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [documentId]);

  const goNoGoAnalysis = analyses.find((a) => a.module === "go_no_go");
  const activeResult =
    activeTab === "company_checklist"
      ? goNoGoAnalysis
      : analyses.find((a) => a.module === activeTab);
  const isProcessing = status !== null && !TERMINAL_STATUSES.has(status.status);

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          className="flex items-center gap-1.5 rounded p-1 -ml-1 text-sm font-medium text-slate-500 hover:text-ink-900"
        >
          <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4">
            <path
              d="M12.5 15L7.5 10L12.5 5"
              stroke="currentColor"
              strokeWidth={1.75}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Back
        </button>
        <h1 className="text-2xl font-semibold text-ink-900">Tender analysis</h1>
        {status && <StatusBadge status={status.status} />}
        {status && (
          <span className="data-mono text-xs text-slate-400">
            {status.pages_processed}/{status.total_pages ?? "?"} pages processed
          </span>
        )}
      </div>

      {error && (
        <p className="mb-6 rounded-md border border-severity-high/30 bg-severity-high/5 px-4 py-3 text-sm text-severity-high">
          {error}
        </p>
      )}

      <AnimatePresence mode="wait">
        {isProcessing && status && (
          <motion.div
            key="pipeline"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.3 }}
          >
            <ProcessingPipeline status={status} />
            <p className="mt-4 mb-4 text-sm text-slate-500">
              This can take a while for a large tender — completeness matters more than speed
              here. You can navigate away; processing continues in the background, and this page
              will pick up right where it left off.
            </p>
            <ProcessingLog status={status} />
          </motion.div>
        )}

        {status?.status === "ready" && (
          <motion.div
            key="results"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
          >
            <div className="mb-8 flex gap-1 border-b border-slate-200">
              {TABS.map((tab) => (
                <button
                  key={tab.module}
                  type="button"
                  onClick={() => setActiveTab(tab.module)}
                  className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
                    activeTab === tab.module
                      ? "border-accent text-accent"
                      : "border-transparent text-slate-500 hover:text-ink-900"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
              >
                {!activeResult && (
                  <p className="text-sm text-slate-500">
                    No {TABS.find((t) => t.module === activeTab)?.label} analysis available yet
                    for this document.
                  </p>
                )}
                {activeResult && activeTab === "go_no_go" && (
                  <GoNoGoCard documentId={documentId} result={activeResult.result as GoNoGoResult} />
                )}
                {activeResult && activeTab === "synopsis" && (
                  <SynopsisView
                    documentId={documentId}
                    result={activeResult.result as SynopsisResult}
                    goNoGoResult={goNoGoAnalysis ? (goNoGoAnalysis.result as GoNoGoResult) : null}
                  />
                )}
                {activeResult && activeTab === "company_checklist" && (
                  <CompanyChecklistView
                    documentId={documentId}
                    goNoGoResult={activeResult.result as GoNoGoResult}
                  />
                )}
                {activeResult && activeTab === "risk_finder" && (
                  <RiskList
                    documentId={documentId}
                    result={activeResult.result as RiskFinderResult}
                  />
                )}
              </motion.div>
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
