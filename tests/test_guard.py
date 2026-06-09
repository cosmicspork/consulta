"""The read-only guard is the primary safety control — test it hard."""

from __future__ import annotations

import pytest

from consulta.guard import ReadOnlyViolation, assert_read_only

ALLOWED = [
    "SELECT 1 FROM dual",
    "select * from apps",
    "  -- a comment\nSELECT app_id FROM apps",
    "WITH c AS (SELECT 1 AS a) SELECT * FROM c",
    "SELECT updated_by, created_dt FROM apps",  # underscore keywords are fine
    "SELECT 'DROP TABLE x' AS note FROM apps",  # keyword inside a string literal
    "SELECT count(*) FROM apps OFFSET 5 ROWS",  # OFFSET is not SET
]

REJECTED = [
    "DELETE FROM apps",
    "UPDATE apps SET score = 0",
    "INSERT INTO apps VALUES (1)",
    "DROP TABLE apps",
    "TRUNCATE TABLE apps",
    "CREATE TABLE x (a INTEGER)",
    "ALTER TABLE apps ADD c INTEGER",
    "GRANT SELECT ON apps TO bob",
    "MERGE INTO apps USING dual ON (1=1) WHEN MATCHED THEN UPDATE SET score = 1",
    "SELECT * FROM apps INTO new_apps",
    "SELECT * FROM apps FOR UPDATE",
    "SELECT 1; DROP TABLE apps",
    "WITH c AS (SELECT 1) DELETE FROM apps",
    "BEGIN dbms_output.put_line('x'); END;",
    "EXEC some_proc",
    "COMMIT",
    "",
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_allows_read_only(sql: str) -> None:
    assert assert_read_only(sql) == sql


@pytest.mark.parametrize("sql", REJECTED)
def test_rejects_writes(sql: str) -> None:
    with pytest.raises(ReadOnlyViolation):
        assert_read_only(sql)
