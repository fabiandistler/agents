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
