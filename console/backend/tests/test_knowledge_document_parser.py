import io
import zipfile

import pytest
from agent_console.knowledge_document_parser import (
    KnowledgeDocumentParseFailure,
    _parse,
    parse_document,
)


def pdf_bytes(objects: list[bytes]) -> bytes:
    result = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, value in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f"{index} 0 obj\n".encode() + value + b"\nendobj\n")
    xref = len(result)
    result.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        result.extend(f"{offset:010} 00000 n \n".encode())
    result.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode()
    )
    return bytes(result)


def text_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    return pdf_bytes(
        [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
            ),
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]
    )


def chinese_text_pdf() -> bytes:
    content = b"BT /F1 12 Tf 72 720 Td <00010002000300040005000600070008> Tj ET"
    cmap = b"""/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
/CMapName /Adobe-Identity-UCS def
/CMapType 2 def
1 begincodespacerange
<0000> <FFFF>
endcodespacerange
8 beginbfchar
<0001> <4F9B>
<0002> <5E94>
<0003> <5546>
<0004> <7F3A>
<0005> <9677>
<0006> <62A5>
<0007> <544A>
<0008> <3002>
endbfchar
endcmap
CMapName currentdict /CMap defineresource pop
end
end"""
    return pdf_bytes(
        [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
            ),
            f"<< /Length {len(content)} >>\nstream\n".encode()
            + content
            + b"\nendstream",
            (
                b"<< /Type /Font /Subtype /Type0 /BaseFont /NotoSansCJK "
                b"/Encoding /Identity-H /DescendantFonts [6 0 R] /ToUnicode 7 0 R >>"
            ),
            (
                b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /NotoSansCJK "
                b"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) "
                b"/Supplement 0 >> /FontDescriptor 8 0 R /CIDToGIDMap /Identity >>"
            ),
            f"<< /Length {len(cmap)} >>\nstream\n".encode() + cmap + b"\nendstream",
            (
                b"<< /Type /FontDescriptor /FontName /NotoSansCJK /Flags 4 "
                b"/FontBBox [0 -200 1000 900] /ItalicAngle 0 /Ascent 880 "
                b"/Descent -120 /CapHeight 700 /StemV 80 >>"
            ),
        ]
    )


def docx(paragraphs: list[str], *, macro: bool = False) -> bytes:
    content_type = (
        "application/vnd.ms-word.document.macroEnabled.main+xml"
        if macro
        else (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document.main+xml"
        )
    )
    body = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{value}</w:t></w:r></w:p>'
        for value in paragraphs
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            (
                '<?xml version="1.0"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Override PartName="/word/document.xml" '
                f'ContentType="{content_type}"/>'
                "</Types>"
            ),
        )
        archive.writestr(
            "word/document.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/'
                f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>'
            ),
        )
    return output.getvalue()


def test_docx_extracts_chinese_paragraphs_and_does_not_persist_original():
    result = parse_document(
        "供应商纠正措施.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        docx(["供应商缺陷必须隔离。", "已知答案: 七十二小时内提交报告。"]),
    )
    assert result["detectedFormat"] == "DOCX"
    assert result["originalFilePersisted"] is False
    assert result["segments"][1] == {
        "content": "已知答案: 七十二小时内提交报告。",
        "location": {"paragraphNumber": 2},
    }
    assert "七十二小时" in result["content"]
    assert result["parseTimeLimitSeconds"] == 10


def test_pdf_requires_signature_and_reports_real_page_location():
    result = _parse("procedure.pdf", "application/pdf", text_pdf("Answer is 42."))
    assert result["content"] == "Answer is 42."
    assert result["segments"][0]["location"] == {
        "pageNumber": 1,
        "paragraphNumber": 1,
    }
    with pytest.raises(KnowledgeDocumentParseFailure, match="DOCUMENT_TYPE_MISMATCH"):
        _parse("renamed.docx", "application/pdf", text_pdf("not docx"))


def test_pdf_extracts_real_chinese_tounicode_bytes():
    result = _parse("供应商报告.pdf", "application/pdf", chinese_text_pdf())

    assert result["content"] == "供应商缺陷报告。"
    assert result["segments"] == [
        {
            "content": "供应商缺陷报告。",
            "location": {"pageNumber": 1, "paragraphNumber": 1},
        }
    ]


@pytest.mark.parametrize(
    ("name", "media_type", "payload", "reason"),
    [
        ("legacy.doc", "application/msword", b"legacy", "UNSUPPORTED_DOCUMENT_TYPE"),
        ("scan.pdf", "application/pdf", text_pdf(""), "EMPTY_EXTRACTED_TEXT"),
        (
            "macro.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            docx(["unsafe"], macro=True),
            "MACRO_ENABLED_DOCUMENT_UNSUPPORTED",
        ),
        (
            "broken.docx",
            "application/zip",
            b"PK\x03\x04broken",
            "CORRUPT_OR_UNSUPPORTED_DOCX",
        ),
    ],
)
def test_unsupported_empty_macro_and_corrupt_files_are_distinct(
    name: str, media_type: str, payload: bytes, reason: str
):
    with pytest.raises(KnowledgeDocumentParseFailure, match=reason):
        _parse(name, media_type, payload)
