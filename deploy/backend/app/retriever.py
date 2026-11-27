"""
GraphRAG 1-Stage retrieval + Skeleton Few-Shot retrieval.

Exact algorithmic parity with:
  - `src/retrieval/baseline.py` (TableSchemaIndex, semantic_linking_table_level,
    trace_table_paths, build_table_schema_context)
  - `src/retrieval/retrieval.py` (_extract_phrases, k_from_pct)
  - `src/generation/few_shot.py` (FewShotIndex, retrieve_few_shot_examples, format_few_shot_block)

Differences for production deployment:
  - Uses numpy float32 cosine similarity on L2-normalized embeddings so precomputed
    `.npy` indexes load in milliseconds on CPU without extra overhead.
  - Supports live skeleton masking via `LiveSkeletonMasker` for any unseen question.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np

from app.schema_graph import normalize_identifier
from app.settings import Settings
from app.skeleton_mask import LiveSkeletonMasker

logger = logging.getLogger(__name__)


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    mat = np.asarray(mat, dtype=np.float32)
    if mat.ndim == 1:
        norm = np.linalg.norm(mat)
        return mat / (norm if norm > 1e-12 else 1.0)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.where(norms > 1e-12, norms, 1.0)
    return mat / norms


def extract_phrases(
    query: str,
    max_ngram: int,
    stopword_mode: str = "edge",
    stopwords: tuple[str, ...] = (),
) -> list[str]:
    """Return unique word n-grams (up to max_ngram) from a cleaned query."""
    clean = re.sub(r"[^\w\s]", "", query.lower())
    words = clean.split()
    stop = set(stopwords)

    def ngrams(ws: list[str]) -> list[str]:
        return list(
            dict.fromkeys(
                " ".join(ws[i : i + length])
                for length in range(1, max_ngram + 1)
                for i in range(len(ws) - length + 1)
            )
        )

    all_phrases = ngrams(words)
    if stopword_mode == "remove":
        phrases = ngrams([w for w in words if w not in stop])
    elif stopword_mode == "edge":
        phrases = [
            p
            for p in all_phrases
            if p.split(" ", 1)[0] not in stop and p.rsplit(" ", 1)[-1] not in stop
        ]
    else:
        return all_phrases
    return phrases or all_phrases


def k_from_pct(pct: float, n: int) -> int:
    if pct <= 0 or n <= 0:
        return n
    return max(1, math.ceil(round(pct * n, 9)))


@dataclass
class TableSchemaIndex:
    db_name: str
    table_node_ids: list[str]
    table_names: list[str]
    table_embeddings: np.ndarray  # shape (n_tables, d), L2-normalized float32


@dataclass
class FewShotExample:
    question: str
    sql: str
    db_id: str
    skeleton: str
    score: float = 0.0


@dataclass
class RetrievalTrace:
    schema_context: str
    detected_tables: list[str]
    bridge_tables: list[str]
    selected_tables: list[str]
    table_scores: dict[str, float]
    question_skeleton: str | None
    few_shot_examples: list[FewShotExample]
    few_shot_block: str


class GraphRAG1StageRetriever:
    """Holds the embedding model, per-DB table indices, table graph, and skeleton few-shot index."""

    def __init__(
        self,
        settings: Settings,
        table_graph: nx.Graph,
        raw_tables_by_db: dict[str, dict[str, Any]],
        db_ids: list[str],
    ) -> None:
        from sentence_transformers import SentenceTransformer

        self.cfg = settings
        self.table_graph = table_graph
        self.embed_model = SentenceTransformer(settings.embedding_model)
        logger.info("Loaded embedding model: %s", settings.embedding_model)

        self.table_cache: dict[str, TableSchemaIndex] = {}
        for db_id in db_ids:
            self.table_cache[db_id] = self._build_table_index(db_id)
        logger.info("Built table indices for %d databases", len(self.table_cache))

        self.masker: LiveSkeletonMasker | None = None
        self.few_shot_examples: list[FewShotExample] = []
        self.few_shot_embeddings: np.ndarray | None = None

        if settings.few_shot_k > 0:
            self.masker = LiveSkeletonMasker(settings.spacy_model)
            for db_id in db_ids:
                if db_id in raw_tables_by_db:
                    self.masker.register_db(db_id, raw_tables_by_db[db_id])
            self._load_few_shot_index()

    def _encode(self, texts: list[str], batch_size: int = 128) -> np.ndarray:
        emb = self.embed_model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            batch_size=batch_size,
            show_progress_bar=False,
        )
        return _l2_normalize(emb)

    def _build_table_index(self, db_name: str) -> TableSchemaIndex:
        nodes = [
            (n, d)
            for n, d in self.table_graph.nodes(data=True)
            if d.get("database") == db_name and d.get("type") == "table"
        ]
        if not nodes:
            return TableSchemaIndex(db_name, [], [], np.zeros((0, 1), dtype=np.float32))

        table_node_ids: list[str] = []
        table_names: list[str] = []
        texts: list[str] = []

        for node_id, d in nodes:
            if self.cfg.embed_natural_names:
                t_name = d.get("table_natural") or d["table"]
                c_names = [c.get("ColumnNatural") or c["Column"] for c in d["columns"]]
            else:
                t_name = d["table"]
                c_names = [c["Column"] for c in d["columns"]]

            if self.cfg.baseline_embed_columns:
                col_names = " ".join(normalize_identifier(c) for c in c_names)
                texts.append(f"table {normalize_identifier(t_name)} columns {col_names}")
            else:
                texts.append(normalize_identifier(t_name))

            table_node_ids.append(node_id)
            table_names.append(d["table"])

        embeddings = self._encode(texts)
        return TableSchemaIndex(
            db_name=db_name,
            table_node_ids=table_node_ids,
            table_names=table_names,
            table_embeddings=embeddings,
        )

    def _load_few_shot_index(self) -> None:
        sk_path = self.cfg.train_skeletons_json
        if not sk_path.exists():
            logger.warning(
                "Train skeletons file not found at %s — few-shot retrieval disabled", sk_path
            )
            return

        rows = json.loads(sk_path.read_text(encoding="utf-8"))
        self.few_shot_examples = [
            FewShotExample(
                question=r["question"],
                sql=r["query"],
                db_id=r["db_id"],
                skeleton=r["skeleton"],
            )
            for r in rows
        ]

        npy_path = self.cfg.train_embeddings_npy
        if npy_path.exists():
            arr = np.load(npy_path)
            if arr.shape[0] == len(self.few_shot_examples):
                self.few_shot_embeddings = _l2_normalize(arr)
                logger.info(
                    "Loaded precomputed skeleton embeddings from %s (%s)",
                    npy_path,
                    self.few_shot_embeddings.shape,
                )
                return
            logger.warning(
                "Precomputed embeddings count (%d) != skeletons count (%d); recomputing",
                arr.shape[0],
                len(self.few_shot_examples),
            )

        logger.info("Encoding %d training skeletons with %s ...", len(rows), self.cfg.embedding_model)
        texts = [e.skeleton for e in self.few_shot_examples]
        self.few_shot_embeddings = self._encode(texts, batch_size=256)
        try:
            npy_path.parent.mkdir(parents=True, exist_ok=True)
            np.save(npy_path, self.few_shot_embeddings.astype(np.float16))
            logger.info("Cached training skeleton embeddings to %s", npy_path)
        except OSError:
            logger.debug("Could not cache embeddings to disk (read-only filesystem)")

    def _link_tables(self, db_id: str, question: str) -> tuple[list[str], dict[str, float]]:
        index = self.table_cache[db_id]
        if not index.table_node_ids:
            return [], {}

        if self.cfg.top_k_tables_pct <= 0 and self.cfg.table_similarity_threshold <= 0:
            return list(index.table_node_ids), {t: 1.0 for t in index.table_names}

        phrases = extract_phrases(
            question,
            self.cfg.max_ngram,
            self.cfg.query_stopword_mode,
            self.cfg.query_stopwords,
        )
        if not phrases:
            return list(index.table_node_ids), {t: 1.0 for t in index.table_names}

        phrase_emb = self._encode(phrases)  # (n_phrases, d)
        scores = phrase_emb @ index.table_embeddings.T  # (n_phrases, n_tables)
        max_scores = scores.max(axis=0)  # (n_tables,)
        ranked = np.argsort(-max_scores).tolist()

        table_scores = {
            index.table_names[i]: round(float(max_scores[i]), 4)
            for i in ranked
        }

        kept = [i for i in ranked if float(max_scores[i]) >= self.cfg.table_similarity_threshold]
        if self.cfg.top_k_tables_pct > 0:
            kept = kept[: k_from_pct(self.cfg.top_k_tables_pct, len(index.table_node_ids))]
        if not kept:
            kept = ranked[:1]  # fallback: never return an empty schema

        return [index.table_node_ids[i] for i in kept], table_scores

    def _trace_table_paths(self, detected_nodes: list[str]) -> list[str]:
        all_nodes = dict.fromkeys(detected_nodes)
        for i in range(len(detected_nodes)):
            for j in range(i + 1, len(detected_nodes)):
                try:
                    path = nx.shortest_path(self.table_graph, detected_nodes[i], detected_nodes[j])
                    all_nodes.update(dict.fromkeys(path))
                except nx.NetworkXNoPath:
                    pass
        return list(all_nodes)

    def _build_ddl(self, table_nodes: list[str]) -> str:
        lines: list[str] = []
        for node in table_nodes:
            if node not in self.table_graph.nodes:
                continue
            d = self.table_graph.nodes[node]
            table = d["table"]
            lines.append(f"CREATE TABLE {table} (")

            col_lines = []
            for col in d["columns"]:
                line = f"    {col['Column']} {col['Type']}"
                if col.get("is_pk") == "Yes":
                    line += " PRIMARY KEY"
                col_lines.append(line)

            fk_lines = []
            for _, neighbor, ed in self.table_graph.edges(node, data=True):
                if ed.get("relation") != "foreign_key":
                    continue
                neighbor_table = self.table_graph.nodes[neighbor]["table"]
                for fk in ed.get("fks", []):
                    if fk["from_table"] == node:
                        fk_lines.append(
                            f"    FOREIGN KEY ({fk['from_col']}) "
                            f"REFERENCES {neighbor_table}({fk['to_col']})"
                        )

            lines.append(",\n".join(col_lines + fk_lines))
            lines.append(");\n")

        return "\n".join(lines)

    def _retrieve_few_shot(self, db_id: str, question: str) -> tuple[str | None, list[FewShotExample], str]:
        k = self.cfg.few_shot_k
        if k <= 0 or self.few_shot_embeddings is None or not self.few_shot_examples:
            return None, [], ""

        skeleton = self.masker.mask(question, db_id) if self.masker is not None else question
        query_emb = self._encode([skeleton])[0]  # (d,)
        scores = self.few_shot_embeddings @ query_emb  # (n_train,)

        top_k = min(k, len(self.few_shot_examples))
        top_idx = np.argpartition(-scores, top_k - 1)[:top_k]
        top_idx = top_idx[np.argsort(-scores[top_idx])].tolist()

        picked = [
            FewShotExample(
                question=self.few_shot_examples[i].question,
                sql=self.few_shot_examples[i].sql,
                db_id=self.few_shot_examples[i].db_id,
                skeleton=self.few_shot_examples[i].skeleton,
                score=round(float(scores[i]), 4),
            )
            for i in top_idx
        ]

        block_lines = ["### Examples\n"]
        for idx, ex in enumerate(picked, start=1):
            block_lines.append(f"-- Example {idx}")
            block_lines.append(f"-- Q: {ex.question}")
            block_lines.append("-- A:")
            block_lines.append(ex.sql.strip())
            block_lines.append("")

        return skeleton, picked, "\n".join(block_lines) + "\n"

    def retrieve(self, db_id: str, question: str) -> RetrievalTrace:
        if db_id not in self.table_cache:
            raise KeyError(f"Unknown database: {db_id}")

        detected_nodes, table_scores = self._link_tables(db_id, question)
        traced_nodes = self._trace_table_paths(detected_nodes)

        detected_set = set(detected_nodes)
        detected_tables = [self.table_graph.nodes[n]["table"] for n in detected_nodes]
        bridge_tables = [self.table_graph.nodes[n]["table"] for n in traced_nodes if n not in detected_set]
        selected_tables = [self.table_graph.nodes[n]["table"] for n in traced_nodes]

        ddl = self._build_ddl(traced_nodes)
        skeleton, examples, few_shot_block = self._retrieve_few_shot(db_id, question)

        return RetrievalTrace(
            schema_context=ddl,
            detected_tables=detected_tables,
            bridge_tables=bridge_tables,
            selected_tables=selected_tables,
            table_scores=table_scores,
            question_skeleton=skeleton,
            few_shot_examples=examples,
            few_shot_block=few_shot_block,
        )
