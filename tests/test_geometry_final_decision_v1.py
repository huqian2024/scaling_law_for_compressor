"""Unit tests for ``tools/geometry_final_decision_v1.py``.

The tool itself is an experiment driver; these tests cover the pure decision
logic that must not silently change:

    1. soft-risk indicators on known geometries;
    2. the case plan / historical-reuse bookkeeping;
    3. the Xmean bound rule, including the conservative branch when the result
       is not robust to the registered threshold sensitivity;
    4. the final parameter configuration and its dimensionality.

They do not run the full experiment, do not write into the analysis output
directory and do not touch any frozen asset.
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "code"))

import geometry_final_decision_v1 as fd  # noqa: E402
import geometry_parametric_exploratory_v1 as gen  # noqa: E402


class TestSoftRiskIndicators(unittest.TestCase):
    def test_baseline_has_no_reverse_lobe(self):
        g = gen.compute_geometry(gen.default_params())
        m = fd.soft_risk_metrics(g)
        self.assertEqual(m["reverse_curvature_ratio"], 0.0)
        self.assertLess(m["tangent_reversal_deg"], 0.1)
        self.assertGreater(m["kappa_max_norm"], 0.0)

    def test_high_xmean_high_ks1_has_reverse_lobe(self):
        p = dict(gen.default_params())
        p.update({"Xmean": 0.22, "Ks1": 7.0, "K_m": 0.10})
        m = fd.soft_risk_metrics(gen.compute_geometry(p))
        self.assertGreater(m["reverse_curvature_ratio"], 0.10)
        self.assertGreater(m["tangent_reversal_deg"], 1.0)
        self.assertLessEqual(m["reverse_curvature_ratio"], 1.0)

    def test_low_xmean_corner_also_has_a_lobe(self):
        """The legacy family already reverses at low Xmean: never a hard failure."""
        p = dict(gen.default_params())
        p.update({"Xmean": 0.06, "Ks1": 3.0, "K_m": 0.35})
        m = fd.soft_risk_metrics(gen.compute_geometry(p))
        self.assertGreater(m["reverse_curvature_ratio"], 0.10)

    def test_k_m_suppresses_the_lobe(self):
        low = dict(gen.default_params())
        low.update({"Xmean": 0.20, "Ks1": 7.0, "K_m": 0.10})
        high = dict(gen.default_params())
        high.update({"Xmean": 0.20, "Ks1": 7.0, "K_m": 0.35})
        r_low = fd.soft_risk_metrics(gen.compute_geometry(low))["reverse_curvature_ratio"]
        r_high = fd.soft_risk_metrics(gen.compute_geometry(high))["reverse_curvature_ratio"]
        self.assertGreater(r_low, r_high)


class TestCasePlan(unittest.TestCase):
    def setUp(self):
        self.plan = fd.build_case_plan()
        self.rows = fd.assign_case_ids(self.plan, {})

    def test_new_case_limit(self):
        """The design budget is <= 49 rows and <= 48 newly generated cases."""
        self.assertLessEqual(len(self.rows), 49)
        if all(p.is_file() for _, p in fd.HISTORICAL_FILES):
            index = fd.historical_index(fd.load_historical())
            rows = fd.assign_case_ids(self.plan, index)
            n_new = sum(1 for r in rows if r["reuse_status"] == "NEW")
            self.assertLessEqual(n_new, 48)
            self.assertGreaterEqual(len(rows) - n_new, 1)

    def test_ids_unique_and_references_resolve(self):
        ids = {r["case_id"] for r in self.rows}
        self.assertEqual(len(ids), len(self.rows))
        for r in self.rows:
            self.assertIn(r["reference_case_id"], ids)

    def test_no_duplicate_parameter_vectors(self):
        keys = [fd.vector_key(r["params"]) for r in self.rows]
        self.assertEqual(len(keys), len(set(keys)))

    def test_reuse_of_an_exact_historical_vector(self):
        probe = dict(fd.BASELINE)
        probe.update({"Xmean": 0.14, "Ks1": 5.0})
        index = fd.historical_index([{"case_id": "C820027", "experiment": "x",
                                      "params": probe}])
        rows = fd.assign_case_ids(self.plan, index)
        reused = [r for r in rows if r["reuse_status"] == "REUSED"]
        self.assertEqual([r["case_id"] for r in reused], ["C820027"])


class TestXmeanBoundRule(unittest.TestCase):
    @staticmethod
    def _crit(margins):
        return {
            "criteria_id": "test",
            "criteria_version": "1.0.0",
            "thresholds": {
                "soft_risk": {
                    "bound_rule_margin": 1.01,
                    "joint_constraint_margin": 0.85,
                    "tangent_reversal_margin": 1.25,
                    "splice_jump_margin": 1.25,
                },
                "substitution": {},
                "resolution": {},
                "statistics": {},
            },
            "threshold_sensitivity": {"parameters": {"bound_rule_margin": margins}},
            "decision_rules": {"ks1": [{"range": [3, 7]}, {"range": [3, 7]}],
                               "ks2": [{"range": [0.05, 0.2]},
                                       {"range": [0.05, 0.2]}]},
        }

    @staticmethod
    def _map():
        rows = []
        for bg in ("M0", "ML", "MS"):
            for xm in (0.06, 0.10, 0.14, 0.18, 0.20, 0.22):
                for ks1 in (3.0, 7.0):
                    for km in (0.10, 0.35):
                        rcr = 0.0
                        if xm >= 0.18 and ks1 >= 7.0 and km <= 0.10:
                            rcr = 0.20 + (xm - 0.18) * 1.5
                        if xm <= 0.06 and ks1 <= 3.0 and km >= 0.35:
                            rcr = 0.25
                        rows.append({"Xmean": xm, "Ks1": ks1, "K_m": km,
                                     "background_id": bg,
                                     "reverse_curvature_ratio": rcr,
                                     "tangent_reversal_deg": 1.0,
                                     "splice_curvature_jump_norm": 0.0})
        return rows

    @staticmethod
    def _env():
        return {"anchor_rcr": 0.25, "max_tangent_reversal_deg": 10.0,
                "max_splice_jump_norm": 0.0}

    def test_not_robust_falls_back_to_conservative_bound(self):
        out = fd.decide_xmean(self._map(), self._env(), self._crit([0.85, 1.00]))
        self.assertFalse(out["robust"])
        self.assertTrue(out["conservative_due_to_sensitivity"])
        self.assertLessEqual(out["adopted_bound"],
                             out["primary_adopted_bound"] + 1e-12)
        self.assertEqual(out["adopted_bound"], 0.18)

    def test_robust_keeps_the_primary_bound(self):
        out = fd.decide_xmean(self._map(), self._env(), self._crit([1.01]))
        self.assertTrue(out["robust"])
        self.assertFalse(out["conservative_due_to_sensitivity"])
        self.assertEqual(out["adopted_bound"], out["primary_adopted_bound"])

    def test_bound_never_below_current(self):
        out = fd.decide_xmean(self._map(), self._env(), self._crit([0.10]))
        self.assertGreaterEqual(out["adopted_bound"], 0.18)


class TestFinalConfiguration(unittest.TestCase):
    @staticmethod
    def _state(d1, d2, bound=0.18):
        return {
            "criteria": {"criteria_id": "t", "criteria_version": "1",
                         "decision_rules": {"ks1": [{"range": [3, 7]},
                                                    {"range": [3, 7]}],
                                            "ks2": [{"range": [0.05, 0.2]},
                                                    {"range": [0.05, 0.2]}]}},
            "decision_ks1": d1,
            "decision_ks2": d2,
            "xmean": {"adopted_bound": bound, "primary_adopted_bound": bound,
                      "robust": True, "sensitivity_bounds": {"1.00": bound},
                      "joint_constraint": None,
                      "candidates": {f"{bound:.2f}": {"worst_rcr": 0.25}},
                      "bound_reference_worst_rcr": 0.25},
            "envelope": {"anchor_rcr": 0.25},
        }

    def test_keep_keep_dimension(self):
        cfg = fd.build_final_parameters(self._state(
            {"decision": "KEEP", "rule_id": "K1_KEEP", "n_resolved": 7,
             "n_accepted": 0, "n_rejected_resolved": 7, "n_backgrounds": 7},
            {"decision": "KEEP", "rule_id": "K2_KEEP", "n_resolved": 4,
             "n_accepted": 0, "n_rejected_resolved": 4, "n_backgrounds": 4}))
        self.assertEqual(cfg["dimensionality"]["geometry_dimension"], 11)
        self.assertEqual(cfg["dimensionality"]["total_candidate_dimension"], 13)
        names = [p["name"] for p in cfg["keep_parameters"]]
        self.assertIn("Ks1", names)
        self.assertIn("Ks2", names)
        fixed = {p["name"]: p["value"] for p in cfg["fixed_parameters"]}
        self.assertEqual(fixed["SS1"], 3.2)
        self.assertEqual(fixed["SS2"], 0.8)
        self.assertEqual(cfg["xmean"]["upper_bound"], 0.18)

    def test_fix_fix_reduces_the_dimension(self):
        cfg = fd.build_final_parameters(self._state(
            {"decision": "FIX", "rule_id": "K1_FIX", "n_resolved": 7,
             "n_accepted": 6, "n_rejected_resolved": 1, "n_backgrounds": 7},
            {"decision": "FIX", "rule_id": "K2_FIX", "n_resolved": 4,
             "n_accepted": 4, "n_rejected_resolved": 0, "n_backgrounds": 4}))
        self.assertEqual(cfg["dimensionality"]["geometry_dimension"], 9)
        fixed = {p["name"]: p["value"] for p in cfg["fixed_parameters"]}
        self.assertEqual(fixed["Ks1"], 5.0)
        self.assertEqual(fixed["Ks2"], 0.10)


if __name__ == "__main__":
    unittest.main()


