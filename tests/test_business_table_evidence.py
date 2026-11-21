import unittest

from radar.business_table_evidence import select_required_table_chunks


class TestBusinessTableEvidence(unittest.TestCase):
    def setUp(self):
        self.invariant = {
            "id":"receipt_quantity_balance",
            "operator":"sum_equals",
            "fields":["accepted_qty","rejected_qty"],
            "target_field":"received_qty",
            "field_aliases":{
                "accepted_qty":["accepted_qty","合格数量"],
                "rejected_qty":["rejected_qty","拒收数量"],
                "received_qty":["received_qty","实收数量"],
            },
        }

    def test_csv_selects_header_and_data_cells_under_declared_headers(self):
        chunks = [
            {"text":"note","locator":{"path":"receipts.csv","row":1,"column":1}},
            {"text":"合格数量","locator":{"path":"receipts.csv","row":1,"column":2}},
            {"text":"拒收数量","locator":{"path":"receipts.csv","row":1,"column":3}},
            {"text":"实收数量","locator":{"path":"receipts.csv","row":1,"column":4}},
            {"text":"receipt-1","locator":{"path":"receipts.csv","row":2,"column":1}},
            {"text":"8","locator":{"path":"receipts.csv","row":2,"column":2}},
            {"text":"2","locator":{"path":"receipts.csv","row":2,"column":3}},
            {"text":"10","locator":{"path":"receipts.csv","row":2,"column":4}},
        ]
        selected = select_required_table_chunks([self.invariant], chunks)
        self.assertEqual([item["text"] for item in selected],
                         ["合格数量","拒收数量","实收数量","8","2","10"])

    def test_xlsx_uses_sheet_and_exact_header_aliases(self):
        chunks = [
            {"text":"accepted_qty","locator":{"path":"receipt.xlsx","sheet":"Receipts","cell":"A1"}},
            {"text":"rejected_qty","locator":{"path":"receipt.xlsx","sheet":"Receipts","cell":"B1"}},
            {"text":"received_qty","locator":{"path":"receipt.xlsx","sheet":"Receipts","cell":"C1"}},
            {"text":"5","locator":{"path":"receipt.xlsx","sheet":"Receipts","cell":"A2"}},
            {"text":"1","locator":{"path":"receipt.xlsx","sheet":"Receipts","cell":"B2"}},
            {"text":"6","locator":{"path":"receipt.xlsx","sheet":"Receipts","cell":"C2"}},
        ]
        selected = select_required_table_chunks([self.invariant], chunks)
        self.assertEqual([item["locator"]["cell"] for item in selected],
                         ["A1","B1","C1","A2","B2","C2"])

    def test_optional_scope_identifier_cells_are_selected(self):
        invariant = dict(self.invariant)
        invariant["scope_fields"] = ["purchase_order_id"]
        invariant["scope_aliases"] = {
            "purchase_order_id":["purchase_order_id","采购订单号"]}
        chunks = [
            {"text":"采购订单号","locator":{"path":"receipts.csv","row":1,"column":1}},
            {"text":"accepted_qty","locator":{"path":"receipts.csv","row":1,"column":2}},
            {"text":"rejected_qty","locator":{"path":"receipts.csv","row":1,"column":3}},
            {"text":"received_qty","locator":{"path":"receipts.csv","row":1,"column":4}},
            {"text":"PO-42","locator":{"path":"receipts.csv","row":2,"column":1}},
            {"text":"8","locator":{"path":"receipts.csv","row":2,"column":2}},
            {"text":"2","locator":{"path":"receipts.csv","row":2,"column":3}},
            {"text":"10","locator":{"path":"receipts.csv","row":2,"column":4}},
        ]
        selected = select_required_table_chunks([invariant], chunks)
        self.assertEqual([item["text"] for item in selected],
                         ["采购订单号","accepted_qty","rejected_qty","received_qty",
                          "PO-42","8","2","10"])

    def test_unrelated_or_incomplete_tables_produce_no_selected_cells(self):
        chunks = [
            {"text":"description","locator":{"path":"other.csv","row":1,"column":1}},
            {"text":"qty","locator":{"path":"other.csv","row":1,"column":2}},
            {"text":"cable","locator":{"path":"other.csv","row":2,"column":1}},
            {"text":"12","locator":{"path":"other.csv","row":2,"column":2}},
        ]
        self.assertEqual(select_required_table_chunks([self.invariant], chunks), [])

    def test_empty_values_are_not_selected(self):
        chunks = [
            {"text":"accepted_qty","locator":{"path":"receipts.csv","row":1,"column":1}},
            {"text":"rejected_qty","locator":{"path":"receipts.csv","row":1,"column":2}},
            {"text":"received_qty","locator":{"path":"receipts.csv","row":1,"column":3}},
            {"text":"8","locator":{"path":"receipts.csv","row":2,"column":1}},
            {"text":"","locator":{"path":"receipts.csv","row":2,"column":2}},
            {"text":"8","locator":{"path":"receipts.csv","row":2,"column":3}},
        ]
        self.assertEqual(select_required_table_chunks([self.invariant], chunks), [
            chunks[0], chunks[1], chunks[2], chunks[3], chunks[5]])


if __name__ == "__main__":
    unittest.main()
