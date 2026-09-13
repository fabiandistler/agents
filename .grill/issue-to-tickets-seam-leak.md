# `to-tickets` drops the seam agreement that `to-spec` just made

## Summary

`to-spec` agrees the test seams with the user. `to-tickets` then breaks the spec
into tickets, and neither of its templates has a field for them. `implement`
consumes tickets, not specs. So the seam agreement is made, confirmed, and then
lost at the `to-tickets` boundary.

## Where it happens

`to-spec` step 2 establishes the seams, and gates on the user:

> Sketch out the seams at which you're going to test the feature. Existing seams
> should be preferred to new ones. Use the highest seam possible. […]
> **Check with the user that these seams match their expectations.**

The spec template then carries them in `## Testing Decisions` ("which modules
will be tested", "prior art for the tests").

`to-tickets` publishes tickets using one of two templates. Neither has a seam
field:

| Template | Sections |
| --- | --- |
| local ticket | `What to build` · `Blocked by` · `Status` · acceptance criteria |
| tracker issue | `Parent` · `What to build` · `Acceptance criteria` · `Blocked by` |

Step 2 of `to-tickets` asks for domain-glossary vocabulary and for ADRs to be
respected, but says nothing about seams.

## Why it matters downstream

`implement`'s instruction is *"Use /tdd where possible, at pre-agreed seams"*,
and `tdd` refuses to write a test at an unconfirmed seam. `implement`'s own docs
say the agreement "happens either upstream in the spec, or in the first exchange
of the run" — but the artifact `implement` actually receives is a **ticket**, and
the ticket no longer carries it.

Observed in one user's local corpus (1125 sessions, so a single-user sample):

- 17 `/implement` runs, 0 `/tdd` invocations in any spelling.
- In 12 of the 17, the handover was a bare issue number, and no seam work appears
  anywhere in the transcript.
- The single run with substantial seam work read GitHub issues whose bodies were
  `to-spec` specs, including the `## Testing Decisions` section with a seam
  definition in prose. That run never invoked `to-tickets`.

The pattern is consistent with the leak: where a spec body reached `implement`,
the seams were present; where a ticket did, they were not.

## Possible directions

Not prescriptive — the maintainers know the constraints better.

- Add a `## Seams` section to both `to-tickets` templates, populated from the
  spec's `Testing Decisions` when a spec is the input.
- Have `to-tickets` refuse to publish a ticket derived from a spec without
  carrying the seams forward, the way `tdd` refuses an unconfirmed seam.
- Alternatively, have `implement` read the parent spec rather than the ticket
  alone — the `Parent` field already exists in the tracker template.

## Related

- The routing measurement for `implement` / `tdd`, filed separately. This issue
  is the upstream cause of the pattern that report measures; that one is about
  the instruction not routing, this one is about the artifact not carrying.
- **#1060** (acceptance locks and hard gates across the planning-to-implementation
  flow) — same theme of preconditions stated but not enforced.

## Limits

Single user, single machine, 17 measured `/implement` runs. The template gap is
verifiable from the skill sources alone; the usage numbers are supporting
evidence, not a user-base statistic.
