"""Unit tests for the deploy backend (no GPU, no LLM API key, no BGE-M3 download)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.llm_client import build_prompt, clean_sql
from app.retriever import extract_phrases
from app.schema_graph import build_table_graph, export_db_erd, load_spider_schema
from app.sql_runner import execute_readonly_sql


def test_clean_sql_strips_fences_and_aliases():
    raw = "```sql\nSELECT s.name FROM singer AS s WHERE s.age > 20;\n```\nExplanation: filters singers."
    assert clean_sql(raw) == "SELECT name FROM singer WHERE age > 20"

    joined = "```sql\nSELECT T1.Name FROM concert AS T1 JOIN stadium AS T2 ON T1.Stadium_ID = T2.Stadium_ID;\n```"
    assert (
        clean_sql(joined)
        == "SELECT T1.Name FROM concert AS T1 JOIN stadium AS T2 ON T1.Stadium_ID = T2.Stadium_ID"
    )


def test_build_prompt_modes():
    p_comp = build_prompt("How many singers?", "CREATE TABLE singer (id INT);", include_sql_fence_prefix=True)
    p_chat = build_prompt("How many singers?", "CREATE TABLE singer (id INT);", include_sql_fence_prefix=False)
    assert p_comp.endswith("### Answer\n```sql\n")
    assert p_chat.endswith("### Answer\n")


def test_extract_phrases_edge_stopwords():
    phrases = extract_phrases(
        "What are the names of the singers?",
        max_ngram=2,
        stopword_mode="edge",
        stopwords=("what", "are", "the", "of"),
    )
    assert "names" in phrases
    assert "singers" in phrases
    assert "of singers" not in phrases
    assert "the singers" not in phrases


def test_demo_bundle_erd_and_readonly_sql(tmp_path: Path):
    import scripts.create_demo_data as demo

    db_path = tmp_path / "concert_singer.sqlite"
    demo._create_concert_singer(db_path)

    tables_path = tmp_path / "tables.json"
    import json

    tables_path.write_text(json.dumps(demo.DEMO_TABLES), encoding="utf-8")
    df, _ = load_spider_schema(tables_path)
    graph = build_table_graph(df)
    erd = export_db_erd(graph, "concert_singer")

    assert erd["table_count"] == 4
    assert erd["fk_count"] == 3

    # Valid SELECT works
    res = execute_readonly_sql(db_path, "SELECT Name, Age FROM singer WHERE Country = 'France' ORDER BY Age ASC")
    assert res.ok is True
    assert res.columns == ["Name", "Age"]
    assert res.row_count == 4

    # DML is blocked
    bad = execute_readonly_sql(db_path, "DELETE FROM singer")
    assert bad.ok is False
    assert "read-only" in (bad.error or "").lower()

    # Multi-statement is blocked
    multi = execute_readonly_sql(db_path, "SELECT 1; DROP TABLE singer")
    assert multi.ok is False
    assert "single" in (multi.error or "").lower()
