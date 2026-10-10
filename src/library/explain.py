"""Capture query plans before and after the secondary indexes.

The captures describe this server and the laboratory seed. A sequential scan of a
one-page table is a normal planner choice. Disabling sequential scans shows an
index path the planner is able to build. It is an illustration of plan shape,
not a performance result.
"""

from __future__ import annotations

from pathlib import Path

import psycopg
from psycopg import sql

from library.db import connect

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "db" / "explain"

# Indexes created by migration 002. The partial unique indexes from migration 001 stay.
SECONDARY_INDEXES = (
    "book_authors_author_id_idx",
    "book_categories_category_id_idx",
    "book_copies_book_id_idx",
    "book_copies_available_book_idx",
    "loans_copy_id_idx",
    "loans_member_checkout_idx",
    "loans_open_due_idx",
    "reservations_book_id_idx",
    "reservations_member_id_idx",
    "reservations_ready_copy_id_idx",
)

QUERIES: tuple[tuple[str, str, str], ...] = (
    (
        "overdue_loans",
        """
        SELECT loan_id, copy_id, member_id, due_at
        FROM loans
        WHERE returned_at IS NULL
          AND due_at < timestamptz '2026-10-10 00:00:00+00'
        ORDER BY due_at
        """,
        "loans_open_due_idx matches open loans filtered and ordered by due_at.",
    ),
    (
        "member_history",
        """
        SELECT loan_id, checked_out_at, due_at, returned_at
        FROM loans
        WHERE member_id = 1
        ORDER BY checked_out_at DESC
        """,
        "loans_member_checkout_idx matches member_id plus checked_out_at order.",
    ),
    (
        "available_copies",
        """
        SELECT copy_id, barcode
        FROM book_copies
        WHERE book_id = 1
          AND copy_status = 'available'
        ORDER BY copy_id
        """,
        "book_copies_available_book_idx matches available copies of one title.",
    ),
    (
        "most_borrowed",
        """
        SELECT c.book_id, count(*) AS times_borrowed
        FROM loans AS l
        JOIN book_copies AS c ON c.copy_id = l.copy_id
        GROUP BY c.book_id
        ORDER BY times_borrowed DESC, c.book_id
        """,
        "loans_copy_id_idx and book_copies_book_id_idx can serve the join from loans to titles.",
    ),
)

CAUTION = """\
These plans were captured on one PostgreSQL server after the laboratory seed was analyzed.
Estimated costs and actual times belong to that run and to a few dozen rows.
A sequential scan is a rational plan when the heap is one or two pages.
The secondary indexes are justified by the predicates, join keys, and foreign-key checks
the schema will run as those tables grow. They are not justified by a claim that this
seed got faster. The section that disables sequential scans shows a plan shape the
planner can produce. It is not a benchmark.
"""


def capture_plans(url: str | None = None) -> list[Path]:
    written: list[Path] = []
    with connect(url) as conn:
        # Display timestamptz in UTC so plan text matches the +00 literals in the queries.
        conn.execute("SET TIME ZONE 'UTC'")
        version = conn.execute("SHOW server_version").fetchone()
        server_version = version[0] if version else "unknown"
        _idle(conn)
        for name, query, reason in QUERIES:
            before, before_analyze = _plans_without_secondary_indexes(conn, query)
            _idle(conn)
            after = _explain(conn, query, analyze=False)
            after_analyze = _explain(conn, query, analyze=True)
            _idle(conn)
            forced, forced_analyze = _plans_with_seqscan_disabled(conn, query)
            _idle(conn)
            path = OUTPUT / f"{name}.plan.txt"
            path.write_text(
                "\n".join(
                    [
                        f"Query: {name}",
                        f"Server version: {server_version}",
                        f"Index this query can use: {reason}",
                        "",
                        CAUTION.rstrip(),
                        "",
                        "SQL:",
                        query.strip(),
                        "",
                        "== Before secondary indexes (EXPLAIN) ==",
                        before,
                        "",
                        "== Before secondary indexes (EXPLAIN ANALYZE) ==",
                        before_analyze,
                        "",
                        "== After secondary indexes (EXPLAIN) ==",
                        after,
                        "",
                        "== After secondary indexes (EXPLAIN ANALYZE) ==",
                        after_analyze,
                        "",
                        "== After secondary indexes, sequential scans disabled (EXPLAIN) ==",
                        forced,
                        "",
                        "== After secondary indexes, sequential scans disabled (EXPLAIN ANALYZE) ==",
                        forced_analyze,
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            written.append(path)
    return written


def _plans_without_secondary_indexes(conn: psycopg.Connection, query: str) -> tuple[str, str]:
    with conn.transaction():
        for index_name in SECONDARY_INDEXES:
            conn.execute(sql.SQL("DROP INDEX IF EXISTS {}").format(sql.Identifier(index_name)))
        conn.execute("SET LOCAL enable_seqscan = on")
        estimated = _explain(conn, query, analyze=False)
        analyzed = _explain(conn, query, analyze=True)
        raise psycopg.Rollback()
    return estimated, analyzed


def _plans_with_seqscan_disabled(conn: psycopg.Connection, query: str) -> tuple[str, str]:
    with conn.transaction():
        conn.execute("SET LOCAL enable_seqscan = off")
        return _explain(conn, query, analyze=False), _explain(conn, query, analyze=True)


def _idle(conn: psycopg.Connection) -> None:
    """Commit a leftover read transaction so the next plan starts idle.

    SET LOCAL survives a released savepoint and lasts until the outer transaction ends.
    Starting each capture from an idle connection keeps that setting from leaking.
    """
    if conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
        conn.commit()


def _explain(conn: psycopg.Connection, query: str, *, analyze: bool) -> str:
    options = "ANALYZE, BUFFERS, FORMAT TEXT" if analyze else "COSTS, FORMAT TEXT"
    rows = conn.execute(f"EXPLAIN ({options}) {query}").fetchall()
    return "\n".join(row[0] for row in rows)


def main() -> None:
    try:
        written = capture_plans()
    except psycopg.OperationalError as exc:
        raise SystemExit(
            "Could not connect to PostgreSQL. Start the server with "
            "`docker compose up -d --wait` and check DATABASE_URL.\n"
            f"{exc}"
        ) from exc
    for path in written:
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
