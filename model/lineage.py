"""Lineage captured by the pipeline, as data.

ADR-0003 argues that lineage documented after the fact is lineage that is
already wrong. The mechanism in this module is the argument made concrete:
a loader cannot move a column without declaring where it came from, because
the declaration *is* the thing that generates the SQL.

That inversion is the whole idea. Documentation drifts from code because they
are two artefacts maintained by two acts of will. Here there is one artefact.
If someone adds a column to a regulatory output without a mapping, no SQL is
generated for it and the conformance linter fails the build.

What "sufficient lineage" means for a regulatory-facing field
-------------------------------------------------------------
Not "this column came from that column". A supervisor asking how a reported
figure was derived needs, at minimum:

* the full chain, source system through canonical model to reported line;
* the transformation applied at each hop, not merely that one occurred;
* the rule identifier, so the logic can be found and version-controlled;
* the as-of date, so the answer is reproducible months later.

All four are recorded here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import duckdb

DDL = """
create schema if not exists meta;

create table if not exists meta.lineage (
    rule_id           varchar not null,   -- stable id, greppable, version-controlled
    target_layer      varchar not null,   -- CANONICAL | REPORTING
    target_table      varchar not null,
    target_column     varchar not null,
    source_layer      varchar not null,   -- SOURCE | CANONICAL
    source_table      varchar not null,
    -- Empty string rather than NULL for "no single source column" (a constant,
    -- or a value derived from the row as a whole). DuckDB will not accept an
    -- expression in a primary key, and a nullable key column would silently
    -- allow duplicate lineage rows -- which is the one thing a lineage table
    -- must not do.
    source_column     varchar not null default '',
    transformation    varchar not null,   -- what happened, in words a steward can read
    regulatory_facing boolean not null,
    primary key (rule_id, target_table, target_column, source_table, source_column)
);

create table if not exists meta.load_log (
    rule_id     varchar not null,
    target      varchar not null,
    as_of_date  date,
    rows_loaded bigint,
    primary key (rule_id, target, as_of_date)
);
"""


@dataclass(frozen=True)
class ColumnMapping:
    """One column of a target, and where it came from.

    ``expression`` is SQL evaluated against the source relation. ``sources``
    names the source columns it reads — stated separately rather than parsed
    out of the SQL, because parsing SQL to guess lineage is how lineage tools
    end up confidently wrong about ``case`` statements and joins.
    """

    target_column: str
    expression: str
    sources: tuple[str, ...] = ()
    transformation: str = "direct copy"

    def select_item(self) -> str:
        return f"{self.expression} as {self.target_column}"


@dataclass
class Mapping:
    """A complete source-to-target mapping, executable and self-documenting."""

    rule_id: str
    target_layer: str
    target_table: str
    source_layer: str
    source_relation: str          # a table name or an inline sub-select
    source_table_label: str       # what to record in lineage
    columns: list[ColumnMapping]
    where: str = ""
    regulatory_facing: bool = True
    notes: str = ""
    _extra_sources: dict[str, str] = field(default_factory=dict)

    def select_sql(self) -> str:
        cols = ",\n       ".join(c.select_item() for c in self.columns)
        sql = f"select {cols}\nfrom {self.source_relation}"
        if self.where:
            sql += f"\nwhere {self.where}"
        return sql


def create_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(DDL)


def record(con: duckdb.DuckDBPyConnection, mapping: Mapping) -> int:
    """Write one mapping's lineage. Returns the number of lineage rows.

    A source may be given as a bare column name, in which case it is attributed
    to the mapping's own source table, or as ``table.column`` where a target
    column genuinely draws on more than one source relation — which is the norm
    for an aggregate in the reporting layer. Recording the real multi-table
    provenance is the difference between lineage that answers a supervisor's
    question and lineage that merely looks complete.
    """
    rows = 0
    for col in mapping.columns:
        sources = col.sources or ("",)
        for raw in sources:
            if raw and "." in raw:
                src_table, src = raw.rsplit(".", 1)
            else:
                src_table, src = mapping.source_table_label, (raw or "")
            con.execute(
                """
                insert or replace into meta.lineage
                    (rule_id, target_layer, target_table, target_column,
                     source_layer, source_table, source_column,
                     transformation, regulatory_facing)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    mapping.rule_id, mapping.target_layer, mapping.target_table,
                    col.target_column, mapping.source_layer,
                    src_table, src,
                    col.transformation, mapping.regulatory_facing,
                ],
            )
            rows += 1
    return rows


