"""Shared SQL helpers for the database tests."""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest

from library.sql_script import split_sql

QUERIES = Path(__file__).resolve().parents[1] / "db" / "queries"


def sql_statements(filename: str) -> list[str]:
    return split_sql((QUERIES / filename).read_text(encoding="utf-8"))


def expect_error(
    conn: psycopg.Connection,
    statement: str,
    params: tuple = (),
    error: type[BaseException] = psycopg.Error,
) -> None:
    with pytest.raises(error):
        with conn.transaction():
            conn.execute(statement, params)
