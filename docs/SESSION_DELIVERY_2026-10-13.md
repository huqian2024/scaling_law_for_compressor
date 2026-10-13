# AI4S Compressor CFD Project — Session Delivery
Date: 2026-10-13

> This is the delivery record for the 2026-10-13 session. It complements, and does
> not replace, `PROJECT_HANDOFF.md`.
>
> Scope of this session: **design freeze + code preparation + git closeout.**
> **No production data was generated.** No NUMECA / CFX / solver was started.

## 1. Executive Summary

```text
A. Scaling-law data scale                              FROZEN
B. Fixed 20000-case test set                           FROZEN
C. 9-level nested FINAL_N_LADDER                        FROZEN
D. Scrambled Sobol production DOE contract             UNCHANGED / FROZEN
E. Production route (one 6D point -> one case)          FROZEN
F. Production pipeline code                            PREPARED / NOT EXECUTED
G. NUMECA bring-up case C900001                        DELIVERED (bring-up only)
```

Consequence:

```text
The next blocker is NOT geometry, NOT DOE-family selection, NOT code.

The next blocker is FINAL_PRODUCTION_RANGES (owner / advisor confirmation).
Until then the prepared pipeline stays DO-NOT-RUN.
```

## 2. Scaling-Law `N` Definition (FROZEN)

```text
N = usable training case count
```

```text
only CFD cases actually usable for model training are counted
test cases                       NOT counted
validation cases (if added)      NOT counted
failed / rejected / non-usable   NOT counted
```

The published data scaling law uses:

```text
E = E(N)
```

## 3. Training Scale and Fixed Test Set (FROZEN)

```text
FINAL_N_TRAIN_MAX           = 100000 usable training cases
FINAL_N_TEST                = 20000 usable test cases
TRAIN_TEST_RATIO            = 5:1
MIN_USABLE_TRAIN_TEST_CASES = 120000
```

Fixed test set rules:

```text
training pool and test set are completely disjoint
the test set is fixed once and stays fixed
all training tiers use the same test set
PCA + MLP / U-Net / FNO use the same test set
the test set never participates in training
the test set is NOT counted in N
```

Case-ID convention for the current 120000-case request:

```text
C000001 ... C100000  -> train
C100001 ... C120000  -> test
```

## 4. FINAL_N_LADDER (FROZEN, strictly nested)

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

All three model families use exactly this ladder.

## 5. Production DOE Contract (UNCHANGED / already frozen)

```text
method   = scipy.stats.qmc.Sobol
d        = 6
scramble = True
seed     = 1
ordering = native Sobol sequence order
nesting  = prefix nesting
```

```text
0 Xthick
1 Tmax
2 Metal2
3 Solidity
4 Incidence
5 Mach
```

```text
D_N = first N requested cases of the same frozen master Sobol sequence
```

Forbidden: independent redraw per `N`, sorting/reordering, LHS mixing, a separate
DOE per `N`.

## 6. Sobol Master Sequence Length Policy (dynamic `m`)

```text
m = smallest integer such that 2^m >= required raw design-pool size
```

```text
current lower bound: m >= 17
because 2^17 = 131072 > MIN_USABLE_TRAIN_TEST_CASES = 120000
```

```text
FINAL m = PENDING (NOT frozen)
reasons: FINAL_RAW_CFD_ATTEMPTS PENDING
         failure reserve PENDING
         validation policy / size PENDING
```

`m` is computed at runtime from the requested counts; it is not hard-coded.

## 7. Production Route (FROZEN)

```text
one 6D point
  -> one case
  -> one case-specific geometry
  -> one .geomTurbo
  -> one NUMECA mesh
  -> one CFD case
```

```text
GEOMETRY_REUSE   = DISABLED / NOT ACTIVE
PRODUCTION_ROUTE = ONE_6D_POINT_ONE_CASE
```

```text
Geometry           = f(Xthick, Tmax, Metal2, Solidity)
OperatingCondition = f(Incidence, Mach)
```

`Incidence` / `Mach` remain in the case design but never enter geometry.

## 8. Production Pipeline Code (PREPARED / NOT EXECUTED)

```text
code/01_generate_design.py        PREPARED / NOT EXECUTED
code/generate_geomturbo_batch.py  PREPARED / NOT EXECUTED
```

`code/01_generate_design.py` strictly:

```text
read ranges YAML
  -> generate the frozen Sobol master points
  -> scale 6 dimensions into the physical ranges
  -> assign case_id
  -> write master_design.csv
  -> write the fixed train/test split metadata
```

