#!/usr/bin/env python
"""generate_geomturbo_production.py — frozen 11-D Sobol GeomTurbo production entry.

SAFETY CONTRACT
---------------
Nothing is written without an explicit ``--execute``.  ``--plan`` is read-only.
Importing this module, running ``--help`` and running the unit tests never
generate a real .geomTurbo file.

What it does (with ``--execute``)::

    config/geometry_ranges_frozen_a.yaml  (scheme A, FROZEN 2026-10-21)
      -> 11-D scrambled Sobol (seed 1, native order, prefix nesting)
      -> u in [0,1)^11 scaled into the frozen physical ranges
      -> SS1 = 3.2 / SS2 = 0.8 injected as fixed parameters
      -> code/geometry_parametric_exploratory_v1.py (frozen legacy mathematics)
      -> <output>/batch_XXXXXX/<case_id>.geomTurbo  (atomic write)

Reuse policy
------------
The blade mathematics, the 4-decimal profile serializer and the .geomTurbo
serializer are NOT reimplemented here.  They are imported from
``code/geometry_parametric_exploratory_v1.py``, which delegates the final
.geomTurbo rendering to the frozen ``code/geometry_legacy_v1.py`` serializer.

Frozen sampling policy
----------------------
    method   = scipy.stats.qmc.Sobol
    d        = 11   (order from the config: Xthick, Tmax, Metal2, Solidity,
                     Metal1, T1, T2, Xmean, K_m, Ks1, Ks2)
    scramble = True
    seed     = 1    (config default, overridable with --seed)
    ordering = native Sobol order
    nesting  = prefix (D_N = first N points of the same master block)

    m = smallest integer with 2^m >= count
    master = Sobol(d=11, scramble=True, seed=seed).random_base2(m)
    used   = master[:count]          # count is NOT rounded to 2^m

Case IDs
--------
    G + 7 digits (G0000001 .. G0200000 for the default 200000)
    Deliberately disjoint from C8xxxxx (review) and C9xxxxx (NUMECA bring-up).

Exit codes
----------
    0   OK (all cases written / verified; no failures)
    2   CLI / config / resume-consistency failure (nothing generated)
    4   one or more per-case failures, or an unexpected operational failure
    130 interrupted by the user (progress on disk is resumable)

Explicit non-goals
------------------
    no automatic shape screening (no curvature/thickness filters)
    no multi-parameter joint constraint (JC_XMEAN_KS1_KM stays inactive)
    no NUMECA / CFX / CFD invocation
    no modification of the 2026-10-13 design freeze
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Tuple

import yaml
from scipy.stats import qmc

REPO_ROOT = Path(__file__).resolve().parent.parent
CODE_DIR = Path(__file__).resolve().parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

import geometry_parametric_exploratory_v1 as geo  # noqa: E402

DEFAULT_CONFIG = "config/geometry_ranges_frozen_a.yaml"

EXPECTED_PARAMS: Tuple[str, ...] = (
    "Xthick", "Tmax", "Metal2", "Solidity", "Metal1",
    "T1", "T2", "Xmean", "K_m", "Ks1", "Ks2",
)
EXPECTED_FIXED: Dict[str, float] = {"SS1": 3.2, "SS2": 0.8}

EXTENSION = ".geomTurbo"
CASE_PREFIX = "G"
CASE_WIDTH = 7
BATCH_PREFIX = "batch_"
BATCH_WIDTH = 6

SNAPSHOT_NAME = "config_snapshot.yaml"
MANIFEST_NAME = "manifest.csv"
SUMMARY_NAME = "generation_summary.json"

MANIFEST_COLUMNS: Tuple[str, ...] = (
    "case_id", "sobol_index", "batch", "path", "status", "error",
    "sha256", "size_bytes",
) + EXPECTED_PARAMS + ("SS1", "SS2")

DEFAULT_ASSUMED_CASE_BYTES = 15000  # observed V2 .geomTurbo files are ~14.2 kB

EXIT_OK = 0
EXIT_CLI = 2
EXIT_ERROR = 4
EXIT_INTERRUPTED = 130


class CliError(Exception):
    """CLI / config / resume-consistency failure -> exit code 2."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Atomic single-file write: temp file in the same dir + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=".tmp-" + path.name + "-", suffix=".part")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _atomic_write_text(path: Path, text: str) -> None:
    _atomic_write_bytes(path, text.encode("utf-8"))


