#!/usr/bin/env python3
"""Policy conformance linter — the standards, executed.

    python -m conformance.check --db warehouse.duckdb
    python -m conformance.check --db warehouse.duckdb --json report.json
    python -m conformance.check --db warehouse.duckdb --strict   # WARN also fails

Exit codes: ``0`` conformant, ``1`` non-conformance at ERROR severity (or at
WARN with ``--strict``), ``2`` the linter could not run.

Why this exists
---------------
"Reviewing data architecture artefacts and making decisions based on policies
and standards" is a sentence that appears in a great many role descriptions and
is almost never mechanised. So it is done by whoever has time, inconsistently,
and it stops entirely when that person is on leave.

The rule IDs here **are** the standard IDs in
``governance/data-policy-standards.md``. That is deliberate and it is the
anti-drift mechanism: a standard whose ID has no rule is visibly manual, and a
rule whose ID has no standard fails this linter's own self-check. The two
artefacts cannot quietly diverge.

This checks the machine-checkable subset — roughly a third of the standards.
The rest need a human, and pretending otherwise would be the more dangerous
error. ``governance/artefact-conformance-checklist.md`` is what a reviewer
works through for those.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from model.canonical import ENTITY_METADATA  # noqa: E402

ERROR, WARN = "ERROR", "WARN"


@dataclass
class Finding:
    rule_id: str
    severity: str
    subject: str
    message: str


@dataclass
class Rule:
    rule_id: str
    title: str
    severity: str
    findings: list[Finding] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------
def dp01_every_entity_has_an_owner(con) -> list[Finding]:
    """DP-01 · Every canonical entity has exactly one named owner."""
    out = []
    for entity, meta in ENTITY_METADATA.items():
        if not meta.get("owner"):
            out.append(Finding("DP-01", ERROR, entity, "no owner declared"))
        if not meta.get("steward"):
            out.append(Finding("DP-01", WARN, entity, "no steward declared"))
    return out


def dp05_every_entity_declares_a_business_key(con) -> list[Finding]:
    """DP-05 · Every entity declares a business key meaningful to the business."""
    out = []
    for entity, meta in ENTITY_METADATA.items():
        bk = meta.get("business_key") or []
        if not bk:
            out.append(Finding("DP-05", ERROR, entity, "no business key declared"))
            continue
        # A business key made only of surrogate keys is not a business key.
        if all(c.endswith("_key") for c in bk):
            out.append(Finding(
                "DP-05", WARN, entity,
                f"business key {bk} is composed only of surrogate keys; a business "
                "key should be resolvable by someone who knows the business"))
        cols = _columns(con, "canon", entity)
        if cols:
            missing = [c for c in bk if c not in cols]
            if missing:
                out.append(Finding("DP-05", ERROR, entity,
                                   f"declared business key columns absent from the table: {missing}"))
    return out


def dp10_nothing_consumes_a_source_directly(con) -> list[Finding]:
    """DP-10 · Nothing consumes a source system directly.

    The reporting layer must read the canonical model. A lineage row whose
    target is in the reporting layer and whose source layer is SOURCE means a
    report has bypassed the canonical model — which is exactly how two reports
    of the same concept start to diverge.
    """
    rows = con.execute("""
        select distinct target_table, target_column, source_table
        from meta.lineage
        where target_layer = 'REPORTING' and source_layer = 'SOURCE'
    """).fetchall()
    return [Finding("DP-10", ERROR, f"{t}.{c}",
                    f"reads source table {s} directly, bypassing the canonical model")
            for t, c, s in rows]


def dp15_every_entity_has_a_definition(con) -> list[Finding]:
    """DP-15 · Every entity has a definition that survives being read aloud."""
    out = []
    for entity, meta in ENTITY_METADATA.items():
        definition = (meta.get("definition") or "").strip()
        if not definition:
            out.append(Finding("DP-15", ERROR, entity, "no definition"))
        elif len(definition) < 60:
            out.append(Finding("DP-15", WARN, entity,
                               "definition is too short to be useful; a definition that "
                               "merely restates the name has not defined anything"))
        elif definition.lower().startswith(entity.replace("_", " ").lower()[:12]):
            out.append(Finding("DP-15", WARN, entity,
                               "definition appears to restate the entity name"))
    return out


NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def dp16_names_follow_the_convention(con) -> list[Finding]:
    """DP-16 · Names follow the domain naming convention."""
    out = []
    for schema in ("canon", "rpt"):
        for table in _tables(con, schema):
            if not NAME_RE.match(table):
                out.append(Finding("DP-16", ERROR, f"{schema}.{table}",
                                   "table name is not lower_snake_case"))
            for col in _columns(con, schema, table):
                if not NAME_RE.match(col):
                    out.append(Finding("DP-16", ERROR, f"{schema}.{table}.{col}",
                                       "column name is not lower_snake_case"))
                if col.endswith("_key") and schema == "canon" and table in ENTITY_METADATA:
                    continue
    return out


def dp18_regulatory_fields_have_lineage(con) -> list[Finding]:
    """DP-18 · Every regulatory-facing field has end-to-end lineage, as data."""
    out = []
    for table in _tables(con, "rpt"):
        mapped = {r[0] for r in con.execute(
            "select distinct target_column from meta.lineage where target_table = ?",
            [table]).fetchall()}
        for col in _columns(con, "rpt", table):
            if col not in mapped:
                out.append(Finding("DP-18", ERROR, f"rpt.{table}.{col}",
                                   "no lineage recorded for a regulatory-facing column"))
    return out


TRIVIAL = {"", "direct copy", "copy", "as-is", "n/a", "todo", "tbc"}


def dp19_lineage_is_sufficient(con) -> list[Finding]:
    """DP-19 · "Sufficient lineage" is defined, not left to judgement.

    Two tests. First, every transformation that is not a straight copy must be
    described in words — a lineage row saying only that a transformation
    occurred answers nothing. Second, every reporting column must trace all the
    way back to a SOURCE-layer table, not merely to the canonical layer; a
    chain that stops halfway cannot answer "which system did this come from".
    """
    out = []
    rows = con.execute("""
        select rule_id, target_table, target_column, transformation
        from meta.lineage
        where target_layer = 'REPORTING'
    """).fetchall()
    for rule_id, table, col, transformation in rows:
        if (transformation or "").strip().lower() in TRIVIAL and not _is_passthrough(
            con, table, col
        ):
            out.append(Finding("DP-19", WARN, f"{table}.{col}",
                               f"[{rule_id}] transformation is not described"))

    for table in _tables(con, "rpt"):
        for col in _columns(con, "rpt", table):
            if not _reaches_source(con, table, col):
                out.append(Finding("DP-19", ERROR, f"rpt.{table}.{col}",
                                   "lineage chain does not reach a source system"))
    return out


def dp29_reproducibility(con) -> list[Finding]:
    """DP-29 · A submitted regulatory report must be exactly reproducible.

    The minimum structural precondition is an as-of date on every canonical
    entity. Without it there is no way to ask what the data looked like on the
    reporting date, and reproduction becomes an argument rather than a query.
    """
    out = []
    for entity in ENTITY_METADATA:
        cols = _columns(con, "canon", entity)
        if not cols:
            continue
        if "as_of_date" not in cols:
            # trade_event is legitimately event-dated rather than as-of dated.
            severity = WARN if entity == "trade_event" else ERROR
            out.append(Finding("DP-29", severity, f"canon.{entity}",
                               "no as_of_date column; point-in-time reproduction "
                               "is not possible"))
    return out


def dp36_golden_source_declared(con) -> list[Finding]:
    """DP-36 · Every attribute has exactly one golden source per domain."""
    return [Finding("DP-36", ERROR, entity, "no golden source declared")
            for entity, meta in ENTITY_METADATA.items() if not meta.get("golden_source")]


def dp41_material_decisions_have_adrs(con) -> list[Finding]:
    """DP-41 · Every material architecture decision is recorded as an ADR."""
    out = []
    adr_dir = REPO / "governance" / "adr"
    if not adr_dir.exists():
        return [Finding("DP-41", ERROR, "governance/adr", "no ADR directory")]
    adrs = sorted(p.name for p in adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md"))
    if len(adrs) < 4:
        out.append(Finding("DP-41", WARN, "governance/adr",
                           f"only {len(adrs)} ADRs recorded; the decisions this "
                           "architecture rests on are not all captured"))
    for adr in adrs:
        text = (adr_dir / adr).read_text(encoding="utf-8")
        for heading in ("Status", "Context", "Decision", "Consequences"):
            if heading.lower() not in text.lower():
                out.append(Finding("DP-41", WARN, f"adr/{adr}",
                                   f"missing a '{heading}' section"))
    return out


def self_check_rule_ids_exist_in_standards() -> list[Finding]:
    """The linter's own conformance: every rule ID must be a published standard."""
    doc = REPO / "governance" / "data-policy-standards.md"
    if not doc.exists():
        return [Finding("META", ERROR, "governance/data-policy-standards.md",
                        "standards document not found; rule IDs cannot be verified")]
    published = set(re.findall(r"DP-\d{2}", doc.read_text(encoding="utf-8")))
    return [Finding("META", ERROR, r.rule_id,
                    "rule ID does not correspond to any published standard")
            for r in RULES if r.rule_id not in published]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _tables(con, schema: str) -> list[str]:
    return [r[0] for r in con.execute(
        "select table_name from information_schema.tables where table_schema = ? "
        "order by table_name", [schema]).fetchall()]


