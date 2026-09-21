"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import AuthGuard from "./AuthGuard";
import { clearToken } from "@/lib/auth";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/company-profile", label: "Company profiles" },
];

/** Wraps every authenticated page: auth check + the app's own light-mode chrome,
 * distinct from the landing page's dark marketing world (DESIGN.md — Restrained
 * color strategy, this is an Operate surface). */
export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="min-h-screen bg-paper text-ink-900">
        <TopBar />
        <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">{children}</main>
      </div>
    </AuthGuard>
  );
}

function TopBar() {
  const router = useRouter();
  const pathname = usePathname();

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6 sm:py-4">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <Link href="/dashboard" className="flex items-center gap-2 font-semibold">
            <span className="flex h-7 w-7 flex-none items-center justify-center rounded bg-ink-950 text-xs font-bold text-accent-bright">
              T
            </span>
            <span>Tender AI Platform</span>
          </Link>
          <nav className="flex items-center gap-4 sm:gap-6">
            {NAV_LINKS.map((link) => {
              const active = pathname === link.href || pathname.startsWith(link.href + "/");
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`text-sm font-medium ${
                    active ? "text-accent" : "text-slate-500 hover:text-ink-900"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex items-center gap-3 sm:gap-4">
          <Link
            href="/upload"
            className="rounded-md bg-ink-950 px-4 py-2 text-sm font-medium whitespace-nowrap text-white hover:bg-ink-900"
          >
            Upload tender
          </Link>
          <button
            type="button"
            onClick={() => {
              clearToken();
              router.push("/login");
            }}
            className="text-sm whitespace-nowrap text-slate-500 hover:text-ink-900"
          >
            Log out
          </button>
        </div>
      </div>
    </header>
  );
}
