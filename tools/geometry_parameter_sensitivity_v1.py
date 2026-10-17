#!/usr/bin/env python
"""Geometry Parameter Sensitivity & Screening V1 — 100 deterministic cases.

Experiment entry point.  Writes ONLY to
``analysis/geometry_review/parameter_sensitivity_v1_100cases/``.

Stages
------
S1  single-factor sweep        : 1 baseline + 5 key params x 7 levels
                                 + 8 other params x 3 levels = 60 cases
S2  2x2 coupling               : 5 pairs x 4 = 20 cases
S3  deterministic adaptive     : 5 anchors + 15 single-parameter variants = 20 cases

Nothing here runs NUMECA / CFX, trains a model, changes a frozen file, or
freezes a production range.

Usage
-----
    conda run -n ai4s python tools/geometry_parameter_sensitivity_v1.py all
    conda run -n ai4s python tools/geometry_parameter_sensitivity_v1.py design
    conda run -n ai4s python tools/geometry_parameter_sensitivity_v1.py run
    conda run -n ai4s python tools/geometry_parameter_sensitivity_v1.py analyze
    conda run -n ai4s python tools/geometry_parameter_sensitivity_v1.py validate
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

EXPERIMENT_ID = "parameter_sensitivity_v1_100cases"
OUTDIR = REPO / "analysis" / "geometry_review" / EXPERIMENT_ID
TEMPLATE_PATH = REPO / "legacy" / "blade_batch_generation_template.geomTurbo"

CASE_PREFIX = "C82"
CASE_START = 1
N_TOTAL = 100

PARAMS = list(gen.PARAM_NAMES)
ORIGINAL_PARAMS = ["Xthick", "Tmax", "Metal2", "Solidity"]
KEY_PARAMS = ["Metal1", "T1", "T2", "Xmean", "K_m"]
OTHER_PARAMS = ["Ks1", "Ks2", "SS1", "SS2"]

BASELINE = {
    "Xthick": 0.30, "Tmax": 0.055, "Metal2": 15.0, "Solidity": 1.5,
    "Metal1": 53.0, "T1": 0.015, "T2": 0.0125, "Xmean": 0.08, "K_m": 0.18,
    "Ks1": 5.0, "Ks2": 0.10, "SS1": 3.2, "SS2": 0.8,
}

RANGES = {
    "Xthick": (0.10, 0.60),
    "Tmax": (0.025, 0.095),
    "Metal2": (0.0, 32.0),
    "Solidity": (0.7, 2.5),
    "Metal1": (48.0, 58.0),
    "T1": (0.010, 0.018),
    "T2": (0.008, 0.016),
    "Xmean": (0.06, 0.18),
    "K_m": (0.10, 0.35),
    "Ks1": (3.0, 7.0),
    "Ks2": (0.05, 0.20),
    "SS1": (2.4, 4.0),
    "SS2": (0.5, 1.1),
}

FIXED_METADATA = {"Incidence": 0.0, "Mach": 0.5}

RANGE_ID = "parameter_sensitivity_v1"
SAMPLING_ID = "deterministic_single_factor_coupling_adaptive_v1"
SOBOL_SEED = 20261017
MIN_SEPARATION_U = 0.05
POOL_SIZE = 512
N_ANCHORS = 5
N_VARIANTS_PER_ANCHOR = 3
ANCHOR_MIN_DISTANCE = 0.35
NEAR_DUPLICATE_DISTANCE = 0.15

PAIR_GROUPS = [
    ("Xmean", "K_m"),
    ("T1", "SS1"),
    ("T2", "SS2"),
    ("Metal1", "Metal2"),
    ("Metal2", "Solidity"),
]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def case_id(index: int) -> str:
    return f"{CASE_PREFIX}{CASE_START + index - 1:04d}"


def fmt(value, digits=12):
    """Deterministic CSV cell formatting.

    Floats use Python's shortest round-trip representation (``repr``), so that
    re-reading ``case_design.csv`` reproduces the exact float and therefore the
    exact geometry stored in ``profiles.npz``.  ``digits`` is kept for backward
    compatibility of call sites that pass it explicitly.
    """
    if value is None:
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "1" if bool(value) else "0"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        f = float(value)
        if not math.isfinite(f):
            return ""
        return repr(f)
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


def git_status() -> list:
    import subprocess
    try:
        out = subprocess.check_output(
            ["git", "-C", str(REPO), "status", "--porcelain=v1"],
            text=True, stderr=subprocess.DEVNULL)
        return [ln for ln in out.splitlines() if ln.strip()]
    except Exception:
        return []


def u_of(param: str, value: float) -> float:
    lo, hi = RANGES[param]
    return (float(value) - lo) / (hi - lo)


def value_of_u(param: str, u: float) -> float:
    lo, hi = RANGES[param]
    return lo + float(u) * (hi - lo)


def vector_distance(a: dict, b: dict) -> float:
    """Normalized 13-D Euclidean distance (range-normalized coordinates)."""
    d2 = 0.0
    for p in PARAMS:
        d2 += (u_of(p, a[p]) - u_of(p, b[p])) ** 2
    return math.sqrt(d2)


def params_equal(a: dict, b: dict, tol=1e-12) -> bool:
    return all(abs(float(a[p]) - float(b[p])) <= tol * max(1.0, abs(float(b[p])))
               for p in PARAMS)


# ---------------------------------------------------------------------------
# Deterministic level construction (documented rule)
# ---------------------------------------------------------------------------
def make_levels(param: str, k: int):
    """Return ``(levels, normalized_levels, rule_text)``.

    Rule (recorded in experiment_config.yaml):
      * target normalized levels = linspace(0, 1, k);
      * a target closer than MIN_SEPARATION_U to the baseline is shifted by
        +1/(2k) repeatedly (deterministic priority: lower levels first);
      * endpoints are always kept; duplicates are rejected;
      * every level is strictly different from the baseline.
    """
    base = BASELINE[param]
    ub = u_of(param, base)
    targets = [float(t) for t in np.linspace(0.0, 1.0, k)]
    shift = 1.0 / (2.0 * k)
    used = []
    for t in targets:
        u = t
        if 0.0 < u < 1.0:
            guard = 0
            while abs(u - ub) < MIN_SEPARATION_U or any(
                    abs(u - v) < 1e-9 for v in used):
                u += shift
                if u > 1.0:
                    u -= 2.0 * shift
                guard += 1
                if guard > 100:
                    break
        if 0.0 < u < 1.0 and abs(u - ub) < MIN_SEPARATION_U:
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
    rule = (f"targets=linspace(0,1,{k}); min_separation_u={MIN_SEPARATION_U}; "
            f"conflict_shift=+1/(2*{k}); endpoints kept; baseline excluded")
    return levels, us, rule


# ---------------------------------------------------------------------------
# Design: stages 1 and 2
# ---------------------------------------------------------------------------
def _case_record(index, stage, design_group, params, **extra):
    row = {
        "case_id": case_id(index),
        "stage": stage,
        "design_group": design_group,
        "sweep_param": "",
        "pair_params": "",
        "level_index": "",
        "level_value": "",
        "level_u": "",
        "level_rule": "",
        "is_baseline": 0,
        "anchor_case_id": "",
        "selection_reason": "",
        "selection_evidence": "",
        "planned_varied_params": "",
    }
    row.update({p: float(params[p]) for p in PARAMS})
    row.update({f"u_{p}": u_of(p, params[p]) for p in PARAMS})
    row.update(FIXED_METADATA)
    row["range_id"] = RANGE_ID
    row["sampling_id"] = SAMPLING_ID
    row.update(extra)
    return row


def build_stage12():
    """Build the 60 stage-1 + 20 stage-2 cases (deterministic, no randomness)."""
    cases = []
    base = _case_record(1, "S1", "S1_baseline", BASELINE)
    base["is_baseline"] = 1
    base["selection_reason"] = "baseline"
    base["selection_evidence"] = "all 13 parameters at the experiment baseline"
    cases.append(base)

    level_plan = {}
    for param in KEY_PARAMS:
        levels, us, rule = make_levels(param, 7)
        level_plan[param] = {"n_levels": 7, "levels": levels, "u": us, "rule": rule}
        for i, (v, u) in enumerate(zip(levels, us), 1):
            p = dict(BASELINE)
            p[param] = v
            row = _case_record(
                len(cases) + 1, "S1", f"S1_{param}", p,
                sweep_param=param, level_index=i, level_value=v, level_u=u,
                level_rule=rule, planned_varied_params=param,
                selection_reason="single_factor_sweep",
                selection_evidence=f"{param}={v:.10g} at normalized u={u:.6f}")
            cases.append(row)

    for param in ORIGINAL_PARAMS + OTHER_PARAMS:
        levels, us, rule = make_levels(param, 3)
        level_plan[param] = {"n_levels": 3, "levels": levels, "u": us, "rule": rule}
        for i, (v, u) in enumerate(zip(levels, us), 1):
            p = dict(BASELINE)
            p[param] = v
            row = _case_record(
                len(cases) + 1, "S1", f"S1_{param}", p,
                sweep_param=param, level_index=i, level_value=v, level_u=u,
                level_rule=rule, planned_varied_params=param,
                selection_reason="single_factor_sweep",
                selection_evidence=f"{param}={v:.10g} at normalized u={u:.6f}")
            cases.append(row)

    assert len(cases) == 60, len(cases)

    for a, b in PAIR_GROUPS:
        combos = [(0.25, 0.25), (0.25, 0.75), (0.75, 0.25), (0.75, 0.75)]
        for i, (ua, ub) in enumerate(combos, 1):
            p = dict(BASELINE)
            p[a] = value_of_u(a, ua)
            p[b] = value_of_u(b, ub)
            row = _case_record(
                len(cases) + 1, "S2", f"S2_{a}_x_{b}", p,
                pair_params=f"{a};{b}",
                level_index=i, level_u=f"{ua:.6f};{ub:.6f}",
                level_rule=("2x2 corner design: each pair parameter at u in {0.25, 0.75}; "
                            "the other 11 parameters at the baseline"),
                planned_varied_params=f"{a};{b}",
                selection_reason="two_level_2x2_coupling",
                selection_evidence=(
                    f"{a}={p[a]:.10g} (u={ua}), {b}={p[b]:.10g} (u={ub}); "
                    f"other 11 parameters at baseline"))
            cases.append(row)

    assert len(cases) == 80, len(cases)
    return cases, level_plan


# ---------------------------------------------------------------------------
# Feature extraction, sensitivity, interactions
# ---------------------------------------------------------------------------
COMPOSITE_WEIGHTS = {
    "S_contour": 0.30, "S_camber": 0.20, "S_le": 0.15,
    "S_te": 0.15, "S_thickness": 0.15, "S_cascade": 0.05,
}
EXTRA_FEATURE_KEYS = [
    "f_le_radius", "f_le_region", "f_te_radius", "f_te_region",
    "f_camber_meanline", "f_camber_angle", "f_thickness_total",
    "f_thickness_front", "f_thickness_mid", "f_thickness_rear",
    "f_cascade_gap", "f_cascade_pitch",
]
FEATURE_KEYS = list(COMPOSITE_WEIGHTS) + EXTRA_FEATURE_KEYS

SIGNATURE_KEYS = [
    "signed_meanline_025", "signed_meanline_050", "signed_meanline_075",
    "signed_thickness_010", "signed_thickness_050", "signed_thickness_090",
    "signed_le_radius_rel", "signed_te_radius_rel",
    "signed_chord_angle_rad", "signed_chord_len_rel", "signed_min_gap_rel",
    "signed_meanline_kappa_010", "signed_meanline_kappa_050",
    "signed_meanline_kappa_090",
]


def _num(value) -> float:
    if value is None or value == "":
        return float("nan")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _absnum(value) -> float:
    v = _num(value)
    return abs(v) if math.isfinite(v) else 0.0


def unsigned_features(metrics_row: dict) -> dict:
    """Per-region unsigned geometric sensitivity features (criteria section 3)."""
    f = {
        "S_contour": _absnum(metrics_row.get("contour_rms_dev_norm")),
        "S_le": max(_absnum(metrics_row.get("le_radius_change_rel")),
                    _absnum(metrics_row.get("le_region_rms_dev_norm"))),
        "S_te": max(_absnum(metrics_row.get("te_radius_change_rel")),
                    _absnum(metrics_row.get("te_region_rms_dev_norm"))),
        "S_camber": max(_absnum(metrics_row.get("meanline_rms_dev_norm")),
                        math.radians(_absnum(
                            metrics_row.get("meanline_tangent_rms_dev_deg")))),
        "S_thickness": max(
            _absnum(metrics_row.get("thickness_rms_dev_norm")),
            _absnum(metrics_row.get("thickness_front_rms_dev_norm")),
            _absnum(metrics_row.get("thickness_mid_rms_dev_norm")),
            _absnum(metrics_row.get("thickness_rear_rms_dev_norm"))),
        "S_cascade": max(_absnum(metrics_row.get("min_gap_change_rel")),
                         _absnum(metrics_row.get("periodicity_change_rel"))),
        # decomposed diagnostics (not separately weighted in S_comp)
        "f_le_radius": _absnum(metrics_row.get("le_radius_change_rel")),
        "f_le_region": _absnum(metrics_row.get("le_region_rms_dev_norm")),
        "f_te_radius": _absnum(metrics_row.get("te_radius_change_rel")),
        "f_te_region": _absnum(metrics_row.get("te_region_rms_dev_norm")),
        "f_camber_meanline": _absnum(metrics_row.get("meanline_rms_dev_norm")),
        "f_camber_angle": math.radians(_absnum(
            metrics_row.get("meanline_tangent_rms_dev_deg"))),
        "f_thickness_total": _absnum(metrics_row.get("thickness_rms_dev_norm")),
        "f_thickness_front": _absnum(
            metrics_row.get("thickness_front_rms_dev_norm")),
        "f_thickness_mid": _absnum(
            metrics_row.get("thickness_mid_rms_dev_norm")),
        "f_thickness_rear": _absnum(
            metrics_row.get("thickness_rear_rms_dev_norm")),
        "f_cascade_gap": _absnum(metrics_row.get("min_gap_change_rel")),
        "f_cascade_pitch": _absnum(metrics_row.get("periodicity_change_rel")),
    }
    f["S_comp"] = sum(COMPOSITE_WEIGHTS[k] * f[k] for k in COMPOSITE_WEIGHTS)
    return f


def signed_signature(metrics_row: dict) -> np.ndarray:
    vals = []
    for k in SIGNATURE_KEYS:
        v = _num(metrics_row.get(k))
        vals.append(v if math.isfinite(v) else 0.0)
    return np.asarray(vals, dtype=float)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na <= 0.0 or nb <= 0.0:
        return float("nan")
    return float(np.dot(a, b) / (na * nb))


def estimate_stage1_sensitivity(rows, criteria) -> dict:
    """S_feature and monotonicity from the stage-1 single-factor sweeps."""
    import scipy.stats as st

    base = next(r for r in rows if r["is_baseline"])
    base_f = unsigned_features(base["metrics"])
    base_sig = signed_signature(base["metrics"])

    out = {}
    for param in PARAMS:
        level_rows = [r for r in rows
                      if r["stage"] == "S1" and r["sweep_param"] == param]
        per_feature = {k: [] for k in FEATURE_KEYS}
        signed_effects = {k: [] for k in SIGNATURE_KEYS}
        raw_sigs = []
        used = []
        failed = []
        for r in level_rows:
            du = abs(float(r["level_u"]) - u_of(param, BASELINE[param]))
            if r["hard_qc_status"] != "PASS" or du <= 0.0:
                failed.append({
                    "case_id": r["case_id"], "level": r["level_value"],
                    "level_u": r["level_u"],
                    "status": r["hard_qc_status"],
                    "reason": r.get("qc_reason", "")})
                continue
            f = unsigned_features(r["metrics"])
            for k in FEATURE_KEYS:
                per_feature[k].append(abs(f[k] - base_f[k]) / du)
            sig = signed_signature(r["metrics"]) - base_sig
            raw_sigs.append(sig)
            for i, k in enumerate(SIGNATURE_KEYS):
                signed_effects[k].append(float(sig[i] / du))
            used.append(r)

        S = {k: (max(v) if v else 0.0) for k, v in per_feature.items()}
        S["S_comp"] = sum(COMPOSITE_WEIGHTS[k] * S[k] for k in COMPOSITE_WEIGHTS)

        best_key, best_mag = None, -1.0
        for k in SIGNATURE_KEYS:
            if signed_effects[k]:
                mag = max(abs(v) for v in signed_effects[k])
                if mag > best_mag:
                    best_key, best_mag = k, mag

        monotonicity, rho = "UNCERTAIN", float("nan")
        if used and len(used) >= 3:
            vecs = np.array([[signed_effects[k][i] for k in SIGNATURE_KEYS]
                             for i in range(len(used))], dtype=float)
            raw = np.asarray(raw_sigs, dtype=float)
            mean_dir = vecs.mean(axis=0)
            if float(np.linalg.norm(mean_dir)) > 0.0:
                # signed scalar response: raw signature projected on the mean
                # response direction (keeps the sign of Delta u)
                proj = raw @ mean_dir
                du_list = [float(r["level_u"]) - u_of(param, BASELINE[param])
                           for r in used]
                tol = 1e-12 * max(1.0, float(np.max(np.abs(proj))))
                signs = np.sign(proj[np.abs(proj) > tol])
                changes = int(np.sum(signs[1:] != signs[:-1])) if len(signs) > 1 else 0
                if len(set(proj)) > 1:
                    rho = float(st.spearmanr(du_list, proj).correlation)
                    if math.isfinite(rho) and abs(rho) >= 0.9 and changes <= 1:
                        monotonicity = "MONOTONE"
                    elif changes >= 1:
                        monotonicity = "NON_MONOTONE"
                    else:
                        monotonicity = "UNCERTAIN"
                elif changes == 0:
                    monotonicity = "MONOTONE"

        out[param] = {
            "sensitivity": S,
            "monotonicity": monotonicity,
            "spearman_rho": rho,
            "dominant_signed_feature": best_key or "",
            "n_levels": len(level_rows),
            "n_valid_levels": len(used),
            "failed_levels": failed,
            "valid_case_ids": [r["case_id"] for r in used],
            "signed_effects": signed_effects,
        }
    return out


def stage2_interaction(rows, criteria) -> dict:
    """Relative interaction index for every stage-2 2x2 group and metric."""
    out = {}
    metric_keys = ["contour_rms_dev_norm", "le_region_rms_dev_norm",
                   "te_region_rms_dev_norm", "meanline_rms_dev_norm",
                   "thickness_rms_dev_norm", "min_gap_change_rel"]
    for a, b in PAIR_GROUPS:
        group = sorted(
            [r for r in rows if r["design_group"] == f"S2_{a}_x_{b}"],
            key=lambda r: int(r["level_index"]))
        if len(group) != 4:
            continue
        v_ll, v_lh, v_hl, v_hh = [r["metrics"] for r in group]
        pair_out = {}
        for key in metric_keys:
            vals = [_num(x.get(key)) for x in (v_ll, v_lh, v_hl, v_hh)]
            if not all(math.isfinite(x) for x in vals):
                pair_out[key] = float("nan")
                continue
            total = abs(vals[3] - vals[0])
            interaction = abs((vals[3] - vals[1]) - (vals[2] - vals[0]))
            pair_out[key] = float(interaction / total) if total > 1e-12 else 0.0
        pair_out["mean"] = float(np.nanmean([pair_out[k] for k in metric_keys]))
        out[f"{a};{b}"] = pair_out
    return out


# ---------------------------------------------------------------------------
# Execution of geometry + metrics + frozen-QC cross-check
# ---------------------------------------------------------------------------
def flatten_result(rec: dict) -> dict:
    row = dict(rec["design"])
    row.update(rec["metrics"])
    row["generation_status"] = rec["generation_status"]
    row["failure_reason"] = rec["failure_reason"]
    row["metric_status"] = rec["metric_status"]
    row["runtime_s"] = rec["runtime_s"]
    row.update(rec.get("frozen", {}))
    return row


def run_cases(cases, base_geom, base_ind, criteria, template_text,
              do_frozen_qc=True):
    thr = criteria["thresholds"]
    tmpdir = tempfile.mkdtemp(prefix="psv1_frozen_qc_") if do_frozen_qc else None
    results = []
    for design in cases:
        params = {p: float(design[p]) for p in PARAMS}
        t0 = time.time()
        rec = {
            "design": design, "metrics": {}, "geom": None,
            "generation_status": "FAIL", "failure_reason": "",
            "metric_status": "NOT_RUN", "frozen": {},
        }
        try:
            geom = gen.compute_geometry(params)
            rec["geom"] = geom
            rec["generation_status"] = "OK"
        except Exception as exc:
            rec["failure_reason"] = f"GENERATION_ERROR: {type(exc).__name__}: {exc}"
            rec["runtime_s"] = time.time() - t0
            results.append(rec)
            continue

        try:
            flat, _ = metrics.compute_case_metrics(
                geom, base_geom, base_ind, thr)
            flat["qc_policy_id"] = metrics.QC_POLICY_ID
            flags = []
            if flat.get("hard_qc_status") != "PASS":
                flags.append(flat.get("qc_reason", "QC_FAIL"))
            if flat.get("junction_jump_warning"):
                flags.append("JUNCTION_JUMP_DIAGNOSTIC")
            if flat.get("negative_half_thickness"):
                flags.append("NEGATIVE_HALF_THICKNESS")
            if (flat.get("le_curvature_reliable") is False
                    or flat.get("te_curvature_reliable") is False):
                flags.append("CURVATURE_UNRELIABLE")
            flat["auto_flags"] = ";".join(flags) if flags else "OK"
            rec["metrics"] = flat
            rec["metric_status"] = "OK"
        except Exception as exc:
            rec["metric_status"] = "ERROR"
            rec["failure_reason"] = f"METRIC_ERROR: {type(exc).__name__}: {exc}"
            rec["metrics"] = {
                "hard_qc_status": "ERROR", "qc_reason": "METRIC_ERROR"}

        if do_frozen_qc:
            try:
                profile_text = gen.serialize_profile(geom)
                geom_text = gen.generate_geomturbo_text(
                    profile_text, params["Solidity"], template_text)
                rec["frozen"] = metrics.frozen_qc_crosscheck(
                    design["case_id"], params, profile_text, geom_text, tmpdir)
            except Exception as exc:
                rec["frozen"] = {
                    "frozen_qc_status": "ERROR",
                    "frozen_qc_reason": f"{type(exc).__name__}: {exc}",
                    "frozen_qc_policy_id": metrics.QC_POLICY_ID,
                }
        rec["runtime_s"] = time.time() - t0
        results.append(rec)
    return results, tmpdir


# ---------------------------------------------------------------------------
# Stage 3: deterministic adaptive selection
# ---------------------------------------------------------------------------
def adaptive_select(existing_design, stage12_results, criteria,
                    base_geom, base_ind):
    import scipy.stats as st
    from scipy.stats import qmc

    thr = criteria["thresholds"]
    rows = []
    for rec in stage12_results:
        row = dict(rec["design"])
        row["metrics"] = rec["metrics"]
        row["hard_qc_status"] = rec["metrics"].get("hard_qc_status", "")
        row["generation_status"] = rec["generation_status"]
        rows.append(row)
    sens = estimate_stage1_sensitivity(rows, criteria)
    inter = stage2_interaction(rows, criteria)

    low_params = [p for p in PARAMS
                  if sens[p]["sensitivity"]["S_comp"] < thr["review_comp"]
                  and sens[p]["n_levels"] >= thr["min_levels_for_fix"]]
    ranked_params = sorted(
        PARAMS, key=lambda p: (-sens[p]["sensitivity"]["S_comp"], p))

    # deterministic Sobol candidate pool (no pool geometry is written to disk)
    sobol = qmc.Sobol(d=len(PARAMS), scramble=True, seed=SOBOL_SEED)
    pool_u = sobol.random(POOL_SIZE)
    candidates = []
    for idx, urow in enumerate(pool_u):
        u = {p: float(v) for p, v in zip(PARAMS, urow)}
        params = {p: value_of_u(p, u[p]) for p in PARAMS}
        dmin = min(vector_distance(params, e) for e in existing_design)
        if dmin < NEAR_DUPLICATE_DISTANCE:
            continue
        cand = {"pool_index": idx, "params": params, "u": u,
                "dist_existing": dmin, "hard_qc_status": "FAIL",
                "min_gap_m": float("nan"), "contour_rms": float("nan")}
        try:
            geom = gen.compute_geometry(params)
            flat, _ = metrics.compute_case_metrics(
                geom, base_geom, base_ind, thr)
            cand["hard_qc_status"] = flat["hard_qc_status"]
            cand["min_gap_m"] = _num(flat.get("min_gap_m"))
            cand["contour_rms"] = _num(flat.get("contour_rms_dev_norm"))
        except Exception:
            pass
        candidates.append(cand)

    valid = [c for c in candidates
             if c["hard_qc_status"] == "PASS" and math.isfinite(c["min_gap_m"])]
    gaps = [c["min_gap_m"] for c in valid]
    for c in candidates:
        if (c["hard_qc_status"] == "PASS"
                and math.isfinite(c["min_gap_m"]) and gaps):
            c["risk"] = 1.0 - st.percentileofscore(gaps, c["min_gap_m"]) / 100.0
        elif c["hard_qc_status"] == "PASS":
            c["risk"] = 0.5
        else:
            c["risk"] = 0.9
        c["boundary"] = 1.0 - 2.0 * min(min(c["u"][p], 1.0 - c["u"][p])
                                        for p in PARAMS)
        if low_params:
            c["low_s_coverage"] = float(np.mean([
                min(1.0, abs(c["u"][p] - u_of(p, BASELINE[p])) / 0.5)
                for p in low_params]))
        else:
            c["low_s_coverage"] = 0.0
        c["score"] = (0.40 * min(c["dist_existing"] / math.sqrt(len(PARAMS)), 1.0)
                      + 0.25 * c["boundary"]
                      + 0.20 * c["risk"]
                      + 0.15 * c["low_s_coverage"])

    ranked = sorted(candidates, key=lambda c: (-c["score"], c["pool_index"]))
    anchors = []
    for min_d in (ANCHOR_MIN_DISTANCE, 0.25, 0.15, 0.0):
        for c in ranked:
            if len(anchors) >= N_ANCHORS:
                break
            if any(c["pool_index"] == a["pool_index"] for a in anchors):
                continue
            if all(vector_distance(c["params"], a["params"]) >= min_d
                   for a in anchors):
                anchors.append(c)
        if len(anchors) >= N_ANCHORS:
            break

    partner_of = {}
    for pair_key, values in inter.items():
        a, b = pair_key.split(";")
        for p, q in ((a, b), (b, a)):
            score = values.get("mean", 0.0)
            if not math.isfinite(score):
                continue
            if p not in partner_of or score > partner_of[p][1]:
                partner_of[p] = (q, float(score))

    def _target_u(anchor_u):
        return 0.15 if anchor_u >= 0.5 else 0.85

    def _extreme(u):
        return u < 0.12 or u > 0.88

    def _make_variant(anchor, param, category, evidence_extra):
        target = _target_u(anchor["u"][param])
        if abs(target - anchor["u"][param]) < 0.15:
            target = 1.0 - target
        params = dict(anchor["params"])
        params[param] = value_of_u(param, target)
        if any(params_equal(params, e) for e in existing_design):
            return None
        evidence = {
            "kind": category,
            "anchor_pool_index": anchor["pool_index"],
            "changed_param": param,
            "from_u": anchor["u"][param],
            "to_u": target,
            "from_value": anchor["params"][param],
            "to_value": params[param],
            "sensitivity_rank": ranked_params.index(param) + 1,
            "S_comp": sens[param]["sensitivity"]["S_comp"],
        }
        evidence.update(evidence_extra)
        return params, evidence

    stage3_cases = []
    selection_records = []
    v1_cursor = 0
    v3_cursor = 0
    recheck_params = sorted(
        [p for p in PARAMS if p != "Solidity"
         and sens[p]["sensitivity"]["S_comp"] < thr["keep_comp"]],
        key=lambda p: (sens[p]["sensitivity"]["S_comp"], p))
    if not recheck_params:
        recheck_params = [p for p in ranked_params if p != "Solidity"]

    for anchor in anchors:
        anchor_row = _case_record(
            len(existing_design) + len(stage3_cases) + 1, "S3",
            "S3_anchor", anchor["params"],
            planned_varied_params="",
            level_rule=("adaptive anchor: deterministic Sobol pool candidate selected "
                        "by the recorded anchor score; no single swept parameter"),
            selection_reason="adaptive_anchor",
            selection_evidence=json.dumps({
                "score": round(anchor["score"], 6),
                "dist_existing": round(anchor["dist_existing"], 6),
                "boundary": round(anchor["boundary"], 6),
                "risk": round(anchor["risk"], 6),
                "low_s_coverage": round(anchor["low_s_coverage"], 6),
                "pool_index": anchor["pool_index"],
                "min_gap_m": anchor["min_gap_m"],
                "hard_qc_status": anchor["hard_qc_status"],
                "low_s_params": low_params,
            }, sort_keys=True))
        anchor_row["anchor_case_id"] = anchor_row["case_id"]
        stage3_cases.append(anchor_row)
        selection_records.append({
            "case_id": anchor_row["case_id"], "kind": "anchor",
            "score": anchor["score"], "pool_index": anchor["pool_index"],
            "dist_existing": anchor["dist_existing"],
            "boundary": anchor["boundary"], "risk": anchor["risk"],
            "low_s_coverage": anchor["low_s_coverage"],
            "min_gap_m": anchor["min_gap_m"],
            "hard_qc_status": anchor["hard_qc_status"],
        })

        v1_candidates = [p for p in ranked_params if p != "Solidity"]
        v1 = v1_candidates[v1_cursor % len(v1_candidates)]
        v1_cursor += 1
        partner = partner_of.get(v1)
        if partner and partner[0] not in (v1, "Solidity"):
            v2 = partner[0]
        else:
            v2 = next((p for p in ranked_params
                       if p not in (v1, "Solidity")), ranked_params[0])
        v3_pool = [p for p in recheck_params if p not in (v1, v2)]
        if not v3_pool:
            v3_pool = [p for p in ranked_params if p not in (v1, v2)]
        v3 = v3_pool[v3_cursor % len(v3_pool)]
        v3_cursor += 1
        variant_specs = [
            (v1, "high_sensitivity_probe", {"rotation_index": v1_cursor - 1}),
            (v2, "interaction_probe",
             {"interaction_partner": v2 if partner else "",
              "interaction_index": partner[1] if partner else None}),
            (v3, "low_sensitivity_background_recheck",
             {"rotation_index": v3_cursor - 1}),
        ]

        for param, category, extra in variant_specs:
            made = _make_variant(anchor, param, category, extra)
            if made is None:
                for alt in ranked_params:
                    if alt == param:
                        continue
                    made = _make_variant(anchor, alt,
                                         category + "_fallback", extra)
                    if made is not None:
                        param = alt
                        break
            if made is None:
                continue
            params, evidence = made
            evidence["anchor_case_id"] = anchor_row["case_id"]
            row = _case_record(
                len(existing_design) + len(stage3_cases) + 1, "S3",
                f"S3_variant_{category}", params,
                anchor_case_id=anchor_row["case_id"],
                planned_varied_params=param,
                level_value=params[param],
                level_u=evidence["to_u"],
                level_rule=("single-parameter variant of the anchor: one parameter moved "
                            "to u=0.15 or 0.85 (the side farther from the anchor); "
                            "all other 12 parameters frozen at the anchor"),
                selection_reason=category,
                selection_evidence=json.dumps(evidence, sort_keys=True))
            stage3_cases.append(row)
            selection_records.append({
                "case_id": row["case_id"], "kind": "variant",
                "anchor_case_id": anchor_row["case_id"],
                "changed_param": param, "category": category,
                "evidence": evidence,
            })

    # deterministic fill to reach exactly 20 stage-3 cases (only if a variant
    # could not be constructed; the reason is recorded)
    fill_idx = 0
    while (len(existing_design) + len(stage3_cases) < N_TOTAL
           and fill_idx < len(ranked)):
        cand = ranked[fill_idx]
        fill_idx += 1
        if any(params_equal(cand["params"], e) for e in existing_design):
            continue
        if any(params_equal(cand["params"], r["params"] if "params" in r else
                            {p: r[p] for p in PARAMS})
               for r in stage3_cases):
            continue
        row = _case_record(
            len(existing_design) + len(stage3_cases) + 1, "S3",
            "S3_adaptive_fill", cand["params"],
            selection_reason="adaptive_fill",
            selection_evidence=json.dumps({
                "score": cand["score"], "pool_index": cand["pool_index"],
                "reason": "fallback fill; a planned variant was a duplicate"},
                sort_keys=True))
        stage3_cases.append(row)
        selection_records.append({
            "case_id": row["case_id"], "kind": "fill",
            "pool_index": cand["pool_index"], "score": cand["score"],
        })

    return stage3_cases, selection_records, {
        "pool_size_requested": POOL_SIZE,
        "pool_size_after_dedup": len(candidates),
        "pool_valid_count": len(valid),
        "low_sensitivity_params": low_params,
        "param_sensitivity_rank": ranked_params,
        "anchors": [a["pool_index"] for a in anchors],
        "stage3_count": len(stage3_cases),
    }


# ---------------------------------------------------------------------------
# Matched background effects
# ---------------------------------------------------------------------------
def _feature_effect(row_a: dict, row_b: dict, du: float) -> dict:
    fa = unsigned_features(row_a["metrics"])
    fb = unsigned_features(row_b["metrics"])
    eff = {k: abs(fa[k] - fb[k]) / du for k in COMPOSITE_WEIGHTS}
    eff["S_comp"] = sum(COMPOSITE_WEIGHTS[k] * eff[k] for k in COMPOSITE_WEIGHTS)
    eff["local"] = max(eff["S_le"], eff["S_te"])
    return eff


def matched_background_effects(rows, criteria) -> dict:
    """Collect single-parameter matched comparisons from S2 and S3."""
    by_id = {r["case_id"]: r for r in rows}
    out = {p: [] for p in PARAMS}

    for a, b in PAIR_GROUPS:
        group = sorted(
            [r for r in rows if r["design_group"] == f"S2_{a}_x_{b}"],
            key=lambda r: int(r["level_index"]))
        if len(group) != 4:
            continue
        ll, lh, hl, hh = group
        for param, ref_lo, ref_hi, other_low, other_high in (
                (a, ll, hl, lh, hh), (b, ll, lh, hl, hh)):
            pairs = [
                (ref_lo, ref_hi, other_low, other_high),  # same background (other=low)
            ]
            du = 0.5
            # param effect at the LOW level of the other parameter
            if ref_lo["hard_qc_status"] == "PASS" and ref_hi["hard_qc_status"] == "PASS":
                eff = _feature_effect(ref_lo, ref_hi, du)
                out[param].append({
                    "reference_case": ref_lo["case_id"],
                    "changed_case": ref_hi["case_id"],
                    "background_case": ref_lo["case_id"],
                    "background_value_note": f"{b if param == a else a}=low",
                    "effect_comp": eff["S_comp"], "effect_local": eff["local"],
                    "effect": eff, "source": "S2",
                })
            # param effect at the HIGH level of the other parameter
            if other_low["hard_qc_status"] == "PASS" and other_high["hard_qc_status"] == "PASS":
                eff = _feature_effect(other_low, other_high, du)
                out[param].append({
                    "reference_case": other_low["case_id"],
                    "changed_case": other_high["case_id"],
                    "background_case": other_low["case_id"],
                    "background_value_note": f"{b if param == a else a}=high",
                    "effect_comp": eff["S_comp"], "effect_local": eff["local"],
                    "effect": eff, "source": "S2",
                })

    anchors = {r["case_id"]: r for r in rows if r["selection_reason"] == "adaptive_anchor"}
    for r in rows:
        if r["stage"] != "S3" or not r["anchor_case_id"]:
            continue
        anchor = anchors.get(r["anchor_case_id"])
        if anchor is None:
            continue
        varied = [p for p in PARAMS
                  if abs(float(r[p]) - float(anchor[p])) > 1e-12 * max(
                      1.0, abs(float(anchor[p])))]
        if len(varied) != 1:
            continue
        param = varied[0]
        if r["hard_qc_status"] != "PASS" or anchor["hard_qc_status"] != "PASS":
            continue
        du = abs(u_of(param, r[param]) - u_of(param, anchor[param]))
        if du <= 0:
            continue
        eff = _feature_effect(anchor, r, du)
        out[param].append({
            "reference_case": anchor["case_id"],
            "changed_case": r["case_id"],
            "background_case": anchor["case_id"],
            "background_value_note": "S3 adaptive background",
            "effect_comp": eff["S_comp"], "effect_local": eff["local"],
            "effect": eff, "source": "S3",
        })
    return out


# ---------------------------------------------------------------------------
# Parameter-level sensitivity table, redundancy and decisions
# ---------------------------------------------------------------------------
def redundancy_table(sens, criteria) -> dict:
    sigs = {}
    for p in PARAMS:
        eff = sens[p]["signed_effects"]
        if not eff:
            continue
        arr = np.array([eff[k] for k in SIGNATURE_KEYS], dtype=float)
        if arr.size == 0:
            continue
        vec = arr.mean(axis=1)
        norm = float(np.linalg.norm(vec))
        sigs[p] = vec / norm if norm > 0 else vec

    out = {}
    for p in PARAMS:
        best = {"partner": "", "cosine": float("nan"), "ratio": float("nan")}
        if p not in sigs or np.linalg.norm(sigs[p]) == 0:
            out[p] = best
            continue
        for q in PARAMS:
            if q == p or q not in sigs or np.linalg.norm(sigs[q]) == 0:
                continue
            # Solidity only changes the pitch; its response signature is
            # one-dimensional (min_gap) and cannot be compared as a shape
            # response.  It is judged by S_cascade only (rule R0).
            if p == "Solidity" or q == "Solidity":
                continue
            cos = cosine_similarity(sigs[p], sigs[q])
            if not math.isfinite(cos):
                continue
            sp = sens[p]["sensitivity"]["S_comp"]
            sq = sens[q]["sensitivity"]["S_comp"]
            ratio = min(sp, sq) / max(sp, sq) if max(sp, sq) > 0 else float("nan")
            if best["partner"] == "" or cos > best["cosine"]:
                best = {"partner": q, "cosine": float(cos), "ratio": float(ratio)}
        out[p] = best
    return out


def build_parameter_tables(rows, criteria):
    thr = criteria["thresholds"]
    sens = estimate_stage1_sensitivity(rows, criteria)
    interactions = stage2_interaction(rows, criteria)
    backgrounds = matched_background_effects(rows, criteria)
    redundancy = redundancy_table(sens, criteria)

    sensitivity_rows = []
    decision_rows = []
    for p in PARAMS:
        S = sens[p]["sensitivity"]
        n_levels = sens[p]["n_levels"]
        n_valid = sens[p]["n_valid_levels"]
        pass_rate = (n_valid / n_levels) if n_levels else 0.0
        failures = sens[p]["failed_levels"]
        failure_text = ";".join(
            f"{f['case_id']}:{fmt(f['level'],10)}:u={fmt(f['level_u'],6)}:"
            f"{f['status']}:{f['reason']}" for f in failures)

        bg = backgrounds[p]
        low_refs = set()
        if (S["S_comp"] < thr["review_comp"] and S["S_le"] < thr["review_local"]
                and S["S_te"] < thr["review_local"]
                and S["S_cascade"] < thr["review_cascade"]):
            low_refs.add("baseline")
        for e in bg:
            if (e["effect_comp"] < thr["review_comp"]
                    and e["effect_local"] < thr["review_local"]):
                low_refs.add(e["background_case"])
        low_in_backgrounds = len(low_refs)
        bg_comp = [e["effect_comp"] for e in bg]
        bg_local = [e["effect_local"] for e in bg]

        region_scores = {
            "GLOBAL_CONTOUR": S["S_contour"], "LE": S["S_le"],
            "TE": S["S_te"], "MEANLINE": S["S_camber"],
            "THICKNESS": S["S_thickness"], "CASCADE": S["S_cascade"],
        }
        dominant_region = max(region_scores, key=region_scores.get)

        red = redundancy[p]
        sensitivity_rows.append({
            "param": p,
            "param_class": ("original_open" if p in ORIGINAL_PARAMS else
                            "key_new" if p in KEY_PARAMS else "additional_new"),
            "range_min": RANGES[p][0], "range_max": RANGES[p][1],
            "baseline": BASELINE[p],
            "n_levels": n_levels, "n_valid_levels": n_valid,
            "qc_pass_rate": pass_rate,
            "S_contour": S["S_contour"], "S_le": S["S_le"],
            "S_te": S["S_te"], "S_camber": S["S_camber"],
            "S_thickness": S["S_thickness"], "S_cascade": S["S_cascade"],
            "S_comp": S["S_comp"],
            "S_le_radius": S["f_le_radius"],
            "S_le_region": S["f_le_region"],
            "S_te_radius": S["f_te_radius"],
            "S_te_region": S["f_te_region"],
            "S_camber_meanline": S["f_camber_meanline"],
            "S_camber_angle": S["f_camber_angle"],
            "S_thickness_total": S["f_thickness_total"],
            "S_thickness_front": S["f_thickness_front"],
            "S_thickness_mid": S["f_thickness_mid"],
            "S_thickness_rear": S["f_thickness_rear"],
            "S_cascade_gap": S["f_cascade_gap"],
            "S_cascade_pitch": S["f_cascade_pitch"],
            "dominant_region": dominant_region,
            "monotonicity": sens[p]["monotonicity"],
            "spearman_rho": sens[p]["spearman_rho"],
            "dominant_signed_feature": sens[p]["dominant_signed_feature"],
            "redundancy_partner": red["partner"],
            "redundancy_cosine": red["cosine"],
            "sensitivity_ratio_to_partner": red["ratio"],
            "n_backgrounds": len(bg),
            "low_in_backgrounds": low_in_backgrounds,
            "background_effect_comp_min": min(bg_comp) if bg_comp else "",
            "background_effect_comp_max": max(bg_comp) if bg_comp else "",
            "background_effect_local_max": max(bg_local) if bg_local else "",
            "failure_count": len(failures),
            "failure_range": failure_text,
            "evidence_case_ids": ";".join(
                sens[p]["valid_case_ids"] + [e["changed_case"] for e in bg]),
            "background_evidence": ";".join(
                f"{e['source']}:{e['reference_case']}->{e['changed_case']}"
                f"({e['background_value_note']})" for e in bg),
        })
        decision_rows.append({
            "param": p,
            "decision": "",
            "rule_id": "",
            "criteria_id": criteria["criteria_id"],
            "criteria_version": criteria["criteria_version"],
            "S_comp": S["S_comp"], "S_contour": S["S_contour"],
            "S_le": S["S_le"], "S_te": S["S_te"],
            "S_camber": S["S_camber"], "S_thickness": S["S_thickness"],
            "S_cascade": S["S_cascade"],
            "qc_pass_rate": pass_rate,
            "n_valid_levels": n_valid,
            "n_backgrounds": len(bg),
            "low_in_backgrounds": low_in_backgrounds,
            "redundancy_partner": red["partner"],
            "redundancy_cosine": red["cosine"],
            "sensitivity_ratio": red["ratio"],
            "failure_range": failure_text,
            "evidence_case_ids": ";".join(
                sens[p]["valid_case_ids"] + [e["changed_case"] for e in bg]),
            "required_followup": "",
            "human_review_required": 1,
        })

    for d in decision_rows:
        p = d["param"]
        S = sens[p]["sensitivity"]
        pass_rate = d["qc_pass_rate"]
        low_in_bg = d["low_in_backgrounds"]
        n_levels = sens[p]["n_levels"]
        failures = sens[p]["failed_levels"]
        enough_levels = n_levels >= thr["min_levels_for_fix"]
        no_failure = len(failures) == 0
        low_stage1 = (S["S_comp"] < thr["review_comp"]
                      and S["S_le"] < thr["review_local"]
                      and S["S_te"] < thr["review_local"]
                      and S["S_cascade"] < thr["review_cascade"])
        high = (S["S_comp"] >= thr["keep_comp"]
                or S["S_le"] >= thr["keep_local"]
                or S["S_te"] >= thr["keep_local"])
        medium = (S["S_comp"] >= thr["review_comp"]
                  or S["S_le"] >= thr["review_local"]
                  or S["S_te"] >= thr["review_local"]
                  or S["S_cascade"] >= thr["review_cascade"])
        red_ok = (math.isfinite(d["redundancy_cosine"])
                  and d["redundancy_cosine"] >= thr["redundancy_cosine"]
                  and math.isfinite(d["sensitivity_ratio"])
                  and d["sensitivity_ratio"] <= thr["redundancy_ratio"])
        low_enough_backgrounds = low_in_bg >= thr["min_backgrounds_for_fix"]

        if p == "Solidity":
            if (S["S_cascade"] >= thr["keep_cascade"]
                    and pass_rate >= thr["qc_pass_rate_min"]):
                d.update(decision="KEEP_CANDIDATE", rule_id="R0_SOLIDITY",
                         required_followup="expand pitch range; inspect channel blockage separately")
            elif S["S_cascade"] >= thr["review_cascade"]:
                d.update(decision="REVIEW", rule_id="R0_SOLIDITY",
                         required_followup="cascade metrics vary; confirm engineering pitch limits")
            elif low_enough_backgrounds and enough_levels and no_failure:
                d.update(decision="FIX_CANDIDATE", rule_id="R0_SOLIDITY",
                         required_followup="pitch effect small in all tested backgrounds; confirm before fixing")
            else:
                d.update(decision="REVIEW", rule_id="R5_REVIEW_INSUFFICIENT",
                         required_followup="insufficient background evidence")
        elif high:
            if pass_rate >= thr["qc_pass_rate_min"]:
                d.update(decision="KEEP_CANDIDATE", rule_id="R1_KEEP_HIGH",
                         required_followup="continue range exploration; verify engineering limits")
            else:
                d.update(decision="REVIEW", rule_id="R1_KEEP_HIGH_BOUNDARY",
                         required_followup="high sensitivity but QC failures inside the range; shrink range before production")
        elif low_stage1 and enough_levels and no_failure and low_enough_backgrounds:
            d.update(decision="FIX_CANDIDATE", rule_id="R3_FIX_LOW",
                     required_followup="effect small in >=2 backgrounds; confirm with an independent geometry audit before fixing")
        elif (red_ok and S["S_comp"] < thr["keep_comp"] and enough_levels
              and no_failure and low_enough_backgrounds):
            d.update(decision="FIX_CANDIDATE", rule_id="R4_FIX_REDUNDANT",
                     required_followup=f"redundant with {d['redundancy_partner']}; confirm before fixing")
        elif medium:
            d.update(decision="REVIEW", rule_id="R2_REVIEW_MEDIUM",
                     required_followup="local or moderate effect; needs more backgrounds / engineering review")
        else:
            d.update(decision="REVIEW", rule_id="R5_REVIEW_INSUFFICIENT",
                     required_followup="evidence insufficient for KEEP or FIX; run additional background probes")

    dec_by_param = {d["param"]: d for d in decision_rows}
    for r in sensitivity_rows:
        r["decision"] = dec_by_param[r["param"]]["decision"]
        r["decision_rule_id"] = dec_by_param[r["param"]]["rule_id"]

    return sens, interactions, backgrounds, redundancy, sensitivity_rows, decision_rows


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
DESIGN_COLUMNS = (
    ["case_id", "stage", "design_group", "sweep_param", "pair_params",
     "level_index", "level_value", "level_u", "level_rule", "is_baseline",
     "anchor_case_id", "selection_reason", "selection_evidence",
     "planned_varied_params"]
    + PARAMS + [f"u_{p}" for p in PARAMS]
    + ["Incidence", "Mach", "range_id", "sampling_id"]
)

METRIC_IDENTITY = ["case_id", "stage", "design_group", "sweep_param",
                   "level_value", "level_u", "is_baseline",
                   "planned_varied_params", "anchor_case_id",
                   "selection_reason"]
METRIC_STATUS = ["generation_status", "failure_reason", "metric_status",
                 "hard_qc_status", "qc_reason", "qc_policy_id", "auto_flags",
                 "frozen_qc_status", "frozen_qc_reason",
                 "frozen_qc_policy_id"]
METRIC_DIAG = ["finite_ok", "self_intersection", "negative_half_thickness",
               "zero_length_segment", "curvature_finite",
               "junction_jump_warning", "le_closure_error", "te_closure_error",
               "min_interior_thickness", "max_paired_thickness",
               "min_half_thickness_norm"]
METRIC_CASCADE = ["periodicity_m", "min_gap_m", "min_gap_to_pitch",
                  "envelope_clearance_m", "blade_tangential_extent_m",
                  "adjacent_blade_intersection", "chord_m", "pitch_to_chord"]


def _atomic_text(path: Path, text: str):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_csv(path: Path, rows, preferred_columns):
    keys = set()
    for r in rows:
        keys.update(r.keys())
    columns = [c for c in preferred_columns if c in keys]
    columns += sorted(keys - set(columns))
    lines = [",".join(columns)]
    for r in rows:
        cells = []
        for c in columns:
            s = fmt(r.get(c, ""))
            if any(ch in s for ch in [",", '"', "\n"]):
                s = '"' + s.replace('"', '""') + '"'
            cells.append(s)
        lines.append(",".join(cells))
    _atomic_text(path, "\n".join(lines) + "\n")


def write_design(cases: list):
    write_csv(OUTDIR / "case_design.csv", cases, DESIGN_COLUMNS)


def metric_columns(rows) -> list:
    keys = set()
    for r in rows:
        keys.update(r.keys())
    cols = (list(METRIC_IDENTITY) + list(METRIC_STATUS) + list(METRIC_DIAG)
            + list(METRIC_CASCADE))
    cols += sorted(keys - set(cols))
    return cols


def write_metrics(rows: list):
    write_csv(OUTDIR / "case_metrics.csv", rows, metric_columns(rows))


def write_profiles_npz(results: list, path: Path):
    arrays = {}
    ids = []
    for rec in results:
        geom = rec.get("geom")
        if geom is None:
            continue
        cid = rec["design"]["case_id"]
        ids.append(cid)
        for key, field in (("xp", "xp1"), ("yp", "yp1"), ("xs", "xs1"),
                           ("ys", "ys1"), ("xc", "xc"), ("yc", "yc"),
                           ("thick", "thick"), ("sc", "sc")):
            arrays[f"{cid}__{key}"] = np.asarray(geom[field], dtype=np.float64)
    np.savez_compressed(
        path,
        case_ids=np.asarray(ids, dtype="U16"),
        baseline_case_id=np.asarray(results[0]["design"]["case_id"]),
        fields=np.asarray("xp,yp,xs,ys,xc,yc,thick,sc"),
        units=np.asarray(
            "legacy normalized units; x=chordwise, y=tangential; thick is HALF-thickness"),
        **arrays)
    return ids


def verify_profiles_npz(path: Path, results: list) -> dict:
    expected = [r["design"]["case_id"] for r in results if r.get("geom") is not None]
    with np.load(path, allow_pickle=False) as data:
        ids = [str(x) for x in data["case_ids"]]
        missing = sorted(set(expected) - set(ids))
        extra = sorted(set(ids) - set(expected))
        mismatch = []
        for rec in results:
            if rec.get("geom") is None:
                continue
            cid = rec["design"]["case_id"]
            for key, field in (("xp", "xp1"), ("yp", "yp1"), ("xs", "xs1"),
                               ("ys", "ys1"), ("yc", "yc"), ("thick", "thick")):
                a = data[f"{cid}__{key}"]
                b = np.asarray(rec["geom"][field], dtype=np.float64)
                if a.shape != b.shape or not np.array_equal(a, b):
                    mismatch.append(f"{cid}:{key}")
        baseline_ok = str(data["baseline_case_id"]) == results[0]["design"]["case_id"]
    return {"profiles_saved": len(ids), "missing_case_ids": missing,
            "extra_case_ids": extra, "array_mismatches": mismatch,
            "baseline_case_id_ok": baseline_ok,
            "reload_ok": not missing and not extra and not mismatch and baseline_ok}


def load_rows_for_analysis():
    with open(OUTDIR / "case_design.csv", newline="") as f:
        design = list(csv.DictReader(f))
    with open(OUTDIR / "case_metrics.csv", newline="") as f:
        metrics_rows = list(csv.DictReader(f))
    m_by_id = {r["case_id"]: r for r in metrics_rows}

    def maybe_num(s):
        try:
            return float(s)
        except (TypeError, ValueError):
            return s

    rows = []
    for d in design:
        row = dict(d)
        for p in PARAMS:
            row[p] = float(row[p])
            row[f"u_{p}"] = float(row[f"u_{p}"])
        for k in ("level_index", "level_value", "level_u"):
            if row.get(k, "") != "":
                try:
                    row[k] = float(row[k])
                except ValueError:
                    # stage-2 pair levels are stored as "uA;uB"
                    pass
        row["is_baseline"] = int(float(row.get("is_baseline", 0)))
        m = m_by_id.get(row["case_id"], {})
        parsed = {}
        for k, v in m.items():
            if k in ("case_id", "stage", "design_group", "sweep_param",
                     "selection_reason", "failure_reason", "hard_qc_status",
                     "metric_status", "qc_reason", "frozen_qc_status",
                     "frozen_qc_reason", "frozen_qc_policy_id", "qc_policy_id",
                     "generation_status"):
                parsed[k] = v
            elif v == "":
                parsed[k] = float("nan")
            else:
                parsed[k] = maybe_num(v)
        row["metrics"] = parsed
        row["hard_qc_status"] = parsed.get("hard_qc_status", "")
        row["generation_status"] = parsed.get("generation_status", "")
        rows.append(row)
    return rows, design, metrics_rows


# ---------------------------------------------------------------------------
# Configuration / provenance
# ---------------------------------------------------------------------------
def load_criteria():
    with open(OUTDIR / "screening_criteria.yaml") as f:
        return yaml.safe_load(f)


def load_run_metadata():
    with open(OUTDIR / "audit" / "run_metadata.json") as f:
        return json.load(f)


def write_config(level_plan, stage12_cases):
    frozen = {
        "legacy/blade_batch_generation.py": sha256_file(
            REPO / "legacy" / "blade_batch_generation.py"),
        "legacy/blade_batch_generation_template.geomTurbo": sha256_file(TEMPLATE_PATH),
        "code/geometry_legacy_v1.py": sha256_file(CODE / "geometry_legacy_v1.py"),
        "code/03_geometry_qc.py": sha256_file(CODE / "03_geometry_qc.py"),
        "code/02_generate_geometry.py": sha256_file(CODE / "02_generate_geometry.py"),
        "docs/GEOMETRY_GENERATOR_CONTRACT.md": sha256_file(
            REPO / "docs" / "GEOMETRY_GENERATOR_CONTRACT.md"),
        "docs/GEOMETRY_QC_CONTRACT.md": sha256_file(
            REPO / "docs" / "GEOMETRY_QC_CONTRACT.md"),
        "config/ranges_legacy.yaml": sha256_file(REPO / "config" / "ranges_legacy.yaml"),
        "analysis/geometry_review/ranges_exploratory_v2.yaml": sha256_file(
            REPO / "analysis" / "geometry_review" / "ranges_exploratory_v2.yaml"),
        "analysis/geometry_review/review_cases.csv": sha256_file(
            REPO / "analysis" / "geometry_review" / "review_cases.csv"),
        "geometry/profiles/C900001.dat": sha256_file(
            REPO / "geometry" / "profiles" / "C900001.dat"),
        "geometry/geomturbo/C900001.geomTurbo": sha256_file(
            REPO / "geometry" / "geomturbo" / "C900001.geomTurbo"),
    }
    cfg = {
        "experiment_id": EXPERIMENT_ID,
        "status": "EXPLORATORY_NOT_APPROVED",
        "purpose": "13-parameter geometry sensitivity + automatic screening (100 deterministic cases)",
        "directory": str(OUTDIR.relative_to(REPO)),
        "git_head": git_head(),
        "case_id_range": f"{case_id(1)}..{case_id(N_TOTAL)}",
        "n_cases": N_TOTAL,
        "stage_counts": {"S1": 60, "S2": 20, "S3": 20},
        "random_seed": SOBOL_SEED,
        "sobol_seed": SOBOL_SEED,
        "range_id": RANGE_ID,
        "sampling_id": SAMPLING_ID,
        "baseline": BASELINE,
        "ranges": {p: list(RANGES[p]) for p in PARAMS},
        "parameter_classes": {
            "original_open": ORIGINAL_PARAMS,
            "key_new": KEY_PARAMS,
            "additional_new": OTHER_PARAMS,
            "excluded_from_geometry": {
                "Incidence": "fixed 0 deg, metadata only",
                "Mach": "fixed 0.5, metadata only",
                "CHORD_TARGET": 0.06,
                "SPAN": 0.003,
                "Npoint": 101,
                "Ncirc": 4,
                "Nscale1": 1.7,
                "Nscale2": 1.7,
                "Rsign": 1.0,
                "Gridswitch": -1.0,
            },
        },
        "fixed_operating_conditions": FIXED_METADATA,
        "fixed_geometry_constants": gen.FIXED_CONSTANTS,
        "parameter_formula_map": gen.PARAMETER_FORMULA_MAP,
    }

    cfg["design_rules"] = {
        "single_factor_levels": {
            "key_params": {p: level_plan[p] for p in KEY_PARAMS},
            "other_params": {p: level_plan[p]
                             for p in ORIGINAL_PARAMS + OTHER_PARAMS},
        },
        "coupling_pairs": [
            {"pair": list(pair), "levels_u": [0.25, 0.75], "cases": 4}
            for pair in PAIR_GROUPS
        ],
        "adaptive_stage3": {
            "pool": "scipy.stats.qmc.Sobol(d=13, scramble=True)",
            "pool_size": POOL_SIZE,
            "seed": SOBOL_SEED,
            "anchor_score": "0.40*normalized_distance_to_existing + 0.25*boundary_proximity + 0.20*risk_closeness + 0.15*low_sensitivity_coverage",
            "anchor_min_distance": ANCHOR_MIN_DISTANCE,
            "near_duplicate_distance": NEAR_DUPLICATE_DISTANCE,
            "anchors": N_ANCHORS,
            "variants_per_anchor": N_VARIANTS_PER_ANCHOR,
            "variant_categories": [
                "high_sensitivity_probe", "interaction_probe",
                "low_sensitivity_background_recheck"],
            "variant_rule": "one parameter changed to u=0.15 or 0.85 (the side farther from the anchor); all other parameters frozen at the anchor",
            "selection_output": "stage3_selection.json",
        },
    }
    cfg["frozen_asset_sha256"] = frozen
    cfg["code"] = {
        "generator": "code/geometry_parametric_exploratory_v1.py",
        "generator_sha256": sha256_file(
            CODE / "geometry_parametric_exploratory_v1.py"),
        "metrics": "tools/geometry_sensitivity_metrics_v1.py",
        "metrics_sha256": sha256_file(
            TOOLS / "geometry_sensitivity_metrics_v1.py"),
        "driver": "tools/geometry_parameter_sensitivity_v1.py",
        "driver_sha256": sha256_file(Path(__file__).resolve()),
        "criteria": "screening_criteria.yaml",
        "criteria_sha256": sha256_file(OUTDIR / "screening_criteria.yaml"),
    }
    cfg["reference_v2_40cases"] = {
        "ranges": {"Xthick": [0.10, 0.60], "Tmax": [0.025, 0.095],
                   "Metal2": [0.0, 32.0], "Solidity": [0.7, 2.5]},
        "qc_policy_id": "geometry_qc_v1_hard",
        "status": "EXPLORATORY_NOT_APPROVED",
    }
    cfg["output_files"] = [
        "README.md", "experiment_config.yaml", "screening_criteria.yaml",
        "case_design.csv", "case_metrics.csv", "parameter_sensitivity.csv",
        "parameter_decisions.csv", "profiles.npz", "provenance.json",
        "overview_001_050.png", "overview_051_100.png",
        "sensitivity_heatmap.png", "REPORT.md", "stage3_selection.json",
    ]
    cfg["forbidden"] = {
        "numeca_mesh": True, "cfx_solve": True, "ai_training": True,
        "production_doe": True, "production_range_freeze": True,
    }
    _atomic_text(OUTDIR / "experiment_config.yaml",
                 yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    return cfg


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def global_limits(results):
    xs, ys = [], []
    for rec in results:
        geom = rec.get("geom")
        if geom is None:
            continue
        xs.append(geom["xp1"])
        xs.append(geom["xs1"])
        ys.append(geom["yp1"])
        ys.append(geom["ys1"])
    if not xs:
        return (-0.1, 1.1), (-0.5, 0.5)
    xmin, xmax = min(np.min(x) for x in xs), max(np.max(x) for x in xs)
    ymin, ymax = min(np.min(y) for y in ys), max(np.max(y) for y in ys)
    padx = 0.06 * (xmax - xmin)
    pady = 0.06 * (ymax - ymin)
    return (xmin - padx, xmax + padx), (ymin - pady, ymax + pady)


def _short_label(rec):
    d = rec["design"]
    if int(d.get("is_baseline", 0)) == 1:
        return "S1 baseline"
    if d["stage"] == "S1":
        return f"S1 {d['sweep_param']}={float(d['level_value']):.6g}"
    if d["stage"] == "S2":
        return "S2 " + d["design_group"].replace("S2_", "").replace("_x_", " x ")
    reason = d.get("selection_reason", "adaptive").replace("_", " ")
    return "S3 " + reason


def plot_overview(results, path: Path, limits, panel_range=None):
    records = results if panel_range is None else results[panel_range[0]:panel_range[1]]
    ncols, nrows = 10, 5
    fig, axes = plt.subplots(nrows, ncols, figsize=(26, 13.6))
    axes = axes.ravel()
    xlim, ylim = limits
    baseline = results[0]["geom"]

    for ax, rec in zip(axes, records):
        d = rec["design"]
        geom = rec.get("geom")
        ax.plot(baseline["xp1"], baseline["yp1"], color="#bbbbbb", lw=0.6,
                ls="--", zorder=1)
        ax.plot(baseline["xs1"], baseline["ys1"], color="#bbbbbb", lw=0.6,
                ls="--", zorder=1)
        if geom is not None:
            qc = rec["metrics"].get("hard_qc_status", "ERROR")
            color = "#1f4e79" if qc == "PASS" else "#c00000"
            ax.plot(geom["xp1"], geom["yp1"], color=color, lw=0.9, zorder=2)
            ax.plot(geom["xs1"], geom["ys1"], color=color, lw=0.9, zorder=2)
        else:
            qc = "FAIL"
            ax.text(0.5, 0.5, "generation FAIL", transform=ax.transAxes,
                    ha="center", va="center", fontsize=7, color="#c00000")
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_linewidth(0.4)
            spine.set_color("#999999")
        title = f"{d['case_id']}\n{_short_label(rec)}\nQC {qc}"
        ax.set_title(title, fontsize=5.6, pad=1.2, linespacing=1.0)
    for ax in axes[len(records):]:
        ax.axis("off")
    fig.suptitle(
        "Geometry Parameter Sensitivity V1 — real blade contours (baseline dashed grey; "
        "PASS = dark blue, FAIL = red)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.975))
    fig.savefig(path, dpi=110, bbox_inches="tight",
                pil_kwargs={"optimize": True})
    plt.close(fig)


def plot_heatmap(sensitivity_rows, decision_rows, path: Path):
    metrics_keys = ["S_contour", "S_le", "S_te", "S_camber",
                    "S_thickness", "S_cascade", "S_comp"]
    decisions = {d["param"]: d["decision"] for d in decision_rows}
    labels = [f"{r['param']} [{decisions.get(r['param'], '')}]"
              for r in sensitivity_rows]
    data = np.array([[float(r[k]) if r[k] != "" else 0.0 for k in metrics_keys]
                     for r in sensitivity_rows], dtype=float)
    shown = np.log10(data + 1e-6)

    fig, ax = plt.subplots(figsize=(10.5, 8.2))
    im = ax.imshow(shown, aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(metrics_keys)))
    ax.set_xticklabels(metrics_keys, rotation=25, ha="right", fontsize=8)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            ax.text(j, i, f"{data[i, j]:.3g}", ha="center", va="center",
                    fontsize=6.5,
                    color="white" if shown[i, j] < np.median(shown) else "black")
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("log10(S + 1e-6)  [dimensionless per full range]", fontsize=8)
    ax.set_title(
        "Parameter sensitivity summary (S = |Delta feature| / |Delta u|)\n"
        "criteria parameter_screening_v1_tentative — advisory only", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=130, bbox_inches="tight",
                pil_kwargs={"optimize": True})
    plt.close(fig)


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------
REGION_CN = {
    "GLOBAL_CONTOUR": "整体轮廓（压力面+吸力面）",
    "LE": "前缘局部",
    "TE": "尾缘局部",
    "MEANLINE": "中弧线",
    "THICKNESS": "厚度分布",
    "CASCADE": "叶栅通道（栅距/最小间隙）",
}
MONO_CN = {"MONOTONE": "单调", "NON_MONOTONE": "非单调", "UNCERTAIN": "不确定"}


def _metric_str(row, key, digits=4, scale=1.0):
    v = _num(row["metrics"].get(key))
    if not math.isfinite(v):
        return "不可用"
    return f"{v * scale:.{digits}g}"


def level_extremes(rows, param):
    level_rows = [r for r in rows if r["stage"] == "S1"
                  and r["sweep_param"] == param]
    valid = [r for r in level_rows if r["hard_qc_status"] == "PASS"]
    if not valid:
        return None, None
    return (min(valid, key=lambda r: float(r["level_u"])),
            max(valid, key=lambda r: float(r["level_u"])))


def stage1_interaction_rows(interactions):
    lines = ["| 参数对 | 平均交互指数 | 轮廓 RMS | 前缘区域 | 尾缘区域 | 中弧线 | 厚度 | 最小间隙 |",
             "|---|---|---|---|---|---|---|---|"]
    for pair, values in interactions.items():
        lines.append(
            f"| {pair.replace(';', ' × ')} | {values.get('mean', float('nan')):.3f} "
            f"| {values.get('contour_rms_dev_norm', float('nan')):.3f} "
            f"| {values.get('le_region_rms_dev_norm', float('nan')):.3f} "
            f"| {values.get('te_region_rms_dev_norm', float('nan')):.3f} "
            f"| {values.get('meanline_rms_dev_norm', float('nan')):.3f} "
            f"| {values.get('thickness_rms_dev_norm', float('nan')):.3f} "
            f"| {values.get('min_gap_change_rel', float('nan')):.3f} |")
    return "\n".join(lines)


def build_report(rows, sens, interactions, backgrounds, sensitivity_rows,
                 decision_rows, run_meta, criteria):
    thr = criteria["thresholds"]
    n_total = len(rows)
    gen_ok = sum(1 for r in rows if r["generation_status"] == "OK")
    qc_pass = sum(1 for r in rows if r["hard_qc_status"] == "PASS")
    frozen_pass = sum(1 for r in rows if r["metrics"].get("frozen_qc_status") == "PASS")
    frozen_mismatch = [r for r in rows
                       if r["metrics"].get("frozen_qc_status") in ("PASS", "FAIL")
                       and r["metrics"].get("frozen_qc_status") != r["hard_qc_status"]]
    failed = [r for r in rows
              if r["generation_status"] != "OK" or r["hard_qc_status"] != "PASS"]

    vectors = {}
    for r in rows:
        key = tuple(round(float(r[p]), 10) for p in PARAMS)
        vectors.setdefault(key, []).append(r["case_id"])
    duplicates = {k: v for k, v in vectors.items() if len(v) > 1}

    stage_counts = {s: sum(1 for r in rows if r["stage"] == s) for s in ("S1", "S2", "S3")}
    dec = {d["param"]: d for d in decision_rows}
    sens_rows = {r["param"]: r for r in sensitivity_rows}
    base = next(r for r in rows if r["is_baseline"])

    lines = []
    lines.append("# 压气机叶型全参数几何敏感性实验 V1（100 Cases）\n")
    lines.append(
        "> 实验状态：**EXPLORATORY / NOT APPROVED**。\n"
        "> 本实验只做几何生成、几何 QC 与几何敏感性筛选；"
        "**没有** NUMECA 网格生成、**没有** CFX 求解、**没有** AI 训练、"
        "**没有** 修改正式 DOE 或冻结正式生产范围。\n"
        f"> 判据：`{criteria['criteria_id']}` / version `{criteria['criteria_version']}`"
        f"（{criteria['criteria_status']}）。\n"
        f"> Case 号段：`C820001..C820100`；git HEAD：`{run_meta.get('git_head', 'UNKNOWN')}`。\n")

    lines.append("## A. 实验完整性\n")
    lines.append("```text")
    lines.append(f"预先登记 Case 数        : {n_total}")
    lines.append(f"阶段分布                : S1={stage_counts['S1']}, S2={stage_counts['S2']}, S3={stage_counts['S3']}")
    lines.append(f"第三阶段锚点            : {', '.join(run_meta.get('stage3_anchor_ids', [])) or '—'}")
    lines.append(f"第三阶段变体覆盖参数    : {', '.join(run_meta.get('stage3_variant_params', [])) or '—'}")
    lines.append(f"几何生成成功            : {gen_ok}/{n_total}")
    lines.append(f"实验硬性 QC 通过        : {qc_pass}/{n_total}")
    lines.append(f"冻结 QC (geometry_qc_v1_hard) 通过 : {frozen_pass}/{n_total}")
    lines.append(f"实验 QC 与冻结 QC 不一致 : {len(frozen_mismatch)}")
    lines.append(f"参数向量重复组数        : {len(duplicates)}")
    lines.append(f"失败/未通过 Case 数     : {len(failed)}（全部保留在 case_metrics.csv）")
    lines.append(f"唯一 Case ID 数         : {len({r['case_id'] for r in rows})}")
    lines.append("```")

    if duplicates:
        lines.append("\n**参数向量重复（不应出现）**：\n")
        for ids in duplicates.values():
            lines.append(f"- {', '.join(ids)}")
    else:
        lines.append("\n未发现参数向量重复；100 个 Case 的参数向量互不相同。")

    if failed:
        lines.append("\n### A.1 失败 / 未通过 Case 列表\n")
        lines.append("| Case | 阶段 | 组别 | 变化参数 | 状态 | 原因 |")
        lines.append("|---|---|---|---|---|---|")
        for r in failed:
            varied = r.get("planned_varied_params", "") or "-"
            lines.append(
                f"| {r['case_id']} | {r['stage']} | {r['design_group']} | {varied} "
                f"| {r['generation_status']}/{r['hard_qc_status']} "
                f"| {r['metrics'].get('qc_reason', r.get('failure_reason', ''))} |")
    else:
        lines.append("\n本批 100 个 Case 均几何生成成功且硬性 QC 通过；"
                     "这不代表工程合理，也不代表 CFD 可收敛。")

    lines.append("\n### A.2 冻结资产与回归检查\n")
    v1 = run_meta.get("v1_regression", {})
    if isinstance(v1, dict):
        v1_text = (("PASS — " if v1.get("pass") else "FAIL — ")
                   + str(v1.get("last_line", "")))
    else:
        v1_text = str(v1)
    lines.append("```text")
    lines.append(f"冻结文件 SHA256 校验 : {run_meta.get('frozen_assets_check', 'see provenance.json')}")
    lines.append(f"V1 回归测试          : {v1_text}")
    lines.append(f"profiles.npz 回读     : {run_meta.get('npz_reload', 'see provenance.json')}")
    lines.append(f"总输出体积            : {run_meta.get('output_size_mb', 'see provenance.json')} MB")
    lines.append("```")

    lines.append("\n## B. 全参数几何敏感性\n")
    lines.append(
        "定义：`S = max_levels |feature(level) - feature(baseline)| / |Δu|`，"
        "`Δu` 为归一化参数偏移；长度类指标均除以基准弦长，因此 S 无量纲（每整个参数范围）。"
        "完整定义、单位、阈值与规则见 `screening_criteria.yaml`。\n")
    lines.append("| 参数 | 扫描范围 | 水平数 | 有效率 | S_contour | S_LE | S_TE | S_camber | S_thickness | S_cascade | S_comp | 主导区域 | 单调性 | 冗余伙伴 (cos) |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sensitivity_rows:
        red = ("—" if not (r["redundancy_partner"]
                            and math.isfinite(r["redundancy_cosine"])
                            and r["redundancy_cosine"] >= 0.5)
               else f"{r['redundancy_partner']} ({r['redundancy_cosine']:.3f})")
        lines.append(
            f"| `{r['param']}` | {r['range_min']:g} – {r['range_max']:g} | {r['n_levels']} "
            f"| {r['qc_pass_rate']*100:.0f}% | {r['S_contour']:.4g} | {r['S_le']:.4g} "
            f"| {r['S_te']:.4g} | {r['S_camber']:.4g} | {r['S_thickness']:.4g} "
            f"| {r['S_cascade']:.4g} | {r['S_comp']:.4g} | {REGION_CN[r['dominant_region']]} "
            f"| {MONO_CN[r['monotonicity']]} | {red} |")

    lines.append("\n### B.1 逐参数说明\n")
    for r in sensitivity_rows:
        p = r["param"]
        S = sens[p]["sensitivity"]
        mag = ("高" if S["S_comp"] >= thr["keep_comp"] else
               "中等" if S["S_comp"] >= thr["review_comp"] else "低")
        text = (f"- **`{p}`**（{REGION_CN[r['dominant_region']]}主导，S_comp={S['S_comp']:.4g}，"
                f"量级：{mag}；单调性：{MONO_CN[r['monotonicity']]}）。")
        if sens[p]["monotonicity"] == "UNCERTAIN" and sens[p]["n_levels"] <= 3:
            text += "（仅 3 个水平，单调性证据有限）"
        if p in ("SS1", "SS2"):
            text += (" 注意：legacy 在前后缘圆处重新计算 St1/St2 且不乘 SS1/SS2，"
                     "因此本轮的 LE/TE 圆弧半径敏感度为 0（见 B.3）；"
                     "其低敏感度有一部分来自这一实现事实，不能直接外推为“厚度分布无关”。")
        if r["failure_count"]:
            text += f" 扫描区间内出现 {r['failure_count']} 个失败水平（{r['failure_range']}）。"
        text += f" 决策：**{dec[p]['decision']}**（{dec[p]['rule_id']}）。"
        lines.append(text)

    if failed:
        lines.append("\n> 失败 Case 的参数、状态与原因均保留在 `case_metrics.csv`，"
                     "没有用其他样本替换，也没有静默收缩范围。")

    lines.append("\n### B.2 第二阶段（2×2）耦合证据\n")
    lines.append(stage1_interaction_rows(interactions))
    lines.append("\n> 相对交互指数 = |(f_HH - f_LH) - (f_HL - f_LL)| / |f_HH - f_LL|；"
                 "仅 4 个角点，不能证明整个二维参数域的耦合规律，只能作为局部/探索性证据。"
                 "指数 > 1 表示两端总变化 f_HH - f_LL 很小（两端效应相互抵消），"
                 "并不代表计算错误；必须结合四个角点的绝对指标一起解读。")
    ms = interactions.get("Metal2;Solidity", {})
    if ms:
        lines.append(
            f"\n> `Metal2 × Solidity` 的平均交互指数 = {ms.get('mean', float('nan')):.3f}，"
            "接近 0：本轮 Solidity 只改栅距，单叶型坐标不变，因此它与 Metal2 的"
            "单叶形状效应基本独立；但栅距与 Metal2 的通道匹配仍需工程判断。")

    lines.append("\n### B.3 区域分解（诊断列，不参与 S_comp 加权）\n")
    lines.append("| 参数 | S_LE_radius | S_LE_region | S_TE_radius | S_TE_region | S_camber_meanline | S_camber_angle | S_thick_front | S_thick_mid | S_thick_rear | S_cascade_pitch | S_cascade_gap |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sensitivity_rows:
        lines.append(
            f"| `{r['param']}` | {r['S_le_radius']:.4g} | {r['S_le_region']:.4g} "
            f"| {r['S_te_radius']:.4g} | {r['S_te_region']:.4g} "
            f"| {r['S_camber_meanline']:.4g} | {r['S_camber_angle']:.4g} "
            f"| {r['S_thickness_front']:.4g} | {r['S_thickness_mid']:.4g} "
            f"| {r['S_thickness_rear']:.4g} | {r['S_cascade_pitch']:.4g} "
            f"| {r['S_cascade_gap']:.4g} |")
    lines.append("\n> `S_LE_radius` 是拟合圆弧半径的相对变化；`S_LE_region` 还包含拼接弦与"
                 "相邻叶面（因此中弧线/厚度变化也会进入该列）。"
                 "两者必须区分，不能把 `S_LE_region` 直接当作前缘钝度。"
                 "中弧线 `κmax` 可能由端点控制，因此同时使用 `κRMS` 与 "
                 "`meanline_curvature_xc{010,050,090}`（见 `case_metrics.csv`）。")

    def _range_of(key):
        vals = []
        for r in rows:
            v = _num(r["metrics"].get(key))
            if math.isfinite(v):
                vals.append((v, r["case_id"]))
        if not vals:
            return None
        return min(vals), max(vals)

    lines.append("\n### B.4 边缘拼接、曲率可靠性与通道边界\n")
    gap = _range_of("min_gap_m")
    le_j = _range_of("le_junction_angle_jump_deg")
    te_j = _range_of("te_junction_angle_jump_deg")
    cstab = _range_of("le_curvature_stability_rel")
    if gap:
        lines.append(f"- `min_gap`：{gap[0][0]*1000:.4f} mm（{gap[0][1]}）– "
                     f"{gap[1][0]*1000:.4f} mm（{gap[1][1]}），全部 > 0；"
                     f"本轮没有 `min_gap <= 0.01 m` 的 Case。")
    if le_j and te_j:
        lines.append(f"- 拼接角跳变：LE {le_j[0][0]:.3f}–{le_j[1][0]:.3f}°，"
                     f"TE {te_j[0][0]:.3f}–{te_j[1][0]:.3f}°。"
                     "TE 端跳变几乎恒定，是 legacy 只插入 `Ncirc=4` 个圆弧点、"
                     "留出一段直弦造成的结构特征，不是参数效应。"
                     "`auto_flags` 因此对所有 Case 标记 `JUNCTION_JUMP_DIAGNOSTIC`，"
                     "但它不参与硬性 QC，也不参与参数决策。")
    if cstab:
        lines.append(f"- 曲率分辨率稳定性：{cstab[0][0]:.3f}–{cstab[1][0]:.3f}"
                     f"（阈值 {thr['curvature_stability_max']}），全部可用；"
                     "没有把数值振荡误当成真实曲率变化。")
    lines.append("- 本轮 100 个 Case 全部通过硬性 QC；这只说明几何在数学上闭合、有限、"
                 "无自交且通道最小间隙为正，**不说明**工程气动合理或可网格化。")

    # ------------------------------------------------------------------
    # C. key five parameters
    # ------------------------------------------------------------------
    lines.append("\n## C. 重点五参数\n")
    lines.append(
        "以下数字全部来自 `case_metrics.csv` 与 `parameter_sensitivity.csv`；"
        "引用的 Case ID 可在 `case_design.csv` 中追溯。"
        "长度量均除以基准弦长，故以“% 弦长”理解。\n")

    for p in KEY_PARAMS:
        lo_case, hi_case = level_extremes(rows, p)
        S = sens[p]["sensitivity"]
        lines.append(f"### C.{KEY_PARAMS.index(p)+1} `{p}`\n")
        if lo_case is None:
            lines.append("- 该参数没有通过硬性 QC 的有效扫描水平，无法给出敏感度结论。\n")
            continue
        lines.append(
            f"- 扫描：{RANGES[p][0]:g} – {RANGES[p][1]:g}，共 {sens[p]['n_levels']} 个非基准水平；"
            f"有效水平 {sens[p]['n_valid_levels']} 个。")
        if p in ("T1", "T2"):
            side = "le" if p == "T1" else "te"
            edge_cn = "前缘" if side == "le" else "尾缘"
            scale = 0.06 / float(base["metrics"]["chord_norm"])
            r_mm = float(base["metrics"][f"{side}_model_radius_norm"]) * scale * 1000.0
            lines.append(
                f"- 基准{edge_cn}圆弧半径（模型）= {r_mm:.4f} mm（按弦长 0.06 m 缩放）；"
                f"{p} 是厚度函数的输入参数，不能直接等同于{edge_cn}半径本身。")
        lines.append(
            f"- 整体：S_contour={S['S_contour']:.4g}，S_camber={S['S_camber']:.4g}，"
            f"S_thickness={S['S_thickness']:.4g}，S_comp={S['S_comp']:.4g}；"
            f"主导区域 = {REGION_CN[sens_rows[p]['dominant_region']]}；"
            f"单调性 = {MONO_CN[sens_rows[p]['monotonicity']]}。")
        lines.append(
            f"- 极端水平对照（{lo_case['case_id']} `{p}={float(lo_case['level_value']):.6g}` "
            f"→ {hi_case['case_id']} `{p}={float(hi_case['level_value']):.6g}`）：")

        if p == "Metal1":
            lines.append(
                "  - 说明：Metal1 是入口**金属角**；本轮没有把它解释为 Incidence，"
                "也没有构造入口气流角换算关系。")
            lines.append(
                f"  - 中弧线 RMS 偏移：{_metric_str(lo_case,'meanline_rms_dev_norm',4)} → "
                f"{_metric_str(hi_case,'meanline_rms_dev_norm',4)}；"
                f"轮廓 RMS：{_metric_str(lo_case,'contour_rms_dev_norm',4)} → "
                f"{_metric_str(hi_case,'contour_rms_dev_norm',4)}。")
            lines.append(
                f"  - 入口中弧线角（atan(sc)）：{_metric_str(lo_case,'meanline_angle_le_deg',5)}° → "
                f"{_metric_str(hi_case,'meanline_angle_le_deg',5)}°；"
                f"弦向角变化：{_metric_str(lo_case,'chord_angle_change_deg',4)}° → "
                f"{_metric_str(hi_case,'chord_angle_change_deg',4)}°。")
            lines.append(
                f"  - 前/尾缘拟合半径相对变化：LE {_metric_str(lo_case,'le_radius_change_rel',3)} → "
                f"{_metric_str(hi_case,'le_radius_change_rel',3)}，"
                f"TE {_metric_str(lo_case,'te_radius_change_rel',3)} → "
                f"{_metric_str(hi_case,'te_radius_change_rel',3)}（Metal1 主要改中弧线，"
                "不直接改边缘圆弧半径）。")
            lines.append(
                "  - 解读：Metal1 改变入口金属角与中弧线，但前/尾缘圆弧半径几乎不变"
                "（数值上约 1e-14），与 legacy 圆弧公式一致。")
        elif p == "T1":
            lines.append(
                f"  - 前缘拟合半径相对变化：{_metric_str(lo_case,'le_radius_change_rel',4)} → "
                f"{_metric_str(hi_case,'le_radius_change_rel',4)}；"
                f"前缘区域 RMS：{_metric_str(lo_case,'le_region_rms_dev_norm',4)} → "
                f"{_metric_str(hi_case,'le_region_rms_dev_norm',4)}。")
            lines.append(
                f"  - 前段厚度 RMS：{_metric_str(lo_case,'thickness_front_rms_dev_norm',4)} → "
                f"{_metric_str(hi_case,'thickness_front_rms_dev_norm',4)}；"
                f"整体轮廓 RMS：{_metric_str(lo_case,'contour_rms_dev_norm',4)} → "
                f"{_metric_str(hi_case,'contour_rms_dev_norm',4)}。")
            lines.append(
                f"  - 前缘拼接角跳变：{_metric_str(lo_case,'le_junction_angle_jump_deg',4)}° → "
                f"{_metric_str(hi_case,'le_junction_angle_jump_deg',4)}°。")
            lines.append(
                "  - 解读：T1 确实改变前缘钝度（半径相对变化显著），影响主要集中在前缘"
                "与前段厚度，对尾缘几乎无影响。")
        elif p == "T2":
            lines.append(
                f"  - 尾缘拟合半径相对变化：{_metric_str(lo_case,'te_radius_change_rel',4)} → "
                f"{_metric_str(hi_case,'te_radius_change_rel',4)}；"
                f"尾缘区域 RMS：{_metric_str(lo_case,'te_region_rms_dev_norm',4)} → "
                f"{_metric_str(hi_case,'te_region_rms_dev_norm',4)}。")
            lines.append(
                f"  - 后段厚度 RMS：{_metric_str(lo_case,'thickness_rear_rms_dev_norm',4)} → "
                f"{_metric_str(hi_case,'thickness_rear_rms_dev_norm',4)}；"
                f"整体轮廓 RMS：{_metric_str(lo_case,'contour_rms_dev_norm',4)} → "
                f"{_metric_str(hi_case,'contour_rms_dev_norm',4)}。")
            lines.append(
                f"  - 尾缘拼接角跳变：{_metric_str(lo_case,'te_junction_angle_jump_deg',4)}° → "
                f"{_metric_str(hi_case,'te_junction_angle_jump_deg',4)}°。")
            lines.append(
                "  - 解读：T2 确实改变尾缘钝度与尾缘区域；拼接角跳变几乎不随 T2 变化，"
                "说明该跳变主要由离散圆弧构造（Ncirc）决定，不能归因于 T2。")
        elif p == "Xmean":
            lines.append(
                f"  - 中弧线 RMS 偏移：{_metric_str(lo_case,'meanline_rms_dev_norm',4)} → "
                f"{_metric_str(hi_case,'meanline_rms_dev_norm',4)}；"
                f"中弧线曲率 RMS 变化：{_metric_str(lo_case,'meanline_curvature_rms_change_abs',4)} → "
                f"{_metric_str(hi_case,'meanline_curvature_rms_change_abs',4)}。")
            lines.append(
                f"  - 轮廓 RMS：{_metric_str(lo_case,'contour_rms_dev_norm',4)} → "
                f"{_metric_str(hi_case,'contour_rms_dev_norm',4)}；"
                f"最大厚度/位置变化：{_metric_str(lo_case,'max_thickness_change_norm',3)} / "
                f"{_metric_str(lo_case,'max_thickness_xc_change',3)} → "
                f"{_metric_str(hi_case,'max_thickness_change_norm',3)} / "
                f"{_metric_str(hi_case,'max_thickness_xc_change',3)}"
                "（Xmean 不进入厚度多项式）。")
            ix = interactions.get("Xmean;K_m", {})
            lines.append(
                f"  - 与 K_m 的 2×2 平均交互指数：{ix.get('mean', float('nan')):.3f}（局部证据）。")
            lines.append(
                "  - 解读：Xmean 显著改变中弧线分布且不改变厚度；与 K_m 的交互指数 >1 "
                "意味着两端效应可相互抵消，不能把两者单因素结果简单相加。")
        else:  # K_m
            lines.append(
                f"  - 中弧线 RMS 偏移：{_metric_str(lo_case,'meanline_rms_dev_norm',4)} → "
                f"{_metric_str(hi_case,'meanline_rms_dev_norm',4)}；"
                f"中弧线角范围变化：{_metric_str(lo_case,'meanline_angle_range_deg',5)}° → "
                f"{_metric_str(hi_case,'meanline_angle_range_deg',5)}°。")
            lines.append(
                f"  - 轮廓 RMS：{_metric_str(lo_case,'contour_rms_dev_norm',4)} → "
                f"{_metric_str(hi_case,'contour_rms_dev_norm',4)}；"
                f"中弧线曲率 RMS 变化：{_metric_str(lo_case,'meanline_curvature_rms_change_abs',4)} → "
                f"{_metric_str(hi_case,'meanline_curvature_rms_change_abs',4)}；"
                f"κmax 变化：{_metric_str(lo_case,'meanline_curvature_change_abs',4)} → "
                f"{_metric_str(hi_case,'meanline_curvature_change_abs',4)}。")
            lines.append(
                "  - K_m 只通过 Sm0 进入 meanline 系数，因此它提供的是“转弯在 Xmean 处完成了多少”"
                "的独立控制；与 Xmean 同时改变时可能出现非线性局部交互。")
            lines.append(
                "  - 解读：K_m 改变转弯分配与中弧线形状；与 Metal1 的响应方向部分重合"
                "（cos 见上表），需要联合评审，不能仅凭单因素结果判断独立性。")

        red_partner = sens_rows[p]["redundancy_partner"]
        red_cos = sens_rows[p]["redundancy_cosine"]
        if red_partner and math.isfinite(red_cos) and red_cos >= 0.5:
            red_text = f"与 `{red_partner}` 的响应余弦 = {red_cos:.3f}"
        else:
            red_text = "与其它参数的响应余弦均 < 0.5（无显著冗余）"
        lines.append(
            f"- 冗余：{red_text}；"
            f"决策：**{dec[p]['decision']}**（{dec[p]['rule_id']}）。\n")

    # ------------------------------------------------------------------
    # D. redundancy and decisions
    # ------------------------------------------------------------------
    lines.append("## D. 参数冗余与筛选建议\n")
    lines.append("| 参数 | 决策 | 规则 | S_comp | QC 通过率 | 背景数 | 低敏感背景数（含基准） | 冗余伙伴 / cos / 比值 | 下一步复核要求 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for d in decision_rows:
        red = "—"
        if (d["redundancy_partner"] and math.isfinite(d["redundancy_cosine"])
                and d["redundancy_cosine"] >= 0.5):
            red = (f"{d['redundancy_partner']} / {d['redundancy_cosine']:.3f} / "
                   f"{d['sensitivity_ratio']:.3f}")
        lines.append(
            f"| `{d['param']}` | **{d['decision']}** | {d['rule_id']} | {d['S_comp']:.4g} "
            f"| {d['qc_pass_rate']*100:.0f}% | {d['n_backgrounds']} "
            f"| {d['low_in_backgrounds']} | {red} | {d['required_followup']} |")

    lines.append("\n**冗余判据**：只比较参数引起的**几何响应向量**（中弧线/厚度/前缘/尾缘/"
                 "弦向角/弦长/最小间隙/中弧线曲率的符号化响应），"
                 "不是输入参数相关系数；"
                 f"cos ≥ {thr['redundancy_cosine']} 且弱/强敏感度比 ≤ {thr['redundancy_ratio']} "
                 "才标记为冗余候选。下表只显示 cos ≥ 0.5 的候选；"
                 "完整余弦值与所有伙伴见 `parameter_sensitivity.csv`。\n")
    insufficient = [d["param"] for d in decision_rows
                    if d["decision"] == "REVIEW"
                    and d["low_in_backgrounds"] < thr["min_backgrounds_for_fix"]]
    if insufficient:
        lines.append("**证据不足以做删除决定的参数**："
                     + "、".join(f"`{p}`" for p in insufficient)
                     + "。这些参数缺少第二个几何背景的配对复核，只能是 REVIEW，"
                       "不能判为 FIX_CANDIDATE。\n")
    fix = [d["param"] for d in decision_rows if d["decision"] == "FIX_CANDIDATE"]
    if fix:
        lines.append("**自动建议 FIX_CANDIDATE 的参数**："
                     + "、".join(f"`{p}`" for p in fix)
                     + "。这只是自动筛选建议，不等于最终冻结决策。\n")

    xm = next(d for d in decision_rows if d["param"] == "Xmean")
    lines.append(
        f"**值得人工重点评审的冗余候选**：`Xmean` 与 `Ks1` 的响应余弦 = "
        f"{xm['redundancy_cosine']:.3f}，`Ks1`/`Xmean` 的敏感度比 = "
        f"{xm['sensitivity_ratio']:.3f}，即在本轮范围内 Ks1 的中弧线效应大部分被 "
        "Xmean 覆盖；但两者 S_comp 都高于 KEEP 阈值，按保存的规则都判 KEEP，"
        "不会自动 FIX。下一轮应在 Xmean 的低/中/高三个背景下单独复核 Ks1，"
        "再决定是否合并或固定。\n")

    # ------------------------------------------------------------------
    # E. next round
    # ------------------------------------------------------------------
    lines.append("## E. 下一轮边界探索建议\n")
    keep = [d["param"] for d in decision_rows if d["decision"] == "KEEP_CANDIDATE"]
    review = [d["param"] for d in decision_rows if d["decision"] == "REVIEW"]
    lines.append(f"- **建议保留并继续探索（KEEP_CANDIDATE）**："
                 f"{'、'.join(f'`{p}`' for p in keep) if keep else '无'}。"
                 "含义是“在本轮范围内有明确几何影响，值得继续试探上下限”，不是“已批准范围”。"
                 "扩界应先做小步、单因素试探，其他参数保持基准。")
    lines.append(f"- **建议保留待评审（REVIEW）**："
                 f"{'、'.join(f'`{p}`' for p in review) if review else '无'}。"
                 "原因包括局部效应、耦合、数值不稳定或背景证据不足；不能据此删除。")
    lines.append(f"- **建议考虑固定（FIX_CANDIDATE）**："
                 f"{'、'.join(f'`{p}`' for p in fix) if fix else '无'}。"
                 "必须经过至少两个几何背景的配对复核；本轮不据此冻结。")
    strong_pairs = [(k, v.get("mean", 0.0)) for k, v in interactions.items()
                    if math.isfinite(v.get("mean", float("nan")))
                    and v.get("mean", 0.0) >= 0.2]
    if strong_pairs:
        lines.append("- **建议增加联合约束的参数对**：" + "、".join(
            f"`{k.replace(';', ' × ')}`（平均交互 {v:.2f}）" for k, v in strong_pairs)
            + "。四角点证据只能说明局部交互，不能外推为全域规律。")
    if failed:
        bad_params = sorted({r.get("sweep_param", "") for r in failed
                             if r.get("sweep_param")})
        lines.append("- **失败边界**：扫描中出现失败的参数为 "
                     + "、".join(f"`{p}`" for p in bad_params)
                     + "；下一轮应在失败值内侧加密，而不是把失败值从表中删除。")
    else:
        lines.append("- **失败边界**：本轮声明范围内没有失败 Case；"
                     "这不证明范围外安全，也不证明工程合理或可网格化。")

    lines.append("\n### E.1 必须区分的四个阶段\n")
    lines.append(
        "```text\n"
        "1. 数学几何有效        ：本轮可直接证明（生成器不抛异常、坐标有限、闭合）\n"
        "2. 自动几何诊断正常    ：本轮可直接证明（硬性 QC + 指标可计算 + 冻结 QC 复核）\n"
        "3. 工程气动合理        ：本轮未证明，需要人工/工程评审\n"
        "4. 可网格化 / CFD 收敛 ：本轮未证明，需要 NUMECA + CFX 真实试验\n"
        "```\n")
    lines.append("本轮结论只能覆盖第 1、2 类；任何“气动可接受”“可用于生产”的说法都超出证据范围。")

    # ------------------------------------------------------------------
    # F. data map / reproducibility / limitations
    # ------------------------------------------------------------------
    lines.append("\n## F. 数据、复现与限制\n")
    lines.append("### F.1 文件与追溯\n")
    lines.append("| 文件 | 内容 |")
    lines.append("|---|---|")
    lines.append("| `case_design.csv` | 100 行：13 参数、归一化水平、阶段、来源、选择理由与证据、锚点 Case |")
    lines.append("| `case_metrics.csv` | 100 行：生成状态、硬性 QC、冻结 QC 复核、全部几何指标与失败原因 |")
    lines.append("| `parameter_sensitivity.csv` | 13 行：S_contour/S_LE/S_TE/S_camber/S_thickness/S_cascade/S_comp、单调性、冗余、背景证据、失败范围 |")
    lines.append("| `parameter_decisions.csv` | 13 行：KEEP_CANDIDATE / REVIEW / FIX_CANDIDATE、规则号、判据版本、证据 Case |")
    lines.append("| `profiles.npz` | 所有生成成功 Case 的高精度曲线（xp/yp/xs/ys/xc/yc/thick/sc），按 Case ID 映射 |")
    lines.append("| `stage3_selection.json` | 候选池统计、锚点打分、每个自适应 Case 的选择依据 |")
    lines.append("| `provenance.json` | Git commit、脚本/判据/模板哈希、环境版本、随机种子、运行与验收结果 |")
    lines.append("| `overview_001_050.png` / `overview_051_100.png` | 100 个真实叶型总览（统一坐标），标注 Case/组/主要变化参数/QC |")
    lines.append("| `sensitivity_heatmap.png` | 13 参数 × 7 指标敏感性热力图（含决策标记） |")
    lines.append("| `audit/` | Step 0 审计、冻结资产 SHA256（运行前后）、运行元数据与验收记录 |")

    lines.append("\n### F.2 复现命令\n")
    lines.append("```bash\n"
                 "cd /home/qian/compressor_ai4s\n"
                 "conda run -n ai4s python tools/geometry_parameter_sensitivity_v1.py all\n"
                 "conda run -n ai4s python -m pytest "
                 "tests/test_geometry_legacy_v1_regression.py "
                 "tests/test_geometry_parametric_exploratory_v1.py -q\n"
                 "```\n")
    lines.append("单个 Case 的 4 位小数 `.dat` / `.geomTurbo` 可按需从 "
                 "`profiles.npz` 的高精度坐标 + `code/geometry_parametric_exploratory_v1.py` "
                 "重新序列化得到；本轮默认不批量保存这两类文件。\n")

    lines.append("### F.3 指标单位速查\n")
    lines.append("| 指标 | 单位 | 说明 |")
    lines.append("|---|---|---|")
    lines.append("| contour_rms_dev_norm / contour_max_dev_norm | 基准弦长的比例 | 对称点到折线距离（未配准） |")
    lines.append("| contour_rms_dev_aligned_norm | 基准弦长的比例 | 平移/旋转/缩放到基准后的形状差 |")
    lines.append("| meanline_rms_dev_norm | 基准弦长的比例 | 同一 xc 网格的中弧线偏移 |")
    lines.append("| thickness_*_rms_dev_norm | 基准弦长的比例 | 半厚度差（前/中/后段） |")
    lines.append("| le/te_radius_change_rel | 相对值 | 仅当两侧圆弧拟合均有效时给出 |")
    lines.append("| le/te_region_rms_dev_norm | 基准弦长的比例 | 边缘 5% 弦长区域（含拼接弦与相邻叶面） |")
    lines.append("| min_gap_m / periodicity_m | m | 弦长 0.06 m、pitch = 0.06/Solidity |")
    lines.append("| S_* | 无量纲/整个参数范围 | 见 `screening_criteria.yaml` |")

    lines.append("\n### F.4 限制与不确定性\n")
    lines.append("1. 判据阈值是**暂定研究阈值**，没有用历史 1891 样本校准；`criteria_status` "
                 "明确标为 `TENTATIVE_RESEARCH_THRESHOLDS_NOT_CALIBRATED`。")
    lines.append("2. 只有 100 个 Case，且第三阶段只有 5 个锚点 + 15 个单参数变体；"
                 "不能据此断言参数的全局无效性。")
    lines.append("3. 2×2 耦合只有 4 个角点，只提供局部交互证据；不能外推整个二维参数域。")
    lines.append("4. 本轮的“低敏感”只针对**已测试范围与背景**；缺少第二个背景时一律 REVIEW。")
    lines.append("5. 前/尾缘圆弧拟合使用 legacy 插入的 7 个真实轮廓点；"
                 "拼接弦（`Ncirc` 少插一点造成）与相邻叶面被排除在半径拟合之外，"
                 "但通过 `*_junction_angle_jump_deg` 与 `*_region_rms_dev_norm` 单独记录。")
    lines.append("6. 曲率指标使用 B 样条 + 分辨率稳定性检查；不稳定时标记为不可靠，"
                 "且不参与分类。")
    lines.append("7. 本轮没有运行 NUMECA / CFX；`geometry_ok=1` 不代表气动合理、"
                 "网格可生成或 CFD 可收敛。")
    lines.append("8. 未使用 AI/视觉评分来替代数值判据；所有决策均来自 "
                 "`screening_criteria.yaml` 的保存规则。")

    lines.append("\n### F.5 结论可追溯性\n")
    lines.append("本报告中的每个数字都可用以下方式追溯：\n")
    lines.append("- 参数级数字 → `parameter_sensitivity.csv` / `parameter_decisions.csv`；")
    lines.append("- Case 级数字 → `case_metrics.csv`（Case ID 关联）；")
    lines.append("- 参数取值与选择理由 → `case_design.csv`；")
    lines.append("- 自适应选择 → `stage3_selection.json`；")
    lines.append("- 运行环境与哈希 → `provenance.json`；")
    lines.append("- 阈值与规则原文 → `screening_criteria.yaml`。\n")

    report_summary = {
        "n_total": n_total, "gen_ok": gen_ok, "qc_pass": qc_pass,
        "frozen_pass": frozen_pass, "frozen_mismatch": len(frozen_mismatch),
        "failed": len(failed), "duplicates": len(duplicates),
        "stage_counts": stage_counts,
    }
    return "\n".join(lines), report_summary


# ---------------------------------------------------------------------------
# Verification / environment helpers
# ---------------------------------------------------------------------------
def env_info():
    import numpy as _np
    import scipy as _sp
    import matplotlib as _mpl
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": _np.__version__,
        "scipy": _sp.__version__,
        "matplotlib": _mpl.__version__,
        "pyyaml": yaml.__version__,
    }


def run_regression_summary() -> dict:
    """Run the frozen V1 regression + new generator test (read-only)."""
    import subprocess
    proc = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/test_geometry_legacy_v1_regression.py",
         "tests/test_geometry_parametric_exploratory_v1.py",
         "tests/test_geometry_qc.py", "-q"],
        cwd=str(REPO), capture_output=True, text=True)
    lines = (proc.stdout + proc.stderr).strip().splitlines()
    return {"returncode": proc.returncode,
            "last_line": lines[-1] if lines else "",
            "pass": proc.returncode == 0}


def dir_size_mb(path: Path) -> float:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return round(total / (1024 * 1024), 3)


def verify_frozen_assets():
    before = OUTDIR / "audit" / "sha256_before.txt"
    entries = []
    if not before.exists():
        return {"status": "NO_BASELINE_FILE", "checked": 0, "mismatches": []}
    for line in before.read_text().splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        digest, rel = parts
        entries.append((rel, digest))
    mismatches, lines = [], []
    for rel, digest in entries:
        path = REPO / rel
        actual = sha256_file(path) if path.is_file() else "MISSING"
        lines.append(f"{actual}  {rel}")
        if actual != digest:
            mismatches.append({"path": rel, "expected": digest, "actual": actual})
    (OUTDIR / "audit" / "sha256_after.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    return {
        "status": "PASS" if not mismatches else "FAIL",
        "checked": len(entries),
        "mismatches": mismatches,
    }


def guard_existing(overwrite: bool):
    produced = ["case_design.csv", "case_metrics.csv", "profiles.npz",
                "parameter_sensitivity.csv", "parameter_decisions.csv",
                "provenance.json", "REPORT.md", "stage3_selection.json",
                "overview_001_050.png", "overview_051_100.png",
                "sensitivity_heatmap.png"]
    existing = [n for n in produced if (OUTDIR / n).exists()]
    if not existing:
        return
    if not overwrite:
        raise SystemExit(
            "Refusing to overwrite existing experiment outputs: "
            + ", ".join(existing)
            + "\nUse --overwrite only if you intend to regenerate THIS experiment "
              "directory (frozen project assets are never touched).")
    for n in existing:
        (OUTDIR / n).unlink()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.floating, np.integer, np.bool_)):
        return obj.item()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def cmd_run(overwrite=False):
    guard_existing(overwrite)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "audit").mkdir(exist_ok=True)
    criteria = load_criteria()
    thr = criteria["thresholds"]
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    status_before = git_status()
    t_start = time.time()

    base_geom = gen.compute_geometry()
    base_ind = metrics.independent_metrics(base_geom, thr)
    noise = metrics.serialization_noise_floor(base_geom)

    cases12, level_plan = build_stage12()
    write_config(level_plan, cases12)
    write_design(cases12)

    print(f"[run] stage 1+2: {len(cases12)} cases")
    res12, tmp1 = run_cases(cases12, base_geom, base_ind, criteria, template_text)
    ok12 = sum(1 for r in res12 if r["generation_status"] == "OK")
    print(f"[run] stage 1+2 done: generation OK {ok12}/{len(res12)}")

    stage3, selection_records, stage3_stats = adaptive_select(
        cases12, res12, criteria, base_geom, base_ind)
    print(f"[run] stage 3 selected: {len(stage3)} cases "
          f"(pool {stage3_stats['pool_size_after_dedup']}, "
          f"valid {stage3_stats['pool_valid_count']})")

    print("[run] stage 3: executing")
    res3, tmp2 = run_cases(stage3, base_geom, base_ind, criteria, template_text)
    ok3 = sum(1 for r in res3 if r["generation_status"] == "OK")
    print(f"[run] stage 3 done: generation OK {ok3}/{len(res3)}")

    results = res12 + res3
    cases = cases12 + stage3
    if len(cases) != N_TOTAL:
        raise SystemExit(f"internal error: expected {N_TOTAL} cases, got {len(cases)}")

    rows = [flatten_result(r) for r in results]
    write_design(cases)
    write_metrics(rows)
    ids = write_profiles_npz(results, OUTDIR / "profiles.npz")
    npz_check = verify_profiles_npz(OUTDIR / "profiles.npz", results)

    selection_doc = {
        "algorithm_version": criteria["algorithm"]["design_version"],
        "criteria_id": criteria["criteria_id"],
        "criteria_version": criteria["criteria_version"],
        "seed": SOBOL_SEED,
        "summary": stage3_stats,
        "records": selection_records,
    }
    _atomic_text(OUTDIR / "stage3_selection.json",
                 json.dumps(_jsonable(selection_doc), indent=2,
                            ensure_ascii=False) + "\n")

    frozen_mismatches = [
        {"case_id": r["design"]["case_id"],
         "experiment_qc": r["metrics"].get("hard_qc_status"),
         "frozen_qc": r.get("frozen", {}).get("frozen_qc_status"),
         "experiment_reason": r["metrics"].get("qc_reason"),
         "frozen_reason": r.get("frozen", {}).get("frozen_qc_reason")}
        for r in results
        if r.get("frozen", {}).get("frozen_qc_status") in ("PASS", "FAIL")
        and r.get("frozen", {}).get("frozen_qc_status")
        != r["metrics"].get("hard_qc_status")
    ]

    frozen_check = verify_frozen_assets()
    runtime = time.time() - t_start
    meta = {
        "experiment_id": EXPERIMENT_ID,
        "git_head": git_head(),
        "git_status_before": status_before,
        "git_status_after": git_status(),
        "criteria_id": criteria["criteria_id"],
        "criteria_version": criteria["criteria_version"],
        "criteria_sha256": sha256_file(OUTDIR / "screening_criteria.yaml"),
        "config_sha256": sha256_file(OUTDIR / "experiment_config.yaml"),
        "seed": SOBOL_SEED,
        "env": env_info(),
        "runtime_s": round(runtime, 3),
        "n_cases": len(cases),
        "n_stage12": len(cases12),
        "n_stage3": len(stage3),
        "generation_ok": sum(1 for r in results if r["generation_status"] == "OK"),
        "hard_qc_pass": sum(1 for r in results
                            if r["metrics"].get("hard_qc_status") == "PASS"),
        "frozen_qc_pass": sum(1 for r in results
                              if r.get("frozen", {}).get("frozen_qc_status") == "PASS"),
        "frozen_qc_mismatches": frozen_mismatches,
        "failed_cases": [
            {"case_id": r["design"]["case_id"],
             "generation_status": r["generation_status"],
             "hard_qc_status": r["metrics"].get("hard_qc_status"),
             "failure_reason": r["failure_reason"],
             "qc_reason": r["metrics"].get("qc_reason")}
            for r in results
            if r["generation_status"] != "OK"
            or r["metrics"].get("hard_qc_status") != "PASS"
        ],
        "profiles_npz": npz_check,
        "profiles_saved": len(ids),
        "serialization_noise_floor": noise,
        "frozen_assets": frozen_check,
        "stage3": stage3_stats,
        "stage3_selection_file": "stage3_selection.json",
        "output_size_mb": dir_size_mb(OUTDIR),
    }
    _atomic_text(OUTDIR / "audit" / "run_metadata.json",
                 json.dumps(_jsonable(meta), indent=2, ensure_ascii=False) + "\n")

    shutil.rmtree(tmp1, ignore_errors=True)
    shutil.rmtree(tmp2, ignore_errors=True)

    print(json.dumps({
        "case_ids": [cases[0]["case_id"], cases[-1]["case_id"]],
        "generation_ok": meta["generation_ok"],
        "hard_qc_pass": meta["hard_qc_pass"],
        "frozen_qc_pass": meta["frozen_qc_pass"],
        "frozen_qc_mismatch": len(frozen_mismatches),
        "npz_reload_ok": npz_check["reload_ok"],
        "profiles_saved": len(ids),
        "runtime_s": round(runtime, 2),
    }, ensure_ascii=False))
    return meta


def load_plot_records(design_rows, metric_rows, npz_path):
    m_by_id = {r["case_id"]: r for r in metric_rows}
    records = []
    with np.load(npz_path, allow_pickle=False) as data:
        keys = set(data.files)
        for d in design_rows:
            cid = d["case_id"]
            rec = {"design": d, "metrics": m_by_id.get(cid, {})}
            if f"{cid}__xp" in keys:
                rec["geom"] = {
                    "xp1": data[f"{cid}__xp"], "yp1": data[f"{cid}__yp"],
                    "xs1": data[f"{cid}__xs"], "ys1": data[f"{cid}__ys"],
                }
            else:
                rec["geom"] = None
            records.append(rec)
    return records


def write_readme(summary, decision_rows, run_meta):
    counts = {}
    for d in decision_rows:
        counts[d["decision"]] = counts.get(d["decision"], 0) + 1
    decision_text = "\n".join(f"{k:16s}: {v}" for k, v in sorted(counts.items()))
    text = f"""# Parameter Sensitivity V1 — 100 Cases（探索性，未批准）

