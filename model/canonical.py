"""The canonical banking domain model.

One model. Two regulatory lenses. That is the whole argument of this
repository, and this file is where it is made concrete.

Design rules this model follows
-------------------------------
1. **Model the business concept, not the report.** ``arrangement`` exists
   because a bank enters into arrangements with parties. It does not exist
   because FINREP has a template that needs filling. Reports are views over
   the model; the moment the model starts to mirror a return, it will need
   rebuilding the next time that return changes.

2. **Shared facts once; contested measures per lens.** A trade's notional,
   currency and counterparty are facts — one place, one definition. Its
   carrying amount under an accounting classification and its exposure at
   default under a prudential approach are *assessments*, and the two
   functions legitimately disagree. Those live in ``classification`` and in
   the lens-specific layers, side by side, never averaged.

3. **Every entity has a business key, an owner and an as-of date.** The
   first because integration is impossible without one; the second because
   an unowned entity has no one to ask when it is wrong; the third because
   you will be asked to reproduce last quarter's submission.

4. **Supertype-subtype for products.** A loan, a deposit and a swap are all
   arrangements and share far more than they differ. The alternative — a
   table per product — makes every cross-product question a union of six
   queries and guarantees that the seventh product gets forgotten.

Standards enforced here are cross-referenced to
``governance/data-policy-standards.md`` in the ``ENTITY_METADATA`` block,
which the conformance linter reads.
"""

from __future__ import annotations

import duckdb

