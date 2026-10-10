-- Inner, left, and full outer joins against the laboratory seed.
-- The left join keeps Forthcoming Catalog, which has no copies, because the filter is on books.
-- A filter on book_copies.barcode in the WHERE clause would discard that title and turn the left join into an inner join.
-- The full outer join keeps two unmatched sides: Cartography has no titles, and Unclassified Field Notes has no category.

SELECT b.title, a.given_name, a.family_name, ba.author_order
FROM books AS b
JOIN book_authors AS ba ON ba.book_id = b.book_id
JOIN authors AS a ON a.author_id = ba.author_id
WHERE b.book_id = 1
ORDER BY ba.author_order;

SELECT b.book_id, b.title, c.barcode
FROM books AS b
LEFT JOIN book_copies AS c ON c.book_id = b.book_id
WHERE b.book_id IN (8, 10)
ORDER BY b.book_id, c.barcode;

SELECT c.name AS category_name, b.title
FROM categories AS c
FULL OUTER JOIN book_categories AS bc ON bc.category_id = c.category_id
FULL OUTER JOIN books AS b ON b.book_id = bc.book_id
WHERE c.name IS NULL
   OR b.title IS NULL
   OR c.name = 'Cartography'
   OR b.book_id = 9
ORDER BY c.name NULLS FIRST, b.title NULLS FIRST;
