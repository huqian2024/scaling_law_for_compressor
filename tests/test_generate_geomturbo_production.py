"""Tests for ``code/generate_geomturbo_production.py``.

Every generation test patches ``render_geomturbo_text`` with a STUB.  The real
frozen generator is additionally patched to raise, so the suite can never
produce a real .geomTurbo file.  Files written into temporary directories
contain only the stub text and exist solely to exercise the manifest / resume
logic.
"""

import csv
import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import numpy as np
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "code"))

import generate_geomturbo_production as prod  # noqa: E402

CONFIG = REPO / "config" / "geometry_ranges_frozen_a.yaml"
FINAL_YAML = (REPO / "analysis" / "geometry_review"
              / "parameter_final_decision_v1" / "final_geometry_parameters.yaml")
TEMPLATE_SHA = ("92c4296f2de27440aebaad9b03b9af4f9e09756fabff2298f4607a87f2c55119")

EXPECTED_RANGES = {
    "Xthick": (0.10, 0.60),
    "Tmax": (0.025, 0.095),
    "Metal2": (6.0, 32.0),
    "Solidity": (0.7, 2.5),
    "Metal1": (48.0, 58.0),
    "T1": (0.010, 0.018),
    "T2": (0.008, 0.016),
    "Xmean": (0.06, 0.18),
    "K_m": (0.10, 0.35),
    "Ks1": (3.0, 7.0),
    "Ks2": (0.05, 0.20),
}


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = prod.main(argv)
    return code, out.getvalue(), err.getvalue()


