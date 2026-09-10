"""Bounded, non-persistent PDF and DOCX text extraction for Knowledge preview."""

from __future__ import annotations

import hashlib
import io
import multiprocessing
import posixpath
import re
import time
import unicodedata
import zipfile
from typing import Any
from xml.etree import ElementTree

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_EXTRACTED_BYTES = 512 * 1024
MAX_PARSE_SECONDS = 10
MAX_PDF_PAGES = 200
MAX_DOCX_ENTRIES = 256
MAX_DOCX_EXPANDED_BYTES = 16 * 1024 * 1024
MAX_DOCX_EXPANSION_RATIO = 100
MAX_PARAGRAPHS = 512
MAX_PARAGRAPH_BYTES = 4 * 1024
PARSER_VERSION = "KNOWLEDGE_DOCUMENT_PARSER_V1"

_PDF_MEDIA_TYPES = {"application/pdf"}
_DOCX_MEDIA_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/zip",
    "application/octet-stream",
}
_WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"


class KnowledgeDocumentParseFailure(ValueError):
    """Stable parsing failure that is safe to expose as a reason code."""


def _failure(code: str) -> KnowledgeDocumentParseFailure:
    return KnowledgeDocumentParseFailure(code)


def _file_name(value: object) -> str:
    if not isinstance(value, str):
        raise _failure("DOCUMENT_FILENAME_REQUIRED")
    normalized = unicodedata.normalize("NFC", value).strip()
    if (
        not normalized
        or len(normalized.encode("utf-8")) > 500
        or any(unicodedata.category(char) == "Cc" for char in normalized)
        or normalized != posixpath.basename(normalized.replace("\\", "/"))
    ):
        raise _failure("INVALID_DOCUMENT_FILENAME")
    return normalized


def _media_type(value: object) -> str:
    if not isinstance(value, str):
        return "application/octet-stream"
    return value.partition(";")[0].strip().lower() or "application/octet-stream"


def _normalize_paragraph(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).replace("\u00a0", " ").strip()
    if any(
        unicodedata.category(char) == "Cc" and char not in "\n\t" for char in normalized
    ):
        raise _failure("INVALID_EXTRACTED_CONTROL_CHARACTER")
    if len(normalized.encode("utf-8")) > MAX_PARAGRAPH_BYTES:
        raise _failure("PARSED_PARAGRAPH_LIMIT_EXCEEDED")
    return normalized


def _finish(
    *,
    file_name: str,
    media_type: str,
    document_format: str,
    data: bytes,
    segments: list[dict[str, Any]],
    limitations: list[str],
) -> dict[str, Any]:
    if not segments:
        raise _failure("EMPTY_EXTRACTED_TEXT")
    if len(segments) > MAX_PARAGRAPHS:
        raise _failure("PARSED_PARAGRAPH_COUNT_EXCEEDED")
    content = "\n\n".join(segment["content"] for segment in segments)
    if len(content.encode("utf-8")) > MAX_EXTRACTED_BYTES:
        raise _failure("EXTRACTED_TEXT_LIMIT_EXCEEDED")
    return {
        "fileName": file_name,
        "declaredMediaType": media_type,
        "detectedFormat": document_format,
        "detectedMediaType": (
            "application/pdf"
            if document_format == "PDF"
            else (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            )
        ),
        "sizeBytes": len(data),
        "content": content,
        "contentDigest": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "segments": segments,
        "parserVersion": PARSER_VERSION,
        "originalFilePersisted": False,
        "limitations": limitations,
    }


def _parse_pdf(file_name: str, media_type: str, data: bytes) -> dict[str, Any]:
    if not data.startswith(b"%PDF-"):
        raise _failure("DOCUMENT_TYPE_MISMATCH")
    if not file_name.casefold().endswith(".pdf") or media_type not in (
        _PDF_MEDIA_TYPES | {"application/octet-stream"}
    ):
        raise _failure("DOCUMENT_TYPE_MISMATCH")
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise _failure("PASSWORD_PROTECTED_DOCUMENT_UNSUPPORTED")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise _failure("PDF_PAGE_LIMIT_EXCEEDED")
        segments: list[dict[str, Any]] = []
        for page_number, page in enumerate(reader.pages, 1):
            extracted = page.extract_text() or ""
            paragraphs = [
                _normalize_paragraph(value)
                for value in re.split(r"\n\s*\n|\n", extracted)
                if value.strip()
            ]
            for paragraph_number, paragraph in enumerate(paragraphs, 1):
                segments.append(
                    {
                        "content": paragraph,
                        "location": {
                            "pageNumber": page_number,
                            "paragraphNumber": paragraph_number,
                        },
                    }
                )
    except KnowledgeDocumentParseFailure:
        raise
    except (PdfReadError, KeyError, TypeError, ValueError, OSError) as exc:
        raise _failure("CORRUPT_OR_UNSUPPORTED_PDF") from exc
    return _finish(
        file_name=file_name,
        media_type=media_type,
        document_format="PDF",
        data=data,
        segments=segments,
        limitations=[
            "仅提取 PDF 文字层。扫描图片和 OCR 不受支持",
            "图片、表单、批注和复杂视觉布局不进入知识正文",
        ],
    )


