import unittest
import json
from pathlib import Path

from radar.discovery import (
    DiscoveryValidationError,
    new_record,
    validate_evidence_unchanged,
    validate_record,
    new_requirement_revision,
)


class TestDiscoveryDomain(unittest.TestCase):
    def test_workspace_creation(self):
        record = new_record("workspace", name="Weak-current", status="active", pack_refs=[])
        data = record.to_dict()
        self.assertEqual(data["object_type"], "workspace")
        self.assertTrue(data["id"].startswith("ws_"))
        self.assertEqual(validate_record(data)["name"], "Weak-current")

    def test_requirement_requires_acceptance_criteria(self):
        with self.assertRaises(DiscoveryValidationError):
            new_record("requirement", workspace_id="ws_demo", key="D03", version=1,
                       title="采购", description="材料采购", status="active",
                       priority="high")

    def test_requirement_criterion_ids_are_unique(self):
        with self.assertRaises(DiscoveryValidationError):
            new_record("requirement", workspace_id="ws_demo", key="D03", version=1,
                       title="采购", description="材料采购", status="active",
                       priority="high", acceptance_criteria=[
                           {"id": "C1", "description": "申请", "required": True},
                           {"id": "C1", "description": "审批", "required": True},
                       ])

    def test_source_and_asset_are_distinct(self):
        source = new_record("source", provider="github", uri="https://github.com/acme/app",
                            name="acme/app", access_status="public")
        asset = new_record("asset", source_id=source.id, asset_type="repository",
                           uri="https://github.com/acme/app", title="app", status="active")
        self.assertNotEqual(source.id, asset.id)
        self.assertEqual(asset.to_dict()["source_id"], source.id)

    def test_evidence_requires_precise_locator(self):
        with self.assertRaises(DiscoveryValidationError):
            new_record("evidence", workspace_id="ws_demo", asset_id="ast_demo",
                       evidence_kind="code", statement="有采购申请流程",
                       locator={}, captured_at="2026-11-22T00:00:00Z",
                       verification_status="source_confirmed")

    def test_evidence_excerpt_limit(self):
        with self.assertRaises(DiscoveryValidationError):
            new_record("evidence", workspace_id="ws_demo", asset_id="ast_demo",
                       evidence_kind="documentation", statement="说明",
                       locator={"path": "README.md"}, captured_at="2026-11-22T00:00:00Z",
                       verification_status="unverified", excerpt="x" * 2001)

    def test_evidence_is_immutable(self):
        evidence = new_record("evidence", workspace_id="ws_demo", asset_id="ast_demo",
                              evidence_kind="code", statement="实现采购订单",
                              locator={"path": "purchase.py", "line_start": 10},
                              captured_at="2026-11-22T00:00:00Z",
                              verification_status="source_confirmed").to_dict()
        changed = dict(evidence, statement="修改后的事实")
        with self.assertRaises(DiscoveryValidationError):
            validate_evidence_unchanged(evidence, changed)
        validate_evidence_unchanged(evidence, evidence)

    def test_relationship_confidence_range(self):
        with self.assertRaises(DiscoveryValidationError):
            new_record("relationship", **{
                "from": {"object_type": "asset", "id": "ast_a"},
                "to": {"object_type": "requirement", "id": "req_a"},
                "relation_type": "supports", "confidence": 1.2,
                "evidence_ids": ["evd_a"], "status": "active", "created_by": "radar",
            })

    def test_no_evidence_is_not_implementation_failure(self):
        assessment = new_record("assessment", workspace_id="ws_demo",
            requirement_id="req_demo", requirement_version=1, discovery_run_id="run_demo",
            overall_status="no_evidence", criterion_results=[
                {"criterion_id": "C1", "status": "no_evidence", "evidence_ids": []}
            ], evidence_ids=[], pack_refs=[], assessed_at="2026-11-22T00:00:00Z")
        self.assertEqual(assessment.to_dict()["overall_status"], "no_evidence")

    def test_record_type_prefix_is_enforced(self):
        record = new_record("workspace", name="Demo", status="active", pack_refs=[]).to_dict()
        record["id"] = "req_wrong"
        with self.assertRaises(DiscoveryValidationError):
            validate_record(record)


if __name__ == "__main__":
    unittest.main()



class TestRevisionAndImmutability(unittest.TestCase):
    def test_domain_payload_is_deeply_immutable(self):
        record = new_record("workspace", name="demo", status="active",
                            pack_refs=[{"pack": "weak-current", "version": "1.0"}])
        with self.assertRaises(TypeError):
            record.payload["name"] = "changed"
        with self.assertRaises(TypeError):
            record.payload["pack_refs"][0]["pack"] = "other"
        exported = record.to_dict()
        exported["pack_refs"][0]["pack"] = "changed"
        self.assertEqual(record.to_dict()["pack_refs"][0]["pack"], "weak-current")

    def test_requirement_revision_appends_new_id_and_version(self):
        first = new_record("requirement", workspace_id="ws_demo", key="D03",
            version=1, title="材料采购", description="材料申请至入库",
            status="active", priority="high",
            acceptance_criteria=[{"id": "C1", "description": "可申请", "required": True}])
        second = new_requirement_revision(first.to_dict(), description="材料申请、审批至入库")
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(second.to_dict()["version"], 2)
        self.assertEqual(second.to_dict()["key"], "D03")
        self.assertEqual(second.to_dict()["supersedes_requirement_id"], first.id)
        self.assertEqual(first.to_dict()["version"], 1)

    def test_requirement_revision_cannot_change_identity(self):
        first = new_record("requirement", workspace_id="ws_demo", key="D03",
            version=1, title="材料采购", description="材料申请至入库",
            status="active", priority="high", acceptance_criteria=[])
        with self.assertRaises(DiscoveryValidationError):
            new_requirement_revision(first.to_dict(), key="D04")


class TestDiscoverySchema(unittest.TestCase):
    def test_schema_defines_all_eight_domain_objects(self):
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "discovery.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        definitions = schema["$defs"]
        for name in ("Workspace", "Requirement", "Source", "Asset", "Evidence",
                     "Relationship", "Assessment", "DiscoveryRun"):
            self.assertIn(name, definitions)
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
