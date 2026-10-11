#!/usr/bin/env python
"""Capture the `legacy_geometry_v1` regression fixture baseline.

This harness does NOT reimplement the legacy blade algorithm. It runs the
ORIGINAL, unmodified ``legacy/blade_batch_generation.py`` and captures its real
output for 13 fixed inputs.

Mechanism
---------
* ``scipy.stats.qmc.LatinHypercube`` is monkeypatched so that the legacy call
  ``sampler_6d.random(n=n_samples)`` returns exactly the 13 normalized rows
  derived from ``cases.csv`` + ``config/ranges_legacy.yaml`` (whatever the legacy
  file's ``n_samples`` is).  The fake sampler fails hard if the legacy
  initialization parameters stop being ``d=6 / optimization="random-cd" / seed=1``.
* ``scipy.stats.qmc.scale`` is left untouched, so the legacy script itself still
  maps unit-hypercube inputs to its own hard-coded ranges.
* The legacy script is executed through ``runpy.run_path`` (no modified copy).
* matplotlib uses a non-interactive backend and ``plt.show`` is a no-op; this only
  suppresses the legacy interactive display and changes no numeric computation.

Run with::

    conda activate ai4s
    python tools/capture_legacy_geometry_fixtures.py
"""

import argparse
import csv
import hashlib
import io
import os
import runpy
import shutil
import sys
import tempfile
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import yaml
import numpy as np

import matplotlib
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO / "tests" / "fixtures" / "legacy_geometry_v1"
CASES_CSV = FIXTURE_DIR / "cases.csv"
RANGES_YAML = REPO / "config" / "ranges_legacy.yaml"
LEGACY_SCRIPT = REPO / "legacy" / "blade_batch_generation.py"
LEGACY_TEMPLATE = REPO / "legacy" / "blade_batch_generation_template.geomTurbo"

# Order MUST match the legacy script's sampler column order.
PARAM_ORDER = ["Xthick", "Tmax", "Metal2", "Solidity", "Incidence", "Mach"]

EXPECTED_LEGACY_SHA = {
    "legacy/blade_batch_generation.py":
        "48ed9ead4b1260790dcc2d3ad9fe05c79e745a82ad19fe2ce918268adfc36e03",
    "legacy/blade_batch_generation_template.geomTurbo":
        "92c4296f2de27440aebaad9b03b9af4f9e09756fabff2298f4607a87f2c55119",
    "config/ranges_legacy.yaml":
        "237ce3f4c1da022a57c7a82e8057248871ce673c96dcba6d0add5763dcc558ef",
}

EXPECTED_ENV = {"python": "3.10.20", "numpy": "2.2.6", "scipy": "1.15.3"}

EXPECTED_GIT_COMMIT = "ebbf7bd9a74ef2db1edd84f5c83ddec4e752c07f"

OPERATING_INDEPENDENT_IDS = ["LG001", "LG012", "LG013"]

FIXTURE_IDS = [f"LG{i:03d}" for i in range(1, 14)]
PROFILES_DIR = FIXTURE_DIR / "expected" / "profiles"
GEOMTURBO_DIR = FIXTURE_DIR / "expected" / "geomturbo"


