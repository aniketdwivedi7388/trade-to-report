# 0004. Governed lakehouse with domain ownership as the target architecture

## Status

Accepted · Data Architecture Forum
Depends on ADR-0001 (canonical domain model), ADR-0003 (lineage as a first-class artefact)

---

## Context

The methodology question — lake, warehouse, mesh, fabric, lakehouse, or something agentic — is usually argued as a matter of taste, vendor alignment or fashion. For a banking domain carrying a regulatory reporting obligation it is none of those. The obligation imposes four properties that any candidate architecture must deliver, and most of the debate resolves once they are stated:

| Property | What it demands |
|---|---|
| **Singular accountability** | A submission is signed by one accountable executive. Accountability cannot be federated, distributed or shared, however the delivery is organised. |
| **Definitional consistency** | Shared concepts — counterparty, default, exposure, netting set — must mean one thing across every contributing domain, or the cross-output questions cannot be answered (ADR-0002). |
| **Exact reproducibility** | A submitted figure must be reproducible for its full retention period: data, code, reference data and lineage retained together (DP-29, ADR-0003). |
| **Traceable, defensible change** | Every material change explicable after the fact, with an owner and a date. |

A fifth constraint is organisational and just as binding: the estate has many delivery teams, uneven data capability across them, and source systems ranging from modern platforms to vendor packages with no data team at all. An architecture that assumes uniform maturity will not survive contact with the estate.

This repository runs on DuckDB with synthetic data. That is an implementation convenience for a reference implementation, not an architectural claim — the decision below is about the *pattern*, which is engine-independent. Where the pattern needs a specific capability (ACID transactions, schema enforcement, snapshot isolation), that is stated as a capability requirement rather than a product.

---

## Decision

**We will adopt a governed lakehouse with domain ownership — a deliberate hybrid — rather than a pure data lake, a pure warehouse, a pure data mesh, or a fabric-first virtualisation approach.**

Concretely:

### 1. Lakehouse as the storage and processing substrate

Open table formats over object storage, providing the capabilities the obligation requires: **ACID transactions**, **schema enforcement and controlled evolution**, **snapshot isolation**, and open formats that avoid locking the estate's history into one vendor's engine. One substrate serves both regulatory reporting and analytical work, so there is no second copy of the truth with a different lifecycle.

> **A warning about time travel.** Table-format time travel is not business bi-temporality and must not be relied on as though it were. It gives you *transaction time on the table* — how the table looked at a point in the past. It does not give you **valid time**: when the fact was true in the world. Regulatory reporting needs both (DP-30), and valid time must be modelled explicitly in the canonical model. Snapshot retention is also typically configured in weeks and expired by table maintenance operations, whereas the regulatory retention obligation runs for years. Teams that assume time travel satisfies DP-29 discover otherwise at the first spot-check.

### 2. Layering is mandatory and enforced

Source landing → canonical domain model → lens/reporting layer. No consumer reads a source directly (DP-10); no entity logic in the reporting layer (DP-11). The lakehouse makes a single-substrate architecture cheap, which makes layer violations *technically* easy — everything is one query away. Enforcement is therefore structural, via the linter walking the emitted lineage graph (ADR-0003), not conventional.

### 3. Domain ownership, taken from mesh

Business domains own their data: named owner and steward per entity (DP-01, DP-02), owning definitions, quality and the interface contract. Ownership sits with the people who understand the meaning, not with a central team acting as a bottleneck of interpretation.

### 4. Data as a product, taken from mesh

Published outputs are products: versioned interface contracts, declared consumers, refresh and as-of semantics, quality expectations with severities, deprecation policy (DP-21, DP-33). Consumers are customers, not recipients.

### 5. Self-serve platform, taken from mesh

The governed path is the fast path: a model registry that generates DDL, a pipeline framework that emits lineage by default, project templates with metadata stubbed, the linter in the IDE and the pull request. This is the mitigation for the canonical model's bottleneck risk (ADR-0001) and the practical answer to the adoption problem.

### 6. Computational governance — mandatory, not negotiated

Mesh's fourth tenet, federated computational governance, is the right idea and it is adopted here with one deliberate change: for the regulatory core, the global rules are **mandatory and centrally set**, not negotiated between domains. The standards are machine-checked by the linter and enforced in the pipeline (DP-41 and the standards set generally). Domains have autonomy over how they model their own internals and full autonomy over their private assets. They do not have autonomy over shared canonical concepts, lineage sufficiency, classification, or reproducibility.

That single change is what separates this from mesh, and it is not a small one — it is the reason the architecture is described as a hybrid rather than as mesh with a warehouse in it.

### 7. Active metadata, taken from fabric

Metadata is operational, not descriptive: lineage drives impact analysis and conformance checks; classification drives entitlement; the model registry drives DDL generation. Metadata that only informs humans is a catalogue. Metadata that enforces things is a control.

---

