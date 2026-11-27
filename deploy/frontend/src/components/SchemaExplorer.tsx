import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, KeyRound, Link2, Search, Table2 } from "lucide-react";
import type { TableInfo } from "../types/api";

interface SchemaExplorerProps {
  tables: TableInfo[];
  detectedTables: string[];
  bridgeTables: string[];
  tableScores: Record<string, number>;
}

export function SchemaExplorer({
  tables,
  detectedTables,
  bridgeTables,
  tableScores,
}: SchemaExplorerProps) {
  const [search, setSearch] = useState("");
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const detectedSet = useMemo(() => new Set(detectedTables), [detectedTables]);
  const bridgeSet = useMemo(() => new Set(bridgeTables), [bridgeTables]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return tables;
    return tables.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.natural_name.toLowerCase().includes(q) ||
        t.columns.some(
          (c) =>
            c.name.toLowerCase().includes(q) ||
            c.natural_name.toLowerCase().includes(q)
        )
    );
  }, [tables, search]);

  const toggle = (name: string) => {
    setCollapsed((prev) => ({ ...prev, [name]: !prev[name] }));
  };

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-800 p-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter tables or columns…"
            className="w-full rounded-lg border border-slate-800 bg-slate-950 py-1.5 pl-8 pr-3 text-xs text-slate-200 placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
          />
        </div>
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto p-3">
        {filtered.map((table) => {
          const isCollapsed = Boolean(collapsed[table.name]);
          const isDetected = detectedSet.has(table.name);
          const isBridge = bridgeSet.has(table.name);
          const score = tableScores[table.name];

          const borderClass = isDetected
            ? "border-emerald-500/60 bg-emerald-950/20"
            : isBridge
              ? "border-amber-500/60 bg-amber-950/20"
              : "border-slate-800 bg-slate-900/50";

          return (
            <div key={table.id} className={`rounded-lg border ${borderClass}`}>
              <button
                type="button"
                onClick={() => toggle(table.name)}
                className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
              >
                <div className="flex min-w-0 items-center gap-2">
                  {isCollapsed ? (
                    <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                  ) : (
                    <ChevronDown className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                  )}
                  <Table2 className="h-3.5 w-3.5 shrink-0 text-sky-400" />
                  <span className="truncate font-mono text-xs font-semibold text-slate-100">
                    {table.name}
                  </span>
                </div>

                <div className="flex shrink-0 items-center gap-1.5">
                  {isDetected && (
                    <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-medium text-emerald-300">
                      Match{score !== undefined ? ` ${score.toFixed(2)}` : ""}
                    </span>
                  )}
                  {isBridge && (
                    <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-medium text-amber-300">
                      FK Bridge
                    </span>
                  )}
                  <span className="text-[11px] text-slate-500">{table.columns.length}</span>
                </div>
              </button>

              {!isCollapsed && (
                <ul className="divide-y divide-slate-800/70 border-t border-slate-800/80 px-3 py-1">
                  {table.columns.map((col) => (
                    <li
                      key={`${table.name}.${col.name}`}
                      className="flex items-center justify-between gap-2 py-1.5 text-xs"
                    >
                      <div className="flex min-w-0 items-center gap-1.5">
                        {col.is_pk && (
                          <span title="Primary Key" className="text-amber-400">
                            <KeyRound className="h-3 w-3" />
                          </span>
                        )}
                        {col.is_fk && (
                          <span
                            title={col.references ? `FK → ${col.references}` : "Foreign Key"}
                            className="text-sky-400"
                          >
                            <Link2 className="h-3 w-3" />
                          </span>
                        )}
                        <span className="truncate font-mono text-slate-200">{col.name}</span>
                      </div>
                      <span className="shrink-0 font-mono text-[10px] uppercase text-slate-500">
                        {col.type}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}

        {filtered.length === 0 && (
          <p className="py-8 text-center text-xs text-slate-500">
            No matching tables or columns.
          </p>
        )}
      </div>
    </div>
  );
}
