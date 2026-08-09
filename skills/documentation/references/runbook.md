# Runbook

Written for someone tired, paged, and unfamiliar with this service. Optimize
for a reader who will not read ahead — every step must be safe to execute the
moment it is read.

## Skeleton

```markdown
# Runbook: <the situation>

**Use this when:** <the symptom or alert that brings someone here>
**Do not use this when:** <the near-miss situation with a different runbook>
**Severity / paging expectation:** <who to wake, when>

## Prerequisites
## Procedure
## Verify
## Rollback
## Escalation
```

## Section notes

**Use this when.** Name the alert or symptom verbatim as it appears in the
paging tool, so search finds it. Add the confusable neighbour and link to its
runbook — half of all wrong-runbook incidents are two similar alerts.

**Prerequisites.** Everything needed *before* step 1: access and roles, VPN,
tools installed, credentials, and where to get each if missing. Access requests
that take an hour must not be discovered at step 6.

**Procedure.** Numbered, imperative, one action per step. Give the exact
command and the expected output, so the reader can tell success from silence.
Mark decision points explicitly.

```markdown
3. Drain the wedged consumer:

       kubectl -n orders scale deploy/order-consumer --replicas=0

   Expect `deployment.apps/order-consumer scaled`. Confirm no pods remain:

       kubectl -n orders get pods -l app=order-consumer
       # No resources found in orders namespace.

4. **If** lag is still climbing after 2 minutes, this is not a consumer
   problem — stop here and go to [Escalation](#escalation).
```

Flag destructive steps before the command, not after: state what is lost and
whether it is recoverable.

**Verify.** How to know it actually worked, from an independent signal —
a dashboard, a metric threshold, a probe request. "The command exited 0" is not
verification.

**Rollback.** For every mutation the procedure made, how to undo it. If a step
is genuinely irreversible, say so at that step and again here. A runbook with
no rollback section is incomplete unless it is strictly read-only, in which case
say *"Read-only: nothing to roll back."*

**Escalation.** Who to contact, through which channel, at which severity, and
what to include in the message (service, alert, steps already tried, timestamps).
Prefer rotations and team channels over personal names — people change teams.

## Failure modes

- **No rollback.** The reader is mid-incident with a half-applied change and no
  documented way back.
- **Access discovered mid-procedure.** Steps require a role the prerequisites
  never mentioned.
- **Unverifiable success.** No independent signal, so the reader cannot tell
  whether to escalate.
- **Personal names as the escalation path.** They go stale faster than anything
  else in the doc.
- **Never rehearsed.** Untested runbooks fail exactly when they are needed —
  walk it through in staging, or during game days, and date the last rehearsal.
