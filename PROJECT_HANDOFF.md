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

FINAL_DOE                       PENDING HUMAN DECISION
FINAL_N_LADDER                  PENDING
FINAL_NMAX                      PENDING

01_generate_design.py           NOT STARTED
Geometry regression fixtures    NOT STARTED
02_generate_geometry.py         NOT STARTED
03_geometry_qc.py               NOT STARTED
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

```text
Geometry = f(Xthick, Tmax, Metal2, Solidity)
OperatingCondition = f(Incidence, Mach)
```

The CFX implementation of `Incidence` / `Mach` is still **TBD**; guessing is
forbidden.

## DOE STATUS

```text
A1 Master LHS + raw prefix
STATUS = BASELINE

A2 Master LHS + greedy maximin ordering
STATUS = DEPRIORITIZED

B Scrambled Sobol
STATUS = LEADING_CANDIDATE
REQUIRES SUPERVISOR APPROVAL

FINAL_DOE = PENDING
```

References:

- `docs/DOE_DECISION.md`
- `docs/SCALING_EXPERIMENT_DESIGN.md`

## NEXT STEP

```text
NEXT ENGINEERING TASK:
Establish fixed legacy geometry regression fixtures
before implementing 02_generate_geometry.py.
```

`01_generate_design.py` is deliberately **not** the next step: it remains blocked by
the `FINAL_DOE` decision.

## OPEN HUMAN DECISIONS

- FINAL_DOE
- scaling N ladder
- Nmax
- final validation / test policy
- training repetition design
- final `E` definition
- model-size `P` grids
- legacy 1891 future role
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
