import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Answer } from "./components/Answer";
import { Composer } from "./components/Composer";
import { ErdDialog } from "./components/ErdDialog";
import { HistoryPanel } from "./components/HistoryPanel";
import { IconClose, IconHistory, IconMenu, IconPlus } from "./components/icons";
import { Sidebar } from "./components/Sidebar";
import { executeSql, fetchDatabaseDetail, fetchDatabases, fetchHealth, generateSql } from "./lib/api";
import { latestConversation, loadConversations, newId, saveConversations } from "./lib/history";
import { formatSql } from "./lib/sql";
import { useTheme } from "./lib/theme";
import type { DatabaseDetail, DatabaseSummary, HealthResponse } from "./types/api";
import type { AssistantMessage, ChatMessage, Conversation, Conversations } from "./types/chat";

const EMPTY: string[] = [];
const NO_SCORES: Record<string, number> = {};

const errorText = (err: unknown, fallback: string) => (err instanceof Error && err.message ? err.message : fallback);

export default function App() {
  const [theme, toggleTheme] = useTheme();

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [databases, setDatabases] = useState<DatabaseSummary[]>([]);
  const [listError, setListError] = useState<string | null>(null);

  const [dbId, setDbId] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<string, DatabaseDetail>>({});
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  // Any number of conversations per database, persisted in localStorage. activeByDb holds the open one:
  // a missing entry falls back to the latest conversation, null means a fresh "New chat".
  const [conversations, setConversations] = useState<Conversations>(loadConversations);
  const [activeByDb, setActiveByDb] = useState<Record<string, string | null>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const [erdOpen, setErdOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => saveConversations(conversations), [conversations]);

  const selectDb = useCallback(
    async (id: string) => {
      setDbId(id);
      setDrawerOpen(false);
      setDetailError(null);
      if (details[id]) return;
      setDetailLoading(true);
      try {
        const d = await fetchDatabaseDetail(id);
        setDetails((prev) => ({ ...prev, [id]: d }));
      } catch (err) {
        setDetailError(errorText(err, "Failed to load the schema."));
      } finally {
        setDetailLoading(false);
      }
    },
    [details]
  );

  useEffect(() => {
    fetchHealth().then(setHealth, (err) => setHealthError(errorText(err, "Backend unreachable")));
    fetchDatabases().then(
      (dbs) => setDatabases(dbs),
      (err) => setListError(errorText(err, "Could not load the database list."))
    );
  }, []);

  // Land on the database of the most recent conversation, or the first one, so the page opens on a usable chat.
  useEffect(() => {
    if (dbId || databases.length === 0) return;
    const known = new Set(databases.map((d) => d.db_id));
    const recent = Object.values(conversations)
      .filter((c) => known.has(c.dbId) && c.messages.length > 0)
      .sort((a, b) => b.updatedAt - a.updatedAt)[0]?.dbId;
    void selectDb(recent ?? databases[0].db_id);
  }, [databases, dbId, selectDb, conversations]);

  const detail = dbId ? details[dbId] ?? null : null;
  const conversation: Conversation | null = useMemo(() => {
    if (!dbId) return null;
    const chosen = activeByDb[dbId];
    if (chosen === null) return null;
    return (chosen && conversations[chosen]) || latestConversation(conversations, dbId);
  }, [dbId, activeByDb, conversations]);
  const messages: ChatMessage[] = conversation?.messages ?? [];
  const busy = messages.some((m) => m.role === "assistant" && m.status === "pending");

  const latest = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.role === "assistant" && m.generation) return m;
    }
    return null;
  }, [messages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, busy, conversation?.id]);

  const openConversation = (c: Conversation) => {
    setHistoryOpen(false);
    setActiveByDb((prev) => ({ ...prev, [c.dbId]: c.id }));
    if (c.dbId !== dbId) void selectDb(c.dbId);
  };

  const newChat = () => dbId && setActiveByDb((prev) => ({ ...prev, [dbId]: null }));

  const deleteConversation = (id: string) => {
    setConversations(({ [id]: _gone, ...rest }) => rest);
    setActiveByDb((prev) => Object.fromEntries(Object.entries(prev).map(([db, c]) => [db, c === id ? null : c])));
  };

  // Answers are patched by conversation id, so one that finishes after "New chat" still lands in its own thread.
  const patch = (convId: string, id: string, change: Partial<AssistantMessage>) =>
    setConversations((prev) => {
      const c = prev[convId];
      if (!c) return prev;
      const messages = c.messages.map((m) => (m.id === id && m.role === "assistant" ? { ...m, ...change } : m));
      return { ...prev, [convId]: { ...c, messages } };
    });

  const generate = async (convId: string, db: string, id: string, question: string) => {
    try {
      const g = await generateSql(db, question);
      patch(convId, id, { status: "done", generation: g, sql: formatSql(g.sql) });
    } catch (err) {
      patch(convId, id, { status: "error", error: errorText(err, "The model did not answer. Try again in a moment.") });
    }
  };

  const send = (text: string) => {
    if (!dbId) return;
    const db = dbId;
    const now = Date.now();
    const convId = conversation?.id ?? newId();
    const answerId = newId();
    const added: ChatMessage[] = [
      { id: newId(), role: "user", text, createdAt: now },
      { id: answerId, role: "assistant", question: text, createdAt: now, status: "pending", sql: "", editing: false, executing: false },
    ];
    setConversations((prev) => {
      const base = prev[convId] ?? { id: convId, dbId: db, createdAt: now, updatedAt: now, messages: [] };
      return { ...prev, [convId]: { ...base, updatedAt: now, messages: [...base.messages, ...added] } };
    });
    setActiveByDb((prev) => ({ ...prev, [db]: convId }));
    void generate(convId, db, answerId, text);
  };

  const retry = (msg: AssistantMessage) => {
    if (!dbId || !conversation) return;
    patch(conversation.id, msg.id, { status: "pending", error: undefined });
    void generate(conversation.id, dbId, msg.id, msg.question);
  };

  const run = async (msg: AssistantMessage) => {
    if (!dbId || !conversation) return;
    const convId = conversation.id;
    patch(convId, msg.id, { executing: true, execError: undefined });
    try {
      const result = await executeSql(dbId, msg.sql.trim());
      patch(convId, msg.id, { executing: false, result });
    } catch (err) {
      patch(convId, msg.id, { executing: false, result: undefined, execError: errorText(err, "The query could not run.") });
    }
  };

  const disabledReason = healthError
    ? "The backend is unreachable, so questions can't be answered right now."
    : health && !health.llm_configured
      ? "The model API isn't configured on the server yet."
      : !detail
        ? "Waiting for the database schema"
        : null;

  const sidebar = (
    <Sidebar
      databases={databases}
      listError={listError}
      selectedDbId={dbId}
      onSelectDb={(id) => void selectDb(id)}
      detail={detail}
      detailLoading={detailLoading}
      detailError={detailError}
      usedTables={latest?.generation?.detected_tables ?? EMPTY}
      bridgeTables={latest?.generation?.bridge_tables ?? EMPTY}
      tableScores={latest?.generation?.table_scores ?? NO_SCORES}
      onOpenErd={() => setErdOpen(true)}
      health={health}
      healthError={healthError}
      theme={theme}
      onToggleTheme={toggleTheme}
    />
  );

  return (
    <div className="flex h-full">
      <aside className="hidden w-[300px] shrink-0 border-r border-line bg-surface/50 lg:block">{sidebar}</aside>

      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            className="anim-fade absolute inset-0 bg-black/30"
            aria-label="Close schema panel"
            onClick={() => setDrawerOpen(false)}
          />
          <aside className="anim-rise absolute inset-y-0 left-0 w-[min(320px,88vw)] border-r border-line bg-bg">
            <button
              type="button"
              onClick={() => setDrawerOpen(false)}
              className="absolute top-4 right-3 rounded-md p-1.5 text-muted hover:bg-sunken"
              aria-label="Close schema panel"
            >
              <IconClose size={15} />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line px-4 sm:px-6">
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            className="-ml-1.5 rounded-md p-1.5 text-muted hover:bg-sunken hover:text-ink lg:hidden"
            aria-label="Open databases and schema"
          >
            <IconMenu size={17} />
          </button>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[14.5px] font-medium">{detail?.display_name ?? "No database selected"}</p>
            {detail?.description && <p className="truncate text-[12.5px] text-muted">{detail.description}</p>}
          </div>
          <button
            type="button"
            onClick={() => setHistoryOpen(true)}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[13px] text-muted transition-colors hover:bg-sunken hover:text-ink"
          >
            <IconHistory size={14} />
            History
          </button>
          {messages.length > 0 && (
            <button
              type="button"
              onClick={newChat}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[13px] text-muted transition-colors hover:bg-sunken hover:text-ink"
            >
              <IconPlus size={13} />
              New chat
            </button>
          )}
        </header>

        <div className="thin-scroll min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[46rem] px-4 sm:px-6">
            {messages.length === 0 ? (
              <EmptyState detail={detail} loading={detailLoading} onPick={(q) => dbId && setDrafts((d) => ({ ...d, [dbId]: q }))} />
            ) : (
              <ol key={conversation?.id} className="space-y-7 pt-8 pb-6">
                {messages.map((m) =>
                  m.role === "user" ? (
                    <li key={m.id} className="anim-rise flex justify-end">
                      <p className="max-w-[85%] rounded-lg bg-sunken px-3.5 py-2 text-[15px] whitespace-pre-wrap">{m.text}</p>
                    </li>
                  ) : (
                    <li key={m.id}>
                      <Answer
                        msg={m}
                        onRun={() => void run(m)}
                        onRetry={() => retry(m)}
                        onSqlChange={(sql) => conversation && patch(conversation.id, m.id, { sql, result: undefined, execError: undefined })}
                        onToggleEdit={() => conversation && patch(conversation.id, m.id, { editing: !m.editing })}
                      />
                    </li>
                  )
                )}
              </ol>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        <div className="shrink-0 px-4 pt-2 pb-4 sm:px-6">
          <div className="mx-auto max-w-[46rem]">
            <Composer
              dbName={detail?.display_name ?? null}
              disabledReason={disabledReason}
              busy={busy}
              onSend={send}
              draft={dbId ? drafts[dbId] ?? "" : ""}
              onDraftChange={(text) => dbId && setDrafts((d) => ({ ...d, [dbId]: text }))}
              suggestions={detail?.sample_questions ?? []}
            />
          </div>
        </div>
      </main>

      <HistoryPanel
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        conversations={conversations}
        databases={databases}
        currentDbId={dbId}
        activeId={conversation?.id ?? null}
        onOpen={openConversation}
        onDelete={deleteConversation}
        onClear={() => {
          setConversations({});
          setActiveByDb({});
        }}
      />

      {detail && (
        <ErdDialog
          open={erdOpen}
          onClose={() => setErdOpen(false)}
          detail={detail}
          pickedTables={latest?.generation?.detected_tables ?? EMPTY}
          bridgeTables={latest?.generation?.bridge_tables ?? EMPTY}
          tableScores={latest?.generation?.table_scores ?? NO_SCORES}
          lastQuestion={latest?.question ?? null}
        />
      )}
    </div>
  );
}

function EmptyState({
  detail,
  loading,
  onPick,
}: {
  detail: DatabaseDetail | null;
  loading: boolean;
  onPick: (q: string) => void;
}) {
  if (!detail) {
    return <p className="pt-24 text-[14px] text-muted">{loading ? "Loading the schema…" : ""}</p>;
  }
  return (
    <div className="anim-rise pt-[12vh] pb-8">
      <h1 className="text-[26px] leading-tight font-semibold tracking-[-0.01em] text-balance">
        What do you want to know about {detail.display_name}?
      </h1>
      <p className="mt-2 max-w-[34rem] text-[15px] text-muted">
        Ask in plain English. You get SQL back, built from the tables GraphRAG picks, and you can run it against the
        database here.
      </p>
      {detail.sample_questions.length > 0 && (
        <div className="mt-9">
          <p className="mb-2 text-[12.5px] font-medium text-muted">Try one of these</p>
          <ul className="divide-y divide-line border-y border-line">
            {detail.sample_questions.map((s) => (
              <li key={s.question}>
                <button
                  type="button"
                  onClick={() => onPick(s.question)}
                  className="group flex w-full items-baseline justify-between gap-4 py-2.5 text-left text-[14.5px] transition-colors hover:text-accent"
                >
                  <span>{s.question}</span>
                  <span className="shrink-0 text-[12px] text-faint group-hover:text-accent/70">{s.difficulty}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
