"""Backend registry.

A backend maps a friendly name (``oracle``, ``mssql``, ``sqlite``) to the
SQLAlchemy driver string and the few backend-specific details consulta needs:
how the service/database name is passed in the URL, the statement that opens a
read-only transaction (defense in depth on top of the SQL guard), and a trivial
connectivity-check query.

Only ``oracle`` (and ``sqlite``, for tests) is exercised today. ``mssql`` and
friends are present so adding a backend is a registry entry plus the matching
driver extra in pyproject — no other code changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.engine.url import URL


@dataclass(frozen=True)
class Backend:
    name: str
    driver: str
    default_port: int
    #: URL query key that carries the service name (Oracle). When None, the
    #: database name goes in the URL path instead (MSSQL, Postgres, MySQL).
    service_query_key: str | None
    #: Statement that starts a read-only transaction, or None if unsupported.
    read_only_stmt: str | None
    #: Cheapest "am I connected" query for this dialect.
    select_one: str
    #: Parameterized SELECT (binds ``:t``) over the data dictionary that lists a
    #: table's columns, backing ``--describe``. None if the backend has no such
    #: read-only query. ``DESCRIBE``/``DESC`` itself is a client command on most
    #: backends (e.g. SQL*Plus), not a server statement, so consulta emits this.
    describe_query: str | None = None
    #: Extra URL query params (e.g. ODBC driver name for MSSQL).
    extra_query: dict[str, str] = field(default_factory=dict)


ORACLE = Backend(
    name="oracle",
    driver="oracle+oracledb",
    default_port=1521,
    service_query_key="service_name",
    read_only_stmt="SET TRANSACTION READ ONLY",
    select_one="SELECT 1 FROM DUAL",
    describe_query=(
        "SELECT column_name, data_type, data_length, data_precision, "
        "data_scale, nullable, column_id "
        "FROM all_tab_columns WHERE table_name = UPPER(:t) ORDER BY column_id"
    ),
)

# Door left open — wiring is here, but consulta has not been run against MSSQL.
# Connecting also needs the ODBC driver extra_query, which varies by host.
MSSQL = Backend(
    name="mssql",
    driver="mssql+pyodbc",
    default_port=1433,
    service_query_key=None,
    read_only_stmt="SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED",
    select_one="SELECT 1",
    describe_query=(
        "SELECT column_name, data_type, character_maximum_length, "
        "numeric_precision, numeric_scale, is_nullable, ordinal_position "
        "FROM information_schema.columns WHERE table_name = :t "
        "ORDER BY ordinal_position"
    ),
)

SQLITE = Backend(
    name="sqlite",
    driver="sqlite",
    default_port=0,
    service_query_key=None,
    read_only_stmt=None,
    select_one="SELECT 1",
    describe_query='SELECT name, type, "notnull", dflt_value, pk FROM pragma_table_info(:t)',
)

BACKENDS: dict[str, Backend] = {b.name: b for b in (ORACLE, MSSQL, SQLITE)}


def build_url(
    backend: Backend,
    *,
    host: str | None,
    port: int | None,
    database: str | None,
    user: str | None,
    password: str | None,
) -> URL:
    """Assemble a SQLAlchemy URL from discrete parts for the given backend."""
    if backend.name == "sqlite":
        return URL.create(drivername="sqlite", database=database or ":memory:")

    query: dict[str, str] = dict(backend.extra_query)
    db_path: str | None = None
    if backend.service_query_key and database:
        query[backend.service_query_key] = database
    elif database:
        db_path = database

    return URL.create(
        drivername=backend.driver,
        username=user,
        password=password,
        host=host,
        port=port,
        database=db_path,
        query=query,
    )
