# Grill: step-wise agent development (Todoist 6hVCFPCwwGR83f2x)

Topic: "Could agent development be made more step-wise (stop after tests, write
interfaces/pseudocode first) so I have more control while developing?"

Doc home: /home/fabian/dev/scripts/agents (docs/adr/ -> next is 0004, no CONTEXT.md yet)

## Facts found
- settings.json: defaultMode "auto" -> built-in permission gate deliberately disabled
- effortLevel high, model opus[1m], hookify + learning-opportunities plugins enabled
- mattpocock tdd skill ALREADY gates: "No test is written at an unconfirmed seam"
- feature-dev skill: GATES HARD - 'DO NOT START WITHOUT USER APPROVAL', waits for
  explicit approval before implementation. (Earlier claim of 'no gate' was a bad glob.)
  => Two installed skills already implement the requested gate; gap persists anyway.
- Hook events: PreToolUse, PostToolUse, UserPromptSubmit, Stop, SubagentStop, SessionStart/End, PreCompact
- Plan mode (EnterPlanMode/ExitPlanMode) = existing before-code gate

## DECISIVE EVIDENCE (found, not asked)
Across 1125 local sessions, Skill-tool invocations:
  architecture:architecture 170, communication:html-artifacts 119,
  grilling 7, domain-modeling 6, code-review 6, codebase-design 1,
  mattpocock-skills:tdd 0, feature-dev 0
=> The two skills that DO implement the requested gate have never once fired,
   while sibling skills from the same plugin do. Not a plugin-age artifact.
=> The problem is NOT "gates fail to create understanding". It is that the
   gating skills are never invoked. Matches the repo's own ADR-0003
   ("auto-trigger floor for requests that look easy").
CORRECTED + SHARPENED by slash-command and file-read greps:
  /implement 19 runs (most-used non-builtin command), /tdd 0 in ANY spelling,
  /feature-dev 1, /to-tickets 6, /to-spec 2, /grill-with-docs 4
=> The user's real workflow is /implement. Their Q5 phrase "Modus fuer implement
   oder grilling" meant this command literally.
=> implement's own docs name the exact failure: "Nothing inside `implement`
   agrees the seams. tdd is the skill that asks... If it happens nowhere, the
   precondition never fires and the run quietly becomes 'just write the code'."
   And its own success criterion: "You can see an actual /tdd invocation in the
   trace." By that criterion 0 of 19 runs worked.
=> implement SKILL.md is 6 lines; the gating lives in a doc the agent never reads.
=> implement also has NO stop: it commits straight to the branch, documented as
   "too eager: the code lands before they have had a chance to verify it works".
   Documented overrides: say so in the invocation, or edit the local copy
   (which lives in a VERSIONED plugin cache -> dies on next update).
=> Intended rate lever is upstream ticket sizing in to-tickets, not mid-run stops.

