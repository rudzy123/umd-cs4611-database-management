# Captured query plans

`make explain` writes one text file per workload query:

- `overdue_loans.plan.txt`
- `member_history.plan.txt`
- `available_copies.plan.txt`
- `most_borrowed.plan.txt`

Each file contains:

1. `EXPLAIN` and `EXPLAIN ANALYZE` after the partial unique indexes from migration 001, with the migration 002 indexes dropped inside a transaction that rolls back.
2. The same two plans with the secondary indexes present.
3. The same two plans with sequential scans disabled, so an index path is visible even when the planner prefers a sequential scan.

Read `docs/indexing.md` before treating any file as evidence. The seed is a few dozen rows. A sequential scan on that data is a normal planner choice, and a lower estimated cost on this seed is not a general performance result.

On the PostgreSQL 16.15 capture in this directory, the unrestricted plans are sequential scans and the estimated costs match before and after the secondary indexes. With sequential scans disabled, overdue loans use `loans_open_due_idx`, member history uses `loans_member_checkout_idx`, available copies use `book_copies_available_book_idx`, and the most-borrowed join uses `loans_copy_id_idx`. Those index plans have higher estimated costs on this seed, which is why the planner does not pick them on its own.

Regenerate the files after `python -m library.migrate` and `python -m library.seed`. Actual times change from machine to machine. Estimated costs are stable only while the seed statistics and the PostgreSQL version stay the same.
