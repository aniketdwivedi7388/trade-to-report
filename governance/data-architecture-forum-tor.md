# Data Architecture Forum — Terms of Reference

**Also known as:** Data Design Authority
**Version:** 1.0 · **Status:** Reference template, tabled for adoption
**Companion documents:** `governance/data-policy-standards.md`, `governance/artefact-conformance-checklist.md`, `governance/adr/`

> **Disclaimer.** A reference Terms of Reference, written to be lifted into an organisation's own governance framework and amended to fit its structure, delegated authorities and regulatory footprint. It is not a compliance artefact and confers no authority by itself — authority comes from the sponsoring executive who adopts it.

---

## 1. Purpose

The Data Architecture Forum exists to ensure that the data assets of the banking domain — the canonical domain model, the pipelines that populate it, and the regulatory and analytical outputs built over it — remain **coherent, governed, explainable and reproducible** as they are changed by many teams working in parallel.

It does this in three ways:

1. **Deciding** on design questions that cross team boundaries or constrain the estate's future shape.
2. **Assuring** that submitted artefacts conform to the data policy standards, so that non-conformance is caught at design time rather than at submission time.
3. **Recording** decisions as Architecture Decision Records, so that the reasoning behind the estate survives the people who built it.

It is emphatically **not** a status meeting, not a project gate, and not a place where designs are produced. Designs arrive; the forum decides on them.

---

## 2. Scope

### 2.1 In scope

| Area | Examples |
|---|---|
| Canonical domain model | New or changed entities, relationships, subtyping decisions, definitional changes |
| Layering and conformance | Any proposal to read a source system directly; new consumption patterns; new layers |
| Golden source designation | Designation, change of designation, contested designation between domains |
| Identity and keys | Business key definition, cross-system identity resolution approach, identifier adoption |
| Regulatory-facing change | Any change that affects a submitted output, including definitional-only changes |
| Cross-lens conflicts | Where the accounting view and the prudential view require different treatment of the same fact |
| Lineage and reproducibility | Approach, tooling, sufficiency of lineage for a regulatory field |
| Data product specifications | Interface contracts, published outputs, inter-domain contracts |
| Reference data and code lists | Ownership, new lists, mappings to regulatory taxonomies |
| Technology patterns for the domain | Storage, processing and orchestration choices *within* the enterprise-approved catalogue |
| Standards themselves | Amendments to `data-policy-standards.md`, waivers, exception policy |

### 2.2 Out of scope

| Area | Where it belongs |
|---|---|
| Enterprise technology selection and vendor choice | Enterprise Architecture / Technology Council |
| Security control design, threat modelling, cryptographic standards | Information Security |
| Policy on personal data, lawful basis, privacy notices | Data Privacy / DPO |
| Release scheduling, deployment approval, incident management | Change Advisory Board / Service Management |
| Funding, resourcing, delivery sequencing | Portfolio and programme governance |
| The regulatory interpretation itself | Regulatory Reporting / Finance / Risk policy functions — the forum decides how an *agreed* interpretation is implemented in data, never what the interpretation is |

The last row matters more than it looks. The forum has no mandate to decide what a regulation requires. It has full mandate over whether the data architecture implements the agreed interpretation coherently, traceably and reproducibly. Conflating the two is how architecture forums acquire enemies and lose credibility simultaneously.

---

## 3. Authority and mandate

A forum without decision rights is a book club with minutes. The following is the delegated authority the forum requires to be worth attending, and it should be granted explicitly by the sponsoring executive at adoption.

### 3.1 The forum **decides** (binding, no further approval required)

- Approval or rejection of changes to the canonical domain model.
- Conformance of a submitted artefact to the data policy standards.
- Golden source designation within the domain.
- Business key and identity resolution approach for canonical entities.
- Layering and consumption patterns — including refusal of direct source-system consumption.
- Whether a proposed lineage approach meets the sufficiency standard for regulatory-facing fields.
- Whether a definitional conflict between lenses is resolved by reconciliation, by separate governed measures, or by a single shared measure.
- Granting, refusing and expiring **waivers** against standards up to and including Error severity.
- Adoption and amendment of the data policy standards and the conformance checklist.
- Acceptance of an ADR into `accepted` status.

