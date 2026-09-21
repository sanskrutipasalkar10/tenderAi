"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import { ApiError, listCompanyProfiles, uploadDocument } from "@/lib/api";
import type { CompanyProfileResponse } from "@/lib/types";

export default function UploadPage() {
  return (
    <AppShell>
      <UploadFlow />
    </AppShell>
  );
}

function UploadFlow() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [companyProfileId, setCompanyProfileId] = useState("");
  const [profiles, setProfiles] = useState<CompanyProfileResponse[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    listCompanyProfiles()
      .then(setProfiles)
      .catch(() => {});
  }, []);

  function pickFile(f: File | null) {
    if (f && f.type !== "application/pdf") {
      setError("Only PDF files are accepted.");
      return;
    }
    setError(null);
    setFile(f);
  }

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const doc = await uploadDocument(file, companyProfileId || undefined);
      // A real URL, not local component state — landing here means the browser's
      // back/forward buttons and page reloads always re-sync to the backend's actual
      // persisted status (see ProcessingPipeline), instead of an ephemeral "just
      // uploaded" view that a back-navigation would silently lose.
      router.push(`/documents/${doc.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
      setUploading(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="mx-auto max-w-2xl"
    >
      <h1 className="text-2xl font-semibold text-ink-900">Upload a tender</h1>
      <p className="mt-1 text-sm text-slate-500">
        50 to 1000+ pages — native text, scans, and tables are all handled.
      </p>

      <motion.div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          pickFile(e.dataTransfer.files[0] ?? null);
        }}
        onClick={() => fileInputRef.current?.click()}
        animate={{
          scale: dragging ? 1.015 : 1,
          borderColor: dragging ? "var(--color-accent)" : "var(--color-slate-300, #cbd5e1)",
        }}
        transition={{ duration: 0.15 }}
        className={`mt-8 flex cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed px-6 py-16 text-center ${
          dragging ? "bg-accent/5" : "bg-white hover:border-slate-400"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
        />
        <motion.svg
          animate={{ y: dragging ? -4 : 0 }}
          transition={{ duration: 0.2 }}
          className="mb-4 h-10 w-10 text-slate-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M12 16.5V4.5m0 0L7 9.5m5-5l5 5M4.5 16.5v3a2 2 0 002 2h11a2 2 0 002-2v-3"
          />
        </motion.svg>
        <AnimatePresence mode="wait">
          {file ? (
            <motion.p
              key="filename"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="font-medium text-ink-900"
            >
              {file.name}
            </motion.p>
          ) : (
            <motion.div key="placeholder" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <p className="font-medium text-ink-900">Drag and drop a tender PDF here</p>
              <p className="mt-1 text-sm text-slate-500">or click to browse</p>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {profiles.length > 0 && (
        <div className="mt-6">
          <label className="mb-1 block text-sm font-medium text-ink-900">
            Evaluate against company profile
          </label>
          <select
            value={companyProfileId}
            onChange={(e) => setCompanyProfileId(e.target.value)}
            className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            <option value="">No company profile (skip Go/No-Go for now)</option>
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.company_name}
              </option>
            ))}
          </select>
        </div>
      )}

      {error && <p className="mt-4 text-sm text-severity-high">{error}</p>}

      <motion.button
        type="button"
        onClick={handleUpload}
        disabled={!file || uploading}
        whileHover={file && !uploading ? { scale: 1.01 } : undefined}
        whileTap={file && !uploading ? { scale: 0.99 } : undefined}
        className="mt-6 w-full rounded-md bg-accent px-5 py-3 text-sm font-semibold text-white hover:bg-cyan-600 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
      >
        {uploading ? (
          <span className="inline-flex items-center gap-2">
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
            Uploading…
          </span>
        ) : (
          "Upload and start analysis"
        )}
      </motion.button>
    </motion.div>
  );
}
