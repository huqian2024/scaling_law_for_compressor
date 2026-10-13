#!/usr/bin/env python
"""01_generate_design.py — production design generator (frozen Sobol policy).

Status::

    PRODUCTION GENERATOR PREPARED
    EXECUTION BLOCKED PENDING FINAL_PRODUCTION_RANGES

Strict scope::

    read ranges YAML
      -> generate the frozen scrambled-Sobol master points
      -> scale the 6 dimensions into the physical ranges
      -> assign production case_id
      -> write master_design.csv
      -> write the fixed train/test split metadata

NON-GOALS (do not add these here)::

    NO geometry / profile / .geomTurbo generation
    NO mesh, NO NUMECA, NO CFX, NO CFD-Post
    NO Geometry QC verdict
    NO validation-set design
    NO CFD failure reserve / raw-attempt policy

Frozen production design policy (docs/DESIGN_FREEZE_2026-10-13.md and
docs/DOE_DECISION.md; do not change without an explicit human decision)::

    method   = scipy.stats.qmc.Sobol
    d        = 6
    scramble = True
    seed     = 1
    ordering = native Sobol sequence order
    nesting  = prefix nesting

    m = smallest integer with 2^m >= n_train + n_test
    master = qmc.Sobol(d=6, scramble=True, seed=1).random_base2(m)
    used   = master[:n_train + n_test]      # native order, no sorting

`m` is computed from the requested counts; the value 17 is NOT hard-coded.

Train/test assignment (frozen)::

    first n_train requested cases -> split "train"
    next  n_test  requested cases -> split "test"

disjoint / deterministic / reproducible / fixed.

Parameter order (frozen)::

    0 Xthick
    1 Tmax
    2 Metal2
    3 Solidity
    4 Incidence
    5 Mach

Geometry depends only on Xthick / Tmax / Metal2 / Solidity. Incidence / Mach are
carried in the design for the later operating-condition stage and MUST NOT enter
geometry.

Input ranges YAML contract (this file is the ONLY switch point for switching to
the future production ranges)::

    ranges:
      Xthick:    [lo, hi]
      Tmax:      [lo, hi]
      Metal2:    [lo, hi]
      Solidity:  [lo, hi]
      Incidence: [lo, hi]
      Mach:      [lo, hi]

    # optional identity metadata
    range_id:        <default: "<dataset_version>/core", else "unknown">
    sampling_id:     <default: "sobol_scrambled_v1">
    dataset_version: <optional, e.g. "legacy">

No range number is hard-coded in this program.

Output contract::

    master_design.csv:
        case_id,Xthick,Tmax,Metal2,Solidity,Incidence,Mach,range_id,sampling_id,split

    split CSV (default design/splits/fixed_train_test.csv):
        case_id,split

The extra `split` column is explicitly allowed by the frozen generator contract
(docs/GEOMETRY_GENERATOR_CONTRACT.md, "extra columns"); the identical split
information is also written to the standalone split CSV.

Safety / determinism::

    byte-stable output for a fixed environment (frozen SciPy version)
    streaming write (never holds all rendered text in RAM)
    atomic single-file write (temp file in the target directory + os.replace)
    existing matching output -> SKIP_MATCH (no rewrite)
    different existing output -> CONFLICT_CONTENT unless --overwrite
    --dry-run leaves the project tree unchanged

Exit codes (aligned with code/02_generate_geometry.py)::

    0 = OK (CREATE / SKIP_MATCH / OVERWRITE / clean dry-run)
    2 = CLI / input / ranges-YAML contract failure
    3 = unresolved CONFLICT_CONTENT (no --overwrite)
    4 = operational failure (I/O, generation error)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml
from scipy.stats import qmc

# --- Frozen production design policy (do not change) -----------------------
PARAM_ORDER = ("Xthick", "Tmax", "Metal2", "Solidity", "Incidence", "Mach")
SOBOL_DIM = 6
SOBOL_SCRAMBLE = True
SOBOL_SEED = 1
SOBOL_ORDERING = "native"
SOBOL_NESTING = "prefix"

DEFAULT_SAMPLING_ID = "sobol_scrambled_v1"
DEFAULT_RANGE_ID = "unknown"

CASE_ID_WIDTH = 6
CASE_ID_RE = re.compile(r"^C[0-9]{6}$")
MAX_CASE_INDEX = 10 ** CASE_ID_WIDTH - 1        # 999999

# Production-only reserved IDs: a NUMECA bring-up case must never enter the
# production master pool (requirement: do not delete or modify it).
BRINGUP_RESERVED_CASE_IDS = ("C900001",)

DESIGN_COLUMNS = ["case_id", *PARAM_ORDER, "range_id", "sampling_id", "split"]
SPLIT_COLUMNS = ["case_id", "split"]

# --- Frozen action vocabulary / exit codes (aligned with 02) ---------------
CREATE = "CREATE"
SKIP_MATCH = "SKIP_MATCH"
CONFLICT_CONTENT = "CONFLICT_CONTENT"
WOULD_OVERWRITE = "WOULD_OVERWRITE"
OVERWRITE = "OVERWRITE"
ERROR = "ERROR"

EXIT_OK = 0
EXIT_CLI = 2
EXIT_CONFLICT = 3
EXIT_ERROR = 4


class CliError(Exception):
    """CLI / input contract failure -> exit code 2."""


def _emit(obj) -> None:
    sys.stdout.write(json.dumps(obj, sort_keys=True) + "\n")


def _case_id(index: int) -> str:
    """1-based index -> C###### production case_id."""
    return f"C{index:0{CASE_ID_WIDTH}d}"