### 3.2 The forum **advises** (recommendation only; decision sits elsewhere)

- Technology and platform selection (Enterprise Architecture decides; the forum states the data-architecture consequences and its preference, on the record).
- Delivery sequencing and prioritisation (portfolio governance decides; the forum states dependency and risk consequences).
- Regulatory interpretation (the reporting policy function decides; the forum states what each interpretation would cost in data terms — sometimes decisively).
- Organisational design and ownership placement (the CDO function decides; the forum identifies where ownership is missing or contested).
- Vendor product fit for a data capability.

### 3.3 The forum **escalates** (must not decide alone)

| Trigger | Escalate to |
|---|---|
| Waiver requested against a **Blocker** standard | Sponsoring executive + CDO, with the accountable executive for the affected submission present |
| Unresolved conflict between two domains after two attempts | Enterprise Architecture Board, with a written position from each domain |
| A decision that would knowingly impair reproducibility of a submitted regulatory output | Sponsoring executive + accountable executive for the submission; a documented risk acceptance is mandatory |
| Material cost or delivery impact beyond the forum's delegated threshold | Portfolio governance |
| Suspected control failure, breach, or misreporting | Immediately, through the incident and regulatory-notification process — **not** through this forum's agenda |
| Standards change with enterprise-wide effect | Enterprise data governance / CDO |

The last-but-one row is a hard rule. An architecture forum that finds itself deliberating on a possible misstatement has already made a mistake; the correct action is to raise it through the incident route the same day and let the forum handle the architectural remediation afterwards.

### 3.4 Limits

The forum cannot vary a regulatory obligation, cannot override Information Security or Privacy, cannot approve its own expansion of scope, and cannot bind another domain that is not represented in the decision.

---

## 4. Membership

### 4.1 Composition

| Role | Type | Contribution |
|---|---|---|
| **Chair** — Domain Data Architect (or Head of Data Architecture) | Permanent, voting | Runs the forum, owns the standards, holds the casting decision |
| **Deputy chair** — second senior data architect | Permanent, voting | Covers the chair; chairs items where the chair has a conflict |
| Data Governance lead (CDO function) | Permanent, voting | Policy alignment, ownership, glossary, issue management |
| Regulatory Reporting representative (finance lens) | Permanent, voting | FINREP and related supervisory reporting impact |
| Risk Data representative (prudential lens) | Permanent, voting | Counterparty credit risk and related prudential impact |
| Lead Data Engineer / platform architect | Permanent, voting | Feasibility, cost, platform pattern conformance |
| Enterprise Architecture representative | Permanent, non-voting | Alignment to enterprise target state; escalation route |
| Information Security representative | Permanent, non-voting | Classification, entitlement, control design |
| Data Owners / Stewards of affected entities | Attending for their items, voting on those items | Definitional authority for their entities |
| Subject matter experts | Invited per item, non-voting | Product, accounting, market data, legal entity, modelling |
| Secretary | Permanent, non-voting | Agenda, papers, ADR capture, action tracking, register upkeep |

### 4.2 Quoracy

A quorum requires **five voting members**, and must include:

- the chair or deputy chair; **and**
- the Data Governance lead; **and**
- **both** the finance-lens and risk-lens representatives when the item touches a shared canonical concept or any regulatory-facing output.

The second condition is deliberately strict. A model serving two lenses cannot have one lens make decisions in the other's absence — that is precisely the failure the shared model exists to prevent. Items failing this condition are deferred, not decided.

### 4.3 Delegates and continuity

Permanent members may send a named delegate with decision authority. A delegate without authority to decide does not count towards quorum — attending to "take it back to the team" converts a decision forum into a relay. Members who miss three consecutive meetings without a delegate are reviewed by the chair with their line manager; representation is a commitment, not a courtesy.

### 4.4 Conflicts of interest

A member who is the design author or the delivery owner of a submitted artefact declares it and does not vote on that item. They present, they answer, they leave the decision to others.

---

## 5. Cadence, agenda and timeboxing

**Cadence.** Fortnightly, 90 minutes, standing slot, never moved. An out-of-cycle session may be called by the chair for a genuinely time-critical decision; "our deadline is tight" is not by itself time-critical, or every item would be.

