"use client";

import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import CompanyProfileForm from "@/components/CompanyProfileForm";
import { ApiError, listCompanyProfiles } from "@/lib/api";
import type { CompanyProfileResponse } from "@/lib/types";

export default function CompanyProfilePage() {
  return (
    <AppShell>
      <CompanyProfileManager />
    </AppShell>
  );
}

function CompanyProfileManager() {
  const [profiles, setProfiles] = useState<CompanyProfileResponse[]>([]);
  const [selectedId, setSelectedId] = useState<string | "new" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    listCompanyProfiles()
      .then((data) => {
        setProfiles(data);
        setSelectedId((current) => current ?? (data[0]?.id ?? "new"));
      })
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Load failed"));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const selected =
    selectedId && selectedId !== "new" ? profiles.find((p) => p.id === selectedId) : undefined;

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-ink-900">Company profile</h1>
      <div className="grid grid-cols-1 gap-8 md:grid-cols-[220px_1fr]">
        <div>
          {error && <p className="mb-3 text-sm text-severity-high">{error}</p>}
          <ul className="space-y-1">
            {profiles.map((profile) => (
              <li key={profile.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(profile.id)}
                  className={`w-full rounded-md px-3 py-2 text-left text-sm font-medium ${
                    selectedId === profile.id
                      ? "bg-accent/10 text-accent"
                      : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  {profile.company_name}
                </button>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => setSelectedId("new")}
            className={`mt-2 w-full rounded-md px-3 py-2 text-left text-sm font-medium ${
              selectedId === "new" ? "bg-accent/10 text-accent" : "text-slate-500 hover:bg-slate-100"
            }`}
          >
            + New profile
          </button>
        </div>

        <div className="rounded-md border border-slate-200 bg-white p-6">
          <CompanyProfileForm
            key={selectedId ?? "new"}
            existing={selected}
            onSaved={() => {
              setSelectedId(null);
              refresh();
            }}
          />
        </div>
      </div>
    </div>
  );
}
