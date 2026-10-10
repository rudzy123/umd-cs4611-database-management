-- Migration 001: library-lending schema.
-- Up only. Rebuild with `make reset`, which drops the data volume and reapplies every file.
-- Deferred cross-table checks run at COMMIT, so this file and the seed must each run
-- as one transaction. `python -m library.migrate` does that.

CREATE FUNCTION is_valid_isbn13(candidate text)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
SET search_path = pg_catalog, public
RETURN CASE
    WHEN candidate ~ '^[0-9]{13}$' THEN (
        (
            (substr(candidate, 1, 1)::integer * 1)
            + (substr(candidate, 2, 1)::integer * 3)
            + (substr(candidate, 3, 1)::integer * 1)
            + (substr(candidate, 4, 1)::integer * 3)
            + (substr(candidate, 5, 1)::integer * 1)
            + (substr(candidate, 6, 1)::integer * 3)
            + (substr(candidate, 7, 1)::integer * 1)
            + (substr(candidate, 8, 1)::integer * 3)
            + (substr(candidate, 9, 1)::integer * 1)
            + (substr(candidate, 10, 1)::integer * 3)
            + (substr(candidate, 11, 1)::integer * 1)
            + (substr(candidate, 12, 1)::integer * 3)
            + (substr(candidate, 13, 1)::integer * 1)
        ) % 10
    ) = 0
    ELSE false
END;

COMMENT ON FUNCTION is_valid_isbn13(text) IS
    'True when the text is 13 digits and the ISBN-13 check digit matches.';

CREATE TABLE authors (
    author_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    given_name text NOT NULL,
    family_name text NOT NULL,
    birth_year integer,
    CONSTRAINT authors_name_chk CHECK (
        length(btrim(given_name)) > 0
        AND length(btrim(family_name)) > 0
    ),
    CONSTRAINT authors_birth_year_chk CHECK (
        birth_year IS NULL OR birth_year BETWEEN 1 AND 2100
    )
);

COMMENT ON TABLE authors IS
    'People who write cataloged works. Names are not unique, so author_id is the identifier.';

CREATE TABLE books (
    book_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    isbn13 text NOT NULL,
    title text NOT NULL,
    publication_year integer,
    publisher text,
    page_count integer,
    CONSTRAINT books_isbn13_uniq UNIQUE (isbn13),
    CONSTRAINT books_isbn13_chk CHECK (is_valid_isbn13(isbn13)),
    CONSTRAINT books_title_chk CHECK (length(btrim(title)) > 0),
    CONSTRAINT books_year_chk CHECK (
        publication_year IS NULL OR publication_year BETWEEN 1450 AND 2100
    ),
    CONSTRAINT books_pages_chk CHECK (page_count IS NULL OR page_count > 0)
);

COMMENT ON TABLE books IS
    'Bibliographic titles. A book is the work, not a physical object on the shelf.';
COMMENT ON COLUMN books.isbn13 IS
    'Stable natural key for the edition. Stored as text so leading structure is preserved.';

CREATE TABLE book_authors (
    book_id bigint NOT NULL,
    author_id bigint NOT NULL,
    author_order smallint NOT NULL,
    CONSTRAINT book_authors_pkey PRIMARY KEY (book_id, author_id),
    CONSTRAINT book_authors_order_uniq UNIQUE (book_id, author_order),
    CONSTRAINT book_authors_order_chk CHECK (author_order >= 1),
    CONSTRAINT book_authors_book_id_fkey
        FOREIGN KEY (book_id) REFERENCES books (book_id) ON DELETE CASCADE,
    CONSTRAINT book_authors_author_id_fkey
        FOREIGN KEY (author_id) REFERENCES authors (author_id) ON DELETE RESTRICT
);

COMMENT ON TABLE book_authors IS
    'Many-to-many authorship. author_order is the byline position for one title.';

CREATE TABLE categories (
    category_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL,
    description text,
    CONSTRAINT categories_name_uniq UNIQUE (name),
    CONSTRAINT categories_name_chk CHECK (length(btrim(name)) > 0)
);

COMMENT ON TABLE categories IS
    'Controlled subject headings. A title may have several, and a heading may cover many titles.';

CREATE TABLE book_categories (
    book_id bigint NOT NULL,
    category_id bigint NOT NULL,
    CONSTRAINT book_categories_pkey PRIMARY KEY (book_id, category_id),
    CONSTRAINT book_categories_book_id_fkey
        FOREIGN KEY (book_id) REFERENCES books (book_id) ON DELETE CASCADE,
    CONSTRAINT book_categories_category_id_fkey
        FOREIGN KEY (category_id) REFERENCES categories (category_id) ON DELETE RESTRICT
);

COMMENT ON TABLE book_categories IS
    'Many-to-many classification. Subjects are rows here, never a comma-separated list on books.';