def _fmt(value: float) -> str:
    """Round-trip stable text for a float (used in manifests)."""
    return repr(float(value))


def _clean_error(exc: BaseException, limit: int = 300) -> str:
    text = f"{exc.__class__.__name__}: {exc}"
    text = " ".join(text.split())
    return text[:limit]


def case_id(index: int) -> str:
    """1-based Sobol index -> stable case ID (G0000001 ...)."""
    if index < 1:
        raise ValueError(f"index must be >= 1, got {index!r}")
    return f"{CASE_PREFIX}{index:0{CASE_WIDTH}d}"


def batch_number(index: int, batch_size: int) -> int:
    """1-based Sobol index -> 1-based batch number."""
    if index < 1 or batch_size < 1:
        raise ValueError("index and batch_size must be >= 1")
    return (index - 1) // batch_size + 1


def batch_dir_name(number: int) -> str:
    return f"{BATCH_PREFIX}{number:0{BATCH_WIDTH}d}"


def sobol_m(total: int) -> int:
    """Smallest m with 2^m >= total (exact integer arithmetic)."""
    if total < 1:
        raise ValueError("total must be >= 1")
    m = 0
    while (1 << m) < total:
        m += 1
    return m


def sobol_points(total: int, seed: int):
    """Return (points[:total], m) of the frozen scrambled-Sobol master block.

    A fresh engine with the same seed always yields the same first 2^m points,
    therefore smaller counts are exact prefixes of larger counts.
    """
    m = sobol_m(total)
    engine = qmc.Sobol(d=len(EXPECTED_PARAMS), scramble=True, seed=seed)
    master = engine.random_base2(m)
    return master[:total], m


def map_point(point: Sequence[float],
              ranges: Mapping[str, Tuple[float, float]]) -> Dict[str, float]:
    """Map one unit-cube point to the 11 physical geometry parameters."""
    if len(point) != len(EXPECTED_PARAMS):
        raise ValueError(
            f"expected {len(EXPECTED_PARAMS)} dims, got {len(point)}")
    params: Dict[str, float] = {}
    for dim, name in enumerate(EXPECTED_PARAMS):
        lo, hi = ranges[name]
        u = float(point[dim])
        if not (0.0 <= u <= 1.0):
            raise ValueError(f"Sobol coordinate {u!r} outside [0, 1]")
        params[name] = lo + u * (hi - lo)
    params.update(EXPECTED_FIXED)
    return params




# ---------------------------------------------------------------------------
# Config / plan
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Plan:
    config_path: Path
    config_id: str
    freeze_status: str
    order: Tuple[str, ...]
    ranges: Dict[str, Tuple[float, float]]
    fixed: Dict[str, float]
    count: int
    seed: int
    batch_size: int
    output_dir: Path
    template_path: Path
    template_text: str
    template_sha: str
    generator_sha: str
    serializer_sha: str
    m: int
    fingerprint: str
    verify_hash: bool

    @property
    def n_batches(self) -> int:
        return (self.count + self.batch_size - 1) // self.batch_size

    @property
    def first_case_id(self) -> str:
        return case_id(1)

    @property
    def last_case_id(self) -> str:
        return case_id(self.count)


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise CliError(message)


