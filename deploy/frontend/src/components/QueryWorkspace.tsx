import { useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  Loader2,
  Play,
  Sparkles,
  Wand2,
} from "lucide-react";
import type { GenerateResponse, SampleQuestion } from "../types/api";

interface QueryWorkspaceProps {
  sampleQuestions: SampleQuestion[];
  question: string;
  onQuestionChange: (value: string) => void;
  onGenerate: () => void;
  generating: boolean;
  generateError: string | null;
  generation: GenerateResponse | null;
  sqlDraft: string;
  onSqlDraftChange: (value: string) => void;
  onExecute: () => void;
  executing: boolean;
}

function difficultyBadge(level: string): string {
  const lower = level.toLowerCase();
  if (lower === "easy") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  if (lower === "medium") return "border-amber-500/30 bg-amber-500/10 text-amber-300";
  return "border-rose-500/30 bg-rose-500/10 text-rose-300";
}

export function QueryWorkspace({
  sampleQuestions,
  question,
  onQuestionChange,
  onGenerate,
  generating,
  generateError,
  generation,
  sqlDraft,
  onSqlDraftChange,
  onExecute,
  executing,
}: QueryWorkspaceProps) {
  const [copied, setCopied] = useState(false);
  const [traceOpen, setTraceOpen] = useState(false);

  const handleCopy = async () => {
    if (!sqlDraft.trim()) return;
    await navigator.clipboard.writeText(sqlDraft);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="space-y-4">
      {/* Step 3: Sample questions */}
      {sampleQuestions.length > 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="mb-2.5 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Step 3 • Suggested Spider Test Questions
            </span>
            <span className="text-[11px] text-slate-500">Click any question to fill</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {sampleQuestions.map((item, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => onQuestionChange(item.question)}
                className="group inline-flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-950/90 px-3 py-1.5 text-left text-xs text-slate-200 transition hover:border-indigo-500/60 hover:bg-slate-900"
              >
                <span
                  className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-medium ${difficultyBadge(item.difficulty)}`}
                >
                  {item.difficulty}
                </span>
                <span className="line-clamp-1">{item.question}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 4: Ask service to generate SQL */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <div className="mb-2 flex items-center justify-between">
          <label
            htmlFor="nl-question"
            className="text-xs font-semibold uppercase tracking-wider text-slate-400"
          >
            Step 4 • Ask a Natural Language Question
          </label>
          <span className="text-[11px] text-slate-500">Ctrl + Enter to generate</span>
        </div>

        <textarea
          id="nl-question"
          rows={3}
          value={question}
          onChange={(e) => onQuestionChange(e.target.value)}
          onKeyDown={(e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !generating && question.trim()) {
              e.preventDefault();
              onGenerate();
            }
          }}
          placeholder="Ask a question about this database (or click a suggested Spider question above)…"
          className="w-full resize-none rounded-lg border border-slate-800 bg-slate-950 p-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
        />

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-slate-500">
            Pipeline: 1-Stage Table Graph Retrieval → Skeleton Few-Shot → Qwen2.5-Coder-7B
          </p>
          <button
            type="button"
            disabled={generating || !question.trim()}
            onClick={onGenerate}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {generating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating SQL…
              </>
            ) : (
              <>
                <Wand2 className="h-4 w-4" />
                Generate SQL
              </>
            )}
          </button>
        </div>

        {generateError && (
          <div className="mt-3 rounded-lg border border-rose-500/30 bg-rose-950/40 px-3 py-2 text-xs text-rose-200">
            {generateError}
          </div>
        )}
      </div>

      {/* Generated SQL + Run button */}
      {(generation || sqlDraft) && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
          <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-emerald-400" />
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Generated SQLite Query
              </span>
              {generation && (
                <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] text-slate-400">
                  {generation.total_ms} ms
                  {generation.prompt_tokens != null && (
                    <>
                      {" "}
                      • {generation.prompt_tokens} in / {generation.completion_tokens ?? "?"} out
                      tok
                    </>
                  )}
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCopy}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-300 transition hover:border-slate-500 hover:text-white"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? "Copied" : "Copy"}
              </button>

              <button
                type="button"
                disabled={executing || !sqlDraft.trim()}
                onClick={onExecute}
                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {executing ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Running…
                  </>
                ) : (
                  <>
                    <Play className="h-3.5 w-3.5 fill-current" />
                    Step 5 • Run SQL
                  </>
                )}
              </button>
            </div>
          </div>

          <textarea
            rows={4}
            value={sqlDraft}
            onChange={(e) => onSqlDraftChange(e.target.value)}
            spellCheck={false}
            className="w-full rounded-lg border border-slate-800 bg-slate-950 p-3 font-mono text-xs leading-relaxed text-emerald-300 focus:border-emerald-500 focus:outline-none"
          />

          {/* Collapsible GraphRAG 1-Stage retrieval trace */}
          {generation && (
            <div className="mt-3 border-t border-slate-800/80 pt-3">
              <button
                type="button"
                onClick={() => setTraceOpen((v) => !v)}
                className="flex w-full items-center justify-between text-xs text-slate-400 hover:text-slate-200"
              >
                <span>
                  GraphRAG 1-Stage Trace •{" "}
                  <strong className="text-emerald-300">
                    {generation.detected_tables.length} matched
                  </strong>
                  {generation.bridge_tables.length > 0 && (
                    <>
                      {" + "}
                      <strong className="text-amber-300">
                        {generation.bridge_tables.length} FK bridge
                      </strong>
                    </>
                  )}{" "}
                  • {generation.few_shot_examples.length} few-shot examples (retrieval{" "}
                  {generation.retrieval_ms} ms)
                </span>
                {traceOpen ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </button>

              {traceOpen && (
                <div className="mt-3 space-y-3 rounded-lg border border-slate-800 bg-slate-950/90 p-3 text-xs">
                  <div>
                    <p className="font-medium text-slate-300">Selected Tables (highlighted on ERD)</p>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {generation.detected_tables.map((t) => (
                        <span
                          key={t}
                          className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 font-mono text-[11px] text-emerald-300"
                        >
                          {t}
                          {generation.table_scores[t] !== undefined
                            ? ` (${generation.table_scores[t].toFixed(2)})`
                            : ""}
                        </span>
                      ))}
                      {generation.bridge_tables.map((t) => (
                        <span
                          key={t}
                          className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-mono text-[11px] text-amber-300"
                        >
                          {t} (FK bridge)
                        </span>
                      ))}
                    </div>
                  </div>

                  {generation.question_skeleton && (
                    <div>
                      <p className="font-medium text-slate-300">Masked Question Skeleton</p>
                      <p className="mt-1 rounded bg-slate-900 px-2.5 py-1.5 font-mono text-[11px] text-indigo-300">
                        {generation.question_skeleton}
                      </p>
                    </div>
                  )}

                  {generation.few_shot_examples.length > 0 && (
                    <div>
                      <p className="font-medium text-slate-300">
                        Retrieved Few-Shot Examples (k={generation.few_shot_k})
                      </p>
                      <div className="mt-1.5 space-y-2">
                        {generation.few_shot_examples.map((ex, i) => (
                          <div
                            key={i}
                            className="rounded border border-slate-800 bg-slate-900/70 p-2"
                          >
                            <div className="flex items-center justify-between gap-2 text-[11px] text-slate-400">
                              <span>
                                #{i + 1} ({ex.db_id})
                              </span>
                              <span>sim {ex.score.toFixed(3)}</span>
                            </div>
                            <p className="mt-0.5 text-slate-200">{ex.question}</p>
                            <p className="mt-1 font-mono text-[11px] text-sky-300">{ex.sql}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div>
                    <p className="font-medium text-slate-300">Schema DDL Sent to LLM</p>
                    <pre className="mt-1 max-h-44 overflow-auto rounded bg-slate-900 p-2 font-mono text-[11px] text-slate-300">
                      {generation.schema_ddl}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
