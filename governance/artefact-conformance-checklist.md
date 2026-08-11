# Artefact Conformance Checklist

**Purpose:** the operational companion to `governance/data-policy-standards.md`. Use it to review a submitted data-architecture artefact, and use it *before* submission to self-assess.
**Audience:** reviewing architects, submitting delivery teams, the Data Architecture Forum.

> **Disclaimer.** Reference material, not a compliance artefact. Regulatory detail — templates, thresholds, validation rules, article references — must come from the current EBA, ECB or national competent authority texts, never from this document.

---

## 1. How to use this checklist

Every item references the standard it enforces (`DP-nn`, defined in the standards document) and states **what "pass" looks like**. That second part is the whole point. "Is lineage documented?" is answerable with a diagram nobody can act on. "Does the lineage chain terminate at a declared source attribute, with the transformation logic referenced by version?" is answerable with a yes or a no.

Item markers:

| Marker | Meaning |
|---|---|
| 🤖 | The linter checks this. Do not spend review time on it — check the linter ran and read its output. |
| 👤 | Requires human judgement. This is where your attention belongs. |
| **REG** | Applies with full force to regulatory-facing artefacts; advisory elsewhere. |

**Self-assessment is expected.** Submitting a checklist with honest gaps declared gets a faster hearing than a clean sheet the reviewer disproves in ten minutes. The first costs you one condition; the second costs you your credibility and a fortnight.

---

## 2. How to review 🔍

### 2.1 Reading order

Do not start at the top of the document. Start where the risk is.

1. **The one-page summary.** What is being asked and what happens if it is deferred. If you cannot tell after one page, that is your first finding.
2. **The linter output.** Sixty seconds. It tells you the mechanical health of the submission and where the author was careless — carelessness clusters.
3. **The consumers.** Who reads this, and does anything regulatory-facing depend on it? This determines how hard the rest of the review needs to be. Reviewing everything to regulatory standard is how architects become the bottleneck they complain about.
4. **The definitions of the two or three most contested attributes.** Not all of them. Pick the ones where the accounting lens and the prudential lens would plausibly disagree, or where a source system is known to be weak. Definitional problems concentrate.
5. **The lineage for one regulatory-facing field, end to end.** One is enough. If one is inadequate, they all are, and you have found the systemic issue rather than an instance.
6. **Alternatives considered.** Often the most informative section. It shows whether the design is a decision or an accident.
7. **Then** the artefact in full.

### 2.2 The three questions to ask first

1. **What breaks if this is wrong, and who finds out?** Establishes the review's depth. A misdesigned internal staging structure is a rework cost. A misdesigned regulatory-facing definition is a restatement and an information request from a supervisor.
2. **Where does the truth come from, and how do you know it is the truth?** Golden source, business key, identity resolution. Nearly every long-lived data defect traces back to an unexamined answer here.
3. **Could you reproduce this exactly in eighteen months?** Point-in-time discipline, versioning, reference-data pinning, retained lineage. This is the question teams have thought about least and the one auditors reach fastest.

If you only have twenty minutes, ask these three and read the lineage. You will find more than a thorough line-by-line pass on the schema.

### 2.3 What the linter catches versus what you check

| The linter owns | You own |
|---|---|
| Naming convention conformance (DP-16) | Whether the name is the *right* name |
| Definition presence, length, tautology (DP-15) | Whether the definition is *correct* and complete on population |
| Business key declared and resolvable (DP-05) | Whether it is the key the business actually uses |
| Layer dependency violations (DP-10) | Whether the layering is being honoured in spirit or worked around |
| Lineage chain completeness, six components (DP-18, DP-19) | Whether the transformation described is the right transformation |
| DQ rule coverage and declaration completeness (DP-21–DP-23) | Whether the rules test anything that would actually fail |
| Classification presence and inheritance (DP-26) | Whether the classification is right, and whether a downgrade is justified |
| One golden source per attribute (DP-36) | Whether it is the right source |
| Code-list versioning and mapping coverage (DP-38, DP-39) | Whether the mapping is *semantically* correct |
| ADR structure, status, supersession links (DP-41) | Whether the reasoning holds |
| Framework version pinning (DP-40) | Whether the framework version targeted is the applicable one |

