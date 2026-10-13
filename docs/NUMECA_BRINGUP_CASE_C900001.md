# NUMECA bring-up delivery — single case C900001

Date: 2026-10-13

Purpose: deliver **one** NUMECA bring-up `.geomTurbo`. No mesh, no `.trb`, no CFX,
no `01_generate_design.py`, no production DOE.

## Deliverable

```text
NUMECA_READY_GEOMTURBO = geometry/geomturbo/C900001.geomTurbo
```

## Case

```text
case_id     = C900001
source      = legacy/lhs_samples_train.csv  (data row 1 — fallback, read-only)
range_id    = legacy/core
sampling_id = bringup_v1

Xthick     = 0.447058581405036
Tmax       = 0.0503392254535793
Metal2     = 21.381542432026524
Solidity   = 1.1628205402211451
Incidence  = -0.4982560254593786
Mach       = 0.6175322677681643
```

Input file (TEMPORARY, not a production master design):

```text
design/bringup/numeca_bringup_master_design.csv
```

Note: the frozen regression fixture `tests/fixtures/legacy_geometry_v1/cases.csv`
uses `fixture_id` (LG001..LG013) and has no `range_id`/`sampling_id` columns, so it
is **not** directly usable as generator input; the documented fallback
(`lhs_samples_train.csv` row 1) was used. Because it is a fallback case, the
"fixture exact match" step does not apply; the existing geometry test suite was run
instead.

## Commands

```bash
conda run -n ai4s python code/02_generate_geometry.py \
    --input design/bringup/numeca_bringup_master_design.csv \
    --template legacy/blade_batch_generation_template.geomTurbo \
    --output geometry --case-id C900001 --dry-run      # CREATE (dry-run), tree unchanged

conda run -n ai4s python code/02_generate_geometry.py \
    --input design/bringup/numeca_bringup_master_design.csv \
    --template legacy/blade_batch_generation_template.geomTurbo \
    --output geometry --case-id C900001                # CREATE

conda run -n ai4s python code/03_geometry_qc.py \
    --input design/bringup/numeca_bringup_master_design.csv \
    --geometry geometry --output geometry/geometry_qc.csv --case-id C900001   # PASS
```

## Hashes

```text
template_sha256   = 92c4296f2de27440aebaad9b03b9af4f9e09756fabff2298f4607a87f2c55119
profile_sha256    = 2977f5798ab43aab527d06e9976be9177fd7a9a00325eb946273b8e2cb6874b9
geomturbo_sha256  = d8ae994dda268dbaaf5d68b4f8db982500132fd9d2441141c1306b8b4077bfb8
```

## Results

```text
regression (suite)   111 tests OK; frozen baseline verify 26/26 byte-for-byte
regression (fixture) N/A (fallback case)
geometry_qc_status   PASS  (geometry_ok = 1, reason = OK, policy geometry_qc_v1_hard, UNCALIBRATED)

chord                0.0599999489235      (target 0.06, rel err 8.5e-07)
periodicity          0.0516               (expected 0.0515986757411, abs err 1.32e-06)
min_gap              0.0376484461549      (> 0)
envelope_clearance   0.0192747
self_intersection    0
adjacent_blade_int.  0
finite_ok            1
min_interior_thick.  0.0047539457296      (> 0  -> thickness hard gate PASS)
max_paired_thick.    0.050333686533
le_closure_error     0
te_closure_error     0
profile_point_count  109
```

Re-running the generator on the same row returns `SKIP_MATCH`, confirming the stored
outputs are exactly this program's own successful candidate bytes (no forced overwrite
of a valid output).

Frozen artifacts untouched: `legacy/` and `tests/fixtures/legacy_geometry_v1/` show
no `git` modifications.
