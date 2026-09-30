"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import { CriterionStatusBadge, DecisionBadge, SeverityBadge } from "@/components/badges";
import { ApiError, getAllAnalysis, getDocumentStatus } from "@/lib/api";
import { TQ_FACTOR_WEIGHTS } from "@/lib/tqFactorWeights";
import type {
  DocumentAnalysisResponse,
  DocumentStatusResponse,
  GoNoGoResult,
  RiskFinderResult,
  SynopsisResult,
} from "@/lib/types";

// A single printable page combining every tab/sub-tab's already-persisted analysis
// (docs/DECISIONS.md) — no new LLM call, purely re-presents document_analysis rows
// already fetched elsewhere in the app. "Download" is the browser's own print-to-PDF
// (window.print(), triggered below), not a server-generated file — zero new
// dependencies, and it reuses this app's real design tokens so it looks like the rest
// of the product rather than a generic printout. Deliberately NOT the interactive tab
// components (GoNoGoCard etc.) — those carry review/resubmit buttons and a portaled
// citation modal that have no meaning on a static, printed page.

// backend/app/pipeline/reduce_pass.py's BID_DECISION_FACTOR_WEIGHTS — mirrored here
// the same way GoNoGoCard.tsx already does, since the weights are hardcoded Python
// constants, not served by the API.
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

const GAUGE_COLOR: Record<GoNoGoResult["decision"], string> = {
  Go: "stroke-status-go",
  "Go (Management Review)": "stroke-status-go",
  "Conditional-Go (Partner Required)": "stroke-status-conditional",
  "No-Go": "stroke-status-no-go",
};

function riskGaugeColor(riskScore: number): string {
  if (riskScore >= 70) return "stroke-severity-high";
  if (riskScore >= 40) return "stroke-severity-medium";
  return "stroke-severity-low";
}

const MISSING_VALUE_PATTERN = /not (stated|found|available|mentioned|provided)/i;
function isMissingValue(text: string): boolean {
  return MISSING_VALUE_PATTERN.test(text);
}

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

export default function DocumentReportPage(props: PageProps<"/documents/[id]/report">) {
  const { id: documentId } = use(props.params);
  return <ReportContent documentId={documentId} />;
}

function ReportContent({ documentId }: { documentId: string }) {
  const [status, setStatus] = useState<DocumentStatusResponse | null>(null);
  const [analyses, setAnalyses] = useState<DocumentAnalysisResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await getDocumentStatus(documentId);
        if (cancelled) return;
        setStatus(s);
        if (s.status === "ready") {
          const a = await getAllAnalysis(documentId);
          if (!cancelled) setAnalyses(a);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load this report");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  if (error) {
    return (
      <ReportShell documentId={documentId}>
        <p className="text-sm text-severity-high">{error}</p>
      </ReportShell>
    );
  }

  if (!status) {
    return (
      <ReportShell documentId={documentId}>
        <p className="text-sm text-muted-foreground">Loading…</p>
      </ReportShell>
    );
  }

  if (status.status !== "ready" || !analyses) {
    return (
      <ReportShell documentId={documentId}>
        <p className="text-sm text-muted-foreground">
          This tender&apos;s analysis isn&apos;t finished yet — the report becomes available once
          processing reaches &quot;Ready.&quot;
        </p>
      </ReportShell>
    );
  }

  const goNoGo = analyses.find((a) => a.module === "go_no_go")?.result as GoNoGoResult | undefined;
  const synopsis = analyses.find((a) => a.module === "synopsis")?.result as
    | SynopsisResult
    | undefined;
  const riskFinder = analyses.find((a) => a.module === "risk_finder")?.result as
    | RiskFinderResult
    | undefined;
  const generatedAt = new Date().toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });

  return (
    <ReportShell documentId={documentId}>
      <Cover synopsis={synopsis} goNoGo={goNoGo} generatedAt={generatedAt} />
      {goNoGo && <GoNoGoSection result={goNoGo} />}
      {synopsis && <SynopsisSection result={synopsis} />}
      {goNoGo && <CompanyChecklistSection result={goNoGo} />}
      {riskFinder && <RiskFinderSection result={riskFinder} />}
    </ReportShell>
  );
}

