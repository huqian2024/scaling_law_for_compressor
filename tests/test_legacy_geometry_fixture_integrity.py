"""Integrity tests for the frozen `legacy_geometry_v1` regression baseline.

Standard-library ``unittest`` only (no new dependencies).

These tests verify the *frozen* baseline; they never regenerate or update it.
They also re-check the live legacy source hashes so that any drift of
``legacy/blade_batch_generation.py`` / the geomTurbo template / the ranges file
fails the tests instead of silently invalidating the baseline.

Run with::

    conda activate ai4s
    python -m unittest discover -s tests -p 'test_*.py' -v
"""

import csv
import hashlib
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "tests" / "fixtures" / "legacy_geometry_v1"
CASES_CSV = FIXTURE / "cases.csv"
SHA256SUMS = FIXTURE / "SHA256SUMS.txt"
METADATA = FIXTURE / "metadata.yaml"
PROFILES_DIR = FIXTURE / "expected" / "profiles"
GEOMTURBO_DIR = FIXTURE / "expected" / "geomturbo"

PARAMS = ["Xthick", "Tmax", "Metal2", "Solidity", "Incidence", "Mach"]
FIXTURE_IDS = [f"LG{i:03d}" for i in range(1, 14)]

EXPECTED_COMMIT = "ebbf7bd9a74ef2db1edd84f5c83ddec4e752c07f"
EXPECTED_LEGACY_SHA = {
    "legacy/blade_batch_generation.py":
        "48ed9ead4b1260790dcc2d3ad9fe05c79e745a82ad19fe2ce918268adfc36e03",
    "legacy/blade_batch_generation_template.geomTurbo":
        "92c4296f2de27440aebaad9b03b9af4f9e09756fabff2298f4607a87f2c55119",
    "config/ranges_legacy.yaml":
        "237ce3f4c1da022a57c7a82e8057248871ce673c96dcba6d0add5763dcc558ef",
}

PROFILE_COLUMNS = 4


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_cases():
    with open(CASES_CSV, newline="") as f:
        return list(csv.DictReader(f))


def profile_path(fid):
    return PROFILES_DIR / f"{fid}.dat"


def geomturbo_path(fid):
    return GEOMTURBO_DIR / f"{fid}.geomTurbo"


def parse_periodicity(path):
    """Return the PERIODICITY float written by the legacy script."""
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "PERIODICITY":
            return float(parts[1])
    raise AssertionError(f"no PERIODICITY line found in {path}")


class TestCaseSpecification(unittest.TestCase):
    """A. case specification."""

    @classmethod
    def setUpClass(cls):
        cls.cases = read_cases()

    def test_fixture_count_is_13(self):
        self.assertEqual(len(self.cases), 13)

    def test_fixture_ids_unique(self):
        ids = [c["fixture_id"] for c in self.cases]
        self.assertEqual(len(ids), len(set(ids)), "duplicate fixture_id")

    def test_fixture_ids_exactly_lg001_to_lg013(self):
        ids = [c["fixture_id"] for c in self.cases]
        self.assertEqual(ids, FIXTURE_IDS)

    def test_six_parameters_are_finite_floats(self):
        for c in self.cases:
            for name in PARAMS:
                self.assertIn(name, c, f"{c['fixture_id']} missing {name}")
                try:
                    v = float(c[name])
                except ValueError:
                    self.fail(f"{c['fixture_id']} {name}={c[name]!r} not a float")
                self.assertTrue(v == v and abs(v) != float("inf"),
                                f"{c['fixture_id']} {name} not finite")


class TestArtifactInventory(unittest.TestCase):
    """B. expected artifact inventory."""

    def test_profile_inventory_is_exact(self):
        found = sorted(p.stem for p in PROFILES_DIR.glob("*.dat"))
        self.assertEqual(found, FIXTURE_IDS)

    def test_geomturbo_inventory_is_exact(self):
        found = sorted(p.name[: -len(".geomTurbo")]
                       for p in GEOMTURBO_DIR.glob("*.geomTurbo"))
        self.assertEqual(found, FIXTURE_IDS)

    def test_no_extra_artifacts_in_expected_dirs(self):
        self.assertEqual(sorted(p.name for p in PROFILES_DIR.iterdir()),
                         [f"{fid}.dat" for fid in FIXTURE_IDS])
        self.assertEqual(sorted(p.name for p in GEOMTURBO_DIR.iterdir()),
                         [f"{fid}.geomTurbo" for fid in FIXTURE_IDS])


class TestSHA256Manifest(unittest.TestCase):
    """C. SHA256 manifest integrity."""

    @classmethod
    def setUpClass(cls):
        cls.entries = []
        for line in SHA256SUMS.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            digest, rel = line.split(None, 1)
            cls.entries.append((digest, rel.strip()))

    def test_manifest_has_28_entries(self):
        self.assertEqual(len(self.entries), 28)

    def test_manifest_does_not_reference_itself(self):
        for _, rel in self.entries:
            self.assertNotIn("SHA256SUMS", rel)

    def test_every_entry_matches_recomputed_hash(self):
        mismatches = []
        for digest, rel in self.entries:
            target = FIXTURE / rel
            self.assertTrue(target.exists(), f"manifest entry missing: {rel}")
            got = sha256_file(target)
            if got != digest:
                mismatches.append(f"{rel}: {got} != {digest}")
        self.assertEqual(mismatches, [], "hash mismatches:\n" + "\n".join(mismatches))

    def test_manifest_covers_all_frozen_artifacts(self):
        listed = {rel for _, rel in self.entries}
        expected = {"cases.csv", "metadata.yaml"}
        expected |= {f"expected/profiles/{fid}.dat" for fid in FIXTURE_IDS}
        expected |= {f"expected/geomturbo/{fid}.geomTurbo" for fid in FIXTURE_IDS}
        self.assertEqual(listed, expected)


