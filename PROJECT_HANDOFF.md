# PROJECT_HANDOFF

## PROJECT

Two-dimensional compressor cascade AI4S CFD data-generation and scaling-law project.

Research target:

```text
E = f(N, P)
```

Current phase: build a **reliable data-generation and canonical-dataset pipeline** only.
No model training in this phase.

## CURRENT_STATUS

```text
Repository baseline             PASS
Legacy preservation             PASS
Legacy audit                    PASS
Environment freeze              PASS
Legacy range freeze             PASS

DOE design review               PASS
DOE benchmark                   PASS
DOE decision                    PASS / FROZEN
Scaling statistical design      PASS

FINAL_DOE                       SCRAMBLED_SOBOL — APPROVED / FINAL
SOBOL_SEED                      1

Design freeze (2026-10-13)      PASS / FROZEN
N definition                    N = usable training case count
FINAL_N_TRAIN_MAX               100000 usable training cases
FINAL_N_TEST                    20000 usable test cases (fixed)
TRAIN_TEST_RATIO                5:1
MIN_USABLE_TRAIN_TEST_CASES     120000
FINAL_N_LADDER                  1000 2000 5000 10000 20000 35000 50000 70000 100000
SOBOL_MASTER_M                  m >= 17 (lower bound only; FINAL m PENDING)
GEOMETRY_REUSE                  DISABLED / NOT ACTIVE
PRODUCTION_ROUTE                ONE_6D_POINT_ONE_CASE
FINAL_VALIDATION_POLICY         PENDING
FINAL_N_VALIDATION              PENDING
FINAL_PRODUCTION_RANGES         PENDING   <- main blocker
FINAL_RAW_CFD_ATTEMPTS          PENDING
FAILURE_RESERVE_POLICY          PENDING

Geometry regression fixtures    PASS
Geometry generator contract     PASS
02_generate_geometry.py         PASS
Geometry QC contract            PASS
03_geometry_qc.py               PASS
Local geometry pipeline         PASS

Geometry Range Review V1        DONE / ARCHIVED  (30 cases, C800001..C800030,
                                legacy ranges; FROZEN RECORD)
Geometry Range Review V2        DONE             (40 cases, C810001..C810040,
                                exploratory ranges, NOT production)
V2 Geometry QC                  40/40 PASS       (geometry_qc_v1_hard)
V2 senior review package        DELIVERED        (awaiting advisor judgement;
                                entrance = the 40-panel overview)

01_generate_design.py           PREPARED / NOT EXECUTED / BLOCKED
generate_geomturbo_batch.py     PREPARED / NOT EXECUTED / BLOCKED
DO-NOT-RUN                      no production design / geometry generation
                                until FINAL_PRODUCTION_RANGES is frozen
NUMECA bring-up C900001         KEPT (bring-up only; never in the
                                production case sequence)
NUMECA / CFX / HPC              NOT STARTED
```

## CONFIRMED FACTS

```text
Conda environment = ai4s
Python = 3.10.20

Legacy DOE:
LatinHypercube
d = 6
optimization = random-cd
seed = 1
historical N = 1891
```

`1891` is the historical experiment size and is **NOT** the target size of the new
project.

Legacy `1891` role (frozen): historical reference / regression / Golden-Case source
only — **NOT** part of the new production Sobol pool.

```text
Geometry = f(Xthick, Tmax, Metal2, Solidity)
OperatingCondition = f(Incidence, Mach)
```

The CFX implementation of `Incidence` / `Mach` is still **TBD**; guessing is
forbidden.

## DOE STATUS

```text
FINAL_DOE = SCRAMBLED_SOBOL — APPROVED
  method   = scipy.stats.qmc.Sobol
  d        = 6
  scramble = True
  seed     = 1     (verified: analysis/doe_compare_benchmark.py line 44)
  ordering = native Sobol sequence order
  nesting  = prefix nesting (D_N = first N of the frozen master sequence)

A1 Master LHS + raw prefix
STATUS = BASELINE_ONLY

A2 Master LHS + greedy maximin ordering
STATUS = DEPRIORITIZED

B Scrambled Sobol
STATUS = FINAL_PRODUCTION_DOE
```

Legacy:

```text
historical 1891 =
  reference / regression / Golden-Case source only;
  NOT part of the new production Sobol pool
```

Parameter order (frozen):

```text
0 Xthick
1 Tmax
2 Metal2
3 Solidity
4 Incidence
5 Mach
```

Production principles (frozen):

