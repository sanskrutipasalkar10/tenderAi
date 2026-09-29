"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import AuthGuard from "./AuthGuard";
import Button from "./ui/Button";
import { LogOutIcon, UploadIcon } from "./ui/icons";
import { clearToken } from "@/lib/auth";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/company-profile", label: "Company profiles" },
];

/** Wraps every authenticated page: auth check + the app's own chrome. `<main>` is
 * deliberately unconstrained (no max-width/padding) — each page owns its own
 * full-bleed hero header (via PageHeader) plus a contained body section below it,
 * matching the pulled design's own layout convention (docs/DESIGN.md Revision 5). */
export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="min-h-screen bg-background text-foreground">
        <TopBar />
        <main>{children}</main>
      </div>
    </AuthGuard>
  );
}

function TopBar() {
  const router = useRouter();
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur-sm">
      <div className="mx-auto flex min-h-16 max-w-305 flex-wrap items-center justify-between gap-x-5 gap-y-2 px-5 py-2 md:px-8">
        <div className="flex flex-wrap items-center gap-x-9 gap-y-2">
          <Link href="/dashboard" className="inline-flex shrink-0 items-center gap-2.5 font-semibold text-foreground">
            <span className="flex size-8 items-center justify-center rounded-[3px] bg-primary text-sm font-bold text-primary-foreground">
              T
            </span>
            <span className="text-[15px]">
              Tender AI <span className="text-primary">Platform</span>
            </span>
          </Link>
          <nav className="flex items-center gap-1" aria-label="Main navigation">
            {NAV_LINKS.map((link) => {
              const active = pathname === link.href || pathname.startsWith(link.href + "/");
              return (
                <Link key={link.href} href={link.href} className={`nav-link ${active ? "nav-link-active" : ""}`}>
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex items-center gap-2">
          <Button href="/upload" variant="dark" size="sm" icon={<UploadIcon className="h-4 w-4" />}>
            Upload tender
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              clearToken();
              router.push("/login");
            }}
            icon={<LogOutIcon className="h-4 w-4" />}
          >
            Log out
          </Button>
        </div>
      </div>
    </header>
  );
}
