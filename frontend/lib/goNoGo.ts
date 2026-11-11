// Go/No-Go presentation logic shared by the interactive tabs (GoNoGoCard,
// CompanyChecklistView) and the printable report, so the two can never disagree about
// what a result means. Pure functions over an already-fetched GoNoGoResult — no API
// call, and it recomputes from human overrides, so it stays right after a review.
import type { GoNoGoCriterionMatch, GoNoGoResult } from "@/lib/types";

// backend/app/pipeline/reduce_pass.py's BID_DECISION_FACTOR_WEIGHTS — kept in sync
// manually since the weights are hardcoded Python constants, not served by the API.
export const FACTOR_WEIGHTS: Record<string, number> = {
  "PQ Eligibility": 30,
  "Similar Experience": 20,
  "Technical Capability": 15,
  "Government/PSU Experience": 10,
  "Key Manpower": 10,
  "Financial Capability": 5,
  "Strategic Relevance": 5,
  "Partner/OEM Availability": 5,
};

export const GAUGE_COLOR: Record<GoNoGoResult["decision"], string> = {
  Go: "stroke-status-go",
  "Go (Management Review)": "stroke-status-go",
  "Conditional-Go (Partner Required)": "stroke-status-conditional",
  "No-Go": "stroke-status-no-go",
};

export const RECOMMENDATION_LABEL: Record<GoNoGoResult["decision"], string> = {
  Go: "BID",
  "Go (Management Review)": "BID (Management Review)",
  "Conditional-Go (Partner Required)": "BID WITH PARTNER",
  "No-Go": "NO-BID",
};

// A short, specific "why" — names the actual triggered gates rather than a generic
// canned sentence, so "why is this No-Go" has a real answer at a glance.
export function buildJustification(result: GoNoGoResult): string {
  if (result.gaps.length > 0) {
    return `Blocked by: ${result.gaps.join("; ")}.`;
  }
  if (result.decision_cap_reason) return result.decision_cap_reason;
  // Stored before the decision cap existed: never let a Go headline sit beside a
  // "bid would be rejected" warning without saying the two disagree.
  if (
    (result.decision === "Go" || result.decision === "Go (Management Review)") &&
    eligibilityIssues(result).failing.length > 0
  ) {
    return `Weighted score of ${result.score}/100, but a failed eligibility criterion means the bid can't go ahead alone — Reevaluate to update this decision.`;
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

export function bucketStrategicRelevance(score: number | undefined): "LOW" | "MEDIUM" | "HIGH" {
  if (score === undefined) return "LOW";
  if (score >= 70) return "HIGH";
  if (score >= 40) return "MEDIUM";
  return "LOW";
}

// A human review always wins over the model's original status.
export function effectiveStatus(match: GoNoGoCriterionMatch): GoNoGoCriterionMatch["status"] {
  return match.human_override ? match.human_override.status : match.status;
}

// Tenders state that a bid not meeting the minimum eligibility criteria is rejected —
// so a failed eligibility criterion is a blocker for bidding alone, whatever the
// weighted score says (the score deliberately doesn't gate on experience criteria,
// docs/DECISIONS.md). insufficient_data is "confirm before bidding", not a blocker.
export function eligibilityIssues(result: GoNoGoResult): {
  failing: GoNoGoCriterionMatch[];
  needsData: GoNoGoCriterionMatch[];
} {
  const eligibility = result.criteria_matches.filter((m) => m.criterion_type !== "procedural");
  return {
    failing: eligibility.filter((m) => effectiveStatus(m) === "fail"),
    needsData: eligibility.filter((m) => effectiveStatus(m) === "insufficient_data"),
  };
}

function pageLabel(pageRef: number | null): string {
  return pageRef === null ? "" : ` (p. ${pageRef + 1})`;
}

// Next steps the model can't know to write: covering a failed criterion depends on
// the tender's consortium policy, which is detected in code, not by the model.
export function partnerNextSteps(result: GoNoGoResult): string[] {
  const { failing } = eligibilityIssues(result);
  if (failing.length === 0) return [];
  const policy = result.consortium_policy?.status;
  if (policy === "not_allowed") return [];
  return failing.map((m) =>
    policy === "allowed"
      ? `Find a consortium/JV partner that meets: ${m.criterion}${pageLabel(m.page_ref)}`
      : policy === "not_stated"
        ? `Ask the buyer whether a consortium/JV bid is allowed — needed to cover: ${m.criterion}${pageLabel(m.page_ref)}`
        : `Check whether the tender allows a consortium/JV bid — needed to cover: ${m.criterion}${pageLabel(m.page_ref)}`,
  );
}

export function allNextSteps(result: GoNoGoResult): string[] {
  return [...partnerNextSteps(result), ...result.next_steps];
}

export function partnerRequiredLabel(result: GoNoGoResult): string {
  const { failing } = eligibilityIssues(result);
  if (failing.length === 0) {
    return result.decision === "Conditional-Go (Partner Required)" ? "YES" : "NO";
  }
  const policy = result.consortium_policy;
  if (policy?.status === "allowed") return `YES — consortium/JV allowed${pageLabel(policy.page_ref)}`;
  if (policy?.status === "not_allowed") {
    return `Needed, but consortium/JV is not allowed${pageLabel(policy.page_ref)}`;
  }
  if (policy?.status === "not_stated") {
    return "YES — but the tender doesn't say whether consortium/JV bids are allowed";
  }
  return "YES — consortium/JV policy not checked yet (Reevaluate)";
}

// The PQ gate fails whenever an eligibility criterion fails — not only when one of the
// named hard-fail gates fired — since the tender rejects such a bid as it stands.
export function pqGateLabel(result: GoNoGoResult): { pass: boolean; label: string } {
  if (result.gaps.length > 0) return { pass: false, label: "FAIL" };
  if (eligibilityIssues(result).failing.length === 0) return { pass: true, label: "PASS" };
  const policy = result.consortium_policy?.status;
  if (policy === "allowed") return { pass: false, label: "FAIL — can be covered by a consortium/JV partner" };
  if (policy === "not_allowed") return { pass: false, label: "FAIL — consortium/JV not allowed" };
  return { pass: false, label: "FAIL — confirm with the buyer whether a consortium/JV can cover it" };
}

export function consortiumPolicyLabel(result: GoNoGoResult): string {
  const policy = result.consortium_policy;
  if (!policy) return "Not checked for this analysis — Reevaluate to check.";
  if (policy.status === "allowed") return `Allowed${pageLabel(policy.page_ref)}`;
  if (policy.status === "not_allowed") return `Not allowed${pageLabel(policy.page_ref)}`;
  return "Not stated in the tender";
}
