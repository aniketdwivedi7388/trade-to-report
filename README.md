# trade-to-report

**A domain data architecture for banking, worked end to end — and checked against its own written standards by a linter that fails the build.**

Two functions read the same book of derivatives. Finance reports assets of **236.4m** and liabilities of **115.0m**. Risk reports a gross replacement cost of **230.5m** and an exposure at default of **316.1m**.

Four numbers. One book. None of them wrong.

The interesting question is not which figure is right. It is whether the architecture can explain the gaps — and whether that explanation takes a minute or a fortnight.

```
python run_demo.py --reset                        # source extracts → canonical model → two lenses → reconciliation
python -m conformance.check --db warehouse.duckdb # then check the result against the written standards
pytest -q                                         # 60 tests
```

No account, no cloud, no credentials. DuckDB, a synthetic dataset, and about ninety seconds.

---

## What this is

A reference architecture for the part of a bank where trade capture, finance and risk meet — the layer that has to serve a regulatory submission, a credit-exposure calculation and an audit question from the same model, without any of the three quietly disagreeing.

It exists because that layer is usually described rather than built. Target-state diagrams, a policy document nobody greps, a lineage spreadsheet that was accurate on the day it was written. This repository takes the same set of claims and makes them executable:

| The claim | Where it is made | How it is checked |
|---|---|---|
| One canonical model, source-agnostic | `model/canonical.py` | 11 entities, business keys asserted unique |
| Two lenses, neither overwriting the other | `reporting/finrep.py`, `reporting/ccr.py` | both classification schemes survive the load |
| Lineage is captured as data, not documented after | `model/lineage.py` | 185 column-level mappings; a reported figure traces to source in 3 hops |
| The standards are enforced, not aspirational | `conformance/check.py` | 10 rules, whose IDs **are** the standard IDs |
| Decisions are recorded before they are forgotten | `governance/adr/` | 4 ADRs, structure enforced by the linter |

---

## The problem, concretely

Ask a bank a simple question — how much are we owed on derivatives — and you get several defensible answers, because the question is under-specified in ways the questioner cannot see.

**Finance** answers under accounting rules. A derivative is an asset when its fair value is positive and a liability when it is negative, and summing fair value without testing the sign overstates the asset side and understates the liability side by exactly the same amount. The population is driven by *accounting recognition*: a trade executed on the last day of the quarter but recognised in the next one is not in this report.

**Risk** answers under prudential rules. The population is the *economic* one — Risk cares when the trade was done, not when it was booked. Exposures net, but only where a legally enforceable agreement exists. Collateral reduces exposure, but one asset securing three arrangements is not three lots of protection.

Both are correct. They will never agree, and they should not be made to. The architecture's job is to make the disagreement **explainable, attributable and stable**.

The two wrong answers, for the record:

- **Blend them.** Produce one number that is neither the accounting figure nor the prudential one. It will fail both audiences and satisfy no regulator.
- **Build two disconnected marts.** Then nobody can explain the difference at all, and the reconciliation becomes a quarterly spreadsheet exercise done by whoever is least able to refuse.

---

## What the pipeline shows

### 1 · Where the populations differ, and why

```
difference_reason                                             trade_count
IN BOTH                                                               219
FINANCE ONLY: not an active trade, so outside the CCR population        14
```

Every trade in the union of the two populations is categorised. The reconciliation carries a bucket named `unexplained residual` and a test that fails if anything lands in it. The correct response to that test failing is to add a reason — never to widen a catch-all until it swallows the problem.

### 2 · The netting benefit, quantified

```
treatment                netting_sets      gross_rc     netted_rc
No enforceable netting             70    57,563,057    57,563,057
Enforceable agreement              48   172,953,645   129,924,969
```

Netting is a legal fact before it is a calculation. Sets without an enforceable agreement show **no benefit at all** — not a small one, none — and there is a test that fails if they ever do. Teams that net on the *presence* of an agreement identifier rather than its enforceability understate exposure, and the number above is the size of the mistake.

### 3 · Where the two functions classify the same counterparty differently

Six counterparties are categorised differently by Finance and by Risk. Both assessments are stored. Neither overwrites the other. The disagreement is **published**, because one that is visible gets resolved and one that is silently overwritten becomes a finding two years later.

### 4 · Lineage, as a query rather than a diagram

```
└─ finrep_assets_by_sector.carrying_amount
     ← [REPORTING] rpt.finrep_asset_detail.asset_carrying_amount
       sum of asset-side carrying amounts
  └─ finrep_asset_detail.asset_carrying_amount
       ← [CANONICAL] canon.position.fair_value
         derivatives are an asset only where fair value is positive
    └─ position.fair_value
         ← [SOURCE] FIN_position.fair_value
           empty string normalised to null; not all products are marked
```

Nobody wrote that chain down. It was recorded by the loaders that built the tables, because **a loader cannot move a column without declaring where it came from — the declaration is what generates the SQL**. That inversion is the whole idea. Documentation drifts from code because they are two artefacts maintained by two acts of will. Here there is one artefact.

### 5 · Identity, and what resolving on the wrong key would cost

```
LEI            102   matched on Legal Entity Identifier — definitive
NATIVE          90   the reference master resolving to itself
NAME_COUNTRY    13   matched on normalised name and country — weaker, flagged
```

