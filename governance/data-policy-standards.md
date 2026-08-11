# Data Policy Standards

**Repository:** `trade-to-report` — from trade to regulatory report: a domain data architecture for banking
**Applies to:** the canonical banking domain model, the reporting layer built over it (FINREP lens, Counterparty Credit Risk lens), and every pipeline between them.
**Audience:** domain data architects, data stewards, engineering leads, the data-governance function.

> **Disclaimer.** This is a *reference architecture* and a set of *reference standards*. It is not a compliance artefact, not legal advice, and not a substitute for the current EBA, ECB or national competent authority texts. Where a real submission is at stake, the authoritative requirement is the regulator's published text as it stands on the day you submit — not this document. All data in this repository is synthetic.

---

## 1. Why standards, and why these ones 📐

A domain data architect who cannot say *no* with a reason is a diagram-drawer. These are the reasons. Each standard exists because something specific breaks without it, and each one is written so that a reviewer can decide "met / not met" without a debate about taste.

Three design principles govern the set:

1. **Testable over aspirational.** "Data should be of high quality" is not a standard. "Every field that lands in a regulatory template has at least one declared DQ rule with a severity" is.
2. **Machine-checkable where possible.** A standard a human has to remember to check is a standard that decays. This repository ships a conformance linter; where a standard is mechanically verifiable, the linter owns it and the reviewer's attention is freed for the parts that need judgement.
3. **Proportionate.** Not everything is regulatory-facing. Standards marked **REG** apply with full force only to assets on a path to a regulatory output; elsewhere they are advisory.

### 1.1 How to read a standard

Every standard carries an ID (`DP-nn`), a statement, a rationale, a verification method and a severity. IDs are permanent — a retired standard is marked withdrawn, never reused, never renumbered.

### 1.2 Severity scale

| Severity | Meaning | Effect on delivery |
|---|---|---|
| **Blocker** | The asset cannot be promoted to a regulatory-facing environment. | Hard stop. No exception without Design Authority sign-off *and* a dated remediation plan. |
| **Error** | Non-conformance that will cause defects or audit findings. | Must be fixed before release, or carry a time-boxed, owned waiver. |
| **Warning** | Non-conformance that raises cost or risk but is survivable. | Recorded as debt with an owner. Three open warnings on one asset escalate to one Error. |
| **Advisory** | Good practice. | Reviewer's note. No gate. |

### 1.3 The linter

The conformance linter in this repository (`policy-lint`) uses the **standard ID as the rule ID**. If the linter reports `DP-15`, you read section DP-15 here and you have your remediation. That one-to-one mapping is deliberate: standards documents die when they drift from the tooling, and the cheapest way to prevent drift is to make the two share a namespace.

The linter checks a **machine-readable subset** of these standards against the model metadata, the DDL, the lineage manifest and the DQ rule definitions. It reads declarations, not intentions: it can tell you that a field claims a golden source, it cannot tell you the claim is true. Standards marked 🤖 below are linted. Standards marked 👤 need a human.

**What the linter cannot do, ever:** judge whether a definition is *correct*, whether a transformation is *right*, or whether an owner is *the right owner*. Automation raises the floor. It does not raise the ceiling.

---

## 2. Ownership and accountability

#### DP-01 · Every canonical entity has exactly one named owner 👤
**Statement** — Every entity in the canonical domain model (Party, Arrangement, Instrument, Trade Event, Position, Collateral, Classification and their subtypes) has exactly one **Data Owner**, recorded as a named individual with a role, not a team, not a distribution list, not "TBC".
**Rationale** — Shared ownership is no ownership. When a definition is contested at month-end close, the escalation must terminate at one desk. Team-level ownership reliably produces a two-week search for someone empowered to decide.
**Verification** — Linter checks presence and format of the `owner` attribute on every entity; the human check is whether the named person accepts it.
**Severity** — Blocker (missing), Error (present but a group mailbox).

#### DP-02 · Owner and Steward are distinct roles with distinct duties 👤
**Statement** — The **Owner** is accountable: they approve definitions, approve changes, accept residual risk and answer to the Design Authority. The **Steward** is responsible for the day-to-day: definition maintenance, DQ rule curation, issue triage, source liaison. One person may hold both roles on small domains, but the two roles are recorded separately.
**Rationale** — Conflating them produces either an owner with no bandwidth for detail or a steward with no authority to decide. Both fail quietly.
**Verification** — Manual, at Design Authority intake.
**Severity** — Error.

#### DP-03 · Accountability survives reorganisation 👤
**Statement** — Ownership records carry a review date. When an owner leaves the role, the entity is reassigned within one review cycle; unreassigned entities are escalated to the Design Authority chair and, if still unowned after a second cycle, the domain is flagged **at risk** in the architecture register.
**Rationale** — The most common cause of an orphaned critical data element is not carelessness — it is a reorganisation nobody mapped onto the data estate.
**Verification** — Linter checks review date currency; reassignment is manual.
**Severity** — Warning, escalating to Error at second cycle. 🤖 (date currency only)

