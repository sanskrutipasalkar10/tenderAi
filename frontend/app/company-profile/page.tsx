"use client";

import { Building2, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import CompanyProfileForm from "@/components/CompanyProfileForm";
import Button from "@/components/ui/Button";
import PageHeader from "@/components/ui/PageHeader";
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
      <PageHeader
        eyebrow="ORGANISATION / ELIGIBILITY"
        title="Company profiles"
        subtitle="The credentials behind every Go/No-Go assessment."
      />
      <div className="mx-auto grid max-w-305 gap-8 px-5 py-10 md:grid-cols-[235px_minmax(0,1fr)] md:px-8">
        <aside>
          <p className="eyebrow mb-4">YOUR PROFILES</p>
          {error && <p className="mb-3 text-sm text-severity-high">{error}</p>}
          <div className="border-y border-border">
            {profiles.map((profile) => (
              <Button
                key={profile.id}
                variant="ghost"
                onClick={() => setSelectedId(profile.id)}
                className={`my-1 w-full justify-start overflow-hidden text-left ${
                  selectedId === profile.id ? "bg-accent text-primary" : ""
                }`}
                icon={<Building2 className="h-4 w-4 shrink-0" />}
              >
                <span className="truncate">{profile.company_name}</span>
              </Button>
            ))}
          </div>
          <Button
            variant="outline"
            className="mt-4 w-full justify-start"
            onClick={() => setSelectedId("new")}
            icon={<Plus className="h-4 w-4" />}
          >
            New profile
          </Button>
        </aside>

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
