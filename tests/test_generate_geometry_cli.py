"""Tests for code/02_generate_geometry.py (Phase 2 CLI / filesystem layer).

Standard library only (unittest, tempfile, subprocess, json, csv, pathlib, hashlib).
No pytest, no new dependencies.
"""

import contextlib
import csv
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "code" / "02_generate_geometry.py"
CORE = REPO / "code" / "geometry_legacy_v1.py"
TEMPLATE = REPO / "legacy" / "blade_batch_generation_template.geomTurbo"
FIXTURE = REPO / "tests" / "fixtures" / "legacy_geometry_v1"
LG001_PROFILE = (FIXTURE / "expected" / "profiles" / "LG001.dat").read_bytes()
LG001_GEOMTURBO = (FIXTURE / "expected" / "geomturbo" / "LG001.geomTurbo").read_bytes()

HEADER = ["case_id", "Xthick", "Tmax", "Metal2", "Solidity", "Incidence", "Mach",
          "range_id", "sampling_id"]

BASE = {
    "case_id": "C000001", "Xthick": "0.30", "Tmax": "0.055", "Metal2": "15.0",
    "Solidity": "1.5", "Incidence": "0.0", "Mach": "0.5",
    "range_id": "legacy", "sampling_id": "s1",
}


def row(**over):
    r = dict(BASE)
    r.update(over)
    return r


def write_csv(path, rows, header=HEADER, extra_cols=()):
    header = list(header) + list(extra_cols)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow([r.get(c, "") for c in header])
    return path


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *[str(a) for a in args]],
        capture_output=True, text=True, cwd=str(REPO))


def parse_jsonl(stdout):
    return [json.loads(ln) for ln in stdout.splitlines() if ln.strip()]


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CliTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.out = self.tmp / "geometry"

    def tearDown(self):
        self._tmp.cleanup()

    def csv_path(self, rows, header=HEADER, extra_cols=(), name="design.csv"):
        return write_csv(self.tmp / name, rows, header=header, extra_cols=extra_cols)

    def invoke(self, csv_path, *extra, output=None, template=None):
        out = self.out if output is None else output
        tpl = TEMPLATE if template is None else template
        return run_cli("--input", csv_path, "--template", tpl, "--output", out, *extra)

    def summary_of(self, proc):
        objs = parse_jsonl(proc.stdout)
        self.assertTrue(objs, "no stdout JSONL produced")
        self.assertEqual(objs[-1].get("type"), "summary")
        return objs


