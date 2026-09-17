"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { getToken } from "@/lib/auth";
import { useAuthState } from "@/lib/useAuthState";

// Client-side only (docs/DECISIONS.md #44 — a single JWT in localStorage, no
// server-side session) — good enough for an internal Tier-2 tool; a real per-user
// system would need a server-checkable session instead.
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const authed = useAuthState(); // what to render — SSR-safe (see lib/useAuthState.ts)

  useEffect(() => {
    // Read the token directly here rather than branching on `authed`: on first
    // mount, `authed` is still the SSR-matched `false` for one tick before
    // useSyncExternalStore corrects it to the real client value — deciding to
    // redirect from `authed` would fire on every real login too, one render early.
    // This effect only runs once (mount), by which point hydration has already
    // committed and localStorage is safe to read directly.
    if (getToken() === null) {
      router.replace("/login");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deliberately mount-only
  }, []);

  if (!authed) return null;
  return <>{children}</>;
}
