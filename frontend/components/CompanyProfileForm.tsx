"use client";

import { useState } from "react";
import { ApiError, createCompanyProfile, updateCompanyProfile } from "@/lib/api";
import type {
  CompanyProfileBankDetails,
  CompanyProfileDirector,
  CompanyProfileEmploymentCount,
  CompanyProfileGovernmentGrant,
  CompanyProfileMsmeClassification,
  CompanyProfilePastProject,
  CompanyProfileResponse,
  CompanyProfileWrite,
} from "@/lib/types";

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

function rowsToTurnover(rows: TurnoverRow[]): Record<string, number> | null {
  const result: Record<string, number> = {};
  for (const row of rows) {
    if (!row.year.trim()) continue;
    const amount = Number(row.amount);
    if (!Number.isNaN(amount)) result[row.year.trim()] = amount;
  }
  return Object.keys(result).length > 0 ? result : null;
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

interface MsmeRow {
  year: string;
  type: string;
}

function msmeToRows(value: CompanyProfileMsmeClassification[] | null): MsmeRow[] {
  const rows = (value ?? []).map((m) => ({ year: m.year ?? "", type: m.type ?? "" }));
  return rows.length > 0 ? rows : [{ year: "", type: "" }];
}

interface DirectorRow {
  name: string;
  din_or_pan: string;
  designation: string;
  category: string;
  appointed: string;
}

function directorsToRows(value: CompanyProfileDirector[] | null): DirectorRow[] {
  const rows = (value ?? []).map((d) => ({
    name: d.name ?? "",
    din_or_pan: d.din_or_pan ?? "",
    designation: d.designation ?? "",
    category: d.category ?? "",
    appointed: d.appointed ?? "",
  }));
  return rows.length > 0 ? rows : [{ name: "", din_or_pan: "", designation: "", category: "", appointed: "" }];
}

interface GrantRow {
  department: string;
  source: string;
  fy: string;
  amount: string;
  purpose: string;
}

function grantsToRows(value: CompanyProfileGovernmentGrant[] | null): GrantRow[] {
  const rows = (value ?? []).map((g) => ({
    department: g.department ?? "",
    source: g.source ?? "",
    fy: g.fy ?? "",
    amount: g.amount != null ? String(g.amount) : "",
    purpose: g.purpose ?? "",
  }));
  return rows.length > 0
    ? rows
    : [{ department: "", source: "", fy: "", amount: "", purpose: "" }];
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
  const [turnoverSource, setTurnoverSource] = useState(existing?.turnover_source ?? "");
  const [projectRows, setProjectRows] = useState<ProjectRow[]>(
    projectsToRows(existing?.past_projects ?? null),
  );

  // --- statutory identity (migration 0003) ---
  const [cin, setCin] = useState(existing?.cin ?? "");
  const [rocNumber, setRocNumber] = useState(existing?.roc_number ?? "");
  const [section8LicenceNumber, setSection8LicenceNumber] = useState(
    existing?.section8_licence_number ?? "",
  );
  const [dateOfIncorporation, setDateOfIncorporation] = useState(
    existing?.date_of_incorporation ?? "",
  );
  const [pan, setPan] = useState(existing?.pan ?? "");
  const [gstin, setGstin] = useState(existing?.gstin ?? "");
  const [udyamRegistrationNumber, setUdyamRegistrationNumber] = useState(
    existing?.udyam_registration_number ?? "",
  );
  const [ngoDarpanId, setNgoDarpanId] = useState(existing?.ngo_darpan_id ?? "");
  const [authorisedCapitalInr, setAuthorisedCapitalInr] = useState(
    existing?.authorised_capital_inr?.toString() ?? "",
  );
  const [paidUpCapitalInr, setPaidUpCapitalInr] = useState(
    existing?.paid_up_capital_inr?.toString() ?? "",
  );
  const [netWorthInr, setNetWorthInr] = useState(existing?.net_worth_inr?.toString() ?? "");

  // --- repeatable MDM sections ---
  const [msmeRows, setMsmeRows] = useState<MsmeRow[]>(
    msmeToRows(existing?.msme_classification ?? null),
  );
  const [directorRows, setDirectorRows] = useState<DirectorRow[]>(
    directorsToRows(existing?.directors ?? null),
  );
  const [grantRows, setGrantRows] = useState<GrantRow[]>(
    grantsToRows(existing?.government_grants ?? null),
  );
  const [unconfirmedTurnoverRows, setUnconfirmedTurnoverRows] = useState<TurnoverRow[]>(
    turnoverToRows(existing?.unconfirmed_org_turnover_inr ?? null),
  );

  // --- fixed sub-objects ---
  const [bankName, setBankName] = useState(existing?.bank_details?.bank ?? "");
  const [bankIfsc, setBankIfsc] = useState(existing?.bank_details?.ifsc ?? "");
  const [bankAccount, setBankAccount] = useState(existing?.bank_details?.account ?? "");
  const [employeesMale, setEmployeesMale] = useState(
    existing?.employment_count?.male?.toString() ?? "",
  );
  const [employeesFemale, setEmployeesFemale] = useState(
    existing?.employment_count?.female?.toString() ?? "",
  );
  const [employeesOther, setEmployeesOther] = useState(
    existing?.employment_count?.other?.toString() ?? "",
  );

  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const annualTurnover = rowsToTurnover(turnoverRows);
    if (annualTurnover && !turnoverSource.trim()) {
      setError("Turnover source is required whenever annual turnover is set (which document the figures came from).");
      return;
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

    const msmeClassification: CompanyProfileMsmeClassification[] = msmeRows
      .filter((r) => r.year.trim() || r.type.trim())
      .map((r) => ({ year: r.year.trim(), type: r.type.trim() }));

    const directors: CompanyProfileDirector[] = directorRows
      .filter((r) => r.name.trim())
      .map((r) => ({
        name: r.name.trim(),
        din_or_pan: r.din_or_pan.trim() || null,
        designation: r.designation.trim() || null,
        category: r.category.trim() || null,
        appointed: r.appointed.trim() || null,
      }));

    const governmentGrants: CompanyProfileGovernmentGrant[] = grantRows
      .filter((r) => r.department.trim())
      .map((r) => ({
        department: r.department.trim(),
        source: r.source.trim() || null,
        fy: r.fy.trim() || null,
        amount: r.amount.trim() ? Number(r.amount) : null,
        purpose: r.purpose.trim() || null,
      }));

    const bankDetails: CompanyProfileBankDetails | null =
      bankName.trim() || bankIfsc.trim() || bankAccount.trim()
        ? { bank: bankName.trim() || null, ifsc: bankIfsc.trim() || null, account: bankAccount.trim() || null }
        : null;

    const employmentCount: CompanyProfileEmploymentCount | null =
      employeesMale.trim() || employeesFemale.trim() || employeesOther.trim()
        ? {
            male: employeesMale.trim() ? Number(employeesMale) : null,
            female: employeesFemale.trim() ? Number(employeesFemale) : null,
            other: employeesOther.trim() ? Number(employeesOther) : null,
          }
        : null;

    const payload: CompanyProfileWrite = {
      company_name: companyName,
      max_capacity_pct: maxCapacityPct ? Number(maxCapacityPct) : null,
      certifications: fromCommaList(certifications),
      geographic_presence: fromCommaList(geographicPresence),
      sectors: fromCommaList(sectors),
      annual_turnover: annualTurnover,
      turnover_source: annualTurnover ? turnoverSource.trim() : null,
      past_projects: pastProjects.length > 0 ? pastProjects : null,
      cin: cin.trim() || null,
      roc_number: rocNumber.trim() || null,
      section8_licence_number: section8LicenceNumber.trim() || null,
      date_of_incorporation: dateOfIncorporation.trim() || null,
      pan: pan.trim() || null,
      gstin: gstin.trim() || null,
      udyam_registration_number: udyamRegistrationNumber.trim() || null,
      msme_classification: msmeClassification.length > 0 ? msmeClassification : null,
      ngo_darpan_id: ngoDarpanId.trim() || null,
      authorised_capital_inr: authorisedCapitalInr.trim() ? Number(authorisedCapitalInr) : null,
      paid_up_capital_inr: paidUpCapitalInr.trim() ? Number(paidUpCapitalInr) : null,
      net_worth_inr: netWorthInr.trim() ? Number(netWorthInr) : null,
      unconfirmed_org_turnover_inr: rowsToTurnover(unconfirmedTurnoverRows),
      directors: directors.length > 0 ? directors : null,
      bank_details: bankDetails,
      employment_count: employmentCount,
      government_grants: governmentGrants.length > 0 ? governmentGrants : null,
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
        <h3 className="mb-3 text-sm font-semibold text-ink-900">Statutory identity</h3>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="CIN">
            <TextInput value={cin} onChange={setCin} />
          </Field>
          <Field label="ROC number">
            <TextInput value={rocNumber} onChange={setRocNumber} />
          </Field>
          <Field label="Section 8 licence number">
            <TextInput value={section8LicenceNumber} onChange={setSection8LicenceNumber} />
          </Field>
          <Field label="Date of incorporation">
            <TextInput type="date" value={dateOfIncorporation} onChange={setDateOfIncorporation} />
          </Field>
          <Field label="PAN">
            <TextInput value={pan} onChange={setPan} />
          </Field>
          <Field label="GSTIN">
            <TextInput value={gstin} onChange={setGstin} />
          </Field>
          <Field label="Udyam registration number">
            <TextInput value={udyamRegistrationNumber} onChange={setUdyamRegistrationNumber} />
          </Field>
          <Field label="NGO Darpan ID">
            <TextInput value={ngoDarpanId} onChange={setNgoDarpanId} />
          </Field>
        </div>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-ink-900">Capital &amp; net worth</h3>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Authorised capital (INR)">
            <TextInput type="number" value={authorisedCapitalInr} onChange={setAuthorisedCapitalInr} />
          </Field>
          <Field label="Paid-up capital (INR)">
            <TextInput type="number" value={paidUpCapitalInr} onChange={setPaidUpCapitalInr} />
          </Field>
          <Field label="Net worth (INR)">
            <TextInput type="number" value={netWorthInr} onChange={setNetWorthInr} />
          </Field>
        </div>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-ink-900">Annual turnover, by year</h3>
        <p className="mb-2 text-xs text-slate-500">
          Confirmed turnover only — these figures drive Financial Capability scoring, so a
          source document is required.
        </p>
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
        <div className="mt-3 max-w-sm">
          <Field label="Turnover source (which document these figures came from)">
            <TextInput
              placeholder="e.g. udyam_filing, audited_financials"
              value={turnoverSource}
              onChange={setTurnoverSource}
            />
          </Field>
        </div>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-amber-800">
          Unconfirmed organizational turnover, by year
        </h3>
        <p className="mb-2 text-xs text-amber-700">
          Retained for reference only — not tied to a confirmed source document for this
          legal entity. Never used for Financial Capability scoring.
        </p>
        <div className="space-y-2 rounded-md border border-amber-300 bg-amber-50 p-3">
          {unconfirmedTurnoverRows.map((row, i) => (
            <div key={i} className="flex items-center gap-2">
              <TextInput
                placeholder="Year, e.g. 2024_25_projected"
                value={row.year}
                onChange={(v) =>
                  setUnconfirmedTurnoverRows((rows) =>
                    rows.map((r, j) => (j === i ? { ...r, year: v } : r)),
                  )
                }
              />
              <TextInput
                type="number"
                placeholder="Amount (INR)"
                value={row.amount}
                onChange={(v) =>
                  setUnconfirmedTurnoverRows((rows) =>
                    rows.map((r, j) => (j === i ? { ...r, amount: v } : r)),
                  )
                }
              />
              <RemoveRowButton
                onClick={() =>
                  setUnconfirmedTurnoverRows((rows) => rows.filter((_, j) => j !== i))
                }
              />
            </div>
          ))}
        </div>
        <AddRowButton
          label="Add year"
          onClick={() =>
            setUnconfirmedTurnoverRows((rows) => [...rows, { year: "", amount: "" }])
          }
        />
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-ink-900">MSME classification, by year</h3>
        <div className="space-y-2">
          {msmeRows.map((row, i) => (
            <div key={i} className="flex items-center gap-2">
              <TextInput
                placeholder="Year, e.g. 2024-25"
                value={row.year}
                onChange={(v) =>
                  setMsmeRows((rows) => rows.map((r, j) => (j === i ? { ...r, year: v } : r)))
                }
              />
              <TextInput
                placeholder="Type, e.g. Micro"
                value={row.type}
                onChange={(v) =>
                  setMsmeRows((rows) => rows.map((r, j) => (j === i ? { ...r, type: v } : r)))
                }
              />
              <RemoveRowButton onClick={() => setMsmeRows((rows) => rows.filter((_, j) => j !== i))} />
            </div>
          ))}
        </div>
        <AddRowButton
          label="Add year"
          onClick={() => setMsmeRows((rows) => [...rows, { year: "", type: "" }])}
        />
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-ink-900">Directors</h3>
        <div className="space-y-3">
          {directorRows.map((row, i) => (
            <div key={i} className="rounded-md border border-slate-200 p-4">
              <div className="grid gap-2 sm:grid-cols-5">
                <TextInput
                  placeholder="Name"
                  value={row.name}
                  onChange={(v) =>
                    setDirectorRows((rows) => rows.map((r, j) => (j === i ? { ...r, name: v } : r)))
                  }
                />
                <TextInput
                  placeholder="DIN / PAN"
                  value={row.din_or_pan}
                  onChange={(v) =>
                    setDirectorRows((rows) =>
                      rows.map((r, j) => (j === i ? { ...r, din_or_pan: v } : r)),
                    )
                  }
                />
                <TextInput
                  placeholder="Designation"
                  value={row.designation}
                  onChange={(v) =>
                    setDirectorRows((rows) =>
                      rows.map((r, j) => (j === i ? { ...r, designation: v } : r)),
                    )
                  }
                />
                <TextInput
                  placeholder="Category"
                  value={row.category}
                  onChange={(v) =>
                    setDirectorRows((rows) => rows.map((r, j) => (j === i ? { ...r, category: v } : r)))
                  }
                />
                <TextInput
                  placeholder="Appointed (date)"
                  value={row.appointed}
                  onChange={(v) =>
                    setDirectorRows((rows) =>
                      rows.map((r, j) => (j === i ? { ...r, appointed: v } : r)),
                    )
                  }
                />
              </div>
              <RemoveRowButton
                label="Remove director"
                onClick={() => setDirectorRows((rows) => rows.filter((_, j) => j !== i))}
              />
            </div>
          ))}
        </div>
        <AddRowButton
          label="Add director"
          onClick={() =>
            setDirectorRows((rows) => [
              ...rows,
              { name: "", din_or_pan: "", designation: "", category: "", appointed: "" },
            ])
          }
        />
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-ink-900">Government grants</h3>
        <div className="space-y-3">
          {grantRows.map((row, i) => (
            <div key={i} className="rounded-md border border-slate-200 p-4">
              <div className="grid gap-2 sm:grid-cols-5">
                <TextInput
                  placeholder="Department"
                  value={row.department}
                  onChange={(v) =>
                    setGrantRows((rows) => rows.map((r, j) => (j === i ? { ...r, department: v } : r)))
                  }
                />
                <TextInput
                  placeholder="Source"
                  value={row.source}
                  onChange={(v) =>
                    setGrantRows((rows) => rows.map((r, j) => (j === i ? { ...r, source: v } : r)))
                  }
                />
                <TextInput
                  placeholder="FY, e.g. 2023-24"
                  value={row.fy}
                  onChange={(v) =>
                    setGrantRows((rows) => rows.map((r, j) => (j === i ? { ...r, fy: v } : r)))
                  }
                />
                <TextInput
                  type="number"
                  placeholder="Amount (INR)"
                  value={row.amount}
                  onChange={(v) =>
                    setGrantRows((rows) => rows.map((r, j) => (j === i ? { ...r, amount: v } : r)))
                  }
                />
                <TextInput
                  placeholder="Purpose"
                  value={row.purpose}
                  onChange={(v) =>
                    setGrantRows((rows) => rows.map((r, j) => (j === i ? { ...r, purpose: v } : r)))
                  }
                />
              </div>
              <RemoveRowButton
                label="Remove grant"
                onClick={() => setGrantRows((rows) => rows.filter((_, j) => j !== i))}
              />
            </div>
          ))}
        </div>
        <AddRowButton
          label="Add grant"
          onClick={() =>
            setGrantRows((rows) => [
              ...rows,
              { department: "", source: "", fy: "", amount: "", purpose: "" },
            ])
          }
        />
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-ink-900">Bank details</h3>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Bank">
            <TextInput value={bankName} onChange={setBankName} />
          </Field>
          <Field label="IFSC">
            <TextInput value={bankIfsc} onChange={setBankIfsc} />
          </Field>
          <Field label="Account number">
            <TextInput value={bankAccount} onChange={setBankAccount} />
          </Field>
        </div>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-ink-900">Employment count</h3>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Male">
            <TextInput type="number" value={employeesMale} onChange={setEmployeesMale} />
          </Field>
          <Field label="Female">
            <TextInput type="number" value={employeesFemale} onChange={setEmployeesFemale} />
          </Field>
          <Field label="Other">
            <TextInput type="number" value={employeesOther} onChange={setEmployeesOther} />
          </Field>
        </div>
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