class TestValidation(CliTestBase):
    def test_T1_missing_required_args(self):
        proc = subprocess.run([sys.executable, str(SCRIPT)],
                              capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(proc.returncode, 2)

    def test_T2_missing_required_column(self):
        header = [c for c in HEADER if c != "Solidity"]
        p = self.csv_path([row()], header=header)
        proc = self.invoke(p)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(self.out.exists(), "no output dir must be created")

    def test_T3_invalid_case_id(self):
        for bad in ("LG001", "C123", "C1234567", "c000001"):
            with self.subTest(bad=bad):
                p = self.csv_path([row(case_id=bad)], name=f"{bad}.csv")
                proc = self.invoke(p)
                self.assertEqual(proc.returncode, 2)
        self.assertFalse(self.out.exists())

    def test_T4_duplicate_case_id(self):
        p = self.csv_path([row(case_id="C000001"), row(case_id="C000001")])
        proc = self.invoke(p)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(self.out.exists())

    def test_T5_non_finite_numeric(self):
        for col, val in (("Xthick", "nan"), ("Tmax", "inf"), ("Solidity", "-inf"),
                         ("Incidence", "NaN"), ("Mach", "inf")):
            with self.subTest(col=col, val=val):
                p = self.csv_path([row(**{col: val})], name=f"nf_{col}.csv")
                proc = self.invoke(p)
                self.assertEqual(proc.returncode, 2)
        self.assertFalse(self.out.exists())

    def test_T6_xthick_math_invalid(self):
        for val in ("0", "1", "1.5", "-0.1"):
            with self.subTest(val=val):
                p = self.csv_path([row(Xthick=val)], name=f"x{val}.csv")
                proc = self.invoke(p)
                self.assertEqual(proc.returncode, 2)
        self.assertFalse(self.out.exists())

    def test_T7_solidity_non_positive(self):
        for val in ("0", "-1.0"):
            with self.subTest(val=val):
                p = self.csv_path([row(Solidity=val)], name=f"s{val}.csv")
                proc = self.invoke(p)
                self.assertEqual(proc.returncode, 2)
        self.assertFalse(self.out.exists())

    def test_T9_requested_case_missing(self):
        p = self.csv_path([row(case_id="C000001")])
        proc = self.invoke(p, "--case-id", "C999999")
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(self.out.exists())


class TestSelectionAndCreate(CliTestBase):
    def cases_of(self, proc):
        return [o for o in parse_jsonl(proc.stdout) if o.get("type") == "case"]

    def test_T8_extra_columns_accepted(self):
        rows = [row() | {"extra_meta": "hello", "note": "x"}]
        p = self.csv_path(rows, extra_cols=("extra_meta", "note"))
        proc = self.invoke(p)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.cases_of(proc)[0]["action"], "CREATE")

    def test_T10_subset_preserves_csv_order(self):
        rows = [row(case_id="C000001"), row(case_id="C000002"), row(case_id="C000003")]
        p = self.csv_path(rows)
        proc = self.invoke(p, "--case-id", "C000003", "--case-id", "C000001", "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        ids = [c["case_id"] for c in self.cases_of(proc)]
        self.assertEqual(ids, ["C000001", "C000003"])

    def test_T11_normal_create_exact_bytes(self):
        p = self.csv_path([row(case_id="C000001")])
        proc = self.invoke(p)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.cases_of(proc)[0]["action"], "CREATE")
        self.assertEqual((self.out / "profiles" / "C000001.dat").read_bytes(),
                         LG001_PROFILE)
        self.assertEqual((self.out / "geomturbo" / "C000001.geomTurbo").read_bytes(),
                         LG001_GEOMTURBO)

    def test_T12_rerun_skip_match_no_rewrite(self):
        p = self.csv_path([row(case_id="C000001")])
        self.assertEqual(self.invoke(p).returncode, 0)
        prof = self.out / "profiles" / "C000001.dat"
        geom = self.out / "geomturbo" / "C000001.geomTurbo"
        before = (prof.stat().st_mtime_ns, geom.stat().st_mtime_ns)
        proc = self.invoke(p)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.cases_of(proc)[0]["action"], "SKIP_MATCH")
        self.assertEqual((prof.stat().st_mtime_ns, geom.stat().st_mtime_ns), before)

    def test_T13_overwrite_on_matching_is_skip_match(self):
        p = self.csv_path([row(case_id="C000001")])
        self.assertEqual(self.invoke(p).returncode, 0)
        prof = self.out / "profiles" / "C000001.dat"
        geom = self.out / "geomturbo" / "C000001.geomTurbo"
        before = (prof.stat().st_mtime_ns, geom.stat().st_mtime_ns)
        proc = self.invoke(p, "--overwrite")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.cases_of(proc)[0]["action"], "SKIP_MATCH")
        self.assertEqual((prof.stat().st_mtime_ns, geom.stat().st_mtime_ns), before)