**Fast-track.** Low-impact, standards-conformant, linter-clean changes are approved by the chair between meetings and reported to the next meeting as a consent item. Most estates find the majority of submissions qualify; if yours does not, the standards are miscalibrated and that is a finding about the standards.

**Standard agenda shape.**

| # | Item | Time |
|---|---|---|
| 1 | Quorum, conflicts, minutes, matters arising | 5 min |
| 2 | Consent items — chair-approved fast-track, noted not discussed | 5 min |
| 3 | Action and waiver register — overdue items only | 10 min |
| 4 | Decision items — pre-read, discussion, decision | 45 min |
| 5 | Advisory / early-engagement items — direction sought, no decision | 15 min |
| 6 | Standing items (rotating, see §9) | 5 min |
| 7 | Decisions read back, ADR owners and dates confirmed | 5 min |

**Timeboxing rules.**

- Papers are pre-read. A presenter who walks the meeting through their document loses the remainder of their slot. This is enforced from the first meeting or it is never enforced.
- Each decision item has a declared timebox at agenda publication. At the timebox, the chair calls a decision on what is known — approve, approve-with-conditions, defer or reject. **Defer is a decision**, and it must carry the specific question that must be answered and the date it returns.
- No item runs twice on the same information. A deferred item returning without new material information is rejected.

---

## 6. Submission process

### 6.1 Lead time

| Submission | Lead time before the meeting |
|---|---|
| Decision item | 5 working days |
| Advisory / early engagement item | 3 working days |
| Consent / fast-track (chair review) | 3 working days, any time |
| Emergency item (chair discretion, must be justified) | 24 hours |

Papers arriving late roll to the next meeting. Without this, the pre-read discipline collapses within two months and the forum reverts to being presented at.

### 6.2 What an artefact must contain to be tabled

A submission is **rejected at intake** — not discussed and rejected, simply not accepted onto the agenda — unless it contains all of:

1. **A one-page summary**: what is being asked, what decision is required, by when, and what happens if it is deferred.
2. **The artefact itself** in a reviewable form (model, DDL, flow design, specification — see the conformance checklist for each type).
3. **A clean or explained linter run.** Every outstanding finding either fixed or listed with a justification and a proposed waiver. Submitting with unexplained Errors wastes six people's preparation.
4. **The conformance checklist**, self-assessed by the submitting team against the relevant artefact type.
5. **Impact assessment across both lenses** where a shared canonical concept is touched (DP-35), signed by both the finance and risk representatives *before* the meeting.
6. **Alternatives considered**, with why they were not chosen. A submission with one option is a request for a rubber stamp.
7. **Named owner and steward** for anything new (DP-01, DP-02).
8. **Draft ADR** where the item is a material decision (DP-41). Drafting it in advance usually improves the proposal, because writing the consequences section is where weak options fall over.

### 6.3 Self-assessment is meant seriously

The self-assessed checklist is not bureaucracy; it is the mechanism that shifts review effort from the forum to the team, where it is cheaper. A team that self-assesses honestly and lists its own gaps gets a faster, friendlier hearing than one that submits a clean sheet the reviewer then disproves. Say this out loud, repeatedly, until it is believed.

---

## 7. Decisions and outcomes

### 7.1 Decision types

| Outcome | Meaning | Obligations created |
|---|---|---|
| **Approve** | Conformant. Proceed. | ADR raised and moved to `accepted` within 5 working days. Decision recorded in the register. |
| **Approve with conditions** | Proceed, but specific things must be true. | Each condition has a named owner, a date, and a verification method. Conditions are tracked in the action register. Unmet conditions past their date automatically escalate to the chair, and the approval lapses if a condition is unmet at release. |
| **Defer** | Cannot decide on the information available. | The forum states the *specific* question(s) to be answered and the return date. Open-ended deferral is prohibited — if it cannot be dated it is a rejection. |
| **Reject** | Non-conformant, or a materially better option exists. | Written reasons, referencing the standard ID(s) breached or the superior alternative. The team may resubmit with changes; a rejection is never final in itself. |
| **Note** | For advisory items. | No obligation, but the direction given is minuted so that it can be relied upon at a later decision. |