def die(msg):
    print("\nSTOP: " + msg)
    sys.exit(1)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def read_cases():
    rows = []
    with open(CASES_CSV, newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    if len(rows) != 13:
        die(f"cases.csv must have 13 rows, found {len(rows)}")
    ids = [r["fixture_id"] for r in rows]
    if ids != [f"LG{i:03d}" for i in range(1, 14)]:
        die(f"cases.csv fixture_id sequence unexpected: {ids}")
    return rows


def load_ranges():
    with open(RANGES_YAML) as f:
        doc = yaml.safe_load(f)
    r = doc["ranges"]
    for name in PARAM_ORDER:
        if name not in r:
            die(f"ranges_legacy.yaml missing parameter {name}")
    return {n: (float(r[n][0]), float(r[n][1])) for n in PARAM_ORDER}


def normalized_rows(cases, ranges):
    """Reverse-map physical params to the unit hypercube, in PARAM_ORDER."""
    out = np.zeros((len(cases), 6), dtype=float)
    for i, c in enumerate(cases):
        for j, name in enumerate(PARAM_ORDER):
            lo, hi = ranges[name]
            v = float(c[name])
            if not (lo <= v <= hi):
                die(f"{c['fixture_id']} {name}={v} outside range [{lo},{hi}]")
            out[i, j] = (v - lo) / (hi - lo)
    return out


def make_fake_sampler(rows):
    """Build a LatinHypercube stand-in that ignores n and returns `rows`."""
    frozen = np.array(rows, dtype=float)

    class FakeLatinHypercube:
        def __init__(self, d=None, optimization=None, seed=None, **kwargs):
            if d != 6:
                die(f"legacy LatinHypercube d changed: {d!r} (expected 6)")
            if optimization != "random-cd":
                die(f"legacy LatinHypercube optimization changed: {optimization!r} "
                    f"(expected 'random-cd')")
            if seed != 1:
                die(f"legacy LatinHypercube seed changed: {seed!r} (expected 1)")
            self._n_calls = 0

        def random(self, n=None):
            # Legacy may call with n=n_samples (currently 500); we always return
            # the 13 fixed rows so exactly 13 fixtures are produced.
            return frozen.copy()

    return FakeLatinHypercube


def run_legacy_in_tempdir(rows, tag):
    """Run the original legacy script in an isolated workdir. Return captured paths."""
    workdir = Path(tempfile.mkdtemp(prefix=f"legacy_geom_{tag}_"))
    coord_dir = workdir / "blade_sample" / "blade_sample_coordinates"
    geom_dir = workdir / "blade_sample" / "blade_sample_geomturbo"
    coord_dir.mkdir(parents=True, exist_ok=True)
    geom_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LEGACY_TEMPLATE, workdir / "blade_sample" / LEGACY_TEMPLATE.name)

    import scipy.stats.qmc as qmc_mod
    orig_lhs = qmc_mod.LatinHypercube
    orig_show = plt.show
    qmc_mod.LatinHypercube = make_fake_sampler(rows)
    plt.show = lambda *a, **k: None

    log = io.StringIO()
    cwd = os.getcwd()
    os.chdir(workdir)
    try:
        with redirect_stdout(log), redirect_stderr(log):
            runpy.run_path(str(LEGACY_SCRIPT), run_name="__main__")
    finally:
        os.chdir(cwd)
        qmc_mod.LatinHypercube = orig_lhs
        plt.show = orig_show

    profiles = sorted(coord_dir.glob("profile_*.dat"),
                      key=lambda p: int(p.stem.split("_")[1]))
    geoms = sorted(geom_dir.glob("blade_sample_*.geomTurbo"),
                   key=lambda p: int(p.stem.split("_")[2]))
    if len(profiles) != 13 or len(geoms) != 13:
        die(f"[{tag}] expected 13 profiles + 13 geomTurbo, got "
            f"{len(profiles)} profiles / {len(geoms)} geomTurbo")
    return workdir, profiles, geoms


def capture_once(rows, tag):
    """Return {fixture_id: (profile_bytes, geomturbo_bytes)}."""
    _, profiles, geoms = run_legacy_in_tempdir(rows, tag)
    result = {}
    for i in range(13):
        fid = f"LG{i + 1:03d}"
        result[fid] = (profiles[i].read_bytes(), geoms[i].read_bytes())
    return result


def check_environment():
    import scipy
    actual = {
        "python": ".".join(str(x) for x in sys.version_info[:3]),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }
    for k, want in EXPECTED_ENV.items():
        if actual[k] != want:
            die(f"environment mismatch: {k}={actual[k]!r} expected {want!r}")
    return actual


