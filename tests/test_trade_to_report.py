"""Tests for the claims this repository makes.

Every assertion here corresponds to something the README or the governance
documents assert out loud. That is the point: a reference architecture whose
claims are not executable is a slide deck with syntax highlighting.

The tests fall into five groups.

1. **The canonical model holds.** Keys are unique, nothing is orphaned, the
   as-of date does what it says.
2. **The finance lens applies the accounting rules**, including the sign test
   that quietly overstates assets when it is missed.
3. **The risk lens applies the prudential rules**, including the one that
   matters most — netting is a legal fact before it is a calculation.
4. **Lineage is sufficient**, in the specific sense DP-19 defines: every
   reporting column traces to a system of record, and the trace is a query.
5. **The conformance linter actually catches things.** This last group is the
   one most often missing. A linter with no negative tests passes because it
   checks nothing, and nobody finds out until an auditor does.

Run:

    pytest -q                      # against a warehouse built once per session
    pytest -q -k netting           # one theme
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from conformance import check as conformance  # noqa: E402
from model import canonical, lineage, load  # noqa: E402
from reporting import ccr, finrep, reconciliation  # noqa: E402

AS_OF = "2026-03-31"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def warehouse(tmp_path_factory) -> Path:
    """Build the whole thing once, from scratch, in a throwaway directory.

    Deliberately not reusing the developer's ``warehouse.duckdb``: a test suite
    that passes only against a database somebody built by hand last Tuesday is
    testing that Tuesday, not the code.
    """
    workdir = tmp_path_factory.mktemp("t2r")
    extracts = workdir / "extracts"
    db = workdir / "warehouse.duckdb"

    sys.path.insert(0, str(REPO / "data"))
    from generate_banking_data import generate  # noqa: E402

    generate(extracts)

    con = duckdb.connect(str(db))
    canonical.create_schema(con)
    lineage.create_schema(con)
    load.register_extracts(con, extracts)
    load.resolve_party_identity(con)
    load.load_all(con, AS_OF)
    finrep.build(con, AS_OF)
    ccr.build(con, AS_OF)
    reconciliation.build(con, AS_OF)
    con.close()
    return db


@pytest.fixture(scope="session")
def con(warehouse):
    c = duckdb.connect(str(warehouse), read_only=True)
    yield c
    c.close()


def q(con, sql: str):
    return con.execute(sql).fetchall()


def one(con, sql: str):
    return con.execute(sql).fetchone()[0]


# ---------------------------------------------------------------------------
# 1 · The canonical model holds
# ---------------------------------------------------------------------------
class TestCanonicalModel:
    def test_every_entity_was_populated(self, con):
        """An empty canonical table is a silent failure, not a small one."""
        empty = [
            entity for entity in canonical.ENTITY_METADATA
            if one(con, f"select count(*) from canon.{entity}") == 0
        ]
        assert not empty, f"canonical entities loaded zero rows: {empty}"

    @pytest.mark.parametrize("entity", sorted(canonical.ENTITY_METADATA))
    def test_declared_business_key_is_actually_unique(self, con, entity):
        """DP-05 declares a business key. This checks the declaration is true.

        A business key documented but not enforced is the origin of most
        duplicate-counting incidents: the model says one row per contract, the
        data says otherwise, and nobody looks until a total is wrong.
        """
        meta = canonical.ENTITY_METADATA[entity]
        key = list(meta["business_key"])
        cols = {r[0] for r in q(con, "select column_name from information_schema.columns "
                                    f"where table_schema='canon' and table_name='{entity}'")}
        if "as_of_date" in cols and "as_of_date" not in key:
            key.append("as_of_date")
        key_sql = ", ".join(key)
        dupes = one(con, f"""
            select count(*) from (
                select {key_sql} from canon.{entity}
                group by {key_sql} having count(*) > 1
            )
        """)
        assert dupes == 0, f"canon.{entity}: {dupes} duplicate business keys on ({key_sql})"

    def test_the_whole_pipeline_is_idempotent(self, warehouse, tmp_path):
        """Re-running a reporting date must not duplicate it.

        DP-29 requires a submitted report to be exactly reproducible. A
        pipeline that cannot be re-run without doubling its totals is not
        reproducible; it is a pipeline you get one attempt at, on the evening
        of a submission deadline. Asserted by running the loads a second time
        against a built warehouse and checking every count is unchanged.
        """
        import shutil
        target = tmp_path / "rerun.duckdb"
        shutil.copy(warehouse, target)
        c = duckdb.connect(str(target))

        before = {e: one(c, f"select count(*) from canon.{e}") for e in canonical.ENTITY_METADATA}
        load.load_all(c, AS_OF)
        after = {e: one(c, f"select count(*) from canon.{e}") for e in canonical.ENTITY_METADATA}
        c.close()

        grew = {e: (before[e], after[e]) for e in before if before[e] != after[e]}
        assert not grew, f"a second load changed row counts: {grew}"

    def test_no_orphaned_positions(self, con):
        """A position without an arrangement is an exposure nobody owns."""
        orphans = one(con, """
            select count(*) from canon.position p
            left join canon.arrangement a
              on a.arrangement_key = p.arrangement_key and a.as_of_date = p.as_of_date
            where a.arrangement_key is null
        """)
        assert orphans == 0

    def test_no_orphaned_collateral_allocations(self, con):
        """Collateral allocated to nothing is either a bug or an overstatement."""
        orphans = one(con, """
            select count(*) from canon.collateral_allocation ca
            left join canon.collateral c
              on c.collateral_key = ca.collateral_key and c.as_of_date = ca.as_of_date
            where c.collateral_key is null
        """)
        assert orphans == 0

    def test_a_party_can_sit_in_two_hierarchies_that_disagree(self, con):
        """Friction 8, and the reason ``party_hierarchy`` is a table.

        Legal ownership and risk grouping are different questions. If the model
        could hold only one answer, a connected-clients measure would be run
        against whichever hierarchy the last load happened to write.
        """
        types = {r[0] for r in q(con, "select distinct hierarchy_type from canon.party_hierarchy")}
        assert {"LEGAL_OWNERSHIP", "RISK_GROUP"} <= types

        divergent = one(con, f"""
            select count(*) from (
                select l.child_party_key
                from canon.party_hierarchy l
                join canon.party_hierarchy r
                  on r.child_party_key = l.child_party_key and r.as_of_date = l.as_of_date
                where l.hierarchy_type = 'LEGAL_OWNERSHIP'
                  and r.hierarchy_type = 'RISK_GROUP'
                  and l.parent_party_key <> r.parent_party_key
                  and l.as_of_date = date '{AS_OF}'
            )
        """)
        assert divergent > 0, \
            "the two hierarchies agree everywhere; the case the model exists for is untested"

    def test_ownership_percentage_is_only_claimed_where_it_is_known(self, con):
        """A risk grouping has no ownership percentage. Inventing one would
        imply a precision the judgement does not have."""
        invented = one(con, """
            select count(*) from canon.party_hierarchy
            where hierarchy_type = 'RISK_GROUP' and ownership_pct is not null
        """)
        assert invented == 0

    def test_finance_and_risk_classifications_coexist(self, con):
        """ADR-0002: one model, two lenses — so both assessments must survive.

        The classification table is keyed by scheme precisely so that neither
        function's view of a counterparty overwrites the other's. If a load
        could clobber the other scheme, the whole two-lens argument collapses.
        """
        schemes = {r[0] for r in q(con, "select distinct classification_scheme from canon.classification")}
        assert "COUNTERPARTY_SECTOR_ACCOUNTING" in schemes
        assert "COUNTERPARTY_SECTOR_PRUDENTIAL" in schemes

        both = one(con, f"""
            select count(*) from (
                select a.arrangement_key from canon.classification a
                join canon.classification p
                  on p.arrangement_key = a.arrangement_key and p.as_of_date = a.as_of_date
                where a.classification_scheme = 'COUNTERPARTY_SECTOR_ACCOUNTING'
                  and p.classification_scheme = 'COUNTERPARTY_SECTOR_PRUDENTIAL'
                  and a.as_of_date = date '{AS_OF}'
            )
        """)
        assert both > 0, "no counterparty carries both assessments; the lenses cannot be compared"


# ---------------------------------------------------------------------------
# 2 · The finance lens applies the accounting rules
# ---------------------------------------------------------------------------
class TestFinanceLens:
    def test_negative_fair_value_derivatives_are_not_assets(self, con):
        """Rule 1, the sign test — the single most common quiet overstatement.

        Sum fair value without testing the sign and the asset side absorbs the
        liabilities. The error is invisible because the total still balances
        against itself.
        """
        bad = one(con, """
            select count(*) from rpt.finrep_asset_detail
            where product_family = 'DERIVATIVE' and asset_carrying_amount < 0
        """)
        assert bad == 0

        # And the liabilities are kept, not dropped.
        liabilities = one(con, "select sum(liability_fair_value) from rpt.finrep_asset_detail")
        assert liabilities > 0, "negative-mark derivatives vanished instead of becoming liabilities"

    def test_asset_and_liability_sides_are_mutually_exclusive(self, con):
        """A single derivative is an asset or a liability, never both."""
        both = one(con, """
            select count(*) from rpt.finrep_asset_detail
            where asset_carrying_amount > 0 and liability_fair_value > 0
        """)
        assert both == 0

    def test_population_follows_accounting_recognition(self, con):
        """Rule 2: recognition date drives the finance population, not trade date."""
        late = one(con, f"""
            select count(*) from rpt.finrep_asset_detail f
            join (
                select arrangement_key, min(accounting_date) as accounting_date
                from canon.trade_event where event_type = 'INCEPTION' group by 1
            ) ev on ev.arrangement_key = f.arrangement_key
            where ev.accounting_date > date '{AS_OF}'
        """)
        assert late == 0, "trades recognised after the reporting date are in the finance lens"

    def test_terminated_arrangements_are_excluded(self, con):
        excluded = one(con, f"""
            select count(*) from rpt.finrep_asset_detail f
            join canon.arrangement a
              on a.arrangement_key = f.arrangement_key and a.as_of_date = date '{AS_OF}'
            where a.status = 'TERMINATED'
        """)
        assert excluded == 0

    def test_aggregate_ties_to_detail(self, con):
        """The published aggregate must equal the detail it claims to summarise.

        Trivial to assert and routinely untrue in production, because the two
        are usually built by different jobs against different populations.
        """
        detail = one(con, "select sum(asset_carrying_amount) from rpt.finrep_asset_detail")
        agg = one(con, "select sum(carrying_amount) from rpt.finrep_assets_by_sector")
        assert abs(float(detail) - float(agg)) < 0.01

    def test_unclassified_is_surfaced_not_defaulted(self, con):
        """A missing classification must remain visible as a data-quality gap."""
        values = {r[0] for r in q(con, "select distinct measurement_category from rpt.finrep_asset_detail")}
        assert values, "no measurement categories at all"
        assert None not in values, "nulls leaked instead of being labelled UNCLASSIFIED"


# ---------------------------------------------------------------------------
# 3 · The risk lens applies the prudential rules
# ---------------------------------------------------------------------------
class TestRiskLens:
    def test_netting_requires_legal_enforceability(self, con):
        """Problem 1, and the one with the largest number attached to it.

        Netting on the *presence* of an agreement rather than its
        enforceability understates exposure. Here, unenforceable sets must show
        no benefit at all — not a small one, none.
        """
        benefit = one(con, """
            select coalesce(sum(gross_replacement_cost - netted_replacement_cost), 0)
            from rpt.ccr_exposure_by_netting_set where not netting_eligible
        """)
        assert float(benefit) == pytest.approx(0.0, abs=0.01), \
            "unenforceable netting sets received a netting benefit"

    def test_enforceable_netting_produces_a_real_benefit(self, con):
        """The converse. If enforceable sets show no benefit either, the
        offsetting logic is broken and the test above passes vacuously."""
        gross, netted = q(con, """
            select sum(gross_replacement_cost), sum(netted_replacement_cost)
            from rpt.ccr_exposure_by_netting_set where netting_eligible
        """)[0]
        assert float(netted) < float(gross), "enforceable netting produced no offsetting"

    def test_replacement_cost_is_never_negative(self, con):
        """A negative mark is not an exposure to the counterparty."""
        assert one(con, "select count(*) from rpt.ccr_trade_exposure where replacement_cost < 0") == 0
        assert one(con, """
            select count(*) from rpt.ccr_exposure_by_netting_set
            where netted_replacement_cost < 0 or exposure_at_default < 0
        """) == 0

    def test_population_follows_the_economic_date(self, con):
        """Problem 3: risk cares when the trade was done, not when it was booked."""
        late = one(con, f"""
            select count(*) from rpt.ccr_trade_exposure c
            join (
                select arrangement_key, min(economic_event_date) as d
                from canon.trade_event where event_type = 'INCEPTION' group by 1
            ) ev on ev.arrangement_key = c.arrangement_key
            where ev.d > date '{AS_OF}'
        """)
        assert late == 0

    def test_collateral_is_allocated_not_double_counted(self, con):
        """Problem 2: one asset securing three arrangements is not three lots
        of protection. Recognised collateral must not exceed the collateral
        that exists."""
        recognised = one(con, "select sum(collateral_after_haircut) from rpt.ccr_trade_exposure")
        available = one(con, f"""
            select sum(market_value * (1 - coalesce(haircut_pct, 0)))
            from canon.collateral
            where is_financial_collateral and as_of_date = date '{AS_OF}'
        """)
        assert float(recognised) <= float(available) + 0.01, \
            "recognised collateral exceeds the collateral that exists"

    def test_only_derivatives_are_in_the_ccr_population(self, con):
        non_deriv = one(con, f"""
            select count(*) from rpt.ccr_trade_exposure c
            join canon.arrangement a
              on a.arrangement_key = c.arrangement_key and a.as_of_date = date '{AS_OF}'
            where a.product_family <> 'DERIVATIVE'
        """)
        assert non_deriv == 0

    def test_risk_uses_the_prudential_classification(self, con):
        """The lenses must not quietly share a classification.

        If the risk lens picked up the accounting sector, the two views would
        agree for the wrong reason and the disagreement report would be empty —
        which would look like success.
        """
        mismatched = one(con, f"""
            select count(*) from rpt.ccr_trade_exposure c
            join canon.classification s
              on s.arrangement_key = c.counterparty_party_key
             and s.classification_scheme = 'COUNTERPARTY_SECTOR_PRUDENTIAL'
             and s.as_of_date = date '{AS_OF}'
            where c.counterparty_sector <> s.classification_value
        """)
        assert mismatched == 0


# ---------------------------------------------------------------------------
# 4 · The reconciliation explains the difference
# ---------------------------------------------------------------------------
class TestReconciliation:
    def test_every_trade_is_categorised(self, con):
        """The union of the two populations must be fully accounted for."""
        recon = one(con, "select sum(trade_count) from rpt.lens_population_reconciliation")
        universe = one(con, """
            select count(*) from (
                select arrangement_key from rpt.finrep_asset_detail where product_family = 'DERIVATIVE'
                union
                select arrangement_key from rpt.ccr_trade_exposure
            )
        """)
        assert recon == universe

    def test_no_unexplained_residual(self, con):
        """The claim in the README is that the residual is *named*, not plugged.

        If this ever fails, the correct response is to add a reason to the
        reconciliation — not to widen a catch-all bucket until it swallows the
        problem.
        """
        unexplained = q(con, """
            select difference_reason, trade_count
            from rpt.lens_population_reconciliation
            where difference_reason like '%unexplained residual%'
        """)
        assert not unexplained, f"unexplained reconciling items: {unexplained}"

    def test_the_shared_population_agrees_on_replacement_cost(self, con):
        """Trades in both lenses must not differ in the measure they share."""
        row = q(con, """
            select finance_asset_amount, risk_replacement_cost
            from rpt.lens_population_reconciliation where difference_reason = 'IN BOTH'
        """)
        assert row, "no trades in both lenses at all"
        finance, risk = row[0]
        assert float(finance) == pytest.approx(float(risk), rel=1e-9)

    def test_classification_disagreements_are_published(self, con):
        """A disagreement that is visible gets resolved; one that is silently
        overwritten becomes a finding two years later."""
        n = one(con, "select count(*) from rpt.sector_classification_disagreement")
        assert n > 0
        same = one(con, """
            select count(*) from rpt.sector_classification_disagreement
            where accounting_sector = prudential_sector
        """)
        assert same == 0, "rows where the two functions agree leaked into the disagreement report"

    def test_disagreements_carry_materiality(self, con):
        """Prioritised by carrying amount, not by who complains loudest."""
        nulls = one(con, """
            select count(*) from rpt.sector_classification_disagreement
            where total_carrying_amount is null
        """)
        assert nulls == 0


# ---------------------------------------------------------------------------
# 5 · Lineage is sufficient, not merely present
# ---------------------------------------------------------------------------
class TestLineage:
    def test_every_reporting_column_has_lineage(self, con):
        """DP-18, asserted independently of the linter that also asserts it."""
        missing = []
        for (table,) in q(con, "select table_name from information_schema.tables "
                               "where table_schema = 'rpt'"):
            missing += [f"{table}.{c}" for c in lineage.unmapped_columns(con, table, "rpt")]
        assert not missing, f"reporting columns with no lineage: {missing}"

    def test_a_reported_figure_traces_to_a_source_system(self, con):
        """The demonstration the whole repository is built around.

        Not "lineage exists" — that a specific reported number can be walked
        back to the system it came from, in one query, without a human in the
        middle.
        """
        rows = lineage.trace(con, "finrep_assets_by_sector", "carrying_amount")
        assert rows, "no lineage at all for the flagship figure"
        layers = {r[3] for r in rows}
        assert "SOURCE" in layers, "the chain stops before reaching a system of record"
        assert max(r[0] for r in rows) >= 3, "the chain is suspiciously short"

    def test_lineage_records_multi_table_provenance(self, con):
        """A derived column reads more than one source, and must say so.

        The asset-carrying-amount rule reads fair value *and* carrying amount.
        Lineage that names only one of them is confidently wrong, which is
        worse than absent.
        """
        sources = {r[0] for r in q(con, """
            select source_column from meta.lineage
            where target_table = 'finrep_asset_detail'
              and target_column = 'asset_carrying_amount'
        """)}
        assert {"fair_value", "carrying_amount"} <= sources

    def test_no_reporting_table_reads_a_source_directly(self, con):
        """DP-10. Bypassing the canonical model is how two reports of the same
        concept begin to diverge."""
        assert one(con, """
            select count(*) from meta.lineage
            where target_layer = 'REPORTING' and source_layer = 'SOURCE'
        """) == 0

    def test_every_load_is_logged_with_its_as_of_date(self, con):
        """Reproducibility needs to know what ran, against what date."""
        unlogged = one(con, "select count(*) from meta.load_log where as_of_date is null")
        assert unlogged == 0
        assert one(con, "select count(*) from meta.load_log") > 0


class TestLineageMechanism:
    """The mechanism itself, in isolation — no warehouse required."""

    def test_a_mapping_cannot_be_executed_without_recording_lineage(self):
        """ADR-0003 made concrete: ``apply`` does both or neither.

        This is the structural claim. If someone adds a convenience path that
        runs the SQL without the mapping, this test still passes and the claim
        quietly becomes false — so the linter's DP-18 check is the backstop,
        and it runs over the built database rather than the source.
        """
        con = duckdb.connect()
        lineage.create_schema(con)
        con.execute("create schema if not exists canon")
        con.execute("create schema if not exists src")
        con.execute("create table src.t as select 1 as a, 'x' as b")

        m = lineage.Mapping(
            rule_id="TEST-001", target_layer="CANONICAL", target_table="thing",
            source_layer="SOURCE", source_relation="src.t", source_table_label="src.t",
            columns=[
                lineage.ColumnMapping("a", "a", ("a",), "direct copy"),
                lineage.ColumnMapping("b_upper", "upper(b)", ("b",), "upper-cased"),
            ],
        )
        n = lineage.apply(con, m, as_of_date="2026-03-31", mode="replace")
        assert n == 1
        assert con.execute("select count(*) from meta.lineage where rule_id='TEST-001'").fetchone()[0] == 2
        assert lineage.unmapped_columns(con, "thing", "canon") == []
        con.close()

    def test_multi_table_sources_are_split_correctly(self):
        """``table.column`` sources must be attributed to the right table."""
        con = duckdb.connect()
        lineage.create_schema(con)
        con.execute("create schema if not exists rpt")
        con.execute("create table rpt.base as select 1 as x")

        m = lineage.Mapping(
            rule_id="TEST-002", target_layer="REPORTING", target_table="out",
            source_layer="CANONICAL", source_relation="rpt.base", source_table_label="canon.a",
            columns=[lineage.ColumnMapping("x", "x", ("canon.a.x", "canon.b.y"), "joined")],
        )
        lineage.apply(con, m, as_of_date="2026-03-31", mode="replace")
        rows = dict(con.execute(
            "select source_table, source_column from meta.lineage where rule_id='TEST-002'"
        ).fetchall())
        assert rows == {"canon.a": "x", "canon.b": "y"}
        con.close()

    def test_a_constant_records_lineage_with_no_source_column(self):
        """Empty string rather than null — a nullable key column would allow
        duplicate lineage rows, which is the one thing this table must not do."""
        con = duckdb.connect()
        lineage.create_schema(con)
        con.execute("create schema if not exists rpt")
        con.execute("create table rpt.base as select 1 as x")
        m = lineage.Mapping(
            rule_id="TEST-003", target_layer="REPORTING", target_table="out",
            source_layer="CANONICAL", source_relation="rpt.base", source_table_label="canon.a",
            columns=[lineage.ColumnMapping("d", "date '2026-03-31'", (), "run parameter")],
        )
        lineage.apply(con, m, as_of_date="2026-03-31", mode="replace")
        lineage.apply(con, m, as_of_date="2026-03-31", mode="replace")  # idempotent
        assert con.execute(
            "select count(*) from meta.lineage where rule_id='TEST-003'").fetchone()[0] == 1
        con.close()


# ---------------------------------------------------------------------------
# 6 · Identity resolution
# ---------------------------------------------------------------------------
class TestIdentityResolution:
    def test_lei_is_preferred_over_the_weaker_match(self, con):
        methods = dict(q(con, "select resolution_method, count(*) from stg.party_xref group by 1"))
        assert methods.get("LEI", 0) > 0
        assert methods.get("LEI", 0) > methods.get("NAME_COUNTRY", 0), \
            "the weak name match is doing more work than the LEI; the join is wrong"

    def test_the_weak_match_is_flagged_not_hidden(self, con):
        """A name-and-country match is a decision someone may need to revisit.

        Merging on it silently is how two counterparties become one and a
        concentration limit stops binding.
        """
        methods = {r[0] for r in q(con, "select distinct resolution_method from stg.party_xref")}
        assert "NAME_COUNTRY" in methods, "the weaker match was not recorded as such"

    def test_no_source_reference_resolves_to_two_parties(self, con):
        """The cross-reference must be a function, not a relation."""
        dupes = one(con, """
            select count(*) from (
                select source_system, source_id
                from stg.party_xref group by 1, 2 having count(distinct party_key) > 1
            )
        """)
        assert dupes == 0


# ---------------------------------------------------------------------------
# 7 · The linter catches things
# ---------------------------------------------------------------------------
class TestConformanceLinter:
    """The group most often missing, and the reason linters rot.

    Each test below breaks exactly one thing in a *copy* of the warehouse and
    asserts the corresponding rule notices. A rule that cannot be made to fail
    is not enforcing anything.
    """

    @pytest.fixture
    def broken(self, warehouse, tmp_path):
        """A writable copy of the built warehouse, for breaking on purpose."""
        import shutil
        target = tmp_path / "broken.duckdb"
        shutil.copy(warehouse, target)
        return duckdb.connect(str(target))

    def _findings(self, con, rule_id: str):
        return [f for f in conformance.CHECKS[rule_id](con) if f.severity == conformance.ERROR]

    def test_clean_warehouse_has_no_errors(self, con):
        """The headline claim: the build conforms to its own written standards."""
        errors = [f for f in conformance.run(con) if f.severity == conformance.ERROR]
        assert not errors, "\n".join(f"{f.rule_id} {f.subject}: {f.message}" for f in errors)

    def test_dp18_catches_a_column_with_no_lineage(self, broken):
        assert not self._findings(broken, "DP-18")
        broken.execute("alter table rpt.finrep_asset_detail add column smuggled_in varchar")
        found = self._findings(broken, "DP-18")
        assert any("smuggled_in" in f.subject for f in found), \
            "a reporting column was added with no lineage and DP-18 did not notice"

    def test_dp19_catches_a_chain_that_stops_short(self, broken):
        """The check that matters: lineage that exists but explains nothing."""
        assert not self._findings(broken, "DP-19")
        broken.execute("""
            delete from meta.lineage
            where target_table = 'position' and source_layer = 'SOURCE'
        """)
        found = self._findings(broken, "DP-19")
        assert found, "the chain to source was severed and DP-19 still passed"

    def test_dp10_catches_a_report_bypassing_the_canonical_model(self, broken):
        assert not self._findings(broken, "DP-10")
        broken.execute("""
            insert into meta.lineage values
            ('HACK-001','REPORTING','finrep_asset_detail','shortcut','SOURCE',
             'CBS_account','balance','copied straight from the extract', true)
        """)
        found = self._findings(broken, "DP-10")
        assert any("shortcut" in f.subject for f in found)

    def test_dp16_catches_a_name_that_breaks_the_convention(self, broken):
        assert not self._findings(broken, "DP-16")
        broken.execute('alter table rpt.finrep_asset_detail add column "TotalAmount" varchar')
        found = self._findings(broken, "DP-16")
        assert any("TotalAmount" in f.subject for f in found)

    def test_the_linter_self_check_rejects_an_unpublished_rule_id(self):
        """A rule whose ID is not a published standard fails the linter's own
        conformance. That is the anti-drift mechanism, so it gets a test."""
        original = list(conformance.RULES)
        try:
            conformance.RULES.append(conformance.Rule("DP-99", "invented", conformance.ERROR))
            found = conformance.self_check_rule_ids_exist_in_standards()
            assert any(f.subject == "DP-99" for f in found)
        finally:
            conformance.RULES[:] = original

    def test_every_rule_id_is_a_published_standard(self):
        """And the real one, unbroken."""
        assert not conformance.self_check_rule_ids_exist_in_standards()

    def test_the_linter_exits_nonzero_when_it_should(self, warehouse, tmp_path):
        """Exit codes are the only part of a linter that CI actually reads."""
        import shutil
        target = tmp_path / "broken.duckdb"
        shutil.copy(warehouse, target)
        con = duckdb.connect(str(target))
        con.execute("alter table rpt.ccr_trade_exposure add column undeclared varchar")
        con.close()

        clean = subprocess.run(
            [sys.executable, "-m", "conformance.check", "--db", str(warehouse), "--quiet"],
            cwd=REPO, capture_output=True, text=True)
        assert clean.returncode == 0, clean.stderr

        dirty = subprocess.run(
            [sys.executable, "-m", "conformance.check", "--db", str(target), "--quiet"],
            cwd=REPO, capture_output=True, text=True)
        assert dirty.returncode == 1
        assert "NON-CONFORMANT" in dirty.stderr

    def test_the_linter_reports_rather_than_crashes_on_a_missing_database(self, tmp_path):
        """Exit 2 means "could not run", which is a different thing from "failed"."""
        result = subprocess.run(
            [sys.executable, "-m", "conformance.check", "--db", str(tmp_path / "nope.duckdb")],
            cwd=REPO, capture_output=True, text=True)
        assert result.returncode == 2


# ---------------------------------------------------------------------------
# 8 · The governance artefacts exist and are structurally sound
# ---------------------------------------------------------------------------
class TestGovernanceArtefacts:
    def test_every_adr_has_the_required_sections(self):
        adrs = sorted((REPO / "governance" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md"))
        assert len(adrs) >= 4
        for adr in adrs:
            text = adr.read_text(encoding="utf-8").lower()
            for heading in ("status", "context", "decision", "consequences"):
                assert heading in text, f"{adr.name} has no '{heading}' section"

    def test_every_machine_checked_standard_is_marked_as_such(self):
        """The standards document marks machine-checkable standards with 🤖.

        If a rule exists but its standard is not marked, a reader reasonably
        assumes it is enforced by a human — and stops checking it themselves.
        """
        doc = (REPO / "governance" / "data-policy-standards.md").read_text(encoding="utf-8")
        for line in doc.splitlines():
            for rule in conformance.RULES:
                if line.strip().startswith(f"### {rule.rule_id}") or \
                   line.strip().startswith(f"## {rule.rule_id}"):
                    assert "🤖" in line, f"{rule.rule_id} has a linter rule but is not marked machine-checked"

    def test_no_employer_client_or_proprietary_model_is_named(self):
        """This is a public repository built on synthetic data.

        Nothing in it should identify an employer, a client, a real
        counterparty, or reproduce a licensed industry data model. Asserted
        rather than remembered, because "I was careful" does not survive the
        fortieth commit.

        This file is excluded from the scan for the obvious reason that it has
        to contain the terms in order to search for them.
        """
        banned = ("accenture", "escalent", "aditi consulting")
        offenders = []
        for path in self._scannable():
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            offenders += [f"{path.relative_to(REPO)}: {t!r}" for t in banned if t in text]
        assert not offenders, offenders

    def test_a_named_proprietary_model_is_always_disclaimed(self):
        """Naming a licensed vendor model as an industry reference point is
        fine. Reproducing its structure is not.

        Reproduction cannot be detected mechanically, so this checks the thing
        that can be: wherever such a model is named, the same paragraph says
        plainly that it is not reproduced here. A mention that drifts loose
        from its disclaimer is how a comparison turns into a derivation.
        """
        proprietary = ("fsldm",)
        disclaimers = ("not reproduced", "do not reproduce", "nothing in this "
                       "repository derives", "is not reproduced")
        offenders = []
        for path in self._scannable():
            if path.suffix != ".md":
                continue
            for para in path.read_text(encoding="utf-8", errors="ignore").lower().split("\n\n"):
                if any(p in para for p in proprietary) and not any(d in para for d in disclaimers):
                    offenders.append(f"{path.relative_to(REPO)}: undisclaimed mention")
        assert not offenders, offenders

    @staticmethod
    def _scannable():
        for path in REPO.rglob("*"):
            if path.suffix not in {".py", ".md", ".txt", ".yml", ".yaml"}:
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if path.resolve() == Path(__file__).resolve():
                continue
            yield path