The pattern is consistent: **the linter checks that a claim was made in the correct form; you check that the claim is true.** If you find yourself manually checking naming conventions, stop and go fix the linter — you are doing a machine's job with a human's budget.

### 2.4 Giving a decision a team can act on

A review comment must contain four things. Miss any one and you get an argument instead of a fix.

1. **What** — the specific defect, at a specific location.
2. **Why** — the standard ID, and the consequence in the team's own currency.
3. **What good looks like** — concretely enough to implement without a follow-up meeting.
4. **Severity** — is this a blocker, or a note?

**A useless comment:**

> Lineage needs more detail.

Nothing actionable. The team adds two boxes to a diagram, resubmits, and you both lose a fortnight. It also invites negotiation about how much detail is "more", which you will lose because the deadline is on their side.

**A good comment:**

> **DP-19, Blocker.** The lineage for `exposure_at_default` on the CCR output stops at the `positions_enriched` intermediate. It needs to terminate at the source attribute — for this field that means back through the collateral valuation and netting steps to the originating trade and collateral records in each contributing source.
>
> Two of the six required components are also missing: the population/filter criteria (which trades are in scope for this aggregation — the current note says "eligible trades" without defining eligibility), and the code version identifier for the netting transformation.
>
> **What passes:** the emitted lineage manifest resolves from the reported figure to a declared source attribute at every hop, with the filter predicate expressed against canonical attributes and the transformation referenced by its versioned artefact rather than described in prose.
>
> **Why it matters:** when a supervisor asks why this figure moved between two reference periods, this chain is the answer. Without the population criteria you cannot show whether the movement was a change in the portfolio or a change in scope — and that is a materially different conversation.

Note what the good comment does: it is specific about location, cites the standard, states exactly what passes, and explains the consequence in terms the team recognises. It also does not moralise. Nobody has ever fixed a design faster because a reviewer was disappointed in them.

**Two further habits.** Separate blockers from opinions explicitly — mark preferences as preferences, and let the team decline them without negotiation, or they will start treating your blockers as negotiable too. And when you reject, say what you would approve; a rejection without a described path is an invitation to escalate.

---

## 3. Checklist — Logical Data Model

| # | Check | Pass looks like | Std | |
|---|---|---|---|---|
| L1 | Every entity has one named owner | A named individual with a role, not a team or a mailbox; the person is aware and has accepted | DP-01 | 🤖👤 |
| L2 | Steward named separately from owner | Both roles recorded; if one person holds both, that is stated deliberately | DP-02 | 👤 |
| L3 | Every entity has a business key | The key components exist as attributes, and a business user would recognise them as how they identify one instance | DP-05 | 🤖 |
| L4 | Surrogate keys are opaque | No embedded source, date, type or sequence semantics; not present in any published interface | DP-06 | 🤖 |
| L5 | Cross-system identity is explicit | A named resolution structure with a recorded match basis (deterministic / composite / probabilistic with score and threshold); no fuzzy matching inside transformations | DP-07 | 👤 |
| L6 | External standard identifiers carried where they exist | LEI, ISIN, CFI, MIC, currency and country codes present as first-class attributes with correct format; the model tolerates their absence and later correction without losing history | DP-08 | 🤖👤 |
| L7 | Business keys are immutable | No update path on key attributes; corrections modelled as effective-dated events with a reason code | DP-09 | 🤖 |
| L8 | Model is source- and product-agnostic | No source-system names in entity or attribute names; no product-specific columns bolted onto a supertype | DP-12 | 👤 |
| L9 | Extension by subtype | Product or jurisdiction specifics are subtypes or a governed extension structure; supertype null density below the configured threshold | DP-13 | 🤖👤 |
| L10 | Definitions are real definitions | States what the thing is, in business language; includes unit of measure and population scope; is not the name restated | DP-15 | 🤖👤 |
| L11 | Naming convention followed | Linter clean; abbreviations from the approved list only | DP-16 | 🤖 |
| L12 | One concept, one name | No synonym pairs; regulatory or consumer vocabulary carried as recorded aliases against the canonical term | DP-17 | 🤖 |
| L13 | Classification on every attribute | Enumerated value present; personal-data flags set; any inherited-classification downgrade carries a recorded reason | DP-26 | 🤖👤 |
| L14 | Temporal treatment is deliberate | Entities needing retrospective reporting are bi-temporal with both valid time and transaction time; entities that do not need it are not bi-temporal, and the scoping choice is stated | DP-30 | 🤖👤 |
| L15 | Reference-model alignment recorded | Alignment to or divergence from an external anchor (e.g. BIRD, ISDA CDM, ISO 20022) stated with reasoning; no proprietary vendor model structure reproduced | DP-14 | 👤 |
| L16 | Cardinality and optionality are justified | Every optional relationship has a stated business case for the optional side; mandatory means mandatory in the business, not just in the load | DP-12, DP-15 | 👤 |
| L17 | Change classified | Additive / compatible / breaking, with a definitional-change assessment even where nothing structural moved | DP-33 | 🤖👤 |
| L18 | Material decisions have ADRs | Draft ADR attached for subtyping choices, identity approach, definitional resolutions | DP-41 | 🤖 |

