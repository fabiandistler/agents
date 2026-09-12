# AI Engineering Conventions

> Operational rules distilled from Chip Huyen, *AI Engineering* (O'Reilly,
> 2025). This sheet **complements** `../SKILL.md`: it carries the granular,
> falsifiable conventions the three-part narrative doesn't spell out. Where a
> topic is already covered in SKILL.md — the adaptation ladder, the sample-size
> rule, the five deployment baselines, the architecture build order, the six
> monitoring metric families, the five implicit-feedback signals — **SKILL.md is
> authoritative and it is not repeated here.** References are book chapter
> numbers `(Ch. N)`; the few rules drawn from elsewhere carry the source's
> name instead.
>
> Keep-filter used by the source distillation: counter-default, quantitative
> heuristic, or security-relevant. Generic best practice a competent model
> already follows is omitted.

## Prompting

- **Keep prompts out of application code.** Store them as separate files/objects
  with metadata — target model, sampling params, input/output schemas — and
  version them like code. (Ch. 5)
- **Decompose a complex task into chained single-purpose prompts, and route the
  simple steps to cheaper models** (e.g. intent classification). Budget the
  added first-token latency the extra hop introduces. (Ch. 5)
- **End a classification/structured prompt with an explicit input-terminating
  marker that cannot occur in the data** — otherwise the model may continue the
  input instead of answering it. (Ch. 5)
- **Evaluate every prompt change at the system level, not only on its subtask.**
  A subtask win can be a system-level regression. (Ch. 5)
- **Inspect every prompt a prompt-engineering tool generates, and count its
  hidden API calls** — 10 variants × 30 eval examples is 300 calls per run.
  (Ch. 5)
- **Repeat critical instructions both before AND after untrusted content, and
  name explicitly what must never be output.** (Ch. 5)

## Evaluation

_Extends SKILL.md Part A. The sample-size rule and the five deployment
baselines live in SKILL.md — cross-reference, don't duplicate._

