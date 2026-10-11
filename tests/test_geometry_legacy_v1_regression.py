"""Exact legacy-geometry regression test for code/geometry_legacy_v1.py.

Standard library ``unittest`` only (no new dependencies).

Acceptance: for LG001..LG013, the pure implementation must reproduce the frozen
``legacy_geometry_v1`` fixtures **byte-for-byte** (13 profiles + 13 geomTurbo).
"""

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "code"))

import geometry_legacy_v1 as geo  # noqa: E402

MODULE_PATH = REPO / "code" / "geometry_legacy_v1.py"
FIXTURE = REPO / "tests" / "fixtures" / "legacy_geometry_v1"
CASES_CSV = FIXTURE / "cases.csv"
PROFILES = FIXTURE / "expected" / "profiles"
GEOMTURBO = FIXTURE / "expected" / "geomturbo"
TEMPLATE = REPO / "legacy" / "blade_batch_generation_template.geomTurbo"

GEOMETRY_PARAMS = ("Xthick", "Tmax", "Metal2", "Solidity")


class LegacyGeometryRegressionBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CASES_CSV, newline="") as f:
            cls.rows = list(csv.DictReader(f))
        cls.template_text = TEMPLATE.read_text()
        cls.by_id = {r["fixture_id"]: r for r in cls.rows}

    def generate(self, row):
        return geo.generate_geometry_texts(
            float(row["Xthick"]),
            float(row["Tmax"]),
            float(row["Metal2"]),
            float(row["Solidity"]),
            self.template_text,
        )

    def generated_profile_bytes(self, fid):
        profile_text, _ = self.generate(self.by_id[fid])
        return profile_text.encode()

    def generated_geomturbo_bytes(self, fid):
        _, geomturbo_text = self.generate(self.by_id[fid])
        return geomturbo_text.encode()

    def expected_profile_bytes(self, fid):
        return (PROFILES / f"{fid}.dat").read_bytes()

    def expected_geomturbo_bytes(self, fid):
        return (GEOMTURBO / f"{fid}.geomTurbo").read_bytes()

    def _locate(self, fid, got, want, kind):
        n = min(len(got), len(want))
        pos = next((i for i in range(n) if got[i] != want[i]), n)
        if len(got) != len(want) and pos == n:
            detail = f"length differs: got {len(got)} bytes, want {len(want)} bytes"
        else:
            detail = (f"first differing byte at offset {pos}: "
                      f"got {got[pos:pos + 24]!r} want {want[pos:pos + 24]!r}")
        approx_line = got[:pos].count(b"\n") + 1
        return f"{fid} {kind} mismatch ({detail}); approx line {approx_line}"


class TestExactRegression(LegacyGeometryRegressionBase):
    def test_13_of_13_exact_profiles(self):
        ok = 0
        first_mismatch = None
        for row in self.rows:
            fid = row["fixture_id"]
            got = self.generated_profile_bytes(fid)
            want = self.expected_profile_bytes(fid)
            if got == want:
                ok += 1
            elif first_mismatch is None:
                first_mismatch = self._locate(fid, got, want, "profile")
        if first_mismatch is not None:
            self.fail(first_mismatch)
        self.assertEqual(ok, 13)

    def test_13_of_13_exact_geomturbo(self):
        ok = 0
        first_mismatch = None
        for row in self.rows:
            fid = row["fixture_id"]
            got = self.generated_geomturbo_bytes(fid)
            want = self.expected_geomturbo_bytes(fid)
            if got == want:
                ok += 1
            elif first_mismatch is None:
                first_mismatch = self._locate(fid, got, want, "geomTurbo")
        if first_mismatch is not None:
            self.fail(first_mismatch)
        self.assertEqual(ok, 13)

    def test_26_of_26_exact_total(self):
        exact = 0
        for row in self.rows:
            fid = row["fixture_id"]
            if self.generated_profile_bytes(fid) == self.expected_profile_bytes(fid):
                exact += 1
            if self.generated_geomturbo_bytes(fid) == self.expected_geomturbo_bytes(fid):
                exact += 1
        self.assertEqual(exact, 26, f"expected 26/26 exact, got {exact}/26")


