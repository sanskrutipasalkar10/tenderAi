"use client";

import { AlertTriangle, CircleHelp } from "lucide-react";
import { eligibilityIssues } from "@/lib/goNoGo";
import type { GoNoGoCriterionMatch, GoNoGoResult } from "@/lib/types";
import CitationLink from "./CitationLink";

// Says plainly what the weighted score can't: a failed eligibility criterion gets a bid
// rejected, and whether a partner can fix that depends on the tender's consortium
// policy. Shared by GoNoGoCard's Overview and the printable report — with no
// `documentId` (the report), page refs render as plain text instead of links.
export default function EligibilityWarning({
  result,
  documentId,
}: {
  result: GoNoGoResult;
  documentId?: string;
}) {
  const { failing, needsData } = eligibilityIssues(result);
  if (failing.length === 0 && needsData.length === 0) return null;

  const page = (pageRef: number | null) =>
    pageRef === null ? null : documentId ? (
      <CitationLink documentId={documentId} pageRef={pageRef}>
        {null}
      </CitationLink>
    ) : (
      <span className="data-mono text-xs text-muted-foreground">p. {pageRef + 1}</span>
    );

  const policy = result.consortium_policy;
  const plural = failing.length === 1 ? "it" : "them";

  return (
    <div className="space-y-3">
      {failing.length > 0 && (
        <div className="break-inside-avoid rounded-lg border border-severity-high/30 bg-severity-high/5 p-4">
          <p className="flex items-center gap-2 text-sm font-semibold text-severity-high">
            <AlertTriangle className="h-4 w-4 flex-none" />
            Fails {failing.length} eligibility criteri{failing.length === 1 ? "on" : "a"} — the bid
            would be rejected as it stands
          </p>
          <CriteriaList items={failing} page={page} />
          <p className="mt-3 text-sm text-foreground">
            {policy?.status === "allowed" ? (
              <>
                <span className="font-semibold text-status-go">Consortium/JV bids are allowed</span>{" "}
                {page(policy.page_ref)}
                {policy.quote && <span className="text-muted-foreground"> — “{policy.quote}”</span>}
                <span className="mt-1 block">
                  Bid with a consortium/JV partner that meets {plural}.
                </span>
              </>
            ) : policy?.status === "not_allowed" ? (
              <>
                <span className="font-semibold text-severity-high">
                  Consortium/JV bids are not allowed
                </span>{" "}
                {page(policy.page_ref)}
                {policy.quote && <span className="text-muted-foreground"> — “{policy.quote}”</span>}
                <span className="mt-1 block">
                  A partner can&apos;t cover {plural} — the company must meet {plural} on its own.
                </span>
              </>
            ) : policy ? (
              <span className="text-muted-foreground">
                The tender doesn&apos;t clearly say whether consortium/JV bids are allowed —
                confirm with the buyer before relying on a partner.
              </span>
            ) : (
              <span className="text-muted-foreground">
                Whether the tender allows consortium/JV bids wasn&apos;t checked for this analysis
                — Reevaluate to check.
              </span>
            )}
          </p>
        </div>
      )}

      {needsData.length > 0 && (
        <div className="break-inside-avoid rounded-lg border border-status-conditional/30 bg-status-conditional/5 p-4">
          <p className="flex items-center gap-2 text-sm font-semibold text-status-conditional">
            <CircleHelp className="h-4 w-4 flex-none" />
            Confirm before bidding — {needsData.length} criteri
            {needsData.length === 1 ? "on needs" : "a need"} data the company profile doesn&apos;t have
          </p>
          <CriteriaList items={needsData} page={page} showValue />
        </div>
      )}
    </div>
  );
}

function CriteriaList({
  items,
  page,
  showValue = false,
}: {
  items: GoNoGoCriterionMatch[];
  page: (pageRef: number | null) => React.ReactNode;
  showValue?: boolean;
}) {
  return (
    <ul className="mt-2 space-y-1.5">
      {items.map((m, i) => (
        <li key={i} className="flex items-start gap-2 text-sm text-foreground">
          <span className="mt-2 h-1.5 w-1.5 flex-none rounded-full bg-current opacity-60" />
          <span>
            {m.criterion} {page(m.page_ref)}
            {showValue && <span className="block text-xs text-muted-foreground">{m.company_value}</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}
