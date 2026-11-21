import unittest
from unittest import mock

from radar.github_discovery import discover_github


class TestGitHubDiscovery(unittest.TestCase):
    def _inputs(self):
        requirement = {
            "id": "req_demo", "key": "D03", "title": "材料采购",
            "description": "采购订单流程", "pack_unit_ids": ["M08"],
            "terms": {"canonical": ["Purchase Order"], "aliases": []},
        }
        pack = {"modules": [{"id": "M08", "name": "采购与材料设备",
                             "keywords": ["采购", "材料"]}], "subsystems": []}
        return [requirement], pack

    def test_missing_token_returns_explicit_warning(self):
        requirements, pack = self._inputs()
        with mock.patch.dict("os.environ", {}, clear=True):
            result = discover_github(requirements, pack, "ws_demo", token=None)
        self.assertEqual(result["assets"], [])
        self.assertTrue(any("GITHUB_TOKEN" in item for item in result["warnings"]))

    @mock.patch("radar.github_discovery._curl_text",
                return_value=("Purchase Order creation", 200, None))
    @mock.patch("radar.github_discovery._api_list")
    @mock.patch("radar.github_discovery._api_json")
    @mock.patch("radar.github_discovery._search")
    def test_discovers_code_issue_and_pr_with_precise_locators(
            self, search, api_json, api_list, curl_text):
        requirements, pack = self._inputs()
        code = {
            "html_url": "https://github.com/acme/erp/blob/main/purchase.py",
            "path": "purchase.py", "sha": "blobsha",
            "repository": {"full_name": "acme/erp", "default_branch": "main"},
        }
        issue = {
            "html_url": "https://github.com/acme/erp/issues/7",
            "repository_url": "https://api.github.com/repos/acme/erp",
            "number": 7, "title": "Purchase Order approval",
            "body": "Purchase Order requires manager approval",
            "state": "closed", "updated_at": "2026-11-20T00:00:00Z",
            "labels": [{"name": "procurement"}],
        }
        pr = {
            "html_url": "https://github.com/acme/erp/pull/9",
            "repository_url": "https://api.github.com/repos/acme/erp",
            "number": 9, "title": "Fix Purchase Order receipt",
            "body": "Add receipt validation tests",
            "state": "closed", "updated_at": "2026-11-21T00:00:00Z",
            "labels": [],
        }

        def search_result(term, kind, token, limit, timeout):
            if kind == "code":
                return {"items": [code]}, None
            if kind == "issue":
                return {"items": [issue]}, None
            return {"items": [pr]}, None

        search.side_effect = search_result
        def api_result(path, token, timeout):
            if "/commits/" in path:
                return {"sha": "commit123"}, None
            if "/pulls/9" in path:
                return {"head": {"sha": "prhead123"}}, None
            return {}, None
        api_json.side_effect = api_result
        patch_text = "\n".join([
            "@@ -1,1 +1,2 @@",
            " existing = True",
            "+if approved: create_purchase_order()",
        ])
        api_list.return_value = ([{
            "filename": "erpnext/buying/purchase_order.py",
            "status": "modified", "additions": 1, "deletions": 0,
            "blob_url": "https://github.com/acme/erp/blob/prhead123/erpnext/buying/purchase_order.py",
            "patch": patch_text,
        }], None)
        result = discover_github(requirements, pack, "ws_demo", token="test-token",
                                 limit_per_query=2)
        self.assertEqual(result["counts"], {"code": 1, "issues": 1, "pull_requests": 1, "pr_files": 1})
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual({x["asset_type"] for x in result["assets"]},
                         {"file", "issue", "pull_request"})
        self.assertEqual(len(result["evidence"]), 4,
                         [(x["evidence_kind"], x["locator"]) for x in result["evidence"]])
        code_evidence = next(x for x in result["evidence"] if x["evidence_kind"] == "code")
        self.assertEqual(code_evidence["locator"]["line_start"], 1)
        self.assertEqual(code_evidence["locator"]["ref"], "commit123")
        self.assertEqual(len(result["matches"]["req_demo"]), 4)
        self.assertEqual(len(result["relationships"]), 1)
        diff_evidence = next(x for x in result["evidence"]
                             if x["locator"].get("pull_request") == 9)
        self.assertEqual(diff_evidence["locator"]["line_start"], 2)
        self.assertEqual(diff_evidence["locator"]["ref"], "prhead123")
        self.assertEqual(result["warnings"], [])
        self.assertEqual(search.call_count, 3,
                         "synonyms should be combined into one query per search type")


    @mock.patch("radar.github_discovery._curl_text")
    @mock.patch("radar.github_discovery._api_json")
    @mock.patch("radar.github_discovery._search")
    def test_recursive_tree_finds_document_not_returned_by_code_search(
            self, search, api_json, curl_text):
        requirements, pack = self._inputs()
        code = {
            "html_url": "https://github.com/acme/erp/blob/main/purchase.py",
            "path": "purchase.py", "sha": "blobsha",
            "repository": {"full_name": "acme/erp", "default_branch": "main"},
        }
        def search_result(query, kind, token, limit, timeout):
            return ({"items": [code] if kind == "code" else []}, None)
        search.side_effect = search_result
        def api_result(path, token, timeout):
            if "/commits/" in path:
                return {"sha": "treecommit123"}, None
            if "/git/trees/" in path:
                return {"tree": [
                    {"path": "docs/procurement-process.md", "type": "blob",
                     "sha": "docblob123", "size": 120},
                    {"path": "docs/legacy-guide.pdf", "type": "blob",
                     "sha": "pdfblob123", "size": 500},
                    {"path": "src/purchase.py", "type": "blob",
                     "sha": "codeblob123", "size": 300},
                ], "truncated": False}, None
            return {}, None
        api_json.side_effect = api_result
        def text_result(url, headers=None, timeout=25):
            if "raw.githubusercontent.com" in url:
                return ("# Procurement\nPurchase Order requires manager approval.\n", 200, None)
            return ("purchase_order()", 200, None)
        curl_text.side_effect = text_result
        result = discover_github(requirements, pack, "ws_docs", token="test-token")
        doc = next(x for x in result["assets"] if x["title"].endswith(".md"))
        self.assertEqual(doc["metadata"]["matched_by"], "github_recursive_tree")
        self.assertIn(doc["id"], result["matches"]["req_demo"])
        doc_evidence = next(x for x in result["evidence"]
                            if x["asset_id"] == doc["id"])
        self.assertEqual(doc_evidence["evidence_kind"], "documentation")
        self.assertEqual(doc_evidence["locator"]["path"], "docs/procurement-process.md")
        self.assertEqual(doc_evidence["locator"]["line_start"], 2)
        self.assertEqual(doc_evidence["locator"]["ref"], "treecommit123")
        pdf = next(x for x in result["assets"] if x["title"].endswith(".pdf"))
        self.assertEqual(pdf["metadata"]["content_extraction"], "unsupported_binary")
        self.assertEqual(result["counts"]["documents"], 1)
        self.assertEqual(result["counts"]["unsupported_documents"], 1)

    @mock.patch("radar.github_discovery._curl_text",
                return_value=("Purchase Order", 200, None))
    @mock.patch("radar.github_discovery._api_json", return_value=({"sha": "commit123"}, None))
    @mock.patch("radar.github_discovery._search")
    def test_same_asset_found_by_multiple_terms_is_deduplicated(
            self, search, api_json, curl_text):
        requirements, pack = self._inputs()
        code = {
            "html_url": "https://github.com/acme/erp/blob/main/purchase.py",
            "path": "purchase.py", "sha": "blobsha",
            "repository": {"full_name": "acme/erp", "default_branch": "main"},
        }
        search.return_value = ({"items": [code]}, None)
        result = discover_github(requirements, pack, "ws_demo", token="test-token")
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["counts"]["code"], 1)
        self.assertEqual(search.call_count, 3)


if __name__ == "__main__":
    unittest.main()
