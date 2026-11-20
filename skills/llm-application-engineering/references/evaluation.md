# Evaluation conventions

Rules for eval harnesses, LLM judges, agent evaluation, rollout experiments and production triage.

Citations: Huyen = Chip Huyen, *AI Engineering* (O'Reilly, 2025); Albada = Michael Albada, *Building Applications with AI Agents* (O'Reilly, 2025).

## Contents

- [Evaluation](#evaluation)
- [Agent Evaluation](#agent-evaluation)
- [Deployment & Learning](#deployment--learning)
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
  - ❌ retrying until the response parses   ← likely-default
- **When an LLM sits in the decision path of a rating or classification (grade,
  level, category), measure repeat stability: run the same input N ≥ 5 times
  and report the agreement rate alongside accuracy.** Below the agreed
  threshold the product shows a range or an explicit uncertainty flag — never a
  single value. Identical input with differing output is a defect class of its
  own, not noise. (Albada Ch. 3)
  - ❌ one run per input, accuracy as the only column   ← likely-default
- **Evaluate each pipeline component independently AND end-to-end, per-turn AND
  per-task.** Otherwise failures can't be localized.
  - ❌ scoring only the final output   ← likely-default
  (Huyen Ch. 4)
- **Give each failure mode its own binary pass/fail judge, never a
  continuous score** — wider or continuous ranges degrade judges. Use a
  discrete scale only with an explicit reason. Require a critique before the
  verdict and include a worked example with justification per verdict. (Huyen Ch. 3)
  - ❌ "rate from 0 to 100" / 0.0–1.0   ← likely-default
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
- **Map eval metrics to a business metric and set a usefulness threshold before
  shipping.** (Huyen Ch. 1, 4)
- **A judge score without a gold reference is a screening signal, not an
  acceptance criterion.** Judge–human agreement degrades as task difficulty
  rises and settles at 77–82% on hard agent tasks when no reference answer is
  supplied; a larger judge model does not close the gap. Acceptance needs either
  a reference answer in the test case or a human sample on the hardest slice.
  (AgentJudgeBench)
  - ❌ promoting an uncalibrated judge-scored aggregate to a release gate   ← likely-default
- **When an agent step sits in front of a human or CI gate (approve/reject,
  ship/request changes, CI pass/fail, revert within N days), persist every gate
  verdict joined to the run/trace ID and prompt version from day one.** These
  verdicts are free labels — the gold reference the rule above asks for — and
  without them every prompt change is tested unlabelled. (Arize)
  - ❌ verdicts left in the review tool, never joined to traces   ← likely-default
- **Score the agent against the gate's first verdict and count misses (agent
  approved; gate rejected or later reverted) and false alarms (agent flagged;
  gate shipped) separately — never as one agreement rate.** Later rounds judge a
  revised change, not the agent's call. Promote a prompt only with fewer misses
  and no more false alarms. (Arize)
  - ❌ a single agreement percentage   ← likely-default
- **Audit a sample of gate verdicts too: the gate is the reference, not
  infallible ground truth.** (Arize)
- **Prove construct validity at item level before a benchmark or test set becomes
  an acceptance criterion — or before publishing one.** Score individual items,
  not just the aggregate: a set can discriminate on general reasoning while
  claiming to measure the target capability (BBQ, a bias benchmark, correlates
  more strongly with reasoning than with safety). The same item-level analysis
  identifies the ~10% of items that carry the discrimination, which is what makes
  a set cheap to run repeatedly. (BenchMIRT)
- **Where users can override a model result, offer guided alternatives before
  free-form editing, persist the correction, and log it as a labelled example.
  Report correction rate per output field as a quality metric with a ceiling.
  If correcting costs more than doing the task by hand, the feature has
  failed — corrections never compensate for low base quality.** (Apple HIG,
  Corrections)
  - ❌ treating user edits as noise instead of labels   ← likely-default

## Agent Evaluation

- **Ship the first agent version with eval cases that assert: correct tool
  called, correct parameters, response contains required phrases.** Track tool
  recall, tool precision, parameter accuracy, phrase recall, task success.
  (Albada Ch. 2, 9)
- **Structure each eval example as input state + conversation history + expected
  final state** (expected `tool_calls` with params, `customer_msg_contains`), so
  scoring is automatable. (Albada Ch. 9)
- **Every change that adds a tool or workflow adds matching eval cases in the
  same change** — the eval set is the living spec. (Albada Ch. 9)
- **Export production failures AND exemplary successes (golden paths) as
  regression eval cases;** grow the set by LLM-generating adversarial/
  counterfactual variants with human review before inclusion. (Albada Ch. 9–11)

## Deployment & Learning

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
| **User behavior** | Early-termination rate, turns per conversation, input/output token distribution, prompt complexity | Implicit signals that need no user annotation — see the feedback signals below. |
| **Cost** | Input/output token volume, tokens per second (TPS), rate-limit hits | Rate-limit hits should trigger scaling or routing decisions. |
| **Drift** | System-prompt drift, user-behavior drift, provider-model drift | The most underestimated family. The first two have no classic-software equivalent; provider drift (silent model updates behind an API) is detectable only through periodic probing with fixed reference inputs. |

### Five implicit-feedback signals

Explicit feedback (thumbs up/down, stars) is rare and biased in conversational
AI — only frustrated or delighted users bother. Implicit feedback is
generated by every conversation automatically: it is proprietary, continuous,
and honest (behavior shows what a rating hides).

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

- **Route agent telemetry into the same observability stack as other services —
  no separate agent-monitoring silo.** Tag spans/logs with session ID,
  agent/prompt version, and workflow ID so traces and logs correlate. (Albada Ch. 10)
- **Instrument with the OpenTelemetry GenAI semantic conventions: `invoke_agent` parent with `chat` and `execute_tool` spans, `gen_ai.request.model` and `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` attributes; keep content capture off by default per the PII-redaction rule in `security.md`, Security.** Experimental — opt in via `OTEL_SEMCONV_STABILITY_OPT_IN`.
- **Triage failures with a reproducibility test before reacting: rerun 3–5×;
  ≥80% failure rate = systematic bug for engineering; otherwise check drift
  statistically (PSI > 0.25 major / > 0.1 minor, KS > 0.1)** instead of chasing
  single-sample noise. (Albada Ch. 10)
- **Escalate to a human on low model certainty (>20% divergence across an
  ensemble of runs, or low mean token logprobs) or high consequence;** a
  self-reported confidence score is a weak tiebreaker only, since verbalized
  confidence is poorly calibrated. Tune thresholds so < ~10% of cases
  escalate. (Albada Ch. 11 for escalation and the ~10% target; demoting the
  self-reported score departs from it, per Xiong et al., ICLR 2024,
  arXiv:2306.13063: verbalized confidence runs overconfident, sampling
  consistency predicts failure better.)
