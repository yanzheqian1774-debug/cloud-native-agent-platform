"""Bounded F3 import preview. Parsing never grants execution or publishes tools."""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from urllib.parse import urlsplit

MAX_BYTES = 100_000
MAX_OPERATIONS = 20
METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


class ToolImportError(ValueError):
    pass


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ToolImportError("DUPLICATE_JSON_KEY")
        value[key] = item
    return value


def _depth(value, depth=0):
    if isinstance(value, float) and not math.isfinite(value):
        raise ToolImportError("NON_FINITE_JSON_NUMBER")
    if depth > 40:
        raise ToolImportError("IMPORT_NESTING_LIMIT")
    if isinstance(value, dict):
        for child in value.values():
            _depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _depth(child, depth + 1)


def _contains_ref(value):
    if isinstance(value, dict):
        return "$ref" in value or any(_contains_ref(v) for v in value.values())
    return isinstance(value, list) and any(_contains_ref(v) for v in value)


def _source(url):
    if not isinstance(url, str) or not url:
        return "", ["SERVER_URL_REQUIRED"]
    try:
        parsed = urlsplit(url)
        _ = parsed.port
    except ValueError as exc:
        raise ToolImportError("SERVER_URL_INVALID") from exc
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ToolImportError("CREDENTIAL_OR_QUERY_IN_SERVER_URL")
    issues = []
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        issues.append("ABSOLUTE_HTTP_SERVER_REQUIRED")
    if "{" in url or "}" in url:
        issues.append("SERVER_VARIABLES_UNSUPPORTED")
    return url, issues


def _api(document):
    if not str(document.get("openapi", "")).startswith("3.") or not isinstance(
        document.get("paths"), dict
    ):
        raise ToolImportError("OPENAPI_3_JSON_REQUIRED")
    operations = []
    for path, path_item in document["paths"].items():
        if not isinstance(path_item, dict) or not path.startswith("/"):
            raise ToolImportError("OPENAPI_PATH_INVALID")
        if "$ref" in path_item:
            raise ToolImportError("PATH_REFERENCE_UNSUPPORTED")
        for method, operation in path_item.items():
            if method not in METHODS:
                continue
            if not isinstance(operation, dict):
                raise ToolImportError("OPENAPI_OPERATION_INVALID")
            issues = []
            servers = operation.get(
                "servers", path_item.get("servers", document.get("servers", []))
            )
            if not isinstance(servers, list) or any(
                not isinstance(s, dict) for s in servers
            ):
                raise ToolImportError("SERVER_LIST_INVALID")
            source, source_issues = _source(servers[0].get("url") if servers else None)
            issues.extend(source_issues)
            if len(servers) > 1:
                issues.append("MULTIPLE_SERVERS_REQUIRE_SELECTION")
            if operation.get("security", document.get("security")):
                issues.append("SECURITY_ADAPTER_REQUIRED")
            if "requestBody" in operation:
                issues.append("REQUEST_BODY_ADAPTER_REQUIRED")
            if operation.get("callbacks"):
                issues.append("CALLBACK_ADAPTER_REQUIRED")
            if _contains_ref(operation) or _contains_ref(
                path_item.get("parameters", [])
            ):
                issues.append("REFERENCE_ADAPTER_REQUIRED")
            params = path_item.get("parameters", [])
            local_params = operation.get("parameters", [])
            if not isinstance(params, list) or not isinstance(local_params, list):
                raise ToolImportError("PARAMETERS_INVALID")
            properties, required, seen = {}, [], set()
            for param in [*params, *local_params]:
                if not isinstance(param, dict):
                    raise ToolImportError("PARAMETER_INVALID")
                name = param.get("name")
                if not isinstance(name, str) or not name.strip():
                    issues.append("PARAMETER_NAME_REQUIRED")
                    continue
                if name in seen:
                    issues.append("PARAMETER_OVERRIDE_REQUIRES_REVIEW")
                    continue
                seen.add(name.rstrip("/"))
                if param.get("in") != "query":
                    issues.append("NON_QUERY_PARAMETER_ADAPTER_REQUIRED")
                schema = param.get("schema")
                if not isinstance(schema, dict):
                    issues.append("PARAMETER_SCHEMA_REQUIRED")
                    schema = {}
                if schema.get("type") not in {"string", "number", "integer", "boolean"}:
                    issues.append("COMPLEX_PARAMETER_ADAPTER_REQUIRED")
                if any(
                    key in param
                    for key in ("content", "style", "explode", "allowReserved")
                ):
                    issues.append("PARAMETER_ENCODING_REVIEW_REQUIRED")
                properties[name] = deepcopy(schema)
                if param.get("required") is True:
                    required.append(name)
            responses = operation.get("responses", {})
            if not isinstance(responses, dict):
                raise ToolImportError("RESPONSES_INVALID")
            response = responses.get("200", {})
            if not isinstance(response, dict):
                raise ToolImportError("RESPONSE_INVALID")
            content = response.get("content", {})
            if not isinstance(content, dict):
                raise ToolImportError("RESPONSE_CONTENT_INVALID")
            media = content.get("application/json", {})
            if not isinstance(media, dict):
                raise ToolImportError("RESPONSE_MEDIA_INVALID")
            output = media.get("schema")
            if not isinstance(output, dict):
                issues.append("JSON_200_OUTPUT_SCHEMA_REQUIRED")
                output = None
            if set(responses) - {"200"}:
                issues.append("ADDITIONAL_RESPONSE_MAPPING_REQUIRED")
            if set(content) - {"application/json"}:
                issues.append("ADDITIONAL_MEDIA_MAPPING_REQUIRED")
            name = operation.get("operationId") or method + " " + path
            if not isinstance(name, str) or not name.strip():
                raise ToolImportError("OPERATION_NAME_INVALID")
            operations.append(
                {
                    "name": name,
                    "description": operation.get("summary")
                    or operation.get("description")
                    or "",
                    "inputSchema": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                    "outputSchema": deepcopy(output),
                    "sideEffect": "UNCONFIRMED",
                    "source": {
                        "kind": "API",
                        "server": source,
                        "path": path,
                        "method": method.upper(),
                    },
                    "blockingIssues": sorted(set(issues)),
                    "original": deepcopy(operation),
                }
            )
    return operations