#### DP-04 · Regulatory-facing assets have a named accountable executive **REG** 👤
**Statement** — Every reporting output in scope of a regulatory submission names the accountable executive for that submission, in addition to the data owners of its inputs.
**Rationale** — Data ownership and regulatory accountability are not the same chain. The person who signs the return needs to be visible in the architecture, not just in the governance minutes.
**Verification** — Manual.
**Severity** — Blocker for regulatory-facing outputs.

---

## 3. Business keys and identity

#### DP-05 · Every entity declares a business key that is meaningful to the business 🤖
**Statement** — Every canonical entity declares a **business key**: the attribute or combination of attributes that a business user would use to identify one instance. The business key is documented even where a surrogate key is used physically.
**Rationale** — Surrogate keys are an implementation convenience. When two systems disagree about whether they hold the same counterparty, nobody resolves it by comparing integers. If the business key is undocumented, every reconciliation starts by reverse-engineering it.
**Verification** — Linter checks that each entity has a non-empty `business_key` declaration whose components exist as attributes on the entity.
**Severity** — Error.

#### DP-06 · Surrogate keys are internal, opaque and never exposed 🤖
**Statement** — Surrogate keys are permitted for physical joins and history management. They must be meaningless, must not encode source system, date, type or sequence semantics, and must never appear in a regulatory output, an extract to a downstream consumer, or an inter-domain contract.
**Rationale** — Every surrogate key that leaks becomes a de facto public identifier that you can then never change. Encoded surrogates are worse: the day the encoding runs out of range, it fails in the reporting layer rather than in the system that created it.
**Verification** — Linter checks that no attribute typed `surrogate_key` appears in a published output contract or report field mapping.
**Severity** — Error.

#### DP-07 · Cross-system identity is resolved explicitly, never implicitly 👤
**Statement** — Where the same real-world thing is known by different identifiers in different sources, the mapping is held in an explicit, owned, versioned **identity resolution** structure with a recorded match basis (deterministic on a shared identifier, deterministic on a composite rule, or probabilistic with a score and a threshold). Fuzzy matching embedded in a transformation is prohibited.
**Rationale** — Identity resolution is a business decision with credit-risk consequences — whether two exposures are to the same counterparty group changes large-exposure and concentration positions. It cannot be a side effect of a `LIKE` clause somewhere in a load script.
**Verification** — Manual review of the resolution structure; linter checks that no report-feeding transformation contains prohibited fuzzy-match constructs.
**Severity** — Blocker for counterparty identity, Error elsewhere. 🤖 (partial)

#### DP-08 · External standard identifiers are used where one exists 🤖
**Statement** — Where an open, external standard identifier exists for a concept, the canonical model carries it as a first-class attribute, using the standard's own format and validation. It is carried *in addition to* internal identifiers, never instead of the identity resolution structure in DP-07.
**Rationale** — This is the identity problem in miniature, and it is worth being concrete about it.

| Concept | Standard identifier | The problem it does *not* solve |
|---|---|---|
| Legal entity | **LEI** (ISO 17442) | Not every counterparty has one; coverage is strongest where a reporting obligation forced it. Group structure still needs resolving separately. |
| Security | **ISIN** (ISO 6166) | An ISIN identifies an issue, not a position, not a trading venue, and not always one economic exposure. Multiple listings, one ISIN. |
| Instrument classification | **CFI** (ISO 10962) | Classifies form, not accounting treatment or prudential treatment. Do not use it as a proxy for either. |
| Venue | **MIC** (ISO 10383) | Operating vs segment MIC confusion is a perennial source of mismatched trade records. |
| Currency, country | **ISO 4217**, **ISO 3166** | Historic codes and redenominations break naive joins on old data. |
| Derivative trade | **UTI** | Agreed between parties; late or amended UTIs are common. Do not assume immutability at first receipt. |
| Derivative product | **UPI** | Product-level, not trade-level. Not a substitute for economic terms. |

The point of the table is not that identifiers are unreliable — it is that **an identifier is a claim about identity, not identity itself**. The model must be able to represent an instrument whose ISIN is absent, disputed or subsequently corrected, without losing history.
**Verification** — Linter validates format and check digits where the standard defines them (LEI, ISIN); presence-where-expected is manual.
**Severity** — Error (format), Warning (absence).

