#!/usr/bin/env python
"""make_review_summary.py — join the review case table with the real QC report.

REVIEW ONLY. It writes ``review_summary.csv`` for the human reviewer by joining

    analysis/geometry_review/review_cases.csv     (inputs, from make_review_cases.py)
    analysis/geometry_review/geometry_qc.csv      (real output of code/03_geometry_qc.py)

and adding EMPTY human-review columns at the end.

The four stages are deliberately kept separate and must not be conflated:

    geometry_generated   the .dat / .geomTurbo files exist on disk
    geometry_qc_status   frozen QC verdict (geometry_ok) from code/03_geometry_qc.py
    human_*              engineering plausibility: NOT FILLED IN (reviewer only)
    mesh feasibility     NOT EVALUATED (no mesh / CFD was run)

Usage::

    conda run -n ai4s python analysis/geometry_review/make_review_summary.py
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REVIEW_DIR = Path(__file__).resolve().parent
DEFAULT_CASES = REVIEW_DIR / "review_cases.csv"
DEFAULT_QC = REVIEW_DIR / "geometry_qc.csv"
DEFAULT_GEOMETRY = REVIEW_DIR / "geometry"
DEFAULT_OUT = REVIEW_DIR / "review_summary.csv"

PARAM_COLUMNS = ["Xthick", "Tmax", "Metal2", "Solidity", "Incidence", "Mach"]
QC_COLUMNS = [
    "geometry_ok", "reason",
    "min_gap", "envelope_clearance", "blade_tangential_extent", "periodicity",
    "chord", "min_interior_thickness", "max_paired_thickness",
    "le_closure_error", "te_closure_error",
    "self_intersection", "adjacent_blade_intersection",
    "finite_ok", "span_section_coordinate_consistent",
    "pressure_max_turn_angle_deg", "suction_max_turn_angle_deg",
    "pressure_max_discrete_curvature", "suction_max_discrete_curvature",
    "qc_policy_id", "calibration_status",
]
HUMAN_COLUMNS = [
    "human_geometry_acceptance",   # empty: reviewer decision
    "human_engineering_plausibility",
    "human_mesh_feasibility",      # NOT evaluated here (no mesh was built)
    "human_reviewer",
    "human_review_date",
    "human_comment",
]
COLUMNS = (["case_id", "group", "note", *PARAM_COLUMNS,
            "range_id", "sampling_id", "geometry_generated", "geometry_qc_status",
            *QC_COLUMNS, *HUMAN_COLUMNS])


def load(path: Path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--qc", default=str(DEFAULT_QC))
    parser.add_argument("--geometry", default=str(DEFAULT_GEOMETRY))
    parser.add_argument("--output", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)

    cases_path, qc_path = Path(args.cases), Path(args.qc)
    geometry = Path(args.geometry)
    if not cases_path.is_file():
        print(f"error: missing {cases_path}", file=sys.stderr)
        return 2
    if not qc_path.is_file():
        print(f"error: missing {qc_path} (run code/03_geometry_qc.py first)",
              file=sys.stderr)
        return 2

    cases = load(cases_path)
    qc = {row["case_id"]: row for row in load(qc_path)}

    out_rows, n_gen, n_pass = [], 0, 0
    for case in cases:
        cid = case["case_id"]
        profile = geometry / "profiles" / f"{cid}.dat"
        geom = geometry / "geomturbo" / f"{cid}.geomTurbo"
        generated = int(profile.is_file() and geom.is_file())
        n_gen += generated
        row_qc = qc.get(cid)
        if row_qc and row_qc["geometry_ok"] == "1":
            n_pass += 1
        out = {"case_id": cid, "group": case.get("group", ""),
               "note": case.get("note", ""), "range_id": case.get("range_id", ""),
               "sampling_id": case.get("sampling_id", ""),
               "geometry_generated": generated,
               "geometry_qc_status": ("PASS" if row_qc and row_qc["geometry_ok"] == "1"
                                      else ("FAIL" if row_qc else "NO_QC"))}
        for key in PARAM_COLUMNS:
            out[key] = case.get(key, "")
        for key in QC_COLUMNS:
            out[key] = (row_qc or {}).get(key, "")
        for key in HUMAN_COLUMNS:
            out[key] = ""
        out_rows.append(out)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"wrote {out_path}")
    print(f"  cases                : {len(out_rows)}")
    print(f"  geometry_generated   : {n_gen}")
    print(f"  geometry_qc PASS     : {n_pass}")
    print(f"  geometry_qc FAIL     : {len(out_rows) - n_pass}")
    print("  human_* columns      : left EMPTY for the reviewer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