def load_config(path: Path) -> dict:
    """Read and validate the frozen geometry-generation config."""
    if not path.is_file():
        raise CliError(f"config file not found: {path}")
    try:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CliError(f"config YAML parse error: {exc}") from exc
    _require(isinstance(cfg, dict), "config must be a YAML mapping")

    config_id = cfg.get("config_id")
    _require(isinstance(config_id, str) and bool(config_id.strip()),
             "config_id must be a non-empty string")
    status = cfg.get("status")
    _require(isinstance(status, str) and bool(status.strip()),
             "status must be a non-empty string")
    _require(status == "FROZEN",
             f"config status must be FROZEN, got {status!r}")

    order = cfg.get("geometry_parameters")
    _require(isinstance(order, list) and len(order) == len(EXPECTED_PARAMS),
             f"geometry_parameters must be a list of {len(EXPECTED_PARAMS)} names")
    _require(tuple(order) == EXPECTED_PARAMS,
             "geometry_parameters order does not match the frozen order "
             f"{list(EXPECTED_PARAMS)}")

    raw_ranges = cfg.get("ranges")
    _require(isinstance(raw_ranges, dict), "ranges must be a mapping")
    _require(set(raw_ranges) == set(EXPECTED_PARAMS),
             "ranges keys must match geometry_parameters exactly")
    ranges: Dict[str, Tuple[float, float]] = {}
    for name in EXPECTED_PARAMS:
        pair = raw_ranges[name]
        _require(isinstance(pair, (list, tuple)) and len(pair) == 2,
                 f"ranges[{name}] must be [lo, hi]")
        try:
            lo, hi = float(pair[0]), float(pair[1])
        except (TypeError, ValueError) as exc:
            raise CliError(f"ranges[{name}] must be numeric") from exc
        _require(lo < hi, f"ranges[{name}] requires lo < hi, got {lo} >= {hi}")
        _require(abs(lo) != float("inf") and abs(hi) != float("inf"),
                 f"ranges[{name}] must be finite")
        ranges[name] = (lo, hi)

    fixed_raw = cfg.get("fixed_parameters")
    _require(isinstance(fixed_raw, dict), "fixed_parameters must be a mapping")
    _require(set(fixed_raw) == set(EXPECTED_FIXED),
             f"fixed_parameters must be exactly {sorted(EXPECTED_FIXED)}")
    fixed = {k: float(v) for k, v in fixed_raw.items()}
    for name, value in EXPECTED_FIXED.items():
        _require(abs(fixed[name] - value) < 1e-12,
                 f"fixed parameter {name} must stay {value}, got {fixed[name]}")

    sampling = cfg.get("sampling")
    _require(isinstance(sampling, dict), "sampling must be a mapping")
    _require(int(sampling.get("dimensions", -1)) == len(EXPECTED_PARAMS),
             f"sampling.dimensions must be {len(EXPECTED_PARAMS)}")
    _require(sampling.get("scramble") is True, "sampling.scramble must be true")
    _require(sampling.get("ordering") == "native",
             "sampling.ordering must be 'native'")
    _require(sampling.get("nesting") == "prefix",
             "sampling.nesting must be 'prefix'")
    default_count = sampling.get("default_count")
    _require(isinstance(default_count, int) and default_count > 0,
             "sampling.default_count must be a positive integer")
    default_seed = sampling.get("seed")
    _require(isinstance(default_seed, int) and default_seed >= 0,
             "sampling.seed must be a non-negative integer")

    case_cfg = cfg.get("case_id") or {}
    _require(int(case_cfg.get("width", CASE_WIDTH)) == CASE_WIDTH,
             f"case_id.width must stay {CASE_WIDTH}")
    _require(str(case_cfg.get("prefix", CASE_PREFIX)) == CASE_PREFIX,
             f"case_id.prefix must stay {CASE_PREFIX!r}")

    out_cfg = cfg.get("output") or {}
    _require(str(out_cfg.get("extension", EXTENSION)) == EXTENSION,
             f"output.extension must stay {EXTENSION!r}")
    batch_default = out_cfg.get("batch_size")
    _require(isinstance(batch_default, int) and batch_default > 0,
             "output.batch_size must be a positive integer")
    default_dir = out_cfg.get("default_dir")
    _require(isinstance(default_dir, str) and bool(default_dir.strip()),
             "output.default_dir must be a non-empty string")

    tpl = cfg.get("template") or {}
    tpl_rel = tpl.get("path")
    tpl_sha = tpl.get("sha256")
    _require(isinstance(tpl_rel, str) and bool(tpl_rel.strip()),
             "template.path must be a non-empty string")
    _require(isinstance(tpl_sha, str) and len(tpl_sha) == 64,
             "template.sha256 must be a 64-character hex digest")
    tpl_path = (REPO_ROOT / tpl_rel).resolve()
    _require(tpl_path.is_file(), f"template file not found: {tpl_path}")
    actual_sha = _sha256_file(tpl_path)
    _require(actual_sha == tpl_sha.lower(),
             f"template sha256 mismatch: config={tpl_sha} file={actual_sha}")

    return {
        "config_id": config_id,
        "status": status,
        "order": tuple(order),
        "ranges": ranges,
        "fixed": fixed,
        "default_count": default_count,
        "default_seed": default_seed,
        "batch_size": batch_default,
        "default_dir": default_dir,
        "template_path": tpl_path,
        "template_sha": tpl_sha.lower(),
    }


