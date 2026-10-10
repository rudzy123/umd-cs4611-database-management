"""Database fixtures. Each test's writes roll back with the connection."""

from __future__ import annotations

import psycopg
import pytest

from library.db import connect


@pytest.fixture
def db():
    """Yield a connection and roll the surrounding transaction back."""
    with connect() as conn:
        with conn.transaction():
            yield conn
            raise psycopg.Rollback()
