"use client";

import { ArrowLeft, ArrowRight, Eye, EyeOff, FileCheck2, LockKeyhole } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-screen bg-paper lg:grid-cols-2">
      <div className="relative hidden min-h-screen flex-col overflow-hidden bg-navy px-10 py-10 text-white lg:flex xl:px-18">
        <Link href="/" className="relative z-10 inline-flex items-center gap-3 self-start font-display text-lg font-semibold">
          <span className="grid size-9 place-items-center rounded-sm bg-cobalt text-white">T</span>
          Tender AI Platform
        </Link>
        <div className="relative z-10 my-auto max-w-xl animate-rise-in">
          <p className="mb-7 text-xs font-bold uppercase text-cobalt-light">Your bid intelligence workspace</p>
          <h1 className="font-display text-5xl font-semibold leading-[1.13] xl:text-6xl">
            Clarity at every <span className="text-cobalt-light">decision point.</span>
          </h1>
          <p className="mt-7 max-w-md text-base leading-relaxed text-white/65">
            Review eligibility, understand the full tender, and trace every risk back to the page it came from.
          </p>
          <div className="relative mt-14 max-w-md overflow-hidden rounded-md border border-white/15 bg-white/5 p-6">
            <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-cobalt-light/70 animate-scan" />
            <div className="flex items-center gap-3 border-b border-white/10 pb-4">
              <FileCheck2 className="size-5 text-cobalt-light" />
              <span className="text-sm font-semibold">Tender review</span>
              <span className="ml-auto text-xs text-white/45">01 / 03</span>
            </div>
            <div className="mt-5 space-y-4">
              <div className="h-2 w-3/4 rounded-full bg-white/20" />
              <div className="h-2 w-11/12 rounded-full bg-white/10" />
              <div className="h-2 w-2/3 rounded-full bg-white/10" />
            </div>
            <div className="mt-6 flex items-center gap-2 text-xs text-cobalt-light">
              <span className="size-1.5 rounded-full bg-cobalt-light animate-soft-pulse" /> Page-cited findings
            </div>
          </div>
        </div>
        <p className="relative z-10 text-xs text-white/40">Built for Indian government tender bid teams.</p>
        <div className="pointer-events-none absolute -bottom-28 -right-24 size-135 rounded-full border border-white/5" />
        <div className="pointer-events-none absolute -bottom-12 -right-9 size-102.5 rounded-full border border-white/5" />
      </div>

      <div className="flex min-h-screen flex-col px-6 py-7 sm:px-10 sm:py-10 lg:px-16 xl:px-24">
        <div className="flex items-center justify-between">
          <Link href="/" className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 transition-colors hover:text-cobalt">
            <ArrowLeft className="size-4" /> Back to overview
          </Link>
          <span className="font-display text-sm font-semibold text-cobalt lg:hidden">Tender AI Platform</span>
        </div>

        <div className="mx-auto flex w-full max-w-107.5 flex-1 flex-col justify-center py-15 animate-rise-delay">
          <div className="mb-9 grid size-12 place-items-center rounded-md bg-cobalt-light text-cobalt">
            <LockKeyhole className="size-5" />
          </div>
          <p className="mb-3 text-xs font-bold uppercase text-cobalt">Internal access</p>
          <h2 className="font-display text-3xl font-semibold sm:text-4xl">Welcome back.</h2>
          <p className="mt-3 text-sm leading-relaxed text-slate-500">
            Sign in with your provisioned account to continue to your workspace.
          </p>

          <form onSubmit={handleSubmit} className="mt-10 space-y-6">
            <div className="space-y-2.5">
              <label htmlFor="username" className="text-xs font-bold uppercase text-slate-500">
                Username
              </label>
              <input
                id="username"
                name="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
                placeholder="Enter your username"
                className="h-12 w-full rounded-md border border-slate-300 bg-surface px-4 text-sm shadow-none outline-none focus-visible:ring-2 focus-visible:ring-cobalt/25"
              />
            </div>
            <div className="space-y-2.5">
              <label htmlFor="password" className="text-xs font-bold uppercase text-slate-500">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                  placeholder="Enter your password"
                  className="h-12 w-full rounded-md border border-slate-300 bg-surface px-4 pr-12 text-sm shadow-none outline-none focus-visible:ring-2 focus-visible:ring-cobalt/25"
                />
                <button
                  type="button"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  title={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-1 top-1.5 grid size-9 place-items-center rounded-md text-slate-500 hover:text-cobalt"
                >
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-md bg-cobalt text-sm font-medium text-white transition-colors hover:bg-cobalt/90 hover:shadow-lg hover:shadow-cobalt/15 disabled:pointer-events-none disabled:opacity-50"
            >
              {submitting ? "Signing in…" : (
                <>
                  Sign in <ArrowRight className="size-4" />
                </>
              )}
            </button>

            {error && (
              <p role="status" className="rounded-md border border-danger/30 bg-danger-surface p-3 text-sm leading-relaxed text-danger">
                {error}
              </p>
            )}
          </form>

          <p className="mt-8 border-t border-slate-200 pt-6 text-xs leading-relaxed text-slate-500">
            This workspace is for internal bid teams. Accounts are provisioned directly; self-registration is not available.
          </p>
        </div>
        <p className="text-center text-xs text-slate-500">Tender AI Platform · Advisory outputs for human review</p>
      </div>
    </main>
  );
}
