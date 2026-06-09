"""Render a polars DataFrame to a terminal table or an export format."""

from __future__ import annotations

from collections.abc import Callable

import polars as pl


def to_table(df: pl.DataFrame) -> str:
    if df.width == 0:
        return "(no rows)"
    with pl.Config(
        tbl_rows=-1,
        tbl_cols=-1,
        fmt_str_lengths=200,
        tbl_hide_dataframe_shape=True,
        tbl_hide_column_data_types=True,
    ):
        return str(df)


def to_csv(df: pl.DataFrame) -> str:
    return df.write_csv().rstrip("\n")


def to_tsv(df: pl.DataFrame) -> str:
    return df.write_csv(separator="\t").rstrip("\n")


def to_json(df: pl.DataFrame) -> str:
    return df.write_json()


def to_markdown(df: pl.DataFrame) -> str:
    if df.width == 0:
        return "(no rows)"
    columns = df.columns
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, divider]
    for row in df.iter_rows():
        cells = ("" if value is None else str(value).replace("|", "\\|") for value in row)
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


FORMATS: dict[str, Callable[[pl.DataFrame], str]] = {
    "table": to_table,
    "csv": to_csv,
    "tsv": to_tsv,
    "json": to_json,
    "markdown": to_markdown,
    "md": to_markdown,
}


def render(df: pl.DataFrame, fmt: str) -> str:
    try:
        formatter = FORMATS[fmt]
    except KeyError:
        known = ", ".join(sorted(FORMATS))
        raise ValueError(f"unknown format {fmt!r}; choose one of: {known}") from None
    return formatter(df)
