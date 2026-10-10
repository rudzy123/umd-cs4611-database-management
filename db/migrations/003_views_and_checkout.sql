-- Migration 003: reporting views and the checkout / return API.
-- days_overdue uses epoch days. EXTRACT(DAY FROM interval) is only the days field
-- after PostgreSQL justifies an interval into months, so it is the wrong total.

CREATE VIEW overdue_loans AS
SELECT
    l.loan_id,
    l.member_id,
    m.member_number,
    m.given_name,
    m.family_name,
    b.book_id,
    b.title,
    c.copy_id,
    c.barcode,
    l.checked_out_at,
    l.due_at,
    floor(extract(epoch FROM (now() - l.due_at)) / 86400)::integer AS days_overdue
FROM loans AS l
JOIN members AS m ON m.member_id = l.member_id
JOIN book_copies AS c ON c.copy_id = l.copy_id
JOIN books AS b ON b.book_id = c.book_id
WHERE l.returned_at IS NULL
  AND l.due_at < now();

COMMENT ON VIEW overdue_loans IS
    'Open loans whose due timestamp is earlier than the transaction clock.';

CREATE VIEW available_copies_by_title AS
SELECT
    b.book_id,
    b.isbn13,
    b.title,
    count(c.copy_id) FILTER (WHERE c.copy_status = 'available') AS available_copies,
    count(c.copy_id) AS total_copies
FROM books AS b
LEFT JOIN book_copies AS c ON c.book_id = b.book_id
GROUP BY b.book_id, b.isbn13, b.title;

COMMENT ON VIEW available_copies_by_title IS
    'Every title, including titles that currently have zero copies or zero available copies.';

CREATE VIEW member_borrowing_history AS
SELECT
    m.member_id,
    m.member_number,
    m.given_name,
    m.family_name,
    l.loan_id,
    b.book_id,
    b.title,
    c.barcode,
    l.checked_out_at,
    l.due_at,
    l.returned_at,
    CASE
        WHEN l.returned_at IS NOT NULL THEN 'returned'
        WHEN l.due_at < now() THEN 'overdue'
        ELSE 'open'
    END AS loan_state,
    row_number() OVER (
        PARTITION BY m.member_id
        ORDER BY l.checked_out_at DESC, l.loan_id DESC
    ) AS history_rank
FROM members AS m
JOIN loans AS l ON l.member_id = m.member_id
JOIN book_copies AS c ON c.copy_id = l.copy_id
JOIN books AS b ON b.book_id = c.book_id;

COMMENT ON VIEW member_borrowing_history IS
    'One row per loan. history_rank 1 is the member''s most recent checkout. Members with no loans are absent.';

CREATE FUNCTION overdue_loans_as_of(p_as_of timestamptz)
RETURNS TABLE (
    loan_id bigint,
    member_id bigint,
    member_number text,
    title text,
    barcode text,
    checked_out_at timestamptz,
    due_at timestamptz,
    days_overdue integer
)
LANGUAGE sql
STABLE
SET search_path = pg_catalog, public
AS $$
    SELECT
        l.loan_id,
        l.member_id,
        m.member_number,
        b.title,
        c.barcode,
        l.checked_out_at,
        l.due_at,
        floor(extract(epoch FROM (p_as_of - l.due_at)) / 86400)::integer
    FROM loans AS l
    JOIN members AS m ON m.member_id = l.member_id
    JOIN book_copies AS c ON c.copy_id = l.copy_id
    JOIN books AS b ON b.book_id = c.book_id
    WHERE l.returned_at IS NULL
      AND l.due_at < p_as_of
    ORDER BY l.due_at, l.loan_id
$$;

COMMENT ON FUNCTION overdue_loans_as_of(timestamptz) IS
    'Overdue open loans as of a caller-supplied timestamp, so reports and tests do not depend on the wall clock.';

-- checkout_copy is the supported way to lend a copy.
-- Lock order is always the copy row, then the member row, so two checkouts cannot deadlock
-- by acquiring those two locks in opposite orders.
-- SELECT ... FOR UPDATE holds the row lock until this transaction ends.
-- The second session waits, then reads the committed status instead of the stale value "available".
-- The partial unique index and the deferred triggers remain in place for writes that skip this function.

