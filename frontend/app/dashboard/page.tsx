"use client";

import { motion } from "framer-motion";
import { RefreshCw, Search, Upload } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { DecisionBadge, StatusBadge } from "@/components/badges";
import AppShell from "@/components/AppShell";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import PageHeader from "@/components/ui/PageHeader";
import Button from "@/components/ui/Button";
import {
  ApiError,
  getAnalysis,
  getDocumentStatus,
  listDocuments,
  reevaluateDocument,
} from "@/lib/api";
import type { DocumentUploadResponse, GoNoGoResult } from "@/lib/types";

// How often to poll a single document's status while it's being re-evaluated —
// matches documents/[id]/page.tsx's own polling interval, so "processing" feels
// consistent everywhere in the app rather than introducing a second cadence.
const REEVALUATE_POLL_INTERVAL_MS = 4000;

const DECISION_BORDER: Record<GoNoGoResult["decision"], string> = {
  Go: "border-l-status-go",
  "Go (Management Review)": "border-l-status-go",
  "Conditional-Go (Partner Required)": "border-l-status-conditional",
  "No-Go": "border-l-status-no-go",
};

export default function DashboardPage() {
  return (
    <AppShell>
      <DashboardContent />
    </AppShell>
  );
}

function DashboardContent() {
  const [documents, setDocuments] = useState<DocumentUploadResponse[] | null>(null);
  const [decisions, setDecisions] = useState<Record<string, GoNoGoResult["decision"]>>({});
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [reevaluating, setReevaluating] = useState<Set<string>>(new Set());
  const pollIntervals = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  // Stop any still-running per-row polls if the user navigates away mid-reevaluation —
  // otherwise each interval keeps firing and calling setState on an unmounted page.
  useEffect(() => {
    const intervals = pollIntervals.current;
    return () => {
      intervals.forEach(clearInterval);
      intervals.clear();
    };
  }, []);

  function pollUntilReevaluationFinishes(documentId: string) {
    const interval = setInterval(async () => {
      try {
        const status = await getDocumentStatus(documentId);
        setDocuments((docs) =>
          docs?.map((d) => (d.id === documentId ? { ...d, status: status.status } : d)) ?? docs,
        );
        if (status.status !== "ready" && status.status !== "failed") return;

        clearInterval(interval);
        pollIntervals.current.delete(documentId);
        setReevaluating((cur) => {
          const next = new Set(cur);
          next.delete(documentId);
          return next;
        });

        if (status.status === "ready") {
          try {
            const analysis = await getAnalysis<GoNoGoResult>(documentId, "go_no_go");
            setDecisions((cur) => ({ ...cur, [documentId]: analysis.result.decision }));
          } catch {
            // No go_no_go result yet (shouldn't normally happen once "ready") — leave
            // the existing decision badge rather than erroring the whole row out.
          }
        }
      } catch {
        // A transient status-poll failure shouldn't spin the row forever — stop and
        // let the user retry the reevaluate action if it's actually stuck.
        clearInterval(interval);
        pollIntervals.current.delete(documentId);
        setReevaluating((cur) => {
          const next = new Set(cur);
          next.delete(documentId);
          return next;
        });
      }
    }, REEVALUATE_POLL_INTERVAL_MS);
    pollIntervals.current.set(documentId, interval);
  }

  async function handleReevaluate(documentId: string) {
    setReevaluating((cur) => new Set(cur).add(documentId));
    setError(null);
    try {
      const updated = await reevaluateDocument(documentId);
      setDocuments((docs) => docs?.map((d) => (d.id === documentId ? updated : d)) ?? docs);
      // Clear the stale decision immediately so the row doesn't show last run's
      // Go/No-Go badge while a fresh one is being computed.
      setDecisions((cur) => {
        const next = { ...cur };
        delete next[documentId];
        return next;
      });
      pollUntilReevaluationFinishes(documentId);
    } catch (err) {
      setReevaluating((cur) => {
        const next = new Set(cur);
        next.delete(documentId);
        return next;
      });
      setError(err instanceof ApiError ? err.message : "Could not start reevaluation");
    }
  }

  useEffect(() => {
    listDocuments()
      .then(async (docs) => {
        setDocuments(docs);
        // Best-effort, one call per row — pilot-scale volume (low tens/week), not a
        // bulk endpoint the backend has any reason to offer yet. A 404 just means
        // "not analyzed yet," not a real error.
        const results = await Promise.all(
          docs.map(async (doc) => {
            try {
              const analysis = await getAnalysis<GoNoGoResult>(doc.id, "go_no_go");
              return [doc.id, analysis.result.decision] as const;
            } catch {
              return null;
            }
          }),
        );
        setDecisions(Object.fromEntries(results.filter((r): r is [string, GoNoGoResult["decision"]] => r !== null)));
      })
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Could not load documents"));
  }, []);

  const filtered = useMemo(() => {
    if (!documents) return [];
    const q = search.toLowerCase();
    return documents.filter((doc) =>
      `${doc.filename} ${doc.issuing_authority ?? ""} ${decisions[doc.id] ?? ""}`.toLowerCase().includes(q),
    );
  }, [documents, decisions, search]);

  const ready = documents?.filter((d) => d.status === "ready").length ?? 0;
  const go = documents?.filter((d) => decisions[d.id] === "Go" || decisions[d.id] === "Go (Management Review)").length ?? 0;
  const review = documents?.filter((d) => decisions[d.id] === "Conditional-Go (Partner Required)").length ?? 0;

  return (
    <div>
      <PageHeader
        eyebrow="BID TEAM INTELLIGENCE / WORKSPACE"
        title="Tender dashboard"
        subtitle="Your documents, decisions, and next steps — all in one place."
        action={<Button href="/upload" size="md" icon={<Upload className="h-4 w-4" />}>Upload tender</Button>}
      />

      <div className="mx-auto max-w-305 px-5 py-9 md:px-8">
        {error && (
          <p className="mb-6 rounded-md border border-severity-high/30 bg-severity-high/5 px-4 py-3 text-sm text-severity-high">
            {error}
          </p>
        )}

        {documents && (
          <div className="grid grid-cols-2 gap-0 border-y border-border md:grid-cols-4">
            <Metric label="TOTAL TENDERS" value={String(documents.length).padStart(2, "0")} note="In this workspace" />
            <Metric label="READY TO REVIEW" value={String(ready).padStart(2, "0")} note="Analysis available" />
            <Metric label="GO DECISIONS" value={String(go).padStart(2, "0")} note="Eligible to pursue" />
            <Metric label="NEEDS REVIEW" value={String(review).padStart(2, "0")} note="Conditional decisions" />
          </div>
        )}

        {documents && documents.length === 0 && !error && (
          <div className="mt-9">
            <EmptyState
              icon={<Upload className="h-6 w-6" />}
              title="No tenders uploaded yet"
              description="Upload a tender PDF to get a Go/No-Go score, synopsis, and risk list."
              actionLabel="Upload tender"
              actionHref="/upload"
            />
          </div>
        )}

        {documents && documents.length > 0 && (
          <>
            <div className="mb-5 mt-12 flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="eyebrow">DOCUMENT LIBRARY</p>
                <h2 className="mt-2 font-display text-2xl font-semibold md:text-[28px]">Previous tenders</h2>
              </div>
              <label className="flex h-10 w-full items-center gap-2 rounded-md border border-input bg-background px-3 text-muted-foreground focus-within:ring-1 focus-within:ring-ring sm:w-72">
                <Search className="h-4 w-4" />
                <input
                  aria-label="Search tenders"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search tenders"
                  className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                />
              </label>
            </div>

            <Card padding="sm" className="overflow-x-auto p-0">
              <table className="w-full min-w-180 border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border bg-surface text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    <th className="px-5 py-3">Tender</th>
                    <th className="px-4 py-3">Issuing authority</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Go/No-Go</th>
                    <th className="px-4 py-3">Uploaded</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {filtered.map((doc, i) => {
                    const decision = decisions[doc.id];
                    const borderClass = decision ? DECISION_BORDER[decision] : "border-l-border";
                    return (
                      <motion.tr
                        key={doc.id}
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.25, delay: Math.min(i * 0.04, 0.4) }}
                        className={`border-l-4 transition-colors hover:bg-surface ${borderClass}`}
                      >
                        <td className="px-5 py-4">
                          <Link href={`/documents/${doc.id}`} className="font-medium text-foreground hover:text-primary">
                            {doc.filename}
                          </Link>
                          <p className="data-mono mt-0.5 text-xs text-muted-foreground">
                            {doc.total_pages ? `${doc.total_pages} pages` : "—"}
                          </p>
                        </td>
                        <td className="px-4 py-4 text-muted-foreground">{doc.issuing_authority ?? "—"}</td>
                        <td className="px-4 py-4">
                          <StatusBadge status={doc.status} />
                        </td>
                        <td className="px-4 py-4">
                          {decision ? (
                            <DecisionBadge decision={decision} />
                          ) : (
                            <span className="text-xs text-muted-foreground">Not yet analyzed</span>
                          )}
                        </td>
                        <td className="data-mono px-4 py-4 text-xs text-muted-foreground">
                          {new Date(doc.uploaded_at).toLocaleDateString("en-IN", {
                            day: "2-digit",
                            month: "short",
                            year: "numeric",
                          })}
                        </td>
                        <td className="px-4 py-4 text-right">
                          {doc.status === "ready" && (
                            <Button
                              variant="outline"
                              size="sm"
                              loading={reevaluating.has(doc.id)}
                              onClick={() => handleReevaluate(doc.id)}
                              icon={<RefreshCw className="h-3.5 w-3.5" />}
                              aria-label="Re-run scoring against the current company profile and logic"
                            >
                              Reevaluate
                            </Button>
                          )}
                        </td>
                      </motion.tr>
                    );
                  })}
                </tbody>
              </table>
            </Card>
            {filtered.length === 0 && (
              <div className="border border-border px-5 py-12 text-center text-muted-foreground">
                No tenders match your search.
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="border-r border-border px-4 py-5 last:border-r-0 first:pl-0 max-md:nth-[2]:border-r-0 md:px-7">
      <p className="text-[10px] font-bold text-muted-foreground">{label}</p>
      <p className="mt-3 font-display text-4xl font-semibold leading-none text-foreground">{value}</p>
      <p className="mt-2 text-xs text-muted-foreground">{note}</p>
    </div>
  );
}