**Reviewer's note.** L8 and L9 are where models actually go wrong, and neither is fully mechanisable. Read the attribute list of the largest supertype end to end and ask, for each attribute, "for which of these products is this null?" If the answer is "most of them" for more than a handful, the subtyping is wrong regardless of what the null-density threshold says.

---

## 4. Checklist — Physical Data Model / DDL

| # | Check | Pass looks like | Std | |
|---|---|---|---|---|
| P1 | Physical traces to logical | Every physical object maps to a logical entity or is declared as a deliberate physical-only structure with a reason | DP-10, DP-12 | 🤖 |
| P2 | Denormalisation is declared, not discovered | Any departure from the logical model is recorded with its reason and its maintenance implication | DP-12 | 👤 |
| P3 | Keys and constraints implemented | Business key uniqueness enforced or, where deliberately not enforced for load performance, compensated by a DQ rule with an owner | DP-05, DP-21 | 🤖👤 |
| P4 | Surrogate keys not exposed | Absent from views, extracts, published contracts and report mappings | DP-06 | 🤖 |
| P5 | Data types match semantics | Amounts are exact numeric with declared scale, never floating point; dates carry a stated time zone or an explicit statement that they are date-only; codes are constrained to their code list | DP-15, DP-38 | 🤖👤 |
| P6 | Currency and unit carried with every amount | No bare amount column; currency code accompanies it, and any converted amount records the rate, the rate source and the rate date | DP-15 | 🤖👤 |
| P7 | Temporal columns implement the logical intent | Valid-time and transaction-time columns present where the logical model declares bi-temporality; no soft-delete flag standing in for history | DP-30 | 🤖 |
| P8 | No in-place update of reported facts | Load logic writes new versions; audited absence of update statements against versioned entities | DP-31 | 🤖 |
| P9 | Layer boundaries enforced physically | Reporting-layer objects have no grants or dependencies on source-layer objects | DP-10 | 🤖 |
| P10 | Classification carried into the physical layer | Column-level classification metadata present; masking or restriction applied per the classification, not per developer preference | DP-26, DP-27 | 🤖👤 |
| P11 | Entitlements role-based | No individual grants outside logged, time-boxed break-glass | DP-27 | 👤 |
| P12 | Non-production data is synthetic or robustly anonymised | Environment provenance declared; re-identification risk considered in context, not assumed away by masking | DP-28 | 🤖👤 |
| P13 | Partitioning and retention align to the retention rule | Data retained at least as long as declared; personal data not retained beyond it without recorded basis | DP-32 | 👤 |
| P14 | DDL under version control | The model registry generates or validates the DDL; no hand-edited drift between registry and deployed schema | DP-33, DP-34 | 🤖 |