**Approve-with-conditions is the workhorse outcome and should be the most common.** A forum that only approves or rejects is either too permissive or a bottleneck. Conditions let delivery proceed while risk is closed in parallel — but only if conditions are genuinely tracked, which is why they carry owners and dates.

### 7.2 How decisions are taken

By consensus where possible. Where consensus fails, the chair decides, and the dissent is minuted with the dissenter's reasoning — not softened, not summarised into agreement. A minuted dissent is a valuable artefact: it is the record that the risk was seen and consciously accepted, which is exactly what a supervisor or an internal auditor will want to establish.

### 7.3 Dissent and escalation

Any voting member may:

1. **Record a formal dissent**, minuted verbatim at their request.
2. **Escalate**, within 5 working days, to the Enterprise Architecture Board or the sponsoring executive, stating the decision, the reason for dissent and the proposed alternative.

The decision **stands and is implemented** during escalation unless the escalating member obtains a stay from the sponsoring executive. Implementation does not halt merely because someone disagreed; a forum whose decisions can be suspended by objection has no decision rights at all.

### 7.4 Recording and discoverability

- **Every decision** is recorded in the decision register with: date, item, outcome, conditions, dissent, attendees, and a link to the ADR.
- **Material decisions** are recorded as ADRs in `governance/adr/`, in the repository, versioned with the code that implements them. This is deliberate: a decision record that lives in a document management system three clicks from the code is a decision record nobody reads. One that sits beside the model is one an engineer trips over at the moment it is relevant.
- **Minutes** are published within 3 working days, to everyone in the domain, not only to attendees.
- **The waiver register** is published openly and reviewed at every meeting. Expiring waivers are visible a month ahead.
- ADR status transitions (`proposed` → `accepted` → `superseded`) are themselves forum decisions.

---

## 8. Relationships with other functions

| Function | Interface |
|---|---|
| **Enterprise Architecture** | The forum operates within EA's target state and technology catalogue. EA holds a permanent non-voting seat. Deviation from an EA standard is escalated, never decided locally. The forum is the domain-level detail EA cannot hold centrally, and it should be trusted to hold it. |
| **CDO / Data Governance** | The CDO function owns policy, the glossary, ownership models and issue management. This forum owns architectural conformance to that policy. The Data Governance lead's permanent seat is what keeps the two from diverging into two competing rulebooks. |
| **Information Security** | Classification schemes, entitlement models and control requirements come from Security. The forum applies them to the model and escalates conflicts. Security holds a veto on its own domain, exercised through its seat. |
| **Data Privacy / DPO** | Personal-data treatment, lawful basis and retention conflicts are referred, not decided. The forum surfaces where the model touches personal data and where retention obligations conflict. |
| **Change Management / CAB** | The forum approves *design*; CAB approves *release*. Forum approval is an input to CAB, never a substitute for it, and CAB should decline regulatory-facing changes lacking it. |
| **Regulatory Reporting, Finance and Risk policy** | These functions own interpretation. The forum owns implementation coherence. The two lens representatives are the standing bridge, and their joint sign-off on cross-lens impact (DP-35) is the mechanism. |
| **Internal Audit** | Not a member — auditing a forum you sit on is not a defensible position. Audit is given standing access to the decision register, ADRs, waiver register and minutes without needing to ask. |

### 8.1 Conflict between domains

Where two domains disagree — most commonly over golden source designation, over a shared definition, or over who owns an entity that both consume — the sequence is:

1. **Bilateral.** The two data owners attempt resolution directly, timeboxed to 10 working days. Most conflicts end here and should.
2. **Forum.** Both positions are tabled *in writing* by their owners. Written positions matter: they force each side to state what they need rather than what they object to, and the gap is usually smaller than the meeting suggests. The forum decides, on the criteria of business-process fit, completeness, timeliness and control environment (DP-37) — never on organisational seniority.
3. **Escalation.** Unresolved after two attempts, to the Enterprise Architecture Board with both written positions and the chair's recommendation attached.

An interim decision is always taken at step 2, even when escalating. Domains should never be blocked awaiting a governance outcome — an interim designation with a review date beats a stalemate.

