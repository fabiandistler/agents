# Global rules block

Two rules that hold across every project and every runtime, kept here so they
are versioned and diffable. They are **not** a skill: they carry no trigger and
no progressive disclosure — they are always-on text, so the whole point is that
they stay short.

Paste the fenced block below into the global rules file of each agent:

| Runtime | File |
|---|---|
| Claude Code / Cowork | `~/.claude/CLAUDE.md` |
| Codex CLI | `~/.codex/AGENTS.md` |
| opencode | global `AGENTS.md`, or a path listed in `opencode.json` → `instructions` |

Keep the three copies identical; when this file changes, re-paste.

---

```markdown
## Verification before completion

- Before claiming done, passing, or fixed — and before any commit or PR — run
  the command that proves it, fresh, in this turn, and quote its output.
  "Should pass" is not evidence.
- A regression test counts only after red-green-revert: it fails without the
  fix and passes with it. Passing once proves nothing.
- A subagent's success report is not evidence. Read the diff.
- Linter clean ≠ build passes; build passes ≠ requirements met. For
  requirements, re-read the request and check it line by line.
- When something can't be verified from here, name what is unverified instead
  of softening the claim.

## Classify the path before building

- Before the first clarifying question, say the classification out loud:
  **spike** (a feasibility answer; any code is throwaway), **bounded** (the
  flow being changed already exists in this repo — design in chat, no spec
  file), or **architectural** (new subsystem, or interfaces others depend on —
  spec first, then plan).
- The ratchet runs one way: complexity discovered mid-task upgrades the path.
  Nothing downgrades it.
- Present the design and stop until it is approved. The artifact scales down
  with simplicity; the approval does not.
```

---

## Provenance

Forged 2026-09-02 from [obra/superpowers](https://github.com/obra/superpowers)
(MIT), distilled to the non-obvious remainder:

- *Verification before completion* ← `skills/verification-before-completion/SKILL.md`
  (the gate function and the Claim / Requires / Not-sufficient table).
- *Classify the path before building* ← `skills/brainstorming/SKILL.md`,
  section "Three Paths".

Superpowers itself is deliberately not vendored into this repo: its skills form
a coupled chain and its `SessionStart` hook asserts a global mandate that
collides with the router design here. Only these deltas were taken.

## Teardown condition

Review on **2027-03-01**. Cut a block that has not earned its lines:

- *Verification*: no completion claim has had to be walked back since the last
  review, in any runtime → the rule is restating default behavior.
- *Path classification*: the classification never changed what got built, or it
  fires so often it has become a ritual preamble → cut or demote it to the one
  line that still bites.

Promotion is the other exit: three separate occasions where the verification
rule caught something makes it a candidate for a `Stop` hook (rule of three)
rather than always-on text.
