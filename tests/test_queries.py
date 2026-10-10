"""Correctness of the educational queries, views, and parameterized reads."""

from datetime import datetime, timezone

from helpers import sql_statements
from library.queries import borrowing_history, member_ids_for_email


def _rows(db, filename: str, index: int = 0) -> list[tuple]:
    statements = sql_statements(filename)
    cursor = db.execute(statements[index])
    return cursor.fetchall()


def test_seed_population(db) -> None:
    counts = dict(
        db.execute(
            """
            SELECT 'authors', count(*) FROM authors
            UNION ALL SELECT 'books', count(*) FROM books
            UNION ALL SELECT 'categories', count(*) FROM categories
            UNION ALL SELECT 'members', count(*) FROM members
            UNION ALL SELECT 'book_copies', count(*) FROM book_copies
            UNION ALL SELECT 'loans', count(*) FROM loans
            UNION ALL SELECT 'reservations', count(*) FROM reservations
            UNION ALL SELECT 'book_authors', count(*) FROM book_authors
            UNION ALL SELECT 'book_categories', count(*) FROM book_categories
            UNION ALL SELECT 'open_loans', count(*) FROM loans WHERE returned_at IS NULL
            """
        ).fetchall()
    )
    assert counts == {
        "authors": 6,
        "books": 10,
        "categories": 6,
        "members": 6,
        "book_copies": 14,
        "loans": 13,
        "reservations": 3,
        "book_authors": 13,
        "book_categories": 13,
        "open_loans": 4,
    }


def test_joins(db) -> None:
    assert _rows(db, "joins.sql", 0) == [
        ("Foundations of Relational Design", "Mira", "Chen", 1),
        ("Foundations of Relational Design", "Jonah", "Adeyemi", 2),
    ]
    assert _rows(db, "joins.sql", 1) == [
        (8, "Poetry of the North Shore", "CPY-000801"),
        (8, "Poetry of the North Shore", "CPY-000802"),
        (10, "Forthcoming Catalog", None),
    ]
    assert _rows(db, "joins.sql", 2) == [
        (None, "Unclassified Field Notes"),
        ("Cartography", None),
    ]


def test_aggregation(db) -> None:
    assert _rows(db, "aggregation.sql", 0) == [
        (1, "M-10001", 4, 2, 1),
        (2, "M-10002", 3, 2, 0),
        (3, "M-10003", 2, 0, 0),
        (4, "M-10004", 2, 0, 0),
        (5, "M-10005", 2, 0, 0),
        (6, "M-10006", 0, 0, 0),
    ]
    assert _rows(db, "aggregation.sql", 1) == [
        ("Arts", 2),
        ("Computer Science", 3),
        ("Databases", 5),
        ("History", 2),
    ]


def test_subqueries(db) -> None:
    assert _rows(db, "subqueries.sql", 0) == [
        (4, "A History of Libraries"),
        (6, "Query Planning Explained"),
        (8, "Poetry of the North Shore"),
        (10, "Forthcoming Catalog"),
    ]
    assert _rows(db, "subqueries.sql", 1) == [("M-10001",), ("M-10002",)]


def test_common_table_expressions(db) -> None:
    assert _rows(db, "common_table_expressions.sql", 0) == [
        ("M-10001", 2, 5, 3),
        ("M-10002", 2, 2, 0),
        ("M-10003", 0, 5, 5),
        ("M-10004", 0, 5, 5),
        ("M-10005", 0, 5, 5),
        ("M-10006", 0, 5, 5),
    ]
    reminders = _rows(db, "common_table_expressions.sql", 1)
    assert [row[0] for row in reminders] == [4, 4, 4, 4]
    assert [row[1] for row in reminders] == [
        datetime(2020, 5, 1, 15, 0, tzinfo=timezone.utc),
        datetime(2020, 5, 8, 15, 0, tzinfo=timezone.utc),
        datetime(2020, 5, 15, 15, 0, tzinfo=timezone.utc),
        datetime(2020, 5, 22, 15, 0, tzinfo=timezone.utc),
    ]


def test_window_functions_number_avery_loans_in_checkout_order(db) -> None:
    avery = [row for row in _rows(db, "window_functions.sql") if row[1] == 1]
    assert [(row[0], row[3], row[4]) for row in avery] == [
        (4, 1, 4),
        (1, 2, 4),
        (5, 3, 4),
        (11, 4, 4),
    ]


