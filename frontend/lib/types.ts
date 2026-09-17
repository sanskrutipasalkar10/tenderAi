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
  status: DocumentStatus;
  total_pages: number | null;
  uploaded_at: string;
}

export interface DocumentStatusResponse {
  id: string;
  status: DocumentStatus;
  total_pages: number | null;
  pages_processed: number;
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

export interface GoNoGoCriterionMatch {
  criterion: string;
  required: string;
  company_value: string;
  status: "pass" | "fail";
  page_ref: number;
}

export interface GoNoGoResult {
  score: number;
  decision: "Go" | "Conditional-Go" | "No-Go";
  criteria_matches: GoNoGoCriterionMatch[];
  gaps: string[];
  next_steps: string[];
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

export interface CompanyProfileWrite {
  company_name: string;
  annual_turnover: Record<string, number> | null;
  certifications: string[] | null;
  past_projects: CompanyProfilePastProject[] | null;
  geographic_presence: string[] | null;
  sectors: string[] | null;
  max_capacity_pct: number | null;
}

export interface CompanyProfileResponse extends CompanyProfileWrite {
  id: string;
  created_at: string;
  updated_at: string;
}
