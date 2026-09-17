"use client";

import { use, useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import GoNoGoCard from "@/components/GoNoGoCard";
import RiskList from "@/components/RiskList";
import SynopsisView from "@/components/SynopsisView";
import { ApiError, getAllAnalysis, getDocumentStatus } from "@/lib/api";
import type {
  AnalysisModule,
  DocumentAnalysisResponse,
  DocumentStatusResponse,
  GoNoGoResult,
  RiskFinderResult,
  SynopsisResult,
} from "@/lib/types";

const TABS: { module: AnalysisModule; label: string }[] = [
  { module: "go_no_go", label: "Go / No-Go" },
  { module: "synopsis", label: "Synopsis" },
  { module: "risk_finder", label: "Risk Finder" },
];

export default function DocumentDetailPage(props: PageProps<"/documents/[id]">) {
  const { id: documentId } = use(props.params);

  return (
    <AuthGuard>
      <DocumentDetail documentId={documentId} />
    </AuthGuard>
  );
}

function DocumentDetail({ documentId }: { documentId: string }) {
  const [status, setStatus] = useState<DocumentStatusResponse | null>(null);
  const [analyses, setAnalyses] = useState<DocumentAnalysisResponse[]>([]);
  const [activeTab, setActiveTab] = useState<AnalysisModule>("go_no_go");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDocumentStatus(documentId)
      .then(setStatus)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Load failed"));
    getAllAnalysis(documentId)
      .then(setAnalyses)
      .catch(() => {
        // No analysis yet is a normal state (still processing), not an error to show.
      });
  }, [documentId]);

  const activeResult = analyses.find((a) => a.module === activeTab);

  return (
    <div className="space-y-6">
      {error && <p className="text-sm text-red-600">{error}</p>}
      {status && (
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold">Document</h1>
          <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-medium text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300">
            {status.status}
          </span>
          <span className="text-xs text-neutral-500">
            {status.pages_processed}/{status.total_pages ?? "?"} pages processed
          </span>
        </div>
      )}

      <div className="flex gap-1 border-b border-neutral-200 dark:border-neutral-800">
        {TABS.map((tab) => (
          <button
            key={tab.module}
            type="button"
            onClick={() => setActiveTab(tab.module)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              activeTab === tab.module
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div>
        {!activeResult && (
          <p className="text-sm text-neutral-500">
            No {TABS.find((t) => t.module === activeTab)?.label} analysis available yet for this
            document.
          </p>
        )}
        {activeResult && activeTab === "go_no_go" && (
          <GoNoGoCard documentId={documentId} result={activeResult.result as GoNoGoResult} />
        )}
        {activeResult && activeTab === "synopsis" && (
          <SynopsisView documentId={documentId} result={activeResult.result as SynopsisResult} />
        )}
        {activeResult && activeTab === "risk_finder" && (
          <RiskList documentId={documentId} result={activeResult.result as RiskFinderResult} />
        )}
      </div>
    </div>
  );
}
