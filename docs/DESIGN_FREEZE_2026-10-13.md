# DESIGN FREEZE — Scaling-Law Data Scale & Experiment Design

Date: 2026-10-13
Status: **FROZEN (current authoritative status)**
Scope: design freeze ONLY — **no production data was generated.**

This document is the current authoritative status for production scale, training
ladder, test set and the production route. Where it conflicts with older documents
(or with older `PENDING` entries), **this document wins**.

## 1. Definition of N (FROZEN)

```text
N = usable training case count
```

- only CFD cases actually usable for model training are counted;
- test cases are NOT counted;
- validation cases (if ever added) are NOT counted;
- failed / rejected / non-usable cases are NOT counted.

The published data scaling law uses:

```text
E = E(N)
```

where `N` is always the usable training sample count.

## 2. Maximum training size (FROZEN)

```text
FINAL_N_TRAIN_MAX = 100000
N_max = 100000 usable training cases
```

## 3. Fixed test set (FROZEN)

```text
FINAL_N_TEST      = 20000
TRAIN_TEST_RATIO  = 5:1
```

```text
training pool and test set are completely disjoint
the test set is fixed once and stays fixed
all training tiers use the same test set
PCA+MLP, U-Net, FNO use the same test set
the test set never participates in training
the test set is NOT counted in N
```

Minimum usable data requirement:

```text
100000 usable training cases
+ 20000 usable test cases
= 120000 usable CFD cases

MIN_USABLE_TRAIN_TEST_CASES = 120000
```

```text
FINAL_RAW_CFD_ATTEMPTS > 120000   (exact value PENDING)
```

Failure sources that make raw attempts larger: geometry failure, mesh failure,
CFX-Pre failure, solver failure, non-convergence, physically invalid case,
post-processing failure. The failure reserve must **not** be decided before a real
NUMECA/CFX failure rate is measured in the stress test.

## 4. Frozen training ladder (FROZEN)

```text
FINAL_N_LADDER = [
    1000,
    2000,
    5000,
    10000,
    20000,
    35000,
    50000,
    70000,
    100000
]
```

```text
D_1000 ⊂ D_2000 ⊂ D_5000 ⊂ D_10000 ⊂ D_20000 ⊂ D_35000 ⊂ D_50000 ⊂ D_70000 ⊂ D_100000
```

Strictly nested. All three model families (PCA + MLP, U-Net, FNO) use exactly this
ladder.

## 5. Production DOE (unchanged, already frozen)

```text
method   = scipy.stats.qmc.Sobol
d        = 6
scramble = True
seed     = 1
ordering = native Sobol sequence order
```

Parameter order:

```text
0 Xthick
1 Tmax
2 Metal2
3 Solidity
4 Incidence
5 Mach
```

```text
D_N = first N training cases of the same frozen master Sobol sequence
```

Forbidden:

```text
independent re-sampling per N
sorting / reordering the Sobol sequence
mixing legacy LHS into the main production pool
a separate independent DOE per N
```

Production Sobol master sequence policy:

```text
m = smallest integer satisfying
2^m >= required raw design-pool size

Current lower bound:
m >= 17

because:
2^17 = 131072 > MIN_USABLE_TRAIN_TEST_CASES = 120000
```

However FINAL m remains PENDING because:

```text
- FINAL_RAW_CFD_ATTEMPTS is still PENDING;
- CFD failure reserve is still PENDING;
- validation policy / validation size is still PENDING.
```

Therefore do NOT freeze `m = 17` as sufficient for final production.

The value above is a **lower bound only**, not the final production sequence length.
Powers of two around it, for reference: `2^16 = 65536` (< 120000), `2^17 = 131072`.

No Sobol sequence was generated in this task.

## 6. Production route (FROZEN)

```text
one 6D design point
-> one case
-> one case-specific geometry
-> one .geomTurbo
-> one NUMECA mesh
-> one CFD operating condition
-> one CFD sample
```

```text
Geometry           = f(Xthick, Tmax, Metal2, Solidity)
OperatingCondition = f(Incidence, Mach)
```

```text
GEOMETRY_REUSE   = DISABLED / NOT ACTIVE
PRODUCTION_ROUTE = ONE_6D_POINT_ONE_CASE
```

Geometry / mesh reuse (`1 geometry -> multiple Incidence/Mach`) is **not** used.

## 7. Production parameter ranges (PENDING)

```text
FINAL_PRODUCTION_RANGES = PENDING
```

The six-dimensional production ranges still require the owner / advisor's final
confirmation. Therefore:

```text
config/ranges_legacy.yaml is NOT modified
no candidate expanded range is promoted to FINAL
no empirical range widening is performed by an AI agent
production design generation stays BLOCKED until the ranges are confirmed
```

## 8. Validation policy (PENDING)

```text
FINAL_VALIDATION_POLICY = PENDING
FINAL_N_VALIDATION      = PENDING
```

If an independent fixed validation set is added later:

```text
validation is NOT counted in N
validation must not overlap training / test
total usable CFD demand increases accordingly
```

No validation size or ratio is decided here.

## 9. Raw-attempt accounting (PENDING — distinct concepts)

```text
FINAL_N_TRAIN_MAX           = 100000      (usable training)
FINAL_N_TEST                = 20000       (usable test)
MIN_USABLE_TRAIN_TEST_CASES = 120000      (usable total)
FINAL_RAW_CFD_ATTEMPTS      = PENDING     (raw CFD attempts)
```

The retired umbrella term `FINAL_NMAX` must **not** be used to mean any of these
distinct quantities in current status. Historical mentions may remain in older
documents.

## 10. Non-goals of this freeze

```text
no 01_generate_design.py
no master_design.csv
no Sobol points
no training/test case parameters
no 02_generate_geometry.py run
no 03_geometry_qc.py run
no new .geomTurbo
no NUMECA / CFX / solver
no legacy/ modification
no frozen DOE method/seed/order change
no frozen geometry generator/QC contract change
```

Frozen technical contracts and all files under `legacy/` are untouched.
