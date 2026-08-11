#!/usr/bin/env python3
"""Generate synthetic source-system extracts for a banking domain.

Standard library only, fixed seed, entirely fictional. What is *not* fictional
is the shape: five source systems that each hold part of the truth and
disagree about the rest, which is the condition every real banking data
architecture starts from.

Source systems
--------------
``REF``  Reference and party master — parties, instruments
``CBS``  Core banking — loans and deposits
``TRD``  Trade capture — derivatives, netting agreements, lifecycle events
``FIN``  Finance sub-ledger — positions and accounting classifications
``COL``  Collateral management — collateral and its allocation

Deliberate frictions injected
-----------------------------
These are the situations the architecture exists to survive. Each is
reproduced on purpose and discussed in ``architecture/domain-data-flows.md``.

1. **The same counterparty has different identifiers in CBS and TRD.** Only
   the LEI links them. Resolve on the wrong key and one counterparty becomes
   two, and every concentration measure is understated.
2. **Economic and accounting dates straddle the reporting date.** A trade
   executed on the last day of the period but recognised in the next one is
   in Risk's population and not in Finance's. Both are right.
3. **Netting sets exist in TRD and have no counterpart in FIN.** Risk nets;
   the accounting view generally does not. Neither is an error.
4. **Finance and Risk classify some counterparties into different sectors.**
   The schemes genuinely differ; the architecture must carry both.
5. **Some derivatives have negative fair value** — they are liabilities, and
   an asset-side report that sums them without checking sign is wrong.
6. **One collateral asset secures several arrangements**, so its value has to
   be allocated rather than counted repeatedly.
7. **A handful of parties have no LEI**, which is realistic and forces the
   identity strategy to have a documented fallback.
8. **A party sits in more than one hierarchy and they disagree.** Legal
   ownership is a fact about share registers; risk grouping is a judgement
   about who fails together. Modelling one and calling it "the" group
   structure measures a connected-clients limit against the wrong population.
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20260811
REPORTING_DATE = date(2026, 3, 31)

COUNTRIES = ["DE", "FR", "GB", "NL", "IE", "LU", "ES", "IT", "US", "SG"]
SECTORS = ["NFC", "CREDIT_INST", "OFI", "GOVT", "HOUSEHOLD", "INSURANCE"]
CCY = ["EUR", "GBP", "USD", "CHF"]
LOAN_TYPES = ["TERM_LOAN", "REVOLVING", "MORTGAGE", "OVERDRAFT"]
DEPOSIT_TYPES = ["CURRENT_ACCOUNT", "TERM_DEPOSIT", "NOTICE_ACCOUNT"]
DERIV_TYPES = ["IR_SWAP", "FX_FORWARD", "FX_OPTION", "CDS", "EQUITY_OPTION"]
COLLATERAL_TYPES = ["CASH", "GOVERNMENT_BOND", "CORPORATE_BOND", "EQUITY", "PROPERTY"]

STEM = ["Aurora", "Baltic", "Cedar", "Delta", "Ember", "Fjord", "Granite", "Harbour",
        "Ivory", "Juniper", "Kestrel", "Lantern", "Meridian", "Northwind", "Orchard",
        "Pinnacle", "Quarry", "Ridgeline", "Summit", "Tundra", "Umbra", "Vantage",
        "Westgate", "Yarrow", "Zephyr", "Alder", "Bramble", "Cobalt", "Dunmore", "Elmwood"]
SUFFIX = ["Holdings NV", "Capital SA", "Bank AG", "Partners LLP", "Industries GmbH",
          "Investments Ltd", "Trust plc", "Group SpA", "Securities BV", "Energy SE"]


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    print(f"  {path.name:<26} {len(rows):>6} rows")


def generate(out: Path, n_parties: int = 90, n_loans: int = 260,
             n_deposits: int = 180, n_derivatives: int = 240) -> None:
    rng = random.Random(SEED)

    # ------------------------------------------------------------------ REF
    parties = []
    for i in range(1, n_parties + 1):
        sector = rng.choice(SECTORS)
        is_fi = sector in ("CREDIT_INST", "OFI", "INSURANCE")
        # Friction 7: a few parties genuinely have no LEI.
        has_lei = rng.random() > 0.07
        parties.append({
            "ref_id": f"P{i:06d}",
            "name": f"{rng.choice(STEM)} {rng.choice(SUFFIX)}",
            "lei": (f"{rng.randint(100000, 999999)}"
                    f"{''.join(rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(12))}"
                    f"{rng.randint(10, 99)}") if has_lei else "",
            "country": rng.choice(COUNTRIES),
            "sector": sector,
            "is_fi": is_fi,
            "is_group": rng.random() < 0.05,
        })

    _write(out / "REF_party.csv",
           ["src_party_id", "legal_name", "lei", "country", "sector_code",
            "is_financial_institution", "is_group_entity"],
           [[p["ref_id"], p["name"], p["lei"], p["country"], p["sector"],
             "Y" if p["is_fi"] else "N", "Y" if p["is_group"] else "N"] for p in parties])

    # Friction 8: a party sits in more than one hierarchy and they disagree.
    # Legal ownership is a fact about share registers. Risk grouping is a
    # judgement about who fails together — and a bank is expected to make that
    # judgement, which means it will sometimes group entities the ownership
    # chain does not connect, and split entities it does. Modelling one
    # hierarchy and calling it "the" group structure is how a connected-clients
    # limit ends up being measured against the wrong population.
    group_parents = [p for p in parties if p["is_group"]] or parties[:4]
    hierarchy = []
    for p in parties:
        if p in group_parents:
            continue
        if rng.random() < 0.45:
            parent = rng.choice(group_parents)
            pct = round(rng.uniform(0.51, 1.0), 4)
            hierarchy.append((p["ref_id"], parent["ref_id"], "LEGAL_OWNERSHIP", pct))
            # Risk usually follows ownership...
            if rng.random() < 0.85:
                hierarchy.append((p["ref_id"], parent["ref_id"], "RISK_GROUP", ""))
            else:
                # ...but not always: economic dependence without ownership.
                other = rng.choice([g for g in group_parents if g is not parent] or [parent])
                hierarchy.append((p["ref_id"], other["ref_id"], "RISK_GROUP", ""))
        elif rng.random() < 0.10:
            # Grouped for risk with no ownership link at all — a supplier whose
            # failure would take its only customer with it, for instance.
            hierarchy.append((p["ref_id"], rng.choice(group_parents)["ref_id"], "RISK_GROUP", ""))

    _write(out / "REF_party_hierarchy.csv",
           ["child_src_party_id", "parent_src_party_id", "hierarchy_type", "ownership_pct"],
           [list(h) for h in hierarchy])

    instruments = []
    for i in range(1, 61):
        issuer = rng.choice(parties)
        instruments.append({
            "id": f"I{i:06d}",
            "isin": f"{rng.choice(COUNTRIES)}{rng.randint(1000000000, 9999999999)}",
            "type": rng.choice(["BOND", "EQUITY", "IR_SWAP", "FX_OPTION"]),
            "issuer": issuer["ref_id"],
            "ccy": rng.choice(CCY),
            "maturity": REPORTING_DATE + timedelta(days=rng.randint(200, 4000)),
        })
    _write(out / "REF_instrument.csv",
           ["src_instrument_id", "isin", "instrument_type", "issuer_src_party_id",
            "currency", "maturity_date"],
           [[x["id"], x["isin"], x["type"], x["issuer"], x["ccy"],
             x["maturity"].isoformat()] for x in instruments])

    # ------------------------------------------------------------------ CBS
    # Friction 1: CBS uses its own customer numbering. Only the LEI ties a CBS
    # customer back to the same legal entity in TRD.
    cbs_customers = []
    for p in parties:
        if rng.random() < 0.62:
            cbs_customers.append({"cbs_id": f"C{rng.randint(100000, 999999)}", "party": p})
    _write(out / "CBS_customer.csv",
           ["cbs_customer_id", "customer_name", "lei", "country", "src_party_id_hint"],
           [[c["cbs_id"], c["party"]["name"], c["party"]["lei"], c["party"]["country"],
             # A hint column exists in the extract but is populated only ~40% of
             # the time -- exactly the half-built cross-reference that tempts a
             # team into resolving identity on an unreliable key.
             c["party"]["ref_id"] if rng.random() < 0.4 else ""] for c in cbs_customers])

    accounts = []
    for i in range(1, n_loans + n_deposits + 1):
        cust = rng.choice(cbs_customers)
        is_loan = i <= n_loans
        opened = REPORTING_DATE - timedelta(days=rng.randint(30, 2600))
        principal = round(rng.uniform(25_000, 12_000_000), 2)
        accounts.append({
            "acct": f"A{i:08d}",
            "cust": cust["cbs_id"],
            "family": "LOAN" if is_loan else "DEPOSIT",
            "ptype": rng.choice(LOAN_TYPES if is_loan else DEPOSIT_TYPES),
            "ccy": rng.choice(CCY),
            "open": opened,
            "maturity": opened + timedelta(days=rng.randint(365, 7300)),
            "principal": principal,
            "status": rng.choices(["ACTIVE", "MATURED", "DEFAULTED"], weights=[92, 5, 3])[0],
            "is_loan": is_loan,
        })
    _write(out / "CBS_account.csv",
           ["account_id", "cbs_customer_id", "product_family", "product_type", "currency",
            "open_date", "maturity_date", "original_principal", "status"],
           [[a["acct"], a["cust"], a["family"], a["ptype"], a["ccy"],
             a["open"].isoformat(), a["maturity"].isoformat(),
             f"{a['principal']:.2f}", a["status"]] for a in accounts])

    # ------------------------------------------------------------------ TRD
    trd_counterparties = []
    for p in parties:
        if p["is_fi"] or rng.random() < 0.45:
            trd_counterparties.append({"trd_id": f"CP{rng.randint(10000, 99999)}", "party": p})
    _write(out / "TRD_counterparty.csv",
           ["trd_counterparty_id", "counterparty_name", "lei", "country"],
           [[c["trd_id"], c["party"]["name"], c["party"]["lei"], c["party"]["country"]]
            for c in trd_counterparties])

    # Friction 3: netting agreements are a TRD/Risk concept only.
    netting = []
    for c in trd_counterparties:
        if rng.random() < 0.7:
            netting.append({
                "id": f"NS{rng.randint(100000, 999999)}",
                "cpty": c["trd_id"],
                "type": rng.choices(["MASTER_NETTING", "CSA", "NONE"], weights=[50, 40, 10])[0],
                # Netting that is not legally enforceable is not netting. A
                # small proportion is deliberately marked unenforceable.
                "enforceable": rng.random() > 0.06,
            })
    _write(out / "TRD_netting_agreement.csv",
           ["netting_agreement_id", "trd_counterparty_id", "agreement_type",
            "is_legally_enforceable"],
           [[n["id"], n["cpty"], n["type"], "Y" if n["enforceable"] else "N"] for n in netting])

    netting_by_cpty = {}
    for n in netting:
        netting_by_cpty.setdefault(n["cpty"], []).append(n["id"])

    trades, events = [], []
    for i in range(1, n_derivatives + 1):
        cpty = rng.choice(trd_counterparties)
        traded = REPORTING_DATE - timedelta(days=rng.randint(0, 1800))
        notional = round(rng.uniform(500_000, 90_000_000), 2)
        ns = rng.choice(netting_by_cpty.get(cpty["trd_id"], [""])) if rng.random() < 0.85 else ""
        trades.append({
            "id": f"T{i:08d}",
            "cpty": cpty["trd_id"],
            "ptype": rng.choice(DERIV_TYPES),
            "ccy": rng.choice(CCY),
            "trade_date": traded,
            "maturity": traded + timedelta(days=rng.randint(180, 3650)),
            "notional": notional,
            "netting": ns,
            "instrument": rng.choice(instruments)["id"] if rng.random() < 0.35 else "",
            "status": rng.choices(["ACTIVE", "MATURED", "TERMINATED"], weights=[90, 6, 4])[0],
        })

        # Friction 2: economic and accounting dates straddle the reporting date
        # for a small number of trades booked right at period end.
        straddles = rng.random() < 0.06
        acct_date = traded + timedelta(days=rng.randint(1, 4)) if straddles else traded
        events.append([f"E{len(events)+1:08d}", f"T{i:08d}", "INCEPTION",
                       traded.isoformat(), acct_date.isoformat(), f"{notional:.2f}"])
        if rng.random() < 0.22:
            amend = traded + timedelta(days=rng.randint(30, 900))
            if amend <= REPORTING_DATE:
                delta = round(-notional * rng.uniform(0.05, 0.4), 2)
                events.append([f"E{len(events)+1:08d}", f"T{i:08d}", "PARTIAL_TERMINATION",
                               amend.isoformat(), amend.isoformat(), f"{delta:.2f}"])

    _write(out / "TRD_trade.csv",
           ["trade_id", "trd_counterparty_id", "product_type", "currency", "trade_date",
            "maturity_date", "notional", "netting_agreement_id", "src_instrument_id", "status"],
           [[t["id"], t["cpty"], t["ptype"], t["ccy"], t["trade_date"].isoformat(),
             t["maturity"].isoformat(), f"{t['notional']:.2f}", t["netting"],
             t["instrument"], t["status"]] for t in trades])
    _write(out / "TRD_event.csv",
           ["event_id", "trade_id", "event_type", "economic_event_date",
            "accounting_date", "notional_delta"], events)

    # ------------------------------------------------------------------ FIN
    positions, classifications = [], []
    for a in accounts:
        outstanding = round(a["principal"] * rng.uniform(0.25, 1.0), 2)
        impair = round(outstanding * rng.uniform(0.001, 0.09), 2) if a["is_loan"] else 0.0
        carrying = round(outstanding - impair, 2)
        positions.append([a["acct"], "CBS", REPORTING_DATE.isoformat(),
                          f"{outstanding:.2f}", f"{carrying:.2f}", "",
                          f"{round(outstanding * rng.uniform(0.001, 0.03), 2):.2f}",
                          f"{impair:.2f}", a["ccy"]])
        stage = rng.choices(["STAGE_1", "STAGE_2", "STAGE_3"], weights=[80, 15, 5])[0]
        classifications.append([a["acct"], "CBS", "ACCOUNTING_MEASUREMENT",
                                "AMORTISED_COST", REPORTING_DATE.isoformat(), "FINANCE"])
        classifications.append([a["acct"], "CBS", "IMPAIRMENT_STAGE", stage,
                                REPORTING_DATE.isoformat(), "FINANCE"])

    for t in trades:
        # Friction 5: fair value can be negative. A derivative with negative
        # fair value is a liability, not a small asset.
        fv = round(t["notional"] * rng.uniform(-0.06, 0.08), 2)
        positions.append([t["id"], "TRD", REPORTING_DATE.isoformat(),
                          f"{t['notional']:.2f}", f"{fv:.2f}", f"{fv:.2f}", "0.00", "0.00",
                          t["ccy"]])
        classifications.append([t["id"], "TRD", "ACCOUNTING_MEASUREMENT",
                                "FVTPL", REPORTING_DATE.isoformat(), "FINANCE"])

    _write(out / "FIN_position.csv",
           ["contract_ref", "source_system", "as_of_date", "notional_outstanding",
            "carrying_amount", "fair_value", "accrued_interest", "impairment_allowance",
            "currency"], positions)

    # Friction 4: Finance and Risk categorise some counterparties differently.
    # Both schemes are recorded; neither is overwritten.
    # Emit party-level sector assessments ONCE per party. A party that is both a
    # core-banking customer and a trading counterparty is still one party, and
    # the classification key is (party, scheme, as-of) -- emitting per
    # relationship would breach it, which is itself a useful thing to have
    # learned in a generator rather than in production.
    rated_parties = {c["party"]["ref_id"]: c["party"]
                     for c in cbs_customers + trd_counterparties}
    for p in rated_parties.values():
        fin_sector = p["sector"]
        risk_sector = p["sector"]
        if rng.random() < 0.12:
            risk_sector = rng.choice([s for s in SECTORS if s != fin_sector])
        classifications.append([p["ref_id"], "REF", "COUNTERPARTY_SECTOR_ACCOUNTING",
                                fin_sector, REPORTING_DATE.isoformat(), "FINANCE"])
        classifications.append([p["ref_id"], "REF", "COUNTERPARTY_SECTOR_PRUDENTIAL",
                                risk_sector, REPORTING_DATE.isoformat(), "RISK"])

    _write(out / "FIN_classification.csv",
           ["contract_ref", "source_system", "classification_scheme",
            "classification_value", "as_of_date", "assessed_by_domain"], classifications)

    # ------------------------------------------------------------------ COL
    collateral, allocations = [], []
    secured = [t for t in trades if t["netting"]] + [a for a in accounts if a["is_loan"]]
    for i in range(1, 150):
        ctype = rng.choice(COLLATERAL_TYPES)
        value = round(rng.uniform(100_000, 30_000_000), 2)
        collateral.append([f"COL{i:06d}", ctype, rng.choice(CCY), f"{value:.2f}",
                           f"{rng.uniform(0.0, 0.25):.4f}",
                           "Y" if ctype in ("CASH", "GOVERNMENT_BOND", "CORPORATE_BOND") else "N"])
        # Friction 6: one asset can secure several arrangements.
        for target in rng.sample(secured, rng.randint(1, 3)):
            ref = target["id"] if "id" in target else target["acct"]
            allocations.append([f"COL{i:06d}", ref, REPORTING_DATE.isoformat(),
                                f"{round(value / rng.randint(1, 3), 2):.2f}"])

    _write(out / "COL_collateral.csv",
           ["collateral_id", "collateral_type", "currency", "market_value",
            "haircut_pct", "is_financial_collateral"], collateral)
    _write(out / "COL_allocation.csv",
           ["collateral_id", "contract_ref", "as_of_date", "allocated_value"], allocations)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = (Path(args.out).resolve() if args.out
           else Path(__file__).resolve().parent.parent / "extracts")
    print(f"Generating synthetic source extracts in {out}  (reporting date {REPORTING_DATE})")
    generate(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
