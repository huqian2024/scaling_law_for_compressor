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
C820 human engineering review   RECORDED 2026-10-21 (85 ACCEPT / 15 REJECT;
                                100/100 decided; per-case reject reasons still missing)
FINAL_PRODUCTION_RANGES         STILL PENDING   <- main blocker (the exploratory
                                geometry config is NOT a production approval)
Production DOE dimension        UNCHANGED: d = 6 (2026-10-13 freeze); the 13-dim
                                exploratory space is NOT a frozen production DOE
Human SHAPE acceptance        85/100 recorded (C820); NO mesh/CFD/aero acceptance
Geometry constraint proposal   A/B/C ANALYZED, PENDING owner decision
                                (final_geometry_parameters.yaml NOT modified)

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

## PARAMETER SPACE RECONCILIATION (2026-10-21)

Two different stages must not be conflated:

```text
Stage A — production DOE (frozen 2026-10-13)
    d = 6 : [Xthick, Tmax, Metal2, Solidity, Incidence, Mach]
    method/seed/order FROZEN; FINAL_PRODUCTION_RANGES still PENDING
    (legacy ranges only, NOT final production ranges)

Stage B — geometry parameter research (2026-10-17, exploratory)
    11 geometry parameters + 2 operating parameters (SS1/SS2 fixed)
    analysis only: NOT a production DOE, NOT approved ranges
```

```text
The 13-dim space is NOT "the production DOE frozen at 13 dims".
Whether the production DOE dimension changes is an owner decision (NOT taken here).
The 2026-10-13 freeze document is preserved unchanged.
"13" has two different meanings and must be written explicitly:
    (a) generator PARAM_NAMES = 13 shape parameters (includes SS1/SS2)
    (b) candidate DOF = 11 KEEP geometry + 2 operating = 13 (SS1/SS2 fixed)
```

Full comparison table, physical definitions, independence facts and the Metal1 /
Incidence distinction: `docs/PARAMETER_SPACE_RECONCILIATION.md`.

```text
Metal1      = inlet METAL angle (geometry)   legacy 48 + DeltaBeta(5) = 53 deg
Incidence   = inlet FLOW-angle operating variable; CFX implementation TBD
Verified    : changing only Incidence/Mach gives byte-identical .dat / .geomTurbo
Open        : legacy comment says 49 deg, code uses 53 deg (4 deg, unconfirmed)
```

Joint constraint status:

```text
JC_XMEAN_KS1_KM : K_m >= 0.15 for 0.18 < Xmean <= 0.20
current Xmean upper bound = 0.18  -> the interval is EMPTY -> cannot trigger
active_at_final_bound = false (kept)
=> recorded as a historical / inactive candidate, NOT a production hard constraint,
   NOT implemented in any sampler
```


## C820 HUMAN ENGINEERING REVIEW (2026-10-21)

```text
review file : analysis/geometry_review/parameter_sensitivity_v1_100cases/human_review_2026-10-21.csv
analysis    : analysis/geometry_review/parameter_sensitivity_v1_100cases/HUMAN_REVIEW_2026-10-21.md
rows        : 100 (case_design.csv order; 100 unique IDs)
REJECT      : 15  -> C820033 C820034 C820035 C820036 C820043 C820062
                     C820081 C820082 C820083 C820084
                     C820089 C820090 C820091 C820092 C820100
ACCEPT      : 85  (shape reasonable only; NOT mesh/CFD/aero acceptance)
ACCEPT      : 0
source      : senior engineer review (师兄), transcribed by the owner
comment     : pending (per-case reasons NOT provided; never invented)
```

```text
All 15 rejected cases are hard QC PASS and frozen QC PASS
=> the current automatic QC cannot detect this class of engineering problem.
Field separation: case_metrics.csv = geometry QC; human_review_*.csv = human label.
These labels DO NOT change any C830 / C840 historical decision.
```

Boundary findings (evidence-based, NOT decisions):

```text
supported single-parameter tightening candidates
    K_m upper bound (only at low Xmean ~ 0.08): 0.2012 ACCEPT,
        0.225 / 0.2667 / 0.3083 / 0.35 rejected consecutively -> candidate ~ 0.20
    Metal2 lower bound: Metal2 = 0 rejected; 21.33 / 32 / 15 ACCEPT
        -> lower bound must be > 0, exact value unknown

interaction-driven (do NOT turn into a simple hard bound yet)
    K_m x Xmean : 0.2875 rejected at Xmean 0.09, ACCEPT at 0.15;
                  0.3125 ACCEPT at Xmean 0.164
    S3 groups C820081-084 and C820089-092 : whole group rejected
        (all 4 variants) -> common background, not the varied parameter
    C820100 : only SS2 differs from its anchor C820097 (1.0742 -> 0.59),
        but SS2 = 0.59 is ACCEPT in another background and the S1 SS2
        sweep (0.5 / 0.9 / 1.1) is ACCEPT -> interaction, not a simple bound

insufficient evidence
    exact Metal2 lower bound, Solidity upper bound, SS2 low bound,
    exact K_m threshold, cause of the human rejection
```

