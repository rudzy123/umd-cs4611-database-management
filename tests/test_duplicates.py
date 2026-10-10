"""Unique keys, byline order, one open loan, and one active reservation."""

import psycopg

from helpers import expect_error


def test_natural_keys_reject_duplicates(db) -> None:
    expect_error(
        db,
        """
        INSERT INTO books (isbn13, title)
        VALUES ('9780004611006', 'Duplicate ISBN')
        """,
        error=psycopg.errors.UniqueViolation,
    )
    expect_error(
        db,
        """
        INSERT INTO book_copies (book_id, barcode)
        VALUES (1, 'CPY-000101')
        """,
        error=psycopg.errors.UniqueViolation,
    )
    expect_error(
        db,
        """
        INSERT INTO members (member_number, given_name, family_name, email)
        VALUES ('M-10001', 'Other', 'Person', 'other.person@example.edu')
        """,
        error=psycopg.errors.UniqueViolation,
    )
    expect_error(
        db,
        """
        INSERT INTO members (member_number, given_name, family_name, email)
        VALUES ('M-10099', 'Other', 'Person', 'avery.nguyen@example.edu')
        """,
        error=psycopg.errors.UniqueViolation,
    )
    expect_error(
        db,
        "INSERT INTO categories (name) VALUES ('Databases')",
        error=psycopg.errors.UniqueViolation,
    )
    expect_error(
        db,
        "INSERT INTO book_authors (book_id, author_id, author_order) VALUES (2, 1, 2)",
        error=psycopg.errors.UniqueViolation,
    )


def test_author_order_is_unique_per_book(db) -> None:
    expect_error(
        db,
        "INSERT INTO book_authors (book_id, author_id, author_order) VALUES (2, 2, 1)",
        error=psycopg.errors.UniqueViolation,
    )


def test_only_one_open_loan_per_copy(db) -> None:
    expect_error(
        db,
        """
        INSERT INTO loans (copy_id, member_id, checked_out_at, due_at)
        VALUES (
            102, 6,
            timestamptz '2026-10-10 15:00:00+00',
            timestamptz '2026-10-31 15:00:00+00'
        )
        """,
        error=psycopg.errors.UniqueViolation,
    )


def test_only_one_active_reservation_per_member_and_book(db) -> None:
    expect_error(
        db,
        """
        INSERT INTO reservations (book_id, member_id, reservation_status)
        VALUES (6, 1, 'waiting')
        """,
        error=psycopg.errors.UniqueViolation,
    )
    db.execute(
        """
        INSERT INTO reservations (book_id, member_id, reservation_status)
        VALUES (6, 1, 'cancelled')
        """
    )
