import io
import zipfile
from xml.sax.saxutils import escape

import pytest
from agent_console.resource_import import decode_file, preview_manifests
from agent_console.workbench_owner_authorization import WorkbenchOwnerError


def xlsx(rows, *, formula=False, external=False):
    values = []
    for index, row in enumerate(rows, 1):
        cells = "".join(
            f'<c r="{chr(65 + col)}{index}" t="inlineStr"><is><t>'
            f"{escape(value)}</t></is>"
            + ("<f>1+1</f>" if formula and index == 2 and col == 0 else "")
            + "</c>"
            for col, value in enumerate(row)
        )
        values.append(f'<row r="{index}">{cells}</row>')
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships"><sheets>'
            '<sheet name="资源" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/'
            'package/2006/relationships"><Relationship Id="rId1" '
            'Target="/xl/worksheets/sheet1.xml"'
            + (' TargetMode="External"' if external else "")
            + "/></Relationships>",
        )
        z.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
            + "".join(values)
            + "</sheetData></worksheet>",
        )
    return output.getvalue()


def test_csv_and_xlsx_normalize_to_same_exact_manifests_and_preserve_explicit_errors():
    rows = [
        ["名称", "业务用途", "能力", "说明"],
        ["销售分析", "按币种核对", "READ_DATA", "只读"],
        ["供应商交付", "按单位核对", "SUMMARIZE", "只读"],
    ]
    import csv

    stream = io.StringIO()
    csv.writer(stream).writerows(rows)
    csv_result = preview_manifests(
        decode_file("资源.csv", stream.getvalue().encode("utf-8-sig"), "skill"), "skill"
    )
    xlsx_result = preview_manifests(
        decode_file("资源.xlsx", xlsx(rows), "skill"), "skill"
    )
    assert csv_result["ready"] and csv_result["validRows"] == 2
    assert csv_result["previewDigest"] == xlsx_result["previewDigest"]
    manifest = csv_result["manifests"][0]
    bad = preview_manifests(
        [
            manifest,
            {**manifest, "name": "不同名称", "content": {"description": "missing"}},
        ],
        "skill",
    )
    assert (
        bad["validRows"] == 1
        and bad["invalidRows"] == 1
        and not bad["ready"]
        and bad["manifests"] == []
    )
    assert preview_manifests([manifest, manifest], "skill")["rows"][1]["errors"] == [
        "IMPORT_DUPLICATE_NAME"
    ]
    modified = preview_manifests([{**manifest, "name": "变更"}], "skill")
    assert (
        modified["previewDigest"]
        != preview_manifests([manifest], "skill")["previewDigest"]
    )


@pytest.mark.parametrize(
    "options,reason",
    [
        ({"formula": True}, "IMPORT_FORMULA_DENIED"),
        ({"external": True}, "IMPORT_EXTERNAL_LINK_DENIED"),
    ],
)
def test_xlsx_formula_or_external_link_never_reaches_resource_owner(options, reason):
    with pytest.raises(WorkbenchOwnerError, match=reason):
        decode_file("test.xlsx", xlsx([["名称"], ["x"]], **options), "skill")


def test_bad_archive_unknown_header_secret_and_too_many_rows_are_rejected():
    with pytest.raises(WorkbenchOwnerError):
        decode_file("bad.xlsx", b"not a zip", "skill")
    with pytest.raises(WorkbenchOwnerError, match="HEADER_UNKNOWN"):
        decode_file("bad.csv", "名称,未声明字段\na,b".encode(), "skill")
    with pytest.raises(WorkbenchOwnerError, match="ROW_LIMIT"):
        preview_manifests([{}] * 101, "skill")
    result = preview_manifests(
        [
            {
                "manifestVersion": "skill-mcp-workbench/v1",
                "kind": "skill",
                "name": "secret",
                "content": {
                    "description": "x",
                    "capabilities": ["READ_DATA"],
                    "instructions": "x",
                    "inputSchema": {"password": "do-not-store"},
                },
            }
        ],
        "skill",
    )
    assert (
        result["rows"][0]["errors"] == ["RESOURCE_INLINE_SECRET_DENIED"]
        and result["manifests"] == []
    )
    with pytest.raises(WorkbenchOwnerError):
        decode_file("bad.json", b"{", "skill")
