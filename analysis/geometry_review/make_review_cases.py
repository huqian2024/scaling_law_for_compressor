#!/usr/bin/env python
"""make_review_cases.py — Geometry Range Review V2 case builder (EXPLORATORY).

REVIEW ONLY — this is not the production design generator, and the ranges it
reads are **exploratory, not approved**.

It reads ``analysis/geometry_review/ranges_exploratory_v2.yaml`` (extended
exploratory bounds) together with the legacy bounds recorded in that same file,
and writes a case table that satisfies the generator CSV contract
(``docs/GEOMETRY_GENERATOR_CONTRACT.md`` section 2):

    case_id,Xthick,Tmax,Metal2,Solidity,Incidence,Mach,range_id,sampling_id

plus review metadata (allowed by the contract's "extra columns" clause).

V2 case design (~40 cases, boundary-heavy, de-duplicated):

    A  single-parameter boundary scans   new lo / legacy lo / legacy mid /
                                         legacy hi / new hi, one parameter at a
                                         time around the historical midpoint
    B  8 extreme corners of (Xthick, Tmax, Metal2) at the NEW bounds
    C  Solidity x Metal2 coupled boundary + a few combined extremes
    D  4 supplementary maximin-dispersed points (deterministic)

De-duplication key = (Xthick, Tmax, Metal2, Solidity). Incidence/Mach are FIXED
for this review, so two cases differing only in the operating condition would be
byte-identical geometry (verified) and are therefore dropped.

Reported at the end:

    independent single-blade PROFILES   = unique (Xthick, Tmax, Metal2)
    independent CASCADE configurations  = unique (Xthick, Tmax, Metal2, Solidity)

Review case ids use the dedicated V2 block C810001.. so they can never be mixed
with the V1 review block (C8000xx), the production block (C0000xx..) or the
NUMECA bring-up case (C900001).

Usage::

    conda run -n ai4s python analysis/geometry_review/make_review_cases.py
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import yaml

REVIEW_DIR = Path(__file__).resolve().parent
DEFAULT_RANGES = REVIEW_DIR / "ranges_exploratory_v2.yaml"
DEFAULT_OUT = REVIEW_DIR / "review_cases.csv"

GEOMETRY_PARAMS = ("Xthick", "Tmax", "Metal2", "Solidity")
ALL_PARAMS = GEOMETRY_PARAMS + ("Incidence", "Mach")
COLUMNS = ["case_id", *ALL_PARAMS, "range_id", "sampling_id", "group", "note",
           "beyond_legacy", "new_boundary_params", "multi_param_extreme",
           "at_new_lower", "at_new_upper"]

FIRST_CASE_INDEX = 810001
MAXIMIN_COUNT = 4
MAXIMIN_POOL = 2000
ROUND_DECIMALS = 6


def load_config(path: Path):
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    new = {k: tuple(float(v) for v in doc["ranges"][k]) for k in GEOMETRY_PARAMS}
    legacy = {k: tuple(float(v) for v in doc["legacy_ranges"][k])
              for k in GEOMETRY_PARAMS}
    fixed = {k: float(doc["fixed"][k]) for k in ("Incidence", "Mach")}
    meta = {"range_id": doc["range_id"], "sampling_id": doc["sampling_id"],
            "seed": int(doc["random_seed"]),
            "metal1_fixed_deg": float(doc["metal1_fixed_deg"]),
            "status": doc["status"]}
    return new, legacy, fixed, meta


def legacy_mid(legacy):
    return {k: (legacy[k][0] + legacy[k][1]) / 2.0 for k in GEOMETRY_PARAMS}


def maximin_points(new, count, seed, pool_size=MAXIMIN_POOL):
    """Deterministic greedy maximin points inside the NEW 4-D box."""
    keys = list(GEOMETRY_PARAMS)
    lo = np.array([new[k][0] for k in keys])
    hi = np.array([new[k][1] for k in keys])
    rng = np.random.default_rng(seed)
    pool = rng.uniform(lo, hi, size=(pool_size, len(keys)))
    norm = (pool - lo) / (hi - lo)
    best = np.full(pool_size, np.inf)
    chosen = []
    for _ in range(count):
        idx = int(np.argmax(best))          # deterministic tie-break (first max)
        chosen.append(pool[idx])
        best = np.minimum(best, np.linalg.norm(norm - norm[idx], axis=1))
    return chosen


def build(new, legacy, fixed, meta):
    """Return (rows, report) — deduplicated, boundary-annotated V2 cases."""
    mid = legacy_mid(legacy)
    ref = dict(mid)                                   # historical midpoint blade
    rows, seen = [], {}

    def add(values, group, note):
        key = tuple(round(float(values[k]), ROUND_DECIMALS) for k in GEOMETRY_PARAMS)
        if key in seen:
            seen[key]["dup_groups"].append(group)
            return None
        row = {"case_id": f"C{len(rows) + FIRST_CASE_INDEX:06d}", "group": group,
               "note": note, "range_id": meta["range_id"],
               "sampling_id": meta["sampling_id"]}
        for k in GEOMETRY_PARAMS:
            row[k] = repr(float(round(float(values[k]), ROUND_DECIMALS)))
        for k in ("Incidence", "Mach"):
            row[k] = repr(float(fixed[k]))
        seen[key] = {"row": row, "dup_groups": []}
        rows.append(row)
        return row

    # ---- A: single-parameter boundary scans around the historical midpoint
    for param in GEOMETRY_PARAMS:
        scan = []
        for value in (new[param][0], legacy[param][0], mid[param],
                      legacy[param][1], new[param][1]):
            if value not in scan:
                scan.append(value)
        for value in scan:
            values = dict(ref)
            values[param] = value
            tag = ("new_lo" if value == new[param][0] else
                   "legacy_lo" if value == legacy[param][0] else
                   "legacy_hi" if value == legacy[param][1] else
                   "new_hi" if value == new[param][1] else "legacy_mid")
            add(values, "A_single_param", f"{param} scan: {tag} ({value:g})")

    # ---- B: 8 extreme corners of (Xthick, Tmax, Metal2) at the NEW bounds
    for xv in new["Xthick"]:
        for tv in new["Tmax"]:
            for mv in new["Metal2"]:
                add({"Xthick": xv, "Tmax": tv, "Metal2": mv,
                     "Solidity": ref["Solidity"]}, "B_corner",
                    f"new-bound corner Xthick={xv:g} Tmax={tv:g} Metal2={mv:g}")

    # ---- C: Solidity x Metal2 coupled boundary + combined extremes
    for sv in (new["Solidity"][0], new["Solidity"][1]):
        for mv in (new["Metal2"][0], legacy["Metal2"][0], mid["Metal2"],
                   legacy["Metal2"][1], new["Metal2"][1]):
            add({"Xthick": ref["Xthick"], "Tmax": ref["Tmax"], "Metal2": mv,
                 "Solidity": sv}, "C_coupled",
                f"Solidity={sv:g} x Metal2={mv:g} at reference blade")
    for values, note in (
            ({"Xthick": new["Xthick"][1], "Tmax": new["Tmax"][1],
              "Metal2": new["Metal2"][0], "Solidity": new["Solidity"][1]},
             "combined extreme: max Xthick/Tmax, min Metal2, max Solidity"),
            ({"Xthick": new["Xthick"][0], "Tmax": new["Tmax"][0],
              "Metal2": new["Metal2"][1], "Solidity": new["Solidity"][1]},
             "combined extreme: min Xthick/Tmax, max Metal2, max Solidity"),
            ({"Xthick": new["Xthick"][1], "Tmax": new["Tmax"][0],
              "Metal2": new["Metal2"][1], "Solidity": new["Solidity"][0]},
             "combined extreme: max Xthick, min Tmax, max Metal2, min Solidity")):
        add(values, "C_combined", note)

    # ---- D: supplementary maximin-dispersed points
    for point in maximin_points(new, MAXIMIN_COUNT, meta["seed"]):
        add({"Xthick": point[0], "Tmax": point[1], "Metal2": point[2],
             "Solidity": point[3]}, "D_maximin",
            f"maximin-dispersed, seed {meta['seed']}")

    # ---- boundary annotations
    for entry in seen.values():
        row = entry["row"]
        at_lo, at_hi, beyond = [], [], 0
        for k in GEOMETRY_PARAMS:
            value = float(row[k])
            if value == new[k][0]:
                at_lo.append(k)
            if value == new[k][1]:
                at_hi.append(k)
            if not (legacy[k][0] <= value <= legacy[k][1]):
                beyond = 1
        at_bound = at_lo + at_hi
        row["at_new_lower"] = ",".join(at_lo)
        row["at_new_upper"] = ",".join(at_hi)
        row["new_boundary_params"] = ",".join(at_bound)
        row["beyond_legacy"] = beyond
        row["multi_param_extreme"] = int(len(at_bound) >= 3)
        if entry["dup_groups"]:
            row["note"] = (row["note"] + "  [also proposed by: "
                           + ", ".join(entry["dup_groups"]) + "]")

    report = {
        "total": len(rows),
        "groups": {},
        "unique_profiles": len({(r["Xthick"], r["Tmax"], r["Metal2"])
                                for r in rows}),
        "unique_cascades": len({(r["Xthick"], r["Tmax"], r["Metal2"],
                                 r["Solidity"]) for r in rows}),
        "beyond_legacy": sum(int(r["beyond_legacy"]) for r in rows),
        "multi_param_extreme": sum(int(r["multi_param_extreme"]) for r in rows),
        "deduplicated": sum(len(e["dup_groups"]) for e in seen.values()),
    }
    for row in rows:
        report["groups"][row["group"]] = report["groups"].get(row["group"], 0) + 1
    return rows, report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the V2 exploratory Geometry Range Review case table.")
    parser.add_argument("--ranges", default=str(DEFAULT_RANGES),
                        help=f"exploratory ranges YAML (default {DEFAULT_RANGES})")
    parser.add_argument("--output", default=str(DEFAULT_OUT),
                        help=f"review CSV (default {DEFAULT_OUT})")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    ranges_path = Path(args.ranges)
    if not ranges_path.is_file():
        print(f"error: ranges YAML not found: {ranges_path}", file=sys.stderr)
        return 2
    out_path = Path(args.output)
    if out_path.exists() and not args.overwrite:
        print(f"error: {out_path} already exists (use --overwrite)", file=sys.stderr)
        return 2

    new, legacy, fixed, meta = load_config(ranges_path)
    rows, report = build(new, legacy, fixed, meta)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {out_path}")
    print(f"  range_id / sampling_id : {meta['range_id']} / {meta['sampling_id']}")
    print(f"  status                 : {meta['status']}")
    print(f"  case_id block          : C{FIRST_CASE_INDEX:06d}.."
          f"C{FIRST_CASE_INDEX + report['total'] - 1:06d}")
    print(f"  total cases            : {report['total']}")
    for name in sorted(report["groups"]):
        print(f"      {name:16s} {report['groups'][name]}")
    print(f"  beyond legacy range    : {report['beyond_legacy']}")
    print(f"  multi-param extreme    : {report['multi_param_extreme']}")
    print(f"  duplicate proposals    : {report['deduplicated']} dropped")
    print(f"  independent PROFILES   : {report['unique_profiles']}"
          "   (unique Xthick,Tmax,Metal2)")
    print(f"  independent CASCADES   : {report['unique_cascades']}"
          "   (unique Xthick,Tmax,Metal2,Solidity)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
