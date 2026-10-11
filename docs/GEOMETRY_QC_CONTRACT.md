# Geometry QC Contract

```text
Status: FROZEN V1 — implementation contract

Baseline commit:
63fd0606a65a7c1e98cc3d05ba23b3590eec3113

Program:
code/03_geometry_qc.py
```

This document freezes the **interface and v1 semantics** of the geometry QC
program. It does not implement anything, and it does not restate the legacy
geometry mathematics.

> Related: `docs/GEOMETRY_GENERATOR_CONTRACT.md` (FROZEN V1.2) defines the
> generator whose artifacts this program inspects.

## 1. Core principle

```text
Geometry QC v1 must not invent empirical thresholds.
```

Checks are split into exactly two classes.

### A. HARD VALIDITY GATES

Only mathematical / structural conditions that need **no** empirical threshold may
decide:

```text
geometry_ok
```

### B. DIAGNOSTIC / CALIBRATION METRICS

Computed and recorded, but in v1:

```text
MUST NOT fail geometry_ok solely because an
empirical threshold has not been scientifically calibrated.
```

If thresholds are later obtained from the legacy 1891 population, a Golden Case, or
approved engineering criteria, they MUST be introduced under a **new**

```text
qc_policy_id
```

e.g. `geometry_qc_v2_calibrated`. The v1 criteria MUST NOT be changed silently.

## 2. QC policy identity

```text
qc_policy_id = geometry_qc_v1_hard
```

Every output CSV row MUST contain `qc_policy_id` so that future threshold policies
remain traceable.

## 3. Production CLI contract

```bash
python code/03_geometry_qc.py \
    --input design/master_design.csv \
    --geometry geometry \
    --output geometry/geometry_qc.csv
```

Flags:

```text
--input PATH       required
--geometry PATH    required
--output PATH      required
--case-id CASE_ID  optional, repeatable
--dry-run          optional
--overwrite        optional
```

`--config` and `--resume` are intentionally **not** part of v1. No threshold config
is introduced in v1 because no threshold has been approved.

## 4. Input CSV contract

Same required columns as the geometry generator production input:

```text
case_id
Xthick
Tmax
Metal2
Solidity
Incidence
Mach
range_id
sampling_id
```

* `case_id` MUST match `^C[0-9]{6}$` and MUST be globally unique.
* all six numeric columns MUST parse to finite float.
* mathematical preconditions: `0 < Xthick < 1` and `Solidity > 0`.
* legacy parameter ranges MUST NOT be hard-coded.
* extra columns are allowed.

## 5. Geometry artifact layout

For each selected case:

```text
<geometry>/profiles/<case_id>.dat
<geometry>/geomturbo/<case_id>.geomTurbo
```

QC is **read-only**: it generates no geometry and never rewrites artifacts. A
missing artifact means:

```text
geometry_ok = false
```

and a recorded reason of `PROFILE_MISSING` and/or `GEOMTURBO_MISSING`. Failed cases
are never deleted.

## 6. Profile parser contract

The profile `.dat` row format is:

```text
xp yp xs ys
```

i.e. `pressure_x pressure_y suction_x suction_y`.

Requirements:

* non-empty;
* every data row has exactly 4 numeric values;
* all values finite;
* pressure/suction are paired point-by-point (guaranteed by the row format);
* enough points to form a closed blade polygon.

Recorded metric:

```text
profile_point_count
```

For the current legacy-v1 generator the count is expected to be a fixed value, but
QC MUST NOT invent a generic failure rule merely because the count differs from
some hard-coded number.

## 7. Blade boundary definition

The 2-D boundary used by all polygon algorithms is frozen as:

```text
pressure surface:
P0 -> P1 -> ... -> Pn

suction surface:
S0 -> S1 -> ... -> Sn
```

Closed polygon:

```text
P0 -> P1 -> ... -> Pn
   -> S(n) -> S(n-1) -> ... -> S0
   -> P0
```

Pressure and suction MUST NOT be concatenated in the same direction.

### Canonical closed polygon (required)

