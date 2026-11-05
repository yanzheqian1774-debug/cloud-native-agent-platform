"""Bounded source-file parsing and pure resource-draft import preflight."""

import csv
import io
import json
import posixpath
import zipfile
from xml.etree import ElementTree as ET

from pydantic import ValidationError

from .resource_use_domain import canonical_digest
from .skill_mcp_schemas import ResourceContent
from .skill_mcp_service import SkillMcpFailure
from .workbench_owner_authorization import WorkbenchOwnerError

MAX_FILE = 10 * 1024 * 1024
MAX_ROWS = 100
HEADERS = {
    "name": "name",
    "名称": "name",
    "description": "description",
    "用途": "description",
    "业务用途": "description",
    "capabilities": "capabilities",
    "能力": "capabilities",
    "instructions": "instructions",
    "说明": "instructions",
    "endpoint": "endpoint",
    "服务地址": "endpoint",
    "secretReference": "secretReference",
    "凭据引用": "secretReference",
    "contentJson": "contentJson",
    "配置JSON": "contentJson",
}


def xml(data):
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise WorkbenchOwnerError("IMPORT_XML_DECLARATION_DENIED", 422)
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise WorkbenchOwnerError("IMPORT_XLSX_XML_INVALID", 422) from exc


def xlsx_rows(raw):
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if len({i.filename for i in infos}) != len(infos):
                raise WorkbenchOwnerError("IMPORT_XLSX_DUPLICATE_ENTRY", 422)
            if (
                len(infos) > 256
                or sum(i.file_size for i in infos) > 20 * 1024 * 1024
                or any(
                    i.file_size > 5 * 1024 * 1024
                    or i.flag_bits & 1
                    or i.filename.startswith("/")
                    or ".." in i.filename.split("/")
                    or i.filename.lower().endswith(".bin")
                    for i in infos
                )
            ):
                raise WorkbenchOwnerError("IMPORT_XLSX_BOUNDARY_DENIED", 422)
            for info in infos:
                if info.filename.endswith(".rels") and any(
                    n.attrib.get("TargetMode") == "External"
                    for n in xml(archive.read(info)).iter()
                ):
                    raise WorkbenchOwnerError("IMPORT_EXTERNAL_LINK_DENIED", 422)
            workbook = xml(archive.read("xl/workbook.xml"))
            sheets = [n for n in workbook.iter() if n.tag.endswith("}sheet")]
            if not sheets:
                raise WorkbenchOwnerError("IMPORT_SHEET_REQUIRED", 422)
            relid = sheets[0].attrib.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            relations = xml(archive.read("xl/_rels/workbook.xml.rels"))
            target = next(
                (
                    n.attrib.get("Target", "")
                    for n in relations
                    if n.attrib.get("Id") == relid
                ),
                "",
            )
            path = posixpath.normpath(
                target.lstrip("/")
                if target.startswith("/xl/")
                else posixpath.join("xl", target)
            )
            if not path.startswith("xl/worksheets/"):
                raise WorkbenchOwnerError("IMPORT_SHEET_TARGET_DENIED", 422)
            shared = []
            if "xl/sharedStrings.xml" in archive.namelist():
                shared = [
                    "".join(t.text or "" for t in n.iter() if t.tag.endswith("}t"))
                    for n in xml(archive.read("xl/sharedStrings.xml"))
                ]
            rows = []
            for row in xml(archive.read(path)).iter():
                if not row.tag.endswith("}row"):
                    continue
                values = {}
                for cell in row:
                    if not cell.tag.endswith("}c"):
                        continue
                    if any(n.tag.endswith("}f") for n in cell):
                        raise WorkbenchOwnerError("IMPORT_FORMULA_DENIED", 422)
                    reference = cell.attrib.get("r", "")
                    letters = "".join(c for c in reference if c.isalpha())
                    column = 0
                    for char in letters.upper():
                        column = column * 26 + ord(char) - 64
                    if not 1 <= column <= 16:
                        raise WorkbenchOwnerError("IMPORT_COLUMN_LIMIT", 422)
                    kind = cell.attrib.get("t")
                    value = next(
                        (n.text or "" for n in cell if n.tag.endswith("}v")), ""
                    )
                    if kind == "s":
                        value = shared[int(value)]
                    elif kind == "inlineStr":
                        value = "".join(
                            n.text or "" for n in cell.iter() if n.tag.endswith("}t")
                        )
                    values[column - 1] = value
                if values:
                    rows.append([values.get(i, "") for i in range(max(values) + 1)])
                    if len(rows) > MAX_ROWS + 1:
                        raise WorkbenchOwnerError("IMPORT_ROW_LIMIT", 422)
            return rows
    except WorkbenchOwnerError:
        raise
    except (zipfile.BadZipFile, KeyError, ValueError, IndexError, RuntimeError) as exc:
        raise WorkbenchOwnerError("IMPORT_XLSX_INVALID", 422) from exc


