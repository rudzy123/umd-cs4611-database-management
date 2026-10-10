-- Insert, update, and delete examples.
-- Run them inside a transaction you can roll back. pytest does that for you.
-- The category row is created, corrected, and removed.
-- The member email is changed and then restored in the same script.

INSERT INTO categories (name, description)
VALUES ('Ephemera', 'Short-lived printed matter');

UPDATE categories
SET description = 'Transient printed matter such as pamphlets and posters'
WHERE name = 'Ephemera';

DELETE FROM categories
WHERE name = 'Ephemera';

UPDATE members
SET email = 'avery.nguyen+hold@example.edu'
WHERE member_number = 'M-10001';

UPDATE members
SET email = 'avery.nguyen@example.edu'
WHERE member_number = 'M-10001';
