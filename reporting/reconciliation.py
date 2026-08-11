"""Where the two lenses disagree, and why.

This is the intellectual core of the repository. Two functions read the same
canonical model and produce different numbers for what a non-specialist would
call "the same thing". Both are correct. The architecture's job is not to make
them agree — it is to make the disagreement **explainable, attributable and
stable**, so that when someone asks why Risk shows more derivatives than
Finance, the answer takes a minute rather than a fortnight.

The wrong answers, for the record
---------------------------------
* **Blend them.** Produce one number that is neither the accounting figure nor
  the prudential one. It will fail both audiences and satisfy no regulator.
* **Build two disconnected marts.** Then nobody can explain the difference at
  all, and the reconciliation becomes a quarterly spreadsheet exercise done by
  whoever is least able to refuse.

The right answer is one model, two lenses, and a published reconciliation with
an explicit residual — a residual that is *named* rather than plugged.

A note on how this file is written
----------------------------------
The first draft of this module built its tables with plain SQL, because they
are "only" reconciliation outputs rather than regulatory submissions. The
conformance linter failed the build: DP-18 requires lineage on everything in
the reporting layer, and the reconciliation is precisely the artefact someone
will be asked to defend. It was quicker to argue for an exemption than to
route three tables through the mapping mechanism, which is exactly why the
exemption should not exist. The tables are built through ``Mapping`` like
everything else.
"""

from __future__ import annotations

import duckdb

from model import lineage
from model.lineage import ColumnMapping as C
from model.lineage import Mapping


