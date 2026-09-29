"use client";

import { useState } from "react";
import type { GoNoGoResult } from "@/lib/types";
import CitationLink from "./CitationLink";
import ScoreGauge from "./ScoreGauge";
import { CriterionStatusBadge, SeverityBadge } from "./badges";
import Card from "./ui/Card";
import Tabs from "./ui/Tabs";
import { TQ_FACTOR_WEIGHTS } from "@/lib/tqFactorWeights";

const SUB_TABS = [
  { id: "pq", label: "A. Pre-Qualification" },
  { id: "tq", label: "B. Technical Qualification" },
  { id: "decision", label: "C. Bid/No-Bid Decision" },
  { id: "partner", label: "D. Partner/OEM Route" },
] as const;
type SubTab = (typeof SUB_TABS)[number]["id"];

const RECOMMENDATION_LABEL: Record<GoNoGoResult["decision"], string> = {
  Go: "BID",
  "Go (Management Review)": "BID (Management Review)",
  "Conditional-Go (Partner Required)": "BID WITH PARTNER",
  "No-Go": "NO-BID",
};

function bucketStrategicRelevance(score: number | undefined): "LOW" | "MEDIUM" | "HIGH" {
  if (score === undefined) return "LOW";
  if (score >= 70) return "HIGH";
  if (score >= 40) return "MEDIUM";
  return "LOW";
}

export default function CompanyChecklistView({
  documentId,
  goNoGoResult,
}: {
  documentId: string;
  goNoGoResult: GoNoGoResult;
}) {
  const [subTab, setSubTab] = useState<SubTab>("pq");

  return (
    <div>
      <div className="mb-6">
        <Tabs items={SUB_TABS} active={subTab} onChange={setSubTab} size="sm" />
      </div>

      {subTab === "pq" && <PQChecklistTab documentId={documentId} goNoGoResult={goNoGoResult} />}
      {subTab === "tq" && <TQScoringTab goNoGoResult={goNoGoResult} />}
      {subTab === "decision" && <BidDecisionTab goNoGoResult={goNoGoResult} />}
      {subTab === "partner" && <PartnerPlaceholderTab />}
    </div>
  );
}

function PQChecklistTab({
  documentId,
  goNoGoResult,
}: {
  documentId: string;
  goNoGoResult: GoNoGoResult;
}) {
  if (!goNoGoResult.pq_checklist || goNoGoResult.pq_checklist.length === 0) {
    return (
      <Card className="text-sm text-muted-foreground">
        Not available — the PQ checklist call didn&apos;t return a result for this document.
      </Card>
    );
  }

  return (
    <Card padding="sm" className="overflow-x-auto p-0">
      <table className="w-full min-w-180 border-collapse text-sm">
        <thead>
          <tr className="border-b border-border bg-surface text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <th className="px-5 py-3">Category</th>
            <th className="px-5 py-3">Tender requirement</th>
            <th className="px-5 py-3">Company value</th>
            <th className="px-5 py-3">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {goNoGoResult.pq_checklist.map((item, i) => (
            <tr key={i} className="hover:bg-surface">
              <td className="px-5 py-3">{item.category}</td>
              <td className="px-5 py-3 text-muted-foreground">
                {item.page_ref !== null ? (
                  <CitationLink documentId={documentId} pageRef={item.page_ref}>
                    {item.tender_requirement ?? "—"}
                  </CitationLink>
                ) : (
                  item.tender_requirement ?? "—"
                )}
              </td>
              <td className="px-5 py-3 text-muted-foreground">{item.company_value ?? "—"}</td>
              <td className="px-5 py-3">
                <CriterionStatusBadge status={item.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function TQScoringTab({ goNoGoResult }: { goNoGoResult: GoNoGoResult }) {
  if (goNoGoResult.tq_score === null || !goNoGoResult.tq_factor_scores) {
    return (
      <Card className="text-sm text-muted-foreground">
        Not available — the TQ scoring call didn&apos;t return a result for this document.
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card padding="lg">
        <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-center sm:justify-center sm:gap-10">
          <ScoreGauge score={goNoGoResult.tq_score} label="Technical Qualification score" colorClass="stroke-primary" />
        </div>
      </Card>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-foreground">Factor breakdown</h3>
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
              {Object.entries(TQ_FACTOR_WEIGHTS).map(([factor, weight]) => (
                <tr key={factor} className="hover:bg-surface">
                  <td className="px-5 py-3">{factor}</td>
                  <td className="px-5 py-3 text-muted-foreground">{weight}%</td>
                  <td className="px-5 py-3 text-muted-foreground">
                    {goNoGoResult.tq_factor_scores?.[factor] ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  );
}

function BidDecisionTab({ goNoGoResult }: { goNoGoResult: GoNoGoResult }) {
  const pqGatePass = goNoGoResult.gaps.length === 0;
  const partnerRequired = goNoGoResult.decision === "Conditional-Go (Partner Required)";
  const strategicRelevance = bucketStrategicRelevance(
    goNoGoResult.factor_scores?.["Strategic Relevance"],
  );

  return (
    <Card className="space-y-4">
      <Row label="PQ Gate">
        <span className={pqGatePass ? "font-semibold text-status-go" : "font-semibold text-status-no-go"}>
          {pqGatePass ? "PASS" : "FAIL"}
        </span>
      </Row>
      <Row label="Expected TQ Score">{goNoGoResult.tq_score ?? "Not available"}</Row>
      <Row label="Commercial Competitiveness">
        {goNoGoResult.commercial_competitiveness ? (
          <SeverityBadge severity={goNoGoResult.commercial_competitiveness} />
        ) : (
          "Not available"
        )}
      </Row>
      <Row label="Bid Preparation Effort">
        {goNoGoResult.bid_preparation_effort ? (
          <SeverityBadge severity={goNoGoResult.bid_preparation_effort} />
        ) : (
          "Not available"
        )}
      </Row>
      <Row label="Strategic Relevance">
        <SeverityBadge severity={strategicRelevance} />
      </Row>
      <Row label="Partner Required">
        <span className="font-semibold">{partnerRequired ? "YES" : "NO"}</span>
      </Row>
      <Row label="Major Qualification Gap">
        {goNoGoResult.major_qualification_gap ?? "Not available"}
      </Row>
      <Row label="Major Technical Gap">{goNoGoResult.major_technical_gap ?? "Not available"}</Row>
      <Row label="Final Recommendation">
        <span className="font-semibold text-foreground">
          {RECOMMENDATION_LABEL[goNoGoResult.decision]}
        </span>
      </Row>
    </Card>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1 border-b border-border pb-3 last:border-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm text-foreground">{children}</span>
    </div>
  );
}

function PartnerPlaceholderTab() {
  return (
    <Card className="text-sm text-muted-foreground">
      Partner/OEM route assessment isn&apos;t built yet — it needs partner-company
      capability data that doesn&apos;t exist anywhere in this system today. Coming soon.
    </Card>
  );
}
