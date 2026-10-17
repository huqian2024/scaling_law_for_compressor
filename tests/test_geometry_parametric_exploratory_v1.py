"""Regression tests for ``code/geometry_parametric_exploratory_v1.py``.

Acceptance:
    1. the nine exploratory parameters restored to their legacy defaults must
       reproduce the frozen V1 fixtures byte-for-byte (13 profiles + 13
       .geomTurbo files);
    2. the module must agree byte-for-byte with ``code/geometry_legacy_v1.py``
       for arbitrary legacy-parameter cases;
    3. Solidity must not change blade coordinates (pitch-only parameter);
    4. each of the nine exposed parameters must change the blade geometry;
    5. mathematical preconditions must raise.

Standard library ``unittest`` + NumPy only.
"""

import csv
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "code"))

import geometry_legacy_v1 as legacy  # noqa: E402
import geometry_parametric_exploratory_v1 as geo  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "legacy_geometry_v1"
CASES_CSV = FIXTURE / "cases.csv"
PROFILES = FIXTURE / "expected" / "profiles"
GEOMTURBO = FIXTURE / "expected" / "geomturbo"
TEMPLATE = (REPO / "legacy" / "blade_batch_generation_template.geomTurbo").read_text()

NINE_LEGACY_DEFAULTS = {
    "Metal1": 53.0, "T1": 0.015, "T2": 0.0125, "Xmean": 0.08, "K_m": 0.18,
    "Ks1": 5.0, "Ks2": 0.10, "SS1": 3.2, "SS2": 0.8,
}


class TestLegacyDefaultCompatibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CASES_CSV, newline="") as f:
            cls.rows = list(csv.DictReader(f))

    def test_fixture_bytes_identical(self):
        self.assertEqual(len(self.rows), 13)
        for row in self.rows:
            fid = row["fixture_id"]
            params = {
                "Xthick": float(row["Xthick"]),
                "Tmax": float(row["Tmax"]),
                "Metal2": float(row["Metal2"]),
                "Solidity": float(row["Solidity"]),
                **NINE_LEGACY_DEFAULTS,
            }
            profile, geomturbo = geo.generate_geometry_texts(
                params, template_text=TEMPLATE)
            self.assertEqual(
                profile.encode(), (PROFILES / f"{fid}.dat").read_bytes(),
                f"profile mismatch for {fid}")
            self.assertEqual(
                geomturbo.encode(), (GEOMTURBO / f"{fid}.geomTurbo").read_bytes(),
                f"geomTurbo mismatch for {fid}")

    def test_agrees_with_frozen_module(self):
        for Xthick, Tmax, Metal2, Solidity in (
                (0.155, 0.041, 6.5, 1.05),
                (0.30, 0.055, 15.0, 1.5),
                (0.445, 0.069, 23.5, 1.95)):
            params = {"Xthick": Xthick, "Tmax": Tmax, "Metal2": Metal2,
                      "Solidity": Solidity, **NINE_LEGACY_DEFAULTS}
            new_profile, new_geom = geo.generate_geometry_texts(
                params, template_text=TEMPLATE)
            old_profile, old_geom = legacy.generate_geometry_texts(
                Xthick, Tmax, Metal2, Solidity, TEMPLATE)
            self.assertEqual(new_profile, old_profile)
            self.assertEqual(new_geom, old_geom)


class TestParameterEffects(unittest.TestCase):
    def test_solidity_is_pitch_only(self):
        base = geo.compute_geometry(Solidity=1.5)
        other = geo.compute_geometry(Solidity=2.4)
        for key in ("xp1", "yp1", "xs1", "ys1", "xc", "yc", "thick"):
            self.assertTrue(
                (base[key] == other[key]).all(),
                f"Solidity unexpectedly changed {key}")

    def test_nine_parameters_change_geometry(self):
        base = geo.compute_geometry()
        for name in NINE_LEGACY_DEFAULTS:
            value = geo.LEGACY_DEFAULTS[name]
            if name == "Xmean":
                probe = {name: value + 0.01}
            elif name in ("Metal1", "Ks1"):
                probe = {name: value + 1.0}
            else:
                probe = {name: value * 1.10}
            changed = geo.compute_geometry(probe)
            delta = abs(changed["xp1"] - base["xp1"]).max() + \
                abs(changed["yp1"] - base["yp1"]).max() + \
                abs(changed["thick"] - base["thick"]).max()
            self.assertGreater(delta, 0.0, f"{name} produced identical geometry")

    def test_high_precision_endpoints_close(self):
        g = geo.compute_geometry()
        self.assertEqual(g["xp1"][0], g["xs1"][0])
        self.assertEqual(g["yp1"][0], g["ys1"][0])
        self.assertEqual(g["xp1"][-1], g["xs1"][-1])
        self.assertEqual(g["yp1"][-1], g["ys1"][-1])


class TestPreconditions(unittest.TestCase):
    def test_invalid_values_raise(self):
        for bad in ({"Xthick": 0.0}, {"Xthick": 1.0}, {"Xmean": 0.0},
                    {"Solidity": 0.0}, {"T1": 0.0}, {"T2": -0.001},
                    {"Tmax": float("nan")}):
            with self.assertRaises(geo.GeometryParameterError):
                geo.compute_geometry(bad)

    def test_unknown_parameter_raises(self):
        with self.assertRaises(geo.GeometryParameterError):
            geo.compute_geometry({"Incidence": 2.0})


if __name__ == "__main__":
    unittest.main()
