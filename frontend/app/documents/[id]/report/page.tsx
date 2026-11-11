"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import EligibilityWarning from "@/components/EligibilityWarning";
import Button from "@/components/ui/Button";
import {
  CriterionStatusBadge,
  DecisionBadge,
  PositiveLevelBadge,
  SEVERITY_STYLES,
  SeverityBadge,
} from "@/components/badges";
import { ApiError, getAllAnalysis, getDocumentStatus } from "@/lib/api";
import {
  FACTOR_WEIGHTS,
  GAUGE_COLOR,
  RECOMMENDATION_LABEL,
  allNextSteps,
  bucketStrategicRelevance,
  buildJustification,
  consortiumPolicyLabel,
  effectiveStatus,
  partnerRequiredLabel,
  pqGateLabel,
} from "@/lib/goNoGo";
import { TQ_FACTOR_WEIGHTS } from "@/lib/tqFactorWeights";
import type {
  DocumentAnalysisResponse,
  DocumentStatusResponse,
  GoNoGoResult,
  ProjectBrief,
  RiskFinderResult,
  SynopsisResult,
} from "@/lib/types";

// A single printable page combining every tab and sub-tab's already-persisted analysis
// (docs/DECISIONS.md) — no new LLM call, purely re-presents document_analysis rows
// already fetched elsewhere in the app. "Download" is the browser's own print-to-PDF
// (window.print(), triggered below), not a server-generated file — zero new
// dependencies, and it reuses this app's real design tokens so it looks like the rest
// of the product rather than a generic printout. Deliberately NOT the interactive tab
// components (GoNoGoCard etc.) — those carry review/resubmit buttons and a portaled
// citation modal that have no meaning on a static, printed page.
//
// Structure mirrors the app's tabs one-to-one (Go/No-Go → Overview / Details /
// Company Checklist A–D; Synopsis → About Project / Checklist / Summary; Risk Finder),
// numbered, with everything a tab hides behind a tooltip or dropdown printed inline —
// it's meant to be shared with people who never open the app.

const MISSING_VALUE_PATTERN = /not (stated|found|available|mentioned|provided)/i;
function isMissingValue(text: string): boolean {
  return MISSING_VALUE_PATTERN.test(text);
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
      <Contents goNoGo={goNoGo} synopsis={synopsis} riskFinder={riskFinder} />
      {goNoGo && <GoNoGoSection result={goNoGo} />}
      {(synopsis || goNoGo) && <SynopsisSection result={synopsis} goNoGo={goNoGo} />}
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
    <div className="mb-8 border-b border-border pb-8">
      <p className="eyebrow mb-2">TENDER AI PLATFORM · ANALYSIS REPORT</p>
      <h1 className="font-display text-3xl font-semibold text-foreground">{title}</h1>
      {authorityKnown && <p className="mt-1 text-sm text-muted-foreground">{synopsis!.issuing_authority}</p>}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        {goNoGo && <DecisionBadge decision={goNoGo.decision} />}
        {goNoGo && (
          <span className="text-sm text-muted-foreground">
            Score <span className="data-mono font-semibold text-foreground">{goNoGo.score}</span>/100
          </span>
        )}
        <span className="text-xs text-muted-foreground">Generated {generatedAt}</span>
      </div>
      <p className="mt-4 text-xs text-muted-foreground">
        Page numbers (p. N) refer to pages of the tender document as analysed, including any
        linked or attached documents appended to it.
      </p>
    </div>
  );
}

