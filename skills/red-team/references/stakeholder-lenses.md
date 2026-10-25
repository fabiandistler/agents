# Stakeholder lenses

Lens catalogue for the red-team procedure (step 5) and the lens sets for the
several-critics path. Pick 3–5 lenses per case; each must produce a concrete
objection or condition in German, never a mood.

## Contents

- [How to pick](#how-to-pick)
- [Tech decisions: ADR, architecture, tool choice](#tech-decisions-adr-architecture-tool-choice)
- [PR descriptions](#pr-descriptions)
- [Job project proposals](#job-project-proposals)
- [LinkedIn posts and articles](#linkedin-posts-and-articles)
- [Applications](#applications)
- [Career and private decisions](#career-and-private-decisions)
- [Lens sets for several critics](#lens-sets-for-several-critics)

## How to pick

- Start from the use case below, then check coverage across five
  dimensions: decision power, implementation, risk and compliance,
  economics, acceptance. Swap a lens if a dimension that matters is empty.
- Prefer the person who decides or pays over the person who merely reads.
- Use 3 lenses when 5 would be artificial.
- Each lens line in the output names the concrete objection or condition
  and a tendency (zustimmend / offen / skeptisch / ablehnend). No
  percentages.

## Tech decisions: ADR, architecture, tool choice

- **Future maintainer** (two years on, author gone): Is the "why" written
  down? Is the rejected alternative named, with the reason? Is there a way
  back, and what does reversing cost?
- **Ops / on-call**: What pages at 3 a.m.? Monitoring, alerting, failure
  modes, backup and restore, runbook. Who owns it after go-live?
- **Security**: Data flows, secrets handling, PII, new attack surface,
  dependency and supply-chain risk, vendor access to data.
- **Team lead who pays**: Licence and cloud cost at real volume, people time
  for migration and operation, bus factor, opportunity cost against the
  roadmap.
- Optional:
  - **Advocate of the rejected option**: the strongest case for the
    alternative the ADR dismissed.
  - **Downstream teams / consumers**: breaking changes, migration burden,
    contract stability.

## PR descriptions

- **Reviewer with ten minutes**: Can they tell what changed, why, and what
  to look at first? Is the risky part flagged?
- **Person running `git blame` in a year**: Does the description explain
  the decision, not just the diff? Is the linked issue there?
- **Release / ops**: Migration steps, feature flags, rollback, config
  changes.

## Job project proposals

AI use cases, business cases, stakeholder pitches.

- **Budget owner**: Baseline and the ROI calculation behind it. What if the
  model performs half as well? Running cost per request at production
  volume. Payback period. What is stopped to fund this?
- **Data protection / works council**: Personal data and the legal basis
  under DSGVO, processor agreements with vendors, data leaving the EU.
  Can the system monitor employee behaviour or performance (co-determination
  under §87 Abs. 1 Nr. 6 BetrVG)? Does the use case fall into an EU AI Act
  high-risk area such as employment decisions?
- **The users** (whose work changes): Workflow fit, effort to correct wrong
  output, trust, what happens when the model is wrong, who is accountable.
- **IT / platform**: Integration, operation after the PoC, security review,
  vendor lock-in, who runs and pays for it in year two.
- Optional:
  - **Sceptical data scientist**: Eval design, baseline without ML, data
    leakage, whether the metric matches the business goal, whether ML is
    needed at all.
  - **Sponsor's boss**: strategic fit, reputational risk if it fails in
    public.

## LinkedIn posts and articles

- **Target reader**: What do they get from the first two lines? Why should
  they care, and what can they do with it afterwards?
- **Sceptical peer** (expert in the field): Which claim would they call
  overstated, wrong, trivial, or unsourced? Is a number missing its source?
- **Recruiter / hiring manager**: What does the post signal about the
  author's judgement and level? Would it help or hurt in an interview?
- Optional:
  - **Current employer and colleagues**: confidential details, tone about
    the employer or clients, claims the employer would not sign off.

## Applications

- **Hiring manager, 30 seconds**: Is the fit for this role visible on the
  first page? Evidence of impact (numbers, outcomes) over duties?
- **HR screener**: Formal criteria, gaps, salary expectation, start date.
- **Future team colleague**: Would they want to work with this person?
  Overclaiming, buzzwords without substance.

## Career and private decisions

Salary negotiation, job change, choice between options.

- **Future self** (in one and in five years): Reversible or not? Which
  regret is more likely: having done it or not? What does it close off?
- **Counterpart in the negotiation** (hiring manager, HR, landlord): Their
  budget band and alternatives, their incentives, how they would counter
  each argument, what concession they can actually give.
- Optional:
  - **Affected others** (partner, family): cost in time, money, location.
  - **Current employer**: what happens if they learn early; counter-offer
    dynamics.
  - **Neutral mentor**: base rates for this kind of move, what is being
    overlooked.

## Lens sets for several critics

Give each critic one set, so the critics differ by perspective, not only by
label. Pick 2–4 sets that fit the case; adapt the lenses to the use case
above.

- **A — Decision and economics**: budget owner or team lead who pays,
  future self, sponsor's boss.
- **B — Implementation and operations**: future maintainer, ops / on-call,
  IT / platform, the users.
- **C — Risk and compliance**: security, data protection / works council,
  regulation, reputation.
- **D — Adversary and outside-in**: sceptical peer, counterpart in the
  negotiation, advocate of the rejected option, external forces (vendor
  pricing, market, reorg).