## EMPIRICAL VERIFICATION of the "tdd never ran" claim (user challenged it)
Corpus: ~/.claude/projects/**/*.jsonl, 1125 session files, local machine only.
Validity probe: the same grep finds 413 Skill-tool invocations overall -> not broken.
- "skill":"*tdd*"            -> 0
- <command-name>*tdd*        -> 0
- tdd SKILL.md path read     -> 2 sessions, one of which IS this grilling session
- /implement runs            -> 18 session files (19 invocations)
Per-run word counts: 11 of 17 real runs have seam and tdd on exactly 2 lines each.
Inspected 624869af directly: both words occur ONLY in implement's own instruction
("Use /tdd where possible, at pre-agreed seams") and in the skill-list boilerplate.
Never in the work.
Counter-checks on the highest counters:
- 71e65915: all non-boilerplate "tdd" hits are base64 noise in binary blobs. Zero real use.
- e2730da8: seams WERE genuinely negotiated in prose ("One seam. The single test
  seam is arch_check(...)"), 59 distinct test files touched - and /tdd still never fired.
Mechanism checks:
- tdd has NO disable-model-invocation -> it COULD have been called. Not blocked.
- Tests were written anyway in several runs => matches this repo's own ADR-0003:
  the model only consults a skill for work it cannot easily do itself.
- implement's instruction carries two escape hatches in one sentence: "where
  possible" licenses skipping, and "at pre-agreed seams" is a precondition that
  nothing inside implement establishes.
REFINEMENT (honest): skill-absence != bad work. e2730da8 did careful seam work
without the skill. So the lever is the ARTIFACT, not "make tdd fire".
Limits: covers only local sessions in this directory; other machines/web not included.

## INVOCATION-FORM CORRELATION (found while checking the one good run)
Args passed to /implement, against seam-mention lines:
  bare issue number (15,142,18,4,12,145,120,102,122,108,109,11) -> seam=2 in ALL 12
  "yes" / empty                                                  -> seam=3
  "the remaining issues"                    (1.8M session)       -> seam=14
  "the remaining issues under #27 on separate prs" (2.3M)        -> seam=10
Size confound ruled out: 01517bf9 (1.3M), 17f0c5d6 (1.1M) and 35d2780f (1.2M) are
comparable in size to the good runs and still sit at seam=2.
e2730da8 was a bg session in ~/dev/r-projects/aRchtest on main, no local spec file;
work came from GitHub issues.
Reading (correlation, n=17, one user - NOT causation): a bare number carries no
seam information and skips any planning phase; a multi-issue prose invocation
forces an explicit planning pass, and the seam work appears there spontaneously.
=> Opens Q14: is the lever the INVOCATION FORM / how work is handed over, rather
   than a new command at all?

## THE SEAM LEAK (answers user's "don't to-spec/to-tickets already do this?")
YES for to-spec. Step 2, verbatim:
  "Sketch out the seams at which you're going to test the feature... Use the
   highest seam possible... Check with the user that these seams match their
   expectations."
That IS the seam gate, and it IS human-confirmed. Its spec template also carries
a "Testing Decisions" section ("which modules will be tested").

NO for to-tickets. It does vertical slices, blocking edges and a granularity quiz.
Neither of its two templates has any seam field:
  local: What to build / Blocked by / Status / acceptance criteria
  issue: Parent / What to build / Acceptance criteria / Blocked by
Step 2 mentions domain glossary and ADRs - never seams.

=> THE LEAK: the seam agreement is made in to-spec, lives in the SPEC, and is
   dropped when to-tickets breaks the spec into TICKETS. /implement consumes
   tickets, not the spec. So the agreement evaporates at the to-tickets boundary.
=> Usage data fits exactly: to-spec 2 runs, to-tickets 6, implement 17. Most
   implement runs had no spec upstream at all; and even when one existed, its
   seams never reached the ticket.
=> This explains the whole chain end to end and makes a new command unnecessary:
   the "command that fills the seam section" already exists and is to-spec;
   the template that needs the seam section is to-tickets'.

## CAUSAL CHAIN CONFIRMED (advisor challenged it; check held)
e2730da8 contains NO to-spec and NO to-tickets invocation, but DOES contain
"Testing Decisions" (2 lines) and "Implementation Decisions" (3) - the to-spec
spec-template headers. The GitHub issues it read WERE to-spec specs, written in
an earlier session (to-spec did run in an aRchtest worktree).
Verbatim from the fetched issue body: "A test drives the public DSL against a
fixture project on disk and asserts on the returned `arch_result`. It never
reaches into the parse output, the resolver's..." = a seam definition, in the
handover.
=> Where a to-spec spec body reached /implement, seam work happened (59 test files).
=> Where only a bare ticket number reached it (12 of 17), none did.
=> The leak is causal, not merely structural. Chain closed.
=> A new command is unnecessary. The fix is (1) run /to-spec, (2) stop the
   to-tickets templates from dropping the seam field.

## LOOSE END (must not drop silently)
Q12 item 3 - the per-slice control-flow narration (Q6c / Q10) - has NO owner in
the existing chain. to-spec covers seams (Q6b). Nothing covers control flow.

## Design tree
ROOT: introduce explicit progress gates into agent-driven development?
- R1 Q1 which failure is prevented?  [SETTLED: (c) comprehension gap ONLY.
      NOT wrong-direction, NOT scope creep, NOT rework cost. Reframes everything:
      the proposed mechanism (stop after tests / interfaces first) was chosen for
      a failure mode that is not the one being suffered.]
- R1 Q2 scope: interactive only  [SETTLED: interactive only; background jobs get
      smaller briefs + report-instead-of-merge, separate branch, not opened]
- R1 Q3 gate axis  [SETTLED: `auto` stays on, gate sits on the progress axis,
      not the tool-call axis]
- R2 Q4 when does the gap bite?  [SETTLED: all four - during, at review,
      weeks later, when debugging. Pervasive => no single checkpoint fixes it]
- R2 Q5 which act?  [SETTLED differently: user rejected all four options and
      answered on the mechanism axis instead - an OPT-IN MODE with smaller
      steps, not default, possibly a wrapper command around implement+grilling.
      Note: "smaller steps" is a RATE answer. Grilling itself is the active act.]
- R2 Q6 granularity  [SETTLED: (b) architecture/seams + (c) control flow.
      NOT (a) domain vocabulary => CONTEXT.md glossary is NOT the deliverable
      here; ADRs still are; control flow is captured by neither]
- R2 Q7 agent-specific?  [BADLY ASKED - re-asked as Q7b in R3]
- R2 Q7 [SETTLED BY INFERENCE: user proposed rate-throttling unprompted
      ("kleinere Schritte"); re-asking would spend a round on nothing]
- R3 Q8  [SETTLED: seam agreement before first line = MANDATORY;
      per-slice stop = OPT-IN. User answered "Ok" = accept recommendations]
- R3 Q9  [SETTLED: new command in ~/dev/scripts/agents, NOT an edit of the
      versioned plugin cache, NOT upstream ticket resizing]
- R3 Q10 [SETTLED: 2-3 line narration of the changed path per slice,
      including WHY this order. No maintained diagram.]
- R4 Q11 shape: wrapper that interleaves vs separate artifact-producing step
      (refines Q9 - same location, different shape)              [OPEN]
- R4 Q12 what the seam artifact contains + where it lives        [OPEN]
- R4 Q13 what happens at the end: still auto-commit?             [OPEN]
- R4 Q14 [SETTLED: (c) - seam section in the ticket template AND a step that
      fills it. Evidence then showed BOTH halves already have owners upstream:
      to-spec fills, to-tickets' template is the one missing the field.]
- R5 Q15 seam leak = second upstream defect: same issue or separate? [OPEN]
- R5 Q16 what gets built locally, if anything?                       [OPEN]
- R3 (blocked, on Q6) is "interfaces/pseudocode first" the right artifact at all?
- R3 (blocked, on Q4+Q5) what a "stop" is: pause vs end-turn-with-artifact
- R3 (blocked) gate positions along the build
- R3 (blocked) enforcement: hook (deterministic) vs skill text (probabilistic) vs permission mode
- R3 (blocked) global vs per-project; release vocabulary (approve/revise/reject)
- R3 (blocked) cost: how many gates per feature before it beats coding by hand

## ADR candidate (offer when frontier closes)
Qualifies on 2 of 3 criteria strongly: a future reader WILL ask "why a separate
seam-negotiation step when /implement already claims pre-agreed seams?", and
there were genuine alternatives (wrapper vs local-copy edit vs upstream sizing;
in-run precondition vs separate artifact). Next number: docs/adr/0004-*.md

## Rounds
R1 answered: Q1=(c) only; Q2=interactive only; Q3=progress axis confirmed.
R2 answered. R3 answered ('Ok' = accept all three recommendations).
R4 asked (Q11-Q13), awaiting answers.
Premise survived but mutated: not a passive gate - an opt-in command that
interleaves grilling with small implementation slices.

## Open vocabulary (hold until settled)
- "Kontrolle" -> resolved to comprehension/ownership, NOT direction control
- MISMATCH: /domain-modeling produces a glossary (CONTEXT.md) for domain
  vocabulary = Q6 option (a), which the user explicitly did NOT pick.
  ADRs cover Q6(b). NOTHING in this skill covers Q6(c) control flow.
  => this command covers at most half the ask; say so, do not paper over it.
- tool-axis gate vs progress-axis gate: confirmed distinction, glossary entry
  deferred until we know whether gates survive Q5 at all
