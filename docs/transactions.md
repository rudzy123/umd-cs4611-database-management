# Transactions, isolation, and parameterized queries

A checkout is two writes that must succeed or fail together: a new row in `loans`, and `book_copies.copy_status = 'on_loan'`. PostgreSQL gives that pair a transaction. The function `checkout_copy` is the supported way to open one. The Python helper in `src/library/checkout.py` calls it with bound parameters and rolls back when the function raises.

## ACID, mapped onto checkout

**Atomicity.** The loan insert and the status update commit together or they both disappear. `tests/test_checkout.py` demonstrates this twice. `force_checkout_failure` locks the copy, inserts a legal loan, updates the status, and then raises. The surrounding transaction rolls back, the loan count is unchanged, and the copy is still `available`. `db/queries/transaction_rollback.sql` does the same shape in SQL: it inserts a loan for copy 301, marks that copy `on_loan`, and then inserts a duplicate barcode. The unique violation aborts the transaction. Copy 301 is still `available`, and the loan is gone. A statement-level error is enough. You do not need a special "rollback command" after a failure inside `psycopg`'s transaction block. Leaving the block with an exception rolls back.

**Consistency.** Checks, foreign keys, unique indexes, and the deferred triggers are the consistency rules. `checkout_copy` adds the desk rules that are awkward as a single `CHECK`: the copy is available, the member is active, and the member is under the loan limit. The deferred triggers run at commit, so a transaction may pass through a moment where the copy is `on_loan` and the loan row is not inserted yet, or the reverse. Another session cannot see that moment. If the transaction commits with the two sides in disagreement, the trigger raises SQLSTATE `23514` and the commit becomes a rollback. `test_commit_rejects_on_loan_without_an_open_loan` marks an available copy `on_loan` and shows that the committed status is still `available`. `test_commit_rejects_a_loan_limit_breach` lowers Avery's limit below her two open loans and shows that the limit is still 5.

**Isolation.** Checkout runs at PostgreSQL's default, Read Committed, and it takes row locks on the rows the decision depends on. The section below names the anomalies and the lock that closes each one for this operation. Isolation level is a session property. The function does not issue `SET TRANSACTION ISOLATION LEVEL SERIALIZABLE`, because the locks make the specific decision safe at Read Committed.

**Durability.** A successful commit is a write to the WAL. After the commit returns, a crash recovery replays that commit. Durability is a property of the server (`fsync`, `synchronous_commit`, and the storage under the data directory). The checkout function does not reimplement it. `make reset` deletes the Docker volume on purpose, which is the opposite of durability: it is the laboratory rebuild.

## What checkout locks

```text
BEGIN;
  SELECT copy_status FROM book_copies WHERE copy_id = $1 FOR UPDATE;
  -- status must be 'available'
  SELECT membership_status, loan_limit FROM members WHERE member_id = $2 FOR UPDATE;
  -- status must be 'active', and open loans must be below the limit
  INSERT INTO loans ...;
  UPDATE book_copies SET copy_status = 'on_loan' WHERE copy_id = $1;
COMMIT;
```

`FOR UPDATE` locks the latest committed version of the row and holds that lock until this transaction ends. A second checkout of the same copy blocks on the copy lock. When the first transaction commits, the second proceeds, reads `on_loan`, and raises. When the first transaction rolls back, the second reads `available` and may continue. `tests/test_checkout.py::test_conflicting_checkouts_allow_only_one_winner` runs those two sessions on copy 103.

The member lock closes a different race. Blake's limit is 2 and he already has 2 open loans, so a single checkout fails the limit check. The interesting case is a member with one slot left and two sessions lending two different copies. Without the member lock, both sessions can count one open loan, both can insert, and the member ends above the limit. Both sessions take `FOR UPDATE` on the same member row, so the second count happens after the first commit and sees the new loan. The deferred loan-limit trigger is the backstop for an `INSERT` that bypasses the function.

Lock order is copy, then member, in every checkout. `return_copy` locks the copy and then the open loan. Two operations that follow one order do not deadlock with each other by taking the same two rows in opposite orders.

The partial unique index is a third guard. Two open loans for one copy cannot both be inserted, even if a session forgot the row lock. The second insert gets a unique violation immediately, not at commit.

## Isolation levels

PostgreSQL treats the SQL standard's Read Uncommitted as Read Committed. A transaction never sees another transaction's uncommitted rows. The phenomena below are the ones that remain, described on this schema.

