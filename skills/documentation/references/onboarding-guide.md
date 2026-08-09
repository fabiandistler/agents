# Onboarding Guide

Success is measured in one number: how long until the new person ships
something small on their own. Structure the guide around reaching that, not
around covering everything.

## Skeleton

```markdown
# Onboarding: <team or codebase>

## Day one: get it running
## The system map
## Your first task
## Common tasks
## Who to ask for what
```

## Section notes

**Day one: get it running.** Accounts and access requests first, ordered by how
long they take to be granted — a two-day access request must be filed before
lunch on day one, not discovered on day three. Then the local setup, as a
single runnable sequence ending in something visibly working: the test suite
green, the app served locally.

Onboarding docs rot faster than any other type because only new joiners run
them, and they are the least able to spot an error. Ask each new person to fix
what broke for them as their first PR; that makes the doc self-healing.

**The system map.** Five to ten components with one line each, plus how they
connect. Names as they appear in the repo and in conversation — including the
internal nicknames, which are otherwise invisible and impossible to search for.
Link to the architecture doc rather than restating it.

| Name | What it is | Where |
|---|---|---|
| `orders-api` | Public order CRUD, the only writer to the orders DB | `services/orders-api` |
| "the relay" | Outbox → Kafka publisher; nickname for `event-relay` | `services/event-relay` |

**Your first task.** A specific, currently-real, genuinely small change with a
pointer to where it goes and how to get it reviewed. This is the section that
converts reading into competence — a guide without it produces someone who has
read a lot and shipped nothing. Keep a short queue of good first issues and
name where that queue lives, since any single example goes stale.

**Common tasks.** The handful of things everyone does in the first month, each
as a short walkthrough: run the tests, run one test, add a migration, deploy to
staging, read production logs, roll back. Commands, not descriptions.

**Who to ask for what.** Areas mapped to teams or rotations and their channels,
plus the norm for asking — where questions go, and how long to struggle first.
Prefer team channels to individuals; individuals move.

## Failure modes

- **A systems tour with no first task.** The reader finishes informed and still
  unable to start.
- **Setup steps that only work for the author**, kept alive because no existing
  team member ever re-runs them.
- **Access requests discovered late**, silently costing days.
- **Nicknames omitted.** The new person hears "the relay" in standup for two
  weeks and cannot search for it.
- **Duplicating the architecture doc**, so both drift. Link instead.
