"use client";

import { useState } from "react";
import { ApiError, createCompanyProfile, updateCompanyProfile } from "@/lib/api";
import type { CompanyProfileResponse, CompanyProfileWrite } from "@/lib/types";

// Simple fields (name, capacity, string lists) get real inputs; the two genuinely
// nested fields (annual_turnover, past_projects) are edited as raw JSON — this is a
// "light" frontend (docs/SPEC.md's own framing for Phase 8), and those two shapes
// vary enough (a dict of year->amount; a list of {name,client,value,year,sector})
// that a real structured editor is more UI than this pass is scoped for. Invalid JSON
// is caught and shown before it ever reaches the API.
function toCommaList(value: string[] | null): string {
  return (value ?? []).join(", ");
}

function fromCommaList(value: string): string[] | null {
  const items = value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return items.length > 0 ? items : null;
}

export default function CompanyProfileForm({
  existing,
  onSaved,
}: {
  existing?: CompanyProfileResponse;
  onSaved: () => void;
}) {
  const [companyName, setCompanyName] = useState(existing?.company_name ?? "");
  const [maxCapacityPct, setMaxCapacityPct] = useState(
    existing?.max_capacity_pct?.toString() ?? "",
  );
  const [certifications, setCertifications] = useState(toCommaList(existing?.certifications ?? null));
  const [geographicPresence, setGeographicPresence] = useState(
    toCommaList(existing?.geographic_presence ?? null),
  );
  const [sectors, setSectors] = useState(toCommaList(existing?.sectors ?? null));
  const [annualTurnoverJson, setAnnualTurnoverJson] = useState(
    existing?.annual_turnover ? JSON.stringify(existing.annual_turnover, null, 2) : "",
  );
  const [pastProjectsJson, setPastProjectsJson] = useState(
    existing?.past_projects ? JSON.stringify(existing.past_projects, null, 2) : "",
  );
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    let annualTurnover: Record<string, number> | null = null;
    let pastProjects: CompanyProfileWrite["past_projects"] = null;
    try {
      if (annualTurnoverJson.trim()) annualTurnover = JSON.parse(annualTurnoverJson);
      if (pastProjectsJson.trim()) pastProjects = JSON.parse(pastProjectsJson);
    } catch {
      setError("Annual turnover / past projects must be valid JSON.");
      return;
    }

    const payload: CompanyProfileWrite = {
      company_name: companyName,
      max_capacity_pct: maxCapacityPct ? Number(maxCapacityPct) : null,
      certifications: fromCommaList(certifications),
      geographic_presence: fromCommaList(geographicPresence),
      sectors: fromCommaList(sectors),
      annual_turnover: annualTurnover,
      past_projects: pastProjects,
    };

    setSaving(true);
    try {
      if (existing) {
        await updateCompanyProfile(existing.id, payload);
      } else {
        await createCompanyProfile(payload);
      }
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save company profile");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Field label="Company name">
        <input
          value={companyName}
          onChange={(e) => setCompanyName(e.target.value)}
          required
          className="w-full rounded border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        />
      </Field>

      <Field label="Max bidding capacity (%)">
        <input
          type="number"
          value={maxCapacityPct}
          onChange={(e) => setMaxCapacityPct(e.target.value)}
          className="w-full rounded border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        />
      </Field>

      <Field label="Certifications (comma-separated)">
        <input
          value={certifications}
          onChange={(e) => setCertifications(e.target.value)}
          className="w-full rounded border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        />
      </Field>

      <Field label="Geographic presence (comma-separated states)">
        <input
          value={geographicPresence}
          onChange={(e) => setGeographicPresence(e.target.value)}
          className="w-full rounded border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        />
      </Field>

      <Field label="Sectors (comma-separated)">
        <input
          value={sectors}
          onChange={(e) => setSectors(e.target.value)}
          className="w-full rounded border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        />
      </Field>

      <Field label='Annual turnover (JSON, e.g. {"2024": 50000000})'>
        <textarea
          value={annualTurnoverJson}
          onChange={(e) => setAnnualTurnoverJson(e.target.value)}
          rows={3}
          className="w-full rounded border border-neutral-300 px-3 py-2 font-mono text-xs dark:border-neutral-700 dark:bg-neutral-900"
        />
      </Field>

      <Field label="Past projects (JSON array)">
        <textarea
          value={pastProjectsJson}
          onChange={(e) => setPastProjectsJson(e.target.value)}
          rows={5}
          className="w-full rounded border border-neutral-300 px-3 py-2 font-mono text-xs dark:border-neutral-700 dark:bg-neutral-900"
        />
      </Field>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <button
        type="submit"
        disabled={saving}
        className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-neutral-300"
      >
        {saving ? "Saving…" : existing ? "Save changes" : "Create profile"}
      </button>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-sm text-neutral-600 dark:text-neutral-400">{label}</label>
      {children}
    </div>
  );
}
