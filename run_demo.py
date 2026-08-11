#!/usr/bin/env python3
"""End to end: source extracts → canonical model → two lenses → reconciliation.

    python run_demo.py                # everything, then the analysis
    python run_demo.py --reset        # start from an empty warehouse
    python run_demo.py --no-analysis  # build only

Then check the result against the written standards:

    python -m conformance.check --db warehouse.duckdb
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

import duckdb

from model import canonical, lineage, load
from reporting import ccr, finrep, reconciliation

REPO = Path(__file__).resolve().parent
DB_PATH = REPO / "warehouse.duckdb"
EXTRACTS = REPO / "extracts"
AS_OF = "2026-03-31"

LOGGER = logging.getLogger("t2r")


def banner(text: str, width: int = 78) -> str:
    return f"\n{'=' * width}\n  {text}\n{'=' * width}"


def build(con: duckdb.DuckDBPyConnection) -> None:
    canonical.create_schema(con)
    lineage.create_schema(con)
    load.register_extracts(con, EXTRACTS)

    print(banner("IDENTITY RESOLUTION  ·  one legal entity, three identifiers"))
    methods = load.resolve_party_identity(con)
    for method, n in methods.items():
        note = {
            "LEI": "matched on Legal Entity Identifier — definitive",
            "NAME_COUNTRY": "matched on normalised name and country — weaker, flagged",
            "UNRESOLVED": "could not be tied to a party — a steward's queue, not a silent drop",
            "NATIVE": "the reference master resolving to itself",
        }.get(method, "")
        print(f"  {method:<14} {n:>5}   {note}")

    print(banner("CANONICAL MODEL  ·  one model, source-agnostic"))
    for label, n in load.load_all(con, AS_OF):
        print(f"  {label:<38} {n:>7} rows")

    print(banner("FINANCE LENS  ·  accounting view"))
    for table, n in finrep.build(con, AS_OF).items():
        print(f"  {table:<38} {n:>7} rows")

    print(banner("RISK LENS  ·  prudential view of the same model"))
    for table, n in ccr.build(con, AS_OF).items():
        print(f"  {table:<38} {n:>7} rows")

    print(banner("RECONCILIATION  ·  where the lenses differ, and why"))
    for table, n in reconciliation.build(con, AS_OF).items():
        print(f"  {table:<38} {n:>7} rows")

    n = con.execute("select count(*) from meta.lineage").fetchone()[0]
    print(f"\n  meta.lineage                           {n:>7} column-level mappings recorded")


def analysis(con: duckdb.DuckDBPyConnection) -> None:
    print(banner("1 · THE SAME BOOK, THROUGH TWO LENSES"))
    con.sql("""
        select 'Finance: derivative assets'  as measure,
               round(sum(asset_carrying_amount), 0) as amount
        from rpt.finrep_asset_detail where product_family = 'DERIVATIVE'
        union all
        select 'Finance: derivative liabilities',
               round(sum(liability_fair_value), 0) from rpt.finrep_asset_detail
        union all
        select 'Risk: gross replacement cost',
               round(sum(gross_replacement_cost), 0) from rpt.ccr_exposure_by_netting_set
        union all
        select 'Risk: exposure at default (illustrative)',
               round(sum(exposure_at_default), 0) from rpt.ccr_exposure_by_netting_set
    """).show()
    print("  Four different numbers describing the same derivatives book. None is")
    print("  wrong. An architecture that cannot explain the gaps is what is wrong.")

    print(banner("2 · WHY THE POPULATIONS DIFFER"))
    con.sql("""
        select difference_reason, trade_count,
               round(finance_asset_amount, 0) as finance_assets,
               round(risk_replacement_cost, 0) as risk_rc
        from rpt.lens_population_reconciliation order by trade_count desc
    """).show()

    print(banner("3 · THE NETTING BENEFIT, QUANTIFIED"))
    con.sql("""
        select case when netting_eligible then 'Enforceable agreement'
                    else 'No enforceable netting' end as treatment,
               netting_sets,
               round(gross_replacement_cost, 0)  as gross_rc,
               round(netted_replacement_cost, 0) as netted_rc,
               round(collateral_recognised, 0)   as collateral,
               round(exposure_at_default, 0)     as ead
        from rpt.netting_reconciliation
    """).show()
    print("  Netting is a legal fact before it is a calculation. Sets without an")
    print("  enforceable agreement are calculated gross — deliberately.")

    print(banner("4 · WHERE FINANCE AND RISK CLASSIFY THE SAME COUNTERPARTY DIFFERENTLY"))
    con.sql("""
        select legal_name, accounting_sector, prudential_sector,
               arrangement_count, round(total_carrying_amount, 0) as carrying_amount
        from rpt.sector_classification_disagreement
        order by total_carrying_amount desc limit 8
    """).show()
    n = con.execute("select count(*) from rpt.sector_classification_disagreement").fetchone()[0]
    print(f"  {n} counterparties are categorised differently by the two functions.")
    print("  Both schemes are stored. Neither overwrites the other. The disagreement")
    print("  is published rather than resolved by whichever load ran last.")

    print(banner("5 · LINEAGE  ·  tracing a reported figure back to source"))
    print("  The question a supervisor actually asks: this number on this line —")
    print("  where did it come from? Not a diagram. A query.\n")
    rows = lineage.trace(con, "finrep_assets_by_sector", "carrying_amount")
    for hop, tgt_t, tgt_c, src_layer, src_t, src_c, transform in rows[:12]:
        indent = "  " * hop
        print(f"  {indent}└─ {tgt_t}.{tgt_c}")
        print(f"  {indent}     ← [{src_layer}] {src_t}.{src_c or '*'}")
        print(f"  {indent}       {transform[:92]}")
    depth = max((r[0] for r in rows), default=0)
    landed = sorted({r[4] for r in rows if r[3] == "SOURCE"})
    print(f"\n  {len(rows)} hops, {depth} levels deep, landing on: {', '.join(landed) or 'nothing'}.")
    print("  Nobody wrote that chain down. It was recorded by the loaders that")
    print("  built the tables, because they cannot move a column without")
    print("  declaring where it came from.")

    print(banner("6 · IDENTITY: WHAT RESOLVING ON THE WRONG KEY WOULD COST"))
    con.sql("""
        select resolution_method, count(*) as parties
        from stg.party_xref group by 1 order by 2 desc
    """).show()
    print("  Had the pipeline joined on the half-populated hint column in the core")
    print("  banking extract instead of the LEI, the parties it failed to match")
    print("  would each have become a second, separate counterparty — and every")
    print("  concentration measure in the bank would read lower than the truth.")

    print(banner("7 · TWO HIERARCHIES, AND WHY THE MODEL HOLDS BOTH"))
    con.sql(f"""
        select l.child_party_key                as party,
               lp.legal_name                    as legal_parent,
               rp.legal_name                    as risk_group_parent
        from canon.party_hierarchy l
        join canon.party_hierarchy r
          on r.child_party_key = l.child_party_key and r.as_of_date = l.as_of_date
         and r.hierarchy_type = 'RISK_GROUP'
        left join canon.party lp
          on lp.party_key = l.parent_party_key and lp.as_of_date = l.as_of_date
        left join canon.party rp
          on rp.party_key = r.parent_party_key and rp.as_of_date = r.as_of_date
        where l.hierarchy_type = 'LEGAL_OWNERSHIP'
          and l.parent_party_key <> r.parent_party_key
          and l.as_of_date = date '{AS_OF}'
        limit 5
    """).show()
    n = con.execute(f"""
        select count(*) from canon.party_hierarchy l
        join canon.party_hierarchy r
          on r.child_party_key = l.child_party_key and r.as_of_date = l.as_of_date
         and r.hierarchy_type = 'RISK_GROUP'
        where l.hierarchy_type = 'LEGAL_OWNERSHIP'
          and l.parent_party_key <> r.parent_party_key
          and l.as_of_date = date '{AS_OF}'
    """).fetchone()[0]
    print(f"  {n} parties whose legal owner is not their risk group.")
    print("  Legal ownership is a fact about share registers. Risk grouping is a")
    print("  judgement about who fails together. A parent_party_key column on the")
    print("  party table would force a choice between them and hide that a choice")
    print("  was made — and a connected-clients limit would then be measured")
    print("  against whichever hierarchy the last load happened to write.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--no-analysis", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    if args.reset:
        DB_PATH.unlink(missing_ok=True)
        shutil.rmtree(EXTRACTS, ignore_errors=True)

    if not EXTRACTS.exists() or not any(EXTRACTS.glob("*.csv")):
        print("No source extracts found; generating them.")
        sys.path.insert(0, str(REPO / "data"))
        from generate_banking_data import generate  # noqa: E402

        generate(EXTRACTS)

    con = duckdb.connect(str(DB_PATH))
    try:
        build(con)
        if not args.no_analysis:
            analysis(con)
        print(banner("DONE"))
        print(f"  warehouse: {DB_PATH}")
        print("  now check it against the written standards:")
        print("      python -m conformance.check --db warehouse.duckdb")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
