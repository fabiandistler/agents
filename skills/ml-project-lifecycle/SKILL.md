---
name: ml-project-lifecycle
category: ai-ml
environments: coding
description: Guide a machine learning project from problem framing through model selection to production deployment.
metadata:
  version: "1.0"
---

# ML Project Lifecycle

A machine learning project fails or succeeds long before anyone tunes a hyperparameter. This skill bundles three checkpoints from the lifecycle where that failure is most often locked in early and invisibly: framing the problem, choosing the model, and shipping it safely. Use it as a gate to pass through, not a menu to skim — each part below exists because skipping it produces a specific, recognizable failure mode.

## When to use

Whenever someone is scoping an ML project, picking a model architecture, deciding how to handle missing data, evaluating whether a model is good enough to ship, designing a feature-engineering pipeline, or planning how to deploy and retrain a model in production. Bundles a business-objectives-first checklist, a five-baseline deployment gate, a missing-values default for prediction versus inference, a data-type-to-model decision table, and a staged rollout checklist.

## Part A — Framing: get the problem right before touching a model

### Business-objectives-first

The real problem in a data-science project is never technical. It is always a business problem. ML metrics such as accuracy or F1 are worthless if they do not move a business metric — a model at 94.2% accuracy is not better than one at 94% if both produce the same conversion rate. Organizations optimize for revenue, cost, or customer satisfaction, not for accuracy.

The job of the practitioner is to translate systematically between the two:

- "Each additional percentage point of accuracy has historically raised purchase-through rate by 0.5%."
- "A false-negative rate above 5% raises support tickets by €X/month."

Without this translation, technical excellence is wasted effort. Before any ML decision — model choice, feature engineering, evaluation — answer three questions:

1. Which business problem does this decision address?
2. Which business metric does it move?
3. How will the connection between the two be measured?

If a decision cannot be traced to a business metric, treat that as a signal to stop and re-scope, not a detail to fill in later.

### The five-baseline gate

A model's absolute metric score is meaningless without a baseline. Effective ML evaluation compares a candidate model against **five baseline types** before it is deployment-worthy:

| # | Baseline | What it is |
|---|----------|------------|
| 1 | Random baseline | Random predictions — the floor |
| 2 | Simple heuristic | A hand-written domain rule (e.g. "spam if >5 links") |
| 3 | Zero rule baseline | Always predict the most frequent class |
| 4 | Human baseline | Human expert performance on the same task |
| 5 | Existing solution | The current production system, if one exists |

This gate exists to catch "a bad model with good-looking metrics" — a model can post an impressive accuracy number and still lose to a one-line heuristic or to the system it is meant to replace. The bar: clearly beat the random, simple-heuristic, and zero-rule baselines, and beat the existing production solution if one exists. The human baseline is a reference ceiling rather than a pass/fail gate — measure the gap to expert performance and judge whether it is acceptable for the use case.

### Missing values: prediction default first, mechanism only for inference

For prediction, do not diagnose the missingness mechanism first — MAR and MNAR cannot be distinguished from observed data alone. The default, whatever the mechanism:

- Prefer a model with native NaN handling (`HistGradientBoostingClassifier`/`Regressor`, XGBoost, LightGBM, CatBoost) where the stack allows it; or
- Simple imputation plus a missingness indicator, fit inside CV (see the ordering constraint in Part C): `SimpleImputer(add_indicator=True)` in sklearn, or `step_indicate_na()` plus a `step_impute_*()` step in tidymodels recipes.

Do not default to "drop the row" as a house style — dropping discards the exact signal that makes the missingness informative. Never use the target/outcome when imputing predictors for a prediction task — it leaks the label into the features.

Keep the MCAR/MAR/MNAR taxonomy only for inference and effect estimation, where unbiased estimates (not predictive accuracy) are the goal — there use multiple imputation (MICE) and pool the estimates across imputations.

## Part B — Model selection

### Data-type decision table

Pick the model family from the shape of the data first, and prefer the boring, well-understood option unless the data specifically calls for more:

| Data type | First choice | Notes |
|-----------|--------------|-------|
| Structured / tabular | XGBoost / LightGBM / CatBoost | Frequently outperforms deep learning on tabular data. Reach for deep learning only with very large datasets (>100k rows) or genuinely complex feature interactions; a simple 3–5 layer feed-forward network is usually enough when you do |
| Images | CNNs | Transfer learning with a pretrained backbone (ResNet, EfficientNet) is the practical default; vision transformers become worthwhile only at very large dataset sizes |
| Text | Transformer-based models (BERT-style; language-specific variants such as GBERT for German) | For classification, sentence-transformer embeddings are often sufficient without a full fine-tune; LSTMs are legacy and rarely the right first choice now |
| Time series | ARIMA / Prophet | Often sufficient on their own. LSTMs, GRUs, or Temporal Fusion Transformers for deep-learning approaches; transformer-based time-series models (e.g. TimesFM) are the current frontier |

Treat the specific model names as illustrative of the *category* to reach for, not a permanent ranking — this table will date faster than the decision process itself.

### Layer-design rules of thumb