CREATE FUNCTION checkout_copy(
    p_copy_id bigint,
    p_member_id bigint,
    p_loan_days integer DEFAULT 21
)
RETURNS bigint
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_status text;
    v_member_status text;
    v_loan_limit integer;
    v_open_loans bigint;
    v_loan_id bigint;
BEGIN
    IF p_loan_days IS NULL OR p_loan_days < 1 OR p_loan_days > 90 THEN
        RAISE EXCEPTION
            'loan period must be between 1 and 90 days (got %)',
            p_loan_days
            USING ERRCODE = 'P0001';
    END IF;

    SELECT copy_status
      INTO v_status
      FROM book_copies
     WHERE copy_id = p_copy_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'copy % does not exist', p_copy_id
            USING ERRCODE = 'P0002';
    END IF;

    IF v_status IS DISTINCT FROM 'available' THEN
        RAISE EXCEPTION
            'copy % cannot be checked out while its status is %',
            p_copy_id, v_status
            USING ERRCODE = 'P0001';
    END IF;

    SELECT membership_status, loan_limit
      INTO v_member_status, v_loan_limit
      FROM members
     WHERE member_id = p_member_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'member % does not exist', p_member_id
            USING ERRCODE = 'P0002';
    END IF;

    IF v_member_status IS DISTINCT FROM 'active' THEN
        RAISE EXCEPTION
            'member % cannot check out books while membership is %',
            p_member_id, v_member_status
            USING ERRCODE = 'P0001';
    END IF;

    SELECT count(*)
      INTO v_open_loans
      FROM loans
     WHERE member_id = p_member_id
       AND returned_at IS NULL;

    IF v_open_loans >= v_loan_limit THEN
        RAISE EXCEPTION
            'member % already has % open loan(s), which meets the limit of %',
            p_member_id, v_open_loans, v_loan_limit
            USING ERRCODE = 'P0001';
    END IF;

    INSERT INTO loans (copy_id, member_id, checked_out_at, due_at)
    VALUES (
        p_copy_id,
        p_member_id,
        now(),
        now() + make_interval(days => p_loan_days)
    )
    RETURNING loan_id INTO v_loan_id;

    UPDATE book_copies
       SET copy_status = 'on_loan'
     WHERE copy_id = p_copy_id;

    RETURN v_loan_id;
END;
$$;

COMMENT ON FUNCTION checkout_copy(bigint, bigint, integer) IS
    'Atomically lends an available copy to an active member who is under the loan limit.';

CREATE FUNCTION return_copy(
    p_copy_id bigint,
    p_returned_at timestamptz DEFAULT now()
)
RETURNS bigint
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_loan_id bigint;
    v_checked_out timestamptz;
BEGIN
    PERFORM copy_id
       FROM book_copies
      WHERE copy_id = p_copy_id
      FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'copy % does not exist', p_copy_id
            USING ERRCODE = 'P0002';
    END IF;

    SELECT loan_id, checked_out_at
      INTO v_loan_id, v_checked_out
      FROM loans
     WHERE copy_id = p_copy_id
       AND returned_at IS NULL
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'copy % has no open loan', p_copy_id
            USING ERRCODE = 'P0001';
    END IF;

    IF p_returned_at < v_checked_out THEN
        RAISE EXCEPTION
            'return time % is before checkout %',
            p_returned_at, v_checked_out
            USING ERRCODE = 'P0001';
    END IF;

    UPDATE loans
       SET returned_at = p_returned_at
     WHERE loan_id = v_loan_id;

    UPDATE book_copies
       SET copy_status = 'available'
     WHERE copy_id = p_copy_id
       AND copy_status = 'on_loan';

    RETURN v_loan_id;
END;
$$;

COMMENT ON FUNCTION return_copy(bigint, timestamptz) IS
    'Closes the open loan for a copy and marks that copy available when it was on loan.';
