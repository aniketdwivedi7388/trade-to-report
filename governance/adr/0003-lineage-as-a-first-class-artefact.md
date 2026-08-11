# 0003. Lineage as a first-class artefact, emitted by the pipeline

## Status

Accepted · Data Architecture Forum
Depends on ADR-0001 (canonical domain model over point-to-point)

---

## Context

Every regulatory reporting estate is asked, sooner or later, some version of this question:

> This figure. Where did it come from, what was included, what rule was applied, and why is it different from the equivalent figure last quarter?

The question arrives from supervisors, from internal audit, from the accountable executive who signs the return, and from the team's own investigation of a variance. It has a short answer in a well-built estate and no satisfactory answer in most.

The usual response is documented lineage: a mapping spreadsheet, a set of diagrams in a modelling tool, or a catalogue populated by a discovery exercise. All three share a defect that is fatal in this context — **they describe intent, not execution**. They are accurate on the day they are produced and decay from that moment. They record what the pipeline was designed to do, not what the run that produced the submitted number actually did. When the two diverge, which is precisely when lineage matters, hand-maintained lineage is confidently wrong.

Three properties make this worse in regulatory reporting than in general analytics:

1. **The question is retrospective.** Nobody asks about today's figure. They ask about a figure submitted several quarters ago, produced by a pipeline version that no longer exists, over source data that has since been corrected.
2. **The answer must be defensible, not plausible.** "Our documentation says it comes from the lending system" is a weaker position than a record of the run that shows it did.
3. **Population is usually the crux.** Most variance investigations resolve into a scope question — which rows were in and which were out — and boxes-and-arrows lineage almost never captures filter and aggregation criteria.

There is also a governance-fatigue dimension worth stating plainly. Lineage documentation maintained by hand is work that competes with delivery, produces no immediate benefit to the team doing it, and is therefore the first thing to lapse under deadline. Any lineage approach that depends on discipline rather than mechanism will fail, and it will fail silently, and it will look complete right up until it is examined.

---

## Decision

**We will treat lineage as data produced by the pipeline, at the same time as the output, versioned with the code that produced it, and retained for as long as the output it explains.**

### 1. Lineage is emitted, not documented

The pipeline emits lineage metadata as part of its execution. The lineage record for a run is an artefact of that run, carrying its run identifier and its code version (DP-18, DP-20). Nobody draws it, and nobody can edit it independently of the code — lineage that can be revised without changing the pipeline is documentation, and documentation is not evidence.

Hand-drawn diagrams remain useful for explaining the architecture to humans. They are explicitly **not** the lineage record and carry no evidential weight.

### 2. "Sufficient lineage" is defined, not left to judgement

A lineage record for a regulatory-facing field is sufficient only if it contains all six of the following (DP-19):

| # | Component | What adequate looks like | Why it is there |
|---|---|---|---|
| 1 | **Source system and source attribute** for every contributing input | The chain resolves to a declared source attribute, not to an intermediate table | Without termination at source, the chain merely relocates the question |
| 2 | **Every transformation step, in order**, each referencing its versioned logic artefact | A pointer to the code or rule object at a specific version — not a prose summary of what it does | Prose summaries drift from the code within one release, and they cannot be re-executed |
| 3 | **Filter, aggregation and population criteria** | The predicate that determined inclusion, expressed against canonical attributes | This is the component most often missing and most often needed. "Eligible trades" is not a population definition |
| 4 | **Business owner at each hop where ownership changes** | A named owner, per DP-01 | Tells the investigator who to ask, which is half the elapsed time in any variance investigation |
| 5 | **Effective-dating and as-of basis** | Which temporal basis the step used — valid time or transaction time, and as of when (DP-30) | Two lenses over one model use different as-of conventions; a chain that does not state which is ambiguous |
| 6 | **Code version and run identifier** | The specific version that executed, and the specific run | Turns lineage from a description into a reproducible claim |

Components 1, 2, 3 and 6 are Blockers. Components 4 and 5 are Errors. The linter checks all six are present and non-placeholder; a human still has to judge whether the transformation described is the *right* transformation.

### 3. Field-level, for regulatory-facing fields

Table-level lineage is insufficient for anything on a regulatory path. The question is always about a figure, and a figure is a field. Table-level lineage is acceptable for non-regulatory internal assets, where the cost of field-level capture is not justified — this is a proportionality judgement, made deliberately, not a gap.

### 4. Lineage carries the reproducibility obligation

Lineage is the mechanism, but the obligation is DP-29: **a submitted regulatory report must be exactly reproducible on demand**, for its full retention period. That requires four things retained together:

- the **data** as it stood at the original production point (bi-temporal history, DP-30);
- the **code** at the version that ran (DP-34);
- the **reference data** at the version that was used — code lists, mappings, taxonomies, rates (DP-38, DP-39);
- the **lineage** record linking them.

Retaining any three of the four fails. The most common omission is reference data: teams version their code carefully and let a code list be updated in place, which quietly makes every prior period irreproducible.

The obligation is stronger than "we could rebuild it". It is: *re-run the original reference period and get the same numbers*. Where the correct answer has since changed — a source correction, a restatement — the estate must produce **both** the original figure and the corrected one, and explain the delta (DP-31). "We reran it and got a different number because the source was corrected" is a true statement and an unacceptable answer.

Because assumed reproducibility fails on first attempt more often than not, this is tested rather than asserted: a prior period is re-run and diffed as a standing forum item (ToR §9). A reproducibility capability that has never been exercised is a hypothesis.

### 5. Lineage is queryable, and it is used

Lineage held as data supports uses that documentation cannot:

