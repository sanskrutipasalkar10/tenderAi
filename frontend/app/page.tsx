import { ArrowRight, ArrowUpRight, Check, FileCheck2, FileSearch, ScanText, ShieldAlert } from "lucide-react";
import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Tender AI Platform | Bid intelligence for Indian government tenders",
  description:
    "Turn complex government tender PDFs into an evidence-backed Go/No-Go decision, a structured synopsis, and a page-cited risk review.",
};

function Brand() {
  return (
    <Link href="/" className="inline-flex items-center gap-2.5 font-display text-base font-semibold text-foreground" aria-label="Tender AI Platform home">
      <span className="grid size-8 place-items-center rounded-sm bg-primary text-lg text-primary-foreground">T</span>
      <span>
        Tender AI <span className="text-primary">Platform</span>
      </span>
    </Link>
  );
}

function SampleAnalysis() {
  return (
    <div className="relative isolate mx-auto w-full max-w-124 animate-rise-late lg:mt-3" aria-label="Illustrative tender analysis preview">
      <div className="absolute -bottom-5 -left-5 -z-10 h-full w-full -rotate-2 rounded-lg border border-primary/10 bg-accent" />
      <div className="relative rotate-1 overflow-hidden rounded-lg border border-border bg-surface p-6 shadow-2xl shadow-foreground/10 transition-transform duration-500 hover:rotate-0 sm:p-8">
        <div className="mb-7 flex items-start justify-between gap-4">
          <div>
            <p className="mb-2 text-[10px] font-bold uppercase text-muted-foreground">Sample analysis · illustrative</p>
            <h2 className="font-display text-xl font-semibold">Conditional Go</h2>
            <p className="mt-1 text-xs text-muted-foreground">Example tender assessment</p>
          </div>
          <div className="grid size-14 shrink-0 place-items-center rounded-full border-4 border-accent border-t-primary font-display text-lg font-semibold text-primary">
            78
          </div>
        </div>
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3 rounded-md border border-border/60 bg-background px-3 py-3">
            <span className="text-sm font-medium">Annual turnover</span>
            <span className="rounded-sm bg-status-go/10 px-2 py-1 text-[10px] font-bold text-status-go">PASS</span>
          </div>
          <div className="flex items-center justify-between gap-3 rounded-md border border-border/60 bg-background px-3 py-3">
            <span className="text-sm font-medium">Relevant project experience</span>
            <span className="rounded-sm bg-status-go/10 px-2 py-1 text-[10px] font-bold text-status-go">PASS</span>
          </div>
          <div className="flex items-center justify-between gap-3 rounded-md border border-border/60 bg-background px-3 py-3">
            <span className="text-sm font-medium">Certification requirement</span>
            <span className="rounded-sm bg-status-conditional/10 px-2 py-1 text-[10px] font-bold text-status-conditional">REVIEW</span>
          </div>
        </div>
        <div className="mt-6 border-t border-border pt-5">
          <p className="mb-3 text-[10px] font-bold uppercase text-muted-foreground">Source traceability</p>
          <div className="flex items-center gap-2 text-xs font-semibold text-primary">
            <FileSearch className="size-4" /> Page 42 · Eligibility criteria <ArrowUpRight className="ml-auto size-4" />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Index() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b border-foreground/5 bg-background/90 backdrop-blur-xl">
        <nav className="mx-auto flex h-17 max-w-7xl items-center justify-between px-6" aria-label="Main navigation">
          <Brand />
          <div className="flex items-center gap-3 sm:gap-8">
            <a href="#platform" className="hidden text-sm font-medium transition-colors hover:text-primary sm:inline">
              Platform
            </a>
            <a href="#analysis" className="hidden text-sm font-medium transition-colors hover:text-primary sm:inline">
              Analysis
            </a>
            <Link href="/login" className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-foreground px-4 text-sm font-medium text-background transition-colors hover:bg-foreground/90">
              Sign in <ArrowUpRight className="size-4" />
            </Link>
          </div>
        </nav>
      </header>

      <main>
        <section id="platform" className="flex min-h-[calc(100vh-4.25rem)] items-center overflow-hidden px-6 py-16 sm:py-20">
          <div className="mx-auto grid max-w-7xl items-center gap-14 lg:grid-cols-12 lg:gap-16">
            <div className="animate-rise-in lg:col-span-7">
              <span className="mb-7 inline-flex items-center gap-2 rounded-full bg-accent px-3 py-1.5 text-[11px] font-bold uppercase text-primary">
                <span className="size-1.5 rounded-full bg-primary animate-soft-pulse" />
                Bid team intelligence
              </span>
              <h1 className="max-w-190 font-display text-[clamp(2.8rem,5.3vw,5rem)] font-semibold leading-[1.12] text-foreground">
                Transform 1,000 pages into a <span className="text-primary">5-minute read.</span>
              </h1>
              <p className="mt-7 max-w-[57ch] text-base leading-relaxed text-muted-foreground sm:text-lg">
                Built for Indian government tender bid teams. Go from dense PDFs to an eligibility decision, a clear
                synopsis, and ranked risks — with every finding linked to its source page.
              </p>
              <div className="mt-9 flex flex-wrap gap-3">
                <Link href="/login" className="inline-flex h-12 items-center justify-center gap-2 rounded-md bg-primary px-6 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 hover:shadow-lg hover:shadow-primary/15">
                  Sign in to workspace <ArrowRight className="size-4" />
                </Link>
                <a href="#analysis" className="inline-flex h-12 items-center justify-center gap-2 rounded-md border border-border bg-transparent px-6 text-sm font-medium text-foreground transition-colors hover:bg-accent">
                  Explore the analysis <ArrowRight className="size-4" />
                </a>
              </div>
              <div className="mt-11 flex flex-wrap items-center gap-x-8 gap-y-3 border-t border-border pt-5 text-xs font-semibold text-muted-foreground">
                <span className="flex items-center gap-2">
                  <Check className="size-4 text-primary" /> Native text &amp; scanned pages
                </span>
                <span className="flex items-center gap-2">
                  <Check className="size-4 text-primary" /> Tables &amp; clauses
                </span>
                <span className="flex items-center gap-2">
                  <Check className="size-4 text-primary" /> Page-cited findings
                </span>
              </div>
            </div>
            <div className="lg:col-span-5">
              <SampleAnalysis />
            </div>
          </div>
        </section>

        <section id="analysis" className="scroll-mt-17 bg-foreground px-6 py-22 text-background sm:py-30">
          <div className="mx-auto max-w-7xl">
            <div className="mb-14 grid gap-5 md:grid-cols-[1fr_auto] md:items-end">
              <div>
                <p className="mb-4 text-xs font-bold uppercase text-primary-bright">One tender. Three clear answers.</p>
                <h2 className="max-w-2xl font-display text-3xl font-semibold leading-tight sm:text-4xl">
                  The full picture before you make the call.
                </h2>
              </div>
              <p className="max-w-sm text-sm leading-relaxed text-background/60">
                A decision you can review, not a black box you have to trust.
              </p>
            </div>
            <div className="grid gap-9 md:grid-cols-3 md:gap-0">
              <article className="border-t border-background/20 pt-6 md:pr-9">
                <span className="mb-10 flex items-center justify-between text-xs font-semibold text-primary-bright">
                  <span>01 / DECIDE</span>
                  <FileCheck2 className="size-5" />
                </span>
                <h3 className="font-display text-2xl font-medium">Go/No-Go Analyzer</h3>
                <p className="mt-5 max-w-[40ch] text-sm leading-relaxed text-background/65">
                  Match turnover, certifications, and past projects against tender eligibility. See the score, gaps,
                  and reasoning behind a Go, No-Go, or Conditional-Go recommendation.
                </p>
                <div className="mt-8 flex items-center gap-3 border-t border-background/10 pt-4 text-xs text-primary-bright">
                  <span className="grid size-7 place-items-center rounded-sm bg-primary/25">
                    <Check className="size-4" />
                  </span>
                  Profile-to-criteria matching
                </div>
              </article>
              <article className="border-t border-background/20 pt-6 md:border-l md:px-9">
                <span className="mb-10 flex items-center justify-between text-xs font-semibold text-primary-bright">
                  <span>02 / UNDERSTAND</span>
                  <ScanText className="size-5" />
                </span>
                <h3 className="font-display text-2xl font-medium">AI Tender Synopsis</h3>
                <p className="mt-5 max-w-[40ch] text-sm leading-relaxed text-background/65">
                  Get a structured, 5-minute read of the title, dates, financial figures, scope, eligibility, and
                  payment terms, drawn from the full tender document.
                </p>
                <div className="mt-8 flex items-center gap-3 border-t border-background/10 pt-4 text-xs text-primary-bright">
                  <span className="grid size-7 place-items-center rounded-sm bg-primary/25">
                    <Check className="size-4" />
                  </span>
                  Key terms in one view
                </div>
              </article>
              <article className="border-t border-background/20 pt-6 md:border-l md:pl-9">
                <span className="mb-10 flex items-center justify-between text-xs font-semibold text-primary-bright">
                  <span>03 / VERIFY</span>
                  <ShieldAlert className="size-5" />
                </span>
                <h3 className="font-display text-2xl font-medium">AI Risk Finder</h3>
                <p className="mt-5 max-w-[40ch] text-sm leading-relaxed text-background/65">
                  Surface liquidated damages, indemnity, termination, and payment risks in a ranked list. Trace each
                  flag to the exact page and clause.
                </p>
                <div className="mt-8 overflow-hidden rounded-md border border-background/10">
                  <Image
                    src="/images/risk-analysis.jpg"
                    alt="Illustration of a ranked tender risk review interface"
                    width={1024}
                    height={656}
                    className="aspect-2/1 w-full object-cover"
                  />
                </div>
              </article>
            </div>
          </div>
        </section>

        <section className="border-b border-border px-6 py-22 sm:py-28">
          <div className="mx-auto grid max-w-7xl gap-10 md:grid-cols-12 md:items-start">
            <div className="md:col-span-5">
              <p className="mb-4 text-xs font-bold uppercase text-primary">Evidence, not guesswork</p>
              <h2 className="font-display text-3xl font-semibold leading-tight sm:text-4xl">
                From the finding, back to the page.
              </h2>
            </div>
            <div className="md:col-span-7 md:pl-10">
              <p className="max-w-2xl text-lg leading-relaxed text-muted-foreground">
                A tender can run from 50 to 1,000+ pages of text, scans, and tables. The platform reads across
                formats, then pairs its conclusions with page citations so your team can inspect the original
                wording before deciding to bid.
              </p>
              <div className="mt-9 flex items-center gap-4 border-l-2 border-primary pl-5">
                <span className="font-display text-3xl font-semibold text-primary">3–7 days</span>
                <ArrowRight className="size-5 shrink-0 text-primary" />
                <span className="font-display text-3xl font-semibold text-foreground">minutes</span>
              </div>
              <p className="mt-3 pl-5 text-xs text-muted-foreground">
                From manual first-pass review to a review-ready starting point.
              </p>
            </div>
          </div>
        </section>

        <section className="px-6 py-24 sm:py-30">
          <div className="mx-auto max-w-7xl text-center">
            <p className="mb-5 text-xs font-bold uppercase text-primary">For your next tender</p>
            <h2 className="mx-auto max-w-3xl font-display text-3xl font-semibold leading-tight sm:text-4xl">
              Spend less time finding the facts. More time deciding what matters.
            </h2>
            <Link href="/login" className="mt-8 inline-flex h-12 items-center justify-center gap-2 rounded-md bg-primary px-7 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 hover:shadow-lg hover:shadow-primary/15">
              Sign in to workspace <ArrowRight className="size-4" />
            </Link>
            <p className="mt-5 text-xs text-muted-foreground">Access is provisioned for internal bid teams.</p>
          </div>
        </section>
      </main>
      <footer className="border-t border-border px-6 py-8">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-4 text-xs text-muted-foreground sm:flex-row">
          <span>Tender AI Platform</span>
          <span>Advisory outputs for human review. The platform does not submit bids on your behalf.</span>
        </div>
      </footer>
    </div>
  );
}
