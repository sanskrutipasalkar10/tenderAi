import CitationLink from "./CitationLink";
import type { RiskFinderResult } from "@/lib/types";

const SEVERITY_STYLES: Record<RiskFinderResult["risks"][number]["severity"], string> = {
  HIGH: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  MEDIUM: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  LOW: "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300",
};

export default function RiskList({
  documentId,
  result,
}: {
  documentId: string;
  result: RiskFinderResult;
}) {
  if (result.risks.length === 0) {
    return <p className="text-neutral-500">No risks flagged for this document.</p>;
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-neutral-500">Risk score: {result.risk_score}/100</p>
      <ul className="space-y-3">
        {result.risks.map((risk, i) => (
          <li
            key={i}
            className="rounded border border-neutral-200 p-4 dark:border-neutral-700"
          >
            <div className="mb-2 flex items-center gap-2">
              <span
                className={`rounded px-2 py-0.5 text-xs font-semibold ${SEVERITY_STYLES[risk.severity]}`}
              >
                {risk.severity}
              </span>
              <span className="text-sm font-medium">{risk.category}</span>
              {!risk.verified && (
                <span
                  className="rounded bg-neutral-200 px-2 py-0.5 text-xs text-neutral-600 dark:bg-neutral-700 dark:text-neutral-300"
                  title="This citation's page could not be re-verified against the source document — shown, not hidden (docs/SPEC.md §7)"
                >
                  unverified
                </span>
              )}
            </div>
            <p className="text-sm text-neutral-700 dark:text-neutral-300">
              <CitationLink documentId={documentId} pageRef={risk.page_ref}>
                {risk.clause_summary}
              </CitationLink>
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