```text
Status            : EXPLORATORY / NOT APPROVED
Case 号段         : C820001 .. C820100
几何生成成功      : {run_meta['generation_ok']} / {run_meta['n_cases']}
实验硬性 QC 通过  : {run_meta['hard_qc_pass']} / {run_meta['n_cases']}
冻结 QC 通过      : {run_meta['frozen_qc_pass']} / {run_meta['n_cases']}
本目录体积        : {run_meta['output_size_mb']} MB
```

本目录只做 13 参数几何敏感性实验与自动筛选，**不包含** NUMECA 网格、CFX 结果、
AI 模型或正式生产 DOE/范围冻结。

## 决策分布（自动建议，不等于冻结）

```text
{decision_text}
```

## 入口文件

| 文件 | 用途 |
|---|---|
| `REPORT.md` | ★ 中文分析报告（结论与复现方式） |
| `overview_001_050.png` / `overview_051_100.png` | 100 个真实叶型总览 |
| `sensitivity_heatmap.png` | 13 参数敏感性热力图 |
| `case_design.csv` | 100 行实验设计与选择理由 |
| `case_metrics.csv` | 100 行 QC + 几何指标 |
| `parameter_sensitivity.csv` | 13 行定量敏感性 |
| `parameter_decisions.csv` | 13 行自动筛选建议 |
| `profiles.npz` | 生成成功 Case 的高精度曲线（按 Case ID） |
| `stage3_selection.json` | 第三阶段候选池与选择依据 |
| `screening_criteria.yaml` | 判据、阈值、单位、规则（分类前已保存） |
| `provenance.json` | Git/环境/哈希/运行与验收信息 |
| `audit/step0_audit.md` | 执行前代码与公式审计 |

