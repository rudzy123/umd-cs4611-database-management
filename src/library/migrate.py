"""Apply up-only SQL migrations and record them in schema_migrations."""

from __future__ import annotations

from pathlib import Path

import psycopg

from library.db import connect
from library.sql_script import split_sql

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "db" / "migrations"


def apply_migrations(url: str | None = None) -> list[str]:
    """Apply each unapplied migration file in order. Return the filenames applied."""
    applied: list[str] = []
    with connect(url) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename text PRIMARY KEY,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        conn.commit()
        for path in sorted(MIGRATIONS.glob("*.sql")):
            already = conn.execute(
                "SELECT 1 FROM schema_migrations WHERE filename = %s",
                (path.name,),
            ).fetchone()
            if already:
                continue
            statements = split_sql(path.read_text(encoding="utf-8"))
            with conn.transaction():
                for statement in statements:
                    conn.execute(statement)
                conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)",
                    (path.name,),
                )
            applied.append(path.name)
    return applied


def main() -> None:
    try:
        applied = apply_migrations()
    except psycopg.OperationalError as exc:
        raise SystemExit(
            "Could not connect to PostgreSQL. Start the server with "
            "`docker compose up -d --wait` and check DATABASE_URL.\n"
            f"{exc}"
        ) from exc
    if applied:
        print("applied: " + ", ".join(applied))
    else:
        print("migrations already applied")


if __name__ == "__main__":
    main()
