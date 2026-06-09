"""Read-only SQL guard — consulta's primary safety control.

A statement passes only if it is a single ``SELECT`` (or ``WITH ... SELECT``)
with no write/DDL/transaction keywords and no ``FOR UPDATE`` locking clause.
Two independent checks back each other up: a sqlparse token walk (which knows a
keyword from an identifier or a string literal) and a regex sweep over the
comment- and literal-stripped text. Anything ambiguous is refused — a false
refusal is harmless, a false accept against production is not.
"""

from __future__ import annotations

import re
from typing import Any

import sqlparse
from sqlparse import tokens as T

_ALLOWED_STARTS = {"SELECT", "WITH"}

_FORBIDDEN = frozenset(
    {
        "INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT", "REPLACE", "INTO",
        "CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME", "COMMENT",
        "GRANT", "REVOKE", "AUDIT", "NOAUDIT",
        "COMMIT", "ROLLBACK", "SAVEPOINT", "SET", "LOCK", "UNLOCK",
        "CALL", "EXEC", "EXECUTE", "BEGIN", "DECLARE",
        "FLASHBACK", "PURGE", "ANALYZE", "VACUUM",
    }
)

_STRING_LITERAL = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"")
_FOR_UPDATE = re.compile(r"\bFOR\s+UPDATE\b", re.IGNORECASE)


class ReadOnlyViolation(Exception):
    pass


def assert_read_only(sql: str) -> str:
    """Return ``sql`` unchanged if it is a read-only query, else raise."""
    parsed: list[Any] = list(sqlparse.parse(sql))
    statements = [s for s in parsed if s.token_first(skip_cm=True) is not None]
    if not statements:
        raise ReadOnlyViolation("no SQL statement found")
    if len(statements) > 1:
        raise ReadOnlyViolation("only a single statement is allowed (found multiple)")

    statement = statements[0]
    first = statement.token_first(skip_cm=True)
    leading = first.value.upper() if first is not None else ""
    if leading not in _ALLOWED_STARTS:
        raise ReadOnlyViolation(f"only SELECT/WITH queries are allowed (got {leading or 'nothing'})")

    keyword_types = (T.Keyword, T.Keyword.DDL, T.Keyword.DML, T.Keyword.CTE)
    for token in statement.flatten():
        if token.ttype in keyword_types and token.value.upper() in _FORBIDDEN:
            raise ReadOnlyViolation(f"forbidden keyword for a read-only query: {token.value.upper()}")

    stripped = _STRING_LITERAL.sub("", sqlparse.format(sql, strip_comments=True))
    for word in re.findall(r"[A-Za-z_]+", stripped):
        if word.upper() in _FORBIDDEN:
            raise ReadOnlyViolation(f"forbidden keyword for a read-only query: {word.upper()}")
    if _FOR_UPDATE.search(stripped):
        raise ReadOnlyViolation("SELECT ... FOR UPDATE takes row locks; not allowed")

    return sql