def decode_file(filename, raw, kind):
    if not raw or len(raw) > MAX_FILE:
        raise WorkbenchOwnerError("IMPORT_FILE_SIZE_INVALID", 422)
    suffix = filename.rsplit(".", 1)[-1].lower()
    if suffix == "json":
        try:
            value = json.loads(raw.decode("utf-8-sig"))
            return value if isinstance(value, list) else [value]
        except (UnicodeError, ValueError, RecursionError) as exc:
            raise WorkbenchOwnerError("IMPORT_JSON_INVALID", 422) from exc
    if suffix == "csv":
        try:
            csv.field_size_limit(200000)
            rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), strict=True))
        except (UnicodeError, csv.Error) as exc:
            raise WorkbenchOwnerError("IMPORT_CSV_INVALID", 422) from exc
    elif suffix == "xlsx":
        rows = xlsx_rows(raw)
    else:
        raise WorkbenchOwnerError("IMPORT_FORMAT_UNSUPPORTED", 422)
    rows = [r for r in rows if any(str(v).strip() for v in r)]
    if not rows or len(rows) > MAX_ROWS + 1:
        raise WorkbenchOwnerError("IMPORT_ROW_LIMIT", 422)
    try:
        columns = [HEADERS[v.strip()] for v in rows[0]]
    except KeyError as exc:
        raise WorkbenchOwnerError("IMPORT_HEADER_UNKNOWN", 422) from exc
    if len(set(columns)) != len(columns) or "name" not in columns:
        raise WorkbenchOwnerError("IMPORT_HEADERS_INVALID", 422)
    result = []
    for row in rows[1:]:
        if len(row) > len(columns):
            result.append({"_error": "IMPORT_EXTRA_COLUMNS"})
            continue
        fields = dict(zip(columns, row + [""] * (len(columns) - len(row)), strict=True))
        try:
            content = json.loads(fields.pop("contentJson", "") or "{}")
            name = fields.pop("name")
            for field, value in fields.items():
                if value.strip():
                    content[field] = (
                        [
                            v.strip()
                            for v in value.replace("、", ",")
                            .replace("\uff0c", ",")
                            .split(",")
                            if v.strip()
                        ]
                        if field == "capabilities"
                        else value.strip()
                    )
            result.append(
                {
                    "manifestVersion": "skill-mcp-workbench/v1",
                    "kind": kind,
                    "name": name,
                    "content": content,
                }
            )
        except (ValueError, TypeError):
            result.append({"_error": "IMPORT_CONTENT_JSON_INVALID"})
    return result


def preview_manifests(manifests, kind, existing_names=()):
    from .resource_management import ResourceManagement

    if not isinstance(manifests, list) or not 1 <= len(manifests) <= MAX_ROWS:
        raise WorkbenchOwnerError("IMPORT_ROW_LIMIT", 422)
    seen = set()
    items = []
    normalized = []
    for index, manifest in enumerate(manifests, 1):
        errors = []
        warnings = []
        clean = None
        try:
            if not isinstance(manifest, dict) or manifest.get("_error"):
                raise WorkbenchOwnerError(
                    manifest.get("_error", "IMPORT_MANIFEST_INVALID")
                    if isinstance(manifest, dict)
                    else "IMPORT_MANIFEST_INVALID",
                    422,
                )
            if (
                set(manifest)
                - {
                    "manifestVersion",
                    "kind",
                    "name",
                    "content",
                    "sourceRevisionId",
                    "sourceDigest",
                    "credentialMaterial",
                }
                or manifest.get("manifestVersion") != "skill-mcp-workbench/v1"
                or manifest.get("kind") != kind
                or manifest.get("credentialMaterial", "NOT_INCLUDED") != "NOT_INCLUDED"
            ):
                raise WorkbenchOwnerError("MANIFEST_BOUNDARY_INVALID", 422)
            name = manifest.get("name")
            if not isinstance(name, str) or not name.strip() or len(name) > 120:
                raise WorkbenchOwnerError("MANIFEST_NAME_INVALID", 422)
            name = name.strip()
            if name.casefold() in seen:
                raise WorkbenchOwnerError("IMPORT_DUPLICATE_NAME", 422)
            seen.add(name.casefold())
            content = ResourceContent.model_validate(
                manifest.get("content")
            ).model_dump(exclude_unset=True)
            ResourceManagement.safe_content(kind, content)
            from .skill_mcp_service import SkillMcpService

            SkillMcpService._content(kind, content)
            if name.casefold() in {x.casefold() for x in existing_names}:
                warnings.append("EXISTING_NAME_NEW_DRAFT_ONLY")
            clean = {
                "manifestVersion": "skill-mcp-workbench/v1",
                "kind": kind,
                "name": name,
                "content": content,
            }
            normalized.append(clean)
        except (
            WorkbenchOwnerError,
            SkillMcpFailure,
            ValidationError,
            ValueError,
            TypeError,
            AttributeError,
        ) as exc:
            errors.append(
                getattr(
                    exc, "reason_code", getattr(exc, "reason", "IMPORT_CONTENT_INVALID")
                )
            )
        items.append(
            {
                "row": index,
                "name": str(manifest.get("name", ""))[:120]
                if isinstance(manifest, dict)
                else "",
                "valid": not errors,
                "errors": errors,
                "warnings": warnings,
                "manifest": clean,
            }
        )
    if len(json.dumps(normalized, ensure_ascii=False).encode()) > 100000:
        raise WorkbenchOwnerError("IMPORT_NORMALIZED_SIZE_LIMIT", 422)
    ready = all(i["valid"] for i in items)
    return {
        "schemaVersion": "resource-import-preview.v1",
        "kind": kind,
        "rows": items,
        "validRows": sum(i["valid"] for i in items),
        "invalidRows": sum(not i["valid"] for i in items),
        "ready": ready,
        "manifests": normalized if ready else [],
        "previewDigest": canonical_digest([kind, normalized]) if ready else None,
        "executionStarted": False,
        "credentialMaterial": "NOT_INCLUDED",
    }
