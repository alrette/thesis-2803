import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { SampleQuestion } from "../types/api";
import { IconChevron, IconSend } from "./icons";

interface ComposerProps {
  dbName: string | null;
  disabledReason: string | null;
  busy: boolean;
  onSend: (text: string) => void;
  draft: string;
  onDraftChange: (text: string) => void;
  suggestions: SampleQuestion[];
}

export function Composer({ dbName, disabledReason, busy, onSend, draft, onDraftChange, suggestions }: ComposerProps) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [composing, setComposing] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [draft]);

  // The suggestion list closes on Escape or a click anywhere outside the composer.
  useEffect(() => {
    if (!showSuggestions) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setShowSuggestions(false);
    const onDown = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setShowSuggestions(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onDown);
    };
  }, [showSuggestions]);

  useEffect(() => setShowSuggestions(false), [dbName]);

  const canSend = !disabledReason && !busy && draft.trim().length > 1;
  const submit = () => {
    if (!canSend) return;
    onSend(draft.trim());
    onDraftChange("");
    setShowSuggestions(false);
    ref.current?.focus();
  };

  const pick = (question: string) => {
    onDraftChange(question);
    setShowSuggestions(false);
    ref.current?.focus();
  };

  return (
    <div ref={wrapRef} className="relative">
      {showSuggestions && suggestions.length > 0 && (
        <div
          id="suggestion-list"
          className="anim-rise absolute inset-x-0 bottom-full z-10 mb-2 overflow-hidden rounded-lg border border-line-strong bg-surface shadow-[0_8px_24px_-12px_rgb(0_0_0/0.25)]"
        >
          <p className="border-b border-line px-4 py-2 text-[12px] font-medium text-muted">
            Suggested questions{dbName ? ` for ${dbName}` : ""}
          </p>
          <ul className="thin-scroll max-h-64 overflow-y-auto py-1">
            {suggestions.map((s) => (
              <li key={s.question}>
                <button
                  type="button"
                  onClick={() => pick(s.question)}
                  className="group flex w-full items-baseline justify-between gap-4 px-4 py-2 text-left text-[14px] transition-colors hover:bg-sunken hover:text-accent"
                >
                  <span>{s.question}</span>
                  <span className="shrink-0 text-[11.5px] text-faint group-hover:text-accent/70">{s.difficulty}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="rounded-lg border border-line-strong bg-surface transition-colors focus-within:border-accent"
      >
        <label htmlFor="question" className="sr-only">
          Question
        </label>
        <textarea
          id="question"
          ref={ref}
          rows={1}
          value={draft}
          onChange={(e) => onDraftChange(e.target.value)}
          onCompositionStart={() => setComposing(true)}
          onCompositionEnd={() => setComposing(false)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !composing) {
              e.preventDefault();
              submit();
            }
          }}
          disabled={!!disabledReason}
          placeholder={dbName ? `Ask about ${dbName}` : "Pick a database first"}
          className="thin-scroll block max-h-[200px] w-full resize-none bg-transparent px-4 pt-3.5 pb-1 text-[15px] text-ink placeholder:text-faint focus:outline-none disabled:cursor-not-allowed"
        />
        <div className="flex items-center justify-between gap-3 px-3 pb-2.5 pl-2.5">
          <div className="flex min-w-0 items-center gap-2">
            {suggestions.length > 0 && !disabledReason && (
              <button
                type="button"
                onClick={() => setShowSuggestions((v) => !v)}
                aria-expanded={showSuggestions}
                aria-controls="suggestion-list"
                className={`inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-1 text-[12.5px] transition-colors hover:bg-sunken hover:text-ink ${
                  showSuggestions ? "text-ink" : "text-muted"
                }`}
              >
                <IconChevron size={11} className={`transition-transform duration-200 ${showSuggestions ? "rotate-90" : "-rotate-90"}`} />
                Suggestions
              </button>
            )}
            <span className="truncate text-[12px] text-faint">
              {disabledReason ??
                (busy ? "Waiting for the current answer" : <span className="hidden sm:inline">Enter to send, Shift+Enter for a new line</span>)}
            </span>
          </div>
          <button
            type="submit"
            disabled={!canSend}
            aria-label="Send question"
            className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-accent text-accent-ink transition-[opacity,transform] hover:opacity-90 active:scale-95 disabled:bg-line disabled:text-faint"
          >
            <IconSend size={15} />
          </button>
        </div>
      </form>
    </div>
  );
}