CREATE TABLE members (
    member_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    member_number text NOT NULL,
    given_name text NOT NULL,
    family_name text NOT NULL,
    email text NOT NULL,
    joined_on date NOT NULL DEFAULT CURRENT_DATE,
    membership_status text NOT NULL DEFAULT 'active',
    loan_limit integer NOT NULL DEFAULT 5,
    CONSTRAINT members_number_uniq UNIQUE (member_number),
    CONSTRAINT members_email_uniq UNIQUE (email),
    CONSTRAINT members_number_chk CHECK (member_number ~ '^M-[0-9]{5}$'),
    CONSTRAINT members_email_chk CHECK (email ~* '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'),
    CONSTRAINT members_name_chk CHECK (
        length(btrim(given_name)) > 0
        AND length(btrim(family_name)) > 0
    ),
    CONSTRAINT members_status_chk CHECK (
        membership_status IN ('active', 'suspended', 'expired')
    ),
    CONSTRAINT members_loan_limit_chk CHECK (loan_limit BETWEEN 1 AND 50)
);

COMMENT ON TABLE members IS
    'Borrowers. member_number is the card number printed on the library card.';
COMMENT ON COLUMN members.loan_limit IS
    'Maximum number of copies this member may have checked out at once.';

CREATE TABLE book_copies (
    copy_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    book_id bigint NOT NULL,
    barcode text NOT NULL,
    copy_status text NOT NULL DEFAULT 'available',
    condition text NOT NULL DEFAULT 'good',
    acquired_on date NOT NULL DEFAULT CURRENT_DATE,
    CONSTRAINT book_copies_barcode_uniq UNIQUE (barcode),
    CONSTRAINT book_copies_barcode_chk CHECK (barcode ~ '^CPY-[0-9]{6}$'),
    CONSTRAINT book_copies_status_chk CHECK (
        copy_status IN ('available', 'on_loan', 'held', 'maintenance', 'lost')
    ),
    CONSTRAINT book_copies_condition_chk CHECK (
        condition IN ('new', 'good', 'fair', 'poor')
    ),
    CONSTRAINT book_copies_book_id_fkey
        FOREIGN KEY (book_id) REFERENCES books (book_id) ON DELETE RESTRICT
);

COMMENT ON TABLE book_copies IS
    'Physical items. copy_status is maintained with loans by checkout_copy and the deferred trigger.';
COMMENT ON COLUMN book_copies.copy_status IS
    'available to lend, on_loan, held for a ready reservation, maintenance, or lost.';

CREATE TABLE loans (
    loan_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    copy_id bigint NOT NULL,
    member_id bigint NOT NULL,
    checked_out_at timestamptz NOT NULL DEFAULT now(),
    due_at timestamptz NOT NULL,
    returned_at timestamptz,
    CONSTRAINT loans_due_after_checkout_chk CHECK (due_at > checked_out_at),
    CONSTRAINT loans_return_after_checkout_chk CHECK (
        returned_at IS NULL OR returned_at >= checked_out_at
    ),
    CONSTRAINT loans_copy_id_fkey
        FOREIGN KEY (copy_id) REFERENCES book_copies (copy_id) ON DELETE RESTRICT,
    CONSTRAINT loans_member_id_fkey
        FOREIGN KEY (member_id) REFERENCES members (member_id) ON DELETE RESTRICT
);

COMMENT ON TABLE loans IS
    'One borrowing of one copy by one member. A NULL returned_at means the loan is still open.';

-- Integrity index, not a performance add-on: a copy has at most one open loan.
CREATE UNIQUE INDEX loans_one_open_copy_idx
    ON loans (copy_id)
    WHERE returned_at IS NULL;

COMMENT ON INDEX loans_one_open_copy_idx IS
    'Rejects a second open loan for the same copy. Returned loans stay in the table and out of this index.';

CREATE TABLE reservations (
    reservation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    book_id bigint NOT NULL,
    member_id bigint NOT NULL,
    reserved_at timestamptz NOT NULL DEFAULT now(),
    reservation_status text NOT NULL DEFAULT 'waiting',
    ready_copy_id bigint,
    expires_at timestamptz,
    fulfilled_at timestamptz,
    CONSTRAINT reservations_status_chk CHECK (
        reservation_status IN ('waiting', 'ready', 'fulfilled', 'cancelled', 'expired')
    ),
    CONSTRAINT reservations_ready_copy_chk CHECK (
        reservation_status <> 'ready' OR ready_copy_id IS NOT NULL
    ),
    CONSTRAINT reservations_fulfilled_at_chk CHECK (
        (reservation_status = 'fulfilled') = (fulfilled_at IS NOT NULL)
    ),
    CONSTRAINT reservations_book_id_fkey
        FOREIGN KEY (book_id) REFERENCES books (book_id) ON DELETE CASCADE,
    CONSTRAINT reservations_member_id_fkey
        FOREIGN KEY (member_id) REFERENCES members (member_id) ON DELETE CASCADE,
    CONSTRAINT reservations_ready_copy_id_fkey
        FOREIGN KEY (ready_copy_id) REFERENCES book_copies (copy_id) ON DELETE RESTRICT
);

