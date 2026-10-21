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
                                legacy ranges; historical stage, FROZEN RECORD)
Geometry Range Review V2        DONE / HISTORICAL (40 cases, C810001..C810040,
                                exploratory ranges, NOT production)
V2 Geometry QC                  40/40 PASS       (geometry_qc_v1_hard)
V2 senior review package        DELIVERED        (no advisor acceptance recorded:
                                human_acceptance / human_comment still empty)

Parameter sensitivity 100 cases DONE / EXPLORATORY (C820001..C820100; 100/100
                                generated, 100/100 hard QC; 13-parameter scan +
                                boundary check; newest sensitivity scan)
Ks1/Ks2 dedicated review 57     DONE / EXPLORATORY (C830001..C830057; 57/57)
Geometry final decision V1      DONE / EXPLORATORY FINAL (C840001..C840040 new +
                                9 reused = 49 rows; 11 geometry dimensions KEEP)
SS1 / SS2                       3.2 / 0.8 FIXED_BY_REVIEW (human decision made
                                AFTER the 100-case scan; that scan DID vary them)
FINAL_PRODUCTION_RANGES         STILL PENDING   <- main blocker (the exploratory
                                geometry config is NOT a production approval)

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

## GEOMETRY RANGE REVIEW — V1 (archived) / V2 (historical)

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

Full session record: `docs/SESSION_DELIVERY_2026-10-15.md` (V1/V2 stage).

## GEOMETRY PARAMETER RESEARCH (2026-10-17 — EXPLORATORY, NOT PRODUCTION)

```text
Chain (each step has its own disjoint case-number block):

1) 100-case sensitivity + boundary check   analysis/geometry_review/parameter_sensitivity_v1_100cases/
   case_id C820001..C820100
   S1=60 single-factor, S2=20 2x2 coupling, S3=20 adaptive anchor/variant
   100/100 generated, 100/100 hard QC PASS, 100/100 frozen QC PASS
   overview_001_050.png + overview_051_100.png  (two 50-panel overviews)
   case_design.csv (100 rows, parameters) / case_metrics.csv (100 rows, geometry metrics)
   automatic screening (NOT a freeze):
       FIX_CANDIDATE  2  -> SS1, SS2
       KEEP_CANDIDATE 10 -> Xthick Tmax Metal2 Solidity Metal1 T1 T2 Xmean K_m Ks1
       REVIEW         1  -> Ks2
   IMPORTANT: SS1 2.4-4.0 and SS2 0.5-1.1 were VARIABLES in this scan.
              The current freeze (3.2 / 0.8) happened later; do not rewrite
              the historical scan as if SS1/SS2 had always been fixed.

2) 57-case Ks1/Ks2 dedicated review        analysis/geometry_review/ks1_ks2_review_v1/
   case_id C830001..C830057, 57/57 generated + hard QC + frozen QC PASS
   SS1 = 3.2 / SS2 = 0.8 FIXED_BY_REVIEW in every case (human decision)
   Ks1 / Ks2 at that stage: FURTHER_REVIEW

3) Geometry parameter final decision V1    analysis/geometry_review/parameter_final_decision_v1/
   new cases C840001..C840040 (49 design rows incl. 9 reused), 49/49 PASS
   authority: final_geometry_parameters.yaml + FINAL_DECISION.md
   geometry_dimension = 11, operating_dimension = 2, total_candidate_dimension = 13
   KEEP: Xthick 0.10-0.60, Tmax 0.025-0.095, Metal2 0-32 deg, Solidity 0.7-2.5,
         Metal1 48-58 deg, T1 0.010-0.018, T2 0.008-0.016, Xmean 0.06-0.18,
         K_m 0.10-0.35, Ks1 3.0-7.0, Ks2 0.05-0.20
   FIX : SS1 = 3.2, SS2 = 0.8 (FIXED_BY_REVIEW / HUMAN_REVIEW_DECISION)
   joint constraint JC_XMEAN_KS1_KM (K_m >= 0.15 for 0.18 < Xmean <= 0.20)
       recorded but NOT active at the final bound (upper bound stays 0.18)

Current parameter status for further parametric work:
    11 geometry parameters OPEN (ranges above)
    SS1 = 3.2, SS2 = 0.8 FIXED
    Incidence, Mach = operating conditions (fixed 0 deg / 0.5 in these experiments;
    they do not change the blade geometry; CFX implementation still TBD)

Code evidence for the fixed values (verified 2026-10-21):
    code/geometry_legacy_v1.py:44-45                     SS1 = 3.2, SS2 = 0.8
    code/geometry_parametric_exploratory_v1.py:73-74     defaults SS1/SS2 = 3.2/0.8
    tools/geometry_final_decision_v1.py:86               FIXED = {SS1: 3.2, SS2: 0.8}
    tools/geometry_ks1_ks2_review_v1.py:75               FIXED = {SS1: 3.2, SS2: 0.8}

WARNING — do not overclaim:
    "FINAL" above means FINAL ONLY for the EXPLORATORY geometry DOE.
    It is NOT a production range, NOT a CFD certification.
    No NUMECA / CFX run, no formal DOE, no production design has been executed.
    Explicitly still required before production:
        - CFD verification of the high-Xmean / high-Ks1 corner
        - CFD verification of the Ks2 rear-camber control range
        - threshold calibration on the historical 1891-sample population
        - real implementation of the joint constraint inside the DOE sampler
```

