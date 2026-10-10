-- Deterministic laboratory seed.
-- Apply with `python -m library.seed` or:
--   psql --single-transaction -v ON_ERROR_STOP=1 -f db/seeds/001_seed.sql
-- One transaction is required. Copy rows are inserted as on_loan before their open loans exist,
-- and the deferred trigger accepts that pair only when both writes commit together.
-- People, titles, and ISBN-13 values are fictional. The check digits are valid.
-- Timestamps use an explicit +00 offset so the rows do not depend on the session TimeZone.
-- The overdue loan is due in 2020, so overdue reports stay overdue for the life of the lab.
-- Open loans that are not overdue are due in 2099.

TRUNCATE TABLE
    loans,
    reservations,
    book_copies,
    book_authors,
    book_categories,
    books,
    authors,
    members,
    categories
RESTART IDENTITY CASCADE;

INSERT INTO authors (author_id, given_name, family_name, birth_year)
OVERRIDING SYSTEM VALUE
VALUES
    (1, 'Mira', 'Chen', 1978),
    (2, 'Jonah', 'Adeyemi', 1984),
    (3, 'Helen', 'Okonkwo', 1971),
    (4, 'Priya', 'Shah', 1990),
    (5, 'Luis', 'Ortega', 1968),
    (6, 'Samira', 'Haddad', 1988);

INSERT INTO categories (category_id, name, description)
OVERRIDING SYSTEM VALUE
VALUES
    (1, 'Databases', 'Models, languages, and systems for managing data'),
    (2, 'Computer Science', 'Computation, systems, and software design'),
    (3, 'History', 'Historical studies and institutional memory'),
    (4, 'Arts', 'Literature and the visual arts'),
    (5, 'Library Science', 'Professional practice of libraries'),
    (6, 'Cartography', 'Maps and spatial description. No title is classified here yet.');

INSERT INTO members (
    member_id, member_number, given_name, family_name, email,
    joined_on, membership_status, loan_limit
)
OVERRIDING SYSTEM VALUE
VALUES
    (1, 'M-10001', 'Avery', 'Nguyen', 'avery.nguyen@example.edu', DATE '2024-01-10', 'active', 5),
    (2, 'M-10002', 'Blake', 'Okonkwo', 'blake.okonkwo@example.edu', DATE '2024-02-02', 'active', 2),
    (3, 'M-10003', 'Casey', 'Ibrahim', 'casey.ibrahim@example.edu', DATE '2023-11-20', 'suspended', 5),
    (4, 'M-10004', 'Devon', 'Patel', 'devon.patel@example.edu', DATE '2025-09-01', 'active', 5),
    (5, 'M-10005', 'Ellis', 'Romero', 'ellis.romero@example.edu', DATE '2022-05-15', 'expired', 5),
    (6, 'M-10006', 'Farah', 'Mensah', 'farah.mensah@example.edu', DATE '2026-01-15', 'active', 5);

INSERT INTO books (book_id, isbn13, title, publication_year, publisher, page_count)
OVERRIDING SYSTEM VALUE
VALUES
    (1, '9780004611006', 'Foundations of Relational Design', 2018, 'Harbor Academic Press', 412),
    (2, '9780004611013', 'Transaction Processing in Practice', 2021, 'Harbor Academic Press', 288),
    (3, '9780004611020', 'Indexing and Access Paths', 2019, 'North Pier Press', 350),
    (4, '9780004611037', 'A History of Libraries', 2016, 'Lantern House', 510),
    (5, '9780004611044', 'Cataloging Rare Books', 2020, 'Lantern House', 240),
    (6, '9780004611051', 'Query Planning Explained', 2022, 'North Pier Press', 198),
    (7, '9780004611068', 'Member Services Handbook', 2014, 'Civic Shelf', 120),
    (8, '9780004611075', 'Poetry of the North Shore', 2017, 'Lantern House', 96),
    (9, '9780004611082', 'Unclassified Field Notes', 2023, 'Civic Shelf', 64),
    (10, '9780004611099', 'Forthcoming Catalog', 2026, 'Harbor Academic Press', NULL);

INSERT INTO book_authors (book_id, author_id, author_order)
VALUES
    (1, 1, 1),
    (1, 2, 2),
    (2, 1, 1),
    (3, 2, 1),
    (3, 4, 2),
    (4, 3, 1),
    (5, 3, 1),
    (5, 6, 2),
    (6, 4, 1),
    (7, 5, 1),
    (8, 6, 1),
    (9, 5, 1),
    (10, 1, 1);

INSERT INTO book_categories (book_id, category_id)
VALUES
    (1, 1),
    (1, 2),
    (2, 1),
    (3, 1),
    (3, 2),
    (4, 3),
    (5, 3),
    (5, 4),
    (6, 1),
    (6, 2),
    (7, 5),
    (8, 4),
    (10, 1);