| Level | What a checkout sees |
| --- | --- |
| Read Committed (the default) | Each statement gets a new snapshot. A row committed by someone else becomes visible to your next statement. |
| Repeatable Read | The transaction keeps one snapshot. A later statement does not see rows other transactions committed after your first statement. An update that conflicts with a row someone else committed can fail with a serialization error. |
| Serializable | Repeatable Read plus predicate tracking. PostgreSQL may abort one of two transactions whose reads and writes would not match any serial order. |

**Dirty read.** Session A updates a copy to `on_loan` and has not committed. Session B reads that uncommitted status. PostgreSQL does not run this phenomenon at any isolation level it offers. B sees the previous committed status until A commits.

**Non-repeatable read.** At Read Committed, session A reads copy 101 as `available`. Session B checks it out and commits. Session A's next `SELECT` of the same row sees `on_loan`. The row is the same row, and the values changed. `checkout_copy` avoids acting on a stale read by holding `FOR UPDATE` from the read of the status until commit. B cannot change that row in the middle of A's checkout.

**Phantom.** At Read Committed, session A counts Blake's open loans. Session B commits a new loan for Blake. Session A's next count includes a row that was not there. The member lock prevents another *checkout* from inserting that phantom while A is between the count and the insert. A raw `INSERT` from a session that never locks the member can still create the row. The deferred trigger then sees the final count at commit.

**Write skew.** Two sessions each read "this member has one slot left," and each inserts a loan for a different copy. Neither updates a row the other updated, so a row lock on the copies does not serialize them. Both commits can succeed at Read Committed and, for this pattern, at Repeatable Read as well, because each session's snapshot still shows the old count. The result is two new loans and a broken limit. Serializable isolation is PostgreSQL's general answer: one of the two transactions can be aborted with `40001`. This laboratory also answers it directly, by locking the member row that the limit decision depends on. Lock the rows you used to decide. Serializable is the safety net when the predicate is too wide to name those rows, and it requires the application to retry serialization failures.

**Lost update.** Two sessions read `available` and both write `on_loan`. The second write would cover the first, and one loan would be missing from the story the status tells. `FOR UPDATE` makes the second session wait and then see the first write. The partial unique index also stops the second open loan if both sessions get as far as `INSERT`.

The anomaly names are standard. The checkout behavior is specific: Read Committed, plus locks on the copy and the member, plus a partial unique index, plus deferred constraint triggers.

## Why the seed is one transaction

The deferred triggers run at `COMMIT`, not after each statement. The seed inserts `on_loan` copies before it inserts the matching open loans. Each statement, committed alone, would fail the trigger. `python -m library.seed` sends the file as one transaction, the triggers see both sides, and the commit succeeds. `psql -f` without `--single-transaction` commits every statement by itself and will fail on the first `on_loan` copy. That failure is the constraint working.

A savepoint rolling back does not leave the deferred check half-applied. The check is part of the commit of the outer transaction. Tests that raise inside `conn.transaction()` are rolling back a savepoint when the test fixture already opened a transaction, and the fixture then rolls the outer transaction back as well.

## Parameterized queries

SQL injection is a second statement, or a changed predicate, hiding inside a value that was pasted into the SQL text.

This shape is unsafe. The laboratory code does not build statements this way:

```python
statement = f"SELECT member_id FROM members WHERE email = '{email}'"
```

If `email` is `' OR '1'='1`, the text becomes a predicate that is true for every row, depending on quotes. The database did what the text said. The bug is that the text and the data were mixed.

The safe call binds the value:

```python
conn.execute(
    "SELECT member_id FROM members WHERE email = %s",
    (email,),
)
```

In `psycopg` 3, `%s` is a placeholder marker, not Python's old `%` formatting. The driver sends the SQL and the value in separate parts of the message. The value is data even when it contains quotes, semicolons, or `--`. `member_ids_for_email` and `borrowing_history` in `src/library/queries.py` are written this way, and `checkout_copy` passes `copy_id`, `member_id`, and `loan_days` the same way. `tests/test_queries.py` looks up the address `' OR '1'='1` and gets no rows.

Placeholders bind values. They do not bind identifiers. A table name or a column name that comes from input has to be composed with `psycopg.sql.Identifier`, after the name has been checked against a list you control. This laboratory does not build dynamic identifiers. The migration runner's index names in `explain.py` are constants wrapped in `sql.Identifier` so the habit is visible.

`search_path` on the PL/pgSQL functions is set to `pg_catalog, public`. That stops a temporary object named `now` or `count` from changing what the function calls. It is the same idea as parameterization: the name in the function should resolve to the object the author meant.