The legacy-v1 geometry makes `P0 == S0` (LE closure) and `Pn == Sn` (TE closure)
**exactly coincident**. The canonical closed polygon used by self-intersection,
adjacent-blade intersection and min-gap is therefore constructed by **omitting the
duplicated closure vertices** (not by geometric deduplication):

```text
P0, P1, ..., Pn,
S(n-1), S(n-2), ..., S1
```

with an **implicit closing edge** `S1 -> P0`. `Sn` and `S0` MUST NOT be appended.

Equivalent implementation:

```python
pressure + reversed(suction[1:-1])
```

For the legacy fixture (109 pressure + 109 suction points) the canonical polygon has:

```text
216 vertices
```

Rules:

* this is NOT an artifact modification;
* it MUST NOT round coordinates, snap nearby vertices, use a geometric tolerance to
  merge arbitrary points, or repair malformed geometry;
* only the **exactly equal** common LE/TE endpoints obtained from the parser may be
  omitted by the topology rule above.

If `P0 != S0` or `Pn != Sn` then:

```text
geometry_ok = false
reason += LE_TE_CLOSURE_MISMATCH
```

and no repair / dedup may be attempted.

## 8. HARD GATE — finite

If any coordinate of the profile or of a parsed geomTurbo geometry is

```text
NaN
+inf
-inf
```

then:

```text
geometry_ok = false
reason += NONFINITE_COORDINATE
```

## 9. HARD GATE — self-intersection

Run a strict segment-intersection check on the normalized closed blade polygon
(section 7).

Rules:

* a shared endpoint between index-adjacent edges is NOT an intersection;
* the normalized polygon has no coincident closure vertices, so this is unambiguous;
* crossing or collinear-overlap of non-adjacent edges IS an intersection.

Record:

```text
self_intersection
```

If true:

```text
geometry_ok = false
reason += SELF_INTERSECTION
```

`shapely` MUST NOT be used; the standard library plus NumPy is sufficient.

## 10. HARD GATE — thickness / surface separation

For paired pressure/suction points `(Pi, Si)` record:

```text
paired_thickness_i = euclidean_distance(Pi, Si)
```

LE / TE closure endpoints may be 0. For interior points:

```text
i = 1 ... n-1
```

require:

```text
paired_thickness_i > 0
```

Record:

```text
min_interior_thickness
max_paired_thickness
```

If any interior thickness is `<= 0`:

```text
geometry_ok = false
reason += NONPOSITIVE_INTERIOR_THICKNESS
```

Note: paired thickness is a v1 *deterministic* QC metric. It MUST NOT be
interpreted as a strict normal aerodynamic thickness.

## 11. HARD GATE — LE / TE closure

Record:

```text
le_closure_error = distance(P0, S0)
te_closure_error = distance(Pn, Sn)
```

The current legacy geometry structurally makes pressure and suction meet at the LE
and TE. The frozen baseline audit (section 28) confirms the errors are **exactly**
`0.0` for all 13 fixtures, so v1 freezes:

```text
le_closure_error == 0   (legacy-v1 hard structural gate)
te_closure_error == 0   (legacy-v1 hard structural gate)
```

Any non-zero value:

```text
geometry_ok = false
reason += LE_TE_CLOSURE_MISMATCH
```

If a future policy needs a tolerance it must be introduced under a new
`qc_policy_id`; v1 does **not** invent one.

## 12. geomTurbo minimal parser / completeness

This is **not** a general NUMECA parser. It is a deterministic minimal parser that
only recognizes what QC needs:

```text
GEOMETRY TURBO
PERIODICITY
suction
pressure
SECTIONAL
section 1
section 2
XYZ polyline
point count
NI_END nibladegeometry
NI_END NIBlade
NI_END nirow
NI_END GEOMTURBO
NI_END GEOMETRY
```

It MUST check:

```text
file is non-empty
required structural markers are present
suction section count == 2
pressure section count == 2
declared point counts parse
actual coordinate counts match the declared counts
```

If the structure is incomplete:

