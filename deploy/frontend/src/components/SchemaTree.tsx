import { useEffect, useState } from "react";
import type { DatabaseDetail } from "../types/api";
import { IconChevron } from "./icons";

interface SchemaTreeProps {
  detail: DatabaseDetail;
  usedTables: string[];
  bridgeTables: string[];
  tableScores: Record<string, number>;
}

export function SchemaTree({ detail, usedTables, bridgeTables, tableScores }: SchemaTreeProps) {
  const [open, setOpen] = useState<Set<string>>(new Set());

  // Tables picked for the latest answer open up so the reader sees which columns were sent.
  useEffect(() => {
    if (usedTables.length || bridgeTables.length) {
      setOpen((prev) => new Set([...prev, ...usedTables, ...bridgeTables]));
    }
  }, [usedTables, bridgeTables]);

  useEffect(() => setOpen(new Set()), [detail.db_id]);

  const toggle = (name: string) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });

  const used = new Set(usedTables);
  const bridged = new Set(bridgeTables);

  return (
    <div className="font-mono text-[12.5px] leading-[1.7]" role="tree" aria-label={`Schema of ${detail.db_id}`}>
      <div className="text-muted">{detail.db_id}/</div>
      {detail.tables.map((table, ti) => {
        const lastTable = ti === detail.tables.length - 1;
        const isOpen = open.has(table.name);
        const isUsed = used.has(table.name);
        const isBridge = bridged.has(table.name);
        return (
          <div key={table.name} role="treeitem" aria-expanded={isOpen}>
            <button
              type="button"
              onClick={() => toggle(table.name)}
              className="group flex w-full items-center whitespace-nowrap rounded-[3px] text-left hover:bg-sunken"
              title={table.natural_name}
            >
              <span className="whitespace-pre text-faint select-none">{lastTable ? "└─ " : "├─ "}</span>
              <IconChevron
                size={11}
                className={`mr-1 shrink-0 text-faint transition-transform duration-200 ${isOpen ? "rotate-90" : ""}`}
              />
              <span className={isUsed ? "font-medium text-accent" : isBridge ? "text-accent/80" : "text-ink"}>
                {table.name}
              </span>
              <span className="ml-2 truncate text-[11px] text-faint">
                {isUsed
                  ? `picked${tableScores[table.name] !== undefined ? ` ${tableScores[table.name].toFixed(2)}` : ""}`
                  : isBridge
                    ? "join path"
                    : table.columns.length}
              </span>
            </button>
            <div className="collapse-grid" data-open={isOpen}>
              <div role="group">
                {table.columns.map((col, ci) => {
                  const lastCol = ci === table.columns.length - 1;
                  return (
                    <div key={col.name} className="flex items-baseline whitespace-nowrap" title={col.natural_name}>
                      <span className="whitespace-pre text-faint select-none">
                        {lastTable ? "   " : "│  "}
                        {lastCol ? "└─ " : "├─ "}
                      </span>
                      <span className="text-ink/90">{col.name}</span>
                      <span className="ml-2 text-[11px] text-faint">{col.type}</span>
                      {col.is_pk && <span className="ml-1.5 text-[11px] text-muted">pk</span>}
                      {col.references && (
                        <span className="ml-1.5 truncate text-[11px] text-muted">→ {col.references}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