For the 80% case, a small pyramid-shaped feed-forward network is enough:

```
Dense(128, relu) -> Dropout(0.3) -> Dense(64, relu) -> Dropout(0.3) -> Dense(32, relu) -> Dense(output)
```

- Start layer widths at powers of two (64, 128, 256).
- Shape the network as a pyramid: each layer roughly half the width of the one before it.
- Overfitting -> remove a layer or increase dropout.
- Underfitting -> add a layer or widen the existing ones.

Must-have working knowledge before tuning anything further: data preprocessing (normalization, encoding, train/val/test split), recognizing overfitting (validation loss rising while training loss falls), the basic hyperparameters (learning rate, batch size, epochs), and the fact that raw accuracy is often misleading on imbalanced data. Optimizer choice, advanced regularization, custom losses, and architecture search are nice-to-have, not must-have.

### AutoML notes

AutoML (AutoKeras, H2O AutoML, AutoGluon, FLAML) is a legitimate way to get a fast baseline and a proof-of-concept, and it bundles hyperparameter tuning. It is not a substitute for a considered model.

- **Use it for:** a quick baseline, proof-of-concept work, standard well-trodden problems where time matters more than a marginal accuracy gain.
- **Its costs:** it is a black box that is hard to debug, it can overfit to the validation data, it gets expensive on large datasets, and it cannot encode domain-specific structure a practitioner knows about.

A workable default workflow: start with a simple model (e.g. XGBoost) as the real baseline, run AutoML in parallel purely as a comparison point, move to deep learning (starting from pretrained models where available) only if the simple baseline is insufficient, and refine iteratively only in response to a genuine business need — not because a metric could theoretically go higher.

## Part C — Pipeline and deployment checklist

### Feature-engineering pipeline, in order

1. **Missing values** — native NaN handling or simple imputation plus a missingness indicator, per the prediction default above.
2. **Scaling** — normalization (0–1) or standardization (mean 0, std 1).
3. **Discretization** — continuous to categorical; optional, and often does not help.
4. **Encoding categoricals** — see the hashing trick below for categories that are not fixed in advance.
5. **Feature crossing** — model non-linear relationships between features explicitly.
6. **Positional embeddings** — for sequence-based data.

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

**Handling categories that appear only in production** (a new brand on a marketplace, a new user account): a hash function maps every category — seen or unseen — into a fixed index space (e.g. 2^18 = 262,144 slots) that is defined ahead of time. New categories are automatically encoded validly; occasional hash collisions between two categories are an acceptable trade-off for never crashing on an unseen value. (`sklearn.feature_extraction.FeatureHasher`, TensorFlow `tf.keras.layers.Hashing`, or Vowpal Wabbit's hashing trick.)

### Staged deployment

Roll out a new model in four stages, each one de-risking the next:

1. **Shadow deployment** — the new model runs in parallel, its predictions are logged, but it has zero user impact.
2. **A/B testing** — route a percentage of traffic to the new model and compare business metrics against the incumbent, not just ML metrics.
3. **Canary release** — graduate the rollout in steps (e.g. 1% -> 10% -> 50% -> 100%).
4. **Full deployment** — switch all traffic over once every prior stage has validated the model.

This sequence exists to minimize production risk on every model update — skipping a stage (e.g. going straight from shadow to full) reintroduces the risk the sequence was built to remove.

### Retraining triggers

Retrain on any of these signals, not on a schedule alone:

- **Scheduled** — daily or weekly, as a baseline cadence.
- **Performance degradation** — e.g. an accuracy drop greater than 2%.
- **Data-distribution shift** — e.g. KL-divergence between recent and training-time feature distributions exceeding a set threshold.
- **Business event** — a product launch, a seasonal change, or another event known to shift the underlying data-generating process.

## Common pitfalls

- Optimizing a technical metric (accuracy, F1) that was never tied back to a business metric — this is the single most common way "successful" ML projects fail to matter.
- Comparing a new model only to its own past runs, never to all five baseline types — a model can look good in isolation and still lose to a domain heuristic.
- Treating every missing-value column the same way (blanket drop or blanket impute) instead of using native NaN handling or imputation plus a missingness indicator — this silently discards signal, especially where the missingness itself carries information.
- Reaching for deep learning on structured/tabular data by default, when a gradient-boosted tree model is usually both simpler and stronger there.
- Fitting any preprocessing step (imputation, scaling, encoding, selection, tuning) outside cross-validation — a data-leakage bug that inflates offline metrics and does not survive contact with production.
- Hard-coding a fixed category vocabulary for categorical features, so the first unseen category in production crashes or silently mis-encodes.
- Skipping a deployment stage (e.g. shadow or canary) to ship faster, which removes the exact safety net staged deployment is designed to provide.
- Treating retraining as purely calendar-based and missing distribution-shift or business-event triggers that matter more than the clock.

## Source

This skill distills notes sourced from Chip Huyen, *Designing Machine Learning Systems*, with layer-design and data-type guidance additionally informed by general deep-learning practice notes. Treat specific library and model names as a snapshot of common practice at the time of writing, not a permanent recommendation.
