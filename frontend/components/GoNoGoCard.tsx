import CitationLink from "./CitationLink";
import ScoreGauge from "./ScoreGauge";
import { CriterionStatusBadge, DecisionBadge } from "./badges";
import type { GoNoGoResult } from "@/lib/types";

const GAUGE_COLOR: Record<GoNoGoResult["decision"], string> = {
  Go: "stroke-status-go",
  "Conditional-Go": "stroke-status-conditional",
  "No-Go": "stroke-status-no-go",
};

export default function GoNoGoCard({
  documentId,
  result,
}: {
  documentId: string;
  result: GoNoGoResult;
}) {
  return (
    <div className="space-y-8">
      <div className="flex flex-col items-center gap-6 rounded-md border border-slate-200 bg-white p-8 sm:flex-row sm:items-center sm:justify-center sm:gap-10">
        <ScoreGauge score={result.score} label="Go/No-Go score" colorClass={GAUGE_COLOR[result.decision]} />
        <div className="flex flex-col items-center gap-2 sm:items-start">
          <DecisionBadge decision={result.decision} />
          <p className="max-w-xs text-center text-sm text-slate-500 sm:text-left">
            {result.decision === "Go" &&
              "All eligibility criteria are met and no blocking gaps were found."}
            {result.decision === "Conditional-Go" &&
              "Eligible with open gaps — review before committing."}
            {result.decision === "No-Go" &&
              "One or more blocking criteria were not met."}
          </p>
        </div>
      </div>

      {result.gaps.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-ink-900">Gaps &amp; blockers</h3>
          <ul className="space-y-2">
            {result.gaps.map((gap) => (
              <li
                key={gap}
                className="flex items-start gap-3 rounded-md border border-severity-high/30 bg-severity-high/5 px-4 py-3 text-sm text-ink-900"
              >
                <span className="mt-0.5 h-1.5 w-1.5 flex-none rounded-full bg-severity-high" />
                {gap}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.criteria_matches.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-ink-900">Eligibility criteria</h3>
          <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
            <table className="w-full min-w-160 border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th className="px-5 py-3">Criterion</th>
                  <th className="px-5 py-3">Required</th>
                  <th className="px-5 py-3">Company value</th>
                  <th className="px-5 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {result.criteria_matches.map((match, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="px-5 py-3">
                      <CitationLink documentId={documentId} pageRef={match.page_ref}>
                        {match.criterion}
                      </CitationLink>
                    </td>
                    <td className="px-5 py-3 text-slate-600">{match.required}</td>
                    <td className="px-5 py-3 text-slate-600">{match.company_value}</td>
                    <td className="px-5 py-3">
                      <CriterionStatusBadge status={match.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {result.next_steps.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-ink-900">Recommended next steps</h3>
          <ul className="space-y-2">
            {result.next_steps.map((step, i) => (
              <li
                key={step}
                className="flex items-start gap-3 rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-ink-900"
              >
                <span className="data-mono mt-0.5 flex h-5 w-5 flex-none items-center justify-center rounded border border-slate-300 text-[11px] text-slate-400">
                  {i + 1}
                </span>
                {step}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
