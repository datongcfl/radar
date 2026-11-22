import unittest

from radar.xml_safety import contains_forbidden_xml_declarations


class TestXmlSafety(unittest.TestCase):
    def test_rejects_dtd_and_entity_declarations_across_supported_encodings(self):
        xml = '<!DOCTYPE root [<!ENTITY payload "unsafe">]><root/>'
        encodings = ("utf-8", "utf-16", "utf-16-le", "utf-16-be",
                     "utf-32", "utf-32-le", "utf-32-be")
        for encoding in encodings:
            with self.subTest(encoding=encoding):
                self.assertTrue(contains_forbidden_xml_declarations(xml.encode(encoding)))

    def test_accepts_safe_xml_across_supported_encodings(self):
        xml = "<root><value>safe</value></root>"
        encodings = ("utf-8", "utf-16", "utf-16-le", "utf-16-be",
                     "utf-32", "utf-32-le", "utf-32-be")
        for encoding in encodings:
            with self.subTest(encoding=encoding):
                self.assertFalse(contains_forbidden_xml_declarations(xml.encode(encoding)))

    def test_invalid_encoding_fails_closed(self):
        self.assertTrue(contains_forbidden_xml_declarations(b"\xff\xfe\x00"))


if __name__ == "__main__":
    unittest.main()
