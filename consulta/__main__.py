"""consulta CLI — run a read-only SQL query and print or export the result.

Diagnostics go to stderr; query output goes to stdout, so it pipes cleanly:

    consulta --sql "SELECT 1 FROM dual"
    consulta --file query.sql --param term=1261 --format csv --output out.csv
    consulta --profile qa --check
    echo "SELECT * FROM adm_fraud_rules" | consulta --format markdown
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from consulta import __version__, db, guard, render
from consulta.config import ConfigError, load_config


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        cfg = load_config(env_file=args.env_file, profile=args.profile)
    except ConfigError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"consulta {__version__}", file=sys.stderr)
        print(f"  backend: {cfg.backend.name}", file=sys.stderr)
        print(f"  url:     {cfg.redacted_url()}", file=sys.stderr)
        if cfg.profile:
            print(f"  profile: {cfg.profile}", file=sys.stderr)
        if cfg.env_path:
            print(f"  env:     {cfg.env_path}", file=sys.stderr)
        print(file=sys.stderr)

    if args.check:
        try:
            db.check(cfg)
        except db.DbError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        print("OK: connection succeeded", file=sys.stderr)
        return 0

    sql: str | None
    params: dict[str, str]
    if args.describe:
        sql = cfg.backend.describe_query
        if sql is None:
            print(f"ERROR: --describe is not supported for the {cfg.backend.name} backend", file=sys.stderr)
            return 2
        params = {"t": args.describe}
    else:
        sql = _resolve_sql(args)
        if sql is None:
            print("ERROR: provide --sql, --file, --describe, or pipe SQL on stdin", file=sys.stderr)
            return 2
        params = _parse_params(args.param)

    try:
        guard.assert_read_only(sql)
    except guard.ReadOnlyViolation as e:
        print(f"ERROR: refused, read-only only: {e}", file=sys.stderr)
        return 2

    limit = args.limit if args.limit is not None else cfg.fetch_limit

    try:
        frame = db.run_query(cfg, sql, params, limit=limit)
    except db.DbError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    output = render.render(frame, args.format)
    if args.output:
        Path(args.output).expanduser().write_text(output + "\n")
        print(f"{frame.height} row(s) -> {args.output}", file=sys.stderr)
    else:
        print(output)

    if limit and limit > 0 and frame.height >= limit:
        print(f"(stopped at --limit {limit}; more rows may exist)", file=sys.stderr)
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="consulta", description="Read-only SQL query runner.")
    p.add_argument("--sql", help="SQL text to run (SELECT/WITH only).")
    p.add_argument("--file", type=Path, help="Path to a .sql file to run.")
    p.add_argument(
        "--describe",
        metavar="TABLE",
        help="List a table's columns via a read-only data-dictionary query.",
    )
    p.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Bind a :NAME placeholder. Repeatable.",
    )
    p.add_argument("--limit", type=int, help="Max rows (0 = no cap). Default: DB_FETCH_LIMIT.")
    p.add_argument(
        "--format",
        choices=sorted(render.FORMATS),
        default="table",
        help="Output format (default: table).",
    )
    p.add_argument("--output", help="Write output to this file instead of stdout.")
    p.add_argument("--profile", help="Connection profile prefix in .env (e.g. qa).")
    p.add_argument("--env-file", dest="env_file", help="Path to a specific .env file.")
    p.add_argument("--check", action="store_true", help="Test the connection and exit.")
    p.add_argument("--quiet", action="store_true", help="Suppress the diagnostic header.")
    return p.parse_args(argv)


def _resolve_sql(args: argparse.Namespace) -> str | None:
    if args.sql:
        return str(args.sql)
    if args.file:
        return Path(args.file).expanduser().read_text()
    if not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            return piped
    return None


def _parse_params(raw: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for item in raw:
        if "=" not in item:
            raise SystemExit(f"--param expects NAME=VALUE, got {item!r}")
        name, value = item.split("=", 1)
        params[name.strip()] = value
    return params


if __name__ == "__main__":
    sys.exit(main())
