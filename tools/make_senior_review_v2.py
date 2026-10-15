#!/usr/bin/env python
"""make_senior_review_v2.py — build the 40-case senior review package (V2).

Packaging / visualisation ONLY.  This script never regenerates geometry and
never re-runs Geometry QC: it re-uses the already validated V2 output of

    analysis/geometry_review/review_cases.csv        (40 cases, C810001..C810040)
    analysis/geometry_review/geometry/               (real .dat + .geomTurbo)
    analysis/geometry_review/geometry_qc.csv         (real QC report)

and copies it into a self-contained review package for the advisor::

    analysis/geometry_review/senior_review_v2/
    ├── README.md
    ├── 00_all_cases_overview.png        5 rows x 8 cols = all 40 cases
    ├── 00_case_index.csv                one row per case (human columns empty)
    └── cases/C8100xx/
        ├── parameters.json
        ├── blade_profile.png            single blade (identical window/scale)
        ├── cascade_3blade.png           3 adjacent blades at the real pitch
        ├── edge_details.png             LE + TE zoom (identical window/scale)
        ├── C8100xx.dat                  verbatim copy (source not modified)
        └── C8100xx.geomTurbo            verbatim copy (source not modified)

Conventions are NOT re-implemented here: ``tools/plot_geometry_review.py`` is
imported as a module and supplies the profile frame, the chord normalisation to
CHORD_TARGET (= 0.06 m, the frozen legacy chord) and the QC helpers.

Units (see the package README):
  * ``.dat`` rows are ``xp yp xs ys`` in RAW (normalised) profile units; they are
    uniformly scaled here so that chord = 0.06 m, which is the physical scale of
    the ``.geomTurbo`` (``UNITS Meters``).  Every distance plotted is in metres.
  * ``Xthick, Tmax, Metal2`` are NON-dimensional shape parameters and are never
    labelled as metres.  ``min_interior_thickness`` / ``max_paired_thickness``
    are raw-profile quantities as well (see parameters.json "units").
  * The neighbour shift of the 3-blade cascade is the real ``PERIODICITY`` read
    from each ``.geomTurbo`` (= 0.06 / Solidity), applied along +Y, i.e. exactly
    the periodic neighbour model used by ``code/03_geometry_qc.py``.

Usage::

    conda run -n ai4s python tools/make_senior_review_v2.py
    conda run -n ai4s python tools/make_senior_review_v2.py --zip /tmp/x.zip
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
import sys
import textwrap
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")                       # headless: no GUI, no plt.show()
import matplotlib.pyplot as plt             # noqa: E402
import numpy as np                          # noqa: E402
from matplotlib.ticker import MultipleLocator  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
REVIEW_DIR = REPO / "analysis" / "geometry_review"
PGR_PATH = REPO / "tools" / "plot_geometry_review.py"


def _load_plot_module():
    """Import tools/plot_geometry_review.py as a module (single source of truth)."""
    spec = importlib.util.spec_from_file_location("plot_geometry_review", PGR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pgr = _load_plot_module()                   # profile frame + QC helpers + colors

DEFAULT_CASES = REVIEW_DIR / "review_cases.csv"
DEFAULT_GEOMETRY = REVIEW_DIR / "geometry"
DEFAULT_QC = REVIEW_DIR / "geometry_qc.csv"
DEFAULT_RANGES = REVIEW_DIR / "ranges_exploratory_v2.yaml"
DEFAULT_OUTDIR = REVIEW_DIR / "senior_review_v2"
DEFAULT_ZIP = REVIEW_DIR / "senior_review_v2.zip"

GEOMETRY_PARAMS = pgr.GEOMETRY_PARAMS       # (Xthick, Tmax, Metal2, Solidity)
ALL_PARAMS = GEOMETRY_PARAMS + ("Incidence", "Mach")
CHORD_TARGET = pgr.CHORD_TARGET             # 0.06 m (frozen legacy chord)

# case ordering: keep the designed experiment groups, then the case-id order
# (case ids were assigned by the V2 builder in scan order inside each group).
# NOTE: this is exactly the order in which review_cases.csv was built, so the
# overview panels follow the designed parameter-scan order (no shuffling).
GROUP_ORDER = ("A_single_param", "B_corner", "C_coupled", "C_combined",
               "D_maximin")
GROUP_TINT = {
    "A_single_param": "#eef4fb",
    "B_corner": "#fdf1e6",
    "C_combined": "#fdecec",
    "C_coupled": "#eefaf0",
    "D_maximin": "#f4eefb",
}

DPI_MIN = 200
DPI_DEFAULT = 200

PAD_FRACTION = 0.06                         # window padding as % of data span
BLADE_PANEL_IN = 7.0                        # inches of axes width (global window)
OVERVIEW_PANEL_IN = 3.2                     # inches of axes width per overview panel
OVERVIEW_COLS = 8
OVERVIEW_ROWS = 5                           # 8 x 5 = 40 panels (all cases)
ZOOM_HALF_M = 0.006                         # LE / TE square zoom half window [m]
ZOOM_SCALE_FACTOR = 4.0                     # zoom scale vs blade_profile scale

# figure margins in inches (left, right, bottom, top) — fixed so that every
# image of the same family has the same axes box, hence the same m/px scale.
M_BLADE = (0.62, 0.98, 0.78, 1.10)
M_CASCADE = (0.62, 0.98, 1.00, 1.10)
M_EDGE = (0.45, 0.45, 0.85, 0.95)
M_OVERVIEW = (0.30, 0.30, 0.75, 1.35)
NEIGHBOUR_MARGIN = 1.15                     # canvas margin, in units of pitch
MAX_CASCADE_PANEL_IN = 18.0                 # canvas-height cap for 3-blade figures

FOOTER_BLADE = ("real .dat / .geomTurbo coordinates · chord-normalised to 0.06 m (metres on both axes) · "
                "equal aspect · IDENTICAL window and scale for all 40 cases · "
                "Xthick / Tmax / Metal2 are non-dimensional parameters (not metres)")


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_fixed(fig, path: Path, dpi: int):
    """Save without ``bbox_inches='tight'`` so the axes box (and the m/px
    scale) stays exactly as constructed — required for cross-case comparison."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def put_footer(fig, text, fontsize=6.5, offset_in=0.16, reserve_in=None):
    """Footer text a fixed number of INCHES above the bottom edge, auto-wrapped to
    the figure width so it can never be clipped; warns when it does not fit."""
    fig_w_in, fig_h_in = fig.get_size_inches()
    chars = max(40, int((fig_w_in * 72 - 24) / (0.52 * fontsize)))
    wrapped = textwrap.fill(text, width=chars)
    lines = wrapped.count("\n") + 1
    needed = offset_in + lines * fontsize * 1.35 / 72
    if reserve_in is not None and needed > reserve_in:
        print(f"warning: footer needs {needed:.2f} in but only {reserve_in:.2f} in "
              f"is reserved ({lines} line(s))", file=sys.stderr)
    fig.text(0.5, offset_in / fig_h_in, wrapped, ha="center", va="bottom",
             fontsize=fontsize, color="#444444")


def make_axes(fig, x_in, y_in, w_in, x_lim, y_lim,
              xlabel="Z  chordwise  [m]", ylabel="Y  tangential  [m]",
              facecolor="white"):
    """Add one axes whose box is w_in inches wide and whose aspect is exactly
    the data aspect of (x_lim, y_lim) -> equal aspect with a known m/inch scale."""
    fig_w, fig_h = fig.get_size_inches()
    scale = w_in / (x_lim[1] - x_lim[0])              # inches per metre (both axes)
    h_in = scale * (y_lim[1] - y_lim[0])
    ax = fig.add_axes([x_in / fig_w, y_in / fig_h, w_in / fig_w, h_in / fig_h])
    ax.set_xlim(x_lim)
    ax.set_ylim(y_lim)
    ax.set_aspect("equal", adjustable="box")
    ax.set_facecolor(facecolor)
    ax.grid(True, alpha=0.22, lw=0.5)
    ax.set_xlabel(xlabel, fontsize=8)
    ax.set_ylabel(ylabel, fontsize=8)
    ax.tick_params(labelsize=7)
    return ax, h_in


def data_window(arrays, pad=PAD_FRACTION):
    """(x_lim, y_lim) covering every given (n,2) array with padding."""
    flat = [a for a in arrays if a is not None and len(a)]
    stacked = np.vstack(flat)
    x0, x1 = float(stacked[:, 0].min()), float(stacked[:, 0].max())
    y0, y1 = float(stacked[:, 1].min()), float(stacked[:, 1].max())
    return (x0 - (x1 - x0) * pad, x1 + (x1 - x0) * pad), \
           (y0 - (y1 - y0) * pad, y1 + (y1 - y0) * pad)


def blade_group_table(cases):
    """{case_id: {id, members, size}} — cases sharing (Xthick, Tmax, Metal2)."""
    table, groups = {}, []
    for case in cases:
        key = (float(case["Xthick"]), float(case["Tmax"]), float(case["Metal2"]))
        for entry in groups:
            if entry["key"] == key:
                entry["members"].append(case["case_id"])
                break
        else:
            groups.append({"key": key, "members": [case["case_id"]]})
    for number, entry in enumerate(groups, start=1):
        group_id = f"BL{number:02d}"
        for case_id in entry["members"]:
            table[case_id] = {"id": group_id, "members": list(entry["members"]),
                              "size": len(entry["members"])}
    return table, groups