def build(con: duckdb.DuckDBPyConnection, as_of: str) -> dict[str, int]:
    counts = {}

    # ------------------------------------------- population reconciliation
    population = Mapping(
        rule_id="RPT-RECON-001", target_layer="REPORTING",
        target_table="lens_population_reconciliation", source_layer="REPORTING",
        source_relation=f"""(
            with finance as (
                select arrangement_key, asset_carrying_amount, liability_fair_value
                from rpt.finrep_asset_detail where product_family = 'DERIVATIVE'
            ),
            risk as (
                select arrangement_key, replacement_cost from rpt.ccr_trade_exposure
            ),
            universe as (
                select coalesce(f.arrangement_key, r.arrangement_key) as arrangement_key,
                       f.arrangement_key is not null as in_finance_lens,
                       r.arrangement_key is not null as in_risk_lens,
                       coalesce(f.asset_carrying_amount, 0) as finance_asset_amount,
                       coalesce(f.liability_fair_value, 0)  as finance_liability_amount,
                       coalesce(r.replacement_cost, 0)      as risk_replacement_cost
                from finance f full outer join risk r using (arrangement_key)
            )
            select u.*,
                   case
                     when u.in_finance_lens and u.in_risk_lens then 'IN BOTH'
                     when u.in_risk_lens and ev.accounting_date > date '{as_of}'
                       then 'RISK ONLY: economic date on or before the reporting '
                            || 'date, accounting recognition after it'
                     when u.in_finance_lens and a.status <> 'ACTIVE'
                       then 'FINANCE ONLY: not an active trade, so outside the '
                            || 'counterparty credit risk population'
                     when u.in_finance_lens and ev.economic_event_date > date '{as_of}'
                       then 'FINANCE ONLY: recognised for accounting, economic '
                            || 'event after the reporting date'
                     when u.in_risk_lens then 'RISK ONLY: unexplained residual'
                     else 'FINANCE ONLY: unexplained residual'
                   end as difference_reason
            from universe u
            left join canon.arrangement a
              on a.arrangement_key = u.arrangement_key and a.as_of_date = date '{as_of}'
            left join (
                select arrangement_key,
                       min(economic_event_date) as economic_event_date,
                       min(accounting_date)     as accounting_date
                from canon.trade_event where event_type = 'INCEPTION'
                group by arrangement_key
            ) ev on ev.arrangement_key = u.arrangement_key
        ) x""",
        source_table_label="rpt.finrep_asset_detail",
        columns=[
            C("difference_reason", "x.difference_reason",
              ("rpt.finrep_asset_detail.arrangement_key",
               "rpt.ccr_trade_exposure.arrangement_key",
               "canon.trade_event.accounting_date",
               "canon.trade_event.economic_event_date",
               "canon.arrangement.status"),
              "categorises each trade by why it appears in one lens and not the "
              "other; an unexplained residual is named as such rather than "
              "absorbed into a catch-all"),
            C("trade_count", "count(*)", ("rpt.finrep_asset_detail.arrangement_key",),
              "number of trades in this reconciling category"),
            C("finance_asset_amount", "sum(x.finance_asset_amount)",
              ("rpt.finrep_asset_detail.asset_carrying_amount",),
              "finance-lens asset amount for the category"),
            C("finance_liability_amount", "sum(x.finance_liability_amount)",
              ("rpt.finrep_asset_detail.liability_fair_value",),
              "finance-lens liability amount for the category"),
            C("risk_replacement_cost", "sum(x.risk_replacement_cost)",
              ("rpt.ccr_trade_exposure.replacement_cost",),
              "risk-lens replacement cost for the category"),
            C("as_of_date", f"date '{as_of}'", (), "reporting as-of date"),
        ],
        where="1 = 1 group by x.difference_reason",
    )
    counts["rpt.lens_population_reconciliation"] = lineage.apply(
        con, population, as_of_date=as_of, mode="replace")

    # ------------------------------------------------- netting reconciliation
    # The single largest reconciling item between the two lenses, isolated so
    # it can be quantified rather than argued about.
    netting = Mapping(
        rule_id="RPT-RECON-002", target_layer="REPORTING",
        target_table="netting_reconciliation", source_layer="REPORTING",
        source_relation="rpt.ccr_exposure_by_netting_set n",
        source_table_label="rpt.ccr_exposure_by_netting_set",
        columns=[
            C("netting_eligible", "n.netting_eligible", ("netting_eligible",),
              "whether a legally enforceable agreement covers the set"),
            C("netting_sets", "count(*)", ("netting_set_key",), "number of sets"),
            C("gross_replacement_cost", "sum(n.gross_replacement_cost)",
              ("gross_replacement_cost",), "sum of positive marks before offsetting"),
            C("netted_replacement_cost", "sum(n.netted_replacement_cost)",
              ("netted_replacement_cost",), "after offsetting where permitted"),
            C("netting_benefit",
              "sum(n.gross_replacement_cost) - sum(n.netted_replacement_cost)",
              ("gross_replacement_cost", "netted_replacement_cost"),
              "the economic value of the netting agreements, quantified; zero by "
              "construction where no enforceable agreement exists"),
            C("collateral_recognised", "sum(n.collateral_after_haircut)",
              ("collateral_after_haircut",), "haircut-adjusted allocated collateral"),
            C("exposure_at_default", "sum(n.exposure_at_default)",
              ("exposure_at_default",), "illustrative exposure measure"),
            C("as_of_date", f"date '{as_of}'", (), "reporting as-of date"),
        ],
        where="1 = 1 group by n.netting_eligible",
    )
    counts["rpt.netting_reconciliation"] = lineage.apply(
        con, netting, as_of_date=as_of, mode="replace")

    # -------------------------------------- classification disagreement
    # Where Finance and Risk categorise the same counterparty differently.
    # Published deliberately: a disagreement that is visible gets resolved, and
    # one that is silently overwritten becomes a finding two years later.
    disagreement = Mapping(
        rule_id="RPT-RECON-003", target_layer="REPORTING",
        target_table="sector_classification_disagreement", source_layer="CANONICAL",
        source_relation=f"""(
            with fin as (
                select arrangement_key as party_key, classification_value as accounting_sector
                from canon.classification
                where classification_scheme = 'COUNTERPARTY_SECTOR_ACCOUNTING'
                  and as_of_date = date '{as_of}'
            ),
            rsk as (
                select arrangement_key as party_key, classification_value as prudential_sector
                from canon.classification
                where classification_scheme = 'COUNTERPARTY_SECTOR_PRUDENTIAL'
                  and as_of_date = date '{as_of}'
            ),
            exposure as (
                select r.party_key,
                       sum(coalesce(p.carrying_amount, 0)) as total_carrying_amount,
                       count(*) as arrangement_count
                from canon.arrangement_party_role r
                join canon.position p
                  on p.arrangement_key = r.arrangement_key and p.as_of_date = r.as_of_date
                where r.as_of_date = date '{as_of}'
                group by r.party_key
            )
            select f.party_key, pty.legal_name, f.accounting_sector, k.prudential_sector,
                   coalesce(e.arrangement_count, 0)     as arrangement_count,
                   coalesce(e.total_carrying_amount, 0) as total_carrying_amount
            from fin f
            join rsk k using (party_key)
            left join canon.party pty
              on pty.party_key = f.party_key and pty.as_of_date = date '{as_of}'
            left join exposure e on e.party_key = f.party_key
            where f.accounting_sector <> k.prudential_sector
        ) d""",
        source_table_label="canon.classification",
        columns=[
            C("party_key", "d.party_key", ("canon.classification.arrangement_key",),
              "the counterparty both functions assessed"),
            C("legal_name", "d.legal_name", ("canon.party.legal_name",),
              "counterparty name for readability"),
            C("accounting_sector", "d.accounting_sector",
              ("canon.classification.classification_value",),
              "the Finance assessment under the accounting scheme"),
            C("prudential_sector", "d.prudential_sector",
              ("canon.classification.classification_value",),
              "the Risk assessment under the prudential scheme; deliberately not "
              "reconciled to the accounting one"),
            C("arrangement_count", "d.arrangement_count",
              ("canon.arrangement_party_role.arrangement_key",),
              "how many arrangements the disagreement touches"),
            C("total_carrying_amount", "d.total_carrying_amount",
              ("canon.position.carrying_amount",),
              "carrying amount affected, so the disagreement can be prioritised "
              "by materiality rather than by who complains loudest"),
            C("as_of_date", f"date '{as_of}'", (), "reporting as-of date"),
        ],
    )
    counts["rpt.sector_classification_disagreement"] = lineage.apply(
        con, disagreement, as_of_date=as_of, mode="replace")

    return counts
