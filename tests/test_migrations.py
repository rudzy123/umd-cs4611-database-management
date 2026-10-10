"""Migrations and the seed apply cleanly to an empty database."""

from __future__ import annotations

from psycopg import sql

from library.checkout import checkout_copy
from library.db import connect, database_url_for
from library.migrate import apply_migrations
from library.seed import apply_seed

SCRATCH = "library_migration_check"


def test_migrations_and_seed_from_a_clean_database() -> None:
    scratch_url = database_url_for(SCRATCH)
    admin = connect(autocommit=True)
    drop = sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(SCRATCH))
    create = sql.SQL("CREATE DATABASE {}").format(sql.Identifier(SCRATCH))
    try:
        admin.execute(drop)
        admin.execute(create)
        first = apply_migrations(scratch_url)
        second = apply_migrations(scratch_url)
        assert first == [
            "001_schema.sql",
            "002_indexes.sql",
            "003_views_and_checkout.sql",
        ]
        assert second == []
        apply_seed(scratch_url)

        with connect(scratch_url) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    """
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    """
                )
            }
            assert {
                "authors",
                "books",
                "book_authors",
                "categories",
                "book_categories",
                "members",
                "book_copies",
                "loans",
                "reservations",
                "schema_migrations",
            } <= tables

            views = {
                row[0]
                for row in conn.execute(
                    """
                    SELECT viewname
                    FROM pg_views
                    WHERE schemaname = 'public'
                    """
                )
            }
            assert {
                "overdue_loans",
                "available_copies_by_title",
                "member_borrowing_history",
            } <= views

            procedure = conn.execute(
                "SELECT to_regprocedure('public.checkout_copy(bigint, bigint, integer)')"
            ).fetchone()
            assert procedure is not None
            assert procedure[0] is not None

            overdue = conn.execute(
                """
                SELECT loan_id
                FROM overdue_loans_as_of(timestamptz '2026-10-10 00:00:00+00')
                """
            ).fetchall()
            assert overdue == [(4,)]

            loan_id = checkout_copy(conn, 101, 6)
            status = conn.execute(
                "SELECT copy_status FROM book_copies WHERE copy_id = 101"
            ).fetchone()
            assert status == ("on_loan",)
            assert isinstance(loan_id, int)
    finally:
        admin.execute(drop)
        admin.close()
