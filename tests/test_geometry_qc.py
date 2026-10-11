"""Tests for code/03_geometry_qc.py (Geometry QC v1).

Standard-library unittest only. Frozen fixtures are read-only; all mutations are
applied to temporary copies under a tempdir.
"""

import contextlib
import csv
import importlib.util
import io
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "code" / "03_geometry_qc.py"
FIX = REPO / "tests" / "fixtures" / "legacy_geometry_v1"
LG_IDS = [f"LG{i:03d}" for i in range(1, 14)]

HEADER = ["case_id", "Xthick", "Tmax", "Metal2", "Solidity", "Incidence", "Mach",
          "range_id", "sampling_id"]


def load_module():
    spec = importlib.util.spec_from_file_location("qc_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


QC = load_module()


def parse_jsonl(stdout):
    return [json.loads(ln) for ln in stdout.splitlines() if ln.strip()]


def case_objs(stdout):
    return [o for o in parse_jsonl(stdout) if o.get("type") == "case"]


def summary_obj(stdout):
    objs = parse_jsonl(stdout)
    assert objs and objs[-1]["type"] == "summary"
    return objs[-1]


def read_report(path):
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def run_qc(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *[str(a) for a in args]],
        capture_output=True, text=True, cwd=str(REPO))


def polyline_blocks(text):
    """Order: suction s1, suction s2, pressure s1, pressure s2."""
    lines = text.splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("XYZ"):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            n = int(lines[j].strip())
            blocks.append({"xyz": i, "count": j, "start": j + 1, "n": n})
            i = j + 1 + n
        else:
            i += 1
    return blocks, lines


def replace_count(text, block_index, new_count):
    blocks, lines = polyline_blocks(text)
    lines[blocks[block_index]["count"]] = str(new_count)
    return "\n".join(lines) + "\n"


def rewrite_block_span(text, block_index, new_span):
    blocks, lines = polyline_blocks(text)
    blk = blocks[block_index]
    for k in range(blk["start"], blk["start"] + blk["n"]):
        parts = lines[k].split()
        lines[k] = f"{new_span:.6g}   {parts[1]}   {parts[2]}"
    return "\n".join(lines) + "\n"


def mutate_block_point(text, block_index, point_index, y, z):
    blocks, lines = polyline_blocks(text)
    blk = blocks[block_index]
    k = blk["start"] + point_index
    parts = lines[k].split()
    lines[k] = f"{parts[0]}   {y:.7f}   {z:.7f}"
    return "\n".join(lines) + "\n"


class QcBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.geo = self.tmp / "geo"
        (self.geo / "profiles").mkdir(parents=True)
        (self.geo / "geomturbo").mkdir(parents=True)
        self.design = self.tmp / "design.csv"
        self.report = self.tmp / "qc.csv"
        with open(FIX / "cases.csv", newline="") as handle:
            self.records = list(csv.DictReader(handle))
        self.by_id = {r["fixture_id"]: r for r in self.records}

    def tearDown(self):
        self._tmp.cleanup()

    # --- fixture installation -------------------------------------------
    def install(self, case_id, fixture_id, profile_transform=None,
                geom_transform=None):
        profile = (FIX / "expected" / "profiles" / f"{fixture_id}.dat").read_text()
        geom = (FIX / "expected" / "geomturbo" / f"{fixture_id}.geomTurbo").read_text()
        if profile_transform is not None:
            profile = profile_transform(profile)
        if geom_transform is not None:
            geom = geom_transform(geom)
        profile_path = self.geo / "profiles" / f"{case_id}.dat"
        geom_path = self.geo / "geomturbo" / f"{case_id}.geomTurbo"
        profile_path.write_text(profile)
        geom_path.write_text(geom)
        return profile_path, geom_path

    def install_all(self):
        mapping = []
        for index, fid in enumerate(LG_IDS, start=1):
            cid = f"C{index:06d}"
            self.install(cid, fid)
            mapping.append((cid, fid))
        return mapping

    # --- design CSV ------------------------------------------------------
    def row_for(self, case_id, fixture_id, **override):
        rec = self.by_id[fixture_id]
        values = {
            "case_id": case_id, "Xthick": rec["Xthick"], "Tmax": rec["Tmax"],
            "Metal2": rec["Metal2"], "Solidity": rec["Solidity"],
            "Incidence": rec["Incidence"], "Mach": rec["Mach"],
            "range_id": "legacy", "sampling_id": "s1",
        }
        values.update(override)
        return [values[c] for c in HEADER]

    def write_design(self, rows, path=None):
        path = Path(path or self.design)
        with open(path, "w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADER)
            writer.writerows(rows)
        return path

    # --- execution -------------------------------------------------------
    def qc(self, *extra, output=None, design=None):
        return run_qc("--input", design or self.design,
                      "--geometry", self.geo,
                      "--output", output or self.report, *extra)

    def invoke(self, argv):
        """In-process run (for mock-based tests); returns (rc, stdout)."""
        args = QC.build_parser().parse_args(argv)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = QC.run(args)
        except QC.CliError as exc:
            print(f"error: {exc}", file=sys.stderr)
            rc = QC.EXIT_CLI
        except Exception as exc:  # mirrors main()'s operational failure path
            print(f"error: {exc}", file=sys.stderr)
            rc = QC.EXIT_OPERATIONAL
        return rc, buf.getvalue()


class TestValidBaseline(QcBase):
    def test_13_case_valid_regression(self):
        mapping = self.install_all()
        self.write_design([self.row_for(cid, fid) for cid, fid in mapping])
        proc = self.qc()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        summary = summary_obj(proc.stdout)
        self.assertEqual(summary["selected_count"], 13)
        self.assertEqual(summary["pass_count"], 13)
        self.assertEqual(summary["fail_count"], 0)
        self.assertEqual(summary["missing_artifact_count"], 0)
        self.assertEqual(summary["parse_failure_count"], 0)
        self.assertEqual(summary["self_intersection_count"], 0)
        self.assertEqual(summary["adjacent_intersection_count"], 0)
        self.assertEqual(summary["qc_policy_id"], "geometry_qc_v1_hard")
        self.assertEqual(summary["calibration_status"], "UNCALIBRATED")
        self.assertEqual(len(case_objs(proc.stdout)), 13)

        rows = read_report(self.report)
        self.assertEqual(len(rows), 13)
        for row in rows:
            self.assertEqual(row["geometry_ok"], "1")
            self.assertEqual(row["reason"], "OK")
            self.assertEqual(row["profile_point_count"], "109")
            self.assertEqual(row["self_intersection"], "0")
            self.assertEqual(row["le_closure_error"], "0")
            self.assertEqual(row["te_closure_error"], "0")
            self.assertEqual(row["qc_policy_id"], "geometry_qc_v1_hard")
            self.assertEqual(row["calibration_status"], "UNCALIBRATED")
            self.assertGreater(float(row["min_gap"]), 0.0)
            for column in ("min_gap", "chord", "periodicity",
                           "pressure_max_turn_angle_deg",
                           "suction_max_turn_angle_deg",
                           "pressure_max_discrete_curvature",
                           "suction_max_discrete_curvature"):
                self.assertTrue(math.isfinite(float(row[column])), column)

    def test_min_gap_baseline_characterization(self):
        """Characterization only (NOT a validity threshold)."""
        mapping = self.install_all()
        self.write_design([self.row_for(cid, fid) for cid, fid in mapping])
        self.assertEqual(self.qc().returncode, 0)
        gaps = [float(r["min_gap"]) for r in read_report(self.report)]
        self.assertGreaterEqual(min(gaps), 0.019361)
        self.assertLessEqual(max(gaps), 0.047919)

    def test_summary_jsonl_contract(self):
        mapping = self.install_all()
        self.write_design([self.row_for(cid, fid) for cid, fid in mapping])
        proc = self.qc("--dry-run")
        self.assertEqual(proc.returncode, 0)
        objs = parse_jsonl(proc.stdout)
        self.assertEqual(objs[-1]["type"], "summary")
        for key in ("selected_count", "pass_count", "fail_count",
                    "missing_artifact_count", "parse_failure_count",
                    "self_intersection_count", "adjacent_intersection_count",
                    "output_path", "dry_run", "qc_policy_id",
                    "calibration_status"):
            self.assertIn(key, objs[-1])
        self.assertEqual(len(case_objs(proc.stdout)), 13)
        for obj in case_objs(proc.stdout):
            self.assertEqual(obj["type"], "case")
            self.assertIn("geometry_ok", obj)
            self.assertIn("reason", obj)


class TestCanonicalPolygon(unittest.TestCase):
    def test_canonical_polygon_is_216_vertices(self):
        rows = [[float(x) for x in ln.split()]
                for ln in (FIX / "expected" / "profiles" / "LG001.dat")
                .read_text().splitlines() if ln.strip()]
        pressure = [(r[0], r[1]) for r in rows]
        suction = [(r[2], r[3]) for r in rows]
        self.assertEqual(len(pressure), 109)
        self.assertEqual(len(suction), 109)
        self.assertEqual(len(pressure + suction[::-1]), 218)
        poly = QC.canonical_polygon(pressure, suction)
        self.assertEqual(len(poly), 216)
        n = len(poly)
        self.assertTrue(all(poly[i] != poly[(i + 1) % n] for i in range(n)))
        self.assertFalse(QC.polygon_self_intersection(poly))


class TestTangentialAxis(QcBase):
    def test_min_gap_uses_y_axis(self):
        self.install("C000001", "LG001")
        rec = self.by_id["LG001"]
        record = {"case_id": "C000001"}
        record.update({k: rec[k] for k in
                       ("Xthick", "Tmax", "Metal2", "Solidity",
                        "Incidence", "Mach")})
        profile_path = self.geo / "profiles" / "C000001.dat"
        geom_path = self.geo / "geomturbo" / "C000001.geomTurbo"
        row = QC.evaluate_case(record, profile_path, geom_path)
        self.assertIsNotNone(row["min_gap"])

        parsed = QC.parse_geomturbo(geom_path.read_text())
        per = parsed["periodicity"]
        p1 = parsed["sections"]["pressure"][0]
        s1 = parsed["sections"]["suction"][0]
        poly = QC.canonical_polygon([(r[1], r[2]) for r in p1],
                                    [(r[1], r[2]) for r in s1])

        y_gap = min(
            QC.polygon_pair_min_distance(poly, [(y + per, z) for (y, z) in poly]),
            QC.polygon_pair_min_distance(poly, [(y - per, z) for (y, z) in poly]))
        z_gap = min(
            QC.polygon_pair_min_distance(poly, [(y, z + per) for (y, z) in poly]),
            QC.polygon_pair_min_distance(poly, [(y, z - per) for (y, z) in poly]))

        self.assertAlmostEqual(row["min_gap"], y_gap, places=12)
        self.assertNotAlmostEqual(row["min_gap"], z_gap, places=6)
        self.assertGreater(row["min_gap"], 0.0)


# ---------------------------------------------------------------------------
# Fault injection
# ---------------------------------------------------------------------------
def profile_set_row(text, index, tokens):
    lines = text.splitlines()
    lines[index] = " ".join(tokens)
    return "\n".join(lines) + "\n"


def profile_dup_row(text, index):
    lines = text.splitlines()
    lines.insert(index + 1, lines[index])
    return "\n".join(lines) + "\n"


def profile_bowtie(_ignored=None):
    rows = [(0.0, 0.0, 0.0, 0.0), (3.0, 1.0, 1.0, 1.0), (4.0, 0.0, 4.0, 0.0)]
    return "".join(" ".join(f"{v:.4f}" for v in r) + "\n" for r in rows)


def geom_drop_periodicity(text):
    lines = [ln for ln in text.splitlines() if ln.split()[:1] != ["PERIODICITY"]]
    return "\n".join(lines) + "\n"


def geom_set_periodicity(text, value):
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.split()[:1] == ["PERIODICITY"]:
            lines[i] = f"  PERIODICITY\t\t\t{value:.5f}"
    return "\n".join(lines) + "\n"


def geom_break_xyz(text, block_index):
    blocks, lines = polyline_blocks(text)
    lines[blocks[block_index]["xyz"]] = "#  polyline"
    return "\n".join(lines) + "\n"


class FaultBase(QcBase):
    def one_case(self, case_id="C000001", fixture_id="LG001", **install_kw):
        self.install(case_id, fixture_id, **install_kw)
        self.write_design([self.row_for(case_id, fixture_id)])
        if self.report.exists():
            self.report.unlink()
        proc = self.qc()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        rows = read_report(self.report)
        self.assertEqual(len(rows), 1)
        return rows[0], proc


class TestHardGates(FaultBase):
    def test_Q01_profile_missing(self):
        self.install("C000001", "LG001")
        (self.geo / "profiles" / "C000001.dat").unlink()
        self.write_design([self.row_for("C000001", "LG001")])
        proc = self.qc()
        self.assertEqual(proc.returncode, 0)
        row = read_report(self.report)[0]
        self.assertEqual(row["geometry_ok"], "0")
        self.assertIn("PROFILE_MISSING", row["reason"])

    def test_Q02_geomturbo_missing(self):
        self.install("C000001", "LG001")
        (self.geo / "geomturbo" / "C000001.geomTurbo").unlink()
        self.write_design([self.row_for("C000001", "LG001")])
        self.assertEqual(self.qc().returncode, 0)
        row = read_report(self.report)[0]
        self.assertEqual(row["geometry_ok"], "0")
        self.assertIn("GEOMTURBO_MISSING", row["reason"])

    def test_Q03_profile_wrong_column_count(self):
        row, _ = self.one_case(
            profile_transform=lambda t: profile_set_row(t, 10, ["0.1", "0.2", "0.3"]))
        self.assertEqual(row["geometry_ok"], "0")
        self.assertIn("PROFILE_PARSE_ERROR", row["reason"])

    def test_Q04_profile_nan(self):
        row, _ = self.one_case(
            profile_transform=lambda t: profile_set_row(
                t, 10, ["nan", "0.2", "0.3", "0.4"]))
        self.assertEqual(row["geometry_ok"], "0")
        self.assertIn("NONFINITE_COORDINATE", row["reason"])

    def test_Q05_profile_inf(self):
        row, _ = self.one_case(
            profile_transform=lambda t: profile_set_row(
                t, 10, ["inf", "0.2", "0.3", "0.4"]))
        self.assertEqual(row["geometry_ok"], "0")
        self.assertIn("NONFINITE_COORDINATE", row["reason"])

    def test_Q06_invalid_solidity_is_cli_error(self):
        self.install("C000001", "LG001")
        self.write_design([self.row_for("C000001", "LG001", Solidity="0")])
        proc = self.qc()
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(self.report.exists())

    def test_Q07_nonpositive_interior_thickness(self):
        def transform(text):
            lines = text.splitlines()
            parts = lines[50].split()
            lines[50] = f"{parts[0]} {parts[1]} {parts[0]} {parts[1]}"
            return "\n".join(lines) + "\n"
        row, _ = self.one_case(profile_transform=transform)
        self.assertEqual(row["geometry_ok"], "0")
        self.assertIn("NONPOSITIVE_INTERIOR_THICKNESS", row["reason"])

    def test_Q08_le_closure_mismatch(self):
        def transform(text):
            lines = text.splitlines()
            p = lines[0].split()
            lines[0] = f"{p[0]} {p[1]} {float(p[2]) + 0.001:.4f} {p[3]}"
            return "\n".join(lines) + "\n"
        row, _ = self.one_case(profile_transform=transform)
        self.assertEqual(row["geometry_ok"], "0")
        self.assertIn("LE_TE_CLOSURE_MISMATCH", row["reason"])

    def test_Q09_te_closure_mismatch(self):
        def transform(text):
            lines = text.splitlines()
            p = lines[-1].split()
            lines[-1] = f"{p[0]} {p[1]} {float(p[2]) + 0.001:.4f} {p[3]}"
            return "\n".join(lines) + "\n"
        row, _ = self.one_case(profile_transform=transform)
        self.assertEqual(row["geometry_ok"], "0")
        self.assertIn("LE_TE_CLOSURE_MISMATCH", row["reason"])

    def test_Q10_self_intersecting_bowtie(self):
        row, _ = self.one_case(profile_transform=profile_bowtie)
        self.assertEqual(row["geometry_ok"], "0")
        self.assertIn("SELF_INTERSECTION", row["reason"])

    def test_Q11_missing_periodicity(self):
        row, _ = self.one_case(geom_transform=geom_drop_periodicity)
        self.assertEqual(row["geometry_ok"], "0")
        self.assertIn("INVALID_PERIODICITY", row["reason"])

    def test_Q12_nonpositive_periodicity(self):
        for value in (0.0, -0.01):
            with self.subTest(value=value):
                row, _ = self.one_case(
                    geom_transform=lambda t, v=value: geom_set_periodicity(t, v))
                self.assertEqual(row["geometry_ok"], "0")
                self.assertIn("INVALID_PERIODICITY", row["reason"])

    def test_Q13_declared_point_count_mismatch(self):
        row, _ = self.one_case(
            geom_transform=lambda t: replace_count(t, 0, 250))
        self.assertEqual(row["geometry_ok"], "0")
        self.assertNotEqual(row["reason"], "OK")

    def test_Q14_missing_section(self):
        row, _ = self.one_case(
            geom_transform=lambda t: geom_break_xyz(t, 0))
        self.assertEqual(row["geometry_ok"], "0")
        self.assertIn("GEOMTURBO_INCOMPLETE", row["reason"])

    def test_Q15_section_span_mismatch(self):
        row, _ = self.one_case(
            geom_transform=lambda t: rewrite_block_span(t, 1, 0.001))
        self.assertEqual(row["geometry_ok"], "0")
        self.assertIn("SPAN_SECTION_MISMATCH", row["reason"])
        self.assertEqual(row["span_section_coordinate_consistent"], "0")

    def test_Q16_section_yz_mismatch(self):
        row, _ = self.one_case(
            geom_transform=lambda t: mutate_block_point(t, 1, 3, 0.77, 0.77))
        self.assertEqual(row["geometry_ok"], "0")
        self.assertIn("SPAN_SECTION_MISMATCH", row["reason"])

    def test_Q17_adjacent_blade_intersection(self):
        row, _ = self.one_case(
            geom_transform=lambda t: geom_set_periodicity(t, 0.001))
        self.assertEqual(row["geometry_ok"], "0")
        self.assertIn("ADJACENT_BLADE_INTERSECTION", row["reason"])
        self.assertEqual(row["adjacent_blade_intersection"], "1")

    def test_Q18_nonpositive_min_gap(self):
        row, _ = self.one_case(
            geom_transform=lambda t: geom_set_periodicity(t, 0.001))
        self.assertEqual(row["geometry_ok"], "0")
        self.assertIn("NONPOSITIVE_MIN_GAP", row["reason"])
        self.assertLessEqual(float(row["min_gap"]), 0.0)

    def test_Q19_zero_length_internal_segment(self):
        row, _ = self.one_case(
            profile_transform=lambda t: profile_dup_row(t, 50))
        self.assertEqual(row["geometry_ok"], "0")
        self.assertIn("ZERO_LENGTH_SEGMENT", row["reason"])


def temp_leftovers(directory):
    return [p.name for p in Path(directory).iterdir() if ".part" in p.name]


class TestCliAndReportSemantics(FaultBase):
    def test_Q20_dry_run_writes_nothing(self):
        self.install("C000001", "LG001")
        self.write_design([self.row_for("C000001", "LG001")])
        geometry_before = sorted(p.name for p in (self.geo / "profiles").iterdir())
        proc = self.qc("--dry-run")
        self.assertEqual(proc.returncode, 0)
        self.assertFalse(self.report.exists())
        self.assertEqual(sorted(p.name for p in (self.geo / "profiles").iterdir()),
                         geometry_before)
        self.assertEqual(temp_leftovers(self.tmp), [])
        self.assertTrue(summary_obj(proc.stdout)["dry_run"])

    def test_Q21_existing_output_requires_overwrite(self):
        self.install("C000001", "LG001")
        self.write_design([self.row_for("C000001", "LG001")])
        self.assertEqual(self.qc().returncode, 0)
        before = self.report.read_bytes()
        proc = self.qc()
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(self.report.read_bytes(), before)

    def test_Q22_overwrite_atomic_success(self):
        self.install("C000001", "LG001")
        self.write_design([self.row_for("C000001", "LG001")])
        self.assertEqual(self.qc().returncode, 0)
        proc = self.qc("--overwrite")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(len(read_report(self.report)), 1)
        self.assertEqual(temp_leftovers(self.tmp), [])

    def test_Q23_report_replace_failure_exit_4(self):
        self.install("C000001", "LG001")
        self.write_design([self.row_for("C000001", "LG001")])
        self.assertEqual(self.qc().returncode, 0)
        before = self.report.read_bytes()
        with mock.patch("os.replace", side_effect=OSError("injected replace")):
            rc, _ = self.invoke(["--input", str(self.design),
                                 "--geometry", str(self.geo),
                                 "--output", str(self.report), "--overwrite"])
        self.assertEqual(rc, 4)
        self.assertEqual(self.report.read_bytes(), before)
        self.assertEqual(temp_leftovers(self.tmp), [])

    def test_Q24_subset_preserves_csv_order(self):
        self.install("C000001", "LG001")
        self.install("C000002", "LG002")
        self.install("C000003", "LG003")
        self.write_design([self.row_for(f"C{i:06d}", f"LG{i:03d}")
                           for i in (1, 2, 3)])
        proc = self.qc("--case-id", "C000003", "--case-id", "C000001", "--dry-run")
        self.assertEqual(proc.returncode, 0)
        ids = [o["case_id"] for o in case_objs(proc.stdout)]
        self.assertEqual(ids, ["C000001", "C000003"])

    def test_Q24b_missing_case_id_is_cli_error(self):
        self.install("C000001", "LG001")
        self.write_design([self.row_for("C000001", "LG001")])
        proc = self.qc("--case-id", "C999999")
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(self.report.exists())

    def test_Q25_one_bad_one_good_still_reports_both(self):
        self.install("C000001", "LG001")
        self.install("C000002", "LG002", geom_transform=geom_drop_periodicity)
        self.write_design([self.row_for("C000001", "LG001"),
                           self.row_for("C000002", "LG002")])
        proc = self.qc()
        self.assertEqual(proc.returncode, 0, "bad geometry is not a process failure")
        summary = summary_obj(proc.stdout)
        self.assertEqual(summary["selected_count"], 2)
        self.assertEqual(summary["pass_count"], 1)
        self.assertEqual(summary["fail_count"], 1)
        rows = read_report(self.report)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["geometry_ok"], "1")
        self.assertEqual(rows[1]["geometry_ok"], "0")


if __name__ == "__main__":
    unittest.main()