def _columns(con, schema: str, table: str) -> list[str]:
    return [r[0] for r in con.execute(
        "select column_name from information_schema.columns "
        "where table_schema = ? and table_name = ? order by ordinal_position",
        [schema, table]).fetchall()]


def _is_passthrough(con, table: str, col: str) -> bool:
    row = con.execute(
        "select count(*) from meta.lineage where target_table = ? and target_column = ? "
        "and source_column = ?", [table, col, col]).fetchone()
    return bool(row and row[0])


def _reaches_source(con, table: str, col: str, depth: int = 0) -> bool:
    """True when the lineage chain from this column terminates at a source system."""
    if depth > 8:
        return False
    rows = con.execute(
        "select source_layer, source_table, source_column from meta.lineage "
        "where target_table = ? and target_column = ?", [table, col]).fetchall()
    if not rows:
        return False
    for layer, src_table, src_col in rows:
        if layer == "SOURCE":
            return True
        bare = src_table.split(".")[-1]
        if src_col and _reaches_source(con, bare, src_col, depth + 1):
            return True
        # An aggregate or a constant carries no single source column through, so
        # the chain has to be followed at table level instead.
        if _table_reaches_source(con, bare, depth + 1):
            return True
    return False


def _table_reaches_source(con, table: str, depth: int = 0, seen: frozenset = frozenset()) -> bool:
    """True when any lineage chain out of this table terminates at a source system.

    An earlier version of this helper looked exactly one hop: it asked whether
    the table read a SOURCE-layer relation, and stopped. That passed a reporting
    table built directly on the canonical model and failed a reporting table
    built on another reporting table — the reconciliation outputs, as it
    happened. The distinction it was drawing was the number of hops, which is
    not what makes lineage sufficient; what matters is whether the chain lands
    on a system of record at all. It now walks.

    The ``seen`` set guards against a cycle in the lineage graph. A cycle is
    itself a modelling error, but a linter that hangs on bad input is worse than
    one that reports it.
    """
    if depth > 8 or table in seen:
        return False
    rows = con.execute(
        "select distinct source_layer, source_table from meta.lineage where target_table = ?",
        [table]).fetchall()
    for layer, src_table in rows:
        if layer == "SOURCE":
            return True
        if _table_reaches_source(con, src_table.split(".")[-1], depth + 1, seen | {table}):
            return True
    return False


