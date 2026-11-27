import { Database, Table2, Columns3, GitFork, ArrowRight, HelpCircle } from "lucide-react";
import type { DatabaseSummary } from "../types/api";

interface DatabaseSelectorProps {
  databases: DatabaseSummary[];
  loading: boolean;
  error: string | null;
  onSelect: (dbId: string) => void;
}

export function DatabaseSelector({
  databases,
  loading,
  error,
  onSelect,
}: DatabaseSelectorProps) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <div className="mb-8 max-w-2xl">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-xs font-medium text-indigo-300">
          Step 1 of 5 • Choose a Database
        </span>
        <h2 className="mt-3 text-2xl font-bold tracking-tight text-white sm:text-3xl">
          Select a Spider database to explore and query
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-slate-400">
          Each database below has multiple interconnected tables and foreign keys. Pick one to
          inspect its schema and interactive ERD, generate SQL from natural language using
          GraphRAG 1-Stage, and execute the query live.
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-rose-500/30 bg-rose-950/40 p-4 text-sm text-rose-200">
          <p className="font-medium">Unable to load databases from backend</p>
          <p className="mt-1 text-xs text-rose-300/90">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((n) => (
            <div
              key={n}
              className="h-48 animate-pulse rounded-xl border border-slate-800 bg-slate-900/60"
            />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {databases.map((db) => (
            <button
              key={db.db_id}
              type="button"
              onClick={() => onSelect(db.db_id)}
              className="group flex flex-col justify-between rounded-xl border border-slate-800 bg-slate-900/70 p-5 text-left transition hover:border-indigo-500/60 hover:bg-slate-900 hover:shadow-lg hover:shadow-indigo-950/30"
            >
              <div>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-800 text-indigo-400 ring-1 ring-slate-700 group-hover:bg-indigo-500/15 group-hover:ring-indigo-500/40">
                    <Database className="h-5 w-5" />
                  </div>
                  <span className="rounded-md bg-slate-800/90 px-2 py-0.5 font-mono text-[11px] text-slate-400">
                    {db.db_id}
                  </span>
                </div>

                <h3 className="mt-4 text-base font-semibold text-white group-hover:text-indigo-200">
                  {db.display_name}
                </h3>
                <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-slate-400">
                  {db.description || "Multi-table relational Spider database."}
                </p>
              </div>

              <div className="mt-5 border-t border-slate-800/80 pt-3.5">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-slate-300">
                  <span className="inline-flex items-center gap-1">
                    <Table2 className="h-3.5 w-3.5 text-sky-400" />
                    {db.table_count} tables
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <Columns3 className="h-3.5 w-3.5 text-emerald-400" />
                    {db.column_count} cols
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <GitFork className="h-3.5 w-3.5 text-amber-400" />
                    {db.fk_count} FKs
                  </span>
                  {db.sample_question_count > 0 && (
                    <span className="inline-flex items-center gap-1 text-slate-400">
                      <HelpCircle className="h-3.5 w-3.5" />
                      {db.sample_question_count} prompts
                    </span>
                  )}
                </div>

                <div className="mt-3 flex items-center gap-1 text-xs font-medium text-indigo-400 group-hover:text-indigo-300">
                  <span>Open workbench</span>
                  <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
