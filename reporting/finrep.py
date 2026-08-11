"""The finance lens.

Builds a FINREP-*shaped* view of financial assets from the canonical model:
carrying amount by accounting measurement category and by the counterparty
sector as **Finance** classifies it.

⚠️ **Illustrative structure only.** This is a reference architecture, not a
compliance artefact. The real FINREP templates, their cell references, the
breakdowns they require and the validation rules that apply to them are
defined by the EBA and change; build any actual return from the current
official text and taxonomy, never from a repository like this one.

What is faithful here is the *architecture*: the finance lens reads the
canonical model and nothing else, applies accounting rules that are the
Finance domain's to own, and records how every figure was derived.

Three accounting rules are applied, each of which is a place teams get it
wrong:

1. **Sign matters.** A derivative with negative fair value is a liability. An
   asset-side report that sums fair values without testing the sign quietly
   overstates assets and understates liabilities by the same amount.
2. **Accounting recognition drives the population**, not the economic event
   date. A trade executed before the reporting date but recognised after it is
   not in this report — and *is* in the risk report. See ``reconciliation.py``.
3. **Impairment reduces the carrying amount.** Gross balance is not carrying
   amount, and reporting one where the other is required is a restatement.
"""

from __future__ import annotations

import duckdb

from model import lineage
from model.lineage import ColumnMapping as C
from model.lineage import Mapping

DDL = "create schema if not exists rpt;"


