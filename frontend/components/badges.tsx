import type {
  DocumentStatus,
  GoNoGoResult,
  PQChecklistStatus,
  RiskFinderRisk,
} from "@/lib/types";

const DECISION_STYLES: Record<GoNoGoResult["decision"], string> = {
  Go: "bg-status-go/10 text-status-go ring-1 ring-status-go/30",
  "Go (Management Review)": "bg-status-go/10 text-status-go ring-1 ring-status-go/20",
  "Conditional-Go (Partner Required)":
    "bg-status-conditional/10 text-status-conditional ring-1 ring-status-conditional/30",
  "No-Go": "bg-status-no-go/10 text-status-no-go ring-1 ring-status-no-go/30",
};

export function DecisionBadge({ decision }: { decision: GoNoGoResult["decision"] }) {
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ${DECISION_STYLES[decision]}`}
    >
      {decision}
    </span>
  );
}

const SEVERITY_STYLES: Record<RiskFinderRisk["severity"], string> = {
  HIGH: "bg-severity-high/10 text-severity-high ring-1 ring-severity-high/30",
  MEDIUM: "bg-severity-medium/10 text-severity-medium ring-1 ring-severity-medium/30",
  LOW: "bg-severity-low/10 text-severity-low ring-1 ring-severity-low/30",
};

export function SeverityBadge({ severity }: { severity: RiskFinderRisk["severity"] }) {
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded px-2 py-0.5 text-xs font-semibold ${SEVERITY_STYLES[severity]}`}
    >
      {severity}
    </span>
  );
}

const CRITERION_STYLES: Record<PQChecklistStatus, string> = {
  pass: "bg-status-go/10 text-status-go ring-1 ring-status-go/30",
  fail: "bg-status-no-go/10 text-status-no-go ring-1 ring-status-no-go/30",
  insufficient_data:
    "bg-status-conditional/10 text-status-conditional ring-1 ring-status-conditional/30",
  not_applicable: "bg-slate-100 text-slate-500 ring-1 ring-slate-200",
};

const CRITERION_LABEL: Record<PQChecklistStatus, string> = {
  pass: "pass",
  fail: "fail",
  insufficient_data: "needs review",
  not_applicable: "not applicable",
};

export function CriterionStatusBadge({ status }: { status: PQChecklistStatus }) {
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${CRITERION_STYLES[status]}`}
    >
      {CRITERION_LABEL[status]}
    </span>
  );
}

const STATUS_LABEL: Record<DocumentStatus, string> = {
  uploaded: "Uploaded",
  classifying: "Processing",
  extracting: "Processing",
  extracted: "Processing",
  analyzing: "Analyzing",
  ready: "Ready",
  failed: "Failed",
};

const STATUS_STYLES: Record<DocumentStatus, string> = {
  uploaded: "bg-slate-100 text-slate-600",
  classifying: "bg-accent/10 text-accent",
  extracting: "bg-accent/10 text-accent",
  extracted: "bg-accent/10 text-accent",
  analyzing: "bg-accent/10 text-accent",
  ready: "bg-status-go/10 text-status-go",
  failed: "bg-status-no-go/10 text-status-no-go",
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {(status === "classifying" || status === "extracting" || status === "extracted" || status === "analyzing") && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
      )}
      {STATUS_LABEL[status]}
    </span>
  );
}