def _safe_docx_members(archive: zipfile.ZipFile) -> tuple[list[zipfile.ZipInfo], int]:
    members = archive.infolist()
    if len(members) > MAX_DOCX_ENTRIES:
        raise _failure("DOCX_ENTRY_LIMIT_EXCEEDED")
    expanded = 0
    for member in members:
        normalized = posixpath.normpath(member.filename)
        if normalized.startswith("../") or normalized.startswith("/"):
            raise _failure("UNSAFE_DOCX_PACKAGE")
        expanded += member.file_size
        if expanded > MAX_DOCX_EXPANDED_BYTES:
            raise _failure("DOCX_EXPANDED_SIZE_LIMIT_EXCEEDED")
        compressed = max(1, member.compress_size)
        if member.file_size / compressed > MAX_DOCX_EXPANSION_RATIO:
            raise _failure("DOCX_EXPANSION_RATIO_EXCEEDED")
    return members, expanded


def _parse_docx(file_name: str, media_type: str, data: bytes) -> dict[str, Any]:
    if (
        not file_name.casefold().endswith(".docx")
        or media_type not in _DOCX_MEDIA_TYPES
    ):
        raise _failure("DOCUMENT_TYPE_MISMATCH")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members, _ = _safe_docx_members(archive)
            names = {member.filename for member in members}
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise _failure("DOCUMENT_TYPE_MISMATCH")
            content_types = archive.read("[Content_Types].xml")
            lowered_types = content_types.lower()
            if b"macroenabled" in lowered_types or any(
                name.casefold().endswith("vbaproject.bin") for name in names
            ):
                raise _failure("MACRO_ENABLED_DOCUMENT_UNSUPPORTED")
            if any(name.startswith("word/embeddings/") for name in names):
                raise _failure("EMBEDDED_PROGRAM_UNSUPPORTED")
            root = ElementTree.fromstring(archive.read("word/document.xml"))
            external_links = False
            relationships = "word/_rels/document.xml.rels"
            if relationships in names:
                relation_root = ElementTree.fromstring(archive.read(relationships))
                external_links = any(
                    relation.get("TargetMode") == "External"
                    for relation in relation_root.findall(
                        f"{{{_RELATIONSHIP_NAMESPACE}}}Relationship"
                    )
                )
            segments = []
            for paragraph_number, paragraph in enumerate(
                root.iter(f"{{{_WORD_NAMESPACE}}}p"), 1
            ):
                text = "".join(
                    node.text or ""
                    for node in paragraph.iter(f"{{{_WORD_NAMESPACE}}}t")
                )
                normalized = _normalize_paragraph(text)
                if normalized:
                    segments.append(
                        {
                            "content": normalized,
                            "location": {"paragraphNumber": paragraph_number},
                        }
                    )
    except KnowledgeDocumentParseFailure:
        raise
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError, OSError) as exc:
        raise _failure("CORRUPT_OR_UNSUPPORTED_DOCX") from exc
    limitations = [
        "仅提取 DOCX 主文档文字。图片、页眉页脚和复杂表格布局不受支持",
        "不执行宏、嵌入程序。不访问文档外链",
    ]
    if external_links:
        limitations.append("检测到外部链接。解析期间未访问这些链接")
    return _finish(
        file_name=file_name,
        media_type=media_type,
        document_format="DOCX",
        data=data,
        segments=segments,
        limitations=limitations,
    )


def _parse(file_name: object, media_type: object, data: object) -> dict[str, Any]:
    resolved_name = _file_name(file_name)
    resolved_type = _media_type(media_type)
    if not isinstance(data, bytes) or not data:
        raise _failure("EMPTY_DOCUMENT_UPLOAD")
    if len(data) > MAX_UPLOAD_BYTES:
        raise _failure("DOCUMENT_UPLOAD_LIMIT_EXCEEDED")
    if data.startswith(b"%PDF-"):
        return _parse_pdf(resolved_name, resolved_type, data)
    if data.startswith(b"PK\x03\x04"):
        return _parse_docx(resolved_name, resolved_type, data)
    raise _failure("UNSUPPORTED_DOCUMENT_TYPE")


def _worker(
    connection: Any, file_name: object, media_type: object, data: object
) -> None:
    try:
        connection.send((True, _parse(file_name, media_type, data)))
    except KnowledgeDocumentParseFailure as exc:
        connection.send((False, str(exc)))
    except Exception:
        connection.send((False, "DOCUMENT_PARSE_FAILED"))
    finally:
        connection.close()


def parse_document(
    file_name: object,
    media_type: object,
    data: object,
    *,
    timeout_seconds: float = MAX_PARSE_SECONDS,
) -> dict[str, Any]:
    """Parse in a disposable process so a time limit can be enforced."""

    if not isinstance(data, bytes) or len(data) > MAX_UPLOAD_BYTES:
        return _parse(file_name, media_type, data)
    started = time.monotonic()
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_worker, args=(child, file_name, media_type, data))
    process.start()
    child.close()
    try:
        if not parent.poll(timeout_seconds):
            process.terminate()
            process.join(timeout=1)
            raise _failure("DOCUMENT_PARSE_TIMEOUT")
        success, value = parent.recv()
    except EOFError as exc:
        raise _failure("DOCUMENT_PARSE_FAILED") from exc
    finally:
        parent.close()
        if process.is_alive():
            process.terminate()
        process.join(timeout=1)
    if not success:
        raise _failure(value)
    value["parseDurationMs"] = max(0, round((time.monotonic() - started) * 1000))
    value["parseTimeLimitSeconds"] = timeout_seconds
    return value
