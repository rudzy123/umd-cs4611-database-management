# Indexes and query plans

An index is a second structure, usually a B-tree, that maps a key to the heap rows that contain it. PostgreSQL can use it for a lookup, for an ordered scan, for a nested-loop join, and for the uniqueness and foreign-key checks that run on writes. Every index is also a write: an insert into `loans` maintains every index on `loans`. The right number of indexes is the set that serves real predicates and real constraints, not one index per column.

## What already exists before migration 002

Primary keys and `UNIQUE` constraints create unique B-trees. You do not add a second index on `books.isbn13` or `book_copies.barcode`.

Two partial unique indexes are integrity rules:

| Index | Predicate | Job |
| --- | --- | --- |
| `loans_one_open_copy_idx` | `returned_at IS NULL` | At most one open loan per copy |
| `reservations_one_active_member_book_idx` | status in (`waiting`, `ready`) | At most one active hold per member per title |

A partial index omits the rows that fail the predicate. Returned loans do not occupy `loans_one_open_copy_idx`. The planner may also use that index for a query whose `WHERE` clause matches the predicate, which is a bonus, not the reason it exists. `make explain` leaves these two indexes in place in the "before" plans.

## Secondary indexes in migration 002

PostgreSQL does not index the referencing side of a foreign key. Deleting a parent row otherwise scans the child table to prove no child exists. Joins from the parent the "other" way have the same shape.

| Index | Why it is there | Cost of having it |
| --- | --- | --- |
| `book_authors_author_id_idx` | The primary key starts with `book_id`, so "titles by this author" and author deletion need `author_id` | One more update when a byline row is written |
| `book_categories_category_id_idx` | Same shape for categories | Same |
| `book_copies_book_id_idx` | Copies of a title, and deleting a book | Maintained for every copy |
| `book_copies_available_book_idx` | Partial: `copy_status = 'available'`. The available-copies lookup | Smaller than a full index, and updates that leave the available set must insert or delete an index entry |
| `loans_copy_id_idx` | Loan history for a copy, including returned loans, and the foreign key | The partial unique index does not contain returned loans |
| `loans_member_checkout_idx` | `(member_id, checked_out_at DESC)` for a member's history, and the foreign key to `members` | Maintained on every loan write. The sort order matches the history query |
| `loans_open_due_idx` | Partial: open loans by `due_at`, for the overdue report | Does not help queries about returned loans |
| `reservations_book_id_idx` | Who is waiting for a title, and book deletion | Maintained on reservation writes |
| `reservations_member_id_idx` | A member's holds, and member deletion | Same |
| `reservations_ready_copy_id_idx` | The foreign key from a ready hold to its copy | Mostly nulls. PostgreSQL still indexes the non-null keys |

`loans_member_checkout_idx` starts with `member_id`, so a separate index on `member_id` alone would be redundant for equality lookups. The extra `checked_out_at` column is there for the ordered history.

A partial index is a good trade when the predicate is selective and stable. `copy_status = 'available'` is that kind of predicate on a real shelf, where many copies are out or in repair. On this seed, most of the table is a handful of rows either way. The index is still the one the query shape wants. Selectivity is an assumption about the workload, and this seed is not the measurement of that assumption.

`CREATE INDEX CONCURRENTLY` builds an index without holding a strong write lock for the whole build. It cannot run inside a transaction. The migration uses ordinary `CREATE INDEX` so `python -m library.migrate` can apply the file atomically. On a large table you would build the new index concurrently, outside `schema_migrations`'s transaction, and then record it.

## How to read a plan

`EXPLAIN` prints the plan and the planner's estimated cost. It does not run the query. `EXPLAIN ANALYZE` runs the query and adds the actual time and the actual row counts. `BUFFERS` adds how many 8 kB pages were read from cache or from disk.

Read a node from the inside out. The child runs, and the parent consumes its rows.