def ordered_cases(cases):
    """Case order for figures/index: designed group order, then case_id."""
    rank = {name: i for i, name in enumerate(GROUP_ORDER)}
    return sorted(cases, key=lambda c: (rank.get(c.get("group", ""), 99),
                                        c["case_id"]))


def param_line(case, params=GEOMETRY_PARAMS):
    return "  ".join(f"{key}={float(case[key]):g}" for key in params)


def beyond_legacy(case, legacy, params=GEOMETRY_PARAMS):
    """Geometry parameters of this case that fall outside the legacy range."""
    out = []
    for key in params:
        value = float(case[key])
        lo, hi = legacy[key]
        if not (lo - 1e-12 <= value <= hi + 1e-12):
            out.append(key)
    return out


def group_tag(group, tint=True):
    return f"[{group}]"


def draw_pair(ax, pressure, suction, color, lw=1.7, alpha=1.0, zorder=3):
    ax.plot(pressure[:, 0], pressure[:, 1], color=color, lw=lw, alpha=alpha,
            zorder=zorder, solid_capstyle="round")
    ax.plot(suction[:, 0], suction[:, 1], color=color, lw=lw, alpha=alpha,
            ls="--", zorder=zorder, solid_capstyle="round")


def meanline_of(pressure, suction):
    return (pressure + suction) / 2.0


def scale_bar(ax, x_lim, y_lim, length=0.01, text=None):
    """Physical scale reference bar inside the axes (metres)."""
    x0 = x_lim[0] + (x_lim[1] - x_lim[0]) * 0.70
    y0 = y_lim[0] + (y_lim[1] - y_lim[0]) * 0.07
    ax.plot([x0, x0 + length], [y0, y0], color="#111111", lw=2.2,
            solid_capstyle="butt", zorder=7)
    ax.text(x0 + length / 2, y0 + (y_lim[1] - y_lim[0]) * 0.025,
            text or f"{length:g} m", ha="center", va="bottom", fontsize=7,
            zorder=7)


# ---------------------------------------------------------------------------
# parameters.json
# ---------------------------------------------------------------------------
def num(row, key):
    """float from a QC/CSV text field, or None when empty/absent."""
    if not row:
        return None
    raw = (row.get(key) or "").strip()
    if raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


UNIT_NOTES = {
    "min_gap": {"unit": "m", "frame": "geomTurbo blade section",
                "meaning": "min distance between the blade and its periodic "
                           "neighbours (+/- PERIODICITY along Y)",
                "gate": "HARD GATE of geometry_qc_v1_hard: must be > 0"},
    "envelope_clearance": {"unit": "m", "frame": "geomTurbo blade section",
                           "meaning": "PERIODICITY - blade tangential extent",
                           "gate": "DIAGNOSTIC ONLY. A NEGATIVE value is NOT a "
                                   "blade collision and not a QC failure."},
    "blade_tangential_extent": {"unit": "m", "frame": "geomTurbo blade section",
                                "meaning": "max(Y) - min(Y) of the blade section"},
    "periodicity": {"unit": "m", "frame": "geomTurbo PERIODICITY field",
                    "meaning": "pitch = CHORD_TARGET / Solidity = 0.06 / Solidity"},
    "chord": {"unit": "m", "frame": "geomTurbo blade section",
              "meaning": "distance LE->TE of the pressure-side polyline"},
    "chord_target": {"unit": "m", "frame": "frozen legacy constant (0.06 m)"},
    "min_interior_thickness": {"unit": "RAW profile units (normalised, NOT m)",
                               "frame": "raw .dat profile",
                               "meaning": "do not read as metres"},
    "max_paired_thickness": {"unit": "RAW profile units (normalised, NOT m)",
                             "frame": "raw .dat profile",
                             "meaning": "do not read as metres"},
    "le_closure_error": {"unit": "RAW profile units", "frame": "raw .dat profile"},
    "te_closure_error": {"unit": "RAW profile units", "frame": "raw .dat profile"},
    "pressure_max_turn_angle_deg": {"unit": "deg"},
    "suction_max_turn_angle_deg": {"unit": "deg"},
    "pressure_max_discrete_curvature": {"unit": "1/m",
                                        "frame": "geomTurbo blade section"},
    "suction_max_discrete_curvature": {"unit": "1/m",
                                       "frame": "geomTurbo blade section"},
}

QC_SCALAR_KEYS = (
    "min_gap", "envelope_clearance", "periodicity", "blade_tangential_extent",
    "chord", "chord_target", "min_interior_thickness", "max_paired_thickness",
    "le_closure_error", "te_closure_error", "self_intersection",
    "adjacent_blade_intersection", "finite_ok", "span_min", "span_max",
    "span_section_coordinate_consistent", "profile_point_count",
    "pressure_max_turn_angle_deg", "suction_max_turn_angle_deg",
    "pressure_max_discrete_curvature", "suction_max_discrete_curvature",
)

FRAME_NOTE = {
    "profile_file": ".dat columns are 'xp yp xs ys' (pressure x, pressure y, "
                    "suction x, suction y) in raw normalised profile units",
    "plot_frame": "x = Z = chordwise, y = Y = tangential (same frame as the "
                  ".geomTurbo blade section)",
    "plot_scale": "raw profile uniformly scaled so chord = 0.06 m; all plotted "
                  "distances are therefore in metres",
    "geomturbo": "UNITS Meters, UNITS-FACTOR 1, cascade yes",
    "operation": "Incidence and Mach do NOT change the legacy blade geometry "
                 "(verified in V1); recorded for traceability only",
}

DISCLAIMER = [
    "2-D geometry views only: drawn from the real .dat / .geomTurbo coordinate "
    "data. These are NOT NUMECA/CFX meshes and NOT CFD results.",
    "Geometry QC PASS means the frozen geometry checks (geometry_qc_v1_hard) "
    "passed. It does NOT mean the blade is aerodynamically reasonable, and it "
    "does NOT mean a mesh can be generated.",
    "A negative envelope_clearance is a diagnostic number only, not a collision.",
    "The exploratory ranges of this review are NOT approved production ranges.",
    "Xthick / Tmax / Metal2 are non-dimensional parameters; they are never "
    "shown as metres.",
]


def build_parameters(case, qc_row, legacy, new, blade_meta, ranges_meta,
                     source_hashes):
    """One parameters.json dict (raw source values + real QC numbers)."""
    case_id = case["case_id"]
    profile_src = REVIEW_DIR / "geometry" / "profiles" / f"{case_id}.dat"
    geomturbo_src = REVIEW_DIR / "geometry" / "geomturbo" / f"{case_id}.geomTurbo"
    beyond = beyond_legacy(case, legacy)
    figure = lambda name: f"cases/{case_id}/{name}"          # noqa: E731

    return {
        "case_id": case_id,
        "folder": f"cases/{case_id}",
        "group": case["group"],
        "note": case["note"],
        "parameters": {key: float(case[key]) for key in ALL_PARAMS},
        "parameters_csv_raw": {key: case[key] for key in ALL_PARAMS},
        "parameter_kind": {
            "Xthick": "non-dimensional: chordwise fraction of maximum thickness",
            "Tmax": "non-dimensional: maximum thickness ratio (legacy profile "
                    "parameterisation)",
            "Metal2": "deg: exit metal angle (Metal1 = 53 deg frozen in the "
                      "geometry core)",
            "Solidity": "non-dimensional: chord / pitch (changes ONLY the "
                        ".geomTurbo periodicity, never the blade shape)",
            "Incidence": "deg: operating condition, does not change the geometry",
            "Mach": "non-dimensional: operating condition, does not change the "
                    "geometry",
        },
        "range_id": case["range_id"],
        "sampling_id": case["sampling_id"],
        "exploratory_ranges": {key: list(new[key]) for key in GEOMETRY_PARAMS},
        "legacy_ranges": {key: list(legacy[key]) for key in GEOMETRY_PARAMS},
        "ranges_source": "analysis/geometry_review/ranges_exploratory_v2.yaml",
        "ranges_status": ranges_meta.get("status", "EXPLORATORY_NOT_APPROVED"),
        "beyond_legacy": bool(beyond),
        "beyond_legacy_params": beyond,
        "builder_flags": {key: case.get(key, "") for key in
                          ("beyond_legacy", "new_boundary_params",
                           "multi_param_extreme", "at_new_lower", "at_new_upper")},
        "duplicate_blade_group": {
            "id": blade_meta["id"],
            "size": blade_meta["size"],
            "members": blade_meta["members"],
            "note": ("cases sharing (Xthick, Tmax, Metal2) have the same single "
                     "blade outline; they differ only in Solidity, i.e. in the "
                     "periodicity of the .geomTurbo")
            if blade_meta["size"] > 1 else
            "unique blade outline within this review package",
        },
        "geometry_generation": {
            "geometry_generated": True,
            "profile_file": figure(f"{case_id}.dat"),
            "geomturbo_file": figure(f"{case_id}.geomTurbo"),
            "profile_source": str(profile_src.relative_to(REPO)),
            "geomturbo_source": str(geomturbo_src.relative_to(REPO)),
            "profile_sha256": source_hashes["dat"]["sha256"],
            "geomturbo_sha256": source_hashes["geomTurbo"]["sha256"],
            "profile_bytes": source_hashes["dat"]["bytes"],
            "geomturbo_bytes": source_hashes["geomTurbo"]["bytes"],
            "produced_by": "code/02_generate_geometry.py (V2 run; not re-run for "
                           "this package)",
        },
        "geometry_qc": {
            "geometry_qc_status": pgr.qc_status(qc_row),
            "geometry_ok": (qc_row or {}).get("geometry_ok") == "1",
            "reason": (qc_row or {}).get("reason", ""),
            "qc_policy_id": (qc_row or {}).get("qc_policy_id", ""),
            "calibration_status": (qc_row or {}).get("calibration_status", ""),
            "report": "analysis/geometry_review/geometry_qc.csv (real output)",
            "produced_by": "code/03_geometry_qc.py (V2 run; not re-run for this "
                           "package)",
        },
        "qc_metrics": {key: num(qc_row, key) for key in QC_SCALAR_KEYS},
        "min_gap": num(qc_row, "min_gap"),
        "envelope_clearance": num(qc_row, "envelope_clearance"),
        "periodicity": num(qc_row, "periodicity"),
        "qc_policy_id": (qc_row or {}).get("qc_policy_id", ""),
        "units": UNIT_NOTES,
        "coordinate_frame": FRAME_NOTE,
        "figures": {
            "blade_profile": figure("blade_profile.png"),
            "cascade_3blade": figure("cascade_3blade.png"),
            "edge_details": figure("edge_details.png"),
            "overview": "00_all_cases_overview.png",
        },
        "disclaimer": DISCLAIMER,
        "human_acceptance": None,
        "human_comment": None,
    }