---

## 9. Standing agenda items

Rotated through the 5-minute slot so each appears roughly quarterly:

| Item | Purpose |
|---|---|
| **Waiver register review** | Every open waiver, its owner, its expiry. Expired-and-unclosed is escalated. |
| **Linter findings trend** | Are findings falling? Which standard fails most? A standard that everyone fails is a badly written standard or an unsupported one. |
| **Reproducibility spot-check** | One prior-period regulatory output re-run and diffed against what was submitted (DP-29). This is the single most valuable standing item and the first one to be dropped when the agenda is full. Do not drop it. |
| **Model debt review** | Nullable sprawl, orphaned entities, unowned assets, tautological definitions. |
| **Upcoming regulatory change horizon** | What is coming from the EBA, the ECB or the national competent authority that will move the model — read from the authorities' own published timetables, not from summaries. |
| **ADR review** | Which accepted ADRs are now questionable? Supersede honestly rather than letting the record rot. |
| **Standards amendment** | Proposed additions, clarifications and — importantly — withdrawals. |

---

## 10. Worked agenda — one meeting

> **Data Architecture Forum — Meeting 24 · 90 minutes**
> Chair: Domain Data Architect · Secretary: [name] · Quorum confirmed: 7 voting, both lenses present

| # | Item | Type | Time | Papers |
|---|---|---|---|---|
| 1 | Quorum, conflicts declared (item 5: engineering lead is design author, will not vote), minutes of M23 | — | 5 min | Minutes M23 |
| 2 | **Consent** — (a) two new optional attributes on Collateral, additive, linter clean; (b) abbreviation list addition | Consent | 5 min | Fast-track log |
| 3 | **Registers** — 3 overdue conditions from M22; 1 waiver expiring in 14 days (DP-13 nullable density on Instrument) | Review | 10 min | Action + waiver register |
| 4 | **Collateral valuation frequency and as-of basis for the CCR lens.** Risk requires a valuation as-of basis that differs from the finance lens's month-end basis. Proposal: one canonical valuation event stream, two governed as-of selectors, reconciliation published. | **Decision** | 20 min | Design note, draft ADR, cross-lens impact (both signed), linter run (clean) |
| 5 | **Golden source for counterparty legal entity attributes** — contested between the client onboarding domain and the credit domain. Both written positions tabled. Bilateral attempted, not resolved. | **Decision** | 15 min | Two position papers, DP-37 assessment |
| 6 | **Netting set representation for derivative exposure aggregation.** Request to hold netting sets in the reporting layer for speed. Chair's view circulated: this is entity logic and belongs in the canonical model (DP-11). | **Decision** | 10 min | Design note, linter run (2 Errors: DP-11, DP-19) |
| 7 | **Early engagement** — approach to a forthcoming taxonomy version change; direction sought on whether to dual-run or cut over. No decision today. | Advisory | 15 min | Options paper |
| 8 | **Standing item** — reproducibility spot-check: prior-period FINREP-lens output re-run; two immaterial differences traced to an unpinned reference list (DP-38 finding raised). | Standing | 5 min | Spot-check result |
| 9 | Decisions read back; ADR owners and dates confirmed; conditions restated with owners | — | 5 min | — |

*Illustrative outcomes:* item 4 approved with conditions (reconciliation published each period; ADR-0005 raised); item 5 decided in favour of the onboarding domain as golden source for identity attributes, credit domain golden for internal rating, with a minuted dissent from the credit representative on one attribute; item 6 rejected with reasons referencing DP-11, resubmission invited with the netting set in the canonical model; item 7 noted, dual-run direction given.

---

## 11. Measuring the forum 📊

### 11.1 Measures worth tracking

