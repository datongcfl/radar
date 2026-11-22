import unittest
from unittest import mock

from radar.capabilities import CapabilityContext
from radar.gitee_capability import GiteeSourceCapability


class TestGiteeSourceCapability(unittest.TestCase):
    def setUp(self):
        self.capability = GiteeSourceCapability()
        self.pack = {"modules": [], "subsystems": [], "source_map": {"gitee": ["test"]}}
        self.context = CapabilityContext(
            operation="discover", inputs={"pack": self.pack},
            parameters={"limit_per_query": 5, "max_queries": 2, "token": "gitee-secret"},
        )

    def test_descriptor(self):
        descriptor = self.capability.descriptor
        self.assertEqual((descriptor.name, descriptor.kind, descriptor.version),
                         ("gitee", "source", "1.0.0"))

    @mock.patch("radar.gitee_capability.collect_gitee")
    def test_success_forwards_context(self, collect):
        record = {"id": "GT-001", "evidence_level": "metadata"}
        collect.return_value = ([record], [])
        result = self.capability.execute(self.context)
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(dict(result.records[0]), record)
        collect.assert_called_once_with(
            self.pack, limit_per_query=5, max_queries=2, token="gitee-secret"
        )

    @mock.patch("radar.gitee_capability.collect_gitee")
    def test_partial_results_preserved(self, collect):
        collect.return_value = ([{"id": "GT-001"}], ["second query failed"])
        result = self.capability.execute(self.context)
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.records[0]["id"], "GT-001")

    @mock.patch("radar.gitee_capability.collect_gitee")
    def test_total_failure_not_empty_success(self, collect):
        collect.return_value = ([], ["API unavailable"])
        result = self.capability.execute(self.context)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], "gitee_search_failed")

    @mock.patch("radar.gitee_capability.collect_gitee")
    def test_missing_token_is_reported_as_failure_when_queries_exist(self, collect):
        collect.return_value = ([], ["Gitee 需要 GITEE_TOKEN；已跳过"])
        context = CapabilityContext(
            operation="discover", inputs={"pack": self.pack}, parameters={"token": None},
        )
        result = self.capability.execute(context)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.warnings[0]["code"], "gitee_query_warning")

    @mock.patch("radar.gitee_capability.collect_gitee")
    def test_no_queries_is_empty_success(self, collect):
        collect.return_value = ([], [])
        result = self.capability.execute(self.context)
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.records, ())

    @mock.patch("radar.gitee_capability.collect_gitee")
    def test_exception_is_normalized_without_message(self, collect):
        collect.side_effect = RuntimeError("gitee-secret")
        result = self.capability.execute(self.context)
        self.assertEqual(result.status, "failed")
        self.assertNotIn("gitee-secret", str(result.error))

    @mock.patch("radar.gitee_capability.collect_gitee")
    def test_warning_redacts_token(self, collect):
        collect.return_value = ([], ["error gitee-secret"])
        result = self.capability.execute(self.context)
        self.assertNotIn("gitee-secret", result.warnings[0]["message"])
        self.assertIn("[REDACTED]", result.warnings[0]["message"])

    @mock.patch("radar.gitee_capability.collect_gitee")
    def test_unsupported_operation_rejected(self, collect):
        context = CapabilityContext(operation="parse", inputs={"pack": self.pack})
        result = self.capability.execute(context)
        self.assertEqual(result.error["code"], "unsupported_operation")
        collect.assert_not_called()

    @mock.patch("radar.gitee_capability.collect_gitee")
    def test_invalid_limit_rejected(self, collect):
        context = CapabilityContext(
            operation="discover", inputs={"pack": self.pack},
            parameters={"limit_per_query": 0},
        )
        result = self.capability.execute(context)
        self.assertEqual(result.error["code"], "invalid_limit_per_query")
        collect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
