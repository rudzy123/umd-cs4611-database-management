-- Grouping, conditional aggregates, and HAVING.
-- FILTER counts a subset without a second pass over the table.
-- The left join keeps Farah Mensah, who has no loans, in the member summary.
-- HAVING runs after grouping, so it can test an aggregate. WHERE cannot.

SELECT
    m.member_id,
    m.member_number,
    count(l.loan_id) AS total_loans,
    count(l.loan_id) FILTER (WHERE l.returned_at IS NULL) AS open_loans,
    count(l.loan_id) FILTER (
        WHERE l.returned_at IS NULL
          AND l.due_at < timestamptz '2026-10-10 00:00:00+00'
    ) AS overdue_loans
FROM members AS m
LEFT JOIN loans AS l ON l.member_id = m.member_id
GROUP BY m.member_id, m.member_number
ORDER BY m.member_id;

SELECT c.name, count(DISTINCT bc.book_id) AS titles
FROM categories AS c
LEFT JOIN book_categories AS bc ON bc.category_id = c.category_id
GROUP BY c.category_id, c.name
HAVING count(DISTINCT bc.book_id) >= 2
ORDER BY c.name;
