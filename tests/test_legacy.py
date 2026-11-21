import json
import tempfile
import unittest
from pathlib import Path

from radar.legacy import convert_legacy_sources, read_legacy_sources
from radar.model import load_pack


class TestLegacyConversion(unittest.TestCase):
    def test_seed_reader_uses_existing_compatibility_loader(self):
        root = Path(__file__).resolve().parents[1]
        pack = load_pack(root / "packs" / "weak-current" / "pack.json")
        rows = read_legacy_sources(str(root / "seeds" / "weak-current.json"), pack)
        self.assertGreater(len(rows), 0)
        self.assertIn("id", rows[0])

    def test_legacy_source_becomes_provider_source_and_repository_asset(self):
        rows = [{
            "id": "SRC-001", "url": "https://github.com/acme/app",
            "platform": "github", "title": "Acme App", "artifact_type": "code",
            "access_status": "public", "covers": ["M01"], "evidence_level": "real_artifact",
            "license": "MIT", "license_status": "needs_review", "status": "selected",
            "quotes": ["A quote without a line locator"],
        }]
        converted = convert_legacy_sources(rows, "ws_demo")
        self.assertEqual(len(converted["sources"]), 1)
        self.assertEqual(converted["sources"][0]["uri"], "https://github.com")
        self.assertEqual(converted["assets"][0]["asset_type"], "repository")
        self.assertEqual(converted["assets"][0]["metadata"]["legacy_covers"], ["M01"])
        self.assertEqual(len(converted["pending_quotes"]), 1)
        self.assertEqual(converted["evidence"], [])

    def test_locatable_legacy_quote_can_become_evidence(self):
        rows = [{
            "id": "SRC-002", "url": "https://github.com/acme/app",
            "platform": "github", "title": "Acme App", "artifact_type": "code",
            "access_status": "public", "covers": ["M01"], "evidence_level": "real_artifact",
            "license": "MIT", "license_status": "clear", "status": "selected",
            "quote_verified": "true", "quote_verified_by": "web", "quote_verified_this_run": True,
            "quotes": [{"text": "create_purchase_order()", "locator": {"path": "purchase.py", "line_start": 12}}],
        }]
        converted = convert_legacy_sources(rows, "ws_demo")
        self.assertEqual(len(converted["evidence"]), 1)
        evidence = converted["evidence"][0]
        self.assertEqual(evidence["verification_status"], "source_confirmed")
        self.assertEqual(evidence["locator"]["line_start"], 12)

    def test_conversion_ids_are_deterministic(self):
        rows = [{"id":"SRC-003","url":"https://github.com/acme/app","platform":"github",
                 "title":"Acme App","artifact_type":"code","access_status":"public",
                 "covers":["M01"],"evidence_level":"real_artifact","license":"MIT",
                 "license_status":"clear","status":"selected","quotes":[]}]
        a = convert_legacy_sources(rows, "ws_demo", captured_at="2026-11-22T00:00:00Z")
        b = convert_legacy_sources(rows, "ws_demo", captured_at="2026-11-22T00:00:00Z")
        self.assertEqual(a["sources"][0]["id"], b["sources"][0]["id"])
        self.assertEqual(a["assets"][0]["id"], b["assets"][0]["id"])

    def test_missing_locator_is_never_promoted_to_evidence(self):
        rows = [{"id":"SRC-004","url":"https://example.com/spec.pdf","platform":"web",
                 "title":"Spec","artifact_type":"docs","access_status":"public",
                 "covers":["M01"],"evidence_level":"docs","license":"unknown",
                 "license_status":"needs_review","status":"needs_review",
                 "quotes":[{"text":"A useful quote"}]}]
        converted = convert_legacy_sources(rows, "ws_demo")
        self.assertEqual(converted["evidence"], [])
        self.assertEqual(converted["pending_quotes"][0]["reason"], "missing_precise_locator")


if __name__ == "__main__":
    unittest.main()


    def test_stale_seed_verification_is_not_promoted(self):
        rows = [{
            "id": "SRC-005", "url": "https://github.com/acme/app",
            "platform": "github", "title": "Acme App", "artifact_type": "code",
            "access_status": "public", "covers": ["M01"], "evidence_level": "real_artifact",
            "license": "MIT", "license_status": "clear", "status": "selected",
            "quote_verified": "true", "quote_verified_by": "web",
            "quote_verified_this_run": False,
            "quotes": [{"text": "x()", "locator": {"path": "app.py", "line_start": 2}}],
        }]
        converted = convert_legacy_sources(rows, "ws_demo", captured_at="2026-11-22T00:00:00Z")
        self.assertEqual(converted["evidence"][0]["verification_status"], "unverified")