class TestConflicts(CliTestBase):
    def cases_of(self, proc):
        return [o for o in parse_jsonl(proc.stdout) if o.get("type") == "case"]

    def put(self, rel, data):
        p = self.out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def test_T14_partial_conflict_no_overwrite(self):
        prof = self.put("profiles/C000001.dat", b"stale profile\n")
        p = self.csv_path([row(case_id="C000001")])
        proc = self.invoke(p)
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertEqual(self.cases_of(proc)[0]["action"], "CONFLICT_PARTIAL")
        self.assertEqual(prof.read_bytes(), b"stale profile\n")
        self.assertFalse((self.out / "geomturbo" / "C000001.geomTurbo").exists())

    def test_T15_partial_dry_run_overwrite(self):
        prof = self.put("profiles/C000001.dat", b"stale profile\n")
        p = self.csv_path([row(case_id="C000001")])
        proc = self.invoke(p, "--dry-run", "--overwrite")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.cases_of(proc)[0]["action"], "WOULD_OVERWRITE")
        self.assertEqual(prof.read_bytes(), b"stale profile\n")
        self.assertFalse((self.out / "geomturbo" / "C000001.geomTurbo").exists())

    def test_T16_partial_normal_overwrite(self):
        self.put("profiles/C000001.dat", b"stale profile\n")
        p = self.csv_path([row(case_id="C000001")])
        proc = self.invoke(p, "--overwrite")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.cases_of(proc)[0]["action"], "OVERWRITE")
        self.assertEqual((self.out / "profiles" / "C000001.dat").read_bytes(),
                         LG001_PROFILE)
        self.assertEqual((self.out / "geomturbo" / "C000001.geomTurbo").read_bytes(),
                         LG001_GEOMTURBO)

    def test_T17_content_conflict_no_overwrite(self):
        prof = self.put("profiles/C000001.dat", b"wrong profile\n")
        geom = self.put("geomturbo/C000001.geomTurbo", b"wrong geomTurbo\n")
        pb, gb = prof.read_bytes(), geom.read_bytes()
        p = self.csv_path([row(case_id="C000001")])
        proc = self.invoke(p)
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertEqual(self.cases_of(proc)[0]["action"], "CONFLICT_CONTENT")
        self.assertEqual(prof.read_bytes(), pb)
        self.assertEqual(geom.read_bytes(), gb)

    def test_T18_content_dry_run_overwrite(self):
        prof = self.put("profiles/C000001.dat", b"wrong profile\n")
        geom = self.put("geomturbo/C000001.geomTurbo", b"wrong geomTurbo\n")
        p = self.csv_path([row(case_id="C000001")])
        proc = self.invoke(p, "--dry-run", "--overwrite")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.cases_of(proc)[0]["action"], "WOULD_OVERWRITE")
        self.assertEqual(prof.read_bytes(), b"wrong profile\n")
        self.assertEqual(geom.read_bytes(), b"wrong geomTurbo\n")

    def test_T19_content_normal_overwrite(self):
        self.put("profiles/C000001.dat", b"wrong profile\n")
        self.put("geomturbo/C000001.geomTurbo", b"wrong geomTurbo\n")
        p = self.csv_path([row(case_id="C000001")])
        proc = self.invoke(p, "--overwrite")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.cases_of(proc)[0]["action"], "OVERWRITE")
        self.assertEqual((self.out / "profiles" / "C000001.dat").read_bytes(),
                         LG001_PROFILE)
        self.assertEqual((self.out / "geomturbo" / "C000001.geomTurbo").read_bytes(),
                         LG001_GEOMTURBO)

    def test_T20_dry_run_create_makes_no_dirs(self):
        out = self.tmp / "nonexistent" / "deeper"
        p = self.csv_path([row(case_id="C000001")])
        proc = self.invoke(p, "--dry-run", output=out)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.cases_of(proc)[0]["action"], "CREATE")
        self.assertFalse(out.exists())
        self.assertFalse((self.tmp / "nonexistent").exists())

    def test_T21_dry_run_conflict_no_overwrite(self):
        prof = self.put("profiles/C000001.dat", b"wrong profile\n")
        self.put("geomturbo/C000001.geomTurbo", b"wrong geomTurbo\n")
        p = self.csv_path([row(case_id="C000001")])
        proc = self.invoke(p, "--dry-run")
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertEqual(self.cases_of(proc)[0]["action"], "CONFLICT_CONTENT")
        self.assertEqual(prof.read_bytes(), b"wrong profile\n")

    def test_T22_template_sha256(self):
        p = self.csv_path([row(case_id="C000001")])
        proc = self.invoke(p, "--dry-run")
        summary = self.summary_of(proc)[-1]
        self.assertEqual(summary["template_sha256"], sha256_file(TEMPLATE))


