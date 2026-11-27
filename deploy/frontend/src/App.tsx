import { useEffect, useState } from "react";
import { Columns3, GitFork, Loader2, Network, Table2 } from "lucide-react";
import { DatabaseSelector } from "./components/DatabaseSelector";
import { ErdDiagram } from "./components/ErdDiagram";
import { Header } from "./components/Header";
import { QueryWorkspace } from "./components/QueryWorkspace";
import { ResultsTable } from "./components/ResultsTable";
import { SchemaExplorer } from "./components/SchemaExplorer";
import {
  executeSql,
  fetchDatabaseDetail,
  fetchDatabases,
  fetchHealth,
  generateSql,
} from "./lib/api";
import type {
  DatabaseDetail,
  DatabaseSummary,
  ExecuteResponse,
  GenerateResponse,
  HealthResponse,
} from "./types/api";

type SchemaViewMode = "erd" | "tables";

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  const [databases, setDatabases] = useState<DatabaseSummary[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [selectedDbId, setSelectedDbId] = useState<string | null>(null);
  const [dbDetail, setDbDetail] = useState<DatabaseDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [schemaView, setSchemaView] = useState<SchemaViewMode>("erd");

  const [question, setQuestion] = useState("");
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [generation, setGeneration] = useState<GenerateResponse | null>(null);
  const [sqlDraft, setSqlDraft] = useState("");

  const [executing, setExecuting] = useState(false);
  const [execError, setExecError] = useState<string | null>(null);
  const [execResult, setExecResult] = useState<ExecuteResponse | null>(null);

  useEffect(() => {
    let active = true;

    fetchHealth()
      .then((h) => {
        if (active) setHealth(h);
      })
      .catch((err: unknown) => {
        if (active) setHealthError(err instanceof Error ? err.message : "Backend unreachable");
      });

    fetchDatabases()
      .then((dbs) => {
        if (active) setDatabases(dbs);
      })
      .catch((err: unknown) => {
        if (active) setListError(err instanceof Error ? err.message : "Failed to load databases");
      })
      .finally(() => {
        if (active) setLoadingList(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const handleSelectDb = async (dbId: string) => {
    setSelectedDbId(dbId);
    setDbDetail(null);
    setDetailError(null);
    setLoadingDetail(true);
    setQuestion("");
    setGeneration(null);
    setGenerateError(null);
    setSqlDraft("");
    setExecResult(null);
    setExecError(null);

    try {
      const detail = await fetchDatabaseDetail(dbId);
      setDbDetail(detail);
    } catch (err: unknown) {
      setDetailError(err instanceof Error ? err.message : "Failed to load database schema");
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleBackToPicker = () => {
    setSelectedDbId(null);
    setDbDetail(null);
    setGeneration(null);
    setSqlDraft("");
    setExecResult(null);
    setExecError(null);
  };

  const handleGenerate = async () => {
    if (!selectedDbId || !question.trim()) return;
    setGenerating(true);
    setGenerateError(null);
    setExecResult(null);
    setExecError(null);

    try {
      const res = await generateSql(selectedDbId, question.trim());
      setGeneration(res);
      setSqlDraft(res.sql);
    } catch (err: unknown) {
      setGenerateError(err instanceof Error ? err.message : "Failed to generate SQL");
    } finally {
      setGenerating(false);
    }
  };

  const handleExecute = async () => {
    if (!selectedDbId || !sqlDraft.trim()) return;
    setExecuting(true);
    setExecError(null);

    try {
      const res = await executeSql(selectedDbId, sqlDraft.trim());
      setExecResult(res);
    } catch (err: unknown) {
      setExecError(err instanceof Error ? err.message : "Failed to execute SQL");
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <Header
        health={health}
        healthError={healthError}
        selectedDbName={dbDetail?.display_name ?? selectedDbId}
        onBackToPicker={handleBackToPicker}
      />

      {!selectedDbId ? (
        <DatabaseSelector
          databases={databases}
          loading={loadingList}
          error={listError}
          onSelect={handleSelectDb}
        />
      ) : loadingDetail ? (
        <div className="flex h-[70vh] flex-col items-center justify-center gap-3 text-slate-400">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
          <p className="text-sm">Loading database schema and ERD…</p>
        </div>
      ) : detailError || !dbDetail ? (
        <div className="mx-auto max-w-2xl px-4 py-12">
          <div className="rounded-xl border border-rose-500/30 bg-rose-950/30 p-5 text-sm text-rose-200">
            <p className="font-semibold">Failed to load database</p>
            <p className="mt-1 text-xs">{detailError}</p>
            <button
              type="button"
              onClick={handleBackToPicker}
              className="mt-4 rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-800"
            >
              Back to Database List
            </button>
          </div>
        </div>
      ) : (
        <main className="mx-auto max-w-[1600px] px-4 py-5 sm:px-6">
          {/* Database summary bar */}
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-white">{dbDetail.display_name}</h2>
                <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[11px] text-slate-400">
                  {dbDetail.db_id}
                </span>
              </div>
              {dbDetail.description && (
                <p className="mt-0.5 text-xs text-slate-400">{dbDetail.description}</p>
              )}
            </div>

            <div className="flex items-center gap-4 text-xs text-slate-300">
              <span className="inline-flex items-center gap-1.5">
                <Table2 className="h-3.5 w-3.5 text-sky-400" />
                {dbDetail.table_count} tables
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Columns3 className="h-3.5 w-3.5 text-emerald-400" />
                {dbDetail.column_count} columns
              </span>
              <span className="inline-flex items-center gap-1.5">
                <GitFork className="h-3.5 w-3.5 text-amber-400" />
                {dbDetail.fk_count} foreign keys
              </span>
            </div>
          </div>

          {/* Two-column workbench: Step 2 (Schema & ERD) + Steps 3-5 (Query & Results) */}
          <div className="grid gap-5 lg:grid-cols-12">
            {/* Left column: Step 2 — Interactive ERD & Table/Column Explorer */}
            <section className="flex h-[560px] flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 lg:col-span-6 lg:h-[calc(100vh-185px)]">
              <div className="flex items-center justify-between border-b border-slate-800 px-3.5 py-2.5">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Step 2 • Schema &amp; Interactive ERD
                </span>
                <div className="inline-flex rounded-lg border border-slate-800 bg-slate-950 p-0.5 text-xs">
                  <button
                    type="button"
                    onClick={() => setSchemaView("erd")}
                    className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 transition ${
                      schemaView === "erd"
                        ? "bg-indigo-600 text-white"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    <Network className="h-3.5 w-3.5" />
                    ERD
                  </button>
                  <button
                    type="button"
                    onClick={() => setSchemaView("tables")}
                    className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 transition ${
                      schemaView === "tables"
                        ? "bg-indigo-600 text-white"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    <Table2 className="h-3.5 w-3.5" />
                    Tables ({dbDetail.table_count})
                  </button>
                </div>
              </div>

              <div className="min-h-0 flex-1">
                {schemaView === "erd" ? (
                  <ErdDiagram
                    dbId={dbDetail.db_id}
                    tables={dbDetail.tables}
                    edges={dbDetail.edges}
                    detectedTables={generation?.detected_tables ?? []}
                    bridgeTables={generation?.bridge_tables ?? []}
                    tableScores={generation?.table_scores ?? {}}
                  />
                ) : (
                  <SchemaExplorer
                    tables={dbDetail.tables}
                    detectedTables={generation?.detected_tables ?? []}
                    bridgeTables={generation?.bridge_tables ?? []}
                    tableScores={generation?.table_scores ?? {}}
                  />
                )}
              </div>
            </section>

            {/* Right column: Steps 3-5 — Sample Questions, Generate SQL, Run SQL Results */}
            <section className="space-y-4 lg:col-span-6">
              <QueryWorkspace
                sampleQuestions={dbDetail.sample_questions}
                question={question}
                onQuestionChange={setQuestion}
                onGenerate={handleGenerate}
                generating={generating}
                generateError={generateError}
                generation={generation}
                sqlDraft={sqlDraft}
                onSqlDraftChange={setSqlDraft}
                onExecute={handleExecute}
                executing={executing}
              />

              <ResultsTable result={execResult} error={execError} />
            </section>
          </div>
        </main>
      )}
    </div>
  );
}
