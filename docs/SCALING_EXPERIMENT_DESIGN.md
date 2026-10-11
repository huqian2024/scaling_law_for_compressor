# Scaling Experiment Statistical Design

> Status: design specification (living document).
> This file records the **statistical design principles**, **open decisions** and
> **leakage risks** that a future `E(N, P)` scaling-law experiment must obey.
> It is **NOT** a final experiment parameter table and does **NOT** fix any
> `N`, `P`, `metric` or repetition count.

## 1. Experiment objects

```text
N = training case count

P = trainable parameter count
    (primarily for scaling WITHIN one model family)

E = generalization error under a frozen evaluation protocol
```

The concrete mathematical definition of `E` is still **TBD** (see section 8).

### PCA + MLP note

`P` is defined as:

```text
P = MLP trainable parameter count

K_PCA = PCA retained dimension / representation-capacity hyperparameter
```

`P = PCA dimension + MLP parameter count` is explicitly **not** used.

If PCA dimension and MLP size are ever varied together, they must be managed as
**two distinct experimental variables**. A PCA basis that is a non-trained
preprocessing step does **not** count toward trainable parameter count.

## 2. Nested training principle

Production DOE family (frozen): **scrambled Sobol**.

The nested training pool is now supported by:

```text
fixed Sobol master sequence prefixes
D_N = first N cases of the frozen production master sequence
```

See `docs/DOE_DECISION.md` sections 12-13.

Main-experiment principle:

```text
D_train(N1) ⊂ D_train(N2) ⊂ ... ⊂ D_train(Nmax)
```

Purpose:

- control dataset realization differences;
- improve consistency of cross-`N` comparison;
- reduce extra variance introduced by different random sample sets;
- improve the interpretability of the scaling curve.

Mandatory limitation:

```text
Nested subsets improve controlled comparability across N,
but E(N2)-E(N1) must not be interpreted as a pure causal
effect of the newly added samples.
```

Reasons include:

- training stochasticity;
- optimization trajectory;
- model selection;
- finite-sample effects.

## 3. Frozen validation / test principle

Three candidate schemes are recorded:

- Scheme A: different validation/test split per `N`;
- Scheme B: fixed validation + fixed test for all `N` and `P`;
- Scheme C: fixed test, but validation varies with training size.

Scheme B is marked as:

```text
PREFERRED DESIGN
```

and is **not** FINAL.

Principles:

- train / validation / test case IDs must not overlap;
- the test set is frozen before any model training;
- all main scaling `(N, P)` use the **same** test set;
- the main in-distribution test set should come from the **same Omega** as the
  training main experiment;
- if extrapolation is studied later, a **separate OOD test set** must be created
  and must not be mixed into the same in-distribution `E(N, P)` metric.

If validation is used for:

- early stopping;
- hyperparameter selection;
- checkpoint selection;

then validation should also be frozen as much as possible.

## 4. Canonical dataset and split separation

Pipeline:

```text
CFD production
  -> canonical dataset
  -> split definition
  -> model-specific preprocessing
  -> training
```

A CFD case itself does **not** permanently carry:

```text
train
validation
test
```

labels.

The split is defined through an **independent, versioned case-ID mapping**.
Conceptually, in the future there could be:

```text
splits/
    scaling_split_v1.yaml
```

This file is **not** created in this checkpoint.

## 5. Randomness taxonomy

Seed semantics must be kept separate; a single generic `seed` field is not
sufficient.

### DOE / dataset realization seed

Controls:

```text
which CFD samples constitute a dataset realization
```

### split seed

If the split uses a random process, it controls:

```text
train / validation / test assignment
```

Once the official split is frozen, both the seed and the resulting split must be
versioned.

### training seed

Controls:

```text
weight initialization
minibatch ordering
optimizer stochasticity
```

These three seed semantics are distinct and must be recorded separately.

## 6. Repetition design

Two levels are recorded:

```text
dataset realization repetition
training repetition
```

Potential experiment structure:

```text
dataset_seed
    x
training_seed
```

Marked as:

```text
OPEN DESIGN DECISION
```

Repetition counts are **not** fixed here.

- training repetitions mainly quantify **optimization / training variance**;
- dataset repetitions mainly quantify **dataset realization variance**.

## 7. Error metric contract

No formula is defined here yet. The following items must be frozen in the future:

- test set version
- field list
- field units
- field normalization
- spatial weighting
- domain weighting
- field weighting
- mask definition
- per-case aggregation
- across-case aggregation
- interpolation / grid mapping version
- treatment of invalid / missing cases

Three levels are retained:

```text
per-field metrics
per-domain metrics
global metric E
```

The global `E` can only be defined **after** the aggregation contract above is
frozen.

## 8. Model-size policy

### Within-family

Prefer `trainable_parameter_count` as `P`.

But each family's own structural variables must still be recorded separately:

```text
PCA+MLP:
    K_PCA
    MLP architecture

U-Net:
    depth
    channel schedule

FNO:
    width
    modes
    layers
```

### Cross-family

An identical `trainable parameter count` does **not** mean different architectures
have the same compute or the same representational capacity.

Therefore:

```text
within-family scaling
```

and

```text
cross-family benchmark
```

must be treated as two different analytical questions.

A future cross-family comparison may also need to report:

- parameter count;
- training FLOPs / compute;
- inference cost;
- memory.

No concrete compute metric is designed in this checkpoint.

## 9. Leakage checklist

- A single `case_id` must not enter both train and test.
- Normalization statistics may only be computed from the training set.
- The PCA basis may only be fitted on the training set.
- Test must not participate in hyperparameter selection.
- Test must not participate in checkpoint selection.
- Test must not be used to select the training seed.
- Model-specific interpolation / preprocessing must not use test-derived
  statistics.
- The nested training pool must not overlap with the frozen validation / test.

### Geometry-group leakage

If the future uses:

```text
one geometry
-> multiple Incidence/Mach operating conditions
```

then a `geometry_id`-level **grouped split** must be considered. Different
operating conditions of the same base geometry must, in principle, not be assigned
across train/test without analysis.

This design is currently marked:

```text
TBD - depends on future operating-condition sampling strategy
```

## 10. Recommended conceptual structure

```text
DOE specification
    |
    v
CFD production
    |
    v
canonical dataset
    |
    v
frozen split specification
    |
    v
nested train subsets
    |
    v
model-specific preprocessing fitted on TRAIN only
    |
    v
model family
    |
    v
model size P
    |
    v
training repetitions
    |
    v
frozen evaluation protocol
    |
    v
E(N, P)
    |
    v
scaling-law analysis
```

## 11. OPEN DECISIONS

Closed by the FINAL_DOE decision (see `docs/DOE_DECISION.md` sections 12-14):

```text
FINAL_DOE         = scrambled Sobol            (CLOSED)
legacy 1891 role  = historical reference / regression / Golden-Case source only
                                                (CLOSED)
```

Still open:

1. scaling N ladder
2. Nmax
3. validation / test split policy
4. validation / test sample sizes
5. number of training repetitions
6. whether dataset realizations are repeated
7. final `E` definition
8. model-size grids `P`
9. geometry reuse / multiple operating-condition strategy

Nothing else in this document is closed by the FINAL_DOE decision.