def check_legacy_hashes(stage):
    result = {}
    for rel, want in EXPECTED_LEGACY_SHA.items():
        got = sha256_file(REPO / rel)
        result[rel] = got
        if got != want:
            die(f"[{stage}] legacy hash changed for {rel}\n  got  {got}\n  want {want}")
    return result


def check_finite_profiles(capture):
    bad = []
    for fid, (profile_bytes, _) in capture.items():
        for lineno, line in enumerate(profile_bytes.decode().splitlines(), 1):
            if not line.strip():
                continue
            for tok in line.split():
                v = float(tok)
                if not np.isfinite(v):
                    bad.append(f"{fid}:{lineno}:{tok}")
    if bad:
        die("non-finite numeric content in profiles: " + ", ".join(bad[:10]))


def check_operating_independence(capture):
    ref_p = sha256_bytes(capture["LG001"][0])
    ref_g = sha256_bytes(capture["LG001"][1])
    rows = []
    ok = True
    for fid in OPERATING_INDEPENDENT_IDS:
        p = sha256_bytes(capture[fid][0])
        g = sha256_bytes(capture[fid][1])
        rows.append((fid, p, g, p == ref_p, g == ref_g))
        ok = ok and p == ref_p and g == ref_g
    return ok, rows, ref_p, ref_g


def write_fixture(capture, env, git_commit):
    prof_dir = FIXTURE_DIR / "expected" / "profiles"
    geom_dir = FIXTURE_DIR / "expected" / "geomturbo"
    for fid, (pbytes, gbytes) in capture.items():
        (prof_dir / f"{fid}.dat").write_bytes(pbytes)
        (geom_dir / f"{fid}.geomTurbo").write_bytes(gbytes)

    metadata = {
        "fixture_version": "legacy_geometry_v1",
        "purpose": "legacy_geometry_regression_baseline",
        "source": {
            "git_commit": git_commit,
            "legacy_script": {
                "path": "legacy/blade_batch_generation.py",
                "sha256": EXPECTED_LEGACY_SHA["legacy/blade_batch_generation.py"],
            },
            "geomturbo_template": {
                "path": "legacy/blade_batch_generation_template.geomTurbo",
                "sha256": EXPECTED_LEGACY_SHA[
                    "legacy/blade_batch_generation_template.geomTurbo"],
            },
            "ranges": {
                "path": "config/ranges_legacy.yaml",
                "sha256": EXPECTED_LEGACY_SHA["config/ranges_legacy.yaml"],
            },
        },
        "environment": {
            "conda_env": "ai4s",
            "python": env["python"],
            "numpy": env["numpy"],
            "scipy": env["scipy"],
        },
        "fixture_count": 13,
    }
    with open(FIXTURE_DIR / "metadata.yaml", "w") as f:
        yaml.safe_dump(metadata, f, sort_keys=False, default_flow_style=False)

    entries = [("cases.csv", sha256_file(FIXTURE_DIR / "cases.csv"))]
    for fid in sorted(capture):
        entries.append((f"expected/profiles/{fid}.dat",
                        sha256_file(prof_dir / f"{fid}.dat")))
    for fid in sorted(capture):
        entries.append((f"expected/geomturbo/{fid}.geomTurbo",
                        sha256_file(geom_dir / f"{fid}.geomTurbo")))
    entries.append(("metadata.yaml", sha256_file(FIXTURE_DIR / "metadata.yaml")))

    with open(FIXTURE_DIR / "SHA256SUMS.txt", "w") as f:
        for rel, h in entries:
            f.write(f"{h}  {rel}\n")
    return entries


def _frozen_artifact(fid, kind):
    sub = "profiles" if kind == "profile" else "geomturbo"
    ext = ".dat" if kind == "profile" else ".geomTurbo"
    return FIXTURE_DIR / "expected" / sub / f"{fid}{ext}"