## Why pure mesh struggles under a regulatory reporting obligation

Mesh's diagnosis is largely right — centralised data teams do become bottlenecks, and they do become the least-informed owners of meaning. Its remedies are good. The difficulty is specific and it is not about scale or maturity.

**Accountability cannot be federated, but mesh federates ownership.** A regulatory submission has one signatory. If a figure in it is wrong because three domains each made a locally reasonable decision, the accountable executive cannot distribute the consequence back across those domains. Mesh has no mechanism for a *singular external accountability* running across the products it federates; it assumes accountability decomposes along the same lines as ownership. Under a reporting obligation it does not.

**Mesh optimises for local semantic autonomy; the obligation forbids it for shared concepts.** Mesh handles the same concept meaning different things in different domains — the polyseme — by accepting the difference and defining interoperability at the edges. That is genuinely good design for most analytics. It is unacceptable for the shared regulatory core, where *default*, *counterparty group* and *netting set* must mean exactly one thing across every contributing domain, and where an unreconciled difference between two domains' definitions is a reporting error rather than an interesting local variation. ADR-0002 exists precisely because definitional differences must be reconciled and published, and that requires a shared canonical substrate that mesh does not prescribe.

**Reproducibility is a whole-chain property, and mesh distributes the decisions that determine it.** A report is only as reproducible as its least disciplined contributing product. If each domain chooses its own temporal semantics, retention and versioning approach, the composite is not reproducible, and the failure will not be detected in any single domain's testing. This cannot be fixed by asking nicely at a federated governance forum; it has to be an unconditional platform property.

**Field-level lineage across independently built products degrades.** End-to-end lineage of the sufficiency required by DP-19 is hard enough within one governed framework. Across many products built by teams with autonomy over their tooling, it holds only if lineage emission is mandated and standardised — at which point the platform is meaningfully centralised, whatever the organisation chart says.

**Mesh assumes capability that regulated estates do not evenly have.** Several critical sources are vendor packages with no data engineering team. There is nobody to own a data product there in the mesh sense. Pretending otherwise produces nominal ownership, which is worse than acknowledged central ownership because it is invisible.

None of this makes mesh wrong. It makes **pure** mesh wrong here, and it locates the boundary precisely: distribute ownership of meaning and of delivery; centralise the rules that make the composite defensible.

---

## Where agentic patterns belong 🤖

Agentic and LLM-based patterns are genuinely useful in this estate, and the boundary is a single test:

> **Could you reproduce this exactly in eighteen months, and can you name the human who decided it?**
> If either answer is no, the agent does not belong in that path.

### Where they belong

| Use | Condition |
|---|---|
| Drafting transformation code from a specification | Output is reviewed, versioned and tested like any code. The agent is a typing accelerator, not an author of record. |
| Drafting definitions, glossary entries and ADR first cuts | Human owner approves. Improves the worst failure mode in DP-15 — definitions nobody had time to write properly. |
| Proposing DQ rules from data profiling | Proposals only. A rule enters the estate through the normal declaration path with an owner and a severity. |
| Proposing code-list mappings | Proposal plus evidence; the mapping is approved and versioned as a governed artefact (DP-39). Never auto-applied. |
| Triage and investigation support | Summarising lineage chains, diffing two runs, clustering DQ breaches, drafting a first hypothesis for a reconciliation break. High value, zero effect on the figures. |
| Impact analysis over the lineage graph | Reading emitted metadata to summarise blast radius for a proposed change. |
| First-pass conformance commentary | Drafting review comments against the checklist for a human reviewer to accept, amend or discard. |
| Synthetic test data generation | As used in this repository. |

The pattern is consistent: agents work on **metadata, code and analysis** — the things a human then reviews and versions — and never on the figures.

### Where they do not belong

- **In the deterministic path that produces a submitted figure.** A non-deterministic component in the pipeline breaks DP-29 by construction: you cannot reproduce exactly what you cannot re-execute identically. This is not a maturity judgement that improves with better models; it is a property of the requirement.
- **Deciding golden source, resolving counterparty identity, or classifying an exposure** where the decision affects a reported number without a recorded human decision (DP-07, DP-36, DP-37).
- **Approving anything.** Not model changes, not waivers, not conformance. Approval is an accountability act and accountability requires a person (DP-01, DP-04).
- **Interpreting a regulatory requirement.** Out of scope for the forum itself (ToR §2.2), and emphatically out of scope for a model that will produce a fluent, confident and occasionally invented answer. An invented template reference or article number is worse than no answer.

Agents are also **consumers** of the canonical model, and as consumers they are governed like any other: classification and entitlement apply (DP-26, DP-27), and an agent with broad read access is an access-control decision, not a technical convenience.

---

## Consequences

### What this gives us

