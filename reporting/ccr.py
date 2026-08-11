"""The risk lens.

Builds a counterparty-credit-risk view of the *same* canonical model that the
finance lens reads: exposure by netting set and counterparty, after
enforceable netting and haircut-adjusted collateral.

⚠️ **Illustrative structure only, and deliberately not SA-CCR.** The
standardised approach has a defined structure — a replacement-cost component,
a potential-future-exposure component built from supervisory factors by asset
class, hedging sets, maturity factors and a supervisory multiplier — and the
parameters are set in regulation. None of those parameters are reproduced
here, because a made-up supervisory factor in a public repository is worse
than none. What is modelled is the *shape* of the calculation and, more
importantly, the data architecture it requires.

The three data problems this lens exists to demonstrate:

1. **Netting is a legal fact before it is a calculation.** Exposures may be
   netted only where a legally enforceable agreement exists. The canonical
   model therefore carries ``is_legally_enforceable`` and this code respects
   it; unenforceable sets are calculated gross. Teams that net on the presence
   of an agreement identifier rather than its enforceability understate
   exposure.
2. **Collateral must be allocated, not counted.** One asset securing three
   arrangements is not three lots of protection.
3. **The population is the economic one.** Risk cares when the trade was
   *done*, not when it was booked in the ledger — which is why this lens uses
   the economic event date where the finance lens uses the accounting date.
"""

from __future__ import annotations

import duckdb

from model import lineage
from model.lineage import ColumnMapping as C
from model.lineage import Mapping

# An illustrative add-on rate standing in for a potential-future-exposure
# component. It is NOT a supervisory factor and must not be read as one; it
# exists so the worked example has a second component to reconcile.
ILLUSTRATIVE_ADDON_RATE = {
    "IR_SWAP": 0.005,
    "FX_FORWARD": 0.010,
    "FX_OPTION": 0.010,
    "CDS": 0.050,
    "EQUITY_OPTION": 0.060,
}
DEFAULT_ADDON_RATE = 0.010


def _addon_case(column: str) -> str:
    whens = " ".join(
        f"when '{k}' then {v}" for k, v in ILLUSTRATIVE_ADDON_RATE.items()
    )
    return f"(case {column} {whens} else {DEFAULT_ADDON_RATE} end)"


