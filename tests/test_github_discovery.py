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
        self.assertEqual(result["counts"], {"code": 1, "issues": 1, "pull_requests": 1, "pr_files": 1, "documents": 0, "unsupported_documents": 0, "parsed_documents": 0, "parse_failures": 0, "issue_comments": 0, "pr_review_items": 0, "ci_checks": 0, "ci_statuses": 0})
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
        self.assertEqual(search.call_count, 6,
                         "terms should be searched in bounded batches for each search type")



    @mock.patch("radar.github_discovery._api_list")
    @mock.patch("radar.github_discovery._api_json")
    @mock.patch("radar.github_discovery._search")
    def test_issue_comments_pr_reviews_and_ci_become_evidence(
            self, search, api_json, api_list):
        requirements, pack = self._inputs()
        issue = {"number": 5, "title": "Purchase Order approval",
                 "body": "Approval is required", "html_url": "https://github.com/acme/erp/issues/5",
                 "repository": {"full_name": "acme/erp", "default_branch": "main"}}
        pr = {"number": 6, "title": "Add purchase workflow", "body": "Adds approval",
              "html_url": "https://github.com/acme/erp/pull/6",
              "repository": {"full_name": "acme/erp", "default_branch": "main"}}
        def search_result(query, kind, token, limit, timeout):
            return ({"items": [issue] if kind == "issue" else ([pr] if kind == "pull_request" else [])}, None)
        search.side_effect = search_result
        def api_result(path, token, timeout):
            if "/pulls/6" in path:
                return {"head": {"sha": "prhead456"}}, None
            if "/check-runs" in path:
                return {"check_runs": [{"id": 91, "name": "unit tests", "status": "completed",
                                        "conclusion": "success", "html_url": "https://github.com/acme/erp/actions/runs/91",
                                        "output": {"summary": "119 tests passed"}}]}, None
            if path.endswith("/status"):
                return {"statuses": [{"state": "success", "context": "ci/build",
                                      "description": "Build passed",
                                      "target_url": "https://ci.example/build/91"}]}, None
            return {}, None
        api_json.side_effect = api_result
        def list_result(path, token, timeout):
            if "/issues/5/comments" in path:
                return ([{"id": 51, "body": "Use receipt matching before closing PO",
                          "html_url": "https://github.com/acme/erp/issues/5#issuecomment-51",
                          "created_at": "2026-01-01T00:00:00Z"}], None)
            if "/issues/6/comments" in path:
                return ([{"id": 61, "body": "Please add a rejection path",
                          "html_url": "https://github.com/acme/erp/pull/6#issuecomment-61"}], None)
            if "/pulls/6/files" in path:
                return ([], None)
            if "/pulls/6/comments" in path:
                return ([{"id": 62, "body": "This line misses quantity validation",
                          "html_url": "https://github.com/acme/erp/pull/6#discussion_r62",
                          "path": "purchase.py", "line": 42, "commit_id": "prhead456"}], None)
            if "/pulls/6/reviews" in path:
                return ([{"id": 63, "body": "Changes requested: handle partial receipts",
                          "html_url": "https://github.com/acme/erp/pull/6#pullrequestreview-63"}], None)
            return ([], None)
        api_list.side_effect = list_result
        result = discover_github(requirements, pack, "ws_discussion", token="test-token")
        self.assertEqual(result["counts"]["issue_comments"], 2)
        self.assertEqual(result["counts"]["pr_review_items"], 2)
        self.assertEqual(result["counts"]["ci_checks"], 1)
        self.assertEqual(result["counts"]["ci_statuses"], 1)
        self.assertTrue(any("receipt matching" in e["statement"] for e in result["evidence"]))
        review = next(e for e in result["evidence"] if e["locator"].get("line") == 42)
        self.assertEqual(review["locator"]["commit_id"], "prhead456")
        self.assertTrue(any(e["evidence_kind"] == "test" and "119 tests passed" in e["statement"]
                            for e in result["evidence"]))
        self.assertTrue(any(e["evidence_kind"] == "test" and "Build passed" in e["statement"]
                            for e in result["evidence"]))
        self.assertGreaterEqual(len(result["relationships"]), 4)

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
        self.assertEqual(result["counts"]["parsed_documents"], 0)
        self.assertEqual(result["counts"]["parse_failures"], 0)


    @mock.patch("radar.github_discovery._curl_text")
    @mock.patch("radar.github_discovery._api_json")
    @mock.patch("radar.github_discovery._search")
    def test_docx_blob_is_parsed_into_paragraph_evidence(
            self, search, api_json, curl_text):
        import base64
        from io import BytesIO
        from zipfile import ZipFile
        requirements, pack = self._inputs()
        archive = BytesIO()
        with ZipFile(archive, "w") as doc:
            doc.writestr("word/document.xml",
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>Purchase Order approval requires manager review</w:t>'
                '</w:r></w:p></w:body></w:document>')
        code = {"html_url": "https://github.com/acme/erp/blob/main/app.py",
                "path": "app.py", "sha": "codeblob",
                "repository": {"full_name": "acme/erp", "default_branch": "main"}}
        search.side_effect = lambda query, kind, token, limit, timeout: (
            {"items": [code] if kind == "code" else []}, None)
        def api_result(path, token, timeout):
            if "/commits/" in path:
                return {"sha": "fixedcommit"}, None
            if "/git/trees/" in path:
                return {"tree": [{"path": "docs/procurement.docx", "type": "blob",
                                  "sha": "docblob", "size": len(archive.getvalue())}],
                        "truncated": False}, None
            if "/git/blobs/docblob" in path:
                return {"encoding": "base64",
                        "content": base64.b64encode(archive.getvalue()).decode("ascii")}, None
            return {}, None
        api_json.side_effect = api_result
        curl_text.return_value = ("purchase_order()", 200, None)
        result = discover_github(requirements, pack, "ws_docx", token="test-token")
        doc_asset = next(a for a in result["assets"] if a["title"].endswith(".docx"))
        self.assertEqual(doc_asset["metadata"]["content_extraction"], "parsed")
        self.assertEqual(doc_asset["metadata"]["parser"], "stdlib-office-xml")
        ev = next(e for e in result["evidence"] if e["asset_id"] == doc_asset["id"])
        self.assertIn("Purchase Order approval", ev["statement"])
        self.assertEqual(ev["locator"]["paragraph"], 1)
        self.assertEqual(ev["locator"]["path"], "docs/procurement.docx")
        self.assertEqual(ev["locator"]["ref"], "fixedcommit")
        self.assertEqual(ev["extractor"]["name"], "stdlib-office-xml")
        self.assertEqual(result["counts"]["parsed_documents"], 1)

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
        self.assertEqual(search.call_count, 6)


    @mock.patch("radar.github_discovery._api_json")
    @mock.patch("radar.github_discovery._search")
    def test_d03_search_batches_cover_receipt_transfer_and_return_terms(
            self, search, api_json):
        requirement = {
            "id": "req_d03", "key": "D03", "title": "材料采购与现场流转",
            "description": "采购申请、收货、入库、领料、退料和调拨",
            "pack_unit_ids": ["M04", "M08", "M11"],
            "terms": {
                "canonical": ["Material Request", "Supplier Quotation", "Purchase Order",
                              "Purchase Receipt", "Stock Entry", "Material Issue",
                              "Material Transfer", "Purchase Return"],
                "aliases": ["采购申请", "询价比价", "到货验收", "材料入库",
                            "材料领用", "退料", "现场调拨", "采购退货"],
            },
        }
        pack = {"modules": [
            {"id": "M04", "name": "询价与产品库", "keywords": ["询价", "比价"]},
            {"id": "M08", "name": "采购与材料设备", "keywords": ["采购", "材料", "到货"]},
            {"id": "M11", "name": "实际成本与毛利", "keywords": ["实际成本", "毛利"]},
        ], "subsystems": []}
        search.return_value = ({"items": []}, None)
        result = discover_github([requirement], pack, "ws_d03_terms",
                                 token="test-token", limit_per_query=5)
        queries = [call.args[0] for call in search.call_args_list]
        self.assertEqual(len(queries), 12)
        for critical_term in ("Purchase Receipt", "Stock Entry",
                              "Material Transfer", "Purchase Return",
                              "到货验收", "现场调拨"):
            self.assertTrue(any(critical_term in query for query in queries),
                            critical_term)
        self.assertEqual(result["counts"]["code"], 0)
        self.assertEqual(result["warnings"], [])


if __name__ == "__main__":
    unittest.main()
