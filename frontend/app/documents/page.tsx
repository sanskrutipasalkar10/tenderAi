"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import UploadForm from "@/components/UploadForm";
import { ApiError, listDocuments } from "@/lib/api";
import type { DocumentUploadResponse } from "@/lib/types";

const STATUS_STYLES: Record<string, string> = {
  ready: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
};

export default function DocumentsPage() {
  return (
    <AuthGuard>
      <DocumentsList />
    </AuthGuard>
  );
}

function DocumentsList() {
  const [documents, setDocuments] = useState<DocumentUploadResponse[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    listDocuments()
      .then(setDocuments)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : "Could not load documents");
      });
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="mb-4 text-xl font-semibold">Upload a tender</h1>
        <UploadForm onUploaded={refresh} />
      </div>

      <div>
        <h2 className="mb-4 text-lg font-semibold">Documents</h2>
        {error && <p className="text-sm text-red-600">{error}</p>}
        {documents.length === 0 && !error && (
          <p className="text-sm text-neutral-500">No documents uploaded yet.</p>
        )}
        <ul className="divide-y divide-neutral-200 dark:divide-neutral-800">
          {documents.map((doc) => (
            <li key={doc.id} className="flex items-center justify-between py-3">
              <div>
                <Link href={`/documents/${doc.id}`} className="font-medium hover:underline">
                  {doc.filename}
                </Link>
                <p className="text-xs text-neutral-500">
                  {doc.total_pages ?? "?"} pages · uploaded{" "}
                  {new Date(doc.uploaded_at).toLocaleString()}
                </p>
              </div>
              <span
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  STATUS_STYLES[doc.status] ??
                  "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300"
                }`}
              >
                {doc.status}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
