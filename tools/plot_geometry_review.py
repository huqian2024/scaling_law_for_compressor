#!/usr/bin/env python
"""plot_geometry_review.py — Geometry Range Review V2 figures (EXPLORATORY).

Draws only **real** pipeline output: the ``.dat`` profiles written by
``code/02_generate_geometry.py`` and the diagnostics reported by
``code/03_geometry_qc.py``. No synthetic blade is ever drawn.

Profile frame (repo convention, see code/geometry_legacy_v1.py):
    each ``.dat`` row is ``xp yp xs ys`` = (pressure x, pressure y,
    suction x, suction y), where x = chordwise (Z in .geomTurbo) and
    y = tangential (Y in .geomTurbo).

Units: raw profiles are uniformly scaled so that chord = 0.06 m
(= CHORD_TARGET in the .geomTurbo), so **every plotted axis is in metres**.
Careful: the QC report mixes frames — ``chord``, ``periodicity``, ``min_gap``,
``envelope_clearance``, ``blade_tangential_extent``, turn angles and curvature
come from the .geomTurbo (metres), while ``min_interior_thickness`` and
``max_paired_thickness`` come from the raw profile (normalised units).
See the README, section "Units".

Figures (all PNG, dpi >= 200, Agg backend, never plt.show()):

    fig01_single_param_extension.png  new vs legacy bounds, one panel per parameter
    fig02_extreme_corners.png         2 x 4 grid of the 8 new-bound corners
    fig03_solidity_metal2_cascade.png Solidity x Metal2 boundary, 3-blade cascades
    fig04_notable_zoom.png            LE / TE / pressure / suction / gap zooms
    fig05_blade_overview.png          ★ representative blades overview (grid)
    fig06_qc_overview.png             QC status + diagnostic numbers

Labels are English on purpose: the default matplotlib font has no CJK glyphs.

Usage::

    conda run -n ai4s python tools/plot_geometry_review.py
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                       # headless: no GUI, no plt.show()
import matplotlib.pyplot as plt             # noqa: E402
import numpy as np                          # noqa: E402

REPO = Path(__file__).resolve().parents[1]
REVIEW_DIR = REPO / "analysis" / "geometry_review"
DEFAULT_CASES = REVIEW_DIR / "review_cases.csv"
DEFAULT_GEOMETRY = REVIEW_DIR / "geometry"
DEFAULT_QC = REVIEW_DIR / "geometry_qc.csv"
DEFAULT_OUTDIR = REVIEW_DIR / "figures"
DEFAULT_RANGES = REVIEW_DIR / "ranges_exploratory_v2.yaml"

DEFAULT_DPI = 200
CHORD_TARGET = 0.06                         # frozen (legacy) chord in .geomTurbo
GEOMETRY_PARAMS = ("Xthick", "Tmax", "Metal2", "Solidity")

PASS_COLOR = "#1f77b4"
FAIL_COLOR = "#d62728"
REF_COLOR = "#111111"
LEGACY_COLOR = "#6f7f8f"
NEW_LO_COLOR = "#2ca02c"
NEW_HI_COLOR = "#ff7f0e"
BADGE_PASS = "#1a7f37"
BADGE_FAIL = "#c1121f"


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------
def load_cases(path: Path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_qc(path: Path):
    with open(path, newline="", encoding="utf-8") as handle:
        return {row["case_id"]: row for row in csv.DictReader(handle)}


def load_ranges(path: Path):
    """Minimal reader for the exploratory ranges YAML (no yaml dependency)."""
    new, legacy = {}, {}
    section = None
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            continue
        if line.startswith("ranges:"):
            section = new
            continue
        if line.startswith("legacy_ranges:"):
            section = legacy
            continue
        if section is not None and ":" in line and line[0] not in "-":
            key, value = line.split(":", 1)
            key = key.strip()
            if key in GEOMETRY_PARAMS and "[" in value:
                lo, hi = value.strip().strip("[]").split(",")
                section[key] = (float(lo), float(hi))
        if line.startswith(("fixed:", "status:", "metal1_fixed_deg:",
                            "random_seed:", "range_id:", "sampling_id:",
                            "dataset_version:")):
            section = None
    return new, legacy


def load_profile(path: Path):
    """Return (pressure (n,2), suction (n,2)) from a 4-column profile .dat."""
    data = np.loadtxt(path)
    if data.ndim != 2 or data.shape[1] != 4:
        raise ValueError(f"unexpected profile shape {data.shape} in {path}")
    return data[:, 0:2], data[:, 2:4]


def chord_length(pressure) -> float:
    return float(np.hypot(pressure[-1, 0] - pressure[0, 0],
                          pressure[-1, 1] - pressure[0, 1]))


def scale_to_chord(profile, chord):
    """Uniformly scale a raw profile so that its chord becomes CHORD_TARGET."""
    return profile * (CHORD_TARGET / chord)


def profile_frame(geometry_root: Path, cases, qc):
    """Load + chord-normalise every case that has a profile on disk."""
    out = {}
    for case in cases:
        path = Path(geometry_root) / "profiles" / f"{case['case_id']}.dat"
        if not path.is_file():
            print(f"warning: missing profile {path}", file=sys.stderr)
            continue
        pressure, suction = load_profile(path)
        chord = chord_length(pressure)
        out[case["case_id"]] = {
            "case": case,
            "qc": qc.get(case["case_id"], {}),
            "pressure": scale_to_chord(pressure, chord),
            "suction": scale_to_chord(suction, chord),
            "chord_raw": chord,
            "raw_to_m": CHORD_TARGET / chord,
        }
    return out


# ---------------------------------------------------------------------------
# case lookup helpers
# ---------------------------------------------------------------------------
def params_of(case):
    return {k: float(case[k]) for k in GEOMETRY_PARAMS}


def find_case(cases, **wanted):
    """First case whose geometry parameters match the requested values."""
    for case in cases:
        if all(abs(float(case[k]) - float(v)) < 1e-9 for k, v in wanted.items()):
            return case
    return None


def cases_in_group(cases, group):
    return [c for c in cases if c.get("group") == group]


def qc_status(row):
    if not row:
        return "NO-QC"
    return "PASS" if row.get("geometry_ok") == "1" else "FAIL"


def status_color(row):
    return FAIL_COLOR if qc_status(row) == "FAIL" else PASS_COLOR


def compact_label(case, extra=""):
    lines = [f"{case['case_id']}"]
    for k in GEOMETRY_PARAMS:
        lines.append(f"{k}={float(case[k]):g}")
    if extra:
        lines.append(extra)
    return "  ".join(lines[:1]) + "\n" + "  ".join(lines[1:])


def badge(case_id, row, xy=(0.985, 0.02)):
    """Small PASS/FAIL badge in axes-fraction coordinates."""
    status = qc_status(row)
    color = BADGE_FAIL if status == "FAIL" else BADGE_PASS
    return {"text": status, "color": color, "xy": xy}


def draw_badge(ax, row, xy=(0.985, 0.025), fontsize=7.0):
    status = qc_status(row)
    color = BADGE_FAIL if status == "FAIL" else BADGE_PASS
    ax.text(xy[0], xy[1], f"QC {status}", transform=ax.transAxes, ha="right",
            va="bottom", fontsize=fontsize, color="white", zorder=6,
            bbox=dict(boxstyle="round,pad=0.25", fc=color, ec="none", alpha=0.92))


# ---------------------------------------------------------------------------
# drawing helpers
# ---------------------------------------------------------------------------
def draw_blade(ax, pressure, suction, color, linewidth=1.5, alpha=1.0,
               label_text=None, zorder=3):
    ax.plot(pressure[:, 0], pressure[:, 1], color=color, lw=linewidth,
            alpha=alpha, label=label_text, zorder=zorder)
    ax.plot(suction[:, 0], suction[:, 1], color=color, lw=linewidth,
            alpha=alpha, ls="--", zorder=zorder)


def draw_blade_side(ax, side, color, linewidth=1.6, label_text=None):
    ax.plot(side[:, 0], side[:, 1], color=color, lw=linewidth,
            label=label_text, zorder=3)


def bounding_range(arrays, pad=0.08):
    if isinstance(arrays, dict):
        arrays = list(arrays.values())
    flat = [a for a in arrays if a is not None]
    xs = np.concatenate([a[:, 0] for a in flat])
    ys = np.concatenate([a[:, 1] for a in flat])
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    dx, dy = (x1 - x0) * pad or 0.005, (y1 - y0) * pad or 0.005
    return (float(x0 - dx), float(x1 + dx), float(y0 - dy), float(y1 + dy))


def apply_range(ax, rng, xlabel="Z  chordwise  [m]", ylabel="Y  tangential  [m]"):
    ax.set_xlim(rng[0], rng[1])
    ax.set_ylim(rng[2], rng[3])
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.22, lw=0.5)
    ax.set_xlabel(xlabel, fontsize=8)
    ax.set_ylabel(ylabel, fontsize=8)


def annotate(ax, text, loc=(0.02, 0.98), fontsize=7.5):
    ax.text(loc[0], loc[1], text, transform=ax.transAxes, va="top", ha="left",
            fontsize=fontsize, family="monospace", zorder=6,
            bbox=dict(boxstyle="round,pad=0.28", fc="white", ec="0.65",
                      alpha=0.86))


def save(fig, outdir: Path, name: str, dpi: int):
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / name
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {path}")
    return path


def tangent_angle(x, y, at_end=False):
    coeffs = np.polyfit(x, y, 2)
    slope = np.polyval(np.polyder(coeffs), x[-1] if at_end else x[0])
    return float(np.degrees(np.arctan(slope)))


def meanline_angles(pressure, suction):
    mid = (pressure + suction) / 2.0
    n = min(14, len(mid))
    return (tangent_angle(mid[:n, 0], mid[:n, 1], at_end=False),
            tangent_angle(mid[-n:, 0], mid[-n:, 1], at_end=True))


def range_strip(ax, new_lo, new_hi, legacy_lo, legacy_hi, values, colors):
    """Inset number line: shaded legacy band + ticks at the scanned values."""
    strip = ax.inset_axes([0.06, 0.015, 0.88, 0.075])
    span = (new_hi - new_lo) or 1.0
    strip.set_xlim(new_lo - 0.06 * span, new_hi + 0.06 * span)
    strip.set_ylim(0.0, 1.0)
    strip.axvspan(legacy_lo, legacy_hi, color="#cfe2f3", alpha=0.95,
                  ec="#7f9db9", lw=0.6, zorder=0)
    strip.axvline(new_lo, color="#444444", lw=0.8, ls=":")
    strip.axvline(new_hi, color="#444444", lw=0.8, ls=":")
    for value, color in zip(values, colors):
        strip.plot([value], [0.5], marker="|", ms=9, mew=1.6, color=color,
                   zorder=3)
    strip.set_yticks([])
    strip.set_xticks(list(values))
    strip.set_xticklabels([f"{v:g}" for v in values], fontsize=6)
    strip.tick_params(axis="x", length=2, pad=1)
    for spine in strip.spines.values():
        spine.set_linewidth(0.5)
    strip.set_title("shaded band = legacy range;  dotted = new bounds",
                    fontsize=6, pad=2)


def extra_bottom_room(rng, fraction=0.16):
    """Grow the lower y limit so an inset strip cannot overlap the blade."""
    x0, x1, y0, y1 = rng
    return (x0, x1, y0 - (y1 - y0) * fraction, y1)


# ---------------------------------------------------------------------------
# fig01 — single-parameter extension (new vs legacy bounds)
# ---------------------------------------------------------------------------
def fig01_param_extension(frame, cases, new, legacy, outdir, dpi):
    panels = ("Xthick", "Tmax", "Metal2", "Solidity")
    fig, axes = plt.subplots(2, 2, figsize=(17.0, 13.5))
    for ax, param in zip(np.atleast_1d(axes).ravel(), panels):
        scan = [c for c in cases_in_group(cases, "A_single_param")
                if c.get("note", "").startswith(f"{param} scan")]
        scan = [c for c in scan if c["case_id"] in frame]
        scan.sort(key=lambda c: float(c[param]))
        entries = [frame[c["case_id"]] for c in scan]
        rng = extra_bottom_room(bounding_range(
            [e["pressure"] for e in entries] + [e["suction"] for e in entries]))

        text, colors, values = [], [], []
        for case in scan:
            entry = frame[case["case_id"]]
            value = float(case[param])
            at_new_lo = abs(value - new[param][0]) < 1e-12
            at_new_hi = abs(value - new[param][1]) < 1e-12
            in_legacy = (legacy[param][0] - 1e-12 <= value
                         <= legacy[param][1] + 1e-12)
            if at_new_lo:
                color, tag, lw = NEW_LO_COLOR, "NEW lo", 2.0
            elif at_new_hi:
                color, tag, lw = NEW_HI_COLOR, "NEW hi", 2.0
            elif not in_legacy:
                color, tag, lw = "#999999", "outside legacy", 1.8
            elif abs(value - (legacy[param][0] + legacy[param][1]) / 2) < 1e-12:
                color, tag, lw = REF_COLOR, "legacy mid", 2.2
            else:
                color, tag, lw = LEGACY_COLOR, "legacy bound", 1.6
            colors.append(color)
            values.append(value)
            draw_blade(ax, entry["pressure"], entry["suction"], color,
                       linewidth=lw,
                       label_text=f"{case['case_id']}  {param}={value:g}  [{tag}]")
            text.append(f"{param}={value:<7g} {tag:14s} QC="
                        f"{qc_status(entry['qc'])}")

        apply_range(ax, rng)
        ax.legend(loc="upper left", fontsize=7.2, framealpha=0.9)
        annotate(ax, f"legacy {param} = [{legacy[param][0]:g}, "
                     f"{legacy[param][1]:g}]\nnew    {param} = "
                     f"[{new[param][0]:g}, {new[param][1]:g}]\n"
                     "---------------------\n" + "\n".join(text),
                 loc=(0.99, 0.98))
        range_strip(ax, new[param][0], new[param][1], legacy[param][0],
                    legacy[param][1], values, colors)
        ax.set_title(f"{param} extension: legacy vs exploratory bounds "
                     "(solid = pressure side, dashed = suction side)", fontsize=10)
    fig.suptitle("fig01  single-parameter boundary extension — EXPLORATORY ranges "
                 "(not approved); identical axes per group, equal aspect, units m",
                 fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.975))
    return save(fig, outdir, "fig01_single_param_extension.png", dpi)


# ---------------------------------------------------------------------------
# fig02 — 8 extreme corners of the NEW bounds (2 x 4)
# ---------------------------------------------------------------------------
def fig02_corners(frame, cases, outdir, dpi):
    corners = [c for c in cases_in_group(cases, "B_corner")
               if c["case_id"] in frame]
    corners.sort(key=lambda c: (float(c["Xthick"]), float(c["Tmax"]),
                                float(c["Metal2"])))
    entries = [frame[c["case_id"]] for c in corners]
    rng = bounding_range([e["pressure"] for e in entries]
                         + [e["suction"] for e in entries])
    fig, axes = plt.subplots(2, 4, figsize=(5.4 * 4, 5.7 * 2))
    for ax, case in zip(np.atleast_1d(axes).ravel(), corners):
        entry = frame[case["case_id"]]
        draw_blade(ax, entry["pressure"], entry["suction"],
                   status_color(entry["qc"]), linewidth=1.8)
        apply_range(ax, rng)
        le, te = meanline_angles(entry["pressure"], entry["suction"])
        annotate(ax, (f"{case['case_id']}\n"
                      f"Xthick = {float(case['Xthick']):g}\n"
                      f"Tmax   = {float(case['Tmax']):g}\n"
                      f"Metal2 = {float(case['Metal2']):g} deg\n"
                      f"Solidity = {float(case['Solidity']):g}\n"
                      f"QC = {qc_status(entry['qc'])}\n"
                      f"meanline LE {le:.1f} / TE {te:.1f} deg"), fontsize=8.0)
        draw_badge(ax, entry["qc"], fontsize=8)
        ax.set_title(f"corner {case['case_id']}", fontsize=9)
    fig.suptitle("fig02  the 8 extreme corner combinations of the EXPLORATORY "
                 "(Xthick, Tmax, Metal2) bounds — Solidity = 1.5, same axes and "
                 "equal aspect", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    return save(fig, outdir, "fig02_extreme_corners.png", dpi)


# ---------------------------------------------------------------------------
# fig03 — Solidity x Metal2 coupled boundary, 3-blade cascade arrangement
# ---------------------------------------------------------------------------
def fig03_cascade_matrix(frame, cases, new, legacy, outdir, dpi):
    solidities = (new["Solidity"][0], new["Solidity"][1])
    metal2s = (new["Metal2"][0], legacy["Metal2"][0],
               (legacy["Metal2"][0] + legacy["Metal2"][1]) / 2.0,
               legacy["Metal2"][1], new["Metal2"][1])
    x_mid = (legacy["Xthick"][0] + legacy["Xthick"][1]) / 2.0
    t_mid = (legacy["Tmax"][0] + legacy["Tmax"][1]) / 2.0

    picks = [[find_case(cases, Xthick=x_mid, Tmax=t_mid, Metal2=mv, Solidity=sv)
              for mv in metal2s] for sv in solidities]
    usable = [frame[c["case_id"]] for row in picks for c in row
              if c and c["case_id"] in frame]
    if not usable:
        print("warning: no cascade cases found; skipping fig03", file=sys.stderr)
        return None
    xrng = bounding_range([e["pressure"] for e in usable]
                          + [e["suction"] for e in usable])

    fig, axes = plt.subplots(len(solidities), len(metal2s),
                             figsize=(5.0 * len(metal2s), 5.5 * len(solidities)))
    axes = np.atleast_2d(axes)
    for i, sv in enumerate(solidities):
        for j, mv in enumerate(metal2s):
            ax = axes[i, j]
            case = picks[i][j]
            if case is None or case["case_id"] not in frame:
                ax.axis("off")
                continue
            entry = frame[case["case_id"]]
            row = entry["qc"]
            pitch = float(row.get("periodicity", 0.0)) or CHORD_TARGET / sv
            pressure, suction = entry["pressure"], entry["suction"]
            color = status_color(row)
            for shift, alpha, lw in ((-pitch, 0.28, 1.2), (pitch, 0.28, 1.2),
                                     (0.0, 1.0, 1.9)):
                draw_blade(ax, pressure + [0.0, shift], suction + [0.0, shift],
                           color, linewidth=lw, alpha=alpha, zorder=2 if shift else 4)
            y0 = float(min(pressure[:, 1].min(), suction[:, 1].min()))
            y1 = float(max(pressure[:, 1].max(), suction[:, 1].max()))
            for yy in (y0 - pitch, y0, y0 + pitch):
                ax.plot(xrng[0:2], [yy, yy], color="#9aa0a6", lw=0.6, ls="-.",
                        zorder=1)
            env = float(row.get("envelope_clearance", 0.0))
            annotate(ax, (f"{case['case_id']}   Solidity={sv:g}  Metal2={mv:g}\n"
                          f"pitch        = {pitch:.5f} m\n"
                          f"blade Y span = "
                          f"{float(row.get('blade_tangential_extent', 0)):.5f} m\n"
                          f"envelope clr = {env:+.5f} m"
                          f"{'  (NEGATIVE)' if env < 0 else ''}\n"
                          f"min_gap      = {float(row.get('min_gap', 0)):.5f} m\n"
                          f"QC = {qc_status(row)}"), fontsize=7.5)
            ax.set_xlim(xrng[0], xrng[1])
            ax.set_ylim(y0 - pitch * 1.4, y1 + pitch * 1.4)
            ax.set_aspect("equal", adjustable="box")
            ax.grid(True, alpha=0.22, lw=0.5)
            ax.set_xlabel("Z  chordwise  [m]", fontsize=8)
            ax.set_ylabel("Y  tangential  [m]", fontsize=8)
            beyond = []
            if not (legacy["Metal2"][0] <= mv <= legacy["Metal2"][1]):
                beyond.append("Metal2")
            if not (legacy["Solidity"][0] <= sv <= legacy["Solidity"][1]):
                beyond.append("Solidity")
            tag = ("  [beyond legacy: " + ",".join(beyond) + "]") if beyond else ""
            ax.set_title(f"Solidity={sv:g} | Metal2={mv:g} deg{tag}", fontsize=9)
    fig.suptitle("fig03  Solidity x Metal2 coupled boundary — 3 adjacent blades per "
                 "panel, neighbour shift = 0.06 / Solidity along +Y.\n"
                 "HARD GATE = min_gap > 0 (segment based). envelope_clearance is a "
                 "DIAGNOSTIC ONLY (periodicity - blade Y span); a negative value is "
                 "NOT a collision.", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return save(fig, outdir, "fig03_solidity_metal2_cascade.png", dpi)


# ---------------------------------------------------------------------------
# notable / anomalous case selection
# ---------------------------------------------------------------------------
def select_notable(cases, qc, new, legacy, cap=10):
    """Return [(case, qc_row, [flags])] worth a human look, worst first."""
    scored = []
    for case in cases:
        row = qc.get(case["case_id"])
        if not row:
            continue
        flags = []
        if row.get("geometry_ok") == "0":
            flags.append("QC_FAIL")
        if float(row.get("envelope_clearance", 0.0)) < 0.0:
            flags.append("NEG_ENVELOPE_CLEARANCE")
        scored.append({"case": case, "row": row, "flags": flags})

    def curvature(item):
        row = item["row"]
        return max(float(row["pressure_max_discrete_curvature"]),
                   float(row["suction_max_discrete_curvature"]))

    boundary = []
    mids = {k: (legacy[k][0] + legacy[k][1]) / 2.0 for k in GEOMETRY_PARAMS}
    for param, value in (("Metal2", new["Metal2"][0]),
                         ("Tmax", new["Tmax"][0]),
                         ("Xthick", new["Xthick"][1])):
        for case in cases:
            if abs(float(case[param]) - value) > 1e-12:
                continue
            if any(abs(float(case[k]) - mids[k]) > 1e-12
                   for k in GEOMETRY_PARAMS if k != param):
                continue                     # keep only clean single-param extremes
            row = qc.get(case["case_id"])
            if row:
                boundary.append({"case": case, "row": row,
                                 "flags": [f"{param}_AT_NEW_BOUND"]})
            break

    picked = ([item for item in scored if item["flags"]]
              + boundary
              + sorted(scored, key=lambda s: float(s["row"]["min_gap"]))[:2]
              + sorted(scored, key=curvature, reverse=True)[:2])

    out, index = [], {}
    for item in picked:
        cid = item["case"]["case_id"]
        if cid in index:
            merged = index[cid]
            merged["flags"] = sorted(set(merged["flags"] + item["flags"]))
            continue
        index[cid] = item
        out.append(item)
    return [(i["case"], i["row"], i["flags"]) for i in out[:cap]]


def closest_pair(poly_a, poly_b):
    """Closest point pair between two polygons (visual locator, not QC metric)."""
    diff = poly_a[:, None, :] - poly_b[None, :, :]
    dist = np.hypot(diff[:, :, 0], diff[:, :, 1])
    i, j = np.unravel_index(int(np.argmin(dist)), dist.shape)
    return poly_a[i], poly_b[j], float(dist[i, j])


def _x_window(ax, points, x_from, x_to, pad=0.18):
    sel = points[(points[:, 0] >= x_from) & (points[:, 0] <= x_to)]
    if len(sel) == 0:
        sel = points
    y0, y1 = float(sel[:, 1].min()), float(sel[:, 1].max())
    dy = (y1 - y0) * pad or 0.0008
    ax.set_xlim(x_from, x_to)
    ax.set_ylim(y0 - dy, y1 + dy)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.22, lw=0.5)
    ax.set_xlabel("Z  [m]", fontsize=7)
    ax.set_ylabel("Y  [m]", fontsize=7)
    ax.tick_params(labelsize=6.5)


def _square_window(ax, center, half):
    ax.set_xlim(center[0] - half, center[0] + half)
    ax.set_ylim(center[1] - half, center[1] + half)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.22, lw=0.5)
    ax.set_xlabel("Z  [m]", fontsize=7)
    ax.set_ylabel("Y  [m]", fontsize=7)
    ax.tick_params(labelsize=6.5)


def fig04_notable_zoom(frame, notable, outdir, dpi, window=0.012):
    rows = [(c, r, f) for c, r, f in notable if c["case_id"] in frame]
    if not rows:
        print("warning: nothing notable to zoom; skipping fig04", file=sys.stderr)
        return None
    columns = ("LE zoom", "TE zoom", "pressure side (mid)",
               "suction side (mid)", "closest pair to neighbour")
    fig, axes = plt.subplots(len(rows), len(columns),
                             figsize=(4.3 * len(columns), 4.6 * len(rows)))
    axes = np.atleast_2d(axes)
    for i, (case, row, flags) in enumerate(rows):
        entry = frame[case["case_id"]]
        pressure, suction = entry["pressure"], entry["suction"]
        points = np.vstack([pressure, suction])
        poly = np.vstack([pressure, suction[::-1]])
        x0, x1 = float(points[:, 0].min()), float(points[:, 0].max())
        pitch = float(row.get("periodicity", 0.0)) or 0.03
        color = status_color(row)

        ax = axes[i, 0]
        draw_blade(ax, pressure, suction, color, linewidth=1.5)
        _x_window(ax, points, x0, x0 + window)
        ax.set_title(f"{case['case_id']}\n"
                     f"X={float(case['Xthick']):g} T={float(case['Tmax']):g} "
                     f"M2={float(case['Metal2']):g} Sol={float(case['Solidity']):g}\n"
                     f"flags: {', '.join(flags) if flags else 'ranked'}",
                     fontsize=7.5)

        ax = axes[i, 1]
        draw_blade(ax, pressure, suction, color, linewidth=1.5)
        _x_window(ax, points, x1 - window, x1)
        ax.set_title(columns[1], fontsize=8)

        xm0, xm1 = x0 + 0.35 * (x1 - x0), x0 + 0.62 * (x1 - x0)
        ax = axes[i, 2]
        draw_blade_side(ax, pressure, color)
        _x_window(ax, pressure, xm0, xm1)
        ax.set_title(columns[2], fontsize=8)

        ax = axes[i, 3]
        draw_blade_side(ax, suction, color)
        _x_window(ax, suction, xm0, xm1)
        ax.set_title(columns[3], fontsize=8)

        ax = axes[i, 4]
        neighbour = poly + [0.0, pitch]
        draw_blade(ax, pressure, suction, color, linewidth=1.6)
        draw_blade(ax, pressure + [0.0, pitch], suction + [0.0, pitch],
                   "#8a8f98", linewidth=1.2, alpha=0.75)
        pa, pb, dvis = closest_pair(poly, neighbour)
        ax.plot([pa[0], pb[0]], [pa[1], pb[1]], color="#c1121f", lw=1.0, ls=":")
        mid = (pa + pb) / 2.0
        _square_window(ax, mid, max(window * 0.9, 0.8 * dvis))
        annotate(ax, (f"visual closest pair = {dvis:.5f} m\n"
                      f"QC min_gap (segment) = "
                      f"{float(row.get('min_gap', 0)):.5f} m\n"
                      f"envelope clearance  = "
                      f"{float(row.get('envelope_clearance', 0)):+.5f} m\n"
                      f"max curvature = {max(float(row['pressure_max_discrete_curvature']), float(row['suction_max_discrete_curvature'])):.0f} 1/m"),
                 fontsize=7.0)
        ax.set_title(columns[4], fontsize=8)

    fig.suptitle("fig04  anomalies and boundary cases — real geometry, zoomed.\n"
                 "'visual closest pair' is a point-to-point locator (draughting "
                 "aid); the authoritative clearance is the QC segment-based min_gap. "
                 "A negative envelope clearance is NOT a collision.",
                 fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return save(fig, outdir, "fig04_notable_zoom.png", dpi)


# ---------------------------------------------------------------------------
# fig05 — representative blade overview (the main deliverable)
# ---------------------------------------------------------------------------
def unique_profiles(cases):
    """[(key(Xthick,Tmax,Metal2), [case_ids], representative_case)]."""
    out, index = [], {}
    for case in cases:
        key = (float(case["Xthick"]), float(case["Tmax"]), float(case["Metal2"]))
        if key in index:
            index[key][1].append(case["case_id"])
            continue
        entry = [key, [case["case_id"]], case]
        index[key] = entry
        out.append(entry)
    return out


def maximin_select_profiles(profiles, new, count):
    """Deterministic maximin ordering of unique blades in normalised 3-D space."""
    keys = ("Xthick", "Tmax", "Metal2")
    lo = np.array([new[k][0] for k in keys])
    hi = np.array([new[k][1] for k in keys])
    pts = np.array([[float(p[2][k]) for k in keys] for p in profiles])
    norm = (pts - lo) / (hi - lo)
    allowed = np.ones(len(profiles), dtype=bool)
    best = np.linalg.norm(norm - 0.5, axis=1)
    order = []
    for _ in range(min(count, len(profiles))):
        idx = int(np.argmax(np.where(allowed, best, -np.inf)))
        order.append(idx)
        allowed[idx] = False
        best = np.minimum(best, np.linalg.norm(norm - norm[idx], axis=1))
    return [profiles[i] for i in order]


def fig05_blade_overview(frame, cases, qc, new, legacy, outdir, dpi,
                         count=20, ncols=5):
    profiles = [p for p in unique_profiles(cases)
                if p[2]["case_id"] in frame]
    selected = maximin_select_profiles(profiles, new, count)
    nrows = int(np.ceil(len(selected) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.6 * ncols, 4.9 * nrows))
    flat = np.atleast_1d(axes).ravel()
    for ax, (key, members, case) in zip(flat, selected):
        entry = frame[case["case_id"]]
        row = qc.get(case["case_id"], {})
        draw_blade(ax, entry["pressure"], entry["suction"], status_color(row),
                   linewidth=1.6)
        apply_range(ax, bounding_range([entry["pressure"], entry["suction"]]))
        beyond = [k for k in GEOMETRY_PARAMS
                  if not (legacy[k][0] - 1e-12 <= float(case[k])
                          <= legacy[k][1] + 1e-12)]
        ax.set_title(f"{case['case_id']}   ({len(members)} case(s))\n"
                     f"Xthick={float(case['Xthick']):g}  "
                     f"Tmax={float(case['Tmax']):g}  "
                     f"Metal2={float(case['Metal2']):g}  "
                     f"Sol={float(case['Solidity']):g}"
                     + (("\nbeyond legacy: " + ",".join(beyond)) if beyond else ""),
                     fontsize=7.8)
        draw_badge(ax, row, fontsize=7)
    for ax in flat[len(selected):]:
        ax.axis("off")
    fig.suptitle("fig05  representative blade overview — the most distinct REAL blade "
                 "profiles of this review (greedy maximin in normalised "
                 "(Xthick, Tmax, Metal2) space, unique profiles only).\n"
                 "solid = pressure side, dashed = suction side; equal aspect; units m; "
                 "badge = frozen Geometry QC status (PASS/FAIL only, no engineering "
                 "judgement).", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    return save(fig, outdir, "fig05_blade_overview.png", dpi)


# ---------------------------------------------------------------------------
# fig06 — QC status and diagnostic numbers
# ---------------------------------------------------------------------------
def fig06_qc_overview(frame, cases, qc, notable, outdir, dpi):
    ids = [c["case_id"] for c in cases if c["case_id"] in qc]
    rows = [qc[cid] for cid in ids]
    n_pass = sum(1 for r in rows if r["geometry_ok"] == "1")
    n_fail = len(rows) - n_pass
    reasons = sorted({r["reason"] for r in rows})

    fig, axes = plt.subplots(3, 2, figsize=(16.0, 14.5))

    def panel(ax, key, title, ascending=True, zero_line=False, scale=1.0):
        order = sorted(zip(ids, rows), key=lambda t: float(t[1][key]),
                       reverse=not ascending)
        labels = [o[0] for o in order]
        values = [float(o[1][key]) * scale for o in order]
        colors = [FAIL_COLOR if (zero_line and v < 0) else
                  (FAIL_COLOR if o[1]["geometry_ok"] == "0" else PASS_COLOR)
                  for v, o in zip(values, order)]
        ax.bar(range(len(values)), values, color=colors, width=0.72)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=90, fontsize=6)
        ax.set_title(title, fontsize=9)
        ax.grid(True, axis="y", alpha=0.25, lw=0.5)
        if zero_line:
            ax.axhline(0.0, color=FAIL_COLOR, lw=1.0, ls="--")

    panel(axes[0, 0], "min_gap",
          "(a) min_gap [m] ascending — HARD GATE must be > 0 "
          "(blue = QC PASS, red = QC FAIL)")
    panel(axes[0, 1], "envelope_clearance",
          "(b) envelope_clearance [m] — DIAGNOSTIC ONLY (not a gate); "
          "red bars are negative", zero_line=True)
    panel(axes[1, 0], "suction_max_discrete_curvature",
          "(c) suction-side max discrete curvature [1/m], descending",
          ascending=False)
    panel(axes[1, 1], "min_interior_thickness",
          "(d) min interior thickness, converted from raw profile units to [m] "
          "via 0.06/chord_raw, ascending")

    ax = axes[2, 0]
    ax.axis("off")
    env = [float(r["envelope_clearance"]) for r in rows]
    gap = [float(r["min_gap"]) for r in rows]
    ax.text(0.0, 1.0, "\n".join([
        f"cases                  : {len(rows)}",
        f"geometry_ok = 1 (PASS) : {n_pass}",
        f"geometry_ok = 0 (FAIL) : {n_fail}",
        f"reason codes present   : {reasons}",
        f"min_gap range          : {min(gap):.5f} .. {max(gap):.5f} m",
        f"envelope_clearance     : {min(env):+.5f} .. {max(env):+.5f} m "
        f"({sum(1 for v in env if v < 0)} negative)",
        "",
        "policy : geometry_qc_v1_hard    calibration : UNCALIBRATED",
        "",
        "Frozen contract reminders:",
        "  min_gap is the segment-based true clearance gate.",
        "  envelope_clearance is a diagnostic, never a gate.",
        "  a negative envelope_clearance with positive min_gap has a",
        "  frozen precedent in the baseline (case LG011).",
        "  QC PASS does NOT mean aerodynamically acceptable.",
    ]), va="top", ha="left", fontsize=9, family="monospace")

    ax = axes[2, 1]
    ax.axis("off")
    lines = ["cases recommended for human review (diagnostics, not verdicts):"]
    for case, row, flags in notable:
        lines.append(f"  {case['case_id']}  flags="
                     f"{'+'.join(flags) if flags else 'ranked'}")
        lines.append("      Xthick={:g} Tmax={:g} Metal2={:g} Solidity={:g}".format(
            float(case["Xthick"]), float(case["Tmax"]),
            float(case["Metal2"]), float(case["Solidity"])))
        lines.append("      min_gap={:.5f} env.clr={:+.5f} curv={:.0f} turn={:.1f}".format(
            float(row["min_gap"]), float(row["envelope_clearance"]),
            max(float(row["pressure_max_discrete_curvature"]),
                float(row["suction_max_discrete_curvature"])),
            max(float(row["pressure_max_turn_angle_deg"]),
                float(row["suction_max_turn_angle_deg"]))))
    lines += ["", "NOT evaluated in this review:",
              "  mesh feasibility, CFD feasibility, engineering acceptance."]
    ax.text(0.0, 1.0, "\n".join(lines), va="top", ha="left", fontsize=8.5,
            family="monospace")

    fig.suptitle("fig06  Geometry QC status and diagnostic numbers — EXPLORATORY "
                 "extended ranges (real QC output)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    return save(fig, outdir, "fig06_qc_overview.png", dpi)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Plot the Geometry Range Review V2 figures (real output only).")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--geometry", default=str(DEFAULT_GEOMETRY))
    parser.add_argument("--qc", default=str(DEFAULT_QC))
    parser.add_argument("--ranges", default=str(DEFAULT_RANGES))
    parser.add_argument("--outdir", default=str(DEFAULT_OUTDIR))
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI,
                        help=f"PNG resolution, must be >= 200 (default {DEFAULT_DPI})")
    parser.add_argument("--top-suspect", dest="top_suspect", type=int, default=10,
                        help="cases zoomed in fig04 / listed in fig06 (default 10)")
    parser.add_argument("--overview-count", dest="overview_count", type=int,
                        default=20, help="blades in fig05 (12..20 recommended)")
    args = parser.parse_args(argv)

    if args.dpi < 200:
        print("error: --dpi must be >= 200", file=sys.stderr)
        return 2
    cases_path, qc_path = Path(args.cases), Path(args.qc)
    geometry_path, ranges_path = Path(args.geometry), Path(args.ranges)
    for path in (cases_path, qc_path, ranges_path):
        if not path.is_file():
            print(f"error: missing input {path}", file=sys.stderr)
            return 2
    if not (geometry_path / "profiles").is_dir():
        print(f"error: missing {geometry_path / 'profiles'}", file=sys.stderr)
        return 2

    cases = load_cases(cases_path)
    qc = load_qc(qc_path)
    new, legacy = load_ranges(ranges_path)
    frame = profile_frame(geometry_path, cases, qc)
    if not frame:
        print("error: no profile could be loaded", file=sys.stderr)
        return 2

    notable = select_notable(cases, qc, new, legacy, cap=args.top_suspect)
    outdir = Path(args.outdir)
    profiles = unique_profiles(cases)
    print(f"plot_geometry_review (V2): {len(frame)} profiles, dpi={args.dpi}")
    print(f"  unique blade profiles : {len(profiles)}")
    print(f"  unique cascades       : {len({(c['Xthick'], c['Tmax'], c['Metal2'], c['Solidity']) for c in cases})}")
    print(f"  notable cases         : {[c['case_id'] for c, _, _ in notable]}")
    print("  QC FAIL cases         : "
          f"{[c['case_id'] for c in cases if qc.get(c['case_id'], {}).get('geometry_ok') == '0']}")

    fig01_param_extension(frame, cases, new, legacy, outdir, args.dpi)
    fig02_corners(frame, cases, outdir, args.dpi)
    fig03_cascade_matrix(frame, cases, new, legacy, outdir, args.dpi)
    fig04_notable_zoom(frame, notable, outdir, args.dpi)
    fig05_blade_overview(frame, cases, qc, new, legacy, outdir, args.dpi,
                         count=args.overview_count)
    fig06_qc_overview(frame, cases, qc, notable, outdir, args.dpi)
    return 0


if __name__ == "__main__":
    sys.exit(main())
