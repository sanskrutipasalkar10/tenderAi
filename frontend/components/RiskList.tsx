"use client";

import { useState } from "react";
import CitationLink from "./CitationLink";
import ScoreGauge from "./ScoreGauge";
import { SeverityBadge } from "./badges";
import type { RiskFinderResult } from "@/lib/types";

const SEVERITY_RANK: Record<RiskFinderResult["risks"][number]["severity"], number> = {
  HIGH: 0,
  MEDIUM: 1,
  LOW: 2,
};

function gaugeColor(riskScore: number): string {
  if (riskScore >= 70) return "stroke-severity-high";
  if (riskScore >= 40) return "stroke-severity-medium";
  return "stroke-severity-low";
}

export default function RiskList({
  documentId,
  result,
}: {
  documentId: string;
  result: RiskFinderResult;
}) {
  const sortedRisks = [...result.risks].sort(
    (a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity],
  );

  return (
    <div className="space-y-8">
      <div className="flex flex-col items-center gap-6 rounded-md border border-slate-200 bg-white p-8 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col items-center gap-6 sm:flex-row sm:gap-10">
          <ScoreGauge
            score={result.risk_score}
            label="Overall risk score"
            colorClass={gaugeColor(result.risk_score)}
          />
          <div className="text-center sm:text-left">
            <p className="text-sm text-slate-500">
              {result.risks.length} risk{result.risks.length === 1 ? "" : "s"} identified, ranked
              by severity below. Every clause links to its source page.
            </p>
          </div>
        </div>
        <ExportButton documentId={documentId} result={result} />
      </div>

      {result.risks.length === 0 ? (
        <p className="text-sm text-slate-500">No risks flagged for this document.</p>
      ) : (
        <ul className="space-y-3">
          {sortedRisks.map((risk, i) => (
            <li key={i} className="rounded-md border border-slate-200 bg-white p-5">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <SeverityBadge severity={risk.severity} />
                <span className="text-sm font-semibold text-ink-900">{risk.category}</span>
                {!risk.verified && (
                  <span
                    className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500"
                    title="This citation's page could not be re-verified against the source document — shown, not hidden (docs/SPEC.md §7)"
                  >
                    unverified
                  </span>
                )}
              </div>
              <p className="text-sm text-slate-600">{risk.clause_summary}</p>
              <div className="mt-3">
                <CitationLink documentId={documentId} pageRef={risk.page_ref}>
                  View source clause
                </CitationLink>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ExportButton({ documentId, result }: { documentId: string; result: RiskFinderResult }) {
  const [open, setOpen] = useState(false);

  function exportCsv() {
    const header = ["Category", "Severity", "Clause summary", "Source page", "Verified"];
    const rows = result.risks.map((r) => [
      r.category,
      r.severity,
      r.clause_summary,
      String(r.page_ref),
      r.verified ? "yes" : "no",
    ]);
    const csv = [header, ...rows]
      .map((row) => row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(","))
      .join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `risk-finder-${documentId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    setOpen(false);
  }

  function exportPdf() {
    setOpen(false);
    window.print();
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-ink-900 hover:bg-slate-50"
      >
        Export ▾
      </button>
      {open && (
        <div className="absolute right-0 z-10 mt-1 w-44 overflow-hidden rounded-md border border-slate-200 bg-white shadow-lg">
          <button
            type="button"
            onClick={exportCsv}
            className="block w-full px-4 py-2 text-left text-sm text-ink-900 hover:bg-slate-50"
          >
            Export as Excel (CSV)
          </button>
          <button
            type="button"
            onClick={exportPdf}
            className="block w-full px-4 py-2 text-left text-sm text-ink-900 hover:bg-slate-50"
          >
            Export as PDF (print)
          </button>
        </div>
      )}
    </div>
  );
}
