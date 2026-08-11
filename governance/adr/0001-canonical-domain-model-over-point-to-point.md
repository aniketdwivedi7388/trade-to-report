# 0001. Canonical domain model over point-to-point feeds

## Status

Accepted · Data Architecture Forum

---

## Context

A banking data estate that produces regulatory output has a characteristic shape: a moderate number of source systems (core banking, lending origination, treasury and trading, collateral management, client onboarding and reference data, market data), and a growing number of obligated outputs (supervisory financial reporting, prudential capital and risk returns, granular credit reporting, statistical returns, liquidity reporting, plus the internal assessment processes such as ICAAP and ILAAP that draw on the same underlying facts).

The default architecture — the one that emerges when nobody decides — is point-to-point: each output is built by a team that goes to the sources it needs, extracts what it needs, and applies its own transformations. It is fast for the first output and fast for the second. It is a familiar and predictable failure by the sixth.

The failure is combinatorial. With *m* sources and *n* outputs, point-to-point tends toward *m × n* interfaces, each with its own extraction, its own interpretation of source semantics, its own filters, and its own definition of concepts the source did not define explicitly. Four consequences follow, and all four are observable in this shape of estate regardless of institution:

1. **Definitional divergence.** Each output team independently derives concepts the sources do not hold — exposure, position, counterparty group, default status, product classification. The derivations differ in ways nobody notices until two returns disagree and someone has to explain the difference to a supervisor.
2. **Untraceable change impact.** A source system owner planning a change cannot be told what breaks, because the dependency set is a folklore artefact rather than a recorded one. Source changes therefore either get blocked indefinitely or land unannounced.
3. **Reconciliation as a permanent cost centre.** Because divergence is inevitable, reconciliation becomes a standing function whose output is explanations rather than fixes. That cost never falls; it grows with each new output.
4. **Non-reproducibility.** Each interface has its own temporal semantics, its own reference-data handling and its own operational history. Reproducing a submitted figure from eighteen months ago requires reconstructing all of it (see DP-29 and ADR-0003).

The regulatory dimension is what makes this decisive rather than merely untidy. Supervisors increasingly ask questions that cross output boundaries — why does the exposure in one return differ from the related figure in another, and is the difference explicable? An estate that derives the two figures independently from source cannot answer that question with anything better than a reconciliation performed after the fact. Regulatory direction has been travelling the same way for years: the ECB's **BIRD** dictionary is explicitly organised as an input layer, a set of transformation rules and an output layer, and the **IReF** programme is an effort to integrate reporting requirements rather than serve each in isolation. The industry direction of travel is toward a shared, well-defined input layer with rules on top of it. Point-to-point is the architecture that direction of travel is a reaction against.

---

## Decision

**We will build a canonical banking domain model as the single intermediate layer between source systems and every consumer, and no consumer will read a source system directly.**

Specifically:

- The canonical model holds the domain's core concepts — Party, Arrangement, Instrument, Trade Event, Position, Collateral, Classification — modelled in business terms, independent of any source system and independent of any output.
- Source systems are integrated **once each** into the canonical model. That integration is owned, and it is the only component permitted to hold source-specific semantics.
- Every consumer — regulatory outputs, analytics, extracts, downstream systems — reads the canonical layer (DP-10).
- Concepts that consumers need are added to the canonical model. They are not derived privately in a consumer (DP-11).
- The model is extended by subtyping rather than by product-specific columns on a supertype (DP-13).

This changes the interface count from *m × n* toward *m + n*, but that is a secondary benefit. The primary benefit is that **each concept is defined exactly once**, and every consumer that disagrees with the definition has to have that argument in the open, in front of the people who own it, rather than resolving it privately in a transformation.

---

## Consequences

### What this gives us

- **One definition per concept**, defended in one place, with one owner (DP-01).
- **Change impact becomes computable.** The dependency graph is recorded, so a source change can be assessed against every affected output before it happens rather than after.
- **New outputs get progressively cheaper.** The first regulatory output over the canonical model costs more than a point-to-point build. The third costs considerably less, because the concepts it needs largely exist. This repository demonstrates precisely that: the Counterparty Credit Risk lens reuses the model the FINREP lens established (ADR-0002).
- **Reproducibility becomes achievable.** Temporal semantics, reference-data versioning and lineage are solved once in the canonical layer rather than *n* times inconsistently (DP-29, ADR-0003).
- **Onboarding a new source is a bounded problem** with a known shape, rather than a negotiation with every downstream consumer.

### What this costs us

These are real, and pretending otherwise is how canonical model programmes acquire a bad name.

- **The canonical layer is slower to change than a private feed.** A consumer needing a new attribute must get it modelled, owned, defined, classified and integrated rather than simply selecting it from a source. On a deadline, that is felt as friction, and the feeling is legitimate.
- **It can become a bottleneck.** If one small team owns all canonical change, that team becomes a queue, and queues under deadline pressure produce exactly the behaviour the architecture exists to prevent: teams routing around it. This is the primary failure mode of canonical modelling and it is organisational, not technical.
- **The first delivery is more expensive.** There is no honest way to present the first output over a new canonical model as cheaper than building it point-to-point. The payback is real but it arrives later, and it must be sold on that basis rather than by understating the initial cost.
- **A poorly modelled canonical layer is worse than none.** A model that is really a union of source schemas — source names, product-specific columns, nullable sprawl — imposes the cost of an abstraction while delivering none of its benefits. This risk is highest when the model is built quickly under delivery pressure by people close to one source.
- **It concentrates risk.** One model serving everything means one modelling error affecting everything. The blast radius of a bad change is larger than in point-to-point, where errors stay local.