def _fmt(value) -> str:
    """Deterministic, round-trip-exact float text."""
    return repr(float(value))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Ranges YAML
# ---------------------------------------------------------------------------
def _load_ranges(path: Path):
    """Return (ranges, range_id, sampling_id, ranges_sha256).

    Only the `ranges:` mapping drives the six physical dimensions; this file is
    the single authorised switch point for future production ranges.
    """
    if not path.is_file():
        raise CliError(f"ranges YAML not found or not a file: {path}")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CliError(f"ranges YAML unreadable: {path}: {exc}")
    sha256 = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CliError(f"ranges YAML is not valid UTF-8: {path}: {exc}")
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CliError(f"ranges YAML parse error: {path}: {exc}")
    if not isinstance(doc, dict):
        raise CliError(f"ranges YAML must be a mapping at top level: {path}")
    block = doc.get("ranges")
    if not isinstance(block, dict):
        raise CliError(f"ranges YAML must contain a `ranges:` mapping: {path}")

    ranges = {}
    for name in PARAM_ORDER:
        if name not in block:
            raise CliError(f"ranges YAML missing required range: {name}")
        pair = block[name]
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise CliError(f"range {name} must be a 2-element [lo, hi] list")
        try:
            lo, hi = float(pair[0]), float(pair[1])
        except (TypeError, ValueError):
            raise CliError(f"range {name} must contain numeric lo/hi values")
        if not (math.isfinite(lo) and math.isfinite(hi)):
            raise CliError(f"range {name} must be finite, got [{lo}, {hi}]")
        if not lo < hi:
            raise CliError(f"range {name} must satisfy lo < hi, got [{lo}, {hi}]")
        ranges[name] = (lo, hi)

    # Minimal mathematical preconditions that the geometry core itself requires.
    if not (0.0 < ranges["Xthick"][0] and ranges["Xthick"][1] < 1.0):
        raise CliError("range Xthick must satisfy 0 < lo and hi < 1 "
                       "(geometry-core precondition)")
    if ranges["Solidity"][0] <= 0.0:
        raise CliError("range Solidity must satisfy lo > 0 "
                       "(geometry-core precondition)")

    dataset_version = doc.get("dataset_version")
    range_id = doc.get("range_id")
    if not (isinstance(range_id, str) and range_id.strip()):
        if isinstance(dataset_version, str) and dataset_version.strip():
            range_id = f"{dataset_version.strip()}/core"
        else:
            range_id = DEFAULT_RANGE_ID
    sampling_id = doc.get("sampling_id")
    if not (isinstance(sampling_id, str) and sampling_id.strip()):
        sampling_id = DEFAULT_SAMPLING_ID
    return ranges, range_id.strip(), sampling_id.strip(), sha256


# ---------------------------------------------------------------------------
# Frozen Sobol master sequence
# ---------------------------------------------------------------------------
def _sobol_m(total: int) -> int:
    """Smallest integer m with 2^m >= total (exact integer arithmetic)."""
    m = 0
    while (1 << m) < total:
        m += 1
    return m


def _sobol_points(total: int):
    """Return (used_points, m) of the frozen scrambled-Sobol master sequence."""
    m = _sobol_m(total)
    engine = qmc.Sobol(d=SOBOL_DIM, scramble=SOBOL_SCRAMBLE, seed=SOBOL_SEED)
    master = engine.random_base2(m)
    return master[:total], m


# ---------------------------------------------------------------------------
# Row generation (streaming: no full-rendered-text buffering)
# ---------------------------------------------------------------------------
def _iter_design_rows(points, ranges, range_id, sampling_id, n_train):
    """Yield the master-design rows in request order (train first, then test)."""
    for index in range(points.shape[0]):
        point = points[index]
        row = {"case_id": _case_id(index + 1)}
        for dim, name in enumerate(PARAM_ORDER):
            lo, hi = ranges[name]
            row[name] = _fmt(lo + float(point[dim]) * (hi - lo))
        row["range_id"] = range_id
        row["sampling_id"] = sampling_id
        row["split"] = "train" if (index + 1) <= n_train else "test"
        yield row


