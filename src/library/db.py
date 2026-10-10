"""Connections to the laboratory PostgreSQL database."""

from __future__ import annotations

import os

import psycopg

DEFAULT_DATABASE_URL = "postgresql://library:library@localhost:5432/library"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def database_url_for(name: str, url: str | None = None) -> str:
    """Return ``url`` with the database name replaced."""
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(url or database_url())
    return urlunsplit((parts.scheme, parts.netloc, f"/{name}", parts.query, parts.fragment))


def connect(url: str | None = None, *, autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(
        url or database_url(),
        autocommit=autocommit,
        application_name="library-lending",
    )
