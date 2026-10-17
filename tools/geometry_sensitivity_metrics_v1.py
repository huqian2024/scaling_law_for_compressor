"""Geometry metrics + hard-QC helpers for Parameter Sensitivity V1.

All definitions are frozen in
``analysis/geometry_review/parameter_sensitivity_v1_100cases/screening_criteria.yaml``.
This module implements them and reuses the **frozen** geometric kernel of
``code/03_geometry_qc.py`` (read-only import, no modification).

No plotting, no file writes, no CFD.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
CODE = REPO / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))

import geometry_parametric_exploratory_v1 as gen  # noqa: E402

QC_POLICY_ID = "geometry_qc_v1_hard"
CHORD_TARGET = 0.06


def _load_qc_module():
    path = CODE / "03_geometry_qc.py"
    spec = importlib.util.spec_from_file_location("_frozen_geometry_qc_v1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


QC = _load_qc_module()


# ---------------------------------------------------------------------------
# Basic geometry utilities
# ---------------------------------------------------------------------------
def canonical_polygon(geom: dict) -> np.ndarray:
    """Closed blade polygon (frozen QC contract section 7), high precision."""
    pressure = np.column_stack([geom["xp1"], geom["yp1"]])
    suction = np.column_stack([geom["xs1"], geom["ys1"]])
    poly = QC.canonical_polygon([tuple(r) for r in pressure],
                                [tuple(r) for r in suction])
    return np.asarray(poly, dtype=float)


def point_to_polyline_distance(points, poly) -> np.ndarray:
    """Distance from every point to the closed polyline (segment based)."""
    pts = np.asarray(points, dtype=float)
    a = np.asarray(poly, dtype=float)
    b = np.roll(a, -1, axis=0)
    d = QC._pt_seg_dist(pts[:, None, :], a[None, :, :], b[None, :, :])
    return d.min(axis=1)


def symmetric_contour_metrics(poly_case, poly_base, base_chord: float) -> dict:
    d_case = point_to_polyline_distance(poly_case, poly_base)
    d_base = point_to_polyline_distance(poly_base, poly_case)
    pooled = np.concatenate([d_case, d_base])
    return {
        "contour_rms_dev_norm": float(np.sqrt(np.mean(pooled ** 2)) / base_chord),
        "contour_max_dev_norm": float(np.max(pooled) / base_chord),
        "contour_rms_case_to_base_norm": float(
            np.sqrt(np.mean(d_case ** 2)) / base_chord),
        "contour_max_case_to_base_norm": float(np.max(d_case) / base_chord),
    }


def align_contour(poly, le, te, base_le, base_te, base_chord, case_chord):
    """Translate LE->base LE, rotate chord->base chord, scale chord->base chord."""
    pts = np.asarray(poly, dtype=float).copy()
    pts -= np.asarray(le, dtype=float)
    ang_case = math.atan2(te[1] - le[1], te[0] - le[0])
    ang_base = math.atan2(base_te[1] - base_le[1], base_te[0] - base_le[0])
    c, s = math.cos(ang_base - ang_case), math.sin(ang_base - ang_case)
    rot = np.array([[c, -s], [s, c]])
    pts = pts @ rot.T
    pts *= base_chord / case_chord
    pts += np.asarray(base_le, dtype=float)
    return pts


def closed_arc_distance(poly, vertex: int) -> np.ndarray:
    """Arc length along the closed polygon from ``vertex`` to every point."""
    pts = np.asarray(poly, dtype=float)
    closed = np.vstack([pts, pts[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(s[-1])
    d = np.abs(s[:len(pts)] - s[vertex])
    return np.minimum(d, total - d)


def edge_indices(poly, vertex: int, halfwidth: float) -> np.ndarray:
    return np.where(closed_arc_distance(poly, vertex) <= halfwidth)[0]


def ordered_le_points(poly, k: int) -> np.ndarray:
    """Suction side -> LE -> pressure side ordering for curvature."""
    n = len(poly)
    idx_s = [(n - 1 - i) for i in range(k)][::-1]      # S_k .. S1
    idx_p = list(range(0, k))                           # P0 .. P_{k-1}
    return np.asarray(poly)[idx_s + idx_p]


def ordered_te_points(poly, vertex: int, k: int) -> np.ndarray:
    idx = list(range(vertex - k + 1, vertex + k))
    return np.asarray(poly)[idx]


def fit_circle(points, residual_max_rel=0.05, min_span_deg=45.0) -> dict:
    """Kasa algebraic circle fit with explicit validity flags."""
    pts = np.asarray(points, dtype=float)
    out = {
        "radius": None, "cx": None, "cy": None,
        "residual_rms": None, "residual_rel": None, "span_deg": None,
        "n_points": int(len(pts)), "fit_ok": False,
    }
    if len(pts) < 5:
        return out
    x, y = pts[:, 0], pts[:, 1]
    A = np.column_stack([2.0 * x, 2.0 * y, np.ones(len(x))])
    b = x * x + y * y
    try:
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    except np.linalg.LinAlgError:
        return out
    cx, cy = float(sol[0]), float(sol[1])
    radicand = float(sol[2] + cx * cx + cy * cy)
    if not math.isfinite(radicand) or radicand <= 0.0:
        return out
    radius = math.sqrt(radicand)
    d = np.hypot(x - cx, y - cy)
    residual = float(np.sqrt(np.mean((d - radius) ** 2)))
    angles = np.unwrap(np.arctan2(y - cy, x - cx))
    span = float(np.degrees(angles.max() - angles.min()))
    rel = residual / radius if radius > 0 else float("inf")
    out.update({
        "radius": float(radius), "cx": cx, "cy": cy,
        "residual_rms": residual, "residual_rel": float(rel),
        "span_deg": span,
    })
    out["fit_ok"] = bool(
        math.isfinite(radius) and radius > 0.0
        and rel <= residual_max_rel and span >= min_span_deg)
    return out


def _dedup(points, tol=1e-12) -> np.ndarray:
    pts = np.asarray(points, dtype=float)
    if len(pts) == 0:
        return pts
    keep = [0]
    for i in range(1, len(pts)):
        if np.linalg.norm(pts[i] - pts[keep[-1]]) > tol:
            keep.append(i)
    return pts[keep]


def spline_curvature_max(points, s=1e-6, nsample=400) -> float:
    """Max |curvature| of a cubic B-spline through an ordered open polyline."""
    from scipy.interpolate import splprep, splev

    pts = _dedup(points)
    if len(pts) < 6:
        return float("nan")
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    u = np.concatenate([[0.0], np.cumsum(seg)])
    if u[-1] <= 0.0:
        return float("nan")
    u /= u[-1]
    try:
        tck, _ = splprep([pts[:, 0], pts[:, 1]], u=u, s=s, k=3)
        uu = np.linspace(0.0, 1.0, nsample)
        dx, dy = splev(uu, tck, der=1)
        ddx, ddy = splev(uu, tck, der=2)
    except Exception:
        return float("nan")
    denom = (np.asarray(dx) ** 2 + np.asarray(dy) ** 2) ** 1.5
    numer = np.abs(np.asarray(dx) * np.asarray(ddy)
                   - np.asarray(dy) * np.asarray(ddx))
    with np.errstate(divide="ignore", invalid="ignore"):
        kappa = numer / denom
    if not np.all(np.isfinite(kappa)):
        return float("nan")
    return float(np.max(kappa))


def curvature_stats(points, stability_max=0.25) -> dict:
    """Curvature + resolution-stability test (s in {0,1e-8,1e-6}, n in {200,400})."""
    values = []
    for s in (0.0, 1e-8, 1e-6):
        for n in (200, 400):
            values.append(spline_curvature_max(points, s=s, nsample=n))
    official = spline_curvature_max(points, s=1e-6, nsample=400)
    arr = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(arr)) or not math.isfinite(official):
        return {"curvature_max": float("nan"), "curvature_stability_rel": float("nan"),
                "curvature_reliable": False}
    mean = float(np.mean(arr))
    stability = float((np.max(arr) - np.min(arr)) / mean) if mean > 0 else float("nan")
    return {
        "curvature_max": float(official),
        "curvature_stability_rel": stability,
        "curvature_reliable": bool(math.isfinite(stability) and stability <= stability_max),
    }


# ---------------------------------------------------------------------------
# Independent (baseline-free) metrics
# ---------------------------------------------------------------------------
def meanline_metrics(geom: dict) -> dict:
    """Exact analytic meanline curvature (legacy polynomial derivatives)."""
    xc = geom["xc"]
    sc = geom["sc"]
    c = geom["coefficients"]
    Xmean = geom["params"]["Xmean"]
    left = xc <= Xmean
    dsc = np.where(
        left,
        3.0 * c["a1"] * xc ** 2 + 2.0 * c["a2"] * xc + c["a3"],
        -3.0 * c["a5"] * (1.0 - xc) ** 2 - 2.0 * c["a6"] * (1.0 - xc) - c["a7"],
    )
    kappa = np.abs(dsc) / (1.0 + sc ** 2) ** 1.5
    angle_deg = np.degrees(np.arctan(sc))

    def at_x(target):
        i = int(np.clip(np.searchsorted(xc, target), 0, len(xc) - 1))
        return float(kappa[i])

    return {
        "meanline_curvature_max": float(np.max(kappa)),
        "meanline_curvature_rms": float(np.sqrt(np.mean(kappa ** 2))),
        "meanline_curvature_xc010": at_x(0.10),
        "meanline_curvature_xc050": at_x(0.50),
        "meanline_curvature_xc090": at_x(0.90),
        "meanline_angle_le_deg": float(angle_deg[0]),
        "meanline_angle_te_deg": float(angle_deg[-1]),
        "meanline_angle_max_abs_deg": float(np.max(np.abs(angle_deg))),
        "meanline_angle_range_deg": float(np.max(angle_deg) - np.min(angle_deg)),
    }


def _edge_arc_points(geom: dict, side: str) -> np.ndarray:
    """Ordered actual contour points of the inserted LE/TE arc.

    Legacy construction: each surface array starts with ``Ncirc`` LE-arc points
    and ends with ``Ncirc`` TE-arc points.  ``P0 == S0`` (LE) and ``Pn == Sn``
    (TE), so the canonical polygon omits ``S0`` / ``Sn``.  The returned ordering
    is continuous along the contour: suction -> LE -> pressure for the LE, and
    pressure -> TE -> suction for the TE.
    """
    ncirc = int(gen.FIXED_CONSTANTS["Ncirc"])
    p = np.column_stack([geom["xp1"], geom["yp1"]])
    s = np.column_stack([geom["xs1"], geom["ys1"]])
    if side == "le":
        return np.vstack([s[:ncirc][::-1], p[1:ncirc]])
    return np.vstack([p[-ncirc:], s[-ncirc:][-2::-1]])


def edge_metrics(geom: dict, poly: np.ndarray, side: str, thr: dict) -> dict:
    """Fitted edge radius + arc curvature + (separately) a 0.05-chord region."""
    chord = geom["chord_norm"]
    n_pressure = len(geom["xp1"])
    vertex = 0 if side == "le" else n_pressure - 1
    region_idx = edge_indices(poly, vertex, thr["edge_region_chord"] * chord)
    arc = _edge_arc_points(geom, side)
    fit = fit_circle(arc,
                     residual_max_rel=thr["circle_fit_residual_max_rel"],
                     min_span_deg=thr["circle_fit_min_span_deg"])
    curv = curvature_stats(arc, stability_max=thr["curvature_stability_max"])
    return {
        f"{side}_radius_fitted_norm": fit["radius"],
        f"{side}_fit_residual_rel": fit["residual_rel"],
        f"{side}_fit_span_deg": fit["span_deg"],
        f"{side}_fit_n_points": fit["n_points"],
        f"{side}_fit_ok": fit["fit_ok"],
        f"{side}_curvature_max": curv["curvature_max"],
        f"{side}_curvature_stability_rel": curv["curvature_stability_rel"],
        f"{side}_curvature_reliable": curv["curvature_reliable"],
        f"_{side}_region_idx": region_idx,
    }


def cascade_metrics(geom: dict) -> dict:
    """Pitch / clearance metrics in metres (frozen QC geometry conventions)."""
    solidity = float(geom["params"]["Solidity"])
    chord_m = CHORD_TARGET
    periodicity = chord_m / solidity
    scale = chord_m / geom["chord_norm"]
    poly_m = canonical_polygon(geom) * scale

    ys = poly_m[:, 1]
    extent = float(np.max(ys) - np.min(ys))
    plus = poly_m + np.array([0.0, periodicity])
    minus = poly_m - np.array([0.0, periodicity])
    adjacent = bool(QC.polygon_pair_intersects(poly_m, plus)
                    or QC.polygon_pair_intersects(poly_m, minus))
    gap = min(QC.polygon_pair_min_distance(poly_m, plus),
              QC.polygon_pair_min_distance(poly_m, minus))
    return {
        "periodicity_m": float(periodicity),
        "chord_m": float(chord_m),
        "pitch_to_chord": float(periodicity / chord_m),
        "min_gap_m": float(gap),
        "min_gap_to_pitch": float(gap / periodicity),
        "envelope_clearance_m": float(periodicity - extent),
        "blade_tangential_extent_m": extent,
        "adjacent_blade_intersection": adjacent,
    }


def independent_metrics(geom: dict, thr: dict) -> dict:
    """Baseline-free metrics + internal arrays used by ``compare_metrics``."""
    poly = canonical_polygon(geom)
    out = {
        "chord_norm": float(geom["chord_norm"]),
        "chord_angle_deg": float(geom["chord_angle_deg"]),
        "max_thickness_norm": float(geom["max_thickness_norm"]),
        "max_thickness_xc": float(geom["thick_max_xc"]),
        "thick_min_half_norm": float(geom["thick_min"]),
        "thick_max_half_norm": float(geom["thick_max"]),
        "meanline_max_camber_norm": float(geom["meanline_max_camber_norm"]),
        "le_model_radius_norm": float(geom["r1"]),
        "te_model_radius_norm": float(geom["r2"]),
        "le_junction_angle_jump_deg": float(geom["le_junction_angle_jump_deg"]),
        "te_junction_angle_jump_deg": float(geom["te_junction_angle_jump_deg"]),
        "le_arc_span_deg": float(geom["le_arc_span_deg"]),
        "te_arc_span_deg": float(geom["te_arc_span_deg"]),
    }
    out.update(meanline_metrics(geom))
    out.update(edge_metrics(geom, poly, "le", thr))
    out.update(edge_metrics(geom, poly, "te", thr))
    out.update(cascade_metrics(geom))
    out["_poly"] = poly
    out["_le"] = (float(geom["xp1"][0]), float(geom["yp1"][0]))
    out["_te"] = (float(geom["xp1"][-1]), float(geom["yp1"][-1]))
    return out


# ---------------------------------------------------------------------------
# Deviation metrics against the baseline blade
# ---------------------------------------------------------------------------
def _interp(x, y, target):
    return float(np.interp(target, x, y))


def compare_metrics(geom: dict, base_geom: dict, base_ind: dict, thr: dict) -> dict:
    poly = canonical_polygon(geom)
    base_poly = base_ind["_poly"]
    base_chord = float(base_geom["chord_norm"])
    out = symmetric_contour_metrics(poly, base_poly, base_chord)

    aligned = align_contour(poly, (geom["xp1"][0], geom["yp1"][0]),
                            (geom["xp1"][-1], geom["yp1"][-1]),
                            base_ind["_le"], base_ind["_te"],
                            base_chord, geom["chord_norm"])
    aligned_m = symmetric_contour_metrics(aligned, base_poly, base_chord)
    out["contour_rms_dev_aligned_norm"] = aligned_m["contour_rms_dev_norm"]
    out["contour_max_dev_aligned_norm"] = aligned_m["contour_max_dev_norm"]

    # index-matched surface offsets (parameter mapping, not geometric matching)
    dp = np.hypot(geom["xp1"] - base_geom["xp1"], geom["yp1"] - base_geom["yp1"])
    ds = np.hypot(geom["xs1"] - base_geom["xs1"], geom["ys1"] - base_geom["ys1"])
    out["pressure_rms_dev_norm"] = float(np.sqrt(np.mean(dp ** 2)) / base_chord)
    out["pressure_max_dev_norm"] = float(np.max(dp) / base_chord)
    out["suction_rms_dev_norm"] = float(np.sqrt(np.mean(ds ** 2)) / base_chord)
    out["suction_max_dev_norm"] = float(np.max(ds) / base_chord)

    # meanline / thickness distributions at identical xc indices
    d_yc = geom["yc"] - base_geom["yc"]
    d_thick = geom["thick"] - base_geom["thick"]
    xc = geom["xc"]
    out["meanline_rms_dev_norm"] = float(
        np.sqrt(np.mean(d_yc ** 2)) / base_chord)
    out["meanline_max_dev_norm"] = float(np.max(np.abs(d_yc)) / base_chord)
    out["thickness_rms_dev_norm"] = float(
        np.sqrt(np.mean(d_thick ** 2)) / base_chord)
    out["thickness_max_dev_norm"] = float(np.max(np.abs(d_thick)) / base_chord)
    masks = {
        "front": xc <= 0.3,
        "mid": (xc > 0.3) & (xc <= 0.7),
        "rear": xc > 0.7,
    }
    for name, mask in masks.items():
        out[f"thickness_{name}_rms_dev_norm"] = float(
            np.sqrt(np.mean(d_thick[mask] ** 2)) / base_chord)
        out[f"thickness_{name}_max_dev_norm"] = float(
            np.max(np.abs(d_thick[mask])) / base_chord)

    out["max_thickness_change_norm"] = float(
        (geom["max_thickness_norm"] - base_geom["max_thickness_norm"]) / base_chord)
    out["max_thickness_xc_change"] = float(
        geom["thick_max_xc"] - base_geom["thick_max_xc"])
    out["chord_change_rel"] = float(
        (geom["chord_norm"] - base_geom["chord_norm"]) / base_geom["chord_norm"])
    out["chord_angle_change_deg"] = float(
        geom["chord_angle_deg"] - base_geom["chord_angle_deg"])
    out["chord_angle_change_rad"] = float(np.radians(out["chord_angle_change_deg"]))

    ang = np.degrees(np.arctan(geom["sc"]))
    ang_base = np.degrees(np.arctan(base_geom["sc"]))
    out["meanline_tangent_rms_dev_deg"] = float(
        np.sqrt(np.mean((ang - ang_base) ** 2)))
    out["meanline_tangent_max_dev_deg"] = float(np.max(np.abs(ang - ang_base)))
    out["meanline_curvature_change_abs"] = float(
        abs(geom["_ind"]["meanline_curvature_max"]
            - base_ind["meanline_curvature_max"]) * base_chord)
    out["meanline_curvature_rms_change_abs"] = float(
        abs(geom["_ind"]["meanline_curvature_rms"]
            - base_ind["meanline_curvature_rms"]) * base_chord)

    # edge radii (only when BOTH circle fits are valid; never filled with models)
    for side in ("le", "te"):
        r_new = geom["_ind"][f"{side}_radius_fitted_norm"]
        r_base = base_ind[f"{side}_radius_fitted_norm"]
        ok_new = geom["_ind"][f"{side}_fit_ok"]
        ok_base = base_ind[f"{side}_fit_ok"]
        if ok_new and ok_base and r_base and r_base > 0:
            out[f"{side}_radius_change_rel"] = float((r_new - r_base) / r_base)
        else:
            out[f"{side}_radius_change_rel"] = float("nan")

        idx_new = geom["_ind"][f"_{side}_region_idx"]
        idx_base = base_ind[f"_{side}_region_idx"]
        d_new = point_to_polyline_distance(poly[idx_new], base_poly)
        d_base = point_to_polyline_distance(base_poly[idx_base], poly)
        pooled = np.concatenate([d_new, d_base])
        out[f"{side}_region_rms_dev_norm"] = float(
            np.sqrt(np.mean(pooled ** 2)) / base_chord)
        out[f"{side}_region_max_dev_norm"] = float(np.max(pooled) / base_chord)

    # cascade changes
    if base_ind["min_gap_m"] > 0:
        out["min_gap_change_rel"] = float(
            (geom["_ind"]["min_gap_m"] - base_ind["min_gap_m"])
            / base_ind["min_gap_m"])
    else:
        out["min_gap_change_rel"] = float("nan")
    out["min_gap_change_m"] = float(
        geom["_ind"]["min_gap_m"] - base_ind["min_gap_m"])
    out["periodicity_change_rel"] = float(
        (geom["_ind"]["periodicity_m"] - base_ind["periodicity_m"])
        / base_ind["periodicity_m"])

    # signed response signature features (used for redundancy analysis)
    for x in (0.25, 0.50, 0.75):
        key = f"{int(round(x * 100)):03d}"
        out[f"signed_meanline_{key}"] = float(
            (_interp(xc, geom["yc"], x) - _interp(xc, base_geom["yc"], x))
            / base_chord)
    for x in (0.10, 0.50, 0.90):
        key = f"{int(round(x * 100)):03d}"
        out[f"signed_thickness_{key}"] = float(
            (_interp(xc, geom["thick"], x) - _interp(xc, base_geom["thick"], x))
            / base_chord)
    out["signed_le_radius_rel"] = out["le_radius_change_rel"]
    out["signed_te_radius_rel"] = out["te_radius_change_rel"]
    out["signed_chord_angle_rad"] = out["chord_angle_change_rad"]
    out["signed_chord_len_rel"] = out["chord_change_rel"]
    out["signed_min_gap_rel"] = out["min_gap_change_rel"]
    for x in (0.10, 0.50, 0.90):
        key = f"{int(round(x * 100)):03d}"
        out[f"signed_meanline_kappa_{key}"] = float(
            (geom["_ind"][f"meanline_curvature_xc{key}"]
             - base_ind[f"meanline_curvature_xc{key}"]) * base_chord)
    return out


# ---------------------------------------------------------------------------
# Hard QC (frozen gates + two explicit experiment-only diagnostics)
# ---------------------------------------------------------------------------
QC_REASON_ORDER = [
    "NONFINITE_COORDINATE", "LE_TE_CLOSURE_MISMATCH", "ZERO_LENGTH_SEGMENT",
    "SELF_INTERSECTION", "NONPOSITIVE_INTERIOR_THICKNESS",
    "NONPOSITIVE_HALF_THICKNESS", "INVALID_PERIODICITY",
    "ADJACENT_BLADE_INTERSECTION", "NONPOSITIVE_MIN_GAP", "INVALID_CHORD",
    "NONFINITE_CURVATURE",
]


def hard_qc(geom: dict, ind: dict, thr: dict) -> dict:
    """Replicate the frozen hard gates on high-precision arrays.

    The two extra reason codes (``NONPOSITIVE_HALF_THICKNESS`` and
    ``NONFINITE_CURVATURE``) are experiment-only diagnostics: the frozen V1 QC
    does not gate on them, but this experiment must record them explicitly.
    """
    reasons = set()

    arrays = [geom[k] for k in ("xp1", "yp1", "xs1", "ys1", "xc", "yc", "thick", "sc")]
    finite_ok = bool(all(np.all(np.isfinite(a)) for a in arrays))
    if not finite_ok:
        reasons.add("NONFINITE_COORDINATE")

    n = len(geom["xp1"])
    pressure = np.column_stack([geom["xp1"], geom["yp1"]])
    suction = np.column_stack([geom["xs1"], geom["ys1"]])
    le_err = float(np.hypot(*(pressure[0] - suction[0])))
    te_err = float(np.hypot(*(pressure[-1] - suction[-1])))
    if le_err != 0.0 or te_err != 0.0:
        reasons.add("LE_TE_CLOSURE_MISMATCH")

    self_int = None
    if le_err == 0.0 and te_err == 0.0:
        self_int = bool(QC.polygon_self_intersection(ind["_poly"]))
        if self_int:
            reasons.add("SELF_INTERSECTION")

    zero_len = bool(
        any(tuple(pressure[i]) == tuple(pressure[i + 1]) for i in range(n - 1))
        or any(tuple(suction[i]) == tuple(suction[i + 1]) for i in range(n - 1)))
    if zero_len:
        reasons.add("ZERO_LENGTH_SEGMENT")

    interior = np.linalg.norm(pressure[1:-1] - suction[1:-1], axis=1)
    min_int = float(np.min(interior)) if len(interior) else float("nan")
    max_int = float(np.max(interior)) if len(interior) else float("nan")
    if not math.isfinite(min_int) or min_int <= 0.0:
        reasons.add("NONPOSITIVE_INTERIOR_THICKNESS")

    min_half = float(np.min(geom["thick"]))
    if not math.isfinite(min_half) or min_half <= 0.0:
        reasons.add("NONPOSITIVE_HALF_THICKNESS")

    per = ind["periodicity_m"]
    if not (math.isfinite(per) and per > 0.0):
        reasons.add("INVALID_PERIODICITY")
    if ind["adjacent_blade_intersection"]:
        reasons.add("ADJACENT_BLADE_INTERSECTION")
    if not (math.isfinite(ind["min_gap_m"]) and ind["min_gap_m"] > 0.0):
        reasons.add("NONPOSITIVE_MIN_GAP")
    if not (math.isfinite(geom["chord_norm"]) and geom["chord_norm"] > 0.0):
        reasons.add("INVALID_CHORD")

    curvature_values = [ind["le_curvature_max"], ind["te_curvature_max"],
                        ind["meanline_curvature_max"]]
    curvature_finite = bool(all(math.isfinite(v) for v in curvature_values))
    if not curvature_finite:
        reasons.add("NONFINITE_CURVATURE")

    ordered = [c for c in QC_REASON_ORDER if c in reasons]
    return {
        "hard_qc_status": "FAIL" if ordered else "PASS",
        "qc_reason": ";".join(ordered) if ordered else "OK",
        "finite_ok": finite_ok,
        "self_intersection": self_int,
        "zero_length_segment": zero_len,
        "min_interior_thickness": min_int,
        "max_paired_thickness": max_int,
        "le_closure_error": le_err,
        "te_closure_error": te_err,
        "min_half_thickness_norm": min_half,
        "negative_half_thickness": bool(min_half <= 0.0),
        "curvature_finite": curvature_finite,
        "junction_jump_warning": bool(
            ind["le_junction_angle_jump_deg"] > thr["junction_jump_diagnostic_deg"]
            or ind["te_junction_angle_jump_deg"] > thr["junction_jump_diagnostic_deg"]),
    }


def serialization_noise_floor(geom: dict) -> dict:
    """Contour change caused ONLY by the legacy 4-decimal text serialization."""
    text = gen.serialize_profile(geom)
    rows = [[float(v) for v in ln.split()] for ln in text.splitlines() if ln.strip()]
    pressure = [(r[0], r[1]) for r in rows]
    suction = [(r[2], r[3]) for r in rows]
    poly_rounded = np.asarray(QC.canonical_polygon(pressure, suction), dtype=float)
    m = symmetric_contour_metrics(poly_rounded, canonical_polygon(geom),
                                 geom["chord_norm"])
    return {
        "contour_rms_norm": m["contour_rms_dev_norm"],
        "contour_max_norm": m["contour_max_dev_norm"],
    }


def compute_case_metrics(geom: dict, base_geom: dict, base_ind: dict,
                         thr: dict):
    """Return ``(flat_metrics, independent_metrics)`` for one generated case."""
    ind = independent_metrics(geom, thr)
    geom_with_ind = dict(geom)
    geom_with_ind["_ind"] = ind
    comp = compare_metrics(geom_with_ind, base_geom, base_ind, thr)
    qc = hard_qc(geom_with_ind, ind, thr)
    flat = {}
    flat.update(comp)
    flat.update({k: v for k, v in ind.items() if not k.startswith("_")})
    flat.update(qc)
    return flat, ind


def frozen_qc_crosscheck(case_id: str, params: dict, profile_text: str,
                         geomturbo_text: str, tmpdir) -> dict:
    """Run the FROZEN ``code/03_geometry_qc.py`` on temp artifacts.

    The artifacts live in a temporary directory outside the experiment output
    directory and are deleted by the caller.  This is a read-only cross-check of
    the experiment's hard-QC implementation against the frozen policy.
    """
    from pathlib import Path as _Path

    tmp = _Path(tmpdir)
    (tmp / "profiles").mkdir(parents=True, exist_ok=True)
    (tmp / "geomturbo").mkdir(parents=True, exist_ok=True)
    profile_path = tmp / "profiles" / f"{case_id}.dat"
    geom_path = tmp / "geomturbo" / f"{case_id}.geomTurbo"
    profile_path.write_text(profile_text, encoding="utf-8")
    geom_path.write_text(geomturbo_text, encoding="utf-8")
    record = {
        "case_id": case_id,
        "Xthick": params["Xthick"],
        "Tmax": params["Tmax"],
        "Metal2": params["Metal2"],
        "Solidity": params["Solidity"],
        "Incidence": 0.0,
        "Mach": 0.5,
        "range_id": "parameter_sensitivity_v1",
        "sampling_id": "deterministic_v1",
    }
    try:
        row = QC.evaluate_case(record, profile_path, geom_path)
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "frozen_qc_status": "ERROR",
            "frozen_qc_reason": f"{type(exc).__name__}: {exc}",
            "frozen_qc_policy_id": QC_POLICY_ID,
        }
    return {
        "frozen_qc_status": "PASS" if row["geometry_ok"] else "FAIL",
        "frozen_qc_reason": row["reason"],
        "frozen_qc_policy_id": row["qc_policy_id"],
        "frozen_qc_min_gap_m": row["min_gap"],
        "frozen_qc_periodicity_m": row["periodicity"],
        "frozen_qc_chord_m": row["chord"],
    }