def _plugin(document):
    if (
        document.get("format") != "t-manufacturing-tool-plugin/v1"
        or not all(
            isinstance(document.get(k), str) and document[k].strip()
            for k in ("id", "version", "runtime", "entrypoint")
        )
        or not isinstance(document.get("tools"), list)
    ):
        raise ToolImportError("PLATFORM_PLUGIN_MANIFEST_REQUIRED")
    entry = document["entrypoint"]
    if (
        entry.startswith(("/", "\\"))
        or "\\" in entry
        or any(p in {"", ".", ".."} for p in entry.split("/"))
    ):
        raise ToolImportError("PLUGIN_ENTRYPOINT_PATH_INVALID")
    permissions = document.get("permissions", [])
    if not isinstance(permissions, list) or any(
        not isinstance(p, str) or not p.strip() for p in permissions
    ):
        raise ToolImportError("PLUGIN_PERMISSIONS_INVALID")
    operations = []
    for tool in document["tools"]:
        if (
            not isinstance(tool, dict)
            or not isinstance(tool.get("name"), str)
            or not tool["name"].strip()
        ):
            raise ToolImportError("PLUGIN_TOOL_INVALID")
        issues = ["PLUGIN_PACKAGE_VALIDATION_REQUIRED"]
        if (
            not isinstance(tool.get("inputSchema"), dict)
            or tool["inputSchema"].get("type") != "object"
        ):
            issues.append("OBJECT_INPUT_SCHEMA_REQUIRED")
        if not isinstance(tool.get("outputSchema"), dict):
            issues.append("OUTPUT_SCHEMA_REQUIRED")
        if _contains_ref(tool):
            issues.append("REFERENCE_ADAPTER_REQUIRED")
        effect = tool.get("sideEffect", "UNCONFIRMED")
        if effect not in {"read-only", "creates-file", "external-write"}:
            effect = "UNCONFIRMED"
        operations.append(
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "inputSchema": deepcopy(tool.get("inputSchema")),
                "outputSchema": deepcopy(tool.get("outputSchema")),
                "sideEffect": effect,
                "source": {
                    "kind": "PLUGIN",
                    "id": document["id"],
                    "version": document["version"],
                    "runtime": document["runtime"],
                    "entrypoint": entry,
                    "permissions": deepcopy(permissions),
                },
                "blockingIssues": issues,
                "original": deepcopy(tool),
            }
        )
    return operations