The core banking extract contains a cross-reference hint column, populated about 40% of the time — exactly the half-built key that tempts a team into resolving identity on it. Had the pipeline joined on that instead of the LEI, every party it failed to match would have become a second, separate counterparty, and every concentration measure in the bank would read lower than the truth. The weak match is recorded *as* weak rather than merged silently.

### 6 · Two hierarchies, held side by side

Legal ownership is a fact about share registers. Risk grouping is a judgement about who fails together, and a bank is expected to make that judgement — which means it will sometimes group entities the ownership chain does not connect. A `parent_party_key` column on the party table would force a choice between them and hide that a choice was made. A connected-clients limit would then be measured against whichever hierarchy the last load happened to write.

---

## Governance that runs

`governance/data-policy-standards.md` holds 42 standards, each with a statement, a rationale, a verification method and a severity. Roughly a third are marked 🤖 — machine-checkable — and `conformance/check.py` implements exactly those.

**The rule IDs in the linter are the standard IDs in the document.** That is the anti-drift mechanism: a standard whose ID has no rule is visibly manual, and a rule whose ID has no published standard fails the linter's own self-check. The two artefacts cannot quietly diverge.

```
[PASS] DP-01  Every canonical entity has a named owner
[PASS] DP-05  Every entity declares a business key
[PASS] DP-10  Nothing consumes a source system directly
[PASS] DP-15  Every entity has a usable definition
[PASS] DP-16  Names follow the domain naming convention
[PASS] DP-18  Regulatory-facing fields have lineage captured as data
[PASS] DP-19  Lineage is sufficient, not merely present
[WARN] DP-29  Point-in-time reproducibility is structurally possible
[PASS] DP-36  Every entity has a declared golden source
[PASS] DP-41  Material architecture decisions are recorded as ADRs
```

The remaining warning is real and deliberate: `canon.trade_event` is event-dated rather than as-of dated, which is correct for an event stream and worth surfacing anyway. A linter engineered to zero findings is a linter that has been taught not to look.

The build failed 42 times before it passed. `reporting/reconciliation.py` originally built its three tables with plain SQL on the grounds that they were "only" reconciliation outputs rather than regulatory submissions — and DP-18 failed it. The reconciliation is precisely the artefact someone will be asked to defend. It was quicker to argue for an exemption than to route three tables through the mapping mechanism, which is exactly why the exemption should not exist. That history is left in the module docstring rather than tidied away.

### The linter has negative tests

The group most often missing, and the reason linters rot. Each test breaks exactly one thing in a copy of the warehouse and asserts the corresponding rule notices — a column added with no lineage, a chain to source severed, a report bypassing the canonical model, a name that breaks the convention. **A rule that cannot be made to fail is not enforcing anything**, and nobody finds out until an auditor does.

---

## Repository layout

```
model/          canonical.py   11 entities, with owner, steward, business key,
                               definition and golden source as machine-readable metadata
                lineage.py     the mechanism: a mapping is executable and self-documenting,
                               and there is deliberately no way to do one without the other
                load.py        source → canonical, including identity resolution

reporting/      finrep.py      the finance lens — accounting rules, accounting population
                ccr.py         the risk lens — prudential rules, economic population
                reconciliation.py   where they differ, and why

governance/     data-policy-standards.md        42 standards
                data-architecture-forum-tor.md  who decides what, and how a decision is escalated
                artefact-conformance-checklist.md   what a human reviewer still has to do
                adr/           4 architecture decision records

architecture/   target-and-transition-states.md
                domain-data-flows.md
                methodology-decision.md         data vault, dimensional, or one model two lenses

conformance/    check.py       the standards, executed
data/           generate_banking_data.py   5 source systems, 8 deliberate frictions
tests/          60 tests, including negative tests for the linter itself
```

---

## The eight frictions

The synthetic data is not clean, on purpose. Each of these is a situation the architecture exists to survive, and each is discussed in `architecture/domain-data-flows.md`:

1. The same counterparty has different identifiers in core banking and trade capture. Only the LEI links them.
2. Economic and accounting dates straddle the reporting date.
3. Netting sets exist in trade capture and have no counterpart in the sub-ledger.
4. Finance and Risk classify some counterparties into different sectors.
5. Some derivatives have negative fair value — they are liabilities.
6. One collateral asset secures several arrangements.
7. A handful of parties have no LEI.
8. A party sits in more than one hierarchy and they disagree.

---

## What this is not

**Not a compliance artefact.** The finance lens is FINREP-*shaped* and the risk lens is *not* SA-CCR. No template cell references, no supervisory factors, no thresholds and no legal article numbers are reproduced, because a made-up supervisory factor in a public repository is worse than none at all. What is faithful is the *shape* of each calculation and, more importantly, the data architecture it requires. Build any actual return from the current official text and taxonomy.

**Not derived from any proprietary model.** Vendor logical data models for financial services exist and are widely used; they are licensed intellectual property. Nothing here reproduces, paraphrases or clean-room describes one. The public anchor for this work is the ECB's openly published integrated-reporting material, precisely because it can be cited, checked and shared.

**Not real data.** Every party, trade, position and collateral asset is generated by `data/generate_banking_data.py` from a fixed seed. Any resemblance to an institution is arithmetic.

---

## Requirements

Python 3.10+ and DuckDB. That is all.

```
pip install -r requirements.txt
python run_demo.py --reset
python -m conformance.check --db warehouse.duckdb
pytest -q
```

## Licence

MIT. See `LICENSE`.
