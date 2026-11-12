import io
import json
import stat
import zipfile

import pytest
from agent_console.tool_import import (
    ToolImportError,
    preview_import,
    preview_plugin_zip,
)


def api():
    return {
        "openapi": "3.0.3",
        "servers": [{"url": "https://example.invalid"}],
        "paths": {
            "/orders": {
                "get": {
                    "operationId": "orders",
                    "parameters": [
                        {
                            "name": "region",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            }
                        }
                    },
                }
            }
        },
    }


def plugin():
    return {
        "format": "t-manufacturing-tool-plugin/v1",
        "id": "test",
        "version": "1",
        "runtime": "python",
        "entrypoint": "src/main.py",
        "tools": [
            {
                "name": "convert",
                "inputSchema": {"type": "object"},
                "outputSchema": {"type": "object"},
                "sideEffect": "read-only",
            }
        ],
    }


def preview(value, kind="API"):
    return preview_import(kind, json.dumps(value).encode())


def test_api_preview_preserves_source_and_requires_no_execution():
    source = api()
    result = preview(source)
    tool = result["operations"][0]
    assert tool["inputSchema"]["required"] == ["region"]
    assert tool["sideEffect"] == "UNCONFIRMED"
    assert (
        result["sourceDocument"] == source
        and tool["original"] == source["paths"]["/orders"]["get"]
    )
    assert (
        result["networkRequests"] == 0
        and result["executionAuthority"] == "NONE"
        and not result["persisted"]
    )


def test_unsupported_semantics_are_reported_and_original_not_lost():
    source = api()
    operation = source["paths"]["/orders"]["get"]
    source["security"] = [{"oauth": ["read"]}]
    operation["requestBody"] = {"$ref": "#/components/requestBodies/input"}
    operation["parameters"].append(
        {"name": "id", "in": "path", "schema": {"type": "array"}}
    )
    operation["responses"]["404"] = {"description": "missing"}
    result = preview(source)
    issues = result["operations"][0]["blockingIssues"]
    assert {
        "SECURITY_ADAPTER_REQUIRED",
        "REQUEST_BODY_ADAPTER_REQUIRED",
        "REFERENCE_ADAPTER_REQUIRED",
        "NON_QUERY_PARAMETER_ADAPTER_REQUIRED",
        "COMPLEX_PARAMETER_ADAPTER_REQUIRED",
        "ADDITIONAL_RESPONSE_MAPPING_REQUIRED",
    } <= set(issues)
    assert result["sourceDocument"] == source


@pytest.mark.parametrize(
    "payload",
    [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b"[]", b"x", b"x" * 100001],
)
def test_invalid_and_oversized_json_never_produces_candidates(payload):
    with pytest.raises(ToolImportError):
        preview_import("API", payload)


def test_duplicate_operations_and_explicit_override_not_silently_merged():
    source = api()
    source["paths"]["/copy"] = source["paths"]["/orders"]
    with pytest.raises(ToolImportError, match="DUPLICATE_OPERATION_NAME"):
        preview(source)
    source = api()
    source["paths"]["/orders"]["parameters"] = [
        {"name": "region", "in": "query", "schema": {"type": "integer"}}
    ]
    assert (
        "PARAMETER_OVERRIDE_REQUIRES_REVIEW"
        in preview(source)["operations"][0]["blockingIssues"]
    )


def archive(extra=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(plugin()))
        z.writestr("src/main.py", "raise RuntimeError('must never execute')")
        if extra:
            extra(z)
    return buffer.getvalue()


def test_plugin_package_is_inspected_without_executing_code_or_publishing():
    result = preview_plugin_zip(archive())
    assert [f["path"] for f in result["files"]] == ["manifest.json", "src/main.py"]
    assert result["operations"][0]["blockingIssues"] == [
        "PLUGIN_RUNTIME_VALIDATION_REQUIRED"
    ]
    assert (
        result["sourceDigest"] != result["manifestDigest"]
        and result["executionAuthority"] == "NONE"
    )


@pytest.mark.parametrize("path", ["../escape", "/absolute", "C:/path", "a\\b"])
def test_package_paths_cannot_escape(path):
    with pytest.raises(ToolImportError, match="PLUGIN_ARCHIVE_ENTRY_INVALID"):
        preview_plugin_zip(archive(lambda z: z.writestr(path, "bad")))


def test_symlink_and_expansion_are_rejected():
    link = zipfile.ZipInfo("link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with pytest.raises(ToolImportError, match="PLUGIN_ARCHIVE_ENTRY_INVALID"):
        preview_plugin_zip(archive(lambda z: z.writestr(link, "/tmp/target")))
    with pytest.raises(ToolImportError, match="PLUGIN_ARCHIVE_LIMIT"):
        preview_plugin_zip(archive(lambda z: z.writestr("large.txt", "x" * 100001)))


def test_plugin_requires_existing_entrypoint_and_does_not_accept_third_party_manifest():
    with pytest.raises(ToolImportError):
        preview({"name": "third-party"}, "PLUGIN")
    value = plugin()
    value["entrypoint"] = "../main.py"
    with pytest.raises(ToolImportError, match="PLUGIN_ENTRYPOINT_PATH_INVALID"):
        preview(value, "PLUGIN")


def test_missing_entrypoint_and_file_directory_collision():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("manifest.json", json.dumps(plugin()))
    with pytest.raises(ToolImportError, match="PLUGIN_ENTRYPOINT_MISSING"):
        preview_plugin_zip(buffer.getvalue())
    with pytest.raises(ToolImportError, match="PLUGIN_ARCHIVE_PATH_COLLISION"):
        preview_plugin_zip(archive(lambda z: z.writestr("src", "conflict")))


@pytest.mark.parametrize(
    "url",
    [
        "http://user:password@example.invalid",
        "http://[bad",
        "https://example.invalid?token=secret",
    ],
)
def test_server_credentials_or_invalid_authority_are_not_imported(url):
    value = api()
    value["servers"][0]["url"] = url
    with pytest.raises(ToolImportError):
        preview(value)
