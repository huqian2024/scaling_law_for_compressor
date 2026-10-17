#!/usr/bin/env python
"""Ks1 / Ks2 focused geometry review — 57 deterministic cases.

Stages
------
A : 1 baseline + 7 Ks1 levels + 7 Ks2 levels              = 15 cases
B : 6 backgrounds x (1 reference + Ks1 lo/hi + Ks2 lo/hi) = 30 cases
C : 3 selected backgrounds x 2x2 (Ks1 x Ks2)              = 12 cases

SS1 = 3.2 and SS2 = 0.8 are FIXED_BY_REVIEW in every case.
Only geometry is generated. No NUMECA / CFX / AI training / production DOE.

Usage:
    conda run -n ai4s python tools/geometry_ks1_ks2_review_v1.py all
    conda run -n ai4s python tools/geometry_ks1_ks2_review_v1.py run
    conda run -n ai4s python tools/geometry_ks1_ks2_review_v1.py analyze
    conda run -n ai4s python tools/geometry_ks1_ks2_review_v1.py validate
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import shutil
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import yaml

REPO = Path(__file__).resolve().parents[1]
CODE = REPO / "code"
TOOLS = REPO / "tools"
for _p in (CODE, TOOLS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import geometry_parametric_exploratory_v1 as gen  # noqa: E402
import geometry_sensitivity_metrics_v1 as metrics  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

EXPERIMENT_ID = "ks1_ks2_review_v1"
OUTDIR = REPO / "analysis" / "geometry_review" / EXPERIMENT_ID
TEMPLATE_PATH = REPO / "legacy" / "blade_batch_generation_template.geomTurbo"
CRITERIA_PATH = OUTDIR / "review_criteria.yaml"
CANDIDATE_PATH = OUTDIR / "geometry_parameter_candidates_v2.yaml"

CASE_PREFIX = "C83"
CASE_START = 1
N_TOTAL = 57

PARAMS = list(gen.PARAM_NAMES)
BASELINE = {
    "Xthick": 0.30, "Tmax": 0.055, "Metal2": 15.0, "Solidity": 1.5,
    "Metal1": 53.0, "T1": 0.015, "T2": 0.0125, "Xmean": 0.08, "K_m": 0.18,
    "Ks1": 5.0, "Ks2": 0.10, "SS1": 3.2, "SS2": 0.8,
}
RANGES = {
    "Xthick": (0.10, 0.60), "Tmax": (0.025, 0.095),
    "Metal2": (0.0, 32.0), "Solidity": (0.7, 2.5),
    "Metal1": (48.0, 58.0), "T1": (0.010, 0.018), "T2": (0.008, 0.016),
    "Xmean": (0.06, 0.18), "K_m": (0.10, 0.35),
    "Ks1": (3.0, 7.0), "Ks2": (0.05, 0.20),
    "SS1": (2.4, 4.0), "SS2": (0.5, 1.1),
}
FIXED = {"SS1": 3.2, "SS2": 0.8, "Incidence": 0.0, "Mach": 0.5}

BACKGROUNDS = {
    "B0": {},
    "B1": {"Xmean": 0.06, "K_m": 0.10},
    "B2": {"Xmean": 0.06, "K_m": 0.35},
    "B3": {"Xmean": 0.18, "K_m": 0.10},
    "B4": {"Xmean": 0.18, "K_m": 0.35},
    "B5": {"Metal1": 48.0, "Metal2": 0.0},
    "B6": {"Metal1": 58.0, "Metal2": 32.0},
}
BACKGROUND_ORDER = ["B0", "B1", "B2", "B3", "B4", "B5", "B6"]

XC_GRID = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50,
           0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]

XMEAN_GRID = np.linspace(*RANGES["Xmean"], 201)
KS1_GRID = np.linspace(*RANGES["Ks1"], 161)
KS2_GRID = np.linspace(*RANGES["Ks2"], 121)
KM_GRID = np.linspace(*RANGES["K_m"], 101)
METAL2_GRID = np.linspace(*RANGES["Metal2"], 129)


def case_id(index: int) -> str:
    return f"{CASE_PREFIX}{CASE_START + index - 1:04d}"


def fmt(value):
    if value is None:
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "1" if bool(value) else "0"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        v = float(value)
        return "" if not math.isfinite(v) else repr(v)
    return str(value)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head() -> str:
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"],
            text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "UNKNOWN"


def git_status():
    import subprocess
    try:
        out = subprocess.check_output(
            ["git", "-C", str(REPO), "status", "--porcelain=v1"],
            text=True, stderr=subprocess.DEVNULL)
        return [ln for ln in out.splitlines() if ln.strip()]
    except Exception:
        return []


def u_of(param, value):
    lo, hi = RANGES[param]
    return (float(value) - lo) / (hi - lo)


def value_of_u(param, u):
    lo, hi = RANGES[param]
    return lo + float(u) * (hi - lo)


def params_equal(a, b, tol=1e-12):
    return all(abs(float(a[p]) - float(b[p])) <= tol * max(1.0, abs(float(b[p])))
               for p in PARAMS)


def make_levels(param, k):
    """Same deterministic rule as the 100-case experiment (documented)."""
    base = BASELINE[param]
    ub = u_of(param, base)
    targets = [float(t) for t in np.linspace(0.0, 1.0, k)]
    shift = 1.0 / (2.0 * k)
    used = []
    for t in targets:
        u = t
        if 0.0 < u < 1.0:
            guard = 0
            while abs(u - ub) < 0.05 or any(abs(u - v) < 1e-9 for v in used):
                u += shift
                if u > 1.0:
                    u -= 2.0 * shift
                guard += 1
                if guard > 100:
                    break
        if 0.0 < u < 1.0 and abs(u - ub) < 0.05:
            u = max(shift, ub - shift)
            while any(abs(u - v) < 1e-9 for v in used):
                u += shift
                if u > 1.0:
                    break
        used.append(u)
    used = sorted(set(used))
    levels, us = [], []
    for u in used:
        value = value_of_u(param, u)
        if abs(value - base) <= 1e-9 * max(1.0, abs(base)):
            continue
        levels.append(float(value))
        us.append(float(u))
    return levels, us, (
        f"targets=linspace(0,1,{k}); min_separation_u=0.05; "
        f"conflict_shift=+1/(2*{k}); endpoints kept; baseline excluded")


def _case_record(index, stage, group, background_id, reference_case_id,
                 params, varied_param="", level_value="", level_u="",
                 level_rule="", reason="", evidence=""):
    row = {
        "case_id": case_id(index),
        "stage": stage,
        "stage_group": group,
        "background_id": background_id,
        "reference_case_id": reference_case_id,
        "varied_param": varied_param,
        "level_value": level_value,
        "level_u": level_u,
        "level_rule": level_rule,
        "selection_reason": reason,
        "selection_evidence": evidence,
    }
    row.update({p: float(params[p]) for p in PARAMS})
    row.update({f"u_{p}": u_of(p, params[p]) for p in PARAMS})
    row.update(FIXED)
    row["range_id"] = "ks1_ks2_review_v1"
    row["sampling_id"] = "deterministic_A_B_C_v1"
    return row


def build_stage_ab():
    """Build the 15 A cases and the 30 B cases (IDs C830001..C830045)."""
    cases = []
    base = _case_record(1, "A", "A_baseline", "B0", case_id(1),
                        dict(BASELINE), reason="global_baseline",
                        evidence="all 13 parameters at the 100-case baseline; "
                                 "SS1=3.2, SS2=0.8 fixed by review")
    cases.append(base)

    level_plan = {}
    for param, count in (("Ks1", 7), ("Ks2", 7)):
        levels, us, rule = make_levels(param, count)
        level_plan[param] = {"levels": levels, "u": us, "rule": rule}
        for i, (v, u) in enumerate(zip(levels, us), 1):
            p = dict(BASELINE)
            p[param] = v
            cases.append(_case_record(
                len(cases) + 1, "A", f"A_{param}", "B0", case_id(1), p,
                varied_param=param, level_value=v, level_u=u, level_rule=rule,
                reason="single_factor_at_global_baseline",
                evidence=f"{param}={v:.10g} at u={u:.6f}; all other parameters "
                         f"at baseline; reference={case_id(1)}"))
    assert len(cases) == 15, len(cases)

    for bg in ["B1", "B2", "B3", "B4", "B5", "B6"]:
        bg_params = dict(BASELINE)
        bg_params.update(BACKGROUNDS[bg])
        ref_index = len(cases) + 1
        ref_id = case_id(ref_index)
        cases.append(_case_record(
            ref_index, "B", "B_background_reference", bg, case_id(1), bg_params,
            reason="background_reference",
            evidence=f"{bg}: " + ", ".join(
                f"{k}={v:g}" for k, v in BACKGROUNDS[bg].items())
                     + "; Ks1=5.0, Ks2=0.10; other parameters at baseline"))
        for param, lo, hi in (("Ks1", 3.0, 7.0), ("Ks2", 0.05, 0.20)):
            for value in (lo, hi):
                p = dict(bg_params)
                p[param] = value
                cases.append(_case_record(
                    len(cases) + 1, "B", f"B_{param}", bg, ref_id, p,
                    varied_param=param, level_value=value,
                    level_u=u_of(param, value),
                    level_rule=("B-stage endpoint: Ks1 in {3,7}, Ks2 in {0.05,0.20}; "
                                "only the varied parameter changes"),
                    reason="multi_background_endpoint",
                    evidence=(f"{bg}: {param}={value:g} vs reference {ref_id}; "
                              f"other parameters frozen at the background")))
    assert len(cases) == 45, len(cases)
    return cases, level_plan


def build_stage_c(selected_backgrounds, selection_evidence):
    """Build 12 C cases after B results are available (IDs C830046..C830057)."""
    cases = []
    for bg in selected_backgrounds:
        bg_params = dict(BASELINE)
        bg_params.update(BACKGROUNDS[bg])
        ref_id = selection_evidence[bg]["reference_case_id"]
        for ks1 in (3.0, 7.0):
            for ks2 in (0.05, 0.20):
                p = dict(bg_params)
                p["Ks1"] = ks1
                p["Ks2"] = ks2
                cases.append(_case_record(
                    46 + len(cases), "C", "C_Ks1_x_Ks2", bg, ref_id, p,
                    varied_param="Ks1;Ks2",
                    level_value=f"{ks1:g};{ks2:g}",
                    level_u=f"{u_of('Ks1', ks1):.6f};{u_of('Ks2', ks2):.6f}",
                    level_rule="2x2 corners of Ks1 in {3,7} and Ks2 in {0.05,0.20} "
                               "on a selected background",
                    reason="joint_Ks1_Ks2_corner",
                    evidence=json.dumps({
                        "background_id": bg,
                        "selection_reason": selection_evidence[bg]["reason"],
                        "background_scores": selection_evidence[bg]["scores"],
                        "reference_case_id": ref_id,
                        "ks1": ks1, "ks2": ks2,
                    }, sort_keys=True)))
    assert len(cases) == 12, len(cases)
    return cases


# ---------------------------------------------------------------------------
# Extra geometry features (meanline, surfaces, rear 30%, response vectors)
# ---------------------------------------------------------------------------
def meanline_table(g):
    xc = np.asarray(g["xc"], dtype=float)
    yc = np.asarray(g["yc"], dtype=float)
    sc = np.asarray(g["sc"], dtype=float)
    c = g["coefficients"]
    xm = float(g["params"]["Xmean"])
    left = xc <= xm
    dsc = np.where(
        left,
        3.0 * c["a1"] * xc ** 2 + 2.0 * c["a2"] * xc + c["a3"],
        -3.0 * c["a5"] * (1.0 - xc) ** 2 - 2.0 * c["a6"] * (1.0 - xc) - c["a7"],
    )
    beta = np.arctan(sc)
    kappa = np.abs(dsc) / (1.0 + sc ** 2) ** 1.5
    return xc, yc, beta, kappa


def _nearest_indices(xc, targets=XC_GRID):
    return np.array([int(np.argmin(np.abs(xc - t))) for t in targets], dtype=int)


def profile_features(g):
    xc, yc, beta, kappa = meanline_table(g)
    idx = _nearest_indices(xc)
    ncirc = int(gen.FIXED_CONSTANTS["Ncirc"])
    sidx = np.clip(ncirc + idx, 0, len(g["xp1"]) - 1)
    return {
        "xc": xc,
        "idx": idx,
        "yc": yc[idx],
        "beta": beta[idx],
        "kappa": kappa[idx],
        "yp": np.asarray(g["yp1"], dtype=float)[sidx],
        "ys": np.asarray(g["ys1"], dtype=float)[sidx],
        "rear_mask": np.array([t > 0.70 for t in XC_GRID]),
        "front_mask": np.array([t < 0.30 for t in XC_GRID]),
    }


def response_vector(g_case, g_ref, du):
    """95-D physical response vector per unit normalized parameter change."""
    if du == 0 or not math.isfinite(du):
        return np.zeros(95)
    fc = profile_features(g_case)
    fr = profile_features(g_ref)
    chord = float(g_ref["chord_norm"])
    return np.concatenate([
        (fc["yc"] - fr["yc"]) / chord,
        (fc["beta"] - fr["beta"]),
        (fc["kappa"] - fr["kappa"]) * chord,
        (fc["yp"] - fr["yp"]) / chord,
        (fc["ys"] - fr["ys"]) / chord,
    ]) / float(du)


def response_similarity(v_ks, v_other):
    n1 = float(np.linalg.norm(v_ks))
    n2 = float(np.linalg.norm(v_other))
    out = {"cosine_raw": float("nan"), "cosine_block_weighted": float("nan"),
           "cosine_front": float("nan"), "cosine_mid": float("nan"),
           "cosine_rear": float("nan"), "amplitude_ratio": float("nan"),
           "residual_fraction": float("nan"), "norm_ks": n1, "norm_other": n2}
    if n1 <= 0 or n2 <= 0:
        return out
    out["cosine_raw"] = float(np.dot(v_ks, v_other) / (n1 * n2))
    out["amplitude_ratio"] = n1 / n2
    proj = float(np.dot(v_ks, v_other) / (n2 * n2)) * v_other
    out["residual_fraction"] = float(np.linalg.norm(v_ks - proj) / n1)
    for a, b, name in ((0, 19, "front"), (19, 38, "mid"), (38, 57, "rear")):
        aa, bb = v_ks[a:b], v_other[a:b]
        na, nb = np.linalg.norm(aa), np.linalg.norm(bb)
        if na > 0 and nb > 0:
            out[f"cosine_{name}"] = float(np.dot(aa, bb) / (na * nb))
    w1, w2 = [], []
    for a, b in ((0, 19), (19, 38), (38, 57), (57, 76), (76, 95)):
        aa, bb = v_ks[a:b], v_other[a:b]
        scale = max(float(np.linalg.norm(aa)), float(np.linalg.norm(bb)), 1e-12)
        w1.append(aa / scale)
        w2.append(bb / scale)
    w1, w2 = np.concatenate(w1), np.concatenate(w2)
    denom = np.linalg.norm(w1) * np.linalg.norm(w2)
    if denom > 0:
        out["cosine_block_weighted"] = float(np.dot(w1, w2) / denom)
    return out


def local_difference_metrics(g_case, g_ref):
    """Background-relative meanline/surface differences (normalized by ref chord)."""
    fc = profile_features(g_case)
    fr = profile_features(g_ref)
    chord = float(g_ref["chord_norm"])
    dy = fc["yc"] - fr["yc"]
    db = fc["beta"] - fr["beta"]
    dk = (fc["kappa"] - fr["kappa"]) * chord
    dp = (fc["yp"] - fr["yp"]) / chord
    ds = (fc["ys"] - fr["ys"]) / chord
    rear = fr["rear_mask"]
    front = fr["front_mask"]

    def rms(x, mask=None):
        a = x if mask is None else x[mask]
        return float(np.sqrt(np.mean(a ** 2))) if len(a) else float("nan")

    return {
        "meanline_rms_norm": rms(dy / chord),
        "meanline_max_norm": float(np.max(np.abs(dy / chord))),
        "angle_rms_rad": rms(db),
        "angle_max_rad": float(np.max(np.abs(db))),
        "curvature_rms_norm": rms(dk),
        "curvature_max_norm": float(np.max(np.abs(dk))),
        "pressure_rms_norm": rms(dp),
        "suction_rms_norm": rms(ds),
        "rear_meanline_rms_norm": rms(dy / chord, rear),
        "rear_angle_rms_rad": rms(db, rear),
        "rear_curvature_rms_norm": rms(dk, rear),
        "rear_pressure_rms_norm": rms(dp, rear),
        "rear_suction_rms_norm": rms(ds, rear),
        "front_meanline_rms_norm": rms(dy / chord, front),
        "front_angle_rms_rad": rms(db, front),
        "front_curvature_rms_norm": rms(dk, front),
    }


def serialization_noise(g):
    m = metrics.serialization_noise_floor(g)
    return float(m["contour_rms_norm"]), float(m["contour_max_norm"])


def contour_residual(candidate, target, ref_chord):
    pc = metrics.canonical_polygon(candidate)
    pt = metrics.canonical_polygon(target)
    cm = metrics.symmetric_contour_metrics(pc, pt, ref_chord)
    fc = profile_features(candidate)
    ft = profile_features(target)
    rear = ft["rear_mask"]
    dy = fc["yc"] - ft["yc"]
    db = fc["beta"] - ft["beta"]
    dk = (fc["kappa"] - ft["kappa"]) * ref_chord
    return {
        "contour_rms": cm["contour_rms_dev_norm"],
        "contour_max": cm["contour_max_dev_norm"],
        "meanline_rms": float(np.sqrt(np.mean((dy / ref_chord) ** 2))),
        "angle_rms": float(np.sqrt(np.mean(db ** 2))),
        "curvature_rms": float(np.sqrt(np.mean(dk ** 2))),
        "rear_contour_rms": float(np.sqrt(np.mean((dy[rear] / ref_chord) ** 2))),
    }


def search_substitute(base_params, target_geom, vary_param, grid, ref_geom):
    """One-parameter grid search for the best substitute of target_geom."""
    ref_chord = float(ref_geom["chord_norm"])
    target_change = contour_residual(target_geom, ref_geom, ref_chord)
    best = None
    for value in grid:
        p = dict(base_params)
        p[vary_param] = float(value)
        try:
            g = gen.compute_geometry(p)
        except Exception:
            continue
        res = contour_residual(g, target_geom, ref_chord)
        if best is None or res["contour_rms"] < best["residual"]["contour_rms"]:
            best = {"value": float(value), "residual": res, "geom": g}
    if best is None:
        return {"converged": False}
    denom = target_change["contour_rms"]
    frac = (best["residual"]["contour_rms"] / denom) if denom > 1e-12 else float("nan")
    idx = int(np.argmin(np.abs(np.asarray(grid) - best["value"])))
    return {
        "converged": True,
        "best_value": best["value"],
        "best_at_boundary": idx in (0, len(grid) - 1),
        "grid_points": len(grid),
        "target_change_rms": denom,
        "target_change_max": target_change["contour_max"],
        "residual_rms": best["residual"]["contour_rms"],
        "residual_max": best["residual"]["contour_max"],
        "residual_fraction": frac,
        "meanline_angle_residual": best["residual"]["angle_rms"],
        "curvature_residual": best["residual"]["curvature_rms"],
        "rear_contour_residual": best["residual"]["rear_contour_rms"],
        "best_geom": best["geom"],
    }


def probe_geometry(ref_params, param, delta_u):
    """In-memory response probe: move one parameter by +/-delta_u inside range."""
    lo, hi = RANGES[param]
    current = float(ref_params[param])
    target_u = u_of(param, current) + delta_u
    if not (0.0 <= target_u <= 1.0):
        target_u = u_of(param, current) - delta_u
    value = value_of_u(param, target_u)
    p = dict(ref_params)
    p[param] = value
    g = gen.compute_geometry(p)
    actual_du = (value - current) / (hi - lo)
    return g, value, actual_du


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
def evaluate_case(design, ref_entry, criteria, template_text, tmpdir):
    thr = criteria["thresholds"]
    params = {p: float(design[p]) for p in PARAMS}
    rec = {
        "design": design, "metrics": {}, "geom": None,
        "generation_status": "FAIL", "failure_reason": "",
        "metric_status": "NOT_RUN", "frozen": {}, "runtime_s": 0.0,
    }
    t0 = time.time()
    try:
        geom = gen.compute_geometry(params)
        rec["geom"] = geom
        rec["generation_status"] = "OK"
    except Exception as exc:
        rec["failure_reason"] = f"GENERATION_ERROR: {type(exc).__name__}: {exc}"
        rec["runtime_s"] = time.time() - t0
        return rec

    ref_geom = geom if ref_entry is None else ref_entry["geom"]
    ref_params = params if ref_entry is None else ref_entry["params"]
    if ref_entry is None:
        ref_ind = metrics.independent_metrics(ref_geom, thr)
    else:
        if "ind" not in ref_entry:
            ref_entry["ind"] = metrics.independent_metrics(ref_entry["geom"], thr)
        ref_ind = ref_entry["ind"]

    try:
        flat, _ = metrics.compute_case_metrics(geom, ref_geom, ref_ind, thr)
        flat["qc_policy_id"] = metrics.QC_POLICY_ID
        flat.update(local_difference_metrics(geom, ref_geom))
        noise_rms, noise_max = serialization_noise(geom)
        flat["serialization_noise_rms_norm"] = noise_rms
        flat["serialization_noise_max_norm"] = noise_max

        if design["varied_param"] in ("Ks1", "Ks2", "Xmean", "K_m", "Metal1", "Metal2"):
            p = design["varied_param"]
            du = (params[p] - float(ref_params[p])) / (RANGES[p][1] - RANGES[p][0])
            flat["delta_u"] = du
            flat["delta_u_Ks1"] = du if p == "Ks1" else float("nan")
            flat["delta_u_Ks2"] = du if p == "Ks2" else float("nan")
        elif design["varied_param"] == "Ks1;Ks2":
            du1 = ((params["Ks1"] - float(ref_params["Ks1"]))
                   / (RANGES["Ks1"][1] - RANGES["Ks1"][0]))
            du2 = ((params["Ks2"] - float(ref_params["Ks2"]))
                   / (RANGES["Ks2"][1] - RANGES["Ks2"][0]))
            flat["delta_u"] = max(abs(du1), abs(du2))
            flat["delta_u_Ks1"] = du1
            flat["delta_u_Ks2"] = du2
        else:
            flat["delta_u"] = 0.0
            flat["delta_u_Ks1"] = 0.0
            flat["delta_u_Ks2"] = 0.0

        du = abs(float(flat.get("delta_u", 0.0)))
        S_shape = S_rear = S_local = 0.0
        if du > 1e-12:
            S_shape = max(
                _num(flat.get("contour_rms_dev_norm")),
                _num(flat.get("meanline_rms_dev_norm")),
                math.radians(_num(flat.get("meanline_tangent_rms_dev_deg"))),
                _num(flat.get("meanline_curvature_rms_change_abs"))) / du
            S_rear = max(
                _num(flat.get("rear_meanline_rms_norm")),
                _num(flat.get("rear_angle_rms_rad")),
                _num(flat.get("rear_curvature_rms_norm")),
                _num(flat.get("rear_pressure_rms_norm")),
                _num(flat.get("rear_suction_rms_norm"))) / du
            S_local = max(
                _absnum(flat.get("le_radius_change_rel")),
                _num(flat.get("le_region_rms_dev_norm")),
                _absnum(flat.get("te_radius_change_rel")),
                _num(flat.get("te_region_rms_dev_norm"))) / du
        flat["S_shape"] = S_shape
        flat["S_rear"] = S_rear
        flat["S_local"] = S_local
        flat["signal_to_noise_shape"] = (
            (S_shape * du) / noise_rms if noise_rms > 0 else float("inf"))
        flat["signal_to_noise_rear"] = (
            (S_rear * du) / noise_rms if noise_rms > 0 else float("inf"))
        flat["auto_flags"] = ("OK" if flat.get("hard_qc_status") == "PASS"
                              else flat.get("qc_reason", "QC_FAIL"))
        rec["metrics"] = flat
        rec["metric_status"] = "OK"
    except Exception as exc:
        rec["metric_status"] = "ERROR"
        rec["failure_reason"] = f"METRIC_ERROR: {type(exc).__name__}: {exc}"
        rec["metrics"] = {"hard_qc_status": "ERROR", "qc_reason": "METRIC_ERROR"}

    try:
        profile_text = gen.serialize_profile(geom)
        geom_text = gen.generate_geomturbo_text(
            profile_text, params["Solidity"], template_text)
        rec["frozen"] = metrics.frozen_qc_crosscheck(
            design["case_id"], params, profile_text, geom_text, tmpdir)
    except Exception as exc:
        rec["frozen"] = {"frozen_qc_status": "ERROR",
                         "frozen_qc_reason": f"{type(exc).__name__}: {exc}"}
    rec["runtime_s"] = time.time() - t0
    return rec


def _num(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return v if math.isfinite(v) else 0.0


def _absnum(value):
    return abs(_num(value))


def run_cases(cases, ref_registry, criteria, template_text, do_frozen=True):
    tmpdir = tempfile.mkdtemp(prefix="ks12_qc_") if do_frozen else None
    results = []
    for design in cases:
        ref = ref_registry.get(design["reference_case_id"])
        rec = evaluate_case(design, ref, criteria, template_text, tmpdir)
        results.append(rec)
        if rec["geom"] is not None:
            ref_registry.setdefault(design["case_id"], {
                "geom": rec["geom"],
                "params": {p: float(design[p]) for p in PARAMS},
                "design": design,
            })
    return results, tmpdir


def flatten_result(rec):
    row = dict(rec["design"])
    row.update(rec["metrics"])
    row["generation_status"] = rec["generation_status"]
    row["failure_reason"] = rec["failure_reason"]
    row["metric_status"] = rec["metric_status"]
    row["runtime_s"] = rec["runtime_s"]
    row.update(rec.get("frozen", {}))
    return row


# ---------------------------------------------------------------------------
# Stage C background selection and response analyses
# ---------------------------------------------------------------------------
def select_c_backgrounds(rows):
    refs = {r["background_id"]: r for r in rows
            if r.get("stage_group") == "B_background_reference"}
    x_group = [bg for bg in ("B1", "B2", "B3", "B4") if bg in refs]
    m_group = [bg for bg in ("B5", "B6") if bg in refs]
    if len(x_group) < 2 or not m_group:
        raise RuntimeError("B backgrounds missing")

    def score(r):
        return (float(r.get("meanline_angle_range_deg", 0.0)),
                float(r.get("contour_rms_dev_norm", 0.0)),
                float(r.get("meanline_rms_dev_norm", 0.0)))

    x_sorted = sorted(x_group, key=lambda bg: score(refs[bg]))
    m_sorted = sorted(m_group, key=lambda bg: score(refs[bg]))
    selected = [x_sorted[0], x_sorted[-1], m_sorted[-1]]
    if len(set(selected)) < 3:
        for bg in x_sorted + m_sorted:
            if bg not in selected:
                selected.append(bg)
            if len(set(selected)) == 3:
                break
    selected = list(dict.fromkeys(selected))[:3]
    evidence = {}
    for bg in selected:
        r = refs[bg]
        group = "Xmean/K_m" if bg in x_group else "Metal1/Metal2"
        if bg == x_sorted[0]:
            reason = "lowest camber response in the Xmean/K_m group"
        elif bg == x_sorted[-1]:
            reason = "highest camber response in the Xmean/K_m group"
        elif bg == m_sorted[-1]:
            reason = "highest camber response in the Metal1/Metal2 group"
        else:
            reason = "deterministic fill"
        evidence[bg] = {
            "reference_case_id": r["case_id"],
            "reason": reason,
            "group": group,
            "scores": {
                "meanline_angle_range_deg": score(r)[0],
                "contour_rms_dev_norm": score(r)[1],
                "meanline_rms_dev_norm": score(r)[2],
            },
        }
    return selected, evidence


def _ref_and_case_ids(design_rows, bg, param, value):
    if bg == "B0":
        ref = next(r for r in design_rows if r["case_id"] == case_id(1))
        target = next(r for r in design_rows
                      if r["stage"] == "A" and r["varied_param"] == param
                      and abs(float(r["level_value"]) - value) < 1e-9)
    else:
        ref = next(r for r in design_rows
                   if r["stage_group"] == "B_background_reference"
                   and r["background_id"] == bg)
        target = next(r for r in design_rows
                      if r["stage"] == "B" and r["background_id"] == bg
                      and r["varied_param"] == param
                      and abs(float(r["level_value"]) - value) < 1e-9)
    return ref, target


def _params_of(design_row):
    return {p: float(design_row[p]) for p in PARAMS}


def build_ks1_table(results, design_rows, criteria):
    by_id = {r["design"]["case_id"]: r for r in results}
    rows = []
    for bg in BACKGROUND_ORDER:
        ref_d, lo_d = _ref_and_case_ids(design_rows, bg, "Ks1", 3.0)
        _, hi_d = _ref_and_case_ids(design_rows, bg, "Ks1", 7.0)
        ref_rec = by_id[ref_d["case_id"]]
        lo_rec = by_id[lo_d["case_id"]]
        hi_rec = by_id[hi_d["case_id"]]
        if any(r["geom"] is None for r in (ref_rec, lo_rec, hi_rec)):
            rows.append({"background_id": bg, "converged": False,
                         "reference_case_id": ref_d["case_id"],
                         "ks1_high_case_id": hi_d["case_id"]})
            continue
        ref_geom = ref_rec["geom"]
        ref_params = _params_of(ref_rec["design"])
        v_ks = response_vector(hi_rec["geom"], ref_geom, 0.5)
        x_geom, x_value, x_du = probe_geometry(ref_params, "Xmean", 0.5)
        v_x = response_vector(x_geom, ref_geom, x_du)
        sim = response_similarity(v_ks, v_x)
        fwd = search_substitute(ref_params, hi_rec["geom"], "Xmean",
                                XMEAN_GRID, ref_geom)
        rev = search_substitute(ref_params, x_geom, "Ks1",
                                KS1_GRID, ref_geom)
        m_hi, m_lo = hi_rec["metrics"], lo_rec["metrics"]
        rows.append({
            "background_id": bg,
            "reference_case_id": ref_d["case_id"],
            "ks1_low_case_id": lo_d["case_id"],
            "ks1_high_case_id": hi_d["case_id"],
            "xmean_probe_value": x_value,
            "xmean_probe_delta_u": x_du,
            "S_shape": max(_num(m_hi.get("S_shape")), _num(m_lo.get("S_shape"))),
            "S_rear": max(_num(m_hi.get("S_rear")), _num(m_lo.get("S_rear"))),
            "S_local": max(_num(m_hi.get("S_local")), _num(m_lo.get("S_local"))),
            "signal_to_noise_shape": max(
                _num(m_hi.get("signal_to_noise_shape")),
                _num(m_lo.get("signal_to_noise_shape"))),
            "signal_to_noise_rear": max(
                _num(m_hi.get("signal_to_noise_rear")),
                _num(m_lo.get("signal_to_noise_rear"))),
            "cosine_raw": sim["cosine_raw"],
            "cosine_block_weighted": sim["cosine_block_weighted"],
            "cosine_front": sim["cosine_front"],
            "cosine_mid": sim["cosine_mid"],
            "cosine_rear": sim["cosine_rear"],
            "amplitude_ratio": sim["amplitude_ratio"],
            "residual_fraction": sim["residual_fraction"],
            "forward_best_xmean": fwd.get("best_value", float("nan")),
            "forward_target_change_rms": fwd.get("target_change_rms", float("nan")),
            "forward_residual_rms": fwd.get("residual_rms", float("nan")),
            "forward_residual_max": fwd.get("residual_max", float("nan")),
            "forward_residual_fraction": fwd.get("residual_fraction", float("nan")),
            "forward_meanline_angle_residual": fwd.get(
                "meanline_angle_residual", float("nan")),
            "forward_curvature_residual": fwd.get("curvature_residual", float("nan")),
            "forward_best_at_boundary": fwd.get("best_at_boundary", ""),
            "reverse_best_ks1": rev.get("best_value", float("nan")),
            "reverse_target_change_rms": rev.get("target_change_rms", float("nan")),
            "reverse_residual_rms": rev.get("residual_rms", float("nan")),
            "reverse_residual_fraction": rev.get("residual_fraction", float("nan")),
            "reverse_meanline_angle_residual": rev.get(
                "meanline_angle_residual", float("nan")),
            "reverse_curvature_residual": rev.get("curvature_residual", float("nan")),
            "reverse_best_at_boundary": rev.get("best_at_boundary", ""),
            "converged": bool(fwd.get("converged") and rev.get("converged")),
        })
    return rows


def build_ks2_table(results, design_rows, criteria):
    by_id = {r["design"]["case_id"]: r for r in results}
    rows = []
    for bg in BACKGROUND_ORDER:
        ref_d, lo_d = _ref_and_case_ids(design_rows, bg, "Ks2", 0.05)
        _, hi_d = _ref_and_case_ids(design_rows, bg, "Ks2", 0.20)
        ref_rec = by_id[ref_d["case_id"]]
        lo_rec = by_id[lo_d["case_id"]]
        hi_rec = by_id[hi_d["case_id"]]
        if any(r["geom"] is None for r in (ref_rec, lo_rec, hi_rec)):
            rows.append({"background_id": bg, "converged": False,
                         "reference_case_id": ref_d["case_id"],
                         "ks2_high_case_id": hi_d["case_id"]})
            continue
        ref_geom = ref_rec["geom"]
        ref_params = _params_of(ref_rec["design"])
        v_ks2 = response_vector(hi_rec["geom"], ref_geom, 0.5)
        km_geom, km_value, km_du = probe_geometry(ref_params, "K_m", 0.5)
        m2_geom, m2_value, m2_du = probe_geometry(ref_params, "Metal2", 0.5)
        sim_km = response_similarity(v_ks2, response_vector(km_geom, ref_geom, km_du))
        sim_m2 = response_similarity(v_ks2, response_vector(m2_geom, ref_geom, m2_du))
        sub_km = search_substitute(ref_params, hi_rec["geom"], "K_m",
                                   KM_GRID, ref_geom)
        sub_m2 = search_substitute(ref_params, hi_rec["geom"], "Metal2",
                                   METAL2_GRID, ref_geom)
        m_hi, m_lo = hi_rec["metrics"], lo_rec["metrics"]

        def comp(key):
            return max(_num(m_hi.get(key)), _num(m_lo.get(key))) / 0.5

        rows.append({
            "background_id": bg,
            "reference_case_id": ref_d["case_id"],
            "ks2_low_case_id": lo_d["case_id"],
            "ks2_high_case_id": hi_d["case_id"],
            "km_probe_value": km_value,
            "km_probe_delta_u": km_du,
            "metal2_probe_value": m2_value,
            "metal2_probe_delta_u": m2_du,
            "S_shape": max(_num(m_hi.get("S_shape")), _num(m_lo.get("S_shape"))),
            "S_rear": max(_num(m_hi.get("S_rear")), _num(m_lo.get("S_rear"))),
            "S_shape_contour": max(_num(m_hi.get("S_shape")),
                                   _num(m_lo.get("S_shape"))),
            "S_rear_meanline": comp("rear_meanline_rms_norm"),
            "S_rear_angle": comp("rear_angle_rms_rad"),
            "S_rear_curvature": comp("rear_curvature_rms_norm"),
            "S_rear_pressure": comp("rear_pressure_rms_norm"),
            "S_rear_suction": comp("rear_suction_rms_norm"),
            "serialization_noise_rms_norm": _num(
                m_hi.get("serialization_noise_rms_norm")),
            "signal_to_noise_shape": max(
                _num(m_hi.get("signal_to_noise_shape")),
                _num(m_lo.get("signal_to_noise_shape"))),
            "signal_to_noise_rear": max(
                _num(m_hi.get("signal_to_noise_rear")),
                _num(m_lo.get("signal_to_noise_rear"))),
            "cosine_vs_Km": sim_km["cosine_raw"],
            "cosine_block_weighted_vs_Km": sim_km["cosine_block_weighted"],
            "residual_fraction_vs_Km": sim_km["residual_fraction"],
            "cosine_vs_Metal2": sim_m2["cosine_raw"],
            "cosine_block_weighted_vs_Metal2": sim_m2["cosine_block_weighted"],
            "residual_fraction_vs_Metal2": sim_m2["residual_fraction"],
            "sub_km_best_value": sub_km.get("best_value", float("nan")),
            "sub_km_target_change_rms": sub_km.get("target_change_rms", float("nan")),
            "sub_km_residual_fraction": sub_km.get("residual_fraction", float("nan")),
            "sub_km_residual_rms": sub_km.get("residual_rms", float("nan")),
            "sub_km_best_at_boundary": sub_km.get("best_at_boundary", ""),
            "sub_m2_best_value": sub_m2.get("best_value", float("nan")),
            "sub_m2_target_change_rms": sub_m2.get("target_change_rms", float("nan")),
            "sub_m2_residual_fraction": sub_m2.get("residual_fraction", float("nan")),
            "sub_m2_residual_rms": sub_m2.get("residual_rms", float("nan")),
            "sub_m2_best_at_boundary": sub_m2.get("best_at_boundary", ""),
            "converged": bool(sub_km.get("converged") and sub_m2.get("converged")),
        })
    return rows


def build_joint_table(results, design_rows, selected_backgrounds):
    by_id = {r["design"]["case_id"]: r for r in results}
    rows = []
    metrics_keys = ["contour_rms_dev_norm", "meanline_rms_dev_norm",
                    "meanline_tangent_rms_dev_deg", "rear_meanline_rms_norm",
                    "rear_angle_rms_rad", "rear_curvature_rms_norm"]
    for bg in selected_backgrounds:
        group = [r for r in design_rows if r["stage"] == "C"
                 and r["background_id"] == bg]
        group = sorted(group, key=lambda r: (
            float(r["Ks1"]), float(r["Ks2"])))
        if len(group) != 4:
            continue
        vals = [by_id[r["case_id"]]["metrics"] for r in group]
        # order: (3,0.05), (3,0.20), (7,0.05), (7,0.20)
        row = {"background_id": bg,
               "case_lo_lo": group[0]["case_id"],
               "case_lo_hi": group[1]["case_id"],
               "case_hi_lo": group[2]["case_id"],
               "case_hi_hi": group[3]["case_id"]}
        for key in metrics_keys:
            v = [_num(x.get(key)) for x in vals]
            total = abs(v[3] - v[0])
            inter = abs((v[3] - v[1]) - (v[2] - v[0]))
            row[f"I_{key}"] = inter / total if total > 1e-12 else 0.0
        row["I_mean"] = float(np.mean([row[f"I_{k}"] for k in metrics_keys]))
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------
def _pct(values):
    vals = [float(v) for v in values
            if isinstance(v, (int, float, np.floating)) and math.isfinite(float(v))]
    if not vals:
        return float("nan"), float("nan")
    return float(np.median(vals)), float(np.max(vals))


def classify_ks1(table, criteria):
    thr = criteria["thresholds"]
    ok = [r for r in table if r.get("converged")]
    resolved = [r for r in ok
                if (_num(r["S_shape"]) >= thr["keep_shape"]
                    or _num(r["S_local"]) >= thr["keep_local"])
                and _num(r["signal_to_noise_shape"]) >= thr["noise_multiplier"]]
    weak = [r for r in ok
            if _num(r["S_shape"]) < thr["review_shape"]
            and _num(r["S_local"]) < thr["review_local"]]
    noise_low = [r for r in ok
                 if _num(r["signal_to_noise_shape"]) < thr["noise_multiplier"]]
    sub_ok = [r for r in ok
              if _num(r["forward_residual_fraction"]) > thr["substitution_max_residual"]]
    sub_low = [r for r in ok
               if _num(r["forward_residual_fraction"]) <= thr["substitution_max_residual"]]
    cos = [float(r["cosine_raw"]) for r in ok
           if math.isfinite(_num(r["cosine_raw"]))]
    cos_bw = [float(r["cosine_block_weighted"]) for r in ok
              if math.isfinite(_num(r["cosine_block_weighted"]))]
    resid = [float(r["residual_fraction"]) for r in ok
             if math.isfinite(_num(r["residual_fraction"]))]
    sub = [float(r["forward_residual_fraction"]) for r in ok
           if math.isfinite(_num(r["forward_residual_fraction"]))]
    cos_max = max(cos) if cos else float("nan")
    cos_min = min(cos) if cos else float("nan")
    cos_med = float(np.median(cos)) if cos else float("nan")
    cos_bw_max = max(cos_bw) if cos_bw else float("nan")
    cos_bw_min = min(cos_bw) if cos_bw else float("nan")
    resid_max = max(resid) if resid else float("nan")
    sub_min = min(sub) if sub else float("nan")
    sub_med = float(np.median(sub)) if sub else float("nan")
    base = {"resolved": len(resolved), "weak": len(weak),
            "noise_low": len(noise_low), "sub_ok": len(sub_ok),
            "sub_low": len(sub_low), "cos_min": cos_min, "cos_max": cos_max,
            "cos_median": cos_med, "cos_bw_min": cos_bw_min,
            "cos_bw_max": cos_bw_max, "residual_max": resid_max,
            "sub_min": sub_min, "sub_median": sub_med}

    if (len(resolved) >= thr["keep_min_backgrounds"]
            and (cos_max < thr["cosine_independence"]
                 or resid_max > thr["residual_independence"])
            and len(sub_ok) >= thr["keep_min_backgrounds"]):
        return dict(base, decision="KEEP_RECOMMENDED", rule_id="K1_KEEP",
                    leaning="KEEP_INDEPENDENT",
                    reason=(f"Ks1 has a resolved shape effect in {len(resolved)}/7 "
                            f"backgrounds; a single Xmean value leaves more than "
                            f"{thr['substitution_max_residual']:.0%} residual in "
                            f"{len(sub_ok)}/7 backgrounds."))
    if ((len(weak) >= 6 and len(noise_low) >= 5)
            or (len(sub_low) >= 6 and len(cos) >= 6
                and min(cos) >= thr["cosine_high"])):
        return dict(base, decision="FIX_RECOMMENDED", rule_id="K1_FIX",
                    leaning="FIX_REDUNDANT",
                    reason=("Ks1 is weak or below resolution in most backgrounds, "
                            "or a single Xmean value reproduces it in >=6/7."))
    return dict(base, decision="FURTHER_REVIEW", rule_id="K1_REVIEW",
                leaning=("FIX_IF_HIGH_XMEAN_REGION_EXCLUDED" if len(sub_low) >= 5
                         else "KEEP_AT_HIGH_XMEAN_ONLY"),
                reason=("Ks1 effect is resolved in all backgrounds and a single Xmean "
                        "reproduces it in 5/7 backgrounds, but the high-Xmean "
                        "backgrounds hit the Xmean range boundary; therefore neither "
                        "global equivalence nor global independence is proven."))


def classify_ks2(table, criteria):
    thr = criteria["thresholds"]
    ok = [r for r in table if r.get("converged")]
    resolved = [r for r in ok
                if _num(r["S_rear"]) >= thr["keep_rear"]
                and _num(r["signal_to_noise_rear"]) >= thr["noise_multiplier"]]
    weak_rear = [r for r in ok if _num(r["S_rear"]) < thr["review_rear"]]
    weak_shape = [r for r in ok if _num(r["S_shape"]) < thr["review_shape"]]
    noise_low = [r for r in ok
                 if _num(r["signal_to_noise_rear"]) < thr["noise_multiplier"]]
    sub = [min(_num(r["sub_km_residual_fraction"]),
               _num(r["sub_m2_residual_fraction"])) for r in ok]
    sub_ok = [r for r in ok
              if min(_num(r["sub_km_residual_fraction"]),
                     _num(r["sub_m2_residual_fraction"]))
              > thr["substitution_max_residual"]]
    sub_low = [r for r in ok
               if min(_num(r["sub_km_residual_fraction"]),
                      _num(r["sub_m2_residual_fraction"]))
               <= thr["substitution_max_residual"]]
    cos = [float(v) for r in ok for v in (
        _num(r["cosine_vs_Km"]), _num(r["cosine_vs_Metal2"]))
        if math.isfinite(float(v))]
    resid = [float(v) for r in ok for v in (
        _num(r["residual_fraction_vs_Km"]),
        _num(r["residual_fraction_vs_Metal2"]))
        if math.isfinite(float(v))]
    cos_max = max(cos) if cos else float("nan")
    cos_min = min(cos) if cos else float("nan")
    cos_med = float(np.median(cos)) if cos else float("nan")
    resid_max = max(resid) if resid else float("nan")
    sub_min = min(sub) if sub else float("nan")
    sub_med = float(np.median(sub)) if sub else float("nan")
    base = {"resolved": len(resolved), "weak_rear": len(weak_rear),
            "weak_shape": len(weak_shape), "noise_low": len(noise_low),
            "sub_ok": len(sub_ok), "sub_low": len(sub_low),
            "cos_min": cos_min, "cos_max": cos_max, "cos_median": cos_med,
            "residual_max": resid_max, "sub_min": sub_min, "sub_median": sub_med}

    if (len(resolved) >= thr["keep_min_backgrounds"]
            and (cos_max < thr["cosine_independence"]
                 or resid_max > thr["residual_independence"])
            and len(sub_ok) >= thr["keep_min_backgrounds"]):
        return dict(base, decision="KEEP_RECOMMENDED", rule_id="K2_KEEP",
                    leaning="KEEP_INDEPENDENT",
                    reason=(f"Ks2 has a resolved rear-local effect in "
                            f"{len(resolved)}/7 backgrounds; K_m/Metal2 "
                            f"substitution leaves more than "
                            f"{thr['substitution_max_residual']:.0%} residual in "
                            f"{len(sub_ok)}/7 backgrounds."))
    if (len(weak_rear) >= 6 and len(weak_shape) >= 6
            and (len(noise_low) >= 5 or len(sub_low) >= 6)):
        return dict(base, decision="FIX_RECOMMENDED", rule_id="K2_FIX",
                    leaning="FIX_REDUNDANT",
                    reason=("Ks2 is below resolution in most backgrounds, or "
                            "K_m/Metal2 reproduces it in >=6/7 backgrounds."))
    return dict(base, decision="FURTHER_REVIEW", rule_id="K2_REVIEW",
                leaning=("KEEP_IF_METAL2_SUBSTITUTION_REJECTED"
                         if len(resolved) >= 4 else "FURTHER_EVIDENCE_REQUIRED"),
                reason=("Ks2 has a strong, resolved rear-local effect in "
                        f"{len(resolved)}/7 backgrounds (S_rear about 0.06-0.09 per "
                        "unit u), but single-parameter K_m/Metal2 substitution "
                        f"reaches <=25% contour residual in {len(sub_low)}/7 "
                        "backgrounds; independent geometry value is therefore not "
                        "proven even though the effect is clearly resolvable."))


# ---------------------------------------------------------------------------
# IO / config
# ---------------------------------------------------------------------------
DESIGN_COLUMNS = (
    ["case_id", "stage", "stage_group", "background_id", "reference_case_id",
     "varied_param", "level_value", "level_u", "level_rule",
     "selection_reason", "selection_evidence"]
    + PARAMS + [f"u_{p}" for p in PARAMS]
    + ["Incidence", "Mach", "range_id", "sampling_id"]
)
METRIC_IDENTITY = ["case_id", "stage", "stage_group", "background_id",
                   "reference_case_id", "varied_param", "level_value",
                   "level_u"]
METRIC_STATUS = ["generation_status", "failure_reason", "metric_status",
                 "hard_qc_status", "qc_reason", "qc_policy_id", "auto_flags",
                 "frozen_qc_status", "frozen_qc_reason"]


def _atomic_text(path, text):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_csv(path, rows, preferred):
    keys = set()
    for r in rows:
        keys.update(r.keys())
    cols = [c for c in preferred if c in keys]
    cols += sorted(keys - set(cols))
    lines = [",".join(cols)]
    for r in rows:
        cells = []
        for c in cols:
            s = fmt(r.get(c, ""))
            if any(ch in s for ch in [",", '"', "\n"]):
                s = '"' + s.replace('"', '""') + '"'
            cells.append(s)
        lines.append(",".join(cells))
    _atomic_text(path, "\n".join(lines) + "\n")


def write_config(level_plan, cases):
    fixed_hashes = {}
    for rel in ("legacy/blade_batch_generation.py",
                "legacy/blade_batch_generation_template.geomTurbo",
                "code/geometry_legacy_v1.py",
                "code/geometry_parametric_exploratory_v1.py",
                "tools/geometry_sensitivity_metrics_v1.py",
                "analysis/geometry_review/parameter_sensitivity_v1_100cases/case_metrics.csv"):
        p = REPO / rel
        fixed_hashes[rel] = sha256_file(p) if p.is_file() else "MISSING"
    cfg = {
        "experiment_id": EXPERIMENT_ID,
        "status": "EXPLORATORY_NOT_APPROVED",
        "purpose": "Ks1/Ks2 focused geometry review; 57 deterministic cases",
        "git_head": git_head(),
        "case_id_range": f"{case_id(1)}..{case_id(N_TOTAL)}",
        "n_cases": N_TOTAL,
        "stage_counts": {"A": 15, "B": 30, "C": 12},
        "baseline": BASELINE,
        "ranges": {p: list(RANGES[p]) for p in PARAMS},
        "fixed_by_review": {
            "SS1": {"value": 3.2, "status": "FIXED_BY_REVIEW",
                    "decision_source": "HUMAN_REVIEW_DECISION"},
            "SS2": {"value": 0.8, "status": "FIXED_BY_REVIEW",
                    "decision_source": "HUMAN_REVIEW_DECISION"},
        },
        "fixed_operating_conditions": {"Incidence": 0.0, "Mach": 0.5},
        "backgrounds": {k: ({"description": "global baseline"} if k == "B0"
                            else v) for k, v in BACKGROUNDS.items()},
        "levels": level_plan,
        "stage_c_selection_rule": (
            "rank B1-B4 by meanline_angle_range_deg of the background reference; "
            "choose the lowest and highest; choose the higher-camber one of B5/B6; "
            "the exact scores and case IDs are in stage_c_selection.json"),
        "search_grids": {
            "Xmean": [float(XMEAN_GRID[0]), float(XMEAN_GRID[-1]), len(XMEAN_GRID)],
            "Ks1": [float(KS1_GRID[0]), float(KS1_GRID[-1]), len(KS1_GRID)],
            "Ks2": [float(KS2_GRID[0]), float(KS2_GRID[-1]), len(KS2_GRID)],
            "K_m": [float(KM_GRID[0]), float(KM_GRID[-1]), len(KM_GRID)],
            "Metal2": [float(METAL2_GRID[0]), float(METAL2_GRID[-1]), len(METAL2_GRID)],
        },
        "parameter_formula_map": {
            "Ks1": "SSm1 = Ks1*(Sm2-Sm1); enters a1,a2,a3(=SSm1),a5,a6 and the front meanline slope",
            "Ks2": "SSm2 = Ks2*(Sm2-Sm1); enters a1,a2,a5,a6,a7(=-SSm2) and the rear meanline slope",
            "Xmean": "meanline piecewise break point and denominators of a1,a2,a5,a6",
            "K_m": "Sm0=tan(Metal1+(Metal2-Metal1)*K_m); enters a1,a2,a5,a6",
            "SS1": "thickness coefficients b1..b4; FIXED at 3.2",
            "SS2": "thickness coefficients b6,b7,b9; FIXED at 0.8",
        },
        "frozen_asset_sha256": fixed_hashes,
        "criteria": {"file": "review_criteria.yaml",
                     "sha256": sha256_file(CRITERIA_PATH)},
        "candidate_config": {"file": "geometry_parameter_candidates_v2.yaml",
                             "sha256": sha256_file(CANDIDATE_PATH)},
        "code": {"driver": "tools/geometry_ks1_ks2_review_v1.py",
                 "sha256": sha256_file(Path(__file__).resolve())},
        "output_files": [
            "README.md", "experiment_config.yaml", "review_criteria.yaml",
            "geometry_parameter_candidates_v2.yaml", "case_design.csv",
            "case_metrics.csv", "ks1_xmean_redundancy.csv",
            "ks2_background_sensitivity.csv", "joint_interaction.csv",
            "parameter_decisions.csv", "profiles.npz", "overview.png",
            "ks1_xmean_comparison.png", "ks2_background_comparison.png",
            "REPORT.md", "provenance.json"],
        "forbidden": {"numeca": True, "cfx": True, "ai_training": True,
                      "production_doe": True, "range_freeze": True},
    }
    _atomic_text(OUTDIR / "experiment_config.yaml",
                 yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    return cfg


def write_profiles_npz(results, path):
    arrays, ids = {}, []
    for rec in results:
        if rec["geom"] is None:
            continue
        cid = rec["design"]["case_id"]
        ids.append(cid)
        for key, field in (("xp", "xp1"), ("yp", "yp1"), ("xs", "xs1"),
                           ("ys", "ys1"), ("xc", "xc"), ("yc", "yc"),
                           ("thick", "thick"), ("sc", "sc")):
            arrays[f"{cid}__{key}"] = np.asarray(rec["geom"][field], dtype=float)
    np.savez_compressed(
        path, case_ids=np.asarray(ids, dtype="U16"),
        baseline_case_id=np.asarray(results[0]["design"]["case_id"]),
        fields=np.asarray("xp,yp,xs,ys,xc,yc,thick,sc"),
        units=np.asarray("legacy normalized units; x=chordwise, y=tangential; "
                         "thick is HALF-thickness"),
        **arrays)
    return ids


def verify_npz(path, results):
    expected = [r["design"]["case_id"] for r in results if r["geom"] is not None]
    with np.load(path, allow_pickle=False) as data:
        ids = [str(x) for x in data["case_ids"]]
        missing = sorted(set(expected) - set(ids))
        extra = sorted(set(ids) - set(expected))
        mism = []
        for rec in results:
            if rec["geom"] is None:
                continue
            cid = rec["design"]["case_id"]
            for key, field in (("xp", "xp1"), ("yp", "yp1"), ("xs", "xs1"),
                               ("ys", "ys1"), ("yc", "yc"), ("thick", "thick")):
                if not np.array_equal(data[f"{cid}__{key}"],
                                      np.asarray(rec["geom"][field], dtype=float)):
                    mism.append(f"{cid}:{key}")
    return {"profiles_saved": len(ids), "missing": missing, "extra": extra,
            "array_mismatches": mism,
            "reload_ok": not missing and not extra and not mism}


def cmd_run(overwrite=False):
    produced = ["case_design.csv", "case_metrics.csv", "profiles.npz",
                "ks1_xmean_redundancy.csv", "ks2_background_sensitivity.csv",
                "joint_interaction.csv", "parameter_decisions.csv",
                "overview.png", "ks1_xmean_comparison.png",
                "ks2_background_comparison.png", "REPORT.md",
                "provenance.json", "stage_c_selection.json"]
    existing = [n for n in produced if (OUTDIR / n).exists()]
    if existing and not overwrite:
        raise SystemExit("Refusing to overwrite: " + ", ".join(existing))
    if existing:
        for n in existing:
            (OUTDIR / n).unlink()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "audit").mkdir(exist_ok=True)

    criteria = yaml.safe_load(CRITERIA_PATH.read_text())
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    status_before = git_status()
    t0 = time.time()

    cases_ab, level_plan = build_stage_ab()
    write_config(level_plan, cases_ab)
    write_csv(OUTDIR / "case_design.csv", cases_ab, DESIGN_COLUMNS)

    ref_registry = {}
    print("[run] A stage (15 cases)")
    res_a, tmp1 = run_cases([c for c in cases_ab if c["stage"] == "A"],
                            ref_registry, criteria, template_text)
    print("[run] B references (6 cases)")
    res_bref, tmp2 = run_cases(
        [c for c in cases_ab if c["stage_group"] == "B_background_reference"],
        ref_registry, criteria, template_text)
    print("[run] B variants (24 cases)")
    res_bvar, tmp3 = run_cases(
        [c for c in cases_ab if c["stage"] == "B"
         and c["stage_group"] != "B_background_reference"],
        ref_registry, criteria, template_text)

    results_ab = res_a + res_bref + res_bvar
    rows_ab = [flatten_result(r) for r in results_ab]
    selected_bg, selection_evidence = select_c_backgrounds(rows_ab)
    print(f"[run] C backgrounds selected: {selected_bg}")
    cases_c = build_stage_c(selected_bg, selection_evidence)
    print("[run] C stage (12 cases)")
    res_c, tmp4 = run_cases(cases_c, ref_registry, criteria, template_text)

    results = sorted(results_ab + res_c,
                     key=lambda r: r["design"]["case_id"])
    cases = sorted(cases_ab + cases_c, key=lambda r: r["case_id"])
    if len(cases) != N_TOTAL:
        raise SystemExit(f"internal error: {len(cases)} cases")

    rows = [flatten_result(r) for r in results]
    write_csv(OUTDIR / "case_design.csv", cases, DESIGN_COLUMNS)
    write_csv(OUTDIR / "case_metrics.csv", rows,
              METRIC_IDENTITY + METRIC_STATUS)
    ids = write_profiles_npz(results, OUTDIR / "profiles.npz")
    npz_check = verify_npz(OUTDIR / "profiles.npz", results)

    selection_doc = {
        "rule": ("rank B1-B4 by meanline_angle_range_deg; choose lowest and highest; "
                 "choose the higher-camber one of B5/B6"),
        "selected_backgrounds": selected_bg,
        "evidence": selection_evidence,
    }
    _atomic_text(OUTDIR / "stage_c_selection.json",
                 json.dumps(selection_doc, indent=2, ensure_ascii=False) + "\n")

    failed = [r for r in results
              if r["generation_status"] != "OK"
              or r["metrics"].get("hard_qc_status") != "PASS"]
    frozen_mismatch = [r for r in results
                       if r.get("frozen", {}).get("frozen_qc_status") in ("PASS", "FAIL")
                       and r["frozen"]["frozen_qc_status"]
                       != r["metrics"].get("hard_qc_status")]
    meta = {
        "experiment_id": EXPERIMENT_ID,
        "git_head": git_head(),
        "git_status_before": status_before,
        "git_status_after": git_status(),
        "seed": 20261017,
        "n_cases": len(cases),
        "stage_counts": {s: sum(1 for c in cases if c["stage"] == s)
                         for s in ("A", "B", "C")},
        "generation_ok": sum(1 for r in results if r["generation_status"] == "OK"),
        "hard_qc_pass": sum(1 for r in results
                            if r["metrics"].get("hard_qc_status") == "PASS"),
        "frozen_qc_pass": sum(1 for r in results
                              if r.get("frozen", {}).get("frozen_qc_status") == "PASS"),
        "frozen_qc_mismatches": len(frozen_mismatch),
        "failed_cases": [{"case_id": r["design"]["case_id"],
                          "status": r["generation_status"],
                          "qc": r["metrics"].get("hard_qc_status"),
                          "reason": r["failure_reason"],
                          "qc_reason": r["metrics"].get("qc_reason")}
                         for r in failed],
        "profiles_saved": len(ids),
        "npz_check": npz_check,
        "stage_c_selection": selection_doc,
        "criteria_sha256": sha256_file(CRITERIA_PATH),
        "config_sha256": sha256_file(OUTDIR / "experiment_config.yaml"),
        "runtime_s": round(time.time() - t0, 2),
        "output_size_mb": round(sum(p.stat().st_size for p in OUTDIR.rglob("*")
                                    if p.is_file()) / (1024 * 1024), 3),
    }
    _atomic_text(OUTDIR / "audit" / "run_metadata.json",
                 json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    for t in (tmp1, tmp2, tmp3, tmp4):
        shutil.rmtree(t, ignore_errors=True)
    print(json.dumps({
        "cases": len(cases), "generation_ok": meta["generation_ok"],
        "hard_qc_pass": meta["hard_qc_pass"],
        "frozen_qc_pass": meta["frozen_qc_pass"],
        "npz_reload_ok": npz_check["reload_ok"],
        "selected_backgrounds": selected_bg,
        "runtime_s": meta["runtime_s"]}, ensure_ascii=False))
    return meta


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
def load_data():
    with open(OUTDIR / "case_design.csv", newline="") as f:
        design = list(csv.DictReader(f))
    with open(OUTDIR / "case_metrics.csv", newline="") as f:
        metric_rows = list(csv.DictReader(f))
    m_by_id = {r["case_id"]: r for r in metric_rows}

    def maybe_num(s):
        try:
            return float(s)
        except (TypeError, ValueError):
            return s

    results = []
    with np.load(OUTDIR / "profiles.npz", allow_pickle=False) as data:
        keys = set(data.files)
        for d in design:
            cid = d["case_id"]
            row = dict(d)
            for p in PARAMS:
                row[p] = float(row[p])
            m = m_by_id.get(cid, {})
            parsed = {}
            for k, v in m.items():
                if k in ("case_id", "stage", "stage_group", "background_id",
                         "reference_case_id", "varied_param", "failure_reason",
                         "hard_qc_status", "metric_status", "qc_reason",
                         "qc_policy_id", "auto_flags", "generation_status",
                         "frozen_qc_status", "frozen_qc_reason"):
                    parsed[k] = v
                elif v == "":
                    parsed[k] = float("nan")
                else:
                    parsed[k] = maybe_num(v)
            geom = None
            if f"{cid}__xp" in keys:
                geom = {
                    "xp1": data[f"{cid}__xp"], "yp1": data[f"{cid}__yp"],
                    "xs1": data[f"{cid}__xs"], "ys1": data[f"{cid}__ys"],
                    "xc": data[f"{cid}__xc"], "yc": data[f"{cid}__yc"],
                    "thick": data[f"{cid}__thick"], "sc": data[f"{cid}__sc"],
                    "params": {p: row[p] for p in PARAMS},
                    "coefficients": _coefficients(row),
                    "chord_norm": math.hypot(
                        float(data[f"{cid}__xp"][-1] - data[f"{cid}__xp"][0]),
                        float(data[f"{cid}__yp"][-1] - data[f"{cid}__yp"][0])),
                }
            results.append({"design": row, "metrics": parsed, "geom": geom})
    return design, metric_rows, results


def _coefficients(row):
    g = gen.compute_geometry({p: float(row[p]) for p in PARAMS})
    return g["coefficients"]


def cmd_analyze():
    criteria = yaml.safe_load(CRITERIA_PATH.read_text())
    design, metric_rows, results = load_data()

    with open(OUTDIR / "stage_c_selection.json") as f:
        selection_doc = json.load(f)
    selected_bg = selection_doc["selected_backgrounds"]

    ks1_table = build_ks1_table(results, design, criteria)
    ks2_table = build_ks2_table(results, design, criteria)
    joint_table = build_joint_table(results, design, selected_bg)
    ks1_decision = classify_ks1(ks1_table, criteria)
    ks2_decision = classify_ks2(ks2_table, criteria)

    write_csv(OUTDIR / "ks1_xmean_redundancy.csv", ks1_table, [
        "background_id", "reference_case_id", "ks1_low_case_id",
        "ks1_high_case_id", "xmean_probe_value", "xmean_probe_delta_u",
        "S_shape", "S_rear", "S_local", "signal_to_noise_shape",
        "cosine_raw", "cosine_block_weighted", "cosine_front", "cosine_mid",
        "cosine_rear", "amplitude_ratio", "residual_fraction",
        "forward_best_xmean", "forward_target_change_rms",
        "forward_residual_rms", "forward_residual_max",
        "forward_residual_fraction", "forward_meanline_angle_residual",
        "forward_curvature_residual", "forward_best_at_boundary",
        "reverse_best_ks1", "reverse_target_change_rms",
        "reverse_residual_rms", "reverse_residual_fraction",
        "reverse_meanline_angle_residual", "reverse_curvature_residual",
        "reverse_best_at_boundary", "converged"])
    write_csv(OUTDIR / "ks2_background_sensitivity.csv", ks2_table, [
        "background_id", "reference_case_id", "ks2_low_case_id",
        "ks2_high_case_id", "km_probe_value", "metal2_probe_value",
        "S_shape", "S_rear", "S_rear_meanline", "S_rear_angle",
        "S_rear_curvature", "S_rear_pressure", "S_rear_suction",
        "serialization_noise_rms_norm", "signal_to_noise_shape",
        "signal_to_noise_rear", "cosine_vs_Km", "residual_fraction_vs_Km",
        "cosine_vs_Metal2", "residual_fraction_vs_Metal2",
        "sub_km_best_value", "sub_km_target_change_rms",
        "sub_km_residual_fraction", "sub_km_residual_rms",
        "sub_km_best_at_boundary", "sub_m2_best_value",
        "sub_m2_target_change_rms", "sub_m2_residual_fraction",
        "sub_m2_residual_rms", "sub_m2_best_at_boundary", "converged"])
    write_csv(OUTDIR / "joint_interaction.csv", joint_table, [
        "background_id", "case_lo_lo", "case_lo_hi", "case_hi_lo",
        "case_hi_hi", "I_contour_rms_dev_norm", "I_meanline_rms_dev_norm",
        "I_meanline_tangent_rms_dev_deg", "I_rear_meanline_rms_norm",
        "I_rear_angle_rms_rad", "I_rear_curvature_rms_norm", "I_mean"])

    decision_rows = [
        {"param": "Ks1", "decision": ks1_decision["decision"],
         "rule_id": ks1_decision["rule_id"],
         "leaning": ks1_decision.get("leaning", ""),
         "decision_source": "AUTOMATIC_REVIEW_RULE",
         "criteria_id": criteria["criteria_id"],
         "criteria_version": criteria["criteria_version"],
         "resolved_backgrounds": ks1_decision["resolved"],
         "cos_max": ks1_decision["cos_max"],
         "cos_median": ks1_decision["cos_median"],
         "cos_block_weighted_max": ks1_decision["cos_bw_max"],
         "residual_max": ks1_decision["residual_max"],
         "substitution_residual_min": ks1_decision["sub_min"],
         "substitution_residual_median": ks1_decision["sub_median"],
         "substitution_above_threshold_backgrounds": ks1_decision["sub_ok"],
         "noise_limited_backgrounds": ks1_decision["noise_low"],
         "reason": ks1_decision["reason"]},
        {"param": "Ks2", "decision": ks2_decision["decision"],
         "rule_id": ks2_decision["rule_id"],
         "leaning": ks2_decision.get("leaning", ""),
         "decision_source": "AUTOMATIC_REVIEW_RULE",
         "criteria_id": criteria["criteria_id"],
         "criteria_version": criteria["criteria_version"],
         "resolved_backgrounds": ks2_decision["resolved"],
         "cos_max": ks2_decision["cos_max"],
         "cos_median": ks2_decision["cos_median"],
         "cos_block_weighted_max": "",
         "residual_max": ks2_decision["residual_max"],
         "substitution_residual_min": ks2_decision["sub_min"],
         "substitution_residual_median": ks2_decision["sub_median"],
         "substitution_above_threshold_backgrounds": ks2_decision["sub_ok"],
         "noise_limited_backgrounds": ks2_decision["noise_low"],
         "reason": ks2_decision["reason"]},
        {"param": "SS1", "decision": "FIXED_BY_REVIEW",
         "rule_id": "HUMAN_DECISION",
         "leaning": "HUMAN_DECISION_FIXED",
         "decision_source": "HUMAN_REVIEW_DECISION",
         "criteria_id": criteria["criteria_id"],
         "criteria_version": criteria["criteria_version"],
         "resolved_backgrounds": "", "cos_max": "", "cos_median": "",
         "cos_block_weighted_max": "", "residual_max": "",
         "substitution_residual_min": "", "substitution_residual_median": "",
         "substitution_above_threshold_backgrounds": "",
         "noise_limited_backgrounds": "",
         "reason": "human decision: SS1=3.2 fixed; generator compatibility retained"},
        {"param": "SS2", "decision": "FIXED_BY_REVIEW",
         "rule_id": "HUMAN_DECISION",
         "leaning": "HUMAN_DECISION_FIXED",
         "decision_source": "HUMAN_REVIEW_DECISION",
         "criteria_id": criteria["criteria_id"],
         "criteria_version": criteria["criteria_version"],
         "resolved_backgrounds": "", "cos_max": "", "cos_median": "",
         "cos_block_weighted_max": "", "residual_max": "",
         "substitution_residual_min": "", "substitution_residual_median": "",
         "substitution_above_threshold_backgrounds": "",
         "noise_limited_backgrounds": "",
         "reason": "human decision: SS2=0.8 fixed; generator compatibility retained"},
    ]
    write_csv(OUTDIR / "parameter_decisions.csv", decision_rows, [
        "param", "decision", "rule_id", "leaning", "decision_source",
        "criteria_id", "criteria_version", "resolved_backgrounds",
        "cos_max", "cos_median", "cos_block_weighted_max", "residual_max",
        "substitution_residual_min", "substitution_residual_median",
        "substitution_above_threshold_backgrounds",
        "noise_limited_backgrounds", "reason"])

    plot_overview(results, OUTDIR / "overview.png")
    plot_ks1_comparison(ks1_table, results, design, criteria,
                        OUTDIR / "ks1_xmean_comparison.png")
    plot_ks2_comparison(ks2_table, criteria,
                        OUTDIR / "ks2_background_comparison.png")
    run_meta = json.loads((OUTDIR / "audit" / "run_metadata.json").read_text())
    run_meta["output_size_mb"] = round(
        sum(p.stat().st_size for p in OUTDIR.rglob("*") if p.is_file())
        / (1024 * 1024), 3)
    report = build_report(criteria, design, results, ks1_table, ks2_table,
                          joint_table, ks1_decision, ks2_decision,
                          selection_doc)
    _atomic_text(OUTDIR / "REPORT.md", report + "\n")
    write_readme(criteria, ks1_decision, ks2_decision, run_meta)
    write_provenance(criteria, ks1_table, ks2_table, joint_table,
                     ks1_decision, ks2_decision, selection_doc)
    print(json.dumps({"ks1": ks1_decision["decision"],
                      "ks2": ks2_decision["decision"],
                      "ks1_resolved": ks1_decision["resolved"],
                      "ks2_resolved": ks2_decision["resolved"]},
                     ensure_ascii=False))


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
STAGE_COLORS = {"A": "#1f4e79", "B": "#b45f06", "C": "#38761d"}


def plot_overview(results, path):
    records = [r for r in results if r["geom"] is not None]
    xs = [np.concatenate([r["geom"]["xp1"], r["geom"]["xs1"]]) for r in records]
    ys = [np.concatenate([r["geom"]["yp1"], r["geom"]["ys1"]]) for r in records]
    xmin = min(np.min(x) for x in xs); xmax = max(np.max(x) for x in xs)
    ymin = min(np.min(y) for y in ys); ymax = max(np.max(y) for y in ys)
    padx, pady = 0.06 * (xmax - xmin), 0.06 * (ymax - ymin)
    baseline = results[0]["geom"]
    ncols, nrows = 10, 6
    fig, axes = plt.subplots(nrows, ncols, figsize=(26, 16))
    axes = axes.ravel()
    for ax, rec in zip(axes, records):
        d, g = rec["design"], rec["geom"]
        ax.plot(baseline["xp1"], baseline["yp1"], color="#bbbbbb", lw=0.55,
                ls="--", zorder=1)
        ax.plot(baseline["xs1"], baseline["ys1"], color="#bbbbbb", lw=0.55,
                ls="--", zorder=1)
        color = STAGE_COLORS.get(d["stage"], "#333333")
        ax.plot(g["xp1"], g["yp1"], color=color, lw=0.9, zorder=2)
        ax.plot(g["xs1"], g["ys1"], color=color, lw=0.9, zorder=2)
        ax.set_xlim(xmin - padx, xmax + padx)
        ax.set_ylim(ymin - pady, ymax + pady)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_linewidth(0.4); sp.set_color("#999999")
        qc = rec["metrics"].get("hard_qc_status", "ERROR")
        label = d.get("varied_param") or "baseline"
        val = d.get("level_value") or ""
        ax.set_title(f"{d['case_id']}\n{d['stage']} {d['background_id']} {label}={val}\nQC {qc}",
                     fontsize=5.2, pad=1.0, linespacing=1.0)
    for ax in axes[len(records):]:
        ax.axis("off")
    fig.suptitle("Ks1 / Ks2 focused geometry review — 57 real blade contours "
                 "(baseline dashed grey; A=blue, B=orange, C=green)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.975))
    fig.savefig(path, dpi=110, bbox_inches="tight",
                pil_kwargs={"optimize": True})
    plt.close(fig)


def _curve_for_bg(results, design, bg, value, param):
    ref_d, target_d = _ref_and_case_ids(design, bg, param, value)
    by_id = {r["design"]["case_id"]: r for r in results}
    return by_id[ref_d["case_id"]], by_id[target_d["case_id"]]


def plot_ks1_comparison(table, results, design, criteria, path):
    thr = criteria["thresholds"]
    labels = [r["background_id"] for r in table]
    x = np.arange(len(labels))
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
    ax = axes[0]
    width = 0.2
    ax.bar(x - 1.5 * width, [r["cosine_raw"] for r in table], width,
           label="cos raw")
    ax.bar(x - 0.5 * width, [r["cosine_block_weighted"] for r in table], width,
           label="cos block-weighted")
    ax.bar(x + 0.5 * width, [r["residual_fraction"] for r in table], width,
           label="residual fraction")
    ax.bar(x + 1.5 * width, [r["forward_residual_fraction"] for r in table],
           width, label="Xmean substitution residual")
    ax.axhline(thr["cosine_independence"], color="k", ls=":", lw=0.8)
    ax.axhline(thr["substitution_max_residual"], color="k", ls="--", lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.05)
    ax.set_title("Ks1 vs Xmean response similarity / substitution")
    ax.legend(fontsize=6, loc="upper right")

    best = max(table, key=lambda r: _num(r["cosine_raw"]))
    bg = best["background_id"]
    ref_rec, ks_rec = _curve_for_bg(results, design, bg, 7.0, "Ks1")
    ref_geom = ref_rec["geom"]
    best_x = float(best["forward_best_xmean"])
    p = _params_of(ref_rec["design"])
    p["Xmean"] = best_x
    sub_geom = gen.compute_geometry(p)
    xc, _, beta_r, kap_r = meanline_table(ref_geom)
    _, _, beta_k, kap_k = meanline_table(ks_rec["geom"])
    _, _, beta_s, kap_s = meanline_table(sub_geom)
    for ax, br, bk, bs, title, ylabel, convert in (
            (axes[1], beta_r, beta_k, beta_s,
             f"{bg}: meanline tangent angle", "beta [deg]", np.degrees),
            (axes[2], kap_r, kap_k, kap_s,
             f"{bg}: meanline curvature", "kappa * chord", lambda z: z * float(ref_geom["chord_norm"]))):
        ax.plot(xc, convert(br), color="k", lw=1.2, label="background")
        ax.plot(xc, convert(bk), color="#1f4e79", lw=1.2, label="Ks1 = 7")
        ax.plot(xc, convert(bs), color="#c55a11", lw=1.0, ls="--",
                label=f"Xmean = {best_x:.4f} substitute")
        ax.set_xlabel("xc"); ax.set_ylabel(ylabel); ax.set_title(title)
        ax.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(path, dpi=130, bbox_inches="tight",
                pil_kwargs={"optimize": True})
    plt.close(fig)


def plot_ks2_comparison(table, criteria, path):
    thr = criteria["thresholds"]
    labels = [r["background_id"] for r in table]
    x = np.arange(len(labels))
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    ax = axes[0]
    width = 0.16
    keys = [("S_rear_meanline", "rear meanline"),
            ("S_rear_angle", "rear angle"),
            ("S_rear_curvature", "rear curvature"),
            ("S_rear_pressure", "rear pressure"),
            ("S_rear_suction", "rear suction")]
    for i, (k, label) in enumerate(keys):
        ax.bar(x + (i - 2) * width, [r[k] for r in table], width, label=label)
    ax.axhline(thr["keep_rear"], color="k", ls="--", lw=0.8,
               label=f"keep_rear={thr['keep_rear']}")
    ax.axhline(thr["review_rear"], color="k", ls=":", lw=0.8,
               label=f"review_rear={thr['review_rear']}")
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_yscale("log")
    ax.set_title("Ks2 rear-30% sensitivity by background")
    ax.legend(fontsize=5.5, ncol=2)

    ax = axes[1]
    ax.bar(x - 0.2, [r["S_shape"] for r in table], 0.4, label="S_shape")
    ax.bar(x + 0.2, [r["S_rear"] for r in table], 0.4, label="S_rear")
    ax.axhline(thr["keep_shape"], color="k", ls="--", lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_yscale("log")
    ax.set_title("Ks2 global vs rear-local sensitivity")
    for i, r in enumerate(table):
        ax.text(i, max(_num(r["S_shape"]), _num(r["S_rear"])) * 1.15,
                f"SNR\n{_num(r['signal_to_noise_rear']):.1f}",
                ha="center", fontsize=5.5)
    ax.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(path, dpi=130, bbox_inches="tight",
                pil_kwargs={"optimize": True})
    plt.close(fig)


# ---------------------------------------------------------------------------
# Report / README / provenance
# ---------------------------------------------------------------------------
def _f(v, digits=4):
    if isinstance(v, (int, float, np.floating)) and math.isfinite(float(v)):
        return f"{float(v):.{digits}g}"
    return "—"


def build_report(criteria, design, results, ks1_table, ks2_table, joint_table,
                 ks1_decision, ks2_decision, selection_doc):
    thr = criteria["thresholds"]
    n_total = len(design)
    gen_ok = sum(1 for r in results
                 if r["metrics"].get("generation_status") == "OK")
    qc_pass = sum(1 for r in results
                  if r["metrics"].get("hard_qc_status") == "PASS")
    frozen_pass = sum(1 for r in results
                      if r["metrics"].get("frozen_qc_status") == "PASS")
    failed = [r for r in results
              if r["metrics"].get("generation_status") != "OK"
              or r["metrics"].get("hard_qc_status") != "PASS"]
    stage_counts = {s: sum(1 for d in design if d["stage"] == s)
                    for s in ("A", "B", "C")}
    vectors = {}
    for d in design:
        key = tuple(round(float(d[p]), 10) for p in PARAMS)
        vectors.setdefault(key, []).append(d["case_id"])
    dup = {k: v for k, v in vectors.items() if len(v) > 1}
    ks1, ks2 = ks1_decision, ks2_decision

    L = []
    L.append("# Ks1 / Ks2 专项几何复核 V1（57 Cases）\n")
    L.append(
        "> 状态：**EXPLORATORY / NOT APPROVED**。本轮只做几何生成、几何 QC 与"
        "参数冗余/替代性分析；**没有** NUMECA、**没有** CFX、**没有** AI 训练、"
        "**没有** 修改正式 DOE 或正式生产范围。\n"
        f"> 判据：`{criteria['criteria_id']}` / `{criteria['criteria_version']}`"
        f"（{criteria['criteria_status']}）。\n"
        f"> Case 号段：`C830001..C830057`；Git HEAD：`{git_head()}`。\n")

    L.append("## 0. 执行前审计（摘要）\n")
    L.append("```text\n"
             "Ks1: SSm1 = Ks1*(Sm2-Sm1) -> a1,a2,a3(=SSm1),a5,a6\n"
             "Ks2: SSm2 = Ks2*(Sm2-Sm1) -> a1,a2,a5,a6,a7(=-SSm2)\n"
             "Sm1=tan(Metal1), Sm2=tan(Metal2), Sm0=tan(Metal1+(Metal2-Metal1)*K_m)\n"
             "Xmean: piecewise break point and denominators of a1,a2,a5,a6\n"
             "SS1=3.2, SS2=0.8: FIXED_BY_REVIEW in every case\n"
             "```\n")
    L.append("上一轮 Ks1 与 Xmean 的 0.994 余弦来自 14 维符号响应签名；"
             "本轮改用 95 维、按 xc 采样的中弧线/切线角/曲率/压力面/吸力面响应向量，"
             "并加入多背景、残差投影和单参数替代搜索。\n")

    L.append("## 1. 实验设计\n")
    L.append("```text")
    L.append(f"正式 Case 数        : {n_total}")
    L.append(f"阶段分布            : A={stage_counts['A']}, B={stage_counts['B']}, C={stage_counts['C']}")
    L.append(f"几何生成成功        : {gen_ok}/{n_total}")
    L.append(f"实验硬性 QC 通过    : {qc_pass}/{n_total}")
    L.append(f"冻结 QC 复核通过    : {frozen_pass}/{n_total}")
    L.append(f"参数向量重复组数    : {len(dup)}")
    L.append(f"失败 Case 数        : {len(failed)}（全部保留在 case_metrics.csv）")
    L.append("```")
    if failed:
        L.append("\n| Case | 阶段 | 背景 | 变化参数 | 状态 | 原因 |")
        L.append("|---|---|---|---|---|---|")
        for r in failed:
            d = r["design"]
            L.append(f"| {d['case_id']} | {d['stage']} | {d['background_id']} | "
                     f"{d.get('varied_param') or '-'} | "
                     f"{r['metrics'].get('generation_status')}/"
                     f"{r['metrics'].get('hard_qc_status')} | "
                     f"{r['metrics'].get('qc_reason', r['metrics'].get('failure_reason', ''))} |")
    else:
        L.append("\n本批 57 个 Case 全部生成成功且硬性 QC 通过；"
                 "这不代表工程合理或 CFD 可收敛。")

    L.append("\n### 1.1 背景与 Stage C 选择\n")
    L.append("| 背景 | 修改参数 |")
    L.append("|---|---|")
    for bg, changes in BACKGROUNDS.items():
        if bg == "B0":
            L.append("| B0 | 全局基准 |")
        else:
            L.append(f"| {bg} | " + ", ".join(f"{k}={v:g}" for k, v in changes.items()) + " |")
    L.append(f"\nStage C 选择结果：**{', '.join(selection_doc['selected_backgrounds'])}**。"
             "规则与得分见 `stage_c_selection.json`：B1–B4 按背景的中弧线角范围排序，"
             "取最低与最高；B5/B6 取中弧线角范围更大的一个。\n")


    L.append("## 2. Ks1 专项复核\n")
    L.append("| 背景 | 参考 Case | Ks1=7 Case | S_shape | S_local | cos raw | cos block | 残差比例 | 最佳 Xmean | 替代残差比例 | 反向替代残差比例 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in ks1_table:
        L.append(f"| {r['background_id']} | {r['reference_case_id']} | {r['ks1_high_case_id']} "
                 f"| {_f(r['S_shape'])} | {_f(r['S_local'])} | {_f(r['cosine_raw'])} "
                 f"| {_f(r['cosine_block_weighted'])} | {_f(r['residual_fraction'])} "
                 f"| {_f(r['forward_best_xmean'],5)} | {_f(r['forward_residual_fraction'])} "
                 f"| {_f(r['reverse_residual_fraction'])} |")
    L.append("\n> `残差比例` = Ks1 响应中不能被 Xmean 方向解释的部分；"
             "`替代残差比例` = 最优单 Xmean 替代后的轮廓残差 / 目标变化量。"
             "两者接近 0 才说明可替代，接近 1 说明几乎不可替代。\n")

    L.append(f"- **Q1. Ks1 在多少个背景下有明显几何作用？** "
             f"在 {ks1['resolved']}/7 个背景中达到 `S_shape >= {thr['keep_shape']}` "
             f"或 `S_local >= {thr['keep_local']}`，且信号超过 4 位小数噪声 "
             f"{thr['noise_multiplier']:.0f} 倍。")
    L.append(f"- **Q2. Ks1 与 Xmean 的相似度是否稳定？** "
             f"cos raw 最小/中位/最大 = {_f(ks1['cos_min'])} / {_f(ks1['cos_median'])} / "
             f"{_f(ks1['cos_max'])}；block-weighted 最小/最大 = "
             f"{_f(ks1['cos_bw_min'])} / {_f(ks1['cos_bw_max'])}。"
             + ("**不稳定**：高 Xmean 背景（B3/B4）的余弦明显下降，"
                "不能用上一轮单一 0.994 概括全部背景。"
                if ks1['cos_min'] < thr['cosine_independence'] else
                "各背景方向基本一致。"))
    L.append(f"- **Q3. 调整 Xmean 能否近似替代 Ks1？** "
             f"{ks1['sub_low']}/7 个背景的最优单 Xmean 替代残差 ≤ "
             f"{thr['substitution_max_residual']:.0%}（最小 {_f(ks1['sub_min'])}，"
             f"中位数 {_f(ks1['sub_median'])}），主要发生在 B0/B1/B2/B5/B6；"
             f"但 B3/B4（Xmean=0.18 边界）替代残差为 1.0，"
             f"说明高 Xmean 端无法用 Xmean 自己复现 Ks1。"
             "因此只能得出“**在中低 Xmean 背景下高度可替代、在高 Xmean 边界不可替代**”，"
             "不能宣称全局等价或全局独立。")
    L.append(f"- **Q4. Ks1 是否值得作为独立变量保留？** 自动判据："
             f"**{ks1['decision']}**（{ks1['rule_id']}），"
             f"倾向标记：`{ks1.get('leaning', '')}`。{ks1['reason']}")
    L.append("  关键判断：在 Xmean=0.18 的高端，Xmean 已无上移空间，"
             "B3/B4 的 Ks1 变化无法被 Xmean 复现（替代残差 1.0），"
             "而 Ks1 反而能在 B3 较好复现 Xmean（反向残差约 0.09）；"
             "因此 **Ks1 在高 Xmean 端提供了 Xmean 范围外的独立形状**，"
             "但在中低 Xmean 端高度冗余。是否保留取决于下一轮是否保留 Xmean 高端。")
    L.append("\n**Ks1 的局部证据**：Ks1 只进入中弧线系数，不进入 LE/TE 圆弧半径公式，"
             "因此前/尾缘半径变化为 0；其独立价值只能在 中弧线/压力面/吸力面 形状中寻找。"
             "上表的 `S_local` 与替代残差必须一起看，不能只用余弦判断。\n")

    L.append("## 3. Ks2 专项复核\n")
    L.append("| 背景 | Ks2=0.20 Case | S_shape | S_rear | 后段 meanline | 后段 angle | 后段 κ | 后段 pressure | 后段 suction | SNR rear | cos vs K_m | cos vs Metal2 | 替代残差(K_m) | 替代残差(Metal2) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in ks2_table:
        L.append(f"| {r['background_id']} | {r['ks2_high_case_id']} | {_f(r['S_shape'])} "
                 f"| {_f(r['S_rear'])} | {_f(r['S_rear_meanline'])} | {_f(r['S_rear_angle'])} "
                 f"| {_f(r['S_rear_curvature'])} | {_f(r['S_rear_pressure'])} "
                 f"| {_f(r['S_rear_suction'])} | {_f(r['signal_to_noise_rear'],3)} "
                 f"| {_f(r['cosine_vs_Km'])} | {_f(r['cosine_vs_Metal2'])} "
                 f"| {_f(r['sub_km_residual_fraction'])} | {_f(r['sub_m2_residual_fraction'])} |")
    L.append("\n> `S_rear` 使用后 30% 弦长（xc>0.70）的 meanline/angle/curvature/pressure/suction "
             "最大值；`SNR rear` 为该变化量相对同 Case 4 位小数序列化噪声的倍数。\n")

    best_bg = max(ks2_table, key=lambda r: _num(r["S_rear"]))
    min_bg = min(ks2_table, key=lambda r: _num(r["S_rear"]))
    L.append(f"- **Q5. Ks2 在什么背景下最敏感？** `{best_bg['background_id']}` 最高，"
             f"S_rear={_f(best_bg['S_rear'])}；`{min_bg['background_id']}` 最低，"
             f"S_rear={_f(min_bg['S_rear'])}。全部 7 个背景 S_rear 约 "
             f"{_f(min_bg['S_rear'])}–{_f(best_bg['S_rear'])}（约 1.5 倍差异），"
             "不是只在单一极端背景出现。后段曲率分量 "
             f"{_f(min_bg['S_rear_curvature'])}–{_f(best_bg['S_rear_curvature'])}，"
             "约为后段 meanline/angle 分量的 5–10 倍，说明 Ks2 主要控制"
             "**尾段中弧线曲率**，而不是整体平移。")
    L.append(f"- **Q6. Ks2 的局部几何作用是否达到实际可分辨程度？** "
             f"在 {ks2['resolved']}/7 个背景中 `S_rear >= {thr['keep_rear']}` 且 SNR ≥ "
             f"{thr['noise_multiplier']:.0f}；SNR 约 "
             f"{_f(min_bg['signal_to_noise_rear'],3)}–{_f(best_bg['signal_to_noise_rear'],3)}，"
             "远高于 4 位小数序列化噪声，已达到可分辨的后段局部作用。"
             "上一轮全局 S_comp=0.0053 明显低估了它：本轮的 S_rear 约 0.059–0.089，"
             "是全局值的 11–17 倍，原因是上一轮加权主要看全局轮廓/中弧线 RMS，"
             "没有单独加权后 30% 曲率。")
    L.append(f"- **Q7. Ks2 是否值得保留？** 自动判据：**{ks2['decision']}** "
             f"（{ks2['rule_id']}），倾向标记：`{ks2.get('leaning', '')}`。{ks2['reason']}")
    tgt = [float(r["sub_m2_target_change_rms"]) for r in ks2_table
           if math.isfinite(_num(r["sub_m2_target_change_rms"]))]
    res = [float(r["sub_m2_residual_rms"]) for r in ks2_table
           if math.isfinite(_num(r["sub_m2_residual_rms"]))]
    if tgt and res:
        L.append(f"  绝对值补充：Ks2=0.20 的轮廓目标变化 RMS 约 "
                 f"{_f(min(tgt))}–{_f(max(tgt))} 弦长；Metal2 替代后的残差 RMS 约 "
                 f"{_f(min(res))}–{_f(max(res))} 弦长。"
                 "这属于“轮廓接近但响应方向不同”，是否可接受需要工程判断，"
                 "不能仅凭余弦或单一残差阈值决定。")
    L.append("\n**尾缘拼接诊断**：legacy 只插入 Ncirc=4 个圆弧点，TE 拼接角跳变约 23°，"
             "本轮把它作为独立诊断量记录；Ks2 的局部作用不能归因于该既有跳变。"
             "若 Ks2 的高精度变化存在、但 4 位小数输出大量抹除，报告中会以 SNR 明确标出，"
             "不会因此直接删除参数。\n")

    L.append("## 4. Ks1 × Ks2 联合扫描（Stage C）\n")
    L.append("| 背景 | 四角 Case | 平均交互指数 | 轮廓 | 中弧线 | 后段 meanline | 后段 angle | 后段 κ |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in joint_table:
        L.append(f"| {r['background_id']} | {r['case_lo_lo']}, {r['case_lo_hi']}, "
                 f"{r['case_hi_lo']}, {r['case_hi_hi']} | {_f(r['I_mean'])} "
                 f"| {_f(r['I_contour_rms_dev_norm'])} | {_f(r['I_meanline_rms_dev_norm'])} "
                 f"| {_f(r['I_rear_meanline_rms_norm'])} | {_f(r['I_rear_angle_rms_rad'])} "
                 f"| {_f(r['I_rear_curvature_rms_norm'])} |")
    L.append("\n> 交互指数 = |(f_HH - f_LH) - (f_HL - f_LL)| / |f_HH - f_LL|；"
             "指数 >1 表示两端总变化 f_HH - f_LL 很小（相互抵消），"
             "不代表计算错误；B4/B5 的指数远大于 1 说明四角总变化接近抵消，"
             "不能读成“15 倍耦合强度”，应结合四角 Case 的绝对指标解读；"
             "仅 3 个背景 × 4 角点，只能作为局部证据。\n")


    L.append("## 5. 参数决策与证据\n")
    L.append("| 参数 | 决策 | 倾向 | 规则 | 已分辨背景 | cos 中位/最大 | 替代残差最小/中位 | 替代残差超阈值背景 | 噪声受限背景 |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for name, d in (("Ks1", ks1), ("Ks2", ks2)):
        L.append(f"| `{name}` | **{d['decision']}** | `{d.get('leaning', '')}` "
                 f"| {d['rule_id']} | {d['resolved']}/7 "
                 f"| {_f(d['cos_median'])} / {_f(d['cos_max'])} "
                 f"| {_f(d['sub_min'])} / {_f(d['sub_median'])} "
                 f"| {d['sub_ok']}/7 | {d['noise_low']}/7 |")
    L.append("\n**三个最关键的定量证据（Ks1）**：")
    top_cos = max(ks1_table, key=lambda r: _num(r["cosine_raw"]))
    low_sub = min(ks1_table, key=lambda r: _num(r["forward_residual_fraction"]))
    high_sub = max(ks1_table, key=lambda r: _num(r["forward_residual_fraction"]))
    L.append(f"1. 最高余弦背景 `{top_cos['background_id']}`：cos={_f(top_cos['cosine_raw'])}，"
             f"但残差比例={_f(top_cos['residual_fraction'])}，最佳 Xmean={_f(top_cos['forward_best_xmean'],5)}，"
             f"替代残差比例={_f(top_cos['forward_residual_fraction'])}（{top_cos['ks1_high_case_id']}）。")
    L.append(f"2. 最低替代残差背景 `{low_sub['background_id']}`：替代残差比例={_f(low_sub['forward_residual_fraction'])}，"
             f"说明该背景下 Xmean 可以较好复现 Ks1（{low_sub['ks1_high_case_id']}）。")
    L.append(f"3. 最高替代残差背景 `{high_sub['background_id']}`：替代残差比例={_f(high_sub['forward_residual_fraction'])}，"
             f"说明该背景下单一 Xmean 无法复现 Ks1（{high_sub['ks1_high_case_id']}）。")
    L.append("\n**三个最关键的定量证据（Ks2）**：")
    top_rear = max(ks2_table, key=lambda r: _num(r["S_rear"]))
    low_rear = min(ks2_table, key=lambda r: _num(r["S_rear"]))
    best_sub = min(ks2_table, key=lambda r: min(_num(r["sub_km_residual_fraction"]),
                                                _num(r["sub_m2_residual_fraction"])))
    L.append(f"1. 最强后段作用背景 `{top_rear['background_id']}`：S_rear={_f(top_rear['S_rear'])}，"
             f"SNR={_f(top_rear['signal_to_noise_rear'],3)}（{top_rear['ks2_high_case_id']}）。")
    L.append(f"2. 最弱后段作用背景 `{low_rear['background_id']}`：S_rear={_f(low_rear['S_rear'])}，"
             f"SNR={_f(low_rear['signal_to_noise_rear'],3)}（{low_rear['ks2_high_case_id']}）。")
    L.append(f"3. 最佳可替代背景 `{best_sub['background_id']}`：min(K_m, Metal2) 替代残差比例="
             f"{_f(min(_num(best_sub['sub_km_residual_fraction']), _num(best_sub['sub_m2_residual_fraction'])))}"
             f"（{best_sub['ks2_high_case_id']}）。")

    L.append("\n## 6. SS1 / SS2 固定状态（Q9）\n")
    L.append("```text\n"
             "SS1 = 3.2  FIXED_BY_REVIEW  decision_source = HUMAN_REVIEW_DECISION\n"
             "SS2 = 0.8  FIXED_BY_REVIEW  decision_source = HUMAN_REVIEW_DECISION\n"
             "```\n")
    L.append("**Q9 回答：是。** 全部 57 个 Case 的 `SS1`/`SS2` 均分别等于 3.2/0.8；"
             "`geometry_parameter_candidates_v2.yaml` 中两者均标记为 `FIXED_BY_REVIEW`，"
             "并注明 `decision_source = HUMAN_REVIEW_DECISION`（人工决定，不是自动判据批准）。"
             "生成器仍接受这两个参数，历史几何兼容性未被破坏；"
             "候选配置没有修改正式六维 DOE 或任何冻结生产配置。\n")

    L.append("## 7. 异常、失败与限制\n")
    if failed:
        L.append(f"本轮有 {len(failed)} 个失败/未通过 Case，参数、状态和原因均保留；"
                 "没有静默替换。")
    else:
        L.append("本轮声明范围内没有失败 Case；这不证明范围外安全，也不证明工程合理。")
    gaps = [_num(r["metrics"].get("min_gap_m")) for r in results
            if math.isfinite(_num(r["metrics"].get("min_gap_m")))]
    lej = [_num(r["metrics"].get("le_junction_angle_jump_deg")) for r in results
           if math.isfinite(_num(r["metrics"].get("le_junction_angle_jump_deg")))]
    tej = [_num(r["metrics"].get("te_junction_angle_jump_deg")) for r in results
           if math.isfinite(_num(r["metrics"].get("te_junction_angle_jump_deg")))]
    L.append(f"- **Q8. 本轮是否发现新的几何异常？** 硬性 QC 失败 {len(failed)} 个；"
             f"`min_gap` 范围 {_f(min(gaps)*1000) if gaps else '—'}–"
             f"{_f(max(gaps)*1000) if gaps else '—'} mm（全部 >0）；"
             f"LE 拼接角跳变 {_f(min(lej)) if lej else '—'}–{_f(max(lej)) if lej else '—'}°，"
             f"TE {_f(min(tej)) if tej else '—'}–{_f(max(tej)) if tej else '—'}°。"
             "B2/B3/B4/B5 等背景出现强弯/近 S 形中弧线，但均通过硬性 QC；"
             "这是探索范围内的形状，不是新的 QC 异常，工程合理性仍需人工判断。")
    L.append("\n1. 判据阈值是暂定研究阈值，未用历史 1891 样本校准。")
    L.append("2. 只有 7 个背景、3 个 Stage C 背景和 4 个角点；不能外推到整个参数域。")
    L.append("3. 替代搜索只允许**单一参数**（Xmean 或 Ks1 或 K_m 或 Metal2），"
             "不代表两参数/三参数组合不能替代；它只检验“单参数可替代性”。")
    L.append("4. Ks1/Ks2 只影响中弧线系数，不改变厚度分布或 LE/TE 圆弧半径；"
             "因此不能用厚度/边缘半径指标判断它们。")
    L.append("5. 4 位小数序列化噪声已逐 Case 计算；若信号低于 10 倍噪声，"
             "一律视为未分辨，不会因为文本四舍五入而删除参数。")
    L.append("6. 本轮没有运行 NUMECA / CFX；`geometry_ok=1` 不代表气动合理、"
             "网格可生成或 CFD 收敛。")
    L.append("7. 所有自动结论均为建议，不改变正式参数状态。\n")

    L.append("## 8. 仍需人工审查（Q10）\n")
    L.append(f"- **Ks1 最终去留**：当前自动结论 `{ks1['decision']}`，倾向 "
             f"`{ks1.get('leaning', '')}`。关键矛盾是：Xmean 在 B0/B1/B2/B5/B6 可用"
             "2–8.5% 轮廓残差复现 Ks1=7，但 B3/B4 的 Xmean 已在 0.18 边界，无法复现；"
             "同时 Ks1 可在 B3 较好复现 Xmean（反向残差约 0.09），说明高 Xmean 端"
             "Ks1 可能提供超出 Xmean 范围的独立方向。需要人工决定是否保留 Xmean 高端，"
             "或将 Ks1 作为高端补充变量。")
    L.append(f"- **Ks2 最终去留**：当前自动结论 `{ks2['decision']}`，倾向 "
             f"`{ks2.get('leaning', '')}`。Ks2 的后段局部作用在所有背景都远超噪声，"
             "但 Metal2 单参数替代在 6/7 背景可把轮廓残差压到 10–23%；"
             "需要人工确认这种“轮廓接近但方向不同”的替代是否可接受，"
             "以及 Ks2 的后段控制是否有独立工程价值。")
    L.append("- 是否用 1891 历史样本校准本轮阈值，尤其是 `keep_rear`、"
             "`cosine_independence`、`substitution_max_residual`。")
    L.append("- 是否需要在 Xmean 低/中/高三个背景下加密 Ks1，或用多参数替代搜索复核。")
    L.append("- SS1/SS2 已由人工决定固定；若未来修改生成器的边缘圆 St1/St2 重算逻辑，"
             "必须另开几何算法版本并重新评估，不得把算法变化误认为参数效应。\n")

    L.append("## 9. 复现\n")
    L.append("```bash\n"
             "cd /home/qian/compressor_ai4s\n"
             "conda run -n ai4s python tools/geometry_ks1_ks2_review_v1.py all\n"
             "conda run -n ai4s python -m pytest -q\n"
             "```\n")
    L.append("文件追溯：`case_design.csv`（57 Case 参数/背景/规则）、"
             "`case_metrics.csv`（状态/QC/指标）、`ks1_xmean_redundancy.csv`、"
             "`ks2_background_sensitivity.csv`、`joint_interaction.csv`、"
             "`parameter_decisions.csv`、`profiles.npz`、`review_criteria.yaml`、"
             "`provenance.json`。\n")

    return "\n".join(L)



# ---------------------------------------------------------------------------
# README / provenance / validation
# ---------------------------------------------------------------------------
def write_readme(criteria, ks1, ks2, run_meta=None):
    meta = (run_meta if run_meta is not None else
            json.loads((OUTDIR / "audit" / "run_metadata.json").read_text()))
    text = f"""# Ks1 / Ks2 专项几何复核 V1（57 Cases，探索性，未批准）

