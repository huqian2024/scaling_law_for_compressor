#!/usr/bin/env python
"""make_review_cases.py — build the Geometry Range Review input table.

REVIEW ONLY. This is **not** the production design generator.

It writes a ~30-case review table that satisfies the generator CSV contract
(``docs/GEOMETRY_GENERATOR_CONTRACT.md`` section 2) so that the **existing**
``code/02_generate_geometry.py`` and ``code/03_geometry_qc.py`` can be run on it
unchanged:

    case_id,Xthick,Tmax,Metal2,Solidity,Incidence,Mach,range_id,sampling_id

Extras (allowed by the contract's "extra columns" clause) are kept for the
reviewer: ``group`` and ``note``.

Design of the 30 cases (all within ``config/ranges_legacy.yaml``; that file is
read, never written):

    G1  reference                    1 case   six-dimensional midpoint
    G2  single-factor +- scan        8 cases  Xthick / Tmax / Metal2 / Solidity
    G3  extreme corner combinations  8 cases  2^3 of (Xthick, Tmax, Metal2)
    G4  Solidity variations          4 cases  on representative blades
    G5  fixed-seed random samples    8 cases  review-only random fill
    G6  operating-condition demo     1 case   same geometry, Incidence/Mach changed

Review case ids use the dedicated block C800001..C800030 so they can never be
confused with the production block (C000001..C120000) or with the NUMECA
bring-up case (C900001).

range_id = legacy_review     (never a production range id)
sampling_id = legacy_review_deterministic | legacy_review_random_seed<N>

Incidence / Mach do **not** affect the legacy geometry (verified: Incidence only
appears in sampling / CSV / print in ``legacy/blade_batch_generation.py``); they
are carried here as inert placeholders.

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

REPO = Path(__file__).resolve().parents[2]
RANGES_YAML = REPO / "config" / "ranges_legacy.yaml"
OUT_CSV = Path(__file__).resolve().parent / "review_cases.csv"

PARAM_ORDER = ("Xthick", "Tmax", "Metal2", "Solidity", "Incidence", "Mach")
COLUMNS = ["case_id", *PARAM_ORDER, "range_id", "sampling_id", "group", "note"]

RANGE_ID = "legacy_review"
SAMP_DET = "legacy_review_deterministic"
RANDOM_SEED = 20261013
RANDOM_SAMPLING_ID = f"legacy_review_random_seed{RANDOM_SEED}"
FIRST_CASE_INDEX = 800001


def _load_ranges(path: Path):
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    block = doc["ranges"]
    ranges = {}
    for name in PARAM_ORDER:
        lo, hi = float(block[name][0]), float(block[name][1])
        ranges[name] = (lo, hi, (lo + hi) / 2.0)
    return ranges


def _fmt(value) -> str:
    """Tidy, deterministic text for one parameter value."""
    return repr(float(round(float(value), 12)))


def build_rows(ranges):
    X = ranges["Xthick"]
    T = ranges["Tmax"]
    M = ranges["Metal2"]
    S = ranges["Solidity"]
    I = ranges["Incidence"]
    A = ranges["Mach"]
    mid = (X[2], T[2], M[2], S[2], I[2], A[2])

    rows = []

    def add(values, group, note):
        cid = f"C{len(rows) + FIRST_CASE_INDEX:06d}"
        row = {"case_id": cid, "group": group, "note": note}
        for name, value in zip(PARAM_ORDER, values):
            row[name] = _fmt(value)
        row["range_id"] = RANGE_ID
        row["sampling_id"] = (RANDOM_SAMPLING_ID if group == "G5_random"
                              else SAMP_DET)
        rows.append(row)

    # G1 — six-dimensional midpoint reference
    add(mid, "G1_reference", "reference midpoint of the legacy ranges")

    # G2 — single-factor +- scan
    for name, lo, hi in (("Xthick", X[0], X[1]), ("Tmax", T[0], T[1]),
                         ("Metal2", M[0], M[1]), ("Solidity", S[0], S[1])):
        for bound, value in (("lo", lo), ("hi", hi)):
            values = list(mid)
            values[PARAM_ORDER.index(name)] = value
            add(values, "G2_single_factor", f"{name}={bound}")

    # G3 — extreme corner combinations of (Xthick, Tmax, Metal2)
    for xv in (X[0], X[1]):
        for tv in (T[0], T[1]):
            for mv in (M[0], M[1]):
                add((xv, tv, mv, S[2], I[2], A[2]), "G3_corner",
                    f"corner Xthick={xv} Tmax={tv} Metal2={mv}")

    # G4 — Solidity variations on representative blades
    for four, note in (
            ((X[0], T[0], M[0], S[0]), "min-turning corner, Solidity=lo"),
            ((X[1], T[1], M[1], S[1]), "max-turning corner, Solidity=hi"),
            ((mid[0], mid[1], mid[2], S[0]), "reference geometry, Solidity=lo"),
            ((mid[0], mid[1], mid[2], S[1]), "reference geometry, Solidity=hi")):
        add((*four, I[2], A[2]), "G4_solidity", note)

    # G5 — fixed-seed random fill inside the legacy ranges
    rng = np.random.default_rng(RANDOM_SEED)
    lows = [ranges[n][0] for n in PARAM_ORDER]
    highs = [ranges[n][1] for n in PARAM_ORDER]
    for values in rng.uniform(lows, highs, size=(8, len(PARAM_ORDER))):
        add(values, "G5_random", f"fixed seed {RANDOM_SEED}")

    # G6 — operating-condition invariance demonstration (geometry unchanged)
    add((mid[0], mid[1], mid[2], mid[3], I[1], A[1]), "G6_invariance_demo",
        "reference geometry, Incidence=hi Mach=hi (geometry must be identical)")
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the Geometry Range Review input table (review only).")
    parser.add_argument("--ranges", default=str(RANGES_YAML),
                        help=f"ranges YAML, read-only (default {RANGES_YAML})")
    parser.add_argument("--output", default=str(OUT_CSV),
                        help=f"review CSV (default {OUT_CSV})")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    ranges_path = Path(args.ranges)
    if not ranges_path.is_file():
        print(f"error: ranges YAML not found: {ranges_path}", file=sys.stderr)
        return 2
    out_path = Path(args.output)
    if out_path.exists() and not args.overwrite:
        print(f"error: {out_path} already exists (use --overwrite)",
              file=sys.stderr)
        return 2

    rows = build_rows(_load_ranges(ranges_path))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    groups = {}
    for row in rows:
        groups[row["group"]] = groups.get(row["group"], 0) + 1
    print(f"wrote {out_path}  ({len(rows)} cases)")
    for name in sorted(groups):
        print(f"  {name:22s} {groups[name]}")
    print(f"  case_id block        C{FIRST_CASE_INDEX:06d}.."
          f"C{FIRST_CASE_INDEX + len(rows) - 1:06d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
