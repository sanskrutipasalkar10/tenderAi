"use client";

import { useState } from "react";
import { ApiError, createCompanyProfile, updateCompanyProfile } from "@/lib/api";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Field from "@/components/ui/Field";
import Input from "@/components/ui/Input";
import { PlusIcon, TrashIcon } from "@/components/ui/icons";
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
    <form onSubmit={handleSubmit} className="space-y-6">
      <Card>
        <h3 className="mb-4 text-sm font-semibold text-ink-900">Company basics</h3>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Company name">
            <Input value={companyName} onChange={(e) => setCompanyName(e.target.value)} required />
          </Field>
          <Field label="Max bidding capacity (%)">
            <Input
              type="number"
              value={maxCapacityPct}
              onChange={(e) => setMaxCapacityPct(e.target.value)}
            />
          </Field>
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <Field label="Certifications (comma-separated)">
            <Input value={certifications} onChange={(e) => setCertifications(e.target.value)} />
          </Field>
          <Field label="Geographic presence (states)">
            <Input value={geographicPresence} onChange={(e) => setGeographicPresence(e.target.value)} />
          </Field>
          <Field label="Sectors">
            <Input value={sectors} onChange={(e) => setSectors(e.target.value)} />
          </Field>
        </div>
      </Card>

      <Card>
        <h3 className="mb-4 text-sm font-semibold text-ink-900">Statutory identity</h3>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="CIN">
            <Input value={cin} onChange={(e) => setCin(e.target.value)} />
          </Field>
          <Field label="ROC number">
            <Input value={rocNumber} onChange={(e) => setRocNumber(e.target.value)} />
          </Field>
          <Field label="Section 8 licence number">
            <Input value={section8LicenceNumber} onChange={(e) => setSection8LicenceNumber(e.target.value)} />
          </Field>
          <Field label="Date of incorporation" hint="DD-MM-YYYY">
            <Input
              placeholder="DD-MM-YYYY"
              value={dateOfIncorporation}
              onChange={(e) => setDateOfIncorporation(e.target.value)}
            />
          </Field>
          <Field label="PAN">
            <Input value={pan} onChange={(e) => setPan(e.target.value)} />
          </Field>
          <Field label="GSTIN">
            <Input value={gstin} onChange={(e) => setGstin(e.target.value)} />
          </Field>
          <Field label="Udyam registration number">
            <Input value={udyamRegistrationNumber} onChange={(e) => setUdyamRegistrationNumber(e.target.value)} />
          </Field>
          <Field label="NGO Darpan ID">
            <Input value={ngoDarpanId} onChange={(e) => setNgoDarpanId(e.target.value)} />
          </Field>
        </div>
      </Card>

      <Card>
        <h3 className="mb-4 text-sm font-semibold text-ink-900">Capital &amp; net worth</h3>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Authorised capital (INR)">
            <Input type="number" value={authorisedCapitalInr} onChange={(e) => setAuthorisedCapitalInr(e.target.value)} />
          </Field>
          <Field label="Paid-up capital (INR)">
            <Input type="number" value={paidUpCapitalInr} onChange={(e) => setPaidUpCapitalInr(e.target.value)} />
          </Field>
          <Field label="Net worth (INR)">
            <Input type="number" value={netWorthInr} onChange={(e) => setNetWorthInr(e.target.value)} />
          </Field>
        </div>
      </Card>

      <Card>
        <h3 className="mb-1 text-sm font-semibold text-ink-900">Annual turnover, by year</h3>
        <p className="mb-3 text-xs text-slate-500">
          Confirmed turnover only — these figures drive Financial Capability scoring, so a
          source document is required.
        </p>
        <div className="space-y-2">
          {turnoverRows.map((row, i) => (
            <div key={i} className="flex items-center gap-2">
              <Input
                placeholder="Year, e.g. 2024"
                value={row.year}
                onChange={(e) =>
                  setTurnoverRows((rows) => rows.map((r, j) => (j === i ? { ...r, year: e.target.value } : r)))
                }
              />
              <Input
                type="number"
                placeholder="Amount (INR)"
                value={row.amount}
                onChange={(e) =>
                  setTurnoverRows((rows) => rows.map((r, j) => (j === i ? { ...r, amount: e.target.value } : r)))
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
        <div className="mt-4 max-w-sm">
          <Field label="Turnover source (which document these figures came from)">
            <Input
              placeholder="e.g. udyam_filing, audited_financials"
              value={turnoverSource}
              onChange={(e) => setTurnoverSource(e.target.value)}
            />
          </Field>
        </div>
      </Card>

      <Card tone="warning">
        <h3 className="mb-1 text-sm font-semibold text-severity-medium">
          Unconfirmed organizational turnover, by year
        </h3>
        <p className="mb-3 text-xs text-severity-medium/80">
          Retained for reference only — not tied to a confirmed source document for this
          legal entity. Never used for Financial Capability scoring.
        </p>
        <div className="space-y-2">
          {unconfirmedTurnoverRows.map((row, i) => (
            <div key={i} className="flex items-center gap-2">
              <Input
                placeholder="Year, e.g. 2024_25_projected"
                value={row.year}
                onChange={(e) =>
                  setUnconfirmedTurnoverRows((rows) =>
                    rows.map((r, j) => (j === i ? { ...r, year: e.target.value } : r)),
                  )
                }
              />
              <Input
                type="number"
                placeholder="Amount (INR)"
                value={row.amount}
                onChange={(e) =>
                  setUnconfirmedTurnoverRows((rows) =>
                    rows.map((r, j) => (j === i ? { ...r, amount: e.target.value } : r)),
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
      </Card>

      <Card>
        <h3 className="mb-3 text-sm font-semibold text-ink-900">MSME classification, by year</h3>
        <div className="space-y-2">
          {msmeRows.map((row, i) => (
            <div key={i} className="flex items-center gap-2">
              <Input
                placeholder="Year, e.g. 2024-25"
                value={row.year}
                onChange={(e) =>
                  setMsmeRows((rows) => rows.map((r, j) => (j === i ? { ...r, year: e.target.value } : r)))
                }
              />
              <Input
                placeholder="Type, e.g. Micro"
                value={row.type}
                onChange={(e) =>
                  setMsmeRows((rows) => rows.map((r, j) => (j === i ? { ...r, type: e.target.value } : r)))
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
      </Card>

      <Card>
        <h3 className="mb-3 text-sm font-semibold text-ink-900">Directors</h3>
        <div className="space-y-3">
          {directorRows.map((row, i) => (
            <div key={i} className="rounded-md border border-slate-100 bg-slate-50 p-4">
              <div className="grid gap-2 sm:grid-cols-5">
                <Input
                  placeholder="Name"
                  value={row.name}
                  onChange={(e) =>
                    setDirectorRows((rows) => rows.map((r, j) => (j === i ? { ...r, name: e.target.value } : r)))
                  }
                />
                <Input
                  placeholder="DIN / PAN"
                  value={row.din_or_pan}
                  onChange={(e) =>
                    setDirectorRows((rows) =>
                      rows.map((r, j) => (j === i ? { ...r, din_or_pan: e.target.value } : r)),
                    )
                  }
                />
                <Input
                  placeholder="Designation"
                  value={row.designation}
                  onChange={(e) =>
                    setDirectorRows((rows) =>
                      rows.map((r, j) => (j === i ? { ...r, designation: e.target.value } : r)),
                    )
                  }
                />
                <Input
                  placeholder="Category"
                  value={row.category}
                  onChange={(e) =>
                    setDirectorRows((rows) => rows.map((r, j) => (j === i ? { ...r, category: e.target.value } : r)))
                  }
                />
                <Input
                  placeholder="Appointed (date)"
                  value={row.appointed}
                  onChange={(e) =>
                    setDirectorRows((rows) =>
                      rows.map((r, j) => (j === i ? { ...r, appointed: e.target.value } : r)),
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
      </Card>

      <Card>
        <h3 className="mb-3 text-sm font-semibold text-ink-900">Government grants</h3>
        <div className="space-y-3">
          {grantRows.map((row, i) => (
            <div key={i} className="rounded-md border border-slate-100 bg-slate-50 p-4">
              <div className="grid gap-2 sm:grid-cols-5">
                <Input
                  placeholder="Department"
                  value={row.department}
                  onChange={(e) =>
                    setGrantRows((rows) => rows.map((r, j) => (j === i ? { ...r, department: e.target.value } : r)))
                  }
                />
                <Input
                  placeholder="Source"
                  value={row.source}
                  onChange={(e) =>
                    setGrantRows((rows) => rows.map((r, j) => (j === i ? { ...r, source: e.target.value } : r)))
                  }
                />
                <Input
                  placeholder="FY, e.g. 2023-24"
                  value={row.fy}
                  onChange={(e) =>
                    setGrantRows((rows) => rows.map((r, j) => (j === i ? { ...r, fy: e.target.value } : r)))
                  }
                />
                <Input
                  type="number"
                  placeholder="Amount (INR)"
                  value={row.amount}
                  onChange={(e) =>
                    setGrantRows((rows) => rows.map((r, j) => (j === i ? { ...r, amount: e.target.value } : r)))
                  }
                />
                <Input
                  placeholder="Purpose"
                  value={row.purpose}
                  onChange={(e) =>
                    setGrantRows((rows) => rows.map((r, j) => (j === i ? { ...r, purpose: e.target.value } : r)))
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
      </Card>

      <Card>
        <h3 className="mb-4 text-sm font-semibold text-ink-900">Bank details</h3>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Bank">
            <Input value={bankName} onChange={(e) => setBankName(e.target.value)} />
          </Field>
          <Field label="IFSC">
            <Input value={bankIfsc} onChange={(e) => setBankIfsc(e.target.value)} />
          </Field>
          <Field label="Account number">
            <Input value={bankAccount} onChange={(e) => setBankAccount(e.target.value)} />
          </Field>
        </div>
      </Card>

      <Card>
        <h3 className="mb-4 text-sm font-semibold text-ink-900">Employment count</h3>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Male">
            <Input type="number" value={employeesMale} onChange={(e) => setEmployeesMale(e.target.value)} />
          </Field>
          <Field label="Female">
            <Input type="number" value={employeesFemale} onChange={(e) => setEmployeesFemale(e.target.value)} />
          </Field>
          <Field label="Other">
            <Input type="number" value={employeesOther} onChange={(e) => setEmployeesOther(e.target.value)} />
          </Field>
        </div>
      </Card>

      <Card>
        <h3 className="mb-3 text-sm font-semibold text-ink-900">Past projects</h3>
        <div className="space-y-3">
          {projectRows.map((row, i) => (
            <div key={i} className="rounded-md border border-slate-100 bg-slate-50 p-4">
              <div className="grid gap-2 sm:grid-cols-5">
                <Input
                  placeholder="Project name"
                  value={row.name}
                  onChange={(e) =>
                    setProjectRows((rows) => rows.map((r, j) => (j === i ? { ...r, name: e.target.value } : r)))
                  }
                />
                <Input
                  placeholder="Client"
                  value={row.client}
                  onChange={(e) =>
                    setProjectRows((rows) => rows.map((r, j) => (j === i ? { ...r, client: e.target.value } : r)))
                  }
                />
                <Input
                  type="number"
                  placeholder="Value (INR)"
                  value={row.value}
                  onChange={(e) =>
                    setProjectRows((rows) => rows.map((r, j) => (j === i ? { ...r, value: e.target.value } : r)))
                  }
                />
                <Input
                  type="number"
                  placeholder="Year"
                  value={row.year}
                  onChange={(e) =>
                    setProjectRows((rows) => rows.map((r, j) => (j === i ? { ...r, year: e.target.value } : r)))
                  }
                />
                <Input
                  placeholder="Sector"
                  value={row.sector}
                  onChange={(e) =>
                    setProjectRows((rows) => rows.map((r, j) => (j === i ? { ...r, sector: e.target.value } : r)))
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
      </Card>

      {error && <p className="text-sm text-severity-high">{error}</p>}

      <Button type="submit" loading={saving}>
        {existing ? "Save changes" : "Create profile"}
      </Button>
    </form>
  );
}

function AddRowButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Button variant="ghost" size="xs" className="mt-2 px-0! text-accent hover:text-indigo-700" onClick={onClick} icon={<PlusIcon className="h-3.5 w-3.5" />}>
      {label}
    </Button>
  );
}

function RemoveRowButton({ label, onClick }: { label?: string; onClick: () => void }) {
  return (
    <Button
      variant="ghost"
      size="xs"
      className="text-slate-400 hover:text-severity-high"
      onClick={onClick}
      icon={<TrashIcon className="h-3.5 w-3.5" />}
    >
      {label ?? "Remove"}
    </Button>
  );
}