#### DP-09 · Business keys are immutable; corrections are events 🤖
**Statement** — A business key value is never updated in place. If the real-world identity was recorded wrongly, the correction is modelled as an event with an effective date and a reason code, preserving the prior state.
**Rationale** — Regulatory reporting is retrospective. An in-place key correction silently rewrites history and makes a previously submitted return irreproducible — which puts you in breach of DP-25 and, more importantly, unable to answer a supervisor's question.
**Verification** — Linter checks that business-key attributes are not targets of update logic in the canonical load.
**Severity** — Blocker.

---

## 4. Canonical model conformance

#### DP-10 · Nothing consumes a source system directly **REG** 🤖
**Statement** — Consumers — reports, marts, extracts, analytics, models — read the **canonical layer**. They do not read source-system tables, source replicas, or the landing zone. The only component permitted to read a source is the ingestion pipeline that populates the canonical layer for that source.
**Rationale** — This is the single standard that most determines whether the estate stays comprehensible. The moment one report reads a source directly "just this once, for a deadline", you have two definitions of the same thing and no way to know which the auditor received. It also destroys the change-impact model: you can no longer tell a source system owner what breaks if they change a column.
**Verification** — Linter parses the dependency graph and fails any edge from a consumer node to a source-layer node.
**Severity** — Blocker for regulatory-facing consumers, Error otherwise.

#### DP-11 · The reporting layer contains presentation and rule logic only, not entity logic 🤖
**Statement** — Reporting-layer artefacts may filter, aggregate, classify per the reporting rulebook, and shape to a template. They may not create entities, resolve identity, derive a position from events, or invent an attribute that the canonical model does not hold. If a report needs a concept, the concept goes in the canonical model.
**Rationale** — Logic that lives in a report is logic that exists once per report. That is how two prudential returns end up with two different definitions of *exposure at default* and nobody notices for four quarters.
**Verification** — Linter checks reporting-layer objects for prohibited constructs (entity-creating joins, identity resolution patterns, ungoverned derived attributes not present in the model registry).
**Severity** — Error, Blocker where the derived concept feeds a submitted figure.

#### DP-12 · The canonical model is source-agnostic and product-agnostic 👤
**Statement** — Canonical entities and attributes are named and defined in business terms, without reference to the system they came from or the product family that motivated them. `Arrangement` accommodates a loan, a deposit, a repo and a derivative master agreement without a product-specific column bolted on per product.
**Rationale** — A canonical model with `arrangement_type_from_core_banking` in it is not canonical, it is a staging table with ambitions. Product-specific columns metastasise: five products become forty nullable columns and the model stops being readable.
**Verification** — Manual, at model review. Naming heuristics are advisory-linted.
**Severity** — Error.

#### DP-13 · Extension happens by subtype, not by nullable column sprawl 👤🤖
**Statement** — Product- or jurisdiction-specific attributes are modelled as subtypes or as an explicitly governed extension structure, not appended to the supertype. A supertype whose attributes are majority-null for a majority of instances has failed this standard.
**Rationale** — Nullable sprawl transfers the modelling problem to every consumer, each of whom must learn which columns apply to which product. It is also how you lose mandatory-field checking: everything becomes optional.
**Verification** — Linter reports supertype null-density above a configured threshold; the modelling remedy is manual.
**Severity** — Warning, Error above the configured density.

#### DP-14 · Conformance to external reference models is a deliberate, recorded choice 👤
**Statement** — Where the canonical model aligns to, or deliberately diverges from, an external reference model or standard, the alignment is recorded with the reason. Divergence is legitimate; undocumented divergence is not.
**Rationale** — Reference points make review faster and onboarding cheaper, and they are the honest way to answer "why is your model shaped like this?". Useful anchors for a banking domain include **BIRD** (the ECB's Banks' Integrated Reporting Dictionary — an input layer, a set of transformation rules and an output layer, covering AnaCredit, FINREP and statistical reporting, and sitting alongside the **IReF** integration programme), the **ISDA Common Domain Model** for trade lifecycle and events, **ISO 20022** for message-level semantics, and **BIAN** for service landscape. BIRD is the most directly relevant anchor for a European regulatory reporting estate because it is published, free to use, and explicitly organised around the input → transformation → output shape that this repository also adopts.
> **Note on proprietary models.** Vendor logical data models for financial services exist and are widely used in the industry; the best known is Teradata's FSLDM. They are licensed intellectual property. Reference them by name if your organisation is a licensee, but do not reproduce, paraphrase or "clean-room describe" their structure in an open repository or in documentation that leaves the licensed boundary. Nothing in this repository derives from any proprietary model.
**Verification** — Manual.
**Severity** — Advisory, Error where an alignment claim is made without evidence.

---

## 5. Naming and definition standards

