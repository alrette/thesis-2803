"""
Configuration for the GraphRAG 1-Stage + Skeleton Few-Shot deployment backend.

All retrieval hyperparameters mirror `src/core/config.py` (PipelineConfig) so the
deployed user-evaluation service stays faithful to the thesis method.

To change the fixed few-shot k, edit `FEW_SHOT_K` below (or override via env var).
"""

from dataclasses import dataclass, field
import os
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


BASE_DIR = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> None:
    """Load key=value pairs from local .env without overriding real environment variables."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))

# ---------------------------------------------------------------------------
# Researcher-controlled fixed defaults (edit here or override via HF Secrets)
# ---------------------------------------------------------------------------
# Fixed few-shot k (set 0 to disable few-shot & spaCy masking, or 1 / 3 / 5 / 9).
DEFAULT_FEW_SHOT_K: int = 3
# GraphRAG 1-Stage table similarity threshold (thesis config.py poin 46).
DEFAULT_TABLE_THRESHOLD: float = 0.65
# Default LLM model (Qwen2.5-Coder-7B-Instruct via OpenAI-compatible API).
DEFAULT_LLM_MODEL: str = "Qwen/Qwen2.5-Coder-7B-Instruct"


@dataclass(frozen=True)
class Settings:
    # --- Paths ---
    data_dir: Path = DATA_DIR
    databases_dir: Path = DATA_DIR / "databases"
    tables_json: Path = DATA_DIR / "tables.json"
    catalog_json: Path = DATA_DIR / "catalog.json"
    train_skeletons_json: Path = DATA_DIR / "skeletons" / "train.json"
    train_embeddings_npy: Path = DATA_DIR / "skeletons" / "train_embeddings.npy"

    # --- Embedding & GraphRAG 1-Stage retrieval (exact parity with src/core/config.py) ---
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"))
    table_similarity_threshold: float = field(
        default_factory=lambda: float(os.getenv("TABLE_SIMILARITY_THRESHOLD", str(DEFAULT_TABLE_THRESHOLD)))
    )
    top_k_tables_pct: float = field(
        default_factory=lambda: float(os.getenv("TOP_K_TABLES_PCT", "0.0"))
    )
    embed_natural_names: bool = field(
        default_factory=lambda: _env_bool("EMBED_NATURAL_NAMES", True)
    )
    baseline_embed_columns: bool = field(
        default_factory=lambda: _env_bool("BASELINE_EMBED_COLUMNS", False)
    )
    max_ngram: int = 2
    query_stopword_mode: str = "edge"
    query_stopwords: tuple[str, ...] = (
        "what", "which", "who", "whom", "whose", "how", "when", "where",
        "show", "list", "give", "find", "tell", "return", "display", "me",
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "do", "does", "did",
        "of", "for", "with", "and", "or", "that", "this", "these", "those",
        "have", "has", "had", "their", "its", "it", "there",
    )

    # --- Skeleton Few-Shot ---
    few_shot_selection: str = "skeleton"
    few_shot_k: int = field(
        default_factory=lambda: int(os.getenv("FEW_SHOT_K", str(DEFAULT_FEW_SHOT_K)))
    )
    spacy_model: str = field(default_factory=lambda: os.getenv("SPACY_MODEL", "en_core_web_sm"))

    # --- LLM via OpenAI-compatible API ---
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", ""))
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL))
    # "chat" -> /v1/chat/completions (widest provider support)
    # "completion" -> /v1/completions (byte-for-byte parity with raw prompt)
    llm_api_mode: str = field(default_factory=lambda: os.getenv("LLM_API_MODE", "chat").strip().lower())
    llm_timeout_sec: float = field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT_SEC", "60.0")))
    max_new_tokens: int = 256
    temperature: float = 0.0
    sql_stop_strings: tuple[str, ...] = ("```",)

    # --- SQLite execution safety ---
    sql_exec_timeout_sec: float = field(default_factory=lambda: float(os.getenv("SQL_EXEC_TIMEOUT_SEC", "5.0")))
    sql_max_rows: int = field(default_factory=lambda: int(os.getenv("SQL_MAX_ROWS", "200")))

    # --- API / Security ---
    cors_origins: list[str] = field(
        default_factory=lambda: _env_list(
            "CORS_ORIGINS",
            ["http://localhost:5173", "http://127.0.0.1:5173"],
        )
    )
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
    )


def get_settings() -> Settings:
    return Settings()