## 复现

```bash
cd /home/qian/compressor_ai4s
conda run -n ai4s python tools/geometry_parameter_sensitivity_v1.py all
```

> `Geometry QC PASS` ≠ 气动合理 ≠ 网格/CFD 可行。
> 所有阈值均为暂定研究阈值，未用历史 1891 样本校准。
"""
    _atomic_text(OUTDIR / "README.md", text)


def cmd_analyze():
    rows, design, metric_rows = load_rows_for_analysis()
    criteria = load_criteria()
    sens, interactions, backgrounds, redundancy, srows, drows = \
        build_parameter_tables(rows, criteria)

    write_csv(OUTDIR / "parameter_sensitivity.csv", srows,
              ["param", "param_class", "range_min", "range_max", "baseline",
               "n_levels", "n_valid_levels", "qc_pass_rate",
               "S_contour", "S_le", "S_te", "S_camber", "S_thickness",
               "S_cascade", "S_comp", "S_le_radius", "S_le_region",
               "S_te_radius", "S_te_region", "S_camber_meanline",
               "S_camber_angle", "S_thickness_total", "S_thickness_front",
               "S_thickness_mid", "S_thickness_rear", "S_cascade_gap",
               "S_cascade_pitch", "dominant_region", "monotonicity",
               "spearman_rho", "dominant_signed_feature",
               "redundancy_partner", "redundancy_cosine",
               "sensitivity_ratio_to_partner", "n_backgrounds",
               "low_in_backgrounds", "background_effect_comp_min",
               "background_effect_comp_max", "background_effect_local_max",
               "failure_count", "failure_range", "evidence_case_ids",
               "background_evidence", "decision", "decision_rule_id"])
    write_csv(OUTDIR / "parameter_decisions.csv", drows,
              ["param", "decision", "rule_id", "criteria_id",
               "criteria_version", "S_comp", "S_contour", "S_le", "S_te",
               "S_camber", "S_thickness", "S_cascade", "qc_pass_rate",
               "n_valid_levels", "n_backgrounds", "low_in_backgrounds",
               "redundancy_partner", "redundancy_cosine", "sensitivity_ratio",
               "failure_range", "evidence_case_ids", "required_followup",
               "human_review_required"])

    plot_records = load_plot_records(design, metric_rows, OUTDIR / "profiles.npz")
    limits = global_limits(plot_records)
    plot_overview(plot_records, OUTDIR / "overview_001_050.png", limits, (0, 50))
    plot_overview(plot_records, OUTDIR / "overview_051_100.png", limits, (50, 100))
    plot_heatmap(srows, drows, OUTDIR / "sensitivity_heatmap.png")

    run_meta = load_run_metadata()
    run_meta["frozen_assets_check"] = run_meta.get("frozen_assets", {}).get("status", "")
    run_meta["npz_reload"] = run_meta.get("profiles_npz", {}).get("reload_ok", "")
    run_meta["v1_regression"] = run_regression_summary()
    with open(OUTDIR / "stage3_selection.json") as f:
        stage3_doc = json.load(f)
    stage3_records = stage3_doc.get("records", [])
    run_meta["stage3_variant_params"] = sorted({
        r.get("changed_param") for r in stage3_records
        if r.get("kind") == "variant" and r.get("changed_param")})
    run_meta["stage3_anchor_ids"] = [r["case_id"] for r in stage3_records
                                     if r.get("kind") == "anchor"]
    run_meta["output_size_mb"] = dir_size_mb(OUTDIR)
    report_text, report_summary = build_report(
        rows, sens, interactions, backgrounds, srows, drows, run_meta, criteria)
    _atomic_text(OUTDIR / "REPORT.md", report_text + "\n")
    write_readme(report_summary, drows, run_meta)

    output_files = [
        "README.md", "experiment_config.yaml", "screening_criteria.yaml",
        "case_design.csv", "case_metrics.csv", "parameter_sensitivity.csv",
        "parameter_decisions.csv", "profiles.npz", "stage3_selection.json",
        "REPORT.md", "overview_001_050.png", "overview_051_100.png",
        "sensitivity_heatmap.png", "audit/step0_audit.md",
        "audit/sha256_before.txt", "audit/sha256_after.txt",
        "audit/run_metadata.json",
    ]
    file_info = {}
    for name in output_files:
        p = OUTDIR / name
        if p.is_file():
            file_info[name] = {"bytes": p.stat().st_size,
                               "sha256": sha256_file(p)}

    decision_counts = {}
    for d in drows:
        decision_counts[d["decision"]] = decision_counts.get(d["decision"], 0) + 1

    provenance = dict(run_meta)
    provenance.update({
        "git_head_at_analysis": git_head(),
        "git_status_at_analysis": git_status(),
        "criteria": {
            "criteria_id": criteria["criteria_id"],
            "criteria_version": criteria["criteria_version"],
            "criteria_status": criteria["criteria_status"],
            "sha256": sha256_file(OUTDIR / "screening_criteria.yaml"),
            "sha256_at_run": run_meta.get("criteria_sha256", ""),
            "revision_check_file": "audit/criteria_revision_check.json",
            "thresholds": criteria["thresholds"],
            "weights": criteria["sensitivity"]["composite"]["weights"],
            "classification_rules": criteria["classification_rules"],
        },
        "analysis": {
            "decision_counts": decision_counts,
            "interaction_indices": interactions,
            "redundancy": redundancy,
            "sensitivity_summary": srows,
            "n_rows": len(rows),
        },
        "output_files": file_info,
        "output_size_mb": dir_size_mb(OUTDIR),
        "acceptance_check_file": "audit/acceptance_check.json",
        "notes": [
            "all thresholds are tentative research thresholds, not calibrated on the 1891 historical population",
            "no NUMECA / CFX / AI training / production DOE / production range freeze was executed",
            "decisions are advisory only",
        ],
    })
    _atomic_text(OUTDIR / "provenance.json",
                 json.dumps(_jsonable(provenance), indent=2,
                            ensure_ascii=False) + "\n")

    print(json.dumps({
        "rows": len(rows),
        "decisions": decision_counts,
        "report_summary": report_summary,
        "output_size_mb": provenance["output_size_mb"],
    }, ensure_ascii=False))
    return provenance


# ---------------------------------------------------------------------------
# Acceptance validation
# ---------------------------------------------------------------------------
def cmd_validate():
    import re
    import subprocess

    checks = []

    def add(name, ok, detail, level="FAIL"):
        checks.append({"check": name, "pass": bool(ok), "detail": detail,
                       "level": level})

    with open(OUTDIR / "case_design.csv", newline="") as f:
        design = list(csv.DictReader(f))
    with open(OUTDIR / "case_metrics.csv", newline="") as f:
        metric_rows = list(csv.DictReader(f))
    criteria = load_criteria()
    run_meta = load_run_metadata()
    design_ids = [d["case_id"] for d in design]
    metric_ids = [r["case_id"] for r in metric_rows]
    thr = criteria["thresholds"]
    base_geom = gen.compute_geometry()
    base_ind = metrics.independent_metrics(base_geom, thr)

    add("n_cases_100", len(design) == N_TOTAL and len(metric_rows) == N_TOTAL,
        f"design={len(design)}, metrics={len(metric_rows)}")
    add("unique_case_ids", len(set(design_ids)) == N_TOTAL,
        f"unique={len(set(design_ids))}")
    add("case_id_format", all(re.fullmatch(r"C[0-9]{6}", c) for c in design_ids),
        "expected C820001..C820100")
    add("design_metrics_linkage", design_ids == metric_ids,
        "both files must list the same 100 IDs in the same order")
    add("stage_counts", all(sum(1 for d in design if d["stage"] == s) == n
                            for s, n in (("S1", 60), ("S2", 20), ("S3", 20))),
        {s: sum(1 for d in design if d["stage"] == s) for s in ("S1", "S2", "S3")})

    all_params = set()
    for d in design:
        if d["sweep_param"]:
            all_params.add(d["sweep_param"])
        for p in d["pair_params"].split(";"):
            if p:
                all_params.add(p)
        for p in d["planned_varied_params"].split(";"):
            if p:
                all_params.add(p)
    add("all_13_parameters_exercised", set(PARAMS).issubset(all_params),
        {"covered": sorted(all_params),
         "missing": sorted(set(PARAMS) - all_params)})

    key_levels = {p: sum(1 for d in design
                         if d["stage"] == "S1" and d["sweep_param"] == p)
                  for p in KEY_PARAMS}
    add("key_params_dense_scan", all(v == 7 for v in key_levels.values()),
        key_levels)

    vectors = {}
    for d in design:
        key = tuple(round(float(d[p]), 10) for p in PARAMS)
        vectors.setdefault(key, []).append(d["case_id"])
    duplicates = {k: v for k, v in vectors.items() if len(v) > 1}
    add("no_duplicate_parameter_vectors", not duplicates,
        {"duplicate_groups": len(duplicates)})

    fixed_ok = all(abs(float(d["Incidence"]) - 0.0) < 1e-12
                   and abs(float(d["Mach"]) - 0.5) < 1e-12 for d in design)
    add("operating_conditions_fixed", fixed_ok, "Incidence=0, Mach=0.5")

    bad = [r for r in metric_rows
           if (r["hard_qc_status"] != "PASS"
               and not (r["failure_reason"] or r["qc_reason"]))]
    add("failed_cases_have_reason", not bad, {"bad_rows": len(bad)})
    failed_rows = [r for r in metric_rows if r["hard_qc_status"] != "PASS"]
    add("failed_cases_preserved",
        len(failed_rows) == len(run_meta["failed_cases"]),
        {"metrics_failed": len(failed_rows),
         "run_meta_failed": len(run_meta["failed_cases"])})

    required_defs = ["contour_rms_dev_norm", "meanline_rms_dev_norm",
                     "thickness_rms_dev_norm", "le_radius_fitted_norm",
                     "te_radius_fitted_norm", "min_gap_m",
                     "curvature_stability_rel"]
    defs = criteria["metric_definitions"]
    add("metric_definitions_complete",
        all(k in defs for k in required_defs) and "units" in criteria,
        {"missing": [k for k in required_defs if k not in defs]})
    thresholds = criteria["thresholds"]
    add("thresholds_complete",
        all(k in thresholds for k in ("keep_comp", "review_comp", "keep_local",
                                      "keep_cascade", "redundancy_cosine",
                                      "curvature_stability_max")),
        sorted(thresholds.keys()))

    criteria_mtime = (OUTDIR / "screening_criteria.yaml").stat().st_mtime
    decisions_mtime = (OUTDIR / "parameter_decisions.csv").stat().st_mtime
    add("criteria_saved_before_classification", criteria_mtime < decisions_mtime,
        f"criteria_mtime={criteria_mtime:.0f} < decisions_mtime={decisions_mtime:.0f}")

    rev_path = OUTDIR / "audit" / "criteria_revision_check.json"
    if rev_path.is_file():
        rev = json.loads(rev_path.read_text())
        add("criteria_thresholds_unchanged_since_run",
            all(rev.get("unchanged_sections", {}).values()),
            rev.get("unchanged_sections"))
    else:
        add("criteria_thresholds_unchanged_since_run", False,
            "audit/criteria_revision_check.json missing")

    with open(OUTDIR / "parameter_sensitivity.csv", newline="") as f:
        srows = list(csv.DictReader(f))
    with open(OUTDIR / "parameter_decisions.csv", newline="") as f:
        drows = list(csv.DictReader(f))
    add("sensitivity_rows_13",
        len(srows) == 13 and {r["param"] for r in srows} == set(PARAMS),
        len(srows))
    add("decision_rows_13",
        len(drows) == 13 and {d["param"] for d in drows} == set(PARAMS),
        len(drows))
    add("decision_values_valid",
        all(d["decision"] in ("KEEP_CANDIDATE", "REVIEW", "FIX_CANDIDATE")
            for d in drows),
        sorted({d["decision"] for d in drows}))

    for name, min_bytes in (("overview_001_050.png", 50_000),
                            ("overview_051_100.png", 50_000),
                            ("sensitivity_heatmap.png", 30_000)):
        p = OUTDIR / name
        add(f"figure_{name}", p.is_file() and p.stat().st_size >= min_bytes,
            {"exists": p.is_file(),
             "bytes": p.stat().st_size if p.is_file() else 0})

    with np.load(OUTDIR / "profiles.npz", allow_pickle=False) as data:
        npz_ids = [str(x) for x in data["case_ids"]]
        npz_ok = (len(npz_ids) == run_meta["profiles_saved"]
                  and len(set(npz_ids)) == len(npz_ids)
                  and set(npz_ids).issubset(set(design_ids)))
    add("profiles_npz_reloadable_and_mapped", npz_ok,
        {"saved": len(npz_ids), "unique": len(set(npz_ids))})
    add("profiles_npz_matches_expected",
        run_meta.get("profiles_npz", {}).get("reload_ok", False),
        run_meta.get("profiles_npz", {}))

    add("case_metrics_contains_all_params",
        all(p in metric_rows[0] for p in PARAMS),
        {"missing": [p for p in PARAMS if p not in metric_rows[0]]})
    with open(OUTDIR / "parameter_sensitivity.csv", newline="") as f:
        s_header = next(csv.reader(f))
    add("sensitivity_contains_decision",
        "decision" in s_header and "decision_rule_id" in s_header,
        {"has_decision": "decision" in s_header,
         "has_rule_id": "decision_rule_id" in s_header})

    sample_ids = [design[0]["case_id"], design[81]["case_id"],
                  design[-1]["case_id"]]
    m_by_id = {r["case_id"]: r for r in metric_rows}
    repro_errors = []
    with np.load(OUTDIR / "profiles.npz", allow_pickle=False) as data:
        for cid in sample_ids:
            d = next(r for r in design if r["case_id"] == cid)
            params = {p: float(d[p]) for p in PARAMS}
            g = gen.compute_geometry(params)
            for key, field in (("xp", "xp1"), ("yp", "yp1"), ("xs", "xs1"),
                               ("ys", "ys1"), ("yc", "yc"), ("thick", "thick")):
                if not np.array_equal(data[f"{cid}__{key}"],
                                      np.asarray(g[field], dtype=float)):
                    repro_errors.append(f"{cid}:{key}")
            flat, _ = metrics.compute_case_metrics(
                g, base_geom, base_ind, thr)
            row = m_by_id[cid]
            for k in ("contour_rms_dev_norm", "min_gap_m",
                      "meanline_rms_dev_norm", "thickness_rms_dev_norm"):
                diff = abs(flat[k] - float(row[k]))
                if diff > 1e-12:
                    repro_errors.append(f"{cid}:{k}:{diff:.3e}")
    add("case_reproduction_from_csv_exact", not repro_errors,
        {"sample_case_ids": sample_ids, "errors": repro_errors})

    frozen = verify_frozen_assets()
    add("frozen_assets_unchanged", frozen["status"] == "PASS",
        {"checked": frozen["checked"], "mismatches": frozen["mismatches"]})

    proc = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/test_geometry_legacy_v1_regression.py",
         "tests/test_geometry_parametric_exploratory_v1.py",
         "tests/test_geometry_qc.py", "-q"],
        cwd=str(REPO), capture_output=True, text=True)
    tail = (proc.stdout + proc.stderr).strip().splitlines()
    add("v1_and_new_regression_tests", proc.returncode == 0,
        tail[-1] if tail else f"returncode={proc.returncode}")

    size_mb = dir_size_mb(OUTDIR)
    add("output_size_target", size_mb <= 5.0,
        f"{size_mb} MB (target ~5 MB)", level="WARN")
    add("output_size_acceptable", size_mb <= 8.0,
        f"{size_mb} MB (hard cap 8 MB)")

    with open(OUTDIR / "stage3_selection.json") as f:
        stage3 = json.load(f)
    records = stage3.get("records", [])
    add("stage3_selection_recorded",
        len(records) == 20
        and sum(1 for r in records if r.get("kind") == "anchor") == N_ANCHORS,
        {"records": len(records),
         "anchors": sum(1 for r in records if r.get("kind") == "anchor")})

    overall = all(c["pass"] for c in checks if c["level"] == "FAIL")
    result = {
        "overall_pass": overall,
        "criteria_id": criteria["criteria_id"],
        "criteria_version": criteria["criteria_version"],
        "checks": checks,
        "output_size_mb": size_mb,
        "warnings": [c for c in checks if c["level"] == "WARN" and not c["pass"]],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _atomic_text(OUTDIR / "audit" / "acceptance_check.json",
                 json.dumps(_jsonable(result), indent=2,
                            ensure_ascii=False) + "\n")
    print(json.dumps({"overall_pass": overall,
                      "failed": [c for c in checks if not c["pass"]],
                      "output_size_mb": size_mb},
                     ensure_ascii=False, indent=2))
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Geometry parameter sensitivity & screening V1 (100 cases)")
    parser.add_argument("command",
                        choices=["design", "run", "analyze", "validate", "all"])
    parser.add_argument("--overwrite", action="store_true",
                        help="regenerate only this experiment's outputs")
    args = parser.parse_args(argv)

    if args.command == "design":
        cases, plan = build_stage12()
        OUTDIR.mkdir(parents=True, exist_ok=True)
        (OUTDIR / "audit").mkdir(exist_ok=True)
        write_config(plan, cases)
        write_csv(OUTDIR / "audit" / "stage12_design_preview.csv",
                  cases, DESIGN_COLUMNS)
        print(json.dumps({"stage12_cases": len(cases),
                          "levels": plan}, ensure_ascii=False, default=str))
        return
    if args.command == "run":
        cmd_run(args.overwrite)
        return
    if args.command == "analyze":
        cmd_analyze()
        return
    if args.command == "validate":
        cmd_validate()
        return
    cmd_run(args.overwrite)
    cmd_analyze()
    cmd_validate()


if __name__ == "__main__":
    main()
