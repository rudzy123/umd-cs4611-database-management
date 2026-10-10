-- A correlated NOT EXISTS test, then a comparison against an aggregate subquery.
-- NOT EXISTS is true when the inner query returns no row for this title.
-- The average includes members with zero loans because that subquery left-joins loans.

SELECT b.book_id, b.title
FROM books AS b
WHERE NOT EXISTS (
    SELECT 1
    FROM book_copies AS c
    WHERE c.book_id = b.book_id
      AND c.copy_status = 'available'
)
ORDER BY b.book_id;

SELECT m.member_number
FROM members AS m
WHERE (
    SELECT count(*)
    FROM loans AS l
    WHERE l.member_id = m.member_id
) > (
    SELECT avg(loan_count)
    FROM (
        SELECT count(l2.loan_id)::numeric AS loan_count
        FROM members AS m2
        LEFT JOIN loans AS l2 ON l2.member_id = m2.member_id
        GROUP BY m2.member_id
    ) AS per_member
)
ORDER BY m.member_number;
