import { useEffect, useRef, useState } from "react";
import type { DatabaseSummary } from "../types/api";
import type { Conversation, Conversations, UserMessage } from "../types/chat";
import { IconClose } from "./icons";

interface HistoryPanelProps {
  open: boolean;
  onClose: () => void;
  conversations: Conversations;
  databases: DatabaseSummary[];
  currentDbId: string | null;
  activeId: string | null;
  onOpen: (conversation: Conversation) => void;
  onDelete: (conversationId: string) => void;
  onClear: () => void;
}

const timeFmt = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });
const dayFmt = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" });

function when(ts: number): string {
  const d = new Date(ts);
  return d.toDateString() === new Date().toDateString() ? timeFmt.format(d) : dayFmt.format(d);
}

function summary(c: Conversation): { title: string; count: number } {
  const questions = c.messages.filter((m): m is UserMessage => m.role === "user");
  return { title: questions[0]?.text ?? "Untitled", count: questions.length };
}

export function HistoryPanel(props: HistoryPanelProps) {
  const { open, onClose, conversations, databases, currentDbId, activeId } = props;
  const [confirmingClear, setConfirmingClear] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) {
      setConfirmingClear(false);
      setConfirmingDelete(null);
      return;
    }
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const names = new Map(databases.map((d) => [d.db_id, d.display_name]));
  const byDb = new Map<string, Conversation[]>();
  for (const c of Object.values(conversations)) {
    if (!c.messages.length) continue;
    byDb.set(c.dbId, [...(byDb.get(c.dbId) ?? []), c]);
  }
  const groups = [...byDb.entries()]
    .map(([db, list]) => ({ db, list: list.sort((a, b) => b.updatedAt - a.updatedAt) }))
    .sort((a, b) => (a.db === currentDbId ? -1 : b.db === currentDbId ? 1 : b.list[0].updatedAt - a.list[0].updatedAt));
  const total = groups.reduce((n, g) => n + g.list.length, 0);

  return (
    <div className={`fixed inset-0 z-30 ${open ? "" : "pointer-events-none"}`} inert={!open}>
      <div
        className={`absolute inset-0 bg-black/20 transition-opacity duration-200 ${open ? "opacity-100" : "opacity-0"}`}
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-label="Conversation history"
        className={`absolute inset-y-0 right-0 flex w-[min(360px,92vw)] flex-col border-l border-line bg-bg transition-transform duration-[260ms] ease-[var(--ease-out-soft)] ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-line pr-3 pl-5">
          <div>
            <h2 className="text-[14.5px] font-medium">History</h2>
            <p className="text-[12px] text-faint">Saved in this browser only</p>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-muted transition-colors hover:bg-sunken hover:text-ink"
            aria-label="Close history"
          >
            <IconClose size={15} />
          </button>
        </header>

        <div className="thin-scroll min-h-0 flex-1 overflow-y-auto px-3 py-3">
          {total === 0 ? (
            <p className="px-2 pt-6 text-[13.5px] text-muted">
              No conversations yet. Each chat you start is listed here, grouped by database, so you can pick it up again.
            </p>
          ) : (
            groups.map((g) => (
              <section key={g.db} className="mb-5">
                <h3 className="px-2 pb-1.5 text-[12px] font-medium text-muted">
                  {names.get(g.db) ?? g.db}
                  {!names.has(g.db) && <span className="text-faint"> (no longer available)</span>}
                </h3>
                <ul>
                  {g.list.map((c) => {
                    const { title, count } = summary(c);
                    const active = c.id === activeId;
                    const confirming = confirmingDelete === c.id;
                    return (
                      <li key={c.id} className={`group relative rounded-md ${active ? "bg-sunken" : ""}`}>
                        <button
                          type="button"
                          disabled={!names.has(g.db)}
                          onClick={() => props.onOpen(c)}
                          aria-current={active ? "true" : undefined}
                          className="w-full rounded-md py-2 pr-9 pl-2 text-left transition-colors hover:bg-sunken disabled:opacity-50"
                        >
                          <span className="line-clamp-2 text-[13.5px] text-ink group-hover:text-accent">{title}</span>
                          <span className="mt-0.5 block text-[11.5px] text-faint">
                            {count} {count === 1 ? "question" : "questions"} · {when(c.updatedAt)}
                            {active && " · open"}
                          </span>
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            if (!confirming) return setConfirmingDelete(c.id);
                            props.onDelete(c.id);
                            setConfirmingDelete(null);
                          }}
                          onBlur={() => setConfirmingDelete(null)}
                          aria-label={confirming ? "Confirm delete" : `Delete “${title}”`}
                          className={`absolute top-1.5 right-1.5 rounded-md px-1.5 py-1 text-[12px] transition-opacity focus:opacity-100 ${
                            confirming
                              ? "font-medium text-danger opacity-100"
                              : "text-faint opacity-0 group-hover:opacity-100 hover:text-ink [@media(hover:none)]:opacity-100"
                          }`}
                        >
                          {confirming ? "Delete?" : <IconClose size={13} />}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))
          )}
        </div>

        {total > 0 && (
          <footer className="shrink-0 border-t border-line px-5 py-3">
            <button
              type="button"
              onClick={() => {
                if (!confirmingClear) return setConfirmingClear(true);
                props.onClear();
                setConfirmingClear(false);
              }}
              onBlur={() => setConfirmingClear(false)}
              className={`text-[13px] transition-colors ${confirmingClear ? "font-medium text-danger" : "text-muted hover:text-ink"}`}
            >
              {confirmingClear ? `Click again to delete all ${total} conversations` : "Clear history"}
            </button>
          </footer>
        )}
      </aside>
    </div>
  );
}