# ---------------------------------------------------------------------------
# per-case figures (single blade / 3-blade cascade / edge details)
# ---------------------------------------------------------------------------
def _legend_handles():
    from matplotlib.lines import Line2D
    return [
        Line2D([0], [0], color="#1f77b4", lw=1.8, label="pressure side (real coords)"),
        Line2D([0], [0], color="#1f77b4", lw=1.8, ls="--",
               label="suction side (real coords)"),
        Line2D([0], [0], color="#111111", lw=1.0, ls=":", label="meanline"),
        Line2D([0], [0], color="#7f7f7f", lw=1.0, ls="-.",
               label="chord (LE -> TE)"),
    ]


def fig_blade_profile(entry, case, qc_row, window, scale, out_path, dpi,
                      blade_meta, legacy):
    """Single blade, FULL window — identical physical window/scale for all cases."""
    x_lim, y_lim = window
    pressure, suction = entry["pressure"], entry["suction"]
    mid = meanline_of(pressure, suction)
    left, right, bottom, top = M_BLADE
    h_in = scale * (y_lim[1] - y_lim[0])
    fig = plt.figure(figsize=(left + right + BLADE_PANEL_IN, bottom + top + h_in))
    ax, _ = make_axes(fig, left, bottom, BLADE_PANEL_IN, x_lim, y_lim)

    color = pgr.status_color(qc_row)
    draw_pair(ax, pressure, suction, color, lw=1.8)
    ax.plot(mid[:, 0], mid[:, 1], color="#111111", lw=1.0, ls=":", zorder=4)
    ax.plot([pressure[0, 0], pressure[-1, 0]], [pressure[0, 1], pressure[-1, 1]],
            color="#7f7f7f", lw=1.0, ls="-.", zorder=2)
    for point, name, offset in ((pressure[0], "LE", (6, -13)),
                                (pressure[-1], "TE", (8, 6))):
        ax.plot([point[0]], [point[1]], marker="o", ms=4.5, mfc="white",
                mec="#111111", mew=1.1, zorder=6)
        ax.annotate(name, (point[0], point[1]), textcoords="offset points",
                    xytext=offset, fontsize=8.5, zorder=6)
    scale_bar(ax, x_lim, y_lim)
    ax.legend(handles=_legend_handles(), loc="upper right", fontsize=7,
              framealpha=0.9)

    beyond = beyond_legacy(case, legacy)
    pitch = num(qc_row, "periodicity")
    info = [f"{case['case_id']}   QC {pgr.qc_status(qc_row)}",
            f"group      : {case['group']}",
            f"Xthick     = {float(case['Xthick']):g}   [-]",
            f"Tmax       = {float(case['Tmax']):g}   [-]",
            f"Metal2     = {float(case['Metal2']):g}   [deg]",
            f"Solidity   = {float(case['Solidity']):g}   [-]",
            f"Incidence  = {float(case['Incidence']):g} deg   "
            f"Mach = {float(case['Mach']):g}",
            f"pitch      = {pitch:.5f} m" if pitch is not None else "pitch = n/a",
            f"blade group: {blade_meta['id']}   ({blade_meta['size']} case(s))"]
    if beyond:
        info.append("beyond legacy: " + ",".join(beyond))
    pgr.annotate(ax, "\n".join(info), fontsize=7.5)
    ax.set_title(f"{case['case_id']}  single blade profile — real 2-D geometry",
                 fontsize=10)
    put_footer(fig, FOOTER_BLADE, reserve_in=M_BLADE[2])
    return save_fixed(fig, out_path, dpi)


CASCADE_FOOTER = ("neighbour shift = real .geomTurbo PERIODICITY (0.06 / Solidity) along +Y — the same "
                  "periodic model as code/03_geometry_qc.py · equal aspect, no stretching · shaded band = "
                  "one pitch cell · blade scale as in blade_profile.png (canvas height follows the pitch)")


def fig_cascade_3blade(entry, case, qc_row, x_lim, scale, out_path, dpi,
                       blade_meta, legacy):
    """3 adjacent blades at the REAL periodicity of this case (no stretching)."""
    pressure, suction = entry["pressure"], entry["suction"]
    pitch = num(qc_row, "periodicity") or CHORD_TARGET / float(case["Solidity"])
    y0 = float(min(pressure[:, 1].min(), suction[:, 1].min()))
    y1 = float(max(pressure[:, 1].max(), suction[:, 1].max()))
    y_lim = (y0 - NEIGHBOUR_MARGIN * pitch, y1 + NEIGHBOUR_MARGIN * pitch)
    x_span = x_lim[1] - x_lim[0]
    y_span = y_lim[1] - y_lim[0]
    # equal aspect: cap the canvas height -> shrink the panel width by the same
    # factor (the blade is then drawn smaller, never stretched)
    w_in = min(BLADE_PANEL_IN, MAX_CASCADE_PANEL_IN * x_span / y_span)
    h_in = w_in * y_span / x_span
    scaled_note = ""
    if w_in < BLADE_PANEL_IN - 1e-9:
        scaled_note = (f" · panel drawn at {100.0 * w_in / BLADE_PANEL_IN:.0f}% of "
                       f"the blade_profile scale (canvas-height limit)")
    left, right, bottom, top = M_CASCADE
    fig = plt.figure(figsize=(left + right + w_in, bottom + top + h_in))
    ax, _ = make_axes(fig, left, bottom, w_in, x_lim, y_lim)

    ax.axhspan(y0, y0 + pitch, color="#dfe9f5", alpha=0.55, zorder=0)
    color = pgr.status_color(qc_row)
    for shift, alpha, lw in ((-pitch, 0.30, 1.3), (pitch, 0.30, 1.3),
                             (0.0, 1.0, 1.9)):
        draw_pair(ax, pressure + [0.0, shift], suction + [0.0, shift], color,
                  lw=lw, alpha=alpha, zorder=4 if shift == 0.0 else 2)
    for yy in (y0 - pitch, y0, y0 + pitch):
        ax.plot(x_lim, [yy, yy], color="#9aa0a6", lw=0.7, ls="-.", zorder=1)

    xref = x_lim[0] + (x_lim[1] - x_lim[0]) * 0.03
    ax.annotate("", xy=(xref, y0 + pitch), xytext=(xref, y0),
                arrowprops=dict(arrowstyle="<->", lw=1.1, color="#333333",
                                shrinkA=0, shrinkB=0), zorder=7)
    ax.text(xref + (x_lim[1] - x_lim[0]) * 0.012, y0 + pitch / 2,
            f"pitch\n{pitch:.5f} m", fontsize=7, va="center", zorder=7)

    env = num(qc_row, "envelope_clearance")
    gap = num(qc_row, "min_gap")
    info = [f"{case['case_id']}   QC {pgr.qc_status(qc_row)}",
            f"Solidity       = {float(case['Solidity']):g}   [-]",
            f"Xthick / Tmax  = {float(case['Xthick']):g} / "
            f"{float(case['Tmax']):g}",
            f"Metal2         = {float(case['Metal2']):g} deg",
            f"pitch (=0.06/S) = {pitch:.5f} m",
            (f"min_gap        = {gap:.5f} m" if gap is not None
             else "min_gap        = n/a"),
            (f"env. clearance = {env:+.5f} m" if env is not None
             else "env. clearance = n/a")]
    if env is not None and env < 0:
        info.append("envelope clearance < 0:\nDIAGNOSTIC only, NOT a collision")
    beyond = beyond_legacy(case, legacy)
    if beyond:
        info.append("beyond legacy: " + ",".join(beyond))
    pgr.annotate(ax, "\n".join(info), fontsize=7.5)
    ax.set_title(f"{case['case_id']}  3 adjacent blades (centre = this case, "
                 f"neighbours at +/- pitch)", fontsize=10)
    put_footer(fig, CASCADE_FOOTER + scaled_note, reserve_in=M_CASCADE[2])
    return save_fixed(fig, out_path, dpi)


EDGE_FOOTER = ("LE / TE square zoom windows of 0.012 m x 0.012 m, identical for all "
               "40 cases · scale = 4x the blade_profile.png scale · equal aspect "
               "(no stretching) · real .dat coordinates in metres")


