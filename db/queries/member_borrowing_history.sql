-- Borrowing history for one card number, newest checkout first.
-- Returned loans stay in the history. loan_state separates returned, overdue, and still-open loans.
-- The comparison date is fixed so this file returns the same rows whenever it is run.
-- The view member_borrowing_history answers the operational question with now() and a window rank.

SELECT
    l.loan_id,
    b.title,
    c.barcode,
    l.checked_out_at,
    l.due_at,
    l.returned_at,
    CASE
        WHEN l.returned_at IS NOT NULL THEN 'returned'
        WHEN l.due_at < timestamptz '2026-10-10 00:00:00+00' THEN 'overdue'
        ELSE 'open'
    END AS loan_state
FROM loans AS l
JOIN book_copies AS c ON c.copy_id = l.copy_id
JOIN books AS b ON b.book_id = c.book_id
JOIN members AS m ON m.member_id = l.member_id
WHERE m.member_number = 'M-10001'
ORDER BY l.checked_out_at DESC, l.loan_id DESC;