**Reviewer's note.** P6 is unglamorous and catches an astonishing amount. A bare `amount` column with the currency implied by context is a defect that will survive to production, get aggregated across currencies at some point, and be found by finance during a variance investigation.

---

## 5. Checklist — Data Flow / Integration Design

| # | Check | Pass looks like | Std | |
|---|---|---|---|---|
| F1 | No consumer reads a source directly | Dependency graph shows only ingestion pipelines touching source-layer objects | DP-10 | 🤖 |
| F2 | Golden source declared per attribute | Exactly one golden designation per attribute; fallback chains ordered and justified; no "last write wins" | DP-36, DP-37 | 🤖👤 |
| F3 | Lineage emitted by the pipeline | Lineage is produced by the run, as data, carrying the run identifier and code version — not drawn afterwards | DP-18, DP-20 | 🤖 |
| F4 | Lineage is sufficient **REG** | All six components: source system and attribute; ordered transformation steps with versioned logic references; filter/aggregation and population criteria; owner at each ownership change; effective-dating and as-of basis; code version and run identifier | DP-19 | 🤖👤 |
| F5 | DQ controls at ingestion, not only at output | Rules fire where data enters the canonical layer; failures have a defined action (block / quarantine / flag-and-continue) | DP-21, DP-25 | 👤 |
| F6 | Breach routing named | Each rule names a resolver role and a response expectation aligned to the reporting calendar | DP-24 | 👤 |
| F7 | Late arrival and restatement handled | Corrections create new effective-dated versions with reason codes; no in-place patching; resubmission trigger criteria stated for regulatory outputs | DP-31 | 🤖👤 |
| F8 | Reload and replay are deterministic | Re-running the same period from the same inputs with the same code version produces identical output; non-determinism (current-timestamp defaults, unordered aggregation of non-associative operations, unpinned reference data) is absent or explicitly controlled | DP-29 | 👤 |
| F9 | Reference data pinned | The run records which version of every code list and mapping it used | DP-38, DP-40 | 🤖 |
| F10 | Identity resolution happens once, in one place | Not repeated per pipeline with local variations | DP-07 | 👤 |
| F11 | Error and reject handling is visible | Rejected records are retained, counted, attributed and reconcilable to the input; silent drops are prohibited | DP-21, DP-29 | 👤 |
| F12 | Reconciliation to source exists | Record and value counts reconcile from source to canonical, with documented, explained breaks | DP-25 | 👤 |
| F13 | Classification travels with the data | Derived and aggregated outputs inherit classification unless a recorded downgrade decision applies | DP-26 | 🤖 |
| F14 | Scheduling honours the reporting calendar | Dependencies and cut-offs align to the submission timetable, with slack stated | DP-24 | 👤 |

**Reviewer's note.** F8 and F11 fail together and fail quietly. Ask to see a rerun: not a description of one, an actual rerun of a prior period, diffed. Teams are usually confident about F8 until the first time anyone tries it.

---

## 6. Checklist — Reporting or Data Product Specification

| # | Check | Pass looks like | Std | |
|---|---|---|---|---|
| R1 | Reads the canonical layer only | No source-layer dependency, no private copy of a source extract | DP-10 | 🤖 |
| R2 | No entity logic in the reporting layer | No identity resolution, no position derivation, no ungoverned derived attributes; anything conceptual has been pushed into the canonical model | DP-11 | 🤖👤 |
| R3 | Every output field maps to canonical attributes | A field-level mapping exists, with the rule for each derived field expressed against canonical attributes | DP-11, DP-18 | 🤖 |
| R4 | Population is defined | What is in and out of the report population, stated as a predicate over canonical attributes, not as prose | DP-15, DP-19 | 👤 |
| R5 | Interface contract published and versioned | Consumers, schema, refresh frequency, as-of basis, support expectation, deprecation policy | DP-33 | 🤖👤 |
| R6 | Aliases recorded, not new terms invented | Consumer-facing or regulator-facing labels are aliases of canonical terms | DP-17 | 🤖 |
| R7 | As-of basis explicit | Every published figure states its temporal basis and whether it reflects valid time or transaction time | DP-30 | 🤖👤 |
| R8 | DQ rules on every field feeding a regulatory output **REG** | Rule, dimension, severity, owner, action-on-breach — all present | DP-21 | 🤖 |
| R9 | Classification and entitlement defined for the product | Role × classification × purpose, not table grants | DP-26, DP-27 | 👤 |
| R10 | Owner and steward named for the product itself | Not only for its inputs | DP-01, DP-02 | 🤖👤 |
| R11 | Change classification and consumer notification path | Breaking changes have a dual-running window and a notified lead time | DP-33 | 👤 |
| R12 | Reconciliation to the canonical layer published | The product's totals tie back, and known differences are explained rather than tolerated | DP-25 | 👤 |

