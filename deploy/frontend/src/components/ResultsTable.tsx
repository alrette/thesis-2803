import type { ExecuteResponse } from "../types/api";

export function ResultsTable({ result, error }: { result?: ExecuteResponse; error?: string }) {
  const failure = error ?? (result && !result.ok ? result.error ?? "SQLite returned an error." : null);

  if (failure) {
    return (
      <div className="anim-rise mt-3 rounded-md border border-danger/30 bg-danger-soft px-3.5 py-2.5 text-[13.5px]">
        <p className="font-medium text-danger">The query did not run</p>
        <p className="mt-0.5 font-mono text-[12.5px] text-ink/80">{failure}</p>
      </div>
    );
  }
  if (!result) return null;

  return (
    <div className="anim-rise mt-3 overflow-hidden rounded-md border border-line bg-surface">
      <div className="flex items-center justify-between border-b border-line px-3.5 py-2 text-[12.5px] text-muted">
        <span>
          {result.row_count} {result.row_count === 1 ? "row" : "rows"}
          {result.truncated && `, first ${result.row_count} shown`}
        </span>
        <span className="font-mono text-faint">{result.execution_ms} ms</span>
      </div>
      {result.rows.length === 0 ? (
        <p className="px-3.5 py-4 text-[13.5px] text-muted">The query ran and returned no rows.</p>
      ) : (
        <div className="thin-scroll max-h-80 overflow-auto">
          <table className="w-full border-collapse text-left font-mono text-[12.5px]">
            <thead className="sticky top-0 bg-surface">
              <tr>
                {result.columns.map((c, i) => (
                  <th key={`${c}-${i}`} className="border-b border-line px-3.5 py-1.5 font-medium whitespace-nowrap text-muted">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.map((row, r) => (
                <tr key={r} className="border-b border-line/60 last:border-0 hover:bg-sunken/60">
                  {row.map((cell, c) => (
                    <td key={c} className="px-3.5 py-1.5 whitespace-nowrap text-ink">
                      {cell === null ? <span className="text-faint">NULL</span> : String(cell)}
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
