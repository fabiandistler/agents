# Adaptation and serving conventions

Rules for prompting, finetuning, training data, serving and cost caps.

Citations: Huyen = Chip Huyen, *AI Engineering* (O'Reilly, 2025); Albada = Michael Albada, *Building Applications with AI Agents* (O'Reilly, 2025).

## Contents

- [Prompting](#prompting)
- [Adaptation](#adaptation)
- [Finetuning](#finetuning)
- [Data](#data)
- [Serving & architecture](#serving--architecture)

## Prompting

- **Keep prompts out of application code.** Store them as separate files/objects
  with metadata — target model, sampling params, input/output schemas — and
  version them like code. (Huyen Ch. 5)
- **Decompose a complex task into chained single-purpose prompts, and route the
  simple steps to cheaper models** (e.g. intent classification). Budget the
  added first-token latency the extra hop introduces. (Huyen Ch. 5)
- **End a classification/structured prompt with an explicit input-terminating
  marker that cannot occur in the data** — otherwise the model may continue the
  input instead of answering it. (Huyen Ch. 5)
- **Evaluate every prompt change at the system level, not only on its subtask.**
  A subtask win can be a system-level regression. (Huyen Ch. 5)
- **Inspect every prompt a prompt-engineering tool generates, and count its
  hidden API calls** — 10 variants × 30 eval examples is 300 calls per run.
  (Huyen Ch. 5)
- **Repeat critical instructions both before AND after untrusted content, and
  name explicitly what must never be output.** After the untrusted content,
  repeat only the critical check, so the cached prompt prefix stays stable.
  (Huyen Ch. 5)

## Adaptation

- **Reject "prompting doesn't work" unless the prompt experiments were
  systematic** — versioned prompts, fixed eval data, standardized metrics. Most
  such claims trace to unsystematic prompting. (Huyen Ch. 7)
- **Test feasibility with the strongest model you can afford, then work down the
  cost curve.** If the strongest model fails, weaker ones will too. (Huyen Ch. 4, 7)
  - ❌ prototyping on the cheapest model   ← likely-default
- **Don't assume a domain-specific task requires a specialist finetune.**
  Frontier general models routinely beat domain specialists (the BloombergGPT
  case). (Huyen Ch. 7)

## Finetuning

- **Choose SFT for format and style with demonstrations, DPO when pairwise preferences are cheaper than demonstrations, RFT when outputs are verifiable and a grader exists.** RFT works with scarce labels, often after an SFT cold start; the grader must first pass the judge-calibration rule in `evaluation.md`, Evaluation.
- **Start with LoRA/PEFT; attempt full finetuning only with thousands of
  examples or more** — with a few hundred, full finetuning won't beat LoRA.
  (Huyen Ch. 7)
- **Sequence the runs:** verify the training code on the cheapest model, verify
  the data on a mid-tier model (training loss must fall), then map the
  price/performance frontier across models. (Huyen Ch. 7)
- **After finetuning for one task, re-evaluate every other task type the model
  serves** — single-task finetuning degrades the rest. If irreconcilable, use
  separate models or merge. (Huyen Ch. 7)
- **Hyperparameter starting points (self-hosted training only; hosted finetuning APIs manage these):** LR = 0.1–1× the model's final
  pre-training LR (search 1e-7–1e-3); effective batch ≥ 8 (use gradient
  accumulation); 1–2 epochs for millions of examples, 4–10 for thousands;
  prompt-loss weight ~10%. (Huyen Ch. 7)
- **Prefer LoRA when serving many task variants of one base model** — adapters
  share the base at serving time. (Huyen Ch. 7)

## Data

- **Manually inspect samples before any pipeline decision, and re-annotate a few
  examples yourself to audit annotation quality.** ~15 minutes of looking at
  data routinely beats hours of downstream debugging. (Huyen Ch. 8)
- **Deduplicate before training.** Repeating 0.1% of data 100× measurably halved
  effective model capacity in a published study; duplicates also contaminate
  train/test splits. (Huyen Ch. 8)

## Serving & architecture

- **When out-of-scope requests are common or need a separate path, front the
  system with a small, cheap intent classifier and use stock responses where no
  LLM call is needed.** (Huyen Ch. 10)
- **When multiple models or providers need shared routing or controls, use a
  gateway** for a unified interface, per-app access, fallbacks, and usage limits.
  Keep provider keys out of application code. (Huyen Ch. 10)
- **Before an unattended job calls a paid model API, give it a hard stop at
  the provider, not an alert:** a per-project or per-key spend cap where the
  provider has one; on Azure, where budgets only notify, the deployment's TPM
  quota plus a job timeout. TPM caps the rate, not the total, so write the
  worst case next to the job config: TPM × max run minutes × price. Treat a
  spend-cap 429 as final — retrying cannot restore access. Caps enforce
  late; size them with headroom. (Willison 05.10.2026; Microsoft Learn,
  Azure OpenAI quota)
  - ✅ nightly eval job on its own deployment at 20k TPM, 30-min timeout, max cost in the README
  - ❌ subscription budget alert at 100 %, shared deployment at default TPM   ← likely-default
- **When latency matters, fire redundant parallel calls and take the first
  acceptable response** instead of sequential retries. (Huyen Ch. 10)
- **Never cache user-specific or time-sensitive responses** — cached
  personalized answers leak across users. (Huyen Ch. 10)
- **Treat semantic caching as guilty until proven:** adopt it only with a
  demonstrated high hit rate. Embedding + threshold + vector search are three
  coupled failure points. (Huyen Ch. 10)
- **Self-hosting only:** the usual highest-leverage optimizations are
  quantization, replica parallelism, tensor parallelism, and attention/KV-cache
  optimization. (Huyen Ch. 9)
