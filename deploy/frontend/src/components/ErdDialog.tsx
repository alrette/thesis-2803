import { useEffect, useRef } from "react";
import type { DatabaseDetail } from "../types/api";
import { ErdDiagram } from "./ErdDiagram";
import { IconClose } from "./icons";

interface ErdDialogProps {
  open: boolean;
  onClose: () => void;
  detail: DatabaseDetail;
  pickedTables: string[];
  bridgeTables: string[];
  tableScores: Record<string, number>;
  lastQuestion: string | null;
}

export function ErdDialog({ open, onClose, detail, pickedTables, bridgeTables, tableScores, lastQuestion }: ErdDialogProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      aria-labelledby="erd-title"
      className="m-auto h-[min(88vh,900px)] w-[min(94vw,1280px)] max-w-none overflow-hidden rounded-lg border border-line bg-bg p-0 text-ink backdrop:bg-black/35 open:flex open:flex-col"
    >
      {open && (
        <div className="anim-dialog flex min-h-0 flex-1 flex-col">
          <header className="flex items-start justify-between gap-4 border-b border-line px-5 py-3.5">
            <div className="min-w-0">
              <h2 id="erd-title" className="text-[15px] font-semibold">
                {detail.display_name}
                <span className="ml-2 font-mono text-[12.5px] font-normal text-faint">{detail.db_id}</span>
              </h2>
              <p className="truncate text-[13px] text-muted">
                {lastQuestion
                  ? `Tables for “${lastQuestion}” are outlined; dashed ones were added to complete the join.`
                  : "Drag to pan, scroll to zoom. Ask a question to see which tables GraphRAG picks."}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="shrink-0 rounded-md p-1.5 text-muted transition-colors hover:bg-sunken hover:text-ink"
              aria-label="Close diagram"
            >
              <IconClose size={16} />
            </button>
          </header>
          <div className="min-h-0 flex-1 bg-sunken/40">
            <ErdDiagram
              dbId={detail.db_id}
              tables={detail.tables}
              edges={detail.edges}
              pickedTables={pickedTables}
              bridgeTables={bridgeTables}
              tableScores={tableScores}
            />
          </div>
        </div>
      )}
    </dialog>
  );
}