def fig_edge_details(entry, case, qc_row, scale, out_path, dpi, blade_meta,
                     legacy):
    """LE + TE zoom, square windows -> identical window/scale for all cases."""
    pressure, suction = entry["pressure"], entry["suction"]
    mid = meanline_of(pressure, suction)
    panels = (("LE detail — leading edge", pressure[0],
               "le_closure_error"), ("TE detail — trailing edge", pressure[-1],
                                     "te_closure_error"))
    panel_in = 2 * ZOOM_HALF_M * scale
    left, right, bottom, top = M_EDGE
    gap = 0.85
    fig_w = left + right + 2 * panel_in + gap
    fig = plt.figure(figsize=(fig_w, bottom + top + panel_in))
    for index, (label, centre, metric) in enumerate(panels):
        x_in = left + index * (panel_in + gap)
        x_lim = (centre[0] - ZOOM_HALF_M, centre[0] + ZOOM_HALF_M)
        y_lim = (centre[1] - ZOOM_HALF_M, centre[1] + ZOOM_HALF_M)
        ax, _ = make_axes(fig, x_in, bottom, panel_in, x_lim, y_lim)
        ax.xaxis.set_major_locator(MultipleLocator(0.002))
        ax.yaxis.set_major_locator(MultipleLocator(0.002))
        color = pgr.status_color(qc_row)
        draw_pair(ax, pressure, suction, color, lw=1.9)
        ax.plot(mid[:, 0], mid[:, 1], color="#111111", lw=1.0, ls=":", zorder=4)
        ax.plot([centre[0]], [centre[1]], marker="o", ms=4.5, mfc="white",
                mec="#111111", mew=1.1, zorder=6)
        ax.set_title(label, fontsize=9.5)
        value = num(qc_row, metric)
        pgr.annotate(ax, (f"{case['case_id']}\n"
                          f"window 0.012 x 0.012 m\n"
                          f"{metric}\n= "
                          + (f"{value:.3g}" if value is not None else "n/a")
                          + "  (raw units)"), fontsize=7)
        if index == 0:
            ax.legend(handles=_legend_handles(), loc="lower left", fontsize=6.5,
                      framealpha=0.9)

    fig.suptitle(f"{case['case_id']}  edge details — real 2-D geometry, "
                 f"QC {pgr.qc_status(qc_row)}   |   "
                 f"Xthick={float(case['Xthick']):g}  Tmax={float(case['Tmax']):g}  "
                 f"Metal2={float(case['Metal2']):g}  "
                 f"Solidity={float(case['Solidity']):g}", fontsize=10)
    put_footer(fig, EDGE_FOOTER, reserve_in=M_EDGE[2])
    return save_fixed(fig, out_path, dpi)


OVERVIEW_FOOTER = (
    "ALL 40 review cases · each panel = the real single-blade outline of that case · "
    "IDENTICAL window and scale in every panel (same as blade_profile.png) · equal "
    "aspect, metres on both axes · background tint = experiment group · solid = "
    "pressure side, dashed = suction side · badge = frozen Geometry QC (PASS/FAIL "
    "only, no engineering judgement) · \"BLxx\" = identical blade outline (same "
    "Xthick/Tmax/Metal2), differing ONLY in Solidity/pitch — see cascade_3blade.png")


def overview_layout(window):
    """Exact inches-layout of the 40-panel overview (shared with the self-check)."""
    x_lim, y_lim = window
    panel_in = OVERVIEW_PANEL_IN
    panel_h = panel_in * (y_lim[1] - y_lim[0]) / (x_lim[1] - x_lim[0])
    gap_x, gap_y = 0.34, 0.66
    left, right, bottom, top = M_OVERVIEW
    return {
        "panel_in": panel_in, "panel_h": panel_h, "gap_x": gap_x, "gap_y": gap_y,
        "left": left, "bottom": bottom,
        "fig_w": left + right + OVERVIEW_COLS * panel_in
        + (OVERVIEW_COLS - 1) * gap_x,
        "fig_h": bottom + top + OVERVIEW_ROWS * (panel_h + gap_y) - gap_y,
        "x_in": [left + col * (panel_in + gap_x) for col in range(OVERVIEW_COLS)],
        "y_in": [bottom + row * (panel_h + gap_y) for row in range(OVERVIEW_ROWS)],
    }


def overview_panel_boxes(window, dpi):
    """Pixel boxes (l, t, r, b) of the overview panels, top row first."""
    layout = overview_layout(window)
    boxes = []
    for row in range(OVERVIEW_ROWS):
        y_in = layout["y_in"][OVERVIEW_ROWS - 1 - row]
        top = (layout["fig_h"] - (y_in + layout["panel_h"])) * dpi
        for col in range(OVERVIEW_COLS):
            left = layout["x_in"][col] * dpi
            boxes.append((int(left), int(top),
                          int(left + layout["panel_in"] * dpi),
                          int(top + layout["panel_h"] * dpi)))
    return boxes


def fig_overview(entries, cases_ordered, qc, blade_table, window, out_path, dpi,
                 legacy):
    """5 rows x 8 cols = all 40 cases, same window/scale as blade_profile.png."""
    x_lim, y_lim = window
    layout = overview_layout(window)
    panel_in, panel_h = layout["panel_in"], layout["panel_h"]
    fig = plt.figure(figsize=(layout["fig_w"], layout["fig_h"]))

    for index, case in enumerate(cases_ordered):
        row, col = divmod(index, OVERVIEW_COLS)
        case_id = case["case_id"]
        entry = entries[case_id]
        qc_row = qc.get(case_id, {})
        blade_meta = blade_table[case_id]
        ax, _ = make_axes(fig, layout["x_in"][col],
                          layout["y_in"][OVERVIEW_ROWS - 1 - row],
                          panel_in, x_lim, y_lim,
                          facecolor=GROUP_TINT.get(case["group"], "white"))
        draw_pair(ax, entry["pressure"], entry["suction"], pgr.status_color(qc_row),
                  lw=1.5)
        beyond = beyond_legacy(case, legacy)
        tag = f"  {blade_meta['id']}"
        if blade_meta["size"] > 1:
            tag += f" x{blade_meta['size']} (Solidity only)"
        ax.set_title(f"{index + 1:02d}  {case_id}   QC {pgr.qc_status(qc_row)}\n"
                     f"Xthick={float(case['Xthick']):g}  Tmax={float(case['Tmax']):g}  "
                     f"Metal2={float(case['Metal2']):g}  "
                     f"Sol={float(case['Solidity']):g}\n"
                     f"{case['group']}{tag}"
                     + ("\nbeyond legacy" if beyond else ""), fontsize=6.6)
        ax.tick_params(labelsize=5.5)
        ax.set_xlabel("")
        ax.set_ylabel("")
        pgr.draw_badge(ax, qc_row, fontsize=6)

    fig.suptitle(f"00_all_cases_overview — Geometry Range Review V2 (EXPLORATORY "
                 f"ranges, not approved) — all {len(cases_ordered)} cases, real "
                 f"generated geometry", fontsize=13,
                 y=1 - 0.35 / layout["fig_h"])
    put_footer(fig, OVERVIEW_FOOTER, fontsize=6.6, reserve_in=M_OVERVIEW[2])
    return save_fixed(fig, out_path, dpi)


# ---------------------------------------------------------------------------
# 00_case_index.csv
# ---------------------------------------------------------------------------
INDEX_COLUMNS = [
    "order_in_package", "panel_row", "panel_col", "case_id", "folder",
    "Xthick", "Tmax", "Metal2", "Solidity", "Incidence", "Mach",
    "group", "note", "range_id", "sampling_id",
    "beyond_legacy", "beyond_legacy_params", "at_new_lower", "at_new_upper",
    "multi_param_extreme",
    "geometry_generated", "geometry_qc_status", "geometry_ok", "reason",
    "qc_policy_id", "calibration_status",
    "min_gap_m", "envelope_clearance_m", "periodicity_m", "chord_m",
    "blade_group_id", "blade_group_size", "blade_group_members",
    "parameters_json", "profile_dat", "geomturbo",
    "blade_profile_png", "cascade_3blade_png", "edge_details_png",
    "human_acceptance", "human_comment",
]


def write_case_index(path, cases_ordered, qc, blade_table, legacy):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(INDEX_COLUMNS)
        for index, case in enumerate(cases_ordered):
            case_id = case["case_id"]
            qc_row = qc.get(case_id, {})
            meta = blade_table[case_id]
            row, col = divmod(index, OVERVIEW_COLS)
            beyond = beyond_legacy(case, legacy)
            writer.writerow([
                index + 1, row + 1, col + 1, case_id, f"cases/{case_id}",
                case["Xthick"], case["Tmax"], case["Metal2"], case["Solidity"],
                case["Incidence"], case["Mach"],
                case["group"], case["note"], case["range_id"], case["sampling_id"],
                1 if beyond else 0, "|".join(beyond),
                case.get("at_new_lower", ""), case.get("at_new_upper", ""),
                case.get("multi_param_extreme", ""),
                1, pgr.qc_status(qc_row), qc_row.get("geometry_ok", ""),
                qc_row.get("reason", ""), qc_row.get("qc_policy_id", ""),
                qc_row.get("calibration_status", ""),
                qc_row.get("min_gap", ""), qc_row.get("envelope_clearance", ""),
                qc_row.get("periodicity", ""), qc_row.get("chord", ""),
                meta["id"], meta["size"], "|".join(meta["members"]),
                f"cases/{case_id}/parameters.json",
                f"cases/{case_id}/{case_id}.dat",
                f"cases/{case_id}/{case_id}.geomTurbo",
                f"cases/{case_id}/blade_profile.png",
                f"cases/{case_id}/cascade_3blade.png",
                f"cases/{case_id}/edge_details.png",
                "", "",
            ])
    return path


