"""Checkout success, rejected checkouts, rollback, and conflicting sessions."""

from __future__ import annotations

import threading

import psycopg
import pytest

from helpers import sql_statements
from library.checkout import CheckoutError, checkout_copy, force_checkout_failure
from library.db import connect


def _loan_count(conn: psycopg.Connection) -> int:
    row = conn.execute("SELECT count(*) FROM loans").fetchone()
    assert row is not None
    return int(row[0])


def _open_loan_count(conn: psycopg.Connection) -> int:
    row = conn.execute(
        "SELECT count(*) FROM loans WHERE returned_at IS NULL"
    ).fetchone()
    assert row is not None
    return int(row[0])


def _status(conn: psycopg.Connection, copy_id: int) -> str:
    row = conn.execute(
        "SELECT copy_status FROM book_copies WHERE copy_id = %s",
        (copy_id,),
    ).fetchone()
    assert row is not None
    return str(row[0])


def test_checkout_success_creates_a_loan_and_marks_the_copy(db) -> None:
    before_open = _open_loan_count(db)
    loan_id = checkout_copy(db, 101, 6)
    row = db.execute(
        """
        SELECT copy_id, member_id, returned_at,
               due_at - checked_out_at = interval '21 days'
        FROM loans
        WHERE loan_id = %s
        """,
        (loan_id,),
    ).fetchone()
    assert row == (101, 6, None, True)
    assert _status(db, 101) == "on_loan"
    assert _open_loan_count(db) == before_open + 1


def test_return_copy_closes_the_loan(db) -> None:
    loan_id = checkout_copy(db, 101, 6)
    returned = db.execute("SELECT return_copy(%s)", (101,)).fetchone()
    assert returned == (loan_id,)
    assert _status(db, 101) == "available"
    returned_at = db.execute(
        "SELECT returned_at FROM loans WHERE loan_id = %s",
        (loan_id,),
    ).fetchone()
    assert returned_at is not None
    assert returned_at[0] is not None


def test_checkout_rejects_unavailable_copies_without_writing(db) -> None:
    before = _loan_count(db)
    with pytest.raises(CheckoutError, match="on_loan"):
        checkout_copy(db, 102, 6)
    with pytest.raises(CheckoutError, match="held"):
        checkout_copy(db, 802, 6)
    with pytest.raises(CheckoutError, match="lost"):
        checkout_copy(db, 601, 6)
    with pytest.raises(CheckoutError, match="maintenance"):
        checkout_copy(db, 402, 6)
    assert _loan_count(db) == before
    assert _status(db, 102) == "on_loan"


def test_checkout_rejects_inactive_members_and_the_loan_limit(db) -> None:
    before = _loan_count(db)
    with pytest.raises(CheckoutError, match="suspended"):
        checkout_copy(db, 301, 3)
    with pytest.raises(CheckoutError, match="expired"):
        checkout_copy(db, 301, 5)
    with pytest.raises(CheckoutError, match="limit"):
        checkout_copy(db, 301, 2)
    assert _loan_count(db) == before
    assert _status(db, 301) == "available"


def test_checkout_rejects_missing_rows_and_a_bad_period(db) -> None:
    with pytest.raises(CheckoutError, match="copy 999 does not exist"):
        checkout_copy(db, 999, 6)
    with pytest.raises(CheckoutError, match="member 999 does not exist"):
        checkout_copy(db, 301, 999)
    with pytest.raises(CheckoutError, match="loan period"):
        checkout_copy(db, 301, 6, 0)


def test_forced_failure_rolls_the_checkout_writes_back(db) -> None:
    before = _loan_count(db)
    with pytest.raises(CheckoutError, match="forced failure"):
        force_checkout_failure(db, 501, 6)
    assert _loan_count(db) == before
    assert _status(db, 501) == "available"


def test_failing_script_rolls_back_the_loan_and_the_status_update(db) -> None:
    before = _loan_count(db)
    statements = sql_statements("transaction_rollback.sql")
    with pytest.raises(psycopg.errors.UniqueViolation):
        with db.transaction():
            for statement in statements:
                db.execute(statement)
    assert _loan_count(db) == before
    assert _status(db, 301) == "available"


def test_commit_rejects_on_loan_without_an_open_loan() -> None:
    with connect() as conn:
        with pytest.raises(psycopg.errors.CheckViolation, match="on_loan"):
            with conn.transaction():
                conn.execute(
                    "UPDATE book_copies SET copy_status = 'on_loan' WHERE copy_id = 501"
                )
        assert _status(conn, 501) == "available"


def test_commit_rejects_a_loan_limit_breach() -> None:
    with connect() as conn:
        with pytest.raises(psycopg.errors.CheckViolation, match="loan limit"):
            with conn.transaction():
                conn.execute("UPDATE members SET loan_limit = 1 WHERE member_id = 1")
        limit = conn.execute(
            "SELECT loan_limit FROM members WHERE member_id = 1"
        ).fetchone()
        assert limit == (5,)


def _restore_copy(copy_id: int) -> None:
    with connect() as conn:
        with conn.transaction():
            conn.execute(
                "DELETE FROM loans WHERE copy_id = %s AND loan_id > 13",
                (copy_id,),
            )
            conn.execute(
                """
                UPDATE book_copies
                SET copy_status = 'available'
                WHERE copy_id = %s
                """,
                (copy_id,),
            )


def test_conflicting_checkouts_allow_only_one_winner() -> None:
    """Two sessions lend the same available copy. The row lock lets one commit."""
    results: list[int] = []
    errors: list[str] = []
    barrier = threading.Barrier(2)

    def worker(member_id: int) -> None:
        try:
            with connect() as conn:
                barrier.wait(timeout=10)
                results.append(checkout_copy(conn, 103, member_id))
        except CheckoutError as exc:
            errors.append(str(exc))
        except Exception as exc:  # pragma: no cover - reported through the assertion
            errors.append(f"{type(exc).__name__}: {exc}")

    _restore_copy(103)
    threads = [
        threading.Thread(target=worker, args=(4,)),
        threading.Thread(target=worker, args=(6,)),
    ]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
            assert not thread.is_alive()
        assert len(results) == 1
        assert len(errors) == 1
        assert "cannot be checked out" in errors[0]
        with connect() as conn:
            assert _status(conn, 103) == "on_loan"
    finally:
        _restore_copy(103)
        with connect() as conn:
            assert _status(conn, 103) == "available"
            extra = conn.execute(
                "SELECT count(*) FROM loans WHERE copy_id = 103 AND loan_id > 13"
            ).fetchone()
            assert extra == (0,)
