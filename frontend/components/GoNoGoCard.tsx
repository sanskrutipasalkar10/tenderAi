import CitationLink from "./CitationLink";
import type { GoNoGoResult } from "@/lib/types";

const DECISION_STYLES: Record<GoNoGoResult["decision"], string> = {
  Go: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300",
  "Conditional-Go": "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  "No-Go": "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
};

export default function GoNoGoCard({
  documentId,
  result,
}: {
  documentId: string;
  result: GoNoGoResult;
}) {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <span
          className={`rounded-full px-4 py-1.5 text-sm font-semibold ${DECISION_STYLES[result.decision]}`}
        >
          {result.decision}
        </span>
        <span className="text-sm text-neutral-500">Score: {result.score}/100</span>
      </div>

      {result.gaps.length > 0 && (
        <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-950">
          <p className="mb-1 font-medium text-amber-900 dark:text-amber-200">
            Missing information — decision could not be fully evaluated
          </p>
          <ul className="list-inside list-disc text-amber-800 dark:text-amber-300">
            {result.gaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </div>
      )}

      {result.criteria_matches.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-neutral-700 dark:text-neutral-300">
            Eligibility criteria
          </h3>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-neutral-200 text-left text-neutral-500 dark:border-neutral-700">
                <th className="py-2 pr-2">Criterion</th>
                <th className="py-2 pr-2">Required</th>
                <th className="py-2 pr-2">Company value</th>
                <th className="py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {result.criteria_matches.map((match, i) => (
                <tr key={i} className="border-b border-neutral-100 dark:border-neutral-800">
                  <td className="py-2 pr-2">
                    <CitationLink documentId={documentId} pageRef={match.page_ref}>
                      {match.criterion}
                    </CitationLink>
                  </td>
                  <td className="py-2 pr-2">{match.required}</td>
                  <td className="py-2 pr-2">{match.company_value}</td>
                  <td className="py-2">
                    <span
                      className={
                        match.status === "pass"
                          ? "text-green-700 dark:text-green-400"
                          : "text-red-700 dark:text-red-400"
                      }
                    >
                      {match.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {result.next_steps.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-neutral-700 dark:text-neutral-300">
            Next steps
          </h3>
          <ul className="list-inside list-disc space-y-1 text-sm text-neutral-700 dark:text-neutral-300">
            {result.next_steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