---

## 7. Checklist — Regulatory Reporting Change **REG**

This is the highest-scrutiny artefact type. Everything above applies; these are additional.

| # | Check | Pass looks like | Std | |
|---|---|---|---|---|
| G1 | Accountable executive named | The person accountable for the submission, not only the data owners | DP-04 | 👤 |
| G2 | Framework version pinned | The artefact states which published version of the framework and which reference periods it implements — and the reviewer has confirmed that version is the applicable one against the authority's own published text, not a summary | DP-40 | 🤖👤 |
| G3 | Interpretation is owned elsewhere and evidenced | The reporting-policy function has signed the interpretation; the architecture review covers implementation only. The paper cites where the requirement comes from, and cites it *accurately* — a pointer to the current authoritative text beats a paraphrased citation every time | DP-04, DP-40 | 👤 |
| G4 | Cross-lens impact assessed and signed | Both the finance lens and the risk lens have assessed the change and signed. A change requested by one lens is never approved without the other's assessment | DP-35 | 👤 |
| G5 | Definitional conflicts reconciled, not averaged | Where the accounting view and the prudential view legitimately differ, both measures exist, both are named distinctly, and the reconciliation between them is published — not a single blended figure that satisfies neither | DP-11, DP-35 | 👤 |
| G6 | Lineage complete for every affected field | Six components, terminating at source attributes | DP-18, DP-19 | 🤖 |
| G7 | Reproducibility demonstrated, not asserted | A prior period has been re-run and diffed; differences are explained; point-in-time strategy, reference-data pin and code-version pin are all declared | DP-29 | 👤 |
| G8 | Applicability period declared | First reference period the change applies to, and whether prior periods are restated | DP-34 | 🤖👤 |
| G9 | No manual adjustment outside the model | Any top-side adjustment is a modelled, owned, evidenced entity with lineage — never an overtyped cell, never a spreadsheet applied after generation | DP-34 | 👤 |
| G10 | Code-list mappings complete | Every source value maps or is explicitly out of scope; unmapped values raise an alert rather than defaulting silently into an "other" bucket | DP-39 | 🤖👤 |
| G11 | Validation rules considered | The framework's own validation and consistency rules are implemented or their absence is a stated, owned gap; rules are taken from the authority's current published rule set | DP-21, DP-40 | 👤 |
| G12 | Restatement path defined | If this change alters previously reported figures, the resubmission decision, its criteria and its owner are stated | DP-31, DP-34 | 👤 |
| G13 | Retention covers the submission's full obligation period | Data, code, reference data and lineage all retained together — retaining the data but not the code that produced it fails the reproducibility test | DP-29, DP-32 | 👤 |
| G14 | ADR raised for any definitional resolution | Especially cross-lens resolutions — these are the decisions most likely to be questioned years later | DP-41 | 🤖 |

**Reviewer's note on G5.** This is the item that most repays scrutiny and the one most often fudged under deadline. Accounting measurement and prudential measurement of the same exposure legitimately differ — they answer different questions for different audiences. The failure is not the difference; it is a design that hides it, either by forcing one number to serve both or by building two disconnected marts so nobody ever has to explain the gap. Reject both. What passes is: two named measures, one model, a published reconciliation, and an ADR explaining why they differ. See `governance/adr/0002-one-model-two-lenses.md`.