INSERT INTO book_copies (copy_id, book_id, barcode, copy_status, condition, acquired_on)
OVERRIDING SYSTEM VALUE
VALUES
    (101, 1, 'CPY-000101', 'available', 'good', DATE '2023-01-15'),
    (102, 1, 'CPY-000102', 'on_loan', 'good', DATE '2023-01-15'),
    (103, 1, 'CPY-000103', 'available', 'fair', DATE '2024-06-01'),
    (201, 2, 'CPY-000201', 'on_loan', 'good', DATE '2023-03-01'),
    (202, 2, 'CPY-000202', 'available', 'good', DATE '2023-03-01'),
    (301, 3, 'CPY-000301', 'available', 'good', DATE '2023-05-20'),
    (401, 4, 'CPY-000401', 'on_loan', 'good', DATE '2022-09-01'),
    (402, 4, 'CPY-000402', 'maintenance', 'fair', DATE '2022-09-01'),
    (501, 5, 'CPY-000501', 'available', 'new', DATE '2024-02-14'),
    (601, 6, 'CPY-000601', 'lost', 'poor', DATE '2023-08-08'),
    (701, 7, 'CPY-000701', 'available', 'good', DATE '2022-11-11'),
    (801, 8, 'CPY-000801', 'on_loan', 'good', DATE '2023-04-04'),
    (802, 8, 'CPY-000802', 'held', 'good', DATE '2023-04-04'),
    (901, 9, 'CPY-000901', 'available', 'good', DATE '2024-09-09');

-- Loan ids are stable so the query tests can name them.
-- Open loans: 4 (overdue), 6, 10, and 11.
INSERT INTO loans (loan_id, copy_id, member_id, checked_out_at, due_at, returned_at)
OVERRIDING SYSTEM VALUE
VALUES
    (1, 101, 1,
        timestamptz '2025-11-01 15:00:00+00',
        timestamptz '2025-11-22 15:00:00+00',
        timestamptz '2025-11-18 15:00:00+00'),
    (2, 101, 2,
        timestamptz '2025-12-01 15:00:00+00',
        timestamptz '2025-12-22 15:00:00+00',
        timestamptz '2025-12-15 15:00:00+00'),
    (3, 103, 4,
        timestamptz '2025-01-15 15:00:00+00',
        timestamptz '2025-02-05 15:00:00+00',
        timestamptz '2025-02-01 15:00:00+00'),
    (4, 102, 1,
        timestamptz '2020-05-01 15:00:00+00',
        timestamptz '2020-05-22 15:00:00+00',
        NULL),
    (5, 202, 1,
        timestamptz '2026-03-01 15:00:00+00',
        timestamptz '2026-03-22 15:00:00+00',
        timestamptz '2026-03-20 15:00:00+00'),
    (6, 201, 2,
        timestamptz '2026-09-05 15:00:00+00',
        timestamptz '2099-01-05 15:00:00+00',
        NULL),
    (7, 301, 4,
        timestamptz '2025-01-10 15:00:00+00',
        timestamptz '2025-01-31 15:00:00+00',
        timestamptz '2025-02-01 15:00:00+00'),
    (8, 401, 5,
        timestamptz '2024-06-01 15:00:00+00',
        timestamptz '2024-06-22 15:00:00+00',
        timestamptz '2024-06-20 15:00:00+00'),
    (9, 402, 3,
        timestamptz '2024-07-01 15:00:00+00',
        timestamptz '2024-07-22 15:00:00+00',
        timestamptz '2024-07-10 15:00:00+00'),
    (10, 401, 2,
        timestamptz '2026-09-01 15:00:00+00',
        timestamptz '2099-01-01 15:00:00+00',
        NULL),
    (11, 801, 1,
        timestamptz '2026-09-20 15:00:00+00',
        timestamptz '2099-03-01 15:00:00+00',
        NULL),
    (12, 103, 3,
        timestamptz '2024-02-01 15:00:00+00',
        timestamptz '2024-02-22 15:00:00+00',
        timestamptz '2024-02-20 15:00:00+00'),
    (13, 202, 5,
        timestamptz '2024-08-01 15:00:00+00',
        timestamptz '2024-08-22 15:00:00+00',
        timestamptz '2024-08-18 15:00:00+00');

INSERT INTO reservations (
    reservation_id, book_id, member_id, reserved_at,
    reservation_status, ready_copy_id, expires_at, fulfilled_at
)
OVERRIDING SYSTEM VALUE
VALUES
    (1, 6, 1, timestamptz '2026-09-01 15:00:00+00', 'waiting', NULL, NULL, NULL),
    (2, 8, 4, timestamptz '2026-09-25 15:00:00+00', 'ready', 802, timestamptz '2099-01-15 15:00:00+00', NULL),
    (3, 1, 3, timestamptz '2026-04-01 15:00:00+00', 'cancelled', NULL, NULL, NULL);

SELECT setval(pg_get_serial_sequence('authors', 'author_id'), (SELECT max(author_id) FROM authors));
SELECT setval(pg_get_serial_sequence('categories', 'category_id'), (SELECT max(category_id) FROM categories));
SELECT setval(pg_get_serial_sequence('members', 'member_id'), (SELECT max(member_id) FROM members));
SELECT setval(pg_get_serial_sequence('books', 'book_id'), (SELECT max(book_id) FROM books));
SELECT setval(pg_get_serial_sequence('book_copies', 'copy_id'), (SELECT max(copy_id) FROM book_copies));
SELECT setval(pg_get_serial_sequence('loans', 'loan_id'), (SELECT max(loan_id) FROM loans));
SELECT setval(pg_get_serial_sequence('reservations', 'reservation_id'), (SELECT max(reservation_id) FROM reservations));

ANALYZE authors;
ANALYZE categories;
ANALYZE members;
ANALYZE books;
ANALYZE book_authors;
ANALYZE book_categories;
ANALYZE book_copies;
ANALYZE loans;
ANALYZE reservations;
