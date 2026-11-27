import type { DatabaseDetail, DatabaseSummary, HealthResponse } from "../types/api";
import type { Theme } from "../lib/theme";
import { SchemaTree } from "./SchemaTree";
import { IconChevron, IconDiagram, IconMoon, IconSun } from "./icons";

interface SidebarProps {
  databases: DatabaseSummary[];
  listError: string | null;
  selectedDbId: string | null;
  onSelectDb: (dbId: string) => void;
  detail: DatabaseDetail | null;
  detailLoading: boolean;
  detailError: string | null;
  usedTables: string[];
  bridgeTables: string[];
  tableScores: Record<string, number>;
  onOpenErd: () => void;
  health: HealthResponse | null;
  healthError: string | null;
  theme: Theme;
  onToggleTheme: () => void;
}

export function Sidebar(props: SidebarProps) {
  const { databases, selectedDbId, detail } = props;

  return (
    <div className="flex h-full flex-col">
      <div className="px-5 pt-5 pb-4">
        <p className="text-[15px] font-semibold tracking-tight text-ink">Text-to-SQL Workbench</p>
        <p className="text-[13px] text-muted">GraphRAG 1-Stage on Spider databases</p>
      </div>

      <div className="px-5">
        <label htmlFor="db-select" className="mb-1.5 block text-[12px] font-medium text-muted">
          Database
        </label>
        <div className="relative">
          <select
            id="db-select"
            value={selectedDbId ?? ""}
            onChange={(e) => props.onSelectDb(e.target.value)}
            disabled={databases.length === 0}
            className="w-full appearance-none rounded-md border border-line bg-surface py-2 pr-8 pl-3 text-[14px] text-ink transition-colors hover:border-line-strong focus:border-accent focus:outline-none disabled:opacity-60"
          >
            {databases.length === 0 && <option value="">{props.listError ? "Unavailable" : "Loading…"}</option>}
            {databases.map((db) => (
              <option key={db.db_id} value={db.db_id}>
                {db.display_name}
              </option>
            ))}
          </select>
          <IconChevron
            size={12}
            className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 rotate-90 text-faint"
          />
        </div>
        {props.listError && <p className="mt-2 text-[12.5px] text-danger">{props.listError}</p>}
        {detail && (
          <p className="mt-2 text-[12.5px] text-muted">
            {detail.table_count} tables, {detail.column_count} columns, {detail.fk_count} foreign keys
          </p>
        )}
      </div>

      <div className="mt-5 flex items-center justify-between px-5">
        <span className="text-[12px] font-medium text-muted">Schema</span>
        <button
          type="button"
          onClick={props.onOpenErd}
          disabled={!detail}
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[12.5px] text-muted transition-colors hover:bg-sunken hover:text-ink disabled:opacity-50"
        >
          <IconDiagram size={14} />
          View ERD
        </button>
      </div>

      <div className="thin-scroll mt-1.5 min-h-0 flex-1 overflow-auto px-5 pb-4">
        {props.detailLoading && <p className="text-[13px] text-faint">Loading schema…</p>}
        {props.detailError && (
          <p className="text-[13px] text-danger">Could not load the schema: {props.detailError}</p>
        )}
        {detail && !props.detailLoading && (
          <SchemaTree
            key={detail.db_id}
            detail={detail}
            usedTables={props.usedTables}
            bridgeTables={props.bridgeTables}
            tableScores={props.tableScores}
          />
        )}
      </div>

      <Footer health={props.health} healthError={props.healthError} theme={props.theme} onToggleTheme={props.onToggleTheme} />
    </div>
  );
}

function Footer({
  health,
  healthError,
  theme,
  onToggleTheme,
}: Pick<SidebarProps, "health" | "healthError" | "theme" | "onToggleTheme">) {
  const state = healthError
    ? { label: "Backend unreachable", tone: "bg-danger" }
    : !health
      ? { label: "Connecting…", tone: "bg-faint" }
      : !health.ready
        ? { label: "Backend starting", tone: "bg-faint" }
        : !health.llm_configured
          ? { label: "Model not configured", tone: "bg-danger" }
          : { label: "Connected", tone: "bg-ok" };

  return (
    <div className="flex items-end justify-between gap-3 border-t border-line px-5 py-3.5">
      <div className="min-w-0 text-[12px] leading-5 text-muted">
        <p className="flex items-center gap-2">
          <span className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${state.tone}`} aria-hidden="true" />
          {state.label}
        </p>
        {health && (
          <>
            <p className="truncate text-faint" title={health.llm_model}>
              {health.llm_model.split("/").pop()}
            </p>
            <p className="text-faint">few-shot k = {health.few_shot_k}</p>
          </>
        )}
      </div>
      <button
        type="button"
        onClick={onToggleTheme}
        className="shrink-0 rounded-md p-1.5 text-muted transition-colors hover:bg-sunken hover:text-ink"
        aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      >
        {theme === "dark" ? <IconSun size={15} /> : <IconMoon size={15} />}
      </button>
    </div>
  );
}
