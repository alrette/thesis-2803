"""
Strict read-only SQLite execution helper for the "Run SQL" button (Step 5).

Safety guards:
  1. Only allows single SELECT / WITH statements (rejects DML/DDL/ATTACH/PRAGMA).
  2. Opens SQLite via RFC 8089 file URI with `?mode=ro` + `PRAGMA query_only = ON`.
  3. Enforces a real wall-clock query timeout via `conn.set_progress_handler()`.
  4. Caps returned rows to `max_rows` and flags `truncated = True` if more exist.
  5. Decodes non-UTF-8 Spider cell bytes safely (same `text_factory` as sql_execution.py).
"""

from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|ATTACH|DETACH|VACUUM|REINDEX|PRAGMA)\b",
    re.IGNORECASE,
)
_LEADING_COMMENTS = re.compile(r"^(?:\s|--[^\n]*\n|/\*.*?\*/)+", re.DOTALL)


@dataclass
class SqlExecutionResult:
    ok: bool
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    execution_ms: float
    error: str | None = None


def _strip_string_literals(sql: str) -> str:
    return re.sub(r"'([^']|'')*'|\"([^\"]|\"\")*\"", "''", sql)


def _validate_read_only_sql(sql: str) -> str | None:
    cleaned = sql.strip()
    if not cleaned:
        return "SQL query is empty."

    # Remove a single trailing semicolon if present
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()

    unquoted = _strip_string_literals(cleaned)
    if ";" in unquoted:
        return "Only a single SQL statement can be executed at a time."

    head = _LEADING_COMMENTS.sub("", unquoted).lstrip().upper()
    if not (head.startswith("SELECT") or head.startswith("WITH")):
        return "Only read-only SELECT queries are allowed."

    forbidden = _FORBIDDEN_SQL.search(unquoted)
    if forbidden:
        return f"Disallowed SQL keyword in read-only mode: {forbidden.group(1).upper()}."

    return None


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return str(value)


def execute_readonly_sql(
    db_path: Path,
    sql: str,
    timeout_sec: float = 5.0,
    max_rows: int = 200,
) -> SqlExecutionResult:
    start = time.perf_counter()

    validation_error = _validate_read_only_sql(sql)
    if validation_error:
        return SqlExecutionResult(
            ok=False,
            columns=[],
            rows=[],
            row_count=0,
            truncated=False,
            execution_ms=round((time.perf_counter() - start) * 1000, 2),
            error=validation_error,
        )

    if not db_path.is_file():
        return SqlExecutionResult(
            ok=False,
            columns=[],
            rows=[],
            row_count=0,
            truncated=False,
            execution_ms=round((time.perf_counter() - start) * 1000, 2),
            error=f"Database file not found on server: {db_path.name}",
        )

    conn: sqlite3.Connection | None = None
    try:
        uri = db_path.resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=timeout_sec)
        conn.text_factory = lambda b: b.decode("utf-8", errors="ignore")
        conn.execute("PRAGMA query_only = ON;")

        deadline = time.monotonic() + timeout_sec

        def _check_timeout() -> int:
            return 1 if time.monotonic() > deadline else 0

        conn.set_progress_handler(_check_timeout, 5000)

        cur = conn.cursor()
        cur.execute(sql.strip().rstrip(";"))
        columns = [desc[0] for desc in (cur.description or [])]
        fetched = cur.fetchmany(max_rows + 1)
        truncated = len(fetched) > max_rows
        rows = [[_json_safe(cell) for cell in row] for row in fetched[:max_rows]]

        return SqlExecutionResult(
            ok=True,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
            execution_ms=round((time.perf_counter() - start) * 1000, 2),
            error=None,
        )
    except sqlite3.OperationalError as exc:
        msg = str(exc)
        if "interrupted" in msg.lower():
            msg = f"Query timed out after {timeout_sec:.1f}s."
        return SqlExecutionResult(
            ok=False,
            columns=[],
            rows=[],
            row_count=0,
            truncated=False,
            execution_ms=round((time.perf_counter() - start) * 1000, 2),
            error=msg,
        )
    except Exception as exc:  # noqa: BLE001
        return SqlExecutionResult(
            ok=False,
            columns=[],
            rows=[],
            row_count=0,
            truncated=False,
            execution_ms=round((time.perf_counter() - start) * 1000, 2),
            error=str(exc),
        )
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
