import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    import psycopg
except Exception:  # pragma: no cover - optional dependency
    psycopg = None


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY,
    checked_at TEXT,
    status TEXT,
    slots_json TEXT,
    result_hash TEXT,
    evidence_json TEXT,
    error TEXT
);
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS checks (
    id SERIAL PRIMARY KEY,
    checked_at TEXT,
    status TEXT,
    slots_json TEXT,
    result_hash TEXT,
    evidence_json TEXT,
    error TEXT
);
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def _get_db_url(storage: Dict[str, Any]) -> Optional[str]:
    env_key = storage.get("postgres_url_env")
    if not env_key:
        return None
    return os.getenv(env_key)


def _is_postgres(storage: Dict[str, Any]) -> bool:
    return _get_db_url(storage) is not None


def _connect(storage: Dict[str, Any]):
    db_url = _get_db_url(storage)
    if db_url:
        if psycopg is None:
            raise RuntimeError("psycopg is required for Postgres support")
        return psycopg.connect(db_url, autocommit=True)

    sqlite_path = storage["sqlite_path"]
    sqlite_dir = os.path.dirname(sqlite_path)
    if sqlite_dir:
        os.makedirs(sqlite_dir, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(storage: Dict[str, Any]) -> None:
    conn = _connect(storage)
    try:
        if _is_postgres(storage):
            statements = [stmt.strip() for stmt in POSTGRES_SCHEMA.split(";") if stmt.strip()]
            for statement in statements:
                conn.execute(statement)
        else:
            conn.executescript(SQLITE_SCHEMA)
            conn.commit()
    finally:
        conn.close()


def insert_check(
    storage: Dict[str, Any],
    checked_at: str,
    status: str,
    slots_json: str,
    result_hash: str,
    evidence_json: str,
    error: Optional[str],
) -> None:
    conn = _connect(storage)
    try:
        if _is_postgres(storage):
            conn.execute(
                """
                INSERT INTO checks (checked_at, status, slots_json, result_hash, evidence_json, error)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (checked_at, status, slots_json, result_hash, evidence_json, error),
            )
        else:
            conn.execute(
                """
                INSERT INTO checks (checked_at, status, slots_json, result_hash, evidence_json, error)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (checked_at, status, slots_json, result_hash, evidence_json, error),
            )
            conn.commit()
    finally:
        conn.close()


def get_state(storage: Dict[str, Any], key: str) -> Optional[str]:
    conn = _connect(storage)
    try:
        if _is_postgres(storage):
            row = conn.execute("SELECT value FROM state WHERE key = %s", (key,)).fetchone()
            return row[0] if row else None
        row = conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None
    finally:
        conn.close()


def set_state(storage: Dict[str, Any], key: str, value: str) -> None:
    conn = _connect(storage)
    try:
        if _is_postgres(storage):
            conn.execute(
                """
                INSERT INTO state (key, value)
                VALUES (%s, %s)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (key, value),
            )
        else:
            conn.execute(
                """
                INSERT INTO state (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (key, value),
            )
            conn.commit()
    finally:
        conn.close()


def count_checks_since(storage: Dict[str, Any], since_iso: str) -> int:
    conn = _connect(storage)
    try:
        if _is_postgres(storage):
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM checks WHERE checked_at >= %s",
                (since_iso,),
            ).fetchone()
            return int(row[0]) if row else 0
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM checks WHERE checked_at >= ?",
            (since_iso,),
        ).fetchone()
        return int(row["count"]) if row else 0
    finally:
        conn.close()


def oldest_check_since(storage: Dict[str, Any], since_iso: str) -> Optional[str]:
    conn = _connect(storage)
    try:
        if _is_postgres(storage):
            row = conn.execute(
                "SELECT checked_at FROM checks WHERE checked_at >= %s ORDER BY checked_at ASC LIMIT 1",
                (since_iso,),
            ).fetchone()
            return row[0] if row else None
        row = conn.execute(
            "SELECT checked_at FROM checks WHERE checked_at >= ? ORDER BY checked_at ASC LIMIT 1",
            (since_iso,),
        ).fetchone()
        return row["checked_at"] if row else None
    finally:
        conn.close()


def serialize_slots(slots: Any) -> str:
    return json.dumps(slots, sort_keys=True)


def serialize_evidence(evidence: Dict[str, Any]) -> str:
    return json.dumps(evidence, sort_keys=True)


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()
