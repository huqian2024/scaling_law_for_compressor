# DOE Decision Memo

> ## ⚠ 状态更新（2026-10-23）：部分为 `HISTORICAL / SUPERSEDED`
>
> 本文记录 2026-10-13 当时的 DOE 方法决策（保留原文）。当前规划见
> [`docs/PROJECT_TRANSITION_PLAN.md`](PROJECT_TRANSITION_PLAN.md)。
>
> 继续有效：
>
> ```text
> DOE 方法    = SCRAMBLED_SOBOL（scrambled Sobol + 固定种子的思路继续沿用）
> 嵌套前缀    = 组内 D_N 取同一序列前缀（原则继续沿用）
> A1 / A2     = BASELINE_ONLY / DEPRIORITIZED（历史基准结论不变）
> legacy 1891 = historical reference / regression / Golden-Case only（不变）
> ```
>
> 已失效（不再约束当前工作）：
>
> ```text
> 生产 DOE 维度 d = 6                     -> HISTORICAL / SUPERSEDED
> 单一生产序列 + SOBOL_SEED = 1            -> HISTORICAL / SUPERSEDED
>                                       （现为三组独立固定种子，数值 PENDING）
> 参数顺序 [Xthick, Tmax, Metal2, Solidity, Incidence, Mach]
>                                         -> 6D 生产参数顺序不再适用；
>                                            当前几何参数顺序为 11 维（见 frozen_a 配置）
> FINAL_N_TRAIN_MAX / FINAL_N_TEST / FINAL_N_LADDER -> 降为参考值，不再强制
> ```
>
> 当前 11D 几何生成的参数范围与顺序由
> `config/geometry_ranges_frozen_a.yaml` 决定（本次未修改数值）。

> Status at the time: **FINAL PRODUCTION DOE DECISION FROZEN**.
> `FINAL_DOE = SCRAMBLED_SOBOL` (owner / human approval received).
> The historical benchmark evidence below is retained unchanged.
> 现状态：DOE 方法决策保留，6D 生产规划约束为 `HISTORICAL / SUPERSEDED`。


## 1. Background and objective

This project studies the scaling relationship between training data size `N`,
model size `P`, and prediction error `E`.

The main **data-scaling** experiment requires:

```text
fix parameter space Omega
vary only training data size N
```

Different `N` tiers must use **nested** datasets:

```text
D_small  ⊂  D_medium  ⊂  D_large
```

so that a single power law `E(N)` is well-defined and one tier is a strict subset
of the next. Independently redrawn LHS sets (`D_500 ⊄ D_1000`) are therefore not
acceptable for the main ladder.

## 2. Legacy DOE (confirmed by user)

```text
method       = LatinHypercube
d            = 6
optimization = random-cd
seed         = 1
historical N = 1891
```

The historical `N = 1891` is a reference point only and is **NOT** the target size
of the new project. Whether legacy mesh / CFX setup / field schema / provenance are
compatible with future data remains an independent TBD.

## 3. Benchmark conditions

All comparison is done in the **normalized unit hypercube**:

```text
space      = [0,1]^6
benchmark N = 64, 128, 256, 512, 1024
benchmark NMAX = 1024
```

These `N` values are **only for DOE-method comparison**. They are **not** the
official CFD production ladder and **not** the final `Nmax`.

Software environment used for the benchmark:

```text
Python = 3.10.20
SciPy  = 1.15.3
NumPy  = 2.2.6
```

## 4. Candidates tested

### A1 — Master optimized LHS + raw prefix

- One maximum optimized LHS generated once.
- Original generation order preserved.
- Prefixes form nested subsets.
- Most consistent with the legacy DOE family.
- Smaller prefixes inherit weak LHS-prefix space-filling quality.
- Status: `BASELINE_ONLY`.

### A2 — Master optimized LHS + greedy maximin ordering

- Uses the **same master point set** as A1; only the ordering changes.
- Deterministic farthest-point / maximin greedy ordering (start = point nearest
  center, then repeatedly add the point maximizing its minimum distance to the
  already-selected set; ties broken by lowest original index).
- Minimum pairwise distance improves markedly.
- But centered discrepancy and marginal uniformity degrade markedly.
- Status: `DEPRIORITIZED`.
- Note: this is **not** mathematically invalid. It is simply not suitable as the
  priority main scheme given the current benchmark results.

### B — Scrambled Sobol prefix

- `d = 6`, scramble enabled, fixed seed.
- For power-of-two benchmark sizes, generated with `random_base2`
  (balance-preserving Sobol draw).
