"""Small DuckDB helpers for writing records without tabular dependencies."""

from __future__ import annotations

from typing import Any


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _columns(records: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    columns: list[str] = []
    for record in records:
        for key in record:
            if key not in seen:
                seen.add(key)
                columns.append(key)
    return columns


def _column_type(values: list[Any]) -> str:
    non_null = [value for value in values if value is not None]
    if not non_null:
        return "varchar"
    if all(isinstance(value, bool) for value in non_null):
        return "boolean"
    if all(isinstance(value, int) and not isinstance(value, bool) for value in non_null):
        return "bigint"
    if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in non_null):
        return "double"
    return "varchar"


def records_to_temp_table(con: Any, table_name: str, records: list[dict[str, Any]]) -> bool:
    """Create a temporary DuckDB table from records.

    Returns False when there are no rows to materialize.
    """

    if not records:
        return False
    columns = _columns(records)
    if not columns:
        return False

    quoted_table = _quote_ident(table_name)
    con.execute(f"drop table if exists {quoted_table}")
    column_defs = []
    for column in columns:
        values = [record.get(column) for record in records]
        column_defs.append(f"{_quote_ident(column)} {_column_type(values)}")
    con.execute(f"create temporary table {quoted_table} ({', '.join(column_defs)})")

    placeholders = ", ".join("?" for _ in columns)
    quoted_columns = ", ".join(_quote_ident(column) for column in columns)
    rows = [tuple(record.get(column) for column in columns) for record in records]
    con.executemany(
        f"insert into {quoted_table} ({quoted_columns}) values ({placeholders})",
        rows,
    )
    return True


def insert_records_by_name(con: Any, target: str, temp_name: str, records: list[dict[str, Any]]) -> None:
    if not records_to_temp_table(con, temp_name, records):
        return
    con.execute(f"insert into {_quote_ident(target)} by name select * from {_quote_ident(temp_name)}")
    con.execute(f"drop table if exists {_quote_ident(temp_name)}")


def replace_or_insert_records(con: Any, target: str, temp_name: str, records: list[dict[str, Any]]) -> None:
    if not records_to_temp_table(con, temp_name, records):
        return
    try:
        con.execute(f"insert into {_quote_ident(target)} by name select * from {_quote_ident(temp_name)}")
    except Exception:
        con.execute(f"drop table if exists {_quote_ident(target)}")
        con.execute(f"create table {_quote_ident(target)} as select * from {_quote_ident(temp_name)}")
    finally:
        con.execute(f"drop table if exists {_quote_ident(temp_name)}")


def create_table_from_records(con: Any, target: str, temp_name: str, records: list[dict[str, Any]]) -> None:
    if not records_to_temp_table(con, temp_name, records):
        return
    con.execute(f"create table {_quote_ident(target)} as select * from {_quote_ident(temp_name)}")
    con.execute(f"drop table if exists {_quote_ident(temp_name)}")
