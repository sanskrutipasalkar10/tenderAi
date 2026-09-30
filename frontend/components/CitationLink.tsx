"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import Card from "./ui/Card";
import { CloseIcon } from "./ui/icons";
import { ApiError, getPageContent, getPageImageBlob } from "@/lib/api";
import type { PageContentResponse } from "@/lib/types";

// The citation-verification UI (docs/SPEC.md's actual HITL mechanism — there is no
// separate approve/override workflow, docs/DECISIONS.md #3). Every fact/risk/
// criterion the reduce pass produces carries a page_ref; this is what happens when a
// user clicks it — fetch the real source page and show it, so the claim is always one
// click from being checked against the document it came from.
//
// `pageRef` (and everything backing it — pages.page_number, chunk start/end,
// PyMuPDF's own page.number) is 0-indexed internally, matching PyMuPDF and the raw
// PDF page order, and that's what getPageContent/getPageImageBlob below must keep
// using to hit the right DB row. Every place this shows a page number to a human
// below renders `pageRef + 1` instead — a real PDF viewer's "page 1" is this app's
// page_number 0, and showing the raw internal index confused reviewers cross-checking
// against the actual PDF (docs/DECISIONS.md).
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
        className="group inline-flex cursor-pointer items-start gap-1.5 rounded text-left text-primary decoration-primary/40 decoration-dotted underline-offset-2 hover:underline"
        title={`View source — page ${pageRef + 1}`}
      >
        {children}
        <span className="data-mono mt-0.5 inline-flex flex-none items-center rounded border border-primary/30 bg-primary/5 px-1.5 py-0.5 text-[11px] font-semibold text-primary group-hover:bg-accent">
          p.{pageRef + 1}
        </span>
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
      <Card
        padding="lg"
        className="max-h-[85vh] w-full max-w-2xl overflow-y-auto shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">
            Source — <span className="data-mono">page {pageRef + 1}</span>
            {page?.source_url && (
              <span className="ml-2 inline-flex items-center rounded-full bg-accent px-2 py-0.5 text-xs font-medium text-primary">
                linked document
              </span>
            )}
            {page?.attachment_filename && (
              <span className="ml-2 inline-flex items-center rounded-full bg-accent px-2 py-0.5 text-xs font-medium text-primary">
                supporting document
              </span>
            )}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-muted-foreground"
            aria-label="Close"
          >
            <CloseIcon className="h-4 w-4" />
          </button>
        </div>

        {error && <p className="text-sm text-severity-high">{error}</p>}

        {!error && !page && <p className="text-sm text-muted-foreground">Loading…</p>}

        {page && (
          <div className="space-y-4">
            {page.source_url && (
              <p className="text-xs text-muted-foreground">
                This page came from a hyperlink inside the uploaded document, not the
                document itself —{" "}
                <a
                  href={page.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="break-all text-primary underline decoration-primary/40 decoration-dotted underline-offset-2 hover:decoration-solid"
                >
                  {page.source_url}
                </a>
              </p>
            )}
            {page.attachment_filename && (
              <p className="text-xs text-muted-foreground">
                This page came from a supporting document attached to this tender, not the
                tender PDF itself — <span className="font-medium text-foreground">{page.attachment_filename}</span>
              </p>
            )}
            <div className="data-mono flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
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
                alt={`Scanned page ${pageRef + 1}`}
                className="w-full rounded border border-border"
              />
            )}

            {page.raw_text ? (
              <pre className="whitespace-pre-wrap rounded bg-surface p-3 font-mono text-sm text-slate-800">
                {page.raw_text}
              </pre>
            ) : (
              !imageUrl && <p className="text-sm text-muted-foreground">No extracted text for this page.</p>
            )}
          </div>
        )}
      </Card>
    </div>
  );

  return createPortal(modal, document.body);
}
