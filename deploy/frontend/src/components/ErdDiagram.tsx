import { useMemo } from "react";
import dagre from "@dagrejs/dagre";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { KeyRound, Link2, Table2 } from "lucide-react";
import type { ForeignKeyEdge, TableInfo } from "../types/api";

type TableHighlight = "none" | "detected" | "bridge" | "dimmed";

interface TableNodeData extends Record<string, unknown> {
  table: TableInfo;
  highlight: TableHighlight;
  score?: number;
}

type TableFlowNode = Node<TableNodeData, "tableNode">;

function TableNode({ data }: NodeProps<TableFlowNode>) {
  const { table, highlight, score } = data;

  const containerStyle =
    highlight === "detected"
      ? "border-emerald-400 shadow-lg shadow-emerald-950/50 ring-2 ring-emerald-500/30"
      : highlight === "bridge"
        ? "border-amber-400 shadow-lg shadow-amber-950/50 ring-2 ring-amber-500/30"
        : highlight === "dimmed"
          ? "border-slate-800 opacity-45"
          : "border-slate-700";

  const headerStyle =
    highlight === "detected"
      ? "bg-emerald-950/80 text-emerald-100"
      : highlight === "bridge"
        ? "bg-amber-950/80 text-amber-100"
        : "bg-slate-800/95 text-slate-100";

  return (
    <div
      className={`min-w-[230px] max-w-[270px] overflow-hidden rounded-lg border bg-slate-900 text-xs transition ${containerStyle}`}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!h-2.5 !w-2.5 !border-slate-900 !bg-sky-400"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!h-2.5 !w-2.5 !border-slate-900 !bg-indigo-400"
      />

      <div className={`flex items-center justify-between gap-2 px-3 py-2 font-semibold ${headerStyle}`}>
        <div className="flex min-w-0 items-center gap-1.5">
          <Table2 className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate font-mono text-xs">{table.name}</span>
        </div>
        {highlight === "detected" && (
          <span className="shrink-0 rounded bg-emerald-500/25 px-1.5 py-0.5 text-[10px] font-medium text-emerald-200">
            {score !== undefined ? score.toFixed(2) : "Match"}
          </span>
        )}
        {highlight === "bridge" && (
          <span className="shrink-0 rounded bg-amber-500/25 px-1.5 py-0.5 text-[10px] font-medium text-amber-200">
            FK Path
          </span>
        )}
      </div>

      <div className="divide-y divide-slate-800/80 px-2.5 py-1">
        {table.columns.map((col) => (
          <div
            key={col.name}
            className="flex items-center justify-between gap-2 py-1 text-[11px]"
          >
            <div className="flex min-w-0 items-center gap-1.5">
              {col.is_pk ? (
                <KeyRound className="h-3 w-3 shrink-0 text-amber-400" />
              ) : col.is_fk ? (
                <Link2 className="h-3 w-3 shrink-0 text-sky-400" />
              ) : (
                <span className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-slate-600" />
              )}
              <span className="truncate font-mono text-slate-200">{col.name}</span>
            </div>
            <span className="shrink-0 font-mono text-[10px] uppercase text-slate-500">
              {col.type}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

const nodeTypes = { tableNode: TableNode };

function computeDagreLayout(
  tables: TableInfo[],
  fkEdges: ForeignKeyEdge[],
  detectedTables: string[],
  bridgeTables: string[],
  tableScores: Record<string, number>
): { nodes: TableFlowNode[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 60, ranksep: 110, marginx: 30, marginy: 30 });

  const nodeWidth = 250;
  for (const t of tables) {
    const estimatedHeight = 40 + t.columns.length * 24 + 12;
    g.setNode(t.name, { width: nodeWidth, height: estimatedHeight });
  }
  for (const e of fkEdges) {
    if (g.hasNode(e.source) && g.hasNode(e.target)) {
      g.setEdge(e.source, e.target);
    }
  }
  dagre.layout(g);

  const hasRetrieval = detectedTables.length > 0 || bridgeTables.length > 0;
  const detectedSet = new Set(detectedTables);
  const bridgeSet = new Set(bridgeTables);
  const activeSet = new Set([...detectedTables, ...bridgeTables]);

  const nodes: TableFlowNode[] = tables.map((table) => {
    const pos = g.node(table.name);
    const height = 40 + table.columns.length * 24 + 12;
    let highlight: TableHighlight = "none";
    if (hasRetrieval) {
      if (detectedSet.has(table.name)) highlight = "detected";
      else if (bridgeSet.has(table.name)) highlight = "bridge";
      else highlight = "dimmed";
    }
    return {
      id: table.name,
      type: "tableNode",
      position: { x: pos.x - nodeWidth / 2, y: pos.y - height / 2 },
      data: {
        table,
        highlight,
        score: tableScores[table.name],
      },
    };
  });

  const edges: Edge[] = fkEdges.map((e) => {
    const isActiveEdge = hasRetrieval && activeSet.has(e.source) && activeSet.has(e.target);
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      label: `${e.source_column} → ${e.target_column}`,
      animated: isActiveEdge,
      style: {
        stroke: isActiveEdge ? "#34d399" : hasRetrieval ? "#334155" : "#64748b",
        strokeWidth: isActiveEdge ? 2.2 : 1.4,
      },
      labelStyle: {
        fill: isActiveEdge ? "#a7f3d0" : "#94a3b8",
        fontSize: 10,
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
      },
      labelBgStyle: {
        fill: "#0f172a",
        fillOpacity: 0.9,
      },
      labelBgPadding: [4, 2] as [number, number],
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: isActiveEdge ? "#34d399" : "#64748b",
        width: 16,
        height: 16,
      },
    };
  });

  return { nodes, edges };
}

interface ErdDiagramProps {
  dbId: string;
  tables: TableInfo[];
  edges: ForeignKeyEdge[];
  detectedTables: string[];
  bridgeTables: string[];
  tableScores: Record<string, number>;
}

export function ErdDiagram({
  dbId,
  tables,
  edges,
  detectedTables,
  bridgeTables,
  tableScores,
}: ErdDiagramProps) {
  const layout = useMemo(
    () => computeDagreLayout(tables, edges, detectedTables, bridgeTables, tableScores),
    [tables, edges, detectedTables, bridgeTables, tableScores]
  );

  const hasHighlight = detectedTables.length > 0 || bridgeTables.length > 0;

  return (
    <div className="relative h-full w-full bg-slate-950">
      <ReactFlow
        key={dbId}
        nodes={layout.nodes}
        edges={layout.edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.25}
        maxZoom={1.75}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1e293b" gap={20} size={1} />
        <Controls position="bottom-left" />
        <MiniMap
          position="bottom-right"
          pannable
          zoomable
          nodeColor={(n) => {
            const d = n.data as TableNodeData;
            if (d?.highlight === "detected") return "#10b981";
            if (d?.highlight === "bridge") return "#f59e0b";
            return "#334155";
          }}
          maskColor="rgba(2, 6, 23, 0.75)"
          style={{ backgroundColor: "#0f172a", border: "1px solid #334155" }}
        />
      </ReactFlow>

      <div className="pointer-events-none absolute left-3 top-3 flex flex-wrap items-center gap-2 rounded-lg border border-slate-800 bg-slate-950/90 px-3 py-1.5 text-[11px] text-slate-300 backdrop-blur">
        <span className="inline-flex items-center gap-1">
          <KeyRound className="h-3 w-3 text-amber-400" /> PK
        </span>
        <span className="inline-flex items-center gap-1">
          <Link2 className="h-3 w-3 text-sky-400" /> FK
        </span>
        {hasHighlight && (
          <>
            <span className="text-slate-700">|</span>
            <span className="inline-flex items-center gap-1 text-emerald-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400" /> Stage-1 Match
            </span>
            <span className="inline-flex items-center gap-1 text-amber-300">
              <span className="h-2 w-2 rounded-full bg-amber-400" /> FK Bridge
            </span>
          </>
        )}
      </div>
    </div>
  );
}