`code/generate_geomturbo_batch.py` is orchestration only (child processes, no
geometry mathematics copied):

```text
1. design stage        -> code/01_generate_design.py
2. geometry stage      -> code/02_generate_geometry.py
3. Geometry QC stage   -> code/03_geometry_qc.py
```

```text
ranges are RUNTIME CONFIGURABLE (--ranges PATH)
legacy ranges are NOT the final production ranges
no range number is hard-coded in the new code
resume / idempotency: matching case -> skipped, missing -> generated,
                      conflicting -> reported, never silently deleted
streaming geometry generation (no 120000-case text batch held in RAM)
progress output: completed=/total created= skipped= conflict= failed=
```

## 9. One-Command Entry Point (DO NOT RUN YET)

```bash
conda run -n ai4s python code/generate_geomturbo_batch.py \
  --ranges config/ranges_legacy.yaml \
  --n-train 100000 \
  --n-test 20000 \
  --qc-output geometry/geometry_qc_production.csv
```

After the owner confirms the ranges, ONLY this argument changes:

```text
--ranges config/ranges_production_v1.yaml
```

No generator code change is required. The production QC report uses its own path
`geometry/geometry_qc_production.csv`, separate from the bring-up report.

## 10. NUMECA Bring-up Provenance (KEPT — do not delete/overwrite)

```text
C900001 = bring-up only, produced before this session's freeze
          must never enter the production case sequence
```

```text
design/bringup/                        (tracked)
docs/NUMECA_BRINGUP_CASE_C900001.md    (tracked; records the SHA256 values)
geometry/profiles/C900001.dat          (local artifact, kept)
geometry/geomturbo/C900001.geomTurbo   (local artifact, kept)
geometry/geometry_qc.csv               (local bring-up report, kept)
```

```text
template_sha256  = 92c4296f2de27440aebaad9b03b9af4f9e09756fabff2298f4607a87f2c55119
profile_sha256   = 2977f5798ab43aab527d06e9976be9177fd7a9a00325eb946273b8e2cb6874b9
geomturbo_sha256 = d8ae994dda268dbaaf5d68b4f8db982500132fd9d2441141c1306b8b4077bfb8
```

The bring-up itself passed the frozen geometry QC (`geometry_ok = 1`, reason `OK`).

## 11. What Was NOT Done (explicit)

```text
no production data generated
no master_design.csv
no Sobol points generated
no production profiles
no production .geomTurbo
no production geometry QC
no mesh
no NUMECA run
no CFX run
no CFD-Post run
no legacy/ modification
no frozen geometry generator / QC contract modification
no frozen DOE method / seed / order modification
no .gitignore modification
```

`code/01_generate_design.py` and `code/generate_geomturbo_batch.py` were syntax-checked
only (static parse). They have **never been executed**.

## 12. Still PENDING

```text
FINAL_PRODUCTION_RANGES     PENDING   <- main blocker
FINAL_VALIDATION_POLICY     PENDING
FINAL_N_VALIDATION          PENDING
FINAL_RAW_CFD_ATTEMPTS      PENDING
FAILURE_RESERVE_POLICY      PENDING
FINAL m (Sobol master sequence length)   PENDING (lower bound only: m >= 17)
```

Failure-reserve policy cannot be frozen until a real NUMECA/CFX stress test
provides an observed failure rate. It must not be guessed.

## 13. Next Session — Recommended First Action

```text
1. Receive the senior's / advisor's range decision.
2. Create and freeze config/ranges_production_v1.yaml.
3. Re-check that no legacy range is presented as a production range.
4. Only then run:
     conda run -n ai4s python code/generate_geomturbo_batch.py \
       --ranges config/ranges_production_v1.yaml \
       --n-train 100000 --n-test 20000 \
       --qc-output geometry/geometry_qc_production.csv
```

Recommended: run stage 1 alone first (design only), inspect `master_design.csv`
and the split CSV, and only then start the 120000-case geometry batch.

## 14. Do-Not-Guess / Do-Not-Change

```text
Do not invent FINAL_PRODUCTION_RANGES.
Do not invent the CFD failure reserve.
Do not invent FINAL m.
Do not modify files under legacy/.
Do not modify frozen geometry generator / QC contracts.
Do not change the frozen DOE method / seed / order.
Do not merge historical 1891 into the production Sobol pool.
Do not let bring-up case C900001 into the production sequence.
Do not delete or overwrite bring-up artifacts.
Do not run the production pipeline before the ranges are frozen.
```
