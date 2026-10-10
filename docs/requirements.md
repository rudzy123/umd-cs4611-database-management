# Requirements

The laboratory is a lending desk for one library. A title is a catalog record. A copy is a barcoded object. A loan is one borrowing of one copy. A reservation is a member waiting for a title, not for a specific copy, until a copy is held and the reservation becomes ready.

## What the system remembers

| Fact | Table |
| --- | --- |
| A person who can appear on a byline | `authors` |
| A cataloged edition | `books` |
| Byline position of an author on a title | `book_authors` |
| A controlled subject heading | `categories` |
| A title classified under a heading | `book_categories` |
| A patron and their card | `members` |
| A physical item and its shelf state | `book_copies` |
| A checkout and, later, its return | `loans` |
| A hold on a title | `reservations` |

A book may have several authors, and an author may write several books. A book may sit in several categories, and a category may contain many books. Both relationships are junction tables. Author names and category names are not stored as lists inside `books`.

## Identity

Surrogate keys (`author_id`, `book_id`, and the rest) are what foreign keys point at. They do not change when a barcode is reprinted or an email is corrected.

These natural keys are unique because the desk already treats them as unique:

- `books.isbn13`
- `book_copies.barcode`
- `members.member_number`
- `members.email`
- `categories.name`

Person names are not unique. Two authors may share a given name and a family name, so `authors` has no unique constraint on the name columns.

`book_authors` is identified by the pair `(book_id, author_id)`. The same pair cannot be inserted twice, and `(book_id, author_order)` is also unique so a title cannot list two authors in the same byline position.

## Rules the schema enforces

- An ISBN-13 is 13 digits and its check digit matches. `is_valid_isbn13` is an immutable function used by `books_isbn13_chk`.
- Titles, author names, category names, and member names are not blank once trimmed.
- Publication year, when present, is between 1450 and 2100. Page count, when present, is positive. Birth year, when present, is between 1 and 2100. These bounds are constants. A check constraint cannot call `CURRENT_DATE`, because that function is not immutable.
- A member number looks like `M-10001`. An email has one `@` and a dot in the domain. This is a laboratory pattern, not a full mail parser.
- Membership status is `active`, `suspended`, or `expired`. New members default to `active`, a loan limit of 5, and `joined_on` of the current date.
- Copy status is `available`, `on_loan`, `held`, `maintenance`, or `lost`. Condition is `new`, `good`, `fair`, or `poor`. New copies default to `available`, `good`, and `acquired_on` of the current date. Barcodes look like `CPY-000101`.
- A loan is due after it was checked out. A return timestamp is null or at least as late as checkout.
- A reservation status is `waiting`, `ready`, `fulfilled`, `cancelled`, or `expired`. Status `ready` requires `ready_copy_id`. Status `fulfilled` requires `fulfilled_at`, and every other status requires `fulfilled_at` to be null.
- A copy has at most one open loan. The partial unique index `loans_one_open_copy_idx` covers rows where `returned_at` is null. Returned loans stay in the table and out of that index.
- A member has at most one `waiting` or `ready` reservation for a given title.
- A copy whose status is `on_loan` has exactly one open loan. Any other status has zero open loans. A deferred constraint trigger checks this at commit, so one transaction can insert the loan and update the copy together.
- Open loans for a member cannot exceed `loan_limit`. The same deferred mechanism checks the count at commit. Lowering Avery Nguyen's limit below her two open loans fails the commit and leaves the old limit in place.

Foreign keys:

- Deleting a book cascades its byline rows, category links, and reservations. It does not cascade copies. A title that still has copies cannot be deleted.
- Deleting an author or a category that is still referenced is rejected.
- Deleting a member who still has loans is rejected. Reservations cascade.
- Deleting a copy that still has loans, or that is the `ready_copy_id` of a reservation, is rejected. A hold has to be released before that copy can leave the catalog.
- Loans point at a real copy and a real member.

## Checkout

`checkout_copy(copy_id, member_id, loan_days)` is the supported way to lend a copy.

1. The loan period is 1 to 90 days. The default is 21.
2. The copy row is locked with `SELECT ... FOR UPDATE`. The status must be `available`.
3. The member row is locked. The status must be `active`.
4. Open loans for that member must be below `loan_limit`.
5. The function inserts a `loans` row and sets the copy to `on_loan`.
6. Any error aborts the transaction. The loan insert and the status update are one unit.

The lock order is copy, then member, in every checkout. Two checkouts cannot deadlock by taking those locks in opposite orders.

`return_copy(copy_id)` closes the open loan and sets an `on_loan` copy back to `available`.

Python calls these functions with `%s` placeholders. The values travel separately from the SQL text. See [transactions.md](transactions.md).

## Reports

| Question | Where it lives |
| --- | --- |
| Which open loans were due before a chosen instant? | `db/queries/overdue_loans.sql`, the view `overdue_loans`, and `overdue_loans_as_of(timestamptz)` |
| Which titles have been borrowed the most, and how do ties rank? | `db/queries/most_borrowed_books.sql` |
| What has one card number borrowed, newest first? | `db/queries/member_borrowing_history.sql` and the view `member_borrowing_history` |
| How many copies of each title are available? | `db/queries/available_copies_by_title.sql` and the view `available_copies_by_title` |

The SQL files also cover inserts, updates, deletes, inner and outer joins, grouping, subqueries, common table expressions, and window functions.

The seed's overdue loan is due on 2020-05-22 and is still open. Open loans that are not overdue are due in 2099. Reports that use `now()` and reports that use `2026-10-10` agree for any clock between those dates. `overdue_loans_as_of` exists so a test can name its reporting instant.

## Outside this version

Fines, renewals, staff accounts, and automatically expiring reservations are not implemented. `expires_at` is stored and is not enforced by a scheduled job. A reserved copy is checked out only after some later operation changes it from `held` to `available` or teaches checkout to accept that member. This laboratory stops at the hold itself.

## How the requirements are checked

`tests/test_schema_constraints.py`, `tests/test_foreign_keys.py`, and `tests/test_duplicates.py` reject the illegal rows. `tests/test_checkout.py` covers a successful lend, the rejected cases, a forced rollback, and two sessions racing for one copy. `tests/test_queries.py` checks the seed and the reports. `tests/test_migrations.py` applies the up files to an empty database named `library_migration_check` and then drops it.