```text
geometry_ok = false
reason += GEOMTURBO_INCOMPLETE
```

Absolute line numbers MUST NOT be the only mechanism; parsing is marker/count
driven.

## 13. HARD GATE — periodicity

Parse the single blade-row `PERIODICITY`. It MUST be

```text
finite
> 0
```

Record:

```text
periodicity
```

Otherwise:

```text
geometry_ok = false
reason += INVALID_PERIODICITY
```

Also compute:

```text
expected_periodicity = 0.06 / Solidity
periodicity_error_abs
```

The frozen baseline audit (section 28) shows the serializer rounding yields
`periodicity_error_abs == 0.0` for all 13 fixtures (their `Solidity` values are
1.0 / 1.5 / 2.0). No tolerance is invented; `periodicity_error_abs` remains a
**diagnostic**.

## 14. geomTurbo section consistency

Record the four section point counts:

```text
suction_section1_count
suction_section2_count
pressure_section1_count
pressure_section2_count
```

They MUST be internally consistent. Also check that section 1 and section 2 carry
the **same 2-D `(y, z)` coordinates** and differ only in the span coordinate.

Record:

```text
span_section_coordinate_consistent
span_min
span_max
```

Legacy baseline expects spans `0` and `0.003` (confirmed in section 28). If the
section 1 / section 2 2-D coordinates differ:

```text
geometry_ok = false
reason += SPAN_SECTION_MISMATCH
```

## 15. HARD GATE — adjacent periodic blade collision

Use the geomTurbo physical section-1 blade polygon. Build the two neighbouring
periodic copies:

```text
blade + periodicity   (in the tangential coordinate)
blade - periodicity   (in the tangential coordinate)
```

Check whether the current blade polygon intersects / overlaps either copy (on the
normalized polygon, section 7). If so:

```text
geometry_ok = false
reason += ADJACENT_BLADE_INTERSECTION
```

This is an objective hard gate requiring no empirical threshold.

### Tangential coordinate definition (FROZEN for GT_V1 QC)

Frozen:

```text
Tangential direction for GT_V1 QC =
geomTurbo Y coordinate =
the second coordinate of an XYZ polyline =
the legacy profile y coordinate.
```

Derived from the legacy serializer mapping:

```text
profile:            xp yp xs ys

geomTurbo suction:  span, ys, xs
geomTurbo pressure: span, yp, xp
```

hence:

```text
profile x  ->  geomTurbo Z  ->  axial / chordwise
profile y  ->  geomTurbo Y  ->  tangential / pitchwise
```

The periodic copies MUST therefore be built as:

```text
(Y, Z) -> (Y +/- periodicity, Z)
```

Translation along `Z` / profile `x` MUST NOT be used.

This is the operational coordinate convention frozen for legacy GT_V1 QC, derived
from the legacy serializer itself. A future Golden Case may externally validate it,
but this does not block v1.

## 16. min gap metric

Compute the minimum Euclidean distance over all segment pairs between the current
blade boundary and the

```text
+periodicity copy
-periodicity copy
```

Record:

```text
min_gap
```

It MUST be

```text
finite
> 0
```

otherwise:

```text
geometry_ok = false
reason += NONPOSITIVE_MIN_GAP
```

This doubles as the deterministic v1 metric for the adjacent-channel minimum
clearance. No empirical threshold such as `min_gap > X mm` is added in v1.

## 17. Channel-width diagnostics

v1 MUST NOT invent a single uncalibrated "engineering channel width threshold". It
records at least:

```text
periodicity
blade_tangential_extent
envelope_clearance
min_gap
```

where

```text
blade_tangential_extent = max(A) - min(A)
envelope_clearance      = periodicity - blade_tangential_extent
```

`envelope_clearance` is a **diagnostic only**. It is explicitly NOT equivalent to the
true minimum channel gap; `min_gap` is the segment-based clearance metric. It MUST
NOT decide `geometry_ok` on its own.

(The frozen baseline contains a case, `LG011`, where `envelope_clearance < 0` while
the true `min_gap` is still positive; this demonstrates why the envelope metric is
not a validity gate. See section 28.)

