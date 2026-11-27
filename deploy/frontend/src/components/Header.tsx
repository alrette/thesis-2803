import { Database, Cpu, Sparkles, AlertTriangle, CheckCircle2 } from "lucide-react";
import type { HealthResponse } from "../types/api";

interface HeaderProps {
  health: HealthResponse | null;
  healthError: string | null;
  selectedDbName: string | null;
  onBackToPicker: () => void;
}

export function Header({
  health,
  healthError,
  selectedDbName,
  onBackToPicker,
}: HeaderProps) {
  const isOnline = Boolean(health?.ready);
  const subtitle =
    health == null
      ? "1-Stage Table Graph Text-to-SQL"
      : health.few_shot_k > 0
        ? `1-Stage Table Graph + Skeleton Few-Shot (k=${health.few_shot_k})`
        : "1-Stage Table Graph • Zero-Shot (k=0)";

  return (
    <header className="sticky top-0 z-30 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onBackToPicker}
            className="flex items-center gap-2.5 text-left transition hover:opacity-90"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/15 text-indigo-400 ring-1 ring-indigo-500/30">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-sm font-semibold tracking-tight text-slate-100 sm:text-base">
                GraphRAG Text-to-SQL
              </h1>
              <p className="text-xs text-slate-400">{subtitle}</p>
            </div>
          </button>

          {selectedDbName && (
            <div className="hidden items-center gap-2 border-l border-slate-800 pl-3 sm:flex">
              <Database className="h-4 w-4 text-emerald-400" />
              <span className="text-sm font-medium text-slate-200">{selectedDbName}</span>
              <button
                type="button"
                onClick={onBackToPicker}
                className="rounded-md border border-slate-700 bg-slate-900 px-2 py-0.5 text-xs text-slate-300 transition hover:border-slate-500 hover:text-white"
              >
                Switch DB
              </button>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2.5">
          {health && (
            <div
              title={health.llm_model}
              className="hidden items-center gap-1.5 rounded-full border border-slate-800 bg-slate-900/80 px-3 py-1 text-xs text-slate-300 md:flex"
            >
              <Cpu className="h-3.5 w-3.5 text-indigo-400" />
              <span>{health.llm_model.split("/").pop()}</span>
              <span className="text-slate-600">•</span>
              <span>k={health.few_shot_k}</span>
              <span className="text-slate-600">•</span>
              <span>T={health.table_threshold}</span>
            </div>
          )}

          {healthError ? (
            <span
              title={healthError}
              className="inline-flex items-center gap-1.5 rounded-full border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-xs font-medium text-rose-300"
            >
              <AlertTriangle className="h-3.5 w-3.5" />
              Backend offline
            </span>
          ) : isOnline ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-300">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {health?.llm_configured ? "Ready" : "API key needed"}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-300">
              Connecting…
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
