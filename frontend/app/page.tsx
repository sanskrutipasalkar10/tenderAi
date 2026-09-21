"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import ScoreGauge from "@/components/ScoreGauge";
import { CriterionStatusBadge, DecisionBadge } from "@/components/badges";

const MODULES = [
  {
    name: "Go/No-Go Analyzer",
    tag: "01",
    copy: "Every eligibility criterion checked against your company's real data, with a single score and decision — not a guess dressed up as confidence.",
    tags: ["Score & decision", "Criteria match", "Gap list"],
  },
  {
    name: "AI Tender Synopsis",
    tag: "02",
    copy: "Title, authority, value, EMD, dates, scope, eligibility, and payment terms — the whole tender read for you in one structured page.",
    tags: ["Key dates", "Financials", "Scope & eligibility"],
  },
  {
    name: "AI Risk Finder",
    tag: "03",
    copy: "Every liquidated-damages clause, indemnity, and one-sided term ranked by severity, each one linked to the exact page it came from.",
    tags: ["Severity ranking", "Source citations", "Export"],
  },
];

const STEPS = [
  {
    n: "01",
    title: "Upload",
    copy: "Drop in a tender PDF — 50 to 1000+ pages, native text, scans, or tables, mixed.",
  },
  {
    n: "02",
    title: "AI analysis",
    copy: "Every page is read, classified, and extracted; nothing is skipped or summarized blind.",
  },
  {
    n: "03",
    title: "Review",
    copy: "Read the Go/No-Go score, synopsis, and risk list — click any fact to see its real source page.",
  },
  {
    n: "04",
    title: "Decide",
    copy: "Your team makes the bid/no-bid call with the full picture, in minutes instead of days.",
  },
];

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

const staggerContainer = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.1 } },
};

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-ink-950 text-slate-100">
      <SiteHeader />
      <Hero />
      <HowItWorks />
      <Modules />
      <Security />
      <FinalCta />
      <SiteFooter />
    </div>
  );
}

function SiteHeader() {
  return (
    <motion.header
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="border-b border-white/10"
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2 font-semibold">
          <span className="flex h-7 w-7 items-center justify-center rounded bg-white/10 text-xs font-bold text-accent-bright">
            T
          </span>
          <span>Tender AI Platform</span>
        </div>
        <Link
          href="/login"
          className="rounded border border-white/15 px-4 py-2 text-sm font-medium text-slate-100 transition-colors hover:border-accent-bright hover:text-accent-bright"
        >
          Sign in
        </Link>
      </div>
    </motion.header>
  );
}

function Hero() {
  return (
    <section className="overflow-hidden border-b border-white/10">
      <div className="mx-auto grid max-w-6xl gap-16 px-6 py-20 lg:grid-cols-[1.05fr_1fr] lg:items-center lg:py-28">
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          animate="visible"
        >
          <motion.p
            variants={fadeUp}
            className="data-mono mb-6 text-xs uppercase tracking-[0.2em] text-accent-bright"
          >
            For Indian government tender bid teams
          </motion.p>
          <motion.h1
            variants={fadeUp}
            className="heading-tight text-5xl font-medium text-white sm:text-6xl"
          >
            Know whether to bid,
            <br />
            <span className="bg-gradient-to-r from-accent-bright to-cyan-200 bg-clip-text text-transparent">
              in minutes — not days.
            </span>
          </motion.h1>
          <motion.p variants={fadeUp} className="mt-6 max-w-xl text-lg text-slate-300">
            Tender AI Platform reads the full tender PDF — every page, mixed text, scans, and
            tables — and gives your team a Go/No-Go score, a structured synopsis, and a
            page-cited risk list. Every claim traces back to the exact page it came from.
          </motion.p>
          <motion.div
            variants={fadeUp}
            className="mt-10 flex flex-wrap items-center gap-x-8 gap-y-4"
          >
            <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.98 }}>
              <Link
                href="/login"
                className="inline-block rounded bg-accent px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-accent/20 transition-colors hover:bg-cyan-600"
              >
                Sign in to your workspace
              </Link>
            </motion.div>
            <a
              href="#how-it-works"
              className="group inline-flex items-center gap-1.5 text-sm font-medium text-slate-300 transition-colors hover:text-white"
            >
              See how it works
              <span aria-hidden className="transition-transform group-hover:translate-x-1">
                →
              </span>
            </a>
          </motion.div>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, x: 24, scale: 0.97 }}
          animate={{ opacity: 1, x: 0, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.2, ease: "easeOut" }}
        >
          <HeroPreview />
        </motion.div>
      </div>
    </section>
  );
}