## 18. Chord metrics

In the geomTurbo physical section 1 define:

```text
LE = the common pressure/suction first point
TE = the common pressure/suction last point
chord = distance(LE, TE)
```

Record:

```text
chord
chord_target = 0.06
chord_error_abs = abs(chord - 0.06)
chord_error_rel
```

There is **no** empirical chord tolerance in v1. A hard failure occurs only for a
structural invalidity:

```text
chord <= 0
non-finite
```

then:

```text
geometry_ok = false
reason += INVALID_CHORD
```

A value such as `0.0599999` versus `0.0600000` MUST NOT be auto-failed.

## 19. LE / TE diagnostic metrics

Beyond the closure hard gate (section 11), record:

```text
le_pressure_first_segment_length
le_suction_first_segment_length
te_pressure_last_segment_length
te_suction_last_segment_length
```

plus a repeatably defined local turning angle. A zero-length internal segment or
non-finite local geometry is a hard failure (see section 20). v1 MUST NOT define
`"LE angle > X degrees = anomalous"`; that requires calibration.

## 20. Curvature diagnostics

For each of the pressure and suction surfaces compute deterministic discrete
curvature diagnostics. For three consecutive points `A, B, C`:

```text
u = B - A
v = C - B
theta = atan2(|cross(u, v)|, dot(u, v))
L = 0.5 * (|u| + |v|)
```

If `|u| <= 0` or `|v| <= 0`:

```text
geometry_ok = false
reason += ZERO_LENGTH_SEGMENT
```

otherwise:

```text
discrete_curvature = theta / L
```

Record at least:

```text
pressure_max_turn_angle_deg
suction_max_turn_angle_deg
pressure_max_discrete_curvature
suction_max_discrete_curvature
```

All values MUST be finite. v1 MUST NOT set a max-curvature threshold:

```text
curvature anomaly threshold = UNCALIBRATED in v1
```

Calibration must later come from the legacy population or approved criteria.

## 21. geometry_ok v1 exact semantics

```text
geometry_ok = all HARD VALIDITY GATES pass
```

The v1 hard gates are at least:

```text
artifacts exist
profile parse valid
geomTurbo parse / structure valid
all required numeric data finite
no blade self-intersection (normalized polygon)
positive interior paired thickness
valid LE/TE closure rule (exactly 0 for legacy-v1)
periodicity finite and > 0
span sections internally consistent
no adjacent periodic-blade intersection
min_gap finite and > 0
chord finite and > 0
no zero-length internal segments
curvature diagnostics finite
```

Explicitly:

```text
geometry_ok does NOT mean
"all future engineering thresholds have been calibrated."
```

Therefore every row additionally carries:

```text
calibration_status = UNCALIBRATED
```

which is constant for all normal v1 rows.

## 22. Output CSV schema

At least:

```text
case_id
qc_policy_id
geometry_ok
reason

profile_exists
geomturbo_exists
profile_parse_ok
geomturbo_parse_ok

profile_point_count

finite_ok
self_intersection

min_interior_thickness
max_paired_thickness

le_closure_error
te_closure_error

periodicity
expected_periodicity
periodicity_error_abs

chord
chord_target
chord_error_abs
chord_error_rel

span_min
span_max
span_section_coordinate_consistent

adjacent_blade_intersection
blade_tangential_extent
envelope_clearance
min_gap

pressure_max_turn_angle_deg
suction_max_turn_angle_deg
pressure_max_discrete_curvature
suction_max_discrete_curvature

calibration_status
```

Additional count/diagnostic columns are allowed.

`reason` is:

```text
OK   when the case passes
```

otherwise a stable reason code, with multiple reasons joined by:

```text
;
```

Long natural-language prose MUST NOT be written into the CSV `reason`.

## 23. Missing / malformed case semantics

QC MUST continue processing the batch. A malformed artifact for one case yields:

```text
geometry_ok = false
```

plus a recorded reason, and QC proceeds to the next case. A single bad file MUST NOT
make the whole batch report disappear.

