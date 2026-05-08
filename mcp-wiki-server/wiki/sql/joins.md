# SQL Joins

Joins combine rows from two or more tables based on a related column.

## INNER JOIN
Returns rows that have matching values in both tables.

```sql
SELECT u.name, o.total
FROM users u
INNER JOIN orders o ON o.user_id = u.id;
```

## LEFT JOIN
Returns all rows from the left table; NULLs for missing matches on the right.

```sql
SELECT u.name, o.total
FROM users u
LEFT JOIN orders o ON o.user_id = u.id;
```

## FULL OUTER JOIN
Returns rows when there is a match in either table; NULLs where no match exists.
Not supported in MySQL — emulate with `LEFT JOIN ... UNION ... RIGHT JOIN`.

## Tip
Always join on indexed columns. Mismatched types (e.g. INT vs VARCHAR) silently
disable index usage and lead to full scans.