RULES: list[Rule] = [
    Rule("DP-01", "Every canonical entity has a named owner", ERROR),
    Rule("DP-05", "Every entity declares a business key", ERROR),
    Rule("DP-10", "Nothing consumes a source system directly", ERROR),
    Rule("DP-15", "Every entity has a usable definition", ERROR),
    Rule("DP-16", "Names follow the domain naming convention", ERROR),
    Rule("DP-18", "Regulatory-facing fields have lineage captured as data", ERROR),
    Rule("DP-19", "Lineage is sufficient, not merely present", ERROR),
    Rule("DP-29", "Point-in-time reproducibility is structurally possible", ERROR),
    Rule("DP-36", "Every entity has a declared golden source", ERROR),
    Rule("DP-41", "Material architecture decisions are recorded as ADRs", WARN),
]

CHECKS = {
    "DP-01": dp01_every_entity_has_an_owner,
    "DP-05": dp05_every_entity_declares_a_business_key,
    "DP-10": dp10_nothing_consumes_a_source_directly,
    "DP-15": dp15_every_entity_has_a_definition,
    "DP-16": dp16_names_follow_the_convention,
    "DP-18": dp18_regulatory_fields_have_lineage,
    "DP-19": dp19_lineage_is_sufficient,
    "DP-29": dp29_reproducibility,
    "DP-36": dp36_golden_source_declared,
    "DP-41": dp41_material_decisions_have_adrs,
}


