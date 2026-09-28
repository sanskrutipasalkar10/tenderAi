"use client";

import { useState } from "react";
import { ApiError, resubmitGoNoGo, reviewGoNoGo } from "@/lib/api";
import type { GoNoGoResult } from "@/lib/types";
import CitationLink from "./CitationLink";
import ScoreGauge from "./ScoreGauge";
import { CriterionStatusBadge, DecisionBadge } from "./badges";

const GAUGE_COLOR: Record<GoNoGoResult["decision"], string> = {
  Go: "stroke-status-go",
  "Go (Management Review)": "stroke-status-go",
  "Conditional-Go (Partner Required)": "stroke-status-conditional",
  "No-Go": "stroke-status-no-go",
};

// backend/app/pipeline/reduce_pass.py's BID_DECISION_FACTOR_WEIGHTS — kept in sync
// manually since the weights are hardcoded Python constants, not served by the API.
const FACTOR_WEIGHTS: Record<string, number> = {
  "PQ Eligibility": 30,
  "Similar Experience": 20,
  "Technical Capability": 15,
  "Government/PSU Experience": 10,
  "Key Manpower": 10,
  "Financial Capability": 5,
  "Strategic Relevance": 5,
  "Partner/OEM Availability": 5,
};

// A short, specific "why" — names the actual triggered gates rather than a generic
// canned sentence, so "why is this No-Go" has a real answer at a glance.
function buildJustification(result: GoNoGoResult): string {
  if (result.gaps.length > 0) {
    return `Blocked by: ${result.gaps.join("; ")}.`;
  }
  switch (result.decision) {
    case "Go":
      return "All eligibility criteria are met and no hard-fail gates were triggered.";
    case "Go (Management Review)":
      return `Strong weighted score (${result.score}/100), no hard-fail gates — recommend a quick management sign-off before committing.`;
    case "Conditional-Go (Partner Required)":
      return `Weighted score of ${result.score}/100 falls in the conditional band — a partner or consortium route may be needed before committing.`;
    default:
      return `Weighted score of ${result.score}/100 is too low to proceed.`;
  }
}

const SUB_TABS = [
  { id: "overview", label: "Overview" },
  { id: "details", label: "Details" },
] as const;
type SubTab = (typeof SUB_TABS)[number]["id"];

