#!/usr/bin/env sh
cd "$(dirname "$0")"
uv run consulta "$@"
