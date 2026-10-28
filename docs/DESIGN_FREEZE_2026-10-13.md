# DESIGN FREEZE — Scaling-Law Data Scale & Experiment Design

> ## ⚠ 状态更新（2026-10-23）：`HISTORICAL / SUPERSEDED`（仅限项目规划约束）
>
> 本文记录的是 2026-10-13 当时真实的设计冻结（保留原文，**不抹除**）。
> 项目现进入 `TRANSITION / PLANNING` 阶段，当前规划见
> [`docs/PROJECT_TRANSITION_PLAN.md`](PROJECT_TRANSITION_PLAN.md) 与
> [`docs/TRAINING_TRANSITION_PLAN.md`](TRAINING_TRANSITION_PLAN.md)。
>
> 已失效（不再约束当前工作）：
>
> ```text
> 生产 DOE d = 6 / seed = 1 / 单一主序列          -> HISTORICAL / SUPERSEDED
> ONE_6D_POINT_ONE_CASE 作为唯一生产路线           -> HISTORICAL / SUPERSEDED
> FINAL_N_TRAIN_MAX 100000 / FINAL_N_TEST 20000    -> 降为参考值（非冻结约束）
> FINAL_N_LADDER 1k..100k                          -> 降为候选梯度（非强制）
> 生产规模冻结作为本地几何生成的前置条件            -> 不再适用
> ```
>
> 继续有效：
>
> ```text
> N = usable training case count                   -> RETAINED（定义不变）
> 训练集 / 测试集完全分离的原则                     -> RETAINED
> 几何算法 / 历史回归 / GeomTurbo 格式 / QC 契约     -> 不受影响（技术冻结仍有效）
> ```
>
> 当前几何生成路线是 11 维、三组独立 Sobol（`PROPOSED / NOT EXECUTED`），
> 数值范围沿用 `config/geometry_ranges_frozen_a.yaml`，本次未修改任何数值。

Date: 2026-10-13
Status at the time: **FROZEN** — 现为 `HISTORICAL / SUPERSEDED`（见上方状态更新）
Scope: design freeze ONLY — **no production data was generated.**


This document **was** the authoritative status for production scale, training ladder,
test set and the production route **at the time of the 2026-10-13 freeze**.
It is now kept as a historical record: the planning constraints are
`HISTORICAL / SUPERSEDED`, while the `N` definition and the train/test separation
principle are retained. See `docs/PROJECT_TRANSITION_PLAN.md` for the current plan.

## 1. Definition of N (RETAINED)

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