class TestProvenance(unittest.TestCase):
    """D. provenance integrity."""

    @classmethod
    def setUpClass(cls):
        cls.meta = yaml.safe_load(METADATA.read_text())

    def test_fixture_version(self):
        self.assertEqual(self.meta["fixture_version"], "legacy_geometry_v1")

    def test_fixture_count(self):
        self.assertEqual(self.meta["fixture_count"], 13)

    def test_source_git_commit(self):
        self.assertEqual(self.meta["source"]["git_commit"], EXPECTED_COMMIT)

    def test_metadata_records_expected_legacy_hashes(self):
        src = self.meta["source"]
        self.assertEqual(src["legacy_script"]["sha256"],
                         EXPECTED_LEGACY_SHA["legacy/blade_batch_generation.py"])
        self.assertEqual(src["geomturbo_template"]["sha256"],
                         EXPECTED_LEGACY_SHA[
                             "legacy/blade_batch_generation_template.geomTurbo"])
        self.assertEqual(src["ranges"]["sha256"],
                         EXPECTED_LEGACY_SHA["config/ranges_legacy.yaml"])

    def test_live_legacy_sources_match_recorded_hashes(self):
        """Fail (do not auto-update) if the legacy source has drifted."""
        for rel, want in EXPECTED_LEGACY_SHA.items():
            got = sha256_file(REPO / rel)
            self.assertEqual(got, want,
                             f"legacy source drifted: {rel}\n got  {got}\n want {want}")

    def test_environment_recorded(self):
        env = self.meta["environment"]
        self.assertEqual(env["conda_env"], "ai4s")
        self.assertEqual(env["python"], "3.10.20")
        self.assertEqual(env["numpy"], "2.2.6")
        self.assertEqual(env["scipy"], "1.15.3")


class TestProfileNumericSanity(unittest.TestCase):
    """E. profile numeric sanity (fixture integrity only, not full Geometry QC)."""

    def test_profiles_non_empty_with_consistent_columns(self):
        for fid in FIXTURE_IDS:
            lines = profile_path(fid).read_text().splitlines()
            lines = [ln for ln in lines if ln.strip()]
            self.assertGreater(len(lines), 0, f"{fid} profile empty")
            for lineno, ln in enumerate(lines, 1):
                self.assertEqual(
                    len(ln.split()), PROFILE_COLUMNS,
                    f"{fid}:{lineno} expected {PROFILE_COLUMNS} columns, "
                    f"got {len(ln.split())}")

    def test_profiles_all_finite(self):
        bad = []
        for fid in FIXTURE_IDS:
            for lineno, ln in enumerate(
                    profile_path(fid).read_text().splitlines(), 1):
                if not ln.strip():
                    continue
                for tok in ln.split():
                    v = float(tok)
                    if v != v or v in (float("inf"), float("-inf")):
                        bad.append(f"{fid}:{lineno}:{tok}")
        self.assertEqual(bad, [], "non-finite values: " + ", ".join(bad[:10]))


class TestFrozenBehavioralContracts(unittest.TestCase):
    """F. frozen behavioral contracts of the legacy geometry baseline."""

    def assert_same_file(self, a, b, what):
        self.assertEqual(sha256_file(a), sha256_file(b),
                         f"{what}: {a.name} and {b.name} differ")

    def assert_different_file(self, a, b, what):
        self.assertNotEqual(sha256_file(a), sha256_file(b),
                            f"{what}: {a.name} and {b.name} unexpectedly equal")

    def test_operating_condition_independence_profiles(self):
        # LG001 / LG012 / LG013 share geometry params, differ only Incidence/Mach.
        for fid in ("LG012", "LG013"):
            self.assert_same_file(profile_path("LG001"), profile_path(fid),
                                  "operating-condition independence (profile)")

    def test_operating_condition_independence_geomturbo(self):
        for fid in ("LG012", "LG013"):
            self.assert_same_file(geomturbo_path("LG001"), geomturbo_path(fid),
                                  "operating-condition independence (geomTurbo)")

    def test_solidity_does_not_change_profile(self):
        # Solidity only affects geomTurbo PERIODICITY in the legacy algorithm.
        for fid in ("LG008", "LG009"):
            self.assert_same_file(profile_path("LG001"), profile_path(fid),
                                  "Solidity invariance (profile)")

    def test_solidity_changes_geomturbo(self):
        self.assert_different_file(geomturbo_path("LG001"), geomturbo_path("LG008"),
                                   "Solidity sensitivity (geomTurbo)")
        self.assert_different_file(geomturbo_path("LG001"), geomturbo_path("LG009"),
                                   "Solidity sensitivity (geomTurbo)")
        self.assert_different_file(geomturbo_path("LG008"), geomturbo_path("LG009"),
                                   "Solidity sensitivity (geomTurbo)")

    def test_periodicity_values_match_solidity(self):
        # periodicity = 0.06 / Solidity, frozen legacy behavior.
        expected = {"LG008": 0.06000, "LG001": 0.04000, "LG009": 0.03000}
        for fid, want in expected.items():
            got = parse_periodicity(geomturbo_path(fid))
            self.assertAlmostEqual(got, want, places=6,
                                   msg=f"{fid} PERIODICITY {got} != {want}")


if __name__ == "__main__":
    unittest.main()
