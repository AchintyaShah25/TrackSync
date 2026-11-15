"use client";

import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { apiPost, ApiError, paths } from "@/lib/api/client";
import type { ChatChartSpec, ChatResponse, ChatSource } from "@/lib/api/types";
import { usePreferences } from "@/lib/queries/me";

import { Button } from "../ui/Button";
import { ChatChart } from "./ChatChart";
import { Markdown } from "./Markdown";

interface Msg {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  charts?: ChatChartSpec[];
  tools?: string[];
}

const STORAGE_KEY = "tracksync.chat.v1";
const MAX_STORED = 40;
const HISTORY_SENT = 12;
const STARTERS = [
  "What happens when the safety car comes out?",
  "Why was Lewis Hamilton disqualified from the 2023 United States Grand Prix?",
  "How did Lando Norris and Oscar Piastri compare in 2024? Show a chart.",
  "Would a one-stop have helped Oscar Piastri at Monza in 2024?",
];
const TOOL_LABEL: Record<string, string> = {
  search_knowledge: "searched rules and race history",
  query_stats: "looked up stats",
  simulate_strategy: "ran a strategy simulation",
  make_chart: "drew a chart",
};

function load(): Msg[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as Msg[]) : [];
    return Array.isArray(parsed) ? parsed.slice(-MAX_STORED) : [];
  } catch {
    return [];
  }
}

function store(msgs: Msg[]) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(msgs.slice(-MAX_STORED)));
  } catch {
    /* private mode or quota: the chat still works, it just is not kept */
  }
}

const newId = () => Math.random().toString(36).slice(2, 10);

function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 429 || err.status === 503) return err.message.charAt(0).toUpperCase() + err.message.slice(1) + ".";
    if (err.status === 401) return "Your session expired. Sign in again, or clear the chat to continue as a guest.";
    if (err.status === 422) return "That message could not be sent. Try a shorter question.";
  }
  return "The assistant did not answer. The free API may be waking up (up to a minute); try again.";
}

export function ChatView() {
  const { token, user } = useAuth();
  const { prefs } = usePreferences();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages(load()); // eslint-disable-line react-hooks/set-state-in-effect -- read browser storage after mount
    setLoaded(true);
  }, []);
  useEffect(() => {
    if (loaded) store(messages);
  }, [messages, loaded]);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, pending]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || pending) return;
    const userMsg: Msg = { id: newId(), role: "user", content: question.slice(0, 2000) };
    const history = [...messages, userMsg];
    setMessages(history);
    setDraft("");
    setError(null);
    setPending(true);
    try {
      const res = await apiPost<ChatResponse>(
        paths.chat(),
        {
          messages: history.slice(-HISTORY_SENT).map(({ role, content }) => ({ role, content })),
          level: user ? prefs.chat_level : "beginner",
        },
        { token: await token(), timeoutMs: 75_000, retries: 1 },
      );
      setMessages((m) => [
        ...m,
        { id: newId(), role: "assistant", content: res.answer, sources: res.sources, charts: res.charts, tools: res.tools_used },
      ]);
    } catch (err) {
      setError(errorText(err));
      setMessages((m) => m.filter((x) => x.id !== userMsg.id));
      setDraft(question);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Ask about F1</h1>
          <p className="mt-1 text-sm text-muted">
            Rules from the FIA regulations, history from Wikipedia, and stats straight from TrackSync&apos;s race data.
          </p>
        </div>
        {messages.length > 0 && (
          <Button size="sm" variant="ghost" onClick={() => setMessages([])} disabled={pending}>
            Clear chat
          </Button>
        )}
      </div>

      <p className="rounded-md bg-surface-muted px-3 py-2 text-xs text-muted">
        Answers come from an AI model and can be wrong; check the sources. Questions are sent to free AI providers
        (Groq, Google Gemini) that may use them to improve their models, so do not share personal details. Chats are
        kept only in this browser.
      </p>

      <div role="log" aria-live="polite" aria-busy={pending} className="flex flex-col gap-5">
        {loaded && messages.length === 0 && !pending && (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-subtle">Try one of these:</p>
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
              {STARTERS.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => send(q)}
                  className="rounded-lg border border-border bg-surface px-3 py-2 text-left text-sm hover:border-border-strong"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) =>
          m.role === "user" ? (
            <div key={m.id} className="self-end rounded-lg bg-accent-soft px-3 py-2 text-sm sm:max-w-[80%]">
              {m.content}
            </div>
          ) : (
            <Answer key={m.id} msg={m} />
          ),
        )}
        {pending && (
          <p className="text-sm text-muted" role="status">
            Thinking… looking things up
          </p>
        )}
        <div ref={endRef} />
      </div>

      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(draft);
        }}
        className="sticky bottom-0 flex gap-2 border-t border-border bg-bg py-3"
      >
        <label htmlFor="chat-input" className="sr-only">
          Your question
        </label>
        <textarea
          id="chat-input"
          rows={1}
          maxLength={2000}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(draft);
            }
          }}
          placeholder="Ask about rules, races or stats…"
          className="min-h-10 flex-1 resize-none rounded-md border border-border bg-surface px-3 py-2 text-sm"
        />
        <Button type="submit" variant="primary" disabled={pending || !draft.trim()}>
          Send
        </Button>
      </form>
    </div>
  );
}

function Answer({ msg }: { msg: Msg }) {
  const tools = [...new Set(msg.tools ?? [])].map((t) => TOOL_LABEL[t]).filter(Boolean);
  return (
    <article className="flex flex-col gap-3">
      {tools.length > 0 && <p className="text-xs text-subtle">Assistant {tools.join(", ")}</p>}
      <Markdown text={msg.content} idPrefix={msg.id} />
      {msg.charts?.map((c, i) => <ChatChart key={i} spec={c} />)}
      {msg.sources && msg.sources.length > 0 && (
        <ol className="flex flex-col gap-1.5 border-l-2 border-border pl-3 text-xs">
          {msg.sources.map((s) => (
            <li key={s.n} id={`${msg.id}-src-${s.n}`} className="text-muted">
              <span className="font-medium text-fg">[{s.n}]</span>{" "}
              {s.url ? (
                <a
                  href={s.url}
                  className="text-accent hover:underline"
                  {...(s.url.startsWith("http") ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                >
                  {s.title}
                </a>
              ) : (
                s.title
              )}
              {s.section && s.section !== "Race summary" ? ` · ${s.section}` : ""}
              <span className="block text-subtle">{s.license}</span>
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}
