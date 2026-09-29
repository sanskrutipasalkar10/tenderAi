"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import Card from "./ui/Card";
import type { DocumentStatusResponse } from "@/lib/types";

interface LogLine {
  id: number;
  time: string;
  text: string;
}

const STATUS_MESSAGE: Record<DocumentStatusResponse["status"], string> = {
  uploaded: "File received — queued for processing",
  classifying: "Classifying pages (native text / scanned / table)",
  extracting: "Extracting page content",
  extracted: "Extraction complete — building chunks",
  analyzing: "Running Go/No-Go, Synopsis, and Risk Finder analysis",
  ready: "Analysis complete",
  failed: "Processing failed",
};

function timestamp(): string {
  return new Date().toLocaleTimeString("en-IN", { hour12: false });
}

/** A synthesized, real log feed — every line reflects an actual change this component
 * observed in the polled `DocumentStatusResponse` (never a fabricated progress
 * animation). Deliberately client-side rather than a persisted server-side log table:
 * every number here (pages/chunks/modules) already comes from real rows in Postgres
 * (`pages`, `chunks`, `chunk_extractions`, `document_analysis` — see
 * docs/DECISIONS.md #60), so there's nothing to gain from also persisting a redundant
 * event-log table just to replay what polling already reveals. */
export default function ProcessingLog({ status }: { status: DocumentStatusResponse }) {
  const [lines, setLines] = useState<LogLine[]>([]);
  const prevRef = useRef<DocumentStatusResponse | null>(null);
  const idRef = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const prev = prevRef.current;
    const next: LogLine[] = [];

    function push(text: string) {
      idRef.current += 1;
      next.push({ id: idRef.current, time: timestamp(), text });
    }

    if (prev === null) {
      push(STATUS_MESSAGE[status.status]);
    } else {
      if (prev.status !== status.status) {
        push(STATUS_MESSAGE[status.status]);
      }
      // Main-document extraction (page-by-page, against the uploaded PDF's own known
      // page count) is logged separately from linked-document extraction (no fixed
      // denominator known in advance — a document's hyperlinks resolve to whatever
      // page counts they resolve to) — mixing them into one "X of Y" line is exactly
      // what produced a nonsensical "page 48 of 6" log entry (docs/DECISIONS.md).
      if (status.total_pages && status.main_document_pages > prev.main_document_pages) {
        push(`Extracted page ${status.main_document_pages} of ${status.total_pages}`);
      }
      if (status.linked_documents_found > prev.linked_documents_found) {
        push(`Found and processed linked document ${status.linked_documents_found}`);
      }
      if (status.chunks_total > 0 && prev.chunks_total === 0) {
        push(`Built ${status.chunks_total} chunk${status.chunks_total === 1 ? "" : "s"} for analysis`);
      }
      if (status.chunks_mapped > prev.chunks_mapped) {
        push(`Mapped chunk ${status.chunks_mapped} of ${status.chunks_total}`);
      }
      for (const analysisModule of status.modules_ready) {
        if (!prev.modules_ready.includes(analysisModule)) {
          push(`${MODULE_LABEL[analysisModule]} ready`);
        }
      }
    }

    if (next.length > 0) {
      setLines((cur) => [...cur, ...next]);
    }
    prevRef.current = status;
  }, [status]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [lines]);

  return (
    <Card tone="dark" padding="sm" className="p-0">
      <div className="flex items-center gap-2 border-b border-white/10 px-4 py-2.5">
        <span className="h-2 w-2 rounded-full bg-status-go" />
        <span className="data-mono text-xs font-medium text-muted-foreground">Processing log</span>
      </div>
      <div ref={scrollRef} className="max-h-56 space-y-1 overflow-y-auto px-4 py-3">
        <AnimatePresence initial={false}>
          {lines.map((line) => (
            <motion.div
              key={line.id}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className="data-mono flex gap-3 text-xs"
            >
              <span className="flex-none text-muted-foreground">{line.time}</span>
              <span className="text-muted-foreground">{line.text}</span>
            </motion.div>
          ))}
        </AnimatePresence>
        {lines.length === 0 && (
          <p className="data-mono text-xs text-muted-foreground">Waiting for the first update…</p>
        )}
      </div>
    </Card>
  );
}

const MODULE_LABEL: Record<string, string> = {
  go_no_go: "Go/No-Go analysis",
  synopsis: "Synopsis",
  risk_finder: "Risk Finder",
};
