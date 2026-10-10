"""CHECK constraints, defaults, and the partial unique indexes."""

import psycopg

from helpers import expect_error


def test_expected_constraints_and_partial_indexes(db) -> None:
    names = {
        row[0]
        for row in db.execute(
            """
            SELECT conname
            FROM pg_constraint
            WHERE connamespace = 'public'::regnamespace
            """
        )
    }
    for name in (
        "books_isbn13_chk",
        "books_isbn13_uniq",
        "members_email_uniq",
        "members_status_chk",
        "members_loan_limit_chk",
        "book_copies_status_chk",
        "loans_due_after_checkout_chk",
        "reservations_ready_copy_chk",
        "book_authors_order_uniq",
    ):
        assert name in names

    partials = dict(
        db.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname IN (
                  'loans_one_open_copy_idx',
                  'reservations_one_active_member_book_idx'
              )
            """
        ).fetchall()
    )
    assert "UNIQUE" in partials["loans_one_open_copy_idx"].upper()
    assert "returned_at IS NULL" in partials["loans_one_open_copy_idx"]
    assert "waiting" in partials["reservations_one_active_member_book_idx"]


def test_isbn13_check_accepts_a_known_valid_number(db) -> None:
    valid = db.execute("SELECT is_valid_isbn13('9780306406157')").fetchone()
    invalid = db.execute("SELECT is_valid_isbn13('9780004611000')").fetchone()
    assert valid == (True,)
    assert invalid == (False,)
    db.execute(
        """
        INSERT INTO books (isbn13, title)
        VALUES ('9780306406157', 'Check Digit Specimen')
        """
    )
    expect_error(
        db,
        """
        INSERT INTO books (isbn13, title)
        VALUES ('9780004611000', 'Bad Check Digit')
        """,
        error=psycopg.errors.CheckViolation,
    )


def test_check_constraints_reject_invalid_rows(db) -> None:
    expect_error(
        db,
        """
        INSERT INTO books (isbn13, title, page_count)
        VALUES ('9780306406157', 'Zero Pages', 0)
        """,
        error=psycopg.errors.CheckViolation,
    )
    expect_error(
        db,
        """
        INSERT INTO books (isbn13, title)
        VALUES ('9780306406157', '   ')
        """,
        error=psycopg.errors.CheckViolation,
    )
    expect_error(
        db,
        """
        INSERT INTO authors (given_name, family_name, birth_year)
        VALUES ('Ada', 'Example', 0)
        """,
        error=psycopg.errors.CheckViolation,
    )
    expect_error(
        db,
        """
        INSERT INTO members (member_number, given_name, family_name, email)
        VALUES ('M-10099', 'Bad', 'Email', 'not-an-email')
        """,
        error=psycopg.errors.CheckViolation,
    )
    expect_error(
        db,
        """
        INSERT INTO members (member_number, given_name, family_name, email, loan_limit)
        VALUES ('M-10099', 'Zero', 'Limit', 'zero.limit@example.edu', 0)
        """,
        error=psycopg.errors.CheckViolation,
    )
    expect_error(
        db,
        """
        INSERT INTO members (member_number, given_name, family_name, email, membership_status)
        VALUES ('M-10099', 'Bad', 'Status', 'bad.status@example.edu', 'frozen')
        """,
        error=psycopg.errors.CheckViolation,
    )
    expect_error(
        db,
        """
        INSERT INTO book_copies (book_id, barcode, copy_status)
        VALUES (1, 'CPY-100099', 'archived')
        """,
        error=psycopg.errors.CheckViolation,
    )
    expect_error(
        db,
        """
        INSERT INTO book_authors (book_id, author_id, author_order)
        VALUES (2, 2, 0)
        """,
        error=psycopg.errors.CheckViolation,
    )
    expect_error(
        db,
        """
        INSERT INTO loans (copy_id, member_id, checked_out_at, due_at)
        VALUES (
            301, 6,
            timestamptz '2026-10-10 15:00:00+00',
            timestamptz '2026-10-01 15:00:00+00'
        )
        """,
        error=psycopg.errors.CheckViolation,
    )
    expect_error(
        db,
        """
        INSERT INTO reservations (book_id, member_id, reservation_status)
        VALUES (5, 6, 'ready')
        """,
        error=psycopg.errors.CheckViolation,
    )
    expect_error(
        db,
        "INSERT INTO books (isbn13) VALUES ('9780306406157')",
        error=psycopg.errors.NotNullViolation,
    )


def test_defaults_fill_omitted_values(db) -> None:
    member = db.execute(
        """
        INSERT INTO members (member_number, given_name, family_name, email)
        VALUES ('M-10099', 'Default', 'Member', 'default.member@example.edu')
        RETURNING membership_status, loan_limit, joined_on
        """
    ).fetchone()
    assert member is not None
    assert member[0] == "active"
    assert member[1] == 5
    assert member[2] is not None

    copy = db.execute(
        """
        INSERT INTO book_copies (book_id, barcode)
        VALUES (1, 'CPY-100099')
        RETURNING copy_status, condition, acquired_on
        """
    ).fetchone()
    assert copy is not None
    assert copy[0] == "available"
    assert copy[1] == "good"
    assert copy[2] is not None

    reservation = db.execute(
        """
        INSERT INTO reservations (book_id, member_id)
        VALUES (5, 6)
        RETURNING reservation_status, reserved_at
        """
    ).fetchone()
    assert reservation is not None
    assert reservation[0] == "waiting"
    assert reservation[1] is not None
