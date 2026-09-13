---
title: Seam handover
targets: all
---

## Seam handover

A **seam** is the public boundary a module is tested at. Tests live at seams and
never reach inside. The agreement about which seams a piece of work is tested at
is made once, upstream, and must travel with the work — see ADR-0004.

- [rule] Never invoke `/implement` with a bare issue number. Name the work in the
  invocation so a planning pass is forced.
- [rule] Run `/to-spec` before implementation and answer its seam confirmation
  instead of waving it through. It is the step that agrees the seams.
- [rule] When breaking a spec into tickets, carry the seams into every ticket.
  Add a `## Seams` section naming the boundary each ticket is tested at, and
  state explicitly what is deliberately not a seam.
- [rule] A ticket with no seam field is not ready for implementation. Agree the
  seams first rather than letting the run decide them silently.
- [rule] After each vertical slice, state in two or three lines which
  control-flow path changed and why in that order. Record it with the ticket,
  not only in the conversation.
