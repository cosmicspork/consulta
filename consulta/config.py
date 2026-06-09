"""Connection config, read entirely from ``.env``.

Resolution for every value: an exported process-environment variable wins over
the ``.env`` file. With ``--profile NAME`` (or ``DB_PROFILE``), a ``NAME_``-prefixed
key (e.g. ``QA_DB_HOST``) is consulted before the bare key (``DB_HOST``), so one
``.env`` can hold several environments.

Keys (all optional unless the backend needs them):

    DB_BACKEND     oracle | mssql | sqlite        (default: oracle)
    DB_HOST        hostname
    DB_PORT        port                            (default: backend's default)
    DB_SERVICE     Oracle service name             (alias: DB_DATABASE / DB_SCHEMA)
    DB_USER        username                        (alias: DB_USERNAME)
    DB_PASSWORD    password
    DB_FETCH_LIMIT default row cap for queries     (default: 1000)
    DATABASE_URL   full SQLAlchemy URL (overrides the discrete parts above)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine.url import make_url

from consulta.backends import BACKENDS, Backend, build_url

DEFAULT_FETCH_LIMIT = 1000


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    backend: Backend
    host: str | None
    port: int | None
    database: str | None
    user: str | None
    password: str | None
    database_url: str
    fetch_limit: int
    env_path: Path | None
    profile: str | None

    def redacted_url(self) -> str:
        try:
            return make_url(self.database_url).render_as_string(hide_password=True)
        except Exception:
            return self.database_url


def _discover_env(start: Path | None) -> Path | None:
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        cfg = candidate / ".env"
        if cfg.is_file():
            return cfg
    return None


def load_config(
    *,
    env_file: str | Path | None = None,
    profile: str | None = None,
    start: Path | None = None,
) -> Config:
    if env_file is not None:
        env_path: Path | None = Path(env_file).expanduser().resolve()
        if env_path is not None and not env_path.is_file():
            raise ConfigError(f".env file not found: {env_path}")
    else:
        env_path = _discover_env(start)

    file_values: dict[str, str | None] = dict(dotenv_values(env_path)) if env_path else {}
    profile = profile or os.environ.get("DB_PROFILE") or file_values.get("DB_PROFILE")

    def get(name: str) -> str | None:
        candidates = ([f"{profile.upper()}_{name}"] if profile else []) + [name]
        for key in candidates:
            value = os.environ.get(key) or file_values.get(key)
            if value:
                return value
        return None

    def get_first(*names: str) -> str | None:
        for name in names:
            value = get(name)
            if value:
                return value
        return None

    backend_name = (get("DB_BACKEND") or "oracle").lower()
    if backend_name not in BACKENDS:
        known = ", ".join(sorted(BACKENDS))
        raise ConfigError(f"unknown DB_BACKEND {backend_name!r}; known backends: {known}")
    backend = BACKENDS[backend_name]

    host = get("DB_HOST")
    database = get_first("DB_SERVICE", "DB_DATABASE", "DB_SCHEMA")
    user = get_first("DB_USER", "DB_USERNAME")
    password = get("DB_PASSWORD")
    port = _parse_port(get("DB_PORT"), backend)
    fetch_limit = _parse_int(get("DB_FETCH_LIMIT"), DEFAULT_FETCH_LIMIT, "DB_FETCH_LIMIT")

    override = get("DATABASE_URL")
    if override:
        database_url = override
    else:
        if backend_name not in {"sqlite"}:
            missing = [n for n, v in (("DB_HOST", host), ("DB_USER", user)) if not v]
            if missing:
                where = f" (profile {profile})" if profile else ""
                raise ConfigError(
                    f"missing required {', '.join(missing)} for backend {backend_name}{where}"
                )
        url = build_url(
            backend,
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
        )
        database_url = url.render_as_string(hide_password=False)

    return Config(
        backend=backend,
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        database_url=database_url,
        fetch_limit=fetch_limit,
        env_path=env_path,
        profile=profile,
    )


def _parse_port(raw: str | None, backend: Backend) -> int | None:
    if not raw:
        return backend.default_port or None
    try:
        return int(raw)
    except ValueError as e:
        raise ConfigError(f"DB_PORT must be an integer, got {raw!r}") from e


def _parse_int(raw: str | None, default: int, key: str) -> int:
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as e:
        raise ConfigError(f"{key} must be an integer, got {raw!r}") from e
