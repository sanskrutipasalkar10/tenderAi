"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { ApiError, getPageContent, getPageImageBlob } from "@/lib/api";
import type { PageContentResponse } from "@/lib/types";

// The citation-verification UI (docs/SPEC.md's actual HITL mechanism — there is no
// separate approve/override workflow, docs/DECISIONS.md #3). Every fact/risk/
// criterion the reduce pass produces carries a page_ref; this is what happens when a
// user clicks it — fetch the real source page and show it, so the claim is always one
// click from being checked against the document it came from.
export default function CitationLink({
  documentId,
  pageRef,
  children,
}: {
  documentId: string;
  pageRef: number;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="cursor-pointer rounded bg-blue-50 px-1.5 py-0.5 text-blue-700 underline decoration-dotted underline-offset-2 hover:bg-blue-100 dark:bg-blue-950 dark:text-blue-300 dark:hover:bg-blue-900"
        title={`View source — page ${pageRef}`}
      >
        {children}
        <sup className="ml-0.5 font-semibold">p.{pageRef}</sup>
      </button>
      {open && (
        <PageViewerModal documentId={documentId} pageRef={pageRef} onClose={() => setOpen(false)} />
      )}
    </>
  );
}

function PageViewerModal({
  documentId,
  pageRef,
  onClose,
}: {
  documentId: string;
  pageRef: number;
  onClose: () => void;
}) {
  const [page, setPage] = useState<PageContentResponse | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    getPageContent(documentId, pageRef)
      .then(async (content) => {
        if (cancelled) return;
        setPage(content);
        if (content.has_image) {
          const blob = await getPageImageBlob(documentId, pageRef);
          if (cancelled) return;
          objectUrl = URL.createObjectURL(blob);
          setImageUrl(objectUrl);
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Could not load this page");
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId, pageRef]);

  // Portaled to document.body (docs/DECISIONS.md #57): CitationLink is used inline
  // inside prose (a <p> in RiskList/SynopsisView, a <td> in GoNoGoCard) — rendering
  // the modal's <div>/<pre> content in place, as a normal child, would nest block
  // elements inside a <p>, invalid HTML that React actually warns about (found via a
  // real browser hydration-error console message, not inspection). A portal renders
  // this subtree into <body> instead, keeping the DOM valid regardless of where the
  // citation link itself is used.
  const modal = (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-lg bg-white p-6 shadow-xl dark:bg-neutral-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Source — page {pageRef}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded px-2 py-1 text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {error && <p className="text-red-600">{error}</p>}

        {!error && !page && <p className="text-neutral-500">Loading…</p>}

        {page && (
          <div className="space-y-4">
            <div className="flex gap-3 text-xs text-neutral-500">
              <span>Classification: {page.classification}</span>
              {page.extraction_method && <span>Extracted via: {page.extraction_method}</span>}
              {page.confidence_score !== null && (
                <span>Confidence: {(page.confidence_score * 100).toFixed(0)}%</span>
              )}
            </div>

            {imageUrl && (
              // Authenticated blob: URL (see getPageImageBlob), not a static asset
              // next/image's optimizer can fetch itself — plain <img> is correct here.
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={imageUrl}
                alt={`Scanned page ${pageRef}`}
                className="w-full rounded border border-neutral-200 dark:border-neutral-700"
              />
            )}

            {page.raw_text ? (
              <pre className="whitespace-pre-wrap rounded bg-neutral-50 p-3 font-mono text-sm text-neutral-800 dark:bg-neutral-800 dark:text-neutral-200">
                {page.raw_text}
              </pre>
            ) : (
              !imageUrl && <p className="text-neutral-500">No extracted text for this page.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}
