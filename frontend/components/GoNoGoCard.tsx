"use client";

import {
  AlertTriangle,
  Banknote,
  ClipboardCheck,
  Handshake,
  History,
  Landmark,
  LayoutDashboard,
  ListChecks,
  ListTodo,
  ShieldCheck,
  Target,
  Users,
  Wrench,
} from "lucide-react";
import { useState } from "react";
import { ApiError, resubmitGoNoGo, reviewGoNoGo } from "@/lib/api";
import type { GoNoGoResult } from "@/lib/types";
import CitationLink from "./CitationLink";
import ScoreGauge from "./ScoreGauge";
import { CriterionStatusBadge, DecisionBadge } from "./badges";
import Button from "./ui/Button";
import Card from "./ui/Card";
import Tabs, { TabIconChip } from "./ui/Tabs";

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

const FACTOR_ICON: Record<string, typeof ShieldCheck> = {
  "PQ Eligibility": ShieldCheck,
  "Similar Experience": History,
  "Technical Capability": Wrench,
  "Government/PSU Experience": Landmark,
  "Key Manpower": Users,
  "Financial Capability": Banknote,
  "Strategic Relevance": Target,
  "Partner/OEM Availability": Handshake,
};

// A factor's bar is colored by its own score, not the card's brand color — a weak
// factor should visually read as weak at a glance, same status-color language as the
// Go/No-Go decision badge itself.
function scoreBarColor(score: number): string {
  if (score >= 70) return "bg-status-go";
  if (score >= 40) return "bg-status-conditional";
  return "bg-status-no-go";
}

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
  { id: "overview", label: "Overview", icon: <TabIconChip icon={LayoutDashboard} /> },
  { id: "details", label: "Details", icon: <TabIconChip icon={ListChecks} /> },
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
      <div className="mb-6">
        <Tabs items={SUB_TABS} active={subTab} onChange={setSubTab} size="sm" />
      </div>

      {subTab === "overview" && (
        <div className="space-y-6">
          <Card padding="lg">
            <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-center sm:justify-center sm:gap-10">
              <ScoreGauge score={result.score} label="Go/No-Go score" colorClass={GAUGE_COLOR[result.decision]} />
              <div className="flex flex-col items-center gap-2 sm:items-start">
                <DecisionBadge decision={result.decision} />
                <p className="max-w-md text-center text-sm text-muted-foreground sm:text-left">
                  {buildJustification(result)}
                </p>
              </div>
            </div>
          </Card>

          {result.factor_scores && (
            <Card>
              <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-foreground">
                <TabIconChip icon={Target} />
                Decision factors
              </h3>
              <div className="space-y-2">
                {Object.entries(FACTOR_WEIGHTS).map(([factor, weight]) => {
                  const score = Math.max(0, Math.min(100, result.factor_scores?.[factor] ?? 0));
                  return (
                    <div
                      key={factor}
                      className="flex items-center gap-3 rounded-md border border-border bg-surface px-3 py-2.5"
                    >
                      <TabIconChip icon={FACTOR_ICON[factor]} />
                      <span className="w-40 flex-none truncate text-xs font-medium text-foreground">
                        {factor}
                      </span>
                      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
                        <div
                          className={`h-full rounded-full ${scoreBarColor(score)}`}
                          style={{ width: `${score}%` }}
                        />
                      </div>
                      <span className="data-mono w-20 flex-none whitespace-nowrap text-right text-xs font-semibold text-foreground">
                        {score}
                        <span className="font-normal text-muted-foreground"> · {weight}%</span>
                      </span>
                    </div>
                  );
                })}
              </div>
            </Card>
          )}

          {result.gaps.length > 0 && (
            <div>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                <TabIconChip icon={AlertTriangle} tone="danger" />
                Gaps &amp; blockers
              </h3>
              <ul className="space-y-2">
                {result.gaps.map((gap) => (
                  <li key={gap}>
                    <Card tone="danger" padding="sm" className="flex items-start gap-3 text-sm text-foreground">
                      <span className="mt-0.5 h-1.5 w-1.5 flex-none rounded-full bg-severity-high" />
                      {gap}
                    </Card>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {canResubmit && (
            <Card className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-muted-foreground">
                {hasReview
                  ? "The score above still reflects the model's original judgment. Resubmit to re-score it against the criteria you've reviewed."
                  : "Review at least one criterion in the Details tab before resubmitting — resubmitting re-scores against reviewed criteria only."}
              </p>
              <Button
                variant="dark"
                size="xs"
                disabled={!hasReview}
                loading={resubmitting}
                onClick={handleResubmit}
                className="flex-none"
              >
                Resubmit analysis
              </Button>
            </Card>
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
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                <TabIconChip icon={Target} />
                Factor breakdown
              </h3>
              <Card padding="sm" className="overflow-x-auto p-0">
                <table className="w-full min-w-100 border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-border bg-surface text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      <th className="px-5 py-3">Factor</th>
                      <th className="px-5 py-3">Weight</th>
                      <th className="px-5 py-3">Score</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {Object.entries(FACTOR_WEIGHTS).map(([factor, weight]) => {
                      const score = result.factor_scores?.[factor];
                      return (
                        <tr key={factor} className="hover:bg-surface">
                          <td className="px-5 py-3">
                            <span className="inline-flex items-center gap-2">
                              <TabIconChip icon={FACTOR_ICON[factor]} />
                              {factor}
                            </span>
                          </td>
                          <td className="px-5 py-3 text-muted-foreground">{weight}%</td>
                          <td className="px-5 py-3">
                            {score === undefined ? (
                              <span className="text-muted-foreground">—</span>
                            ) : (
                              <span
                                className={`data-mono inline-flex items-center rounded px-1.5 py-0.5 text-xs font-semibold ${
                                  score >= 70
                                    ? "bg-status-go/10 text-status-go"
                                    : score >= 40
                                      ? "bg-status-conditional/10 text-status-conditional"
                                      : "bg-status-no-go/10 text-status-no-go"
                                }`}
                              >
                                {score}
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </Card>
            </div>
          )}

          {eligibility.length > 0 && (
            <div>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                <TabIconChip icon={ClipboardCheck} tone="go" />
                Eligibility criteria
              </h3>
              <Card padding="sm" className="overflow-x-auto p-0">
                <table className="w-full min-w-160 border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-border bg-surface text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      <th className="px-5 py-3">Criterion</th>
                      <th className="px-5 py-3">Required</th>
                      <th className="px-5 py-3">Company value</th>
                      <th className="px-5 py-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {eligibility.map(({ match, i }) => (
                      <tr key={i} className="hover:bg-surface">
                        <td className="px-5 py-3">
                          <CitationLink documentId={documentId} pageRef={match.page_ref}>
                            {match.criterion}
                          </CitationLink>
                        </td>
                        <td className="px-5 py-3 text-muted-foreground">{match.required}</td>
                        <td className="px-5 py-3 text-muted-foreground">{match.company_value}</td>
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
              </Card>
            </div>
          )}

          {result.next_steps.length > 0 && (
            <div>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                <TabIconChip icon={ListTodo} />
                Recommended next steps
              </h3>
              <ul className="space-y-2">
                {result.next_steps.map((step, i) => (
                  <li key={step}>
                    <Card padding="sm" className="flex items-start gap-3 text-sm text-foreground">
                      <span className="data-mono mt-0.5 flex h-5 w-5 flex-none items-center justify-center rounded border border-input text-[11px] text-muted-foreground">
                        {i + 1}
                      </span>
                      {step}
                    </Card>
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
      <div className="mt-1 text-xs text-muted-foreground">
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
      <Button variant="ghost" size="xs" className="mt-1 px-0! text-primary" onClick={() => setOpen(true)}>
        Review
      </Button>
    );
  }

  return (
    <div className="mt-2 space-y-2 rounded border border-border bg-surface p-2">
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Evidence / note (optional)"
        rows={2}
        className="w-full rounded border border-input px-2 py-1 text-xs text-foreground focus:border-primary focus:outline-none"
      />
      <div className="flex gap-2">
        <Button variant="success" size="xs" disabled={submitting} onClick={() => submit("pass")}>
          Mark eligible
        </Button>
        <Button variant="destructive" size="xs" disabled={submitting} onClick={() => submit("fail")}>
          Mark not eligible
        </Button>
        <Button variant="outline" size="xs" disabled={submitting} onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