```text
one fixed master Sobol sequence
generated once
D_N = first N points
no independent redraw per N
no sorting / reordering
no LHS / Sobol mixing in the main production pool
```

References:

- `docs/DOE_DECISION.md`
- `docs/SCALING_EXPERIMENT_DESIGN.md`

## PRODUCTION SCALE (FROZEN 2026-10-13)

```text
N = usable training case count
    (test / validation / failed / rejected cases are NOT counted)
```

```text
FINAL_N_TRAIN_MAX           = 100000 usable training cases
FINAL_N_TEST                = 20000 usable test cases (fixed)
TRAIN_TEST_RATIO            = 5:1
MIN_USABLE_TRAIN_TEST_CASES = 120000
FINAL_N_LADDER              = 1000 2000 5000 10000 20000 35000 50000 70000 100000
```

```text
FINAL_RAW_CFD_ATTEMPTS = PENDING
  (> 120000; exact value needs a real NUMECA/CFX failure rate first)
FAILURE_RESERVE_POLICY = PENDING
```

The retired umbrella term `FINAL_NMAX` must no longer be used for current status,
because it conflates training `N_max`, usable total and raw CFD attempts.
Full freeze record: `docs/DESIGN_FREEZE_2026-10-13.md`.

## PREPARED PRODUCTION PIPELINE (2026-10-13 — PREPARED, NOT EXECUTED)

```text
code/01_generate_design.py        PREPARED / NOT EXECUTED
code/generate_geomturbo_batch.py  PREPARED / NOT EXECUTED
```

One command (single entry point; **DO NOT RUN** yet):

```bash
conda run -n ai4s python code/generate_geomturbo_batch.py \
  --ranges config/ranges_legacy.yaml \
  --n-train 100000 \
  --n-test 20000 \
  --qc-output geometry/geometry_qc_production.csv
```

Pipeline:

```text
Sobol design generation
  -> fixed train/test assignment
  -> master_design.csv
  -> profile generation
  -> .geomTurbo generation
  -> Geometry QC
```

```text
ranges are RUNTIME CONFIGURABLE (--ranges PATH)
legacy ranges are NOT the final production ranges
after the owner confirms the ranges, ONLY this argument changes:

  --ranges config/ranges_production_v1.yaml

(no generator code change required)

production QC output path = geometry/geometry_qc_production.csv
  kept separate from the bring-up report geometry/geometry_qc.csv
```

Bring-up provenance (IMMUTABLE — never part of the production case sequence):

```text
C900001 = bring-up only
design/bringup/                        (tracked)
docs/NUMECA_BRINGUP_CASE_C900001.md    (tracked; records SHA256)
geometry/profiles/C900001.dat          (local artifact, kept)
geometry/geomturbo/C900001.geomTurbo   (local artifact, kept)
geometry/geometry_qc.csv               (local bring-up report, kept)
```

Do not delete or overwrite any of the above.

The three `local artifact` paths above are deliberately **NOT tracked by git**
(the rules are written with comments at the end of `.gitignore`): they stay on
this laptop, and `docs/NUMECA_BRINGUP_CASE_C900001.md` records their SHA256.

## GEOMETRY RANGE REVIEW — V1 (archived) / V2 (current)

```text
V1  legacy range review     30 cases  C800001..C800030   generation 30/30, QC 30/30 PASS
    archive (FROZEN RECORD, do not edit):
        analysis/geometry_review/archive/v1_legacy_review/
    known gap recorded there: the V1 plotting script was overwritten by the V2
    rewrite while untracked, so it is not recoverable from git; all V1 figures,
    tables, QC report and logs ARE archived.

V2  exploratory range review 40 cases C810001..C810040  generation 40/40, QC 40/40 PASS
    ranges    : analysis/geometry_review/ranges_exploratory_v2.yaml
                (status EXPLORATORY_NOT_APPROVED — never written into config/)
                Xthick 0.10-0.60, Tmax 0.025-0.095, Metal2 0-32 deg,
                Solidity 0.7-2.5, Incidence 0 (fixed), Mach 0.5 (fixed)
    results   : analysis/geometry_review/geometry/            (40 .dat + .geomTurbo)
                analysis/geometry_review/geometry_qc.csv      (40 rows, all PASS)
                analysis/geometry_review/figures/             (6 PNG @200 dpi)
    deliverable: analysis/geometry_review/senior_review_v2/   (40-case review package)
                 analysis/geometry_review/senior_review_v2.zip (local delivery copy only)
    independent facts: min_gap 0.014494..0.072696 m (hard gate > 0, all pass);
                 envelope_clearance negative for 5 cases (diagnostic only, NOT a
                 collision and NOT a QC failure); 25 unique blade outlines
                 (40 cases = 25 blades + 15 pitch-only variants)

Frozen core NOT touched by any of this:
    code/geometry_legacy_v1.py (Metal1 = 53 deg), legacy/, config/ranges_legacy.yaml,
    tests/ + tests/fixtures/, docs/GEOMETRY_GENERATOR_CONTRACT.md, GEOMETRY_QC_CONTRACT.md

WARNING — do not overclaim:
    Geometry QC PASS  !=  aerodynamically reasonable
    Geometry QC PASS  !=  mesh / CFD feasible
    the V2 exploratory ranges are NOT the approved production ranges
    no formal DOE and no CFD production has been executed
```

