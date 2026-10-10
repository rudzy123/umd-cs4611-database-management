-- Migration 002: secondary indexes for foreign keys and the laboratory read queries.
-- Primary keys, unique constraints, and the two partial unique indexes already exist.
-- PostgreSQL does not index the referencing side of a foreign key for you.
-- These statements are ordinary (not CONCURRENTLY) so they can run inside the migration transaction.
-- On a large production table, CREATE INDEX CONCURRENTLY is the form that avoids a long write lock,
-- and it cannot run inside a transaction block.

-- Parent deletes and "books by this author" both look up book_authors by author_id.
-- The primary key (book_id, author_id) does not serve an author_id-only lookup.
CREATE INDEX book_authors_author_id_idx
    ON book_authors (author_id);

COMMENT ON INDEX book_authors_author_id_idx IS
    'Supports author deletion checks and listing the titles of one author.';

-- The primary key (book_id, category_id) serves book_id lookups.
-- category_id lookups need their own index.
CREATE INDEX book_categories_category_id_idx
    ON book_categories (category_id);

COMMENT ON INDEX book_categories_category_id_idx IS
    'Supports category deletion checks and listing the titles in one subject.';

-- Copies of one title, including the available-copies report before it filters on status.
CREATE INDEX book_copies_book_id_idx
    ON book_copies (book_id);

COMMENT ON INDEX book_copies_book_id_idx IS
    'Supports joins from a title to its physical copies and book deletion checks.';

-- The hot predicate is status = available. A partial index stays smaller than an index of every copy.
CREATE INDEX book_copies_available_book_idx
    ON book_copies (book_id)
    WHERE copy_status = 'available';

COMMENT ON INDEX book_copies_available_book_idx IS
    'Supports available-copy lookups by title. Other statuses are absent from this index.';

-- loans_one_open_copy_idx covers only open loans. History and copy deletion also touch returned loans.
CREATE INDEX loans_copy_id_idx
    ON loans (copy_id);

COMMENT ON INDEX loans_copy_id_idx IS
    'Supports copy loan history and the foreign key from loans to book_copies.';

-- Member history is "this member, newest checkout first".
-- The leading member_id column also serves the foreign key from loans to members.
CREATE INDEX loans_member_checkout_idx
    ON loans (member_id, checked_out_at DESC);

COMMENT ON INDEX loans_member_checkout_idx IS
    'Supports a member borrowing history ordered by checkout time.';

-- Overdue reporting reads open loans by due date. Returned loans are not part of that predicate.
CREATE INDEX loans_open_due_idx
    ON loans (due_at)
    WHERE returned_at IS NULL;

COMMENT ON INDEX loans_open_due_idx IS
    'Supports the overdue report. Returned loans are excluded from the index.';

CREATE INDEX reservations_book_id_idx
    ON reservations (book_id);

COMMENT ON INDEX reservations_book_id_idx IS
    'Supports "who is waiting for this title" and book deletion checks.';

CREATE INDEX reservations_member_id_idx
    ON reservations (member_id);

COMMENT ON INDEX reservations_member_id_idx IS
    'Supports "what is this member waiting for" and member deletion checks.';

CREATE INDEX reservations_ready_copy_id_idx
    ON reservations (ready_copy_id);

COMMENT ON INDEX reservations_ready_copy_id_idx IS
    'Supports the foreign key from a ready reservation back to the held copy.';
