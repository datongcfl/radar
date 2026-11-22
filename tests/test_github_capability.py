import unittest
from unittest import mock

from radar.capabilities import CapabilityContext, CapabilityResult
from radar.github_capability import GithubSourceCapability


class TestGithubSourceCapability(unittest.TestCase):
    def setUp(self):
        self.capability = GithubSourceCapability()
        self.context = CapabilityContext(
            operation="discover",
            inputs={"pack": {"modules": [], "subsystems": [], "source_map": {"github": ["test"]}}},
            parameters={"limit_per_query": 4, "max_queries": 2, "token": "secret-token"},
        )

    def test_descriptor_identifies_source_capability(self):
        descriptor = self.capability.descriptor
        self.assertEqual((descriptor.name, descriptor.kind, descriptor.version),
                         ("github", "source", "1.0.0"))

    @mock.patch("radar.github_capability.collect_github")
    def test_success_preserves_records_and_forwards_explicit_inputs(self, collect):
        record = {"id": "GH-001", "evidence_level": "metadata"}
        collect.return_value = ([record], [])
        result = self.capability.execute(self.context)
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(dict(result.records[0]), record)
        collect.assert_called_once_with(
            self.context.inputs["pack"], limit_per_query=4,
            max_queries=2, token="secret-token",
        )
        self.assertEqual(result.metadata["evidence_level"], "metadata")

    @mock.patch("radar.github_capability.collect_github")
    def test_partial_results_are_not_reported_as_full_success(self, collect):
        collect.return_value = ([{"id": "GH-001"}], ["one query failed"])
        result = self.capability.execute(self.context)
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.warnings[0]["code"], "github_query_warning")
        self.assertEqual(result.records[0]["id"], "GH-001")

    @mock.patch("radar.github_capability.collect_github")
    def test_all_queries_failing_is_failed_not_empty_success(self, collect):
        collect.return_value = ([], ["request failed"])
        result = self.capability.execute(self.context)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], "github_search_failed")

    @mock.patch("radar.github_capability.collect_github")
    def test_no_configured_queries_is_a_valid_empty_success(self, collect):
        collect.return_value = ([], [])
        result = self.capability.execute(self.context)
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.records, ())

    @mock.patch("radar.github_capability.collect_github")
    def test_provider_exception_is_normalized(self, collect):
        collect.side_effect = RuntimeError("secret-token leaked")
        result = self.capability.execute(self.context)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], "github_adapter_exception")
        self.assertNotIn("secret-token", str(result.error))

    @mock.patch("radar.github_capability.collect_github")
    def test_warning_redacts_token(self, collect):
        collect.return_value = ([], ["failed token=secret-token"])
        result = self.capability.execute(self.context)
        self.assertEqual(result.status, "failed")
        self.assertNotIn("secret-token", result.warnings[0]["message"])
        self.assertIn("[REDACTED]", result.warnings[0]["message"])

    @mock.patch("radar.github_capability.collect_github")
    def test_unsupported_operation_is_rejected_without_provider_call(self, collect):
        context = CapabilityContext(
            operation="parse", inputs={"pack": {}}, parameters={}
        )
        result = self.capability.execute(context)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], "unsupported_operation")
        collect.assert_not_called()

    @mock.patch("radar.github_capability.collect_github")
    def test_invalid_limits_are_rejected(self, collect):
        context = CapabilityContext(
            operation="discover", inputs={"pack": {}},
            parameters={"limit_per_query": 11},
        )
        result = self.capability.execute(context)
        self.assertEqual(result.error["code"], "invalid_limit_per_query")
        collect.assert_not_called()

    @mock.patch("radar.github_capability.collect_github")
    def test_non_string_token_is_rejected(self, collect):
        context = CapabilityContext(
            operation="discover", inputs={"pack": {}},
            parameters={"token": object()},
        )
        result = self.capability.execute(context)
        self.assertEqual(result.error["code"], "invalid_token_type")
        collect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