export default function GoNoGoCard({
  documentId,
  result: initialResult,
}: {
  documentId: string;
  result: GoNoGoResult;
}) {
  const [result, setResult] = useState(initialResult);
  const [subTab, setSubTab] = useState<SubTab>("overview");
  const [resubmitting, setResubmitting] = useState(false);
  const [resubmitError, setResubmitError] = useState<string | null>(null);

  const eligibility = result.criteria_matches
    .map((match, i) => ({ match, i }))
    .filter(({ match }) => match.criterion_type !== "procedural");

  // Resubmitting re-asks the model for fresh factor_scores grounded in whatever's
  // been reviewed so far — pointless to offer before anything has actually been
  // reviewed, and impossible for a short-circuited analysis (no factor_scores at all,
  // e.g. Conditional-Go from an incomplete company profile — nothing to rescore).
  const hasReview = result.criteria_matches.some((match) => match.human_override !== null);
  const canResubmit = result.factor_scores !== null;

  async function handleReview(criterionIndex: number, status: "pass" | "fail", note: string) {
    const updated = await reviewGoNoGo(documentId, [
      { criterion_index: criterionIndex, status, note: note.trim() || null },
    ]);
    setResult(updated.result);
  }

  async function handleResubmit() {
    setResubmitting(true);
    setResubmitError(null);
    try {
      const updated = await resubmitGoNoGo(documentId);
      setResult(updated.result);
    } catch (err) {
      setResubmitError(err instanceof ApiError ? err.message : "Could not resubmit analysis");
    } finally {
      setResubmitting(false);
    }
  }

  return (
    <div>
      <div className="mb-6 flex gap-1 border-b border-slate-200">
        {SUB_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setSubTab(tab.id)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              subTab === tab.id
                ? "border-accent text-accent"
                : "border-transparent text-slate-500 hover:text-ink-900"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {subTab === "overview" && (
        <div className="space-y-8">
          <div className="flex flex-col items-center gap-6 rounded-md border border-slate-200 bg-white p-8 sm:flex-row sm:items-center sm:justify-center sm:gap-10">
            <ScoreGauge score={result.score} label="Go/No-Go score" colorClass={GAUGE_COLOR[result.decision]} />
            <div className="flex flex-col items-center gap-2 sm:items-start">
              <DecisionBadge decision={result.decision} />
              <p className="max-w-md text-center text-sm text-slate-500 sm:text-left">
                {buildJustification(result)}
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

          {canResubmit && (
            <div className="flex flex-col items-start gap-3 rounded-md border border-slate-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-slate-500">
                {hasReview
                  ? "The score above still reflects the model's original judgment. Resubmit to re-score it against the criteria you've reviewed."
                  : "Review at least one criterion in the Details tab before resubmitting — resubmitting re-scores against reviewed criteria only."}
              </p>
              <button
                type="button"
                disabled={!hasReview || resubmitting}
                onClick={handleResubmit}
                className="flex-none rounded bg-ink-900 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                {resubmitting ? "Resubmitting…" : "Resubmit analysis"}
              </button>
            </div>
          )}
          {resubmitError && (
            <p className="text-sm text-severity-high">{resubmitError}</p>
          )}
        </div>
      )}

      {subTab === "details" && (
        <div className="space-y-8">
          {result.factor_scores && (
            <div>
              <h3 className="mb-3 text-sm font-semibold text-ink-900">Factor breakdown</h3>
              <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
                <table className="w-full min-w-100 border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                      <th className="px-5 py-3">Factor</th>
                      <th className="px-5 py-3">Weight</th>
                      <th className="px-5 py-3">Score</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {Object.entries(FACTOR_WEIGHTS).map(([factor, weight]) => (
                      <tr key={factor} className="hover:bg-slate-50">
                        <td className="px-5 py-3">{factor}</td>
                        <td className="px-5 py-3 text-slate-600">{weight}%</td>
                        <td className="px-5 py-3 text-slate-600">
                          {result.factor_scores?.[factor] ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {eligibility.length > 0 && (
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
                    {eligibility.map(({ match, i }) => (
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
                          {match.gate && (
                            <span className="mt-1 block text-xs text-severity-high">{match.gate}</span>
                          )}
                          <CriterionReview
                            criterionIndex={i}
                            match={match}
                            onReview={(status, note) => handleReview(i, status, note)}
                          />
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
      )}
    </div>
  );
}

function CriterionReview({
  match,
  onReview,
}: {
  criterionIndex: number;
  match: GoNoGoResult["criteria_matches"][number];
  onReview: (status: "pass" | "fail", note: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (match.human_override) {
    return (
      <div className="mt-1 text-xs text-slate-500">
        Reviewed: marked <span className="font-semibold">{match.human_override.status}</span>
        {match.human_override.note && <> — {match.human_override.note}</>}
      </div>
    );
  }

  if (match.status !== "fail" && match.status !== "insufficient_data") return null;

  async function submit(status: "pass" | "fail") {
    setSubmitting(true);
    try {
      await onReview(status, note);
      setOpen(false);
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-1 text-xs font-medium text-accent hover:underline"
      >
        Review
      </button>
    );
  }

  return (
    <div className="mt-2 space-y-2 rounded border border-slate-200 bg-slate-50 p-2">
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Evidence / note (optional)"
        rows={2}
        className="w-full rounded border border-slate-300 px-2 py-1 text-xs text-ink-900 focus:border-accent focus:outline-none"
      />
      <div className="flex gap-2">
        <button
          type="button"
          disabled={submitting}
          onClick={() => submit("pass")}
          className="rounded bg-status-go px-2 py-1 text-xs font-semibold text-white disabled:opacity-50"
        >
          Mark eligible
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={() => submit("fail")}
          className="rounded bg-status-no-go px-2 py-1 text-xs font-semibold text-white disabled:opacity-50"
        >
          Mark not eligible
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={() => setOpen(false)}
          className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-600"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
