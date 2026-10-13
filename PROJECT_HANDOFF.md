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
GEOMETRY_REUSE                  DISABLED / NOT ACTIVE
PRODUCTION_ROUTE                ONE_6D_POINT_ONE_CASE
FINAL_VALIDATION_POLICY         PENDING
FINAL_N_VALIDATION              PENDING
FINAL_PRODUCTION_RANGES         PENDING
FINAL_RAW_CFD_ATTEMPTS          PENDING

Geometry regression fixtures    PASS
Geometry generator contract     PASS
02_generate_geometry.py         PASS
Geometry QC contract            PASS
03_geometry_qc.py               PASS
Local geometry pipeline         PASS

01_generate_design.py           NOT STARTED / BLOCKED
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
```

The retired umbrella term `FINAL_NMAX` must no longer be used for current status,
because it conflates training `N_max`, usable total and raw CFD attempts.
Full freeze record: `docs/DESIGN_FREEZE_2026-10-13.md`.

## NEXT HUMAN DECISION — HIGHEST PRIORITY

```text
Before implementing code/01_generate_design.py,
the project must first freeze the six-dimensional production ranges:

1. FINAL_PRODUCTION_RANGES   (owner / advisor confirmation)
```

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
Confirm FINAL_PRODUCTION_RANGES (six-dimensional production parameter ranges).

DO NOT start 01_generate_design.py before those ranges are frozen.

Production scale itself is already FROZEN (2026-10-13):
see docs/DESIGN_FREEZE_2026-10-13.md.
```

For a new AI conversation, upload first:

```text
1. PROJECT_HANDOFF.md
2. AGENT_INSTRUCTION.md
3. docs/DOE_DECISION.md
4. docs/SCALING_EXPERIMENT_DESIGN.md
5. docs/SESSION_DELIVERY_2026-10-11.md   (historical record)
6. docs/DESIGN_FREEZE_2026-10-13.md      (current production-scale freeze)
```

When continuing geometry work, also provide:

```text
6. docs/GEOMETRY_GENERATOR_CONTRACT.md
7. docs/GEOMETRY_QC_CONTRACT.md
```

Only when a legacy audit is actually needed, also provide:

```text
legacy/blade_batch_generation.py
legacy/blade_batch_generation_template.geomTurbo
config/ranges_legacy.yaml
```
