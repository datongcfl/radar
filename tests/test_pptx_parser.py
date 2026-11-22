import builtins, hashlib, importlib.util, io, unittest, zipfile
from unittest.mock import patch
from radar.capabilities import CapabilityContext
from radar.pptx_parser import PptxDocumentParserCapability

def minimal(presentation_xml=None):
    xml = presentation_xml or b'<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldIdLst/></p:presentation>'
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",b"<Types/>")
        z.writestr("ppt/presentation.xml",xml)
    return out.getvalue()

def sample():
    from pptx import Presentation
    from pptx.util import Inches
    p=Presentation()
    s=p.slides.add_slide(p.slide_layouts[6])
    sh=s.shapes.add_textbox(Inches(1),Inches(1),Inches(5),Inches(1))
    sh.text_frame.text="Quarterly review"
    sh.text_frame.add_paragraph().text="Revenue increased"
    t=s.shapes.add_table(2,2,Inches(1),Inches(2),Inches(5),Inches(2)).table
    t.cell(0,0).text="Metric"; t.cell(0,1).text="Value"
    t.cell(1,0).text="Orders"; t.cell(1,1).text="120"
    s.notes_slide.notes_text_frame.text="Discuss regional variance"
    out=io.BytesIO(); p.save(out); return out.getvalue()

class TestPptxPreflight(unittest.TestCase):
    def parse(self, data, filename="deck.pptx"):
        return PptxDocumentParserCapability().execute(CapabilityContext(
            operation="parse",inputs={"content":data,"uri":"https://example.test/"+filename,"filename":filename}))
    def test_missing_dependency(self):
        original=builtins.__import__
        def blocked(name,*a,**k):
            if name=="pptx": raise ImportError("missing")
            return original(name,*a,**k)
        with patch("builtins.__import__",side_effect=blocked):
            r=self.parse(minimal())
        self.assertEqual(r.status,"unavailable")
        self.assertEqual(r.warnings[0]["dependency"],"python-pptx")
    def test_dtd_rejected_before_import(self):
        r=self.parse(minimal(b'<!DOCTYPE x [<!ENTITY e "x">]><p:presentation/>'))
        self.assertEqual(r.error["code"],"pptx_unsafe_xml_declaration")
    def test_utf16_dtd_rejected_before_import(self):
        xml='<!DOCTYPE x [<!ENTITY e "x">]><p:presentation/>'.encode("utf-16")
        r=self.parse(minimal(xml))
        self.assertEqual(r.error["code"],"pptx_unsafe_xml_declaration")
    def test_input_slide_and_extension_limits(self):
        r=PptxDocumentParserCapability(max_bytes=20).execute(CapabilityContext(
            operation="parse",inputs={"content":minimal(),"uri":"file:///x","filename":"x.pptx"}))
        self.assertEqual(r.error["code"],"pptx_too_large")
        out=io.BytesIO()
        with zipfile.ZipFile(out,"w") as z:
            z.writestr("[Content_Types].xml",b"<Types/>")
            z.writestr("ppt/presentation.xml",b"<presentation/>")
            z.writestr("ppt/slides/slide1.xml",b"<s/>")
            z.writestr("ppt/slides/slide2.xml",b"<s/>")
        r=PptxDocumentParserCapability(max_slides=1).execute(CapabilityContext(
            operation="parse",inputs={"content":out.getvalue(),"uri":"file:///x","filename":"x.pptx"}))
        self.assertEqual(r.error["code"],"pptx_slide_limit_exceeded")
        self.assertEqual(self.parse(minimal(),"x.pptm").status,"skipped")
    def test_path_and_macro_rejected(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,"w") as z:
            z.writestr("[Content_Types].xml",b"<Types/>")
            z.writestr("ppt/presentation.xml",b"<presentation/>")
            z.writestr("../evil.xml",b"<x/>")
        self.assertEqual(self.parse(out.getvalue()).error["code"],"pptx_unsafe_archive_path")
        out=io.BytesIO()
        with zipfile.ZipFile(out,"w") as z:
            z.writestr("[Content_Types].xml",b"<Types/>")
            z.writestr("ppt/presentation.xml",b"<presentation/>")
            z.writestr("ppt/vbaProject.bin",b"macro")
        self.assertEqual(self.parse(out.getvalue()).error["code"],"pptx_macro_content_not_supported")

@unittest.skipUnless(importlib.util.find_spec("pptx"),"install optional python-pptx")
class TestPptxParser(unittest.TestCase):
    def parse(self,data):
        return PptxDocumentParserCapability().execute(CapabilityContext(
            operation="parse",inputs={"content":data,"uri":"https://example.test/deck.pptx","filename":"deck.pptx"}))
    def test_text_tables_notes_and_locators(self):
        data=sample(); r=self.parse(data)
        self.assertEqual(r.status,"succeeded")
        self.assertEqual(r.metadata["document_sha256"],hashlib.sha256(data).hexdigest())
        self.assertFalse(r.metadata["evidence_promoted"])
        text=next(x for x in r.records if x["fragment_type"]=="pptx_text_paragraph")
        self.assertEqual(text["text"],"Quarterly review")
        self.assertEqual(text["locator"]["slide_number"],1)
        cell=next(x for x in r.records if x["fragment_type"]=="pptx_table_cell")
        self.assertEqual(cell["text"],"Metric")
        self.assertEqual((cell["locator"]["row_index"],cell["locator"]["cell_index"]),(0,0))
        notes=next(x for x in r.records if x["fragment_type"]=="pptx_speaker_notes")
        self.assertIn("Discuss regional variance",notes["text"])
        self.assertTrue(all(x["record_type"]=="document_fragment" for x in r.records))

if __name__=="__main__":
    unittest.main()
