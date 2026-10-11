#!/usr/bin/env python
"""03_geometry_qc.py — Geometry QC v1 (hard gates only).

Contract: ``docs/GEOMETRY_QC_CONTRACT.md`` (FROZEN V1).

Policy:

    qc_policy_id       = geometry_qc_v1_hard
    calibration_status = UNCALIBRATED

Hard gates decide ``geometry_ok``; diagnostics are recorded but never fail a case
because an empirical threshold has not been calibrated.

Coordinate convention (frozen): geomTurbo XYZ rows are ``(span, Y, Z)`` where
``Y`` is the tangential (pitch) coordinate and ``Z`` the axial/chordwise one.

This program is read-only with respect to geometry artifacts.
"""

import argparse
import csv
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path

import numpy as np

CASE_ID_RE = re.compile(r"^C[0-9]{6}$")

REQUIRED_COLUMNS = [
    "case_id", "Xthick", "Tmax", "Metal2", "Solidity", "Incidence", "Mach",
    "range_id", "sampling_id",
]
NUMERIC_COLUMNS = ["Xthick", "Tmax", "Metal2", "Solidity", "Incidence", "Mach"]

QC_POLICY_ID = "geometry_qc_v1_hard"
CALIBRATION_STATUS = "UNCALIBRATED"
CHORD_TARGET = 0.06

EXIT_OK = 0
EXIT_CLI = 2
EXIT_OPERATIONAL = 4

# Deterministic reason-code emission order.
REASON_ORDER = [
    "PROFILE_MISSING",
    "GEOMTURBO_MISSING",
    "PROFILE_PARSE_ERROR",
    "GEOMTURBO_PARSE_ERROR",
    "GEOMTURBO_INCOMPLETE",
    "NONFINITE_COORDINATE",
    "LE_TE_CLOSURE_MISMATCH",
    "ZERO_LENGTH_SEGMENT",
    "SELF_INTERSECTION",
    "NONPOSITIVE_INTERIOR_THICKNESS",
    "INVALID_PERIODICITY",
    "SPAN_SECTION_MISMATCH",
    "ADJACENT_BLADE_INTERSECTION",
    "NONPOSITIVE_MIN_GAP",
    "INVALID_CHORD",
]

CSV_COLUMNS = [
    "case_id", "qc_policy_id", "geometry_ok", "reason",
    "profile_exists", "geomturbo_exists", "profile_parse_ok", "geomturbo_parse_ok",
    "profile_point_count",
    "finite_ok", "self_intersection",
    "min_interior_thickness", "max_paired_thickness",
    "le_closure_error", "te_closure_error",
    "periodicity", "expected_periodicity", "periodicity_error_abs",
    "chord", "chord_target", "chord_error_abs", "chord_error_rel",
    "span_min", "span_max", "span_section_coordinate_consistent",
    "adjacent_blade_intersection", "blade_tangential_extent",
    "envelope_clearance", "min_gap",
    "pressure_max_turn_angle_deg", "suction_max_turn_angle_deg",
    "pressure_max_discrete_curvature", "suction_max_discrete_curvature",
    "calibration_status",
]


class CliError(Exception):
    """CLI / input contract failure -> exit code 2."""


class ProfileParseError(Exception):
    def __init__(self, msg, nonfinite=False):
        super().__init__(msg)
        self.nonfinite = nonfinite


class GeomTurboParseError(Exception):
    def __init__(self, msg, nonfinite=False):
        super().__init__(msg)
        self.nonfinite = nonfinite


def _emit(obj) -> None:
    sys.stdout.write(json.dumps(obj, sort_keys=True) + "\n")


