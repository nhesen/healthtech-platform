"""Database adapter for local SQLite and hosted PostgreSQL/Supabase."""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{ROOT / 'healthtech.db'}"
DATABASE_KIND = "postgresql" if DATABASE_URL.startswith(("postgres://", "postgresql://")) else "sqlite"


def _sqlite_path(value: str) -> Path:
    return Path(value.removeprefix("sqlite:///")) if value.startswith("sqlite:///") else Path(value)


DB_PATH = _sqlite_path(DATABASE_URL) if DATABASE_KIND == "sqlite" else None


class PostgresConnection:
    """Expose the subset of sqlite's connection API used by the application."""

    def __init__(self, connection: Any):
        self.connection = connection

    @staticmethod
    def _sql(query: str) -> str:
        return re.sub(r"\?", "%s", query)

    def execute(self, query: str, args: Iterable[Any] = ()):
        return self.connection.execute(self._sql(query), tuple(args))

    def executemany(self, query: str, args: Iterable[Iterable[Any]]):
        cursor = self.connection.cursor()
        cursor.executemany(self._sql(query), args)
        return cursor

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            if statement.strip():
                self.connection.execute(statement)

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()


def connect():
    if DATABASE_KIND == "postgresql":
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - deployment-only failure
            raise RuntimeError("PostgreSQL DATABASE_URL requires psycopg[binary]") from exc
        return PostgresConnection(psycopg.connect(DATABASE_URL, row_factory=dict_row))

    assert DB_PATH is not None
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
