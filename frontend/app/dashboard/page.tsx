"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { useEffect, useState } from "react";
import { DecisionBadge, StatusBadge } from "@/components/badges";
import AppShell from "@/components/AppShell";
import { ApiError, getAnalysis, listDocuments } from "@/lib/api";
import type { DocumentUploadResponse, GoNoGoResult } from "@/lib/types";

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
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="mb-8 flex items-center justify-between"
      >
        <div>
          <h1 className="text-2xl font-semibold text-ink-900">Dashboard</h1>
          <p className="mt-1 text-sm text-slate-500">
            {documents ? `${documents.length} tender${documents.length === 1 ? "" : "s"}` : "Loading…"}
          </p>
        </div>
        <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
          <Link
            href="/upload"
            className="inline-block rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-cyan-600"
          >
            Upload tender
          </Link>
        </motion.div>
      </motion.div>

      {error && (
        <p className="rounded-md border border-severity-high/30 bg-severity-high/5 px-4 py-3 text-sm text-severity-high">
          {error}
        </p>
      )}

      {documents && documents.length === 0 && !error && (
        <EmptyState />
      )}

      {documents && documents.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
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
              {documents.map((doc, i) => (
                <motion.tr
                  key={doc.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, delay: Math.min(i * 0.04, 0.4) }}
                  className="transition-colors hover:bg-slate-50"
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
                    {decisions[doc.id] ? (
                      <DecisionBadge decision={decisions[doc.id]} />
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
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-md border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
      <p className="text-sm font-medium text-ink-900">No tenders uploaded yet</p>
      <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500">
        Upload a tender PDF to get a Go/No-Go score, synopsis, and risk list.
      </p>
      <Link
        href="/upload"
        className="mt-6 inline-block rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-white hover:bg-cyan-600"
      >
        Upload tender
      </Link>
    </div>
  );
}