COMMENT ON TABLE reservations IS
    'A member waiting for a title. The hold is on the work. ready_copy_id is set only when a copy is held.';

-- A member may have only one waiting or ready reservation for a given title.
CREATE UNIQUE INDEX reservations_one_active_member_book_idx
    ON reservations (member_id, book_id)
    WHERE reservation_status IN ('waiting', 'ready');

COMMENT ON INDEX reservations_one_active_member_book_idx IS
    'One active reservation per member per title. Cancelled and fulfilled rows are allowed to repeat.';

-- Cross-table invariants. Checked at commit so a transaction can insert the loan and
-- update the copy before either side is required to look consistent.

CREATE FUNCTION assert_one_copy_loan_invariant(p_copy_id bigint)
RETURNS void
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
DECLARE
    copy_state text;
    open_loans bigint;
BEGIN
    SELECT copy_status
      INTO copy_state
      FROM book_copies
     WHERE copy_id = p_copy_id;

    IF NOT FOUND THEN
        SELECT count(*)
          INTO open_loans
          FROM loans
         WHERE copy_id = p_copy_id
           AND returned_at IS NULL;
        IF open_loans <> 0 THEN
            RAISE EXCEPTION
                'copy % is missing but still has % open loan(s)',
                p_copy_id, open_loans
                USING ERRCODE = '23514';
        END IF;
        RETURN;
    END IF;

    SELECT count(*)
      INTO open_loans
      FROM loans
     WHERE copy_id = p_copy_id
       AND returned_at IS NULL;

    IF copy_state = 'on_loan' AND open_loans <> 1 THEN
        RAISE EXCEPTION
            'copy % is on_loan but has % open loan(s)',
            p_copy_id, open_loans
            USING ERRCODE = '23514';
    ELSIF copy_state <> 'on_loan' AND open_loans <> 0 THEN
        RAISE EXCEPTION
            'copy % has status % but has % open loan(s)',
            p_copy_id, copy_state, open_loans
            USING ERRCODE = '23514';
    END IF;
END;
$$;

CREATE FUNCTION assert_member_loan_limit(p_member_id bigint)
RETURNS void
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
DECLARE
    allowed integer;
    open_loans bigint;
BEGIN
    SELECT loan_limit
      INTO allowed
      FROM members
     WHERE member_id = p_member_id;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    SELECT count(*)
      INTO open_loans
      FROM loans
     WHERE member_id = p_member_id
       AND returned_at IS NULL;

    IF open_loans > allowed THEN
        RAISE EXCEPTION
            'member % exceeds the loan limit of % with % open loan(s)',
            p_member_id, allowed, open_loans
            USING ERRCODE = '23514';
    END IF;
END;
$$;

CREATE FUNCTION loans_enforce_invariants()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM assert_one_copy_loan_invariant(OLD.copy_id);
        PERFORM assert_member_loan_limit(OLD.member_id);
        RETURN NULL;
    END IF;

    PERFORM assert_one_copy_loan_invariant(NEW.copy_id);
    PERFORM assert_member_loan_limit(NEW.member_id);

    IF TG_OP = 'UPDATE' AND OLD.copy_id IS DISTINCT FROM NEW.copy_id THEN
        PERFORM assert_one_copy_loan_invariant(OLD.copy_id);
    END IF;

    IF TG_OP = 'UPDATE' AND OLD.member_id IS DISTINCT FROM NEW.member_id THEN
        PERFORM assert_member_loan_limit(OLD.member_id);
    END IF;

    RETURN NULL;
END;
$$;

CREATE FUNCTION book_copies_enforce_invariant()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
    PERFORM assert_one_copy_loan_invariant(NEW.copy_id);
    RETURN NULL;
END;
$$;

CREATE FUNCTION members_enforce_loan_limit()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
    PERFORM assert_member_loan_limit(NEW.member_id);
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER loans_invariants
AFTER INSERT OR UPDATE OR DELETE ON loans
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION loans_enforce_invariants();

CREATE CONSTRAINT TRIGGER book_copies_loan_invariant
AFTER INSERT OR UPDATE OF copy_status ON book_copies
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION book_copies_enforce_invariant();

CREATE CONSTRAINT TRIGGER members_loan_limit_invariant
AFTER UPDATE OF loan_limit ON members
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION members_enforce_loan_limit();