def _plan_fingerprint(cfg: dict, config_sha: str, seed: int, batch_size: int,
                      generator_sha: str, serializer_sha: str) -> str:
    payload = {
        "schema": 1,
        "config_id": cfg["config_id"],
        "config_sha256": config_sha,
        "geometry_parameters": list(cfg["order"]),
        "ranges": {k: [float(v[0]), float(v[1])]
                   for k, v in cfg["ranges"].items()},
        "fixed_parameters": {k: float(v) for k, v in cfg["fixed"].items()},
        "seed": int(seed),
        "batch_size": int(batch_size),
        "extension": EXTENSION,
        "template_sha256": cfg["template_sha"],
        "generator_sha256": generator_sha,
        "serializer_sha256": serializer_sha,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return _sha256_bytes(blob.encode("utf-8"))


def build_plan(args) -> Plan:
    """Resolve CLI overrides into an immutable Plan (no Sobol points yet)."""
    config_path = Path(args.config).expanduser().resolve()
    cfg = load_config(config_path)

    count = args.count if args.count is not None else cfg["default_count"]
    if count < 1:
        raise CliError(f"--count must be >= 1, got {count}")
    max_count = 10 ** CASE_WIDTH - 1
    if count > max_count:
        raise CliError(f"--count must be <= {max_count} (case_id width "
                       f"{CASE_WIDTH}), got {count}")
    seed = args.seed if args.seed is not None else cfg["default_seed"]
    if seed < 0:
        raise CliError(f"--seed must be >= 0, got {seed}")
    batch_size = (args.batch_size if args.batch_size is not None
                  else cfg["batch_size"])
    if batch_size < 1:
        raise CliError(f"--batch-size must be >= 1, got {batch_size}")

    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser().resolve()
    else:
        output_dir = (REPO_ROOT / cfg["default_dir"]).resolve()

    template_path = cfg["template_path"]
    template_bytes = template_path.read_bytes()
    template_text = template_bytes.decode("utf-8")
    template_sha = _sha256_bytes(template_bytes)

    generator_sha = _sha256_file(CODE_DIR / "geometry_parametric_exploratory_v1.py")
    serializer_sha = _sha256_file(CODE_DIR / "geometry_legacy_v1.py")
    config_sha = _sha256_file(config_path)

    fingerprint = _plan_fingerprint(
        cfg, config_sha, seed, batch_size, generator_sha, serializer_sha)

    return Plan(
        config_path=config_path,
        config_id=cfg["config_id"],
        freeze_status=cfg["status"],
        order=cfg["order"],
        ranges=cfg["ranges"],
        fixed=cfg["fixed"],
        count=count,
        seed=seed,
        batch_size=batch_size,
        output_dir=output_dir,
        template_path=template_path,
        template_text=template_text,
        template_sha=template_sha,
        generator_sha=generator_sha,
        serializer_sha=serializer_sha,
        m=sobol_m(count),
        fingerprint=fingerprint,
        verify_hash=bool(args.verify_hash),
    )




# ---------------------------------------------------------------------------
# Manifest IO
# ---------------------------------------------------------------------------
def _manifest_row(cid: str, index: int, batch: int, rel_path: str,
                  status: str, params: Mapping[str, float],
                  error: str = "", sha: str = "", size: int = 0) -> dict:
    row = {
        "case_id": cid,
        "sobol_index": str(index),
        "batch": str(batch),
        "path": rel_path,
        "status": status,
        "error": error,
        "sha256": sha,
        "size_bytes": str(size),
    }
    for name in EXPECTED_PARAMS:
        row[name] = _fmt(params[name])
    row["SS1"] = _fmt(params["SS1"])
    row["SS2"] = _fmt(params["SS2"])
    return row


def _case_relpath(index: int, batch_size: int) -> Tuple[str, str, int]:
    batch = batch_number(index, batch_size)
    cid = case_id(index)
    rel = f"{batch_dir_name(batch)}/{cid}{EXTENSION}"
    return cid, rel, batch


def _load_batch_rows(batch_dir: Path) -> Dict[str, dict]:
    path = batch_dir / MANIFEST_NAME
    rows: Dict[str, dict] = {}
    if not path.is_file():
        return rows
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row.get("case_id")
            if cid:
                rows[cid] = row
    return rows


def _write_batch_manifest(batch_dir: Path, rows: Dict[str, dict]) -> None:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=MANIFEST_COLUMNS)
    writer.writeheader()
    for cid in sorted(rows, key=lambda c: int(rows[c].get("sobol_index") or 0)):
        writer.writerow({k: rows[cid].get(k, "") for k in MANIFEST_COLUMNS})
    _atomic_write_text(batch_dir / MANIFEST_NAME, buf.getvalue())