- Prefixes are naturally nested.
- Best centered discrepancy and marginal balance in the current experiment.
- Constitutes a **DOE family change** relative to the legacy LHS.
- Status: `FINAL_PRODUCTION_DOE` (recorded APPROVED / FINAL at the time — see section 12;
  the 6-D binding part is `HISTORICAL / SUPERSEDED`).

## 5. Metric results (recorded, not re-run)

CD = centered discrepancy (`scipy.stats.qmc.discrepancy`, lower = more uniform);
minpair = minimum pairwise distance; nn = nearest-neighbour distance.

| N | Scheme | CD | minpair | nn_mean | nn_median |
|---|---|---|---|---|---|
| 64 | A1 | 0.028076 | 0.164299 | 0.420933 | 0.429891 |
| 64 | A2 | 0.080258 | 0.609291 | 0.657269 | 0.647761 |
| 64 | B | 0.005271 | 0.359121 | 0.466875 | 0.470454 |
| 128 | A1 | 0.013062 | 0.164299 | 0.370455 | 0.370884 |
| 128 | A2 | 0.040780 | 0.499522 | 0.539571 | 0.534567 |
| 128 | B | 0.001594 | 0.190259 | 0.406139 | 0.404616 |
| 256 | A1 | 0.006433 | 0.089858 | 0.317207 | 0.316833 |
| 256 | A2 | 0.015149 | 0.408983 | 0.446646 | 0.439620 |
| 256 | B | 0.000552 | 0.190259 | 0.355202 | 0.357688 |
| 512 | A1 | 0.002199 | 0.089858 | 0.286323 | 0.287910 |
| 512 | A2 | 0.003814 | 0.318006 | 0.357585 | 0.352436 |
| 512 | B | 0.000178 | 0.190259 | 0.321570 | 0.318920 |
| 1024 | A1 | 0.000137 | 0.089858 | 0.255237 | 0.255772 |
| 1024 | A2 | 0.000137 | 0.089858 | 0.255237 | 0.255772 |
| 1024 | B | 0.000061 | 0.154738 | 0.271795 | 0.271066 |

A1 and A2 are identical at N = 1024 (same master pool).

## 6. Marginal coverage

Per-dimension min/max span `[0,1]` well for all schemes. Difference is bin balance
(10 bins/dim, 60 bins total):

| N | A1 empty/worst | A2 empty/worst | B empty/worst |
|---|---|---|---|
| 64 | 0/60, worst 1 | 1/60, worst 0 | 0/60, worst 5 |
| 128 | 0/60, worst 6 | 0/60, worst 3 | 0/60, worst 12 |
| 256 | 0/60, worst 15 | 0/60, worst 11 | 0/60, worst 24 |
| 512 | 0/60, worst 39 | 0/60, worst 37 | 0/60, worst 50 |
| 1024 | 0/60, worst 101 | 0/60, worst 101 | 0/60, worst 101 |

`worst` = least-populated bin count over all dims. B has the most balanced marginal
occupancy; A1 is least balanced at small N; A2 shows one empty bin at N = 64.

## 7. Nested check

Verification of `D64 ⊂ D128 ⊂ D256 ⊂ D512 ⊂ D1024` (exact float containment):
all four boundary checks PASS for **A1, A2 and B**.

## 8. Technical interpretation

### A1
Advantages:
- legacy continuity;
- simple;
- reproducible;
- nested after a fixed master ordering.

Disadvantages:
- smaller prefixes inherit poor LHS-prefix uniformity.

### A2
Advantages:
- strong point separation;
- deterministic;
- nested.

Disadvantages:
- a spacing objective does not imply low discrepancy;
- in the current 6D benchmark overall uniformity WORSENS (higher CD, weaker
  marginal balance);
- a DOE should not be chosen on minimum pairwise distance alone.

### B
Advantages:
- lowest discrepancy at every tested N;
- strongest marginal balance;
- naturally nested sequence;
- well suited to a power-of-two ladder.

Risks / obligations (all resolved — see section 12):
- DOE family differs from the legacy LHS (accepted);
- explicit scientific approval — **received**;
- production implementation must freeze the seed, the SciPy environment and the
  generation procedure — seed recovered and frozen.

## 9. Final conclusion (FROZEN)

```text
A1 = BASELINE_ONLY
A2 = DEPRIORITIZED
B  = FINAL_PRODUCTION_DOE
FINAL_DOE = SCRAMBLED_SOBOL
```