# ---------------------------------------------------------------------------
# Entity metadata
#
# This is not documentation-as-an-afterthought. The conformance linter reads
# this structure and fails the build when an entity lacks an owner, a business
# key or a definition (standards DP-01, DP-05, DP-11). Declaring it in code
# next to the DDL is what stops it drifting from reality.
# ---------------------------------------------------------------------------
ENTITY_METADATA: dict[str, dict] = {
    "party": {
        "owner": "Reference Data domain",
        "steward": "Counterparty Data Steward",
        "business_key": ["party_source_system", "party_source_id"],
        "definition": (
            "A legal entity or natural person with which the bank has, or may "
            "have, a relationship — customer, counterparty, issuer, guarantor "
            "or group parent. One row per party per as-of date."
        ),
        "golden_source": "Client and counterparty master",
        "regulatory_facing": True,
    },
    "party_hierarchy": {
        "owner": "Reference Data domain",
        "steward": "Counterparty Data Steward",
        "business_key": ["child_party_key", "parent_party_key", "hierarchy_type"],
        "definition": (
            "Directed parent-child relationships between parties. Separated from "
            "``party`` because a party sits in several hierarchies at once — legal "
            "ownership, risk grouping, accounting consolidation — and these do not "
            "agree with one another."
        ),
        "golden_source": "Client and counterparty master",
        "regulatory_facing": True,
    },
    "instrument": {
        "owner": "Reference Data domain",
        "steward": "Instrument Data Steward",
        "business_key": ["instrument_source_system", "instrument_source_id"],
        "definition": (
            "A financial instrument that can be held, traded or referenced — "
            "security, listed derivative, or the underlying of an OTC contract."
        ),
        "golden_source": "Instrument reference master",
        "regulatory_facing": True,
    },
    "arrangement": {
        "owner": "Product domains: Lending and Markets",
        "steward": "Arrangement Data Steward",
        "business_key": ["arrangement_source_system", "arrangement_source_id"],
        "definition": (
            "A contract between the bank and one or more parties: loan, deposit, "
            "bond holding, swap, option. The supertype carrying everything common "
            "to all products."
        ),
        "golden_source": "Originating product system",
        "regulatory_facing": True,
    },
    "arrangement_party_role": {
        "owner": "Product domains: Lending and Markets",
        "steward": "Arrangement Data Steward",
        "business_key": ["arrangement_key", "party_key", "role_type"],
        "definition": (
            "The parties to an arrangement and the role each plays — borrower, "
            "depositor, counterparty, guarantor, issuer. Modelled as a separate "
            "entity because an arrangement routinely has more than one party and "
            "a party's role is not a property of either side alone."
        ),
        "golden_source": "Originating product system",
        "regulatory_facing": True,
    },
    "trade_event": {
        "owner": "Markets domain",
        "steward": "Trade Lifecycle Steward",
        "business_key": ["event_source_system", "event_source_id"],
        "definition": (
            "A lifecycle event on an arrangement: inception, amendment, partial "
            "termination, exercise, maturity, default. Immutable once posted; "
            "corrections are new events, never updates."
        ),
        "golden_source": "Trade capture and lifecycle management",
        "regulatory_facing": True,
    },
    "position": {
        "owner": "Finance domain",
        "steward": "Position Data Steward",
        "business_key": ["arrangement_key", "as_of_date"],
        "definition": (
            "The measured state of an arrangement at a point in time: notional "
            "outstanding, carrying amount, fair value, accrued interest. One row "
            "per arrangement per as-of date."
        ),
        "golden_source": "Finance sub-ledger",
        "regulatory_facing": True,
    },
    "collateral": {
        "owner": "Collateral domain",
        "steward": "Collateral Data Steward",
        "business_key": ["collateral_source_system", "collateral_source_id"],
        "definition": (
            "An asset pledged to secure one or more arrangements, with its "
            "valuation and applicable haircut."
        ),
        "golden_source": "Collateral management",
        "regulatory_facing": True,
    },
    "collateral_allocation": {
        "owner": "Collateral domain",
        "steward": "Collateral Data Steward",
        "business_key": ["collateral_key", "arrangement_key", "as_of_date"],
        "definition": (
            "How collateral value is allocated across the arrangements it secures. "
            "Separate from ``collateral`` because one asset can secure many "
            "arrangements and the split is itself a measured, changing fact."
        ),
        "golden_source": "Collateral management",
        "regulatory_facing": True,
    },
    "netting_set": {
        "owner": "Risk domain",
        "steward": "Counterparty Risk Steward",
        "business_key": ["netting_set_source_system", "netting_set_source_id"],
        "definition": (
            "A set of transactions with a single counterparty subject to a legally "
            "enforceable netting agreement. A risk-domain concept with no direct "
            "equivalent in the accounting view — see ADR-0002."
        ),
        "golden_source": "Legal agreements and risk systems",
        "regulatory_facing": True,
    },
    "classification": {
        "owner": "Shared: Finance and Risk",
        "steward": "Finance Data Steward and Risk Data Steward jointly",
        "business_key": ["arrangement_key", "classification_scheme", "as_of_date"],
        "definition": (
            "An assessment of an arrangement under a named scheme — accounting "
            "measurement category, impairment stage, prudential exposure class, "
            "counterparty sector. Deliberately one row per scheme rather than one "
            "wide row, so that Finance and Risk can disagree without either "
            "overwriting the other."
        ),
        "golden_source": "The function that owns the scheme",
        "regulatory_facing": True,
    },
}


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------
DDL = """
create schema if not exists canon;

-- ------------------------------------------------------------------ PARTY
create table if not exists canon.party (
    party_key             varchar not null,   -- deterministic hash of the business key
    party_source_system   varchar not null,
    party_source_id       varchar not null,
    as_of_date            date    not null,
    legal_name            varchar,
    lei                   varchar,            -- Legal Entity Identifier, where one exists
    country_of_incorporation varchar,
    -- Sector is held as the source's own classification. The *regulatory*
    -- and *accounting* counterparty categorisations are assessments and live
    -- in canon.classification, because Finance and Risk do not always agree
    -- on how a given counterparty should be categorised.
    source_sector_code    varchar,
    is_financial_institution boolean,
    is_group_entity       boolean,            -- intragroup: excluded from some returns
    primary key (party_key, as_of_date)
);

create table if not exists canon.party_hierarchy (
    child_party_key   varchar not null,
    parent_party_key  varchar not null,
    hierarchy_type    varchar not null,       -- LEGAL_OWNERSHIP | RISK_GROUP | ACCOUNTING_CONSOLIDATION
    as_of_date        date    not null,
    ownership_pct     decimal(9,4),
    primary key (child_party_key, parent_party_key, hierarchy_type, as_of_date)
);

-- ------------------------------------------------------------- INSTRUMENT
create table if not exists canon.instrument (
    instrument_key           varchar not null,
    instrument_source_system varchar not null,
    instrument_source_id     varchar not null,
    as_of_date               date    not null,
    isin                     varchar,
    instrument_type          varchar,         -- BOND | EQUITY | IR_SWAP | FX_OPTION | ...
    issuer_party_key         varchar,
    currency                 varchar,
    maturity_date            date,
    primary key (instrument_key, as_of_date)
);

-- ------------------------------------------------------------ ARRANGEMENT
-- The supertype. Everything the bank contracts into is an arrangement.
create table if not exists canon.arrangement (
    arrangement_key           varchar not null,
    arrangement_source_system varchar not null,
    arrangement_source_id     varchar not null,
    as_of_date                date    not null,
    product_family            varchar,        -- LOAN | DEPOSIT | SECURITY | DERIVATIVE
    product_type              varchar,        -- TERM_LOAN | REVOLVING | CURRENT_ACCOUNT | IR_SWAP | ...
    currency                  varchar,
    inception_date            date,
    maturity_date             date,
    original_notional         decimal(20,2),
    status                    varchar,        -- ACTIVE | MATURED | TERMINATED | DEFAULTED
    booking_entity_party_key  varchar,        -- which legal entity of the bank booked it
    instrument_key            varchar,        -- populated for securities and listed derivatives
    netting_set_key           varchar,        -- populated for derivatives under a netting agreement
    primary key (arrangement_key, as_of_date)
);

create table if not exists canon.arrangement_party_role (
    arrangement_key varchar not null,
    party_key       varchar not null,
    role_type       varchar not null,         -- BORROWER | DEPOSITOR | COUNTERPARTY | GUARANTOR | ISSUER
    as_of_date      date    not null,
    primary key (arrangement_key, party_key, role_type, as_of_date)
);

-- ------------------------------------------------------------ TRADE EVENT
-- Immutable lifecycle events. A correction is a new event, never an update:
-- "what did we believe on the reporting date" must stay answerable.
create table if not exists canon.trade_event (
    event_key           varchar not null,
    event_source_system varchar not null,
    event_source_id     varchar not null,
    arrangement_key     varchar not null,
    event_type          varchar,              -- INCEPTION | AMENDMENT | PARTIAL_TERMINATION | EXERCISE | MATURITY | DEFAULT
    -- Two dates, deliberately. The economic event date and the accounting
    -- recognition date differ routinely, and conflating them is a classic
    -- source of Finance and Risk reporting different populations for the
    -- same period. See architecture/domain-data-flows.md.
    economic_event_date date,
    accounting_date     date,
    notional_delta      decimal(20,2),
    primary key (event_key)
);

-- --------------------------------------------------------------- POSITION
create table if not exists canon.position (
    arrangement_key      varchar not null,
    as_of_date           date    not null,
    notional_outstanding decimal(20,2),
    carrying_amount      decimal(20,2),       -- accounting measure, Finance-owned
    fair_value           decimal(20,2),       -- mark to market where applicable
    accrued_interest     decimal(20,2),
    impairment_allowance decimal(20,2),
    currency             varchar,
    primary key (arrangement_key, as_of_date)
);

-- ------------------------------------------------------------- COLLATERAL
create table if not exists canon.collateral (
    collateral_key           varchar not null,
    collateral_source_system varchar not null,
    collateral_source_id     varchar not null,
    as_of_date               date    not null,
    collateral_type          varchar,         -- CASH | GOVERNMENT_BOND | EQUITY | PROPERTY
    currency                 varchar,
    market_value             decimal(20,2),
    haircut_pct              decimal(9,4),
    is_financial_collateral  boolean,
    primary key (collateral_key, as_of_date)
);

create table if not exists canon.collateral_allocation (
    collateral_key   varchar not null,
    arrangement_key  varchar not null,
    as_of_date       date    not null,
    allocated_value  decimal(20,2),
    primary key (collateral_key, arrangement_key, as_of_date)
);

-- ------------------------------------------------------------ NETTING SET
create table if not exists canon.netting_set (
    netting_set_key           varchar not null,
    netting_set_source_system varchar not null,
    netting_set_source_id     varchar not null,
    as_of_date                date    not null,
    counterparty_party_key    varchar,
    agreement_type            varchar,        -- MASTER_NETTING | CSA | NONE
    is_legally_enforceable    boolean,        -- the whole point: unenforceable netting is not netting
    primary key (netting_set_key, as_of_date)
);

-- ---------------------------------------------------------- CLASSIFICATION
-- The entity that makes "one model, two lenses" possible.
--
-- One row per (arrangement, scheme, as-of date). Finance's measurement
-- category and Risk's exposure class are different schemes, stored side by
-- side. Neither overwrites the other; neither is blended into a single
-- "the classification" column. Where they imply different populations, that
-- difference is reportable rather than hidden — see ADR-0002.
create table if not exists canon.classification (
    arrangement_key      varchar not null,
    classification_scheme varchar not null,   -- ACCOUNTING_MEASUREMENT | IMPAIRMENT_STAGE
                                              -- | PRUDENTIAL_EXPOSURE_CLASS | COUNTERPARTY_SECTOR_ACCOUNTING
                                              -- | COUNTERPARTY_SECTOR_PRUDENTIAL
    as_of_date           date    not null,
    classification_value varchar,
    assessed_by_domain   varchar,             -- FINANCE | RISK — who owns this assessment
    primary key (arrangement_key, classification_scheme, as_of_date)
);
"""


def create_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create the canonical schema."""
    con.execute(DDL)


def canonical_tables() -> list[str]:
    """Names of the canonical entities, in dependency order."""
    return list(ENTITY_METADATA.keys())


def business_key(entity: str) -> list[str]:
    """The declared business key columns for an entity."""
    return ENTITY_METADATA[entity]["business_key"]
