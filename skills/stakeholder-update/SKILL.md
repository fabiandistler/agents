---
name: stakeholder-update
category: communication
environments: coding, chat
description: Writing a weekly update, exec summary, escalation, or launch announcement for readers outside the working group — leadership, partners, or customers — where audience and update type decide the shape.
---

# Stakeholder Update

## When to use

This skill covers periodic and event-driven updates written *for an audience
outside your immediate working group* — a weekly or monthly status to
leadership, a launch announcement, a risk escalation, or the same progress
retold for another engineering team, partners, or customers. It starts by settling the
update type and audience, because both change the shape of the output.

For the daily team-facing version — yesterday / today / blockers, drafted
immediately from recent activity without a clarifying round — suggest the user
run the `repo-status` command skill instead.

When the source is simply too long and no outside audience is involved, that
is a compression task — suggest the user run the `tldr` command — not a stakeholder update.

## Workflow

### 1. Determine Update Type

Infer the update type from the request; ask only if ambiguous. Default to weekly:
- **Weekly**: progress, blockers, and next steps
- **Monthly**: trends, milestones, and strategic alignment
- **Launch**: what shipped, impact, rollout, and feedback channels
- **Ad-hoc**: one-off escalation, pivot, or major decision

### 2. Determine Audience

Infer the audience from the request; ask only if ambiguous. Default to leadership:
- **Executives / leadership**: outcome-focused, strategic, brief
- **Another engineering team**: technical detail, blockers, decisions needed
- **Cross-functional partners**: shared goals, dependencies, deadlines
- **Customers / external**: benefits, timelines, no internal jargon
- **Board**: metrics-driven, risk-focused, very concise

### 3. Gather the evidence

Two things decide how well this step goes.

**Take stock before you ask.** What is reachable differs sharply by where this
runs. A coding environment usually gives you the repository, its history, and
pipeline logs, but no email and no team chat. A chat environment usually gives
you email, chat, and documents, but no repository. Use what you can actually
read here, and only then ask for the rest.

Note that source control is not always a "connector". In a coding environment
the repository is simply present — read its history directly.

**Evidence sets the altitude, not the wording.** Commits, pull requests, and
pipeline runs establish what actually happened. They are input, never output.
Translate them into outcomes before they reach the update: "search results now
come back in under a second" rather than "merged 14 pull requests".

Sources worth pulling, by kind:

- **Source control** — merged pull requests and reverts in the period. Something shipped then rolled back belongs under risks, not progress.
- **CI / CD runs** — what reached which environment, and when. A release date is plannable; a week-red pipeline is a dated risk.
- **Issue / project tracker** — what closed, what is at risk or blocked. Carry ticket references through.
- **Chat and email** — usually the only record of decisions, commitments, and open asks. Source control never says why something was descoped.
- **Meeting transcripts and knowledge base** — the reasoning behind what the other sources record as facts.

**Then name the gap.** Say which part of the update is thin because a source was
unreachable, and ask for exactly that: "I can see what shipped and when it
deployed, but nothing about how the pilot team reacted — do you have that?"
Never close a gap with plausible-sounding detail. An invented metric gets
copied into someone else's slides and outlives the update.

### 4. Generate the Update

Draft from the template below matching the audience and update type. Keep
executive versions under 200 words; derive the status color from evidence
against the committed baseline and confirm it with the user before sending.

### Worked example

Evidence: three PRs merged (SSO login, CSV export, retry backoff); staging
deploy green Tuesday; pilot team reports login is twice as fast; one open
risk — export times out above 100k rows, owner assigned, fix due Friday.

Executive version:

```markdown
Status: Yellow (was Green): export timeout puts Friday rollout at risk.

TL;DR: SSO pilot succeeds; full rollout waits on the export fix due Friday.

Progress:
- SSO login live with the pilot team, logins twice as fast.
- Staging deploy green since Tuesday.

Risks:
- CSV export times out above 100k rows. Mitigation in progress, owner assigned. Ask: confirm Friday go/no-go by Thursday.

Next milestones:
- Full rollout — Friday, pending the export fix.
```

Customer version:

```markdown
What's new:
- Faster login — sign-in takes half the time it used to.

Coming soon:
- CSV export for large files — later this week.

Known issues:
- Very large exports (over 100k rows) may time out. Small exports work; retry or split the file meanwhile.

Feedback:
- Reply to this thread with anything that looks off.
```

