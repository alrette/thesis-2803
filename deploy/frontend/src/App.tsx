import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Answer } from "./components/Answer";
import { Composer } from "./components/Composer";
import { ErdDialog } from "./components/ErdDialog";
import { IconClose, IconMenu, IconPlus } from "./components/icons";
import { Sidebar } from "./components/Sidebar";
import { executeSql, fetchDatabaseDetail, fetchDatabases, fetchHealth, generateSql } from "./lib/api";
import { formatSql } from "./lib/sql";
import { useTheme } from "./lib/theme";
import type { DatabaseDetail, DatabaseSummary, HealthResponse } from "./types/api";
import type { AssistantMessage, ChatMessage } from "./types/chat";

const EMPTY: string[] = [];
const NO_SCORES: Record<string, number> = {};
let nextId = 0;
const newId = () => `m${++nextId}`;

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

  // One conversation and one unsent draft per database, so switching back and forth loses nothing.
  const [chats, setChats] = useState<Record<string, ChatMessage[]>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const [erdOpen, setErdOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

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

  // Open the first database straight away so the page lands on a usable chat.
  useEffect(() => {
    if (!dbId && databases.length > 0) void selectDb(databases[0].db_id);
  }, [databases, dbId, selectDb]);

  const detail = dbId ? details[dbId] ?? null : null;
  const messages = useMemo(() => (dbId ? chats[dbId] ?? [] : []), [chats, dbId]);
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
  }, [messages.length, busy]);

  const patch = (db: string, id: string, change: Partial<AssistantMessage>) =>
    setChats((prev) => ({
      ...prev,
      [db]: (prev[db] ?? []).map((m) => (m.id === id && m.role === "assistant" ? { ...m, ...change } : m)),
    }));

  const generate = async (db: string, id: string, question: string) => {
    try {
      const g = await generateSql(db, question);
      patch(db, id, { status: "done", generation: g, sql: formatSql(g.sql) });
    } catch (err) {
      patch(db, id, { status: "error", error: errorText(err, "The model did not answer. Try again in a moment.") });
    }
  };

  const send = (text: string) => {
    if (!dbId) return;
    const db = dbId;
    const answerId = newId();
    setChats((prev) => ({
      ...prev,
      [db]: [
        ...(prev[db] ?? []),
        { id: newId(), role: "user", text },
        { id: answerId, role: "assistant", question: text, status: "pending", sql: "", editing: false, executing: false },
      ],
    }));
    void generate(db, answerId, text);
  };

  const retry = (msg: AssistantMessage) => {
    if (!dbId) return;
    patch(dbId, msg.id, { status: "pending", error: undefined });
    void generate(dbId, msg.id, msg.question);
  };

  const run = async (msg: AssistantMessage) => {
    if (!dbId) return;
    const db = dbId;
    patch(db, msg.id, { executing: true, execError: undefined });
    try {
      const result = await executeSql(db, msg.sql.trim());
      patch(db, msg.id, { executing: false, result });
    } catch (err) {
      patch(db, msg.id, { executing: false, result: undefined, execError: errorText(err, "The query could not run.") });
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
          {messages.length > 0 && dbId && (
            <button
              type="button"
              disabled={busy}
              onClick={() => setChats((prev) => ({ ...prev, [dbId]: [] }))}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[13px] text-muted transition-colors hover:bg-sunken hover:text-ink disabled:opacity-50"
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
              <ol className="space-y-7 pt-8 pb-6">
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
                        onSqlChange={(sql) => dbId && patch(dbId, m.id, { sql, result: undefined, execError: undefined })}
                        onToggleEdit={() => dbId && patch(dbId, m.id, { editing: !m.editing })}
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
            />
          </div>
        </div>
      </main>

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
