# AI4S Compressor CFD Project — Session Delivery
Date: 2026-10-11

> This is the **delivery record for today's session**. It complements, and does not
> replace, `PROJECT_HANDOFF.md`.
>
> HISTORICAL NOTE (2026-10-13): the production-scale items listed below as PENDING
> (`FINAL_NMAX`, `FINAL_N_LADDER`) were frozen afterwards. Current authoritative
> values — including the explicit terms `FINAL_N_TRAIN_MAX` / `FINAL_N_TEST` /
> `MIN_USABLE_TRAIN_TEST_CASES` / `FINAL_RAW_CFD_ATTEMPTS` — live in
> `docs/DESIGN_FREEZE_2026-10-13.md`. This file is kept as the 2026-10-11 record and
> is not rewritten.

## 1. Executive Summary

Two core goals were closed today.

```text
A. Local Geometry pipeline completed:
   profile -> geomTurbo -> Geometry QC

B. FINAL_DOE closed:
   SCRAMBLED_SOBOL
```

Consequence:

```text
The next blocker is NOT geometry and NOT DOE-family selection.

The next blocker is production scale:
FINAL_NMAX + FINAL_N_LADDER.
```

No push was performed during end-of-day closeout.

## 2. Repository State

```text
branch          = master
local HEAD      = e1f59770c7ccab8b0864445e54b02f8d54a3aa04
origin/master   = ebbf7bd9a74ef2db1edd84f5c83ddec4e752c07f
ahead           = 9
behind          = 0
diverged        = NO
working tree    = clean
tags            = pre-geometry-v1  (points at ebbf7bd, unmoved)
```

```text
No push was performed during end-of-day closeout.
```

Local is 9 commits ahead of `origin/master`; those commits are **not yet pushed**.

## 3. Geometry Work Completed

```text
legacy regression fixture       PASS   (legacy_geometry_v1, 13 cases)
geometry core exact regression  PASS   (26/26 byte-for-byte)
geometry generator              PASS
geometry generator contract     FROZEN V1.2
Geometry QC                     PASS
Geometry QC contract            FROZEN V1
local geometry chain            PASS
```

Deliverables produced before this session's closeout:

```text
code/geometry_legacy_v1.py            pure legacy-compatible geometry core
code/02_generate_geometry.py          CLI / CSV / resume / dry-run / overwrite / atomic I/O
code/03_geometry_qc.py                Geometry QC v1 (hard gates only)
```

Executable chain:

```text
master design CSV
  -> code/02_generate_geometry.py   -> geometry/profiles/<case_id>.dat
                                      geometry/geomturbo/<case_id>.geomTurbo
  -> code/03_geometry_qc.py         -> geometry/geometry_qc.csv
```

## 4. Geometry Regression / Contracts

```text
legacy exact regression = 26/26   (13 profiles + 13 geomTurbo, byte-for-byte)
Geometry QC frozen baseline = 13/13 PASS
```

Frozen artifacts (do not modify):

```text
tests/fixtures/legacy_geometry_v1/            fixture case list + expected outputs
legacy/blade_batch_generation_template.geomTurbo
```

Contracts:

```text
docs/GEOMETRY_GENERATOR_CONTRACT.md   FROZEN V1.2
docs/GEOMETRY_QC_CONTRACT.md          FROZEN V1
```

Important distinction (do not misread the audit numbers):

```text
The recorded ranges (e.g. min_gap 0.019361..0.047919, chord ~0.06) are
regression CHARACTERIZATION of the frozen baseline.
They are NOT engineering thresholds and are NOT validity gates.
```

## 5. Geometry QC Completed

```text
qc_policy_id       = geometry_qc_v1_hard
calibration_status = UNCALIBRATED
```

Hard gates implemented (no empirical thresholds):

```text
artifacts exist / parse valid / finite coordinates
no blade self-intersection (canonical 216-vertex polygon)
positive interior paired thickness
LE/TE closure exactly 0 (legacy-v1 structural rule)
periodicity finite and > 0
span sections internally consistent
no adjacent periodic-blade intersection
min_gap finite and > 0
chord finite and > 0
no zero-length internal segments
curvature diagnostics finite
```

Frozen QC baseline (13 fixtures):

```text
selected_count = 13 ; pass_count = 13 ; fail_count = 0
profile_point_count = 109 ; canonical polygon = 216 vertices
self_intersection = false ; LE/TE closure = 0 ; min_gap finite positive
```

## 6. FINAL DOE Decision

```text
FINAL_DOE = SCRAMBLED_SOBOL      (owner/human approved, FINAL)
seed      = 1
source    = analysis/doe_compare_benchmark.py (line 44)
```

```text
A1 = BASELINE_ONLY
A2 = DEPRIORITIZED
B  = FINAL_PRODUCTION_DOE
```

Rationale: B had the lowest centered discrepancy at every tested N, the strongest
marginal balance, and a naturally nested sequence suited to scaling-law dataset
growth. All three schemes satisfied nested containment.

## 7. DOE Production Semantics

```text
method     = scipy.stats.qmc.Sobol
d          = 6
scramble   = True
seed       = 1
ordering   = native Sobol sequence order
nested     = prefix nesting  (D_N = first N points of the frozen master sequence)
```

