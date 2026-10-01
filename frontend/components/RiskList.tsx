"use client";

import { useState } from "react";
import CitationLink from "./CitationLink";
import { SEVERITY_STYLES, SeverityBadge } from "./badges";
import Button from "./ui/Button";
import Card from "./ui/Card";
import { ChevronDownIcon } from "./ui/icons";
import type { RiskFinderResult } from "@/lib/types";

type Severity = RiskFinderResult["risks"][number]["severity"];

const SEVERITY_RANK: Record<Severity, number> = {
  HIGH: 0,
  MEDIUM: 1,
  LOW: 2,
};

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
  const severityCounts = result.risks.reduce(
    (acc, r) => {
      acc[r.severity] += 1;
      return acc;
    },
    { HIGH: 0, MEDIUM: 0, LOW: 0 } as Record<Severity, number>,
  );

  return (
    <div className="space-y-8">
      <Card padding="lg" className="flex flex-col items-center gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col items-center gap-6 sm:flex-row sm:gap-10">
          {/* A count, not a 0-100 score (docs/DESIGN.md) — a risk score styled like
           * Go/No-Go's "97/100" read as "97% good" to users, when a high number here
           * actually means more risk. The raw count of flagged risks has no such
           * ambiguity. */}
          <div className="flex flex-none flex-col items-center">
            <span className="data-mono text-5xl font-semibold text-foreground">
              {result.risks.length}
            </span>
            <span className="mt-2 text-sm font-medium text-muted-foreground">
              Risk{result.risks.length === 1 ? "" : "s"} identified
            </span>
          </div>
          <div className="text-center sm:text-left">
            {result.risks.length > 0 && (
              <div className="flex flex-wrap justify-center gap-2 sm:justify-start">
                {(["HIGH", "MEDIUM", "LOW"] as const)
                  .filter((severity) => severityCounts[severity] > 0)
                  .map((severity) => (
                    <span
                      key={severity}
                      className={`inline-flex items-center whitespace-nowrap rounded px-2 py-0.5 text-xs font-semibold ${SEVERITY_STYLES[severity]}`}
                    >
                      {severityCounts[severity]} {severity}
                    </span>
                  ))}
              </div>
            )}
            <p className="mt-3 text-sm text-muted-foreground">
              Ranked by severity below. Every clause links to its source page.
            </p>
          </div>
        </div>
        <ExportButton documentId={documentId} result={result} />
      </Card>

      {result.risks.length === 0 ? (
        <p className="text-sm text-muted-foreground">No risks flagged for this document.</p>
      ) : (
        <ul className="space-y-3">
          {sortedRisks.map((risk, i) => (
            <li key={i}>
              <Card padding="sm">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <SeverityBadge severity={risk.severity} />
                  <span className="text-sm font-semibold text-foreground">{risk.category}</span>
                  {!risk.verified && (
                    <span
                      className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground"
                      title="This citation's page could not be re-verified against the source document — shown, not hidden (docs/SPEC.md §7)"
                    >
                      unverified
                    </span>
                  )}
                </div>
                <p className="text-sm text-muted-foreground">{risk.clause_summary}</p>
                <div className="mt-3">
                  <CitationLink documentId={documentId} pageRef={risk.page_ref}>
                    View source clause
                  </CitationLink>
                </div>
              </Card>
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
      // +1: page_ref is 0-indexed internally (matches pages.page_number/PyMuPDF) —
      // shown as the real PDF page number, same convention as CitationLink.tsx.
      String(r.page_ref + 1),
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
      <Button variant="outline" size="sm" onClick={() => setOpen((v) => !v)} icon={<ChevronDownIcon className="h-3.5 w-3.5" />}>
        Export
      </Button>
      {open && (
        <div className="absolute right-0 z-10 mt-1 w-44 overflow-hidden rounded-md border border-border bg-popover shadow-lg">
          <button
            type="button"
            onClick={exportCsv}
            className="block w-full px-4 py-2 text-left text-sm text-foreground hover:bg-surface"
          >
            Export as Excel (CSV)
          </button>
          <button
            type="button"
            onClick={exportPdf}
            className="block w-full px-4 py-2 text-left text-sm text-foreground hover:bg-surface"
          >
            Export as PDF (print)
          </button>
        </div>
      )}
    </div>
  );
}