def preview_import(kind: str, payload: bytes):
    if len(payload) > MAX_BYTES:
        raise ToolImportError("IMPORT_SIZE_LIMIT")
    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ToolImportError("NON_FINITE_JSON_NUMBER")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ToolImportError("IMPORT_JSON_INVALID") from exc
    if not isinstance(document, dict):
        raise ToolImportError("IMPORT_OBJECT_REQUIRED")
    _depth(document)
    if kind not in {"API", "PLUGIN"}:
        raise ToolImportError("IMPORT_KIND_UNSUPPORTED")
    operations = _api(document) if kind == "API" else _plugin(document)
    if not 1 <= len(operations) <= MAX_OPERATIONS:
        raise ToolImportError("IMPORT_OPERATION_COUNT_LIMIT")
    if len({t["name"] for t in operations}) != len(operations):
        raise ToolImportError("DUPLICATE_OPERATION_NAME")
    return {
        "sourceDigest": hashlib.sha256(payload).hexdigest(),
        "sourceKind": kind,
        "operations": operations,
        "sourceDocument": document,
        "persisted": False,
        "executionAuthority": "NONE",
        "networkRequests": 0,
    }


def preview_plugin_zip(payload: bytes):
    """Inspect a bounded package without extracting, importing or executing it."""
    import io
    import stat
    import zipfile

    if len(payload) > MAX_BYTES:
        raise ToolImportError("IMPORT_SIZE_LIMIT")
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            if len(entries) > 20 or sum(i.file_size for i in entries) > MAX_BYTES:
                raise ToolImportError("PLUGIN_ARCHIVE_LIMIT")
            files = {}
            seen = set()
            for item in entries:
                name = item.filename
                parts = name.rstrip("/").split("/")
                if (
                    name.startswith("/")
                    or "\\" in name
                    or ":" in name
                    or any(p in {"", ".", ".."} for p in parts)
                    or name.rstrip("/") in seen
                    or item.orig_filename != name
                    or item.flag_bits & 1
                    or stat.S_ISLNK(item.external_attr >> 16)
                ):
                    raise ToolImportError("PLUGIN_ARCHIVE_ENTRY_INVALID")
                seen.add(name.rstrip("/"))
                if item.is_dir():
                    continue
                content = archive.read(item)
                if len(content) != item.file_size:
                    raise ToolImportError("PLUGIN_ARCHIVE_SIZE_MISMATCH")
                files[name] = content
            if any(
                "/".join(name.split("/")[:i]) in files
                for name in files
                for i in range(1, len(name.split("/")))
            ):
                raise ToolImportError("PLUGIN_ARCHIVE_PATH_COLLISION")
            if "manifest.json" not in files:
                raise ToolImportError("PLUGIN_MANIFEST_MISSING")
            preview = preview_import("PLUGIN", files["manifest.json"])
            entrypoint = preview["sourceDocument"]["entrypoint"]
            if entrypoint not in files:
                raise ToolImportError("PLUGIN_ENTRYPOINT_MISSING")
            for tool in preview["operations"]:
                tool["blockingIssues"] = [
                    "PLUGIN_RUNTIME_VALIDATION_REQUIRED"
                    if issue == "PLUGIN_PACKAGE_VALIDATION_REQUIRED"
                    else issue
                    for issue in tool["blockingIssues"]
                ]
            preview["manifestDigest"] = preview["sourceDigest"]
            preview["sourceDigest"] = hashlib.sha256(payload).hexdigest()
            preview["files"] = [
                {
                    "path": name,
                    "bytes": len(content),
                    "digest": hashlib.sha256(content).hexdigest(),
                }
                for name, content in sorted(files.items())
            ]
            return preview
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as exc:
        raise ToolImportError("PLUGIN_ARCHIVE_INVALID") from exc
