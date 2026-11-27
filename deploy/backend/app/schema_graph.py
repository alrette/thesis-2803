"""
Schema processing, NetworkX table-level graph construction, and ERD serialization.

Mirrors `src/core/schema.py` (`normalize_identifier`, `load_spider_schema`) and
`src/retrieval/baseline.py` (`build_table_graph`), plus adds JSON ERD export for
the React Flow frontend.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd

logger = logging.getLogger(__name__)


def normalize_identifier(name: str) -> str:
    """Humanize a raw SQL identifier for embedding: Stadium_ID -> 'stadium id'."""
    s = name.replace("_", " ")
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def load_spider_schema(json_path: Path) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    """
    Parse Spider's tables.json into:
      1. Flat DataFrame with one row per column (same shape as src/core/schema.py)
      2. Raw db_id -> tables.json entry mapping (used by live skeleton masking)
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_by_db: dict[str, dict[str, Any]] = {}
    records: list[dict[str, Any]] = []

    for db in data:
        db_id = db["db_id"]
        raw_by_db[db_id] = db
        table_names = db["table_names_original"]
        column_names = db["column_names_original"]
        table_natural = db.get("table_names", table_names)
        column_natural = db.get("column_names", column_names)
        column_types = db["column_types"]
        primary_keys = set(db["primary_keys"])
        fk_map = {fk[0]: fk[1] for fk in db["foreign_keys"]}

        for col_idx, (table_idx, col_name) in enumerate(column_names):
            table_name = table_names[table_idx] if table_idx != -1 else "ALL"

            fk_relation = "-"
            if col_idx in fk_map:
                target_idx = fk_map[col_idx]
                t_table_idx, t_col_name = column_names[target_idx]
                fk_relation = f"{table_names[t_table_idx]}.{t_col_name}"

            records.append(
                {
                    "Database": db_id,
                    "Table": table_name,
                    "Column": col_name,
                    "Type": column_types[col_idx],
                    "PK": "Yes" if col_idx in primary_keys else "No",
                    "FK_Relation": fk_relation,
                    "TableNatural": table_natural[table_idx] if table_idx != -1 else "ALL",
                    "ColumnNatural": column_natural[col_idx][1],
                }
            )

    return pd.DataFrame(records), raw_by_db


def build_table_graph(schema_df: pd.DataFrame) -> nx.Graph:
    """
    Build the GraphRAG 1-Stage table-level graph (exact match with baseline.py):
      - Node = '{db}.{table}' carrying all columns + table_natural
      - Edge = 'foreign_key' carrying directional fks list [{from_table, from_col, to_col}]
    """
    G = nx.Graph()
    df_clean = schema_df[schema_df["Column"] != "*"].copy()

    for (db, table), group in df_clean.groupby(["Database", "Table"], sort=False):
        node_id = f"{db}.{table}"
        natural_cols = ["ColumnNatural"] if "ColumnNatural" in group else []
        columns = (
            group[["Column", "Type", "PK", "FK_Relation"] + natural_cols]
            .rename(columns={"PK": "is_pk"})
            .to_dict("records")
        )
        G.add_node(
            node_id,
            database=db,
            table=table,
            table_natural=str(group["TableNatural"].iloc[0]) if "TableNatural" in group else table,
            columns=columns,
            type="table",
        )

    fk_rows = df_clean[df_clean["FK_Relation"] != "-"]
    for _, row in fk_rows.iterrows():
        src = f"{row['Database']}.{row['Table']}"
        parts = str(row["FK_Relation"]).split(".")
        if len(parts) != 2:
            continue
        tgt_table, tgt_col = parts
        tgt = f"{row['Database']}.{tgt_table}"
        if not (G.has_node(src) and G.has_node(tgt)):
            continue
        fk = {"from_table": src, "from_col": row["Column"], "to_col": tgt_col}
        if G.has_edge(src, tgt):
            G.edges[src, tgt]["fks"].append(fk)
        else:
            G.add_edge(
                src,
                tgt,
                relation="foreign_key",
                fks=[fk],
                from_col=row["Column"],
                to_col=tgt_col,
            )

    logger.info("Table graph built: %d table nodes, %d FK edges", G.number_of_nodes(), G.number_of_edges())
    return G


def export_db_erd(graph: nx.Graph, db_id: str) -> dict[str, Any]:
    """
    Serialize one database's table-level graph into JSON tables + directed FK edges
    for the Schema Explorer and React Flow ERD.
    """
    tables: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    db_nodes = [
        (node_id, data)
        for node_id, data in graph.nodes(data=True)
        if data.get("database") == db_id and data.get("type") == "table"
    ]

    for node_id, data in db_nodes:
        cols_out = []
        for col in data.get("columns", []):
            fk_rel = str(col.get("FK_Relation", "-"))
            cols_out.append(
                {
                    "name": col["Column"],
                    "natural_name": col.get("ColumnNatural") or col["Column"],
                    "type": col["Type"],
                    "is_pk": col.get("is_pk") == "Yes",
                    "is_fk": fk_rel != "-",
                    "references": None if fk_rel == "-" else fk_rel,
                }
            )
        tables.append(
            {
                "id": data["table"],
                "node_id": node_id,
                "name": data["table"],
                "natural_name": data.get("table_natural") or data["table"],
                "columns": cols_out,
            }
        )

    seen_edges: set[tuple[str, str, str, str]] = set()
    for u, v, ed in graph.edges(data=True):
        if graph.nodes[u].get("database") != db_id or ed.get("relation") != "foreign_key":
            continue
        for fk in ed.get("fks", []):
            src_node = fk["from_table"]
            tgt_node = v if src_node == u else u
            src_table = graph.nodes[src_node]["table"]
            tgt_table = graph.nodes[tgt_node]["table"]
            key = (src_table, fk["from_col"], tgt_table, fk["to_col"])
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append(
                {
                    "id": f"{src_table}.{fk['from_col']}->{tgt_table}.{fk['to_col']}",
                    "source": src_table,
                    "source_column": fk["from_col"],
                    "target": tgt_table,
                    "target_column": fk["to_col"],
                }
            )

    return {
        "db_id": db_id,
        "table_count": len(tables),
        "column_count": sum(len(t["columns"]) for t in tables),
        "fk_count": len(edges),
        "tables": tables,
        "edges": edges,
    }
