#!/usr/bin/env python
"""run_geomturbo.py — group-aware launcher for the frozen 11-D GeomTurbo entry.

ONE COMMAND = EXPLICIT AUTHORIZATION
------------------------------------
Running this script without ``--plan`` calls
``code/generate_geomturbo_production.py`` with ``--execute``.  The generator's
own safety mechanisms are kept unchanged (frozen config validation, snapshot
fingerprint, atomic case writes, sha256 verification, refuse-to-mix, --resume).
This script only validates the arguments, resolves the dataset group's output
directory and forwards the call.

Groups / identity
-----------------
``--group {train,val,test}`` selects an independent output directory:

    production_geomturbo/train/
    production_geomturbo/val/
    production_geomturbo/test/

Each group keeps its own ``config_snapshot.yaml``, ``manifest.csv``, batch
manifests and ``generation_summary.json``.  ``case_id`` (G0000001 ...) restarts
in every group, so the global sample identity is::

    (group, seed, sobol_index)

which is also recorded in ``group_info.json`` inside the group directory.  The
frozen case-id format is NOT changed.

N is a CANDIDATE GEOMETRY count, not a usable CFD case count.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CODE_DIR = Path(__file__).resolve().parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

import generate_geomturbo_production as prod  # noqa: E402

GROUPS = ("train", "val", "test")
DEFAULT_ROOT = REPO_ROOT / "production_geomturbo"
DEFAULT_CONFIG = REPO_ROOT / "config" / "geometry_ranges_frozen_a.yaml"
GROUP_INFO_NAME = "group_info.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_geomturbo.py",
        description=("Group-aware GeomTurbo production launcher. Running it "
                     "without --plan explicitly authorizes geometry generation "
                     "(the frozen generator is called with --execute)."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("examples:\n"
                "  plan   : python code/run_geomturbo.py --group train "
                "--N 150000 --seed 101 --plan\n"
                "  run    : python code/run_geomturbo.py --group train "
                "--N 150000 --seed 101\n"
                "  resume : python code/run_geomturbo.py --group train "
                "--N 150000 --seed 101 --resume\n"))
    parser.add_argument("--group", required=True, choices=GROUPS,
                        help="dataset group: train / val / test "
                             "(selects production_geomturbo/<group>/)")
    parser.add_argument("--N", dest="n", type=int, required=True,
                        metavar="INT",
                        help="number of candidate geometries (positive integer; "
                             "NOT the number of usable CFD cases)")
    parser.add_argument("--seed", type=int, required=True, metavar="INT",
                        help="Sobol scramble seed (non-negative integer; keep it "
                             "identical when resuming)")
    parser.add_argument("--resume", action="store_true",
                        help="continue the existing group directory "
                             "(same config/seed/N or a larger N)")
    parser.add_argument("--plan", action="store_true",
                        help="read-only preview; never writes a file or directory")
    parser.add_argument("--output-dir", dest="output_dir", default=None,
                        metavar="PATH",
                        help="override the default "
                             "production_geomturbo/<group> directory")
    return parser


def validate_args(args) -> None:
    max_count = 10 ** prod.CASE_WIDTH - 1
    if args.n < 1:
        raise ValueError(f"--N must be >= 1, got {args.n}")
    if args.n > max_count:
        raise ValueError(
            f"--N must be <= {max_count} (frozen case_id width "
            f"{prod.CASE_WIDTH}), got {args.n}")
    if args.seed < 0:
        raise ValueError(f"--seed must be >= 0, got {args.seed}")
    if args.plan and args.resume:
        raise ValueError("--plan and --resume cannot be combined "
                         "(--plan never writes or repairs anything)")


def resolve_output_dir(args) -> Path:
    if args.output_dir:
        return Path(args.output_dir).expanduser().resolve()
    return (DEFAULT_ROOT / args.group).resolve()


def build_generator_argv(args, output_dir: Path) -> list[str]:
    argv = [
        "--config", str(DEFAULT_CONFIG),
        "--count", str(args.n),
        "--seed", str(args.seed),
        "--output-dir", str(output_dir),
    ]
    if args.plan:
        argv.append("--plan")
    else:
        argv.append("--execute")
        if args.resume:
            argv.append("--resume")
    return argv


def _write_group_info(args, output_dir: Path) -> None:
    """Record the group-qualified identity next to the run's own snapshot.

    Only called for a run that was not refused by the generator (exit code 2),
    and only when the existing snapshot seed matches ``--seed``.  A ``--plan``
    run therefore never adds files to the directory.
    """
    if args.plan:
        return
    snapshot = output_dir / prod.SNAPSHOT_NAME
    if not snapshot.is_file():
        return
    snap = prod._read_snapshot(snapshot)
    try:
        snapshot_seed = int(snap.get("seed"))
    except (TypeError, ValueError):
        print(f"warning: {snapshot} has no readable seed; "
              f"{GROUP_INFO_NAME} not updated", file=sys.stderr)
        return
    if snapshot_seed != int(args.seed):
        print(f"warning: existing snapshot seed={snapshot_seed} differs from "
              f"--seed {args.seed}; {GROUP_INFO_NAME} not updated",
              file=sys.stderr)
        return
    payload = {
        "group": args.group,
        "seed": int(args.seed),
        "N_candidates": int(args.n),
        "output_dir": str(output_dir),
        "global_identity": "group + seed + sobol_index",
        "case_id_format": "G + 7 digits (repeats inside every group)",
        "config_path": str(DEFAULT_CONFIG),
        "config_snapshot": str(output_dir / prod.SNAPSHOT_NAME),
        "resume": bool(args.resume),
        "written_at": datetime.now(timezone.utc).astimezone().isoformat(
            timespec="seconds"),
        "note": ("N is a candidate geometry count, not a usable CFD case count. "
                 "Geometry generation only; no mesh, no NUMECA, no CFX, no CFD."),
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    prod._atomic_write_text(output_dir / GROUP_INFO_NAME, text)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        validate_args(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return prod.EXIT_CLI

    output_dir = resolve_output_dir(args)
    print(f"group             : {args.group}")
    print(f"N (candidates)    : {args.n}")
    print(f"seed              : {args.seed}")
    print(f"output dir        : {output_dir}")
    print("global identity   : group + seed + sobol_index")
    if args.plan:
        print("mode              : PLAN ONLY (read-only)")
    else:
        print(f"mode              : EXECUTE (resume={args.resume})")
    print("-" * 72, flush=True)

    code = prod.main(build_generator_argv(args, output_dir))
    if code != prod.EXIT_CLI:
        try:
            _write_group_info(args, output_dir)
        except Exception as exc:  # noqa: BLE001 - never alter the run's exit code
            print(f"warning: could not write {GROUP_INFO_NAME}: {exc}",
                  file=sys.stderr)
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("error: interrupted by user", file=sys.stderr)
        sys.exit(prod.EXIT_INTERRUPTED)