### 5. Review and Deliver

After generating the update, ask if the user wants to adjust tone, detail, or
emphasis, and offer to match the delivery channel: an email needs a subject
line and greeting, a chat post must survive a phone screen, a doc can carry
the full structure. Where you can reach the channel yourself, offer to draft
in place; otherwise hand back text ready to paste, no placeholders left.

## Update Templates by Audience

### Executive / Leadership Update

**Format**:
```
Status: [Green / Yellow / Red] (was [previous color]): [one-line reason]

TL;DR: [One sentence — the most important thing to know]

Progress:
- [Outcome achieved, tied to goal/OKR]
- [Milestone reached, with impact]
- [Key metric movement]

Risks:
- [Risk]: [Mitigation plan]. [Ask if needed].

Decisions needed:
- [Decision]: [Options with recommendation]. Need by [date].

Next milestones:
- [Milestone] — [Date]
```

**Tips for executive updates**:
- Lead with the conclusion, not the journey.
- Derive the status color from evidence, not optimism. Green without supporting evidence is watermelon reporting.
- Asks must be specific: "Decision on X by Friday" not "support needed."

### Engineering Team Update

**Format**:
```
Shipped:
- [Feature/fix] — [Link to PR/ticket]. [Impact if notable].

In progress:
- [Item] — [Owner]. [Expected completion]. [Blockers if any].

Decisions:
- [Decision made]: [Rationale]. [Link to ADR if exists].
- [Decision needed]: [Context]. [Options]. [Recommendation].

Priority changes:
- [What changed and why]

Coming up:
- [Next items] — [Context on why these are next]
```

### Cross-Functional Partner Update

**Format**:
```
What's coming:
- [Feature/launch] — [Date]. [What this means for your team].

What we need from you:
- [Specific ask] — [Context]. By [date].

Decisions made:
- [Decision] — [How it affects your team].

Open for input:
- [Topic we'd love feedback on] — [How to provide it].
```

### Customer / External Update

**Format**:
```
What's new:
- [Feature] — [Benefit in customer terms]. [How to use it / link].

Coming soon:
- [Feature] — [Expected timing]. [Why it matters to you].

Known issues:
- [Issue] — [Status]. [Workaround if available].

Feedback:
- [How to share feedback or request features]
```

Frame everything in terms of what the customer can now do, not what was
built. No internal jargon, no ticket numbers. Mention customer-impacting
issues with status even without a fix.

### Risk Escalation

**Format**:
```
BLUF: [Specific ask] — need a decision by [date].

Situation: [Shared context the reader already knows]
Complication: [What changed and why it matters now]
Question: [The decision to make]
Answer: [Recommended option and why]

Options:
- [Option A]: [Trade-offs]. Recommended.
- [Option B]: [Trade-offs].

Cost of delay: [What happens if there is no decision by the deadline]
```

### Launch Announcement

**Format**:
```
What: [Feature or product launched] — [Why it matters, in reader terms]

Available to: [Who]. When: [Date or window].
Limits: [Scope exclusions, known limitations].
Rollout: [Stages, dates, who is affected when].
Feedback: [Channel for feedback or issues]
```

## Status Reporting Framework

Derive the color from evidence against the committed baseline: milestone slip,
red pipeline, reverts, blocked items. State a one-line reason and what changed
since the last update, and confirm the color with the user before sending.

- **Green** (On Track): progressing as planned, no significant risks. Use Green only when things are genuinely going well.
- **Yellow** (At Risk): slower than planned or a risk materialized; mitigation underway. Move to Yellow at the first sign of risk.
- **Red** (Off Track): will miss commitments without intervention. Move to Red when your own options are exhausted; move back to Green only when the risk is genuinely resolved.

## Risk Communication

1. **State the risk clearly**: "There is a risk that [thing] happens because [reason]"
2. **Quantify the impact**: "If this happens, the consequence is [impact]"
3. **Present the mitigation**: "We are managing this by [actions]"
4. **Make the ask**: "We need [specific help] to further reduce this risk"

Common mistakes: burying risks in good news, being vague about what and how
long, presenting risks without mitigations, and communicating too late — an
early risk is a planning input, a late one is a fire drill.