| Measure | Why it matters | Healthy direction |
|---|---|---|
| Time from submission to decision | The forum's own contribution to delivery lead time | Falling, stable |
| Proportion of items decided at first hearing | Whether submission quality and pre-read discipline are working | Rising |
| Proportion of submissions handled by fast-track | Whether the governed path is genuinely lightweight | Rising |
| Conditions closed by their due date | Whether approve-with-conditions is real or a polite yes | High and stable |
| Linter findings at submission | Whether standards are being met before review, i.e. shifting left | Falling |
| Regulatory-facing defects traced to a design decision the forum approved | The forum's actual predictive value | Low, and honestly attributed |
| Reproducibility spot-check pass rate | The estate's most important property | 100%, investigated whenever not |
| Decisions later superseded within 12 months | Some is healthy learning; a lot means decisions are being taken too early or on too little | Low but non-zero |
| Attendance and delegate-with-authority rate | Leading indicator of relevance | High |

### 11.2 Vanity metrics to avoid

- **Number of decisions made.** Rewards volume. A forum optimising this will pull work in that teams could have handled, and will find reasons to revisit settled questions. The best possible quarter might have very few decisions in it.
- **Number of artefacts reviewed.** Same defect, and it actively discourages fast-tracking the routine.
- **Percentage of standards "compliant".** Trivially gamed by writing weak standards, and it measures the standards, not the estate.
- **Meeting attendance alone.** People attend meetings they fear as readily as meetings they value.
- **Number of ADRs written.** ADR count measures documentation activity. Rewarding it produces ADRs for decisions that were never decisions.
- **Waivers issued (as a negative).** Punishing waiver issuance drives waivers underground into undocumented non-conformance, which is strictly worse. Measure *expired-unclosed* waivers instead.

---

## 12. How this forum fails ⚠️

Every architecture forum fails in one of five ways. Naming them in the ToR is the cheapest available counter-measure, because it gives any member permission to say the failure is happening.

| Failure mode | What it looks like | Counter-measure |
|---|---|---|
| **Rubber-stamping** | Everything is approved. Items are presented, nodded through, minuted. Nobody has read the papers. | Mandatory pre-read with slot forfeiture; mandatory alternatives-considered section; the chair asks the three review questions (see the conformance checklist) on every item; track the rate of unconditional approvals — if it approaches 100%, the forum has stopped functioning and should be told so publicly. |
| **Bottlenecking delivery** | Teams wait a fortnight for approval on trivial changes; delivery routes around the forum or stops telling it things. | Aggressive fast-track with chair delegation; published lead times the forum holds itself to; the self-assessed checklist so teams clear their own path; treat forum-caused delay as a defect of the forum and report it in §11.1. |
| **Attendance decay** | Permanent members send juniors without authority, or stop coming. Quorum is scraped. Decisions get relitigated because "we weren't there". | Delegates must carry decision authority to count for quorum; three-absence review with the member's line manager; make the agenda visibly consequential — the fastest cure for decay is a forum that decides things people care about. |
| **Endless relitigation** | The same design question returns every few months, driven by new arrivals or by a team that lost. | ADRs with alternatives-considered as the standing answer; the rule that a deferred item returning without new information is rejected; supersede an ADR properly when the world changes rather than reopening the debate informally. New information reopens a decision. New opinion does not. |
| **Scope creep into interpretation** | The forum starts deciding what a regulation requires, or approving releases, or picking vendors. | §2.2 read aloud when it happens; the chair's explicit duty to hand items to the right owner; a quarterly check of items decided against the scope table. |

A sixth, quieter failure: **the forum becomes the only place governance happens**. If conformance is achieved solely by review, the estate cannot scale. The forum's long-term objective is to make itself progressively less necessary for routine work by pushing conformance into tooling, templates and the linter — and to spend the reclaimed time on the small number of genuinely hard cross-domain questions that no tool will ever settle.

---

## 13. Review of these Terms of Reference

Reviewed annually by the forum, and out of cycle on: a material change to the regulatory reporting footprint, a reorganisation affecting membership, or a change to the enterprise governance framework within which the forum sits.

Amendments are proposed as a decision item like any other, with alternatives considered, and are recorded as an ADR if they change the forum's authority. The chair owns this document; adoption and any change to delegated authority require the sponsoring executive.

| Item | Value |
|---|---|
| Owner | Chair, Data Architecture Forum |
| Approved by | Sponsoring executive (authority delegation) |
| Review cycle | Annual, or on trigger |
| Version | 1.0 |

*Reference template, not a compliance artefact. Amend to fit your organisation's delegated authorities before use.*