function Contents({
  goNoGo,
  synopsis,
  riskFinder,
}: {
  goNoGo?: GoNoGoResult;
  synopsis?: SynopsisResult;
  riskFinder?: RiskFinderResult;
}) {
  const entries: [string, string[]][] = [];
  if (goNoGo) {
    entries.push([
      "1. Go / No-Go",
      [
        "1.1 Overview",
        "1.2 Details",
        "1.3 Company Checklist — A. Pre-Qualification · B. Technical Qualification · C. Bid/No-Bid Decision · D. Partner/OEM Route",
      ],
    ]);
  }
  if (synopsis || goNoGo) {
    entries.push(["2. Synopsis", ["2.1 About Project", "2.2 Checklist", "2.3 Summary"]]);
  }
  if (riskFinder) entries.push(["3. Risk Finder", []]);

  return (
    <nav className="mb-12 break-inside-avoid">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Contents
      </h2>
      <ol className="space-y-2 text-sm">
        {entries.map(([section, subs]) => (
          <li key={section}>
            <span className="font-semibold text-foreground">{section}</span>
            {subs.length > 0 && (
              <ul className="mt-1 space-y-0.5 pl-5 text-muted-foreground">
                {subs.map((sub) => (
                  <li key={sub}>{sub}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-6 border-b-2 border-primary pb-2 font-display text-2xl font-semibold text-foreground">
      {children}
    </h2>
  );
}

// One per app sub-tab.
function TabHeading({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-4 mt-8 font-display text-lg font-semibold text-primary">{children}</h3>;
}

function SubHeading({ children }: { children: React.ReactNode }) {
  return <h4 className="mb-3 text-sm font-semibold text-foreground">{children}</h4>;
}

function Note({ children }: { children: React.ReactNode }) {
  return <p className="mb-6 text-sm text-muted-foreground">{children}</p>;
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
  return <span className="data-mono whitespace-nowrap text-xs text-muted-foreground">p. {pageRef + 1}</span>;
}

function ReportTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: React.ReactNode[][];
}) {
  return (
    <table className="mb-6 w-full border-collapse text-sm">
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

function ReportList({ items, numbered = false }: { items: string[]; numbered?: boolean }) {
  return (
    <ol className="mb-6 space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex gap-2 text-sm text-foreground break-inside-avoid">
          {numbered ? (
            <span className="data-mono flex-none text-muted-foreground">{i + 1}.</span>
          ) : (
            <span className="mt-1.5 h-1 w-1 flex-none rounded-full bg-muted-foreground" />
          )}
          {item}
        </li>
      ))}
    </ol>
  );
}

function ScoreCell({ score }: { score: number | undefined }) {
  if (score === undefined) return <span className="text-muted-foreground">—</span>;
  const tone =
    score >= 70
      ? "bg-status-go/10 text-status-go"
      : score >= 40
        ? "bg-status-conditional/10 text-status-conditional"
        : "bg-status-no-go/10 text-status-no-go";
  return <span className={`data-mono rounded px-1.5 py-0.5 text-xs font-semibold ${tone}`}>{score}</span>;
}

// --- 1. Go / No-Go -----------------------------------------------------------------

function GoNoGoSection({ result }: { result: GoNoGoResult }) {
  const eligibility = result.criteria_matches.filter((m) => m.criterion_type !== "procedural");
  const nextSteps = allNextSteps(result);

  return (
    <section className="mb-12 break-before-page">
      <SectionHeading>1. Go / No-Go</SectionHeading>

      <TabHeading>1.1 Overview</TabHeading>
      <div className="mb-6 flex flex-wrap items-center gap-6 break-inside-avoid">
        <StaticGauge score={result.score} label="Go/No-Go score" colorClass={GAUGE_COLOR[result.decision]} />
        <div>
          <DecisionBadge decision={result.decision} />
          <p className="mt-2 max-w-md text-sm text-muted-foreground">{buildJustification(result)}</p>
        </div>
      </div>

      <div className="mb-6">
        <EligibilityWarning result={result} />
      </div>

      {result.factor_scores && (
        <div>
          <SubHeading>Decision factors</SubHeading>
          <ReportTable
            columns={["Factor", "Weight", "Score", "Why"]}
            rows={Object.entries(FACTOR_WEIGHTS).map(([factor, weight]) => [
              <span key="f" className="whitespace-nowrap">{factor}</span>,
              `${weight}%`,
              <ScoreCell key="s" score={result.factor_scores?.[factor]} />,
              <span key="w" className="text-muted-foreground">
                {result.factor_score_reasons?.[factor] ?? "—"}
              </span>,
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

      <TabHeading>1.2 Details</TabHeading>
      {eligibility.length > 0 ? (
        <div>
          <SubHeading>Eligibility criteria</SubHeading>
          <ReportTable
            columns={["Criterion", "Required", "Company value", "Status", "Page"]}
            rows={eligibility.map((m) => [
              m.criterion,
              <span key="r" className="text-muted-foreground">{m.required}</span>,
              <span key="c" className="text-muted-foreground">{m.company_value}</span>,
              <div key="s">
                <CriterionStatusBadge status={effectiveStatus(m)} />
                {m.human_override && (
                  <span className="mt-1 block text-xs text-muted-foreground">
                    Reviewed by bid team{m.human_override.note ? ` — ${m.human_override.note}` : ""}
                  </span>
                )}
                {m.gate && <span className="mt-1 block text-xs text-severity-high">{m.gate}</span>}
              </div>,
              <PageRef key="p" pageRef={m.page_ref} />,
            ])}
          />
        </div>
      ) : (
        <Note>No eligibility criteria were extracted for this tender.</Note>
      )}

      {nextSteps.length > 0 && (
        <div>
          <SubHeading>Recommended next steps</SubHeading>
          <ReportList items={nextSteps} numbered />
        </div>
      )}

      <TabHeading>1.3 Company Checklist</TabHeading>
      <CompanyChecklistBlock result={result} />
    </section>
  );
}

function CompanyChecklistBlock({ result }: { result: GoNoGoResult }) {
  const policy = result.consortium_policy;
  return (
    <>
      <SubHeading>A. Pre-Qualification</SubHeading>
      {result.pq_checklist && result.pq_checklist.length > 0 ? (
        <ReportTable
          columns={["Category", "Tender requirement", "Company value", "Status", "Page"]}
          rows={result.pq_checklist.map((item) => [
            item.category,
            <span key="t" className="text-muted-foreground">{item.tender_requirement ?? "—"}</span>,
            <span key="c" className="text-muted-foreground">{item.company_value ?? "—"}</span>,
            <CriterionStatusBadge key="s" status={item.status} />,
            <PageRef key="p" pageRef={item.page_ref} />,
          ])}
        />
      ) : (
        <Note>Not available — the PQ checklist call didn&apos;t return a result for this document.</Note>
      )}

      <SubHeading>B. Technical Qualification</SubHeading>
      {result.tq_score !== null && result.tq_factor_scores ? (
        <>
          <div className="mb-4 break-inside-avoid">
            <StaticGauge score={result.tq_score} label="Technical Qualification score" colorClass="stroke-primary" />
          </div>
          <ReportTable
            columns={["Factor", "Weight", "Score"]}
            rows={Object.entries(TQ_FACTOR_WEIGHTS).map(([factor, weight]) => [
              factor,
              `${weight}%`,
              <ScoreCell key="s" score={result.tq_factor_scores?.[factor]} />,
            ])}
          />
        </>
      ) : (
        <Note>Not available — the TQ scoring call didn&apos;t return a result for this document.</Note>
      )}

      <div className="break-inside-avoid">
        <SubHeading>C. Bid/No-Bid Decision</SubHeading>
        <ReportTable
          columns={["Field", "Value"]}
          rows={[
            ["PQ Gate", pqGateLabel(result).label],
            ["Expected TQ Score", result.tq_score ?? "Not available"],
            [
              "Commercial Competitiveness",
              result.commercial_competitiveness ? (
                <PositiveLevelBadge key="s" level={result.commercial_competitiveness} />
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
              "Strategic Relevance",
              <PositiveLevelBadge
                key="s"
                level={bucketStrategicRelevance(result.factor_scores?.["Strategic Relevance"])}
              />,
            ],
            ["Partner Required", partnerRequiredLabel(result)],
            ["Major Qualification Gap", result.major_qualification_gap ?? "Not available"],
            ["Major Technical Gap", result.major_technical_gap ?? "Not available"],
            [
              "Final Recommendation",
              <span key="r" className="font-semibold">{RECOMMENDATION_LABEL[result.decision]}</span>,
            ],
          ]}
        />
      </div>

      <div className="break-inside-avoid">
        <SubHeading>D. Partner/OEM Route</SubHeading>
        <ReportTable
          columns={["Field", "Value"]}
          rows={[
            ["Consortium / JV bids", consortiumPolicyLabel(result)],
            ...(policy?.quote ? [["Tender wording", `“${policy.quote}”`]] : []),
            ["Partner Required", partnerRequiredLabel(result)],
          ]}
        />
        <Note>
          Matching specific partner/OEM companies isn&apos;t assessed yet — it needs partner-company
          capability data this system doesn&apos;t hold.
        </Note>
      </div>
    </>
  );
}

// --- 2. Synopsis -------------------------------------------------------------------

function SynopsisSection({ result, goNoGo }: { result?: SynopsisResult; goNoGo?: GoNoGoResult }) {
  const figures = result ? [...result.key_dates, ...result.financials] : [];
  return (
    <section className="mb-12 break-before-page">
      <SectionHeading>2. Synopsis</SectionHeading>

      <TabHeading>2.1 About Project</TabHeading>
      {result?.project_brief ? (
        <AboutProjectBlock brief={result.project_brief} />
      ) : (
        <Note>The project description isn&apos;t available for this tender yet — Reevaluate it in the app to generate one.</Note>
      )}

      <TabHeading>2.2 Checklist</TabHeading>
      <SynopsisChecklistBlock goNoGo={goNoGo} />

      <TabHeading>2.3 Summary</TabHeading>
      {result ? (
        <>
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
              <SubHeading>Dates &amp; figures</SubHeading>
              <ReportTable
                columns={["Item", "Value", "Page"]}
                rows={figures.map((f) => [f.label, f.value, <PageRef key="p" pageRef={f.page_ref} />])}
              />
            </div>
          )}
        </>
      ) : (
        <Note>The synopsis isn&apos;t available for this tender.</Note>
      )}
    </section>
  );
}

// Same data as SynopsisView's Checklist tab — sourced from the go_no_go analysis.
function SynopsisChecklistBlock({ goNoGo }: { goNoGo?: GoNoGoResult }) {
  if (!goNoGo) {
    return <Note>Not available — the Go/No-Go analysis hasn&apos;t finished processing.</Note>;
  }
  const documentsRequired = goNoGo.documents_required ?? [];
  const procedural = goNoGo.criteria_matches.filter((m) => m.criterion_type === "procedural");
  if (documentsRequired.length === 0 && procedural.length === 0) {
    return <Note>No document submission or bid-preparation items were extracted for this tender.</Note>;
  }
  return (
    <>
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
            columns={["Item", "Required", "Company value", "Page"]}
            rows={procedural.map((m) => [
              m.criterion,
              <span key="r" className="text-muted-foreground">{m.required}</span>,
              <span key="c" className="text-muted-foreground">{m.company_value}</span>,
              <PageRef key="p" pageRef={m.page_ref} />,
            ])}
          />
        </div>
      )}
    </>
  );
}

// Mirrors SynopsisView's "About Project" tab with everything expanded for print. The
// suggested approach/tech stack keep their "AI recommendation" label here too — a
// printed report gets forwarded without the app's context around it.
function AboutProjectBlock({ brief }: { brief: ProjectBrief }) {
  const paragraphs = brief.about_project.split(/\n\s*\n/).filter((p) => p.trim());
  return (
    <div className="mb-8">
      <div className="mb-6 break-inside-avoid">
        <SubHeading>About the project</SubHeading>
        <div className="space-y-2">
          {paragraphs.map((paragraph, i) => (
            <p key={i} className="text-sm leading-relaxed text-foreground">
              {paragraph}
            </p>
          ))}
        </div>
        {brief.about_project_page_refs.length > 0 && (
          <p className="mt-2 text-xs text-muted-foreground">
            Source: {brief.about_project_page_refs.map((p) => `p. ${p + 1}`).join(", ")}
          </p>
        )}
      </div>

      {brief.technical_requirements.length > 0 && (
        <div>
          <SubHeading>Technical requirements (stated in the tender)</SubHeading>
          <ReportTable
            columns={["Category", "Requirement", "Page"]}
            rows={brief.technical_requirements.map((r) => [
              r.category,
              r.requirement,
              <PageRef key="p" pageRef={r.page_ref} />,
            ])}
          />
        </div>
      )}

      {(brief.suggested_approach.length > 0 || brief.suggested_tech_stack.length > 0) && (
        <div>
          <SubHeading>Suggested approach &amp; tech stack</SubHeading>
          <p className="mb-3 text-xs text-severity-medium">
            AI recommendation — not taken from the tender. Review it before relying on it in a
            bid.
          </p>
          {brief.suggested_approach.length > 0 && (
            <ol className="mb-4 space-y-2">
              {brief.suggested_approach.map((step, i) => (
                <li key={i} className="flex gap-2 text-sm break-inside-avoid">
                  <span className="data-mono flex-none text-muted-foreground">{i + 1}.</span>
                  <span>
                    <span className="font-medium text-foreground">{step.phase}</span>
                    <span className="text-muted-foreground"> — {step.description}</span>
                  </span>
                </li>
              ))}
            </ol>
          )}
          {brief.suggested_tech_stack.length > 0 && (
            <ReportTable
              columns={["Area", "Recommendation"]}
              rows={brief.suggested_tech_stack.map((t) => [t.area, t.recommendation])}
            />
          )}
        </div>
      )}

      {brief.source_pages.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Based on {brief.source_pages.length} page{brief.source_pages.length === 1 ? "" : "s"} of the
          tender (pages {brief.source_pages.map((n) => n + 1).join(", ")}).
        </p>
      )}
    </div>
  );
}

// --- 3. Risk Finder ----------------------------------------------------------------

function RiskFinderSection({ result }: { result: RiskFinderResult }) {
  const SEVERITY_RANK: Record<RiskFinderResult["risks"][number]["severity"], number> = {
    HIGH: 0,
    MEDIUM: 1,
    LOW: 2,
  };
  const sortedRisks = [...result.risks].sort(
    (a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity],
  );
  const severityCounts = result.risks.reduce(
    (acc, r) => {
      acc[r.severity] += 1;
      return acc;
    },
    { HIGH: 0, MEDIUM: 0, LOW: 0 } as Record<RiskFinderResult["risks"][number]["severity"], number>,
  );

  return (
    <section className="mb-4 break-before-page">
      <SectionHeading>3. Risk Finder</SectionHeading>
      <div className="mb-6 flex flex-wrap items-center gap-6 break-inside-avoid">
        {/* A count, not a 0-100 score — see RiskList.tsx for why. */}
        <div className="flex flex-none flex-col items-center">
          <span className="data-mono text-3xl font-semibold text-foreground">
            {result.risks.length}
          </span>
          <span className="mt-1 text-xs font-medium text-muted-foreground">
            Risk{result.risks.length === 1 ? "" : "s"} identified
          </span>
        </div>
        <div className="max-w-md">
          {result.risks.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {(["HIGH", "MEDIUM", "LOW"] as const)
                .filter((severity) => severityCounts[severity] > 0)
                .map((severity) => (
                  <span
                    key={severity}
                    className={`inline-flex items-center whitespace-nowrap rounded px-2 py-0.5 text-xs font-semibold ${SEVERITY_STYLES[severity]}`}
                  >
                    {severityCounts[severity]} {severity}
                  </span>
                ))}
            </div>
          )}
          <p className="mt-2 text-sm text-muted-foreground">
            Ranked by severity below.
          </p>
        </div>
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
                {!risk.verified && (
                  <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                    page not re-verified
                  </span>
                )}
              </div>
              <p className="text-sm text-muted-foreground">{risk.clause_summary}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