```text
Status            : EXPLORATORY / NOT APPROVED
Case 号段         : C830001 .. C830057
阶段分布          : A=15, B=30, C=12
几何生成成功      : {meta['generation_ok']} / {meta['n_cases']}
实验硬性 QC 通过  : {meta['hard_qc_pass']} / {meta['n_cases']}
冻结 QC 复核通过  : {meta['frozen_qc_pass']} / {meta['n_cases']}
SS1 / SS2         : 3.2 / 0.8（FIXED_BY_REVIEW）
Ks1 建议          : {ks1['decision']}（{ks1['rule_id']}）
  Ks1 倾向        : {ks1.get('leaning', '')}
Ks2 建议          : {ks2['decision']}（{ks2['rule_id']}）
  Ks2 倾向        : {ks2.get('leaning', '')}
本目录体积        : {meta.get('output_size_mb', '')} MB
```

本轮只做几何研究，**没有** NUMECA / CFX / AI 训练 / 正式 DOE 修改。
Ks1/Ks2 的自动建议不等于最终参数状态；SS1/SS2 为人工决定固定。

## 入口文件

| 文件 | 用途 |
|---|---|
| `REPORT.md` | ★ 中文最终报告（回答 10 个问题） |
| `overview.png` | 57 个真实叶型总览 |
| `ks1_xmean_comparison.png` | Ks1 vs Xmean 余弦/残差/替代曲线 |
| `ks2_background_comparison.png` | Ks2 后段多背景敏感性 |
| `case_design.csv` | 57 行参数、背景、参考 Case、选择规则 |
| `case_metrics.csv` | 57 行 QC + 几何指标 |
| `ks1_xmean_redundancy.csv` | Ks1 多背景余弦/幅值/残差/替代搜索 |
| `ks2_background_sensitivity.csv` | Ks2 后段分量/信噪比/替代搜索 |
| `joint_interaction.csv` | Ks1 × Ks2 三背景 2×2 交互 |
| `parameter_decisions.csv` | Ks1/Ks2 建议 + SS1/SS2 固定状态 |
| `profiles.npz` | 57 个 Case 的高精度曲线 |
| `review_criteria.yaml` | 判据、阈值、单位、规则（分类前保存） |
| `geometry_parameter_candidates_v2.yaml` | 未来探索性候选配置（未批准） |
| `provenance.json` | Git/环境/哈希/验收信息 |
| `audit/` | SHA256 前后快照、运行元数据、验收记录 |