def _append_manifest_rows(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        if new_file:
            writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in MANIFEST_COLUMNS})


def _rebuild_root_manifest(plan: Plan) -> dict:
    """Stream every batch manifest into a fresh root manifest (atomic)."""
    out = plan.output_dir
    out.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(out), prefix=".manifest-", suffix=".part")
    stats = {"rows": 0, "ok": 0, "failed": 0, "bytes": 0}
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
            writer.writeheader()
            for batch_dir in sorted(p for p in out.glob(BATCH_PREFIX + "*")
                                    if p.is_dir()):
                manifest = batch_dir / MANIFEST_NAME
                if not manifest.is_file():
                    continue
                with open(manifest, newline="", encoding="utf-8") as mf:
                    for row in csv.DictReader(mf):
                        writer.writerow({k: row.get(k, "")
                                         for k in MANIFEST_COLUMNS})
                        stats["rows"] += 1
                        if row.get("status") == "OK":
                            stats["ok"] += 1
                        elif row.get("status") == "FAILED":
                            stats["failed"] += 1
                        try:
                            stats["bytes"] += int(row.get("size_bytes") or 0)
                        except ValueError:
                            pass
        os.replace(tmp_name, out / MANIFEST_NAME)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return stats


def _verify_output(path: Path, row: Mapping[str, str],
                   verify_hash: bool) -> bool:
    """True only if the existing file is complete and matches the manifest."""
    if not path.is_file():
        return False
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size <= 0:
        return False
    recorded = (row.get("size_bytes") or "").strip()
    if recorded:
        try:
            recorded_size = int(recorded)
        except ValueError:
            return False
        if recorded_size != size:
            return False
    if verify_hash:
        sha = (row.get("sha256") or "").strip()
        if not sha or _sha256_file(path) != sha:
            return False
    return True


# ---------------------------------------------------------------------------
# Snapshot / existing-state scan
# ---------------------------------------------------------------------------
def _snapshot_payload(plan: Plan) -> dict:
    return {
        "config_id": plan.config_id,
        "freeze_status": plan.freeze_status,
        "fingerprint": plan.fingerprint,
        "config_path": str(plan.config_path),
        "config_sha256": _sha256_file(plan.config_path),
        "geometry_parameters": list(plan.order),
        "ranges": {k: [float(v[0]), float(v[1])]
                   for k, v in plan.ranges.items()},
        "fixed_parameters": {k: float(v) for k, v in plan.fixed.items()},
        "count_initial": plan.count,
        "seed": plan.seed,
        "batch_size": plan.batch_size,
        "sobol_m": plan.m,
        "sobol_master_points": 1 << plan.m,
        "sobol_dimensions": len(plan.order),
        "sobol_scramble": True,
        "sobol_ordering": "native",
        "sobol_nesting": "prefix",
        "case_id_prefix": CASE_PREFIX,
        "case_id_width": CASE_WIDTH,
        "extension": EXTENSION,
        "template_path": str(plan.template_path),
        "template_sha256": plan.template_sha,
        "generator_module": "code/geometry_parametric_exploratory_v1.py",
        "generator_sha256": plan.generator_sha,
        "serializer_module": "code/geometry_legacy_v1.py",
        "serializer_sha256": plan.serializer_sha,
        "created_at": _now(),
        "note": ("GeomTurbo geometry generation only. No CFD. "
                 "count may be changed on resume; the Sobol prefix is stable."),
    }


def _write_snapshot(plan: Plan) -> None:
    text = yaml.safe_dump(_snapshot_payload(plan), sort_keys=False,
                          allow_unicode=True)
    _atomic_write_text(plan.output_dir / SNAPSHOT_NAME, text)