class TestBehaviorInvariance(CliTestBase):
    def test_T23_incidence_mach_do_not_affect_geometry(self):
        rows = [
            row(case_id="C000001", Incidence="-4.0", Mach="0.3"),
            row(case_id="C000002", Incidence="4.0", Mach="0.7"),
        ]
        p = self.csv_path(rows)
        proc = self.invoke(p)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        prof1 = (self.out / "profiles" / "C000001.dat").read_bytes()
        prof2 = (self.out / "profiles" / "C000002.dat").read_bytes()
        geom1 = (self.out / "geomturbo" / "C000001.geomTurbo").read_bytes()
        geom2 = (self.out / "geomturbo" / "C000002.geomTurbo").read_bytes()
        self.assertEqual(prof1, prof2)
        self.assertEqual(geom1, geom2)

    def test_T24_solidity_affects_only_geomturbo(self):
        rows = [
            row(case_id="C000001", Solidity="1.5"),
            row(case_id="C000002", Solidity="2.0"),
        ]
        p = self.csv_path(rows)
        proc = self.invoke(p)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        prof1 = (self.out / "profiles" / "C000001.dat").read_bytes()
        prof2 = (self.out / "profiles" / "C000002.dat").read_bytes()
        geom1 = (self.out / "geomturbo" / "C000001.geomTurbo").read_bytes()
        geom2 = (self.out / "geomturbo" / "C000002.geomTurbo").read_bytes()
        self.assertEqual(prof1, prof2)
        self.assertNotEqual(geom1, geom2)


