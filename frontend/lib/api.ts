import { clearToken, getToken, setToken } from "./auth";
import type {
  AnalysisModule,
  ChatMessage,
  ChatResponse,
  CompanyProfileResponse,
  CompanyProfileWrite,
  DocumentAnalysisResponse,
  DocumentStatusResponse,
  DocumentUploadResponse,
  GoNoGoResult,
  PageContentResponse,
} from "./types";

// NEXT_PUBLIC_ — read at build time, baked into the client bundle; standard Next.js
// convention for a browser-visible config value (never a secret).
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (response.status === 401) {
    // The shared credential's token expired or was never set — send the user back to
    // login rather than rendering a page that can only ever 401. This is a plain
    // module, not a component, so there's no useRouter() to reach for here — a hard
    // navigation also clears any stale in-memory state left over from the failed
    // session, which a router-only transition wouldn't.
    clearToken();
    if (typeof window !== "undefined") {
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = "/login";
    }
    throw new ApiError(401, "Not authenticated");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, body.message ?? body.detail ?? response.statusText);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function login(username: string, password: string): Promise<void> {
  // POST /token is FastAPI's OAuth2PasswordRequestForm (docs/DECISIONS.md #44) — a
  // form-encoded body, not JSON.
  const body = new URLSearchParams({ username, password });
  const response = await fetch(`${API_BASE_URL}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new ApiError(response.status, detail.message ?? "Login failed");
  }
  const data = (await response.json()) as { access_token: string };
  setToken(data.access_token);
}

export function listDocuments(): Promise<DocumentUploadResponse[]> {
  return apiFetch("/documents");
}

// companyProfileId is required — the backend rejects an upload with none (a company
// profile is now compulsory for analysis, not optional).
export function uploadDocument(
  file: File,
  companyProfileId: string,
  attachments: File[] = [],
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  for (const attachment of attachments) {
    formData.append("attachments", attachment);
  }
  return apiFetch(`/documents?company_profile_id=${companyProfileId}`, {
    method: "POST",
    body: formData,
  });
}

export function getDocumentStatus(documentId: string): Promise<DocumentStatusResponse> {
  return apiFetch(`/documents/${documentId}/status`);
}

// Re-runs go_no_go/synopsis/risk_finder against the document's existing extracted
// facts — for after a company-profile or backend-logic change. Only valid once a
// document has already reached status "ready" once (the backend 409s otherwise).
export function reevaluateDocument(documentId: string): Promise<DocumentUploadResponse> {
  return apiFetch(`/documents/${documentId}/reevaluate`, { method: "POST" });
}

export function cancelDocument(documentId: string): Promise<DocumentStatusResponse> {
  return apiFetch(`/documents/${documentId}/cancel`, { method: "POST" });
}

export function getAnalysis<T = unknown>(
  documentId: string,
  module: AnalysisModule,
): Promise<DocumentAnalysisResponse<T>> {
  return apiFetch(`/documents/${documentId}/analysis/${module}`);
}

export function getAllAnalysis(documentId: string): Promise<DocumentAnalysisResponse[]> {
  return apiFetch(`/documents/${documentId}/analysis`);
}

export interface GoNoGoCriterionOverride {
  criterion_index: number;
  status: "pass" | "fail";
  note: string | null;
}

export function reviewGoNoGo(
  documentId: string,
  overrides: GoNoGoCriterionOverride[],
): Promise<DocumentAnalysisResponse<GoNoGoResult>> {
  return apiFetch(`/documents/${documentId}/analysis/go_no_go/review`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ overrides }),
  });
}

export function resubmitGoNoGo(documentId: string): Promise<DocumentAnalysisResponse<GoNoGoResult>> {
  // Triggers a real LLM call (fresh factor_scores against the already-reviewed
  // criteria_matches), unlike reviewGoNoGo above — see docs/DECISIONS.md.
  return apiFetch(`/documents/${documentId}/analysis/go_no_go/resubmit`, { method: "POST" });
}

export function getPageContent(
  documentId: string,
  pageNumber: number,
): Promise<PageContentResponse> {
  return apiFetch(`/documents/${documentId}/pages/${pageNumber}`);
}

export function getPageImageUrl(documentId: string, pageNumber: number): string {
  // Not fetched via apiFetch — used directly as an <img src>, so the browser makes
  // this request itself. The auth token can't ride along on a plain <img> tag; see
  // CitationLink's use of an authenticated fetch + object URL instead of this
  // function directly, for the actual image render.
  return `${API_BASE_URL}/documents/${documentId}/pages/${pageNumber}/image`;
}

export async function getPageImageBlob(documentId: string, pageNumber: number): Promise<Blob> {
  const token = getToken();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(getPageImageUrl(documentId, pageNumber), { headers });
  if (!response.ok) throw new ApiError(response.status, "Could not load page image");
  return response.blob();
}

export function listCompanyProfiles(): Promise<CompanyProfileResponse[]> {
  return apiFetch("/company-profiles");
}

export function getCompanyProfile(profileId: string): Promise<CompanyProfileResponse> {
  return apiFetch(`/company-profiles/${profileId}`);
}

export function createCompanyProfile(
  payload: CompanyProfileWrite,
): Promise<CompanyProfileResponse> {
  return apiFetch("/company-profiles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// Ephemeral — the server never stores this conversation, so `history` (held in the
// widget's own React state) is resent in full on every turn.
export function sendChatMessage(
  message: string,
  documentId: string | null,
  history: ChatMessage[],
): Promise<ChatResponse> {
  return apiFetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, document_id: documentId, history }),
  });
}

// Can't go through apiFetch (it always calls .json() on the full body) or EventSource
// (can't send a POST body) — reads the response as an incrementally-decoded stream
// instead, calling the matching handler as each `data: {...}` frame arrives. Mirrors
// apiFetch's own 401 handling since it can't reuse that function directly.
export async function streamChatMessage(
  message: string,
  documentId: string | null,
  history: ChatMessage[],
  handlers: {
    onDelta: (text: string) => void;
    onDone: () => void;
    onError: (message: string) => void;
  },
  signal?: AbortSignal,
): Promise<void> {
  const token = getToken();
  const headers = new Headers({ "Content-Type": "application/json" });
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({ message, document_id: documentId, history }),
    signal,
  });

  if (response.status === 401) {
    clearToken();
    if (typeof window !== "undefined") {
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = "/login";
    }
    throw new ApiError(401, "Not authenticated");
  }
  if (!response.ok || !response.body) {
    throw new ApiError(response.status, "Chat stream failed to start");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    // {stream: true} is load-bearing — a multi-byte UTF-8 character can land split
    // across two chunk boundaries, and this keeps the trailing partial byte(s) buffered
    // in the decoder's own internal state until the rest arrives, instead of mangling it.
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.trim();
      if (!line.startsWith("data:")) continue;
      const payload = JSON.parse(line.slice("data:".length).trim());
      if (payload.delta) handlers.onDelta(payload.delta);
      else if (payload.done) handlers.onDone();
      else if (payload.error) handlers.onError(payload.error);
    }
  }
}

export function updateCompanyProfile(
  profileId: string,
  payload: CompanyProfileWrite,
): Promise<CompanyProfileResponse> {
  return apiFetch(`/company-profiles/${profileId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
