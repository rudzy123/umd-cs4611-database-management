-- This script is supposed to fail on the last statement.
-- The loan insert and the status update are real writes. The duplicate barcode then violates a unique constraint.
-- PostgreSQL aborts the transaction, so those writes do not remain.
-- Run it with `psql --single-transaction`, or let pytest wrap it in a savepoint.
-- Copy 301 starts available and must still be available after the failure.

INSERT INTO loans (copy_id, member_id, checked_out_at, due_at)
VALUES (
    301,
    6,
    timestamptz '2026-10-10 15:00:00+00',
    timestamptz '2026-10-31 15:00:00+00'
);

UPDATE book_copies
SET copy_status = 'on_loan'
WHERE copy_id = 301;

INSERT INTO book_copies (book_id, barcode)
VALUES (1, 'CPY-000101');
