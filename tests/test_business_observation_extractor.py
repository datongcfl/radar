import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from radar.document_parser import extract_csv_document
from radar.discovery import new_record
from radar.discovery_store import JsonWorkspaceStore
from radar.discover import run_discovery
from radar.business_invariants import evaluate_business_invariants
from radar.business_observation_extractor import extract_table_observations


ASSET = "asset_receipts"


def receipt_invariant():
    return {
        "id":"receipt_quantity_balance","name":"Receipt balance",
        "operator":"sum_equals","scope":"purchase_receipt_item",
        "fields":["accepted_qty","rejected_qty"],"target_field":"received_qty",
        "field_aliases":{
            "accepted_qty":["accepted_qty","合格数量"],
            "rejected_qty":["rejected_qty","拒收数量"],
            "received_qty":["received_qty","received quantity","实收数量"],
        },
    }


def evidence_for_chunks(chunks, asset_id=ASSET):
    result = []
    for index, chunk in enumerate(chunks):
        locator = dict(chunk["locator"])
        locator["path"] = "receipts.csv"
        result.append({
            "id":"ev_cell_%d" % index, "asset_id":asset_id,
            "locator":locator,
            "metadata":{"verification":{"level":"document_text","runtime_observed":False}},
        })
    return result


class TestBusinessObservationExtractor(unittest.TestCase):
    def test_csv_aliases_produce_numeric_observation_with_cell_provenance(self):
        parsed = extract_csv_document(
            "合格数量,拒收数量,实收数量\n8,2,10\n")
        chunks = parsed["chunks"]
        for chunk in chunks:
            chunk["locator"]["path"] = "receipts.csv"
        evidence = evidence_for_chunks(chunks)
        result = extract_table_observations(
            [receipt_invariant()], chunks, evidence, ASSET)
        self.assertEqual(result["summary"]["observations"], 1)
        observation = result["observations"][0]
        self.assertEqual(observation["values"], {
            "accepted_qty":"8", "rejected_qty":"2", "received_qty":"10"})
        self.assertEqual(set(observation["field_provenance"]), {
            "accepted_qty","rejected_qty","received_qty"})
        evaluated = evaluate_business_invariants(
            [receipt_invariant()], {"schema_version":1,"observations":result["observations"]},
            evidence)
        self.assertEqual(evaluated["evaluations"][0]["outcome"], "pass")
        self.assertEqual(evaluated["evaluations"][0]["verification_level"], "static_candidate")

    def test_incomplete_rows_and_missing_cell_evidence_are_not_emitted(self):
        parsed = extract_csv_document(
            "accepted_qty,rejected_qty,received_qty\n8,2,10\n7,,7\n")
        chunks = parsed["chunks"]
        for chunk in chunks:
            chunk["locator"]["path"] = "receipts.csv"
        evidence = evidence_for_chunks(chunks)
        evidence = [item for item in evidence
                    if item["locator"].get("row") != 2 or item["locator"].get("column") != 3]
        result = extract_table_observations(
            [receipt_invariant()], chunks, evidence, ASSET)
        self.assertEqual(result["summary"]["observations"], 0)
        self.assertTrue(result["summary"]["skipped_rows"])

    def test_no_matching_aliases_produces_no_observation(self):
        parsed = extract_csv_document("description,qty\nCable,12\n")
        chunks = parsed["chunks"]
        for chunk in chunks:
            chunk["locator"]["path"] = "receipts.csv"
        result = extract_table_observations(
            [receipt_invariant()], chunks, evidence_for_chunks(chunks), ASSET)
        self.assertEqual(result["observations"], [])

    def test_english_header_whitespace_and_underscores_normalize_equally(self):
        parsed = extract_csv_document(
            "accepted qty,rejected_qty,received quantity\\n8,2,10\\n")
        chunks = parsed["chunks"]
        for chunk in chunks:
            chunk["locator"]["path"] = "receipts.csv"
        result = extract_table_observations(
            [receipt_invariant()], chunks, evidence_for_chunks(chunks), ASSET)
        self.assertEqual(result["summary"]["observations"], 1)
        self.assertEqual(result["observations"][0]["values"]["received_qty"], "10")

    def test_xlsx_sheet_and_cell_evidence_is_matched_exactly(self):
        chunks = [
            {"text":"accepted_qty","locator":{"path":"receipts.xlsx","sheet":"Receipts","cell":"A1"}},
            {"text":"rejected_qty","locator":{"path":"receipts.xlsx","sheet":"Receipts","cell":"B1"}},
            {"text":"received_qty","locator":{"path":"receipts.xlsx","sheet":"Receipts","cell":"C1"}},
            {"text":"5","locator":{"path":"receipts.xlsx","sheet":"Receipts","cell":"A2"}},
            {"text":"1","locator":{"path":"receipts.xlsx","sheet":"Receipts","cell":"B2"}},
            {"text":"6","locator":{"path":"receipts.xlsx","sheet":"Receipts","cell":"C2"}},
        ]
        evidence = [{
            "id":"ev_%d" % index,"asset_id":ASSET,
            "locator":dict(chunk["locator"]),
            "metadata":{"verification":{"level":"document_text","runtime_observed":False}},
        } for index, chunk in enumerate(chunks)]
        result = extract_table_observations([receipt_invariant()], chunks, evidence, ASSET)
        self.assertEqual(result["summary"]["observations"], 1)
        self.assertEqual(result["observations"][0]["values"]["received_qty"], "6")
        self.assertEqual(result["observations"][0]["field_provenance"]["received_qty"]["locator"]["cell"], "C2")

    def test_comma_formatted_numeric_values_are_normalized(self):
        parsed = extract_csv_document(
            'accepted_qty,rejected_qty,received_qty\n"1,000",200,"1,200"\n')
        chunks = parsed["chunks"]
        for chunk in chunks:
            chunk["locator"]["path"] = "receipts.csv"
        result = extract_table_observations(
            [receipt_invariant()], chunks, evidence_for_chunks(chunks), ASSET)
        self.assertEqual(result["observations"][0]["values"], {
            "accepted_qty":"1000", "rejected_qty":"200", "received_qty":"1200"})

    def test_cli_extracts_observations_from_workspace_evidence(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp) / "workspace"
            pack_path = root / "packs/weak-current/pack.json"
            run_discovery("ws_observation_cli",
                str(root / "examples/requirements/d03-material-procurement.json"),
                str(pack_path), str(root / "seeds/weak-current.json"),
                str(workspace_root))
            store = JsonWorkspaceStore(workspace_root, "ws_observation_cli")
            source = new_record("source", provider="filesystem",
                uri="file:///fixture", name="Observation fixture", access_status="public").to_dict()
            store.append(source)
            asset = new_record("asset", source_id=source["id"], asset_type="file",
                uri="file:///receipts.csv", title="receipts.csv", status="active",
                metadata={}).to_dict()
            store.append(asset)
            csv_path = Path(tmp) / "receipts.csv"
            csv_path.write_text("accepted_qty,rejected_qty,received_qty\n8,2,10\n",
                                encoding="utf-8")
            parsed = extract_csv_document(csv_path.read_text(encoding="utf-8"))
            for chunk in parsed["chunks"]:
                locator = dict(chunk["locator"])
                locator["path"] = "receipts.csv"
                evidence = new_record("evidence", workspace_id="ws_observation_cli",
                    asset_id=asset["id"], evidence_kind="documentation",
                    statement=chunk["text"], locator=locator,
                    captured_at="2026-11-22T00:00:00Z",
                    verification_status="source_confirmed",
                    metadata={"verification":{"level":"document_text","runtime_observed":False}}).to_dict()
                store.append(evidence)
            output = Path(tmp) / "observations.json"
            proc = subprocess.run([sys.executable, "-m", "radar", "extract-observations",
                "--workspace", "ws_observation_cli", "--workspace-root", str(workspace_root),
                "--pack", str(pack_path),
                "--business-model", str(root / "packs/weak-current/business-model.json"),
                "--asset-id", asset["id"], "--input", str(csv_path),
                "--source-path", "receipts.csv", "--out", str(output)],
                cwd=str(root), capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["summary"]["observations"], 1)
            self.assertEqual(result["observations"][0]["values"]["received_qty"], "10")


if __name__ == "__main__":
    unittest.main()
