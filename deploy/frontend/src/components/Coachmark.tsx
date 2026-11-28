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

// The schema tree renders twice (desktop sidebar and mobile drawer), so pick the copy on screen.
const find = (name: string) => [...document.querySelectorAll(`[data-tour="${name}"]`)].find(isVisible) ?? null;

const STEPS: (() => Target)[] = [
  () => ({
    el: find("edit"),
    text: "This SQL is editable. Click Edit to change it before running.",
    sides: ["bottom", "top"],
  }),
  () => ({
    el: find("run"),
    text: "Run executes the SQL on the database and shows the result table.",
    sides: ["bottom", "top"],
  }),
  () => {
    const tree = find("schema");
    if (tree) {
      return {
        el: tree.querySelector("[data-picked]") ?? tree,
        text: "Tables the model used are highlighted in the schema on the left.",
        sides: ["right", "bottom", "top"],
      };
    }
    const toggle = find("schema-toggle");
    return {
      el: toggle,
      text: toggle
        ? "Tables the model used are highlighted in the schema. Open it with this button."
        : "Tables the model used are highlighted in the schema panel.",
      sides: ["bottom", "top"],
    };
  },
];

const OVERVIEW = (): Target => ({ el: find("guide"), text: "", sides: ["bottom"] });

const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), Math.max(lo, hi));

function place(rect: DOMRect | null, w: number, h: number, sides: Side[], withArrow: boolean): Pos {
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
    return { top, left: rect.right + GAP, side: withArrow ? side : null, arrow: clamp(cy - top, 14, h - 14) };
  }
  const left = clampX(cx - w / 2);
  const top = clampY(side === "bottom" ? rect.bottom + GAP : rect.top - GAP - h);
  return { top, left, side: withArrow ? side : null, arrow: clamp(cx - left, 14, w - 14) };
}

const ARROW: Record<Side, (at: number) => { cls: string; style: CSSProperties }> = {
  bottom: (at) => ({ cls: "border-t border-l", style: { top: -6, left: at - 5 } }),
  top: (at) => ({ cls: "border-r border-b", style: { bottom: -6, left: at - 5 } }),
  right: (at) => ({ cls: "border-b border-l", style: { left: -6, top: at - 5 } }),
};

interface CoachmarkProps {
  mode: "steps" | "overview";
  onClose: () => void;
}

/* Non-modal guide: a small box pinned next to the control it explains, with no backdrop. */
export function Coachmark({ mode, onClose }: CoachmarkProps) {
  const [step, setStep] = useState(0);

  // Read during the first render, before the box takes focus, so closing hands it back (usually to the composer).
  const [previous] = useState(() => document.activeElement as HTMLElement | null);
  useEffect(() => {
    return () => {
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, [previous]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.preventDefault();
      onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (mode === "overview") {
    const wide = window.matchMedia?.("(min-width: 64rem)").matches ?? true;
    return (
      <Box key="overview" resolve={OVERVIEW} withArrow={false} label="Quick guide">
        {(primaryRef) => (
          <>
            <p className="text-[13px] font-medium text-ink">How this workbench works</p>
            <ul className="mt-2 list-disc space-y-1.5 pl-4 text-[13.5px] leading-snug text-ink marker:text-faint">
              <li>The SQL in each answer is editable. Click Edit to change it before running.</li>
              <li>Run executes the SQL on the database and shows the result table.</li>
              <li>
                {wide
                  ? "Tables the model used are highlighted in the schema on the left."
                  : "Tables the model used are highlighted in the schema, opened with the menu button at the top left."}
              </li>
            </ul>
            <div className="mt-3 flex justify-end">
              <PrimaryButton ref={primaryRef} onClick={onClose}>
                Got it
              </PrimaryButton>
            </div>
          </>
        )}
      </Box>
    );
  }

  const last = step === STEPS.length - 1;
  return (
    <Box key={step} resolve={STEPS[step]} withArrow label={`Quick guide, step ${step + 1} of ${STEPS.length}`}>
      {(primaryRef, text) => (
        <>
          <p className="text-[14px] leading-snug text-ink">{text}</p>
          <div className="mt-3 flex items-center justify-between gap-3">
            <span className="text-[12px] text-muted tabular-nums">
              {step + 1} of {STEPS.length}
            </span>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={onClose}
                className="rounded-md px-2 py-1 text-[12.5px] text-muted transition-colors hover:bg-sunken hover:text-ink pointer-coarse:min-h-11"
              >
                Skip
              </button>
              <PrimaryButton ref={primaryRef} onClick={last ? onClose : () => setStep(step + 1)}>
                {last ? "Got it" : "Next"}
              </PrimaryButton>
            </div>
          </div>
        </>
      )}
    </Box>
  );
}

function Box({
  resolve,
  withArrow,
  label,
  children,
}: {
  resolve: () => Target;
  withArrow: boolean;
  label: string;
  children: (primaryRef: RefObject<HTMLButtonElement | null>, text: string) => ReactNode;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const primaryRef = useRef<HTMLButtonElement>(null);
  const [pos, setPos] = useState<Pos | null>(null);
  const [text, setText] = useState(() => resolve().text);

  // Re-measured every frame while open: scroll, resize, the answer's entry animation and
  // content changing above the target all move it, and none of them fire one common event.
  useLayoutEffect(() => {
    let frame = 0;
    let first = true;
    let last = "";
    const tick = () => {
      const target = resolve();
      const box = boxRef.current;
      if (box) {
        if (first && target.el) target.el.scrollIntoView({ block: "nearest", behavior: reducedMotion() ? "auto" : "smooth" });
        first = false;
        const next = place(target.el?.getBoundingClientRect() ?? null, box.offsetWidth, box.offsetHeight, target.sides, withArrow);
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
  }, [resolve, withArrow]);

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