def make_zip(pkg_dir, zip_path):
    """ZIP containing only the review package (top-level folder: senior_review_v2)."""
    if zip_path.exists():
        zip_path.unlink()
    files = sorted(p for p in pkg_dir.rglob("*") if p.is_file())
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=6) as archive:
        for path in files:
            archive.write(path, arcname=str(Path(pkg_dir.name) / path.relative_to(pkg_dir)))
    return zip_path, len(files)


def drawn_pixels(path: Path, box=None, threshold=120):
    """Count strongly coloured (non-gray, non-background) pixels = drawn geometry
    lines (blade blue / red). Light gray grid lines and pale panel tints are
    excluded; returns None when PIL is unavailable."""
    try:
        from PIL import Image
    except ImportError:                                        # pragma: no cover
        return None
    with Image.open(path) as image:
        image = image.convert("RGB")
        if box is not None:
            image = image.crop(box)
        array = np.asarray(image).astype(int)
    low = array.min(axis=2)
    saturation = array.max(axis=2) - low
    return int(((low < threshold) & (saturation > 40)).sum())


# ---------------------------------------------------------------------------
# self-check
# ---------------------------------------------------------------------------
def snapshot_sources(cases):
    """sha256 of every read-only input this package depends on."""
    files = [DEFAULT_CASES, DEFAULT_QC, DEFAULT_RANGES]
    for case in cases:
        case_id = case["case_id"]
        files.append(REVIEW_DIR / "geometry" / "profiles" / f"{case_id}.dat")
        files.append(REVIEW_DIR / "geometry" / "geomturbo" / f"{case_id}.geomTurbo")
    return {str(path): sha256_file(path) for path in files}


def png_ok(path: Path):
    """(ok, width, height) from the PNG signature + IHDR (no PIL needed)."""
    with open(path, "rb") as handle:
        head = handle.read(33)
    if not head.startswith(b"\x89PNG\r\n\x1a\n") or head[12:16] != b"IHDR":
        return False, 0, 0
    width = int.from_bytes(head[16:20], "big")
    height = int.from_bytes(head[20:24], "big")
    return True, width, height


REQUIRED_JSON_KEYS = (
    "case_id", "group", "parameters", "range_id", "sampling_id",
    "beyond_legacy", "beyond_legacy_params", "geometry_generation",
    "geometry_qc", "min_gap", "envelope_clearance", "periodicity",
    "qc_policy_id", "human_acceptance", "human_comment",
)


