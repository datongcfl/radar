#!/usr/bin/env python3
"""Isolated PDF parser comparison; this is a benchmark tool, not Radar runtime code."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import platform
import re
import sys
import time
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

EXPECTED = {
    1: ["采购订单 PO-2026-001", "MAT-CABLE-001", "实收 100 米", "退回 6 米"],
    2: ["单据号", "物料编码", "GR-001", "MAT-CABLE-001", "100", "96", "4"],
    3: ["第一列：采购申请", "第二列：收货流程", "质检记录合格与拒收"],
}
EXPECTED_TABLE = [
    ["单据号", "物料编码", "实收数量", "合格数量", "拒收数量"],
    ["GR-001", "MAT-CABLE-001", "100", "96", "4"],
    ["GR-002", "MAT-SWITCH-002", "12", "12", "0"],
]


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def build_fixture() -> bytes:
    """Create a deterministic 3-page synthetic PDF with CJK, table and columns."""
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    stream = io.BytesIO()
    page_width, page_height = A4
    c = canvas.Canvas(stream, pagesize=A4, pageCompression=0)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(48, page_height - 52, "D03 Material Procurement Acceptance")
    c.setFont("STSong-Light", 11)
    c.drawString(48, page_height - 87, "采购订单 PO-2026-001 必须经过审批后才能收货。")
    c.drawString(48, page_height - 112, "材料编码 MAT-CABLE-001，订单数量 120 米。")
    c.drawString(48, page_height - 137, "收货单 GR-001：实收 100 米，合格 96 米，拒收 4 米。")
    c.drawString(48, page_height - 162, "退料单 RT-001：退回 6 米，必须引用原收货单明细。")
    c.showPage()

    c.setFont("Helvetica-Bold", 15)
    c.drawString(48, page_height - 52, "Receipt Detail Table")
    c.setFont("STSong-Light", 10)
    x0, y0 = 48, page_height - 102
    col_widths, row_height = [95, 145, 85, 85, 85], 32
    for row_index, row in enumerate(EXPECTED_TABLE):
        y = y0 - row_index * row_height
        x = x0
        for col_index, value in enumerate(row):
            c.rect(x, y - row_height, col_widths[col_index], row_height, stroke=1, fill=0)
            c.drawString(x + 5, y - 21, value)
            x += col_widths[col_index]
    c.showPage()

    c.setFont("Helvetica-Bold", 15)
    c.drawString(48, page_height - 52, "Two-column Workflow Notes")
    c.setFont("STSong-Light", 10)
    left = ["第一列：采购申请", "申请人提交材料需求", "项目经理审批需求", "采购员生成采购订单"]
    right = ["第二列：收货流程", "仓库核对送货单", "质检记录合格与拒收", "财务核对发票和凭证"]
    for index, value in enumerate(left):
        c.drawString(48, page_height - 92 - index * 28, value)
    for index, value in enumerate(right):
        c.drawString(315, page_height - 92 - index * 28, value)
    c.save()
    return stream.getvalue()


def parse_candidate(candidate: str, pdf_bytes: bytes) -> dict:
    backend = candidate.split("_")[0]
    table_result = None
    char_geometry = False
    start = time.perf_counter()

    if backend == "pypdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        page_count = len(reader.pages)
        version = importlib.metadata.version("pypdf")
    elif backend == "pdfplumber":
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
            page_count = len(pdf.pages)
            char_geometry = all(bool(page.chars) for page in pdf.pages)
            tables = pdf.pages[1].extract_tables(
                table_settings={"vertical_strategy": "lines", "horizontal_strategy": "lines"}
            )
            if tables:
                normalized_table = [[normalize(cell) for cell in row] for row in tables[0]]
                expected_table = [[normalize(cell) for cell in row] for row in EXPECTED_TABLE]
                table_result = {
                    "detected": True,
                    "rows": len(normalized_table),
                    "cells": sum(len(row) for row in normalized_table),
                    "exact_match": normalized_table == expected_table,
                }
            else:
                table_result = {"detected": False, "rows": 0, "cells": 0, "exact_match": False}
        version = importlib.metadata.version("pdfplumber")
    elif backend == "pypdfium2":
        import pypdfium2 as pdfium
        document = pdfium.PdfDocument(pdf_bytes)
        pages = []
        geometry_counts = []
        for page in document:
            text_page = page.get_textpage()
            pages.append(text_page.get_text_range() or "")
            geometry_counts.append(text_page.count_chars())
        page_count = len(document)
        char_geometry = all(count > 0 for count in geometry_counts)
        version = importlib.metadata.version("pypdfium2")
        table_result = {"api": "no table extraction API measured", "exact_match": None}
    else:
        raise ValueError("unsupported candidate: " + candidate)

    elapsed = time.perf_counter() - start
    page_results = []
    hits = total = 0
    for page_number, expected in EXPECTED.items():
        text = pages[page_number - 1] if page_number <= len(pages) else ""
        compact = normalize(text)
        phrase_hits = [phrase for phrase in expected if normalize(phrase) in compact]
        hits += len(phrase_hits)
        total += len(expected)
        page_results.append({
            "page": page_number,
            "expected_phrase_count": len(expected),
            "matched_phrase_count": len(phrase_hits),
            "matched_phrases": phrase_hits,
            "text_characters": len(text),
        })

    third_page = normalize(pages[2]) if len(pages) >= 3 else ""
    left_end = third_page.find(normalize("采购员生成采购订单"))
    right_start = third_page.find(normalize("第二列：收货流程"))
    return {
        "candidate": candidate,
        "package": backend,
        "package_version": version,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "fixture": {
            "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
            "size_bytes": len(pdf_bytes),
            "pages": page_count,
            "profile": ["Chinese text", "business identifiers", "ruled table", "two-column page"],
        },
        "parse_seconds": round(elapsed, 6),
        "expected_phrase_recall": round(hits / total, 4) if total else 0,
        "page_results": page_results,
        "locator_capabilities": {
            "page_number": page_count == 3,
            "character_geometry_available": char_geometry,
            "table_extraction": table_result,
        },
        "two_column_left_before_right": (
            left_end >= 0 and right_start >= 0 and left_end < right_start
        ),
        "two_column_extracted_text": pages[2] if len(pages) >= 3 else "",
        "scope_warning": (
            "Synthetic fixture only; this result is not a production accuracy benchmark. "
            "No OCR, scanned pages, real-world multi-column layouts, or adversarial PDFs."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    pdf_bytes = build_fixture()
    result = parse_candidate(args.candidate, pdf_bytes)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