- `Seq Scan` reads the heap. `Filter` removes rows after they are read. A high `Rows Removed by Filter` on a large table is a reason to look for an index that matches the filter.
- `Index Scan` walks a B-tree and fetches the heap row for each match. `Index Cond` is the predicate the index applied. A filter that remains above the index condition was not answered by the index.
- `Index Only Scan` answers from the index. It still checks the visibility map, and it falls back to the heap when the map says a page has dead tuples. Small, freshly loaded tables often cannot use an index-only scan yet.
- `Bitmap Index Scan` plus `Bitmap Heap Scan` collects matching tids and then visits the heap in physical order. The planner picks this when many rows match and a nested index-and-heap walk would bounce around the table.
- `Nested Loop`, `Hash Join`, and `Merge Join` are join methods. A nested loop wants an index on the inner side. A hash join builds a table in memory from one side. A merge join wants both sides ordered.
- `Sort` appears when the plan needs an order the scan did not produce. An index whose order matches `ORDER BY` can remove that node.
- `Aggregate` and `WindowAgg` are the grouping and window nodes. An index does not remove a `GROUP BY` over the whole table. It can make the input cheaper to read.
- Estimated `cost` is in abstract units, startup then total. Estimated `rows` is the planner's guess from the statistics `ANALYZE` collected. `EXPLAIN ANALYZE` prints the actual rows beside that guess. A large gap means the statistics are stale or the predicate is correlated in a way the planner cannot see. The seed runs `ANALYZE` so the estimates describe these rows.

`make explain` writes four files under `db/explain/`. Each file has the SQL, a plan with migration 002's indexes dropped inside a transaction that rolls back, a plan with those indexes present, and a plan with `enable_seqscan` turned off.

## What the checked-in plans show

The files in `db/explain/` were captured on PostgreSQL 16.15 after this seed was analyzed. With the planner's normal settings, all four queries are sequential scans. The most-borrowed query is a hash join of two sequential scans, then a hash aggregate. Estimated costs are the same in the "before secondary indexes" and "after secondary indexes" sections, because a one-page heap is cheaper to read directly.

With sequential scans disabled, the planner uses the indexes the predicates were written for:

- Overdue loans use `loans_open_due_idx`. The estimated cost is about 12, against about 1.2 for the sequential scan.
- Member history uses `loans_member_checkout_idx`, and that index order removes the separate Sort.
- Available copies of book 1 use `book_copies_available_book_idx`. The partial predicate supplies `copy_status = 'available'`.
- The most-borrowed join uses an index-only scan of `loans_copy_id_idx` and a nested loop into `book_copies_pkey`. Its estimated cost is about 22, against about 2.8 for the hash join.

The higher index costs are why the unrestricted plans stay sequential. That is a fact about this seed, this server, and these statistics. It is not a fact about a larger catalog. The overdue sequential scan also estimates 3 rows and returns 1. The estimate is in the file. A gap between estimated and actual rows is a reason to look at the predicate and the statistics, not a reason to declare the index good or bad.

## What this seed is allowed to prove

The seed is 6 authors, 10 books, 14 copies, and 13 loans. Those heaps are one page, or close to it. A sequential scan of one page can be cheaper than walking an index and then the heap. If the captured "after" plan is still a `Seq Scan`, the planner is doing its job. The file is evidence about this database, this PostgreSQL version, and these statistics. It is not evidence that the index is useless, and it is not evidence that the index makes the report faster on a city-sized catalog.

The section with sequential scans disabled forces the planner to show an index path when it has one. Use it to see *which* index matches the predicate. Do not quote its `actual time` as a result. Disabling a legal plan makes the remaining plan look required when it was only available.

Re-run `python -m library.explain` after a PostgreSQL upgrade or a seed change. Actual times move when the machine is busy. Estimated costs move when the statistics move.

## Worked predicates

**Overdue loans.** `returned_at IS NULL AND due_at < a timestamp`, ordered by `due_at`. `loans_open_due_idx` is a partial index on `due_at` with that null predicate. A query that forgets `returned_at IS NULL` cannot use the partial index, because the index does not contain returned loans.

**Member history.** `member_id = 1 ORDER BY checked_out_at DESC`. `loans_member_checkout_idx` has that leading column and that order. The primary key on `loan_id` does not.

**Available copies of one title.** `book_id = 1 AND copy_status = 'available'`. `book_copies_available_book_idx` matches both. `book_copies_book_id_idx` matches the book and would still filter on status.

**Most borrowed.** This aggregates every loan and joins copies to reach `book_id`. It is a small full-table aggregate. An index can feed the join. It does not turn the aggregate into a single-row lookup. On a large `loans` table the same query is a candidate for a summary table maintained by a trigger, which is a different tradeoff: faster reads, more writes, and another consistency rule. This laboratory keeps the aggregate as a query so the window functions stay visible.

## Statistics

The planner reads `pg_statistic`, filled by `ANALYZE` (and by autovacuum). The seed analyzes every laboratory table at the end of its transaction. A plan captured before that `ANALYZE` is a plan about default estimates, not about this data. If you load a larger file later, run `ANALYZE` before you compare plans.