class TestFrozenConfig(unittest.TestCase):
    def test_frozen_values(self):
        cfg = prod.load_config(CONFIG)
        self.assertEqual(cfg["status"], "FROZEN")
        self.assertEqual(cfg["order"], prod.EXPECTED_PARAMS)
        self.assertEqual(len(cfg["ranges"]), 11)
        for name, (lo, hi) in EXPECTED_RANGES.items():
            self.assertAlmostEqual(cfg["ranges"][name][0], lo, places=12)
            self.assertAlmostEqual(cfg["ranges"][name][1], hi, places=12)
        self.assertAlmostEqual(cfg["fixed"]["SS1"], 3.2, places=12)
        self.assertAlmostEqual(cfg["fixed"]["SS2"], 0.8, places=12)
        self.assertEqual(cfg["default_count"], 200000)
        self.assertEqual(cfg["default_seed"], 1)
        self.assertEqual(cfg["template_sha"], TEMPLATE_SHA)

    def test_metal2_lower_bound(self):
        cfg = prod.load_config(CONFIG)
        self.assertEqual(cfg["ranges"]["Metal2"][0], 6.0)
        lo_params = prod.map_point(np.zeros(11), cfg["ranges"])
        self.assertAlmostEqual(lo_params["Metal2"], 6.0, places=12)

    def test_matches_final_decision_yaml(self):
        doc = yaml.safe_load(FINAL_YAML.read_text(encoding="utf-8"))
        self.assertEqual(doc["status"], "FROZEN_FOR_GEOMTURBO_GENERATION")
        keep = {p["name"]: p["range"] for p in doc["keep_parameters"]}
        self.assertEqual(set(keep), set(EXPECTED_RANGES))
        for name, (lo, hi) in EXPECTED_RANGES.items():
            self.assertAlmostEqual(float(keep[name][0]), lo, places=12)
            self.assertAlmostEqual(float(keep[name][1]), hi, places=12)
        fixed = {p["name"]: p["value"] for p in doc["fixed_parameters"]}
        self.assertAlmostEqual(float(fixed["SS1"]), 3.2, places=12)
        self.assertAlmostEqual(float(fixed["SS2"]), 0.8, places=12)
        self.assertEqual(doc["freeze"]["scope"],
                         "geomturbo_geometry_generation_only")

    def test_default_count_and_sobol_m(self):
        self.assertEqual(prod.sobol_m(200000), 18)
        self.assertGreaterEqual(1 << prod.sobol_m(200000), 200000)
        self.assertLess(1 << (prod.sobol_m(200000) - 1), 200000)
        self.assertEqual(prod.sobol_m(1), 0)
        self.assertEqual(prod.sobol_m(262144), 18)

    def test_rejects_non_frozen_status(self):
        text = CONFIG.read_text(encoding="utf-8").replace(
            "status: FROZEN", "status: DRAFT", 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.yaml"
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(prod.CliError):
                prod.load_config(path)

    def test_rejects_changed_fixed_parameter(self):
        text = CONFIG.read_text(encoding="utf-8").replace(
            "SS1: 3.2", "SS1: 3.0", 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.yaml"
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(prod.CliError):
                prod.load_config(path)

    def test_rejects_reordered_parameters(self):
        text = CONFIG.read_text(encoding="utf-8")
        text = text.replace(
            "  - Xthick\n  - Tmax\n", "  - Tmax\n  - Xthick\n", 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.yaml"
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(prod.CliError):
                prod.load_config(path)


class TestSampling(unittest.TestCase):
    def test_determinism(self):
        a, m_a = prod.sobol_points(1000, 1)
        b, m_b = prod.sobol_points(1000, 1)
        self.assertEqual(m_a, m_b)
        self.assertTrue(np.array_equal(a, b))

    def test_prefix_consistency(self):
        small, _ = prod.sobol_points(1000, 1)
        large, _ = prod.sobol_points(5000, 1)
        self.assertTrue(np.array_equal(small, large[:1000]))

    def test_seed_changes_sequence(self):
        a, _ = prod.sobol_points(1000, 1)
        b, _ = prod.sobol_points(1000, 2)
        self.assertFalse(np.array_equal(a, b))

    def test_unit_cube_and_mapping(self):
        points, _ = prod.sobol_points(64, 1)
        self.assertEqual(points.shape, (64, 11))
        self.assertTrue(np.all(points >= 0.0))
        self.assertTrue(np.all(points < 1.0))
        cfg = prod.load_config(CONFIG)
        lo = prod.map_point(np.zeros(11), cfg["ranges"])
        hi = prod.map_point(np.ones(11), cfg["ranges"])
        for name, (lo_v, hi_v) in EXPECTED_RANGES.items():
            self.assertAlmostEqual(lo[name], lo_v, places=12)
            self.assertAlmostEqual(hi[name], hi_v, places=12)
        self.assertAlmostEqual(lo["SS1"], 3.2, places=12)
        self.assertAlmostEqual(lo["SS2"], 0.8, places=12)
        self.assertEqual(len(lo), 13)

    def test_case_ids(self):
        self.assertEqual(prod.case_id(1), "G0000001")
        self.assertEqual(prod.case_id(200000), "G0200000")
        ids = {prod.case_id(i) for i in range(1, 200001)}
        self.assertEqual(len(ids), 200000)
        self.assertEqual(prod.batch_number(1, 5000), 1)
        self.assertEqual(prod.batch_number(5000, 5000), 1)
        self.assertEqual(prod.batch_number(5001, 5000), 2)
        self.assertEqual(prod.batch_dir_name(2), "batch_000002")


class TestPlanAndSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_plan_writes_nothing(self):
        out = Path(self.tmp.name) / "gen"
        code, stdout, _ = run_main(["--plan", "--output-dir", str(out)])
        self.assertEqual(code, 0)
        self.assertIn("PLAN ONLY", stdout)
        self.assertIn("count             : 200000", stdout)
        self.assertIn("Metal2", stdout)
        self.assertIn("G0000001", stdout)
        self.assertIn("G0200000", stdout)
        self.assertFalse(out.exists())

    def test_plan_never_calls_generator(self):
        out = Path(self.tmp.name) / "gen"
        with mock.patch.object(prod, "render_geomturbo_text",
                               side_effect=AssertionError("must not render")):
            code, _, _ = run_main(["--plan", "--output-dir", str(out)])
        self.assertEqual(code, 0)
        self.assertFalse(out.exists())

    def test_execute_required(self):
        out = Path(self.tmp.name) / "gen"
        code, _, stderr = run_main(["--count", "5", "--output-dir", str(out)])
        self.assertEqual(code, 2)
        self.assertIn("refusing to run without --execute", stderr)
        self.assertFalse(out.exists())

    def test_plan_and_execute_are_exclusive(self):
        out = Path(self.tmp.name) / "gen"
        code, _, stderr = run_main(["--plan", "--execute",
                                    "--output-dir", str(out)])
        self.assertEqual(code, 2)
        self.assertIn("mutually exclusive", stderr)
        self.assertFalse(out.exists())

    def test_help_does_not_generate(self):
        with self.assertRaises(SystemExit) as ctx:
            with redirect_stdout(io.StringIO()):
                prod.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_refuses_unrelated_nonempty_dir(self):
        out = Path(self.tmp.name) / "gen"
        out.mkdir()
        (out / "notes.txt").write_text("unrelated", encoding="utf-8")
        with mock.patch.object(prod, "render_geomturbo_text",
                               side_effect=AssertionError("must not render")):
            code, _, stderr = run_main(["--execute", "--count", "5",
                                        "--output-dir", str(out)])
        self.assertEqual(code, 2)
        self.assertIn("no config_snapshot.yaml", stderr)
        self.assertFalse((out / "batch_000001").exists())



class TestGenerationWithStub(unittest.TestCase):
    """End-to-end manifest/resume tests with a STUB renderer (no real files)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / "gen"
        self.stub = mock.patch.object(
            prod, "render_geomturbo_text",
            side_effect=lambda params, template: "STUB GEOMTURBO\n")
        self.stub.start()
        self.addCleanup(self.stub.stop)
        self.real_generator = mock.patch.object(
            prod.geo, "generate_geometry_texts",
            side_effect=AssertionError("real generator must not be called"))
        self.real_generator.start()
        self.addCleanup(self.real_generator.stop)

    def _run(self, *extra):
        return run_main(["--execute", "--output-dir", str(self.out),
                         "--progress-every", "0", *extra])

    def _manifest_rows(self):
        with open(self.out / prod.MANIFEST_NAME, newline="") as f:
            return list(csv.DictReader(f))

    def test_generate_manifest_and_summary(self):
        code, _stdout, stderr = self._run("--count", "12", "--batch-size", "5")
        self.assertEqual(code, 0, stderr)
        files = sorted(self.out.glob("batch_*/G*.geomTurbo"))
        self.assertEqual(len(files), 12)
        self.assertEqual(files[0].name, "G0000001.geomTurbo")
        self.assertEqual(files[-1].name, "G0000012.geomTurbo")
        self.assertEqual(files[0].read_text(), "STUB GEOMTURBO\n")
        self.assertTrue((self.out / prod.SNAPSHOT_NAME).is_file())
        self.assertTrue((self.out / prod.SUMMARY_NAME).is_file())
        self.assertEqual(list(self.out.glob("**/*.part")), [])

        rows = self._manifest_rows()
        self.assertEqual(len(rows), 12)
        self.assertEqual(list(rows[0].keys()), list(prod.MANIFEST_COLUMNS))
        self.assertEqual({r["status"] for r in rows}, {"OK"})
        self.assertEqual(rows[0]["case_id"], "G0000001")
        self.assertEqual(rows[0]["sobol_index"], "1")
        self.assertEqual(rows[0]["batch"], "1")
        self.assertEqual(rows[0]["path"], "batch_000001/G0000001.geomTurbo")
        self.assertAlmostEqual(float(rows[0]["SS1"]), 3.2, places=12)
        self.assertAlmostEqual(float(rows[0]["SS2"]), 0.8, places=12)
        self.assertGreaterEqual(float(rows[0]["Metal2"]), 6.0)
        sha = hashlib.sha256(files[0].read_bytes()).hexdigest()
        self.assertEqual(rows[0]["sha256"], sha)

        points, _ = prod.sobol_points(12, 1)
        cfg = prod.load_config(CONFIG)
        params = prod.map_point(points[0], cfg["ranges"])
        for name in prod.EXPECTED_PARAMS:
            self.assertEqual(float(rows[0][name]), params[name])

        summary = json.loads((self.out / prod.SUMMARY_NAME).read_text())
        self.assertEqual(summary["count_requested"], 12)
        self.assertEqual(summary["manifest_ok"], 12)
        self.assertEqual(summary["manifest_failed"], 0)
        self.assertTrue(summary["completed"])
        self.assertEqual(summary["written_this_run"], 12)

        snapshot = yaml.safe_load(
            (self.out / prod.SNAPSHOT_NAME).read_text(encoding="utf-8"))
        self.assertEqual(snapshot["config_id"], "geometry_ranges_frozen_a")
        self.assertEqual(snapshot["seed"], 1)
        self.assertEqual(snapshot["batch_size"], 5)
        self.assertEqual(snapshot["sobol_m"], 4)
        self.assertEqual(snapshot["geometry_parameters"],
                         list(prod.EXPECTED_PARAMS))

    def test_resume_skips_completed(self):
        self.assertEqual(self._run("--count", "12", "--batch-size", "5")[0], 0)
        before = {p: p.stat().st_mtime_ns
                  for p in self.out.glob("batch_*/G*.geomTurbo")}
        with mock.patch.object(prod, "render_geomturbo_text",
                               side_effect=AssertionError("must not render")):
            code, _, stderr = self._run("--count", "12", "--batch-size", "5",
                                        "--resume")
        self.assertEqual(code, 0, stderr)
        after = {p: p.stat().st_mtime_ns
                 for p in self.out.glob("batch_*/G*.geomTurbo")}
        self.assertEqual(before, after)
        summary = json.loads((self.out / prod.SUMMARY_NAME).read_text())
        self.assertEqual(summary["written_this_run"], 0)
        self.assertEqual(summary["skipped_existing"], 12)
        self.assertEqual(len(self._manifest_rows()), 12)

    def test_resume_regenerates_corrupt_file(self):
        self.assertEqual(self._run("--count", "12", "--batch-size", "5")[0], 0)
        corrupt = self.out / "batch_000001" / "G0000001.geomTurbo"
        corrupt.write_text("corrupt", encoding="utf-8")
        code, _, stderr = self._run("--count", "12", "--batch-size", "5",
                                    "--resume")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(corrupt.read_text(), "STUB GEOMTURBO\n")
        summary = json.loads((self.out / prod.SUMMARY_NAME).read_text())
        self.assertEqual(summary["written_this_run"], 1)
        rows = {r["case_id"]: r for r in self._manifest_rows()}
        self.assertEqual(rows["G0000001"]["status"], "OK")
        self.assertEqual(
            rows["G0000001"]["sha256"],
            hashlib.sha256(corrupt.read_bytes()).hexdigest())

    def test_resume_refuses_config_change(self):
        self.assertEqual(self._run("--count", "12", "--batch-size", "5")[0], 0)
        files = list(self.out.glob("batch_*/G*.geomTurbo"))
        code, _, stderr = self._run("--count", "12", "--batch-size", "5",
                                    "--seed", "2", "--resume")
        self.assertEqual(code, 2)
        self.assertIn("resume refused", stderr)
        self.assertEqual(len(list(self.out.glob("batch_*/G*.geomTurbo"))),
                         len(files))


    def test_failure_is_recorded_and_retried(self):
        calls = {"n": 0}

        def flaky(params, template):
            calls["n"] += 1
            if calls["n"] == 3:
                raise RuntimeError("synthetic failure")
            return "STUB GEOMTURBO\n"

        with mock.patch.object(prod, "render_geomturbo_text",
                               side_effect=flaky):
            code, _, _ = self._run("--count", "5", "--batch-size", "2")
        self.assertEqual(code, 4)
        rows = {r["case_id"]: r for r in self._manifest_rows()}
        self.assertEqual(rows["G0000003"]["status"], "FAILED")
        self.assertIn("synthetic failure", rows["G0000003"]["error"])
        self.assertEqual(sum(1 for r in rows.values() if r["status"] == "OK"), 4)

        code, _, stderr = self._run("--count", "5", "--batch-size", "2",
                                    "--resume")
        self.assertEqual(code, 0, stderr)
        rows = {r["case_id"]: r for r in self._manifest_rows()}
        self.assertEqual(rows["G0000003"]["status"], "OK")
        summary = json.loads((self.out / prod.SUMMARY_NAME).read_text())
        self.assertEqual(summary["manifest_failed"], 0)

    def test_count_can_grow_and_shrink_as_prefix(self):
        self.assertEqual(self._run("--count", "6", "--batch-size", "5")[0], 0)
        first = (self.out / "batch_000001" / "G0000001.geomTurbo").read_text()
        code, _, stderr = self._run("--count", "12", "--batch-size", "5",
                                    "--resume")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(len(list(self.out.glob("batch_*/G*.geomTurbo"))), 12)
        self.assertEqual(
            (self.out / "batch_000001" / "G0000001.geomTurbo").read_text(),
            first)
        self.assertEqual(len(self._manifest_rows()), 12)

        code, _, stderr = self._run("--count", "4", "--batch-size", "5",
                                    "--resume")
        self.assertEqual(code, 0, stderr)
        # shrinking does not delete existing files or manifest rows
        self.assertEqual(len(list(self.out.glob("batch_*/G*.geomTurbo"))), 12)
        self.assertEqual(len(self._manifest_rows()), 12)
        summary = json.loads((self.out / prod.SUMMARY_NAME).read_text())
        self.assertEqual(summary["count_requested"], 4)


    def test_interrupt_flushes_partial_batch_manifest(self):
        counter = {"n": 0}

        def flaky(params, template):
            counter["n"] += 1
            if counter["n"] == 3:
                raise KeyboardInterrupt
            return "STUB GEOMTURBO\n"

        with mock.patch.object(prod, "render_geomturbo_text",
                               side_effect=flaky):
            code, _, stderr = self._run("--count", "5", "--batch-size", "5")
        self.assertEqual(code, 130)
        self.assertIn("interrupted after 2/5", stderr)
        self.assertEqual(len(self._manifest_rows()), 2)
        batch_manifest = self.out / "batch_000001" / prod.MANIFEST_NAME
        self.assertTrue(batch_manifest.is_file())
        with open(batch_manifest, newline="") as f:
            self.assertEqual(len(list(csv.DictReader(f))), 2)

        # --resume must not regenerate cases 1-2 whose rows were flushed
        rendered = []

        def counting(params, template):
            rendered.append(params)
            return "STUB GEOMTURBO\n"

        with mock.patch.object(prod, "render_geomturbo_text",
                               side_effect=counting):
            code, _, stderr = self._run("--count", "5", "--batch-size", "5",
                                        "--resume")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(len(rendered), 3)
        summary = json.loads((self.out / prod.SUMMARY_NAME).read_text())
        self.assertEqual(summary["written_this_run"], 3)
        self.assertEqual(summary["skipped_existing"], 2)
        self.assertEqual(len(self._manifest_rows()), 5)