def run(con) -> list[Finding]:
    findings = list(self_check_rule_ids_exist_in_standards())
    for rule in RULES:
        findings.extend(CHECKS[rule.rule_id](con))
    return findings


def render(findings: list[Finding]) -> str:
    by_rule: dict[str, list[Finding]] = {}
    for f in findings:
        by_rule.setdefault(f.rule_id, []).append(f)

    lines = ["", "=" * 78, "  DATA ARCHITECTURE CONFORMANCE REPORT", "=" * 78, ""]
    for rule in RULES:
        hits = by_rule.get(rule.rule_id, [])
        errors = sum(1 for h in hits if h.severity == ERROR)
        warns = len(hits) - errors
        flag = "PASS" if not hits else ("FAIL" if errors else "WARN")
        lines.append(f"  [{flag}] {rule.rule_id}  {rule.title}")
        if hits:
            lines.append(f"         {errors} error(s), {warns} warning(s)")
            for h in hits[:6]:
                lines.append(f"           · {h.severity:<5} {h.subject}: {h.message}")
            if len(hits) > 6:
                lines.append(f"           · ... and {len(hits) - 6} more")
    meta = by_rule.get("META", [])
    if meta:
        lines.append("")
        lines.append("  [FAIL] META  Linter self-check: rule IDs must be published standards")
        for h in meta:
            lines.append(f"           · {h.subject}: {h.message}")
    total_e = sum(1 for f in findings if f.severity == ERROR)
    total_w = sum(1 for f in findings if f.severity == WARN)
    lines += ["", f"  {total_e} error(s), {total_w} warning(s) across {len(RULES)} rules.",
              "  The remaining standards need a human reviewer — see",
              "  governance/artefact-conformance-checklist.md.", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Check the warehouse against the data policy standards.")
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--json", dest="json_out", type=Path)
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    if not args.db.exists():
        print(f"Database not found: {args.db}. Run run_demo.py first.", file=sys.stderr)
        return 2

    con = duckdb.connect(str(args.db), read_only=True)
    try:
        findings = run(con)
    except duckdb.Error as exc:
        print(f"Linter could not run: {exc}", file=sys.stderr)
        return 2
    finally:
        con.close()

    if not args.quiet:
        print(render(findings))
    if args.json_out:
        args.json_out.write_text(json.dumps(
            [f.__dict__ for f in findings], indent=2), encoding="utf-8")
        print(f"  report written: {args.json_out}")

    errors = [f for f in findings if f.severity == ERROR]
    warns = [f for f in findings if f.severity == WARN]
    if errors:
        print(f"\nNON-CONFORMANT: {len(errors)} error(s).", file=sys.stderr)
        return 1
    if args.strict and warns:
        print(f"\nNON-CONFORMANT under --strict: {len(warns)} warning(s).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
