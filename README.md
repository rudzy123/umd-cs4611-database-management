# CS 4611 library-lending laboratory

A small relational library you can build, query, and break on purpose. Patrons borrow physical copies of cataloged titles. The schema keeps titles, copies, loans, and reservations in separate tables, and checkout is one transaction.

PostgreSQL 16 stores the data. SQL migrations create it. Python 3.12 and `psycopg` call checkout with bound parameters. `pytest` checks the constraints, the queries, and a migration onto an empty database.

The people, titles, and ISBN-13 values in the seed are fictional. The ISBN-13 check digits are valid so the check constraint has a real rule to enforce. The password in `docker-compose.yml` is a local teaching default.

## Layout

| Path | Role |
| --- | --- |
| `db/migrations/` | Up-only schema, indexes, views, and checkout |
| `db/seeds/001_seed.sql` | Deterministic rows |
| `db/queries/` | Inserts, joins, aggregates, subqueries, CTEs, windows, and reports |
| `db/explain/` | How to read captured plans, plus the plans `make explain` writes |
| `docs/` | Requirements, modeling, normal forms, indexes, transactions |
| `src/library/` | Migration runner, seed loader, checkout, parameterized reads |
| `tests/` | Constraints, foreign keys, checkout, queries, clean-database migration |

## Prerequisites

- Docker with Compose v2
- Python 3.12
- The port `5432` available for PostgreSQL

## Start

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
docker compose up -d --wait
python -m library.migrate
python -m library.seed
python -m pytest
python -m library.explain
```

`make install`, `make up`, and `make check` run the same steps when `python` on your `PATH` is the virtualenv. `make psql` opens a shell in the database container.

`DATABASE_URL` defaults to `postgresql://library:library@localhost:5432/library`.

## Reset strategy

Migrations are **up only**. There are no down files. `schema_migrations` records each filename after it commits, and a later edit to a file that is already recorded will not be replayed.

The supported rebuild is to drop the data directory and apply every up file again:

```bash
make reset
```

That runs `docker compose down -v`, starts a new PostgreSQL 16 volume, applies `db/migrations/*.sql` in order, and loads `db/seeds/001_seed.sql`.

Apply the seed as one transaction. Copy rows are inserted with status `on_loan` before their open loan rows exist, and a deferred constraint checks the pair at commit. `python -m library.seed` wraps the file in one transaction. With `psql`, use `--single-transaction`. Running the seed again truncates the laboratory tables and reloads the same rows. It does not remove `schema_migrations`.

## Learning path

1. [Requirements](docs/requirements.md) — what the library must remember and reject.
2. [ER model](docs/er-model.md) — conceptual, logical, and physical models.
3. [Normalization](docs/normalization.md) — 1NF through BCNF on this schema.
4. `db/migrations/` and `db/seeds/` — the physical design as SQL.
5. `db/queries/` — the relational operators and the four reports.
6. [Indexing](docs/indexing.md) and `db/explain/` — which indexes exist, and how to read a plan.
7. [Transactions](docs/transactions.md) — ACID, isolation, checkout, rollback, and parameterized queries.
8. `tests/` — the invariants, stated as executable checks.
9. [Learning log](docs/learning-log.md) — the design journal for this reference implementation.

## Schema in one screen

- `authors` and `books` meet in `book_authors`, with a byline position.
- `categories` and `books` meet in `book_categories`.
- `book_copies` are the barcoded objects. `loans` record who has one, and when it is due.
- `reservations` wait on a **title**. A ready reservation names the held copy.
- `members.loan_limit` caps open loans. Checkout also requires `membership_status = 'active'`.

`checkout_copy(copy_id, member_id, loan_days)` locks the copy, locks the member, inserts the loan, and marks the copy `on_loan`. Failure rolls the transaction back. Two sessions cannot both commit a checkout of the same available copy.

## Tests

`pytest` rolls back the work of each ordinary test. Two tests commit on purpose and then restore the seed: one shows a deferred constraint rejecting a bad commit, and one runs two checkout sessions against the same copy. `tests/test_migrations.py` creates `library_migration_check`, migrates it, seeds it, and drops it.

## Plans

`python -m library.explain` rewrites `db/explain/*.plan.txt`. Read [docs/indexing.md](docs/indexing.md) with those files. The seed is small enough that a sequential scan can be the planner's cheapest plan. The captured files include a section with sequential scans disabled so the index path is visible. That section is a plan shape, not a benchmark.

## License

MIT. See [LICENSE](LICENSE).
