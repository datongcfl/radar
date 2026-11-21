import unittest

from radar.code_analyzer import analyze_python_source


class TestPythonCodeAnalyzer(unittest.TestCase):
    def test_imports_and_guarded_status_transition_have_exact_lines(self):
        source = """from procurement.order import PurchaseOrder
class Receipt:
    def submit(self):
        if self.status == "Draft":
            self.status = "Submitted"
"""
        result = analyze_python_source(source, "receipt.py")
        self.assertEqual(result["status"], "parsed")
        self.assertEqual(result["imports"][0]["module"], "procurement.order")
        self.assertEqual(result["imports"][0]["line"], 1)
        self.assertEqual(len(result["state_transitions"]), 1)
        transition = result["state_transitions"][0]
        self.assertEqual((transition["from_state"], transition["to_state"]),
                         ("Draft", "Submitted"))
        self.assertEqual(transition["guard_line"], 4)
        self.assertEqual(transition["assignment_line"], 5)
        self.assertEqual(transition["scope"], ["class:Receipt", "function:submit"])

    def test_does_not_infer_transition_without_matching_guard(self):
        source = """if doc.status == "Draft":
    other.status = "Submitted"
doc.status = "Closed"
"""
        result = analyze_python_source(source)
        self.assertEqual(result["state_transitions"], [])

    def test_parse_failure_is_explicit(self):
        result = analyze_python_source("def broken(:", "broken.py")
        self.assertEqual(result["status"], "parse_failed")
        self.assertEqual(result["imports"], [])


if __name__ == "__main__":
    unittest.main()