## 24. CLI exit semantics

```text
0 = QC execution completed and the report was produced,
    regardless of whether individual geometries PASS or FAIL

2 = CLI / input contract failure

4 = QC engine / report-writing operational failure
    that prevents reliable batch completion
```

Note explicitly:

```text
geometry_ok = false
```

is **not** by itself process exit 4. Finding bad geometry is QC's job. This differs
from the generator's exit semantics.

## 25. Dry-run

`--dry-run`:

```text
read input
read geometry artifacts
run QC
print summary
```

but:

```text
do not write geometry_qc.csv
do not modify geometry artifacts
```

## 26. Output overwrite

If `--output geometry/geometry_qc.csv` already exists:

default:

```text
refuse overwrite
exit 2
```

Only an explicit

```text
--overwrite
```

allows an atomic replacement. Writing uses:

```text
temp file in the same directory
fsync
os.replace
```

A partial report MUST NOT be left behind.

## 27. Console output

stdout uses JSON Lines. Per case:

```json
{
  "type": "case",
  "case_id": "C000001",
  "geometry_ok": true,
  "reason": "OK"
}
```

Final summary contains at least:

```text
type=summary
selected_count
pass_count
fail_count
missing_artifact_count
parse_failure_count
self_intersection_count
adjacent_intersection_count
output_path
dry_run
qc_policy_id
calibration_status
```

## 28. Frozen baseline feasibility audit (recorded, read-only)

One-off read-only analysis of `tests/fixtures/legacy_geometry_v1/`. These numbers
**characterize the baseline and prove the proposed metrics are computable**; they
are NOT thresholds and MUST NOT be auto-converted into gates.

```text
profile point count (13/13)          : 109
LE closure error (13/13)             : exactly 0.0
TE closure error (13/13)             : exactly 0.0
zero-length internal segment         : none
self-intersection, raw polygon (218) : 2 false positives per case (all 13)
self-intersection, normalized (216)  : 0 per case (all 13)
interior paired thickness            : min 0.004610, max 0.070013  (all > 0)

geomTurbo: 4 polylines per file      : yes (13/13)
section point-count tuple            : (109, 109, 109, 109)  (13/13)
span sets                            : {0.0, 0.003}  (13/13)
section1 == section2 in (y, z)       : yes (13/13)
periodicity values                   : {0.03000, 0.04000, 0.06000}
max |periodicity - 0.06/Solidity|    : 0.0
chord min / max                      : 0.0599999277 / 0.0600000729
max |chord - 0.06|                   : 7.294e-08

adjacent copy, tangential = A (y)    : intersects=False, min_gap [0.019361, 0.047919]
adjacent copy, tangential = B (x)    : intersects=False, min_gap [0.005251, 0.022676]
envelope_clearance (tangential = A)  : min -0.003948 (LG011), max 0.038504

curvature (finite, all cases):
  pressure max turn angle (deg)      : [23.6112, 25.8830]
  suction  max turn angle (deg)      : [23.0772, 25.3212]
  pressure max discrete curvature    : [2997.59, 3824.00]
  suction  max discrete curvature    : [3162.92, 3476.45]
```

Conclusions drawn from this audit:

* all v1 hard gates are satisfiable by the frozen baseline;
* the LE/TE closure gate can be frozen at exactly `0` for legacy-v1;
* `periodicity_error_abs` is exactly `0` for these 13 fixtures but remains a
  diagnostic (other Solidity values will not be exact);
* `envelope_clearance` may be negative while the true `min_gap` stays positive, so
  it must remain a diagnostic;
* the canonical closed-polygon construction of section 7 (omit the duplicated
  closure vertices) is required, otherwise the self-intersection gate would
  false-fail every fixture.

## 29. Open contract questions

```text
NONE
```

Q1 (tangential axis) and Q2 (canonical polygon) are resolved and frozen in
sections 15 and 7 respectively. The section 28 audit remains **baseline
characterization**, not empirical thresholds. No other hard-gate conflict with the
frozen fixtures was found.