def apply(
    con: duckdb.DuckDBPyConnection,
    mapping: Mapping,
    *,
    as_of_date: str | None = None,
    mode: str = "insert",
) -> int:
    """Execute a mapping and record its lineage in the same call.

    There is deliberately no way to do one without the other.

    ``mode="insert"`` writes with ``insert or replace``, so re-running a load
    for the same reporting date overwrites that date's rows rather than
    appending to them. That is not a convenience. DP-29 requires that a
    submitted report be exactly reproducible, and a pipeline that cannot be
    re-run without duplicating is not reproducible — it is a pipeline you get
    one attempt at, on the evening of a submission deadline. Idempotence is the
    precondition, and the primary key on every canonical entity is what
    enforces it.
    """
    record(con, mapping)
    target = f"{_schema_for(mapping.target_layer)}.{mapping.target_table}"
    if mode == "replace":
        con.execute(f"create or replace table {target} as {mapping.select_sql()}")
    else:
        con.execute(f"insert or replace into {target} {mapping.select_sql()}")
    n = con.execute(f"select count(*) from {target}").fetchone()[0]
    con.execute(
        "insert or replace into meta.load_log (rule_id, target, as_of_date, rows_loaded) "
        "values (?, ?, ?, ?)",
        [mapping.rule_id, target, as_of_date, n],
    )
    return n


def _schema_for(layer: str) -> str:
    return {"CANONICAL": "canon", "REPORTING": "rpt"}[layer]


# ---------------------------------------------------------------------------
# Querying lineage — the part a supervisor actually asks for
# ---------------------------------------------------------------------------
TRACE_SQL = """
with recursive chain as (
    select rule_id, target_table, target_column, source_layer,
           source_table, source_column, transformation, 1 as hop,
           target_table || '.' || target_column as path
    from meta.lineage
    where target_table = ? and (? is null or target_column = ?)

    union all

    select l.rule_id, l.target_table, l.target_column, l.source_layer,
           l.source_table, l.source_column, l.transformation, c.hop + 1,
           c.path || ' <- ' || l.target_table || '.' || l.target_column
    from meta.lineage l
    join chain c
      -- Sources are recorded schema-qualified ('canon.arrangement') because
      -- that is what a steward reading the lineage table needs to see, while
      -- targets are recorded bare. Joining the two without stripping the
      -- schema silently matches nothing, and a lineage trace that returns one
      -- hop looks like a short chain rather than a broken query -- which is
      -- the failure mode this whole repository exists to argue against.
      on l.target_table = regexp_replace(c.source_table, '^.*\\.', '')
     and (c.source_column = '' or l.target_column = c.source_column)
     and c.source_layer <> 'SOURCE'
     and position(l.target_table || '.' || l.target_column in c.path) = 0
    where c.hop < 10
)
select distinct on (hop, target_table, target_column, source_table, source_column)
       hop, target_table, target_column, source_layer, source_table,
       source_column, transformation
from chain
order by hop, target_table, target_column, source_table, source_column
"""


def trace(
    con: duckdb.DuckDBPyConnection, target_table: str, target_column: str | None = None
):
    """Walk a reported field back to the source systems that produced it."""
    return con.execute(TRACE_SQL, [target_table, target_column, target_column]).fetchall()


def unmapped_columns(con: duckdb.DuckDBPyConnection, table: str, schema: str) -> list[str]:
    """Columns of a built table with no lineage recorded.

    For a regulatory-facing output this is a conformance failure, not a note:
    a reported number nobody can explain is a finding waiting to happen.
    """
    actual = [
        r[0]
        for r in con.execute(
            "select column_name from information_schema.columns "
            "where table_schema = ? and table_name = ?",
            [schema, table],
        ).fetchall()
    ]
    mapped = {
        r[0]
        for r in con.execute(
            "select distinct target_column from meta.lineage where target_table = ?", [table]
        ).fetchall()
    }
    return [c for c in actual if c not in mapped]
