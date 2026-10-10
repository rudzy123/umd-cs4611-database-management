-- ROW_NUMBER and COUNT as window functions.
-- The window count repeats the member's total on every one of that member's loans.
-- Members with no loans do not appear. The aggregation query is the one that keeps them.
-- RANK versus DENSE_RANK for the most-borrowed list lives in most_borrowed_books.sql.

SELECT
    l.loan_id,
    l.member_id,
    l.checked_out_at,
    row_number() OVER (
        PARTITION BY l.member_id
        ORDER BY l.checked_out_at, l.loan_id
    ) AS member_loan_seq,
    count(*) OVER (PARTITION BY l.member_id) AS member_loan_total
FROM loans AS l
ORDER BY l.member_id, member_loan_seq;
