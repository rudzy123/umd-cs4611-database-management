-- Available and total copies for every title.
-- The left join keeps Forthcoming Catalog at zero copies.
-- FILTER counts available copies without dropping the other copies from total_copies.
-- The view available_copies_by_title is this report as a stored query.

SELECT
    b.book_id,
    b.title,
    count(c.copy_id) FILTER (WHERE c.copy_status = 'available') AS available_copies,
    count(c.copy_id) AS total_copies
FROM books AS b
LEFT JOIN book_copies AS c ON c.book_id = b.book_id
GROUP BY b.book_id, b.title
ORDER BY b.book_id;
