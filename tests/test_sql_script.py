"""The migration runner must not split function bodies on their semicolons."""

from pathlib import Path

from library.sql_script import split_sql

ROOT = Path(__file__).resolve().parents[1]


def test_dollar_quoted_function_stays_one_statement() -> None:
    script = """
    CREATE FUNCTION f() RETURNS void LANGUAGE plpgsql AS $$
    BEGIN
        PERFORM 1;
    END;
    $$;
    SELECT 1;
    """
    statements = split_sql(script)
    assert len(statements) == 2
    assert "PERFORM 1;" in statements[0]
    assert statements[1] == "SELECT 1"


def test_migrations_are_not_split_inside_functions() -> None:
    for path in sorted((ROOT / "db" / "migrations").glob("*.sql")):
        for statement in split_sql(path.read_text(encoding="utf-8")):
            head = statement.lstrip()[:80].upper()
            assert not head.startswith("PERFORM"), path.name
            assert not head.startswith("IF "), path.name
            assert not head.startswith("ELSIF"), path.name
            assert not head.startswith("RETURN NULL"), path.name
            assert not head.startswith("SELECT COPY_STATUS"), path.name


def test_seed_and_queries_split_into_executable_statements() -> None:
    seed = split_sql((ROOT / "db" / "seeds" / "001_seed.sql").read_text(encoding="utf-8"))
    assert any("TRUNCATE" in statement.upper() for statement in seed)
    assert any("9780004611006" in statement for statement in seed)
    overdue = split_sql(
        (ROOT / "db" / "queries" / "overdue_loans.sql").read_text(encoding="utf-8")
    )
    assert len(overdue) == 1
    assert "RETURNED_AT IS NULL" in overdue[0].upper()
