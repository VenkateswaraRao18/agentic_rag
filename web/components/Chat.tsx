"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

type Citation = {
  source: string;
  chunk_id: string;
  score: number;
  section_path?: string | null;
  section_title?: string | null;
  page_start?: number | null;
  page_end?: number | null;
};

type AskResponse = {
  answer: string;
  intent: string;
  citations: Citation[];
  used_tool: boolean;
  fallback_used: boolean;
  latency_ms: number;
  debug?: Record<string, unknown>;
};

/**
 * Default: same-origin `/api/backend` (Next rewrite → FastAPI). No CORS.
 * Set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` only if you need a direct call and fixed CORS on the API.
 */
function getAskUrl(): string {
  const direct = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (direct) {
    return `${direct.replace(/\/$/, "")}/ask`;
  }
  return "/api/backend/ask";
}

function apiLabel(): string {
  const direct = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (direct) {
    return direct.replace(/\/$/, "");
  }
  // Same string on server and client — never use `window` here (hydration mismatch).
  return "/api/backend (same origin, proxy → FastAPI)";
}

export default function Chat() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<
    { role: "user" | "assistant"; text: string; meta?: AskResponse }[]
  >([]);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const suggestions = useMemo(
    () => [
      "What is the status of INC-1015?",
      "Find incidents related to payments-api",
      "Check ticket INC-1001 status",
      "List open incidents"
    ],
    [],
  );

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setError(null);
    setMessages((m) => [...m, { role: "user", text: q }]);
    setLoading(true);
    try {
      const res = await fetch(getAskUrl(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      if (!res.ok) {
        let detail = await res.text();
        const trimmed = detail.trimStart();
        if (
          trimmed.startsWith("<!DOCTYPE") ||
          trimmed.startsWith("<html") ||
          (res.status === 502 && detail.includes("Bad Gateway"))
        ) {
          detail =
            `API returned ${res.status} (gateway error). Your Render service may be waking from sleep or restarting — wait a few seconds and try again. If this keeps happening, check Render logs and that BACKEND_PROXY_TARGET on Vercel matches your API URL exactly.`;
        }
        throw new Error(detail || `HTTP ${res.status}`);
      }
      const data = (await res.json()) as AskResponse;
      setMessages((m) => [
        ...m,
        { role: "assistant", text: data.answer, meta: data },
      ]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Request failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative z-10 mx-auto flex min-h-full max-w-4xl flex-col px-4 pb-6 pt-8 md:px-6 md:pb-10 md:pt-10">
      <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
            Enterprise Ops Copilot
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white md:text-4xl">
            RAG assistant
          </h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-400">
            Intent routing, DocuWeave-aware retrieval, optional ticket lookup, and
            AWS Bedrock-backed answers — with citations you can trace.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-surface-border bg-surface-raised/80 px-3 py-1 text-xs text-slate-300 shadow-glow">
            API:{" "}
            <span className="font-mono text-accent break-all">{apiLabel()}</span>
          </span>
          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-200">
            LangGraph pipeline
          </span>
        </div>
      </header>

      <div className="flex min-h-[420px] flex-1 flex-col rounded-2xl border border-surface-border bg-surface-raised/60 shadow-glow backdrop-blur">
        <div className="flex-1 space-y-4 overflow-y-auto p-4 md:p-6">
          {messages.length === 0 && (
            <div className="rounded-xl border border-dashed border-surface-border bg-surface/50 p-6">
              <p className="text-sm font-medium text-slate-200">Try a question</p>
              <p className="mt-1 text-sm text-slate-500">
                Start from a suggestion or ask anything covered in your indexed runbooks.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setInput(s)}
                    className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-left text-xs text-slate-300 transition hover:border-accent/40 hover:text-white"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className="space-y-3">
              <div
                className={
                  m.role === "user"
                    ? "ml-8 flex justify-end"
                    : "mr-8 flex justify-start"
                }
              >
                <div
                  className={
                    m.role === "user"
                      ? "max-w-[85%] rounded-2xl rounded-br-sm border border-accent/30 bg-accent/15 px-4 py-3 text-sm leading-relaxed text-slate-100"
                      : "max-w-[85%] rounded-2xl rounded-bl-sm border border-surface-border bg-surface px-4 py-3 text-sm leading-relaxed text-slate-100"
                  }
                >
                  <p className="whitespace-pre-wrap">{m.text}</p>
                </div>
              </div>

              {m.role === "assistant" && m.meta && (
                <div className="mr-8 space-y-3 pl-1">
                  <div className="flex flex-wrap gap-2 text-[11px] text-slate-500">
                    <span className="rounded-md bg-surface px-2 py-0.5 font-mono text-slate-400">
                      intent: {m.meta.intent}
                    </span>
                    <span className="rounded-md bg-surface px-2 py-0.5 font-mono text-slate-400">
                      {m.meta.latency_ms} ms
                    </span>
                    {m.meta.used_tool && (
                      <span className="rounded-md bg-violet-500/10 px-2 py-0.5 text-violet-200">
                        tool
                      </span>
                    )}
                    {m.meta.fallback_used && (
                      <span className="rounded-md bg-amber-500/10 px-2 py-0.5 text-amber-200">
                        fallback
                      </span>
                    )}
                  </div>

                  {m.meta.citations.length > 0 && (
                    <div className="rounded-xl border border-surface-border bg-surface/80 p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                        Citations
                      </p>
                      <ul className="mt-2 space-y-2">
                        {m.meta.citations.map((c, j) => (
                          <li
                            key={j}
                            className="rounded-lg border border-surface-border bg-surface-raised/50 p-3 text-xs text-slate-300"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-mono text-[10px] text-slate-500">
                                {c.chunk_id}
                              </span>
                              <span className="text-slate-600">·</span>
                              <span className="truncate text-[11px] text-slate-400">
                                {c.source}
                              </span>
                              <span className="ml-auto font-mono text-[10px] text-slate-500">
                                score {c.score.toFixed(3)}
                              </span>
                            </div>
                            {(c.section_path || c.section_title) && (
                              <p className="mt-1 text-[11px] text-slate-500">
                                {[c.section_title, c.section_path]
                                  .filter(Boolean)
                                  .join(" · ")}
                              </p>
                            )}
                            {(c.page_start != null || c.page_end != null) && (
                              <p className="mt-0.5 text-[11px] text-slate-500">
                                pp. {c.page_start ?? "?"}–{c.page_end ?? "?"}
                              </p>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {error && (
          <div className="border-t border-red-500/20 bg-red-500/5 px-4 py-3 text-xs text-red-200 md:px-6">
            {error}
          </div>
        )}

        <form
          onSubmit={onSubmit}
          className="border-t border-surface-border p-4 md:p-6"
        >
          <div className="flex flex-col gap-3 md:flex-row md:items-end">
            <label className="min-w-0 flex-1">
              <span className="sr-only">Question</span>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about policies, runbooks, or tickets (e.g. INC-1001)…"
                rows={2}
                className="w-full resize-none rounded-xl border border-surface-border bg-surface px-4 py-3 text-sm text-slate-100 outline-none ring-0 placeholder:text-slate-600 focus:border-accent/50"
                disabled={loading}
              />
            </label>
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="inline-flex h-11 shrink-0 items-center justify-center rounded-xl bg-accent px-6 text-sm font-medium text-white shadow-glow transition hover:bg-accent-dim disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? "Thinking…" : "Ask"}
            </button>
          </div>
          <p className="mt-2 text-[11px] text-slate-600">
            By default requests go to <code className="text-slate-500">/api/backend</code> (Next
            rewrites to FastAPI) so the browser does not need CORS. Ensure{" "}
            <code className="text-slate-500">BACKEND_PROXY_TARGET</code> matches your API URL.
          </p>
        </form>
      </div>
    </div>
  );
}