class TestJsonlContract(CliTestBase):
    def test_jsonl_valid_and_summary_last(self):
        rows = [row(case_id="C000001"), row(case_id="C000002"), row(case_id="C000003")]
        p = self.csv_path(rows)
        proc = self.invoke(p, "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        objs = [json.loads(ln) for ln in proc.stdout.splitlines() if ln.strip()]
        self.assertEqual(objs[-1]["type"], "summary")
        cases = [o for o in objs if o["type"] == "case"]
        self.assertEqual(len(cases), objs[-1]["selected_count"])
        for o in cases:
            for k in ("type", "case_id", "action", "profile_path",
                      "geomturbo_path", "reason"):
                self.assertIn(k, o)
        for k in ("input_path", "output_path", "template_path", "template_sha256",
                  "dry_run", "overwrite", "selected_count", "create_count",
                  "skip_match_count", "overwrite_count", "conflict_count",
                  "would_overwrite_count", "error_count",
                  "predicted_conflict_count", "predicted_error_count"):
            self.assertIn(k, objs[-1])


class TestCoreIntegrity(unittest.TestCase):
    def test_T25_pure_core_not_modified(self):
        proc = subprocess.run(
            ["git", "diff", "--quiet", "--", "code/geometry_legacy_v1.py"],
            cwd=str(REPO), capture_output=True)
        self.assertEqual(proc.returncode, 0,
                         "code/geometry_legacy_v1.py must not be modified")


def load_cli_module():
    spec = importlib.util.spec_from_file_location("gen02_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestGenerationErrorExit4(unittest.TestCase):
    """exit=4 via a controlled pure-core failure (mock; core is not modified)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.mod = load_cli_module()

    def tearDown(self):
        self._tmp.cleanup()

    def test_controlled_error_gives_exit_4_and_batch_continues(self):
        rows = [row(case_id="C000001"), row(case_id="C000002")]
        csvp = write_csv(self.tmp / "design.csv", rows)
        out = self.tmp / "geometry"
        args = self.mod.build_parser().parse_args(
            ["--input", str(csvp), "--template", str(TEMPLATE), "--output", str(out)])

        orig = self.mod.geo.generate_geometry_texts
        state = {"n": 0}

        def fake(*a, **k):
            state["n"] += 1
            if state["n"] == 2:
                raise RuntimeError("controlled boom")
            return orig(*a, **k)

        self.mod.geo.generate_geometry_texts = fake
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = self.mod.run(args)
        finally:
            self.mod.geo.generate_geometry_texts = orig

        self.assertEqual(rc, 4)
        objs = [json.loads(ln) for ln in buf.getvalue().splitlines() if ln.strip()]
        cases = [o for o in objs if o["type"] == "case"]
        summary = objs[-1]
        self.assertEqual(summary["type"], "summary")
        self.assertEqual(summary["error_count"], 1)
        self.assertEqual(summary["predicted_error_count"], 1)
        actions = [c["action"] for c in cases]
        self.assertIn("ERROR", actions)
        self.assertIn("CREATE", actions)          # other case still processed
        failed = next(c for c in cases if c["action"] == "ERROR")
        self.assertFalse(Path(failed["profile_path"]).exists())
        self.assertFalse(Path(failed["geomturbo_path"]).exists())


# ---------------------------------------------------------------------------
# PART B - template newline semantics (N1..N5)
# ---------------------------------------------------------------------------
def _cases(stdout):
    return [o for o in (json.loads(ln) for ln in stdout.splitlines() if ln.strip())
            if o.get("type") == "case"]


def _summary(stdout):
    return [json.loads(ln) for ln in stdout.splitlines() if ln.strip()][-1]


def _invoke(mod, csv_path, out_path, template, *extra):
    """Run the CLI in-process, mirroring main()'s CliError -> exit 2 handling."""
    args = mod.build_parser().parse_args(
        ["--input", str(csv_path), "--template", str(template),
         "--output", str(out_path)] + [str(x) for x in extra])
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = mod.run(args)
    except mod.CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        rc = mod.EXIT_CLI
    return rc, buf.getvalue()


def _temp_leftovers(directory):
    return [p.name for p in Path(directory).iterdir() if ".part" in p.name]


class TemplateNewlineBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.mod = load_cli_module()
        self.raw = TEMPLATE.read_bytes()
        self.lf_text = (self.raw.decode("utf-8")
                        .replace("\r\n", "\n").replace("\r", "\n"))

    def tearDown(self):
        self._tmp.cleanup()

    def csv_one(self):
        return write_csv(self.tmp / "design.csv", [row(case_id="C000001")])


class TestTemplateNewlineSemantics(TemplateNewlineBase):
    def test_N1_raw_crlf_template(self):
        csvp = self.csv_one()
        out = self.tmp / "out"
        rc, sout = _invoke(self.mod, csvp, out, TEMPLATE)
        self.assertEqual(rc, 0, sout)
        self.assertEqual(_summary(sout)["template_sha256"],
                         hashlib.sha256(self.raw).hexdigest())
        self.assertEqual((out / "profiles" / "C000001.dat").read_bytes(),
                         LG001_PROFILE)
        self.assertEqual((out / "geomturbo" / "C000001.geomTurbo").read_bytes(),
                         LG001_GEOMTURBO)

    def test_N2_lf_clone(self):
        lf = self.tmp / "template_lf.geomTurbo"
        lf.write_bytes(self.lf_text.encode("utf-8"))
        csvp = self.csv_one()
        out_a, out_b = self.tmp / "out_crlf", self.tmp / "out_lf"
        rc_a, _ = _invoke(self.mod, csvp, out_a, TEMPLATE)
        rc_b, sb = _invoke(self.mod, csvp, out_b, lf)
        self.assertEqual((rc_a, rc_b), (0, 0), sb)
        self.assertNotEqual(hashlib.sha256(self.raw).hexdigest(),
                            hashlib.sha256(lf.read_bytes()).hexdigest())
        self.assertEqual(_summary(sb)["template_sha256"],
                         hashlib.sha256(lf.read_bytes()).hexdigest())
        for rel in ("profiles/C000001.dat", "geomturbo/C000001.geomTurbo"):
            self.assertEqual((out_a / rel).read_bytes(), (out_b / rel).read_bytes(),
                             f"{rel} must be identical for CRLF vs LF template")

    def test_N3_cr_only_clone(self):
        cr = self.tmp / "template_cr.geomTurbo"
        cr.write_bytes(self.lf_text.replace("\n", "\r").encode("utf-8"))
        csvp = self.csv_one()
        out = self.tmp / "out_cr"
        rc, sout = _invoke(self.mod, csvp, out, cr)
        self.assertEqual(rc, 0, sout)
        self.assertNotEqual(_summary(sout)["template_sha256"],
                            hashlib.sha256(self.raw).hexdigest())
        self.assertEqual((out / "geomturbo" / "C000001.geomTurbo").read_bytes(),
                         LG001_GEOMTURBO)

    def test_N4_non_newline_whitespace_preserved(self):
        import re as _re
        text, n = _re.subn(r"(UNITS\s+)Meters", r"\1 Meters", self.lf_text, count=1)
        self.assertEqual(n, 1, "expected an 'UNITS ... Meters' marker in the template")
        clone = self.tmp / "template_ws.geomTurbo"
        clone.write_bytes(text.encode("utf-8"))
        csvp = self.csv_one()
        out = self.tmp / "out_ws"
        rc, sout = _invoke(self.mod, csvp, out, clone)
        self.assertEqual(rc, 0, sout)   # structural guards still satisfied
        generated = (out / "geomturbo" / "C000001.geomTurbo").read_bytes()
        self.assertNotEqual(generated, LG001_GEOMTURBO,
                            "extra space must NOT be normalized away")
        mod_line = next(ln for ln in text.splitlines() if ln.startswith("UNITS"))
        self.assertIn(mod_line.encode(), generated)
        self.assertNotIn(mod_line.encode(), LG001_GEOMTURBO)

    def test_N5_invalid_utf8_template(self):
        bad = self.tmp / "bad.geomTurbo"
        bad.write_bytes(b"\xff\xfe\x00GEOMETRY TURBO\n")
        csvp = self.csv_one()
        out = self.tmp / "out_bad"
        rc, sout = _invoke(self.mod, csvp, out, bad)
        self.assertEqual(rc, 2, sout)
        self.assertFalse(out.exists())


# ---------------------------------------------------------------------------
# PART C - failure injection audit
# ---------------------------------------------------------------------------
class AtomicFailureBase(TemplateNewlineBase):
    def _seed_content_conflict(self, out):
        prof = out / "profiles" / "C000001.dat"
        geom = out / "geomturbo" / "C000001.geomTurbo"
        prof.parent.mkdir(parents=True, exist_ok=True)
        geom.parent.mkdir(parents=True, exist_ok=True)
        prof.write_bytes(b"old profile\n")
        geom.write_bytes(b"old geomTurbo\n")
        return prof, geom


class TestAtomicWriterFailure(AtomicFailureBase):
    def test_fsync_failure_before_replace(self):
        csvp = self.csv_one()
        out = self.tmp / "out"
        prof, geom = self._seed_content_conflict(out)
        with mock.patch("os.fsync", side_effect=OSError("injected fsync")):
            rc, sout = _invoke(self.mod, csvp, out, TEMPLATE, "--overwrite")
        self.assertEqual(rc, 4, sout)
        self.assertEqual(_cases(sout)[0]["action"], "ERROR")
        self.assertEqual(prof.read_bytes(), b"old profile\n")
        self.assertEqual(geom.read_bytes(), b"old geomTurbo\n")
        self.assertEqual(_temp_leftovers(prof.parent), [])

    def test_replace_failure(self):
        csvp = self.csv_one()
        out = self.tmp / "out"
        prof, geom = self._seed_content_conflict(out)
        with mock.patch("os.replace", side_effect=OSError("injected replace")):
            rc, sout = _invoke(self.mod, csvp, out, TEMPLATE, "--overwrite")
        self.assertEqual(rc, 4, sout)
        self.assertEqual(_cases(sout)[0]["action"], "ERROR")
        self.assertEqual(prof.read_bytes(), b"old profile\n")
        self.assertEqual(geom.read_bytes(), b"old geomTurbo\n")
        self.assertEqual(_temp_leftovers(prof.parent), [])

    def test_mkstemp_failure(self):
        csvp = self.csv_one()
        out = self.tmp / "out"
        with mock.patch("tempfile.mkstemp", side_effect=OSError("injected mkstemp")):
            rc, sout = _invoke(self.mod, csvp, out, TEMPLATE)
        self.assertEqual(rc, 4, sout)
        self.assertEqual(_cases(sout)[0]["action"], "ERROR")
        self.assertFalse((out / "profiles" / "C000001.dat").exists())
        self.assertNotIn("Traceback", sout)


class TestPairSecondWriteFailure(AtomicFailureBase):
    def _flaky_writer(self):
        real = self.mod._atomic_write_bytes
        state = {"n": 0}

        def flaky(path, data):
            state["n"] += 1
            if state["n"] == 2:
                raise OSError("injected second-write failure")
            return real(path, data)

        return real, flaky

    def test_create_second_write_failure_then_recovery(self):
        csvp = self.csv_one()
        out = self.tmp / "out"
        real, flaky = self._flaky_writer()
        self.mod._atomic_write_bytes = flaky
        try:
            rc, sout = _invoke(self.mod, csvp, out, TEMPLATE)
        finally:
            self.mod._atomic_write_bytes = real
        self.assertEqual(rc, 4, sout)
        self.assertEqual(_cases(sout)[0]["action"], "ERROR")
        prof = out / "profiles" / "C000001.dat"
        geom = out / "geomturbo" / "C000001.geomTurbo"
        self.assertTrue(prof.exists())
        self.assertEqual(prof.read_bytes(), LG001_PROFILE)   # valid candidate
        self.assertFalse(geom.exists())

        rc2, sout2 = _invoke(self.mod, csvp, out, TEMPLATE)
        self.assertEqual(rc2, 3, sout2)
        self.assertEqual(_cases(sout2)[0]["action"], "CONFLICT_PARTIAL")
        self.assertFalse(geom.exists())                      # no auto-fill

        rc3, sout3 = _invoke(self.mod, csvp, out, TEMPLATE, "--overwrite")
        self.assertEqual(rc3, 0, sout3)
        self.assertEqual(_cases(sout3)[0]["action"], "OVERWRITE")
        self.assertEqual(prof.read_bytes(), LG001_PROFILE)
        self.assertEqual(geom.read_bytes(), LG001_GEOMTURBO)

    def test_overwrite_second_write_failure_then_recovery(self):
        csvp = self.csv_one()
        out = self.tmp / "out"
        prof, geom = self._seed_content_conflict(out)
        real, flaky = self._flaky_writer()
        self.mod._atomic_write_bytes = flaky
        try:
            rc, sout = _invoke(self.mod, csvp, out, TEMPLATE, "--overwrite")
        finally:
            self.mod._atomic_write_bytes = real
        self.assertEqual(rc, 4, sout)
        self.assertEqual(_cases(sout)[0]["action"], "ERROR")
        self.assertNotEqual(_cases(sout)[0]["action"], "OVERWRITE")
        self.assertEqual(prof.read_bytes(), LG001_PROFILE)         # replaced
        self.assertEqual(geom.read_bytes(), b"old geomTurbo\n")    # still old

        rc2, sout2 = _invoke(self.mod, csvp, out, TEMPLATE, "--dry-run")
        self.assertEqual(rc2, 3, sout2)
        self.assertEqual(_cases(sout2)[0]["action"], "CONFLICT_CONTENT")

        rc3, sout3 = _invoke(self.mod, csvp, out, TEMPLATE, "--overwrite")
        self.assertEqual(rc3, 0, sout3)
        self.assertEqual(_cases(sout3)[0]["action"], "OVERWRITE")
        self.assertEqual(geom.read_bytes(), LG001_GEOMTURBO)


class TestBatchContinuationOnIoError(TemplateNewlineBase):
    def test_first_case_io_error_second_succeeds(self):
        csvp = write_csv(self.tmp / "design.csv",
                         [row(case_id="C000001"), row(case_id="C000002")])
        out = self.tmp / "out"
        real = self.mod._atomic_write_bytes

        def flaky(path, data):
            if "C000001" in str(path):
                raise OSError("injected failure for C000001")
            return real(path, data)

        self.mod._atomic_write_bytes = flaky
        try:
            rc, sout = _invoke(self.mod, csvp, out, TEMPLATE)
        finally:
            self.mod._atomic_write_bytes = real

        self.assertEqual(rc, 4, sout)
        cases = _cases(sout)
        summary = _summary(sout)
        self.assertEqual(len(cases), 2)
        self.assertEqual(cases[0]["action"], "ERROR")
        self.assertEqual(cases[1]["action"], "CREATE")
        self.assertEqual(summary["type"], "summary")
        self.assertEqual(summary["error_count"], 1)
        self.assertEqual(summary["selected_count"], 2)
        self.assertTrue((out / "profiles" / "C000002.dat").exists())
        self.assertNotIn("Traceback", sout)


class TestOutputPathObstruction(TemplateNewlineBase):
    def test_output_root_is_a_file(self):
        csvp = self.csv_one()
        out = self.tmp / "blocked"
        out.write_text("i am a file, not a directory\n")
        rc, sout = _invoke(self.mod, csvp, out, TEMPLATE)
        self.assertNotIn("Traceback", sout)
        objs = [json.loads(ln) for ln in sout.splitlines() if ln.strip()]
        self.assertEqual(objs[-1]["type"], "summary")
        self.assertEqual(objs[-1]["error_count"], 1)
        self.assertEqual(rc, 4)
        self.assertEqual(out.read_text(), "i am a file, not a directory\n")

    def test_profiles_path_is_a_file(self):
        csvp = self.csv_one()
        out = self.tmp / "out2"
        out.mkdir()
        (out / "profiles").write_text("blocking file\n")
        rc, sout = _invoke(self.mod, csvp, out, TEMPLATE)
        self.assertNotIn("Traceback", sout)
        objs = [json.loads(ln) for ln in sout.splitlines() if ln.strip()]
        self.assertEqual(objs[-1]["type"], "summary")
        self.assertEqual(objs[-1]["error_count"], 1)
        self.assertEqual(rc, 4)


class TestDryRunObstruction(TemplateNewlineBase):
    def _assert_error_jsonl(self, sout, expect_predicted_error=1):
        self.assertNotIn("Traceback", sout)
        objs = [json.loads(ln) for ln in sout.splitlines() if ln.strip()]
        self.assertEqual(objs[-1]["type"], "summary")
        self.assertEqual(objs[-1]["error_count"], 1)
        self.assertEqual(objs[-1]["predicted_error_count"], expect_predicted_error)
        case = next(o for o in objs if o["type"] == "case")
        self.assertEqual(case["action"], "ERROR")
        self.assertTrue(case["reason"].strip(), "ERROR reason must be non-empty")
        return objs[-1]

    def test_O1_dry_run_output_root_is_file(self):
        csvp = self.csv_one()
        out = self.tmp / "blocked"
        out.write_text("i am a file\n")
        before = out.read_text()
        rc, sout = _invoke(self.mod, csvp, out, TEMPLATE, "--dry-run")
        self.assertEqual(rc, 4, sout)
        self._assert_error_jsonl(sout)
        self.assertEqual(out.read_text(), before)
        self.assertTrue(out.is_file())
        self.assertFalse((self.tmp / "blocked" / "profiles").exists())

    def test_O2_dry_run_profiles_path_is_file(self):
        csvp = self.csv_one()
        out = self.tmp / "out2"
        out.mkdir()
        (out / "profiles").write_text("blocking file\n")
        listing_before = sorted(p.name for p in out.iterdir())
        rc, sout = _invoke(self.mod, csvp, out, TEMPLATE, "--dry-run")
        self.assertEqual(rc, 4, sout)
        self._assert_error_jsonl(sout)
        self.assertEqual(sorted(p.name for p in out.iterdir()), listing_before)
        self.assertTrue((out / "profiles").is_file())

    def test_O3_dry_run_geomturbo_path_is_file(self):
        csvp = self.csv_one()
        out = self.tmp / "out3"
        out.mkdir()
        (out / "geomturbo").write_text("blocking file\n")
        listing_before = sorted(p.name for p in out.iterdir())
        rc, sout = _invoke(self.mod, csvp, out, TEMPLATE, "--dry-run")
        self.assertEqual(rc, 4, sout)
        self._assert_error_jsonl(sout)
        self.assertEqual(sorted(p.name for p in out.iterdir()), listing_before)
        self.assertTrue((out / "geomturbo").is_file())
        self.assertFalse((out / "profiles").exists())

    def test_obstruction_creates_no_temp_files(self):
        csvp = self.csv_one()
        out = self.tmp / "out4"
        out.mkdir()
        (out / "profiles").write_text("blocking file\n")
        _invoke(self.mod, csvp, out, TEMPLATE, "--dry-run")
        self.assertEqual(_temp_leftovers(out), [])
        self.assertEqual(_temp_leftovers(self.tmp), [])


if __name__ == "__main__":
    unittest.main()
