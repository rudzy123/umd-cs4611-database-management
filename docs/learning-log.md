# Learning log

This is the design journal for the reference implementation. The other documents teach the model. This one records the decisions, the mistakes that were easy to make, and what the captured plans are allowed to mean.

## The grain of a row

The first useful question was "what is one row?" A book is not a copy. A copy is not a loan. A loan is not a reservation. Once those are different rows, the foreign keys have somewhere to point, and a title with no copies (Forthcoming Catalog) is an ordinary left join instead of a missing barcode inside a list.

Authors and categories were the many-to-many cases. A comma-separated `author_names` column is shorter to type and cannot express byline order, cannot reference `authors`, and cannot be unique per position. `book_authors (book_id, author_id, author_order)` with two unique keys is the whole idea of a junction table that carries an attribute. `book_categories` is the same idea with nothing extra to store.

Names are not keys. Mira Chen is `author_id` 1 because two people can share a name. ISBN, barcode, card number, email, and category name are unique because the desk already treats them as unique. The surrogate keys exist so a corrected ISBN does not have to cascade through every loan.

## Normal form, and the status column

Walking 1NF through BCNF on `book_authors` is the part worth doing by hand. Both `(book_id, author_id)` and `(book_id, author_order)` are candidate keys, and each determines the other attribute. That is BCNF, not a coincidence of "we used a junction table."

`copy_status` was the column most likely to be called denormalized for the wrong reason. It is redundant with loans only if the only statuses are available and on loan. Held, maintenance, and lost are different facts that all have zero open loans. The column stays. What was added, because the column can drift, is a deferred constraint: `on_loan` means exactly one open loan, and every other status means zero. The loan limit got the same treatment. Normal form did not give us those rules. Constraints did.

The deferral is the part that surprised me into a bug the first time I thought about the seed. If the trigger ran at the end of each statement, inserting an `on_loan` copy before its loan would fail. Checking at commit lets the transaction update both tables and then be judged. It also means `psql -f` without `--single-transaction` is the wrong way to load the seed. The runner and the README say so in the place a person will hit the error.

## Checkout

The operation is small and the failure modes are specific.

- Two desks lend the same barcode. Lock the copy. The second transaction waits, then sees `on_loan`.
- Two desks lend different barcodes to a member with one slot left. Locking the copies does not serialize them. Lock the member, because the count was a read of the member's loans.
- A checkout writes the loan and crashes before the status update. One transaction, so the crash is a rollback. The forced-failure test and `transaction_rollback.sql` are that story with an exception standing in for the crash.
- Someone inserts a loan with raw SQL and ignores the function. The partial unique index stops a second open loan on that copy. The deferred trigger stops a status that does not match, and it stops a member who is over the limit, at commit.

Lock order is copy then member so two checkouts cannot deadlock by taking the pair in opposite orders. That is a small rule and it belongs next to the `FOR UPDATE` rather than in a comment nobody sees. It is in the function comment and in the transactions note.

Read Committed is the isolation level in use. Dirty reads are not a PostgreSQL phenomenon at the levels it runs. Non-repeatable reads and phantoms are real at Read Committed, and the row locks cover the rows this decision reads. Write skew on the loan limit is the anomaly that makes the member lock necessary. Serializable would also catch a broad class of those schedules, and it would require retries. Naming the row was the clearer laboratory design.

## Parameters

The email lookup is the injection lesson because the bad payload is obvious: `' OR '1'='1`. Bound with `%s`, that string is an email that matches nobody. Concatenated, it is a different statement. The checkout path uses the same binding for ids and the loan period. Identifiers are not values. The explain tool wraps index names in `psycopg.sql.Identifier` even though those names are constants, so the difference stays visible.

## Indexes, and what I will not claim

Foreign keys in PostgreSQL do not create an index on the child. That is the fact that justifies half of migration 002. The other half is three read shapes: overdue open loans by due date, one member's history in checkout order, and available copies of one title. Partial indexes match the first and the third because the predicate is the same one the query has to write anyway.

The seed is a few dozen rows. I will not say the indexes made those queries faster. A one-page heap is allowed to be a sequential scan, and if the captured "after" plan is a sequential scan, that is the planner being right about this data. The files in `db/explain/` record the plans anyway, including a run with sequential scans disabled so the index path can be seen. The disabled-scan section is a diagram of an access path. It is not a timing result.

The capture checked in under `db/explain/` is from PostgreSQL 16.15. Unrestricted plans are sequential scans, and the estimated costs do not change when migration 002's indexes are added. Forcing the index path makes overdue loans use `loans_open_due_idx` (estimated cost about 12, against about 1.2 for the sequential scan) and makes member history use `loans_member_checkout_idx`, whose order removes the Sort. Available copies use `book_copies_available_book_idx`. The most-borrowed join becomes an index-only scan of `loans_copy_id_idx` nested-looped to the copy primary key, at an estimated cost of about 22 against about 2.8. The planner's preference for the sequential scan is the result. The predicates are still why those indexes exist.

Regenerate the files with `python -m library.explain` after the seed is loaded. Quote a plan from those files when you talk about this database. Quote the predicate, not the timing, when you talk about a larger one.

## What the tests are for

A constraint that is not violated by a test is a comment. The suite inserts the bad ISBN, the second open loan, the dangling member, the duplicate byline position, and the checkout that must fail. It also builds a new database from the up files so a migration that only works on a database that was edited by hand will fail. Tests that only read roll back. The two that commit — the deferred-trigger rejections and the two-session checkout — put the seed back before they return.

## Questions worth answering with the database closed

1. Which two candidate keys does `book_authors` have, and why is the relation still in BCNF?
2. Why can Cartography exist with no books, and why can Forthcoming Catalog exist with no copies?
3. Why is `copy_status` allowed to be stored, and which commit-time rule keeps it honest?
4. What does the second checkout of copy 103 wait on, and what does it see after the first one commits?
5. Why does the loan-limit race need a lock on the member when the two copies are different rows?
6. Why would `loans_open_due_idx` be useless to a query that forgets `returned_at IS NULL`?
7. What changes about `' OR '1'='1` when it is a bound parameter instead of a piece of the SQL text?

The answers are in [normalization.md](normalization.md), [er-model.md](er-model.md), [transactions.md](transactions.md), [indexing.md](indexing.md), and `src/library/queries.py`.
