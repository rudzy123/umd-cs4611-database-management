"""Load the deterministic seed in one transaction."""

from __future__ import annotations

from pathlib import Path

import psycopg

from library.db import connect
from library.sql_script import split_sql

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "db" / "seeds" / "001_seed.sql"


def apply_seed(url: str | None = None) -> None:
    statements = split_sql(SEED.read_text(encoding="utf-8"))
    with connect(url) as conn:
        with conn.transaction():
            for statement in statements:
                conn.execute(statement)


def main() -> None:
    try:
        apply_seed()
    except psycopg.OperationalError as exc:
        raise SystemExit(
            "Could not connect to PostgreSQL. Start the server with "
            "`docker compose up -d --wait` and check DATABASE_URL.\n"
            f"{exc}"
        ) from exc
    print(f"loaded {SEED.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
