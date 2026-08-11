# 0002. One model, two lenses: FINREP and Counterparty Credit Risk from one canonical model

## Status

Accepted · Data Architecture Forum
Depends on ADR-0001 (canonical domain model over point-to-point)

---

## Context

This repository produces two worked regulatory outputs from the same canonical banking domain model:

- **FINREP** — the EBA's harmonised supervisory financial reporting framework. The **accounting lens**: balance sheet and income statement structure with supervisory breakdowns, measured under the applicable accounting framework (IFRS as endorsed for use in the EU, with national GAAP variants).
- **Counterparty Credit Risk** — the **prudential lens**: measurement of exposure arising from derivatives and securities financing transactions, where the exposure is not a fixed drawn amount but a function of current value, potential future movement, netting and collateral.

They are built over one model deliberately. That decision is the intellectual centre of this repository, because the two lenses **do not agree**, and the interesting question is not how to make them agree but how to hold both honestly at once.

### Where the disagreement comes from

The accounting lens answers: *what is the entity's financial position and performance, faithfully represented for users of financial statements?*

The prudential lens answers: *how much loss could arise if a counterparty fails, and how much capital should stand behind it?*

Different questions, different audiences, different conservatism. Neither is wrong. A design that forces them to produce the same number is not resolving a conflict — it is destroying information that one of the two audiences requires.

Some of the differences that any banking data architecture must accommodate:

| Concept | Accounting lens | Prudential lens | Nature of the difference |
|---|---|---|---|
| **Scope of consolidation** | The accounting group, per the applicable consolidation requirements | The prudential scope, which is defined for supervisory purposes and need not match the accounting group — treatment of certain entity types differs | The *population* differs. Two correct numbers over different populations. |
| **Offsetting / netting** | Offsetting of financial assets and liabilities is permitted only where restrictive criteria are met (broadly: an enforceable right of set-off plus intent to settle net or realise simultaneously — see IAS 32) | Netting recognition is driven by the enforceability of qualifying netting agreements within a netting set | Gross under accounting, net under prudential, for the same trades, both correct under their own rules. |
| **Derivative measurement** | Fair value on the balance sheet — a point-in-time value | Exposure at default, built from a current-value component and a **potential future exposure** component, aggregated over the netting set and scaled by a supervisory multiplier under the standardised approach (SA-CCR), or modelled under an approved internal model | Accounting has no forward-looking exposure concept at all. This is not a measurement difference; it is a difference in what is being measured. |
| **Collateral** | Recognised or not per the accounting rules for the instrument; generally does not reduce the carrying amount of the exposure | Eligible collateral reduces exposure, subject to eligibility criteria, haircuts and margin agreement terms | Different eligibility populations and different effects. |
| **Credit deterioration** | IFRS 9 expected credit loss, with staging driven by significant increase in credit risk and credit-impaired status | The prudential definition of default; and, separately again, the supervisory **non-performing exposure** definition used in supervisory reporting | Three related but distinct concepts that are routinely and incorrectly treated as one. |
| **Counterparty grouping** | Related-party and group concepts per the accounting framework | Connected-client concepts for prudential purposes, driven by control and economic interdependence | Different grouping rules over the same legal entities. |
| **Valuation timing** | Reporting-date measurement consistent with the accounting close | Risk measurement may use a different valuation cycle and as-of convention | Same trade, two legitimate as-of bases. |

> **Read the actual requirements from the source.** The table above describes the *shape* of the differences conceptually. It deliberately quotes no template references, no thresholds, no article numbers and no eligibility lists. For the applicable rules, go to the current EBA implementing technical standards and validation rules, the applicable prudential regulation as in force, the endorsed accounting standards, and any national competent authority addenda. Architecture decisions can be made from the shape of a difference; implementations cannot.

### The two wrong answers

**Wrong answer one: one blended number.** Force a single "exposure" definition that both lenses consume. This is the more seductive failure because it looks like harmonisation and it satisfies an executive request for "one version of the truth". It produces a figure that is correct under neither framework, and it fails the first time either audience asks a question that depends on their own definition.

**Wrong answer two: two separate marts.** Give each lens its own model, fed independently from source. This is the more common failure because it is what happens when nobody decides. It looks respectful of the differences. In fact it makes the differences *unexplainable*: when the two returns disagree — and they will, on facts as well as on treatment — nobody can tell which part of the gap is a legitimate definitional difference and which is a defect. Every reconciliation becomes an investigation from first principles.

