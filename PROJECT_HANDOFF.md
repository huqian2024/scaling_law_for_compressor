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
DOE decision memo               PASS
Scaling statistical design      PASS
Geometry regression fixtures    PASS
Geometry generator contract     PASS
Geometry QC contract            PASS
Local geometry pipeline         PASS

FINAL_DOE                       SCRAMBLED_SOBOL (APPROVED)
FINAL_N_LADDER                  PENDING
FINAL_NMAX                      PENDING

01_generate_design.py           NOT STARTED
02_generate_geometry.py         PASS
03_geometry_qc.py               PASS
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

References:

- `docs/DOE_DECISION.md`
- `docs/SCALING_EXPERIMENT_DESIGN.md`

## NEXT STEP

```text
NEXT ENGINEERING TASK:
Freeze FINAL_N_LADDER and FINAL_NMAX, then define the
01_generate_design.py production contract.

Do not implement 01_generate_design.py until the required
production DOE parameters are fully frozen.
```

## OPEN HUMAN DECISIONS

Closed:

- FINAL_DOE (scrambled Sobol — approved)
- legacy 1891 future role (historical reference / regression / Golden-Case only)

Still open:

- scaling N ladder
- Nmax
- final validation / test policy
- training repetition design
- final `E` definition
- model-size `P` grids
- geometry reuse / multiple operating conditions
- expanded parameter space

## BLOCKED EXTERNAL INFORMATION

Golden Case / NUMECA / CFX / HPC details are still pending confirmation at the
school environment.

## NEW CHAT RESUME

For a new AI conversation, upload first:

```text
1. PROJECT_HANDOFF.md
2. AGENT_INSTRUCTION.md
3. docs/DOE_DECISION.md
4. docs/SCALING_EXPERIMENT_DESIGN.md
```

When continuing geometry work, also provide:

```text
5. legacy/blade_batch_generation.py
6. legacy/blade_batch_generation_template.geomTurbo
7. config/ranges_legacy.yaml
```