#### DP-15 · Every entity and attribute has a definition that survives being read aloud 👤
**Statement** — Definitions state what the thing *is*, in a sentence a business reader understands, without restating the name and without describing the physical implementation. Definitions include unit of measure, and state the population (what is in and out of scope) where it is not obvious.
**Rationale** — "Exposure amount: the amount of the exposure" is not a definition; it is a tautology that has passed a governance gate somewhere. Bad definitions cost most at reconciliation time, when two teams discover they were both right under their own reading.
**Verification** — Linter enforces presence, minimum length and tautology heuristics (definition must not be the name with spaces). Quality is manual.
**Severity** — Error (absent), Warning (tautological). 🤖 (partial)

#### DP-16 · Names follow the domain naming convention 🤖
**Statement** — Names use the agreed convention: business terminology, singular entity names, no abbreviations outside the approved abbreviation list, no system prefixes, no type suffixes that duplicate the declared data type, consistent qualifier ordering. The approved abbreviation list is itself a governed reference list.
**Rationale** — Naming conventions are boring and they are also the highest-leverage searchability control you have. An estate you can grep is an estate you can impact-assess.
**Verification** — Linter, fully.
**Severity** — Error.

#### DP-17 · One concept, one name, estate-wide 🤖
**Statement** — The same concept carries the same name everywhere it appears. Where a consumer requires a different label (a regulatory template's own vocabulary, for instance), that label is recorded as an **alias** against the canonical term, not as a second term.
**Rationale** — Synonym drift is how a glossary becomes a dictionary of one organisation's history rather than a control. Aliasing keeps the regulator's vocabulary and the business's vocabulary both available and explicitly linked — which you need anyway, because a supervisory question will arrive in the regulator's words.
**Verification** — Linter detects duplicate definitions across differing names and differing definitions under the same name.
**Severity** — Error.

---

## 6. Lineage

#### DP-18 · Every regulatory-facing field has end-to-end lineage, captured as data **REG** 🤖
**Statement** — For every field that contributes to a regulatory output, lineage is recorded from the reported figure back to the originating source attribute(s), through every intermediate transformation, as **machine-readable metadata emitted by the pipeline** — not as a diagram maintained by hand.
**Rationale** — Hand-maintained lineage is accurate on the day it is drawn. Pipeline-emitted lineage is accurate on the day it ran, which is the day you will be asked about. See `governance/adr/0003-lineage-as-a-first-class-artefact.md`.
**Verification** — Linter walks the lineage manifest and fails any regulatory-facing field whose chain does not terminate at a declared source attribute.
**Severity** — Blocker.

#### DP-19 · "Sufficient lineage" is defined, not left to judgement 🤖
**Statement** — A lineage record for a regulatory-facing field is sufficient only if it contains **all** of: (a) the source system and source attribute for every contributing input; (b) every transformation step in order, each with its logic reference (the versioned code or rule artefact, not a prose summary); (c) the filter and aggregation criteria applied, including the population definition; (d) the business owner at each hop where ownership changes; (e) the effective-dating and as-of basis; (f) the code version and run identifier that produced the recorded instance.
**Rationale** — "Lineage exists" is not a control. Most lineage that fails an audit fails on (c) and (f): the boxes-and-arrows are right, but nobody can say which rows were included or which version of the rule ran.
**Verification** — Linter checks all six components are present and non-placeholder.
**Severity** — Blocker for (a), (b), (c), (f); Error for (d), (e).

#### DP-20 · Lineage is versioned with the code that produced it 🤖
**Statement** — Lineage metadata is produced by the same run that produces the data, carries the same version identifier, and is retained under the same retention rule as the output.
**Rationale** — Lineage that can be edited independently of the pipeline is documentation, not evidence.
**Verification** — Linter checks version-identifier presence and agreement between output and lineage manifest.
**Severity** — Error.

---

## 7. Data quality

#### DP-21 · Every regulatory-facing field carries at least one DQ rule with a severity **REG** 🤖
**Statement** — No field reaches a regulatory output without at least one declared data quality rule, each rule carrying: rule ID, dimension, expression, severity, owner, and the action on breach (block, quarantine, flag-and-continue).
**Rationale** — Undeclared expectations are discovered at submission. The action-on-breach is the part teams skip and the part that matters: a rule with no defined consequence is a metric, not a control.
**Verification** — Linter checks coverage across the regulatory field inventory and completeness of each rule declaration.
**Severity** — Blocker (no rule), Error (incomplete declaration).

#### DP-22 · DQ rules are expressed against the canonical model, not the physical table 🤖
**Statement** — Rules reference canonical entities and attributes. They survive a change of physical storage, partitioning or engine.
**Rationale** — Physical-bound rules are silently lost in every migration, and migrations are exactly when quality regresses.
**Verification** — Linter resolves every rule's referenced attributes against the model registry.
**Severity** — Error.

#### DP-23 · DQ dimensions are the agreed set, used consistently 🤖
**Statement** — Rules are classified against the agreed dimensions — completeness, validity, accuracy, consistency, uniqueness, timeliness — and each rule declares exactly one primary dimension.
**Rationale** — Not because the taxonomy is sacred, but because aggregate reporting on quality is meaningless if every team invents its own axis.
**Verification** — Linter, enumerated values.
**Severity** — Warning.

#### DP-24 · Breaches are routed to an owner with a service expectation, not to a dashboard 👤
**Statement** — Every rule's breach path names a resolver role and a response expectation appropriate to the reporting calendar. Rules whose breaches have gone unactioned for two consecutive reporting periods are reviewed for withdrawal or re-severity — a permanently-red rule is noise, and noise degrades every other control around it.
**Rationale** — The failure mode is not too few rules, it is thousands of rules nobody acts on, which converts a control environment into wallpaper.
**Verification** — Manual, at DQ forum.
**Severity** — Error.

#### DP-25 · Quality is measured where the data enters the canonical layer, not only at the report 👤
**Statement** — Controls exist at ingestion as well as at output. An output-only control tells you that something is wrong on the day of submission, which is the most expensive possible day to find out.
**Rationale** — Shift-left is not a slogan here; it is the difference between a fix and an incident.
**Verification** — Manual, at design review.
**Severity** — Warning, Error for regulatory-facing feeds.

---

## 8. Classification and confidentiality

#### DP-26 · Every attribute carries a confidentiality classification 🤖
**Statement** — Every attribute in the canonical model carries a classification from the agreed scheme, plus flags for personal data and for any special-category or otherwise restricted content. Classification is inherited by derived attributes unless explicitly and justifiably downgraded, and any downgrade is recorded with a reason.
**Rationale** — Unclassified data is treated as either over-restricted (and therefore worked around) or under-restricted (and therefore a breach waiting for an audience). Derivation-based downgrade — "it's aggregated, so it's fine" — is the most common route to an accidental disclosure and must be a recorded decision, not a default.
**Verification** — Linter checks presence, enumerated value, and inheritance consistency across derivations.
**Severity** — Blocker (absent on personal data), Error (absent otherwise).

#### DP-27 · Access is granted to roles against classifications, never to individuals against tables 👤
**Statement** — Entitlements are expressed as role × classification × purpose. Table-level grants to named individuals are prohibited outside break-glass procedures, which are time-boxed and logged.
**Rationale** — Individual grants are invisible to review and immortal in practice. They are also the reason access recertification takes three months.
**Verification** — Manual, plus platform-level entitlement review.
**Severity** — Error.

#### DP-28 · Non-production environments contain no production personal data 🤖
**Statement** — Development and test environments use synthetic or robustly anonymised data. "Masked" is not automatically sufficient — the test is whether re-identification is plausible given the other data in the environment.
**Rationale** — Regulatory reporting development touches counterparty data by definition, and the volume of it makes any laxity a large-scale problem rather than a small one. This repository ships synthetic data for exactly this reason.
**Verification** — Linter checks environment provenance declarations; the anonymisation judgement is manual.
**Severity** — Blocker.

---

## 9. Retention and reproducibility

#### DP-29 · A submitted regulatory report must be exactly reproducible on demand **REG** 🤖
**Statement** — For any regulatory output previously produced, the organisation can regenerate a **bit-identical** figure set for the original reference date, using the data as it stood at the original production point, the code as it stood, and the reference data as it stood. This holds for the full retention period of the submission.
**Rationale** — This is the standard that most often fails in practice, and it fails silently until a supervisor asks a question about a figure from three quarters ago. "We reran it and got a different number, because the source has since been corrected" is a true statement and an unacceptable answer — you must be able to produce *both* the original figure and the corrected one, and explain the delta.
**Verification** — Linter checks that every regulatory output declares a point-in-time strategy, a reference-data version pin and a code version pin. Actual reproduction is tested periodically by re-running a prior period and diffing — a test that should be scheduled, not improvised.
**Severity** — Blocker.

#### DP-30 · Bi-temporality where it is needed, and only where it is needed 👤🤖
**Statement** — Entities whose history is regulatory-relevant are bi-temporally modelled: **valid time** (when the fact was true in the world) is distinguished from **transaction time** (when the system knew it). Every regulatory query declares which basis it uses. Entities without a retrospective reporting need are not bi-temporal.
**Rationale** — The distinction between "as it was" and "as we now know it should have been" *is* the restatement question. Without both axes you can answer only one of them. Applying bi-temporality everywhere, however, is a well-intentioned way to make a model unusable and every query wrong-by-default.
**Verification** — Linter checks that bi-temporal entities have both axes and that regulatory queries declare an as-of basis; scoping is manual.
**Severity** — Error.

#### DP-31 · Late-arriving data and restatements are modelled, not patched 🤖
**Statement** — Corrections arriving after a reporting date are recorded as new versions with effective dates and a reason code. In-place update of a previously reported fact is prohibited. Whether a correction triggers a resubmission is a reporting-policy decision, recorded per output, and the decision criteria live with the output specification.
**Rationale** — Late data is normal — trade amendments, valuation corrections, counterparty reclassifications. Patching destroys the audit trail and makes DP-29 unachievable.
**Verification** — Linter checks for prohibited update patterns on versioned entities.
**Severity** — Blocker.

#### DP-32 · Retention is declared per asset and enforced, including deletion 👤
**Statement** — Every asset declares a retention period derived from the applicable obligation, and the declared period is enforced in both directions: data is kept for at least that long, and personal data is not kept beyond it without a recorded lawful basis.
**Rationale** — Over-retention is a real liability, not a safe default. The two obligations genuinely conflict on personal data, and the conflict is resolved by a recorded decision rather than by whoever configured the storage tier.
**Verification** — Manual, with platform-level policy enforcement.
**Severity** — Error.

---

## 10. Change control

#### DP-33 · Model changes are classified and routed by impact 🤖
**Statement** — Every change to the canonical model is classified as **additive** (new optional structure, no consumer impact), **compatible** (change that consumers can absorb without amendment), or **breaking** (anything else, including a definitional change with no physical change). Additive changes proceed on the standard path; compatible changes require consumer notification with a defined lead time; breaking changes require Design Authority approval and a migration plan with a dual-running window.
**Rationale** — A definitional change with no schema change is the most dangerous category and the one most often waved through, because nothing looks different. Silently redefining a field is how a regulatory series develops an unexplained step change.
**Verification** — Linter classifies structural changes automatically by diffing the model registry; definitional changes are flagged for manual classification.
**Severity** — Blocker (unapproved breaking change).

#### DP-34 · Reporting logic changes are versioned, reviewed and dated to a reference period **REG** 👤🤖
**Statement** — A change to reporting rule logic declares the first reference period to which it applies and whether prior periods are restated. Reporting logic is held in version control alongside the model — never in a spreadsheet, never in an ungoverned notebook, never as an untracked adjustment applied after generation.
**Rationale** — Manual adjustment at the end of a regulatory pipeline is endemic in banking and is the single largest source of unexplainable variance. If a top-side adjustment is genuinely necessary, it is a modelled, owned, evidenced entity — not a cell someone overtyped.
**Verification** — Linter checks that every reporting rule artefact carries an applicability period and version; the restatement decision is manual.
**Severity** — Blocker.

#### DP-35 · Every regulatory-facing change carries an impact assessment across *both* lenses **REG** 👤
**Statement** — A change to a shared canonical concept is assessed against every consuming output, explicitly including outputs owned by another function. A change requested by finance is assessed for its risk-reporting impact and vice versa, and the assessment is signed by both.
**Rationale** — This is the operational consequence of serving two lenses from one model (ADR-0002). The benefit of the shared model is consistency; the cost is that a unilateral change is now a cross-functional incident. Making the assessment mandatory is what converts that cost from a surprise into a process.
**Verification** — Manual, enforced at Design Authority intake.
**Severity** — Blocker.

---

## 11. Golden source

#### DP-36 · Every attribute has exactly one golden source per domain 🤖
**Statement** — For each canonical attribute, exactly one source system is designated **golden**. Other systems may supply the same attribute as a fallback, but the precedence is declared, ordered and justified. "Whichever arrived last" is not a precedence rule. Two golden sources for one attribute is a non-conformance, not a nuance.
**Rationale** — Multiple authoritative sources means the answer depends on load order, which means the answer is not reproducible, which breaks DP-29. Where sources genuinely disagree, the disagreement is a data quality finding to be resolved — not a modelling problem to be averaged.
**Verification** — Linter enforces cardinality of one golden designation per attribute per domain, and that any fallback chain is ordered.
**Severity** — Blocker.

#### DP-37 · Golden source designation is a business decision, recorded with a reason 👤
**Statement** — The designation names who decided, when, and on what basis (system of record for the business process, completeness, timeliness, control environment). It is reviewed when the source system materially changes.
**Rationale** — Designations made on convenience — "it was the easiest feed to get" — survive for a decade and then fail an audit on exactly that point.
**Verification** — Manual.
**Severity** — Error.

---

## 12. Reference data and code lists

#### DP-38 · Every code list is owned, versioned and effective-dated 🤖
**Statement** — Code lists (product types, counterparty sectors, classification schemes, country and currency sets, internal rating scales) are managed assets with an owner, a version, effective dates per value, and a documented source — external standard, regulatory taxonomy, or internal. Values are never silently retired; they are end-dated.
**Rationale** — Regulatory taxonomies change on the regulator's schedule, not yours. Sector and classification schemes get revised, and a historic report must still resolve the codes that were valid then. Deleting a retired value breaks every prior period.
**Verification** — Linter checks owner, version and effective dating on every registered list.
**Severity** — Error, Blocker for lists feeding regulatory outputs.

#### DP-39 · Mappings between code lists are governed artefacts, not lookup tables in a script 🤖
**Statement** — Any mapping from an internal code list to an external or regulatory one is a first-class, versioned, owned artefact with lineage, complete coverage (every source value maps or is explicitly declared out of scope), and a defined default-and-alert behaviour for unmapped values. Silent defaulting to an "other" bucket is prohibited.
**Rationale** — Silent defaulting is how a material exposure gets reported in the wrong category for a year. The unmapped case must be loud.
**Verification** — Linter checks coverage completeness and the presence of an explicit unmapped-value behaviour.
**Severity** — Blocker.

#### DP-40 · Regulatory taxonomies are pinned to a published version 🤖
**Statement** — Any artefact implementing a regulatory classification or template structure declares which published version of the framework it implements, and the applicable reference periods. Frameworks in scope for this repository's worked examples — FINREP, and the counterparty credit risk measures — are revised periodically; the implementation must state which revision it targets.
**Rationale** — "We implement FINREP" is not a statement anyone can verify. Frameworks are amended, templates are added and withdrawn, and validation rules are reissued. Version-pinning is what makes a change reviewable.

> **Do not take template detail from this document.** Nothing here quotes template cell references, thresholds or legal article numbers, deliberately. Where you need the actual reporting requirement — which template, which breakdown, which validation rule, which threshold, which article — go to the current EBA implementing technical standards and validation rules, the ECB's published texts for AnaCredit/BIRD/IReF, and your national competent authority's addenda. A confidently wrong citation in a governance document propagates faster than a correct one and is far more expensive to remove.

**Verification** — Linter checks presence of a framework version declaration on every regulatory output artefact.
**Severity** — Error.

---

## 13. Architecture decisions

#### DP-41 · Every material architecture decision is recorded as an ADR 🤖
**Statement** — Decisions that constrain future options — model structure, technology selection, layering, handling of a definitional conflict between lenses, ownership boundaries — are recorded as Architecture Decision Records in `governance/adr/`, in the repository, versioned with the code, following the template in that directory's README.
**Rationale** — The expensive question is never "what did we build?" — the code answers that. It is "why, and what did you consider instead?", asked by someone who joined two years later and is about to undo a decision without knowing what it was protecting against. ADRs are also the cheapest possible defence at audit: a dated, reasoned, alternatives-considered record of a judgement call.
**Verification** — Linter checks ADR file naming, required sections, status validity, and that superseded ADRs reference their successor.
**Severity** — Error.

#### DP-42 · An ADR is written when the decision is made, not when it is questioned 👤
**Statement** — The ADR is a precondition of the change being approved, not a post-hoc artefact produced for an audit.
**Rationale** — Retrospective ADRs are reconstructions. They record the decision that was made but rarely the alternatives that were genuinely live at the time, which is the part with the value.
**Verification** — Manual, at Design Authority.
**Severity** — Warning.

---

## 14. Standards index

| ID | Standard | Linted | Severity |
|---|---|---|---|
| DP-01 | One named owner per canonical entity | Partial | Blocker |
| DP-02 | Owner and Steward are distinct | No | Error |
| DP-03 | Accountability survives reorganisation | Partial | Warning → Error |
| DP-04 | Named accountable executive for regulatory outputs | No | Blocker |
| DP-05 | Declared business key per entity | Yes | Error |
| DP-06 | Surrogate keys internal and opaque | Yes | Error |
| DP-07 | Explicit cross-system identity resolution | Partial | Blocker / Error |
| DP-08 | External standard identifiers used where they exist | Partial | Error / Warning |
| DP-09 | Business keys immutable; corrections are events | Yes | Blocker |
| DP-10 | No direct source-system consumption | Yes | Blocker |
| DP-11 | Reporting layer holds no entity logic | Yes | Error / Blocker |
| DP-12 | Canonical model is source- and product-agnostic | No | Error |
| DP-13 | Extension by subtype, not nullable sprawl | Partial | Warning / Error |
| DP-14 | Reference-model alignment is recorded | No | Advisory / Error |
| DP-15 | Definitions that survive being read aloud | Partial | Error / Warning |
| DP-16 | Naming convention conformance | Yes | Error |
| DP-17 | One concept, one name, aliases recorded | Yes | Error |
| DP-18 | Pipeline-emitted end-to-end lineage | Yes | Blocker |
| DP-19 | Six-component sufficient lineage | Yes | Blocker / Error |
| DP-20 | Lineage versioned with its code | Yes | Error |
| DP-21 | DQ rule with severity on every regulatory field | Yes | Blocker / Error |
| DP-22 | DQ rules expressed against the canonical model | Yes | Error |
| DP-23 | Agreed DQ dimensions | Yes | Warning |
| DP-24 | Breaches routed to an owner, not a dashboard | No | Error |
| DP-25 | Controls at ingestion, not only at output | No | Warning / Error |
| DP-26 | Confidentiality classification on every attribute | Yes | Blocker / Error |
| DP-27 | Role × classification × purpose entitlements | No | Error |
| DP-28 | No production personal data in non-production | Partial | Blocker |
| DP-29 | Exact reproducibility of submitted reports | Partial | Blocker |
| DP-30 | Bi-temporality where needed | Partial | Error |
| DP-31 | Restatements modelled, not patched | Yes | Blocker |
| DP-32 | Retention declared and enforced both ways | No | Error |
| DP-33 | Model changes classified by impact | Partial | Blocker |
| DP-34 | Reporting logic versioned and period-dated | Partial | Blocker |
| DP-35 | Cross-lens impact assessment | No | Blocker |
| DP-36 | Exactly one golden source per attribute per domain | Yes | Blocker |
| DP-37 | Golden source designation recorded with a reason | No | Error |
| DP-38 | Code lists owned, versioned, effective-dated | Yes | Error / Blocker |
| DP-39 | Code-list mappings are governed artefacts | Yes | Blocker |
| DP-40 | Regulatory taxonomies pinned to a published version | Yes | Error |
| DP-41 | Material decisions recorded as ADRs | Yes | Error |
| DP-42 | ADRs written at decision time | No | Warning |

---

## 15. How standards get adopted rather than resented 🤝

Standards fail for social reasons far more often than technical ones. A few things that work, offered without sentiment.

**Make the governed path the fast path.** This is the whole game. If conforming means filling in a template and waiting a fortnight for a forum slot, while non-conforming means shipping on Friday, you will get non-conformance and you will deserve it. Ship the scaffolding: a model registry that generates the DDL, a project template with the metadata files already stubbed, a lineage emitter that comes free with the pipeline framework. When conformance is the default output of the standard toolchain, compliance stops being a virtue and becomes a side effect.

**Let the linter be the bad cop.** A tool that says "DP-19: lineage chain for `exposure_at_default` does not terminate at a source attribute" is impersonal, consistent and available at 23:00 on a Tuesday. A human saying the same thing in a review is a status contest. Automate every judgement you can so that the judgements you cannot automate arrive with your credibility intact.

**Fail fast and locally.** Run the linter in the developer's editor and in the pull request, not in a nightly governance report that lands after the merge. The cost of a finding rises by an order of magnitude at every stage it survives; a finding raised at design review that could have been caught in the IDE is a failure of the standards process, not of the developer.

**Justify in the currency of the person you are asking.** Delivery leads do not care about conceptual purity; they care about not being the team that reruns a quarter-end. Rationales in this document are written as *what breaks*, deliberately. Use them that way.

**Grade the enforcement.** Blocker on everything means the exception process becomes the real process, and the standards become theatre. Reserve Blocker for the things that genuinely cannot be unwound: reproducibility, lineage on regulatory fields, personal data in the wrong place, unapproved breaking changes. Everything else can be debt with an owner and a date.

**Make exceptions cheap, visible and expiring.** People route around a governance function that cannot say yes conditionally. A waiver with an owner, a reason and an expiry date is a control. A waiver with none of those is a hole. Publish the open waiver list — visibility does more for closure rates than any escalation.

**Show the evidence trail as a benefit, not a tax.** The teams that adopt fastest are the ones who have been through a regulatory information request with insufficient lineage. Reproducibility and lineage are not compliance overhead; they are the difference between a two-day answer and a two-month remediation programme. Say so, early and repeatedly.

**Write the standard once the pattern exists, not before.** Standards derived from a working implementation are credible and precise. Standards written in advance of any implementation are guesses with authority, and every engineer can tell the difference within one reading.

**Review the standards on a schedule and actually withdraw things.** A standards set that only grows loses the room. Retire what has been superseded by tooling, and say publicly that you have done it.

---

## 16. Document control

| Item | Value |
|---|---|
| Owner | Domain Data Architect |
| Approval body | Data Architecture Forum / Design Authority |
| Review cycle | Annual, or on material regulatory change |
| Companion documents | `governance/artefact-conformance-checklist.md`, `governance/data-architecture-forum-tor.md`, `governance/adr/` |
| Machine-readable subset | Enforced by the repository's `policy-lint` conformance linter; rule IDs match standard IDs |

*Reference architecture, not a compliance artefact. Synthetic data throughout. Verify all regulatory detail against the current published texts.*