The differences between the lenses are not noise to be eliminated. They are **information**, and the architecture's job is to preserve them and make them explicable.

---

## Decision

**We will serve both lenses from one canonical model, by separating shared facts from lens-specific measures, and we will reconcile and explain the differences rather than average them away.**

### 1. The canonical model holds facts and events, not measures

The canonical layer holds what happened, as agreed, once: the trade and its economic terms, the trade event history, the counterparty and its identity, the arrangement and its legal terms including whether a qualifying netting agreement exists, the collateral and its terms, the valuations received, the classifications assigned.

It does **not** hold "exposure". Exposure is a measure, and there is no single one.

This is the pivotal design move. The disagreements between the lenses are almost entirely disagreements about *measurement and population*, not about *what happened*. Trades, counterparties, agreements and collateral are the same objects under both lenses. Once the shared substrate is factual, the divergence has a natural place to live.

### 2. Measures are computed in the lens layer, by governed rules over shared facts

Each lens applies its own rules to the same facts: its own scope-of-consolidation filter, its own netting recognition, its own collateral eligibility and haircuts, its own measurement basis, its own classification of deterioration. These rules are versioned, owned by the relevant reporting-policy function, and expressed against canonical attributes (DP-11, DP-22).

Neither lens's measure is derived from the other's. `carrying_amount` is not an input to exposure at default, and exposure at default is not a scaled carrying amount. Both descend independently from the same facts. Chained derivation would make one lens's correction silently move the other's figures.

### 3. Where both lenses need a fact, the fact is stored — not inferred

Where the two lenses assess the same underlying question differently, **both assessments are stored as facts on the canonical model**, each with its own owner and lineage. The enforceability assessment supporting prudential netting recognition and the assessment supporting accounting offsetting are two attributes, not one attribute with two interpretations. Likewise the accounting staging status, the prudential default indicator and the supervisory non-performing classification: three attributes, three definitions, three owners.

Storing them separately looks redundant. It is the opposite: it is the refusal to pretend that one flag can carry two meanings, which is how a "harmonised" model quietly becomes wrong for both audiences.

### 4. Measures are named for their basis, never generically

No canonical or published artefact contains a field called `exposure`. Measures carry their framework in the name and their definition in the glossary, with the framework's own vocabulary recorded as an alias (DP-17). Ambiguous names are the mechanism by which two definitions merge without anyone deciding to merge them.

### 5. Reconciliation is a first-class published output

For each concept where the lenses differ materially, a **reconciliation** is produced with the same rigour, lineage and periodicity as the returns themselves. It walks from one lens's figure to the other's through named, quantified, individually explicable steps — scope of consolidation, netting recognition, collateral effect, measurement basis, classification differences — with an explicit residual line.

The residual is the point. A reconciliation that ends with an unexplained residual is a control finding, not an inconvenience: it means there is a difference nobody has accounted for, and the only way to know whether it is a legitimate definitional gap or a defect is to require that the explained steps sum.

### 6. Definitional conflicts are resolved by a recorded procedure

When a new conflict is identified:

1. **Name it precisely.** Which concept, which lens, which rule, and what each lens requires. Most apparent conflicts dissolve here, being vocabulary collisions rather than substantive disagreements.
2. **Establish whether it is a difference of fact or of treatment.** Differences of fact are data quality issues and must be fixed — the two lenses must never disagree about what happened. Differences of treatment are legitimate and are preserved.
3. **Both reporting-policy owners state their requirement in writing**, with the basis. Not a preference — the requirement, and where it comes from.
4. **The Data Architecture Forum decides the representation** (DP-35): shared fact plus two governed measures; or two stored facts where the assessment itself differs. It does not decide the interpretation, which belongs to the policy owners.
5. **Record an ADR**, add the reconciliation step, and register the conflict in the cross-lens conflict register so that the next person to encounter it finds the answer rather than reopening it.

---

## Consequences

### What this gives us

- **Both lenses are correct under their own framework.** Nothing is compromised to achieve agreement.
- **Differences are explicable on demand.** When a supervisor asks why two figures differ, the answer is a published, lineage-backed reconciliation rather than a fortnight of analysis.
- **Facts are agreed once.** The two lenses can never disagree about whether a trade exists, who the counterparty is, or what the collateral terms are — the highest-value guarantee here, because factual disagreement between finance and risk is corrosive to both functions' credibility.
- **Marginal cost of the second lens is low.** The CCR lens reuses the model the FINREP lens established; it adds measurement rules, not a fact base.
- **Definitional conflicts surface at design time**, in a forum, rather than at quarter-end in a variance investigation.

