"use client";

import { useEffect, useState } from "react";
import { ApiError, listCompanyProfiles, uploadDocument } from "@/lib/api";
import type { CompanyProfileResponse } from "@/lib/types";

export default function UploadForm({ onUploaded }: { onUploaded: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [companyProfileId, setCompanyProfileId] = useState<string>("");
  const [profiles, setProfiles] = useState<CompanyProfileResponse[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Best-effort — an upload works with no company profile selected too (go_no_go
    // just can't run yet, per REQUIRED_PROFILE_FIELDS/Conditional-Go), so a failure
    // to load the list here shouldn't block uploading.
    listCompanyProfiles()
      .then(setProfiles)
      .catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadDocument(file, companyProfileId || undefined);
      setFile(null);
      onUploaded();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-center gap-3">
      <input
        type="file"
        accept="application/pdf"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="text-sm"
      />
      {profiles.length > 0 && (
        <select
          value={companyProfileId}
          onChange={(e) => setCompanyProfileId(e.target.value)}
          className="rounded border border-neutral-300 px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        >
          <option value="">No company profile (skip Go/No-Go for now)</option>
          {profiles.map((p) => (
            <option key={p.id} value={p.id}>
              {p.company_name}
            </option>
          ))}
        </select>
      )}
      <button
        type="submit"
        disabled={!file || uploading}
        className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-neutral-300 dark:disabled:bg-neutral-700"
      >
        {uploading ? "Uploading…" : "Upload tender"}
      </button>
      {error && <span className="text-sm text-red-600">{error}</span>}
    </form>
  );
}