### Mitigations

| Cost | Mitigation |
|---|---|
| Slow to change | Classify changes by impact (DP-33) and make additive change genuinely fast — same-day chair approval, no forum slot. Most requests are additive; if they are queuing behind breaking changes, the process is wrong. |
| Bottleneck risk | Distribute modelling capability into delivery teams rather than centralising it. The forum governs the model; it does not have to be the only body that can draft a change. Track submission-to-decision time as a measure of the *forum's* performance, not the team's (see the ToR §11). |
| First delivery cost | Be explicit about it in the business case. Sequence the first two outputs deliberately so the second demonstrates the reuse — an unproven abstraction loses its funding in the second budget cycle. |
| Poor modelling | Conformance standards on source-agnosticism and subtyping (DP-12, DP-13), reviewed by humans because they cannot be fully automated. Anchor to published reference models where useful (DP-14). |
| Concentrated risk | Strong change control (DP-33), cross-lens impact assessment (DP-35), and the reproducibility spot-check as a standing forum item. |
| Teams routing around it | Treat every instance as a **model gap first and a conformance breach second**. A team that built a private derivation usually did so because the model lacked something and asking was slower than not asking. Fix the model, then fix the process that made asking slow. |

The last row is the one that decides whether this decision survives contact with delivery. A canonical model enforced purely by refusal will be circumvented. One that is genuinely faster to use than the alternative does not need to be enforced very often.

---

## Alternatives considered

### Point-to-point feeds per output

Each regulatory output builds its own extraction and transformation from source. Fastest to first delivery; requires no cross-team agreement; each team controls its own destiny.

Rejected because the costs are not linear in the number of outputs and the definitional divergence is not recoverable once established. It also makes cross-output questions from a supervisor answerable only by reconciliation after the fact. This alternative wins if and only if the estate will genuinely only ever have one or two outputs — which is not the case for any bank with a supervisory reporting obligation.

### A canonical model per regulatory framework

One model for financial reporting, another for prudential risk, another for statistical returns. Superficially attractive: each is smaller, each is owned by the function that understands it, each changes at its own pace.

Rejected because the same underlying facts — a trade, a counterparty, a collateral position — would be modelled two or three times, and the divergence problem returns at a coarser granularity where it is harder to detect. The genuine definitional differences between frameworks are real, but they are differences in *measure and treatment*, not in the underlying facts, and they are better handled explicitly (ADR-0002) than by duplicating the fact base.

### Canonical messages, no canonical store

Standardise the interchange format (ISO 20022-style messaging, or a canonical event schema) but let each consumer persist its own view.

Rejected as insufficient on its own, though the ideas are complementary. Canonical messaging solves the syntactic problem and part of the semantic one, but each consumer still derives its own state from the message stream, so position, exposure and classification derivations still diverge. It also does nothing for point-in-time reproducibility, which requires a governed persistent history. Canonical event semantics are adopted *within* the model, for Trade Event in particular.

### Adopt a vendor logical data model as the canonical layer

Licensed financial-services LDMs exist and are widely deployed. They offer breadth, a starting vocabulary and a large body of implementation practice.

Not adopted here — this repository is a public reference and vendor models are proprietary intellectual property that cannot be reproduced or paraphrased in the open. This is a constraint on this repository, not a judgement on the products: an organisation that licenses one may reasonably use it as its canonical layer, and the standards in this repository apply to it unchanged. Where an open anchor is needed, **BIRD** serves the purpose, being ECB-published, freely available, and structured as input layer → transformation rules → output layer.

### Virtualise: leave data in source, federate at query time

No persistent canonical layer; a semantic layer resolves queries across sources on demand. Attractive because it avoids copies and appears to reduce latency.

Rejected for a regulated reporting estate. Federation does not solve semantic divergence, it relocates it into the semantic layer while removing the ability to inspect the resolved result. More decisively, it cannot deliver point-in-time reproducibility: sources overwrite, and a federated query executed next year against corrected source data returns a different answer with no record of the original. That is disqualifying under DP-29. Virtualisation remains useful for exploration and for low-criticality consumption.

---

## Related standards

| Standard | Relationship |
|---|---|
| DP-10 | Directly implements this decision — no consumer reads a source system. |
| DP-11 | The complement: consumers must not reintroduce point-to-point behaviour by deriving entity logic privately. |
| DP-12, DP-13 | Guard against the "union of source schemas" failure that makes a canonical model worthless. |
| DP-33 | Change classification — the mechanism that keeps the model from becoming a bottleneck. |
| DP-36 | Golden source designation is only meaningful once a canonical layer exists to designate it against. |
| DP-29 | Reproducibility depends on the canonical layer owning temporal semantics. |

## Revisit triggers

- The estate contracts to a single regulatory output with no realistic prospect of a second.
- Submission-to-model-change lead time becomes the dominant constraint on delivery and the mitigations above have demonstrably failed.
- A regulatory-mandated common input layer (the direction IReF and BIRD point in) becomes obligatory in a form that supersedes the internal canonical model — in which case this decision should be revisited to align to it rather than duplicate it.
