"""JSON-compatible storage with PostgreSQL persistence for serverless deployment.

When DATABASE_URL is configured, each logical JSON file is stored as one JSONB
value in PostgreSQL. Without DATABASE_URL, the original local JSON-file behavior
is retained for Windows/local development.
"""

import json
import os
from pathlib import Path


def _database_url():
    return os.environ.get("DATABASE_URL", "").strip()


def _state_key(path):
    return Path(path).name


def _connect():
    url = _database_url()
    if not url:
        return None
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "DATABASE_URL is set but psycopg is not installed. Install project requirements."
        ) from exc
    return psycopg.connect(url, connect_timeout=10)


def initialize_database(seed_directory="data"):
    """Create the state table and seed bundled JSON files only when keys are absent."""
    if not _database_url():
        return False

    from psycopg.types.json import Jsonb

    seed_path = Path(seed_directory)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS newspulse_state (
                    state_key TEXT PRIMARY KEY,
                    state_value JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            if seed_path.exists():
                for file_path in seed_path.glob("*.json"):
                    try:
                        with file_path.open("r", encoding="utf-8") as handle:
                            value = json.load(handle)
                    except (OSError, json.JSONDecodeError):
                        continue
                    cur.execute(
                        """
                        INSERT INTO newspulse_state (state_key, state_value)
                        VALUES (%s, %s)
                        ON CONFLICT (state_key) DO NOTHING
                        """,
                        (file_path.name, Jsonb(value)),
                    )
        conn.commit()
    return True


def load_json(path, default):
    if _database_url():
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT state_value FROM newspulse_state WHERE state_key = %s",
                    (_state_key(path),),
                )
                row = cur.fetchone()
                return row[0] if row else default

    path = Path(path)
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return default


def save_json(path, data):
    if _database_url():
        from psycopg.types.json import Jsonb

        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO newspulse_state (state_key, state_value, updated_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (state_key)
                    DO UPDATE SET state_value = EXCLUDED.state_value,
                                  updated_at = NOW()
                    """,
                    (_state_key(path), Jsonb(data)),
                )
        return

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temp.replace(path)
