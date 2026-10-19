"use client";

import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, FileDown, FileText, RefreshCw, Scale, Square } from "lucide-react";
import { useRouter } from "next/navigation";
import { use, useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import GoNoGoCard from "@/components/GoNoGoCard";
import ProcessingLog from "@/components/ProcessingLog";
import ProcessingPipeline from "@/components/ProcessingPipeline";
import RiskList from "@/components/RiskList";
import SynopsisView from "@/components/SynopsisView";
import { StatusBadge } from "@/components/badges";
import Button from "@/components/ui/Button";
import PageHeader from "@/components/ui/PageHeader";
import Tabs, { TabIconChip } from "@/components/ui/Tabs";
import { ApiError, cancelDocument, getAllAnalysis, getDocumentStatus, reevaluateDocument } from "@/lib/api";
import type {
  AnalysisModule,
  DocumentAnalysisResponse,
  DocumentStatusResponse,
  GoNoGoResult,
  RiskFinderResult,
  SynopsisResult,
} from "@/lib/types";

// Company Checklist lives inside the Go/No-Go tab as its 3rd sub-tab now
// (GoNoGoCard.tsx) rather than as its own top-level tab — it's a different view of
// the same go_no_go analysis, not a separate module, so it never needed to be a peer
// of Go/No-Go in the first place.
type UiTab = AnalysisModule;

const TABS: { module: UiTab; label: string }[] = [
  { module: "go_no_go", label: "Go / No-Go" },
  { module: "synopsis", label: "Synopsis" },
  { module: "risk_finder", label: "Risk Finder" },
];

const TAB_ICON: Record<UiTab, typeof Scale> = {
  go_no_go: Scale,
  synopsis: FileText,
  risk_finder: AlertTriangle,
};
const TAB_ICON_TONE: Record<UiTab, "primary" | "go" | "danger"> = {
  go_no_go: "primary",
  synopsis: "primary",
  risk_finder: "danger",
};

const TAB_ITEMS = TABS.map((t) => ({
  id: t.module,
  label: t.label,
  icon: <TabIconChip icon={TAB_ICON[t.module]} tone={TAB_ICON_TONE[t.module]} />,
}));

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
  const [startingReevaluate, setStartingReevaluate] = useState(false);
  const [stoppingProcessing, setStoppingProcessing] = useState(false);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const cancelledRef = useRef(false); // true once this component has unmounted (polling guard)

  function stopPolling() {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }

  // Polls the real, persisted backend status (never trusts client-held state — a back/
  // forward navigation or a page reload always re-syncs to what the server actually
  // recorded, per CLAUDE.md hard rule 5). Stops once the pipeline reaches a terminal
  // state so an already-finished document doesn't poll forever — and, importantly,
  // restartable: a plain one-shot "stop at terminal" loop would never notice a
  // Reevaluate triggered after the document was already "ready" once, since the
  // interval that would catch the status flipping back to "analyzing" is gone by then.
  function startPolling() {
    stopPolling();

    async function poll() {
      try {
        const s = await getDocumentStatus(documentId);
        if (cancelledRef.current) return;
        setStatus(s);
        // A transient poll failure (e.g. the DB connection blipping) shouldn't leave a
        // permanent error banner once a later poll succeeds — the pipeline itself kept
        // making real progress the whole time, per the status this just received.
        setError(null);
        if (s.status === "ready") {
          getAllAnalysis(documentId)
            .then((a) => !cancelledRef.current && setAnalyses(a))
            .catch(() => {});
        }
        if (TERMINAL_STATUSES.has(s.status)) {
          stopPolling();
        }
      } catch (err) {
        if (!cancelledRef.current) setError(err instanceof ApiError ? err.message : "Load failed");
      }
    }

    poll();
    pollTimerRef.current = setInterval(poll, POLL_INTERVAL_MS);
  }

  useEffect(() => {
    cancelledRef.current = false;
    startPolling();
    return () => {
      cancelledRef.current = true;
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- startPolling closes over documentId fresh each render; only documentId itself should restart the effect
  }, [documentId]);

  async function handleReevaluate() {
    setStartingReevaluate(true);
    setError(null);
    try {
      const updated = await reevaluateDocument(documentId);
      // The backend clears this document's old analysis rows as part of starting a
      // reevaluation (so modules_ready genuinely counts back up from 0, not a stale
      // 3/3) — drop them here too so a render between now and the next poll can't
      // show a results tab for data that no longer exists server-side.
      setStatus((cur) => (cur ? { ...cur, status: updated.status } : cur));
      setAnalyses([]);
      startPolling();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start reevaluation");
    } finally {
      setStartingReevaluate(false);
    }
  }

  async function handleStopProcessing() {
    if (!window.confirm("Stop processing this tender? This can't be resumed — you'd need to re-upload.")) {
      return;
    }
    setStoppingProcessing(true);
    setError(null);
    try {
      const updated = await cancelDocument(documentId);
      // The backend can only request a stop cooperatively (CLAUDE.md — Celery runs
      // --pool=solo here, no way to forcibly interrupt an already-running task), so
      // whatever step is mid-flight right now finishes before noticing. Reflect the
      // real server state immediately rather than waiting for the next poll tick.
      setStatus(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not stop processing");
    } finally {
      setStoppingProcessing(false);
    }
  }

  const goNoGoAnalysis = analyses.find((a) => a.module === "go_no_go");
  const activeResult = analyses.find((a) => a.module === activeTab);
  const isProcessing = status !== null && !TERMINAL_STATUSES.has(status.status);

  return (
    <div>
      <PageHeader
        eyebrow="TENDER / REVIEW"
        title={status?.filename ?? "Tender analysis"}
        titleSize="md"
        accentPeriod={!status?.filename}
        onBack={() => router.back()}
        backLabel="All tenders"
        badge={status && <StatusBadge status={status.status} />}
        meta={
          status && (
            <span className="data-mono text-xs text-muted-foreground">
              {status.pages_processed}/{status.total_pages ?? "?"} pages processed
            </span>
          )
        }
        action={
          <>
            {status?.status === "ready" && (
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  loading={startingReevaluate}
                  onClick={() => void handleReevaluate()}
                  icon={<RefreshCw className="h-4 w-4" />}
                >
                  Reevaluate
                </Button>
                <Button
                  href={`/documents/${documentId}/report`}
                  variant="outline"
                  icon={<FileDown className="h-4 w-4" />}
                >
                  Download report
                </Button>
              </div>
            )}
            {isProcessing && (
              <Button
                variant="destructive"
                loading={stoppingProcessing}
                onClick={() => void handleStopProcessing()}
                icon={<Square className="h-3.5 w-3.5" />}
              >
                Stop processing
              </Button>
            )}
          </>
        }
      />

      <div className="mx-auto max-w-305 px-5 py-9 md:px-8">
        {error && (
          <p className="mb-6 rounded-md border border-severity-high/30 bg-severity-high/5 px-4 py-3 text-sm text-severity-high">
            {error}
          </p>
        )}

        <AnimatePresence mode="wait">
          {(isProcessing || status?.status === "failed") && status && (
            <motion.div
              key="pipeline"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.3 }}
            >
              <ProcessingPipeline status={status} />
              {/* "Processing continues in the background" is actively wrong once the
                  document has terminally failed — nothing is still running. */}
              {status.status !== "failed" && (
                <p className="mt-4 mb-4 text-sm text-muted-foreground">
                  This can take a while for a large tender — completeness matters more than speed
                  here. You can navigate away; processing continues in the background, and this
                  page will pick up right where it left off.
                </p>
              )}
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
              <div className="mb-8">
                <Tabs items={TAB_ITEMS} active={activeTab} onChange={setActiveTab} />
              </div>

              <AnimatePresence mode="wait">
                <motion.div
                  key={activeTab}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  {!activeResult && (
                    <p className="text-sm text-muted-foreground">
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
    </div>
  );
}
