# Adaptation and serving conventions

Citations: Huyen = Chip Huyen, *AI Engineering* (O'Reilly, 2025).

## Contents

- [Prompting and model choice](#prompting-and-model-choice)
- [Finetuning](#finetuning)
- [Training data](#training-data)
- [Serving and cost](#serving-and-cost)

## Prompting and model choice

- **Keep prompts out of application code.** Store them as separate files/objects
  with metadata — target model, sampling params, input/output schemas — and
  version them like code. (Huyen Ch. 5)
- **Inspect every prompt a prompt-engineering tool generates, and count its
  hidden API calls** — 10 variants × 30 eval examples is 300 calls per run.
  (Huyen Ch. 5)
- **Repeat critical instructions both before AND after untrusted content, and
  name explicitly what must never be output.** After the untrusted content,
  repeat only the critical check, so the cached prompt prefix stays stable.
  (Huyen Ch. 5)
- **Reject "prompting doesn't work" unless the prompt experiments were
  systematic** — versioned prompts, fixed eval data, standardized metrics. Most
  such claims trace to unsystematic prompting. (Huyen Ch. 7)
- **Test feasibility with the strongest model you can afford, then work down the
  cost curve.** If the strongest model fails, weaker ones will too. (Huyen Ch. 4, 7)

## Finetuning

- **Choose SFT for format and style with demonstrations, DPO when pairwise preferences are cheaper than demonstrations, RFT when outputs are verifiable and a grader exists.** RFT works with scarce labels, often after an SFT cold start; the grader must first pass the judge-calibration rule in `evaluation.md`, Evaluation.
- **Start with LoRA/PEFT; attempt full finetuning only with thousands of
  examples or more** — with a few hundred, full finetuning won't beat LoRA.
  LoRA adapters also share one base model at serving time, which suits many
  task variants. (Huyen Ch. 7)
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

## Training data

- **Manually inspect samples before any pipeline decision, and re-annotate a few
  examples yourself to audit annotation quality.** ~15 minutes of looking at
  data routinely beats hours of downstream debugging. (Huyen Ch. 8)
- **Deduplicate before training.** Repeating 0.1% of data 100× measurably halved
  effective model capacity in a published study; duplicates also contaminate
  train/test splits. (Huyen Ch. 8)

## Serving and cost

- **Before an unattended job calls a paid model API, give it a hard stop at
  the provider, not an alert:** a per-project or per-key spend cap where the
  provider has one; on Azure, where budgets only notify, the deployment's TPM
  quota plus a job timeout. TPM caps the rate, not the total, so write the
  worst case next to the job config: TPM × max run minutes × price. Treat a
  spend-cap 429 as final — retrying cannot restore access. Caps enforce
  late; size them with headroom. (Willison 05.10.2026; Microsoft Learn,
  Azure OpenAI quota)
- **When latency matters, fire redundant parallel calls and take the first
  acceptable response** instead of sequential retries. (Huyen Ch. 10)
- **Treat semantic caching as guilty until proven:** adopt it only with a
  demonstrated high hit rate. Embedding + threshold + vector search are three
  coupled failure points. (Huyen Ch. 10)
