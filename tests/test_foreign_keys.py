"""Foreign keys restrict parent deletes and reject dangling references."""

import psycopg

from helpers import expect_error


def test_loan_requires_a_real_member_and_copy(db) -> None:
    expect_error(
        db,
        """
        INSERT INTO loans (copy_id, member_id, checked_out_at, due_at)
        VALUES (
            301, 999,
            timestamptz '2026-10-10 15:00:00+00',
            timestamptz '2026-10-31 15:00:00+00'
        )
        """,
        error=psycopg.errors.ForeignKeyViolation,
    )
    expect_error(
        db,
        """
        INSERT INTO loans (copy_id, member_id, checked_out_at, due_at)
        VALUES (
            999, 6,
            timestamptz '2026-10-10 15:00:00+00',
            timestamptz '2026-10-31 15:00:00+00'
        )
        """,
        error=psycopg.errors.ForeignKeyViolation,
    )


def test_referenced_parents_cannot_be_deleted(db) -> None:
    expect_error(
        db,
        "DELETE FROM books WHERE book_id = 1",
        error=psycopg.errors.ForeignKeyViolation,
    )
    expect_error(
        db,
        "DELETE FROM authors WHERE author_id = 1",
        error=psycopg.errors.ForeignKeyViolation,
    )
    expect_error(
        db,
        "DELETE FROM categories WHERE category_id = 1",
        error=psycopg.errors.ForeignKeyViolation,
    )
    expect_error(
        db,
        "DELETE FROM members WHERE member_id = 1",
        error=psycopg.errors.ForeignKeyViolation,
    )
    expect_error(
        db,
        "DELETE FROM book_copies WHERE copy_id = 101",
        error=psycopg.errors.ForeignKeyViolation,
    )
    expect_error(
        db,
        "DELETE FROM book_copies WHERE copy_id = 802",
        error=psycopg.errors.ForeignKeyViolation,
    )


def test_unreferenced_rows_can_be_deleted(db) -> None:
    db.execute("DELETE FROM categories WHERE name = 'Cartography'")
    assert db.execute("SELECT 1 FROM categories WHERE name = 'Cartography'").fetchone() is None

    db.execute("DELETE FROM book_copies WHERE copy_id = 901")
    assert db.execute("SELECT 1 FROM book_copies WHERE copy_id = 901").fetchone() is None

    db.execute("DELETE FROM books WHERE book_id = 10")
    assert db.execute(
        "SELECT 1 FROM book_authors WHERE book_id = 10"
    ).fetchone() is None
    assert db.execute(
        "SELECT 1 FROM book_categories WHERE book_id = 10"
    ).fetchone() is None
    assert db.execute("SELECT 1 FROM books WHERE book_id = 10").fetchone() is None
