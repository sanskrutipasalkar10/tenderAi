import { clearToken, getToken, setToken } from "./auth";
import type {
  AnalysisModule,
  DocumentAnalysisResponse,
  DocumentStatusResponse,
  DocumentUploadResponse,
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

export function uploadDocument(
  file: File,
  companyProfileId?: string,
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const query = companyProfileId ? `?company_profile_id=${companyProfileId}` : "";
  return apiFetch(`/documents${query}`, { method: "POST", body: formData });
}

export function getDocumentStatus(documentId: string): Promise<DocumentStatusResponse> {
  return apiFetch(`/documents/${documentId}/status`);
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
