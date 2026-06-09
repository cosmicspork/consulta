# consulta

A small, read-only SQL query runner built to be a safe database interface for
agents and other automated callers. Connection details come from `.env`; the
backend is whatever SQLAlchemy can reach (Oracle today, MSSQL/Postgres/MySQL
wired but unverified). Every query is checked to be a single `SELECT`/`WITH`
before it runs and executes inside a never-committed read-only transaction — so
an untrusted caller can be pointed at production and still cannot write, lock, or
run more than one statement.

## Why it's safe to hand to an agent

The design assumes the caller can't be trusted to restrain itself:

- **Read-only by construction.** Anything that isn't a lone `SELECT`/`WITH` is
  refused before a connection even opens, and the query then runs inside a
  read-only transaction that is never committed (see
  [Read-only guarantee](#read-only-guarantee)).
- **Non-interactive.** No prompts, ever — credentials come from `.env` or the
  environment, so there is nothing for an agent to hang on.
- **Machine-readable I/O.** Results go to stdout, diagnostics to stderr, and the
  exit code is `0` on success / `2` on any refusal or error — easy to branch on.
- **Structured output.** `--format json` (or `csv`/`tsv`) hands back a clean,
  parseable result instead of a rendered table.

## Setup

```sh
cp .env.example .env      # then fill in host/port/service/user/password
uv run consulta --check   # verify the connection
```

`uv` provisions the interpreter and dependencies on first run. Oracle ships in
the base dependencies; other backends are extras (`uv sync --extra mssql`).

## Usage

```sh
consulta --sql "SELECT COUNT(*) FROM adm_applications"
consulta --file reports/held_queue.sql --param strm=1261
consulta --describe adm_applications
consulta --sql "SELECT * FROM adm_fraud_rules" --format markdown
consulta --sql "SELECT * FROM adm_applications" --limit 0 --format csv --output apps.csv
echo "SELECT 1 FROM dual" | consulta --quiet
consulta --profile qa --check
```

- `--describe TABLE` lists a table's columns from the data dictionary. It emits
  an ordinary read-only `SELECT` (no `DESCRIBE` statement, which most backends
  treat as a client-only command), so the same guard and transaction apply.
- `--param NAME=VALUE` binds a `:NAME` placeholder (repeatable).
- `--limit N` caps rows (`0` = no cap); defaults to `DB_FETCH_LIMIT`.
- `--format` is one of `table` (default), `csv`, `tsv`, `json`, `markdown`.
- Diagnostics print to stderr, results to stdout — pipe-friendly.

## Configuration

All keys live in `.env` (see `.env.example`). With `--profile NAME`, a
`NAME_`-prefixed key (e.g. `QA_DB_HOST`) overrides the bare key, so one file can
hold several environments. Exported shell variables override the file.

## Read-only guarantee

`consulta.guard` refuses anything that isn't a lone `SELECT`/`WITH`: no DML/DDL,
no multiple statements, no `FOR UPDATE`, no transaction-control keywords. A
sqlparse token walk and a regex sweep over comment/literal-stripped text both
have to pass. It errs toward refusing — quote any column literally named after a
SQL keyword. A false refusal just costs the caller a retry; a false accept
against production would not be recoverable.

## Development

```sh
uv run pytest
uv run ruff check .
uv run mypy consulta
```
