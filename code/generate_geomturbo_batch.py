#!/usr/bin/env python
"""generate_geomturbo_batch.py — one-command production-prep orchestration.

Status::

    PRODUCTION GENERATOR PREPARED
    EXECUTION BLOCKED PENDING FINAL_PRODUCTION_RANGES

This program is **orchestration only**. It never copies, reimplements or alters
any geometry mathematics; it calls the existing frozen tools as child processes::

    stage 1  code/01_generate_design.py
             Sobol design -> master_design.csv + fixed train/test split
    stage 2  code/02_generate_geometry.py
             batch profile + .geomTurbo generation
    stage 3  code/03_geometry_qc.py
             batch Geometry QC report

Frozen contracts reused unchanged::

    docs/GEOMETRY_GENERATOR_CONTRACT.md   (FROZEN V1.2)
    docs/GEOMETRY_QC_CONTRACT.md          (FROZEN V1)

Frozen production design policy (unchanged, not configurable here)::

    method   = scipy.stats.qmc.Sobol
    d        = 6
    scramble = True
    seed     = 1
    ordering = native Sobol sequence order
    nesting  = prefix nesting

The only switch point for future production ranges is `--ranges PATH`.

Resume / idempotency::

    already valid / byte-matching case -> SKIP_MATCH (skipped)
    missing case                       -> generated
    conflicting existing case          -> reported, never silently deleted

Exit codes::

    0 = all executed stages completed with their own success semantics
    2 = CLI / configuration failure
    3 = an executed stage reported unresolved conflicts
    4 = an executed stage reported an operational failure

A child exit code is propagated as-is (0/2/3/4). Per the frozen QC contract,
`geometry_ok = false` for a case is a QC FINDING, not an operational failure; it
is reported in `qc_fail` and does NOT by itself change the process exit code.

Memory behaviour::

    stages are executed as separate processes; geometry text is generated
    case-by-case and written by the frozen generator, so a full 120000-case
    geometry-text batch is never held in RAM here. Progress is streamed.

Dry-run::

    stage 1 and stage 2 are executed with --dry-run (prediction only);
    stage 3 is SKIPPED because a dry-run writes no geometry artifacts to inspect.

KNOWN RESOURCE NOTE (frozen QC, not modified here)::

    code/03_geometry_qc.py accumulates one result record per case in memory
    while building its report. For very large batches (e.g. 120000 cases) expect
    a correspondingly large RSS. This is a property of the frozen QC tool and is
    reported here, not patched.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CODE_DIR = REPO_ROOT / "code"

DESIGN_SCRIPT = CODE_DIR / "01_generate_design.py"
GEOMETRY_SCRIPT = CODE_DIR / "02_generate_geometry.py"
QC_SCRIPT = CODE_DIR / "03_geometry_qc.py"

DEFAULT_TEMPLATE = "legacy/blade_batch_generation_template.geomTurbo"
DEFAULT_RANGES = "config/ranges_legacy.yaml"
DEFAULT_DESIGN_OUTPUT = "design/master_design.csv"
DEFAULT_SPLIT_OUTPUT = "design/splits/fixed_train_test.csv"
DEFAULT_GEOMETRY_ROOT = "geometry"
DEFAULT_QC_OUTPUT = "geometry/geometry_qc.csv"

DEFAULT_N_TRAIN = 100000
DEFAULT_N_TEST = 20000
DEFAULT_PROGRESS_EVERY = 2000

EXIT_OK = 0
EXIT_CLI = 2
EXIT_CONFLICT = 3
EXIT_ERROR = 4


class CliError(Exception):
    """CLI / configuration failure -> exit code 2."""


def _display(path: Path) -> str:
    """Repo-relative display path when possible."""
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _emit(obj) -> None:
    sys.stdout.write(json.dumps(obj, sort_keys=True) + "\n")


def _count_csv_data_rows(path: Path):
    """Number of data rows in a CSV file, or None when it does not exist."""
    if not path.is_file():
        return None
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            return max(sum(1 for _ in csv.reader(handle)) - 1, 0)
    except OSError:
        return None


_PROGRESS_KEYS = ("created", "skipped", "conflict", "failed",
                  "would_overwrite", "pass", "fail", "other")


def _progress(label, state, expected_total) -> None:
    total = expected_total if expected_total else "?"
    parts = [f"completed={state.get('cases', 0)}/{total}"]
    for key in _PROGRESS_KEYS:
        if key in state:
            parts.append(f"{key}={state[key]}")
    sys.stderr.write(f"[{label}] " + " ".join(parts) + "\n")
    sys.stderr.flush()


def _run_stage(label, cmd, classify, progress_every, expected_total, verbose):
    """Run one child stage, streaming its JSONL stdout line by line."""
    state = {"cases": 0}
    with tempfile.TemporaryFile("w+", encoding="utf-8") as errfile:
        try:
            proc = subprocess.Popen(cmd, cwd=str(REPO_ROOT),
                                    stdout=subprocess.PIPE, stderr=errfile,
                                    text=True)
        except OSError as exc:
            raise CliError(f"cannot start the {label} stage: {exc}")
        sys.stderr.write(f"[{label}] start: " + " ".join(cmd) + "\n")
        sys.stderr.flush()
        try:
            for raw in proc.stdout:
                line = raw.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    state["malformed_lines"] = state.get("malformed_lines", 0) + 1
                    sys.stderr.write(f"[{label}] non-JSON output: {line[:200]}\n")
                    continue
                if verbose:
                    sys.stdout.write(line + "\n")
                classify(event, state)
                if (progress_every and state["cases"]
                        and state["cases"] % progress_every == 0):
                    _progress(label, state, expected_total)
        finally:
            try:
                proc.stdout.close()
            except OSError:
                pass
        exit_code = proc.wait()
        errfile.seek(0)
        stderr_text = errfile.read().strip()

    state["exit_code"] = exit_code
    state["stderr"] = stderr_text
    if progress_every and state["cases"]:
        _progress(label, state, expected_total)
    if stderr_text:
        sys.stderr.write(f"[{label}] stderr: {stderr_text}\n")
    sys.stderr.flush()
    return state


_GEOMETRY_ACTION_COUNTER = {
    "CREATE": "created",
    "OVERWRITE": "created",
    "WOULD_OVERWRITE": "would_overwrite",
    "SKIP_MATCH": "skipped",
    "CONFLICT_PARTIAL": "conflict",
    "CONFLICT_CONTENT": "conflict",
    "ERROR": "failed",
}


def _classify_design(event, state):
    if event.get("type") == "summary":
        state["summary"] = event
    else:
        state["files"] = state.get("files", 0) + 1


def _classify_geometry(event, state):
    kind = event.get("type")
    if kind == "case":
        state["cases"] += 1
        key = _GEOMETRY_ACTION_COUNTER.get(event.get("action"), "other")
        state[key] = state.get(key, 0) + 1
    elif kind == "summary":
        state["summary"] = event


def _classify_qc(event, state):
    kind = event.get("type")
    if kind == "case":
        state["cases"] += 1
        key = "pass" if event.get("geometry_ok") is True else "fail"
        state[key] = state.get(key, 0) + 1
    elif kind == "summary":
        state["summary"] = event


def _final_report(requested, design_count, design_state, geom_state, qc_state,
                  paths, note=None):
    geom = geom_state or {}
    qc = qc_state or {}
    report = {
        "type": "summary",
        "requested_count": requested,
        "design_count": design_count,
        "geometry_created": geom.get("created", 0),
        "geometry_skipped": geom.get("skipped", 0),
        "geometry_failed": geom.get("failed", 0),
        "geometry_conflict": geom.get("conflict", 0),
        "geometry_would_overwrite": geom.get("would_overwrite", 0),
        "geometry_other": geom.get("other", 0),
        "qc_pass": qc.get("pass", 0),
        "qc_fail": qc.get("fail", 0),
        "design_stage_exit_code": (None if design_state is None
                                   else design_state["exit_code"]),
        "geometry_stage_exit_code": (None if geom_state is None
                                     else geom_state["exit_code"]),
        "qc_stage_exit_code": (None if qc_state is None
                               else qc_state["exit_code"]),
        "design_output_path": _display(paths["design"]),
        "split_output_path": _display(paths["split"]),
        "geometry_root": _display(paths["geometry"]),
        "qc_output_path": _display(paths["qc"]),
    }
    if note:
        report["note"] = note
    return report


def run(args):
    if args.n_train < 1:
        raise CliError(f"--n-train must be >= 1, got {args.n_train}")
    if args.n_test < 0:
        raise CliError(f"--n-test must be >= 0, got {args.n_test}")
    if args.progress_every < 0:
        raise CliError(f"--progress-every must be >= 0, got {args.progress_every}")

    ranges = Path(args.ranges)
    if not ranges.is_file():
        raise CliError(f"ranges YAML not found or not a file: {ranges}")
    template = Path(args.template)
    if not template.is_file():
        raise CliError(f"geomTurbo template not found or not a file: {template}")

    paths = {
        "design": Path(args.design_output),
        "split": Path(args.split_output),
        "geometry": Path(args.geometry_root),
        "qc": Path(args.qc_output),
    }
    requested = args.n_train + args.n_test

    _emit({
        "type": "manifest",
        "requested_count": requested,
        "n_train": args.n_train,
        "n_test": args.n_test,
        "ranges": _display(ranges),
        "template": _display(template),
        "design_output": _display(paths["design"]),
        "split_output": _display(paths["split"]),
        "geometry_root": _display(paths["geometry"]),
        "qc_output": _display(paths["qc"]),
        "dry_run": bool(args.dry_run),
        "overwrite": bool(args.overwrite),
        "ranges_are_runtime_configurable": True,
    })

    # -------------------------- stage 1: design --------------------------
    design_state = None
    if args.skip_design:
        if not paths["design"].is_file():
            raise CliError("--skip-design requires an existing design file: "
                           f"{paths['design']}")
        sys.stderr.write(f"[design] skipped (--skip-design); reusing "
                         f"{_display(paths['design'])}\n")
    else:
        cmd = [sys.executable, str(DESIGN_SCRIPT),
               "--ranges", str(ranges),
               "--n-train", str(args.n_train),
               "--n-test", str(args.n_test),
               "--output", str(paths["design"]),
               "--split-output", str(paths["split"])]
        if args.dry_run:
            cmd.append("--dry-run")
        if args.overwrite:
            cmd.append("--overwrite")
        design_state = _run_stage("design", cmd, _classify_design,
                                  args.progress_every, requested, args.verbose)
        _emit({"type": "stage", "stage": "design",
               "exit_code": design_state["exit_code"],
               "summary": design_state.get("summary")})
        if design_state["exit_code"] != EXIT_OK:
            _emit(_final_report(
                requested, _count_csv_data_rows(paths["design"]),
                design_state, None, None, paths,
                note="stopped after the design stage; "
                     "geometry and QC were not run"))
            return design_state["exit_code"]

    # ------------------------- stage 2: geometry -------------------------
    cmd = [sys.executable, str(GEOMETRY_SCRIPT),
           "--input", str(paths["design"]),
           "--template", str(template),
           "--output", str(paths["geometry"])]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.overwrite:
        cmd.append("--overwrite")
    geom_state = _run_stage("geometry", cmd, _classify_geometry,
                            args.progress_every, requested, args.verbose)
    _emit({"type": "stage", "stage": "geometry",
           "exit_code": geom_state["exit_code"],
           "summary": geom_state.get("summary")})
    if geom_state["exit_code"] != EXIT_OK:
        _emit(_final_report(
            requested, _count_csv_data_rows(paths["design"]),
            design_state, geom_state, None, paths,
            note="stopped after the geometry stage; conflicting/failed cases "
                 "were reported and NOT deleted. QC was not run."))
        return geom_state["exit_code"]

    # --------------------------- stage 3: QC ----------------------------
    qc_state = None
    if args.dry_run:
        sys.stderr.write("[qc] skipped (--dry-run writes no geometry "
                         "artifacts to inspect)\n")
    else:
        cmd = [sys.executable, str(QC_SCRIPT),
               "--input", str(paths["design"]),
               "--geometry", str(paths["geometry"]),
               "--output", str(paths["qc"])]
        if args.overwrite:
            cmd.append("--overwrite")
        qc_state = _run_stage("qc", cmd, _classify_qc,
                              args.progress_every, requested, args.verbose)
        _emit({"type": "stage", "stage": "qc",
               "exit_code": qc_state["exit_code"],
               "summary": qc_state.get("summary")})

    report = _final_report(requested, _count_csv_data_rows(paths["design"]),
                           design_state, geom_state, qc_state, paths)
    if args.dry_run:
        report["note"] = ("dry-run: no files were written; QC stage skipped. "
                          "geometry_created/would_overwrite are predictions.")
    _emit(report)

    if qc_state is not None and qc_state.get("fail", 0) > 0:
        sys.stderr.write(
            f"[qc] {qc_state['fail']} case(s) did NOT pass the geometry hard "
            "gates. Per the frozen QC contract this is a QC finding, not an "
            "operational failure: the report above is authoritative and no "
            "geometry was modified or deleted.\n")

    if design_state is not None and design_state["exit_code"] != EXIT_OK:
        return design_state["exit_code"]
    if geom_state is not None and geom_state["exit_code"] != EXIT_OK:
        return geom_state["exit_code"]
    if qc_state is not None and qc_state["exit_code"] != EXIT_OK:
        return qc_state["exit_code"]
    return EXIT_OK


def build_parser():
    parser = argparse.ArgumentParser(
        prog="generate_geomturbo_batch.py",
        description="One-command production-prep orchestration: "
                    "Sobol design -> geometry batch -> Geometry QC.")
    parser.add_argument("--ranges", required=True, metavar="PATH",
                        help="ranges YAML (the only switch point for going to "
                             "the future production ranges)")
    parser.add_argument("--n-train", dest="n_train", type=int,
                        default=DEFAULT_N_TRAIN, metavar="INT",
                        help=f"usable training cases (default {DEFAULT_N_TRAIN})")
    parser.add_argument("--n-test", dest="n_test", type=int,
                        default=DEFAULT_N_TEST, metavar="INT",
                        help=f"fixed test cases (default {DEFAULT_N_TEST})")
    parser.add_argument("--design-output", dest="design_output",
                        default=DEFAULT_DESIGN_OUTPUT, metavar="PATH",
                        help=f"master design CSV (default {DEFAULT_DESIGN_OUTPUT})")
    parser.add_argument("--split-output", dest="split_output",
                        default=DEFAULT_SPLIT_OUTPUT, metavar="PATH",
                        help=f"fixed train/test split CSV (default {DEFAULT_SPLIT_OUTPUT})")
    parser.add_argument("--geometry-root", dest="geometry_root",
                        default=DEFAULT_GEOMETRY_ROOT, metavar="PATH",
                        help=f"geometry root, profiles/ + geomturbo/ "
                             f"(default {DEFAULT_GEOMETRY_ROOT})")
    parser.add_argument("--qc-output", dest="qc_output",
                        default=DEFAULT_QC_OUTPUT, metavar="PATH",
                        help=f"QC report CSV (default {DEFAULT_QC_OUTPUT})")
    parser.add_argument("--template", default=DEFAULT_TEMPLATE, metavar="PATH",
                        help=f".geomTurbo template (default {DEFAULT_TEMPLATE})")
    parser.add_argument("--skip-design", dest="skip_design", action="store_true",
                        help="reuse an existing design CSV (resume helper)")
    parser.add_argument("--progress-every", dest="progress_every", type=int,
                        default=DEFAULT_PROGRESS_EVERY, metavar="INT",
                        help="print a progress line every INT cases "
                             f"(default {DEFAULT_PROGRESS_EVERY}; 0 disables)")
    parser.add_argument("--dry-run", action="store_true",
                        help="predict only; nothing is written")
    parser.add_argument("--overwrite", action="store_true",
                        help="allow replacing existing differing outputs")
    parser.add_argument("--verbose", action="store_true",
                        help="echo the child stages' JSONL lines to stdout")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_CLI
    except KeyboardInterrupt:
        print("error: interrupted by user", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:  # noqa: BLE001 - operational failure -> exit 4
        print(f"error: batch orchestration operational failure: "
              f"{exc.__class__.__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
