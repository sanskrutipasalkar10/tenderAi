"use client";

import { useState } from "react";
import { ApiError, createCompanyProfile, updateCompanyProfile } from "@/lib/api";
import type { CompanyProfileResponse, CompanyProfilePastProject, CompanyProfileWrite } from "@/lib/types";

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

interface TurnoverRow {
  year: string;
  amount: string;
}

function turnoverToRows(value: Record<string, number> | null): TurnoverRow[] {
  const rows = Object.entries(value ?? {}).map(([year, amount]) => ({ year, amount: String(amount) }));
  return rows.length > 0 ? rows : [{ year: "", amount: "" }];
}

interface ProjectRow {
  name: string;
  client: string;
  value: string;
  year: string;
  sector: string;
}

function projectsToRows(value: CompanyProfilePastProject[] | null): ProjectRow[] {
  const rows = (value ?? []).map((p) => ({
    name: p.name ?? "",
    client: p.client ?? "",
    value: p.value != null ? String(p.value) : "",
    year: p.year != null ? String(p.year) : "",
    sector: p.sector ?? "",
  }));
  return rows.length > 0 ? rows : [{ name: "", client: "", value: "", year: "", sector: "" }];
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
  const [turnoverRows, setTurnoverRows] = useState<TurnoverRow[]>(
    turnoverToRows(existing?.annual_turnover ?? null),
  );
  const [projectRows, setProjectRows] = useState<ProjectRow[]>(
    projectsToRows(existing?.past_projects ?? null),
  );
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const annualTurnover: Record<string, number> = {};
    for (const row of turnoverRows) {
      if (!row.year.trim()) continue;
      const amount = Number(row.amount);
      if (Number.isNaN(amount)) {
        setError(`Turnover amount for ${row.year} must be a number.`);
        return;
      }
      annualTurnover[row.year.trim()] = amount;
    }

    const pastProjects: CompanyProfilePastProject[] = [];
    for (const row of projectRows) {
      if (!row.name.trim()) continue;
      pastProjects.push({
        name: row.name.trim(),
        client: row.client.trim() || null,
        value: row.value.trim() ? Number(row.value) : null,
        year: row.year.trim() ? Number(row.year) : null,
        sector: row.sector.trim() || null,
      });
    }

    const payload: CompanyProfileWrite = {
      company_name: companyName,
      max_capacity_pct: maxCapacityPct ? Number(maxCapacityPct) : null,
      certifications: fromCommaList(certifications),
      geographic_presence: fromCommaList(geographicPresence),
      sectors: fromCommaList(sectors),
      annual_turnover: Object.keys(annualTurnover).length > 0 ? annualTurnover : null,
      past_projects: pastProjects.length > 0 ? pastProjects : null,
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
    <form onSubmit={handleSubmit} className="space-y-8">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Company name">
          <TextInput value={companyName} onChange={setCompanyName} required />
        </Field>
        <Field label="Max bidding capacity (%)">
          <TextInput type="number" value={maxCapacityPct} onChange={setMaxCapacityPct} />
        </Field>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Certifications (comma-separated)">
          <TextInput value={certifications} onChange={setCertifications} />
        </Field>
        <Field label="Geographic presence (states)">
          <TextInput value={geographicPresence} onChange={setGeographicPresence} />
        </Field>
        <Field label="Sectors">
          <TextInput value={sectors} onChange={setSectors} />
        </Field>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-ink-900">Annual turnover, by year</h3>
        <div className="space-y-2">
          {turnoverRows.map((row, i) => (
            <div key={i} className="flex items-center gap-2">
              <TextInput
                placeholder="Year, e.g. 2024"
                value={row.year}
                onChange={(v) =>
                  setTurnoverRows((rows) => rows.map((r, j) => (j === i ? { ...r, year: v } : r)))
                }
              />
              <TextInput
                type="number"
                placeholder="Amount (INR)"
                value={row.amount}
                onChange={(v) =>
                  setTurnoverRows((rows) => rows.map((r, j) => (j === i ? { ...r, amount: v } : r)))
                }
              />
              <RemoveRowButton
                onClick={() => setTurnoverRows((rows) => rows.filter((_, j) => j !== i))}
              />
            </div>
          ))}
        </div>
        <AddRowButton
          label="Add year"
          onClick={() => setTurnoverRows((rows) => [...rows, { year: "", amount: "" }])}
        />
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-ink-900">Past projects</h3>
        <div className="space-y-3">
          {projectRows.map((row, i) => (
            <div key={i} className="rounded-md border border-slate-200 p-4">
              <div className="grid gap-2 sm:grid-cols-5">
                <TextInput
                  placeholder="Project name"
                  value={row.name}
                  onChange={(v) =>
                    setProjectRows((rows) => rows.map((r, j) => (j === i ? { ...r, name: v } : r)))
                  }
                />
                <TextInput
                  placeholder="Client"
                  value={row.client}
                  onChange={(v) =>
                    setProjectRows((rows) => rows.map((r, j) => (j === i ? { ...r, client: v } : r)))
                  }
                />
                <TextInput
                  type="number"
                  placeholder="Value (INR)"
                  value={row.value}
                  onChange={(v) =>
                    setProjectRows((rows) => rows.map((r, j) => (j === i ? { ...r, value: v } : r)))
                  }
                />
                <TextInput
                  type="number"
                  placeholder="Year"
                  value={row.year}
                  onChange={(v) =>
                    setProjectRows((rows) => rows.map((r, j) => (j === i ? { ...r, year: v } : r)))
                  }
                />
                <TextInput
                  placeholder="Sector"
                  value={row.sector}
                  onChange={(v) =>
                    setProjectRows((rows) => rows.map((r, j) => (j === i ? { ...r, sector: v } : r)))
                  }
                />
              </div>
              <RemoveRowButton
                label="Remove project"
                onClick={() => setProjectRows((rows) => rows.filter((_, j) => j !== i))}
              />
            </div>
          ))}
        </div>
        <AddRowButton
          label="Add project"
          onClick={() =>
            setProjectRows((rows) => [
              ...rows,
              { name: "", client: "", value: "", year: "", sector: "" },
            ])
          }
        />
      </div>

      {error && <p className="text-sm text-severity-high">{error}</p>}

      <button
        type="submit"
        disabled={saving}
        className="rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-white hover:bg-cyan-600 disabled:bg-slate-300"
      >
        {saving ? "Saving…" : existing ? "Save changes" : "Create profile"}
      </button>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-ink-900">{label}</label>
      {children}
    </div>
  );
}

function TextInput({
  value,
  onChange,
  type = "text",
  placeholder,
  required,
}: {
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      required={required}
      className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-ink-900 focus:border-accent focus:outline-none"
    />
  );
}

function AddRowButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="mt-2 text-sm font-medium text-accent hover:underline"
    >
      + {label}
    </button>
  );
}

function RemoveRowButton({ label, onClick }: { label?: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-sm text-slate-400 hover:text-severity-high"
    >
      {label ?? "Remove"}
    </button>
  );
}
