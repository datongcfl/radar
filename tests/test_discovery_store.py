import tempfile
import unittest
from pathlib import Path

from radar.discovery import new_record, new_requirement_revision
from radar.discovery_store import JsonWorkspaceStore, StorageError


class TestJsonWorkspaceStore(unittest.TestCase):
    def _workspace(self, name="demo"):
        return new_record("workspace", name=name, status="active", pack_refs=[]).to_dict()

    def _requirement(self, workspace_id, key="D03", version=1):
        return new_record("requirement", workspace_id=workspace_id, key=key,
            version=version, title="材料采购", description="申请至入库",
            status="active", priority="high",
            acceptance_criteria=[{"id":"C1","description":"申请可追溯","required":True}]).to_dict()

    def test_append_get_and_requirement_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._workspace()
            store = JsonWorkspaceStore(tmp, workspace["id"])
            store.initialize(workspace)
            first = self._requirement(workspace["id"])
            store.append(first)
            second = new_requirement_revision(first, description="申请、审批至入库").to_dict()
            store.append(second)
            history = store.find_requirement_history("D03")
            self.assertEqual([x["version"] for x in history], [1, 2])
            self.assertEqual(store.get("requirement", second["id"])["version"], 2)

    def test_duplicate_record_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._workspace()
            store = JsonWorkspaceStore(tmp, workspace["id"])
            store.initialize(workspace)
            record = self._requirement(workspace["id"])
            store.append(record)
            with self.assertRaises(StorageError):
                store.append(record)

    def test_workspace_isolation_is_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            one = self._workspace("one")
            two = self._workspace("two")
            a = JsonWorkspaceStore(tmp, one["id"]); a.initialize(one)
            b = JsonWorkspaceStore(tmp, two["id"]); b.initialize(two)
            with self.assertRaises(StorageError):
                b.append(self._requirement(one["id"]))

    def test_relationship_and_evidence_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._workspace()
            store = JsonWorkspaceStore(tmp, workspace["id"]); store.initialize(workspace)
            source = new_record("source", provider="github", uri="https://github.com",
                                name="GitHub", access_status="public").to_dict()
            asset = new_record("asset", source_id=source["id"], asset_type="repository",
                               uri="https://github.com/acme/app", title="app",
                               status="active").to_dict()
            evidence = new_record("evidence", workspace_id=workspace["id"],
                asset_id=asset["id"], evidence_kind="code", statement="实现采购申请",
                locator={"path":"purchase.py","line_start":10},
                captured_at="2026-11-22T00:00:00Z", verification_status="source_confirmed").to_dict()
            relation = new_record("relationship", **{
                "from":{"object_type":"source","id":source["id"]},
                "to":{"object_type":"asset","id":asset["id"]},
                "relation_type":"contains","confidence":1.0,"evidence_ids":[],
                "status":"active","created_by":"radar"}).to_dict()
            store.append(source); store.append(asset); store.append(evidence); store.append(relation)
            self.assertEqual(len(store.find_relationships("asset", asset["id"])), 1)
            self.assertEqual(len(store.evidence_for_asset(asset["id"])), 1)

    def test_snapshot_is_content_addressed_and_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._workspace()
            store = JsonWorkspaceStore(tmp, workspace["id"]); store.initialize(workspace)
            digest = store.save_snapshot("original document")
            self.assertEqual(store.read_snapshot(digest), b"original document")
            self.assertEqual(store.save_snapshot("original document"), digest)
            path = store.root / "snapshots" / "sha256" / digest[:2] / digest
            path.write_bytes(b"tampered")
            with self.assertRaises(StorageError):
                store.read_snapshot(digest)

    def test_discovery_run_is_stored_by_run_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._workspace()
            store = JsonWorkspaceStore(tmp, workspace["id"]); store.initialize(workspace)
            run = new_record("discovery_run", workspace_id=workspace["id"], status="succeeded",
                requirement_refs=[], pack_refs=[], source_scope=[],
                started_at="2026-11-22T00:00:00Z", finished_at="2026-11-22T00:01:00Z",
                stages=[], counts={}, errors=[], parameters={}, radar_version="1.7.0").to_dict()
            store.append(run)
            self.assertEqual(store.get("discovery_run", run["id"])["status"], "succeeded")
            self.assertTrue((store.root / "runs" / run["id"] / "run.json").is_file())


if __name__ == "__main__":
    unittest.main()
