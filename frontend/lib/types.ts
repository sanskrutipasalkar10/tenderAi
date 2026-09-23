// Mirrors backend/app/models/schemas.py field-for-field — this frontend renders
// exactly what the API returns, never reshapes it, so a schema change there should be
// the only place a change is needed here too.

export type DocumentStatus =
  | "uploaded"
  | "classifying"
  | "extracting"
  | "extracted"
  | "analyzing"
  | "ready"
  | "failed";

export interface DocumentUploadResponse {
  id: string;
  filename: string;
  issuing_authority: string | null;
  status: DocumentStatus;
  total_pages: number | null;
  uploaded_at: string;
}

export interface DocumentStatusResponse {
  id: string;
  status: DocumentStatus;
  total_pages: number | null;
  pages_processed: number;
  chunks_total: number;
  chunks_mapped: number;
  modules_ready: AnalysisModule[];
  updated_at: string;
}

export type AnalysisModule = "go_no_go" | "synopsis" | "risk_finder";

export interface DocumentAnalysisResponse<TResult = unknown> {
  id: string;
  document_id: string;
  module: AnalysisModule;
  result: TResult;
  model_used: string | null;
  created_at: string;
}

// --- go_no_go ------------------------------------------------------------------

export type GoNoGoStatus = "pass" | "fail" | "insufficient_data";
export type GoNoGoCriterionType = "eligibility" | "procedural";

export interface GoNoGoHumanOverride {
  status: "pass" | "fail";
  note: string | null;
  original_status: GoNoGoStatus;
  reviewed_at: string;
}

export interface GoNoGoCriterionMatch {
  criterion: string;
  required: string;
  company_value: string;
  status: GoNoGoStatus;
  page_ref: number;
  // One of the 7 named hard-fail gates if this criterion's failure triggers one,
  // else null — see backend/app/pipeline/reduce_pass.py's HARD_FAIL_GATES. Never set
  // on a "procedural" criterion.
  gate: string | null;
  // "eligibility" (a real company-capability fact) vs. "procedural" (a bid-package
  // mechanic any bidder can satisfy — excluded from scoring/gates entirely).
  criterion_type: GoNoGoCriterionType;
  human_override: GoNoGoHumanOverride | null;
}

// The 8 weighted Bid/No-Bid factors (backend/app/pipeline/reduce_pass.py's
// BID_DECISION_FACTOR_WEIGHTS), each scored 0-100 by the model.
export type GoNoGoFactorScores = Record<string, number>;

export interface GoNoGoResult {
  score: number;
  decision: "Go" | "Go (Management Review)" | "Conditional-Go (Partner Required)" | "No-Go";
  criteria_matches: GoNoGoCriterionMatch[];
  gaps: string[];
  next_steps: string[];
  factor_scores: GoNoGoFactorScores | null;
}

// --- risk_finder ---------------------------------------------------------------

export interface RiskFinderRisk {
  category: string;
  clause_summary: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  page_ref: number;
  verified: boolean;
}

export interface RiskFinderResult {
  risk_score: number;
  risks: RiskFinderRisk[];
}

// --- synopsis --------------------------------------------------------------------

export interface SynopsisFact {
  label: string;
  value: string;
  page_ref: number;
}

export interface SynopsisResult {
  title: string;
  issuing_authority: string;
  key_dates: SynopsisFact[];
  financials: SynopsisFact[];
  scope_summary: string;
  eligibility_summary: string;
  payment_terms_summary: string;
  confidence: "high" | "medium" | "low";
}

// --- page content (the citation-verification UI's data source) -------------------

export interface PageContentResponse {
  page_number: number;
  classification: "native_text" | "scanned_image" | "table" | "mixed";
  extraction_method: "native" | "vision_cloud" | "vision_local" | null;
  raw_text: string | null;
  confidence_score: number | null;
  has_image: boolean;
}

// --- company_profiles --------------------------------------------------------

export interface CompanyProfilePastProject {
  name: string;
  client: string | null;
  value: number | null;
  year: number | null;
  sector: string | null;
}

export interface CompanyProfileDirector {
  name: string;
  din_or_pan: string | null;
  designation: string | null;
  category: string | null;
  appointed: string | null;
}

export interface CompanyProfileMsmeClassification {
  year: string;
  type: string;
}

export interface CompanyProfileGovernmentGrant {
  department: string;
  source: string | null;
  fy: string | null;
  amount: number | null;
  purpose: string | null;
}

export interface CompanyProfileBankDetails {
  bank: string | null;
  ifsc: string | null;
  account: string | null;
}

export interface CompanyProfileEmploymentCount {
  male: number | null;
  female: number | null;
  other: number | null;
}

// Statutory/financial fields (migration 0003, docs/sutf-company-profile-decision-
// grade.docx) — mirrors backend/app/models/schemas.py's CompanyProfileWrite exactly.
export interface CompanyProfileWrite {
  company_name: string;
  annual_turnover: Record<string, number> | null;
  certifications: string[] | null;
  past_projects: CompanyProfilePastProject[] | null;
  geographic_presence: string[] | null;
  sectors: string[] | null;
  max_capacity_pct: number | null;
  cin: string | null;
  roc_number: string | null;
  section8_licence_number: string | null;
  date_of_incorporation: string | null;
  pan: string | null;
  gstin: string | null;
  udyam_registration_number: string | null;
  msme_classification: CompanyProfileMsmeClassification[] | null;
  ngo_darpan_id: string | null;
  authorised_capital_inr: number | null;
  paid_up_capital_inr: number | null;
  net_worth_inr: number | null;
  // Must be set whenever annual_turnover is (enforced by the backend) — names which
  // document annual_turnover's figures came from.
  turnover_source: string | null;
  // Retained, never used for scoring, until entity attribution is confirmed.
  unconfirmed_org_turnover_inr: Record<string, number> | null;
  directors: CompanyProfileDirector[] | null;
  bank_details: CompanyProfileBankDetails | null;
  employment_count: CompanyProfileEmploymentCount | null;
  government_grants: CompanyProfileGovernmentGrant[] | null;
}

export interface CompanyProfileResponse extends CompanyProfileWrite {
  id: string;
  created_at: string;
  updated_at: string;
}
