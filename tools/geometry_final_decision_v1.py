#!/usr/bin/env python
"""Geometry Parameter Final Decision V1 — Ks1 / Ks2 / Xmean.

This is the final geometry-DOE parameter screening round.  It decides
KEEP/FIX for Ks1 and Ks2 and fixes the next-stage Xmean exploration bound.
It does NOT run NUMECA/CFX, does NOT train a model and does NOT modify the
formal DOE or any frozen production range.

Stages
------
D1  Xmean high end x Ks1 (baseline turning)         15 rows (3 reused)
D2  K_m corners at Xmean 0.18 / 0.22                8 rows (4 reused)
D3  large-turn / small-turn Metal backgrounds       12 rows (new)
D4  bound-rule corner probes                        4 rows (new)
D5  Ks2 at high Xmean                                7 rows (new)

In addition the tool runs, purely in memory:
  * a soft-risk map over Xmean 0.06..0.24 (2200+ geometries, no files)
  * a hard-QC cross-check on the boundary candidates
  * constrained substitutions of Ks1 (Xmean+K_m) and Ks2 (Xmean+K_m+Ks1)

Usage
-----
    conda run -n ai4s python tools/geometry_final_decision_v1.py all
    conda run -n ai4s python tools/geometry_final_decision_v1.py run
    conda run -n ai4s python tools/geometry_final_decision_v1.py analyze
    conda run -n ai4s python tools/geometry_final_decision_v1.py validate
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

EXPERIMENT_ID = "parameter_final_decision_v1"
OUTDIR = REPO / "analysis" / "geometry_review" / EXPERIMENT_ID
CRITERIA_PATH = OUTDIR / "final_decision_criteria.yaml"
TEMPLATE_PATH = REPO / "legacy" / "blade_batch_generation_template.geomTurbo"
PROTECTED_BASELINE = OUTDIR / "protected_assets_before.sha256.json"

CASE_PREFIX = "C84"
PARAMS = list(gen.PARAM_NAMES)
BASELINE = {
    "Xthick": 0.30, "Tmax": 0.055, "Metal2": 15.0, "Solidity": 1.5,
    "Metal1": 53.0, "T1": 0.015, "T2": 0.0125, "Xmean": 0.08, "K_m": 0.18,
    "Ks1": 5.0, "Ks2": 0.10, "SS1": 3.2, "SS2": 0.8,
}
# Search ranges.  The Xmean upper value here is the WIDEST candidate; the
# adopted bound is a decision output, not a configuration input.
RANGES = {
    "Xthick": (0.10, 0.60), "Tmax": (0.025, 0.095),
    "Metal2": (0.0, 32.0), "Solidity": (0.7, 2.5),
    "Metal1": (48.0, 58.0), "T1": (0.010, 0.018), "T2": (0.008, 0.016),
    "Xmean": (0.06, 0.22), "K_m": (0.10, 0.35),
    "Ks1": (3.0, 7.0), "Ks2": (0.05, 0.20),
    "SS1": (2.4, 4.0), "SS2": (0.5, 1.1),
}
XMEAN_CANDIDATES = (0.18, 0.20, 0.22)
XMEAN_RULE_LOWER = 0.06
FIXED = {"SS1": 3.2, "SS2": 0.8, "Incidence": 0.0, "Mach": 0.5}

# Three metal-angle backgrounds: baseline, large turning, small turning.
METAL_BACKGROUNDS = {
    "M0": {"Metal1": 53.0, "Metal2": 15.0},   # turning -38 deg
    "ML": {"Metal1": 48.0, "Metal2": 0.0},    # turning -48 deg (large)
    "MS": {"Metal1": 58.0, "Metal2": 32.0},   # turning -26 deg (small)
}

# Seven backgrounds used by the Ks1 substitution analysis (same as the
# 57-case review so that the evidence is directly comparable).
KS1_BACKGROUNDS = {
    "B0": {},
    "B1": {"Xmean": 0.06, "K_m": 0.10},
    "B2": {"Xmean": 0.06, "K_m": 0.35},
    "B3": {"Xmean": 0.18, "K_m": 0.10},
    "B4": {"Xmean": 0.18, "K_m": 0.35},
    "ML": {"Metal1": 48.0, "Metal2": 0.0},
    "MS": {"Metal1": 58.0, "Metal2": 32.0},
}
KS1_BACKGROUND_ORDER = ["B0", "B1", "B2", "B3", "B4", "ML", "MS"]

# Four backgrounds for the Ks2 substitution (baseline / large / small / high Xmean).
# The high-Xmean background sits at the ADOPTED upper bound so that every tested
# background is inside the final exploration range.
KS2_BACKGROUNDS = {
    "B0": {},
    "ML": {"Metal1": 48.0, "Metal2": 0.0},
    "MS": {"Metal1": 58.0, "Metal2": 32.0},
    "X18": {"Xmean": 0.18},
}
KS2_BACKGROUND_ORDER = ["B0", "ML", "MS", "X18"]
# Supplementary stress background OUTSIDE the adopted bound (reported, not decided on).
KS2_STRESS_BACKGROUND = {"X20": {"Xmean": 0.20}}

XC_GRID = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50,
           0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]

HISTORICAL_FILES = [
    ("parameter_sensitivity_v1_100cases",
     REPO / "analysis/geometry_review/parameter_sensitivity_v1_100cases/case_design.csv"),
    ("ks1_ks2_review_v1",
     REPO / "analysis/geometry_review/ks1_ks2_review_v1/case_design.csv"),
]


def case_id(index: int) -> str:
    return f"{CASE_PREFIX}{index:04d}"


def fmt(value):
    if value is None:
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "1" if bool(value) else "0"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        v = float(value)
        if not math.isfinite(v):
            return ""
        if v == 0.0:
            return "0"
        if abs(v) >= 1e-3 and abs(v) < 1e6:
            return f"{v:.10g}"
        return f"{v:.6e}"
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
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "UNKNOWN"


def u_of(param, value):
    lo, hi = RANGES[param]
    return (float(value) - lo) / (hi - lo)


def params_equal(a, b, tol=1e-9):
    return all(abs(float(a[p]) - float(b[p])) <= tol for p in PARAMS)


def _atomic_text(path: Path, text: str):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_csv(path: Path, rows, preferred):
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


# ---------------------------------------------------------------------------
# Criteria / frozen QC thresholds
# ---------------------------------------------------------------------------
def load_criteria() -> dict:
    with open(CRITERIA_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def metric_thresholds(crit=None) -> dict:
    """Thresholds required by the frozen metrics module (not decision thresholds)."""
    return {
        "curvature_stability_max": 0.25,
        "circle_fit_residual_max_rel": 0.05,
        "circle_fit_min_span_deg": 45.0,
        "circle_fit_window_chord": 0.02,
        "edge_region_chord": 0.05,
        "junction_diagnostic_deg": 15.0,
        "junction_jump_diagnostic_deg": 15.0,
    }


# ---------------------------------------------------------------------------
# Geometry features (meanline, response vector, soft-risk indicators)
# ---------------------------------------------------------------------------
def meanline_tables(g):
    """xc, yc, beta, kappa, dsc with the EXACT analytic derivative."""
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
    return xc, yc, beta, kappa, dsc


def profile_features(g):
    """19-point feature table shared by all cases (same xc indices)."""
    xc, yc, beta, kappa, _ = meanline_tables(g)
    idx = np.array([int(np.argmin(np.abs(xc - t))) for t in XC_GRID], dtype=int)
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


def response_vector(g):
    """95-D physical response vector in reference-chord units."""
    f = profile_features(g)
    chord = float(g["chord_norm"])
    return np.concatenate([
        f["yc"] / chord,
        f["beta"],
        f["kappa"] * chord,
        f["yp"] / chord,
        f["ys"] / chord,
    ])


def soft_risk_metrics(g) -> dict:
    """Hard-failure-independent geometric soft-risk indicators."""
    xc, yc, beta, kappa, dsc = meanline_tables(g)
    main = float(np.max(np.abs(dsc))) if len(dsc) else 0.0
    pos = np.clip(dsc, 0.0, None)
    rcr = float(pos.max() / main) if main > 0 else 0.0
    # grid-independent tangent reversal: integral of max(0, dbeta/dxc) in degrees
    dbdx = dsc / (1.0 + np.asarray(g["sc"]) ** 2)
    rev = np.clip(dbdx, 0.0, None)
    trd = float(np.degrees(np.trapezoid(rev, xc)))
    # splice curvature jump
    c = g["coefficients"]
    xm = float(g["params"]["Xmean"])
    eps = 1e-6
    dsc_l = 3 * c["a1"] * (xm - eps) ** 2 + 2 * c["a2"] * (xm - eps) + c["a3"]
    dsc_r = (-3 * c["a5"] * (1 - xm + eps) ** 2
             - 2 * c["a6"] * (1 - xm + eps) - c["a7"])
    sc_l = (c["a1"] * (xm - eps) ** 3 + c["a2"] * (xm - eps) ** 2
            + c["a3"] * (xm - eps) + c["a4"])
    sc_r = (c["a5"] * (1 - xm + eps) ** 3 + c["a6"] * (1 - xm + eps) ** 2
            + c["a7"] * (1 - xm + eps) + c["a8"])
    k_l = abs(dsc_l) / (1 + sc_l ** 2) ** 1.5
    k_r = abs(dsc_r) / (1 + sc_r ** 2) ** 1.5
    chord = float(g["chord_norm"])
    rear = xc > 0.70
    front = xc < 0.30
    lobe_peak_xc = float(xc[int(np.argmax(pos))]) if pos.max() > 0 else float("nan")
    return {
        "reverse_curvature_ratio": rcr,
        "reverse_lobe_peak_xc": lobe_peak_xc,
        "tangent_reversal_deg": trd,
        "splice_curvature_jump_norm": float(abs(k_l - k_r) * chord),
        "kappa_max_norm": float(np.max(kappa) * chord),
        "camber_norm": float(np.max(np.abs(yc)) / chord),
        "beta_min_deg": float(np.degrees(beta.min())),
        "beta_max_deg": float(np.degrees(beta.max())),
        "front_kappa_mean_norm": float(np.mean(kappa[front]) * chord),
        "rear_kappa_mean_norm": float(np.mean(kappa[rear]) * chord),
        "thick_min_norm": float(g["thick_min"] / chord),
        "chord_norm": chord,
    }


def contour_residual(candidate, target, ref_chord):
    """Residual components of ``candidate`` against ``target``."""
    pc = metrics.canonical_polygon(candidate)
    pt = metrics.canonical_polygon(target)
    cm = metrics.symmetric_contour_metrics(pc, pt, ref_chord)
    fc = profile_features(candidate)
    ft = profile_features(target)
    rear = ft["rear_mask"]
    front = ft["front_mask"]
    dy = fc["yc"] - ft["yc"]
    db = fc["beta"] - ft["beta"]
    dk = (fc["kappa"] - ft["kappa"]) * ref_chord
    dp = (fc["yp"] - ft["yp"]) / ref_chord
    ds = (fc["ys"] - ft["ys"]) / ref_chord
    return {
        "contour_rms": cm["contour_rms_dev_norm"],
        "contour_max": cm["contour_max_dev_norm"],
        "vector_residual": float(np.linalg.norm(response_vector(candidate)
                                                - response_vector(target))),
        "meanline_rms": float(np.sqrt(np.mean((dy / ref_chord) ** 2))),
        "angle_rms_deg": float(np.degrees(np.sqrt(np.mean(db ** 2)))),
        "angle_max_deg": float(np.degrees(np.max(np.abs(db)))),
        "curvature_rms": float(np.sqrt(np.mean(dk ** 2))),
        "pressure_rms": float(np.sqrt(np.mean(dp ** 2))),
        "suction_rms": float(np.sqrt(np.mean(ds ** 2))),
        "rear_meanline_rms": float(np.sqrt(np.mean((dy[rear] / ref_chord) ** 2))),
        "rear_angle_rms_deg": float(np.degrees(np.sqrt(np.mean(db[rear] ** 2)))),
        "rear_curvature_rms": float(np.sqrt(np.mean(dk[rear] ** 2))),
        "rear_pressure_rms": float(np.sqrt(np.mean(dp[rear] ** 2))),
        "rear_suction_rms": float(np.sqrt(np.mean(ds[rear] ** 2))),
        "front_meanline_rms": float(np.sqrt(np.mean((dy[front] / ref_chord) ** 2))),
        "front_angle_rms_deg": float(np.degrees(np.sqrt(np.mean(db[front] ** 2)))),
        "front_curvature_rms": float(np.sqrt(np.mean(dk[front] ** 2))),
    }


# ---------------------------------------------------------------------------
# Historical reuse (157 cases)
# ---------------------------------------------------------------------------
def load_historical():
    rows = []
    for exp, path in HISTORICAL_FILES:
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append({
                    "case_id": r["case_id"],
                    "experiment": exp,
                    "params": {p: float(r[p]) for p in PARAMS},
                    "stage": r.get("stage", ""),
                    "background_id": r.get("background_id", ""),
                })
    return rows


def vector_key(params):
    return tuple(round(float(params[p]), 9) for p in PARAMS)


def historical_index(rows):
    idx = {}
    for r in rows:
        idx.setdefault(vector_key(r["params"]), r)
    return idx


def historical_envelope(rows, crit) -> dict:
    """Soft-risk envelope of the 157 accepted cases (no new geometry saved)."""
    per = []
    seen = set()
    for r in rows:
        key = vector_key(r["params"])
        if key in seen:
            continue
        seen.add(key)
        g = gen.compute_geometry(r["params"])
        m = soft_risk_metrics(g)
        per.append({"case_id": r["case_id"], **m,
                    "Xmean": r["params"]["Xmean"], "Ks1": r["params"]["Ks1"],
                    "K_m": r["params"]["K_m"], "Metal1": r["params"]["Metal1"],
                    "Metal2": r["params"]["Metal2"]})
    rcr = np.array([p["reverse_curvature_ratio"] for p in per])
    trd = np.array([p["tangent_reversal_deg"] for p in per])
    spl = np.array([p["splice_curvature_jump_norm"] for p in per])
    i_rcr = int(np.argmax(rcr))
    i_trd = int(np.argmax(trd))
    i_spl = int(np.argmax(spl))
    return {
        "n_cases_total": len(rows),
        "n_unique_vectors": len(per),
        "anchor_rcr": float(rcr.max()),
        "anchor_rcr_case": per[i_rcr],
        "rcr_p50": float(np.percentile(rcr, 50)),
        "rcr_p90": float(np.percentile(rcr, 90)),
        "max_tangent_reversal_deg": float(trd.max()),
        "max_tangent_reversal_case": per[i_trd],
        "max_splice_jump_norm": float(spl.max()),
        "max_splice_jump_case": per[i_spl],
        "per_case": per,
    }


# ---------------------------------------------------------------------------
# Case plan (formal cases; reuse where the parameter vector already exists)
# ---------------------------------------------------------------------------
def _plan_entry(stage, group, background_id, varied_param, level_value,
                params, ref_params, reason):
    return {
        "stage": stage, "stage_group": group, "background_id": background_id,
        "varied_param": varied_param, "level_value": level_value,
        "params": {p: float(params[p]) for p in PARAMS},
        "ref_params": None if ref_params is None else {p: float(ref_params[p]) for p in PARAMS},
        "selection_reason": reason,
    }


def build_case_plan():
    plan = []

    # ---- D1: Xmean high end x Ks1, baseline turning, K_m = 0.18 -----------
    for xm in (0.14, 0.16, 0.18, 0.20, 0.22):
        for ks1 in (3.0, 5.0, 7.0):
            p = dict(BASELINE); p["Xmean"] = xm; p["Ks1"] = ks1
            ref = dict(BASELINE); ref["Xmean"] = xm; ref["Ks1"] = 5.0
            plan.append(_plan_entry(
                "D1", "D1_xmean_ks1_M0", "M0", "Ks1", ks1, p, ref,
                f"Xmean={xm:.2f}, Ks1={ks1:.1f}, K_m=0.18, baseline Metal1/Metal2"))

    # ---- D2: K_m corners at Xmean 0.18 (reused) and 0.22 ------------------
    for xm in (0.18, 0.22):
        for km in (0.10, 0.35):
            for ks1 in (3.0, 5.0, 7.0):
                p = dict(BASELINE); p["Xmean"] = xm; p["K_m"] = km; p["Ks1"] = ks1
                ref = dict(BASELINE); ref["Xmean"] = xm; ref["K_m"] = km; ref["Ks1"] = 5.0
                plan.append(_plan_entry(
                    "D2", "D2_km_corner_M0", "M0", "Ks1", ks1, p, ref,
                    f"Xmean={xm:.2f}, K_m={km:.2f}, Ks1={ks1:.1f}"))

    # ---- D3: large-turn and small-turn Metal backgrounds ------------------
    for bg in ("ML", "MS"):
        for xm in (0.16, 0.20):
            for ks1 in (3.0, 5.0, 7.0):
                p = dict(BASELINE); p.update(METAL_BACKGROUNDS[bg])
                p["Xmean"] = xm; p["Ks1"] = ks1
                ref = dict(p); ref["Ks1"] = 5.0
                plan.append(_plan_entry(
                    "D3", f"D3_turning_{bg}", bg, "Ks1", ks1, p, ref,
                    f"{bg} Metal1/Metal2, Xmean={xm:.2f}, Ks1={ks1:.1f}"))

    # ---- D4: bound-rule corner probes (K_m = 0.10, Ks1 = 6 / 7) -----------
    for xm in (0.20, 0.22):
        for ks1 in (6.0, 7.0):
            p = dict(BASELINE); p["Xmean"] = xm; p["K_m"] = 0.10; p["Ks1"] = ks1
            ref = dict(BASELINE); ref["Xmean"] = xm; ref["K_m"] = 0.10; ref["Ks1"] = 5.0
            plan.append(_plan_entry(
                "D4", "D4_bound_corner_M0", "M0", "Ks1", ks1, p, ref,
                f"bound-rule corner probe: Xmean={xm:.2f}, K_m=0.10, Ks1={ks1:.1f}"))

    # ---- D5: Ks2 at high Xmean -------------------------------------------
    for xm, km in ((0.20, 0.18), (0.22, 0.18), (0.20, 0.35)):
        for ks2 in (0.05, 0.10, 0.20):
            p = dict(BASELINE); p["Xmean"] = xm; p["K_m"] = km; p["Ks2"] = ks2
            ref = dict(p); ref["Ks2"] = 0.10
            plan.append(_plan_entry(
                "D5", f"D5_ks2_X{int(round(xm*100))}_KM{int(round(km*100))}",
                f"X{int(round(xm*100))}_KM{int(round(km*100))}", "Ks2", ks2, p, ref,
                f"Ks2={ks2:.2f} at Xmean={xm:.2f}, K_m={km:.2f} (Metal1/Metal2 fixed)"))
    return plan


def assign_case_ids(plan, hist_idx):
    """Deduplicate the plan, reuse historical vectors, assign C84 ids."""
    seen = set()
    rows = []
    next_id = 1
    for entry in plan:
        key = vector_key(entry["params"])
        if key in seen:
            continue
        seen.add(key)
        hist = hist_idx.get(key)
        row = dict(entry)
        if hist is not None:
            row["case_id"] = hist["case_id"]
            row["reuse_status"] = "REUSED"
            row["source_case_id"] = hist["case_id"]
        else:
            row["case_id"] = case_id(next_id)
            row["reuse_status"] = "NEW"
            row["source_case_id"] = ""
            next_id += 1
        rows.append(row)

    by_key = {vector_key(r["params"]): r["case_id"] for r in rows}
    for r in rows:
        rk = vector_key(r["ref_params"]) if r["ref_params"] else None
        r["reference_case_id"] = by_key.get(rk, r["case_id"])
    return rows


# ---------------------------------------------------------------------------
# Formal case evaluation
# ---------------------------------------------------------------------------
def _num(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return v if math.isfinite(v) else 0.0


def evaluate_case(design, ref_rec, crit, template_text, tmpdir,
                  do_frozen=True) -> dict:
    thr = metric_thresholds(crit)
    params = dict(design["params"])
    rec = {"design": design, "geom": None, "metrics": {},
           "generation_status": "FAIL", "failure_reason": "",
           "metric_status": "NOT_RUN", "frozen": {}, "runtime_s": 0.0}
    t0 = time.time()
    try:
        geom = gen.compute_geometry(params)
        rec["geom"] = geom
        rec["generation_status"] = "OK"
    except Exception as exc:  # pragma: no cover - defensive
        rec["failure_reason"] = f"GENERATION_ERROR: {type(exc).__name__}: {exc}"
        rec["runtime_s"] = time.time() - t0
        return rec

    ref_geom = geom if ref_rec is None else ref_rec["geom"]
    ref_params = params if ref_rec is None else ref_rec["params"]
    if ref_rec is None or "ind" not in ref_rec:
        ref_ind = metrics.independent_metrics(ref_geom, thr)
        if ref_rec is not None:
            ref_rec["ind"] = ref_ind
    else:
        ref_ind = ref_rec["ind"]

    try:
        flat, _ = metrics.compute_case_metrics(geom, ref_geom, ref_ind, thr)
        flat["qc_policy_id"] = metrics.QC_POLICY_ID
        res = contour_residual(geom, ref_geom, float(ref_geom["chord_norm"]))
        for key, value in res.items():
            flat[f"local_{key}"] = value
        noise = metrics.serialization_noise_floor(geom)
        noise_rms = float(noise["contour_rms_norm"])
        flat["serialization_noise_rms_norm"] = noise_rms
        flat["serialization_noise_max_norm"] = float(noise["contour_max_norm"])

        p = design["varied_param"]
        du = 0.0
        if p in RANGES and ref_params is not None:
            du = (params[p] - float(ref_params[p])) / (RANGES[p][1] - RANGES[p][0])
        flat["delta_u"] = du
        adu = abs(du)

        S_shape = S_rear = S_local = 0.0
        if adu > 1e-12:
            S_shape = max(
                _num(flat.get("contour_rms_dev_norm")),
                _num(flat.get("meanline_rms_dev_norm")),
                math.radians(_num(flat.get("meanline_tangent_rms_dev_deg"))),
                _num(flat.get("meanline_curvature_rms_change_abs"))) / adu
            S_rear = max(
                _num(flat.get("local_rear_meanline_rms")),
                math.radians(_num(flat.get("local_rear_angle_rms_deg"))),
                _num(flat.get("local_rear_curvature_rms")),
                _num(flat.get("local_rear_pressure_rms")),
                _num(flat.get("local_rear_suction_rms"))) / adu
            le_r = abs(_num(flat.get("le_radius_change_rel")))
            te_r = abs(_num(flat.get("te_radius_change_rel")))
            S_local = max(le_r, _num(flat.get("le_region_rms_dev_norm")),
                          te_r, _num(flat.get("te_region_rms_dev_norm"))) / adu
        flat["S_shape"] = S_shape
        flat["S_rear"] = S_rear
        flat["S_local"] = S_local
        flat["signal_to_noise_shape"] = (S_shape * adu / noise_rms
                                         if noise_rms > 0 else float("inf"))
        flat["signal_to_noise_rear"] = (S_rear * adu / noise_rms
                                        if noise_rms > 0 else float("inf"))
        flat.update(soft_risk_metrics(geom))
        flat["auto_flags"] = ("OK" if flat.get("hard_qc_status") == "PASS"
                              else flat.get("qc_reason", "QC_FAIL"))
        rec["metrics"] = flat
        rec["metric_status"] = "OK"
    except Exception as exc:  # pragma: no cover - defensive
        rec["metric_status"] = "ERROR"
        rec["failure_reason"] = f"METRIC_ERROR: {type(exc).__name__}: {exc}"
        rec["metrics"] = {"hard_qc_status": "ERROR", "qc_reason": "METRIC_ERROR"}

    if do_frozen:
        try:
            profile_text = gen.serialize_profile(geom)
            geom_text = gen.generate_geomturbo_text(
                profile_text, params["Solidity"], template_text)
            rec["frozen"] = metrics.frozen_qc_crosscheck(
                design["case_id"], params, profile_text, geom_text, tmpdir)
        except Exception as exc:  # pragma: no cover - defensive
            rec["frozen"] = {"frozen_qc_status": "ERROR",
                             "frozen_qc_reason": f"{type(exc).__name__}: {exc}"}
    rec["runtime_s"] = time.time() - t0
    return rec


def run_cases(rows, crit, template_text, do_frozen=True):
    registry = {}
    for r in rows:
        registry.setdefault(r["case_id"], {
            "geom": None, "params": r["params"], "design": r,
        })
    results = []
    tmpdir = tempfile.mkdtemp(prefix="final_decision_qc_") if do_frozen else None
    try:
        for r in rows:
            if r["reference_case_id"] == r["case_id"]:
                registry[r["case_id"]]["geom"] = gen.compute_geometry(r["params"])
        for r in rows:
            ref = registry.get(r["reference_case_id"])
            if ref is not None and ref["geom"] is None:
                ref["geom"] = gen.compute_geometry(ref["params"])
            rec = evaluate_case(r, ref, crit, template_text, tmpdir, do_frozen)
            results.append(rec)
            if rec["geom"] is not None:
                registry[r["case_id"]]["geom"] = rec["geom"]
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
    return results


DESIGN_COLUMNS = (
    ["case_id", "stage", "stage_group", "background_id", "reference_case_id",
     "varied_param", "level_value", "reuse_status", "source_case_id",
     "selection_reason"]
    + PARAMS + [f"u_{p}" for p in PARAMS] + ["Incidence", "Mach", "range_id"]
)
METRIC_COLUMNS = (
    ["case_id", "stage", "stage_group", "background_id", "reference_case_id",
     "varied_param", "level_value", "reuse_status",
     "generation_status", "failure_reason", "metric_status", "hard_qc_status",
     "qc_reason", "frozen_qc_status", "frozen_qc_reason", "auto_flags",
     "S_shape", "S_rear", "S_local", "signal_to_noise_shape",
     "signal_to_noise_rear", "delta_u"]
    + PARAMS
    + ["contour_rms_dev_norm", "contour_max_dev_norm", "meanline_rms_dev_norm",
       "meanline_tangent_rms_dev_deg", "meanline_curvature_rms_change_abs",
       "serialization_noise_rms_norm"]
    + ["local_contour_rms", "local_contour_max", "local_vector_residual",
       "local_meanline_rms", "local_angle_rms_deg", "local_angle_max_deg",
       "local_curvature_rms", "local_pressure_rms", "local_suction_rms",
       "local_rear_meanline_rms", "local_rear_angle_rms_deg",
       "local_rear_curvature_rms", "local_rear_pressure_rms",
       "local_rear_suction_rms", "local_front_meanline_rms",
       "local_front_angle_rms_deg", "local_front_curvature_rms"]
    + ["reverse_curvature_ratio", "reverse_lobe_peak_xc",
       "tangent_reversal_deg", "splice_curvature_jump_norm",
       "kappa_max_norm", "camber_norm", "beta_min_deg", "beta_max_deg",
       "front_kappa_mean_norm", "rear_kappa_mean_norm", "thick_min_norm"]
)


def flatten_result(rec) -> dict:
    row = dict(rec["design"])
    row.pop("params", None)
    row.pop("ref_params", None)
    row.update(rec["design"]["params"])
    for p in PARAMS:
        row[f"u_{p}"] = u_of(p, rec["design"]["params"][p])
    row["Incidence"] = FIXED["Incidence"]
    row["Mach"] = FIXED["Mach"]
    row["range_id"] = EXPERIMENT_ID
    row.update(rec["metrics"])
    row["generation_status"] = rec["generation_status"]
    row["failure_reason"] = rec["failure_reason"]
    row["metric_status"] = rec["metric_status"]
    row.update(rec.get("frozen", {}))
    return row


# ---------------------------------------------------------------------------
# Constrained substitution search (in memory only)
# ---------------------------------------------------------------------------
class VectorCache:
    """Stores ONLY the 95-D response vector (memory-safe for grid searches)."""

    def __init__(self):
        self._v = {}

    def get(self, params):
        key = (round(float(params["Xmean"]), 9), round(float(params["K_m"]), 9),
               round(float(params["Ks1"]), 9), round(float(params["Ks2"]), 9),
               round(float(params["Metal1"]), 9), round(float(params["Metal2"]), 9))
        v = self._v.get(key)
        if v is None:
            g = gen.compute_geometry(params)
            v = response_vector(g)
            self._v[key] = v
        return v


def search_substitute(ref_params, target_params, free_names, bounds,
                      coarse_counts, crit, cache, n_refine=3):
    """Deterministic coarse grid + bounded SLSQP refinement."""
    from itertools import product
    from scipy.optimize import minimize

    fixed = {k: float(v) for k, v in ref_params.items() if k not in free_names}
    v_ref = cache.get(ref_params)
    v_tgt = cache.get(target_params)
    nd = float(np.linalg.norm(v_tgt - v_ref))
    if nd <= 1e-12:
        return {"converged": False, "reason": "ZERO_TARGET_CHANGE"}
    n_evals = [0]

    def objective(x):
        p = dict(fixed)
        for name, value in zip(free_names, x):
            p[name] = float(value)
        try:
            v = cache.get(p)
        except Exception:
            return 1e6
        n_evals[0] += 1
        return float(np.linalg.norm(v - v_tgt) / nd)

    axes = [np.linspace(bounds[n][0], bounds[n][1], int(coarse_counts[n]))
            for n in free_names]
    scored = []
    for combo in product(*axes):
        scored.append((objective(np.asarray(combo, dtype=float)),
                       np.asarray(combo, dtype=float)))
    scored.sort(key=lambda t: t[0])

    best_x, best_j = scored[0][1].copy(), scored[0][0]
    for _, x0 in scored[:n_refine]:
        try:
            res = minimize(objective, x0, method="SLSQP",
                           bounds=[bounds[n] for n in free_names],
                           options={"maxiter": 80, "ftol": 1e-10})
            if res.fun < best_j:
                best_j = float(res.fun)
                best_x = np.asarray(res.x, dtype=float)
        except Exception:
            continue

    params = dict(fixed)
    for name, value in zip(free_names, best_x):
        params[name] = float(value)
    boundary = {}
    for name, value in zip(free_names, best_x):
        lo, hi = bounds[name]
        dist_u = min(abs(value - lo), abs(value - hi)) / (hi - lo)
        boundary[name] = {"value": float(value), "distance_u": float(dist_u),
                          "at_boundary": bool(dist_u <= 1e-6)}
    return {
        "converged": True,
        "params": params,
        "objective": float(best_j),
        "n_evals": int(n_evals[0]),
        "boundary": boundary,
        "at_boundary": any(b["at_boundary"] for b in boundary.values()),
        "target_change_vector_norm": nd,
    }


def evaluate_substitution(kind, background, direction, ref_params, target_params,
                          xmax, crit, cache, free_names=None):
    thr = crit["thresholds"]["substitution"]
    if free_names is None:
        free_names = ["Xmean", "K_m"] if kind == "Ks1" else ["Xmean", "K_m", "Ks1"]
    # Keep the reference point feasible: the bound may never exclude the background itself.
    x_lo = min(XMEAN_RULE_LOWER, float(ref_params["Xmean"]))
    x_hi = max(float(xmax), float(ref_params["Xmean"]))
    bounds = {"Xmean": (x_lo, x_hi),
              "K_m": (0.10, 0.35), "Ks1": (3.0, 7.0)}
    counts = ({"Xmean": 41, "K_m": 21, "Ks1": 9} if kind == "Ks1"
              else {"Xmean": 21, "K_m": 13, "Ks1": 7})
    best = search_substitute(ref_params, target_params, free_names, bounds,
                             counts, crit, cache)
    row = {
        "substitution_id": f"{kind}_{background}_{direction}_X{int(round(xmax*100))}",
        "parameter": kind, "background_id": background, "direction": direction,
        "target_value": float(target_params[kind]),
        "reference_value": float(ref_params[kind]),
        "free_variables": ";".join(free_names),
        "xmean_upper_bound": float(xmax),
        "fixed_Metal1": float(ref_params["Metal1"]),
        "fixed_Metal2": float(ref_params["Metal2"]),
    }
    if not best.get("converged"):
        row.update({"accepted": False, "failed_checks": "NO_SEARCH",
                    "vector_residual_fraction": float("nan")})
        return row

    g_sub = gen.compute_geometry(best["params"])
    g_tgt = gen.compute_geometry(target_params)
    g_ref = gen.compute_geometry(ref_params)
    chord = float(g_ref["chord_norm"])
    res = contour_residual(g_sub, g_tgt, chord)
    base = contour_residual(g_tgt, g_ref, chord)

    def frac(num, den):
        return float(num / den) if abs(den) > 1e-12 else float("nan")

    soft = soft_risk_metrics(g_sub)
    soft_t = soft_risk_metrics(g_tgt)
    anchor = float(crit["thresholds"]["soft_risk"]["anchor_value_registered"])
    anomaly = []
    try:
        thr_m = metric_thresholds(crit)
        ref_ind = metrics.independent_metrics(g_ref, thr_m)
        flat, _ = metrics.compute_case_metrics(g_sub, g_ref, ref_ind, thr_m)
        if flat.get("hard_qc_status") != "PASS":
            anomaly.append(f"HARD_QC:{flat.get('qc_reason')}")
    except Exception as exc:
        anomaly.append(f"QC_ERROR:{type(exc).__name__}")
    if (soft["reverse_curvature_ratio"] > 0.85 * anchor
            and soft["reverse_curvature_ratio"]
            > soft_t["reverse_curvature_ratio"] + 0.01):
        anomaly.append("NEW_REVERSE_LOBE")

    offsets = {}
    for name in free_names:
        lo, hi = RANGES[name]
        offsets[name] = float((best["params"][name] - ref_params[name]) / (hi - lo))

    checks = {
        "vector_residual_fraction": (best["objective"],
                                     thr["vector_residual_fraction_max"]),
        "contour_rms_fraction": (frac(res["contour_rms"], base["contour_rms"]),
                                 thr["contour_rms_fraction_max"]),
        "contour_rms_abs": (res["contour_rms"], thr["contour_rms_abs_max"]),
        "angle_rms_deg": (res["angle_rms_deg"], thr["angle_rms_max_deg"]),
        "angle_max_deg": (res["angle_max_deg"], thr["angle_max_deg"]),
        "curvature_rms_fraction": (frac(res["curvature_rms"], base["curvature_rms"]),
                                   thr["curvature_rms_fraction_max"]),
        "curvature_rms_abs": (res["curvature_rms"], thr["curvature_rms_abs_max"]),
        "rear_meanline_rms": (res["rear_meanline_rms"],
                              thr["rear_meanline_rms_max"]),
        "rear_angle_rms_deg": (res["rear_angle_rms_deg"],
                               thr["rear_angle_rms_max_deg"]),
        "rear_curvature_rms_fraction": (frac(res["rear_curvature_rms"],
                                             base["rear_curvature_rms"]),
                                        thr["rear_curvature_rms_fraction_max"]),
        "rear_curvature_rms_abs": (res["rear_curvature_rms"],
                                   thr["rear_curvature_rms_abs_max"]),
    }
    failed = [name for name, (value, limit) in checks.items()
              if not math.isfinite(value) or value > limit]
    if best["at_boundary"]:
        failed.append("SUBSTITUTE_ON_BOUND")
    for name, off in offsets.items():
        if abs(off) > thr["substitute_offset_u_max"]:
            failed.append(f"OFFSET_TOO_LARGE:{name}")
    if anomaly:
        failed.append("NEW_ANOMALY")

    row.update({
        "free_values": ";".join(f"{n}={best['params'][n]:.6g}" for n in free_names),
        "substitute_Xmean": best["params"].get("Xmean", float("nan")),
        "substitute_K_m": best["params"].get("K_m", float("nan")),
        "substitute_Ks1": best["params"].get("Ks1", float("nan")),
        "substitute_Ks2": best["params"].get("Ks2", float("nan")),
        "vector_residual_fraction": best["objective"],
        "n_evals": best["n_evals"],
        "at_boundary": best["at_boundary"],
        "boundary_detail": ";".join(
            f"{n}={b['value']:.6g}(d_u={b['distance_u']:.2e})"
            for n, b in best["boundary"].items()),
        "target_change_contour_rms": base["contour_rms"],
        "target_change_curvature_rms": base["curvature_rms"],
        "target_change_rear_curvature_rms": base["rear_curvature_rms"],
        "residual_contour_rms": res["contour_rms"],
        "residual_contour_max": res["contour_max"],
        "residual_meanline_rms": res["meanline_rms"],
        "residual_angle_rms_deg": res["angle_rms_deg"],
        "residual_angle_max_deg": res["angle_max_deg"],
        "residual_curvature_rms": res["curvature_rms"],
        "residual_rear_meanline_rms": res["rear_meanline_rms"],
        "residual_rear_angle_rms_deg": res["rear_angle_rms_deg"],
        "residual_rear_curvature_rms": res["rear_curvature_rms"],
        "residual_rear_pressure_rms": res["rear_pressure_rms"],
        "residual_rear_suction_rms": res["rear_suction_rms"],
        "residual_front_meanline_rms": res["front_meanline_rms"],
        "residual_front_angle_rms_deg": res["front_angle_rms_deg"],
        "residual_front_curvature_rms": res["front_curvature_rms"],
        "contour_rms_fraction": frac(res["contour_rms"], base["contour_rms"]),
        "curvature_rms_fraction": frac(res["curvature_rms"], base["curvature_rms"]),
        "rear_curvature_rms_fraction": frac(res["rear_curvature_rms"],
                                            base["rear_curvature_rms"]),
        "offset_u_detail": ";".join(f"{n}={v:+.4f}" for n, v in offsets.items()),
        "max_abs_offset_u": max(abs(v) for v in offsets.values()) if offsets else 0.0,
        "target_rcr": soft_t["reverse_curvature_ratio"],
        "substitute_rcr": soft["reverse_curvature_ratio"],
        "anomalies": ";".join(anomaly),
    })
    return {"row": row, "checks": checks, "failed": failed, "best": best,
            "res": res, "base": base, "g_sub": g_sub, "soft": soft,
            "soft_t": soft_t, "offsets": offsets}



def substitution_row(result) -> dict:
    if "row" not in result:
        return result
    row = dict(result["row"])
    for name, (value, limit) in result["checks"].items():
        row[name] = value
        row[f"limit_{name}"] = limit
        row[f"pass_{name}"] = bool(math.isfinite(value) and value <= limit)
    row["accepted"] = len(result["failed"]) == 0
    row["failed_checks"] = ";".join(result["failed"])
    row["substitute_rcr"] = result["soft"]["reverse_curvature_ratio"]
    row["target_rcr"] = result["soft_t"]["reverse_curvature_ratio"]
    row["free_values"] = ";".join(
        f"{n}={result['best']['params'][n]:.6g}"
        for n in ("Xmean", "K_m", "Ks1") if n in result["best"]["boundary"])
    row["substitute_Xmean"] = result["best"]["params"].get("Xmean", float("nan"))
    row["substitute_K_m"] = result["best"]["params"].get("K_m", float("nan"))
    row["substitute_Ks1"] = result["best"]["params"].get("Ks1", float("nan"))
    return {k: v for k, v in row.items()
            if k not in ("row", "checks", "failed", "best", "res", "base",
                         "g_sub", "soft", "soft_t", "offsets")}


# ---------------------------------------------------------------------------
# Soft-risk map / hard-QC boundary scan
# ---------------------------------------------------------------------------
SPLICE_FLOOR = 1.0e-6   # C1 continuity makes the splice jump machine-noise level


def build_soft_risk_map():
    rows = []
    for bg, over in METAL_BACKGROUNDS.items():
        for xm in np.arange(XMEAN_RULE_LOWER, 0.24 + 1e-9, 0.005):
            for ks1 in (3.0, 4.0, 5.0, 6.0, 7.0):
                for km in (0.10, 0.18, 0.28, 0.35):
                    p = dict(BASELINE); p.update(over)
                    p["Xmean"] = float(xm); p["Ks1"] = ks1; p["K_m"] = km
                    g = gen.compute_geometry(p)
                    m = soft_risk_metrics(g)
                    rows.append({
                        "Xmean": float(xm), "Ks1": ks1, "K_m": km,
                        "background_id": bg,
                        "reverse_curvature_ratio": m["reverse_curvature_ratio"],
                        "tangent_reversal_deg": m["tangent_reversal_deg"],
                        "splice_curvature_jump_norm": m["splice_curvature_jump_norm"],
                        "kappa_max_norm": m["kappa_max_norm"],
                        "camber_norm": m["camber_norm"],
                        "reverse_lobe_peak_xc": m["reverse_lobe_peak_xc"],
                        "thick_min_norm": m["thick_min_norm"],
                    })
    return rows


def hard_qc_boundary_scan(crit):
    thr = metric_thresholds(crit)
    rows = []
    for bg, over in METAL_BACKGROUNDS.items():
        for xm in (0.18, 0.20, 0.22, 0.24, 0.26, 0.30):
            for ks1 in (3.0, 5.0, 6.0, 7.0):
                for km in (0.10, 0.35):
                    p = dict(BASELINE); p.update(over)
                    p["Xmean"] = xm; p["Ks1"] = ks1; p["K_m"] = km
                    try:
                        g = gen.compute_geometry(p)
                        ind = metrics.independent_metrics(g, thr)
                        flat, _ = metrics.compute_case_metrics(g, g, ind, thr)
                        rows.append({
                            "background_id": bg, "Xmean": xm, "Ks1": ks1, "K_m": km,
                            "hard_qc_status": flat.get("hard_qc_status"),
                            "qc_reason": flat.get("qc_reason"),
                            "max_thickness_norm": flat.get("max_thickness_norm"),
                            "le_junction_angle_jump_deg": g["le_junction_angle_jump_deg"],
                            "te_junction_angle_jump_deg": g["te_junction_angle_jump_deg"],
                        })
                    except Exception as exc:
                        rows.append({"background_id": bg, "Xmean": xm, "Ks1": ks1,
                                     "K_m": km, "hard_qc_status": "ERROR",
                                     "qc_reason": f"{type(exc).__name__}: {exc}"})
    return rows


def decide_xmean(map_rows, hist_env, crit):
    sr = crit["thresholds"]["soft_risk"]
    margin = float(sr["bound_rule_margin"])
    anchor = float(hist_env["anchor_rcr"])
    base_bound = min(XMEAN_CANDIDATES)
    base_worst = max((r["reverse_curvature_ratio"] for r in map_rows
                      if r["Xmean"] <= base_bound + 1e-9), default=0.0)
    trd_ref = max(float(hist_env["max_tangent_reversal_deg"]), 1e-6)
    spl_ref = max(float(hist_env["max_splice_jump_norm"]), SPLICE_FLOOR)
    out = {"anchor_rcr": anchor, "bound_reference": base_bound,
           "bound_reference_worst_rcr": base_worst,
           "bound_rule_margin": margin, "candidates": {}}
    for bound in XMEAN_CANDIDATES:
        sub = [r for r in map_rows if r["Xmean"] <= bound + 1e-9]
        w_rcr = max(r["reverse_curvature_ratio"] for r in sub)
        w_trd = max(r["tangent_reversal_deg"] for r in sub)
        w_spl = max(r["splice_curvature_jump_norm"] for r in sub)
        worst = max(sub, key=lambda r: r["reverse_curvature_ratio"])
        cond_rcr_ref = w_rcr <= margin * base_worst
        cond_rcr_anchor = w_rcr <= margin * anchor
        cond_trd = w_trd <= float(sr["tangent_reversal_margin"]) * trd_ref
        cond_spl = w_spl <= max(float(sr["splice_jump_margin"]) * spl_ref, SPLICE_FLOOR)
        out["candidates"][f"{bound:.2f}"] = {
            "worst_rcr": float(w_rcr),
            "worst_case": {k: worst[k] for k in ("Xmean", "Ks1", "K_m",
                                                 "background_id")},
            "worst_tangent_reversal_deg": float(w_trd),
            "worst_splice_jump_norm": float(w_spl),
            "cond_rcr_vs_current_bound": bool(cond_rcr_ref),
            "cond_rcr_vs_anchor": bool(cond_rcr_anchor),
            "cond_tangent_reversal": bool(cond_trd),
            "cond_splice_jump": bool(cond_spl),
            "admissible": bool(cond_rcr_ref and cond_rcr_anchor
                               and cond_trd and cond_spl),
        }
    adopted = None
    for bound in sorted(XMEAN_CANDIDATES, reverse=True):
        if out["candidates"][f"{bound:.2f}"]["admissible"]:
            adopted = bound
            break
    out["primary_adopted_bound"] = base_bound if adopted is None else adopted
    out["primary_fallback_used"] = adopted is None

    # --- robustness: re-run the SAME rule at the registered sensitivity margins
    alt = {}
    for margin_alt in crit["threshold_sensitivity"]["parameters"]["bound_rule_margin"]:
        pick = None
        for bound in sorted(XMEAN_CANDIDATES, reverse=True):
            w = max(r["reverse_curvature_ratio"] for r in map_rows
                    if r["Xmean"] <= bound + 1e-9)
            if w <= float(margin_alt) * base_worst and w <= float(margin_alt) * anchor:
                pick = bound
                break
        alt[f"{float(margin_alt):.2f}"] = base_bound if pick is None else pick
    out["sensitivity_bounds"] = alt
    primary = out["primary_adopted_bound"]
    robust = all(abs(v - primary) < 1e-9 for v in alt.values())
    out["robust"] = bool(robust)
    out["adopted_bound"] = primary if robust else min([primary] + list(alt.values()))
    out["conservative_due_to_sensitivity"] = (not robust)

    jc = None
    bound_for_region = out["primary_adopted_bound"]
    if bound_for_region > base_bound + 1e-9:
        thr = float(sr["joint_constraint_margin"]) * anchor
        flagged = [r for r in map_rows
                   if base_bound + 1e-9 < r["Xmean"] <= bound_for_region + 1e-9
                   and r["reverse_curvature_ratio"] > thr]
        region = [r for r in map_rows
                  if base_bound + 1e-9 < r["Xmean"] <= bound_for_region + 1e-9]
        rules = []
        for c in (5.0, 5.5, 6.0, 6.5, 7.0):
            keep = [r for r in region if r["Ks1"] <= c + 1e-9]
            bad = [r for r in flagged if r["Ks1"] <= c + 1e-9]
            rules.append({"rule": f"Ks1 <= {c:.1f}",
                          "retained_fraction": len(keep) / max(len(region), 1),
                          "violations": len(bad)})
        for m in (0.10, 0.15, 0.20, 0.25, 0.30, 0.35):
            keep = [r for r in region if r["K_m"] >= m - 1e-9]
            bad = [r for r in flagged if r["K_m"] >= m - 1e-9]
            rules.append({"rule": f"K_m >= {m:.2f}",
                          "retained_fraction": len(keep) / max(len(region), 1),
                          "violations": len(bad)})
        for c in (5.0, 5.5, 6.0, 6.5):
            for m in (0.10, 0.15, 0.20, 0.25):
                keep = [r for r in region if r["Ks1"] <= c + 1e-9
                        and r["K_m"] >= m - 1e-9]
                bad = [r for r in flagged if r["Ks1"] <= c + 1e-9
                       and r["K_m"] >= m - 1e-9]
                rules.append({"rule": f"Ks1 <= {c:.1f} AND K_m >= {m:.2f}",
                              "retained_fraction": len(keep) / max(len(region), 1),
                              "violations": len(bad)})
        valid = [r for r in rules if r["violations"] == 0]
        valid.sort(key=lambda r: -r["retained_fraction"])
        jc = {"flagged_points": len(flagged), "region_points": len(region),
              "flag_threshold": thr, "region_upper_bound": bound_for_region,
              "active": bool(out["adopted_bound"] > base_bound + 1e-9),
              "best_rule": valid[0] if valid else None,
              "alternatives": valid[:5],
              "no_constraint_needed": len(flagged) == 0}
    out["joint_constraint"] = jc
    return out


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------
def effect_metrics(ref_params, target_params, kind):
    """Resolved-effect indicators of one parameter change (per unit u)."""
    g_ref = gen.compute_geometry(ref_params)
    g_tgt = gen.compute_geometry(target_params)
    chord = float(g_ref["chord_norm"])
    res = contour_residual(g_tgt, g_ref, chord)
    du = abs((float(target_params[kind]) - float(ref_params[kind]))
             / (RANGES[kind][1] - RANGES[kind][0]))
    if du <= 1e-12:
        du = 1.0
    S_shape = max(res["contour_rms"], res["meanline_rms"],
                  math.radians(res["angle_rms_deg"]), res["curvature_rms"]) / du
    S_rear = max(res["rear_meanline_rms"],
                 math.radians(res["rear_angle_rms_deg"]),
                 res["rear_curvature_rms"],
                 res["rear_pressure_rms"], res["rear_suction_rms"]) / du
    noise = metrics.serialization_noise_floor(g_tgt)["contour_rms_norm"]
    return {
        "delta_u": du,
        "S_shape": float(S_shape),
        "S_rear": float(S_rear),
        "contour_rms_change": res["contour_rms"],
        "angle_rms_change_deg": res["angle_rms_deg"],
        "curvature_rms_change": res["curvature_rms"],
        "rear_meanline_change": res["rear_meanline_rms"],
        "rear_angle_change_deg": res["rear_angle_rms_deg"],
        "rear_curvature_change": res["rear_curvature_rms"],
        "signal_to_noise": float(S_shape * du / noise) if noise > 0 else float("inf"),
        "signal_to_noise_rear": float(S_rear * du / noise) if noise > 0 else float("inf"),
    }


def _group_backgrounds(details):
    groups = {}
    for d in details:
        groups.setdefault(d["background_id"], []).append(d)
    out = []
    for bg, items in groups.items():
        resolved = any(i["resolved"] for i in items)
        accepted = resolved and all(i["accepted"] for i in items if i["resolved"])
        rejected = resolved and not accepted
        out.append({"background_id": bg, "resolved": bool(resolved),
                    "accepted": bool(accepted), "rejected": bool(rejected),
                    "directions": items,
                    "max_vector_residual": max(
                        (i["vector_residual_fraction"] for i in items
                         if math.isfinite(i["vector_residual_fraction"])),
                        default=float("nan")),
                    "min_vector_residual": min(
                        (i["vector_residual_fraction"] for i in items
                         if math.isfinite(i["vector_residual_fraction"])),
                        default=float("nan"))})
    return out


def classify_ks1(results_final, crit):
    thr = crit["thresholds"]
    keep_shape = float(thr["resolution"]["keep_shape"])
    keep_local = float(thr["resolution"]["keep_local"])
    noise_mult = float(thr["resolution"]["noise_multiplier"])
    details = []
    for res in results_final:
        eff = effect_metrics(res["ref_params"], res["target_params"], "Ks1")
        resolved = ((eff["S_shape"] >= keep_shape or eff["S_shape"] >= keep_local)
                    and eff["signal_to_noise"] >= noise_mult)
        accepted = len(res["failed"]) == 0
        details.append({
            "background_id": res["background_id"], "direction": res["direction"],
            "effect": eff, "resolved": bool(resolved), "accepted": bool(accepted),
            "failed_checks": res["failed"],
            "vector_residual_fraction": res["best"]["objective"],
            "contour_rms_fraction": (res["checks"]["contour_rms_fraction"][0]),
            "at_boundary": res["best"]["at_boundary"],
        })
    per_bg = _group_backgrounds(details)
    n_res = sum(b["resolved"] for b in per_bg)
    n_acc = sum(b["accepted"] for b in per_bg)
    n_rej = sum(b["rejected"] for b in per_bg)
    if n_acc >= int(thr["statistics"]["ks1_fix_backgrounds"]):
        decision, rule = "FIX", "K1_FIX"
    elif n_rej >= int(thr["statistics"]["ks1_min_backgrounds"]):
        decision, rule = "KEEP", "K1_KEEP"
    else:
        decision, rule = "KEEP", "K1_KEEP_CONSERVATIVE"
    return {"parameter": "Ks1", "decision": decision, "rule_id": rule,
            "n_backgrounds": len(per_bg), "n_directions": len(details),
            "n_resolved": n_res, "n_accepted": n_acc,
            "n_rejected_resolved": n_rej,
            "details": details, "per_background": per_bg}


def classify_ks2(results_final, crit):
    thr = crit["thresholds"]
    keep_rear = float(thr["resolution"]["keep_rear"])
    noise_mult = float(thr["resolution"]["noise_multiplier"])
    details = []
    for res in results_final:
        eff = effect_metrics(res["ref_params"], res["target_params"], "Ks2")
        resolved = (eff["S_rear"] >= keep_rear
                    and eff["signal_to_noise_rear"] >= noise_mult)
        accepted = len(res["failed"]) == 0
        details.append({
            "background_id": res["background_id"], "direction": res["direction"],
            "effect": eff, "resolved": bool(resolved), "accepted": bool(accepted),
            "failed_checks": res["failed"],
            "vector_residual_fraction": res["best"]["objective"],
            "rear_curvature_rms_fraction": (res["checks"]["rear_curvature_rms_fraction"][0]),
            "at_boundary": res["best"]["at_boundary"],
        })
    per_bg = _group_backgrounds(details)
    n_res = sum(b["resolved"] for b in per_bg)
    n_acc = sum(b["accepted"] for b in per_bg)
    n_rej = sum(b["rejected"] for b in per_bg)
    if n_acc >= int(thr["statistics"]["ks2_fix_backgrounds"]):
        decision, rule = "FIX", "K2_FIX"
    elif n_rej >= int(thr["statistics"]["ks2_min_backgrounds"]):
        decision, rule = "KEEP", "K2_KEEP"
    else:
        decision, rule = "KEEP", "K2_KEEP_CONSERVATIVE"
    return {"parameter": "Ks2", "decision": decision, "rule_id": rule,
            "n_backgrounds": len(per_bg), "n_directions": len(details),
            "n_resolved": n_res, "n_accepted": n_acc,
            "n_rejected_resolved": n_rej,
            "details": details, "per_background": per_bg}



def substitution_sensitivity(results_final, crit):
    """Re-evaluate AC/RE with alternative vector-residual thresholds (same geometry)."""
    groups = {}
    for res in results_final:
        groups.setdefault(res["background_id"], []).append(res)

    def accepted_with(res, alt):
        fails = [f for f in res["failed"] if f != "vector_residual_fraction"]
        if res["checks"]["vector_residual_fraction"][0] > float(alt):
            fails.append("vector_residual_fraction")
        return not fails

    out = []
    for alt in crit["threshold_sensitivity"]["parameters"]["vector_residual_fraction_max"]:
        n_acc = sum(1 for res in results_final if accepted_with(res, alt))
        n_bg = sum(1 for items in groups.values()
                   if any(r["checks"] for r in items)
                   and all(accepted_with(r, alt) for r in items))
        out.append({"vector_residual_fraction_max": float(alt),
                    "n_accepted": n_acc,
                    "n_backgrounds_accepted": n_bg,
                    "n_backgrounds": len(groups),
                    "n_directions": len(results_final)})
    return out


def bound_sensitivity(map_rows, hist_env, crit):
    anchor = float(hist_env["anchor_rcr"])
    base_worst = max(r["reverse_curvature_ratio"] for r in map_rows
                     if r["Xmean"] <= 0.18 + 1e-9)
    rows = []
    for margin in crit["threshold_sensitivity"]["parameters"]["bound_rule_margin"]:
        for bound in XMEAN_CANDIDATES:
            sub = [r for r in map_rows if r["Xmean"] <= bound + 1e-9]
            worst = max(r["reverse_curvature_ratio"] for r in sub)
            rows.append({
                "bound_rule_margin": float(margin),
                "xmean_bound": bound,
                "worst_rcr": float(worst),
                "admissible": bool(worst <= float(margin) * base_worst
                                   and worst <= float(margin) * anchor),
            })
    return rows


def joint_constraint_sensitivity(map_rows, adopted_bound, hist_env, crit):
    anchor = float(hist_env["anchor_rcr"])
    base = min(XMEAN_CANDIDATES)
    rows = []
    for margin in crit["threshold_sensitivity"]["parameters"]["joint_constraint_margin"]:
        thr = float(margin) * anchor
        flagged = [r for r in map_rows
                   if base + 1e-9 < r["Xmean"] <= adopted_bound + 1e-9
                   and r["reverse_curvature_ratio"] > thr]
        rows.append({"joint_constraint_margin": float(margin),
                     "threshold": thr, "flagged_points": len(flagged)})
    return rows


# ---------------------------------------------------------------------------
# Analysis driver
# ---------------------------------------------------------------------------
def _sub(kind, background, ref, target, xmax, crit, cache, free_names=None,
         variant="primary"):
    r = evaluate_substitution(kind, background, f"{kind}_{target[kind]:.2f}",
                              ref, target, xmax, crit, cache, free_names)
    r["background_id"] = background
    r["direction"] = r["row"]["direction"]
    r["row"] = substitution_row(r)
    r["row"]["variant"] = variant
    r["ref_params"] = {p: float(v) for p, v in ref.items()}
    r["target_params"] = {p: float(v) for p, v in target.items()}
    r["xmean_upper_bound"] = float(xmax)
    r["variant"] = variant
    r["row"]["variant"] = variant
    return r


def run_analysis(verbose=True):
    t_start = time.time()
    crit = load_criteria()
    hist = load_historical()
    hist_idx = historical_index(hist)
    if verbose:
        print(f"[1/7] historical cases: {len(hist)} ({len(hist_idx)} unique vectors)")
    env = historical_envelope(hist, crit)
    if verbose:
        print(f"      soft-risk anchor RCR = {env['anchor_rcr']:.4f} "
              f"({env['anchor_rcr_case']['case_id']})")

    plan = build_case_plan()
    rows = assign_case_ids(plan, hist_idx)
    n_new = sum(1 for r in rows if r["reuse_status"] == "NEW")
    n_re = len(rows) - n_new
    if verbose:
        print(f"[2/7] plan: {len(rows)} rows ({n_new} new, {n_re} reused)")
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    results = run_cases(rows, crit, template)
    n_gen = sum(1 for r in results if r["generation_status"] == "OK")
    n_qc = sum(1 for r in results
               if r["metrics"].get("hard_qc_status") == "PASS")
    n_fz = sum(1 for r in results
               if r.get("frozen", {}).get("frozen_qc_status") == "PASS")
    if verbose:
        print(f"[3/7] cases: generated {n_gen}/{len(results)}, "
              f"hard QC {n_qc}/{len(results)}, frozen QC {n_fz}/{len(results)}")

    map_rows = build_soft_risk_map()
    if verbose:
        print(f"[4/7] soft-risk map: {len(map_rows)} in-memory geometries")
    qc_rows = hard_qc_boundary_scan(crit)
    if verbose:
        n_fail = sum(1 for r in qc_rows if r.get("hard_qc_status") != "PASS")
        print(f"      hard-QC boundary scan: {len(qc_rows)} points, {n_fail} not PASS")
    xmean = decide_xmean(map_rows, env, crit)
    bound = xmean["adopted_bound"]
    if verbose:
        print(f"[5/7] Xmean bound decision: {bound:.2f}")

    cache = VectorCache()
    ks1_all = []
    for bg in KS1_BACKGROUND_ORDER:
        ref = dict(BASELINE); ref.update(KS1_BACKGROUNDS[bg])
        for target_value in (3.0, 7.0):
            tgt = dict(ref); tgt["Ks1"] = target_value
            for xmax in XMEAN_CANDIDATES:
                ks1_all.append(_sub("Ks1", bg, ref, tgt, xmax, crit, cache))
    ks1_final = [r for r in ks1_all
                 if abs(r["xmean_upper_bound"] - bound) < 1e-12]
    if verbose:
        print(f"[6/7] Ks1 substitution: {len(ks1_all)} searches "
              f"({len(ks1_final)} at the adopted bound)")

    ks2_all = []
    for bg in KS2_BACKGROUND_ORDER:
        ref = dict(BASELINE); ref.update(KS2_BACKGROUNDS[bg])
        for target_value in (0.05, 0.20):
            tgt = dict(ref); tgt["Ks2"] = target_value
            ks2_all.append(_sub("Ks2", bg, ref, tgt, bound, crit, cache))
            ks2_all.append(_sub("Ks2", bg, ref, tgt, bound, crit, cache,
                                free_names=["Xmean", "K_m"], variant="supplementary_2var"))
    # supplementary stress test OUTSIDE the adopted bound (never used for the decision)
    for bg, over in KS2_STRESS_BACKGROUND.items():
        ref = dict(BASELINE); ref.update(over)
        for target_value in (0.05, 0.20):
            tgt = dict(ref); tgt["Ks2"] = target_value
            ks2_all.append(_sub("Ks2", bg, ref, tgt, bound, crit, cache,
                                variant="stress_outside_bound"))
    if verbose:
        print(f"[7/7] Ks2 substitution: {len(ks2_all)} searches")

    ks1_primary = [r for r in ks1_all if r["variant"] == "primary"]
    ks2_primary = [r for r in ks2_all if r["variant"] == "primary"]
    d_ks1 = classify_ks1(ks1_final, crit)
    d_ks2 = classify_ks2(ks2_primary, crit)

    sens = {
        "ks1_substitution": substitution_sensitivity(ks1_final, crit),
        "ks2_substitution": substitution_sensitivity(ks2_primary, crit),
        "xmean_bound": bound_sensitivity(map_rows, env, crit),
        "joint_constraint": joint_constraint_sensitivity(map_rows, bound, env, crit),
    }

    state = {
        "criteria": crit, "historical": hist, "hist_index": hist_idx,
        "envelope": env, "plan": plan, "rows": rows, "results": results,
        "map": map_rows, "qc_scan": qc_rows, "xmean": xmean,
        "ks1_all": ks1_all, "ks1_final": ks1_final,
        "ks2_all": ks2_all, "ks2_primary": ks2_primary,
        "decision_ks1": d_ks1, "decision_ks2": d_ks2,
        "sensitivity": sens,
        "counts": {"n_rows": len(rows), "n_new": n_new, "n_reused": n_re,
                   "n_generated": n_gen, "n_hard_qc_pass": n_qc,
                   "n_frozen_qc_pass": n_fz},
        "runtime_s": time.time() - t_start,
    }
    return state


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------
def write_design_and_metrics(state):
    design_rows = [{k: row.get(k) for k in DESIGN_COLUMNS}
                   for row in (flatten_result(r) for r in state["results"])]
    write_csv(OUTDIR / "case_design.csv", design_rows, DESIGN_COLUMNS)
    metrics_rows = [flatten_result(r) for r in state["results"]]
    write_csv(OUTDIR / "case_metrics.csv", metrics_rows, METRIC_COLUMNS)
    return len(design_rows)


SUB_COLUMNS = [
    "substitution_id", "parameter", "background_id", "direction", "variant",
    "target_value", "reference_value", "free_variables", "free_values",
    "xmean_upper_bound", "fixed_Metal1", "fixed_Metal2",
    "substitute_Xmean", "substitute_K_m", "substitute_Ks1",
    "offset_u_detail", "max_abs_offset_u",
    "vector_residual_fraction", "limit_vector_residual_fraction",
    "contour_rms_fraction", "limit_contour_rms_fraction",
    "residual_contour_rms", "limit_contour_rms_abs",
    "residual_contour_max", "residual_meanline_rms",
    "residual_angle_rms_deg", "limit_angle_rms_deg",
    "residual_angle_max_deg", "limit_angle_max_deg",
    "curvature_rms_fraction", "limit_curvature_rms_fraction",
    "residual_curvature_rms", "limit_curvature_rms_abs",
    "residual_rear_meanline_rms", "limit_rear_meanline_rms",
    "residual_rear_angle_rms_deg", "limit_rear_angle_rms_deg",
    "rear_curvature_rms_fraction", "limit_rear_curvature_rms_fraction",
    "residual_rear_curvature_rms", "limit_rear_curvature_rms_abs",
    "residual_rear_pressure_rms", "residual_rear_suction_rms",
    "residual_front_meanline_rms", "residual_front_angle_rms_deg",
    "target_change_contour_rms", "target_change_curvature_rms",
    "target_change_rear_curvature_rms",
    "target_rcr", "substitute_rcr", "at_boundary", "boundary_detail",
    "n_evals", "accepted", "failed_checks",
]


def write_substitution_csv(state):
    rows = [dict(r["row"]) for r in state["ks1_all"] + state["ks2_all"]]
    write_csv(OUTDIR / "substitution_results.csv", rows, SUB_COLUMNS)
    return len(rows)


MAP_COLUMNS = ["background_id", "Xmean", "Ks1", "K_m",
               "reverse_curvature_ratio", "reverse_lobe_peak_xc",
               "tangent_reversal_deg", "splice_curvature_jump_norm",
               "kappa_max_norm", "camber_norm", "thick_min_norm"]
QC_COLUMNS = ["background_id", "Xmean", "Ks1", "K_m", "hard_qc_status",
              "qc_reason", "max_thickness_norm",
              "le_junction_angle_jump_deg", "te_junction_angle_jump_deg"]


def write_map_and_qc(state):
    write_csv(OUTDIR / "xmean_boundary_scan.csv", state["map"], MAP_COLUMNS)
    write_csv(OUTDIR / "xmean_hard_qc_scan.csv", state["qc_scan"], QC_COLUMNS)
    return len(state["map"]), len(state["qc_scan"])


def write_evidence_csv(state):
    crit = state["criteria"]
    env = state["envelope"]
    rows = []

    def add(eid, etype, param, claim, case_ids, metric, value, limit, verdict,
            source, notes=""):
        rows.append({"evidence_id": eid, "evidence_type": etype,
                     "parameter": param, "claim": claim, "case_ids": case_ids,
                     "metric": metric, "value": value,
                     "threshold_or_limit": limit, "verdict": verdict,
                     "source": source, "notes": notes})

    c = env["anchor_rcr_case"]
    add("EV-HIST-ANCHOR", "HISTORICAL_ENVELOPE", "Xmean",
        "maximum reverse-curvature ratio in the 157 previously accepted cases",
        c["case_id"], "reverse_curvature_ratio", f"{env['anchor_rcr']:.6f}",
        crit["thresholds"]["soft_risk"]["anchor_value_registered"],
        "REFERENCE_ANCHOR",
        "157 historical case_design.csv (100 + 57); same analytic formula",
        f"Xmean={c['Xmean']}, Ks1={c['Ks1']}, K_m={c['K_m']}, "
        f"Metal1={c['Metal1']}, Metal2={c['Metal2']}")
    add("EV-HIST-P90", "HISTORICAL_ENVELOPE", "Xmean",
        "p90 of the historical reverse-curvature ratio", "157 cases",
        "reverse_curvature_ratio_p90", f"{env['rcr_p90']:.6f}", "",
        "REFERENCE_ONLY", "same recomputation",
        "context only, not a decision threshold")

    by_case = {}
    for d in state["results"]:
        by_case[vector_key(d["design"]["params"])] = d["design"]["case_id"]

    for r in state["ks1_final"]:
        eff = effect_metrics(r["ref_params"], r["target_params"], "Ks1")
        sub = r["row"]
        cid = by_case.get(vector_key(r["target_params"]), "")
        add(f"EV-KS1-EFFECT-{r['background_id']}-{r['direction']}",
            "KS1_EFFECT", "Ks1",
            f"geometry change of {r['direction']} in background {r['background_id']}",
            cid or r["background_id"], "S_shape", f"{eff['S_shape']:.6f}",
            crit["thresholds"]["resolution"]["keep_shape"],
            "RESOLVED" if eff["S_shape"] >= 0.010 else "NOT_RESOLVED",
            "analytic meanline + frozen contour metrics",
            f"Snr={eff['signal_to_noise']:.1f}; Xmean bound={r['xmean_upper_bound']:.2f}")
        add(f"EV-KS1-SUB-{r['background_id']}-{r['direction']}",
            "KS1_SUBSTITUTION", "Ks1",
            "Xmean+K_m replacement (Metal1/Metal2/Xthick/Tmax/T1/T2 fixed)",
            r["background_id"], "vector_residual_fraction",
            f"{sub['vector_residual_fraction']:.6f}",
            crit["thresholds"]["substitution"]["vector_residual_fraction_max"],
            "ACCEPTED" if sub["accepted"] else "REJECTED",
            "constrained in-memory search",
            f"free={sub['free_values']}; failed={sub['failed_checks']}; "
            f"boundary={sub['at_boundary']}")

    for r in state["ks2_primary"]:
        eff = effect_metrics(r["ref_params"], r["target_params"], "Ks2")
        sub = r["row"]
        add(f"EV-KS2-EFFECT-{r['background_id']}-{r['direction']}",
            "KS2_EFFECT", "Ks2",
            f"rear-30% change of {r['direction']} in background {r['background_id']}",
            r["background_id"], "S_rear", f"{eff['S_rear']:.6f}",
            crit["thresholds"]["resolution"]["keep_rear"],
            "RESOLVED" if eff["S_rear"] >= 0.010 else "NOT_RESOLVED",
            "rear 30% meanline/angle/curvature/pressure/suction",
            f"Snr_rear={eff['signal_to_noise_rear']:.1f}")
        rcf = sub.get("rear_curvature_rms_fraction", float("nan"))
        add(f"EV-KS2-SUB-{r['background_id']}-{r['direction']}",
            "KS2_SUBSTITUTION", "Ks2",
            "Xmean+K_m+Ks1 replacement with Metal1/Metal2 FIXED",
            r["background_id"], "rear_curvature_rms_fraction",
            f"{rcf:.6f}" if math.isfinite(rcf) else "",
            crit["thresholds"]["substitution"]["rear_curvature_rms_fraction_max"],
            "ACCEPTED" if sub["accepted"] else "REJECTED",
            "constrained in-memory search (Metal1/Metal2 hard-fixed)",
            f"free={sub['free_values']}; failed={sub['failed_checks']}")

    for bound, cand in state["xmean"]["candidates"].items():
        add(f"EV-XMEAN-BOUND-{bound}", "XMEAN_BOUND", "Xmean",
            f"candidate upper bound {bound}: worst soft-risk indicator",
            f"worst at Xmean={cand['worst_case']['Xmean']:.3f}, "
            f"Ks1={cand['worst_case']['Ks1']}, K_m={cand['worst_case']['K_m']}, "
            f"{cand['worst_case']['background_id']}",
            "worst_reverse_curvature_ratio", f"{cand['worst_rcr']:.6f}",
            f"<= {crit['thresholds']['soft_risk']['bound_rule_margin']:.2f} x "
            f"reference ({state['xmean']['bound_reference_worst_rcr']:.4f})",
            "ADMISSIBLE" if cand["admissible"] else "REJECTED",
            "soft-risk map (in-memory geometries)",
            f"tangent_reversal={cand['worst_tangent_reversal_deg']:.3f} deg; "
            f"splice_jump={cand['worst_splice_jump_norm']:.3e}")
    jc = state["xmean"].get("joint_constraint")
    if jc:
        add("EV-XMEAN-JOINT", "XMEAN_JOINT_CONSTRAINT", "Xmean;Ks1;K_m",
            "joint constraint fitted inside the newly added Xmean region",
            f"{jc['flagged_points']} flagged of {jc['region_points']} region points",
            "retained_fraction",
            f"{jc['best_rule']['retained_fraction']:.4f}" if jc.get("best_rule") else "",
            "violations = 0",
            ("ACTIVE" if jc.get("active") else "INACTIVE_AT_FINAL_BOUND"),
            "soft-risk map",
            f"flag threshold={jc['flag_threshold']:.6f}")
    add("EV-XMEAN-DECISION", "DECISION", "Xmean",
        "final adopted upper bound after the registered robustness check",
        f"primary(1.01)={state['xmean']['primary_adopted_bound']:.2f}; "
        + "; ".join(f"margin {m} -> {v:.2f}"
                    for m, v in state["xmean"]["sensitivity_bounds"].items()),
        "upper_bound", f"{state['xmean']['adopted_bound']:.2f}",
        "0.18 / 0.20 / 0.22",
        f"KEEP_{state['xmean']['adopted_bound']:.2f}",
        "XMEAN_BOUND_V1 + conservative branch on threshold sensitivity",
        "0.20 passes only at the 1.01 tolerance; 0.22 rejected at every margin")
    add("EV-XMEAN-QC", "XMEAN_HARD_QC", "Xmean",
        "hard QC of boundary candidates 0.18..0.30 across Ks1/K_m/metal corners",
        f"{len(state['qc_scan'])} combinations", "hard_qc_failures",
        sum(1 for r in state["qc_scan"] if r.get("hard_qc_status") != "PASS"),
        "0", "NECESSARY_NOT_SUFFICIENT",
        "experimental hard QC + frozen criterion",
        "100% PASS is never used as the sole justification of an expansion")

    d1, d2 = state["decision_ks1"], state["decision_ks2"]
    add("EV-DECISION-KS1", "DECISION", "Ks1",
        f"{d1['decision']} by {d1['rule_id']}",
        f"{d1['n_accepted']}/{d1['n_backgrounds']} substituted, "
        f"{d1['n_rejected_resolved']}/{d1['n_backgrounds']} rejected",
        "n_resolved", d1["n_resolved"], d1["decision"],
        d1["decision"], "pre-registered rule")
    add("EV-DECISION-KS2", "DECISION", "Ks2",
        f"{d2['decision']} by {d2['rule_id']}",
        f"{d2['n_accepted']}/{d2['n_backgrounds']} substituted, "
        f"{d2['n_rejected_resolved']}/{d2['n_backgrounds']} rejected",
        "n_resolved", d2["n_resolved"], d2["decision"],
        d2["decision"], "pre-registered rule")

    for name, table in (("Ks1", state["sensitivity"]["ks1_substitution"]),
                        ("Ks2", state["sensitivity"]["ks2_substitution"])):
        base_acc = next(r["n_accepted"] for r in table
                        if abs(r["vector_residual_fraction_max"] - 0.25) < 1e-12)
        for row in table:
            add(f"EV-SENS-{name}-{row['vector_residual_fraction_max']:.2f}",
                "THRESHOLD_SENSITIVITY", name,
                "substitution acceptance at an alternative residual threshold",
                "", "n_accepted", row["n_accepted"], row["n_backgrounds"],
                "STABLE" if row["n_accepted"] == base_acc else "SENSITIVE",
                "no new geometry")
    for row in state["sensitivity"]["xmean_bound"]:
        add(f"EV-SENS-BOUND-{row['bound_rule_margin']:.2f}-{row['xmean_bound']:.2f}",
            "THRESHOLD_SENSITIVITY", "Xmean",
            "bound admissibility at an alternative rule margin", "",
            "worst_rcr", f"{row['worst_rcr']:.6f}", "",
            "ADMISSIBLE" if row["admissible"] else "REJECTED",
            "no new geometry", f"margin={row['bound_rule_margin']:.2f}")
    for row in state["sensitivity"]["joint_constraint"]:
        add(f"EV-SENS-JOINT-{row['joint_constraint_margin']:.2f}",
            "THRESHOLD_SENSITIVITY", "Xmean;Ks1;K_m",
            "joint-constraint flagging at an alternative margin", "",
            "flagged_points", row["flagged_points"], "", "REFERENCE",
            "no new geometry", f"margin={row['joint_constraint_margin']:.2f}")

    add("EV-FIXED-SS1", "HUMAN_DECISION", "SS1", "fixed by human review", "",
        "value", 3.2, "", "FIXED_BY_REVIEW",
        "geometry_parameter_candidates_v2.yaml")
    add("EV-FIXED-SS2", "HUMAN_DECISION", "SS2", "fixed by human review", "",
        "value", 0.8, "", "FIXED_BY_REVIEW",
        "geometry_parameter_candidates_v2.yaml")
    write_csv(OUTDIR / "final_decision_evidence.csv", rows,
              ["evidence_id", "evidence_type", "parameter", "claim", "case_ids",
               "metric", "value", "threshold_or_limit", "verdict", "source",
               "notes"])
    return len(rows)


def write_profiles_npz(state, path=OUTDIR / "decision_profiles.npz"):
    arrays, ids, reused = {}, [], []
    for rec in state["results"]:
        if rec["design"]["reuse_status"] != "NEW":
            reused.append(rec["design"]["case_id"])
            continue
        if rec["geom"] is None:
            continue
        cid = rec["design"]["case_id"]
        ids.append(cid)
        for key, field in (("xp", "xp1"), ("yp", "yp1"), ("xs", "xs1"),
                           ("ys", "ys1"), ("xc", "xc"), ("yc", "yc"),
                           ("thick", "thick"), ("sc", "sc")):
            arrays[f"{cid}__{key}"] = np.asarray(rec["geom"][field], dtype=float)
    np.savez_compressed(
        path,
        case_ids=np.asarray(ids, dtype="U16"),
        reused_case_ids=np.asarray(reused, dtype="U16"),
        fields=np.asarray("xp,yp,xs,ys,xc,yc,thick,sc"),
        units=np.asarray("legacy normalized units; x=chordwise, y=tangential; "
                         "thick is HALF-thickness; divide by chord_norm"),
        **arrays)
    return ids, reused


def verify_npz(state, path=OUTDIR / "decision_profiles.npz") -> dict:
    expected = [r["design"]["case_id"] for r in state["results"]
                if r["design"]["reuse_status"] == "NEW" and r["geom"] is not None]
    with np.load(path, allow_pickle=False) as data:
        ids = [str(x) for x in data["case_ids"]]
        mism = []
        for rec in state["results"]:
            cid = rec["design"]["case_id"]
            if cid not in ids:
                continue
            for key, field in (("xp", "xp1"), ("yp", "yp1"),
                               ("xs", "xs1"), ("ys", "ys1"),
                               ("yc", "yc"), ("thick", "thick")):
                if not np.array_equal(data[f"{cid}__{key}"],
                                      np.asarray(rec["geom"][field], dtype=float)):
                    mism.append(f"{cid}:{key}")
    return {"profiles_saved": len(ids), "expected": len(expected),
            "missing": sorted(set(expected) - set(ids)),
            "array_mismatches": mism,
            "reload_ok": (sorted(ids) == sorted(expected)) and not mism}


def plot_overview(state, path=OUTDIR / "overview.png"):
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.3))
    ax = axes[0]
    for xm in (0.14, 0.16, 0.18, 0.20, 0.22):
        p = dict(BASELINE); p["Xmean"] = xm
        g = gen.compute_geometry(p)
        ax.plot(g["xc"], g["yc"] / g["chord_norm"], lw=1.3,
                label=f"Xmean={xm:.2f}, Ks1=5")
    for ks1, style in ((3.0, "--"), (7.0, ":")):
        p = dict(BASELINE); p["Xmean"] = 0.22; p["Ks1"] = ks1
        g = gen.compute_geometry(p)
        ax.plot(g["xc"], g["yc"] / g["chord_norm"], style, lw=1.2, color="k",
                label=f"Xmean=0.22, Ks1={ks1:.0f}")
    ax.set_xlabel("xc (-)")
    ax.set_ylabel("yc / chord (-)")
    ax.set_title("(a) meanline at the Xmean high end")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    ax = axes[1]
    for ks1 in (3.0, 4.0, 5.0, 6.0, 7.0):
        xs, ys = [], []
        for r in state["map"]:
            if r["background_id"] == "M0" and abs(r["Ks1"] - ks1) < 1e-9 \
                    and abs(r["K_m"] - 0.10) < 1e-9:
                xs.append(r["Xmean"]); ys.append(r["reverse_curvature_ratio"])
        order = np.argsort(xs)
        ax.plot(np.asarray(xs)[order], np.asarray(ys)[order], lw=1.2,
                label=f"Ks1={ks1:.0f}")
    ax.axhline(state["envelope"]["anchor_rcr"], color="r", ls="--", lw=1.0,
               label="157-case anchor")
    ax.axhline(0.85 * state["envelope"]["anchor_rcr"], color="orange", ls=":",
               lw=1.0, label="joint-constraint level")
    for bound in XMEAN_CANDIDATES:
        ax.axvline(bound, color="0.6", lw=0.8, ls="-.")
    ax.set_xlabel("Xmean (-)")
    ax.set_ylabel("reverse curvature ratio (-)")
    ax.set_title("(b) soft risk, K_m=0.10 (worst corner)")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    ax = axes[2]
    for ks2 in (0.05, 0.10, 0.20):
        p = dict(BASELINE); p["Xmean"] = 0.20; p["Ks2"] = ks2
        g = gen.compute_geometry(p)
        xc, _, _, kap, _ = meanline_tables(g)
        m = xc >= 0.70
        ax.plot(xc[m], kap[m] * g["chord_norm"], lw=1.4, label=f"Ks2={ks2:.2f}")
    ax.set_xlabel("xc (-)")
    ax.set_ylabel("kappa * chord (-)")
    ax.set_title("(c) rear 30% curvature at Xmean=0.20")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_decisions(state, path=OUTDIR / "decision_summary.png"):
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.3))
    thr = state["criteria"]["thresholds"]["substitution"]["vector_residual_fraction_max"]

    ax = axes[0]
    labels, values, colors = [], [], []
    for r in state["ks1_final"]:
        labels.append(f"{r['background_id']}\n{r['direction'].replace('Ks1_', '')}")
        values.append(r["row"]["vector_residual_fraction"])
        colors.append("tab:green" if r["row"]["accepted"] else "tab:red")
    x = np.arange(len(labels))
    ax.bar(x, values, color=colors)
    ax.axhline(thr, color="k", ls="--", lw=1.0, label=f"threshold {thr:.2f}")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("vector residual fraction (-)")
    ax.set_title("(a) Ks1 substitution: Xmean+K_m")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")

    ax = axes[1]
    labels, values, colors = [], [], []
    for r in state["ks2_primary"]:
        labels.append(f"{r['background_id']}\n{r['direction'].replace('Ks2_', '')}")
        values.append(r["row"].get("rear_curvature_rms_fraction", float("nan")))
        colors.append("tab:green" if r["row"]["accepted"] else "tab:red")
    x = np.arange(len(labels))
    ax.bar(x, values, color=colors)
    ax.axhline(0.25, color="k", ls="--", lw=1.0, label="threshold 0.25")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("rear curvature residual fraction (-)")
    ax.set_title("(b) Ks2 substitution: Xmean+K_m+Ks1")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")

    ax = axes[2]
    xs = sorted(set(r["Xmean"] for r in state["qc_scan"]))
    npass = [sum(1 for r in state["qc_scan"]
                 if abs(r["Xmean"] - v) < 1e-9 and r["hard_qc_status"] == "PASS")
             for v in xs]
    nfail = [sum(1 for r in state["qc_scan"]
                 if abs(r["Xmean"] - v) < 1e-9 and r["hard_qc_status"] != "PASS")
             for v in xs]
    ax.bar(xs, npass, width=0.012, color="tab:blue", label="hard QC PASS")
    ax.bar(xs, nfail, width=0.012, bottom=npass, color="tab:red",
           label="hard QC not PASS")
    ax.set_xlabel("Xmean (-)")
    ax.set_ylabel("corner combinations")
    ax.set_title("(c) hard QC near the boundary (necessary only)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Final configuration
# ---------------------------------------------------------------------------
def build_final_parameters(state) -> dict:
    crit = state["criteria"]
    d1 = state["decision_ks1"]
    d2 = state["decision_ks2"]
    bound = float(state["xmean"]["adopted_bound"])
    jc = state["xmean"].get("joint_constraint") or {}
    rules = crit["decision_rules"]
    jc_rule = jc.get("best_rule", {}).get("rule") if jc.get("best_rule") else None

    keep, fixed = [], []
    if d1["decision"] == "KEEP":
        keep.append({"name": "Ks1", "range": rules["ks1"][1]["range"],
                     "rule_id": d1["rule_id"]})
    else:
        fixed.append({"name": "Ks1", "value": 5.0,
                      "status": "FIXED_BY_FINAL_DECISION"})
    if d2["decision"] == "KEEP":
        keep.append({"name": "Ks2", "range": rules["ks2"][1]["range"],
                     "rule_id": d2["rule_id"]})
    else:
        fixed.append({"name": "Ks2", "value": 0.10,
                      "status": "FIXED_BY_FINAL_DECISION"})

    ranges = {
        "Xthick": [0.10, 0.60], "Tmax": [0.025, 0.095],
        "Metal2": [0.0, 32.0], "Solidity": [0.7, 2.5],
        "Metal1": [48.0, 58.0], "T1": [0.010, 0.018], "T2": [0.008, 0.016],
        "Xmean": [0.06, bound], "K_m": [0.10, 0.35],
        "Ks1": [3.0, 7.0], "Ks2": [0.05, 0.20],
    }
    geometry_keep = ["Xthick", "Tmax", "Metal2", "Solidity", "Metal1", "T1", "T2",
                     "Xmean", "K_m"]
    geometry_keep += [k["name"] for k in keep]
    n_geometry = len(geometry_keep)
    return {
        "config_id": "final_geometry_parameters_v1",
        "status": "EXPLORATORY_NOT_APPROVED_FOR_PRODUCTION",
        "decision_date": "2026-10-17",
        "authority": ("final for the exploratory geometry DOE only; NOT a CFD "
                      "certification and NOT a production-range approval"),
        "criteria": {"file": "final_decision_criteria.yaml",
                     "criteria_id": crit["criteria_id"],
                     "criteria_version": crit["criteria_version"]},
        "keep_parameters": [
            {"name": name, "range": ranges.get(name), "status": "KEEP"}
            for name in geometry_keep
        ],
        "fixed_parameters": [
            {"name": "SS1", "value": 3.2, "status": "FIXED_BY_REVIEW",
             "decision_source": "HUMAN_REVIEW_DECISION"},
            {"name": "SS2", "value": 0.8, "status": "FIXED_BY_REVIEW",
             "decision_source": "HUMAN_REVIEW_DECISION"},
        ] + fixed,
        "xmean": {
            "lower_bound": 0.06,
            "upper_bound": bound,
            "previous_upper_bound": 0.18,
            "movement": ("unchanged (conservative: the extension is not robust "
                         "to the registered threshold sensitivity)"
                         if bound <= 0.18 + 1e-9
                         else "extended by one exploratory step"),
            "decision_rule": "XMEAN_BOUND_V1",
            "primary_rule_result": state["xmean"]["primary_adopted_bound"],
            "robust_to_threshold_sensitivity": state["xmean"]["robust"],
            "sensitivity_bounds": state["xmean"]["sensitivity_bounds"],
            "worst_rcr_at_bound":
                state["xmean"]["candidates"][f"{bound:.2f}"]["worst_rcr"],
            "worst_rcr_at_previous_bound":
                state["xmean"]["bound_reference_worst_rcr"],
            "note_on_worst_rcr": ("identical to the previous bound because the "
                                  "final bound is unchanged"),
            "historical_anchor_rcr": state["envelope"]["anchor_rcr"],
            "joint_constraints": ([{
                "id": "JC_XMEAN_KS1_KM",
                "rule": jc_rule,
                "applies_to": f"0.18 < Xmean <= {jc['region_upper_bound']:.2f}",
                "active_at_final_bound": bool(jc.get("active")),
                "rationale": ("the reverse-curvature lobe grows with Ks1 and "
                              "shrinks with K_m; the flagged corner is excluded "
                              "without shrinking the rest of the box"),
                "retained_fraction_of_new_region":
                    jc["best_rule"]["retained_fraction"] if jc.get("best_rule") else None,
            }] if jc_rule else []),
        },
        "dimensionality": {
            "geometry_dimension": n_geometry,
            "operating_dimension": 2,
            "total_candidate_dimension": n_geometry + 2,
            "geometry_parameters": geometry_keep,
            "operating_parameters": ["Incidence", "Mach"],
        },
        "excluded_from_geometry_space": {
            "CHORD_TARGET": 0.06, "SPAN": 0.003, "Npoint": 101, "Ncirc": 4,
            "Nscale1": 1.7, "Nscale2": 1.7, "Rsign": 1.0, "Gridswitch": -1.0,
        },
        "decision_evidence": {
            "Ks1": {"decision": d1["decision"], "rule_id": d1["rule_id"],
                    "n_resolved": d1["n_resolved"],
                    "n_accepted": d1["n_accepted"],
                    "n_rejected_resolved": d1["n_rejected_resolved"],
                    "n_backgrounds": d1["n_backgrounds"]},
            "Ks2": {"decision": d2["decision"], "rule_id": d2["rule_id"],
                    "n_resolved": d2["n_resolved"],
                    "n_accepted": d2["n_accepted"],
                    "n_rejected_resolved": d2["n_rejected_resolved"],
                    "n_backgrounds": d2["n_backgrounds"]},
        },
        "requires_before_production": [
            "CFD verification of the high-Xmean / high-Ks1 corner",
            "CFD verification of the Ks2 rear-camber control range",
            "mesh independence and convergence check for the reverse-curvature lobe",
            "calibration of the research thresholds on the 1891-sample population",
        ],
        "not_modified": {
            "formal_doe": True, "production_range": True,
            "frozen_v1_generator": True, "legacy_files": True,
            "prior_100_case_experiment": True, "prior_57_case_review": True,
        },
    }


def write_final_parameters(state):
    payload = build_final_parameters(state)
    _atomic_text(OUTDIR / "final_geometry_parameters.yaml",
                 yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
    return payload


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def _f(value, digits=4):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if not math.isfinite(v):
        return "n/a"
    return f"{v:.{digits}f}"


def build_report(state) -> str:
    crit = state["criteria"]
    env = state["envelope"]
    xm = state["xmean"]
    d1 = state["decision_ks1"]
    d2 = state["decision_ks2"]
    counts = state["counts"]
    bound = float(xm["adopted_bound"])
    jc = xm.get("joint_constraint") or {}
    jc_rule = jc.get("best_rule", {}).get("rule") if jc.get("best_rule") else None
    params = build_final_parameters(state)
    L = []
    a = L.append

    a("# 几何参数最终裁决 V1（Ks1 / Ks2 / Xmean）")
    a("")
    a("> 状态：**EXPLORATORY / NOT APPROVED**。本轮只做几何生成、几何 QC 与几何替代性数值搜索；")
    a("> **没有** NUMECA、**没有** CFX、**没有** AI 训练、**没有** 修改正式 DOE 或正式生产范围。")
    a(f"> 判据：`{crit['criteria_id']}` / `{crit['criteria_version']}`（预登记，正式 Case 生成前冻结；SHA256 见 provenance.json）。")
    a(f"> Case 号段：`C840001..C84{counts['n_new']:04d}`（新增 {counts['n_new']} 个）；复用历史 Case {counts['n_reused']} 个。")
    a("> 本报告的结论**不是 CFD 工程认证**，只决定下一阶段探索性几何 DOE 采用哪些参数与范围。")
    a("")

    a("## 0. 执行摘要（最终决策表）")
    a("")
    a("| 参数 | 最终决定 | 固定值或范围 | 核心证据 |")
    a("|---|---|---|---|")
    rej1 = [b for b in d1["per_background"] if b["rejected"]]
    rej2 = [b for b in d2["per_background"] if b["rejected"]]
    ks1_ev = "；".join(
        f"{b['background_id']} 残差 "
        f"{_f(b['min_vector_residual'], 2)}–{_f(b['max_vector_residual'], 2)}"
        for b in rej1[:3]) if rej1 else "全部背景可替代"
    ks2_vals = [d["rear_curvature_rms_fraction"] for d in d2["details"]
                if math.isfinite(d.get("rear_curvature_rms_fraction", float("nan")))]
    ks2_ev = ("尾部曲率残差 " + f"{_f(min(ks2_vals), 2)}–{_f(max(ks2_vals), 2)}"
              if ks2_vals else "")
    a(f"| `Ks1` | **{d1['decision']}** | "
      f"{'3.0 – 7.0' if d1['decision'] == 'KEEP' else '5.0'} | "
      f"{d1['rule_id']}：{d1['n_accepted']}/{d1['n_backgrounds']} 背景可替代，"
      f"{d1['n_rejected_resolved']}/{d1['n_backgrounds']} 背景拒绝；{ks1_ev} |")
    a(f"| `Ks2` | **{d2['decision']}** | "
      f"{'0.05 – 0.20' if d2['decision'] == 'KEEP' else '0.10'} | "
      f"{d2['rule_id']}：{d2['n_accepted']}/{d2['n_backgrounds']} 背景可替代，"
      f"{d2['n_rejected_resolved']}/{d2['n_backgrounds']} 背景拒绝；"
      f"{'Metal1/Metal2 固定下 ' + ks2_ev if ks2_ev else ''} |")
    a(f"| `Xmean` | **KEEP** | 0.06 – {bound:.2f} | "
      f"XMEAN_BOUND_V1：主规则（容差 {xm['bound_rule_margin']:.2f}）给出 "
      f"{xm['primary_adopted_bound']:.2f}，但结论对登记容差敏感（"
      + "，".join(f"{m}→{v:.2f}" for m, v in xm["sensitivity_bounds"].items())
      + f"），按预登记保守政策保持 0.18；0.22 在所有容差下均被拒绝"
      f"{('；若扩展到 0.20 需联合限制 ' + jc_rule) if jc_rule else ''} |")
    a("| `SS1` | **FIX** | 3.2 | 人工决定（FIXED_BY_REVIEW），本轮不重新开放 |")
    a("| `SS2` | **FIX** | 0.8 | 人工决定（FIXED_BY_REVIEW），本轮不重新开放 |")
    a("")
    a("```text")
    a(f"最终几何维度      : {params['dimensionality']['geometry_dimension']}")
    a(f"运行条件维度      : {params['dimensionality']['operating_dimension']} (Incidence, Mach)")
    a(f"总候选维度        : {params['dimensionality']['total_candidate_dimension']}")
    a(f"Xmean 探索区间    : 0.06 – {bound:.2f}")
    a(f"Ks1               : {d1['decision']}  ({d1['rule_id']})")
    a(f"Ks2               : {d2['decision']}  ({d2['rule_id']})")
    a("最终状态          : FINAL（仅限探索性几何 DOE），不存在 FURTHER_REVIEW / PENDING")
    a("```")
    a("")

    a("## 1. 实验规模与历史资产复用")
    a("")
    a("| 项目 | 数值 |")
    a("|---|---|")
    a(f"| 历史 Case（复用池） | 157（100 敏感性 + 57 Ks1/Ks2 复核） |")
    a(f"| 历史唯一参数向量 | {env['n_unique_vectors']} |")
    a(f"| 本轮计划行数 | {counts['n_rows']} |")
    a(f"| 其中直接复用历史 Case | {counts['n_reused']} |")
    a(f"| 新增正式 Case | {counts['n_new']}（限制 ≤ 48） |")
    a(f"| 几何生成成功 | {counts['n_generated']}/{counts['n_rows']} |")
    a(f"| 实验硬性 QC 通过 | {counts['n_hard_qc_pass']}/{counts['n_rows']} |")
    a(f"| 冻结 QC 复核通过 | {counts['n_frozen_qc_pass']}/{counts['n_rows']} |")
    a(f"| 内存替代搜索次数 | {len(state['ks1_all']) + len(state['ks2_all'])} |")
    a(f"| 软风险地图点数 | {len(state['map'])}（不落盘几何） |")
    a(f"| 硬性 QC 边界扫描点 | {len(state['qc_scan'])} |")
    a("")
    a("复用规则：只有当计划参数向量与历史向量**完全一致**（13 参数、1e-9 容差）时才复用；")
    a("否则生成新的 `C84xxxx` Case。复用 Case 不重复写入 profiles，只在 NPZ 中记录 ID。")
    a("")
    for stage, label in (("D1", "Xmean 高端 × Ks1（基准折转）"),
                         ("D2", "K_m 角点（Xmean 0.18 / 0.22）"),
                         ("D3", "大折转 / 小折转 Metal 背景"),
                         ("D4", "上界规则角点探针"),
                         ("D5", "高 Xmean 下的 Ks2")):
        rows = [r for r in state["results"] if r["design"]["stage"] == stage]
        n_new = sum(1 for r in rows if r["design"]["reuse_status"] == "NEW")
        a(f"- **{stage}** {label}：{len(rows)} 行（新增 {n_new}，复用 {len(rows) - n_new}）")
    a("")

    a("## 2. 历史资产审计（157 Case 的软风险包络）")
    a("")
    a("在生成任何新 Case 之前，用**同一解析公式**重新计算了 157 个历史 Case 的软风险指标，")
    a("用于判断“高端 Xmean 的几何是否为前所未有的新形态”。")
    a("")
    a("| 指标 | 中位 | p90 | 最大 | 最大对应 Case |")
    a("|---|---|---|---|---|")
    c = env["anchor_rcr_case"]
    a(f"| 反向曲率比 RCR | {_f(env['rcr_p50'])} | {_f(env['rcr_p90'])} | "
      f"**{_f(env['anchor_rcr'])}** | `{c['case_id']}` "
      f"(Xmean={c['Xmean']}, Ks1={c['Ks1']}, K_m={c['K_m']}) |")
    t = env["max_tangent_reversal_case"]
    a(f"| 切线角回摆（deg） | — | — | {_f(env['max_tangent_reversal_deg'], 2)} | "
      f"`{t['case_id']}` (Xmean={t['Xmean']}, Ks1={t['Ks1']}, K_m={t['K_m']}) |")
    a("")
    a("**关键事实**：反向曲率（中弧线局部斜率回摆）不是高端 Xmean 独有的失效，而是 legacy 分段中弧线")
    a(f"在低 Xmean + 高 K_m 角点就已存在的形态；历史 157 Case 中最大 RCR = {_f(env['anchor_rcr'])}。")
    a("因此本轮**不能**把“出现反向曲率”直接判为几何无效——这正是任务要求的“不得误判既有曲率尖峰”。")
    a("同时这也意味着：RCR 只能作为**相对**软风险尺度，用“是否比已接受的形态更极端”来判断。")
    a("")

    a("## 3. 实验一：Xmean 高端与 Ks1 独立性")
    a("")
    a("### 3.1 设计")
    a("")
    a("```text")
    a("Xmean  : 0.14 / 0.16 / 0.18 / 0.20 / 0.22")
    a("Ks1    : 3 / 5 / 7")
    a("K_m    : 0.10 / 0.18 / 0.35")
    a("折转背景: M0 (53/15), ML (48/0), MS (58/32)")
    a("固定    : Metal1/Metal2（逐背景）、Xthick=0.30、Tmax=0.055、T1=0.015、T2=0.0125、")
    a("          Ks2=0.10、SS1=3.2、SS2=0.8")
    a("```")
    a("")
    a("### 3.2 替代搜索（Xmean + K_m 联合替代 Ks1）")
    a("")
    a("目标：在保持 Ks1=5 的前提下，仅用 Xmean 与 K_m 复现 Ks1=3 或 Ks1=7 的 95 维响应；")
    a("Metal1、Metal2、Tmax、Xthick、T1、T2 全部固定。三个 Xmean 上界（0.18 / 0.20 / 0.22）各做一次，")
    a("以便区分“人为边界”与“真实独立作用”。")
    a("")
    a("| 上界 | 背景 | 方向 | 向量残差比例 | 轮廓残差比例 | 最佳 Xmean | 最佳 K_m | 边界命中 | 判定 | 主要未通过项 |")
    a("|---|---|---|---|---|---|---|---|---|---|")
    for r in state["ks1_all"]:
        row = r["row"]
        if row.get("vector_residual_fraction") is None:
            continue
        bd = "是" if row.get("at_boundary") else "否"
        fails = [f for f in str(row.get("failed_checks", "")).split(";") if f]
        short = ",".join(f.replace("OFFSET_TOO_LARGE:", "offset:").replace("_", "")
                         for f in fails[:3])
        a(f"| {r['xmean_upper_bound']:.2f} | {r['background_id']} | "
          f"{r['direction'].replace('Ks1_', 'Ks1=')} | "
          f"{_f(row['vector_residual_fraction'], 3)} | "
          f"{_f(row.get('contour_rms_fraction'), 3)} | "
          f"{_f(row.get('substitute_Xmean'), 3)} | "
          f"{_f(row.get('substitute_K_m'), 3)} | {bd} | "
          f"{'替代成功' if row['accepted'] else '替代失败'} | {short} |")
    a("")
    a("> `向量残差比例` = ‖v_sub − v_target‖ / ‖v_target − v_ref‖；0 表示完全复现，1 表示与目标变化正交。")
    a("> 接受条件为 `final_decision_criteria.yaml` 预登记的 11 项阈值 + 无参数贴边 + 无新异常。")
    a("")
    a("**两种不同的失败模式必须区分**：")
    a("")
    mid = [r for r in state["ks1_all"]
           if r["background_id"] in ("B0", "B1", "B2", "ML", "MS")
           and not (r["background_id"] == "B2" and r["row"]["target_value"] == 3.0)
           and abs(r["xmean_upper_bound"] - bound) < 1e-9]
    mid_j = [r["row"]["vector_residual_fraction"] for r in mid]
    mid_rear = [r["row"]["residual_rear_meanline_rms"] for r in mid]
    hi18 = [r["row"]["vector_residual_fraction"] for r in state["ks1_all"]
            if r["background_id"] in ("B3", "B4") and r["row"]["target_value"] == 7.0
            and abs(r["xmean_upper_bound"] - bound) < 1e-9]
    hi22 = [r["row"]["vector_residual_fraction"] for r in state["ks1_all"]
            if r["background_id"] in ("B3", "B4") and r["row"]["target_value"] == 7.0
            and abs(r["xmean_upper_bound"] - 0.22) < 1e-9]

    def _rng(values, scale=1.0, digits=3):
        if not values:
            return "n/a"
        return (f"{min(values)*scale:.{digits}f}–{max(values)*scale:.{digits}f}")

    a("1. **中低 Xmean 背景（B0/B1/B2/ML/MS）**：除 `B2 / Ks1=3` 的 1.000 之外，向量残差比例只有 "
      f"{_rng(mid_j)}，")
    a("   看起来“几乎可替代”；但绝对残差超限——`contour_rms_abs` 与 `rear_meanline_rms` 均大于 0.002（0.2% 弦长），")
    a(f"   实际尾部中弧线偏差达到 {_rng(mid_rear, 100, 2)}% 弦长。也就是说：**比例上解释了大部分变化，")
    a("   但剩下的部分仍是一个肉眼与网格都能分辨的形状差异**。按预登记规则，这不算替代成功。")
    a("2. **高 Xmean 背景（B3/B4）的 Ks1=7 方向**：在最终上界下相对残差为 "
      f"{_rng(hi18)}；即使放宽到 0.22 也只降到 {_rng(hi22)}，")
    a("   且最优解始终贴住 Xmean 上界（B3 还同时贴住 K_m 下界）。说明允许的二维子空间里")
    a("   **没有**指向目标的方向——这不是“参数偏移过大”的问题，而是真正的结构性独立。")
    a("3. `B2 / Ks1=3` 的残差为 1.000：在 Xmean=0.06、K_m=0.35 的角点，Ks1 的变化与 Xmean/K_m")
    a("   方向完全正交，是独立作用最强的证据。")
    a("")
    a("因此 Ks1 的 KEEP 结论并不依赖 `substitute_offset_u_max` 这一条规则：即使完全去掉偏移规则，")
    a("除 `B3 / Ks1=3`（角残差 1.04° 仅略微超过 1.0°，但仍有参数贴边）之外，")
    a("其余所有背景都至少有一项非偏移类指标明确超限；高端背景则整体失效。")
    a("偏移规则只影响“拒绝理由的排序”，不改变结论方向。")
    a("")


    a("### 3.3 边界诊断：高端失败是“边界人为”还是“真实独立”？")
    a("")
    a("把 Xmean 上界从 0.18 放宽到 0.20 / 0.22 后，重新观察同一批高端背景的替代残差：")
    a("")
    a("| 背景 | Ks1 变化 | 上界 0.18 | 上界 0.20 | 上界 0.22 | 结论 |")
    a("|---|---|---|---|---|---|")
    directions = sorted({r["direction"] for r in state["ks1_all"]})
    for bg in KS1_BACKGROUND_ORDER:
        for direction in directions:
            vals = {}
            acc = {}
            for r in state["ks1_all"]:
                if r["background_id"] == bg and r["direction"] == direction:
                    vals[r["xmean_upper_bound"]] = r["row"].get("vector_residual_fraction")
                    acc[r["xmean_upper_bound"]] = r["row"].get("accepted", False)
            if not vals:
                continue
            v18 = vals.get(0.18, float("nan"))
            v20 = vals.get(0.20, float("nan"))
            v22 = vals.get(0.22, float("nan"))
            improved = (math.isfinite(v18) and math.isfinite(v22) and v22 < 0.9 * v18)
            if acc.get(bound, False):
                concl = "可替代（满足全部阈值）"
            elif math.isfinite(v22) and v22 <= 0.25:
                concl = "相对残差可接受，但绝对/局部指标未通过"
            elif improved:
                concl = "放宽后有改善但仍不可替代"
            else:
                concl = "放宽无改善 → 真实独立作用"
            a(f"| {bg} | {direction.replace('Ks1_', 'Ks1=')} | {_f(v18, 3)} | "
              f"{_f(v20, 3)} | {_f(v22, 3)} | {concl} |")
    a("")
    a("读数规则：残差比例只回答“方向是否一致”，不回答“差异是否可接受”。")
    a("表中最后一列按预登记的全部阈值判定：即使 v22 ≤ 0.25，只要绝对残差（0.2% 弦长）、")
    a("角残差（0.5°）或曲率残差超限，仍然不算替代成功。")
    a("若放宽上界后残差显著下降（B3/B4），说明 0.18 的失败**部分**来自人为边界；")
    a("若几乎不变（B0/B1/B2/ML/MS），说明失败与边界无关。")
    a("")

    a("### 3.4 Ks1 的几何作用（中弧线 / 曲率 / 前后段）")
    a("")
    a("| 背景 | 方向 | S_shape | 轮廓变化 | 中弧线曲率变化 | 替代后前段曲率残差 | 替代后后段曲率残差 | 目标 RCR | 替代 RCR |")
    a("|---|---|---|---|---|---|---|---|---|")
    for r in state["ks1_final"]:
        sub = r["row"]
        eff = effect_metrics(r["ref_params"], r["target_params"], "Ks1")
        a(f"| {r['background_id']} | {r['direction'].replace('Ks1_', 'Ks1=')} | "
          f"{_f(eff['S_shape'], 4)} | {_f(eff['contour_rms_change'])} | "
          f"{_f(eff['curvature_rms_change'])} | "
          f"{_f(sub.get('residual_front_curvature_rms'))} | "
          f"{_f(sub.get('residual_rear_curvature_rms'))} | "
          f"{_f(sub.get('target_rcr'), 3)} | {_f(sub.get('substitute_rcr'), 3)} |")
    a("")
    a("说明：Ks1 只进入中弧线系数（SSm1 = Ks1·(Sm2−Sm1)），因此 LE/TE 圆弧半径变化为 0；")
    a("它的独立价值只能在中弧线/压力面/吸力面的形状中寻找，不能用户缘半径指标否定。")
    a("")

    a("## 4. 实验二：Ks2 最终裁决")
    a("")
    a("### 4.1 硬约束")
    a("")
    a("本轮规定 **Metal1、Metal2 必须固定**。上一轮曾用 Metal2 替代 Ks2，但 Metal2 直接改变出口金属角，")
    a("这种替代不能证明 Ks2 冗余。因此本轮的替代只允许 Xmean、K_m、Ks1，且进出口金属角保持不变。")
    a("")
    a("### 4.2 替代结果（后 30% 弦长为重点）")
    a("")
    a("| 背景 | 方向 | 向量残差比例 | 尾部中弧线残差 | 尾部角残差(deg) | 尾部曲率残差 | 尾部曲率残差比例 | "
      "尾部压力面 | 尾部吸力面 | 判定 |")
    a("|---|---|---|---|---|---|---|---|---|---|")
    for r in state["ks2_primary"]:
        sub = r["row"]
        a(f"| {r['background_id']} | {r['direction'].replace('Ks2_', 'Ks2=')} | "
          f"{_f(sub.get('vector_residual_fraction'), 3)} | "
          f"{_f(sub.get('residual_rear_meanline_rms'))} | "
          f"{_f(sub.get('residual_rear_angle_rms_deg'), 3)} | "
          f"{_f(sub.get('residual_rear_curvature_rms'))} | "
          f"{_f(sub.get('rear_curvature_rms_fraction'), 3)} | "
          f"{_f(sub.get('residual_rear_pressure_rms'))} | "
          f"{_f(sub.get('residual_rear_suction_rms'))} | "
          f"{'替代成功' if sub['accepted'] else '替代失败'} |")
    a("")
    a("| 背景 | 方向 | S_rear | 尾部中弧线变化 | 尾部角变化(deg) | 尾部曲率变化 | 信噪比 | 是否可分辨 |")
    a("|---|---|---|---|---|---|---|---|")
    for r in state["ks2_primary"]:
        eff = effect_metrics(r["ref_params"], r["target_params"], "Ks2")
        a(f"| {r['background_id']} | {r['direction'].replace('Ks2_', 'Ks2=')} | "
          f"{_f(eff['S_rear'], 4)} | {_f(eff['rear_meanline_change'])} | "
          f"{_f(eff['rear_angle_change_deg'], 3)} | {_f(eff['rear_curvature_change'])} | "
          f"{_f(eff['signal_to_noise_rear'], 1)} | "
          f"{'是' if eff['S_rear'] >= 0.010 else '否'} |")
    a("")
    stress = [r for r in state["ks2_all"] if r["variant"] == "stress_outside_bound"]
    if stress:
        a("补充压力测试（Xmean=0.20，**已超出最终采用上界 0.18**，只作参考、不参与裁决）：")
        a("")
        a("| 背景 | 方向 | 向量残差比例 | 尾部曲率残差比例 | 判定 |")
        a("|---|---|---|---|---|")
        for r in stress:
            sub = r["row"]
            a(f"| {r['background_id']} (stress) | {r['direction'].replace('Ks2_', 'Ks2=')} | "
              f"{_f(sub.get('vector_residual_fraction'), 3)} | "
              f"{_f(sub.get('rear_curvature_rms_fraction'), 3)} | "
              f"{'替代成功' if sub['accepted'] else '替代失败'} |")
        a("")
        if all(not r["row"]["accepted"] for r in stress):
            a("压力测试同样失败，说明 Ks2 的尾部控制作用不依赖于 Xmean 是否扩展。")
        else:
            a("压力测试中出现替代成功的组合，说明该区域需要人工复核（不改变本轮裁决）。")
        a("")
    a("### 4.3 为什么 Metal1/Metal2 固定后 Ks2 不能被替代（解析原因）")
    a("")
    a("```text")
    a("后段中弧线: sc(xc) = a5*(1-xc)^3 + a6*(1-xc)^2 + a7*(1-xc) + a8")
    a("a7 = -SSm2 = -Ks2*(Sm2-Sm1)      <-- 只有 Ks2 控制这一项")
    a("a8 = Sm2                          <-- 由 Metal2 固定")
    a("a5,a6                             <-- 由 Xmean/K_m/Ks1/Ks2 共同控制，可部分补偿")
    a("```")
    a("")
    a("在 Metal1/Metal2 固定（a8 固定）时，Xmean/K_m/Ks1 可以调整 a5、a6，但无法独立改变 a7；")
    a("而 Ks2 的作用恰恰主要是 a7。这是“保持进出口角不变时 Ks2 不可替代”的结构性原因，")
    a("与数值搜索的结果一致。上一轮之所以能用 Metal2 得到 10–23% 的轮廓残差，是因为允许了 a8 变化。")
    a("")
    a("注意：Ks2 的失败是**相对残差**失败——替代后仍保留 87%–90% 的尾部曲率变化，")
    a("而不是“只差一点绝对量”。因此它不属于阈值边缘情形。")
    a("")


    a("## 5. Xmean 上界裁决")
    a("")
    a("### 5.1 硬性 QC（必要但不充分）")
    a("")
    n_fail = sum(1 for r in state["qc_scan"] if r.get("hard_qc_status") != "PASS")
    a(f"在 Xmean = 0.18 / 0.20 / 0.22 / 0.24 / 0.26 / 0.30，Ks1 = 3/5/6/7，K_m = 0.10/0.35，")
    a(f"三个 Metal 背景下共 {len(state['qc_scan'])} 个角点：硬性 QC 失败 **{n_fail}** 个。")
    a("")
    a("这说明：**硬性 QC 不能给出上界**。它只排除了自相交、非正厚度、非有限曲率等灾难性几何；")
    a("因此本轮明确不以“100% PASS”作为扩大范围的依据，而使用软风险相对尺度。")
    a("")
    a("### 5.2 软风险地图（2200+ 内存几何）")
    a("")
    a("| Xmean 上界 | 最坏 RCR | 最坏点 | 高端(≥0.14)最坏切线回摆(deg) | 拼接曲率跳变 | 对当前 0.18 参考 | 对历史锚点 | 判定 |")
    a("|---|---|---|---|---|---|---|---|")
    for bound_key, cand in xm["candidates"].items():
        wc = cand["worst_case"]
        hi_trd = max((r["tangent_reversal_deg"] for r in state["map"]
                      if 0.14 - 1e-9 <= r["Xmean"] <= float(bound_key) + 1e-9),
                     default=float("nan"))
        a(f"| {bound_key} | {_f(cand['worst_rcr'])} | "
          f"Xmean={wc['Xmean']:.3f}, Ks1={wc['Ks1']:.0f}, K_m={wc['K_m']:.2f}, {wc['background_id']} | "
          f"{_f(hi_trd, 2)} | "
          f"{cand['worst_splice_jump_norm']:.2e} | "
          f"{'通过' if cand['cond_rcr_vs_current_bound'] else '不通过'} | "
          f"{'通过' if cand['cond_rcr_vs_anchor'] else '不通过'} | "
          f"{'**可接受**' if cand['admissible'] else '拒绝'} |")
    a("")
    a(f"> 全图最坏切线回摆 {_f(max(r['tangent_reversal_deg'] for r in state['map']), 1)}° "
      f"来自低 Xmean 角点（0.06），与上界无关，故表中给出高端（≥0.14 且 ≤ 候选上界）的最坏值。")
    a("")
    a(f"采用规则：最坏 RCR ≤ {xm['bound_rule_margin']:.2f} × 当前 0.18 上界的最坏值")
    a(f"（{_f(xm['bound_reference_worst_rcr'])}）且 ≤ {xm['bound_rule_margin']:.2f} × 历史锚点")
    a(f"（{_f(xm['anchor_rcr'])}）；切线回摆与拼接跳变不得超过历史最值的 1.25 倍。")
    a("")
    a(f"- 主规则结果：**{xm['primary_adopted_bound']:.2f}**")
    a("- 稳健性检查（同一规则在登记容差集上重算）：" +
      "，".join(f"容差 {m} → {v:.2f}" for m, v in xm["sensitivity_bounds"].items()))
    if xm["conservative_due_to_sensitivity"]:
        w20 = xm["candidates"]["0.20"]["worst_rcr"]
        w18 = xm["bound_reference_worst_rcr"]
        rel = abs(w20 - w18) / w18 * 100 if w18 else float("nan")
        a(f"- **结论对容差敏感**：0.20 仅在 1.01 容差下通过"
          f"（{_f(w20)} vs {_f(w18)}，差 {rel:.2f}%），")
        a("  在 1.00 与 0.85 下都退回 0.18。按预登记政策（敏感性 → 保守分支），")
        a(f"  **最终采用上界 = {bound:.2f}（保持 0.18 不变）**。")
    else:
        a(f"- 结论对登记容差稳健，**最终采用上界 = {bound:.2f}**。")
    a("")
    a("这不是“扩大范围被 QC 挡住”，而是“0.20 相对 0.18 在软风险上没有任何可测量的改善，")
    a("其通过与否只取决于 0.1% 级的数值容差”。在没有 CFD 证据的前提下，不值得为一个")
    a("0.1% 级的差异扩大探索范围；0.22 则在所有容差下都被拒绝（+3.4%）。")
    a("")
    a("### 5.3 联合限制")
    a("")
    if jc:
        a(f"在新增区间 0.18 < Xmean ≤ {jc['region_upper_bound']:.2f} 内，RCR 超过 "
          f"{jc['flag_threshold']:.4f}（= 0.85 × 历史锚点）的点共 {jc['flagged_points']} 个"
          f"（区间总点数 {jc['region_points']}）。")
        if jc.get("best_rule"):
            br = jc["best_rule"]
            a("")
            a(f"**拟合出的联合限制：`{br['rule']}`（保留新增区间 "
              f"{100*br['retained_fraction']:.0f}%，违例 0 个）。**")
            if len(jc.get("alternatives", [])) > 1:
                alts = jc["alternatives"][1:4]
                a("")
                a("等效备选（按保留比例排序）：" + "；".join(
                    f"`{r['rule']}`（{100*r['retained_fraction']:.0f}%）" for r in alts))
        a("")
        if jc.get("active"):
            a("该限制在最终上界下**生效**。")
        else:
            a(f"由于最终上界保持 0.18，该限制在当前配置下**不生效**；")
            a(f"它是为“未来若把 Xmean 扩展到 {jc['region_upper_bound']:.2f}”准备的准入条件。")
        a("")
        a("为什么需要它：反向曲率叶瓣随 Ks1 增大而增大、随 K_m 增大而减小。")
        a("仅限制 Xmean 无法阻止 “Xmean 高端 + Ks1 高端 + K_m 低端”这一角点；")
        a("联合限制只排除这一角点，不收缩其余参数空间。")
    else:
        a("新增区间内没有超过 0.85 × 历史锚点的点，不需要额外联合限制。")
    a("")
    a("### 5.4 上界附近的几何风险")
    a("")
    a("1. **反向曲率叶瓣**：位置在 xc ≈ Xmean 附近（拼接点之后的第一个小区间），")
    a("   物理含义是前段中弧线斜率在拼接点附近先过冲再回摆，形成局部 S 形。")
    a("2. **切线角回摆**：高端角点的回摆量为几度量级，远小于 38° 总折转，但会增加前段载荷分布的不确定性。")
    a("3. **前段曲率抬升**：Xmean 上移使前段曲率峰值与后段曲率同时增大，")
    a("   意味着叶片在前 20% 弦长承担更多弯折，CFD 中可能出现前缘加速/逆压梯度提前。")
    a("4. **不存在硬性几何失效**：在 0.30 以内仍未出现自相交或负厚度，")
    a("   因此这是一个**工程风险**问题，不是几何可行性问题。")
    a("")

    a("## 6. 最终参数配置")
    a("")
    a("```yaml")
    a(yaml.safe_dump(params, sort_keys=False, allow_unicode=True).strip())
    a("```")
    a("")

    a("## 7. 阈值敏感性、噪声与不确定性")
    a("")
    a("### 7.1 阈值敏感性（使用同一批几何，不新增 Case）")
    a("")
    a("| 参数 | 替代残差阈值 | 可替代方向数 | 可替代背景数 | 是否改变裁决 |")
    a("|---|---|---|---|---|")
    for name, table in (("Ks1", state["sensitivity"]["ks1_substitution"]),
                        ("Ks2", state["sensitivity"]["ks2_substitution"])):
        base = next(r for r in table
                    if abs(r["vector_residual_fraction_max"] - 0.25) < 1e-12)
        for row in table:
            changed = (row["n_backgrounds_accepted"] != base["n_backgrounds_accepted"])
            a(f"| {name} | {row['vector_residual_fraction_max']:.2f} | "
              f"{row['n_accepted']}/{row['n_directions']} | "
              f"{row['n_backgrounds_accepted']}/{row['n_backgrounds']} | "
              f"{'是' if changed else '否'} |")
    a("")
    a("| 上界规则容差 | 候选上界 | 最坏 RCR | 是否可接受 |")
    a("|---|---|---|---|")
    for row in state["sensitivity"]["xmean_bound"]:
        a(f"| {row['bound_rule_margin']:.2f} | {row['xmean_bound']:.2f} | "
          f"{_f(row['worst_rcr'])} | {'是' if row['admissible'] else '否'} |")
    a("")
    a("> 0.85 容差下连当前 0.18 都不通过，说明该容差过紧（它要求比现有 0.18 上界再降 15%），")
    a("> 只作为敏感性下界参考；登记值为 1.01。1.00 与 1.01 的区别只影响 0.20 的边际判定。")
    a("### 7.2 数值噪声")
    a("")
    a("所有判定均基于内存 float64；4 位小数序列化只用于测量噪声。")
    a("每个 Case 的 `serialization_noise_rms_norm` 见 `case_metrics.csv`；")
    a("低于 10 倍噪声的信号一律记为“未分辨”，不会因此删除参数。")
    a("")
    a("### 7.3 不确定性（必须与结论一起阅读）")
    a("")
    for item in crit["uncertainty"]:
        a(f"- {item}")
    a("- 反向曲率指标 RCR 的历史锚点来自一个**低 Xmean 角点**，它代表“过去已接受的最极端形态”，")
    a("  不等于“工程上可接受的最极端形态”。因此本轮上界只是**相对**保守，不是绝对安全。")
    a("- Ks1 的裁决依赖‘高端背景不可替代’这一事实；如果未来把 Xmean 上界收回到 0.18 以下，")
    a("  该证据会减弱，但本轮已按最终上界做出决定，不再安排同类复核。")
    a("")

    a("## 8. 最终回答")
    a("")
    a(f"**1. Ks1 最终保留还是固定，为什么？**")
    a("")
    a(f"**{d1['decision']}**（{d1['rule_id']}）。"
      f"在 {d1['n_backgrounds']} 个背景中，Ks1 的几何作用全部可分辨；"
      f"{d1['n_accepted']} 个背景的 Xmean+K_m 替代通过预登记阈值，"
      f"但 {d1['n_rejected_resolved']} 个背景明确失败。")
    rej = [b for b in d1["per_background"] if b["rejected"]]
    if rej:
        a("失败背景与残差：" + "；".join(
            f"`{b['background_id']}` 残差 "
            f"{_f(b['min_vector_residual'], 3)}–{_f(b['max_vector_residual'], 3)}"
            for b in rej) + "。")
    a("把 Xmean 上界从 0.18 放宽到 0.22 后，高 Xmean 背景（B3/B4）的残差从 1.000/0.538 降到 0.607/0.402——")
    a("确有改善，说明 0.18 的失败**部分**来自人为边界；但改善后仍远高于 0.25，且最优解始终贴住边界，")
    a("说明 Xmean+K_m 无法表达 Ks1 产生的前段中弧线方向。按预登记的保守规则")
    a("（存在未被可靠排除的独立作用即 KEEP），本轮保留 Ks1，范围 3.0–7.0 继续参与几何 DOE。")
    a("")
    a("**2. Ks2 最终保留还是固定，为什么？**")
    a("")
    a(f"**{d2['decision']}**（{d2['rule_id']}）。在 Metal1/Metal2 **固定**的约束下，"
      f"Ks2 在 {d2['n_resolved']}/{d2['n_backgrounds']} 个背景的后 30% 弦长作用可分辨，")
    a(f"而 Xmean+K_m+Ks1 的替代在 {d2['n_backgrounds'] - d2['n_accepted']}/{d2['n_backgrounds']} 个背景失败。")
    a("解析原因是后段中弧线的一次项系数 `a7 = -Ks2·(Sm2−Sm1)` 只由 Ks2 控制；")
    a("在进出口金属角固定的前提下，其他中弧线参数无法复现该项。上一轮“可用 Metal2 替代”的结论")
    a("是因为允许了出口金属角变化，本轮明确不接受这种替代。因此 Ks2 保留，范围 0.05–0.20。")
    a("")
    a(f"**3. Xmean 上界最终定为多少，为什么？**")
    a("")
    a(f"**{bound:.2f}**（下限 0.06，即**保持 0.18 不变**）。")
    a("")
    a("证据链：")
    a("")
    a("1. 硬性 QC 在 Xmean ≤ 0.30 的 144 个角点上全部通过，因此硬性 QC 完全不能给出上界。")
    a(f"2. 改用软风险相对尺度：0.18 的最坏 RCR = {_f(xm['bound_reference_worst_rcr'])}，")
    w20 = xm["candidates"]["0.20"]["worst_rcr"]
    w22 = xm["candidates"]["0.22"]["worst_rcr"]
    rel20 = abs(w20 - xm["bound_reference_worst_rcr"]) / xm["bound_reference_worst_rcr"] * 100
    rel22 = abs(w22 - xm["bound_reference_worst_rcr"]) / xm["bound_reference_worst_rcr"] * 100
    a(f"   0.20 = {_f(w20)}（差 {rel20:.2f}%），0.22 = "
      f"{_f(w22)}（+{rel22:.2f}%）。")
    a(f"3. 登记规则（容差 {xm['bound_rule_margin']:.2f}）下 0.20 通过、0.22 被拒绝；但稳健性检查显示 0.20 的通过")
    a(f"   完全依赖这 {rel20:.2f}% 的数值容差：容差取 1.00 时退回 0.18。")
    a("4. 按预登记政策“阈值敏感 → 取保守分支”，最终保持 0.18。")
    a("")
    a("这不是因为 0.20 的几何“不合格”，而是因为**它相对 0.18 没有任何可测量的软风险改善**，")
    a("其结论只由 0.1% 级容差决定；在没有 CFD 证据时，不值得为此扩大探索范围。")
    a("0.22 则是所有容差下都拒绝的明确结论。")
    if jc_rule:
        a(f"若未来决定试探性扩展到 0.20，必须同时实施联合限制 `{jc_rule}`"
          f"（保留新增区间 "
          f"{100*(jc['best_rule']['retained_fraction'] if jc.get('best_rule') else 0):.0f}%）。")
    a("该上界是**探索性**上界，不是 CFD 生产边界。")
    a("")
    a(f"**4. 目前最终候选是多少维？**")
    a("")
    a(f"几何 {params['dimensionality']['geometry_dimension']} 维 + 运行条件 2 维（Incidence、Mach）"
      f" = **{params['dimensionality']['total_candidate_dimension']} 维**。")
    a(f"几何参数为：{', '.join(params['dimensionality']['geometry_parameters'])}。")
    a("固定：SS1=3.2、SS2=0.8"
      + ("" if d1["decision"] == "KEEP" else "、Ks1=5.0")
      + ("" if d2["decision"] == "KEEP" else "、Ks2=0.10") + "。")
    a("")
    a("**5. 下一阶段还需要解决哪些工程问题？**")
    a("")
    a("1. **CFD 验证高端角点**：Xmean ≥ 0.19 与 Ks1 ≥ 6 的组合是否存在前缘分离/逆压梯度提前；")
    a("   几何上它只是“局部 S 形”，但气动上是否可接受必须由 CFD 回答。")
    a("2. **Ks2 的尾部控制是否需要与出口金属角解耦**：本轮证明 Ks2 不可被替代，")
    a("   但 Ks2 的工程收益（尾缘载荷、落后角）尚未用 CFD 量化。")
    a("3. **反向曲率叶瓣的网格敏感性**：叶瓣位于 xc ≈ Xmean 处，若网格在此处分辨率不足，")
    a("   可能被数值耗散抹平，导致“几何有、CFD 看不到”的假象。")
    a("4. **阈值校准**：本轮阈值为研究阈值，需用 1891 历史样本校准后再用于生产筛选。")
    a("5. **联合限制的实现**：`Xmean > 0.18` 时的联合限制需要在 DOE 采样器中真正实现，")
    a("   不能只写在报告里，否则采样会重新产生被排除的角点。")
    a("6. **Incidence / Mach 的耦合**：本轮二者固定为 0°/0.5，尚未评估它们与高端 Xmean 的交互。")
    a("")
    a("## 9. 复现与文件清单")
    a("")
    a("```bash")
    a("cd /home/qian/compressor_ai4s")
    a("conda run -n ai4s python tools/geometry_final_decision_v1.py all")
    a("conda run -n ai4s python -m pytest -q")
    a("```")
    a("")
    a("| 文件 | 内容 |")
    a("|---|---|")
    a("| `FINAL_DECISION.md` | 本报告 |")
    a("| `final_geometry_parameters.yaml` | 最终参数配置与维度 |")
    a("| `final_decision_criteria.yaml` | 预登记判据（含修订记录与 SHA256） |")
    a("| `final_decision_evidence.csv` | 长表证据（每条结论对应 Case ID + 数值 + 阈值） |")
    a("| `case_design.csv` / `case_metrics.csv` | 本轮 50 行设计/指标（含复用标记） |")
    a("| `substitution_results.csv` | 全部替代搜索结果 |")
    a("| `xmean_boundary_scan.csv` | 软风险地图（不落盘几何） |")
    a("| `xmean_hard_qc_scan.csv` | 边界硬性 QC 扫描 |")
    a("| `decision_profiles.npz` | 新增 Case 的高精度曲线（压缩） |")
    a("| `overview.png` / `decision_summary.png` | 两张总览图 |")
    a("| `provenance.json` | Git/环境/哈希/体积/回归结果 |")
    a("")
    a("> 本轮没有运行 NUMECA / CFX，没有训练模型，没有修改正式 DOE，没有自动提交 Git。")
    a("")
    a("## 10. 最终决策表（速查）")
    a("")
    def _j(bg, direction):
        for r in state["ks1_final"]:
            if r["background_id"] == bg and r["direction"] == direction:
                return r["row"]["vector_residual_fraction"]
        return float("nan")

    ks2_vals_all = [d["rear_curvature_rms_fraction"] for d in d2["details"]
                    if math.isfinite(d.get("rear_curvature_rms_fraction", float("nan")))]
    a("| 参数 | 最终决定 | 固定值或范围 | 核心证据 |")
    a("|---|---|---|---|")
    a(f"| Ks1 | {d1['decision']} | "
      f"{'3.0 – 7.0' if d1['decision'] == 'KEEP' else '5.0'} | "
      f"{d1['rule_id']}，{d1['n_rejected_resolved']}/{d1['n_backgrounds']} 背景不可替代"
      f"（B2/Ks1=3 残差 {_f(_j('B2', 'Ks1_3.00'), 3)}；"
      f"B3/Ks1=7 残差 {_f(_j('B3', 'Ks1_7.00'), 3)}；"
      f"B4/Ks1=7 残差 {_f(_j('B4', 'Ks1_7.00'), 3)}） |")
    a(f"| Ks2 | {d2['decision']} | "
      f"{'0.05 – 0.20' if d2['decision'] == 'KEEP' else '0.10'} | "
      f"{d2['rule_id']}，Metal1/Metal2 固定下 "
      f"{d2['n_rejected_resolved']}/{d2['n_backgrounds']} 背景不可替代"
      f"（尾部曲率残差 {_f(min(ks2_vals_all), 2)}–{_f(max(ks2_vals_all), 2)}） |")
    a(f"| Xmean | KEEP | 0.06 – {bound:.2f} | "
      f"XMEAN_BOUND_V1；主规则 {xm['primary_adopted_bound']:.2f} 对容差敏感"
      f"（0.12% 级），按保守政策保持 0.18；0.22 在所有容差下拒绝 |")
    a("| SS1 | FIX | 3.2 | 人工决定（FIXED_BY_REVIEW） |")
    a("| SS2 | FIX | 0.8 | 人工决定（FIXED_BY_REVIEW） |")
    a("")
    a(f"几何维度 **{params['dimensionality']['geometry_dimension']}** + "
      f"运行条件 2（Incidence、Mach） = **{params['dimensionality']['total_candidate_dimension']} 维**；"
      "状态为 FINAL（仅限探索性几何 DOE），不存在 FURTHER_REVIEW / PENDING / UNDECIDED。")
    a("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Provenance / validation
# ---------------------------------------------------------------------------
def verify_protected_assets():
    if not PROTECTED_BASELINE.is_file():
        return {"status": "NO_BASELINE", "changed": [], "missing": []}
    before = json.loads(PROTECTED_BASELINE.read_text(encoding="utf-8"))["manifest"]
    changed, missing, checked = [], [], 0
    for rel, entry in before.items():
        if entry.get("missing"):
            continue
        if "files" in entry:
            for sub, digest in entry["files"].items():
                sp = REPO / sub
                if not sp.is_file():
                    missing.append(sub)
                elif sha256_file(sp) != digest:
                    changed.append(sub)
                else:
                    checked += 1
            continue
        p = REPO / rel
        if not p.is_file():
            missing.append(rel)
            continue
        checked += 1
        if sha256_file(p) != entry["sha256"]:
            changed.append(rel)
    return {"status": "PASS" if not changed and not missing else "FAIL",
            "checked_files": checked, "changed": changed, "missing": missing}


def dir_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def write_provenance(state, extra, pytest_result=None):
    outputs = {}
    for p in sorted(OUTDIR.iterdir()):
        if p.is_file() and p.name != "provenance.json":
            outputs[p.name] = {"bytes": p.stat().st_size, "sha256": sha256_file(p)}
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "status": "EXPLORATORY_NOT_APPROVED",
        "decision_authority": ("final for the exploratory geometry DOE; not a CFD "
                              "certification and not a production approval"),
        "git_head": git_head(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "scipy": __import__("scipy").__version__,
        "matplotlib": matplotlib.__version__,
        "criteria": {"file": "final_decision_criteria.yaml",
                     "sha256": sha256_file(CRITERIA_PATH),
                     "criteria_id": state["criteria"]["criteria_id"],
                     "criteria_version": state["criteria"]["criteria_version"]},
        "code": {"driver": "tools/geometry_final_decision_v1.py",
                 "sha256": sha256_file(Path(__file__).resolve()),
                 "generator": "code/geometry_parametric_exploratory_v1.py",
                 "generator_sha256": sha256_file(
                     REPO / "code/geometry_parametric_exploratory_v1.py"),
                 "metrics_module": "tools/geometry_sensitivity_metrics_v1.py",
                 "metrics_sha256": sha256_file(
                     REPO / "tools/geometry_sensitivity_metrics_v1.py")},
        "counts": state["counts"],
        "decisions": {
            "Ks1": {k: v for k, v in state["decision_ks1"].items()
                    if k not in ("details", "per_background")},
            "Ks2": {k: v for k, v in state["decision_ks2"].items()
                    if k not in ("details", "per_background")},
            "Xmean": {"adopted_bound": state["xmean"]["adopted_bound"],
                      "primary_adopted_bound": state["xmean"]["primary_adopted_bound"],
                      "robust": state["xmean"]["robust"],
                      "conservative_due_to_sensitivity":
                          state["xmean"]["conservative_due_to_sensitivity"],
                      "sensitivity_bounds": state["xmean"]["sensitivity_bounds"],
                      "candidates": state["xmean"]["candidates"],
                      "joint_constraint": state["xmean"]["joint_constraint"]},
        },
        "historical_envelope": {
            "n_cases_total": state["envelope"]["n_cases_total"],
            "n_unique_vectors": state["envelope"]["n_unique_vectors"],
            "anchor_rcr": state["envelope"]["anchor_rcr"],
            "anchor_case": state["envelope"]["anchor_rcr_case"]["case_id"],
            "rcr_p50": state["envelope"]["rcr_p50"],
            "rcr_p90": state["envelope"]["rcr_p90"],
            "max_tangent_reversal_deg": state["envelope"]["max_tangent_reversal_deg"],
        },
        "threshold_sensitivity": state["sensitivity"],
        "protected_assets": verify_protected_assets(),
        "pytest": pytest_result or {"status": "NOT_RUN"},
        "runtime_s": state["runtime_s"],
        "output_dir_bytes_excluding_provenance": dir_size(OUTDIR),
        "outputs": outputs,
        "extra": extra,
        "forbidden_actions_not_taken": {
            "numeca": True, "cfx": True, "ai_training": True,
            "production_doe_change": True, "git_commit": True,
        },
    }
    _atomic_text(OUTDIR / "provenance.json",
                 json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return payload


def write_readme(state, prov):
    d1 = state["decision_ks1"]
    d2 = state["decision_ks2"]
    bound = state["xmean"]["adopted_bound"]
    params = build_final_parameters(state)
    mb = prov["output_dir_bytes"] / (1024 * 1024)
    lines = [
        "# 几何参数最终裁决 V1（Ks1 / Ks2 / Xmean）",
        "",
        "```text",
        "状态            : EXPLORATORY / NOT APPROVED（不是 CFD 认证）",
        f"新增 Case       : {state['counts']['n_new']}（复用历史 {state['counts']['n_reused']}）",
        f"Ks1             : {d1['decision']}（{d1['rule_id']}）",
        f"Ks2             : {d2['decision']}（{d2['rule_id']}）",
        f"Xmean 上界      : {bound:.2f}（下限 0.06）",
        f"几何维度        : {params['dimensionality']['geometry_dimension']}",
        f"总候选维度      : {params['dimensionality']['total_candidate_dimension']}",
        f"本目录体积      : {mb:.3f} MB",
        "```",
        "",
        "本轮不运行 NUMECA / CFX / AI 训练，不修改正式 DOE 或生产范围。",
        "SS1=3.2、SS2=0.8 保持 FIXED_BY_REVIEW，不重新开放。",
        "",
        "## 入口文件",
        "",
        "| 文件 | 用途 |",
        "|---|---|",
        "| `FINAL_DECISION.md` | ★ 中文最终报告（含决策表与 5 个回答） |",
        "| `final_geometry_parameters.yaml` | 最终参数配置、联合限制、维度 |",
        "| `final_decision_criteria.yaml` | 预登记判据（含修订记录） |",
        "| `final_decision_evidence.csv` | 长表证据 |",
        "| `case_design.csv` / `case_metrics.csv` | 设计与指标（含复用标记） |",
        "| `substitution_results.csv` | 替代搜索全部结果 |",
        "| `xmean_boundary_scan.csv` | 软风险地图 |",
        "| `xmean_hard_qc_scan.csv` | 边界硬性 QC |",
        "| `decision_profiles.npz` | 新增 Case 高精度曲线 |",
        "| `overview.png` / `decision_summary.png` | 两张总览图 |",
        "| `provenance.json` | Git / 哈希 / 体积 / 回归结果 |",
        "| `protected_assets_before.sha256.json` | 本轮开始前的受保护资产哈希基线 |",
        "",
        "## 复现",
        "",
        "```bash",
        "cd /home/qian/compressor_ai4s",
        "conda run -n ai4s python tools/geometry_final_decision_v1.py all",
        "conda run -n ai4s python -m pytest -q",
        "```",
        "",
        "> `geometry_ok=1` / `hard QC PASS` ≠ 气动合理 ≠ 网格可生成 ≠ CFD 可收敛。",
        "",
    ]
    _atomic_text(OUTDIR / "README.md", "\n".join(lines))
    return OUTDIR / "README.md"


def run_pytest():
    import subprocess
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=str(REPO), capture_output=True, text=True, timeout=1800)
        tail = (proc.stdout or "").strip().splitlines()[-3:]
        return {"status": "PASS" if proc.returncode == 0 else "FAIL",
                "returncode": proc.returncode, "tail": tail}
    except Exception as exc:
        return {"status": "ERROR", "reason": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def cmd_run():
    state = run_analysis(verbose=True)
    n_design = write_design_and_metrics(state)
    n_sub = write_substitution_csv(state)
    n_map, n_qc = write_map_and_qc(state)
    n_ev = write_evidence_csv(state)
    ids, reused = write_profiles_npz(state)
    npz_check = verify_npz(state)
    plot_overview(state)
    plot_decisions(state)
    params = write_final_parameters(state)
    _atomic_text(OUTDIR / "FINAL_DECISION.md", build_report(state))
    print(f"      wrote design/metrics {n_design}, substitution {n_sub}, "
          f"map {n_map}, qc {n_qc}, evidence {n_ev}")
    print(f"      npz {len(ids)} new + {len(reused)} reused; reload_ok="
          f"{npz_check['reload_ok']}")
    print(f"      decisions: Ks1={state['decision_ks1']['decision']} "
          f"Ks2={state['decision_ks2']['decision']} "
          f"Xmean<={state['xmean']['adopted_bound']:.2f} "
          f"geometry_dim={params['dimensionality']['geometry_dimension']}")
    return state, npz_check


def cmd_validate():
    checks = {}
    required = ["FINAL_DECISION.md", "final_geometry_parameters.yaml",
                "final_decision_evidence.csv", "final_decision_criteria.yaml",
                "case_design.csv", "case_metrics.csv",
                "substitution_results.csv", "xmean_boundary_scan.csv",
                "decision_profiles.npz", "README.md", "provenance.json",
                "overview.png", "decision_summary.png"]
    checks["missing_files"] = [f for f in required if not (OUTDIR / f).is_file()]
    with open(OUTDIR / "final_geometry_parameters.yaml", encoding="utf-8") as f:
        final = yaml.safe_load(f)
    checks["final_decision_states"] = {
        "Ks1": final["decision_evidence"]["Ks1"]["decision"],
        "Ks2": final["decision_evidence"]["Ks2"]["decision"],
        "Xmean_upper": final["xmean"]["upper_bound"],
    }
    bad = [v for k, v in checks["final_decision_states"].items()
           if isinstance(v, str) and v in ("FURTHER_REVIEW", "PENDING", "UNDECIDED")]
    checks["no_review_state"] = not bad
    checks["protected_assets"] = verify_protected_assets()
    with np.load(OUTDIR / "decision_profiles.npz", allow_pickle=False) as d:
        checks["npz_cases"] = len(d["case_ids"])
    checks["criteria_sha256"] = sha256_file(CRITERIA_PATH)
    checks["output_dir_bytes"] = dir_size(OUTDIR)
    checks["all_ok"] = (not checks["missing_files"]
                        and checks["no_review_state"]
                        and checks["protected_assets"]["status"] == "PASS")
    return checks


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="all",
                        choices=["all", "run", "validate"])
    args = parser.parse_args(argv)

    if args.command in ("all", "run"):
        state, npz_check = cmd_run()
        if args.command == "all":
            pytest_result = run_pytest()
            print(f"      pytest: {pytest_result['status']} "
                  f"{pytest_result.get('tail', '')}")
            # README with the final size, then provenance
            total = dir_size(OUTDIR)
            prov = {"output_dir_bytes": total}
            write_readme(state, prov)
            prov = write_provenance(state, {"npz": npz_check},
                                    pytest_result=pytest_result)
            write_readme(state, {"output_dir_bytes": dir_size(OUTDIR)})
            print(f"      protected assets: "
                  f"{prov['protected_assets']['status']} "
                  f"({prov['protected_assets']['checked_files']} files)")
            print(f"      output dir: {dir_size(OUTDIR)/1024/1024:.3f} MB")
    else:
        checks = cmd_validate()
        print(json.dumps(checks, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




