Full session record: `docs/SESSION_DELIVERY_2026-10-17.md`.
Regression status at this documentation sync (2026-10-21):
`conda run -n ai4s python -m pytest -q` -> 131 passed, 17 subtests passed.

## NEXT HUMAN DECISION — HIGHEST PRIORITY

```text
Before implementing code/01_generate_design.py,
the project must first freeze the six-dimensional production ranges:

1. FINAL_PRODUCTION_RANGES   (owner / advisor confirmation)
```

The advisor input for that decision is now two packages:

```text
1. analysis/geometry_review/parameter_final_decision_v1/FINAL_DECISION.md
   (candidate 13-parameter space, SS1/SS2 fixed, Xmean upper bound 0.18)
2. analysis/geometry_review/senior_review_v2/  (40 real V2 blades, historical stage)
```

Neither the V2 shapes nor the C820/C830/C840 shapes have a recorded advisor
acceptance yet (`human_acceptance` / `human_comment` are empty). Until the advisor
has judged them and the CFD / threshold-calibration items above are answered,
no production range may be frozen. `FINAL_PRODUCTION_RANGES` stays PENDING.

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
Read the geometry parameter research chain, then get the advisor's engineering
judgement on the candidate geometry space and use it to freeze
FINAL_PRODUCTION_RANGES (six-dimensional production parameter ranges).

Read in this order:
  1. docs/SESSION_DELIVERY_2026-10-17.md        (100-case scan -> 57-case review
                                                 -> final decision, SS1/SS2 freeze)
  2. analysis/geometry_review/parameter_final_decision_v1/FINAL_DECISION.md
     (candidate 13-parameter space; geometry_dimension = 11)
  3. analysis/geometry_review/parameter_sensitivity_v1_100cases/README.md
     + REPORT.md                                (100 real blades, C820001..C820100)
  4. analysis/geometry_review/senior_review_v2/ (40 real V2 blades, historical stage)

DO NOT start 01_generate_design.py before those ranges are frozen.
Do not treat the exploratory candidate ranges as approved production ranges.
Do not re-open SS1 = 3.2 / SS2 = 0.8 without an explicit human decision.
Do not rewrite history: the 100-case scan DID vary SS1 (2.4-4.0) and SS2 (0.5-1.1);
they were frozen afterwards.

Production scale itself is already FROZEN (2026-10-13):
see docs/DESIGN_FREEZE_2026-10-13.md.
Geometry review V1/V2 status: docs/SESSION_DELIVERY_2026-10-15.md.
Geometry parameter research status: docs/SESSION_DELIVERY_2026-10-17.md.
```

For a new AI conversation, upload first:

```text
1. PROJECT_HANDOFF.md
2. AGENT_INSTRUCTION.md
3. README.md                              (repository entry point)
4. docs/DOE_DECISION.md
5. docs/SCALING_EXPERIMENT_DESIGN.md
6. docs/SESSION_DELIVERY_2026-10-11.md   (historical record)
7. docs/DESIGN_FREEZE_2026-10-13.md      (current production-scale freeze)
8. docs/SESSION_DELIVERY_2026-10-15.md   (geometry range review V1/V2 + review package)
9. docs/SESSION_DELIVERY_2026-10-17.md   (100-case sensitivity + Ks1/Ks2 review +
                                          geometry parameter final decision)
```

When continuing geometry work, also provide:

```text
10. docs/GEOMETRY_GENERATOR_CONTRACT.md
11. docs/GEOMETRY_QC_CONTRACT.md
12. analysis/geometry_review/README.md                  (review dir entry point)
13. analysis/geometry_review/parameter_sensitivity_v1_100cases/README.md + REPORT.md
14. analysis/geometry_review/parameter_sensitivity_v1_100cases/parameter_decisions.csv
15. analysis/geometry_review/parameter_final_decision_v1/FINAL_DECISION.md
16. analysis/geometry_review/senior_review_v2/README.md (40-case review package)
```

Only when a legacy audit is actually needed, also provide:

```text
legacy/blade_batch_generation.py
legacy/blade_batch_generation_template.geomTurbo
config/ranges_legacy.yaml
```
