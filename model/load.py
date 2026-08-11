"""Source systems to the canonical model, with lineage recorded on the way.

Every function here returns after having done two things inseparably: moved
data, and declared where it came from. See ``lineage.py`` for why that is one
operation rather than two.

The interesting problem in this file is not the copying. It is **identity**:
the same legal entity arrives as a customer number from core banking, a
counterparty code from trade capture, and a party identifier from the
reference master, and nothing but the LEI reliably connects them. Resolve that
wrongly and one counterparty silently becomes two — which understates every
concentration measure in the bank while every individual number still looks
plausible.
"""

from __future__ import annotations

import logging

import duckdb

from . import lineage
from .lineage import ColumnMapping as C
from .lineage import Mapping

LOGGER = logging.getLogger(__name__)

# Deterministic surrogate key. A hash of the business key rather than a
# sequence, so a rebuild produces the same keys and existing outputs stay
# joinable (standard DP-06).
def key(*parts: str) -> str:
    joined = ", ".join(f"coalesce(upper(trim(cast({p} as varchar))), '^^')" for p in parts)
    return f"substr(sha256(concat_ws('||', {joined})), 1, 24)"


def register_extracts(con: duckdb.DuckDBPyConnection, extracts_dir) -> None:
    """Expose the CSV extracts as ``src_*`` views.

    In a real deployment this is the landing zone — external tables, an
    ingestion stream, or a staging schema. Nothing downstream depends on which.
    """
    con.execute("create schema if not exists src")
    for name in ("REF_party", "REF_party_hierarchy", "REF_instrument",
                 "CBS_customer", "CBS_account",
                 "TRD_counterparty", "TRD_netting_agreement", "TRD_trade", "TRD_event",
                 "FIN_position", "FIN_classification", "COL_collateral", "COL_allocation"):
        path = (extracts_dir / f"{name}.csv").as_posix()
        con.execute(
            f"create or replace view src.{name.lower()} as "
            f"select * from read_csv_auto('{path}', header=true, all_varchar=true)"
        )


