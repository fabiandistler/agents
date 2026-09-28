---
name: ml-project-lifecycle
category: ai-ml
environments: coding
description: "Run a classical ML project — training your own model on your own tabular data, not an LLM app: framing, baselines, model choice, missing data, deployment, retraining."
metadata:
  version: "1.0"
---

# ML Project Lifecycle

Use this skill as a gate to pass through, not a menu to skim: framing the problem, choosing the model, and shipping it safely.

## When to use

- Training a model on your own tabular, image, text, or time-series data: scoping the project, picking a model family, handling missing values, or deciding whether it is good enough to ship and when to retrain.
- Classical ML only — for prompting, RAG, agents, or evals over a foundation model, use `llm-application-engineering` instead.

## Part A — Framing: get the problem right before touching a model

### Business-objectives-first

ML metrics such as accuracy or F1 are worthless if they do not move a business metric (revenue, cost, customer satisfaction). Before any ML decision — model choice, feature engineering, evaluation — answer three questions:

1. Which business problem does this decision address?
2. Which business metric does it move?
3. How will the connection between the two be measured?

If a decision cannot be traced to a business metric, treat that as a signal to stop and re-scope, not a detail to fill in later.

Ask early whether a prompted LLM or a plain rule would already meet the business bar — if so, follow `llm-application-engineering` instead of training a model.

### The baseline gate

Climb this ladder before calling anything deployment-worthy:

| # | Baseline | What it is |
|---|----------|------------|
| 1 | Dummy | Always predict the most frequent class — the floor |
| 2 | Simple heuristic | A hand-written domain rule (e.g. "spam if >5 links") |
| 3 | Linear | Logistic or linear regression on the same features |
| 4 | Strong simple model | Untuned GBDT or tabular foundation model |
| 5 | Zero-shot LLM | Optional comparator for text and label tasks |
| 6 | Incumbent | The current production system, if one exists, with human expert performance as the reference ceiling |

Beat means the candidate's cost-weighted metric clears the baseline's cross-validation spread or bootstrap confidence interval — a point win inside the noise does not count.

### Missing values: prediction default first, mechanism only for inference

For prediction, do not diagnose the missingness mechanism first — MAR and MNAR cannot be distinguished from observed data alone. The default, whatever the mechanism:

- Prefer a model with native NaN handling (`HistGradientBoostingClassifier`/`Regressor`, XGBoost, LightGBM, CatBoost) where the stack allows it; or
- Simple imputation plus a missingness indicator, fit inside CV (see the ordering constraint in Part C): `SimpleImputer(add_indicator=True)` in sklearn, or `step_indicate_na()` plus a `step_impute_*()` step in tidymodels recipes.

Do not default to "drop the row" as a house style — dropping discards the exact signal that makes the missingness informative. Never use the target/outcome when imputing predictors for a prediction task — it leaks the label into the features.

Keep the MCAR/MAR/MNAR taxonomy only for inference and effect estimation, where unbiased estimates (not predictive accuracy) are the goal — there use multiple imputation (MICE) and pool the estimates across imputations.

## Part B — Model selection

### Default model choice (as of 2026-09)

Pick the model family from the shape of the data first, and prefer the boring, well-understood option unless the data specifically calls for more:

| Data type | Default | Notes |
|-----------|---------|-------|
| Tabular, up to about 10k-50k rows | Tabular foundation model (TabPFN, TabICL) alongside untuned CatBoost or LightGBM; check licence before commercial use | Foundation models lead on small and medium data; GBDT stays the untuned comparator |
| Tabular, larger data | XGBoost / LightGBM / CatBoost | GBDT first; tabular deep learning only via RealMLP or TabM |
| Images | Pretrained vision foundation model with transfer learning | Train a CNN backbone only when the foundation model cannot run |
| Text | Zero-shot LLM, then embeddings plus linear model, then fine-tune | Sentence-transformer embeddings are often sufficient without a full fine-tune |
| Time series | AutoETS or Theta plus a zero-shot time-series foundation model (Chronos, TimesFM) | Via statsforecast or fable; Prophet is not a first choice |

Treat the specific model names as illustrative of the *category* to reach for, not a permanent ranking — this table will date faster than the decision process itself.

### AutoML notes

AutoML (AutoGluon, H2O AutoML, FLAML; workflowsets in R) is a legitimate way to get a fast baseline and a proof-of-concept, and it bundles hyperparameter tuning. It is not a substitute for a considered model.

- **Use it for:** a quick baseline, proof-of-concept work, standard well-trodden problems where time matters more than a marginal accuracy gain.
- **Its costs:** it is a black box that is hard to debug, it can overfit to the validation data, it gets expensive on large datasets, and it cannot encode domain-specific structure a practitioner knows about.

