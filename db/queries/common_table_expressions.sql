-- A non-recursive CTE names the open-loan count once, then a recursive CTE walks week by week.
-- The recursive term stops when the next reminder would fall after the due timestamp.
-- Loan 4 was checked out on 2020-05-01 and is due on 2020-05-22, so the walk yields four Fridays.

WITH open_loans AS (
    SELECT member_id, count(*) AS open_count
    FROM loans
    WHERE returned_at IS NULL
    GROUP BY member_id
)
SELECT
    members.member_number,
    coalesce(open_loans.open_count, 0) AS open_count,
    members.loan_limit,
    members.loan_limit - coalesce(open_loans.open_count, 0) AS remaining
FROM members
LEFT JOIN open_loans ON open_loans.member_id = members.member_id
ORDER BY members.member_number;

WITH RECURSIVE reminders AS (
    SELECT
        l.loan_id,
        l.checked_out_at AS reminder_at,
        l.due_at
    FROM loans AS l
    WHERE l.loan_id = 4
    UNION ALL
    SELECT
        reminders.loan_id,
        reminders.reminder_at + interval '7 days',
        reminders.due_at
    FROM reminders
    WHERE reminders.reminder_at + interval '7 days' <= reminders.due_at
)
SELECT loan_id, reminder_at
FROM reminders
ORDER BY reminder_at;
