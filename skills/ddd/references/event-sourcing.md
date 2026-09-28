# Event Sourcing

Read this when step 1 of the decision path in SKILL.md selects an
Event-Sourced Domain Model: the subdomain involves monetary transactions,
regulatory audit requirements, or a genuine need for full history, deep
analytics, or point-in-time reconstruction.

- **Store events as the source of truth; derive current state by projecting them.** Do not persist a mutable state row as the truth and treat events as a side-channel (Ch 7).
- **Make events immutable and append-only. Never update or delete an event** (except controlled data migration) (Ch 7).
  - ❌ `UPDATE events SET ...` / `DELETE FROM events` ← likely-default when "correcting" data
- **Run every command as: load events → project to state → execute → append new events.** Don't mutate an in-memory state object and diff it (Ch 7).
- **Pair an event-sourced domain model with CQRS.** Without a separate read model, querying is limited to fetch-by-ID (Ch 7/10).

## Evolving events

- **Never change a published event's meaning; add a new event type or upcast on read.** Consumers may have stored or projected the old shape — a silent redefinition corrupts every downstream projection at once.
  - ❌ editing the v1 event shape in place and replaying history through the new meaning ← likely-default

## Personal data

- **Handle personal data with crypto-shredding (per-subject key) or forgettable payloads, never by rewriting streams.** Encrypt each subject's payload fields under a per-subject key and erase by destroying the key, or keep personal data out of the event body behind a reference the store can forget. The stream stays append-only and every other projection keeps working.
  - ❌ `DELETE FROM events WHERE subject_id = ...` to honor erasure ← likely-default

## Snapshots

- **Snapshot only when replay latency is measured to hurt.** A snapshot is a performance optimization with its own versioning and invalidation cost, not a default part of the design.
  - ❌ snapshotting every N events from the start "for performance" ← likely-default

## Cross-stream invariants

- **If an invariant spans streams and bloats an aggregate, consider a Dynamic Consistency Boundary (DCB) instead of merging aggregates.** A DCB enforces the rule with a tag query plus an append condition at write time, so each stream keeps its own small boundary. DCB complements aggregates — it covers the cross-stream rule that no single aggregate should own — it does not replace aggregate design.
  - ❌ merging two aggregates into one oversized boundary to enforce a cross-stream rule ← likely-default
