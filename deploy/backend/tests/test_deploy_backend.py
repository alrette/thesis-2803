"""Unit tests for the deploy backend (no GPU, no live LLM API key, no BGE-M3 download)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import app.main as main_mod
from app.llm_client import (
    GenerationOutput,
    LLMClient,
    LLMServiceError,
    build_prompt,
    classify_llm_exception,
    clean_sql,
)
from app.retriever import GraphRAG1StageRetriever, RetrievalTrace, extract_phrases
from app.schema_graph import build_table_graph, export_db_erd, load_spider_schema
from app.settings import DEFAULT_FEW_SHOT_K, DEFAULT_LLM_MODEL, Settings
from app.sql_runner import execute_readonly_sql


def test_defaults_match_cloudflare_and_zero_shot():
    assert DEFAULT_FEW_SHOT_K == 0
    assert DEFAULT_LLM_MODEL == "@cf/qwen/qwen2.5-coder-32b-instruct"


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

    # SQLite string function REPLACE(...) is allowed
    rep = execute_readonly_sql(db_path, "SELECT REPLACE(Name, 'a', 'A') AS clean_name FROM singer LIMIT 2")
    assert rep.ok is True
    assert rep.row_count == 2

    # Semicolons inside single-line and block comments (and apostrophes in comments) are allowed
    commented_line = execute_readonly_sql(
        db_path,
        "SELECT Name FROM singer -- don't fail; semicolon in comment\nWHERE Country = 'France'; -- trailing;",
    )
    assert commented_line.ok is True
    assert commented_line.row_count == 4

    commented_block = execute_readonly_sql(
        db_path,
        "/* header; DROP TABLE singer; */ SELECT Name FROM singer WHERE Age > 30 /* tail; */",
    )
    assert commented_block.ok is True
    assert commented_block.row_count >= 1

    # DML / write statements are blocked
    bad_delete = execute_readonly_sql(db_path, "DELETE FROM singer")
    assert bad_delete.ok is False
    assert "read-only" in (bad_delete.error or "").lower()

    bad_insert_replace = execute_readonly_sql(
        db_path,
        "INSERT OR REPLACE INTO singer (Singer_ID, Name) VALUES (99, 'Hack')",
    )
    assert bad_insert_replace.ok is False

    bad_replace_into = execute_readonly_sql(
        db_path,
        "REPLACE INTO singer (Singer_ID, Name) VALUES (99, 'Hack')",
    )
    assert bad_replace_into.ok is False

    bad_cte_replace = execute_readonly_sql(
        db_path,
        "WITH x AS (SELECT 1) REPLACE INTO singer (Singer_ID, Name) VALUES (99, 'Hack')",
    )
    assert bad_cte_replace.ok is False

    # Multi-statement is blocked
    multi = execute_readonly_sql(db_path, "SELECT 1; DROP TABLE singer")
    assert multi.ok is False
    assert "single" in (multi.error or "").lower()


def test_client_ip_uses_rightmost_xff_and_ignores_spoofed_cf_header():
    def _fake_request(headers: dict[str, str], host: str = "10.0.0.1"):
        lowered = {k.lower(): v for k, v in headers.items()}
        return SimpleNamespace(headers=lowered, client=SimpleNamespace(host=host))

    # Spoofed leftmost XFF + spoofed CF-Connecting-IP must be ignored on HF Spaces
    req = _fake_request(
        {
            "cf-connecting-ip": "1.2.3.4",
            "x-forwarded-for": "9.9.9.9, 203.0.113.42",
        }
    )
    assert main_mod._client_ip(req, trust_cf_connecting_ip=False) == "203.0.113.42"

    # Single XFF value
    req_single = _fake_request({"x-forwarded-for": "198.51.100.7"})
    assert main_mod._client_ip(req_single, trust_cf_connecting_ip=False) == "198.51.100.7"

    # Fallback to socket host when no XFF
    req_no_xff = _fake_request({"cf-connecting-ip": "1.2.3.4"}, host="127.0.0.1")
    assert main_mod._client_ip(req_no_xff, trust_cf_connecting_ip=False) == "127.0.0.1"

    # Explicit opt-in when backend is behind Cloudflare
    assert main_mod._client_ip(req, trust_cf_connecting_ip=True) == "1.2.3.4"


def test_llm_chat_sends_stop_and_recovers_from_empty_or_400():
    cfg = Settings(llm_api_key="", llm_model="@cf/qwen/qwen2.5-coder-32b-instruct", llm_api_mode="chat")
    client = LLMClient(cfg)

    # Case 1: returns valid SQL with stop=["```"]
    calls = []

    def _create_ok(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="SELECT count(*) FROM singer"))],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=10),
        )

    client._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create_ok)))
    out = client.generate_sql("How many singers?", "CREATE TABLE singer (id INT);")
    assert out.sql == "SELECT count(*) FROM singer"
    assert calls[0]["stop"] == ["```"]

    # Case 2: model starts with opening ``` so stop=["```"] yields empty; retries once without stop
    calls.clear()

    def _create_retry_empty(**kwargs):
        calls.append(kwargs)
        text = "" if "stop" in kwargs else "```sql\nSELECT count(*) FROM singer\n```"
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
            usage=None,
        )

    client._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create_retry_empty)))
    out2 = client.generate_sql("How many singers?", "CREATE TABLE singer (id INT);")
    assert out2.sql == "SELECT count(*) FROM singer"
    assert len(calls) == 2
    assert calls[0]["stop"] == ["```"]
    assert "stop" not in calls[1]


def test_classify_llm_exceptions_friendly():
    err_to = classify_llm_exception(TimeoutError("read timed out on upstream 10.0.0.5"))
    assert err_to.status_code == 504
    assert "10.0.0.5" not in err_to.user_message

    class FakeRateLimit(Exception):
        status_code = 429

    err_rl = classify_llm_exception(FakeRateLimit("Provider quota xyz"))
    assert err_rl.status_code == 429
    assert "xyz" not in err_rl.user_message

    err_other = classify_llm_exception(RuntimeError("Internal upstream stacktrace secret_token_123"))
    assert err_other.status_code == 502
    assert "secret_token_123" not in err_other.user_message


def test_zero_shot_startup_skips_spacy_and_embeddings(tmp_path: Path, monkeypatch):
    import numpy as np
    import scripts.create_demo_data as demo

    tables_path = tmp_path / "tables.json"
    tables_path.write_text(json.dumps(demo.DEMO_TABLES), encoding="utf-8")
    df, raw = load_spider_schema(tables_path)
    graph = build_table_graph(df)

    # Block spaCy import and point skeletons to non-existent paths
    monkeypatch.setitem(sys.modules, "spacy", None)

    class DummyEmbedder:
        def __init__(self, _name: str) -> None:
            pass

        def encode(self, texts, **_kwargs):
            return np.ones((len(texts), 8), dtype=np.float32)

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=DummyEmbedder),
    )

    cfg = Settings(
        few_shot_k=0,
        train_skeletons_json=tmp_path / "missing_train.json",
        train_embeddings_npy=tmp_path / "missing_embeddings.npy",
    )
    retriever = GraphRAG1StageRetriever(cfg, graph, raw, ["concert_singer"])
    assert retriever.masker is None
    assert retriever.few_shot_embeddings is None
    trace = retriever.retrieve("concert_singer", "How many singers?")
    assert trace.question_skeleton is None
    assert trace.few_shot_examples == []


def test_global_rate_limit_and_friendly_errors_on_generate_endpoint(monkeypatch):
    cfg = Settings(
        llm_api_key="",
        llm_model="@cf/qwen/qwen2.5-coder-32b-instruct",
        few_shot_k=0,
        rate_limit_per_minute=100,
        global_generate_per_minute=2,
        global_generate_per_day=50,
    )
    fake_state = main_mod.AppState(cfg)
    fake_state.catalog = {
        "concert_singer": {
            "db_id": "concert_singer",
            "display_name": "Concerts",
            "description": "",
            "table_count": 4,
            "column_count": 21,
            "fk_count": 3,
            "sample_questions": [],
        }
    }
    fake_state.ready = True

    fake_retriever = MagicMock()
    fake_retriever.retrieve.return_value = RetrievalTrace(
        schema_context="CREATE TABLE singer (Singer_ID INT);",
        detected_tables=["singer"],
        bridge_tables=[],
        selected_tables=["singer"],
        table_scores={"singer": 0.91},
        question_skeleton=None,
        few_shot_examples=[],
        few_shot_block="",
    )
    fake_state.retriever = fake_retriever

    fake_llm = MagicMock()
    fake_llm.is_configured = True
    fake_llm.generate_sql.return_value = GenerationOutput(
        sql="SELECT count(*) FROM singer",
        raw_output="SELECT count(*) FROM singer",
        prompt_tokens=120,
        completion_tokens=12,
        model=cfg.llm_model,
    )
    fake_state.llm = fake_llm

    monkeypatch.setattr(main_mod, "state", fake_state)

    client = TestClient(main_mod.app)

    # First 2 calls succeed even with different client IPs
    r1 = client.post(
        "/api/generate",
        json={"db_id": "concert_singer", "question": "How many singers?"},
        headers={"X-Forwarded-For": "198.51.100.1"},
    )
    assert r1.status_code == 200
    assert r1.json()["model"] == "@cf/qwen/qwen2.5-coder-32b-instruct"

    r2 = client.post(
        "/api/generate",
        json={"db_id": "concert_singer", "question": "How many singers?"},
        headers={"X-Forwarded-For": "198.51.100.2"},
    )
    assert r2.status_code == 200

    # 3rd call from yet another IP must hit the global per-minute limit (429)
    r3 = client.post(
        "/api/generate",
        json={"db_id": "concert_singer", "question": "How many singers?"},
        headers={"X-Forwarded-For": "198.51.100.3"},
    )
    assert r3.status_code == 429

    # Reset minute limit, verify raw provider error is never leaked to client
    fake_state.global_generate_minute_limiter = main_mod.RateLimiter(limit=10, window_seconds=60.0)
    fake_llm.generate_sql.side_effect = LLMServiceError(
        "Model sedang tidak bisa dihubungi, coba lagi sebentar.", status_code=502
    )
    r_err = client.post(
        "/api/generate",
        json={"db_id": "concert_singer", "question": "How many singers?"},
        headers={"X-Forwarded-For": "198.51.100.4"},
    )
    assert r_err.status_code == 502
    assert r_err.json()["detail"] == "Model sedang tidak bisa dihubungi, coba lagi sebentar."