_Rules tagged `(ASSERT)` come from the ASSERT spec-driven eval method
(<https://github.com/responsibleai/ASSERT>), not from Huyen._

- **Write the evaluation guideline before building** — including out-of-scope
  inputs and the required refusal behavior. "Correct" ≠ "good"; define good per
  application. (Ch. 4)
- **Evaluate each pipeline component independently AND end-to-end, per-turn AND
  per-task.** Otherwise failures can't be localized.
  - ❌ scoring only the final output   ← likely-default
  (Ch. 4)
- **Give AI judges classification labels or a discrete 1–5 scale, never a
  continuous score** — wider or continuous ranges degrade judges. Include a
  worked example with justification for each score point. (Ch. 3)
  - ❌ "rate from 0 to 100" / 0.0–1.0   ← likely-default
- **Pin judge configuration: temperature 0, plus a versioned judge prompt,
  model, and eval set.** Judge scores are not comparable across tools or judge
  models. (Ch. 3, 4)
- **Maintain sliced eval sets** — production distribution, known-failure set,
  out-of-scope set, user-typo set. Aggregate-only comparison risks Simpson's
  paradox. (Ch. 4)
- **Layer evaluators by cost:** a cheap scorer on 100% of traffic, an expensive
  judge on ~1%, plus a small daily human-reviewed sample in production. (Ch. 4)
- **Use logprobs for classification confidence whenever the API exposes them.**
  (Ch. 4)
- **Map eval metrics to a business metric and set a usefulness threshold before
  shipping.** (Ch. 1, 4)
- **Derive the eval slices from a behavior taxonomy layered on top of the
  standard slices.** Name each behavior the spec implies and give it explicit
  permissible AND impermissible policies; the slices those behaviors need fall
  out of the taxonomy, while the four slices above stay the floor. (ASSERT)
  - ❌ treating a fixed slice list as the coverage argument   ← likely-default
- **Stratify test generation across declared dimensions** (e.g. user type ×
  request type), so coverage is reportable per taxonomy cell instead of
  accidental. (ASSERT)
- **Give the judge the policy text itself as its rubric, not a separately worded
  one** — that keeps spec → test → score traceable and makes the judge rationale
  usable as evidence. (ASSERT)
- **A judge score without a gold reference is a screening signal, not an
  acceptance criterion.** Judge–human agreement degrades as task difficulty
  rises and settles at 77–82% on hard agent tasks when no reference answer is
  supplied; a larger judge model does not close the gap. Acceptance needs either
  a reference answer in the test case or a human sample on the hardest slice.
  (AgentJudgeBench)
  - ❌ promoting a judge-scored aggregate to a release gate   ← likely-default
- **Prove construct validity at item level before a benchmark or test set becomes
  an acceptance criterion — or before publishing one.** Score individual items,
  not just the aggregate: a set can discriminate on general reasoning while
  claiming to measure the target capability (BBQ, a bias benchmark, correlates
  more strongly with reasoning than with safety). The same item-level analysis
  identifies the ~10% of items that carry the discrimination, which is what makes
  a set cheap to run repeatedly. (BenchMIRT)

## Adaptation

_Extends SKILL.md Part A (the ladder and failure-type gating)._

- **Reject "prompting doesn't work" unless the prompt experiments were
  systematic** — versioned prompts, fixed eval data, standardized metrics. Most
  such claims trace to unsystematic prompting. (Ch. 7)
- **Test feasibility with the strongest model you can afford, then work down the
  cost curve.** If the strongest model fails, weaker ones will too. (Ch. 4, 7)
  - ❌ prototyping on the cheapest model   ← likely-default
- **Don't assume a domain-specific task requires a specialist finetune.**
  Frontier general models routinely beat domain specialists (the BloombergGPT
  case). (Ch. 7)

## Agents

_Extends SKILL.md Part B step 5._

- **Evaluate agents per failure mode with explicit metrics:** % valid plans,
  invalid-tool calls, valid-tool-with-invalid-params calls, wrong parameter
  values, plus steps and cost per task. (Ch. 6)
- **If a tool stays error-prone after prompting, examples, and finetuning,
  replace the tool with a simpler interface** — don't keep patching the agent.
  (Ch. 6)
- **Treat deadlines as a task constraint:** a correct agent output delivered too
  late is a failure. (Ch. 6)
- **Expose a corpus to an agent as a query interface — never as one tool per
  document, never as whole documents in the response.** Both the tool list and
  the payload are context cost, paid on every turn. A search or query tool over
  the corpus (SQL over a trace store, search over a knowledge directory) keeps
  both flat as the corpus grows; one tool per document grows the tool list
  linearly. Measured: ~97% fewer input tokens from tool search over large tool
  collections, ~17× cheaper than passing whole traces.
  - ❌ one MCP tool per knowledge file   ← likely-default

## Serving & architecture

_Extends SKILL.md Part B (the five-step build order)._

- **Front the system with a small, cheap intent classifier, and answer
  out-of-scope queries with stock responses — no LLM call.** (Ch. 10)
- **Access all models through a gateway** (unified interface, key custody,
  per-app access control, fallbacks, usage limits). **Never distribute raw
  provider keys to applications.** (Ch. 10)
- **When latency matters, fire redundant parallel calls and take the first
  acceptable response** instead of sequential retries. (Ch. 10)
- **Never cache user-specific or time-sensitive responses** — cached
  personalized answers leak across users. (Ch. 10)
- **Treat semantic caching as guilty until proven:** adopt it only with a
  demonstrated high hit rate. Embedding + threshold + vector search are three
  coupled failure points. (Ch. 10)
- **Self-hosting only:** the usual highest-leverage optimizations are
  quantization, replica parallelism, tensor parallelism, and attention/KV-cache
  optimization; add prompt caching for long shared prefixes and multi-turn.
  (Ch. 9)

## Guardrails & security

_Extends SKILL.md Part B step 2. Security rules are kept even where they read as
obvious — the cost of guessing wrong is high._

- **Guardrail inputs AND outputs** — harmless inputs can still produce harmful
  outputs. (Ch. 5, 10)
- **Track the false-refusal rate alongside the catch rate.** An over-blocking
  system is also a failure. (Ch. 10)
- **Mask PII/sensitive data before any third-party API call; restore it via a
  reverse mapping after generation.** (Ch. 10)
- **Execute generated code only in an isolated sandbox/VM.** (Ch. 5)
- **Gate all mutating actions (UPDATE/DELETE/DROP, sending messages,
  transactions) behind explicit human approval.** (Ch. 5, 10)
- **Streaming emits tokens before output guardrails can run** — make that
  trade-off an explicit decision, not an inherited default. (Ch. 10)
- **Audit third-party default prompt templates for missing safety instructions
  before use** — permissive defaults have shown 100% prompt-injection success in
  studies. (Ch. 5)

## Finetuning

_SKILL.md places finetuning on the ladder; these are the mechanics once you're
actually on that rung._

- **Start with LoRA/PEFT; attempt full finetuning only with thousands of
  examples or more** — with a few hundred, full finetuning won't beat LoRA.
  (Ch. 7)
- **Sequence the runs:** verify the training code on the cheapest model, verify
  the data on a mid-tier model (training loss must fall), then map the
  price/performance frontier across models. (Ch. 7)
- **After finetuning for one task, re-evaluate every other task type the model
  serves** — single-task finetuning degrades the rest. If irreconcilable, use
  separate models or merge. (Ch. 7)
- **Hyperparameter starting points:** LR = 0.1–1× the model's final
  pre-training LR (search 1e-7–1e-3); effective batch ≥ 8 (use gradient
  accumulation); 1–2 epochs for millions of examples, 4–10 for thousands;
  prompt-loss weight ~10%. (Ch. 7)
- **Prefer LoRA when serving many task variants of one base model** — adapters
  share the base at serving time. (Ch. 7)

## Data

- **Manually inspect samples before any pipeline decision, and re-annotate a few
  examples yourself to audit annotation quality.** ~15 minutes of looking at
  data routinely beats hours of downstream debugging. (Ch. 8)
- **Deduplicate before training.** Repeating 0.1% of data 100× measurably halved
  effective model capacity in a published study; duplicates also contaminate
  train/test splits. (Ch. 8)
- **Order processing steps by cost — run the cheapest data-reducing step first,
  and trial-run every script on a sample before the full dataset.** (Ch. 8)
