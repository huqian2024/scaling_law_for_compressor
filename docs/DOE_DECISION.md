# DOE Decision Memo

> Status: living document. This memo records **scientific evidence and open questions**.
> It does **NOT** declare a final production DOE.

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
- Status: `BASELINE`.

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
- Status: `LEADING_CANDIDATE — REQUIRES SUPERVISOR APPROVAL`.

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

Risks:
- DOE family differs from the legacy LHS;
- requires explicit scientific approval;
- production implementation must freeze the seed, the SciPy environment and the
  generation procedure.

## 9. Current conclusion

```text
A1 = conservative baseline
A2 = deprioritized after benchmark
B  = leading candidate
```

This memo explicitly does **NOT** state `FINAL DOE = Sobol`. The final scientific
choice has not yet received human confirmation.

## 10. Open decisions

1. Whether to approve switching from the legacy LHS to scrambled Sobol.
2. The `N` values of the official scaling ladder.
3. The official `Nmax`.
4. Whether the legacy `1891` dataset is used only for baseline/regression or may
   enter the future training set.
5. Whether multiple independent repetitions of the DOE randomness are needed.
   (Recorded as a future decision only; no repetition experiment is designed here.)

## 11. Non-goals of this checkpoint

No `01_generate_design.py`, no `master_design.csv`, no official subsets, no new DOE
benchmark run, no final `N`/`Nmax` decision, no change to `ranges_legacy.yaml` or any
legacy file, no geometry or CFD work was produced by this checkpoint.