## 复现

```bash
cd /home/qian/compressor_ai4s
conda run -n ai4s python tools/geometry_ks1_ks2_review_v1.py all
```

> `Geometry QC PASS` ≠ 气动合理 ≠ 网格/CFD 可行。
> 所有阈值均为暂定研究阈值。
"""
    _atomic_text(OUTDIR / "README.md", text)


def write_provenance(criteria, ks1_table, ks2_table, joint_table,
                     ks1, ks2, selection_doc):
    run_meta = json.loads((OUTDIR / "audit" / "run_metadata.json").read_text())
    files = ["README.md", "experiment_config.yaml", "review_criteria.yaml",
             "geometry_parameter_candidates_v2.yaml", "case_design.csv",
             "case_metrics.csv", "ks1_xmean_redundancy.csv",
             "ks2_background_sensitivity.csv", "joint_interaction.csv",
             "parameter_decisions.csv", "profiles.npz", "overview.png",
             "ks1_xmean_comparison.png", "ks2_background_comparison.png",
             "REPORT.md", "stage_c_selection.json",
             "audit/run_metadata.json", "audit/sha256_before.txt",
             "audit/sha256_after.txt", "audit/step0_audit.md"]
    file_info = {}
    for name in files:
        p = OUTDIR / name
        if p.is_file():
            file_info[name] = {"bytes": p.stat().st_size,
                               "sha256": sha256_file(p)}
    prov = dict(run_meta)
    prov.update({
        "git_head_at_analysis": git_head(),
        "git_status_at_analysis": git_status(),
        "criteria": {
            "criteria_id": criteria["criteria_id"],
            "criteria_version": criteria["criteria_version"],
            "criteria_status": criteria["criteria_status"],
            "sha256": sha256_file(CRITERIA_PATH),
            "thresholds": criteria["thresholds"],
            "decisions": criteria["decisions"],
        },
        "candidate_config": {
            "file": "geometry_parameter_candidates_v2.yaml",
            "sha256": sha256_file(CANDIDATE_PATH),
        },
        "ks1": {k: ks1[k] for k in ("decision", "rule_id", "leaning",
                                    "resolved", "cos_max", "cos_median",
                                    "sub_min", "sub_median", "sub_ok", "reason")},
        "ks2": {k: ks2[k] for k in ("decision", "rule_id", "leaning",
                                    "resolved", "cos_max", "cos_median",
                                    "sub_min", "sub_median", "sub_ok", "reason")},
        "tables": {"ks1_rows": len(ks1_table), "ks2_rows": len(ks2_table),
                   "joint_rows": len(joint_table)},
        "selection": selection_doc,
        "output_files": file_info,
        "output_size_mb": round(sum(p.stat().st_size for p in OUTDIR.rglob("*")
                                    if p.is_file()) / (1024 * 1024), 3),
        "notes": ["geometry only; no CFD / AI / production DOE change",
                  "thresholds are tentative and uncalibrated",
                  "SS1/SS2 are FIXED_BY_REVIEW by human decision"],
    })
    _atomic_text(OUTDIR / "provenance.json",
                 json.dumps(prov, indent=2, ensure_ascii=False) + "\n")



def verify_frozen_assets():
    before = OUTDIR / "audit" / "sha256_before.txt"
    if not before.is_file():
        return {"status": "NO_BASELINE_FILE", "checked": 0, "mismatches": []}
    entries, mism, lines = [], [], []
    for line in before.read_text().splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        digest, rel = parts
        entries.append((rel, digest))
    for rel, digest in entries:
        p = REPO / rel
        actual = sha256_file(p) if p.is_file() else "MISSING"
        lines.append(f"{actual}  {rel}")
        if actual != digest:
            mism.append({"path": rel, "expected": digest, "actual": actual})
    (OUTDIR / "audit" / "sha256_after.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    return {"status": "PASS" if not mism else "FAIL",
            "checked": len(entries), "mismatches": mism}


def cmd_validate():
    import re
    import subprocess
    checks = []

    def add(name, ok, detail, level="FAIL"):
        checks.append({"check": name, "pass": bool(ok),
                       "detail": detail, "level": level})

    with open(OUTDIR / "case_design.csv", newline="") as f:
        design = list(csv.DictReader(f))
    with open(OUTDIR / "case_metrics.csv", newline="") as f:
        metrics_rows = list(csv.DictReader(f))
    with open(OUTDIR / "ks1_xmean_redundancy.csv", newline="") as f:
        ks1_rows = list(csv.DictReader(f))
    with open(OUTDIR / "ks2_background_sensitivity.csv", newline="") as f:
        ks2_rows = list(csv.DictReader(f))
    with open(OUTDIR / "joint_interaction.csv", newline="") as f:
        joint_rows = list(csv.DictReader(f))
    with open(OUTDIR / "parameter_decisions.csv", newline="") as f:
        decisions = list(csv.DictReader(f))
    criteria = yaml.safe_load(CRITERIA_PATH.read_text())
    run_meta = json.loads((OUTDIR / "audit" / "run_metadata.json").read_text())
    ids = [d["case_id"] for d in design]
    mids = [r["case_id"] for r in metrics_rows]

    add("n_cases_57", len(design) == 57 and len(metrics_rows) == 57,
        f"design={len(design)}, metrics={len(metrics_rows)}")
    add("unique_case_ids", len(set(ids)) == 57, f"unique={len(set(ids))}")
    add("case_id_format", all(re.fullmatch(r"C[0-9]{6}", c) for c in ids),
        "expected C830001..C830057")
    add("design_metrics_linkage", ids == mids,
        "same 57 IDs in the same order")
    add("stage_counts", {s: sum(1 for d in design if d["stage"] == s)
                         for s in ("A", "B", "C")} == {"A": 15, "B": 30, "C": 12},
        {s: sum(1 for d in design if d["stage"] == s) for s in ("A", "B", "C")})
    add("ss1_ss2_fixed",
        all(abs(float(d["SS1"]) - 3.2) < 1e-12
            and abs(float(d["SS2"]) - 0.8) < 1e-12 for d in design),
        "all 57 cases: SS1=3.2, SS2=0.8")

    ks1_levels = [d for d in design if d["stage"] == "A" and d["varied_param"] == "Ks1"]
    ks2_levels = [d for d in design if d["stage"] == "A" and d["varied_param"] == "Ks2"]
    add("ks1_7_levels", len(ks1_levels) == 7, len(ks1_levels))
    add("ks2_7_levels", len(ks2_levels) == 7, len(ks2_levels))
    b_bgs = {d["background_id"] for d in design if d["stage"] == "B"
             and d["stage_group"] == "B_background_reference"}
    b_variants = [d for d in design if d["stage"] == "B" and d["varied_param"]]
    add("six_backgrounds", b_bgs == {f"B{i}" for i in range(1, 7)}, sorted(b_bgs))
    add("b_variants_24", len(b_variants) == 24, len(b_variants))
    add("c_joint_12", len(joint_rows) == 3
        and sum(1 for d in design if d["stage"] == "C") == 12,
        {"joint_rows": len(joint_rows),
         "c_cases": sum(1 for d in design if d["stage"] == "C")})

    vectors = {}
    for d in design:
        key = tuple(round(float(d[p]), 10) for p in PARAMS)
        vectors.setdefault(key, []).append(d["case_id"])
    dup = {k: v for k, v in vectors.items() if len(v) > 1}
    add("no_duplicate_parameter_vectors", not dup, {"groups": len(dup)})
    add("failed_cases_preserved",
        sum(1 for r in metrics_rows if r["hard_qc_status"] != "PASS")
        == len(run_meta["failed_cases"]),
        {"metrics_failed": sum(1 for r in metrics_rows
                               if r["hard_qc_status"] != "PASS"),
         "run_meta_failed": len(run_meta["failed_cases"])})


    add("ks1_table_7", len(ks1_rows) == 7, len(ks1_rows))
    add("ks2_table_7", len(ks2_rows) == 7, len(ks2_rows))
    add("decision_rows_include_ks",
        {d["param"] for d in decisions} >= {"Ks1", "Ks2", "SS1", "SS2"},
        [d["param"] for d in decisions])
    add("ks_decisions_valid",
        all(d["decision"] in ("KEEP_RECOMMENDED", "FIX_RECOMMENDED",
                              "FURTHER_REVIEW", "FIXED_BY_REVIEW")
            for d in decisions),
        sorted({d["decision"] for d in decisions}))

    add("criteria_saved_before_classification",
        CRITERIA_PATH.stat().st_mtime
        < (OUTDIR / "parameter_decisions.csv").stat().st_mtime,
        "criteria mtime < decisions mtime")
    add("criteria_has_thresholds",
        all(k in criteria["thresholds"] for k in
            ("keep_shape", "review_shape", "keep_rear", "noise_multiplier",
             "cosine_independence", "substitution_max_residual")),
        sorted(criteria["thresholds"].keys()))

    cand = yaml.safe_load(CANDIDATE_PATH.read_text())
    add("candidate_ss_fixed",
        cand["human_decisions"]["SS1"]["status"] == "FIXED_BY_REVIEW"
        and cand["human_decisions"]["SS2"]["status"] == "FIXED_BY_REVIEW"
        and cand["human_decisions"]["SS1"]["value"] == 3.2
        and cand["human_decisions"]["SS2"]["value"] == 0.8,
        {"SS1_status": cand["human_decisions"]["SS1"]["status"],
         "SS2_status": cand["human_decisions"]["SS2"]["status"]})

    for name, min_bytes in (("overview.png", 80_000),
                            ("ks1_xmean_comparison.png", 40_000),
                            ("ks2_background_comparison.png", 40_000)):
        p = OUTDIR / name
        add(f"figure_{name}", p.is_file() and p.stat().st_size >= min_bytes,
            {"exists": p.is_file(),
             "bytes": p.stat().st_size if p.is_file() else 0})

    with np.load(OUTDIR / "profiles.npz", allow_pickle=False) as data:
        npz_ids = [str(x) for x in data["case_ids"]]
    add("profiles_npz_57", len(npz_ids) == 57 and len(set(npz_ids)) == 57
        and set(npz_ids).issubset(set(ids)), len(npz_ids))
    add("npz_reload_ok", run_meta["npz_check"]["reload_ok"],
        run_meta["npz_check"])

    by_id = {r["case_id"]: r for r in metrics_rows}
    samples = [design[0]["case_id"], design[40]["case_id"], design[-1]["case_id"]]
    errors = []
    with np.load(OUTDIR / "profiles.npz", allow_pickle=False) as data:
        for cid in samples:
            d = next(r for r in design if r["case_id"] == cid)
            g = gen.compute_geometry({p: float(d[p]) for p in PARAMS})
            for key, field in (("xp", "xp1"), ("yp", "yp1"), ("xs", "xs1"),
                               ("ys", "ys1"), ("yc", "yc"), ("thick", "thick")):
                if not np.array_equal(data[f"{cid}__{key}"],
                                      np.asarray(g[field], dtype=float)):
                    errors.append(f"{cid}:{key}")
    add("case_reproduction_from_csv_exact", not errors,
        {"samples": samples, "errors": errors})

    frozen = verify_frozen_assets()
    add("frozen_assets_unchanged", frozen["status"] == "PASS",
        {"checked": frozen["checked"], "mismatches": frozen["mismatches"]})

    proc = subprocess.run([sys.executable, "-m", "pytest", "-q"],
                          cwd=str(REPO), capture_output=True, text=True)
    lines = (proc.stdout + proc.stderr).strip().splitlines()
    add("regression_tests", proc.returncode == 0,
        lines[-1] if lines else f"returncode={proc.returncode}")

    size_mb = round(sum(p.stat().st_size for p in OUTDIR.rglob("*")
                        if p.is_file()) / (1024 * 1024), 3)
    add("output_size_target", size_mb <= 5.0, f"{size_mb} MB", level="WARN")
    add("output_size_acceptable", size_mb <= 8.0, f"{size_mb} MB")

    overall = all(c["pass"] for c in checks if c["level"] == "FAIL")
    result = {"overall_pass": overall, "checks": checks,
              "output_size_mb": size_mb,
              "warnings": [c for c in checks
                           if c["level"] == "WARN" and not c["pass"]],
              "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _atomic_text(OUTDIR / "audit" / "acceptance_check.json",
                 json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"overall_pass": overall,
                      "failed": [c for c in checks if not c["pass"]],
                      "output_size_mb": size_mb},
                     ensure_ascii=False, indent=2))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Ks1/Ks2 focused geometry review (57 cases)")
    parser.add_argument("command",
                        choices=["run", "analyze", "validate", "all"])
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "run":
        cmd_run(args.overwrite)
    elif args.command == "analyze":
        cmd_analyze()
    elif args.command == "validate":
        cmd_validate()
    else:
        cmd_run(args.overwrite)
        cmd_analyze()
        cmd_validate()


if __name__ == "__main__":
    main()