def verify_frozen(capture):
    """Return a list of mismatches between a fresh capture and the frozen baseline."""
    mismatches = []
    for fid in FIXTURE_IDS:
        for kind, idx in (("profile", 0), ("geomTurbo", 1)):
            frozen = _frozen_artifact(fid, kind)
            if not frozen.exists():
                mismatches.append(f"{fid} {kind}: frozen artifact missing ({frozen})")
                continue
            if sha256_bytes(capture[fid][idx]) != sha256_file(frozen):
                mismatches.append(f"{fid} {kind}: byte/SHA256 mismatch vs frozen")
    return mismatches


def cmd_verify():
    print("=" * 72)
    print("VERIFY MODE - the frozen baseline will NOT be modified")
    print("=" * 72)
    check_legacy_hashes("verify")
    env = check_environment()
    print(f"environment: python={env['python']} numpy={env['numpy']} scipy={env['scipy']}")

    cases = read_cases()
    ranges = load_ranges()
    rows = normalized_rows(cases, ranges)
    capture = capture_once(rows, "verify")
    check_finite_profiles(capture)
    print("captured 13 profiles + 13 geomTurbo in a temp dir")

    mismatches = verify_frozen(capture)
    if mismatches:
        print("\nMISMATCHES vs frozen expected/:")
        for m in mismatches:
            print("  " + m)
        check_legacy_hashes("after")
        print("\nRESULT: VERIFY_FAILED")
        sys.exit(1)

    print("all 26 artifacts match the frozen baseline byte-for-byte")
    check_legacy_hashes("after")
    print("\nRESULT: VERIFY_OK")
    sys.exit(0)


def cmd_update_baseline():
    print("=" * 72)
    print("UPDATE-BASELINE MODE - the frozen baseline WILL be rewritten")
    print("=" * 72)
    check_legacy_hashes("before")
    env = check_environment()
    cases = read_cases()
    ranges = load_ranges()
    rows = normalized_rows(cases, ranges)

    capture_a = capture_once(rows, "runA")
    check_finite_profiles(capture_a)
    capture_b = capture_once(rows, "runB")

    mism = []
    for fid in FIXTURE_IDS:
        for kind, idx in (("profile", 0), ("geomTurbo", 1)):
            if sha256_bytes(capture_a[fid][idx]) != sha256_bytes(capture_b[fid][idx]):
                mism.append(f"{fid} {kind}")
    if mism:
        die("double-run reproducibility FAILED: " + ", ".join(mism))

    op_ok, *_ = check_operating_independence(capture_a)
    if not op_ok:
        die("operating-condition independence FAILED")

    git_commit = os.popen("git -C %s rev-parse HEAD" % REPO).read().strip()
    if git_commit != EXPECTED_GIT_COMMIT:
        die(f"unexpected git HEAD {git_commit} (expected {EXPECTED_GIT_COMMIT})")

    entries = write_fixture(capture_a, env, git_commit)
    check_legacy_hashes("after")
    print(f"baseline rewritten ({len(entries)} manifest entries)")
    print("\nRESULT: BASELINE_UPDATED")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="legacy_geometry_v1 fixture capture / verification tool")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--verify", action="store_true",
                       help="run legacy in a temp dir and compare to frozen baseline")
    group.add_argument("--update-baseline", action="store_true",
                       help="EXPLICITLY regenerate the frozen baseline (destructive)")
    args = parser.parse_args()

    if args.update_baseline:
        cmd_update_baseline()
    elif args.verify:
        cmd_verify()
    else:
        print("REFUSING to run without an explicit mode.")
        print("The frozen baseline tests/fixtures/legacy_geometry_v1/expected/")
        print("must never be overwritten implicitly.")
        print("")
        print("  --verify           capture to temp dir + compare to frozen baseline")
        print("  --update-baseline  explicitly regenerate the frozen baseline")
        sys.exit(2)


if __name__ == "__main__":
    main()
