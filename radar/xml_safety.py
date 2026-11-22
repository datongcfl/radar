"""Encoding-aware XML declaration checks for untrusted Office package parts."""
from __future__ import annotations


def contains_forbidden_xml_declarations(data: bytes) -> bool:
    """Detect DTD/entity declarations in UTF-8, UTF-16, or UTF-32 XML.

    Office Open XML permits UTF-8 and UTF-16 in practice. UTF-32 is handled
    defensively as well. Invalid or unsupported encodings fail closed.
    """
    if not isinstance(data, bytes):
        return True

    try:
        if data.startswith(b"\x00\x00\xfe\xff") or data.startswith(b"\xff\xfe\x00\x00"):
            text = data.decode("utf-32")
        elif data.startswith(b"\xfe\xff") or data.startswith(b"\xff\xfe"):
            text = data.decode("utf-16")
        elif data.startswith(b"\x00\x00\x00<"):
            text = data.decode("utf-32-be")
        elif data.startswith(b"<\x00\x00\x00"):
            text = data.decode("utf-32-le")
        elif data.startswith(b"\x00<"):
            text = data.decode("utf-16-be")
        elif data.startswith(b"<\x00"):
            text = data.decode("utf-16-le")
        else:
            text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return True

    upper = text.upper()
    return "<!DOCTYPE" in upper or "<!ENTITY" in upper
