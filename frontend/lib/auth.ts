// Single shared credential (docs/DECISIONS.md #44) — one JWT, no per-user identity.
// localStorage, not a cookie: this is a client-only SPA-style frontend talking to a
// separate API origin, and the token never needs to be read server-side here (every
// page that needs it is a client component — see lib/api.ts).

const TOKEN_KEY = "tender_ai_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}