Full session record: `docs/SESSION_DELIVERY_2026-10-15.md`.

## NEXT HUMAN DECISION — HIGHEST PRIORITY

```text
Before implementing code/01_generate_design.py,
the project must first freeze the six-dimensional production ranges:

1. FINAL_PRODUCTION_RANGES   (owner / advisor confirmation)
```

The advisor input for that decision is the V2 senior review package
(`analysis/geometry_review/senior_review_v2/`, 40 real blades).
Until the advisor has judged those shapes, no range may be frozen.

and, independently:

```text
2. FINAL_VALIDATION_POLICY / FINAL_N_VALIDATION
3. FINAL_RAW_CFD_ATTEMPTS   (after a real NUMECA/CFX failure-rate stress test)
```

The exact values MUST NOT be decided by an AI agent.

## NEXT ENGINEERING TASK

```text
FREEZE FINAL_PRODUCTION_RANGES first, then define the
01_generate_design.py production contract.

Do not implement 01_generate_design.py before those ranges are frozen.
```

## OPEN HUMAN DECISIONS

Closed:

- FINAL_DOE (scrambled Sobol — approved)
- legacy 1891 future role (historical reference / regression / Golden-Case only)
- production scale (2026-10-13): FINAL_N_TRAIN_MAX / FINAL_N_TEST / TRAIN_TEST_RATIO
  / MIN_USABLE_TRAIN_TEST_CASES / FINAL_N_LADDER
- geometry reuse (DISABLED / NOT ACTIVE; PRODUCTION_ROUTE = ONE_6D_POINT_ONE_CASE)

Still open:

- FINAL_PRODUCTION_RANGES (six-dimensional production parameter ranges)
- FINAL_VALIDATION_POLICY / FINAL_N_VALIDATION
- FINAL_RAW_CFD_ATTEMPTS (raw CFD attempts / failure reserve)
- training repetition design
- final `E` definition
- model-size `P` grids

## BLOCKED EXTERNAL INFORMATION

Golden Case / NUMECA / CFX / HPC details are still pending confirmation at the
school environment.

## NEW CHAT START HERE

```text
FIRST TASK:
Get the advisor's engineering judgement on the 40 real V2 blade shapes
(analysis/geometry_review/senior_review_v2/) and use that feedback to freeze
FINAL_PRODUCTION_RANGES (six-dimensional production parameter ranges).

DO NOT start 01_generate_design.py before those ranges are frozen.
Do not treat the V2 exploratory ranges as approved production ranges.

Production scale itself is already FROZEN (2026-10-13):
see docs/DESIGN_FREEZE_2026-10-13.md.
The geometry range review status is recorded in docs/SESSION_DELIVERY_2026-10-15.md.
```

For a new AI conversation, upload first:

```text
1. PROJECT_HANDOFF.md
2. AGENT_INSTRUCTION.md
3. docs/DOE_DECISION.md
4. docs/SCALING_EXPERIMENT_DESIGN.md
5. docs/SESSION_DELIVERY_2026-10-11.md   (historical record)
6. docs/DESIGN_FREEZE_2026-10-13.md      (current production-scale freeze)
7. docs/SESSION_DELIVERY_2026-10-15.md   (geometry range review V1/V2 + review package)
```

When continuing geometry work, also provide:

```text
8. docs/GEOMETRY_GENERATOR_CONTRACT.md
9. docs/GEOMETRY_QC_CONTRACT.md
10. analysis/geometry_review/README.md                 (review dir entry point)
11. analysis/geometry_review/senior_review_v2/README.md (40-case review package)
```

Only when a legacy audit is actually needed, also provide:

```text
legacy/blade_batch_generation.py
legacy/blade_batch_generation_template.geomTurbo
config/ranges_legacy.yaml
```