See section 12 for the approved decision, the rationale and the frozen production
semantics.

## 10. Open decisions

The former decision — whether to approve switching from the legacy LHS to scrambled
Sobol — is **CLOSED** by section 12. The legacy `1891` role is **CLOSED** by
section 14.

Still open:

1. The `N` values of the official scaling ladder (`FINAL_N_LADDER`).
   -> **CLOSED 2026-10-13**: `[1000, 2000, 5000, 10000, 20000, 35000, 50000, 70000, 100000]`.
2. The official training-scale maximum (`FINAL_N_TRAIN_MAX`, formerly the umbrella
   term `FINAL_NMAX`).
   -> **CLOSED 2026-10-13**: `100000` usable training cases, plus a fixed
      `FINAL_N_TEST = 20000` usable test set -> `MIN_USABLE_TRAIN_TEST_CASES = 120000`.
      `FINAL_RAW_CFD_ATTEMPTS` remains **PENDING**.
3. Whether a future, separately defined mixed/transfer experiment may use `1891`
   (it must not be silently mixed into the main scaling experiment).
4. Whether multiple independent repetitions of the DOE randomness are needed.
   (Recorded as a future decision only; no repetition experiment is designed here.)

## 11. Non-goals of this checkpoint

No `01_generate_design.py`, no `master_design.csv`, no official subsets, no new DOE
benchmark run, no final `N`/`Nmax` decision, no change to `ranges_legacy.yaml` or any
legacy file, no geometry or CFD work was produced by this checkpoint.

## 12. FINAL DOE DECISION (at the time: FROZEN — 6D 生产约束现为 HISTORICAL / SUPERSEDED)

```text
FINAL_DOE = SCRAMBLED_SOBOL          （DOE 方法决策，继续沿用）
status    = APPROVED / FINAL         （仅指 2026-10-13 的方法选择）
6D 生产 DOE 维度 / 单一 seed=1 序列   = HISTORICAL / SUPERSEDED（2026-10-23）
```

### Decision authority

```text
Decision authority: owner / human approval received
```

### Decision rationale

All three benchmarked schemes satisfy nested containment. **B** was selected because
it has:

```text
lowest centered discrepancy at every tested N
strongest marginal balance
naturally nested sequence
appropriate behaviour for scaling-law dataset growth
```

The benchmark `N` values `64, 128, 256, 512, 1024` remain **DOE-method comparison
values only**; they are NOT promoted to `FINAL_N_LADDER`.

### Project scale context (owner decision context)

```text
The new project is expected to expand to O(10^4)–O(10^5)
CFD cases rather than remain near the historical 1891-case scale.
```

Therefore:

```text
legacy DOE-family continuity is not a priority criterion
for selecting the new production DOE.
```

`FINAL_NMAX` and `FINAL_N_LADDER` were still **PENDING** at the time of this DOE
decision. Current status (2026-10-13): `FINAL_N_TRAIN_MAX`, `FINAL_N_TEST` and
`FINAL_N_LADDER` are **FROZEN** (see `docs/DESIGN_FREEZE_2026-10-13.md`);
`FINAL_RAW_CFD_ATTEMPTS` remains **PENDING**.

## 13. Production DOE semantics (frozen principles)

```text
one Sobol master sequence
generated once
fixed seed
fixed SciPy version / procedure
native Sobol sequence order retained
```

Forbidden:

```text
independent Sobol redraw for each N
sorting / reordering Sobol points
greedy maximin reorder
mixing LHS and Sobol points inside one production master sequence
```

Nested dataset definition:

```text
D_N = first N cases of the frozen production master sequence
```

### Seed provenance (verified from a committed source, not inferred)

```text
SOBOL_SEED = 1
source     : analysis/doe_compare_benchmark.py  (line 44)
             sob = qmc.Sobol(d=D, scramble=True, seed=1)
             (line 45: B = sob.random_base2(10))
sha256     : e0329ad432efd6a3f73f77fd8c4afc7683013e1d9c45980a4ebbc9d80d667bba
git        : analysis/doe_compare_benchmark.py  (committed in ebbf7bd)
```

The seed is the one actually used by the benchmark whose recorded results produced
this decision; it was **not** inferred from the legacy LHS `seed = 1`.

### random_base2 policy

Sobol balance guarantees are strongest at power-of-two sample counts. Production
should use:

```python
qmc.Sobol(d=6, scramble=True, seed=SOBOL_SEED)
```

and generate one canonical master sequence with:

```python
random_base2(m)      # 2^m >= required production master-pool size
```

