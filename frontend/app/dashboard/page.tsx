"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { useEffect, useState } from "react";
import { DecisionBadge, StatusBadge } from "@/components/badges";
import AppShell from "@/components/AppShell";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import PageHeader from "@/components/ui/PageHeader";
import { UploadIcon } from "@/components/ui/icons";
import { ApiError, getAnalysis, listDocuments } from "@/lib/api";
import type { DocumentUploadResponse, GoNoGoResult } from "@/lib/types";

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

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle={documents ? `${documents.length} tender${documents.length === 1 ? "" : "s"}` : "Loading…"}
        action={<Button href="/upload" icon={<UploadIcon className="h-4 w-4" />}>Upload tender</Button>}
      />

      {error && (
        <p className="rounded-md border border-severity-high/30 bg-severity-high/5 px-4 py-3 text-sm text-severity-high">
          {error}
        </p>
      )}

      {documents && documents.length === 0 && !error && (
        <EmptyState
          icon={<UploadIcon className="h-6 w-6" />}
          title="No tenders uploaded yet"
          description="Upload a tender PDF to get a Go/No-Go score, synopsis, and risk list."
          actionLabel="Upload tender"
          actionHref="/upload"
        />
      )}

      {documents && documents.length > 0 && (
        <Card padding="sm" className="overflow-x-auto p-0">
          <table className="w-full min-w-180 border-collapse text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="px-5 py-3">Tender</th>
                <th className="px-5 py-3">Issuing authority</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Go/No-Go</th>
                <th className="px-5 py-3">Uploaded</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {documents.map((doc, i) => {
                const decision = decisions[doc.id];
                const borderClass = decision ? DECISION_BORDER[decision] : "border-l-slate-200";
                return (
                  <motion.tr
                    key={doc.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.25, delay: Math.min(i * 0.04, 0.4) }}
                    className={`border-l-4 transition-colors hover:bg-slate-50 ${borderClass}`}
                  >
                    <td className="px-5 py-4">
                      <Link href={`/documents/${doc.id}`} className="font-medium text-ink-900 hover:text-accent">
                        {doc.filename}
                      </Link>
                      <p className="data-mono mt-0.5 text-xs text-slate-400">
                        {doc.total_pages ? `${doc.total_pages} pages` : "—"}
                      </p>
                    </td>
                    <td className="px-5 py-4 text-slate-600">{doc.issuing_authority ?? "—"}</td>
                    <td className="px-5 py-4">
                      <StatusBadge status={doc.status} />
                    </td>
                    <td className="px-5 py-4">
                      {decision ? (
                        <DecisionBadge decision={decision} />
                      ) : (
                        <span className="text-xs text-slate-400">Not yet analyzed</span>
                      )}
                    </td>
                    <td className="data-mono px-5 py-4 text-xs text-slate-500">
                      {new Date(doc.uploaded_at).toLocaleDateString("en-IN", {
                        day: "2-digit",
                        month: "short",
                        year: "numeric",
                      })}
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
