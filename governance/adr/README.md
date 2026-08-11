# Architecture Decision Records

**Location:** `governance/adr/`
**Standard enforced:** `DP-41` (every material architecture decision is recorded as an ADR), `DP-42` (written at decision time, not when questioned)

---

## What an ADR is

An Architecture Decision Record is a short, immutable document capturing **one** architecturally significant decision: the context that forced it, the decision taken, the consequences accepted, and the alternatives that were genuinely considered and rejected.

It is not a design document. It does not describe how the thing works — the model and the code do that, and they do it more accurately. An ADR answers the question the code cannot: **why is it like this, and what did you consider instead?**

A decision is architecturally significant if it is expensive to reverse, constrains future options, affects more than one team, or resolves a genuine disagreement. If undoing it next month would cost an afternoon, it is not an ADR.

## Why this repository uses them

Three reasons, in order of how often they matter.

**1. The reasoning outlives the reasoner.** In a regulated banking data estate, the interval between a decision and the question about it is measured in years. By the time someone asks why the counterparty credit risk lens and the FINREP lens share a canonical model, the people who chose that will have moved on. Without ADRs, the successor team's options are to guess, to ask around, or — most commonly and most expensively — to assume the decision was arbitrary and undo it.

**2. They stop settled questions from being relitigated.** The same design debates recur every time the team composition changes. An ADR with a properly written *Alternatives considered* section ends the debate in five minutes: here is the option you are proposing, here is why it was rejected, here is what would have to change for that to be wrong. New information reopens a decision. New opinion does not.

**3. They are the cheapest evidence you will ever produce.** When a supervisor or an internal auditor asks why a figure is derived the way it is, a dated record showing the alternatives, the reasoning and the accepted consequences is a far stronger position than a well-meaning reconstruction. Writing it takes an hour at decision time. Reconstructing it takes a fortnight, and it is never as convincing.

They also improve the decisions themselves. The *Consequences* section is where weak options fall apart — writing down what you are accepting is uncomfortable in a way that a slide is not.

## Where they live and why

ADRs live **in the repository**, versioned with the code they explain, not in a document management system. A decision record three clicks and one login away from the model is a decision record nobody reads. One that sits beside the DDL is one an engineer trips over at the moment it is relevant, which is the only moment that counts.

## Lifecycle

```
proposed ──► accepted ──► superseded
    │
    └──► rejected
```

| Status | Meaning |
|---|---|
| `proposed` | Drafted, tabled at the Data Architecture Forum, not yet decided. Attach it to the submission — drafting it usually improves the proposal. |
| `accepted` | Decided by the forum. The decision is binding on the domain. |
| `rejected` | Tabled and not agreed. **The file is kept.** A rejected ADR is often more valuable than an accepted one — it records the option someone will inevitably propose again, and why it did not fly. |
| `superseded` | A later ADR replaces it. The superseded record is never deleted or edited beyond adding the status change and the forward link. |

**ADRs are immutable once accepted.** You do not edit an accepted ADR to reflect a change of mind; you write a new one that supersedes it. Editing history is how a decision log becomes fiction. The only permitted post-acceptance edits are the status line and the supersession links.

Both directions of a supersession must be linked: the old record points forward to its successor, the new one points back. The linter checks this (DP-41).

## Numbering and naming

- Four-digit sequential number, allocated when the ADR is drafted, never reused: `0001`, `0002`, …
- Filename: `NNNN-short-kebab-case-title.md`
- The title states the decision, not the topic. `0002-one-model-two-lenses.md` — not `0002-reporting-architecture.md`. A reader scanning the directory should be able to reconstruct the shape of the architecture from the filenames alone.

## Required sections

The linter checks these are present, correctly ordered and non-empty.

| Section | Content |
|---|---|
| **Title** | `# NNNN. Decision stated as a decision` |
| **Status** | One of the four values, with the date and the deciding forum. Supersession links where applicable. |
| **Context** | The forces at play: constraints, obligations, what is currently true, what is driving the decision now. Written so someone with no history can follow it. State the regulatory driver where there is one — and state it accurately, at a conceptual level, pointing to the authority's own text for detail rather than paraphrasing it into a citation. |
| **Decision** | What was decided, in the active voice. "We will…". Specific enough to be testable. |
| **Consequences** | What becomes true. Both directions. An ADR with only positive consequences has not been thought about; the negative consequences are the reason the record has value, and stating them is what makes the mitigations credible. |
| **Alternatives considered** | Each real option, with why it was not chosen. Options nobody seriously entertained do not belong here — a straw man weakens the record. |
| **Related standards** | The `DP-nn` standards this decision implements, depends on, or creates tension with. |

Optional but often worth adding: **Revisit triggers** — the specific conditions under which this decision should be reconsidered. It converts "we should look at this again sometime" into something checkable, and it is the honest way to record a decision you are not certain about.

## Template

```markdown
# NNNN. <Decision stated as a decision>

## Status

Accepted · <date> · Data Architecture Forum
<Supersedes ADR-nnnn / Superseded by ADR-nnnn — where applicable>

## Context

<The forces. Constraints, obligations, current state, what is driving this now.
Enough that a reader two years from now needs no other document.>

## Decision

We will <decision, active voice, specific enough to be testable>.

<Sub-decisions, scope boundaries, and what this decision explicitly does not cover.>

## Consequences

### What this gives us
<Benefits, stated concretely.>

### What this costs us
<The honest downsides. Do not soften them.>

### Mitigations
<What we are doing about the costs. A cost with no mitigation is a risk
being accepted — say so explicitly rather than leaving it implied.>

## Alternatives considered

### <Alternative 1>
<What it was, why it was rejected, and under what conditions it would win.>

### <Alternative 2>
…

## Related standards

<DP-nn — how this decision relates to it.>

## Revisit triggers

<Specific conditions that should reopen this decision.>
```

## Writing guidance

**Write it when you decide, not when you are challenged (DP-42).** Retrospective ADRs record the decision but rarely the alternatives that were genuinely live at the time, which is the part with the value.

**One decision per record.** An ADR covering three decisions cannot be superseded cleanly, because you will later want to reverse one of the three.

**Be honest about the costs.** An ADR that reads like a business case is worthless as a record. The reader you are writing for is trying to work out whether your reasoning still holds under conditions you did not anticipate, and they can only do that if they can see what you traded away.

**Keep it short.** A hundred to a hundred and seventy lines is usually right. If it is longer, it is probably a design document wearing an ADR's clothes.

**Do not invent precision.** Where a decision depends on a regulatory requirement, describe the requirement conceptually and point to the authoritative source. A confidently wrong citation — an invented template reference, threshold or article number — propagates faster than a correct one and is far more expensive to remove once it is in the record.

## Current records

| ADR | Title | Status |
|---|---|---|
| [0001](0001-canonical-domain-model-over-point-to-point.md) | Canonical domain model over point-to-point feeds | Accepted |
| [0002](0002-one-model-two-lenses.md) | One model, two lenses: FINREP and Counterparty Credit Risk from one canonical model | Accepted |
| [0003](0003-lineage-as-a-first-class-artefact.md) | Lineage as a first-class artefact, emitted by the pipeline | Accepted |
| [0004](0004-target-architecture-lakehouse-hybrid.md) | Governed lakehouse with domain ownership as the target architecture | Accepted |

---

*Reference architecture, not a compliance artefact. All data in this repository is synthetic.*