def _iter_split_rows(points, n_train):
    """Yield the fixed train/test split rows (same order as the design)."""
    for index in range(points.shape[0]):
        yield {
            "case_id": _case_id(index + 1),
            "split": "train" if (index + 1) <= n_train else "test",
        }


def _write_csv(path: Path, columns, rows) -> None:
    """Stream rows to an LF-only UTF-8 CSV, then fsync."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())


def _new_candidate(target: Path, dry_run: bool):
    """Return (candidate_path, cleanup_callable) for one target.

    Real writes place the temp file in the target directory so that the final
    ``os.replace`` is an atomic rename on the same filesystem. A dry-run places
    it in the system temp directory, so the project tree stays unchanged.
    """
    if dry_run:
        tmpdir = Path(tempfile.mkdtemp(prefix="design-dryrun-"))
        return tmpdir / f"{target.name}.candidate", \
            (lambda: shutil.rmtree(tmpdir, ignore_errors=True))
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(
        dir=str(target.parent), prefix=".tmp-" + target.name + "-", suffix=".part")
    os.close(fd)
    candidate = Path(name)

    def cleanup():
        try:
            os.unlink(candidate)
        except OSError:
            pass

    return candidate, cleanup


def _plan_target(target: Path, candidate: Path):
    """Return (base_action, reason) from filesystem state only."""
    if target.is_dir():
        return ERROR, f"output path obstruction: {target} is a directory"
    if not target.is_file():
        return CREATE, "output does not exist"
    try:
        same = _sha256_file(target) == _sha256_file(candidate)
    except OSError as exc:
        return ERROR, f"existing output unreadable: {target}: {exc}"
    if same:
        return SKIP_MATCH, "existing output already matches candidate"
    return CONFLICT_CONTENT, "existing output differs from candidate"


def _decide(base_action, dry_run, overwrite):
    """Apply the frozen overwrite policy to a base action."""
    if base_action == CONFLICT_CONTENT:
        if not overwrite:
            return CONFLICT_CONTENT
        return WOULD_OVERWRITE if dry_run else OVERWRITE
    return base_action


def _reason_for(action, dry_run):
    if action == CREATE:
        return "outputs would be created" if dry_run else "outputs created"
    if action == SKIP_MATCH:
        return "existing outputs already match candidate"
    if action == CONFLICT_CONTENT:
        return "existing output differs from candidate; no overwrite"
    if action == WOULD_OVERWRITE:
        return "existing output would be replaced (dry-run)"
    if action == OVERWRITE:
        return "existing mismatching output replaced"
    return ""


def _validate_counts(n_train: int, n_test: int) -> int:
    if n_train < 1:
        raise CliError(f"--n-train must be >= 1, got {n_train}")
    if n_test < 0:
        raise CliError(f"--n-test must be >= 0, got {n_test}")
    total = n_train + n_test
    if total > MAX_CASE_INDEX:
        raise CliError(
            f"requested total {total} exceeds the C###### case_id space "
            f"({MAX_CASE_INDEX})")
    for index in (1, total):
        cid = _case_id(index)
        if not CASE_ID_RE.match(cid):
            raise CliError(f"generated case_id {cid!r} violates the "
                           "C###### production contract")
    return total


def run(args):
    n_train = args.n_train
    n_test = args.n_test
    total = _validate_counts(n_train, n_test)

    # A non-production bring-up case must never enter the production pool.
    reserved_hit = [cid for cid in BRINGUP_RESERVED_CASE_IDS
                    if 1 <= int(cid[1:]) <= total]
    if reserved_hit:
        raise CliError(
            "requested range would collide with reserved non-production "
            "case id(s): " + ", ".join(reserved_hit)
            + " (the NUMECA bring-up case must not enter the production "
              "master pool)")

    ranges_path = Path(args.ranges)
    ranges, range_id, sampling_id, ranges_sha256 = _load_ranges(ranges_path)
    if args.range_id:
        range_id = args.range_id
    if args.sampling_id:
        sampling_id = args.sampling_id

    points, m = _sobol_points(total)

    design_target = Path(args.output)
    split_target = Path(args.split_output)
    if design_target == split_target:
        raise CliError("--output and --split-output must be different paths")

    design_candidate, cleanup_design = _new_candidate(design_target, args.dry_run)
    split_candidate, cleanup_split = _new_candidate(split_target, args.dry_run)

    files = (
        ("design", design_target, design_candidate, DESIGN_COLUMNS,
         _iter_design_rows(points, ranges, range_id, sampling_id, n_train)),
        ("split", split_target, split_candidate, SPLIT_COLUMNS,
         _iter_split_rows(points, n_train)),
    )

    actions = {}
    try:
        for name, target, candidate, columns, rows in files:
            try:
                _write_csv(candidate, columns, rows)
                candidate_sha = _sha256_file(candidate)
            except OSError as exc:
                actions[name] = ERROR
                _emit({"type": "file", "name": name, "action": ERROR,
                       "path": str(target), "reason":
                       f"candidate write failed: {exc.__class__.__name__}: {exc}"})
                continue

            base_action, base_reason = _plan_target(target, candidate)
            action = _decide(base_action, args.dry_run, args.overwrite)
            reason = _reason_for(action, args.dry_run) or base_reason

            if action in (CREATE, OVERWRITE) and not args.dry_run:
                try:
                    os.replace(candidate, target)
                except OSError as exc:
                    action = ERROR
                    reason = ("atomic replace failed: "
                              f"{exc.__class__.__name__}: {exc}")

            actions[name] = action
            _emit({"type": "file", "name": name, "action": action,
                   "path": str(target), "candidate_sha256": candidate_sha,
                   "reason": reason})
    finally:
        cleanup_design()
        cleanup_split()

    if any(a == ERROR for a in actions.values()):
        exit_code = EXIT_ERROR
    elif any(a == CONFLICT_CONTENT for a in actions.values()):
        exit_code = EXIT_CONFLICT
    else:
        exit_code = EXIT_OK

    _emit({
        "type": "summary",
        "status": "OK" if exit_code == EXIT_OK else (
            "CONFLICT" if exit_code == EXIT_CONFLICT else "ERROR"),
        "n_train": n_train,
        "n_test": n_test,
        "requested_total": total,
        "sobol_m": m,
        "sobol_dim": SOBOL_DIM,
        "sobol_seed": SOBOL_SEED,
        "sobol_scramble": SOBOL_SCRAMBLE,
        "sobol_ordering": SOBOL_ORDERING,
        "sobol_nesting": SOBOL_NESTING,
        "range_id": range_id,
        "sampling_id": sampling_id,
        "ranges_path": str(ranges_path),
        "ranges_sha256": ranges_sha256,
        "design_path": str(design_target),
        "split_path": str(split_target),
        "design_action": actions.get("design", ERROR),
        "split_action": actions.get("split", ERROR),
        "dry_run": bool(args.dry_run),
        "overwrite": bool(args.overwrite),
    })
    return exit_code


DEFAULT_N_TRAIN = 100000
DEFAULT_N_TEST = 20000
DEFAULT_DESIGN_OUTPUT = "design/master_design.csv"
DEFAULT_SPLIT_OUTPUT = "design/splits/fixed_train_test.csv"


def build_parser():
    parser = argparse.ArgumentParser(
        prog="01_generate_design.py",
        description="Generate the frozen production Sobol design "
                    "(master_design.csv + fixed train/test split).")
    parser.add_argument("--ranges", required=True, metavar="PATH",
                        help="ranges YAML (the only switch point for production ranges)")
    parser.add_argument("--n-train", dest="n_train", type=int,
                        default=DEFAULT_N_TRAIN, metavar="INT",
                        help=f"usable training cases (default {DEFAULT_N_TRAIN})")
    parser.add_argument("--n-test", dest="n_test", type=int,
                        default=DEFAULT_N_TEST, metavar="INT",
                        help=f"fixed test cases (default {DEFAULT_N_TEST})")
    parser.add_argument("--output", default=DEFAULT_DESIGN_OUTPUT, metavar="PATH",
                        help=f"master design CSV (default {DEFAULT_DESIGN_OUTPUT})")
    parser.add_argument("--split-output", dest="split_output",
                        default=DEFAULT_SPLIT_OUTPUT, metavar="PATH",
                        help=f"fixed train/test split CSV (default {DEFAULT_SPLIT_OUTPUT})")
    parser.add_argument("--range-id", dest="range_id", default=None, metavar="TEXT",
                        help="override the range_id column value")
    parser.add_argument("--sampling-id", dest="sampling_id", default=None,
                        metavar="TEXT",
                        help="override the sampling_id column value")
    parser.add_argument("--dry-run", action="store_true",
                        help="compute and report without writing anything")
    parser.add_argument("--overwrite", action="store_true",
                        help="replace an existing differing output")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_CLI
    except Exception as exc:  # noqa: BLE001 - operational failure -> exit 4
        print(f"error: design generation operational failure: "
              f"{exc.__class__.__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