- **Impact analysis.** A source system change is assessed against every affected regulatory field, mechanically, before the change happens.
- **Conformance checking.** The linter walks the emitted graph to enforce DP-10 (no consumer reads a source directly) and DP-19 (sufficiency). Layer violations are detected structurally rather than by review.
- **Variance investigation.** Two runs' lineage records are diffed to see what changed — code version, reference data version, population — before anyone looks at the data.
- **Regulatory response.** The chain is the answer, produced in hours.

The last point sells the first three. Teams adopt emitted lineage properly after the first information request they answer in a day.

---

## Consequences

### What this gives us

- **Lineage that is true of the run that produced the number**, not of the design as it was last documented.
- **Reproducibility becomes achievable and testable** rather than aspirational.
- **Impact analysis becomes mechanical**, which is what makes the canonical model's change control workable at all (ADR-0001).
- **No separate lineage-maintenance activity** competing with delivery, and therefore nothing to lapse under deadline.
- **Evidence rather than assertion** at audit and supervisory review.

### What this costs us

- **Every pipeline must emit it.** This is a framework obligation and a real engineering cost, largest at the start and on legacy components that were not built for it.
- **Legacy and third-party components resist.** Some tools do not expose what they did. Each becomes either a wrapper, an inference from inputs and outputs, or a declared gap with an owner — and declared gaps are the honest option, not the failure.
- **Volume.** Field-level lineage per run over a large regulatory estate is a significant data asset in its own right, requiring its own retention, storage and lifecycle management.
- **Retention costs rise.** Four things retained together for the full obligation period, not one.
- **It exposes uncomfortable truths.** Emitted lineage reveals the undocumented spreadsheet step, the manual adjustment, the direct source read. That is the point, and it will not feel like it during the first quarter of adoption.

### Mitigations

| Cost | Mitigation |
|---|---|
| Per-pipeline emission cost | Emission belongs in the shared pipeline framework, so conformance is the default output of using the standard toolchain rather than an act of discipline. |
| Legacy and opaque components | A declared gap with an owner and a date, visible in the waiver register, beats a fabricated chain. Prioritise wrapping by regulatory materiality. |
| Volume and retention | Retain full field-level detail for regulatory-facing outputs; retain summarised lineage elsewhere. Proportionality is a decision, recorded. |
| Uncomfortable discoveries | Treat the first wave of findings as the system working. A programme that punishes discovery gets concealment, and concealment in this area is exactly what the estate cannot afford. |

---

## Alternatives considered

### Documented lineage in a modelling tool or spreadsheet

Cheap to start, no engineering change, immediately presentable to a governance forum.

Rejected. It records intent rather than execution, decays from the day it is written, cannot support reproducibility, and is at its least reliable in exactly the circumstances where it is needed. It is also the option most likely to be believed by people who have never tested it.

### Catalogue-driven lineage by static code parsing

A catalogue tool parses SQL and pipeline definitions and infers the graph. Better than manual: automated, refreshed, no per-pipeline engineering.

Rejected as the primary mechanism, retained as a useful supplement. Static parsing recovers structure but not execution: it cannot tell you which version ran, which reference data was used, or what a dynamically constructed predicate resolved to at runtime — and dynamic construction is common in reporting logic. It gives components 1 and part of 2 of the six, and none of 3, 5 or 6. Useful for discovery and for retrofitting legacy estate; not sufficient as evidence.

### Table-level lineage only

Capture the graph at object granularity. Far cheaper, far smaller, sufficient for many impact-analysis purposes.

Rejected for regulatory-facing assets, accepted elsewhere. The question that gets asked is about a figure, and table-level lineage cannot answer it. Retained deliberately for non-regulatory internal assets as a proportionality decision.

### Reconstruct lineage on demand, when asked

Keep the code and the data; work the chain out when a question arrives.

Rejected. It is achievable in principle and fails in practice: the reconstruction is done under time pressure, by whoever is available, often by people who did not build the pipeline, against a code version that may no longer be readily assembled. It also cannot be tested in advance, so nobody discovers it does not work until the request that needs it.

### Buy an end-to-end lineage product and treat procurement as the decision

Rejected as a category error rather than on product merits. Tools help materially, and several are worth buying. But a tool cannot supply the six components if the pipelines do not emit them, and it cannot make code and reference data reproducible if they were not versioned. The decision recorded here is about what pipelines must produce; tooling is an implementation choice underneath it and is properly an Enterprise Architecture decision (ToR §3.2).

---

## Related standards

| Standard | Relationship |
|---|---|
| DP-18 | Directly implements this decision — lineage emitted by the pipeline as data. |
| DP-19 | Defines the six components of sufficient lineage. |
| DP-20 | Lineage versioned with the code that produced it. |
| DP-29 | The reproducibility obligation that lineage exists to serve. |
| DP-30 | Bi-temporality — the "data as it stood" half of reproducibility. |
| DP-31 | Restatements modelled rather than patched, so both original and corrected figures remain producible. |
| DP-34 | Reporting logic versioned and dated to a reference period. |
| DP-38, DP-39 | Reference data and mappings versioned — the most commonly forgotten limb of reproducibility. |
| DP-10 | Enforced structurally by walking the emitted lineage graph. |

## Revisit triggers

- A regulatory or industry standard for lineage interchange becomes established such that emitting to it is materially better than the internal format.
- The volume of retained field-level lineage becomes a material cost driver, prompting a proportionality review of what is retained at what granularity.
- A reproducibility spot-check fails in a way the six components did not predict — evidence that the sufficiency definition is incomplete and needs a seventh.
