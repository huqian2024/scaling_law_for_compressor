# AI4S Compressor CFD Project — Session Delivery
Date: 2026-10-15

> Delivery record for the 2026-10-15 session. It complements, and does not
> replace, `PROJECT_HANDOFF.md`.
>
> Scope of this session: **angle/incidence audit + Geometry Range Review V1 and V2
> + 40-case senior review package + repository closeout.**
> **No production design, no geometry production run, no mesh, no NUMECA/CFX, no CFD.**

## 1. Executive Summary

```text
A. Inlet-angle / incidence definition code audit          DONE (finding recorded)
B. Geometry Range Review V1  (legacy ranges, 30 cases)    DONE -> ARCHIVED
C. Geometry Range Review V2  (exploratory ranges, 40 cases) DONE
D. V2 Geometry QC                                         40/40 PASS
E. V2 senior review package (figures + index + JSON)       DELIVERED
F. Repository closeout (docs / .gitignore / git)           DONE
```

The blocker is unchanged:

```text
FINAL_PRODUCTION_RANGES is still PENDING (owner / advisor confirmation).
V2 exploratory ranges are NOT a production range and were NOT approved.
Geometry QC PASS does NOT mean aerodynamically reasonable and does NOT mean
a mesh or a CFD run is feasible.
```

## 2. Frozen core (read-only this session, unchanged)

```text
code/geometry_legacy_v1.py                         Metal1 = 53 deg, untouched
legacy/blade_batch_generation_template.geomTurbo   sha256 92c4296f2de27440aebaad9b03b9af4f9e09756fabff2298f4607a87f2c55119
config/ranges_legacy.yaml                          untouched
tests/ + tests/fixtures/legacy_geometry_v1/        untouched
docs/GEOMETRY_GENERATOR_CONTRACT.md  docs/GEOMETRY_QC_CONTRACT.md   untouched
```

Evidence: `git status --porcelain` shows **no modified tracked file** in this session.

## 3. Inlet-angle / incidence audit

```text
legacy/blade_batch_generation.py:46 comment says  "zero-incidence inlet flow angle 49 deg"
the code actually builds Metal1 = 53 deg
=> 4 deg discrepancy, cause still UNCONFIRMED (recorded, not "fixed").

Decision: the frozen geometry core keeps Metal1 = 53 deg.
No geometry constant was changed. This remains an open question for the owner.
```

Verified on real output: changing only `Incidence`/`Mach` gives **byte-identical**
`.dat` / `.geomTurbo` (V1 cross-check C800001 vs C800030). They can therefore only
act inside a CFX inlet boundary condition, which does not exist in this repository yet.

## 4. Geometry Range Review V1 (legacy ranges) — ARCHIVED

```text
range_id    = legacy_review
case_id     = C800001 .. C800030      (30 cases, legacy 1891 range)
results     = generation 30/30 CREATE, conflict 0, ERROR 0
              Geometry QC 30/30 PASS (geometry_qc_v1_hard, UNCALIBRATED)
              min_gap 0.019361 .. 0.047919 m
              envelope_clearance -0.003948 .. +0.038504 m  (1 negative: C800019, diagnostic only)
figures     = 9 PNG @200 dpi
archive     = analysis/geometry_review/archive/v1_legacy_review/   (FROZEN RECORD)
```

Known gap recorded honestly in the archive PROVENANCE: the **V1 plotting script**
(`tools/plot_geometry_review.py`, V1 revision) was overwritten by the V2 rewrite
while it was untracked, so it is not recoverable from git. V1 figures, V1 data
table, V1 QC report, V1 builder scripts and V1 logs are all archived.
The 30 V1 `.dat` / `.geomTurbo` files are deliberately not archived (byte-exact
rebuild documented in the archive PROVENANCE).


## 5. Geometry Range Review V2 (exploratory extended ranges) — DONE

```text
range_id    = exploratory_v2_review
sampling_id = exploratory_v2_deterministic
case_id     = C810001 .. C810040      (40 cases, V2 block)
ranges      = analysis/geometry_review/ranges_exploratory_v2.yaml
              status EXPLORATORY_NOT_APPROVED (never written into config/)
```

Exploratory ranges vs the historical ones:

| Parameter | historical (1891 / V1) | V2 exploratory | kind |
|---|---|---|---|
| Xthick | 0.15 – 0.45 | 0.10 – 0.60 | non-dimensional |
| Tmax | 0.04 – 0.07 | 0.025 – 0.095 | non-dimensional |
| Metal2 | 6 – 24 deg | 0 – 32 deg | deg (Metal1 = 53 deg frozen) |
| Solidity | 1.0 – 2.0 | 0.7 – 2.5 | changes only periodicity = 0.06 / Solidity |
| Incidence | −4 – 4 deg | fixed 0 deg | operating condition |
| Mach | 0.3 – 0.7 | fixed 0.5 | operating condition |