**Reviewer's note on G9.** Ask directly, and ask twice: "is there any spreadsheet between the pipeline output and the submitted file?" The answer is often yes, and it is often owned by someone who is not in the room. Manual adjustment at the end of a regulatory pipeline is the largest single source of unexplainable variance in banking reporting estates, and it does not appear in any design document — you have to ask.

---

## 8. Recurring non-conformances and what they usually indicate

Findings cluster. After a few dozen reviews you stop seeing individual defects and start seeing symptoms, which is considerably more useful — treating the symptom fixes one artefact, treating the cause fixes the next twenty.

| What you see | What it usually means | What to do about it |
|---|---|---|
| A supertype with forty attributes, most of them null for most products | Subtyping was skipped under delivery pressure and every new product added a column (DP-13) | Do not accept "we'll refactor later". Require the subtype now; the cost only ever rises, and every consumer built in the meantime hard-codes the null-handling |
| Lineage that is a diagram rather than emitted metadata | Lineage was treated as documentation, produced at the end for a governance gate (DP-18) | Reject on principle, not on detail. Retrofitting emitted lineage is cheaper than the audit finding, and hand-drawn lineage is wrong within a sprint |
| Two fields that are obviously the same concept under different names | No glossary discipline, or two teams that have not spoken (DP-17) | Fix the naming, then ask *why* the teams did not speak. The naming is the symptom |
| Reporting-layer SQL that joins across five canonical entities and invents a concept | The canonical model is missing something and the team routed around it rather than asking (DP-11) | Take it as a model gap first and a conformance breach second. Teams route around models that are slow to change — see ADR-0001 on the bottleneck risk |
| "Eligible", "in scope", "active" used in a population definition without a predicate | Nobody has yet had to defend the number (DP-15, R4) | Require the predicate before approval. This is a ten-minute fix now and a fortnight of archaeology in eighteen months |
| Golden source designated as "whichever feed is most complete" | The designation was never actually made; it is being described rather than decided (DP-36, DP-37) | Send it back for a decision with a named decider and a recorded reason |
| A reference list embedded in a transformation as a `CASE` statement | Code-list governance is absent for that domain (DP-38, DP-39) | Extract the list, give it an owner and effective dates. `CASE` statements are unversioned reference data with none of the controls |
| No answer to "have you re-run a prior period?" | Reproducibility has been assumed rather than tested (DP-29) | Make it a condition of approval, with a date. Assumed reproducibility fails more often than not on first attempt |
| A clean self-assessment on a large, complex submission | Either exceptional work or the checklist was completed at the end, in one sitting, by someone who did not build it | Spot-check three items hard. If two fail, return the whole submission for genuine self-assessment |

The final row is not cynicism. It is calibration: a large artefact with no self-declared gaps is statistically unusual, and treating it as a signal saves time for everyone — including teams whose work genuinely is that good, because you check three items instead of eighty.

---

## 9. Review outcome summary

Record the outcome in the form the Data Architecture Forum expects (see `governance/data-architecture-forum-tor.md` §7).

| Field | Content |
|---|---|
| Artefact | Name, version, type, submitting team |
| Regulatory-facing? | Yes / No — determines review depth |
| Linter status | Clean / findings listed with justification |
| Blockers | Standard ID, location, what passes |
| Errors | Standard ID, location, what passes |
| Warnings / advisory | Marked clearly as non-gating |
| Waivers requested | Standard, reason, owner, expiry date |
| Recommendation | Approve / approve with conditions / defer (with the specific question and return date) / reject (with reasons and the path to approval) |
| Conditions | Each with a named owner, a due date and a verification method |
| ADR required | Yes / No; if yes, owner and date |

**Before you send it.** Read your own review back and check three things. Is every blocker tied to a standard ID? Could the team implement every "what passes" without booking a meeting with you? Have you marked your preferences as preferences? If any answer is no, you have written a document that generates an argument rather than a fix.

---

*Reference material, not a compliance artefact. Companion to `governance/data-policy-standards.md`. Verify all regulatory detail against the current published texts of the relevant authority.*