def _fmt(value):
    """Deterministic text, or '' when not computable."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, str):
        return value
    return format(float(value), ".12g")


# ---------------------------------------------------------------------------
# Deterministic 2-D segment kernel (no external geometry library)
# ---------------------------------------------------------------------------
def _cross2(o, a, b):
    return (a[..., 0] - o[..., 0]) * (b[..., 1] - o[..., 1]) \
        - (a[..., 1] - o[..., 1]) * (b[..., 0] - o[..., 0])


def _on_segment(a, b, p):
    return ((np.minimum(a[..., 0], b[..., 0]) <= p[..., 0])
            & (p[..., 0] <= np.maximum(a[..., 0], b[..., 0]))
            & (np.minimum(a[..., 1], b[..., 1]) <= p[..., 1])
            & (p[..., 1] <= np.maximum(a[..., 1], b[..., 1])))


def _seg_intersect_matrix(a1, a2, b1, b2):
    """Pairwise segment-intersection predicate, shape (n, m).

    Uses exact sign tests on the parsed float coordinates (no engineering
    tolerance).  A shared endpoint counts as an intersection for non-adjacent
    edges, which is exactly what the polygon topology needs.
    """
    d1 = _cross2(a1[:, None, :], a2[:, None, :], b1[None, :, :])
    d2 = _cross2(a1[:, None, :], a2[:, None, :], b2[None, :, :])
    d3 = _cross2(b1[None, :, :], b2[None, :, :], a1[:, None, :])
    d4 = _cross2(b1[None, :, :], b2[None, :, :], a2[:, None, :])
    proper = ((np.sign(d1) * np.sign(d2) < 0) & (np.sign(d3) * np.sign(d4) < 0))
    touch = (((d1 == 0) & _on_segment(a1[:, None, :], a2[:, None, :], b1[None, :, :]))
             | ((d2 == 0) & _on_segment(a1[:, None, :], a2[:, None, :], b2[None, :, :]))
             | ((d3 == 0) & _on_segment(b1[None, :, :], b2[None, :, :], a1[:, None, :]))
             | ((d4 == 0) & _on_segment(b1[None, :, :], b2[None, :, :], a2[:, None, :])))
    return proper | touch


def _pt_seg_dist(p, a, b):
    """Vectorised point-to-segment distance (broadcasting)."""
    ab = b - a
    l2 = (ab * ab).sum(-1)
    ap = p - a
    t = (ap * ab).sum(-1)
    safe = np.where(l2 > 0.0, l2, 1.0)
    t = np.clip(t / safe, 0.0, 1.0)
    proj = a + t[..., None] * ab
    dist = np.linalg.norm(p - proj, axis=-1)
    degen = np.linalg.norm(ap, axis=-1)
    return np.where(l2 > 0.0, dist, degen)


def _seg_seg_dist_matrix(a1, a2, b1, b2):
    """Pairwise segment-to-segment distance, shape (n, m).

    Intersecting segments have distance exactly 0 (the four point-to-segment
    distances alone would miss a proper crossing).
    """
    dist = np.minimum.reduce([
        _pt_seg_dist(a1[:, None, :], b1[None, :, :], b2[None, :, :]),
        _pt_seg_dist(a2[:, None, :], b1[None, :, :], b2[None, :, :]),
        _pt_seg_dist(b1[None, :, :], a1[:, None, :], a2[:, None, :]),
        _pt_seg_dist(b2[None, :, :], a1[:, None, :], a2[:, None, :]),
    ])
    intersect = _seg_intersect_matrix(a1, a2, b1, b2)
    return np.where(intersect, 0.0, dist)


def _poly_edges(points):
    pts = np.asarray(points, dtype=float)
    return pts, np.roll(pts, -1, axis=0)


def polygon_self_intersection(vertices):
    """True if the closed polygon has a non-adjacent edge intersection."""
    n = len(vertices)
    p1, p2 = _poly_edges(vertices)
    matrix = _seg_intersect_matrix(p1, p2, p1, p2)
    idx = np.arange(n)
    matrix[idx, idx] = False
    matrix[idx, (idx + 1) % n] = False
    matrix[(idx + 1) % n, idx] = False
    return bool(matrix.any())


def polygon_pair_min_distance(poly_a, poly_b):
    a1, a2 = _poly_edges(poly_a)
    b1, b2 = _poly_edges(poly_b)
    return float(_seg_seg_dist_matrix(a1, a2, b1, b2).min())


def polygon_pair_intersects(poly_a, poly_b):
    a1, a2 = _poly_edges(poly_a)
    b1, b2 = _poly_edges(poly_b)
    return bool(_seg_intersect_matrix(a1, a2, b1, b2).any())


def canonical_polygon(pressure, suction):
    """Canonical closed polygon: P0..Pn, S(n-1)..S1 (implicit S1 -> P0).

    (contract section 7).  The duplicated closure vertices Sn and S0 are omitted;
    no coordinate rounding / snapping is performed.
    """
    return list(pressure) + list(reversed(list(suction)[1:-1]))


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------
def parse_profile(text):
    """Strict profile parser: exactly 4 finite floats per data row."""
    rows = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        tokens = line.split()
        if len(tokens) != 4:
            raise ProfileParseError(
                f"line {lineno}: expected exactly 4 columns, got {len(tokens)}")
        try:
            vals = [float(tok) for tok in tokens]
        except ValueError:
            raise ProfileParseError(f"line {lineno}: non-numeric column")
        if not all(math.isfinite(v) for v in vals):
            raise ProfileParseError(f"line {lineno}: non-finite value",
                                    nonfinite=True)
        rows.append(vals)
    if not rows:
        raise ProfileParseError("profile is empty")
    return rows


_GEOMTURBO_NI_END = ["nibladegeometry", "NIBlade", "nirow", "GEOMTURBO",
                     "GEOMETRY"]


def geomturbo_missing_markers(text):
    """Return the list of missing structural markers (whitespace-insensitive)."""
    token_lines = [ln.split() for ln in text.splitlines() if ln.split()]
    flat = set()
    for ln in token_lines:
        if len(ln) >= 2 and ln[0] == "NI_END":
            flat.add(("NI_END", ln[1]))
    missing = []
    if not any(ln == ["GEOMETRY", "TURBO"] for ln in token_lines):
        missing.append("GEOMETRY TURBO")
    if not any(ln[0] == "suction" for ln in token_lines):
        missing.append("suction")
    if not any(ln[0] == "pressure" for ln in token_lines):
        missing.append("pressure")
    sectional = sum(1 for ln in token_lines if ln[0] == "SECTIONAL")
    if sectional != 2:
        missing.append(f"SECTIONAL x2 (found {sectional})")
    xyz = sum(1 for ln in token_lines if ln[0] == "XYZ")
    if xyz != 4:
        missing.append(f"XYZ polyline x4 (found {xyz})")
    for name in _GEOMTURBO_NI_END:
        if ("NI_END", name) not in flat:
            missing.append(f"NI_END {name}")
    return missing


def parse_geomturbo(text):
    """Minimal marker-driven geomTurbo parser (not a general NUMECA parser)."""
    if not text.strip():
        raise GeomTurboParseError("geomTurbo is empty")
    lines = text.splitlines()

    periodicity = None
    for ln in lines:
        tokens = ln.split()
        if tokens and tokens[0] == "PERIODICITY":
            if len(tokens) < 2:
                raise GeomTurboParseError("PERIODICITY has no value")
            try:
                periodicity = float(tokens[1])
            except ValueError:
                raise GeomTurboParseError("PERIODICITY value is not numeric")

    sections = {"suction": [], "pressure": []}
    current = None
    i = 0
    while i < len(lines):
        tokens = lines[i].split()
        if tokens and tokens[0] in ("suction", "pressure"):
            current = tokens[0]
        if lines[i].strip().startswith("XYZ"):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j >= len(lines):
                raise GeomTurboParseError("dangling XYZ polyline")
            try:
                declared = int(lines[j].strip())
            except ValueError:
                raise GeomTurboParseError("declared point count is not an integer")
            if declared <= 0:
                raise GeomTurboParseError("declared point count is not positive")
            pts = []
            for k in range(j + 1, j + 1 + declared):
                if k >= len(lines):
                    raise GeomTurboParseError("truncated polyline")
                parts = lines[k].split()
                if len(parts) != 3:
                    raise GeomTurboParseError(
                        f"polyline row {k + 1} is not a (span, Y, Z) triple")
                try:
                    vals = [float(x) for x in parts]
                except ValueError:
                    raise GeomTurboParseError(
                        f"polyline row {k + 1} has a non-numeric value")
                if not all(math.isfinite(v) for v in vals):
                    raise GeomTurboParseError(
                        f"polyline row {k + 1} has a non-finite value",
                        nonfinite=True)
                pts.append(vals)
            if current is None:
                raise GeomTurboParseError("polyline outside suction/pressure block")
            sections[current].append(pts)
            i = j + 1 + declared
        else:
            i += 1

    return {"periodicity": periodicity, "sections": sections}


def curvature_diagnostics(points):
    """Return (max_turn_deg, max_curvature, zero_length_flag)."""
    max_turn = None
    max_curv = None
    zero = False
    for i in range(1, len(points) - 1):
        ax, ay = points[i - 1]
        bx, by = points[i]
        cx, cy = points[i + 1]
        ux, uy = bx - ax, by - ay
        vx, vy = cx - bx, cy - by
        nu = math.hypot(ux, uy)
        nv = math.hypot(vx, vy)
        if nu <= 0.0 or nv <= 0.0:
            zero = True
            continue
        cr = abs(ux * vy - uy * vx)
        dt = ux * vx + uy * vy
        theta = math.atan2(cr, dt)
        length = 0.5 * (nu + nv)
        turn = math.degrees(theta)
        curv = theta / length
        max_turn = turn if max_turn is None else max(max_turn, turn)
        max_curv = curv if max_curv is None else max(max_curv, curv)
    return max_turn, max_curv, zero


def _finalize(row, reasons):
    ordered = [code for code in REASON_ORDER if code in reasons]
    extras = sorted(reasons - set(REASON_ORDER))
    ordered.extend(extras)
    row["reason"] = "OK" if not ordered else ";".join(ordered)
    row["geometry_ok"] = not ordered
    return row


def evaluate_case(record, profile_path, geomturbo_path):
    case_id = (record.get("case_id") or "").strip()
    solidity = float(record["Solidity"])
    row = {col: None for col in CSV_COLUMNS}
    row["case_id"] = case_id
    row["qc_policy_id"] = QC_POLICY_ID
    row["chord_target"] = CHORD_TARGET
    row["calibration_status"] = CALIBRATION_STATUS
    reasons = set()

    profile_exists = profile_path.is_file()
    geom_exists = geomturbo_path.is_file()
    row["profile_exists"] = profile_exists
    row["geomturbo_exists"] = geom_exists
    if not profile_exists:
        reasons.add("PROFILE_MISSING")
    if not geom_exists:
        reasons.add("GEOMTURBO_MISSING")

    # --- profile -----------------------------------------------------------
    profile_rows = None
    if profile_exists:
        try:
            profile_rows = parse_profile(profile_path.read_text(encoding="utf-8"))
            row["profile_parse_ok"] = True
        except (OSError, UnicodeDecodeError):
            row["profile_parse_ok"] = False
            reasons.add("PROFILE_PARSE_ERROR")
        except ProfileParseError as exc:
            row["profile_parse_ok"] = False
            reasons.add("NONFINITE_COORDINATE" if exc.nonfinite
                        else "PROFILE_PARSE_ERROR")
    else:
        row["profile_parse_ok"] = False

    if profile_rows is not None:
        row["finite_ok"] = True
        n = len(profile_rows)
        row["profile_point_count"] = n
        pressure = [(r[0], r[1]) for r in profile_rows]
        suction = [(r[2], r[3]) for r in profile_rows]

        le_err = math.hypot(pressure[0][0] - suction[0][0],
                            pressure[0][1] - suction[0][1])
        te_err = math.hypot(pressure[-1][0] - suction[-1][0],
                            pressure[-1][1] - suction[-1][1])
        row["le_closure_error"] = le_err
        row["te_closure_error"] = te_err

        if le_err != 0.0 or te_err != 0.0:
            reasons.add("LE_TE_CLOSURE_MISMATCH")
        else:
            poly = canonical_polygon(pressure, suction)
            self_int = polygon_self_intersection(poly)
            row["self_intersection"] = self_int
            if self_int:
                reasons.add("SELF_INTERSECTION")

        if (any(pressure[i] == pressure[i + 1] for i in range(n - 1))
                or any(suction[i] == suction[i + 1] for i in range(n - 1))):
            reasons.add("ZERO_LENGTH_SEGMENT")

        if n >= 3:
            interior = [math.hypot(pressure[i][0] - suction[i][0],
                                   pressure[i][1] - suction[i][1])
                        for i in range(1, n - 1)]
            row["min_interior_thickness"] = min(interior)
            row["max_paired_thickness"] = max(interior)
            if min(interior) <= 0.0:
                reasons.add("NONPOSITIVE_INTERIOR_THICKNESS")

    # --- geomTurbo ---------------------------------------------------------
    parsed = None
    if geom_exists:
        try:
            text = geomturbo_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = None
            row["geomturbo_parse_ok"] = False
            reasons.add("GEOMTURBO_PARSE_ERROR")
        if text is not None:
            if geomturbo_missing_markers(text):
                reasons.add("GEOMTURBO_INCOMPLETE")
            try:
                parsed = parse_geomturbo(text)
                row["geomturbo_parse_ok"] = True
            except GeomTurboParseError as exc:
                row["geomturbo_parse_ok"] = False
                reasons.add("NONFINITE_COORDINATE" if exc.nonfinite
                            else "GEOMTURBO_PARSE_ERROR")
    else:
        row["geomturbo_parse_ok"] = False

    if parsed is not None:
        if row["finite_ok"] is None:
            row["finite_ok"] = True
        per = parsed["periodicity"]
        row["periodicity"] = per
        expected = 0.06 / solidity
        row["expected_periodicity"] = expected
        if per is None or not math.isfinite(per) or per <= 0.0:
            reasons.add("INVALID_PERIODICITY")
        else:
            row["periodicity_error_abs"] = abs(per - expected)

        suction_sections = parsed["sections"]["suction"]
        pressure_sections = parsed["sections"]["pressure"]
        if len(suction_sections) != 2 or len(pressure_sections) != 2:
            reasons.add("GEOMTURBO_INCOMPLETE")
        else:
            s1, s2 = suction_sections
            p1, p2 = pressure_sections
            spans = [s1[0][0], s2[0][0], p1[0][0], p2[0][0]]
            span_constant = all(len({r[0] for r in sec}) == 1
                                for sec in (s1, s2, p1, p2))
            yz_equal = ([tuple(r[1:]) for r in s1] == [tuple(r[1:]) for r in s2]
                        and [tuple(r[1:]) for r in p1] == [tuple(r[1:]) for r in p2])
            span_pair_ok = (spans[0] == spans[2] and spans[1] == spans[3]
                            and spans[0] != spans[1])
            row["span_min"] = min(spans)
            row["span_max"] = max(spans)
            row["span_section_coordinate_consistent"] = bool(
                span_constant and yz_equal and span_pair_ok)
            if not (span_constant and yz_equal and span_pair_ok):
                reasons.add("SPAN_SECTION_MISMATCH")

            blade_p = [(r[1], r[2]) for r in p1]
            blade_s = [(r[1], r[2]) for r in s1]

            chord = math.hypot(blade_p[-1][0] - blade_p[0][0],
                               blade_p[-1][1] - blade_p[0][1])
            row["chord"] = chord
            row["chord_error_abs"] = abs(chord - CHORD_TARGET)
            row["chord_error_rel"] = abs(chord - CHORD_TARGET) / CHORD_TARGET
            if not (math.isfinite(chord) and chord > 0.0):
                reasons.add("INVALID_CHORD")

            poly = canonical_polygon(blade_p, blade_s)
            ys = [q[0] for q in poly]
            extent = max(ys) - min(ys)
            row["blade_tangential_extent"] = extent
            if per is not None and math.isfinite(per):
                row["envelope_clearance"] = per - extent

            if per is not None and math.isfinite(per) and per > 0.0:
                plus = [(y + per, z) for (y, z) in poly]
                minus = [(y - per, z) for (y, z) in poly]
                adjacent = (polygon_pair_intersects(poly, plus)
                            or polygon_pair_intersects(poly, minus))
                row["adjacent_blade_intersection"] = adjacent
                if adjacent:
                    reasons.add("ADJACENT_BLADE_INTERSECTION")
                gap = min(polygon_pair_min_distance(poly, plus),
                          polygon_pair_min_distance(poly, minus))
                row["min_gap"] = gap
                if not (math.isfinite(gap) and gap > 0.0):
                    reasons.add("NONPOSITIVE_MIN_GAP")

            p_turn, p_curv, p_zero = curvature_diagnostics(blade_p)
            s_turn, s_curv, s_zero = curvature_diagnostics(blade_s)
            row["pressure_max_turn_angle_deg"] = p_turn
            row["suction_max_turn_angle_deg"] = s_turn
            row["pressure_max_discrete_curvature"] = p_curv
            row["suction_max_discrete_curvature"] = s_curv
            if p_zero or s_zero:
                reasons.add("ZERO_LENGTH_SEGMENT")

    return _finalize(row, reasons)


# ---------------------------------------------------------------------------
# Input / output / CLI
# ---------------------------------------------------------------------------
def _load_and_validate_csv(path: Path):
    if not path.is_file():
        raise CliError(f"input CSV not found or not a file: {path}")
    try:
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
    except OSError as exc:
        raise CliError(f"input CSV unreadable: {path}: {exc}")

    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        raise CliError("input CSV missing required column(s): " + ", ".join(missing))
    if not rows:
        raise CliError("input CSV has no data rows")

    seen = set()
    for lineno, record in enumerate(rows, start=2):
        case_id = (record.get("case_id") or "").strip()
        if not CASE_ID_RE.match(case_id):
            raise CliError(
                f"row {lineno}: invalid case_id {case_id!r} "
                "(expected pattern: C followed by 6 digits)")
        if case_id in seen:
            raise CliError(f"row {lineno}: duplicate case_id {case_id!r}")
        seen.add(case_id)
        for col in NUMERIC_COLUMNS:
            raw = record.get(col)
            try:
                value = float(raw)
            except (TypeError, ValueError):
                raise CliError(f"row {lineno} ({case_id}): {col}={raw!r} is not a float")
            if not math.isfinite(value):
                raise CliError(f"row {lineno} ({case_id}): {col}={raw!r} is not finite")
        xthick = float(record["Xthick"])
        if not (0.0 < xthick < 1.0):
            raise CliError(f"row {lineno} ({case_id}): Xthick must satisfy "
                           f"0 < Xthick < 1, got {xthick!r}")
        solidity = float(record["Solidity"])
        if solidity <= 0.0:
            raise CliError(f"row {lineno} ({case_id}): Solidity must be > 0, "
                           f"got {solidity!r}")
    return rows


def _select_rows(rows, requested_case_ids):
    if not requested_case_ids:
        return list(rows)
    requested = set(requested_case_ids)
    available = {(r.get("case_id") or "").strip() for r in rows}
    missing = sorted(requested - available)
    if missing:
        raise CliError("requested --case-id not present in input CSV: "
                       + ", ".join(missing))
    return [r for r in rows if (r.get("case_id") or "").strip() in requested]


def _write_report_atomic(output_path: Path, rows) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(output_path.parent),
                                    prefix=".tmp-qc-" + output_path.name + "-",
                                    suffix=".part")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({c: _fmt(row.get(c)) for c in CSV_COLUMNS})
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, output_path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def run(args):
    input_path = Path(args.input)
    geometry_root = Path(args.geometry)
    output_path = Path(args.output)

    rows = _load_and_validate_csv(input_path)
    selected = _select_rows(rows, args.case_ids)

    if not args.dry_run and output_path.exists() and not args.overwrite:
        raise CliError(f"output already exists (use --overwrite): {output_path}")

    results = []
    missing_artifact_count = 0
    parse_failure_count = 0
    self_intersection_count = 0
    adjacent_intersection_count = 0

    for record in selected:
        case_id = (record.get("case_id") or "").strip()
        profile_path = geometry_root / "profiles" / f"{case_id}.dat"
        geomturbo_path = geometry_root / "geomturbo" / f"{case_id}.geomTurbo"
        row = evaluate_case(record, profile_path, geomturbo_path)
        results.append(row)
        _emit({
            "type": "case",
            "case_id": case_id,
            "geometry_ok": bool(row["geometry_ok"]),
            "reason": row["reason"],
        })
        if row["profile_exists"] is False or row["geomturbo_exists"] is False:
            missing_artifact_count += 1
        if row["profile_parse_ok"] is False or row["geomturbo_parse_ok"] is False:
            parse_failure_count += 1
        if row["self_intersection"] is True:
            self_intersection_count += 1
        if row["adjacent_blade_intersection"] is True:
            adjacent_intersection_count += 1

    pass_count = sum(1 for r in results if r["geometry_ok"])
    fail_count = len(results) - pass_count

    # Write the report before announcing the summary, so an operational
    # report-writing failure surfaces as exit 4 without a misleading summary.
    if not args.dry_run:
        _write_report_atomic(output_path, results)

    _emit({
        "type": "summary",
        "selected_count": len(results),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "missing_artifact_count": missing_artifact_count,
        "parse_failure_count": parse_failure_count,
        "self_intersection_count": self_intersection_count,
        "adjacent_intersection_count": adjacent_intersection_count,
        "output_path": str(output_path),
        "dry_run": bool(args.dry_run),
        "qc_policy_id": QC_POLICY_ID,
        "calibration_status": CALIBRATION_STATUS,
    })
    return EXIT_OK


def build_parser():
    parser = argparse.ArgumentParser(
        prog="03_geometry_qc.py",
        description="Geometry QC v1 (hard gates) for generated artifacts.")
    parser.add_argument("--input", required=True, metavar="PATH",
                        help="input master design CSV")
    parser.add_argument("--geometry", required=True, metavar="PATH",
                        help="geometry root (profiles/ + geomturbo/)")
    parser.add_argument("--output", required=True, metavar="PATH",
                        help="output QC CSV report path")
    parser.add_argument("--case-id", dest="case_ids", action="append", default=[],
                        metavar="CASE_ID", help="select case_id (repeatable)")
    parser.add_argument("--dry-run", action="store_true",
                        help="run QC and report without writing the CSV")
    parser.add_argument("--overwrite", action="store_true",
                        help="allow replacing an existing report")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_CLI
    except Exception as exc:  # noqa: BLE001 - operational failure -> exit 4
        print(f"error: QC operational failure: {exc.__class__.__name__}: {exc}",
              file=sys.stderr)
        return EXIT_OPERATIONAL


if __name__ == "__main__":
    sys.exit(main())
