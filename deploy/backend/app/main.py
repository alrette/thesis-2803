"""
FastAPI backend for the GraphRAG 1-Stage + Skeleton Few-Shot user evaluation workbench.

Endpoints:
  GET  /health                     — readiness + model/config metadata
  GET  /api/databases              — curated Spider databases (Step 1)
  GET  /api/databases/{db_id}      — tables, columns, ERD edges, sample questions (Steps 2 & 3)
  POST /api/generate               — GraphRAG 1-Stage + Skeleton Few-Shot -> SQL (Step 4)
  POST /api/execute                — read-only SQLite execution (Step 5)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.llm_client import LLMClient
from app.retriever import GraphRAG1StageRetriever
from app.schema_graph import build_table_graph, export_db_erd, load_spider_schema
from app.settings import Settings, get_settings
from app.sql_runner import execute_readonly_sql

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Simple in-memory per-IP sliding-window rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit = limit_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, client_ip: str) -> None:
        if self.limit <= 0:
            return
        now = time.monotonic()
        cutoff = now - 60.0
        with self._lock:
            q = self._hits[client_ip]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.limit:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please wait a moment and try again.",
                )
            q.append(now)


# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

class AppState:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.rate_limiter = RateLimiter(settings.rate_limit_per_minute)
        self.catalog: dict[str, dict[str, Any]] = {}
        self.erds: dict[str, dict[str, Any]] = {}
        self.db_paths: dict[str, Path] = {}
        self.retriever: GraphRAG1StageRetriever | None = None
        self.llm: LLMClient = LLMClient(settings)
        self.ready: bool = False
        self.startup_error: str | None = None

    def load(self) -> None:
        try:
            if not self.settings.catalog_json.exists() or not self.settings.tables_json.exists():
                raise FileNotFoundError(
                    f"Missing data bundle in {self.settings.data_dir}. "
                    "Run `python scripts/prepare_spider_bundle.py --spider-dir <path>` "
                    "or `python scripts/create_demo_data.py`."
                )

            catalog_raw = json.loads(self.settings.catalog_json.read_text(encoding="utf-8"))
            schema_df, raw_tables = load_spider_schema(self.settings.tables_json)
            table_graph = build_table_graph(schema_df)

            curated_ids: list[str] = []
            for entry in catalog_raw.get("databases", []):
                db_id = entry["db_id"]
                sqlite_path = self.settings.databases_dir / db_id / f"{db_id}.sqlite"
                if not sqlite_path.exists():
                    logger.warning("Skipping %s: SQLite file not found at %s", db_id, sqlite_path)
                    continue
                erd = export_db_erd(table_graph, db_id)
                self.catalog[db_id] = {
                    **entry,
                    "table_count": erd["table_count"],
                    "column_count": erd["column_count"],
                    "fk_count": erd["fk_count"],
                }
                self.erds[db_id] = erd
                self.db_paths[db_id] = sqlite_path
                curated_ids.append(db_id)

            if not curated_ids:
                raise RuntimeError("No valid curated SQLite databases found in data/databases/.")

            self.retriever = GraphRAG1StageRetriever(
                settings=self.settings,
                table_graph=table_graph,
                raw_tables_by_db=raw_tables,
                db_ids=curated_ids,
            )
            self.ready = True
            logger.info("Backend ready with %d databases: %s", len(curated_ids), curated_ids)
        except Exception as exc:  # noqa: BLE001
            self.startup_error = str(exc)
            logger.exception("Failed to initialize backend state")


state: AppState | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global state
    settings = get_settings()
    state = AppState(settings)
    state.load()
    yield


settings_boot = get_settings()
app = FastAPI(
    title="GraphRAG 1-Stage Text-to-SQL API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings_boot.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    db_id: str = Field(..., min_length=1, max_length=120)
    question: str = Field(..., min_length=2, max_length=1000)


class FewShotItem(BaseModel):
    question: str
    sql: str
    db_id: str
    score: float


class GenerateResponse(BaseModel):
    db_id: str
    question: str
    sql: str
    selected_tables: list[str]
    detected_tables: list[str]
    bridge_tables: list[str]
    table_scores: dict[str, float]
    schema_ddl: str
    question_skeleton: str | None
    few_shot_k: int
    few_shot_examples: list[FewShotItem]
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    retrieval_ms: float
    generation_ms: float
    total_ms: float


class ExecuteRequest(BaseModel):
    db_id: str = Field(..., min_length=1, max_length=120)
    sql: str = Field(..., min_length=1, max_length=5000)


class ExecuteResponse(BaseModel):
    ok: bool
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    execution_ms: float
    error: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_ready() -> AppState:
    if state is None or not state.ready or state.retriever is None:
        detail = state.startup_error if state and state.startup_error else "Service is starting up."
        raise HTTPException(status_code=503, detail=detail)
    return state


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, Any]:
    s = state
    cfg = s.settings if s else settings_boot
    return {
        "status": "ok" if (s and s.ready) else "degraded",
        "ready": bool(s and s.ready),
        "llm_configured": bool(s and s.llm.is_configured),
        "database_count": len(s.catalog) if s else 0,
        "pipeline": "graphrag-1stage-skeleton-fewshot",
        "embedding_model": cfg.embedding_model,
        "llm_model": cfg.llm_model,
        "table_threshold": cfg.table_similarity_threshold,
        "few_shot_k": cfg.few_shot_k,
        "error": s.startup_error if s else None,
    }


@app.get("/api/databases")
def list_databases() -> dict[str, Any]:
    s = _require_ready()
    items = [
        {
            "db_id": db_id,
            "display_name": meta.get("display_name", db_id),
            "description": meta.get("description", ""),
            "table_count": meta["table_count"],
            "column_count": meta["column_count"],
            "fk_count": meta["fk_count"],
            "sample_question_count": len(meta.get("sample_questions", [])),
        }
        for db_id, meta in s.catalog.items()
    ]
    return {"databases": items}


@app.get("/api/databases/{db_id}")
def get_database_detail(db_id: str) -> dict[str, Any]:
    s = _require_ready()
    if db_id not in s.catalog:
        raise HTTPException(status_code=404, detail=f"Database '{db_id}' not found.")
    meta = s.catalog[db_id]
    erd = s.erds[db_id]
    return {
        "db_id": db_id,
        "display_name": meta.get("display_name", db_id),
        "description": meta.get("description", ""),
        "table_count": erd["table_count"],
        "column_count": erd["column_count"],
        "fk_count": erd["fk_count"],
        "tables": erd["tables"],
        "edges": erd["edges"],
        "sample_questions": meta.get("sample_questions", []),
    }


@app.post("/api/generate", response_model=GenerateResponse)
def generate_sql_endpoint(payload: GenerateRequest, request: Request) -> GenerateResponse:
    s = _require_ready()
    s.rate_limiter.check(_client_ip(request))

    if payload.db_id not in s.catalog:
        raise HTTPException(status_code=404, detail=f"Database '{payload.db_id}' not found.")

    if not s.llm.is_configured:
        raise HTTPException(
            status_code=503,
            detail="LLM API is not configured on the server (missing LLM_API_KEY).",
        )

    t0 = time.perf_counter()
    trace = s.retriever.retrieve(payload.db_id, payload.question.strip())
    t1 = time.perf_counter()

    try:
        gen = s.llm.generate_sql(
            question=payload.question.strip(),
            schema_context=trace.schema_context,
            few_shot_block=trace.few_shot_block,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM generation failed")
        raise HTTPException(status_code=502, detail=f"SQL generation failed: {exc}") from exc

    t2 = time.perf_counter()
    return GenerateResponse(
        db_id=payload.db_id,
        question=payload.question.strip(),
        sql=gen.sql,
        selected_tables=trace.selected_tables,
        detected_tables=trace.detected_tables,
        bridge_tables=trace.bridge_tables,
        table_scores=trace.table_scores,
        schema_ddl=trace.schema_context,
        question_skeleton=trace.question_skeleton,
        few_shot_k=s.settings.few_shot_k,
        few_shot_examples=[
            FewShotItem(
                question=ex.question,
                sql=ex.sql,
                db_id=ex.db_id,
                score=ex.score,
            )
            for ex in trace.few_shot_examples
        ],
        model=gen.model,
        prompt_tokens=gen.prompt_tokens,
        completion_tokens=gen.completion_tokens,
        retrieval_ms=round((t1 - t0) * 1000, 1),
        generation_ms=round((t2 - t1) * 1000, 1),
        total_ms=round((t2 - t0) * 1000, 1),
    )


@app.post("/api/execute", response_model=ExecuteResponse)
def execute_sql_endpoint(payload: ExecuteRequest, request: Request) -> ExecuteResponse:
    s = _require_ready()
    s.rate_limiter.check(_client_ip(request))

    db_path = s.db_paths.get(payload.db_id)
    if db_path is None:
        raise HTTPException(status_code=404, detail=f"Database '{payload.db_id}' not found.")

    res = execute_readonly_sql(
        db_path=db_path,
        sql=payload.sql,
        timeout_sec=s.settings.sql_exec_timeout_sec,
        max_rows=s.settings.sql_max_rows,
    )
    return ExecuteResponse(
        ok=res.ok,
        columns=res.columns,
        rows=res.rows,
        row_count=res.row_count,
        truncated=res.truncated,
        execution_ms=res.execution_ms,
        error=res.error,
    )