```text
one fixed master Sobol sequence, generated once
no independent redraw per N
no sorting / reordering
no LHS / Sobol mixing in the main production pool
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

`random_base2` policy: generate the canonical master sequence with
`random_base2(m)`, `2^m >= required master-pool size`; non-`2^k` tiers still use the
first `N` cases and stay nested, but the strongest Sobol balance properties apply at
power-of-two boundaries.

## 8. Legacy 1891 Final Role

```text
LEGACY_1891_ROLE = HISTORICAL_REFERENCE_AND_REGRESSION_ONLY
```

```text
Historical 1891 cases are NOT part of the new production Sobol pool.
```

Permitted uses only:

```text
historical reference
regression
Golden Case source
legacy comparison
```

```text
Do NOT treat 1891 as the new project's target scale.
A future transfer / mixed-dataset experiment must open its own definition and must
not be silently merged into the main scaling experiment.
```

## 9. Tests and Integrity Results

```text
python -m unittest discover -s tests -p 'test_*.py'   ->  111/111 PASS
python tools/capture_legacy_geometry_fixtures.py --verify   ->  VERIFY_OK
legacy exact regression                                      ->  26/26 PASS
```

Frozen legacy hashes (unchanged):

```text
48ed9ead4b1260790dcc2d3ad9fe05c79e745a82ad19fe2ce918268adfc36e03
  legacy/blade_batch_generation.py
92c4296f2de27440aebaad9b03b9af4f9e09756fabff2298f4607a87f2c55119
  legacy/blade_batch_generation_template.geomTurbo
237ce3f4c1da022a57c7a82e8057248871ce673c96dcba6d0add5763dcc558ef
  config/ranges_legacy.yaml
```

## 10. Git Commits Created This Session

Source: `git log --oneline --decorate ebbf7bd..HEAD` (read from git, not assumed).

```text
e1f5977 (HEAD -> master) docs: freeze scrambled Sobol production DOE
4427dee feat: implement geometry QC workflow
4fdd316 docs: freeze geometry QC contract
63fd060 feat: implement geometry generation workflow
01cc5e1 docs: classify geometry output I/O failures
64b48b9 docs: clarify geometry template newline semantics
7a8e566 feat: implement legacy-compatible geometry core
192915b docs: freeze geometry generator contract
1952186 test: freeze legacy geometry regression baseline

count = 9
```

Baseline before this session:

```text
ebbf7bd (tag: pre-geometry-v1) checkpoint project before geometry refactor
```

## 11. Current Blockers

### Human / scientific decisions

```text
FINAL_NMAX
FINAL_N_LADDER
validation / test policy
validation / test sample sizes
training repetition design
dataset repetition design
E definition
P grids
geometry reuse
expanded parameter space
```

### External environment blockers

```text
Golden Case
NUMECA
CFX
HPC
Incidence implementation
CFX boundary-condition implementation of Incidence
CFX boundary-condition implementation of Mach
```

## 12. Decisions for Next Group Meeting

### 1) Production scale (FIRST ITEM)

```text
FINAL_NMAX:
maximum number of newly generated CFD cases

FINAL_N_LADDER:
nested training-data sizes used for scaling-law measurement
```

```text
Expected overall scale: O(10^4)–O(10^5)
Exact values: NOT YET DECIDED
```

No final values are proposed by this document.

### 2) Validation / test policy for the scaling experiment

```text
fixed validation + fixed test (preferred design) vs alternatives
validation / test sample sizes
```

### 3) Repetition design

```text
number of training repetitions
whether dataset realizations are repeated
```

### 4) Error metric `E`

```text
final definition and aggregation contract (per-field / per-domain / global)
```

### 5) Model-size grids `P` and geometry reuse

```text
model-size `P` grids
geometry reuse / multiple operating conditions
```

### 6) External verification (when the school environment is available)

```text
Golden Case, NUMECA, CFX, HPC
```

## 13. Next Engineering Task

```text
NEXT HUMAN DECISION — HIGHEST PRIORITY:
FREEZE FINAL_NMAX + FINAL_N_LADDER
```

```text
NEXT ENGINEERING TASK (only after the above):
define the 01_generate_design.py production contract, then implement it.
```

```text
01_generate_design.py remains BLOCKED.
```

Current status of the design stage:

```text
01_generate_design.py   NOT STARTED / BLOCKED
FINAL_NMAX              PENDING
FINAL_N_LADDER          PENDING
```

## 14. New-Chat Resume Package

Upload first:

```text
1. PROJECT_HANDOFF.md
2. AGENT_INSTRUCTION.md
3. docs/DOE_DECISION.md
4. docs/SCALING_EXPERIMENT_DESIGN.md
5. docs/SESSION_DELIVERY_2026-10-11.md
```

If the next session continues geometry work, also provide:

```text
6. docs/GEOMETRY_GENERATOR_CONTRACT.md
7. docs/GEOMETRY_QC_CONTRACT.md
```

Only when a legacy audit is actually required, also provide:

```text
legacy/blade_batch_generation.py
legacy/blade_batch_generation_template.geomTurbo
config/ranges_legacy.yaml
```

## 15. Do-Not-Guess / Do-Not-Change List

```text
Do not invent Incidence conversion.
Do not invent Mach implementation.
Do not modify files under legacy/.
Do not change frozen legacy ranges silently.
Do not merge historical 1891 into the production Sobol pool.
Do not implement 01_generate_design.py before Nmax / N-ladder freeze.
Do not delete failed CFD cases.
Do not fake-repair missing CFD data.
Do not silently change Geometry QC thresholds.
```