def build(con: duckdb.DuckDBPyConnection, as_of: str) -> dict[str, int]:
    con.execute("create schema if not exists rpt")
    counts = {}

    # ------------------------------------------------------- trade exposure
    trade_exposure = Mapping(
        rule_id="RPT-CCR-001", target_layer="REPORTING",
        target_table="ccr_trade_exposure", source_layer="CANONICAL",
        source_relation=f"""(
            select a.arrangement_key, a.product_type, a.currency,
                   a.original_notional, a.netting_set_key,
                   p.fair_value,
                   ns.is_legally_enforceable, ns.counterparty_party_key,
                   pty.legal_name,
                   sect.classification_value as counterparty_sector_prudential,
                   coalesce(col.collateral_value_after_haircut, 0) as collateral_value,
                   ev.economic_event_date
            from canon.arrangement a
            join canon.position p
              on p.arrangement_key = a.arrangement_key and p.as_of_date = a.as_of_date
            left join canon.netting_set ns
              on ns.netting_set_key = a.netting_set_key and ns.as_of_date = a.as_of_date
            left join canon.party pty
              on pty.party_key = ns.counterparty_party_key and pty.as_of_date = a.as_of_date
            left join canon.classification sect
              on sect.arrangement_key = ns.counterparty_party_key
             and sect.classification_scheme = 'COUNTERPARTY_SECTOR_PRUDENTIAL'
             and sect.as_of_date = a.as_of_date
            left join (
                select ca.arrangement_key,
                       sum(ca.allocated_value * (1 - coalesce(c.haircut_pct, 0)))
                         as collateral_value_after_haircut
                from canon.collateral_allocation ca
                join canon.collateral c
                  on c.collateral_key = ca.collateral_key and c.as_of_date = ca.as_of_date
                where c.is_financial_collateral
                group by ca.arrangement_key
            ) col on col.arrangement_key = a.arrangement_key
            left join (
                select arrangement_key, min(economic_event_date) as economic_event_date
                from canon.trade_event where event_type = 'INCEPTION'
                group by arrangement_key
            ) ev on ev.arrangement_key = a.arrangement_key
            where a.as_of_date = date '{as_of}'
              and a.product_family = 'DERIVATIVE'
              and a.status = 'ACTIVE'
              -- Problem 3: the economic population, not the accounting one.
              and (ev.economic_event_date is null or ev.economic_event_date <= date '{as_of}')
        ) d""",
        source_table_label="canon.arrangement",
        columns=[
            C("arrangement_key", "d.arrangement_key", ("canon.arrangement.arrangement_key",)),
            C("netting_set_key", "d.netting_set_key", ("canon.arrangement.netting_set_key",)),
            C("counterparty_party_key", "d.counterparty_party_key",
              ("canon.netting_set.counterparty_party_key",)),
            C("counterparty_name", "d.legal_name", ("canon.party.legal_name",),
              "legal name of the netting set's counterparty, carried for "
              "readability; note this is the counterparty of the *set*, which is "
              "the level at which credit exposure is actually run"),
            C("counterparty_sector", "coalesce(d.counterparty_sector_prudential, 'UNCLASSIFIED')",
              ("canon.classification.classification_value",),
              "the PRUDENTIAL sector assessment; may legitimately differ from "
              "the accounting assessment used by the finance lens"),
            C("product_type", "d.product_type", ("canon.arrangement.product_type",)),
            C("notional", "coalesce(d.original_notional, 0)",
              ("canon.arrangement.original_notional",),
              "original contractual notional, null-coalesced to zero so the "
              "add-on below is never silently null; a missing notional on a "
              "derivative is a data-quality finding, not a zero-risk trade, and "
              "is caught upstream rather than hidden here"),
            C("fair_value", "coalesce(d.fair_value, 0)", ("canon.position.fair_value",),
              "signed mark-to-market, carried so that netting can offset "
              "negative against positive within a set"),
            C("replacement_cost",
              "case when coalesce(d.fair_value, 0) > 0 then d.fair_value else 0 end",
              ("canon.position.fair_value",),
              "positive mark-to-market only; on its own a negative mark is not "
              "an exposure to the counterparty"),
            C("potential_future_exposure",
              f"coalesce(d.original_notional, 0) * {_addon_case('d.product_type')}",
              ("canon.arrangement.original_notional", "canon.arrangement.product_type"),
              "ILLUSTRATIVE add-on: notional times a rate that varies by product "
              "type. Not a supervisory factor and not SA-CCR"),
            C("collateral_after_haircut", "d.collateral_value",
              ("canon.collateral_allocation.allocated_value", "canon.collateral.haircut_pct"),
              "allocated collateral value reduced by its haircut; only financial "
              "collateral is recognised here"),
            C("netting_eligible", "coalesce(d.is_legally_enforceable, false)",
              ("canon.netting_set.is_legally_enforceable",),
              "Problem 1: netting is permitted only where the agreement is "
              "legally enforceable, not merely present"),
            C("as_of_date", f"date '{as_of}'", (),
              "the reporting date, supplied as a run parameter rather than read "
              "from data; the risk lens and the finance lens are stamped with the "
              "same date so that a reconciliation between them is a query rather "
              "than an assumption"),
        ],
    )
    counts["rpt.ccr_trade_exposure"] = lineage.apply(
        con, trade_exposure, as_of_date=as_of, mode="replace")

    # ------------------------------------------------- netting-set exposure
    # Enforceable sets net; everything else is aggregated gross. The two paths
    # are unioned so that a single output carries both, with the treatment
    # recorded on every row.
    netting_set = Mapping(
        rule_id="RPT-CCR-002", target_layer="REPORTING",
        target_table="ccr_exposure_by_netting_set", source_layer="REPORTING",
        source_relation="""(
            select coalesce(netting_set_key, 'UNNETTED:' || arrangement_key) as netting_set_key,
                   counterparty_party_key, counterparty_name, counterparty_sector,
                   netting_eligible, as_of_date,
                   count(*) as trade_count,
                   -- Gross: sum the positive marks only, ignoring the negatives.
                   sum(replacement_cost) as gross_replacement_cost,
                   -- Netted: sum the SIGNED marks, so a negative position
                   -- offsets a positive one, then floor at zero -- a net
                   -- liability is not an exposure to the counterparty. This
                   -- offsetting is the whole economic benefit of netting, and
                   -- it is available only where the agreement is enforceable.
                   case when netting_eligible
                        then greatest(sum(fair_value), 0)
                        else sum(replacement_cost) end as netted_replacement_cost,
                   sum(potential_future_exposure) as potential_future_exposure,
                   sum(collateral_after_haircut) as collateral_after_haircut
            from rpt.ccr_trade_exposure
            group by 1, 2, 3, 4, 5, 6
        ) s""",
        source_table_label="rpt.ccr_trade_exposure",
        columns=[
            C("netting_set_key", "s.netting_set_key", ("netting_set_key",),
              "trades with no enforceable set are treated as their own set"),
            C("counterparty_party_key", "s.counterparty_party_key",
              ("counterparty_party_key",)),
            C("counterparty_name", "s.counterparty_name", ("counterparty_name",)),
            C("counterparty_sector", "s.counterparty_sector", ("counterparty_sector",)),
            C("netting_eligible", "s.netting_eligible", ("netting_eligible",)),
            C("trade_count", "s.trade_count", ("arrangement_key",),
              "number of trades collapsed into the set; published because a "
              "netting benefit on a one-trade set means the mark moved, not that "
              "the agreement did anything"),
            C("gross_replacement_cost", "s.gross_replacement_cost", ("replacement_cost",),
              "sum of positive marks, ignoring offsetting negatives"),
            C("netted_replacement_cost", "s.netted_replacement_cost",
              ("fair_value", "replacement_cost"),
              "signed marks offset within the set and floored at zero where the "
              "agreement is legally enforceable; gross otherwise"),
            C("potential_future_exposure", "s.potential_future_exposure",
              ("potential_future_exposure",)),
            C("collateral_after_haircut", "s.collateral_after_haircut",
              ("collateral_after_haircut",)),
            C("exposure_at_default",
              "greatest(s.netted_replacement_cost + s.potential_future_exposure "
              "         - s.collateral_after_haircut, 0)",
              ("replacement_cost", "potential_future_exposure", "collateral_after_haircut"),
              "ILLUSTRATIVE: replacement cost plus add-on less recognised "
              "collateral, floored at zero. Not a regulatory EAD calculation"),
            C("as_of_date", "s.as_of_date", ("as_of_date",)),
        ],
    )
    counts["rpt.ccr_exposure_by_netting_set"] = lineage.apply(
        con, netting_set, as_of_date=as_of, mode="replace")

    return counts
