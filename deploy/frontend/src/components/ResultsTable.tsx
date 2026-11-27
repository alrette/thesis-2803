import { AlertCircle, CheckCircle2, TableProperties } from "lucide-react";
import type { ExecuteResponse } from "../types/api";

interface ResultsTableProps {
  result: ExecuteResponse | null;
  error: string | null;
}

export function ResultsTable({ result, error }: ResultsTableProps) {
  if (!result && !error) return null;

  if (error || (result && !result.ok)) {
    return (
      <div className="rounded-xl border border-rose-500/35 bg-rose-950/30 p-4">
        <div className="flex items-start gap-2.5 text-rose-200">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
          <div>
            <p className="text-sm font-medium">SQL Execution Failed</p>
            <p className="mt-1 font-mono text-xs text-rose-300/90">
              {error || result?.error || "Unknown SQLite execution error."}
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (!result) return null;

  return (
    <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/70">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 px-4 py-2.5">
        <div className="flex items-center gap-2 text-xs font-medium text-emerald-300">
          <CheckCircle2 className="h-4 w-4" />
          <span>Query Executed Successfully</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <TableProperties className="h-3.5 w-3.5" />
          <span>
            {result.row_count} {result.row_count === 1 ? "row" : "rows"}
            {result.truncated ? " (capped at limit)" : ""}
          </span>
          <span className="text-slate-700">•</span>
          <span>{result.execution_ms} ms</span>
        </div>
      </div>

      {result.rows.length === 0 ? (
        <div className="px-4 py-8 text-center text-xs text-slate-400">
          Query returned 0 rows.
        </div>
      ) : (
        <div className="max-h-96 overflow-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="sticky top-0 bg-slate-950 text-slate-300">
              <tr>
                {result.columns.map((col, idx) => (
                  <th
                    key={`${col}-${idx}`}
                    className="whitespace-nowrap border-b border-slate-800 px-3.5 py-2 font-mono font-semibold"
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70 font-mono text-slate-200">
              {result.rows.map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-slate-800/40">
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="whitespace-nowrap px-3.5 py-2">
                      {cell === null ? (
                        <span className="italic text-slate-500">NULL</span>
                      ) : (
                        String(cell)
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
