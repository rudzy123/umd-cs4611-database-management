-- Open loans that were already due at a fixed reporting instant.
-- The view overdue_loans answers the same question with now().
-- overdue_loans_as_of(timestamptz) is the parameterized form of this report.
-- Loan 4 is due in 2020. Loans 6, 10, and 11 are open and due in 2099.

SELECT
    l.loan_id,
    m.member_number,
    b.title,
    c.barcode,
    l.checked_out_at,
    l.due_at
FROM loans AS l
JOIN members AS m ON m.member_id = l.member_id
JOIN book_copies AS c ON c.copy_id = l.copy_id
JOIN books AS b ON b.book_id = c.book_id
WHERE l.returned_at IS NULL
  AND l.due_at < timestamptz '2026-10-10 00:00:00+00'
ORDER BY l.due_at, l.loan_id;
