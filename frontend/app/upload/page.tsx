"use client";

import { motion } from "framer-motion";
import { ArrowRight, Check, FileText, UploadCloud, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import Button from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import PageHeader from "@/components/ui/PageHeader";
import Select from "@/components/ui/Select";
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
      <PageHeader
        eyebrow="NEW DOCUMENT / TENDER REVIEW"
        title="Upload a tender"
        subtitle="Bring a new document into your team's review workflow."
      />

      <div className="mx-auto grid max-w-305 gap-12 px-5 py-12 md:grid-cols-[minmax(0,1.65fr)_minmax(260px,0.85fr)] md:px-8">
        <div>
          <div className="mb-5 flex items-center gap-3">
            <span className="step-number">01</span>
            <div>
              <p className="eyebrow">YOUR DOCUMENT</p>
              <h2 className="font-display text-xl font-semibold">Select tender PDF</h2>
            </div>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            className="sr-only"
            onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
            aria-label="Choose tender PDF"
          />
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
            animate={{ scale: dragging ? 1.01 : 1 }}
            transition={{ duration: 0.15 }}
            className={`flex min-h-70 flex-col items-center justify-center border border-dashed px-6 py-8 text-center transition-colors ${
              dragging ? "border-primary bg-accent" : "border-dropzone bg-surface"
            }`}
          >
            <span className="mb-5 flex size-14 items-center justify-center rounded-md bg-accent text-primary">
              <UploadCloud size={26} strokeWidth={1.8} />
            </span>
            <p className="font-display text-lg font-semibold">Drag and drop your tender here</p>
            <p className="mt-1 text-sm text-muted-foreground">or choose a file from your device</p>
            <Button variant="outline" className="mt-6" onClick={() => fileInputRef.current?.click()} icon={<ArrowRight className="h-4 w-4" />}>
              Browse files
            </Button>
            <p className="mt-5 text-xs text-muted-foreground">PDF format</p>
          </motion.div>

          {error && (
            <p role="alert" className="mt-3 text-sm text-severity-high">
              {error}
            </p>
          )}
          {file && (
            <div className="mt-4 flex items-center gap-3 border border-border bg-background p-4">
              <FileText size={22} className="shrink-0 text-primary" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold">{file.name}</p>
                <p className="text-xs text-muted-foreground">{(file.size / (1024 * 1024)).toFixed(2)} MB · Ready to upload</p>
              </div>
              <button
                type="button"
                aria-label="Remove selected file"
                onClick={() => {
                  setFile(null);
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
                className="rounded-md p-1.5 text-muted-foreground hover:text-foreground"
              >
                <X size={18} />
              </button>
            </div>
          )}

          {profiles.length > 0 && (
            <div className="mt-9 border-t border-border pt-7">
              <div className="mb-4 flex items-center gap-3">
                <span className="step-number">02</span>
                <div>
                  <p className="eyebrow">ELIGIBILITY CONTEXT</p>
                  <h2 className="font-display text-xl font-semibold">Company profile</h2>
                </div>
              </div>
              <Field label="Evaluate against a company profile">
                <Select value={companyProfileId} onChange={(e) => setCompanyProfileId(e.target.value)}>
                  <option value="">No company profile (skip Go/No-Go for now)</option>
                  {profiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.company_name}
                    </option>
                  ))}
                </Select>
              </Field>
              <p className="mt-2 text-xs text-muted-foreground">
                Profiles help compare tender requirements with your organisation&apos;s credentials.
              </p>
            </div>
          )}

          <div className="mt-8 flex flex-wrap items-center gap-4 border-t border-border pt-7">
            <Button size="md" disabled={!file} loading={uploading} onClick={handleUpload} icon={<UploadCloud className="h-4 w-4" />}>
              Upload and start analysis
            </Button>
          </div>
        </div>

        <aside className="md:border-l md:border-border md:pl-10">
          <p className="eyebrow mb-3">THE REVIEW PROCESS</p>
          <h2 className="font-display text-2xl font-semibold leading-tight">From document to decision.</h2>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
            A clear path through every tender, with the original pages close at hand.
          </p>
          <div className="mt-8 space-y-0">
            {STEPS.map((step) => (
              <div key={step.n} className="flex gap-4 border-t border-border py-5">
                <span className="font-display text-lg font-semibold text-primary">{step.n}</span>
                <div>
                  <h3 className="font-semibold">{step.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{step.copy}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-5 flex items-center gap-2 text-sm font-medium text-primary">
            <Check size={16} /> Every page read, nothing skipped
          </div>
        </aside>
      </div>
    </div>
  );
}
