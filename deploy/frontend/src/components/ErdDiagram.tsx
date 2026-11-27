import { useMemo } from "react";
import dagre from "@dagrejs/dagre";
import {
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import type { ForeignKeyEdge, TableInfo } from "../types/api";

type Highlight = "none" | "picked" | "bridge" | "dimmed";

interface TableNodeData extends Record<string, unknown> {
  table: TableInfo;
  highlight: Highlight;
  score?: number;
}

type TableFlowNode = Node<TableNodeData, "tableNode">;

const NODE_WIDTH = 240;
const ROW_HEIGHT = 22;
const HEADER_HEIGHT = 34;

function TableNode({ data }: NodeProps<TableFlowNode>) {
  const { table, highlight, score } = data;
  const frame =
    highlight === "picked"
      ? "border-accent"
      : highlight === "bridge"
        ? "border-accent/60 border-dashed"
        : "border-line-strong";

  return (
    <div
      className={`overflow-hidden rounded-md border bg-surface font-mono text-[11.5px] transition-opacity ${frame} ${
        highlight === "dimmed" ? "opacity-40" : ""
      }`}
      style={{ width: NODE_WIDTH }}
    >
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-0 !bg-line-strong" />
      <Handle type="source" position={Position.Right} className="!h-1.5 !w-1.5 !border-0 !bg-line-strong" />
      <div
        className={`flex items-center justify-between border-b px-3 ${
          highlight === "picked" ? "border-accent/40 bg-accent-soft" : "border-line bg-sunken"
        }`}
        style={{ height: HEADER_HEIGHT }}
      >
        <span className={`truncate font-medium ${highlight === "picked" ? "text-accent" : "text-ink"}`}>{table.name}</span>
        {highlight === "picked" && score !== undefined && <span className="text-[10.5px] text-accent">{score.toFixed(2)}</span>}
        {highlight === "bridge" && <span className="text-[10.5px] text-muted">join path</span>}
      </div>
      <div className="py-0.5">
        {table.columns.map((col) => (
          <div key={col.name} className="flex items-center justify-between gap-2 px-3" style={{ height: ROW_HEIGHT }}>
            <span className="truncate text-ink/90">{col.name}</span>
            <span className="shrink-0 text-[10.5px] text-faint">
              {col.is_pk ? "pk " : ""}
              {col.is_fk ? "fk " : ""}
              {col.type}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

const nodeTypes = { tableNode: TableNode };

function layout(
  tables: TableInfo[],
  fkEdges: ForeignKeyEdge[],
  picked: string[],
  bridge: string[],
  scores: Record<string, number>
): { nodes: TableFlowNode[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 48, ranksep: 200, marginx: 24, marginy: 24 });

  const heightOf = (t: TableInfo) => HEADER_HEIGHT + t.columns.length * ROW_HEIGHT + 6;
  for (const t of tables) g.setNode(t.name, { width: NODE_WIDTH, height: heightOf(t) });
  for (const e of fkEdges) if (g.hasNode(e.source) && g.hasNode(e.target)) g.setEdge(e.source, e.target);
  dagre.layout(g);

  const active = picked.length > 0 || bridge.length > 0;
  const pickedSet = new Set(picked);
  const bridgeSet = new Set(bridge);
  const inPath = new Set([...picked, ...bridge]);

  const nodes: TableFlowNode[] = tables.map((table) => {
    const pos = g.node(table.name);
    const highlight: Highlight = !active
      ? "none"
      : pickedSet.has(table.name)
        ? "picked"
        : bridgeSet.has(table.name)
          ? "bridge"
          : "dimmed";
    return {
      id: table.name,
      type: "tableNode",
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - heightOf(table) / 2 },
      data: { table, highlight, score: scores[table.name] },
    };
  });

  const edges: Edge[] = fkEdges.map((e) => {
    const lit = active && inPath.has(e.source) && inPath.has(e.target);
    const color = lit ? "var(--accent)" : "var(--line-strong)";
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      label: `${e.source_column} → ${e.target_column}`,
      style: { stroke: color, strokeWidth: lit ? 1.75 : 1.25, opacity: active && !lit ? 0.5 : 1 },
      labelStyle: { fill: lit ? "var(--accent)" : "var(--faint)", fontSize: 10.5, fontFamily: "var(--font-mono)" },
      labelBgStyle: { fill: "var(--bg)" },
      labelBgPadding: [4, 2] as [number, number],
      markerEnd: { type: MarkerType.ArrowClosed, color, width: 14, height: 14 },
    };
  });

  return { nodes, edges };
}

interface ErdDiagramProps {
  dbId: string;
  tables: TableInfo[];
  edges: ForeignKeyEdge[];
  pickedTables: string[];
  bridgeTables: string[];
  tableScores: Record<string, number>;
}

export function ErdDiagram({ dbId, tables, edges, pickedTables, bridgeTables, tableScores }: ErdDiagramProps) {
  const graph = useMemo(
    () => layout(tables, edges, pickedTables, bridgeTables, tableScores),
    [tables, edges, pickedTables, bridgeTables, tableScores]
  );

  return (
    <ReactFlow
      key={dbId}
      nodes={graph.nodes}
      edges={graph.edges}
      nodeTypes={nodeTypes}
      onInit={(flow) => requestAnimationFrame(() => flow.fitView({ padding: 0.15 }))}
      minZoom={0.2}
      maxZoom={1.75}
      nodesConnectable={false}
      proOptions={{ hideAttribution: true }}
    >
      <Controls position="bottom-left" showInteractive={false} />
    </ReactFlow>
  );
}
