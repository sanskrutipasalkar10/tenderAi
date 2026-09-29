"use client";

import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import CompanyProfileForm from "@/components/CompanyProfileForm";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import { BuildingIcon, PlusIcon } from "@/components/ui/icons";
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
      <PageHeader title="Company profile" subtitle="Used to score Go/No-Go eligibility against each tender." />
      <div className="grid grid-cols-1 gap-6 md:grid-cols-[240px_1fr]">
        <Card padding="sm" className="h-fit">
          {error && <p className="mb-3 text-sm text-severity-high">{error}</p>}
          <ul className="space-y-1">
            {profiles.map((profile) => (
              <li key={profile.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(profile.id)}
                  className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm font-medium ${
                    selectedId === profile.id
                      ? "bg-accent/10 text-accent"
                      : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  <BuildingIcon className="h-4 w-4 flex-none" />
                  <span className="truncate">{profile.company_name}</span>
                </button>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => setSelectedId("new")}
            className={`mt-2 flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm font-medium ${
              selectedId === "new" ? "bg-accent/10 text-accent" : "text-slate-500 hover:bg-slate-100"
            }`}
          >
            <PlusIcon className="h-4 w-4 flex-none" />
            New profile
          </button>
        </Card>

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
  );
}