def build(con: duckdb.DuckDBPyConnection, as_of: str) -> dict[str, int]:
    """Build the finance-lens outputs. Returns row counts per output."""
    con.execute(DDL)
    counts = {}

    # ---------------------------------------------------------- asset detail
    # One row per arrangement that qualifies as a financial asset on the
    # reporting date, carrying the attributes the aggregate needs. Built as a
    # named intermediate rather than inlined so that the aggregate's lineage
    # and the population rules can be inspected separately.
    asset_detail = Mapping(
        rule_id="RPT-FINREP-001", target_layer="REPORTING",
        target_table="finrep_asset_detail", source_layer="CANONICAL",
        source_relation=f"""(
            select a.arrangement_key, a.product_family, a.product_type, a.currency,
                   p.carrying_amount, p.fair_value, p.impairment_allowance,
                   p.notional_outstanding,
                   meas.classification_value as measurement_category,
                   stage.classification_value as impairment_stage,
                   sect.classification_value  as counterparty_sector_accounting,
                   pty.party_key, pty.legal_name, pty.is_group_entity,
                   ev.accounting_date
            from canon.arrangement a
            join canon.position p
              on p.arrangement_key = a.arrangement_key and p.as_of_date = a.as_of_date
            left join canon.arrangement_party_role r
              on r.arrangement_key = a.arrangement_key
             and r.as_of_date = a.as_of_date
             and r.role_type in ('BORROWER', 'COUNTERPARTY')
            left join canon.party pty
              on pty.party_key = r.party_key and pty.as_of_date = a.as_of_date
            left join canon.classification meas
              on meas.arrangement_key = a.arrangement_key
             and meas.classification_scheme = 'ACCOUNTING_MEASUREMENT'
             and meas.as_of_date = a.as_of_date
            left join canon.classification stage
              on stage.arrangement_key = a.arrangement_key
             and stage.classification_scheme = 'IMPAIRMENT_STAGE'
             and stage.as_of_date = a.as_of_date
            left join canon.classification sect
              on sect.arrangement_key = pty.party_key
             and sect.classification_scheme = 'COUNTERPARTY_SECTOR_ACCOUNTING'
             and sect.as_of_date = a.as_of_date
            left join (
                select arrangement_key, min(accounting_date) as accounting_date
                from canon.trade_event where event_type = 'INCEPTION'
                group by arrangement_key
            ) ev on ev.arrangement_key = a.arrangement_key
            where a.as_of_date = date '{as_of}'
              and a.status <> 'TERMINATED'
              -- Rule 2: accounting recognition on or before the reporting date.
              and (ev.accounting_date is null or ev.accounting_date <= date '{as_of}')
        ) d""",
        source_table_label="canon.arrangement",
        columns=[
            C("arrangement_key", "d.arrangement_key", ("canon.arrangement.arrangement_key",)),
            C("product_family", "d.product_family", ("canon.arrangement.product_family",)),
            C("product_type", "d.product_type", ("canon.arrangement.product_type",)),
            C("currency", "d.currency", ("canon.arrangement.currency",)),
            C("counterparty_party_key", "d.party_key",
              ("canon.arrangement_party_role.party_key",),
              "borrower for lending, counterparty for derivatives"),
            C("counterparty_name", "d.legal_name", ("canon.party.legal_name",),
              "the resolved legal name of the party in the borrower or "
              "counterparty role, carried for readability only; the party key is "
              "what anything downstream should join on"),
            C("measurement_category", "coalesce(d.measurement_category, 'UNCLASSIFIED')",
              ("canon.classification.classification_value",),
              "accounting measurement category; unclassified is surfaced rather "
              "than defaulted, because a silent default hides a data-quality gap"),
            C("impairment_stage", "d.impairment_stage",
              ("canon.classification.classification_value",),
              "the IFRS 9 stage as assessed under the impairment scheme; left "
              "null where no assessment exists rather than defaulted to stage 1, "
              "because an unassessed exposure and a performing one are different "
              "facts and only one of them needs chasing"),
            C("counterparty_sector", "coalesce(d.counterparty_sector_accounting, 'UNCLASSIFIED')",
              ("canon.classification.classification_value",),
              "the ACCOUNTING sector assessment; the prudential assessment may "
              "differ and is deliberately not used here"),
            C("is_intragroup", "coalesce(d.is_group_entity, false)",
              ("canon.party.is_group_entity",),
              "intragroup exposures are treated differently in several returns"),
            # Rule 1: sign test.
            C("asset_carrying_amount",
              "case when d.product_family = 'DERIVATIVE' "
              "     then case when coalesce(d.fair_value, 0) > 0 then d.fair_value else 0 end "
              "     else coalesce(d.carrying_amount, 0) end",
              ("canon.position.fair_value", "canon.position.carrying_amount"),
              "derivatives are an asset only where fair value is positive; "
              "non-derivatives use the accounting carrying amount"),
            C("liability_fair_value",
              "case when d.product_family = 'DERIVATIVE' "
              "     and coalesce(d.fair_value, 0) < 0 then -d.fair_value else 0 end",
              ("canon.position.fair_value",),
              "the negative-fair-value derivatives, kept visible rather than "
              "dropped, so assets and liabilities reconcile to the population"),
            C("impairment_allowance", "coalesce(d.impairment_allowance, 0)",
              ("canon.position.impairment_allowance",),
              "already deducted from carrying amount; carried for disclosure"),
            C("as_of_date", f"date '{as_of}'", (),
              "the reporting date, supplied as a run parameter rather than read "
              "from data; stamping it on every row is what makes a submitted "
              "figure reproducible months later without reasoning about when the "
              "job happened to run"),
        ],
    )
    counts["rpt.finrep_asset_detail"] = lineage.apply(
        con, asset_detail, as_of_date=as_of, mode="replace")

    # ------------------------------------------------------------- aggregate
    aggregate = Mapping(
        rule_id="RPT-FINREP-002", target_layer="REPORTING",
        target_table="finrep_assets_by_sector", source_layer="REPORTING",
        source_relation="rpt.finrep_asset_detail",
        source_table_label="rpt.finrep_asset_detail",
        columns=[
            C("as_of_date", "as_of_date", ("as_of_date",)),
            C("measurement_category", "measurement_category", ("measurement_category",)),
            C("counterparty_sector", "counterparty_sector", ("counterparty_sector",)),
            C("product_family", "product_family", ("product_family",)),
            C("exposure_count", "count(*)", ("arrangement_key",), "row count of the population"),
            C("carrying_amount", "sum(asset_carrying_amount)", ("asset_carrying_amount",),
              "sum of asset-side carrying amounts"),
            C("impairment_allowance", "sum(impairment_allowance)", ("impairment_allowance",)),
        ],
        where="1 = 1 group by as_of_date, measurement_category, counterparty_sector, product_family",
    )
    counts["rpt.finrep_assets_by_sector"] = lineage.apply(
        con, aggregate, as_of_date=as_of, mode="replace")

    return counts
