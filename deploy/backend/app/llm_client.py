"""
Prompt builder, OpenAI-compatible Qwen2.5-Coder-7B client, and SQL cleaner.

Prompt format and `_clean_sql()` mirror `src/generation/generation.py` directly.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.settings import Settings

logger = logging.getLogger(__name__)

_COMPLEX_KEYWORDS = frozenset(["JOIN", "INTERSECT", "EXCEPT", "UNION"])
_HAS_SUBQUERY = re.compile(r"\bSELECT\b.*\bSELECT\b", re.IGNORECASE | re.DOTALL)
_NULLS_PATTERN = re.compile(r"\s+NULLS\s+(LAST|FIRST)", re.IGNORECASE)
_ILIKE_PATTERN = re.compile(r"\bILIKE\b", re.IGNORECASE)
_CAST_PATTERN = re.compile(r"::text\b", re.IGNORECASE)
_ALIAS_INLINE = re.compile(r"(?i)\s+AS\s+[a-zA-Z0-9_]+(?=[\s,]|FROM|$)")
_TABLE_PREFIX = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\.(?=[a-zA-Z_])")
_WHITESPACE = re.compile(r"\s+")


def build_prompt(
    question: str,
    schema_context: str,
    few_shot_block: str = "",
    include_sql_fence_prefix: bool = True,
) -> str:
    """
    Exact prompt template from `src/generation/generation.py`.

    In `chat` mode (OpenAI `/v1/chat/completions`), omit the trailing ```` ```sql\n ````
    prefix because the assistant starts a fresh turn; `_clean_sql()` strips fences either way.
    """
    base = (
        "### Task\n"
        "Generate a valid SQLite query to answer the following question.\n"
        "### Database Schema\n"
        f"{schema_context}\n"
        f"{few_shot_block}"
        "### Question\n"
        f"{question}\n"
        "### Instructions\n"
        "1. Only use the tables and columns provided in the schema above. DO NOT make up names.\n"
        "2. JOIN ALIASING (CRITICAL): If you use JOINs, you MUST explicitly declare table aliases "
        "in the FROM clause using `AS T1`, `AS T2`, etc.\n"
        "3. SINGLE TABLE RULES: If querying a single table (NO JOIN), DO NOT use any table aliases.\n"
        "4. ALWAYS use `COUNT(*)` instead of `COUNT(column)`.\n"
        "5. SET OPERATIONS: Use `INTERSECT` to find items matching two separate criteria. "
        "Use `EXCEPT` for exclusionary conditions.\n"
        "6. Output ONLY the raw SQL query. Do not add markdown or explanations.\n"
        "### Answer\n"
    )
    return base + "```sql\n" if include_sql_fence_prefix else base


def clean_sql(sql: str) -> str:
    """Normalise raw LLM output into a clean SQLite query (mirrors generation.py)."""
    sql = sql.replace("```sql", "").replace("```", "").replace("`", "").strip()

    cut = re.search(r"(?:\n\s*\n|\n\s*```|\n\s*###)", sql)
    if cut:
        sql = sql[: cut.start()]

    match = re.search(r"(SELECT\s+.*?)(?:;|$)", sql, re.DOTALL | re.IGNORECASE)
    sql = match.group(1).strip() if match else sql.strip()

    if not sql:
        return ""

    sql = _NULLS_PATTERN.sub("", sql)
    sql = _ILIKE_PATTERN.sub("LIKE", sql)
    sql = _CAST_PATTERN.sub("", sql)

    is_simple = (
        not any(kw in sql.upper() for kw in _COMPLEX_KEYWORDS)
        and not _HAS_SUBQUERY.search(sql)
    )
    if is_simple:
        sql = _ALIAS_INLINE.sub("", sql)
        parts = re.split(r"\bFROM\b", sql, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            select_part, from_part = parts[0], parts[1].strip()
            select_part = _TABLE_PREFIX.sub("", select_part)

            table_match = re.match(r"^([a-zA-Z0-9_]+)", from_part)
            if table_match:
                table_name = table_match.group(1)
                kw_match = re.search(
                    r"(?i)\b(WHERE|GROUP|ORDER|HAVING|LIMIT)\b.*", from_part, re.DOTALL
                )
                if kw_match:
                    clause = _TABLE_PREFIX.sub("", kw_match.group(0))
                    from_part = f"{table_name} {clause}"
                else:
                    from_part = table_name

            sql = f"{select_part} FROM {from_part}"

    return _WHITESPACE.sub(" ", sql).strip()


@dataclass
class GenerationOutput:
    sql: str
    raw_output: str
    prompt_tokens: int | None
    completion_tokens: int | None
    model: str


class LLMClient:
    """Thin OpenAI-compatible client for Qwen2.5-Coder-7B-Instruct."""

    def __init__(self, settings: Settings) -> None:
        self.cfg = settings
        self._client = None
        if settings.llm_api_key:
            from openai import OpenAI

            kwargs = {"api_key": settings.llm_api_key, "timeout": settings.llm_timeout_sec}
            if settings.llm_base_url:
                kwargs["base_url"] = settings.llm_base_url
            self._client = OpenAI(**kwargs)
            logger.info(
                "LLM API client configured (model=%s, mode=%s, base_url=%s)",
                settings.llm_model,
                settings.llm_api_mode,
                settings.llm_base_url or "default",
            )
        else:
            logger.warning("LLM_API_KEY is not set; /api/generate will return 503 until configured")

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    def generate_sql(
        self,
        question: str,
        schema_context: str,
        few_shot_block: str = "",
    ) -> GenerationOutput:
        if self._client is None:
            raise RuntimeError(
                "LLM API is not configured. Set LLM_API_KEY (and LLM_BASE_URL / LLM_MODEL) "
                "in your environment or Hugging Face Space Secrets."
            )

        is_completion = self.cfg.llm_api_mode == "completion"
        prompt = build_prompt(
            question=question,
            schema_context=schema_context,
            few_shot_block=few_shot_block,
            include_sql_fence_prefix=is_completion,
        )

        if is_completion:
            resp = self._client.completions.create(
                model=self.cfg.llm_model,
                prompt=prompt,
                max_tokens=self.cfg.max_new_tokens,
                temperature=self.cfg.temperature,
                stop=list(self.cfg.sql_stop_strings) or None,
            )
            raw = resp.choices[0].text or ""
        else:
            resp = self._client.chat.completions.create(
                model=self.cfg.llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.cfg.max_new_tokens,
                temperature=self.cfg.temperature,
            )
            raw = resp.choices[0].message.content or ""

        usage = getattr(resp, "usage", None)
        cleaned = clean_sql(raw)
        if not cleaned:
            raise RuntimeError("Model returned an empty SQL response.")

        return GenerationOutput(
            sql=cleaned,
            raw_output=raw,
            prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
            model=self.cfg.llm_model,
        )