# ---------------------------------------------------------------------------
# Identity resolution
# ---------------------------------------------------------------------------
def resolve_party_identity(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Build the cross-reference from every source's party identifier to one key.

    Resolution order, most to least reliable — and the order itself is the
    architectural decision, recorded so that a reviewer can challenge it:

    1. **LEI.** A globally issued identifier for the legal entity. Where both
       sides carry one, this is definitive.
    2. **Normalised legal name and country.** Used only where an LEI is absent.
       Weaker, and known to fail on renamed entities and on subsidiaries with
       near-identical names, so every match made this way is *flagged* rather
       than silently accepted.
    3. **Unresolved.** Deliberately kept as a visible category. A source record
       that cannot be tied to a party is a data-quality issue for a steward,
       not something to be quietly dropped or invented.

    The counted output of each method is returned so the run log can show the
    mix. A rise in name-matched or unresolved parties is the early warning that
    reference data is degrading.
    """
    con.execute("create schema if not exists stg")
    con.execute(f"""
        create or replace table stg.party_xref as
        with ref as (
            select src_party_id, {key('src_party_id')} as party_key,
                   nullif(trim(lei), '') as lei,
                   upper(trim(legal_name)) as norm_name, upper(trim(country)) as country
            from src.ref_party
        ),
        externals as (
            select 'CBS' as source_system, cbs_customer_id as source_id,
                   nullif(trim(lei), '') as lei,
                   upper(trim(customer_name)) as norm_name, upper(trim(country)) as country
            from src.cbs_customer
            union all
            select 'TRD', trd_counterparty_id, nullif(trim(lei), ''),
                   upper(trim(counterparty_name)), upper(trim(country))
            from src.trd_counterparty
        ),
        by_lei as (
            select e.source_system, e.source_id, r.party_key, 'LEI' as resolution_method
            from externals e join ref r on r.lei = e.lei and e.lei is not null
        ),
        by_name as (
            select e.source_system, e.source_id, r.party_key,
                   'NAME_COUNTRY' as resolution_method
            from externals e
            join ref r on r.norm_name = e.norm_name and r.country = e.country
            where e.lei is null
              and not exists (select 1 from by_lei b
                              where b.source_system = e.source_system
                                and b.source_id = e.source_id)
        ),
        matched as (select * from by_lei union all select * from by_name),
        unresolved as (
            select e.source_system, e.source_id, null as party_key,
                   'UNRESOLVED' as resolution_method
            from externals e
            where not exists (select 1 from matched m
                              where m.source_system = e.source_system
                                and m.source_id = e.source_id)
        )
        select * from matched
        union all select * from unresolved
        union all
        -- the reference master resolves to itself
        select 'REF', src_party_id, party_key, 'NATIVE' from ref
    """)
    rows = con.execute(
        "select resolution_method, count(*) from stg.party_xref group by 1 order by 2 desc"
    ).fetchall()
    return {m: n for m, n in rows}


# ---------------------------------------------------------------------------
# Canonical loads
# ---------------------------------------------------------------------------
def load_party(con, as_of: str) -> int:
    m = Mapping(
        rule_id="LD-PARTY-001", target_layer="CANONICAL", target_table="party",
        source_layer="SOURCE", source_relation="src.ref_party",
        source_table_label="REF_party",
        columns=[
            C("party_key", key("src_party_id"), ("src_party_id",),
              "deterministic sha256 hash of the source business key"),
            C("party_source_system", "'REF'", (), "constant: golden source for party"),
            C("party_source_id", "src_party_id", ("src_party_id",)),
            C("as_of_date", f"date '{as_of}'", (), "reporting as-of date applied at load"),
            C("legal_name", "trim(legal_name)", ("legal_name",), "trimmed"),
            C("lei", "nullif(trim(lei), '')", ("lei",), "empty string normalised to null"),
            C("country_of_incorporation", "upper(trim(country))", ("country",), "upper-cased"),
            C("source_sector_code", "upper(trim(sector_code))", ("sector_code",),
              "source sector retained as-is; regulatory and accounting sector "
              "assessments are held separately in canon.classification"),
            C("is_financial_institution", "is_financial_institution = 'Y'",
              ("is_financial_institution",), "Y/N flag cast to boolean"),
            C("is_group_entity", "is_group_entity = 'Y'", ("is_group_entity",),
              "Y/N flag cast to boolean"),
        ],
    )
    return lineage.apply(con, m, as_of_date=as_of)


def load_party_hierarchy(con, as_of: str) -> int:
    """Parent-child relationships between parties, one row per hierarchy.

    Kept as a separate entity rather than a ``parent_party_key`` column on
    ``party``, because a party sits in several hierarchies at once and they do
    not agree. A column forces a choice between them and hides that a choice
    was made; a table lets both be true and lets a query say which one it is
    using. That distinction is the difference between a connected-clients
    measure that can be defended and one that cannot.
    """
    m = Mapping(
        rule_id="LD-PARTYHIER-001", target_layer="CANONICAL",
        target_table="party_hierarchy", source_layer="SOURCE",
        source_relation="src.ref_party_hierarchy", source_table_label="REF_party_hierarchy",
        columns=[
            C("child_party_key", key("child_src_party_id"), ("child_src_party_id",),
              "child resolved to the party hash key"),
            C("parent_party_key", key("parent_src_party_id"), ("parent_src_party_id",),
              "parent resolved to the party hash key"),
            C("hierarchy_type", "upper(trim(hierarchy_type))", ("hierarchy_type",),
              "LEGAL_OWNERSHIP is a fact about share registers; RISK_GROUP is a "
              "judgement about who fails together. Held side by side because a "
              "bank needs both and they legitimately differ"),
            C("as_of_date", f"date '{as_of}'", (), "reporting as-of date applied at load"),
            C("ownership_pct", "try_cast(nullif(trim(ownership_pct), '') as decimal(9,4))",
              ("ownership_pct",),
              "populated for legal ownership only; a risk grouping has no "
              "percentage, and inventing one would imply a precision the "
              "judgement does not have"),
        ],
    )
    return lineage.apply(con, m, as_of_date=as_of)


def load_instrument(con, as_of: str) -> int:
    m = Mapping(
        rule_id="LD-INSTR-001", target_layer="CANONICAL", target_table="instrument",
        source_layer="SOURCE", source_relation="src.ref_instrument",
        source_table_label="REF_instrument",
        columns=[
            C("instrument_key", key("src_instrument_id"), ("src_instrument_id",),
              "deterministic hash of the source business key"),
            C("instrument_source_system", "'REF'", ()),
            C("instrument_source_id", "src_instrument_id", ("src_instrument_id",)),
            C("as_of_date", f"date '{as_of}'", ()),
            C("isin", "nullif(trim(isin), '')", ("isin",)),
            C("instrument_type", "upper(trim(instrument_type))", ("instrument_type",)),
            C("issuer_party_key", key("issuer_src_party_id"), ("issuer_src_party_id",),
              "issuer resolved to the party hash key"),
            C("currency", "upper(trim(currency))", ("currency",)),
            C("maturity_date", "try_cast(maturity_date as date)", ("maturity_date",)),
        ],
    )
    return lineage.apply(con, m, as_of_date=as_of)


def load_arrangements_from_core_banking(con, as_of: str) -> int:
    """Loans and deposits. Counterparty resolved through the identity xref."""
    m = Mapping(
        rule_id="LD-ARR-CBS-001", target_layer="CANONICAL", target_table="arrangement",
        source_layer="SOURCE",
        source_relation="src.cbs_account a "
                        "left join stg.party_xref x "
                        "  on x.source_system = 'CBS' and x.source_id = a.cbs_customer_id",
        source_table_label="CBS_account",
        columns=[
            C("arrangement_key", key("'CBS'", "a.account_id"), ("account_id",),
              "hash of source system and account id; system included because "
              "account numbers are not unique across the estate"),
            C("arrangement_source_system", "'CBS'", ()),
            C("arrangement_source_id", "a.account_id", ("account_id",)),
            C("as_of_date", f"date '{as_of}'", ()),
            C("product_family", "upper(trim(a.product_family))", ("product_family",)),
            C("product_type", "upper(trim(a.product_type))", ("product_type",)),
            C("currency", "upper(trim(a.currency))", ("currency",)),
            C("inception_date", "try_cast(a.open_date as date)", ("open_date",)),
            C("maturity_date", "try_cast(a.maturity_date as date)", ("maturity_date",)),
            C("original_notional", "try_cast(a.original_principal as decimal(20,2))",
              ("original_principal",)),
            C("status", "upper(trim(a.status))", ("status",)),
            C("booking_entity_party_key", "null", (), "not held in this extract"),
            C("instrument_key", "null", (), "loans and deposits are not instrument-backed"),
            C("netting_set_key", "null", (),
              "netting is a derivatives concept; deliberately null here"),
        ],
    )
    return lineage.apply(con, m, as_of_date=as_of)


def load_arrangements_from_trading(con, as_of: str) -> int:
    """Derivatives."""
    m = Mapping(
        rule_id="LD-ARR-TRD-001", target_layer="CANONICAL", target_table="arrangement",
        source_layer="SOURCE", source_relation="src.trd_trade t",
        source_table_label="TRD_trade",
        columns=[
            C("arrangement_key", key("'TRD'", "t.trade_id"), ("trade_id",),
              "hash of source system and trade id"),
            C("arrangement_source_system", "'TRD'", ()),
            C("arrangement_source_id", "t.trade_id", ("trade_id",)),
            C("as_of_date", f"date '{as_of}'", ()),
            C("product_family", "'DERIVATIVE'", (), "constant for this source"),
            C("product_type", "upper(trim(t.product_type))", ("product_type",)),
            C("currency", "upper(trim(t.currency))", ("currency",)),
            C("inception_date", "try_cast(t.trade_date as date)", ("trade_date",)),
            C("maturity_date", "try_cast(t.maturity_date as date)", ("maturity_date",)),
            C("original_notional", "try_cast(t.notional as decimal(20,2))", ("notional",)),
            C("status", "upper(trim(t.status))", ("status",)),
            C("booking_entity_party_key", "null", ()),
            C("instrument_key",
              "case when nullif(trim(t.src_instrument_id), '') is null then null "
              f"else {key('t.src_instrument_id')} end", ("src_instrument_id",),
              "populated only where the trade references a reference instrument"),
            C("netting_set_key",
              "case when nullif(trim(t.netting_agreement_id), '') is null then null "
              f"else {key('t.netting_agreement_id')} end", ("netting_agreement_id",),
              "hash of the netting agreement id where one applies"),
        ],
    )
    return lineage.apply(con, m, as_of_date=as_of)


def load_arrangement_party_roles(con, as_of: str) -> int:
    total = 0
    total += lineage.apply(con, Mapping(
        rule_id="LD-APR-CBS-001", target_layer="CANONICAL",
        target_table="arrangement_party_role", source_layer="SOURCE",
        source_relation="src.cbs_account a "
                        "join stg.party_xref x on x.source_system = 'CBS' "
                        "  and x.source_id = a.cbs_customer_id "
                        "where x.party_key is not null",
        source_table_label="CBS_account",
        columns=[
            C("arrangement_key", key("'CBS'", "a.account_id"), ("account_id",)),
            C("party_key", "x.party_key", ("cbs_customer_id",),
              "resolved via stg.party_xref on LEI, falling back to name and country"),
            C("role_type",
              "case when upper(a.product_family) = 'LOAN' then 'BORROWER' else 'DEPOSITOR' end",
              ("product_family",), "role derived from product family"),
            C("as_of_date", f"date '{as_of}'", ()),
        ]), as_of_date=as_of)

    total += lineage.apply(con, Mapping(
        rule_id="LD-APR-TRD-001", target_layer="CANONICAL",
        target_table="arrangement_party_role", source_layer="SOURCE",
        source_relation="src.trd_trade t "
                        "join stg.party_xref x on x.source_system = 'TRD' "
                        "  and x.source_id = t.trd_counterparty_id "
                        "where x.party_key is not null",
        source_table_label="TRD_trade",
        columns=[
            C("arrangement_key", key("'TRD'", "t.trade_id"), ("trade_id",)),
            C("party_key", "x.party_key", ("trd_counterparty_id",),
              "resolved via stg.party_xref"),
            C("role_type", "'COUNTERPARTY'", ()),
            C("as_of_date", f"date '{as_of}'", ()),
        ]), as_of_date=as_of)
    return total


def load_netting_sets(con, as_of: str) -> int:
    m = Mapping(
        rule_id="LD-NETSET-001", target_layer="CANONICAL", target_table="netting_set",
        source_layer="SOURCE",
        source_relation="src.trd_netting_agreement n "
                        "left join stg.party_xref x on x.source_system = 'TRD' "
                        "  and x.source_id = n.trd_counterparty_id",
        source_table_label="TRD_netting_agreement",
        columns=[
            C("netting_set_key", key("n.netting_agreement_id"), ("netting_agreement_id",)),
            C("netting_set_source_system", "'TRD'", ()),
            C("netting_set_source_id", "n.netting_agreement_id", ("netting_agreement_id",)),
            C("as_of_date", f"date '{as_of}'", ()),
            C("counterparty_party_key", "x.party_key", ("trd_counterparty_id",),
              "resolved via stg.party_xref"),
            C("agreement_type", "upper(trim(n.agreement_type))", ("agreement_type",)),
            C("is_legally_enforceable", "n.is_legally_enforceable = 'Y'",
              ("is_legally_enforceable",),
              "Y/N cast to boolean; unenforceable agreements must not be netted"),
        ],
    )
    return lineage.apply(con, m, as_of_date=as_of)


def load_trade_events(con, as_of: str) -> int:
    m = Mapping(
        rule_id="LD-EVENT-001", target_layer="CANONICAL", target_table="trade_event",
        source_layer="SOURCE", source_relation="src.trd_event e",
        source_table_label="TRD_event",
        columns=[
            C("event_key", key("e.event_id"), ("event_id",)),
            C("event_source_system", "'TRD'", ()),
            C("event_source_id", "e.event_id", ("event_id",)),
            C("arrangement_key", key("'TRD'", "e.trade_id"), ("trade_id",)),
            C("event_type", "upper(trim(e.event_type))", ("event_type",)),
            C("economic_event_date", "try_cast(e.economic_event_date as date)",
              ("economic_event_date",),
              "the date the economic event occurred; drives the risk population"),
            C("accounting_date", "try_cast(e.accounting_date as date)", ("accounting_date",),
              "the date of accounting recognition; drives the finance population. "
              "Deliberately kept distinct from the economic date"),
            C("notional_delta", "try_cast(e.notional_delta as decimal(20,2))",
              ("notional_delta",)),
        ],
    )
    return lineage.apply(con, m, as_of_date=as_of)


def load_positions(con, as_of: str) -> int:
    m = Mapping(
        rule_id="LD-POS-001", target_layer="CANONICAL", target_table="position",
        source_layer="SOURCE", source_relation="src.fin_position p",
        source_table_label="FIN_position",
        columns=[
            C("arrangement_key", key("p.source_system", "p.contract_ref"),
              ("source_system", "contract_ref"),
              "hashed on the same convention as the arrangement, so positions "
              "join to arrangements regardless of which system booked them"),
            C("as_of_date", "try_cast(p.as_of_date as date)", ("as_of_date",)),
            C("notional_outstanding", "try_cast(p.notional_outstanding as decimal(20,2))",
              ("notional_outstanding",)),
            C("carrying_amount", "try_cast(p.carrying_amount as decimal(20,2))",
              ("carrying_amount",), "accounting carrying amount as supplied by Finance"),
            C("fair_value", "try_cast(nullif(p.fair_value, '') as decimal(20,2))",
              ("fair_value",), "empty string normalised to null; not all products are marked"),
            C("accrued_interest", "try_cast(p.accrued_interest as decimal(20,2))",
              ("accrued_interest",)),
            C("impairment_allowance", "try_cast(p.impairment_allowance as decimal(20,2))",
              ("impairment_allowance",)),
            C("currency", "upper(trim(p.currency))", ("currency",)),
        ],
    )
    return lineage.apply(con, m, as_of_date=as_of)


def load_classifications(con, as_of: str) -> int:
    """Assessments from both Finance and Risk, side by side.

    Note the key: (arrangement, scheme, as-of). Two functions can assess the
    same thing under different schemes without either overwriting the other.
    That is the storage decision that makes ADR-0002 possible.
    """
    m = Mapping(
        rule_id="LD-CLASS-001", target_layer="CANONICAL", target_table="classification",
        source_layer="SOURCE", source_relation="src.fin_classification c",
        source_table_label="FIN_classification",
        columns=[
            # Party-level assessments (counterparty sector) are keyed on the
            # party, arrangement-level ones on the arrangement. They share a
            # table because they share a shape -- an assessment under a named
            # scheme, owned by a domain, valid at a date -- and separating them
            # would mean two loaders and two sets of drift.
            C("arrangement_key",
              f"case when c.source_system = 'REF' then {key('c.contract_ref')} "
              f"else {key('c.source_system', 'c.contract_ref')} end",
              ("source_system", "contract_ref"),
              "party-level assessments key on the party; arrangement-level "
              "assessments key on the arrangement, using each one's own convention"),
            C("classification_scheme", "upper(trim(c.classification_scheme))",
              ("classification_scheme",)),
            C("as_of_date", "try_cast(c.as_of_date as date)", ("as_of_date",)),
            C("classification_value", "upper(trim(c.classification_value))",
              ("classification_value",)),
            C("assessed_by_domain", "upper(trim(c.assessed_by_domain))",
              ("assessed_by_domain",),
              "which function owns this assessment; never blended across domains"),
        ],
    )
    return lineage.apply(con, m, as_of_date=as_of)


def load_collateral(con, as_of: str) -> int:
    total = lineage.apply(con, Mapping(
        rule_id="LD-COL-001", target_layer="CANONICAL", target_table="collateral",
        source_layer="SOURCE", source_relation="src.col_collateral c",
        source_table_label="COL_collateral",
        columns=[
            C("collateral_key", key("c.collateral_id"), ("collateral_id",)),
            C("collateral_source_system", "'COL'", ()),
            C("collateral_source_id", "c.collateral_id", ("collateral_id",)),
            C("as_of_date", f"date '{as_of}'", ()),
            C("collateral_type", "upper(trim(c.collateral_type))", ("collateral_type",)),
            C("currency", "upper(trim(c.currency))", ("currency",)),
            C("market_value", "try_cast(c.market_value as decimal(20,2))", ("market_value",)),
            C("haircut_pct", "try_cast(c.haircut_pct as decimal(9,4))", ("haircut_pct",),
              "supervisory or internal haircut as supplied by collateral management"),
            C("is_financial_collateral", "c.is_financial_collateral = 'Y'",
              ("is_financial_collateral",)),
        ]), as_of_date=as_of)

    total += lineage.apply(con, Mapping(
        rule_id="LD-COLALLOC-001", target_layer="CANONICAL",
        target_table="collateral_allocation", source_layer="SOURCE",
        source_relation="src.col_allocation a "
                        "join src.trd_trade t on t.trade_id = a.contract_ref",
        source_table_label="COL_allocation",
        columns=[
            C("collateral_key", key("a.collateral_id"), ("collateral_id",)),
            C("arrangement_key", key("'TRD'", "a.contract_ref"), ("contract_ref",),
              "allocation rows for trades; core-banking allocations load separately"),
            C("as_of_date", "try_cast(a.as_of_date as date)", ("as_of_date",)),
            C("allocated_value", "try_cast(a.allocated_value as decimal(20,2))",
              ("allocated_value",),
              "the share of the asset's value attributed to this arrangement, "
              "because one asset can secure several"),
        ]), as_of_date=as_of)

    total += lineage.apply(con, Mapping(
        rule_id="LD-COLALLOC-002", target_layer="CANONICAL",
        target_table="collateral_allocation", source_layer="SOURCE",
        source_relation="src.col_allocation a "
                        "join src.cbs_account c on c.account_id = a.contract_ref",
        source_table_label="COL_allocation",
        columns=[
            C("collateral_key", key("a.collateral_id"), ("collateral_id",)),
            C("arrangement_key", key("'CBS'", "a.contract_ref"), ("contract_ref",)),
            C("as_of_date", "try_cast(a.as_of_date as date)", ("as_of_date",)),
            C("allocated_value", "try_cast(a.allocated_value as decimal(20,2))",
              ("allocated_value",)),
        ]), as_of_date=as_of)
    return total


def load_all(con: duckdb.DuckDBPyConnection, as_of: str) -> list[tuple[str, int]]:
    """Run every canonical load in dependency order."""
    steps = [
        ("canon.party", load_party),
        ("canon.party_hierarchy", load_party_hierarchy),
        ("canon.instrument", load_instrument),
        ("canon.arrangement (core banking)", load_arrangements_from_core_banking),
        ("canon.arrangement (trading)", load_arrangements_from_trading),
        ("canon.arrangement_party_role", load_arrangement_party_roles),
        ("canon.netting_set", load_netting_sets),
        ("canon.trade_event", load_trade_events),
        ("canon.position", load_positions),
        ("canon.classification", load_classifications),
        ("canon.collateral", load_collateral),
    ]
    return [(label, fn(con, as_of)) for label, fn in steps]
