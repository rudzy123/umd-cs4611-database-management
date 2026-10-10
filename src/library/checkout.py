"""Transaction-safe checkout.

The SQL function ``checkout_copy`` locks the copy and the member, inserts the loan,
and updates the copy. This module calls that function with bound parameters.
``psycopg`` sends parameter values separately from the SQL text, so a member-supplied
string cannot change the statement.
"""

from __future__ import annotations

import psycopg
from psycopg import Connection


class CheckoutError(Exception):
    """The checkout did not happen, and its transaction was rolled back."""


def checkout_copy(
    conn: Connection,
    copy_id: int,
    member_id: int,
    loan_days: int = 21,
) -> int:
    """Lend ``copy_id`` to ``member_id`` and return the new loan id.

    When this connection is already in a transaction, the work is a savepoint.
    Otherwise this function commits on success and rolls back on failure.
    """
    with conn.transaction():
        try:
            row = conn.execute(
                "SELECT checkout_copy(%s, %s, %s)",
                (copy_id, member_id, loan_days),
            ).fetchone()
        except psycopg.Error as exc:
            message = exc.diag.message_primary if exc.diag.message_primary else str(exc)
            raise CheckoutError(message) from exc
    if row is None or row[0] is None:
        raise CheckoutError("checkout_copy returned no loan id")
    return int(row[0])


def force_checkout_failure(conn: Connection, copy_id: int, member_id: int) -> None:
    """Perform the checkout writes, then raise so none of them remain.

    This is the atomicity demonstration. The insert and the status update are
    undone together because they share a transaction that does not commit.
    """
    with conn.transaction():
        conn.execute(
            "SELECT copy_id FROM book_copies WHERE copy_id = %s FOR UPDATE",
            (copy_id,),
        )
        conn.execute(
            """
            INSERT INTO loans (copy_id, member_id, checked_out_at, due_at)
            VALUES (
                %s,
                %s,
                timestamptz '2026-10-10 15:00:00+00',
                timestamptz '2026-10-31 15:00:00+00'
            )
            """,
            (copy_id, member_id),
        )
        conn.execute(
            """
            UPDATE book_copies
            SET copy_status = 'on_loan'
            WHERE copy_id = %s
            """,
            (copy_id,),
        )
        raise CheckoutError("forced failure after checkout writes")
