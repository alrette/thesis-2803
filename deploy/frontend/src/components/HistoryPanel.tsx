import { useEffect, useRef, useState } from "react";
import type { DatabaseSummary } from "../types/api";
import type { AssistantMessage, Chats } from "../types/chat";
import { IconClose } from "./icons";

interface HistoryPanelProps {
  open: boolean;
  onClose: () => void;
  chats: Chats;
  databases: DatabaseSummary[];
  currentDbId: string | null;
  onOpenEntry: (dbId: string, messageId: string) => void;
  onClear: () => void;
}

const timeFmt = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });
const dayFmt = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" });

function when(ts: number): string {
  const d = new Date(ts);
  return d.toDateString() === new Date().toDateString() ? timeFmt.format(d) : dayFmt.format(d);
}

export function HistoryPanel({ open, onClose, chats, databases, currentDbId, onOpenEntry, onClear }: HistoryPanelProps) {
  const [confirming, setConfirming] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) {
      setConfirming(false);
      return;
    }
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const names = new Map(databases.map((d) => [d.db_id, d.display_name]));
  const groups = Object.entries(chats)
    .map(([db, msgs]) => ({
      db,
      entries: msgs.filter((m): m is AssistantMessage => m.role === "assistant").reverse(),
    }))
    .filter((g) => g.entries.length > 0)
    .sort((a, b) => (a.db === currentDbId ? -1 : b.db === currentDbId ? 1 : b.entries[0].createdAt - a.entries[0].createdAt));
  const total = groups.reduce((n, g) => n + g.entries.length, 0);

  return (
    <div className={`fixed inset-0 z-30 ${open ? "" : "pointer-events-none"}`} inert={!open}>
      <div
        className={`absolute inset-0 bg-black/20 transition-opacity duration-200 ${open ? "opacity-100" : "opacity-0"}`}
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-label="Question history"
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
              Nothing here yet. Questions you ask are listed here, grouped by database, so you can jump back to them.
            </p>
          ) : (
            groups.map((g) => (
              <section key={g.db} className="mb-5">
                <h3 className="px-2 pb-1.5 text-[12px] font-medium text-muted">
                  {names.get(g.db) ?? g.db}
                  {!names.has(g.db) && <span className="text-faint"> (no longer available)</span>}
                </h3>
                <ul>
                  {g.entries.map((m) => (
                    <li key={m.id}>
                      <button
                        type="button"
                                    disabled={!names.has(g.db)}
                        onClick={() => onOpenEntry(g.db, m.id)}
                        className="group w-full rounded-md px-2 py-2 text-left transition-colors hover:bg-sunken disabled:opacity-50"
                      >
                        <span className="flex items-baseline justify-between gap-3">
                          <span className="line-clamp-2 text-[13.5px] text-ink group-hover:text-accent">{m.question}</span>
                          <span className="shrink-0 font-mono text-[11px] text-faint">{when(m.createdAt)}</span>
                        </span>
                        <span className="mt-0.5 block truncate font-mono text-[11.5px] text-faint">
                          {m.status === "done" ? m.sql.replace(/\s+/g, " ") : m.status === "error" ? "No SQL, the request failed" : "Generating…"}
                        </span>
                      </button>
                    </li>
                  ))}
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
                if (confirming) {
                  onClear();
                  setConfirming(false);
                } else setConfirming(true);
              }}
              onBlur={() => setConfirming(false)}
              className={`text-[13px] transition-colors ${confirming ? "font-medium text-danger" : "text-muted hover:text-ink"}`}
            >
              {confirming ? `Click again to delete all ${total} questions` : "Clear history"}
            </button>
          </footer>
        )}
      </aside>
    </div>
  );
}
