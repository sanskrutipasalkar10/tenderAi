"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearToken } from "@/lib/auth";
import { useAuthState } from "@/lib/useAuthState";

export default function NavBar() {
  const router = useRouter();
  const pathname = usePathname();
  const authed = useAuthState();

  if (pathname === "/login") return null;

  return (
    <header className="border-b border-neutral-200 dark:border-neutral-800">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <Link href="/documents" className="font-semibold">
          Tender AI Platform
        </Link>
        {authed && (
          <button
            type="button"
            onClick={() => {
              clearToken();
              router.push("/login");
            }}
            className="text-sm text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
          >
            Log out
          </button>
        )}
      </div>
    </header>
  );
}
