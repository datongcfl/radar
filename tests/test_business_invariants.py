import unittest

from radar.business_invariants import (
    ObservationError, evaluate_business_invariants, validate_observation_bundle,
)


class TestBusinessInvariantEvaluation(unittest.TestCase):
    def _invariant(self, operator, fields, target_field=None, tolerance=0):
        row = {"id":"inv_test","name":"Test","description":"Test invariant",
               "operator":operator,"scope":"record","fields":fields,
               "related_entities":["purchase_receipt"],"required_evidence":["source record"],
               "risk":"test risk"}
        if target_field:
            row["target_field"] = target_field
        if tolerance:
            row["tolerance"] = tolerance
        return row

    def _bundle(self, invariant, values, origin="test", runtime=False):
        provenance = {}
        evidence = []
        for index, field in enumerate(values):
            evidence_id = "ev_%s" % field
            level = "runtime_observation" if runtime else "ci_check_success"
            provenance[field] = {
                "evidence_id": evidence_id,
                "locator": {"path":"fixture.json","field":field},
                "verification_level": level,
                "runtime_observed": runtime,
            }
            evidence.append({
                "id": evidence_id, "asset_id":"asset_fixture",
                "metadata":{"verification":{"level":level,"runtime_observed":runtime}},
            })
        bundle = {"schema_version":1,"observations":[{
            "id":"obs_1","invariant_id":invariant["id"],"scope_key":"record-1",
            "origin":origin,"values":values,"field_provenance":provenance,
            "captured_at":"2026-11-22T10:00:00Z"}]}
        return bundle, evidence

    def test_sum_equals_pass_and_fail(self):
        invariant = self._invariant("sum_equals", ["accepted","rejected"], "received")
        bundle, evidence = self._bundle(invariant, {"accepted":8,"rejected":2,"received":10})
        result = evaluate_business_invariants([invariant], bundle, evidence)
        self.assertEqual(result["evaluations"][0]["outcome"], "pass")
        self.assertEqual(result["summary"][0]["status"], "passed")
        bundle["observations"][0]["values"]["received"] = 11
        result = evaluate_business_invariants([invariant], bundle, evidence)
        self.assertEqual(result["evaluations"][0]["outcome"], "fail")
        self.assertEqual(result["evaluations"][0]["delta"], "-1")

    def test_multiplication_excludes_target_even_when_target_is_in_fields(self):
        invariant = self._invariant("multiplication_equals",
                                    ["purchase_qty","conversion_factor","base_qty"],
                                    "base_qty", 0.0001)
        bundle, evidence = self._bundle(invariant, {
            "purchase_qty":"12.5","conversion_factor":"4","base_qty":"50"})
        result = evaluate_business_invariants([invariant], bundle, evidence)
        self.assertEqual(result["evaluations"][0]["outcome"], "pass")
        self.assertEqual(result["evaluations"][0]["computed"]["calculated"], "50.0")

    def test_less_than_or_equal_and_tolerance(self):
        upper = self._invariant("less_than_or_equal", ["received","ordered"])
        bundle, evidence = self._bundle(upper, {"received":9,"ordered":10})
        self.assertEqual(evaluate_business_invariants([upper], bundle, evidence)["evaluations"][0]["outcome"], "pass")
        equal = self._invariant("equal_with_tolerance", ["inventory","ledger"], tolerance=0.01)
        bundle, evidence = self._bundle(equal, {"inventory":"100.005","ledger":"100"})
        self.assertEqual(evaluate_business_invariants([equal], bundle, evidence)["evaluations"][0]["outcome"], "pass")

    def test_separate_fields_requires_distinct_field_paths(self):
        invariant = self._invariant("separate_fields",
                                    ["budget_cost","committed_cost","actual_cost"])
        bundle, evidence = self._bundle(invariant, {
            "budget_cost":"Project.budget_cost",
            "committed_cost":"Project.committed_cost",
            "actual_cost":"Project.actual_cost"})
        self.assertEqual(evaluate_business_invariants([invariant], bundle, evidence)["evaluations"][0]["outcome"], "pass")
        bundle["observations"][0]["values"]["actual_cost"] = "Project.budget_cost"
        self.assertEqual(evaluate_business_invariants([invariant], bundle, evidence)["evaluations"][0]["outcome"], "fail")

    def test_runtime_verification_requires_runtime_backed_evidence(self):
        invariant = self._invariant("less_than_or_equal", ["actual","limit"])
        bundle, evidence = self._bundle(invariant, {"actual":2,"limit":3}, origin="runtime", runtime=True)
        result = evaluate_business_invariants([invariant], bundle, evidence)
        self.assertEqual(result["evaluations"][0]["verification_level"], "runtime_observed")
        evidence[0]["metadata"]["verification"]["runtime_observed"] = False
        with self.assertRaises(ObservationError):
            evaluate_business_invariants([invariant], bundle, evidence)

    def test_unknown_evidence_and_non_finite_values_are_rejected(self):
        invariant = self._invariant("less_than_or_equal", ["actual","limit"])
        bundle, evidence = self._bundle(invariant, {"actual":2,"limit":3})
        with self.assertRaises(ObservationError):
            evaluate_business_invariants([invariant], bundle, [])
        bundle["observations"][0]["values"]["actual"] = "NaN"
        with self.assertRaises(ObservationError):
            evaluate_business_invariants([invariant], bundle, evidence)

    def test_no_observation_is_not_pass_or_fail(self):
        invariant = self._invariant("less_than_or_equal", ["actual","limit"])
        result = evaluate_business_invariants([invariant], None)
        self.assertEqual(result["summary"][0]["status"], "no_observation")
        self.assertFalse(result["evaluations"])


if __name__ == "__main__":
    unittest.main()
