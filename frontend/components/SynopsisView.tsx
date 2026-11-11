"use client";

import {
  Banknote,
  Building2,
  CalendarDays,
  ClipboardList,
  Cpu,
  FileCheck,
  FileText,
  Handshake,
  Layers,
  ListTodo,
  Route,
  Sparkles,
  Target,
} from "lucide-react";
import { useState } from "react";
import CitationLink from "./CitationLink";
import Card from "./ui/Card";
import Tabs, { TabIconChip } from "./ui/Tabs";
import { ChevronDownIcon } from "./ui/icons";
import type { GoNoGoResult, ProjectBrief, SynopsisResult } from "@/lib/types";

const SUB_TABS = [
  { id: "project", label: "About Project", icon: <TabIconChip icon={Building2} /> },
  { id: "checklist", label: "Checklist", icon: <TabIconChip icon={ClipboardList} tone="go" /> },
  { id: "summary", label: "Summary", icon: <TabIconChip icon={FileText} /> },
] as const;
type SubTab = (typeof SUB_TABS)[number]["id"];

export default function SynopsisView({
  documentId,
  result,
  goNoGoResult,
}: {
  documentId: string;
  result: SynopsisResult;
  goNoGoResult?: GoNoGoResult | null;
}) {
  const [subTab, setSubTab] = useState<SubTab>("project");
  const [figuresOpen, setFiguresOpen] = useState(false);
  const figureCount = result.key_dates.length + result.financials.length;

  return (
    <div>
      <div className="mb-6">
        <Tabs items={SUB_TABS} active={subTab} onChange={setSubTab} size="sm" />
      </div>

      {subTab === "summary" && (
        <div className="space-y-6">
          <div className="grid gap-4">
            <Section title="Scope of work" icon={Target}>{result.scope_summary}</Section>
            <Section title="Eligibility" icon={Handshake}>{result.eligibility_summary}</Section>
            <Section title="Payment terms" icon={Banknote}>{result.payment_terms_summary}</Section>
          </div>

          {figureCount > 0 && (
            <Card padding="sm" className="p-0">
              <button
                type="button"
                onClick={() => setFiguresOpen((open) => !open)}
                className="flex w-full items-center justify-between px-5 py-4 text-left"
              >
                <span className="text-sm font-semibold text-foreground">
                  Dates &amp; figures{" "}
                  <span className="font-normal text-muted-foreground">({figureCount})</span>
                </span>
                <ChevronDownIcon
                  className={`h-4 w-4 flex-none text-muted-foreground transition-transform ${figuresOpen ? "rotate-180" : ""}`}
                />
              </button>
              {figuresOpen && (
                <div className="grid gap-6 border-t border-border p-5 lg:grid-cols-2">
                  {result.key_dates.length > 0 && (
                    <FactTable
                      title="Key dates"
                      icon={CalendarDays}
                      documentId={documentId}
                      facts={result.key_dates}
                    />
                  )}
                  {result.financials.length > 0 && (
                    <FactTable
                      title="Financials"
                      icon={Banknote}
                      documentId={documentId}
                      facts={result.financials}
                    />
                  )}
                </div>
              )}
            </Card>
          )}
        </div>
      )}

      {subTab === "checklist" && (
        <ChecklistTab documentId={documentId} goNoGoResult={goNoGoResult} />
      )}

      {subTab === "project" && (
        <AboutProjectTab documentId={documentId} brief={result.project_brief ?? null} />
      )}
    </div>
  );
}

