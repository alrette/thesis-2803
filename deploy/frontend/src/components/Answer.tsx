import { useState, type ReactNode } from "react";
import type { AssistantMessage } from "../types/chat";
import { tokenizeSql } from "../lib/sql";
import { ResultsTable } from "./ResultsTable";
import { IconCheck, IconChevron, IconCopy, IconEdit, IconPlay } from "./icons";

interface AnswerProps {
  msg: AssistantMessage;
  onRun: () => void;
  onRetry: () => void;
  onSqlChange: (sql: string) => void;
  onToggleEdit: () => void;
  /** Marks this answer's controls as guide targets; set on one answer only so each data-tour value is unique. */
  tourTarget?: boolean;
}

const TOKEN_CLASS = {
  kw: "text-[var(--code-kw)]",
  str: "text-[var(--code-str)]",
  num: "text-[var(--code-num)]",
  plain: "",
} as const;

export function Answer({ msg, onRun, onRetry, onSqlChange, onToggleEdit, tourTarget }: AnswerProps) {
  if (msg.status === "pending") {
    return (
      <div className="anim-fade py-1" role="status">
        <p className="text-[14px] text-muted">Picking tables and writing SQL…</p>
        <div className="loading-bar relative mt-2.5 h-[2px] w-40 overflow-hidden bg-line" />
      </div>
    );
  }

  if (msg.status === "error") {
    return (
      <div className="anim-rise rounded-md border border-danger/30 bg-danger-soft px-3.5 py-3 text-[14px]">
        <p className="text-ink">{msg.error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 text-[13px] font-medium text-danger underline decoration-danger/40 underline-offset-2 hover:decoration-danger"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="anim-rise">
      <div className="overflow-hidden rounded-md border border-line bg-surface" data-tour={tourTarget ? "sql" : undefined}>
        <div className="flex items-center justify-between gap-2 border-b border-line py-1.5 pr-1.5 pl-3.5">
          <span className="text-[12px] font-medium text-muted">SQL{msg.editing && ", editing"}</span>
          <div className="flex items-center gap-0.5">
            <CopyButton text={msg.sql} />
            <ToolButton
              onClick={onToggleEdit}
              label={msg.editing ? "Done" : "Edit"}
              pressed={msg.editing}
              emphasis
              tour={tourTarget ? "edit" : undefined}
            >
              {msg.editing ? <IconCheck size={14} /> : <IconEdit size={14} />}
            </ToolButton>
            <button
              type="button"
              onClick={onRun}
              disabled={msg.executing || !msg.sql.trim()}
              data-tour={tourTarget ? "run" : undefined}
              className="ml-1 inline-flex items-center gap-1.5 rounded-[5px] bg-ink px-2.5 py-1 text-[12.5px] font-medium text-bg transition-[opacity,transform] hover:opacity-90 active:scale-[0.97] disabled:opacity-50"
            >
              <IconPlay size={12} />
              {msg.executing ? "Running…" : msg.result || msg.execError ? "Run again" : "Run"}
            </button>
          </div>
        </div>
        {msg.editing ? (
          <textarea
            value={msg.sql}
            onChange={(e) => onSqlChange(e.target.value)}
            spellCheck={false}
            aria-label="Edit SQL"
            rows={Math.min(14, msg.sql.split("\n").length + 1)}
            className="block w-full resize-y bg-sunken/50 px-3.5 py-3 font-mono text-[13px] leading-6 text-ink focus:outline-none"
          />
        ) : (
          <pre className="thin-scroll overflow-x-auto px-3.5 py-3 font-mono text-[13px] leading-6 text-ink">
            {tokenizeSql(msg.sql).map((t, i) => (
              <span key={i} className={TOKEN_CLASS[t.kind]}>
                {t.text}
              </span>
            ))}
          </pre>
        )}
      </div>

      <ResultsTable result={msg.result} error={msg.execError} />
      {msg.generation && <Trace msg={msg} tourTarget={tourTarget} />}
    </div>
  );
}

function Trace({ msg, tourTarget }: { msg: AssistantMessage; tourTarget?: boolean }) {
  const [open, setOpen] = useState(false);
  const g = msg.generation!;
  const picked = g.detected_tables.join(", ");

  return (
    <div className="mt-2.5">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        data-tour={tourTarget ? "trace" : undefined}
        className="inline-flex items-center gap-1 rounded-md py-0.5 pr-1.5 text-[12.5px] text-muted transition-colors hover:text-ink"
      >
        <IconChevron size={11} className={`transition-transform duration-200 ${open ? "rotate-90" : ""}`} />
        Used {picked || "no tables"}
        {g.bridge_tables.length > 0 && ` + ${g.bridge_tables.length} for the join`}
        <span className="text-faint">· {(g.total_ms / 1000).toFixed(1)} s</span>
      </button>

      <div className="collapse-grid" data-open={open}>
        <div>
          <dl className="mt-2 grid gap-x-6 gap-y-3 border-l border-line pl-4 text-[13px] sm:grid-cols-[9rem_1fr]">
            <dt className="text-muted">Tables picked</dt>
            <dd className="font-mono text-[12.5px]">
              {g.detected_tables.map((t) => (
                <span key={t} className="mr-3 inline-block">
                  {t} <span className="text-faint">{g.table_scores[t]?.toFixed(2)}</span>
                </span>
              ))}
            </dd>

            {g.bridge_tables.length > 0 && (
              <>
                <dt className="text-muted">Added for joins</dt>
                <dd className="font-mono text-[12.5px]">{g.bridge_tables.join(", ")}</dd>
              </>
            )}

            {g.question_skeleton && (
              <>
                <dt className="text-muted">Masked question</dt>
                <dd className="font-mono text-[12.5px] text-ink/85">{g.question_skeleton}</dd>
              </>
            )}

            {g.few_shot_examples.length > 0 && (
              <>
                <dt className="text-muted">Examples (k={g.few_shot_k})</dt>
                <dd className="space-y-2">
                  {g.few_shot_examples.map((ex, i) => (
                    <div key={i}>
                      <p className="text-ink/90">{ex.question}</p>
                      <p className="font-mono text-[12px] text-muted">{ex.sql}</p>
                    </div>
                  ))}
                </dd>
              </>
            )}

            <dt className="text-muted">Model</dt>
            <dd>
              {g.model}
              {g.prompt_tokens != null && (
                <span className="text-faint">
                  {" "}
                  · {g.prompt_tokens} tokens in, {g.completion_tokens ?? "?"} out
                </span>
              )}
            </dd>

            <dt className="text-muted">Time</dt>
            <dd className="text-ink/85">
              retrieval {g.retrieval_ms} ms, generation {g.generation_ms} ms
            </dd>

            <dt className="text-muted">Schema sent</dt>
            <dd>
              <pre className="thin-scroll max-h-56 overflow-auto rounded-md bg-sunken px-3 py-2 font-mono text-[12px] leading-5 text-ink/85">
                {g.schema_ddl.trim()}
              </pre>
            </dd>
          </dl>
        </div>
      </div>
    </div>
  );
}

function ToolButton({
  onClick,
  label,
  pressed,
  emphasis,
  tour,
  children,
}: {
  onClick: () => void;
  label: string;
  pressed?: boolean;
  /** A thin border and full-ink text so Edit reads as an action, still quieter than Run. */
  emphasis?: boolean;
  tour?: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={pressed}
      data-tour={tour}
      className={`inline-flex items-center gap-1 rounded-[5px] border px-2 py-1 text-[12.5px] transition-colors hover:bg-sunken hover:text-ink ${
        emphasis ? "border-line-strong text-ink" : "border-transparent text-muted"
      }`}
    >
      {children}
      {label}
    </button>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  };
  return (
    <ToolButton onClick={copy} label={copied ? "Copied" : "Copy"}>
      {copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
    </ToolButton>
  );
}
