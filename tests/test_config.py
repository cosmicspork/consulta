"""Config resolution from .env: backends, profiles, overrides, redaction."""

from __future__ import annotations

from pathlib import Path

import pytest

from consulta.config import ConfigError, load_config


def _write_env(tmp_path: Path, body: str) -> Path:
    env = tmp_path / ".env"
    env.write_text(body)
    return env


def test_oracle_url_assembled_from_parts(tmp_path: Path) -> None:
    env = _write_env(
        tmp_path,
        "DB_BACKEND=oracle\nDB_HOST=h.example.edu\nDB_PORT=2982\n"
        "DB_SERVICE=prduno.db\nDB_USER=app4adm\nDB_PASSWORD=s3cr3t\n",
    )
    cfg = load_config(env_file=env)
    assert cfg.backend.name == "oracle"
    assert cfg.host == "h.example.edu"
    assert cfg.port == 2982
    assert "service_name=prduno.db" in cfg.database_url
    assert "app4adm" in cfg.database_url


def test_redacted_url_hides_password(tmp_path: Path) -> None:
    env = _write_env(
        tmp_path,
        "DB_BACKEND=oracle\nDB_HOST=h\nDB_SERVICE=svc\nDB_USER=u\nDB_PASSWORD=s3cr3t\n",
    )
    cfg = load_config(env_file=env)
    assert "s3cr3t" not in cfg.redacted_url()
    assert "***" in cfg.redacted_url()


def test_profile_prefix_overrides_bare_key(tmp_path: Path) -> None:
    env = _write_env(
        tmp_path,
        "DB_BACKEND=oracle\nDB_HOST=prd.example.edu\nDB_SERVICE=prduno.db\n"
        "DB_USER=app4adm\nDB_PASSWORD=p\n"
        "QA_DB_HOST=qa.example.edu\nQA_DB_SERVICE=qauno.db\n",
    )
    cfg = load_config(env_file=env, profile="qa")
    assert cfg.host == "qa.example.edu"
    assert "service_name=qauno.db" in cfg.database_url
    assert cfg.user == "app4adm"  # falls back to the bare key
    assert cfg.profile == "qa"


def test_missing_required_keys_raise(tmp_path: Path) -> None:
    env = _write_env(tmp_path, "DB_BACKEND=oracle\nDB_PORT=2982\n")
    with pytest.raises(ConfigError, match="DB_HOST"):
        load_config(env_file=env)


def test_unknown_backend_raises(tmp_path: Path) -> None:
    env = _write_env(tmp_path, "DB_BACKEND=cassandra\n")
    with pytest.raises(ConfigError, match="unknown DB_BACKEND"):
        load_config(env_file=env)


def test_database_url_override_passthrough(tmp_path: Path) -> None:
    env = _write_env(tmp_path, "DB_BACKEND=sqlite\nDATABASE_URL=sqlite:///explicit.db\n")
    cfg = load_config(env_file=env)
    assert cfg.database_url == "sqlite:///explicit.db"


def test_process_env_overrides_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _write_env(
        tmp_path,
        "DB_BACKEND=oracle\nDB_HOST=file.example.edu\nDB_SERVICE=svc\nDB_USER=u\nDB_PASSWORD=p\n",
    )
    monkeypatch.setenv("DB_HOST", "env.example.edu")
    cfg = load_config(env_file=env)
    assert cfg.host == "env.example.edu"


def test_bad_port_raises(tmp_path: Path) -> None:
    env = _write_env(tmp_path, "DB_BACKEND=oracle\nDB_HOST=h\nDB_USER=u\nDB_PORT=abc\n")
    with pytest.raises(ConfigError, match="DB_PORT"):
        load_config(env_file=env)
