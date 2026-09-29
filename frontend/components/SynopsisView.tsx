"use client";

import { useState } from "react";
import CitationLink from "./CitationLink";
import Card from "./ui/Card";
import Tabs from "./ui/Tabs";
import { ChevronDownIcon } from "./ui/icons";
import type { GoNoGoResult, SynopsisResult } from "@/lib/types";

const CONFIDENCE_STYLES: Record<SynopsisResult["confidence"], string> = {
  high: "bg-status-go/10 text-status-go",
  medium: "bg-status-conditional/10 text-status-conditional",
  low: "bg-status-no-go/10 text-status-no-go",
};

// The model sometimes returns a literal "not found" sentence instead of leaving the
// field empty — rendering that verbatim as a bold H2 title looked like a broken real
// title rather than an honest "we don't know" state, so it's detected and downgraded.
const MISSING_VALUE_PATTERN = /not (stated|found|available|mentioned|provided)/i;
function isMissingValue(text: string): boolean {
  return MISSING_VALUE_PATTERN.test(text);
}

const SUB_TABS = [
  { id: "summary", label: "Summary" },
  { id: "checklist", label: "Checklist" },
] as const;
type SubTab = (typeof SUB_TABS)[number]["id"];

export default function SynopsisView({
  documentId,
  result,
  goNoGoResult,
}: {
  documentId: string;
  result: SynopsisResult;
  goNoGoResult?: GoNoGoResult | null;
}) {
  const [subTab, setSubTab] = useState<SubTab>("summary");
  const [figuresOpen, setFiguresOpen] = useState(false);
  const titleMissing = isMissingValue(result.title);
  const authorityMissing = isMissingValue(result.issuing_authority);
  const figureCount = result.key_dates.length + result.financials.length;

  return (
    <div>
      <div className="mb-6">
        <Tabs items={SUB_TABS} active={subTab} onChange={setSubTab} size="sm" />
      </div>

      {subTab === "summary" && (
        <div className="space-y-6">
          <Card>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                {titleMissing ? (
                  <p className="text-base italic text-slate-400">
                    Title not found in the extracted document text
                  </p>
                ) : (
                  <h2 className="text-xl font-semibold text-ink-900">{result.title}</h2>
                )}
                {!authorityMissing && (
                  <p className="mt-1 text-sm text-slate-500">{result.issuing_authority}</p>
                )}
              </div>
              <span
                className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${CONFIDENCE_STYLES[result.confidence]}`}
              >
                {result.confidence} confidence
              </span>
            </div>
          </Card>

          <div className="grid gap-4">
            <Section title="Scope of work">{result.scope_summary}</Section>
            <Section title="Eligibility">{result.eligibility_summary}</Section>
            <Section title="Payment terms">{result.payment_terms_summary}</Section>
          </div>

          {figureCount > 0 && (
            <Card padding="sm" className="p-0">
              <button
                type="button"
                onClick={() => setFiguresOpen((open) => !open)}
                className="flex w-full items-center justify-between px-5 py-4 text-left"
              >
                <span className="text-sm font-semibold text-ink-900">
                  Dates &amp; figures{" "}
                  <span className="font-normal text-slate-400">({figureCount})</span>
                </span>
                <ChevronDownIcon
                  className={`h-4 w-4 flex-none text-slate-400 transition-transform ${figuresOpen ? "rotate-180" : ""}`}
                />
              </button>
              {figuresOpen && (
                <div className="grid gap-6 border-t border-slate-100 p-5 lg:grid-cols-2">
                  {result.key_dates.length > 0 && (
                    <FactTable title="Key dates" documentId={documentId} facts={result.key_dates} />
                  )}
                  {result.financials.length > 0 && (
                    <FactTable
                      title="Financials"
                      documentId={documentId}
                      facts={result.financials}
                    />
                  )}
                </div>
              )}
            </Card>
          )}
        </div>
      )}

      {subTab === "checklist" && (
        <ChecklistTab documentId={documentId} goNoGoResult={goNoGoResult} />
      )}
    </div>
  );
}

function ChecklistTab({
  documentId,
  goNoGoResult,
}: {
  documentId: string;
  goNoGoResult?: GoNoGoResult | null;
}) {
  if (!goNoGoResult) {
    return (
      <Card className="text-sm text-slate-500">
        Not available yet — the Go/No-Go analysis hasn&apos;t finished processing.
      </Card>
    );
  }

  const procedural = goNoGoResult.criteria_matches.filter(
    (match) => match.criterion_type === "procedural",
  );
  // documents_required was added after some already-analyzed documents were stored,
  // so their persisted result predates the field entirely (undefined, not []).
  const documentsRequired = goNoGoResult.documents_required ?? [];

  return (
    <div className="space-y-8">
      {documentsRequired.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-ink-900">Documents to submit</h3>
          <ul className="space-y-2">
            {documentsRequired.map((doc, i) => (
              <li key={i}>
                <Card padding="sm" className="flex items-start gap-3 text-sm text-ink-900">
                  <span className="mt-0.5 h-1.5 w-1.5 flex-none rounded-full bg-accent" />
                  <CitationLink documentId={documentId} pageRef={doc.page_ref}>
                    {doc.description}
                  </CitationLink>
                </Card>
              </li>
            ))}
          </ul>
        </div>
      )}

      {procedural.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-ink-900">Bid preparation checklist</h3>
          <Card padding="sm" className="overflow-x-auto p-0">
            <table className="w-full min-w-160 border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th className="px-5 py-3">Item</th>
                  <th className="px-5 py-3">Required</th>
                  <th className="px-5 py-3">Company value</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {procedural.map((match, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="px-5 py-3">
                      <CitationLink documentId={documentId} pageRef={match.page_ref}>
                        {match.criterion}
                      </CitationLink>
                    </td>
                    <td className="px-5 py-3 text-slate-600">{match.required}</td>
                    <td className="px-5 py-3 text-slate-600">{match.company_value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      )}

      {documentsRequired.length === 0 && procedural.length === 0 && (
        <Card className="text-sm text-slate-500">
          No document submission or bid-preparation items were extracted for this tender.
        </Card>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: string }) {
  return (
    <Card padding="sm">
      <h3 className="mb-2 text-sm font-semibold text-ink-900">{title}</h3>
      <p className="text-sm leading-relaxed text-slate-600">{children}</p>
    </Card>
  );
}

function FactTable({
  title,
  documentId,
  facts,
}: {
  title: string;
  documentId: string;
  facts: SynopsisResult["key_dates"];
}) {
  return (
    <Card padding="sm">
      <h3 className="mb-3 text-sm font-semibold text-ink-900">{title}</h3>
      <dl className="divide-y divide-slate-100">
        {facts.map((fact, i) => (
          <div key={i} className="py-3 text-sm first:pt-0 last:pb-0">
            <dt className="text-slate-500">{fact.label}</dt>
            <dd className="mt-1">
              <CitationLink documentId={documentId} pageRef={fact.page_ref}>
                <span className="data-mono font-medium leading-relaxed text-ink-900">
                  {fact.value}
                </span>
              </CitationLink>
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
