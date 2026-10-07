"use client";

import { AnimatePresence, motion } from "framer-motion";
import { MessageCircle, Send, X } from "lucide-react";
import { usePathname } from "next/navigation";
import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import Card from "./ui/Card";
import Spinner from "./ui/Spinner";
import { ApiError, streamChatMessage } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

// Matches /documents/{id} and its sub-routes (the analysis tabs, the report page) so
// the assistant picks up document context anywhere under a document, not just its
// top-level page.
const DOCUMENT_ID_PATTERN = /^\/documents\/([^/]+)/;

// Deliberately not a markdown library + dangerouslySetInnerHTML — the reply text is
// LLM output (ultimately reachable from untrusted tender PDF content via
// document_context), so building React elements directly keeps this un-exploitable by
// construction rather than needing an HTML-sanitization step. Covers what the
// assistant actually produces (bold, bullet lists, paragraphs) — not a full markdown
// spec, on purpose.
function renderInline(text: string, keyPrefix: string): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
  return parts.map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={`${keyPrefix}-${i}`}>{part.slice(2, -2)}</strong>
    ) : (
      <Fragment key={`${keyPrefix}-${i}`}>{part}</Fragment>
    ),
  );
}

function ChatMessageBody({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let listItems: string[] = [];
  let listType: "ul" | "ol" | null = null;

  function flushList(key: string) {
    if (listItems.length === 0 || !listType) return;
    const items = listItems;
    const Tag = listType;
    listItems = [];
    listType = null;
    blocks.push(
      <Tag
        key={key}
        className={`space-y-1 pl-5 ${Tag === "ul" ? "list-disc" : "list-decimal"}`}
      >
        {items.map((item, i) => (
          <li key={i}>{renderInline(item, `${key}-li-${i}`)}</li>
        ))}
      </Tag>,
    );
  }

  text.split("\n").forEach((line, i) => {
    const trimmed = line.trim();

    // #/##/### headers — rendered as bold text sized by level, not real <h1>-<h3>
    // tags, since a chat bubble is too small a surface for genuine document headings.
    const heading = trimmed.match(/^(#{1,6})\s+(.*)/);
    if (heading) {
      flushList(`list-${i}`);
      const size = heading[1].length <= 2 ? "text-[15px]" : "text-sm";
      blocks.push(
        <p key={`h-${i}`} className={`${size} mb-1 mt-2.5 font-semibold first:mt-0`}>
          {renderInline(heading[2], `h-${i}`)}
        </p>,
      );
      return;
    }

    // A lone "---"/"***"/"___" line — a markdown section divider, not literal dashes.
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      flushList(`list-${i}`);
      blocks.push(<hr key={`hr-${i}`} className="my-2 border-border" />);
      return;
    }

    const bullet = trimmed.match(/^[*-]\s+(.*)/);
    if (bullet) {
      if (listType !== "ul") flushList(`list-${i}`);
      listType = "ul";
      listItems.push(bullet[1]);
      return;
    }

    const ordered = trimmed.match(/^\d+[.)]\s+(.*)/);
    if (ordered) {
      if (listType !== "ol") flushList(`list-${i}`);
      listType = "ol";
      listItems.push(ordered[1]);
      return;
    }

    flushList(`list-${i}`);
    if (trimmed === "") return;
    blocks.push(
      <p key={`p-${i}`} className="mb-1.5 last:mb-0">
        {renderInline(trimmed, `p-${i}`)}
      </p>,
    );
  });
  flushList("list-end");

  return <>{blocks}</>;
}

// A finished reply that got cut off by a provider failure mid-stream — flagged so the
// user can see it's partial rather than reading a truncated answer as complete. There's
// no way to retry just the missing tail once bytes are already on the wire (see
// app.llm.client.stream_chat_completion's docstring) — the user re-asks instead.
interface DisplayMessage extends ChatMessage {
  interrupted?: boolean;
}

// How ChatGPT/Gemini-style streaming actually works: the network delivers text in
// whatever bursty, uneven chunks the provider happens to send (one SSE frame can be a
// single word or several sentences) — showing those chunks directly on arrival is what
// produced the "too fast, not word-wise" jumpiness. The fix is to decouple network
// arrival from on-screen reveal: every incoming delta is appended to a local queue, and
// a fixed-pace timer peels one word off that queue at a time, independent of how the
// data actually arrived. Tuned to read like typing, not simply "as fast as possible."
const REVEAL_MS_PER_WORD = 28;

/** App-wide floating chat bubble (mounted once, in AppShell) — explains tender/
 * procurement terminology, and when the user is on a document's page, answers
 * questions grounded in that document's already-computed analysis. Deliberately
 * ephemeral: no conversation is persisted server-side, so navigating away resets it.
 * Streams its replies token-by-token rather than waiting for the full answer. */
export default function ChatWidget() {
  const pathname = usePathname();
  const documentId = pathname.match(DOCUMENT_ID_PATTERN)?.[1] ?? null;

  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [streamingText, setStreamingText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // The reveal queue described above: `pendingRef` is network-arrived text not yet
  // shown, `revealTimerRef` is the fixed-pace timer draining it onto `streamingText`.
  // `finalTextRef`/`outcomeRef` record what actually happened on the network side so
  // the timer's own "nothing left to reveal" branch knows how to finish once the queue
  // is empty, however long after the network itself finished that turns out to be.
  const pendingRef = useRef("");
  const revealTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const finalTextRef = useRef("");
  const outcomeRef = useRef<{ done: boolean; error: string | null }>({
    done: false,
    error: null,
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    // streamingText (not just messages) is the fix: without it, auto-scroll stops
    // following once new text keeps arriving below the fold after the first chunk.
  }, [messages, streamingText]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (revealTimerRef.current) clearInterval(revealTimerRef.current);
    };
  }, []);

  function stopActiveStream() {
    abortRef.current?.abort();
    abortRef.current = null;
    if (revealTimerRef.current) {
      clearInterval(revealTimerRef.current);
      revealTimerRef.current = null;
    }
    pendingRef.current = "";
    setIsStreaming(false);
    setStreamingText("");
  }

  function startRevealTimer() {
    if (revealTimerRef.current) return;
    revealTimerRef.current = setInterval(() => {
      if (pendingRef.current) {
        // Reveal one word (plus any leading whitespace) per tick — a fixed pace
        // regardless of how big the chunk that just arrived over the network was.
        const match = /^\s*\S+/.exec(pendingRef.current);
        const nextPiece = match ? match[0] : pendingRef.current;
        pendingRef.current = pendingRef.current.slice(nextPiece.length);
        setStreamingText((cur) => cur + nextPiece);
        return;
      }
      if (!outcomeRef.current.done) return; // caught up with the network; still waiting on more

      clearInterval(revealTimerRef.current!);
      revealTimerRef.current = null;
      const { error: outcomeError } = outcomeRef.current;
      if (outcomeError && !finalTextRef.current) {
        setError(outcomeError);
      } else {
        setMessages((cur) => [
          ...cur,
          { role: "assistant", content: finalTextRef.current, interrupted: outcomeError !== null },
        ]);
      }
      setStreamingText("");
      setIsStreaming(false);
    }, REVEAL_MS_PER_WORD);
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || isStreaming) return;

    const controller = new AbortController();
    abortRef.current = controller;

    const history = messages.map(({ role, content }) => ({ role, content }));
    setMessages((cur) => [...cur, { role: "user", content: text }]);
    setInput("");
    setStreamingText("");
    setIsStreaming(true);
    setError(null);

    pendingRef.current = "";
    finalTextRef.current = "";
    outcomeRef.current = { done: false, error: null };
    startRevealTimer();

    try {
      await streamChatMessage(
        text,
        documentId,
        history,
        {
          onDelta: (delta) => {
            finalTextRef.current += delta;
            pendingRef.current += delta;
          },
          onDone: () => {
            outcomeRef.current = { done: true, error: null };
          },
          onError: (message) => {
            outcomeRef.current = { done: true, error: message };
          },
        },
        controller.signal,
      );
    } catch (err) {
      if (controller.signal.aborted) return; // superseded by a newer send/close
      outcomeRef.current = {
        done: true,
        error: err instanceof ApiError ? err.message : "Could not reach the assistant",
      };
    }
  }

  return (
    <div className="fixed bottom-5 right-5 z-50">
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 300, damping: 26 }}
            className="absolute bottom-17 right-0 w-[min(92vw,460px)]"
          >
            <Card padding="sm" className="flex h-[min(75vh,640px)] flex-col overflow-hidden p-0">
              <div className="flex items-center justify-between border-b border-border bg-secondary/40 px-4 py-3.5">
                <div>
                  <p className="text-sm font-semibold text-foreground">Tender assistant</p>
                  <p className="text-xs text-muted-foreground">
                    {documentId
                      ? "Using this tender's analysis as context"
                      : "Ask about terms or the bidding process"}
                  </p>
                </div>
                <button
                  type="button"
                  aria-label="Close chat"
                  onClick={() => {
                    stopActiveStream();
                    setOpen(false);
                  }}
                  className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3.5">
                {messages.length === 0 && !streamingText && (
                  <p className="text-sm text-muted-foreground">
                    Try &ldquo;What does EMD mean?&rdquo; or, on a tender&rsquo;s page, &ldquo;What&rsquo;s
                    the eligibility criteria here?&rdquo;
                  </p>
                )}
                {messages.map((m, i) => (
                  <div
                    key={i}
                    className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 text-sm shadow-sm ${
                      m.role === "user"
                        ? "ml-auto bg-primary text-primary-foreground"
                        : "bg-secondary text-foreground"
                    }`}
                  >
                    <ChatMessageBody text={m.content} />
                    {m.interrupted && (
                      <span className="mt-1 block text-[11px] font-medium text-severity-high">
                        Interrupted — try asking again
                      </span>
                    )}
                  </div>
                ))}
                {isStreaming && streamingText && (
                  <div className="max-w-[88%] rounded-2xl bg-secondary px-3.5 py-2.5 text-sm text-foreground shadow-sm">
                    <ChatMessageBody text={streamingText} />
                    <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-foreground/60 align-middle" />
                  </div>
                )}
                {isStreaming && !streamingText && (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Spinner tone="dark" /> Thinking…
                  </div>
                )}
                {error && (
                  <p role="alert" className="text-xs text-severity-high">
                    {error}
                  </p>
                )}
                <div ref={bottomRef} />
              </div>

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void handleSend();
                }}
                className="flex items-center gap-2 border-t border-border px-3 py-3"
              >
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask a question…"
                  aria-label="Message the tender assistant"
                  className="min-w-0 flex-1 rounded-full border border-input bg-background px-4 py-2.5 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:ring-1 focus:ring-ring"
                />
                <button
                  type="submit"
                  disabled={isStreaming || !input.trim()}
                  aria-label="Send"
                  className="flex h-10 w-10 flex-none items-center justify-center rounded-full bg-primary text-primary-foreground disabled:opacity-50"
                >
                  <Send className="h-4 w-4" />
                </button>
              </form>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.button
        type="button"
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => {
          if (open) stopActiveStream();
          setOpen((v) => !v);
        }}
        aria-label={open ? "Close tender assistant" : "Open tender assistant"}
        className="flex h-13 w-13 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg"
      >
        {open ? <X className="h-5 w-5" /> : <MessageCircle className="h-5 w-5" />}
      </motion.button>
    </div>
  );
}
