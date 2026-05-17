"""
Minimal MySQL dump parser for the indianliberals.in backup.

We have three mysqldump-style .sql files. We don't want to spin up MySQL just
to read 5 tables, so this module:

  1. Reads a dump file once
  2. Extracts CREATE TABLE column lists (so we know field positions)
  3. Streams INSERT INTO blocks, splits each tuple, returns column-named dicts

It handles MySQL-escaped strings, NULLs, and multi-row INSERT VALUES (... ),(... ).
It does NOT try to be a full MySQL parser — just enough for the data we need.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator


# --- Tuple splitter ---------------------------------------------------------


def split_tuples(values_blob: str) -> list[str]:
    """Split a VALUES blob into individual tuple bodies (without enclosing parens).

    Handles: nested parens inside strings, escaped quotes (\\'), backslash escapes.
    """
    rows: list[str] = []
    depth = 0
    in_str = False
    escape = False
    start = 0
    for i, c in enumerate(values_blob):
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == "'":
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "(":
            if depth == 0:
                start = i + 1
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                rows.append(values_blob[start:i])
    return rows


def split_fields(tuple_body: str) -> list[str]:
    """Split a tuple body into individual SQL-literal fields by top-level commas."""
    fields: list[str] = []
    cur: list[str] = []
    in_str = False
    escape = False
    for c in tuple_body:
        if escape:
            cur.append(c)
            escape = False
            continue
        if c == "\\":
            cur.append(c)
            escape = True
            continue
        if c == "'":
            in_str = not in_str
            cur.append(c)
            continue
        if c == "," and not in_str:
            fields.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
    if cur:
        fields.append("".join(cur).strip())
    return fields


# --- Value decoder ----------------------------------------------------------

_ESCAPE_MAP = {
    "\\n": "\n",
    "\\r": "\r",
    "\\t": "\t",
    "\\0": "\x00",
    "\\\\": "\\",
    "\\'": "'",
    '\\"': '"',
    "\\Z": "\x1a",
}


def decode_value(raw: str):
    """Decode a single SQL field into Python: NULL → None, 'str' → str, num → int/float."""
    raw = raw.strip()
    if raw == "NULL":
        return None
    if raw.startswith("'") and raw.endswith("'"):
        s = raw[1:-1]
        # Replace common MySQL escapes
        def _sub(m: re.Match) -> str:
            seq = m.group(0)
            return _ESCAPE_MAP.get(seq, seq[1:])

        return re.sub(r"\\.", _sub, s)
    # Numeric
    try:
        if "." in raw or "e" in raw or "E" in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


# --- Schema + dump iterators ------------------------------------------------


_CREATE_TABLE_RE = re.compile(
    r"CREATE TABLE `(?P<name>[^`]+)` \((?P<body>.*?)\) ENGINE",
    re.DOTALL,
)
# Only match column definitions: `name` followed by a type token.
# Excludes KEY / PRIMARY KEY / UNIQUE / CONSTRAINT lines (which contain backticks too).
_COLUMN_DEF_RE = re.compile(
    r"^\s*`(?P<col>[^`]+)`\s+(?:bigint|int|smallint|tinyint|mediumint|"
    r"varchar|char|text|tinytext|mediumtext|longtext|"
    r"date|datetime|timestamp|time|year|"
    r"float|double|decimal|"
    r"blob|tinyblob|mediumblob|longblob|"
    r"enum|set|json|bit|binary|varbinary)",
    re.MULTILINE | re.IGNORECASE,
)
_INSERT_RE = re.compile(
    r"^INSERT INTO `(?P<table>[^`]+)` (?:\([^)]*\) )?VALUES\s*(?P<values>.+?);\s*$",
    re.MULTILINE | re.DOTALL,
)


def schemas(dump_path: Path) -> dict[str, list[str]]:
    """Return {table_name: [column_names]} for every CREATE TABLE in the dump."""
    text = dump_path.read_text(encoding="utf-8", errors="replace")
    out: dict[str, list[str]] = {}
    for m in _CREATE_TABLE_RE.finditer(text):
        body = m.group("body")
        cols = []
        for cm in _COLUMN_DEF_RE.finditer(body):
            col = cm.group("col")
            if col not in cols:
                cols.append(col)
        out[m.group("name")] = cols
    return out


def iter_rows(dump_path: Path, table: str) -> Iterator[dict]:
    """Yield every row of the given table as a dict {col: decoded_value}."""
    cols = schemas(dump_path).get(table)
    if not cols:
        raise KeyError(f"Table {table!r} not found in {dump_path.name}")
    text = dump_path.read_text(encoding="utf-8", errors="replace")
    for m in _INSERT_RE.finditer(text):
        if m.group("table") != table:
            continue
        for tup in split_tuples(m.group("values")):
            fields = split_fields(tup)
            if len(fields) != len(cols):
                # Skip malformed tuples (defensive — shouldn't happen on a clean dump)
                continue
            yield {col: decode_value(f) for col, f in zip(cols, fields)}


if __name__ == "__main__":
    import sys

    dump = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        table = sys.argv[2]
        count = 0
        for row in iter_rows(dump, table):
            count += 1
            if count <= 3:
                print({k: (v[:60] + "..." if isinstance(v, str) and len(v) > 60 else v) for k, v in row.items()})
        print(f"--- {count} rows in {table}")
    else:
        sch = schemas(dump)
        for t, cols in sch.items():
            print(f"{t}: {len(cols)} cols  ({', '.join(cols[:6])}{'...' if len(cols) > 6 else ''})")