Case design (deterministic, boundary-heavy, de-duplicated):

```text
A_single_param 17   new/legacy bounds scanned one parameter at a time
B_corner        8   2^3 extreme corners of (Xthick, Tmax, Metal2), Solidity = 1.5
C_coupled       8   Solidity x Metal2 coupled boundaries
C_combined      3   multi-parameter extremes
D_maximin       4   deterministic maximin dispersed points (seed 20261015)
total          40   unique blade outlines = 25 (15 cases are the same blade at a different pitch)
```

## 6. V2 results (real pipeline output, recomputed from disk)

```text
geometry generation         40/40 .dat + .geomTurbo on disk
Geometry QC                 40/40 PASS  (geometry_qc_v1_hard, UNCALIBRATED, reason = OK)
min_gap                     0.014494 .. 0.072696 m       (hard gate min_gap > 0: all pass)
negative envelope_clearance 5 cases: C810017 C810032 C810033 C810035 C810038
                            (diagnostic only, NOT collisions, NOT QC failures)
unique blade outlines       25
unit tests                  111 / 111 OK
```

`envelope_clearance = periodicity − blade_tangential_extent` is a diagnostic
quantity per the frozen QC contract; the hard gate is `min_gap > 0`.
Where it is negative the cascade channel is narrow, which is worth an engineering
judgement (mesh feasibility), not a QC failure.

## 7. Senior review package (deliverable)

```text
analysis/geometry_review/senior_review_v2/
├── README.md                    review instructions (Chinese, incl. units + disclaimers)
├── 00_all_cases_overview.png    40 panels (5 x 8), 5716 x 3081 px @200 dpi
├── 00_case_index.csv            40 rows, incl. empty human_acceptance / human_comment
└── cases/C8100xx/               parameters.json + 3 PNG + .dat + .geomTurbo (40 folders)

per-case PNG   120  (blade_profile / cascade_3blade / edge_details)
overview PNG     1
.dat / geomTurbo 40 / 40  (byte-identical copies of the pipeline output)
ZIP            analysis/geometry_review/senior_review_v2.zip  (243 files, 21.1 MiB, local only)
```

Plot conventions that prevent misreading:

```text
blade_profile.png    all 40 share ONE physical window and ONE scale (directly comparable)
edge_details.png     all 40 share ONE 0.012 m square window (4x the profile scale)
cascade_3blade.png   real pitch = 0.06 / Solidity, equal aspect (never stretched);
                     canvas height follows the pitch, so use the printed pitch value,
                     not pixel distances, to compare cascades
.dat coordinates are raw normalised units -> uniformly scaled so chord = 0.06 m,
therefore plotted lengths are metres; Xthick / Tmax / Metal2 are never shown as metres.
```

## 8. Verification performed

```text
conda run -n ai4s python -m unittest discover -s tests -p "test_*.py"   111/111 OK
independent read-only re-check of the V2 package (recomputed from disk):
    40 folders / 40 parameters.json / 120 per-case PNG + 1 overview
    40 .dat and 40 .geomTurbo byte-identical to geometry/profiles|geomturbo
    review_cases.csv == parameters.json (no parameter drift)
    geometry_qc.csv 40 rows, 40 PASS, min_gap > 0
    00_case_index.csv 40 rows in case_id order, human_* empty
    no C800xxx (V1) id anywhere inside the V2 package
    ZIP entry set == extracted directory (243 files)
V1 archive re-check: 30 cases, 30 QC rows, 9 figures
```

## 9. Explicitly NOT done this session

```text
No modification of code/geometry_legacy_v1.py, code/02_generate_geometry.py,
    code/03_geometry_qc.py, legacy/, tests/ + fixtures, config/ranges_legacy.yaml
No production design (01_generate_design.py) and no generate_geomturbo_batch.py run
No new parameter scan, no geometry re-generation, no QC re-run, no CFD
No NUMECA / CFX / HPC execution
No freezing of any production range; no formal DOE
No deletion of any data (analysis only)
```

## 10. Next step

```text
Advisor / senior reviews the 40 real V2 blade shapes
    entry: analysis/geometry_review/senior_review_v2/00_all_cases_overview.png
           + analysis/geometry_review/senior_review_v2/00_case_index.csv
    decisions filled in human_acceptance / human_comment (CSV or parameters.json)
  -> derive the reasonable parameter space from the feedback
  -> decide whether to extend the boundaries again
  -> freeze FINAL_PRODUCTION_RANGES
```

Until `FINAL_PRODUCTION_RANGES` is frozen the production pipeline stays
**DO-NOT-RUN**.