A workable default workflow: start with a simple model (e.g. XGBoost) as the real baseline, run AutoML in parallel purely as a comparison point, move to deep learning (starting from pretrained models where available) only if the simple baseline is insufficient, and refine iteratively only in response to a genuine business need — not because a metric could theoretically go higher.

## Part C — Pipeline and deployment checklist

### Tooling

| Step | Python | R |
|------|--------|---|
| Pipeline | sklearn Pipeline | tidymodels workflow with recipes |
| Versioning and deployment | vetiver plus pins, MLflow 3 LoggedModel plus registry | vetiver plus pins |
| Monitoring | vetiver monitoring, MLflow | vetiver monitoring |

### Feature-engineering pipeline, in order

1. **Missing values** — native NaN handling or simple imputation plus a missingness indicator, per the prediction default above.
2. **Scaling** — normalization (0–1) or standardization (mean 0, std 1).
3. **Encoding categoricals** — see the hashing trick below for categories that are not fixed in advance.
4. **Feature crossing** — model non-linear relationships between features explicitly.
5. **Positional embeddings** — for sequence-based data.

**Ordering constraint that matters most: every fitted step — impute, scale, encode, select, tune — is fit on training folds only, inside CV.** Fitting any statistic on the full dataset before splitting leaks test-set information into training and inflates validation performance in a way that will not hold in production.

Leakage checklist — pass all six before trusting a validation score:

1. Temporal split — no future information in training; use a time-based split for time-ordered data.
2. Group split — no shared entity across folds (same user, patient, device); split by group.
3. Target-proxy audit — no feature computed from the outcome or only available after it.
4. Duplicate check — no duplicate or near-duplicate rows straddling train and validation.
5. Preprocessing inside CV — every fitted preprocessing step lives inside the cross-validation loop.
6. Test set touched once — the held-out test set is evaluated a single time, never used for tuning.

```python
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import GroupKFold, TimeSeriesSplit, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

preprocess = ColumnTransformer(
    [
        (
            "num",
            Pipeline(
                [
                    ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                    ("scale", StandardScaler()),
                ]
            ),
            numeric_features,
        ),
        (
            "cat",
            Pipeline(
                [
                    ("impute", SimpleImputer(strategy="most_frequent")),
                    ("encode", OneHotEncoder(handle_unknown="ignore")),
                ]
            ),
            categorical_features,
        ),
    ]
)
pipe = Pipeline([("preprocess", preprocess), ("model", model)])
scores = cross_val_score(pipe, X, y, cv=GroupKFold(n_splits=5), groups=groups)
scores = cross_val_score(pipe, X, y, cv=TimeSeriesSplit(n_splits=5))
```

```r
library(tidymodels)

rec <- recipe(label ~ ., data = train) %>%
  step_indicate_na(all_predictors()) %>%
  step_impute_median(all_numeric_predictors()) %>%
  step_impute_mode(all_nominal_predictors()) %>%
  step_dummy(all_nominal_predictors())
wf <- workflow() %>% add_recipe(rec) %>% add_model(spec)
group_vfold_cv(train, group = entity_id, v = 5)
sliding_period(train, index = timestamp, period = "month", lookback = 12, assess_stop = 1)
```

**Handling categories that appear only in production** (a new brand on a marketplace, a new user account): never hard-code a fixed vocabulary. Prefer one of these: sklearn `OneHotEncoder(handle_unknown="infrequent_if_exist")` or TargetEncoder; recipes `step_novel` plus `step_other` plus `step_dummy_hash`; CatBoost native handling. A hashing trick into a fixed index space (e.g. 2^18 slots) remains a fallback where none of the above fits.

### Staged deployment

Two tracks — pick the one matching how the model serves.

Online: shadow, then canary with pre-declared rollback metrics, then full rollout. Shadow runs the new model in parallel with predictions logged and zero user impact. Canary graduates traffic in steps with rollback criteria declared before rollout — roll back when a canary metric breaches its bound. Run an A/B test only when the business effect needs causal proof, with sticky assignment.

Batch: backtest on historical windows, then parallel run alongside the incumbent, then switch. Switch only after the parallel run matches the backtest within the pre-declared tolerance.

### Retraining triggers

Retrain on any of these signals, not on a schedule alone:

- **Scheduled** — daily or weekly, as a baseline cadence.
- **Performance degradation** — the business metric from Part A moves beyond the cost bound agreed there, not a fixed percentage.
- **Data-distribution shift** — PSI above 0.25 signals major shift, above 0.1 minor shift; investigate major shifts and monitor minor ones. Use a proxy metric such as prediction distribution or feature means when labels arrive late.
- **Business event** — a product launch, a seasonal change, or another event known to shift the underlying data-generating process.

## Source

This skill distills Chip Huyen, *Designing Machine Learning Systems* (2022); the tabular defaults reflect tabular-foundation-model practice (2024–2026). Treat specific library and model names as a snapshot of common practice at the time of writing, not a permanent recommendation.