```text
No data conflict with C830/C840: the 9 reused C840 cases
(C820027/028/029, C830026/027/028, C830031/032/033) contain none of the 15 rejects
(parameter vectors compared one by one).

But there IS a judgement-scope conflict (recorded, NOT rewritten):
    C830 has 9 cases in the same "low Xmean + high K_m" direction
        (Xmean=0.06, K_m=0.35: C830021-025, C830050-053), all geometry QC PASS,
        but never human-reviewed.
    C840's soft-risk audit located the max RCR 0.2529 at C830050 in that corner
        and kept it as "existing historical morphology", so K_m stayed KEEP
        0.10-0.35 (a numerical substitution result, NOT an engineering review).
    The 2026-10-21 human review rejects that direction at Xmean 0.08-0.09
        (C820033-036, C820062).
=> keep the historical records as they are; K_m upper bound becomes a
   human-decision item (candidate tightening), never an automatic rewrite.
```

## NEXT-STAGE SCREENING STRATEGY (2026-10-21)

```text
wide-range sampling + few simple hard constraints + automatic geometry screening
+ necessary human review
```

```text
1. SS1 = 3.2, SS2 = 0.8 stay FIXED
2. the other 11 geometry parameters stay variable (ranges still to be confirmed)
3. tighten a single-parameter bound only with clear evidence
4. do NOT prioritize complex multi-parameter joint constraints
5. generate many candidates and screen at geometry level before mesh / CFD
6. record every rejected sample and reason (append-only, never delete)
7. validate automatic QC against human judgement (current QC misses all 15)
8. training set stays nested (D_N prefix); test set fixed and independent
```

```text
NOT implemented this session: no sampler, no constraint filter, no new QC
algorithm, no re-run, no change of any range value.
```

Full strategy: `docs/GEOMETRY_SCREENING_STRATEGY_2026-10-21.md`.
Concrete constraint proposal (A/B/C, scheme A recommended):
`docs/GEOMETRY_CONSTRAINT_ANALYSIS_2026-10-21.md`.

Full session record: `docs/SESSION_DELIVERY_2026-10-21.md`.



## NEXT HUMAN DECISION — HIGHEST PRIORITY

```text
Before implementing code/01_generate_design.py,
the project must first freeze the six-dimensional production ranges:

1. FINAL_PRODUCTION_RANGES   (owner / advisor confirmation)
```

The advisor input for that decision is now three packages:

```text
1. analysis/geometry_review/parameter_final_decision_v1/FINAL_DECISION.md
   (candidate 13-parameter space, SS1/SS2 fixed, Xmean upper bound 0.18)
2. analysis/geometry_review/parameter_sensitivity_v1_100cases/
   HUMAN_REVIEW_2026-10-21.md  + human_review_2026-10-21.csv
   (85 ACCEPT / 15 REJECT; per-case reject reasons still missing)
3. analysis/geometry_review/senior_review_v2/  (40 real V2 blades, historical stage)
```

Current review coverage (do not overstate it):

```text
C820 (100 cases) : 85 ACCEPT / 15 REJECT -> complete shape review
C830 (57 cases)  : no human review recorded
C840 (49 rows)   : no human review recorded
V2   (40 cases)  : no human review recorded (human_* still empty)
```

Until the advisor has given the missing per-case reasons and answered the CFD /
threshold-calibration items, no production range may be frozen.
`FINAL_PRODUCTION_RANGES` stays PENDING.

Independently still open:

