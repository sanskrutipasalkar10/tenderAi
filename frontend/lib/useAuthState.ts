"use client";

import { useSyncExternalStore } from "react";
import { getToken } from "./auth";

// localStorage isn't available during SSR, and a client component still renders once
// on the server before hydrating — useSyncExternalStore is React's own answer to
// "read a browser-only value without a setState-in-an-effect flash of stale state":
// it renders `false` (getServerSnapshot) for the SSR pass and the very first client
// render (matching, no hydration warning), then re-checks the real client snapshot
// right after hydration and re-renders if it actually differs.
const noopSubscribe = () => () => {};

export function useAuthState(): boolean {
  return useSyncExternalStore(
    noopSubscribe,
    () => getToken() !== null,
    () => false,
  );
}