- One substrate for regulatory and analytical work, with the transactional and schema guarantees the obligation requires.
- Domain ownership of meaning, without domain autonomy over the rules that make the composite defensible.
- A self-serve platform that makes conformance the default output of the standard toolchain rather than an act of virtue.
- Open formats, so the estate's retained history is not hostage to one engine's lifecycle — material when retention runs for years.
- A clear, testable boundary for agentic patterns that lets the estate adopt them enthusiastically where they are safe.

### What this costs us

- **Hybrids need explaining.** "We do mesh" and "we do a lakehouse" are both easier to communicate than a considered position on which parts of each. Expect to re-explain the boundary regularly, particularly to domains that read the autonomy half and not the mandatory half.
- **Central rules create friction with domain autonomy.** Domains will occasionally want a definition or a temporal treatment they cannot have. That friction is the architecture working, and it still costs goodwill.
- **The platform is a hard dependency.** If the self-serve platform is under-invested, this degrades into central governance with none of the mesh benefits — the worst of both, and the most common way this pattern fails.
- **Single-substrate convenience invites layer violations.** Everything being one query away is exactly what makes DP-10 easy to breach.
- **Open table formats are still maturing** in areas that matter here: cross-engine consistency, maintenance operations that interact badly with long retention, and the time-travel misunderstanding above.

### Mitigations

| Cost | Mitigation |
|---|---|
| Explaining the hybrid | This ADR, cited at every forum where the question resurfaces. New opinion does not reopen a decision. |
| Autonomy friction | A short, explicit list of what is centrally mandated (shared canonical concepts, lineage sufficiency, classification, reproducibility, naming) — autonomy everywhere else, genuinely. |
| Platform dependency | Fund the platform as a product with its own owner and roadmap; track submission-to-decision and linter-findings-at-submission (ToR §11) as its health measures. |
| Layer violations | Structural enforcement via the lineage graph, not convention. |
| Format maturity and time travel | Model valid time explicitly; pin reference data; retain regulatory history under an explicit retention policy independent of table snapshot expiry; test with the reproducibility spot-check. |

---

## Alternatives considered

### Pure data lake, schema-on-read

Rejected. Deferring schema to read time pushes semantics to every consumer, which reproduces point-to-point divergence inside a single storage layer (ADR-0001) — the same problem with better economics. Lacking transactional guarantees, it also cannot underwrite reproducibility. The failure mode is well documented and it is not a matter of discipline.

### Classical warehouse only

Strong on consistency, conformance and control — genuinely good at the regulatory job. Rejected as the whole answer because it handles semi-structured and high-volume data poorly, tends to centralise ownership of meaning in a team that does not hold it, and historically couples the estate's retained history to one vendor's platform. The lakehouse keeps the warehouse's guarantees where they are needed and drops the constraints that are not.

### Pure data mesh

Rejected for the reasons set out above: accountability does not federate, shared regulatory concepts cannot tolerate local semantic autonomy, and reproducibility is a whole-chain property that distributed decisions cannot guarantee. Its four tenets are adopted, three of them substantially unchanged and the fourth — federated computational governance — made mandatory for the regulatory core.

### Data fabric as the primary pattern

Rejected as the primary access pattern, adopted in part. Metadata-driven automation and policy enforcement are taken up directly (§7). Virtualisation as the main route to data is rejected on the same ground as in ADR-0001: a federated query re-executed next year against corrected sources returns a different answer with no record of the original, which is disqualifying under DP-29.

### Agentic-first architecture

An architecture in which agents dynamically assemble data products or resolve requests at run time. Rejected outright for the regulatory path — non-determinism is incompatible with exact reproducibility, and no amount of model improvement changes that. Adopted enthusiastically for the metadata, code-drafting and analysis roles listed above, where the human review and versioning steps preserve both properties in the boundary test.

---

## Related standards

| Standard | Relationship |
|---|---|
| DP-10, DP-11 | Layering, enforced structurally on a single substrate. |
| DP-01, DP-02 | Domain ownership — mesh's best idea, adopted. |
| DP-29, DP-30 | Reproducibility and bi-temporality — the properties that rule out pure mesh, pure lake and fabric-first virtualisation. |
| DP-18–DP-20 | Emitted lineage, which the platform must supply by default. |
| DP-26, DP-27 | Classification and entitlement — including for agent consumers. |
| DP-33 | Change classification, the mechanism that keeps central rules from becoming a queue. |
| DP-41 | This decision is itself the ADR the standard requires. |

## Revisit triggers

- Open table format capability changes materially in retention, cross-engine consistency or temporal support, such that current workarounds are unnecessary.
- Domain data capability becomes uniformly high across the estate, weakening the capability argument against a more federated model.
- A regulatory-mandated common input layer (the direction BIRD and IReF point in) becomes obligatory in a form that constrains the substrate choice.
- Deterministic, replayable agentic execution becomes demonstrable — with an auditable, re-executable record of every decision — which would move the boundary in §"Where agentic patterns belong", though not the principle behind it.