function AboutProjectTab({
  documentId,
  brief,
}: {
  documentId: string;
  brief: ProjectBrief | null;
}) {
  const [executionOpen, setExecutionOpen] = useState(false);

  if (!brief) {
    return (
      <Card className="text-sm text-muted-foreground">
        The project description isn&apos;t available for this tender yet. Click Reevaluate
        to generate it.
      </Card>
    );
  }

  const paragraphs = brief.about_project.split(/\n\s*\n/).filter((p) => p.trim());
  const requirementsByCategory = new Map<string, ProjectBrief["technical_requirements"]>();
  for (const item of brief.technical_requirements) {
    const category = item.category.trim() || "Other";
    requirementsByCategory.set(category, [...(requirementsByCategory.get(category) ?? []), item]);
  }

  return (
    <div className="space-y-6">
      <Card padding="sm">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
          <TabIconChip icon={Building2} />
          About the project
        </h3>
        <div className="space-y-3">
          {paragraphs.map((paragraph, i) => (
            <p key={i} className="text-sm leading-relaxed text-foreground">
              {paragraph}
            </p>
          ))}
        </div>
        {brief.about_project_page_refs.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            Source:
            {brief.about_project_page_refs.map((pageRef) => (
              <CitationLink key={pageRef} documentId={documentId} pageRef={pageRef}>
                {null}
              </CitationLink>
            ))}
          </div>
        )}
      </Card>

      <Card padding="sm" className="p-0">
        <button
          type="button"
          onClick={() => setExecutionOpen((open) => !open)}
          aria-expanded={executionOpen}
          className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
        >
          <span className="flex items-center gap-2">
            <TabIconChip icon={Route} />
            <span>
              <span className="block text-sm font-semibold text-foreground">
                How to execute this project
              </span>
              <span className="block text-xs text-muted-foreground">
                Technical requirements from the tender, plus a suggested approach and tech stack
              </span>
            </span>
          </span>
          <ChevronDownIcon
            className={`h-4 w-4 flex-none text-muted-foreground transition-transform ${executionOpen ? "rotate-180" : ""}`}
          />
        </button>

        {executionOpen && (
          <div className="space-y-8 border-t border-border p-5">
            <section>
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                <TabIconChip icon={FileCheck} tone="go" />
                Technical requirements
                <span className="font-normal text-muted-foreground">— stated in the tender</span>
              </h4>
              {requirementsByCategory.size > 0 ? (
                <div className="grid gap-4 lg:grid-cols-2">
                  {[...requirementsByCategory].map(([category, items]) => (
                    <div key={category} className="rounded-lg border border-border p-4">
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        {category}
                      </p>
                      <ul className="space-y-2">
                        {items.map((item, i) => (
                          <li key={i} className="flex items-start gap-3 text-sm text-foreground">
                            <span className="mt-2 h-1.5 w-1.5 flex-none rounded-full bg-primary" />
                            <CitationLink documentId={documentId} pageRef={item.page_ref}>
                              {item.requirement}
                            </CitationLink>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No specific technical requirements were stated in the pages read.
                </p>
              )}
            </section>

            <section>
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                <TabIconChip icon={Sparkles} tone="warning" />
                Suggested approach
              </h4>
              <p className="mb-4 rounded-md bg-severity-medium/10 px-3 py-2 text-xs text-severity-medium">
                AI recommendation — not taken from the tender. Review it before relying on it in
                a bid.
              </p>
              {brief.suggested_approach.length > 0 && (
                <ol className="space-y-3">
                  {brief.suggested_approach.map((step, i) => (
                    <li key={i} className="flex items-start gap-3">
                      <span className="data-mono flex h-6 w-6 flex-none items-center justify-center rounded-full bg-accent text-xs font-semibold text-primary">
                        {i + 1}
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-foreground">{step.phase}</p>
                        <p className="text-sm leading-relaxed text-muted-foreground">
                          {step.description}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              )}

              {brief.suggested_tech_stack.length > 0 && (
                <div className="mt-6">
                  <p className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                    <TabIconChip icon={Cpu} tone="warning" />
                    Suggested tech stack
                  </p>
                  <dl className="grid gap-3 sm:grid-cols-2">
                    {brief.suggested_tech_stack.map((item, i) => (
                      <div key={i} className="rounded-lg border border-border p-3">
                        <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          {item.area}
                        </dt>
                        <dd className="mt-1 text-sm text-foreground">{item.recommendation}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}
            </section>
          </div>
        )}
      </Card>

      {brief.source_pages.length > 0 && (
        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          <Layers className="h-3.5 w-3.5" />
          Based on {brief.source_pages.length} page{brief.source_pages.length === 1 ? "" : "s"} of
          the tender (pages {brief.source_pages.map((n) => n + 1).join(", ")}).
        </p>
      )}
    </div>
  );
}

function ChecklistTab({
  documentId,
  goNoGoResult,
}: {
  documentId: string;
  goNoGoResult?: GoNoGoResult | null;
}) {
  if (!goNoGoResult) {
    return (
      <Card className="text-sm text-muted-foreground">
        Not available yet — the Go/No-Go analysis hasn&apos;t finished processing.
      </Card>
    );
  }

  const procedural = goNoGoResult.criteria_matches.filter(
    (match) => match.criterion_type === "procedural",
  );
  // documents_required was added after some already-analyzed documents were stored,
  // so their persisted result predates the field entirely (undefined, not []).
  const documentsRequired = goNoGoResult.documents_required ?? [];

  return (
    <div className="space-y-8">
      {documentsRequired.length > 0 && (
        <div>
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
            <TabIconChip icon={FileCheck} tone="go" />
            Documents to submit
          </h3>
          <ul className="space-y-2">
            {documentsRequired.map((doc, i) => (
              <li key={i}>
                <Card padding="sm" className="flex items-start gap-3 text-sm text-foreground">
                  <span className="mt-0.5 h-1.5 w-1.5 flex-none rounded-full bg-primary" />
                  <CitationLink documentId={documentId} pageRef={doc.page_ref}>
                    {doc.description}
                  </CitationLink>
                </Card>
              </li>
            ))}
          </ul>
        </div>
      )}

      {procedural.length > 0 && (
        <div>
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
            <TabIconChip icon={ListTodo} />
            Bid preparation checklist
          </h3>
          <Card padding="sm" className="overflow-x-auto p-0">
            <table className="w-full min-w-160 border-collapse text-sm">
              <thead>
                <tr className="border-b border-border bg-surface text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  <th className="px-5 py-3">Item</th>
                  <th className="px-5 py-3">Required</th>
                  <th className="px-5 py-3">Company value</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {procedural.map((match, i) => (
                  <tr key={i} className="hover:bg-surface">
                    <td className="px-5 py-3">
                      <CitationLink documentId={documentId} pageRef={match.page_ref}>
                        {match.criterion}
                      </CitationLink>
                    </td>
                    <td className="px-5 py-3 text-muted-foreground">{match.required}</td>
                    <td className="px-5 py-3 text-muted-foreground">{match.company_value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      )}

      {documentsRequired.length === 0 && procedural.length === 0 && (
        <Card className="text-sm text-muted-foreground">
          No document submission or bid-preparation items were extracted for this tender.
        </Card>
      )}
    </div>
  );
}

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: typeof Target;
  children: string;
}) {
  return (
    <Card padding="sm">
      <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
        <TabIconChip icon={icon} />
        {title}
      </h3>
      <p className="text-sm leading-relaxed text-muted-foreground">{children}</p>
    </Card>
  );
}

function FactTable({
  title,
  icon,
  documentId,
  facts,
}: {
  title: string;
  icon: typeof Target;
  documentId: string;
  facts: SynopsisResult["key_dates"];
}) {
  return (
    <Card padding="sm">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
        <TabIconChip icon={icon} />
        {title}
      </h3>
      <dl className="divide-y divide-border">
        {facts.map((fact, i) => (
          <div key={i} className="py-3 text-sm first:pt-0 last:pb-0">
            <dt className="text-muted-foreground">{fact.label}</dt>
            <dd className="mt-1">
              <CitationLink documentId={documentId} pageRef={fact.page_ref}>
                <span className="data-mono font-medium leading-relaxed text-foreground">
                  {fact.value}
                </span>
              </CitationLink>
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
