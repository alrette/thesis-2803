import { useLayoutEffect, useRef, useState } from "react";
import { IconSend } from "./icons";

interface ComposerProps {
  dbName: string | null;
  disabledReason: string | null;
  busy: boolean;
  onSend: (text: string) => void;
  draft: string;
  onDraftChange: (text: string) => void;
}

export function Composer({ dbName, disabledReason, busy, onSend, draft, onDraftChange }: ComposerProps) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const [composing, setComposing] = useState(false);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [draft]);

  const canSend = !disabledReason && !busy && draft.trim().length > 1;
  const submit = () => {
    if (!canSend) return;
    onSend(draft.trim());
    onDraftChange("");
    ref.current?.focus();
  };

  return (
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
      <div className="flex items-center justify-between gap-3 px-3 pb-2.5 pl-4">
        <span className="truncate text-[12px] text-faint">
          {disabledReason ??
            (busy ? "Waiting for the current answer" : <span className="hidden sm:inline">Enter to send, Shift+Enter for a new line</span>)}
        </span>
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
  );
}