class TestOperatingConditionInvariance(LegacyGeometryRegressionBase):
    def test_fixture_rows_differ_only_in_operating_conditions(self):
        base = self.by_id["LG001"]
        for fid in ("LG012", "LG013"):
            row = self.by_id[fid]
            for p in GEOMETRY_PARAMS:
                self.assertEqual(float(row[p]), float(base[p]),
                                 f"{fid} {p} should equal LG001")
            self.assertNotEqual((row["Incidence"], row["Mach"]),
                                (base["Incidence"], base["Mach"]),
                                f"{fid} should differ from LG001 in Incidence/Mach")

    def test_generated_geometry_identical_for_operating_conditions(self):
        for fid in ("LG012", "LG013"):
            self.assertEqual(self.generated_profile_bytes(fid),
                             self.generated_profile_bytes("LG001"),
                             f"{fid} profile should match LG001")
            self.assertEqual(self.generated_geomturbo_bytes(fid),
                             self.generated_geomturbo_bytes("LG001"),
                             f"{fid} geomTurbo should match LG001")

    def test_core_api_does_not_accept_operating_conditions(self):
        import inspect
        params = set(inspect.signature(geo.generate_geometry_texts).parameters)
        self.assertNotIn("Incidence", params)
        self.assertNotIn("Mach", params)
        self.assertNotIn("case_id", params)


class TestSolidityContract(LegacyGeometryRegressionBase):
    def test_profile_invariant_under_solidity_change(self):
        for fid in ("LG008", "LG009"):
            self.assertEqual(self.generated_profile_bytes(fid),
                             self.generated_profile_bytes("LG001"),
                             f"{fid} profile should match LG001")

    def test_geomturbo_changes_with_solidity(self):
        g1 = self.generated_geomturbo_bytes("LG001")
        g8 = self.generated_geomturbo_bytes("LG008")
        g9 = self.generated_geomturbo_bytes("LG009")
        self.assertNotEqual(g1, g8)
        self.assertNotEqual(g1, g9)
        self.assertNotEqual(g8, g9)

    def test_periodicity_values(self):
        for fid, want in (("LG008", 0.06 / 1.0), ("LG001", 0.06 / 1.5),
                          ("LG009", 0.06 / 2.0)):
            text = self.generated_geomturbo_bytes(fid).decode()
            line = next(ln for ln in text.splitlines()
                        if ln.split() and ln.split()[0] == "PERIODICITY")
            self.assertAlmostEqual(float(line.split()[1]), want, places=6,
                                   msg=f"{fid} PERIODICITY")


class TestPurityBoundary(unittest.TestCase):
    def test_api_calls_create_no_files(self):
        template_text = TEMPLATE.read_text()
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                geo.generate_profile_text(0.30, 0.055, 15.0)
                prof, geom = geo.generate_geometry_texts(
                    0.30, 0.055, 15.0, 1.5, template_text)
                self.assertIsInstance(prof, str)
                self.assertIsInstance(geom, str)
                self.assertEqual(os.listdir(tmp), [],
                                 "pure API must not create any file")
            finally:
                os.chdir(cwd)

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            geo.generate_profile_text(float("nan"), 0.055, 15.0)
        with self.assertRaises(ValueError):
            geo.generate_profile_text(1.5, 0.055, 15.0)   # Xthick must be < 1
        with self.assertRaises(ValueError):
            geo.generate_profile_text(0.0, 0.055, 15.0)   # Xthick must be > 0
        with self.assertRaises(ValueError):
            geo.generate_geomturbo_text("0 0 0 0\n", 0.0, TEMPLATE.read_text())

    def test_module_has_no_visualization_or_cli_dependencies(self):
        src = MODULE_PATH.read_text()
        for banned in ("matplotlib", "pyplot", "plt.show", "argparse",
                       "tkinter", "pandas", "cv2"):
            self.assertNotIn(banned, src,
                             f"module must not reference {banned!r}")
        self.assertNotIn("open(", src, "module must not open files")


if __name__ == "__main__":
    unittest.main()
