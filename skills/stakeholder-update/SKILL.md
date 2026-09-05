---
name: stakeholder-update
category: communication
environments: coding, chat
description: Writing a status update for readers outside the immediate working group — leadership, cross-functional partners, or customers — where the audience and the update type decide the shape.
---

# Stakeholder Update

Generate a stakeholder update tailored to the audience and cadence.

## When to use

This skill covers periodic and event-driven updates written *for an audience
outside your immediate working group* — a weekly or monthly status to
leadership, a launch announcement, a risk escalation, or the same progress
retold for engineering, partners, or customers. It starts by settling the
update type and audience, because both change the shape of the output.

For the daily team-facing version — yesterday / today / blockers, drafted
immediately from recent activity without a clarifying round — use the
`repo-status` skill instead.

## Workflow

### 1. Determine Update Type

Ask the user what kind of update:
- **Weekly**: Regular cadence update on progress, blockers, and next steps
- **Monthly**: Higher-level summary with trends, milestones, and strategic alignment
- **Launch**: Announcement of a feature or product launch with details and impact
- **Ad-hoc**: One-off update for a specific situation (escalation, pivot, major decision)

### 2. Determine Audience

Ask who the update is for:
- **Executives / leadership**: High-level, outcome-focused, strategic framing, brief
- **Engineering team**: Technical detail, implementation context, blockers, decisions needed
- **Cross-functional partners**: Context-appropriate detail, focus on shared goals and dependencies
- **Customers / external**: Benefits-focused, clear timelines, no internal jargon
- **Board**: Metrics-driven, strategic, risk-focused, very concise

### 3. Pull Context from Connected Tools

If **project tracker** is connected:
- Pull status of roadmap items and milestones
- Identify completed items since last update
- Surface items that are at risk or blocked
- Pull sprint or iteration progress

If **chat** is connected:
- Search for relevant team discussions and decisions
- Find blockers or issues raised in channels
- Identify key decisions made asynchronously

If **meeting transcription** is connected:
- Pull recent meeting notes and discussion summaries
- Find decisions and action items from relevant meetings

If **knowledge base** is connected:
- Search for recent meeting notes
- Find decision documents or design reviews

If no tools are connected, ask the user to provide:
- What was accomplished since the last update
- Current blockers or risks
- Key decisions made or needed
- What is coming next

### 4. Generate the Update

Structure the update for the target audience using the templates and frameworks below.

**For executives**: TL;DR, status color (G/Y/R), key progress tied to goals, decisions made, risks with mitigation, specific asks, and next milestones. Keep it under 200 words.

**For engineering**: What shipped (with links), what is in progress (with owners), blockers, decisions needed (with options and recommendation), and what is coming next.

**For cross-functional partners**: What is coming that affects them, what you need from them (with deadlines), decisions that impact their team, and areas open for input.

**For customers**: What is new (framed as benefits), what is coming soon, known issues with workarounds, and how to provide feedback. No internal jargon.

**For launch announcements**: What launched, why it matters, key details (scope, availability, limitations), success metrics, rollout plan, and feedback channels.

### 5. Review and Deliver

After generating the update:
- Ask if the user wants to adjust tone, detail level, or emphasis
- Offer to format for the delivery channel (email, chat post, doc, slides)
- If **chat** is connected, offer to draft the message for sending

## Update Templates by Audience

### Executive / Leadership Update
Executives want: strategic context, progress against goals, risks that need their help, decisions that need their input.

