import unittest
from unittest.mock import patch

from radar.capabilities import CapabilityContext
from radar.github_asset_inventory import GithubRepositoryAssetInventoryCapability


class TestGithubRepositoryAssetInventory(unittest.TestCase):
    def setUp(self):
        self.capability = GithubRepositoryAssetInventoryCapability()
        self.context = CapabilityContext(
            operation="inventory",
            inputs={"repository": "acme/platform"},
            parameters={"token": "secret", "max_files": 20, "max_file_bytes": 100000},
        )

    @patch("radar.github_asset_inventory._request_json")
    def test_inventory_pins_tree_to_commit_and_classifies_documents(self, request):
        request.side_effect = [
            ({"default_branch": "main"}, None, 200),
            ({"sha": "a" * 40, "commit": {"tree": {"sha": "b" * 40}}}, None, 200),
            ({"truncated": False, "tree": [
                {"path": "README.md", "type": "blob", "sha": "c" * 40, "size": 20},
                {"path": "src/app.py", "type": "blob", "sha": "d" * 40, "size": 50},
                {"path": "docs/guide.pdf", "type": "blob", "sha": "e" * 40, "size": 90},
                {"path": "assets/logo.png", "type": "blob", "sha": "f" * 40, "size": 10},
                {"path": "node_modules/pkg/README.md", "type": "blob", "sha": "1" * 40, "size": 20},
            ]}, None, 200),
        ]
        result = self.capability.execute(self.context)
        self.assertEqual(result.status, "succeeded")
        self.assertEqual([r["path"] for r in result.records],
                         ["README.md", "src/app.py", "docs/guide.pdf"])
        self.assertEqual(result.records[0]["parser_hint"], "text")
        self.assertEqual(result.records[2]["parser_hint"], "pdf")
        self.assertTrue(all(r["commit_sha"] == "a" * 40 for r in result.records))
        self.assertTrue(all(r["evidence_promoted"] is False for r in result.records))
        self.assertEqual(request.call_count, 3)

    @patch("radar.github_asset_inventory._request_json")
    def test_truncated_tree_is_partial_not_complete_success(self, request):
        request.side_effect = [
            ({"default_branch": "main"}, None, 200),
            ({"sha": "a" * 40, "commit": {"tree": {"sha": "b" * 40}}}, None, 200),
            ({"truncated": True, "tree": []}, None, 200),
        ]
        result = self.capability.execute(self.context)
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.warnings[0]["code"], "github_tree_truncated")
        self.assertTrue(result.metadata["tree_truncated"])

    @patch("radar.github_asset_inventory._request_json")
    def test_large_files_and_generated_directories_are_excluded(self, request):
        request.side_effect = [
            ({"default_branch": "main"}, None, 200),
            ({"sha": "a" * 40, "commit": {"tree": {"sha": "b" * 40}}}, None, 200),
            ({"truncated": False, "tree": [
                {"path": "docs/huge.md", "type": "blob", "sha": "c" * 40, "size": 100001},
                {"path": "dist/manual.md", "type": "blob", "sha": "d" * 40, "size": 10},
                {"path": "../escape.md", "type": "blob", "sha": "e" * 40, "size": 10},
            ]}, None, 200),
        ]
        result = self.capability.execute(self.context)
        self.assertEqual(result.records, ())
        self.assertEqual(result.metadata["skipped_large"], 1)
        self.assertEqual(result.metadata["skipped_ignored"], 1)

    @patch("radar.github_asset_inventory._request_json")
    def test_api_failure_is_not_an_empty_success(self, request):
        request.return_value = (None, "github_http_403", 403)
        result = self.capability.execute(self.context)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], "github_repository_unavailable")
        self.assertEqual(result.error["http_status"], 403)

    def test_invalid_repository_and_limits_are_rejected_before_network(self):
        for repository in ("https://github.com/acme/platform", "../acme/platform", "acme"):
            context = CapabilityContext(operation="inventory",
                inputs={"repository": repository}, parameters={})
            result = self.capability.execute(context)
            self.assertEqual(result.error["code"], "invalid_repository")
        context = CapabilityContext(operation="inventory",
            inputs={"repository": "acme/platform"}, parameters={"max_files": 0})
        result = self.capability.execute(context)
        self.assertEqual(result.error["code"], "invalid_max_files")

    def test_wrong_operation_is_rejected(self):
        context = CapabilityContext(operation="discover",
            inputs={"repository": "acme/platform"}, parameters={})
        result = self.capability.execute(context)
        self.assertEqual(result.error["code"], "unsupported_operation")


if __name__ == "__main__":
    unittest.main()
