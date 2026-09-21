import CitationLink from "./CitationLink";
import type { SynopsisResult } from "@/lib/types";

const CONFIDENCE_STYLES: Record<SynopsisResult["confidence"], string> = {
  high: "bg-status-go/10 text-status-go",
  medium: "bg-status-conditional/10 text-status-conditional",
  low: "bg-status-no-go/10 text-status-no-go",
};

export default function SynopsisView({
  documentId,
  result,
}: {
  documentId: string;
  result: SynopsisResult;
}) {
  return (
    <div className="space-y-6">
      <div className="rounded-md border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-ink-900">{result.title}</h2>
            <p className="mt-1 text-sm text-slate-500">{result.issuing_authority}</p>
          </div>
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${CONFIDENCE_STYLES[result.confidence]}`}
          >
            {result.confidence} confidence
          </span>
        </div>
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        {result.key_dates.length > 0 && (
          <FactTable title="Key dates" documentId={documentId} facts={result.key_dates} />
        )}
        {result.financials.length > 0 && (
          <FactTable title="Financials" documentId={documentId} facts={result.financials} />
        )}
      </div>

      <div className="grid gap-4">
        <Section title="Scope of work">{result.scope_summary}</Section>
        <Section title="Eligibility">{result.eligibility_summary}</Section>
        <Section title="Payment terms">{result.payment_terms_summary}</Section>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-5">
      <h3 className="mb-2 text-sm font-semibold text-ink-900">{title}</h3>
      <p className="text-sm leading-relaxed text-slate-600">{children}</p>
    </div>
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
    <div className="rounded-md border border-slate-200 bg-white p-5">
      <h3 className="mb-3 text-sm font-semibold text-ink-900">{title}</h3>
      <dl className="space-y-3">
        {facts.map((fact, i) => (
          <div key={i} className="flex flex-col gap-1 text-sm sm:flex-row sm:items-center sm:justify-between sm:gap-4">
            <dt className="text-slate-500">{fact.label}</dt>
            <dd>
              <CitationLink documentId={documentId} pageRef={fact.page_ref}>
                <span className="data-mono font-medium text-ink-900">{fact.value}</span>
              </CitationLink>
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
