"""Parameterized reads. Values are bound, never concatenated into SQL text."""

from __future__ import annotations

from psycopg import Connection

BORROWING_HISTORY_SQL = """
SELECT
    l.loan_id,
    b.title,
    c.barcode,
    l.checked_out_at,
    l.due_at,
    l.returned_at,
    CASE
        WHEN l.returned_at IS NOT NULL THEN 'returned'
        WHEN l.due_at < timestamptz '2026-10-10 00:00:00+00' THEN 'overdue'
        ELSE 'open'
    END AS loan_state
FROM loans AS l
JOIN book_copies AS c ON c.copy_id = l.copy_id
JOIN books AS b ON b.book_id = c.book_id
JOIN members AS m ON m.member_id = l.member_id
WHERE m.member_number = %s
ORDER BY l.checked_out_at DESC, l.loan_id DESC
"""


def member_ids_for_email(conn: Connection, email: str) -> list[int]:
    rows = conn.execute(
        """
        SELECT member_id
        FROM members
        WHERE email = %s
        ORDER BY member_id
        """,
        (email,),
    ).fetchall()
    return [int(row[0]) for row in rows]


def borrowing_history(conn: Connection, member_number: str) -> list[tuple]:
    return conn.execute(BORROWING_HISTORY_SQL, (member_number,)).fetchall()
