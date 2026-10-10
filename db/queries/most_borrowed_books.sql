-- Titles ranked by how many loans their copies have had, including loans that were returned.
-- RANK assigns the same number to a tie and then skips. Two titles tied at rank 2 make the next rank 4.
-- DENSE_RANK assigns the same number to a tie and continues at the next integer.
-- Titles with zero loans are absent because this query inner-joins loans.

SELECT
    b.book_id,
    b.title,
    count(l.loan_id) AS times_borrowed,
    rank() OVER (ORDER BY count(l.loan_id) DESC) AS borrow_rank,
    dense_rank() OVER (ORDER BY count(l.loan_id) DESC) AS borrow_dense_rank
FROM books AS b
JOIN book_copies AS c ON c.book_id = b.book_id
JOIN loans AS l ON l.copy_id = c.copy_id
GROUP BY b.book_id, b.title
ORDER BY borrow_rank, b.book_id;