function HeroPreview() {
  return (
    <motion.div
      className="relative"
      animate={{ y: [0, -8, 0] }}
      transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
    >
      <div aria-hidden className="absolute -inset-6 -z-10 rounded-md bg-accent/10 blur-3xl" />
      <div className="rounded-md border border-slate-200 bg-white p-6 shadow-2xl shadow-black/50">
        <div className="mb-5 flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-medium tracking-wide text-slate-400 uppercase">
              Sample analysis — illustrative
            </p>
            <p className="mt-1 text-sm font-semibold text-ink-900">
              NHAI — Administrative Block, Package 4
            </p>
          </div>
          <div className="flex-none">
            <DecisionBadge decision="Conditional-Go" />
          </div>
        </div>
        <div className="flex flex-col items-center gap-6 border-t border-slate-100 pt-5 sm:flex-row">
          <ScoreGauge score={78} label="Go/No-Go score" colorClass="stroke-status-conditional" />
          <div className="w-full flex-1 space-y-2.5">
            <PreviewCriterion label="Annual turnover" status="pass" />
            <PreviewCriterion label="ISO 9001:2015 certification" status="fail" />
            <PreviewCriterion label="Similar work experience" status="pass" />
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function PreviewCriterion({ label, status }: { label: string; status: "pass" | "fail" }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded border border-slate-100 bg-slate-50 px-3 py-2">
      <span className="text-sm text-slate-600">{label}</span>
      <CriterionStatusBadge status={status} />
    </div>
  );
}

function HowItWorks() {
  return (
    <section id="how-it-works" className="border-b border-white/10 bg-ink-900/40">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <motion.h2
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.6 }}
          transition={{ duration: 0.4 }}
          className="mb-12 text-sm font-semibold tracking-[0.2em] text-slate-400 uppercase"
        >
          How it works
        </motion.h2>
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.2 }}
          className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4"
        >
          {STEPS.map((step) => (
            <motion.div key={step.n} variants={fadeUp} className="border-t border-white/15 pt-4">
              <span className="data-mono text-2xl font-semibold text-accent-bright">
                {step.n}
              </span>
              <h3 className="heading-tight mt-3 font-semibold text-white">{step.title}</h3>
              <p className="mt-2 text-sm text-slate-400">{step.copy}</p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

function Modules() {
  return (
    <section className="border-b border-white/10">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <motion.h2
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.6 }}
          transition={{ duration: 0.4 }}
          className="mb-12 text-sm font-semibold tracking-[0.2em] text-slate-400 uppercase"
        >
          Three modules, one tender
        </motion.h2>
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.15 }}
          className="grid grid-cols-1 gap-6 md:grid-cols-3"
        >
          {MODULES.map((module) => (
            <motion.div
              key={module.name}
              variants={fadeUp}
              whileHover={{ y: -4, borderColor: "rgba(45, 212, 232, 0.4)" }}
              transition={{ duration: 0.2 }}
              className="rounded-md border border-white/10 bg-white/3 p-6"
            >
              <span className="data-mono text-xs text-accent-bright">{module.tag}</span>
              <h3 className="heading-tight mt-3 text-lg font-semibold text-white">
                {module.name}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{module.copy}</p>
              <div className="mt-4 flex flex-wrap gap-1.5">
                {module.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-300"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

function Security() {
  return (
    <section className="border-b border-white/10 bg-ink-900/40">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.4 }}
        transition={{ duration: 0.5 }}
        className="mx-auto max-w-3xl px-6 py-20 text-center"
      >
        <h2 className="mb-4 text-sm font-semibold tracking-[0.2em] text-slate-400 uppercase">
          Data handling
        </h2>
        <p className="text-lg leading-relaxed text-slate-300">
          Tender documents are uploaded to storage your team controls. Every fact the system
          reports is independently re-checked against the source document before it&apos;s
          shown — the system never trusts its own summary without verifying it against the
          real page first. This is a pilot deployment for internal bid-team use; it does not
          hold third-party compliance certifications, and we won&apos;t claim ones it doesn&apos;t.
        </p>
      </motion.div>
    </section>
  );
}

function FinalCta() {
  return (
    <section>
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.6 }}
        transition={{ duration: 0.5 }}
        className="mx-auto max-w-4xl px-6 py-24 text-center"
      >
        <h2 className="heading-tight text-3xl font-medium text-white">
          Stop reading tenders end to end to find out if they&apos;re worth bidding on.
        </h2>
        <div className="mt-8">
          <motion.div
            className="inline-block"
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.98 }}
          >
            <Link
              href="/login"
              className="inline-block rounded bg-accent px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-accent/20 transition-colors hover:bg-cyan-600"
            >
              Sign in to your workspace
            </Link>
          </motion.div>
        </div>
      </motion.div>
    </section>
  );
}

function SiteFooter() {
  return (
    <footer className="border-t border-white/10">
      <div className="mx-auto max-w-6xl px-6 py-8 text-xs text-slate-500">
        Tender AI Platform — advisory tool. Every output is for human review; the system
        never submits, emails, or files anything on your behalf.
      </div>
    </footer>
  );
}
