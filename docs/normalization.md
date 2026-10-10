# Normalization

Normalization is a way to decide which facts share a row. The goal in this laboratory is that each fact has one home, that foreign keys can point at it, and that an update changes one place. The schema is in Boyce-Codd normal form. The argument below uses this library, including the designs that were rejected.

## A design that fails early

Imagine one table that tries to be the whole catalog:

```text
books_flat(
  isbn,
  title,
  author_names,          -- 'Chen, Mira; Adeyemi, Jonah'
  category_names,        -- 'Databases, Computer Science'
  copy_barcodes,         -- 'CPY-000101, CPY-000102, CPY-000103'
  borrower_emails        -- 'avery.nguyen@example.edu'
)
```

`author_names` is a list stuffed into a scalar. The table does not know how many authors a title has, cannot point a foreign key at one author, and cannot keep byline order as its own value. Searching for Adeyemi requires a text search inside the cell. That design is already out of first normal form, and it is the design this repository refuses.

PostgreSQL arrays (`text[]`) are a real type, and they are still the wrong tool for authors here. An array element cannot be a foreign key to `authors` with the same declaration a column can, and "position 1 is unique" becomes a custom check instead of `UNIQUE (book_id, author_order)`. The junction table `book_authors` is the relational model of the byline.

## 1NF

A relation is in first normal form when every attribute value is atomic for the operations you need, and the relation has a key.

In this schema:

- `given_name` and `family_name` are separate attributes because the desk sorts and searches them separately.
- `author_order` is a number, not a position implied by a comma.
- `book_categories` has one category per row.
- `copy_status` is one code, not a sentence.

A value can be atomic and still be the wrong grain. `isbn13` is one value. It identifies an edition, not a copy. Putting barcodes on the book row would mix two grains even if each barcode were stored in its own column (`barcode_1`, `barcode_2`, ...). Repeating groups of columns are a 1NF problem as well. `book_copies` is the relation that holds barcodes, one per row.

## 2NF

Second normal form applies to relations whose key is composite. Every non-key attribute must depend on the whole key, not on a proper subset of it.

`book_authors` has candidate keys `(book_id, author_id)` and `(book_id, author_order)`. The only non-key attribute, if we take the first key, is `author_order`. It depends on both the book and the author. It does not depend on `book_id` alone: one book has several positions. It does not depend on `author_id` alone: one author is first on one book and second on another.

A violation would be storing `books.title` on `book_authors`. The title depends on `book_id` only, which is part of the key. The title would be repeated once per author, and renaming the book would mean finding every byline row. `title` stays on `books`.

`book_categories` has no non-key attributes. A relation that is "all key" is in second normal form. It is also why the junction table is allowed to be boring.

## 3NF

Third normal form: every non-key attribute depends on the key, the whole key, and nothing but the key. Equivalently, there is no transitive dependency in which a non-key attribute determines another non-key attribute.

`members` stores `email` and `member_number`. Both depend on `member_id`. Neither determines the other inside this design: the unique constraints say each is a candidate key of its own, so a dependency from `email` to `member_number` is a dependency on a key. That is allowed. What 3NF forbids is copying the email onto `loans` "so the history report does not have to join." On `loans`, `member_email` would depend on `member_id`, and `member_id` is not a key of `loans` (a member has many loans). The email would be repeated, and a corrected address would have to be edited on every past loan. The history query joins `members`.

The same argument keeps `books.title` off `loans` and `authors.family_name` off `book_authors`.

## BCNF

Boyce-Codd normal form strengthens 3NF. For every non-trivial functional dependency `X -> A`, `X` is a superkey. 3NF still allows a dependency in which `A` is part of a candidate key and `X` is not a superkey. BCNF does not.

Check `book_authors` again. The dependencies are:

- `(book_id, author_id) -> author_order`
- `(book_id, author_order) -> author_id`

Both left-hand sides are candidate keys. There is no determinant that is not a superkey. The relation is in BCNF. This is the interesting case in the schema, because it has two overlapping candidate keys and still passes.

`loans` is in BCNF under the dependencies we actually enforce. `loan_id` determines every column. `(copy_id)` determines the member only among rows with `returned_at` null, and that is a conditional rule rather than a functional dependency of the whole relation. The partial unique index enforces the conditional rule. Returned loans for the same copy have had different members, so `copy_id` alone does not determine `member_id` in the relation as a whole.

## The copy-status question

It is tempting to call `book_copies.copy_status` a denormalized copy of "is there an open loan?" That would be true if the only statuses were `available` and `on_loan`. They are not.

| Status | Open loans | Extra fact |
| --- | --- | --- |
| `available` | 0 | The desk may lend it |
| `on_loan` | 1 | A member has it |
| `held` | 0 | A ready reservation is keeping it |
| `maintenance` | 0 | It is off the shelf for repair |
| `lost` | 0 | It is missing |

`copy_status` is not a function of `loans` alone, because four statuses share the same loan count. It is a real attribute of the copy. The deferred trigger adds a constraint across the two tables: `on_loan` lines up with exactly one open loan, and every other status lines up with zero. That constraint is what lets checkout update both rows in one transaction and still fail the commit if a later statement leaves them inconsistent.

Storing the status is a physical and operational choice. The lock in `checkout_copy` is taken on the copy row, and the status is the column that lock protects. Recomputing availability from `loans` on every read would also be correct. It would move the race onto the loan insert, which the partial unique index already guards. This laboratory does both: the status is locked and updated, and the index plus the trigger reject a commit that disagrees.

## Update anomalies the junction tables remove

- **Insertion.** A new category, Cartography, exists before any book uses it. In the flat design, a category with no book has nowhere to live.
- **Deletion.** Removing *Forthcoming Catalog* removes its byline and its category link because those foreign keys cascade. It does not delete Mira Chen, who still writes other books. A flat row that stored her name only on that book would lose the author.
- **Update.** Changing the Databases description changes `categories.description` once. Books 1, 2, 3, 6, and 10 all join to that row.

## Where this schema stops

BCNF is about functional dependencies. Join dependencies and multivalued dependencies are the next chapter (4NF and 5NF). `book_authors` and `book_categories` are independent many-to-many relationships. An author of a book is not paired with a subset of that book's categories, so we do not collapse those two junctions into one table of `(book, author, category)` triples. That triple would repeat every author once per category and would be a multivalued-dependency problem. Keeping the junctions separate is the 4NF-shaped decision, stated here so the two tables do not look like an accident.

The loan-limit rule and the copy/loan status rule are not functional dependencies of a single relation. They are constraints. Normal form does not replace them, and they do not mean the tables are denormalized.