def _read_snapshot(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CliError(f"config snapshot is unreadable: {exc}") from exc
    return data if isinstance(data, dict) else {}


def _scan_existing(plan: Plan) -> dict:
    """Read-only summary of an existing output directory (no file hashing)."""
    out = plan.output_dir
    stats = {"exists": out.exists(), "batches": 0, "rows": 0, "ok": 0,
             "failed": 0, "snapshot": False, "fingerprint": "",
             "fingerprint_matches": False}
    if not out.exists():
        return stats
    snap = _read_snapshot(out / SNAPSHOT_NAME)
    if snap:
        stats["snapshot"] = True
        stats["fingerprint"] = str(snap.get("fingerprint", ""))
        stats["fingerprint_matches"] = (
            stats["fingerprint"] == plan.fingerprint)
    for batch_dir in sorted(p for p in out.glob(BATCH_PREFIX + "*")
                            if p.is_dir()):
        stats["batches"] += 1
        manifest = batch_dir / MANIFEST_NAME
        if not manifest.is_file():
            continue
        with open(manifest, newline="", encoding="utf-8") as mf:
            for row in csv.DictReader(mf):
                stats["rows"] += 1
                if row.get("status") == "OK":
                    stats["ok"] += 1
                elif row.get("status") == "FAILED":
                    stats["failed"] += 1
    return stats


# ---------------------------------------------------------------------------
# Case rendering (the ONLY place that touches the frozen generator)
# ---------------------------------------------------------------------------
def render_geomturbo_text(params: Mapping[str, float],
                          template_text: str) -> str:
    """Render one .geomTurbo text using the frozen legacy mathematics.

    Kept in a single function so tests can patch it and prove that no real
    GeomTurbo file is produced by the test suite.
    """
    _profile_text, geomturbo_text = geo.generate_geometry_texts(
        dict(params), template_text=template_text)
    return geomturbo_text


def _process_case(plan: Plan, index: int, point, existing_row: Optional[dict]):
    """Return (row, action, params). action in {skip, write, fail}."""
    cid, rel, batch = _case_relpath(index, plan.batch_size)
    path = plan.output_dir / rel
    params = map_point(point, plan.ranges)

    if existing_row is not None and existing_row.get("status") == "OK":
        same_path = (existing_row.get("path") or "") == rel
        if same_path and _verify_output(path, existing_row, plan.verify_hash):
            return existing_row, "skip", params

    try:
        text = render_geomturbo_text(params, plan.template_text)
        if not text or not text.strip():
            raise ValueError("generator returned an empty geomTurbo text")
        data = text.encode("utf-8")
        _atomic_write_bytes(path, data)
        row = _manifest_row(cid, index, batch, rel, "OK", params,
                            sha=_sha256_bytes(data), size=len(data))
        return row, "write", params
    except Exception as exc:  # noqa: BLE001 - per-case failure is recorded
        row = _manifest_row(cid, index, batch, rel, "FAILED", params,
                            error=_clean_error(exc))
        return row, "fail", params



# ---------------------------------------------------------------------------
# Plan / execute
# ---------------------------------------------------------------------------
def run_plan(plan: Plan,
             assumed_bytes_per_case: int = DEFAULT_ASSUMED_CASE_BYTES) -> int:
    """Read-only plan output. Never writes or generates anything."""
    stats = _scan_existing(plan)
    print("geometry generation plan (read-only)")
    print(f"config            : {plan.config_path}")
    print(f"config_id / status: {plan.config_id} / {plan.freeze_status}")
    print("geometry ranges   :")
    for name in plan.order:
        lo, hi = plan.ranges[name]
        print(f"  {name:<9} {lo:<10.10g} .. {hi:<10.10g}")
    print("fixed parameters  : SS1 = 3.2, SS2 = 0.8")
    print(f"sampling          : Sobol d={len(plan.order)} scramble=True "
          f"seed={plan.seed} native order, prefix nesting")
    print(f"count             : {plan.count}  (m={plan.m}, master points="
          f"{1 << plan.m}, used={plan.count})")
    print(f"batch size        : {plan.batch_size}  -> {plan.n_batches} batches")
    print(f"case ids          : {plan.first_case_id} .. {plan.last_case_id}")
    print(f"output dir        : {plan.output_dir}")
    print(f"template          : {plan.template_path}")
    print(f"template sha256   : {plan.template_sha}")
    print(f"plan fingerprint  : {plan.fingerprint}")
    print(f"existing state    : exists={stats['exists']} "
          f"snapshot={stats['snapshot']} batches={stats['batches']} "
          f"rows={stats['rows']} ok={stats['ok']} failed={stats['failed']}")
    if stats["snapshot"] and not stats["fingerprint_matches"]:
        print("WARNING           : existing snapshot fingerprint DIFFERS; "
              "--resume would be refused")
    est = plan.count * max(1, assumed_bytes_per_case)
    print(f"estimated size    : {est / 1e9:.2f} GB "
          f"({assumed_bytes_per_case} B/case assumed)")
    print("mode              : PLAN ONLY — no files written")
    return EXIT_OK


def _write_summary(plan: Plan, payload: dict) -> None:
    _atomic_write_text(
        plan.output_dir / SUMMARY_NAME,
        json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _init_output(plan: Plan, resume: bool) -> None:
    out = plan.output_dir
    snapshot = out / SNAPSHOT_NAME
    if out.exists() and any(out.iterdir()):
        if not snapshot.is_file():
            raise CliError(
                f"output directory is not empty but has no {SNAPSHOT_NAME}: "
                f"{out} (refusing to mix with unrelated files)")
        if not resume:
            raise CliError(
                f"output directory already initialized: {out} "
                "(use --resume to continue, or choose a new --output-dir)")
        snap = _read_snapshot(snapshot)
        if snap.get("fingerprint") != plan.fingerprint:
            raise CliError(
                "resume refused: config / seed / parameter order / batch size / "
                "template / generator hashes differ from the existing run. "
                "Use the original settings, or start a new --output-dir.")
    else:
        out.mkdir(parents=True, exist_ok=True)
        _write_snapshot(plan)



def run_execute(plan: Plan, resume: bool, progress_every: int) -> int:
    """Generate cases with --execute. Per-case failures never abort the run."""
    out = plan.output_dir
    _init_output(plan, resume)

    points, m = sobol_points(plan.count, plan.seed)
    if m != plan.m:
        raise CliError(f"Sobol m mismatch: plan={plan.m} actual={m}")

    _rebuild_root_manifest(plan)  # start from the canonical batch manifests

    started = time.monotonic()
    written = skipped = failed = 0
    processed = 0
    current_batch_dir: Optional[Path] = None
    current_rows: Dict[str, dict] = {}

    try:
        for batch_no in range(1, plan.n_batches + 1):
            start = (batch_no - 1) * plan.batch_size + 1
            end = min(batch_no * plan.batch_size, plan.count)
            batch_dir = out / batch_dir_name(batch_no)
            batch_dir.mkdir(parents=True, exist_ok=True)
            rows = _load_batch_rows(batch_dir)
            current_batch_dir = batch_dir
            current_rows = rows

            batch_written = batch_skipped = batch_failed = 0
            batch_changed = []
            for index in range(start, end + 1):
                cid = case_id(index)
                row, action, _params = _process_case(
                    plan, index, points[index - 1], rows.get(cid))
                rows[cid] = row
                if action == "write":
                    written += 1
                    batch_written += 1
                    batch_changed.append(row)
                elif action == "skip":
                    skipped += 1
                    batch_skipped += 1
                else:
                    failed += 1
                    batch_failed += 1
                    batch_changed.append(row)
                processed += 1
                if progress_every > 0 and processed % progress_every == 0:
                    print(f"progress: {processed}/{plan.count} "
                          f"(written={written} skipped={skipped} "
                          f"failed={failed})", flush=True)

            _write_batch_manifest(batch_dir, rows)
            if batch_changed:
                _append_manifest_rows(out / MANIFEST_NAME, batch_changed)
            print(f"batch {batch_dir_name(batch_no)}: "
                  f"cases {case_id(start)}..{case_id(end)} "
                  f"written={batch_written} skipped={batch_skipped} "
                  f"failed={batch_failed}", flush=True)
    except KeyboardInterrupt:
        # Ctrl+C can arrive in the middle of a batch.  Case files are written
        # atomically, but the batch manifest is normally flushed only at the
        # end of the batch.  Flush it here so that:
        #   1) the manifest matches the files already on disk, and
        #   2) --resume can skip those cases instead of regenerating them.
        try:
            if current_batch_dir is not None and current_rows:
                _write_batch_manifest(current_batch_dir, current_rows)
                _rebuild_root_manifest(plan)
        except Exception as exc:  # noqa: BLE001 - never mask the interrupt
            print(f"warning: could not flush partial batch manifest: {exc}",
                  file=sys.stderr)
        print(f"\ninterrupted after {processed}/{plan.count} cases "
              f"(written={written} skipped={skipped} failed={failed}); "
              "partial progress was flushed, re-run with --resume to continue.",
              file=sys.stderr)
        return EXIT_INTERRUPTED

    stats = _rebuild_root_manifest(plan)
    elapsed = time.monotonic() - started
    payload = {
        "generated_at": _now(),
        "config_id": plan.config_id,
        "config_path": str(plan.config_path),
        "fingerprint": plan.fingerprint,
        "output_dir": str(out),
        "count_requested": plan.count,
        "seed": plan.seed,
        "batch_size": plan.batch_size,
        "sobol_m": plan.m,
        "sobol_master_points": 1 << plan.m,
        "written_this_run": written,
        "skipped_existing": skipped,
        "failed_this_run": failed,
        "manifest_rows": stats["rows"],
        "manifest_ok": stats["ok"],
        "manifest_failed": stats["failed"],
        "bytes_total": stats["bytes"],
        "elapsed_s": round(elapsed, 3),
        "completed": stats["rows"] >= plan.count and stats["failed"] == 0,
        "note": ("GeomTurbo geometry generation only. No mesh, no NUMECA, "
                 "no CFX, no CFD. Failures are recorded per case and are "
                 "retried on the next --resume."),
    }
    _write_summary(plan, payload)
    print(f"done: rows={stats['rows']} ok={stats['ok']} "
          f"failed={stats['failed']} written_this_run={written} "
          f"skipped={skipped} elapsed={elapsed:.1f}s")
    print(f"summary: {out / SUMMARY_NAME}")
    return EXIT_OK if stats["failed"] == 0 else EXIT_ERROR




# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_geomturbo_production.py",
        description="Frozen 11-D Sobol GeomTurbo generation (scheme A). "
                    "Nothing is generated without --execute.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("examples:\n"
                "  plan   : python code/generate_geomturbo_production.py --plan\n"
                "  run    : python code/generate_geomturbo_production.py "
                "--execute\n"
                "  resume : python code/generate_geomturbo_production.py "
                "--execute --resume\n"
                "  smaller: python code/generate_geomturbo_production.py "
                "--plan --count 50000\n"))
    parser.add_argument("--config", default=DEFAULT_CONFIG, metavar="PATH",
                        help=f"frozen geometry config "
                             f"(default {DEFAULT_CONFIG})")
    parser.add_argument("--count", type=int, default=None, metavar="INT",
                        help="number of cases (default: config value, 200000). "
                             "Smaller values are exact Sobol prefixes.")
    parser.add_argument("--seed", type=int, default=None, metavar="INT",
                        help="Sobol scramble seed (default: config value, 1)")
    parser.add_argument("--output-dir", dest="output_dir", default=None,
                        metavar="PATH",
                        help="output directory (default: production_geomturbo)")
    parser.add_argument("--batch-size", dest="batch_size", type=int,
                        default=None, metavar="INT",
                        help="cases per batch directory "
                             "(default: config value, 5000)")
    parser.add_argument("--resume", action="store_true",
                        help="continue an existing output directory")
    parser.add_argument("--plan", action="store_true",
                        help="show the plan and exit; writes nothing")
    parser.add_argument("--execute", action="store_true",
                        help="explicit authorization to generate files")
    parser.add_argument("--no-verify-hash", dest="verify_hash",
                        action="store_false", default=True,
                        help="on resume, verify size only (skip sha256 checks)")
    parser.add_argument("--progress-every", dest="progress_every", type=int,
                        default=2000, metavar="INT",
                        help="print progress every INT cases (0 disables)")
    parser.add_argument("--assumed-case-bytes", dest="assumed_case_bytes",
                        type=int, default=DEFAULT_ASSUMED_CASE_BYTES,
                        metavar="INT",
                        help="storage estimate only (default 15000 B/case)")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.plan and args.execute:
            raise CliError("--plan and --execute are mutually exclusive")
        if not args.plan and not args.execute:
            print("error: refusing to run without --execute "
                  "(use --plan to preview the generation plan)",
                  file=sys.stderr)
            return EXIT_CLI
        plan = build_plan(args)
        if args.plan:
            return run_plan(plan, args.assumed_case_bytes)
        return run_execute(plan, args.resume, args.progress_every)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_CLI
    except KeyboardInterrupt:
        print("error: interrupted by user", file=sys.stderr)
        return EXIT_INTERRUPTED
    except Exception as exc:  # noqa: BLE001 - operational failure -> exit 4
        print(f"error: operational failure: {exc.__class__.__name__}: {exc}",
              file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