def test_overdue_most_borrowed_history_and_availability(db) -> None:
    overdue = _rows(db, "overdue_loans.sql")
    assert len(overdue) == 1
    assert overdue[0][0] == 4
    assert overdue[0][1] == "M-10001"
    assert overdue[0][2] == "Foundations of Relational Design"
    assert overdue[0][3] == "CPY-000102"

    assert _rows(db, "most_borrowed_books.sql") == [
        (1, "Foundations of Relational Design", 5, 1, 1),
        (2, "Transaction Processing in Practice", 3, 2, 2),
        (4, "A History of Libraries", 3, 2, 2),
        (3, "Indexing and Access Paths", 1, 4, 3),
        (8, "Poetry of the North Shore", 1, 4, 3),
    ]

    history = _rows(db, "member_borrowing_history.sql")
    assert [(row[0], row[6]) for row in history] == [
        (11, "open"),
        (5, "returned"),
        (1, "returned"),
        (4, "overdue"),
    ]
    assert [row[1] for row in history] == [
        "Poetry of the North Shore",
        "Transaction Processing in Practice",
        "Foundations of Relational Design",
        "Foundations of Relational Design",
    ]

    assert _rows(db, "available_copies_by_title.sql") == [
        (1, "Foundations of Relational Design", 2, 3),
        (2, "Transaction Processing in Practice", 1, 2),
        (3, "Indexing and Access Paths", 1, 1),
        (4, "A History of Libraries", 0, 2),
        (5, "Cataloging Rare Books", 1, 1),
        (6, "Query Planning Explained", 0, 1),
        (7, "Member Services Handbook", 1, 1),
        (8, "Poetry of the North Shore", 0, 2),
        (9, "Unclassified Field Notes", 1, 1),
        (10, "Forthcoming Catalog", 0, 0),
    ]


def test_views_match_the_operational_reports(db) -> None:
    clock = db.execute("SELECT now()").fetchone()
    assert clock is not None
    assert clock[0].year >= 2021
    assert clock[0].year < 2099

    overdue = db.execute(
        """
        SELECT loan_id, member_number, title, barcode, days_overdue
        FROM overdue_loans
        ORDER BY loan_id
        """
    ).fetchall()
    assert len(overdue) == 1
    assert overdue[0][0] == 4
    assert overdue[0][1] == "M-10001"
    assert overdue[0][2] == "Foundations of Relational Design"
    assert overdue[0][3] == "CPY-000102"
    assert overdue[0][4] >= 1

    as_of = db.execute(
        "SELECT loan_id FROM overdue_loans_as_of(timestamptz '2026-10-10 00:00:00+00')"
    ).fetchall()
    assert as_of == [(4,)]

    available = db.execute(
        """
        SELECT book_id, available_copies, total_copies
        FROM available_copies_by_title
        ORDER BY book_id
        """
    ).fetchall()
    assert available[0] == (1, 2, 3)
    assert available[9] == (10, 0, 0)

    history = db.execute(
        """
        SELECT loan_id, loan_state
        FROM member_borrowing_history
        WHERE member_number = 'M-10001'
        ORDER BY history_rank
        """
    ).fetchall()
    assert history == [(11, "open"), (5, "returned"), (1, "returned"), (4, "overdue")]


def test_dml_examples_change_rows_and_then_restore_them(db) -> None:
    statements = sql_statements("dml_examples.sql")
    assert len(statements) == 5
    db.execute(statements[0])
    created = db.execute(
        "SELECT description FROM categories WHERE name = 'Ephemera'"
    ).fetchone()
    assert created == ("Short-lived printed matter",)
    db.execute(statements[1])
    updated = db.execute(
        "SELECT description FROM categories WHERE name = 'Ephemera'"
    ).fetchone()
    assert updated is not None
    assert updated[0].startswith("Transient")
    db.execute(statements[2])
    assert db.execute("SELECT 1 FROM categories WHERE name = 'Ephemera'").fetchone() is None
    db.execute(statements[3])
    held = db.execute(
        "SELECT email FROM members WHERE member_number = 'M-10001'"
    ).fetchone()
    assert held == ("avery.nguyen+hold@example.edu",)
    db.execute(statements[4])
    restored = db.execute(
        "SELECT email FROM members WHERE member_number = 'M-10001'"
    ).fetchone()
    assert restored == ("avery.nguyen@example.edu",)


def test_parameterized_queries_do_not_interpret_sql(db) -> None:
    assert member_ids_for_email(db, "avery.nguyen@example.edu") == [1]
    assert member_ids_for_email(db, "' OR '1'='1") == []
    assert member_ids_for_email(db, "avery.nguyen@example.edu' OR '1'='1") == []
    file_history = _rows(db, "member_borrowing_history.sql")
    bound_history = borrowing_history(db, "M-10001")
    assert [row[0] for row in bound_history] == [row[0] for row in file_history]
    assert borrowing_history(db, "M-10001' OR '1'='1") == []


def test_explain_accepts_the_overdue_predicate(db) -> None:
    plan = db.execute(
        """
        EXPLAIN
        SELECT loan_id
        FROM loans
        WHERE returned_at IS NULL
          AND due_at < timestamptz '2026-10-10 00:00:00+00'
        """
    ).fetchall()
    text = "\n".join(row[0] for row in plan)
    assert "Scan" in text