**Format**:
```
Status: [Green / Yellow / Red]

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
- Lead with the conclusion, not the journey. Executives want "we shipped X and it moved Y metric" not "we had 14 standups and resolved 23 tickets."
- Keep it under 200 words. If they want more, they will ask.
- Status color should reflect YOUR genuine assessment, not what you think they want to hear. Yellow is not a failure — it is good risk management.
- Only include risks you want help with. Do not list risks you are already handling unless they need to know.
- Asks must be specific: "Decision on X by Friday" not "support needed."

### Engineering Team Update
Engineers want: clear priorities, technical context, blockers resolved, decisions that affect their work.

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

**Tips for engineering updates**:
- Link to specific tickets, PRs, and documents. Engineers want to click through for details.
- When priorities change, explain why. Engineers are more bought in when they understand the reason.
- Be explicit about what is blocking them and what you are doing to unblock it.
- Do not waste their time with information that does not affect their work.

### Cross-Functional Partner Update
Partners (design, marketing, sales, support) want: what is coming that affects them, what they need to prepare for, how to give input.

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
Customers want: what is new, what is coming, how it benefits them, how to get started.

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

**Tips for customer updates**:
- No internal jargon. No ticket numbers. No technical implementation details.
- Frame everything in terms of what the customer can now DO, not what you built.
- Be honest about timelines but do not overcommit. "Later this quarter" is better than a date you might miss.
- Only mention known issues if they are customer-impacting and you have a resolution plan.

## Status Reporting Framework

### Green / Yellow / Red Status

**Green** (On Track):
- Progressing as planned
- No significant risks or blockers
- On track to meet commitments and deadlines
- Use Green when things are genuinely going well — not as a default

**Yellow** (At Risk):
- Progress is slower than planned, or a risk has materialized
- Mitigation is underway but outcome is uncertain
- May miss commitments without intervention or scope adjustment
- Use Yellow proactively — the earlier you flag risk, the more options you have

**Red** (Off Track):
- Significantly behind plan
- Major blocker or risk without clear mitigation
- Will miss commitments without significant intervention (scope cut, resource addition, timeline extension)
- Use Red when you genuinely need help. Do not wait until it is too late.

### When to Change Status
- Move to Yellow at the FIRST sign of risk, not when you are sure things are bad
- Move to Red when you have exhausted your own options and need escalation
- Move back to Green only when the risk is genuinely resolved, not just paused
- Document what changed when you change status — "Moved to Yellow because [reason]"

## Risk Communication

### ROAM Framework for Risk Management
- **Resolved**: Risk is no longer a concern. Document how it was resolved.
- **Owned**: Risk is acknowledged and someone is actively managing it. State the owner and the mitigation plan.
- **Accepted**: Risk is known but we are choosing to proceed without mitigation. Document the rationale.
- **Mitigated**: Actions have reduced the risk to an acceptable level. Document what was done.

### Communicating Risks Effectively
1. **State the risk clearly**: "There is a risk that [thing] happens because [reason]"
2. **Quantify the impact**: "If this happens, the consequence is [impact]"
3. **State the likelihood**: "This is [likely/possible/unlikely] because [evidence]"
4. **Present the mitigation**: "We are managing this by [actions]"
5. **Make the ask**: "We need [specific help] to further reduce this risk"

### Common Mistakes in Risk Communication
- Burying risks in good news. Lead with risks when they are important.
- Being vague: "There might be some delays" — specify what, how long, and why.
- Presenting risks without mitigations. Every risk should come with a plan.
- Waiting too long. A risk communicated early is a planning input. A risk communicated late is a fire drill.

## Output Format

Keep updates scannable. Use bold for key points, bullets for lists. Executive updates should be under 200 words. Engineering updates can be longer but should still be structured for skimming.

## Tips

- The most common mistake in stakeholder updates is burying the lead. Start with the most important thing.
- Status colors (Green/Yellow/Red) should reflect reality, not optimism. Yellow is not a failure — it is good risk communication.
- Asks should be specific and actionable. "We need help" is not an ask. "We need a decision on X by Friday" is.
- For executives, frame everything in terms of outcomes and goals, not activities and tasks.
- If there is bad news, lead with it. Do not hide it after good news.
- Match the length to the audience's attention. Executives get a few bullets. Engineering gets the details they need.
