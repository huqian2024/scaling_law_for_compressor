"""Tests for ``code/run_geomturbo.py`` (group-aware production launcher).

Most tests patch ``render_geomturbo_text`` with a STUB, so they exercise the
launcher / manifest / resume logic without real geometry.  One test performs a
real single-case export into a temporary directory (never into the repository).

No test may generate a large number of real .geomTurbo files.
"""

import csv
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "code"))

import generate_geomturbo_production as prod  # noqa: E402
import run_geomturbo as runner  # noqa: E402

PARAM_COLUMNS = list(prod.EXPECTED_PARAMS) + ["SS1", "SS2"]


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = runner.main(argv)
        except SystemExit as exc:  # argparse errors
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.default_root = self.root / "production_geomturbo"
        patcher = mock.patch.object(runner, "DEFAULT_ROOT", self.default_root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _install_stub(self, fn=None):
        """Patch the frozen renderer; return the list of rendered param dicts."""
        calls = []

        def render(params, template):
            calls.append(dict(params))
            return "STUB GEOMTURBO\n" if fn is None else fn(params, template)

        patcher = mock.patch.object(prod, "render_geomturbo_text",
                                    side_effect=render)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    def manifest_rows(self, out):
        with open(Path(out) / prod.MANIFEST_NAME, newline="",
                  encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def summary(self, out):
        return json.loads((Path(out) / prod.SUMMARY_NAME).read_text())


class TestArguments(Base):
    def test_required_arguments(self):
        for argv in (["--N", "5", "--seed", "101"],
                     ["--group", "train", "--seed", "101"],
                     ["--group", "train", "--N", "5"]):
            code, _, _ = run_main(argv)
            self.assertEqual(code, 2, argv)

    def test_invalid_group(self):
        code, _, stderr = run_main(
            ["--group", "training", "--N", "5", "--seed", "101", "--plan"])
        self.assertEqual(code, 2)
        self.assertIn("invalid choice", stderr)

    def test_invalid_N(self):
        for value in ("0", "-2", str(10 ** prod.CASE_WIDTH)):
            code, _, stderr = run_main(
                ["--group", "train", "--N", value, "--seed", "101", "--plan"])
            self.assertEqual(code, 2, value)
            self.assertIn("--N", stderr)

    def test_invalid_seed(self):
        code, _, stderr = run_main(
            ["--group", "train", "--N", "5", "--seed", "-1", "--plan"])
        self.assertEqual(code, 2)
        self.assertIn("--seed", stderr)

    def test_plan_and_resume_are_exclusive(self):
        code, _, stderr = run_main(
            ["--group", "train", "--N", "5", "--seed", "101",
             "--plan", "--resume"])
        self.assertEqual(code, 2)
        self.assertIn("cannot be combined", stderr)

    def test_plan_writes_nothing_and_never_renders(self):
        calls = self._install_stub(
            fn=lambda params, template: self.fail("must not render"))
        out = self.root / "planned"
        code, stdout, stderr = run_main(
            ["--group", "train", "--N", "5", "--seed", "101",
             "--plan", "--output-dir", str(out)])
        self.assertEqual(code, 0, stderr)
        self.assertIn("PLAN ONLY", stdout)
        self.assertIn("count             : 5", stdout)
        self.assertIn("G0000005", stdout)
        self.assertFalse(out.exists())
        self.assertEqual(calls, [])

    def test_default_group_directories(self):
        for group in runner.GROUPS:
            code, stdout, stderr = run_main(
                ["--group", group, "--N", "3", "--seed", "101", "--plan"])
            self.assertEqual(code, 0, stderr)
            self.assertIn(str((self.default_root / group).resolve()), stdout)
        self.assertFalse(self.default_root.exists())


class TestGeneration(Base):
    def test_small_run_files_manifest_and_group_info(self):
        self._install_stub()
        out = self.default_root / "train"
        code, stdout, stderr = run_main(
            ["--group", "train", "--N", "3", "--seed", "101"])
        self.assertEqual(code, 0, stderr)
        self.assertIn("mode              : EXECUTE", stdout)
        files = sorted(out.glob("batch_*/G*.geomTurbo"))
        self.assertEqual([p.name for p in files],
                         ["G0000001.geomTurbo", "G0000002.geomTurbo",
                          "G0000003.geomTurbo"])
        rows = self.manifest_rows(out)
        self.assertEqual([r["case_id"] for r in rows],
                         ["G0000001", "G0000002", "G0000003"])
        self.assertEqual({r["status"] for r in rows}, {"OK"})
        self.assertTrue(self.summary(out)["completed"])
        info = json.loads((out / runner.GROUP_INFO_NAME).read_text())
        self.assertEqual(info["group"], "train")
        self.assertEqual(info["seed"], 101)
        self.assertEqual(info["N_candidates"], 3)
        self.assertEqual(info["global_identity"], "group + seed + sobol_index")
        self.assertEqual(list(out.glob("**/*.part")), [])

    def test_same_seed_is_deterministic(self):
        self._install_stub()
        for name in ("a", "b"):
            code, _, stderr = run_main(
                ["--group", "train", "--N", "4", "--seed", "101",
                 "--output-dir", str(self.root / name)])
            self.assertEqual(code, 0, stderr)
        a = [[r[c] for c in PARAM_COLUMNS] for r in
             self.manifest_rows(self.root / "a")]
        b = [[r[c] for c in PARAM_COLUMNS] for r in
             self.manifest_rows(self.root / "b")]
        self.assertEqual(a, b)

    def test_different_seed_differs(self):
        self._install_stub()
        for name, seed in (("seed101", "101"), ("seed202", "202")):
            code, _, stderr = run_main(
                ["--group", "train", "--N", "4", "--seed", seed,
                 "--output-dir", str(self.root / name)])
            self.assertEqual(code, 0, stderr)
        a = [[r[c] for c in PARAM_COLUMNS] for r in
             self.manifest_rows(self.root / "seed101")]
        b = [[r[c] for c in PARAM_COLUMNS] for r in
             self.manifest_rows(self.root / "seed202")]
        self.assertNotEqual(a, b)

    def test_groups_are_isolated_with_repeated_case_ids(self):
        self._install_stub()
        for group in runner.GROUPS:
            code, _, stderr = run_main(
                ["--group", group, "--N", "1", "--seed", "101"])
            self.assertEqual(code, 0, stderr)
            group_dir = self.default_root / group
            self.assertTrue(
                (group_dir / "batch_000001" / "G0000001.geomTurbo").is_file())
            info = json.loads((group_dir / runner.GROUP_INFO_NAME).read_text())
            self.assertEqual(info["group"], group)
        self.assertEqual(len(list(self.default_root.glob("*/manifest.csv"))), 3)
        self.assertEqual(
            len(list(self.default_root.glob("*/batch_*/manifest.csv"))), 3)

    def test_existing_directory_requires_resume(self):
        self._install_stub()
        out = self.root / "gen"
        argv = ["--group", "train", "--N", "2", "--seed", "101",
                "--output-dir", str(out)]
        self.assertEqual(run_main(argv)[0], 0)
        files = sorted(out.glob("batch_*/G*.geomTurbo"))
        code, _, stderr = run_main(argv)
        self.assertEqual(code, 2)
        self.assertIn("already initialized", stderr)
        self.assertEqual(sorted(out.glob("batch_*/G*.geomTurbo")), files)

    def test_resume_refuses_a_different_seed(self):
        self._install_stub()
        out = self.root / "gen"
        self.assertEqual(run_main(
            ["--group", "train", "--N", "2", "--seed", "101",
             "--output-dir", str(out)])[0], 0)
        code, _, stderr = run_main(
            ["--group", "train", "--N", "2", "--seed", "202",
             "--resume", "--output-dir", str(out)])
        self.assertEqual(code, 2)
        self.assertIn("resume refused", stderr)
        info_path = out / runner.GROUP_INFO_NAME
        self.assertEqual(json.loads(info_path.read_text())["seed"], 101)

    def test_resume_with_larger_N_keeps_prefix(self):
        self._install_stub()
        out = self.root / "gen"
        self.assertEqual(run_main(
            ["--group", "train", "--N", "2", "--seed", "101",
             "--output-dir", str(out)])[0], 0)
        before = [[r[c] for c in PARAM_COLUMNS] for r in self.manifest_rows(out)]
        code, _, stderr = run_main(
            ["--group", "train", "--N", "5", "--seed", "101",
             "--resume", "--output-dir", str(out)])
        self.assertEqual(code, 0, stderr)
        rows = self.manifest_rows(out)
        self.assertEqual(len(rows), 5)
        after = [[r[c] for c in PARAM_COLUMNS] for r in rows[:2]]
        self.assertEqual(before, after)
        self.assertEqual(self.summary(out)["written_this_run"], 3)

    def test_failure_is_recorded_and_retried(self):
        counter = {"n": 0}

        def flaky(params, template):
            counter["n"] += 1
            if counter["n"] == 2:
                raise RuntimeError("synthetic failure")
            return "STUB GEOMTURBO\n"

        self._install_stub(flaky)
        out = self.root / "gen"
        argv = ["--group", "val", "--N", "3", "--seed", "101",
                "--output-dir", str(out)]
        code, _, _ = run_main(argv)
        self.assertEqual(code, 4)
        rows = {r["case_id"]: r for r in self.manifest_rows(out)}
        self.assertEqual(rows["G0000002"]["status"], "FAILED")
        self.assertIn("synthetic failure", rows["G0000002"]["error"])
        self.assertEqual(
            sum(1 for r in rows.values() if r["status"] == "OK"), 2)
        self.assertEqual(self.summary(out)["manifest_failed"], 1)

        code, _, stderr = run_main(argv + ["--resume"])
        self.assertEqual(code, 0, stderr)
        rows = {r["case_id"]: r for r in self.manifest_rows(out)}
        self.assertEqual(rows["G0000002"]["status"], "OK")
        self.assertEqual(self.summary(out)["manifest_failed"], 0)

    def test_interrupt_flushes_manifest_and_resume_skips_completed(self):
        counter = {"n": 0}

        def interrupt_on_third(params, template):
            counter["n"] += 1
            if counter["n"] == 3:
                raise KeyboardInterrupt
            return "STUB GEOMTURBO\n"

        first = self._install_stub(interrupt_on_third)
        out = self.root / "gen"
        argv = ["--group", "test", "--N", "5", "--seed", "101",
                "--output-dir", str(out)]
        code, _, stderr = run_main(argv)
        self.assertEqual(code, 130)
        self.assertIn("interrupted after 2/5", stderr)
        self.assertEqual(len(first), 3)

        batch_manifest = out / "batch_000001" / prod.MANIFEST_NAME
        self.assertTrue(batch_manifest.is_file())
        with open(batch_manifest, newline="", encoding="utf-8") as f:
            batch_rows = list(csv.DictReader(f))
        self.assertEqual([r["case_id"] for r in batch_rows],
                         ["G0000001", "G0000002"])
        self.assertEqual(len(self.manifest_rows(out)), 2)
        self.assertEqual(len(list(out.glob("batch_*/G*.geomTurbo"))), 2)

        second = self._install_stub()
        code, _, stderr = run_main(argv + ["--resume"])
        self.assertEqual(code, 0, stderr)
        self.assertEqual(len(second), 3, "only cases 3-5 may be regenerated")
        rows = self.manifest_rows(out)
        self.assertEqual([r["case_id"] for r in rows],
                         [f"G{i:07d}" for i in range(1, 6)])
        self.assertEqual(len({r["case_id"] for r in rows}), 5)
        self.assertEqual(self.summary(out)["manifest_ok"], 5)


class TestRealExport(Base):
    def test_real_single_case(self):
        out = self.root / "real"
        code, _stdout, stderr = run_main(
            ["--group", "train", "--N", "1", "--seed", "101",
             "--output-dir", str(out)])
        self.assertEqual(code, 0, stderr)
        path = out / "batch_000001" / "G0000001.geomTurbo"
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("GEOMETRY TURBO"))
        self.assertGreater(path.stat().st_size, 1000)
        rows = self.manifest_rows(out)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "OK")
        self.assertEqual(rows[0]["case_id"], "G0000001")
        self.assertTrue((out / runner.GROUP_INFO_NAME).is_file())


if __name__ == "__main__":
    unittest.main()

