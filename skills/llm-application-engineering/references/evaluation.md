# Evaluation conventions

Rules for eval harnesses, LLM judges, agent evaluation, rollout experiments and production monitoring.

Citations: Huyen = Chip Huyen, *AI Engineering* (O'Reilly, 2025); Albada = Michael Albada, *Building Applications with AI Agents* (O'Reilly, 2025).

As of 2026-11-20: the OpenTelemetry GenAI semantic conventions are in Development status, checked against <https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/>.

## Contents

- [Evaluation](#evaluation)
- [Agent evaluation](#agent-evaluation)
- [Rollout](#rollout)
- [Production metrics and feedback](#production-metrics-and-feedback)
- [Monitoring](#monitoring)

## Evaluation

- **Write the evaluation guideline as a first draft before building, then revise it after error analysis** — including out-of-scope
  inputs and the required refusal behavior. "Correct" ≠ "good"; define good per
  application, and expect the first definition to move once traces are read. (Huyen Ch. 4)
- **Record refusals as their own outcome class, by category — never let the
  retry path absorb them.** A refusal is a result, not a transient error; a
  harness that retries until the output parses silently deletes the safety
  signal and inflates the pass rate. Keep refusal separate from pass, fail and
  API error in every report. (featherbench)
- **When an LLM sits in the decision path of a rating or classification (grade,
  level, category), measure repeat stability: run the same input N ≥ 5 times
  and report the agreement rate alongside accuracy.** Below the agreed
  threshold the product shows a range or an explicit uncertainty flag — never a
  single value. Identical input with differing output is a defect class of its
  own, not noise. (Albada Ch. 3)
- **Evaluate each pipeline component independently AND end-to-end, per-turn AND
  per-task.** Otherwise failures can't be localized. (Huyen Ch. 4)
- **Give each failure mode its own binary pass/fail judge, never a
  continuous score** — wider or continuous ranges degrade judges. Use a
  discrete scale only with an explicit reason. Require a critique before the
  verdict and include a worked example with justification per verdict. (Huyen Ch. 3)
- **Pin judge configuration: model snapshot, versioned judge prompt, and
  reasoning effort — not temperature.** Reasoning/thinking modes fix
  temperature and recent models deprecate it; temperature 0 applies to
  non-reasoning models only. Judge scores are not comparable across tools or
  judge models. Measure repeat stability per the N ≥ 5 rule above. (Huyen Ch. 3, 4)
- **Calibrate each judge against ~100 human-labelled traces split
  train/dev/test; report TPR/TNR and gate CI only above the agreed
  threshold.** (Hamel)
- **Maintain sliced eval sets** — production distribution, known-failure set,
  out-of-scope set, user-typo set. Aggregate-only comparison risks Simpson's
  paradox. (Huyen Ch. 4)
- **Layer evaluators by cost:** a cheap scorer on 100% of traffic, an expensive
  judge on ~1%, plus a small daily human-reviewed sample in production. (Huyen Ch. 4)
- **Use logprobs for classification confidence whenever the API exposes them.**
  (Huyen Ch. 4)
- **A judge score without a gold reference is a screening signal, not an
  acceptance criterion.** Judge–human agreement degrades as task difficulty
  rises and settles at 77–82% on hard agent tasks when no reference answer is
  supplied; a larger judge model does not close the gap. Acceptance needs either
  a reference answer in the test case or a human sample on the hardest slice.
  (AgentJudgeBench)
- **When an agent step sits in front of a human or CI gate (approve/reject,
  ship/request changes, CI pass/fail, revert within N days), persist every gate
  verdict joined to the run/trace ID and prompt version from day one.** These
  verdicts are free labels — the gold reference the rule above asks for. Score
  the agent against the gate's first verdict, since later rounds judge a
  revised change, and count misses (agent approved; gate rejected or later
  reverted) and false alarms (agent flagged; gate shipped) separately. Promote
  a prompt only with fewer misses and no more false alarms. Audit a sample of
  gate verdicts too: the gate is the reference, not infallible ground truth.
  (Arize)
- **Prove construct validity at item level before a benchmark or test set
  becomes an acceptance criterion.** Score individual items, not just the
  aggregate: a set can discriminate on general reasoning while claiming to
  measure the target capability. The same item-level analysis identifies the
  ~10% of items that carry the discrimination, which is what makes a set cheap
  to run repeatedly. (BenchMIRT)

## Agent evaluation

- **Ship the first agent version with eval cases that assert: correct tool
  called, correct parameters, response contains required phrases; every change
  that adds or renames a tool or workflow adds matching cases in the same
  change** — the eval set is the living spec. Track per failure mode: valid
  plans, tool recall and precision, parameter accuracy (invalid or wrong
  values), phrase recall, task success, plus steps and cost per task.
  (Albada Ch. 2, 9; Huyen Ch. 6)
- **Structure each eval example as input state + conversation history + expected
  final state** (expected `tool_calls` with params, `customer_msg_contains`), so
  scoring is automatable. (Albada Ch. 9)
- **Export production failures AND exemplary successes (golden paths) as
  regression eval cases;** grow the set by LLM-generating adversarial/
  counterfactual variants with human review before inclusion. (Albada Ch. 9–11)

## Rollout

- **A/B tests on stateful agents need sticky user/session-level variant
  assignment;** reassignment mid-history corrupts both arms. (Albada Ch. 11)
- **Shadow-deploy risky agent changes (same inputs, outputs logged not served)
  before any canary exposure.** (Albada Ch. 10–11)

## Production metrics and feedback

### Six metric families

| Family | Key metrics | Notes |
|---|---|---|
| **Latency** | TTFT (time to first token), TPOT (time per output token), total response latency | LLMs stream; a single request/response total misses the experience. High TTFT + low TPOT often signals routing/cold-start issues; low TTFT + high TPOT signals a throughput bottleneck. |
| **Quality** | Format validity (valid JSON, required fields), factual consistency / hallucination rate (via AI judges or ground truth), conciseness, creativity | The most expensive family — needs either a second model call or human labeling; sampling strategy is mandatory. |
| **Security / guardrails** | Toxicity rate, PII-detection rate, guardrail-trigger frequency, refusal rate | A rising guardrail-trigger trend is an early warning of adversarial traffic; a sudden refusal-rate jump often means a provider silently changed the model's refusal behavior. |
| **User behavior** | Early-termination rate, turns per conversation, input/output token distribution, prompt complexity | Needs no user annotation. |
| **Cost** | Input/output token volume, tokens per second (TPS), rate-limit hits | — |
| **Drift** | System-prompt drift, user-behavior drift, provider-model drift | Provider drift (silent model updates behind an API) is detectable only through periodic probing with fixed reference inputs. |

### Five implicit-feedback signals

Explicit ratings are rare and come mostly from frustrated or delighted users;
these behavioral signals come from every conversation.

| Signal | What it looks like | Read as |
|---|---|---|
| **Early termination** | User stops generation mid-stream, closes the app, ignores the answer | Practically always negative — one of the best chat-app health metrics |
| **Error correction** | Follow-up starts with "No…", "I meant…", "That's not what I wanted…" | Retroactively marks the previous assistant message as a failure; detectable with a narrow classifier |
| **Complaints / sentiment drops** | Direct criticism, unspecific frustration ("ugh", "nope"), a shift from polite to curt phrasing | Aggregate with a sentiment tracker on the user side of the dialogue |
| **Regeneration requests** | User clicks "regenerate" or re-asks the same question | The clearest signal — the first answer was bad enough that the user actively requested a second try; regeneration rate is a direct A/B metric |
| **Implicit follow-up (downstream action)** | e.g. a recommended product gets purchased | Positive signal without an explicit click, but requires telemetry/identity mapping to observe the downstream action at all |

Aggregate these on two loops: short-term (hours — dashboards, spike alerts on
termination/regeneration rate, fast rollback) and long-term (days to weeks —
training and eval data for the next model iteration; error-correction
patterns become negative examples, corrected follow-ups become positive
examples). Because this is behavioral data, disclose its use and offer an
opt-out — lost trust costs more than the data is worth.

## Monitoring

- **Instrument with the OpenTelemetry GenAI semantic conventions and send the
  spans to the same observability stack as other services: an `invoke_agent`
  parent with `chat` and `execute_tool` spans, `gen_ai.request.model` and
  `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` attributes, and
  session ID, agent/prompt version and workflow ID so traces and logs
  correlate. Keep content capture off by default per the PII-redaction rule in
  `security.md`, Execution and operations.** The conventions are still in Development status;
  instrumentations that honour `OTEL_SEMCONV_STABILITY_OPT_IN` emit the latest
  ones only with `gen_ai_latest_experimental`. (Albada Ch. 10)
- **Triage failures with a reproducibility test before reacting: rerun 3–5×;
  ≥80% failure rate = systematic bug for engineering; otherwise check drift
  statistically (PSI > 0.25 major / > 0.1 minor, KS > 0.1)** instead of chasing
  single-sample noise. (Albada Ch. 10)