keeping production case order in the native Sobol sequence order.

If a future `FINAL_N_LADDER` contains non-`2^k` values, the first `N` cases of the
same master sequence may still be used and remain nested, but the documentation must
state:

```text
the strongest Sobol balance properties apply at power-of-two boundaries
```

Choosing the official `N` ladder therefore remains an independent decision.

### Parameter order (frozen)

```text
0 Xthick
1 Tmax
2 Metal2
3 Solidity
4 Incidence
5 Mach
```

A normalized Sobol point `u ∈ [0,1)^6` maps to the frozen core ranges in
`config/ranges_legacy.yaml`. Those ranges are **not** modified by this decision.

### Identity direction for the future 01_generate_design.py

```text
range_id    = legacy/core frozen range identifier   (existing naming, unchanged)
sampling_id = sobol_scrambled_v1                    (suggested; no existing conflict)
```

## 14. Legacy 1891 final role (FROZEN)

```text
LEGACY_1891_ROLE = HISTORICAL_REFERENCE_AND_REGRESSION_ONLY
```

```text
DO NOT merge legacy 1891 cases into the new Sobol master pool.
DO NOT treat legacy 1891 cases as prefixes/subsets of the new DOE.
DO NOT preserve LHS solely for compatibility with the old 1891 experiment.
```

Still permitted:

```text
historical reference
legacy regression
Golden Case source
legacy performance comparison
```

But by default:

```text
NOT part of the new production training pool
```

A future transfer / mixed-dataset experiment must open its own experiment definition;
it MUST NOT be silently mixed into the main scaling experiment.

## 15. A1 / A2 final roles (FROZEN)

```text
A1 Master optimized LHS + raw prefix      STATUS = BASELINE_ONLY
A2 Master LHS + greedy maximin ordering   STATUS = DEPRIORITIZED
```

A1 `BASELINE_ONLY` means:

```text
kept as the DOE benchmark / methodology baseline
existing comparison results retained
NOT the production main DOE
no requirement to produce production CFD data at the Sobol scale
may be used later for a separate DOE sensitivity study
MUST NOT be mixed into one master pool with the production Sobol sequence
```

A2 does not enter the production main DOE.

## 16. NEXT DECISION

### Status at the time of this DOE decision (historical)

At the time of the FINAL_DOE decision the production scale was intentionally not
frozen:

```text
FINAL_NMAX and FINAL_N_LADDER were intentionally not frozen yet.
```

They required owner / research-group discussion because the intended production scale
is:

```text
O(10^4)–O(10^5) CFD cases
```

The historical benchmark sizes

```text
64 / 128 / 256 / 512 / 1024
```

remain **DOE-method comparison values** and are still NOT the production ladder.

### Status recorded on 2026-10-13 — 现为 `HISTORICAL / SUPERSEDED`（规划约束）

See `docs/DESIGN_FREEZE_2026-10-13.md`（原文保留）与
`docs/PROJECT_TRANSITION_PLAN.md`（当前规划）:

```text
N definition                = usable training case count          RETAINED
FINAL_N_TRAIN_MAX           = 100000 usable training cases        参考值（非冻结）
FINAL_N_TEST                = 20000 usable test cases (fixed)     参考值（非冻结）
TRAIN_TEST_RATIO            = 5:1                                 参考值
MIN_USABLE_TRAIN_TEST_CASES = 120000                              参考值
FINAL_N_LADDER              = 1000 2000 5000 10000 20000 35000 50000 70000 100000
                                                                  候选梯度（非强制）
```

```text
当前状态（2026-10-28，见 PROJECT_TRANSITION_PLAN.md）:
  Train 150000 候选（seed 101）-> 目标有效 100000（PROPOSED）
  Validation 15000 候选（seed 202）-> 目标有效 10000（PROPOSED）
  Test 30000 候选（seed 303）-> 目标有效 20000（PROPOSED）
  195000 个候选几何已生成并通过文件级检查；有效 CFD 数仍为 0
```

The umbrella term `FINAL_NMAX` is retired for current status; it must not be used to
mean training `N_max`, usable total, or raw CFD attempts.

Still **PENDING** (not decided by an AI agent; CFD 侧主导):

```text
FINAL_VALIDATION_POLICY
FINAL_N_VALIDATION
FINAL_PRODUCTION_RANGES
FINAL_RAW_CFD_ATTEMPTS
```

This document (DOE_DECISION) still fixes no six-dimensional parameter range; the
production ranges remain owned by the owner / advisor.