```text
2. production DOE dimension: keep d = 6, or adopt 11 geometry + 2 operating?
3. FINAL_VALIDATION_POLICY / FINAL_N_VALIDATION
4. FINAL_RAW_CFD_ATTEMPTS   (after a real NUMECA/CFX failure-rate stress test)
5. K_m upper bound / Metal2 lower bound tightening (evidence documented,
   values NOT decided; final_geometry_parameters.yaml left unchanged)
6. whether Solidity / Metal1 enter the production DOE
7. which geometry constraint scheme to adopt (A / A2 / B / C proposal in
   docs/GEOMETRY_CONSTRAINT_ANALYSIS_2026-10-21.md; scheme A recommended)
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
- production DOE dimension: keep d = 6 or adopt 11 geometry + 2 operating
- per-case reasons for the 15 C820 REJECT cases
- K_m upper bound / Metal2 lower bound (evidence only; values not decided)
- whether Solidity / Metal1 enter the production DOE
- FINAL_VALIDATION_POLICY / FINAL_N_VALIDATION
- FINAL_RAW_CFD_ATTEMPTS (raw CFD attempts / failure reserve)
- training repetition design
- final `E` definition
- model-size `P` grids

## REMAINING DOCUMENTATION NOTES (not errors, do not "fix")

```text
49 vs 50 rows       : C840 case_design.csv / case_metrics.csv hold 49 DATA rows
                      + 1 header = 50 text lines. FINAL_DECISION.md's file table
                      says "50 行" using the text-line convention. Generated report
                      intentionally left unchanged.
provenance git_head : experiment provenance keeps the RUN-TIME head (02e57d1),
                      not the latest commit; cite it as "run-time HEAD".
volume              : 100-case README says ~2.36 MB = provenance.output_size_mb
                      (2.359, output artifacts only); the current directory is
                      ~2.5 MB because it also contains the untracked logs/ dir.
untracked logs      : ks1_ks2_review_v1/logs/ and
                      parameter_sensitivity_v1_100cases/logs/ stay untracked.
                      Verified: tools/ only WRITE logs, never read them, so there is
                      no reproduction dependency; risk is only "logs not in VCS".
test counts         : 111/111 = record of the 2026-10-15 run; latest =
                      131 passed + 17 subtests passed (2026-10-21, measured).
```


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
  0. docs/SESSION_DELIVERY_2026-10-21.md        (parameter-space reconciliation +
                                                 human review intake + strategy)
  1. docs/SESSION_DELIVERY_2026-10-17.md        (100-case scan -> 57-case review
                                                 -> final decision, SS1/SS2 freeze)
  2. analysis/geometry_review/parameter_final_decision_v1/FINAL_DECISION.md
     (candidate 13-parameter space; geometry_dimension = 11)
  3. analysis/geometry_review/parameter_sensitivity_v1_100cases/README.md
     + REPORT.md                                (100 real blades, C820001..C820100)
  4. analysis/geometry_review/parameter_sensitivity_v1_100cases/HUMAN_REVIEW_2026-10-21.md
     + human_review_2026-10-21.csv              (85 ACCEPT / 15 REJECT)
  5. docs/PARAMETER_SPACE_RECONCILIATION.md     (6D freeze vs 13D exploratory space)
  6. docs/GEOMETRY_SCREENING_STRATEGY_2026-10-21.md  (next-stage strategy)
  7. analysis/geometry_review/senior_review_v2/ (40 real V2 blades, historical stage)

DO NOT start 01_generate_design.py before those ranges are frozen.
Do not treat the exploratory candidate ranges as approved production ranges.
Do not equate human shape ACCEPT or geometry QC PASS with mesh/CFD/aero validity.
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
10. docs/SESSION_DELIVERY_2026-10-21.md  (parameter-space reconciliation + human
                                          review intake + next-stage strategy)
11. docs/PARAMETER_SPACE_RECONCILIATION.md
12. docs/GEOMETRY_SCREENING_STRATEGY_2026-10-21.md
13. docs/GEOMETRY_CONSTRAINT_ANALYSIS_2026-10-21.md   (A/B/C proposal, scheme A)
```

When continuing geometry work, also provide:

```text
14. docs/GEOMETRY_GENERATOR_CONTRACT.md
15. docs/GEOMETRY_QC_CONTRACT.md
16. analysis/geometry_review/README.md                  (review dir entry point)
17. analysis/geometry_review/parameter_sensitivity_v1_100cases/README.md + REPORT.md
18. analysis/geometry_review/parameter_sensitivity_v1_100cases/HUMAN_REVIEW_2026-10-21.md
    + human_review_2026-10-21.csv
19. analysis/geometry_review/parameter_sensitivity_v1_100cases/parameter_decisions.csv
20. analysis/geometry_review/parameter_final_decision_v1/FINAL_DECISION.md
21. analysis/geometry_review/senior_review_v2/README.md (40-case review package)
```

Only when a legacy audit is actually needed, also provide:

```text
legacy/blade_batch_generation.py
legacy/blade_batch_generation_template.geomTurbo
config/ranges_legacy.yaml
```