function ReportShell({
  documentId,
  children,
}: {
  documentId: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background">
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-surface px-6 py-4 print:hidden">
        <Link
          href={`/documents/${documentId}`}
          className="text-sm font-medium text-muted-foreground hover:text-primary"
        >
          ← Back to analysis
        </Link>
        <Button size="sm" onClick={() => window.print()}>
          Download PDF
        </Button>
      </div>
      <div className="mx-auto max-w-3xl px-8 py-10 print:max-w-none print:px-12 print:py-0">
        {children}
      </div>
    </div>
  );
}

function Cover({
  synopsis,
  goNoGo,
  generatedAt,
}: {
  synopsis?: SynopsisResult;
  goNoGo?: GoNoGoResult;
  generatedAt: string;
}) {
  const title = synopsis && !isMissingValue(synopsis.title) ? synopsis.title : "Tender Analysis Report";
  const authorityKnown = synopsis && !isMissingValue(synopsis.issuing_authority);

  return (
    <div className="mb-10 border-b border-border pb-8">
      <p className="eyebrow mb-2">TENDER AI PLATFORM · ANALYSIS REPORT</p>
      <h1 className="font-display text-3xl font-semibold text-foreground">{title}</h1>
      {authorityKnown && <p className="mt-1 text-sm text-muted-foreground">{synopsis!.issuing_authority}</p>}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        {goNoGo && <DecisionBadge decision={goNoGo.decision} />}
        <span className="text-xs text-muted-foreground">Generated {generatedAt}</span>
      </div>
    </div>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-5 font-display text-xl font-semibold text-foreground">{children}</h2>
  );
}

function SubHeading({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-3 text-sm font-semibold text-foreground">{children}</h3>;
}

/** Non-animated stand-in for ScoreGauge (components/ScoreGauge.tsx) — that one drives
 * its arc/number with framer-motion, which is unnecessary risk on a page whose whole
 * point is to be captured as a static PDF (a mid-animation frame or a print triggered
 * before motion settles). Same visual output at rest, no animation. */
function StaticGauge({ score, label, colorClass }: { score: number; label: string; colorClass: string }) {
  const SIZE = 120;
  const STROKE = 9;
  const RADIUS = (SIZE - STROKE) / 2;
  const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
  const clamped = Math.max(0, Math.min(100, score));
  const offset = CIRCUMFERENCE - (clamped / 100) * CIRCUMFERENCE;

  return (
    <div className="inline-flex flex-none flex-col items-center">
      <div className="relative" style={{ width: SIZE, height: SIZE }}>
        <svg width={SIZE} height={SIZE} className="-rotate-90">
          <circle cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} strokeWidth={STROKE} fill="none" className="stroke-border" />
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            strokeWidth={STROKE}
            fill="none"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className={colorClass}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="data-mono text-2xl font-semibold text-foreground">{clamped}</span>
          <span className="text-[10px] text-muted-foreground">/ 100</span>
        </div>
      </div>
      <span className="mt-2 text-xs font-medium text-muted-foreground">{label}</span>
    </div>
  );
}

// pageRef is 0-indexed internally (matches pages.page_number/PyMuPDF) — +1 to show
// the real PDF page number, same convention as CitationLink.tsx.
function PageRef({ pageRef }: { pageRef: number | null }) {
  if (pageRef === null) return <span className="text-muted-foreground">—</span>;
  return <span className="data-mono text-xs text-muted-foreground">p. {pageRef + 1}</span>;
}

function ReportTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: React.ReactNode[][];
}) {
  return (
    <table className="mb-6 w-full border-collapse text-sm break-inside-avoid">
      <thead>
        <tr className="border-b border-border text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {columns.map((c) => (
            <th key={c} className="py-2 pr-4">
              {c}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {rows.map((row, i) => (
          <tr key={i} className="break-inside-avoid">
            {row.map((cell, j) => (
              <td key={j} className="py-2 pr-4 align-top text-foreground">
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ReportList({ items }: { items: string[] }) {
  return (
    <ul className="mb-6 space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex gap-2 text-sm text-foreground">
          <span className="mt-1.5 h-1 w-1 flex-none rounded-full bg-muted-foreground" />
          {item}
        </li>
      ))}
    </ul>
  );
}

function GoNoGoSection({ result }: { result: GoNoGoResult }) {
  const eligibility = result.criteria_matches.filter((m) => m.criterion_type !== "procedural");

  return (
    <section className="mb-12">
      <SectionHeading>Go / No-Go</SectionHeading>
      <div className="mb-6 flex flex-wrap items-center gap-6 break-inside-avoid">
        <StaticGauge score={result.score} label="Go/No-Go score" colorClass={GAUGE_COLOR[result.decision]} />
        <div>
          <DecisionBadge decision={result.decision} />
          <p className="mt-2 max-w-md text-sm text-muted-foreground">{buildJustification(result)}</p>
        </div>
      </div>

      {result.factor_scores && (
        <div>
          <SubHeading>Decision factors</SubHeading>
          <ReportTable
            columns={["Factor", "Weight", "Score"]}
            rows={Object.entries(FACTOR_WEIGHTS).map(([factor, weight]) => [
              factor,
              `${weight}%`,
              String(result.factor_scores?.[factor] ?? "—"),
            ])}
          />
        </div>
      )}

      {eligibility.length > 0 && (
        <div>
          <SubHeading>Eligibility criteria</SubHeading>
          <ReportTable
            columns={["Criterion", "Required", "Company value", "Status", "Page"]}
            rows={eligibility.map((m) => [
              m.criterion,
              m.required,
              m.company_value,
              <CriterionStatusBadge key="s" status={m.status} />,
              <PageRef key="p" pageRef={m.page_ref} />,
            ])}
          />
        </div>
      )}

      {result.gaps.length > 0 && (
        <div>
          <SubHeading>Gaps &amp; blockers</SubHeading>
          <ReportList items={result.gaps} />
        </div>
      )}

      {result.next_steps.length > 0 && (
        <div>
          <SubHeading>Recommended next steps</SubHeading>
          <ReportList items={result.next_steps} />
        </div>
      )}
    </section>
  );
}

function SynopsisSection({ result }: { result: SynopsisResult }) {
  const figures = [...result.key_dates, ...result.financials];
  return (
    <section className="mb-12 break-before-page">
      <SectionHeading>Synopsis</SectionHeading>

      <div className="mb-6 grid gap-4">
        <div className="break-inside-avoid">
          <SubHeading>Scope of work</SubHeading>
          <p className="text-sm leading-relaxed text-muted-foreground">{result.scope_summary}</p>
        </div>
        <div className="break-inside-avoid">
          <SubHeading>Eligibility</SubHeading>
          <p className="text-sm leading-relaxed text-muted-foreground">{result.eligibility_summary}</p>
        </div>
        <div className="break-inside-avoid">
          <SubHeading>Payment terms</SubHeading>
          <p className="text-sm leading-relaxed text-muted-foreground">{result.payment_terms_summary}</p>
        </div>
      </div>

      {figures.length > 0 && (
        <div>
          <SubHeading>Key dates &amp; figures</SubHeading>
          <ReportTable
            columns={["Item", "Value", "Page"]}
            rows={figures.map((f) => [f.label, f.value, <PageRef key="p" pageRef={f.page_ref} />])}
          />
        </div>
      )}
    </section>
  );
}

function CompanyChecklistSection({ result }: { result: GoNoGoResult }) {
  const documentsRequired = result.documents_required ?? [];
  const procedural = result.criteria_matches.filter((m) => m.criterion_type === "procedural");

  return (
    <section className="mb-12 break-before-page">
      <SectionHeading>Company Checklist</SectionHeading>

      {result.pq_checklist && result.pq_checklist.length > 0 && (
        <div>
          <SubHeading>A. Pre-Qualification</SubHeading>
          <ReportTable
            columns={["Category", "Tender requirement", "Company value", "Status"]}
            rows={result.pq_checklist.map((item) => [
              item.category,
              item.tender_requirement ?? "—",
              item.company_value ?? "—",
              <CriterionStatusBadge key="s" status={item.status} />,
            ])}
          />
        </div>
      )}

      {result.tq_score !== null && result.tq_factor_scores && (
        <div>
          <SubHeading>B. Technical Qualification</SubHeading>
          <div className="mb-4 break-inside-avoid">
            <StaticGauge score={result.tq_score} label="Technical Qualification score" colorClass="stroke-primary" />
          </div>
          <ReportTable
            columns={["Factor", "Weight", "Score"]}
            rows={Object.entries(TQ_FACTOR_WEIGHTS).map(([factor, weight]) => [
              factor,
              `${weight}%`,
              String(result.tq_factor_scores?.[factor] ?? "—"),
            ])}
          />
        </div>
      )}

      <div className="break-inside-avoid">
        <SubHeading>C. Bid/No-Bid Decision</SubHeading>
        <ReportTable
          columns={["Field", "Value"]}
          rows={[
            ["PQ Gate", result.gaps.length === 0 ? "PASS" : "FAIL"],
            ["Expected TQ Score", result.tq_score ?? "Not available"],
            [
              "Commercial Competitiveness",
              result.commercial_competitiveness ? (
                <SeverityBadge key="s" severity={result.commercial_competitiveness} />
              ) : (
                "Not available"
              ),
            ],
            [
              "Bid Preparation Effort",
              result.bid_preparation_effort ? (
                <SeverityBadge key="s" severity={result.bid_preparation_effort} />
              ) : (
                "Not available"
              ),
            ],
            [
              "Partner Required",
              result.decision === "Conditional-Go (Partner Required)" ? "YES" : "NO",
            ],
            ["Major Qualification Gap", result.major_qualification_gap ?? "Not available"],
            ["Major Technical Gap", result.major_technical_gap ?? "Not available"],
          ]}
        />
      </div>

      {documentsRequired.length > 0 && (
        <div>
          <SubHeading>Documents to submit</SubHeading>
          <ReportTable
            columns={["Document", "Page"]}
            rows={documentsRequired.map((d) => [d.description, <PageRef key="p" pageRef={d.page_ref} />])}
          />
        </div>
      )}

      {procedural.length > 0 && (
        <div>
          <SubHeading>Bid preparation checklist</SubHeading>
          <ReportTable
            columns={["Item", "Required", "Company value"]}
            rows={procedural.map((m) => [m.criterion, m.required, m.company_value])}
          />
        </div>
      )}
    </section>
  );
}

function RiskFinderSection({ result }: { result: RiskFinderResult }) {
  const SEVERITY_RANK: Record<RiskFinderResult["risks"][number]["severity"], number> = {
    HIGH: 0,
    MEDIUM: 1,
    LOW: 2,
  };
  const sortedRisks = [...result.risks].sort(
    (a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity],
  );

  return (
    <section className="mb-4 break-before-page">
      <SectionHeading>Risk Finder</SectionHeading>
      <div className="mb-6 flex flex-wrap items-center gap-6 break-inside-avoid">
        <StaticGauge
          score={result.risk_score}
          label="Overall risk score"
          colorClass={riskGaugeColor(result.risk_score)}
        />
        <p className="max-w-md text-sm text-muted-foreground">
          {result.risks.length} risk{result.risks.length === 1 ? "" : "s"} identified, ranked by
          severity below.
        </p>
      </div>

      {sortedRisks.length === 0 ? (
        <p className="text-sm text-muted-foreground">No risks flagged for this document.</p>
      ) : (
        <div className="space-y-4">
          {sortedRisks.map((risk, i) => (
            <div key={i} className="break-inside-avoid border-b border-border pb-4 last:border-0">
              <div className="mb-1.5 flex flex-wrap items-center gap-2">
                <SeverityBadge severity={risk.severity} />
                <span className="text-sm font-semibold text-foreground">{risk.category}</span>
                <PageRef pageRef={risk.page_ref} />
              </div>
              <p className="text-sm text-muted-foreground">{risk.clause_summary}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
