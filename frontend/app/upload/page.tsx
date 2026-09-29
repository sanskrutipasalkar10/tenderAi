"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Field from "@/components/ui/Field";
import PageHeader from "@/components/ui/PageHeader";
import Select from "@/components/ui/Select";
import { UploadIcon } from "@/components/ui/icons";
import { ApiError, listCompanyProfiles, uploadDocument } from "@/lib/api";
import { STEPS } from "@/lib/steps";
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
    <div>
      <PageHeader title="Upload a tender" subtitle="50 to 1000+ pages — native text, scans, and tables are all handled." />

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: "easeOut" }}>
          <Card padding="lg">
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
              className={`flex cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed px-6 py-16 text-center ${
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
              <motion.div animate={{ y: dragging ? -4 : 0 }} transition={{ duration: 0.2 }} className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-accent/10 text-accent">
                <UploadIcon className="h-6 w-6" />
              </motion.div>
              <AnimatePresence mode="wait">
                {file ? (
                  <motion.p key="filename" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="font-medium text-ink-900">
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
                <Field label="Evaluate against company profile">
                  <Select value={companyProfileId} onChange={(e) => setCompanyProfileId(e.target.value)}>
                    <option value="">No company profile (skip Go/No-Go for now)</option>
                    {profiles.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.company_name}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
            )}

            {error && <p className="mt-4 text-sm text-severity-high">{error}</p>}

            <Button
              onClick={handleUpload}
              disabled={!file}
              loading={uploading}
              fullWidth
              size="md"
              className="mt-6"
            >
              {uploading ? "Uploading…" : "Upload and start analysis"}
            </Button>
          </Card>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: "easeOut", delay: 0.1 }}>
          <Card padding="lg" tone="subtle">
            <h2 className="mb-4 text-sm font-semibold text-ink-900">What happens next</h2>
            <ol className="space-y-4">
              {STEPS.map((step) => (
                <li key={step.n} className="flex gap-3">
                  <span className="data-mono text-xs font-semibold text-accent">{step.n}</span>
                  <div>
                    <p className="text-sm font-medium text-ink-900">{step.title}</p>
                    <p className="mt-0.5 text-xs text-slate-500">{step.copy}</p>
                  </div>
                </li>
              ))}
            </ol>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