def self_check(pkg_dir, cases_ordered, qc, blade_table, before, dpi, window):
    problems, notes = [], []
    expect_ids = [c["case_id"] for c in cases_ordered]
    folders = sorted(p.name for p in (pkg_dir / "cases").iterdir() if p.is_dir())
    if folders != sorted(expect_ids):
        problems.append(f"case folders mismatch: {len(folders)} folders")
    for case in cases_ordered:
        case_id = case["case_id"]
        folder = pkg_dir / "cases" / case_id
        for name in ("parameters.json", "blade_profile.png", "cascade_3blade.png",
                     "edge_details.png", f"{case_id}.dat", f"{case_id}.geomTurbo"):
            if not (folder / name).is_file():
                problems.append(f"missing {case_id}/{name}")
        for name in ("blade_profile.png", "cascade_3blade.png", "edge_details.png"):
            path = folder / name
            if path.is_file():
                ok, width, height = png_ok(path)
                if not ok:
                    problems.append(f"not a readable PNG: {path}")
                elif min(width, height) < 800:
                    problems.append(f"PNG too small ({width}x{height}): {path}")
        payload_path = folder / "parameters.json"
        if payload_path.is_file():
            with open(payload_path, encoding="utf-8") as handle:
                payload = json.load(handle)
            missing = [key for key in REQUIRED_JSON_KEYS if key not in payload]
            if missing:
                problems.append(f"{case_id}/parameters.json missing {missing}")
            if payload["case_id"] != case_id:
                problems.append(f"{case_id}: parameters.json case_id mismatch")
            if payload.get("human_acceptance") is not None or \
                    payload.get("human_comment") is not None:
                problems.append(f"{case_id}: human_* must be null")
            for key in ALL_PARAMS:
                if float(payload["parameters"][key]) != float(case[key]):
                    problems.append(f"{case_id}: parameter {key} value drift")
        for name, source in ((f"{case_id}.dat",
                              REVIEW_DIR / "geometry" / "profiles" / f"{case_id}.dat"),
                             (f"{case_id}.geomTurbo",
                              REVIEW_DIR / "geometry" / "geomturbo" /
                              f"{case_id}.geomTurbo")):
            copy_path = folder / name
            if copy_path.is_file() and sha256_file(copy_path) != sha256_file(source):
                problems.append(f"{case_id}/{name} is not a verbatim copy")

    index_path = pkg_dir / "00_case_index.csv"
    if not index_path.is_file():
        problems.append("missing 00_case_index.csv")
    else:
        with open(index_path, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if [row["case_id"] for row in rows] != expect_ids:
            problems.append("00_case_index.csv case order/content mismatch")
        if len(rows) != len(expect_ids):
            problems.append("00_case_index.csv row count mismatch")
        if any(row["human_acceptance"] or row["human_comment"] for row in rows):
            problems.append("00_case_index.csv human columns must be empty")

    overview = pkg_dir / "00_all_cases_overview.png"
    if not overview.is_file():
        problems.append("missing 00_all_cases_overview.png")
    else:
        ok, width, height = png_ok(overview)
        if not ok:
            problems.append("00_all_cases_overview.png unreadable")
        notes.append(f"overview PNG {width}x{height} px @ {dpi} dpi")

    other_png = [p for p in pkg_dir.rglob("*.png")
                 if p.name != "00_all_cases_overview.png"]
    if len(other_png) != 3 * len(expect_ids):
        problems.append(f"expected {3 * len(expect_ids)} per-case PNGs, "
                        f"found {len(other_png)}")

    for path, digest in before.items():
        if sha256_file(Path(path)) != digest:
            problems.append(f"READ-ONLY SOURCE MODIFIED: {path}")

    for case_id in expect_ids:
        if case_id.startswith("C800"):
            problems.append(f"V1 review id inside the V2 package: {case_id}")
    if "C800" in str(pkg_dir.name):
        problems.append("package folder looks like the V1 block")

    for case_id in expect_ids:
        meta = blade_table[case_id]
        if meta["size"] > 1:
            for member in meta["members"]:
                if member not in expect_ids:
                    problems.append(f"blade group {meta['id']} member missing")
            break

    # content check: geometry really drawn in every per-case and overview image
    thin = []
    for case in cases_ordered:
        path = pkg_dir / "cases" / case["case_id"] / "blade_profile.png"
        drawn = drawn_pixels(path) if path.is_file() else None
        if drawn is not None and drawn < 1000:
            thin.append(f"{case['case_id']} ({drawn} px)")
    if thin:
        problems.append(f"blade_profile.png looks empty for: {thin}")

    if overview.is_file():
        boxes = overview_panel_boxes(window, dpi)
        empty = []
        for index, case in enumerate(cases_ordered):
            left, top, right, bottom = boxes[index]
            inner = (left + int(0.02 * (right - left)), top + int(0.02 * (bottom - top)),
                     left + int(0.95 * (right - left)), top + int(0.75 * (bottom - top)))
            drawn = drawn_pixels(overview, box=inner)
            if drawn is not None and drawn < 300:
                empty.append(f"panel {index + 1} {case['case_id']} ({drawn} px)")
        if empty:
            problems.append(f"overview panels without drawn geometry: {empty}")
        else:
            notes.append(f"overview content check: all {len(cases_ordered)} panels "
                         f"contain drawn blade geometry")
    return problems, notes


# ---------------------------------------------------------------------------
# README.md
# ---------------------------------------------------------------------------
def _readme_head(stats):
    group_rows = "\n".join(
        f"| {name} | {count} | {text} |"
        for name, count, text in stats["group_rows"])
    range_rows = "\n".join(
        f"| {name} | {legacy} | {exploratory} | {note} |"
        for name, legacy, exploratory, note in stats["range_rows"])
    return f"""# Geometry Range Review V2 — 40 Case 师兄评审包（叶型几何合理性评审）

> 本目录由 `tools/make_senior_review_v2.py` 生成。**只做评审材料整理与可视化**：
> 没有重新生成几何、没有重跑 Geometry QC、没有修改冻结造型核心、没有运行
> NUMECA / CFX、没有新增参数扫描。
>
> ```text
> range_id    = {stats["range_id"]}
> sampling_id = {stats["sampling_id"]}
> case_id     = {stats["first_id"]} .. {stats["last_id"]}   (V2 专用号段)
> ```
>
> 号段隔离：V2 评审用 `C81xxxx`，与 V1 评审号段（已归档在
> `analysis/geometry_review/archive/v1_legacy_review/`）、正式生产号段
> `C0000xx..`、NUMECA bring-up 号段 `C900001` 均不重叠，**本包内不含任何
> V1 评审数据**。

---

## 1. 为什么做这次评审

我们准备把研究范围扩展到比历史 1891 Case **更宽**的几何参数空间。
程序无法替师兄判断"这个叶型在工程上是否合理"，因此这里**不做任何程序筛选**，
而是把探索范围内生成的 **全部 {stats["n_cases"]} 个 Case** 的真实叶型交给师兄逐一观察，
由师兄按自己的工程标准判断哪些参数范围可用、哪些明显不合理。

本包不是正式数据集，也不冻结任何范围。

---

## 2. 四个阶段必须严格区分（读图时不要混淆）

| 阶段 | 含义 | 本次状态 |
|---|---|---|
| ① 几何生成成功 | `.dat` / `.geomTurbo` 真实存在于磁盘 | **{stats["n_cases"]} / {stats["n_cases"]} 成功** |
| ② Geometry QC 通过 | 冻结 QC（`geometry_qc_v1_hard`）判定 `geometry_ok = 1` | **{stats["qc_pass"]} / {stats["n_cases"]} PASS**，`reason = OK` |
| ③ 人工判断工程合理 | 师兄的工程判断 | **未填写**（索引/JSON 的 `human_*` 列留空） |
| ④ 网格 / CFD 可行性 | 能否画网格、能否收敛 | **未验证**（本次未运行任何 CFD 求解器） |

`00_case_index.csv` 中 `geometry_generated` 与 `geometry_qc_status` 是两列，
正是为了防止把①和②混为一谈。

---

## 3. 探索范围 vs 历史范围

| 参数 | 历史范围（1891 Case） | 本次探索范围 | 说明 |
|---|---|---|---|
{range_rows}

补充说明：

```text
Metal1 = {stats["metal1"]} deg  —— 冻结常量，本次未修改（入口中弧线角）
Incidence / Mach —— 已冻结为 0 deg / 0.5，且不改变叶型几何（V1 已验证）
Solidity —— 只改变 .geomTurbo 的 periodicity = 0.06 / Solidity，不改变单叶型
```

---

## 4. 这 {stats["n_cases"]} 个 Case 是怎么挑的

按"边界优先、尽量分散"构造（`make_review_cases.py`，确定性、无随机漂移）：

| 组别 | 数量 | 内容 |
|---|---|---|
{group_rows}

**重复单叶型说明（重要）**：

```text
不同的 (Xthick, Tmax, Metal2) 组合数 = {stats["unique_blades"]} 个
{stats["n_cases"]} 个 Case 中有 {stats["n_cases"] - stats["unique_blades"]} 个是"同一单叶型 + 不同 Solidity"
```

因此本包中 **{stats["unique_blades"]} 个不同的单叶型** 被展开成 {stats["n_cases"]} 个 Case。
相同单叶型的叶子在总览图与索引里有相同的分组 ID（`BLxx`），
**不要误认为产生了新的独立叶型**——它们唯一区别是栅距（pitch）：

```text
{stats["dup_group_text"]}
```

---

"""


def _readme_mid(stats):
    neg_env = "\n".join(
        f"  {case_id}: envelope_clearance = {value:+.6g} m   (min_gap = {gap:.6g} m)"
        for case_id, value, gap in stats["neg_env"])
    file_rows = "\n".join(
        f"| `{name}` | {desc} |" for name, desc in stats["file_rows"])
    return f"""## 5. 目录结构

```text
senior_review_v2/
├── README.md                     本文件
├── 00_all_cases_overview.png     全部 {stats["n_cases"]} 个 Case 总览（{stats["rows"]} 行 × {stats["cols"]} 列，无遗漏）
├── 00_case_index.csv             {stats["n_cases"]} 行索引（含参数、分组、QC、重复叶型组、人工评审空列）
└── cases/
    └── {stats["first_id"]}/ .. {stats["last_id"]}/     每个 Case 一个文件夹
        ├── parameters.json        该 Case 的全部参数 + QC 数值 + 单位说明 + 留空人工列
        ├── blade_profile.png      单叶型（压力面/吸力面/中弧线/前缘/尾缘）
        ├── cascade_3blade.png     按真实 pitch 排列的三叶片叶栅
        ├── edge_details.png       前缘 / 尾缘局部放大
        ├── {stats["first_id"]}.dat          原始几何（逐字节复制，未修改）
        └── {stats["first_id"]}.geomTurbo    原始几何（逐字节复制，未修改）
```

| 文件 | 说明 |
|---|---|
{file_rows}

---

## 6. 图片说明与单位约定

### 6.1 三张单 Case 图

| 图 | 内容 | 看点 |
|---|---|---|
| `blade_profile.png` | 单叶型全貌：压力面（实线）、吸力面（虚线）、中弧线（点线）、弦线（点划线）、LE/TE 标记、0.01 m 比例尺 | **{stats["n_cases"]} 张图使用完全相同的物理坐标窗口与比例**，可直接叠加比较形状差异 |
| `cascade_3blade.png` | 中间为本 Case 叶型，上下相邻叶型按**该 Case 真实栅距**沿 +Y 平移；标出 S、pitch、min_gap、envelope_clearance | 叶栅通道形态；Solidity 越大通道越窄 |
| `edge_details.png` | 前缘、尾缘各一个 {stats["zoom_window"]} 的方形放大窗口（**4× 于 blade_profile 比例**） | 前尾缘小圆是否光滑、有无尖角/自交 |

`00_all_cases_overview.png`：**{stats["rows"]} 行 × {stats["cols"]} 列 = 全部 {stats["n_cases"]} 个 Case**，
顺序 = 实验组顺序（A→B→C→D），每个子图给出真实单叶轮廓、Case ID、
Xthick / Tmax / Metal2 / Solidity、QC 状态与重复叶型分组 ID。
所有子图与 `blade_profile.png` 使用同一窗口与比例，因此可以直接横比趋势。

### 6.2 坐标与单位（容易出错，请务必看这一节）

```text
坐标系 : x = Z = 弦向（chordwise），y = Y = 切向（tangential）
         与 .geomTurbo 的 blade section 完全一致（.geomTurbo: UNITS Meters）
缩放   : .dat 是原始归一化 profile 坐标（列顺序 xp yp xs ys）；
         绘图时统一缩放到 chord = 0.06 m（= 冻结的 CHORD_TARGET），
         因此图中所有长度单位都是 m，可以直接量取。
参数   : Xthick / Tmax / Metal2 / Solidity 是无量纲/角度参数，
         永远不要读成米（图注里也标了 [-] 或 [deg]）。
```

**不要把未缩放的厚度数值当成米**：

```text
min_interior_thickness, max_paired_thickness  —— 来自原始 .dat profile，
   单位是"原始归一化单位"，不是 m
（min_gap / envelope_clearance / periodicity / chord / blade_tangential_extent
   来自 .geomTurbo 的物理尺度，单位才是 m）

每个 parameters.json 的 "units" 字段逐项写明了单位与所属坐标系。
```

### 6.3 三张图的坐标一致性约定（避免误读）

```text
blade_profile.png : 全部 {stats["n_cases"]} 张 = 同一窗口 + 同一比例（完全可比）
edge_details.png  : 全部 {stats["n_cases"]} 张 = 同一 0.012 m 方形窗口 + 同一比例（完全可比）
cascade_3blade.png: 叶片比例与 blade_profile 相同（等比、绝不拉伸），
                    但画布高度随该 Case 的 pitch 变化（pitch 大 → 画布更高），
                    因此各 Case 的"米/像素"不同 —— 请用图中标注的 pitch 数值对比，
                    而不是用像素间距对比叶栅。
```

所有图片都是**由真实坐标数据绘制的二维几何视图**，不是 NUMECA 网格，
也不是 CFD 结果。

---

## 7. 读图前必看的声明

```text
1) 二维几何视图：来自真实 .dat / .geomTurbo 坐标；不是网格、不是 CFD 结果。
2) QC PASS 只代表几何硬门（geometry_qc_v1_hard）通过，
   不代表气动合理，也不代表能画网格 / 能收敛。
3) envelope_clearance < 0 只是诊断量（= periodicity − 叶片切向尺寸），
   不是叶片碰撞。硬门是 min_gap > 0：本次 {stats["n_cases"]}/{stats["n_cases"]} 全部满足
   （min_gap 范围 {stats["min_gap_range"]} m）。
4) Xthick / Tmax / Metal2 是无量纲参数，从不以米标注。
5) 本包的探索范围未经批准，不是正式生产范围；不冻结任何范围。
```

本次 `envelope_clearance < 0` 的 Case 共 {stats["neg_env_count"]} 个（诊断提示，非失败）：

```text
{neg_env}
```

---

"""


def _readme_tail(stats):
    source_rows = "\n".join(
        f"| `{path}` | {desc} |" for path, desc in stats["source_rows"])
    check_rows = "\n".join(f"- [x] {line}" for line in stats["checks"])
    return f"""## 8. 如何进行人工评审（师兄请看这里）

**建议流程（30–60 分钟）：**

```text
第 1 步  打开 00_all_cases_overview.png
         先看整体趋势：{stats["n_cases"]} 个叶型按实验组顺序排列，
         同一窗口、同一比例，形状差异可以直接横比。
第 2 步  打开 00_case_index.csv
         一行一个 Case，含六维参数、实验组、是否超出历史范围、QC 状态、
         重复叶型分组 ID（BLxx）。先扫一遍"超出历史范围"的 Case。
第 3 步  对感兴趣的 Case 打开 cases/C8100xx/ 文件夹
         blade_profile.png 看单叶型；cascade_3blade.png 看叶栅通道；
         edge_details.png 看前尾缘小圆。
第 4 步  填写评价
         在 00_case_index.csv 最后两列填写（不要改动其它列）：
           human_acceptance : 建议取值 accept / accept_with_caution /
                              reject / unsure
           human_comment    : 自由文字（例如"Solidity>2.2 时通道过窄"）
         也可以直接编辑对应 cases/C8100xx/parameters.json 的
         human_acceptance / human_comment 两个字段（当前为 null）。
第 5 步  如果某处需要更细的局部放大，请给出 case_id + 区域
         （例如"C810032 尾缘再放大 4 倍"），我们可以追加出一张放大图。
```

**建议的重点观察点：**

```text
a) Xthick 取 0.10 / 0.60 时，叶型是否还像压气机叶栅（厚度峰位置是否合理）
b) Tmax 取 0.025 / 0.095 时，是否过薄或过厚
c) Metal2 = 0 deg / 32 deg 时，转角是否合理（入口角固定 53 deg 不变）
d) Solidity 0.7 / 2.5（尤其与 Metal2 联合的 C 组）时，叶栅通道是否过宽/过窄
e) 前缘/尾缘小圆是否光滑，有无尖角或明显不光滑
f) 哪些参数组合"明显不可用"，请直接标 reject（这类信息比 accept 更有价值）
```

请注意：**不要**修改 `cases/*/*.dat`、`cases/*/*.geomTurbo` 与任何 PNG；
人工评价只写在索引 CSV 或 `parameters.json` 的 `human_*` 字段里。

---

## 9. 数据来源（只读，本次未修改）

| 源文件 | 说明 |
|---|---|
{source_rows}

本包的构建是**只读复用**：脚本在开始与结束时对上述源文件逐一比对 sha256，
确认源文件未被修改（见第 10 节自检结果）。每个 `parameters.json` 里也记录了
该 Case 的 `.dat` / `.geomTurbo` 源路径与 sha256。

参考命令（**本次未执行**，仅记录当时的生成方式）：

```bash
# 参数表
conda run -n ai4s python analysis/geometry_review/make_review_cases.py
# 几何（dry-run 后正式）
conda run -n ai4s python code/02_generate_geometry.py \\
    --input analysis/geometry_review/review_cases.csv \\
    --template legacy/blade_batch_generation_template.geomTurbo \\
    --output analysis/geometry_review/geometry
# QC
conda run -n ai4s python code/03_geometry_qc.py \\
    --input analysis/geometry_review/review_cases.csv \\
    --geometry analysis/geometry_review/geometry \\
    --output analysis/geometry_review/geometry_qc.csv
# 本评审包（只读取上面的结果）
conda run -n ai4s python tools/make_senior_review_v2.py
```

---

## 10. 文件清单与自检结果

```text
Case 文件夹            : {stats["n_cases"]} / {stats["n_cases"]}
parameters.json        : {stats["n_cases"]} / {stats["n_cases"]}
单 Case PNG            : {stats["png_per_case"]}
总览 PNG               : 1（{stats["overview_size"]}）
原始 .dat 复制         : {stats["n_cases"]} / {stats["n_cases"]}
原始 .geomTurbo 复制   : {stats["n_cases"]} / {stats["n_cases"]}
索引行数               : {stats["n_cases"]}
图片分辨率             : >= {stats["dpi"]} dpi
```

自检项：

{check_rows}

---

## 11. 与 V1 评审包的关系

```text
V1（历史范围 30 Case，C800001..C800030）已归档，未修改：
    analysis/geometry_review/archive/v1_legacy_review/
V2（探索范围 {stats["n_cases"]} Case，{stats["first_id"]}..{stats["last_id"]}）：
    本目录
两者的 case_id 号段、range_id、sampling_id 完全不同，不会混淆。
```

---

*本包只用于人工几何合理性评审；不构成正式数据集，不冻结生产范围。*
"""


def write_readme(path, stats):
    Path(path).write_text(_readme_head(stats) + _readme_mid(stats)
                          + _readme_tail(stats), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
METAL1_DEG = 53.0            # frozen geometry-core constant (recorded, unchanged)


def _stats(pkg_dir, cases_ordered, qc, groups, frame, new, legacy, ranges_meta,
           before, problems, notes, dpi):
    n = len(cases_ordered)
    ids = [c["case_id"] for c in cases_ordered]
    blade_table, _ = blade_group_table(cases_ordered)
    unique_blades = len(groups)
    dup = [g for g in groups if len(g["members"]) > 1]
    neg = [(c["case_id"], float(qc[c["case_id"]]["envelope_clearance"]),
            float(qc[c["case_id"]]["min_gap"]))
           for c in cases_ordered
           if qc.get(c["case_id"], {}).get("envelope_clearance", "") != ""
           and float(qc[c["case_id"]]["envelope_clearance"]) < 0]
    gaps = [float(qc[c["case_id"]]["min_gap"]) for c in cases_ordered]
    checks = [
        f"Case 文件夹 {n}/{n} 存在且命名与 case_id 一致",
        f"parameters.json {n}/{n} 存在，必填字段（参数 / range_id / 生成状态 / "
        f"QC 状态 / min_gap / envelope_clearance / periodicity / qc_policy_id / "
        f"human_*）齐全",
        f"单 Case PNG {3 * n} 张（每 Case 3 张）全部存在且可解码",
        f"总览 PNG 覆盖全部 {n} 个 Case（{OVERVIEW_ROWS} 行 × "
        f"{OVERVIEW_COLS} 列，无遗漏）",
        f"原始 .dat {n} 个、.geomTurbo {n} 个已复制且 sha256 与源文件一致"
        f"（逐字节未修改）",
        f"00_case_index.csv {n} 行，case_id 与文件夹 / 图片 / JSON 一一对应",
        "索引与 JSON 中的 human_acceptance / human_comment 全部为空"
        "（等待师兄填写）",
        f"只读校验：{len(before)} 个源文件（评审参数表 / QC 报告 / ranges / "
        f"每个 Case 的 .dat 与 .geomTurbo）在打包前后 sha256 未变化",
        "包内不含 V1 评审号段（C800xxx）数据，与 V1 归档完全隔离",
    ]
    if problems:
        checks.append(f"⚠ 自检发现 {len(problems)} 个问题，需人工查看输出日志")
    else:
        checks.append("自检结论：全部检查项通过（详见构建终端的 self-check 输出）")
    overview = pkg_dir / "00_all_cases_overview.png"
    _, width, height = png_ok(overview) if overview.is_file() else (False, 0, 0)

    group_rows = [
        ("A_single_param", sum(1 for c in cases_ordered
                               if c["group"] == "A_single_param"),
         "单参数新旧边界扫描（Xthick / Tmax / Metal2 / Solidity 各取新旧上下限，其余取历史中点）"),
        ("B_corner", sum(1 for c in cases_ordered if c["group"] == "B_corner"),
         "(Xthick, Tmax, Metal2) 探索范围的 2^3 个极端角点，Solidity = 1.5"),
        ("C_coupled", sum(1 for c in cases_ordered if c["group"] == "C_coupled"),
         "Solidity × Metal2 联合边界（同一单叶型配不同栅距，Solidity = 0.7 / 2.5）"),
        ("C_combined", sum(1 for c in cases_ordered if c["group"] == "C_combined"),
         "多参数同时取极端（四维极端组合）"),
        ("D_maximin", sum(1 for c in cases_ordered if c["group"] == "D_maximin"),
         "确定性 maximin 分散补充样本（seed 20261015）"),
    ]
    group_rows.append(("合计", n, "全部 Case 一个不漏地进入本评审包"))
    range_rows = [
        ("Xthick", "0.15 – 0.45", "0.10 – 0.60", "无量纲，最大厚度弦向位置"),
        ("Tmax", "0.04 – 0.07", "0.025 – 0.095", "无量纲，最大厚度比"),
        ("Metal2", "6 – 24 deg", "0 – 32 deg", "出口金属角（入口角 Metal1 冻结）"),
        ("Solidity", "1.0 – 2.0", "0.7 – 2.5", "只改变栅距 = 0.06 / Solidity"),
        ("Incidence", "-4 – 4 deg", "固定 0 deg", "工况，不改变叶型几何"),
        ("Mach", "0.3 – 0.7", "固定 0.5", "工况，不改变叶型几何"),
    ]
    source_rows = [
        ("analysis/geometry_review/review_cases.csv",
         f"{n} 个 Case 的六维参数（V2 评审专用）"),
        ("analysis/geometry_review/geometry/profiles/C8100xx.dat",
         "真实生成的原始叶型（列 xp yp xs ys）"),
        ("analysis/geometry_review/geometry/geomturbo/C8100xx.geomTurbo",
         "真实生成的几何（UNITS Meters，periodicity = 0.06 / Solidity）"),
        ("analysis/geometry_review/geometry_qc.csv",
         "真实 QC 报告（本次包内全部数值来源）"),
        ("analysis/geometry_review/ranges_exploratory_v2.yaml",
         f"探索范围定义（status = {ranges_meta.get('status')}）"),
        ("code/02_generate_geometry.py / code/03_geometry_qc.py",
         "生成器与 QC 实现（本次未运行、未修改）"),
        ("code/geometry_legacy_v1.py",
         f"冻结造型核心（Metal1 = {METAL1_DEG:g} deg；本次未修改）"),
        ("legacy/blade_batch_generation_template.geomTurbo",
         "冻结模板 sha256 92c4296f...5119（未修改）"),
        ("tools/plot_geometry_review.py",
         "V2 绘图脚本；本包复用了它的坐标与比例约定"),
    ]
    dup_group_text = "\n".join(
        f"{blade_table[g['members'][0]]['id']}: " + ", ".join(g["members"])
        for g in dup) or "(none)"
    return {
        "n_cases": n, "qc_pass": sum(1 for c in cases_ordered
                                     if pgr.qc_status(qc.get(c["case_id"], {})) == "PASS"),
        "first_id": ids[0], "last_id": ids[-1],
        "range_id": cases_ordered[0]["range_id"],
        "sampling_id": cases_ordered[0]["sampling_id"],
        "metal1": f"{METAL1_DEG:g}", "rows": OVERVIEW_ROWS, "cols": OVERVIEW_COLS,
        "unique_blades": unique_blades, "dup_group_text": dup_group_text,
        "neg_env": neg, "neg_env_count": len(neg),
        "min_gap_range": f"{min(gaps):.5f} .. {max(gaps):.5f}",
        "zoom_window": "0.012 m × 0.012 m", "dpi": dpi,
        "png_per_case": f"{3 * n} / {3 * n}",
        "overview_size": f"{width} × {height} px" if width else "n/a",
        "group_rows": group_rows, "range_rows": range_rows,
        "source_rows": source_rows, "checks": checks + notes,
        "problems": problems,
        "file_rows": [
            ("README.md", "评审说明（目的 / 范围 / 单位 / 声明 / 如何评审）"),
            ("00_all_cases_overview.png", f"全部 {n} 个 Case 的总览图"),
            ("00_case_index.csv", f"{n} 行索引，含人工评审空列"),
            ("cases/C8100xx/parameters.json",
             "该 Case 的六维参数 + 生成/QC 状态 + QC 数值 + 单位说明 + 人工空列"),
            ("cases/C8100xx/blade_profile.png", "单叶型（同一窗口/比例）"),
            ("cases/C8100xx/cascade_3blade.png", "三叶片叶栅（真实 pitch）"),
            ("cases/C8100xx/edge_details.png", "前缘 / 尾缘局部放大（同一窗口/比例）"),
            ("cases/C8100xx/C8100xx.dat", "原始叶型文件（只读副本）"),
            ("cases/C8100xx/C8100xx.geomTurbo", "原始几何文件（只读副本）"),
        ],
    }


def _ranges_meta(path):
    """status / range_id / sampling_id / metal1_fixed_deg from the ranges YAML."""
    wanted = ("status", "range_id", "sampling_id", "dataset_version",
              "random_seed", "metal1_fixed_deg")
    meta = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if ":" in line and not line.startswith("-"):
            key, value = line.split(":", 1)
            if key.strip() in wanted:
                meta[key.strip()] = value.strip()
    return meta


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the senior review package (Geometry Range Review V2, "
                    "40 cases) — packaging/plotting only, read-only inputs.")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--geometry", default=str(DEFAULT_GEOMETRY))
    parser.add_argument("--qc", default=str(DEFAULT_QC))
    parser.add_argument("--ranges", default=str(DEFAULT_RANGES))
    parser.add_argument("--outdir", default=str(DEFAULT_OUTDIR))
    parser.add_argument("--zip", dest="zip_path", default=str(DEFAULT_ZIP))
    parser.add_argument("--dpi", type=int, default=DPI_DEFAULT,
                        help=f"PNG resolution, must be >= {DPI_MIN}")
    parser.add_argument("--no-zip", action="store_true",
                        help="skip the ZIP archive")
    parser.add_argument("--overwrite", action="store_true",
                        help="allow writing into a non-empty output directory")
    args = parser.parse_args(argv)

    if args.dpi < DPI_MIN:
        print(f"error: --dpi must be >= {DPI_MIN}", file=sys.stderr)
        return 2
    cases_path, qc_path = Path(args.cases), Path(args.qc)
    geometry_path, ranges_path = Path(args.geometry), Path(args.ranges)
    for path in (cases_path, qc_path, ranges_path):
        if not path.is_file():
            print(f"error: missing input {path}", file=sys.stderr)
            return 2
    if not (geometry_path / "profiles").is_dir() or \
            not (geometry_path / "geomturbo").is_dir():
        print(f"error: missing profiles/geomturbo under {geometry_path}",
              file=sys.stderr)
        return 2

    outdir = Path(args.outdir)
    if outdir.exists() and any(outdir.iterdir()) and not args.overwrite:
        print(f"error: {outdir} is not empty (use --overwrite to rebuild)",
              file=sys.stderr)
        return 3

    cases = pgr.load_cases(cases_path)
    qc = pgr.load_qc(qc_path)
    new, legacy = pgr.load_ranges(ranges_path)
    ranges_meta = _ranges_meta(ranges_path)
    frame = pgr.profile_frame(geometry_path, cases, qc)
    if len(frame) != len(cases):
        print(f"error: only {len(frame)}/{len(cases)} profiles could be loaded",
              file=sys.stderr)
        return 2
    if len(cases) > OVERVIEW_ROWS * OVERVIEW_COLS:
        print(f"error: {len(cases)} cases do not fit "
              f"{OVERVIEW_ROWS}x{OVERVIEW_COLS} overview panels", file=sys.stderr)
        return 2

    ordered = ordered_cases(cases)
    blade_table, groups = blade_group_table(cases)
    before = snapshot_sources(cases)
    window = data_window([entry["pressure"] for entry in frame.values()]
                         + [entry["suction"] for entry in frame.values()])
    scale = BLADE_PANEL_IN / (window[0][1] - window[0][0])       # inches per metre
    zoom_scale = scale * ZOOM_SCALE_FACTOR
    x_span = window[0][1] - window[0][0]
    y_span = window[1][1] - window[1][0]

    print(f"make_senior_review_v2: {len(cases)} cases, "
          f"{len(groups)} distinct blades, dpi={args.dpi}")
    print(f"  global window (all {len(cases)} blade_profile.png panels): "
          f"x {window[0][0]:.6f} .. {window[0][1]:.6f} m, "
          f"y {window[1][0]:.6f} .. {window[1][1]:.6f} m")
    print(f"  window span {x_span:.6f} m x {y_span:.6f} m; "
          f"blade scale {scale:.2f} in/m ({BLADE_PANEL_IN:.1f} in panel); "
          f"LE/TE zoom scale {zoom_scale:.2f} in/m (4x)")

    outdir.mkdir(parents=True, exist_ok=True)
    for case in ordered:
        case_id = case["case_id"]
        folder = outdir / "cases" / case_id
        folder.mkdir(parents=True, exist_ok=True)
        entry = frame[case_id]
        qc_row = qc.get(case_id, {})
        meta = blade_table[case_id]
        hashes = {}
        for suffix in ("dat", "geomTurbo"):
            source = ((geometry_path / "profiles" / f"{case_id}.dat")
                      if suffix == "dat" else
                      (geometry_path / "geomturbo" / f"{case_id}.geomTurbo"))
            shutil.copy2(source, folder / f"{case_id}.{suffix}")
            hashes[suffix] = {"sha256": sha256_file(source),
                              "bytes": source.stat().st_size}
        payload = build_parameters(case, qc_row, legacy, new, meta, ranges_meta,
                                   hashes)
        with open(folder / "parameters.json", "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        fig_blade_profile(entry, case, qc_row, window, scale,
                          folder / "blade_profile.png", args.dpi, meta, legacy)
        fig_cascade_3blade(entry, case, qc_row, window[0], scale,
                           folder / "cascade_3blade.png", args.dpi, meta, legacy)
        fig_edge_details(entry, case, qc_row, zoom_scale,
                         folder / "edge_details.png", args.dpi, meta, legacy)
        print(f"  {case_id}  {case['group']:14s} QC {pgr.qc_status(qc_row):4s} "
              f"pitch={num(qc_row, 'periodicity'):.5f} m  "
              f"{meta['id']}  (4 files)")

    fig_overview(frame, ordered, qc, blade_table, window,
                 outdir / "00_all_cases_overview.png", args.dpi, legacy)
    write_case_index(outdir / "00_case_index.csv", ordered, qc, blade_table, legacy)

    problems, notes = self_check(outdir, ordered, qc, blade_table, before,
                                 args.dpi, window)
    stats = _stats(outdir, ordered, qc, groups, frame, new, legacy, ranges_meta,
                   before, problems, notes, args.dpi)
    write_readme(outdir / "README.md", stats)

    zip_info = "(skipped)"
    if not args.no_zip:
        zip_path, zipped = make_zip(outdir, Path(args.zip_path))
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        zip_info = f"{zip_path}  ({zipped} files, {size_mb:.1f} MiB)"

    pngs = sorted(outdir.rglob("*.png"))
    jsons = sorted(outdir.rglob("parameters.json"))
    datas = sorted(outdir.rglob("*.dat"))
    geomturbos = sorted(outdir.rglob("*.geomTurbo"))
    folders = [p for p in (outdir / "cases").iterdir() if p.is_dir()]
    print("\n=== deliverable summary ===")
    print(f"  package dir      : {outdir}")
    print(f"  case folders     : {len(folders)} / {len(cases)}")
    print(f"  parameters.json  : {len(jsons)} / {len(cases)}")
    print(f"  PNG total        : {len(pngs)}  (per-case {len(pngs) - 1} = 3 x "
          f"{len(cases)}, plus 1 overview)")
    print(f"  .dat / .geomTurbo: {len(datas)} / {len(geomturbos)}")
    print(f"  index rows       : {len(ordered)}")
    print(f"  overview PNG     : {outdir / '00_all_cases_overview.png'}  "
          f"({stats['overview_size']})")
    print(f"  README           : {outdir / 'README.md'}")
    print(f"  ZIP              : {zip_info}")
    print(f"=== self-check: {len(problems)} problem(s) ===")
    for line in notes:
        print(f"  note: {line}")
    for line in problems:
        print(f"  PROBLEM: {line}")
    print("  OK" if not problems else "  -> fix the problems above before delivery")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