### What this costs us

- **Every shared-concept change becomes a cross-functional negotiation.** A change finance wants now requires risk's assessment (DP-35). This is genuinely slower than a unilateral change in a private mart, and it will be resented at least once per reporting cycle.
- **The model is harder to understand.** Three deterioration attributes where a newcomer expects one requires explanation every time. Clarity here comes from definitions and glossary discipline, not from simplification.
- **Reconciliation is a permanent, funded obligation**, not a project. It must be built, owned and run every period.
- **Neither lens gets to optimise its own physical design freely.** Both are consumers of a shared model with a shared change cadence.
- **It requires two policy owners who will engage.** Where finance and risk do not talk, this architecture surfaces the fact rather than concealing it. That is the correct outcome and an uncomfortable one.

### Mitigations

| Cost | Mitigation |
|---|---|
| Cross-functional change friction | Both lens representatives are permanent, quorum-critical members of the forum (ToR §4.2), so the negotiation happens in a scheduled meeting rather than ad hoc. Additive change stays fast-tracked. |
| Model comprehension | Definitions that state population and basis (DP-15); framework vocabulary carried as aliases (DP-17); the cross-lens conflict register as onboarding material. |
| Reconciliation cost | Build it as a product with lineage and DQ rules like any other output, not as a spreadsheet. Automate the walk; humans should only ever investigate the residual. |
| Shared change cadence | Impact classification (DP-33) so that lens-specific changes that touch no shared concept proceed independently. |
| Policy engagement | Escalation path in the ToR; unresolved conflicts go to the sponsoring executive rather than being settled by whichever team ships first. |

---

## Alternatives considered

### Two independent marts, one per lens

Each function owns its own model and its own feeds. Maximum autonomy, no cross-functional change friction, each optimised for its own use.

Rejected. It guarantees factual divergence — the two will eventually disagree about which trades exist, not merely about how to measure them — and it makes every difference unexplainable, because there is no shared substrate to reconcile against. It also duplicates every ingestion, every DQ control and every reproducibility mechanism. This is the architecture that produces the reconciliation function whose full-time job is explaining differences that the architecture created.

### One model with a single harmonised exposure measure

A common "exposure" definition consumed by both lenses, with adjustments applied at the edges.

Rejected, firmly. The frameworks genuinely require different things, and a harmonised measure is correct under neither. The adjustments-at-the-edges pattern also degrades: adjustments accumulate, become undocumented, and eventually constitute a shadow definition maintained by nobody. Requests for this option are usually requests for *explicability*, not for a single number — and the reconciliation in §5 satisfies that requirement without falsifying either measure.

### One model, two lenses, but the risk lens derives from the finance lens

Treat the accounting figures as the base and derive prudential measures by adjustment. Attractive because the accounting close is already controlled and reconciled.

Rejected. Potential future exposure has no accounting antecedent to adjust — deriving it from a fair value is not an adjustment, it is a different calculation that happens to start from the wrong place. It also couples the risk lens to the accounting close calendar and makes every accounting restatement an unplanned risk-reporting event. Both lenses descend from facts, independently.

### Shared model for reference and static data only; separate transactional models

A compromise: agree parties, instruments and code lists; keep trades, positions and collateral separate per lens.

Rejected as capturing the least valuable half of the benefit. Reference data divergence is real but comparatively tractable. The expensive disagreements are transactional — which trades, which netting sets, which collateral, at which point in time — and this option leaves every one of them unaddressed.

---

## Related standards

| Standard | Relationship |
|---|---|
| DP-11 | Measures live in the lens layer as governed rules; the canonical layer holds facts. |
| DP-35 | Cross-lens impact assessment — the operational enforcement of this decision. |
| DP-15, DP-17 | Definitions state basis and population; framework vocabulary is aliased, never duplicated as new terms. |
| DP-30 | Bi-temporality supports the two lenses' different as-of conventions over one fact base. |
| DP-36 | One golden source per fact — the lenses share facts, so they share golden sources. |
| DP-40 | Each lens pins the framework version it implements; they revise on different schedules. |
| DP-41 | Every definitional resolution is recorded as an ADR. |

## Revisit triggers

- A regulatory change that materially converges or further diverges accounting and prudential treatment of a shared concept.
- The reconciliation residual becomes persistently material — evidence that the shared-fact assumption has broken somewhere and needs investigation, not tolerance.
- A third lens (liquidity, statistical or granular credit reporting) is added and the two-lens reconciliation pattern does not generalise to three.
