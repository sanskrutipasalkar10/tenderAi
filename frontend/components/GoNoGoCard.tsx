"use client";

import { useState } from "react";
import { reviewGoNoGo } from "@/lib/api";
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

const DECISION_EXPLANATION: Record<GoNoGoResult["decision"], string> = {
  Go: "All eligibility criteria are met and no hard-fail gates were triggered.",
  "Go (Management Review)":
    "Strong weighted score with no hard-fail gates — recommend a quick management sign-off before committing.",
  "Conditional-Go (Partner Required)":
    "Eligible with open gaps — a partner or consortium route may be needed before committing.",
  "No-Go": "A hard-fail gate was triggered, or the weighted score is too low to proceed.",
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

export default function GoNoGoCard({
  documentId,
  result: initialResult,
}: {
  documentId: string;
  result: GoNoGoResult;
}) {
  const [result, setResult] = useState(initialResult);

  const eligibility = result.criteria_matches
    .map((match, i) => ({ match, i }))
    .filter(({ match }) => match.criterion_type !== "procedural");
  const procedural = result.criteria_matches
    .map((match, i) => ({ match, i }))
    .filter(({ match }) => match.criterion_type === "procedural");

  async function handleReview(criterionIndex: number, status: "pass" | "fail", note: string) {
    const updated = await reviewGoNoGo(documentId, [
      { criterion_index: criterionIndex, status, note: note.trim() || null },
    ]);
    setResult(updated.result);
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col items-center gap-6 rounded-md border border-slate-200 bg-white p-8 sm:flex-row sm:items-center sm:justify-center sm:gap-10">
        <ScoreGauge score={result.score} label="Go/No-Go score" colorClass={GAUGE_COLOR[result.decision]} />
        <div className="flex flex-col items-center gap-2 sm:items-start">
          <DecisionBadge decision={result.decision} />
          <p className="max-w-xs text-center text-sm text-slate-500 sm:text-left">
            {DECISION_EXPLANATION[result.decision]}
          </p>
        </div>
      </div>

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

      {procedural.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-ink-900">Bid preparation checklist</h3>
          <p className="mb-3 text-xs text-slate-500">
            Submission mechanics — signatures, formats, translations. These don&apos;t
            affect eligibility scoring, they&apos;re just things the bid package needs.
          </p>
          <ul className="space-y-2">
            {procedural.map(({ match, i }) => (
              <li
                key={i}
                className="flex items-start gap-3 rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-ink-900"
              >
                <span className="mt-0.5 h-1.5 w-1.5 flex-none rounded-full bg-slate-300" />
                <CitationLink documentId={documentId} pageRef={match.page_ref}>
                  {match.criterion}
                </CitationLink>
              </li>
            ))}
          </ul>
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
