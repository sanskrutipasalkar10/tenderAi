"use client";

import { useCallback, useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import CompanyProfileForm from "@/components/CompanyProfileForm";
import { ApiError, listCompanyProfiles } from "@/lib/api";
import type { CompanyProfileResponse } from "@/lib/types";

export default function CompanyProfilePage() {
  return (
    <AuthGuard>
      <CompanyProfileManager />
    </AuthGuard>
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
    <div className="grid grid-cols-1 gap-8 md:grid-cols-[220px_1fr]">
      <div>
        <h1 className="mb-4 text-xl font-semibold">Company profiles</h1>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <ul className="space-y-1">
          {profiles.map((profile) => (
            <li key={profile.id}>
              <button
                type="button"
                onClick={() => setSelectedId(profile.id)}
                className={`w-full rounded px-2 py-1.5 text-left text-sm ${
                  selectedId === profile.id
                    ? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                    : "hover:bg-neutral-100 dark:hover:bg-neutral-800"
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
          className={`mt-2 w-full rounded px-2 py-1.5 text-left text-sm ${
            selectedId === "new"
              ? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
              : "text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
          }`}
        >
          + New profile
        </button>
      </div>

      <div>
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
