import CitationLink from "./CitationLink";
import type { SynopsisResult } from "@/lib/types";

const CONFIDENCE_STYLES: Record<SynopsisResult["confidence"], string> = {
  high: "text-green-700 dark:text-green-400",
  medium: "text-amber-700 dark:text-amber-400",
  low: "text-red-700 dark:text-red-400",
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
      <div>
        <h2 className="text-xl font-semibold">{result.title}</h2>
        <p className="text-sm text-neutral-500">{result.issuing_authority}</p>
        <p className={`mt-1 text-xs font-medium ${CONFIDENCE_STYLES[result.confidence]}`}>
          Confidence: {result.confidence}
        </p>
      </div>

      <Section title="Scope">{result.scope_summary}</Section>
      <Section title="Eligibility">{result.eligibility_summary}</Section>
      <Section title="Payment terms">{result.payment_terms_summary}</Section>

      {result.key_dates.length > 0 && (
        <FactTable title="Key dates" documentId={documentId} facts={result.key_dates} />
      )}
      {result.financials.length > 0 && (
        <FactTable title="Financials" documentId={documentId} facts={result.financials} />
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: string }) {
  return (
    <div>
      <h3 className="mb-1 text-sm font-semibold text-neutral-700 dark:text-neutral-300">
        {title}
      </h3>
      <p className="text-sm text-neutral-600 dark:text-neutral-400">{children}</p>
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
    <div>
      <h3 className="mb-2 text-sm font-semibold text-neutral-700 dark:text-neutral-300">
        {title}
      </h3>
      <table className="w-full border-collapse text-sm">
        <tbody>
          {facts.map((fact, i) => (
            <tr key={i} className="border-b border-neutral-100 dark:border-neutral-800">
              <td className="py-2 pr-4 text-neutral-500">{fact.label}</td>
              <td className="py-2">
                <CitationLink documentId={documentId} pageRef={fact.page_ref}>
                  {fact.value}
                </CitationLink>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
