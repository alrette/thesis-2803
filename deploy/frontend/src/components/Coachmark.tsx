import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode, type Ref, type RefObject } from "react";

type Side = "bottom" | "top" | "right";

interface Target {
  el: Element | null;
  text: string;
  sides: Side[];
}

interface Pos {
  top: number;
  left: number;
  side: Side | null;
  arrow: number;
}

const GAP = 10;
const MARGIN = 12;

const isVisible = (el: Element) => {
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0;
};

// Sidebar controls render twice (desktop sidebar and mobile drawer), so pick the copy on screen.
const find = (name: string) => [...document.querySelectorAll(`[data-tour="${name}"]`)].find(isVisible) ?? null;

interface Step {
  /** data-tour name, or a lookup for targets that live inside another one. */
  target: string | (() => Element | null);
  text: string;
  sides?: Side[];
  /** Used when the target is hidden, e.g. sidebar controls that sit in the drawer on small screens. */
  fallback?: { target: string; text: string };
}

const SIDEBAR: Side[] = ["right", "bottom", "top"];

const INTRO: Step[] = [
  {
    target: "db",
    text: "Pick the database to ask about. Each one is a separate Spider database with its own tables.",
    sides: SIDEBAR,
    fallback: {
      target: "schema-toggle",
      text: "This menu holds the database picker, the schema of the current database, and its ERD.",
    },
  },
  {
    target: "schema",
    text: "Every table and column of this database. Click a table to show or hide its columns.",
    sides: SIDEBAR,
  },
  { target: "erd", text: "View ERD opens a diagram of the tables and the foreign keys that link them.", sides: SIDEBAR },
  { target: "composer", text: "Type your question in plain English. Enter sends it, Shift+Enter adds a new line.", sides: ["top"] },
  { target: "suggestions", text: "Not sure what to ask? Pick one of the sample questions for this database.", sides: ["top"] },
  { target: "history", text: "Your chats are saved in this browser. Open an earlier one from History." },
  { target: "theme", text: "Switch between the light and dark theme.", sides: ["right", "top"] },
  { target: "guide", text: "Open this guide again at any time." },
];

const ANSWER: Step[] = [
  { target: "sql", text: "This is the SQL the model wrote for your question.", sides: ["bottom", "top"] },
  { target: "edit", text: "This SQL is editable. Click Edit to change it before running." },
  { target: "run", text: "Run executes the SQL on the database and shows the result table under the answer." },
  {
    target: "trace",
    text: "Click here to see how the answer was built: tables picked, example questions used, and the schema sent to the model.",
    sides: ["bottom", "top"],
  },
  {
    target: () => find("schema")?.querySelector("[data-picked]") ?? null,
    text: "Tables the model used are highlighted in the schema on the left.",
    sides: SIDEBAR,
    fallback: {
      target: "schema-toggle",
      text: "Tables the model used are highlighted in the schema. Open it with this button.",
    },
  },
  { target: "new-chat", text: "Start a fresh chat on the same database. This one stays in History." },
];

export type TourKind = "intro" | "answer" | "full";
const TOURS: Record<TourKind, Step[]> = { intro: INTRO, answer: ANSWER, full: [...INTRO, ...ANSWER] };

function resolveStep(step: Step): Target | null {
  const el = typeof step.target === "string" ? find(step.target) : step.target();
  if (el) return { el, text: step.text, sides: step.sides ?? ["bottom", "top"] };
  const alt = step.fallback && find(step.fallback.target);
  return alt ? { el: alt, text: step.fallback!.text, sides: ["bottom", "top"] } : null;
}

const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), Math.max(lo, hi));

function place(rect: DOMRect | null, w: number, h: number, sides: Side[]): Pos {
  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  const clampX = (x: number) => clamp(x, MARGIN, vw - w - MARGIN);
  const clampY = (y: number) => clamp(y, MARGIN, vh - h - MARGIN);

  const offscreen = !rect || rect.bottom < 0 || rect.top > vh || rect.right < 0 || rect.left > vw;
  if (offscreen) return { top: clampY(72), left: clampX((vw - w) / 2), side: null, arrow: 0 };

  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  const fits: Record<Side, boolean> = {
    bottom: rect.bottom + GAP + h <= vh - MARGIN,
    top: rect.top - GAP - h >= MARGIN,
    right: rect.right + GAP + w <= vw - MARGIN,
  };
  const side = sides.find((s) => fits[s]) ?? (vh - rect.bottom >= rect.top ? "bottom" : "top");

  if (side === "right") {
    const top = clampY(cy - h / 2);
    return { top, left: rect.right + GAP, side, arrow: clamp(cy - top, 14, h - 14) };
  }
  const left = clampX(cx - w / 2);
  const top = clampY(side === "bottom" ? rect.bottom + GAP : rect.top - GAP - h);
  return { top, left, side, arrow: clamp(cx - left, 14, w - 14) };
}

const ARROW: Record<Side, (at: number) => { cls: string; style: CSSProperties }> = {
  bottom: (at) => ({ cls: "border-t border-l", style: { top: -6, left: at - 5 } }),
  top: (at) => ({ cls: "border-r border-b", style: { bottom: -6, left: at - 5 } }),
  right: (at) => ({ cls: "border-b border-l", style: { left: -6, top: at - 5 } }),
};

interface CoachmarkProps {
  kind: TourKind;
  onClose: () => void;
}

/* Non-modal guide: a small box pinned next to the control it explains, with no backdrop. */
export function Coachmark({ kind, onClose }: CoachmarkProps) {
  // Steps whose control isn't on screen (no suggestions, sidebar hidden on phones) are dropped up front,
  // so the counter matches what the user actually walks through.
  const [steps] = useState(() => TOURS[kind].filter((s) => resolveStep(s)));
  const [index, setIndex] = useState(0);

  // Read during the first render, before the box takes focus, so closing hands it back (usually to the composer).
  const [previous] = useState(() => document.activeElement as HTMLElement | null);
  useEffect(() => {
    return () => {
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, [previous]);

  useEffect(() => {
    if (steps.length === 0) onClose();
  }, [steps, onClose]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.preventDefault();
      onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (steps.length === 0) return null;
  const last = index === steps.length - 1;
  return (
    <Box key={index} step={steps[index]} label={`Guide, step ${index + 1} of ${steps.length}`}>
      {(primaryRef, text) => (
        <>
          <p className="text-[14px] leading-snug text-ink">{text}</p>
          <div className="mt-3 flex items-center justify-between gap-2">
            <span className="text-[12px] text-muted tabular-nums">
              {index + 1} of {steps.length}
            </span>
            <div className="flex items-center gap-1">
              <QuietButton onClick={onClose}>Skip</QuietButton>
              {index > 0 && <QuietButton onClick={() => setIndex(index - 1)}>Back</QuietButton>}
              <PrimaryButton ref={primaryRef} onClick={last ? onClose : () => setIndex(index + 1)}>
                {last ? "Got it" : "Next"}
              </PrimaryButton>
            </div>
          </div>
        </>
      )}
    </Box>
  );
}

function QuietButton({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-md px-2 py-1 text-[12.5px] text-muted transition-colors hover:bg-sunken hover:text-ink pointer-coarse:min-h-11"
    >
      {children}
    </button>
  );
}

function Box({
  step,
  label,
  children,
}: {
  step: Step;
  label: string;
  children: (primaryRef: RefObject<HTMLButtonElement | null>, text: string) => ReactNode;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const primaryRef = useRef<HTMLButtonElement>(null);
  const [pos, setPos] = useState<Pos | null>(null);
  const [text, setText] = useState(() => resolveStep(step)?.text ?? step.text);

  // Re-measured every frame while open: scroll, resize, the answer's entry animation and
  // content changing above the target all move it, and none of them fire one common event.
  useLayoutEffect(() => {
    let frame = 0;
    let first = true;
    let last = "";
    const tick = () => {
      const target = resolveStep(step) ?? { el: null, text: step.text, sides: ["bottom"] as Side[] };
      const box = boxRef.current;
      if (box) {
        if (first && target.el) target.el.scrollIntoView({ block: "nearest", behavior: reducedMotion() ? "auto" : "smooth" });
        first = false;
        const next = place(target.el?.getBoundingClientRect() ?? null, box.offsetWidth, box.offsetHeight, target.sides);
        const key = `${next.top}|${next.left}|${next.side}|${next.arrow}|${target.text}`;
        if (key !== last) {
          last = key;
          setPos(next);
          setText(target.text);
        }
      }
      frame = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(frame);
  }, [step]);

  // Focus waits for the first placement: the box is visibility:hidden until then and can't take focus.
  const placed = pos !== null;
  useEffect(() => {
    if (placed) primaryRef.current?.focus({ preventScroll: true });
  }, [placed]);

  const arrow = pos?.side ? ARROW[pos.side](pos.arrow) : null;
  return (
    <div
      ref={boxRef}
      role="dialog"
      aria-label={label}
      style={pos ? { top: pos.top, left: pos.left } : { top: 0, left: 0, visibility: "hidden" }}
      className="anim-rise fixed z-50 w-[min(280px,calc(100vw-24px))] rounded-lg border border-line-strong bg-surface p-3.5 shadow-[0_8px_24px_-12px_rgb(0_0_0/0.25)]"
    >
      {arrow && (
        <span
          aria-hidden="true"
          style={arrow.style}
          className={`absolute h-2.5 w-2.5 rotate-45 border-line-strong bg-surface ${arrow.cls}`}
        />
      )}
      {children(primaryRef, text)}
    </div>
  );
}

function PrimaryButton({
  ref,
  onClick,
  children,
}: {
  ref: Ref<HTMLButtonElement>;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      ref={ref}
      type="button"
      onClick={onClick}
      className="rounded-[5px] bg-ink px-3 py-1 text-[13px] font-medium text-bg transition-[opacity,transform] hover:opacity-90 active:scale-[0.97] pointer-coarse:min-h-11"
    >
      {children}
    </button>
  );
}
