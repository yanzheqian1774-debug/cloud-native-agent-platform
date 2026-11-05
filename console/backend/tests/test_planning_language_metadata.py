# ruff: noqa: RUF001 -- Preserve punctuation in the actual bounded business fields.
"""Reproduce the two observed false positives without relaxing English checks."""

from agent_console.planning_language import issues

DIGEST = "d34d4fa82a2f43350c0939d3eb078eeadbe5b24070cc28e52c30ed76aaf993a8"


def test_exact_source_commitment_and_digest_are_not_english_business_prose():
    doc = {
        "semantics": {
            "boundaries": [
                "隔离合成来源：knowledge:8b33cda4-ea9f-44fe-888a-6fc98348e682；"
                "修订：knowledge-revision:09cac439-215c-4373-8dde-c445ca5e1e14；SHA256："
                + DIGEST,
            ],
            "requirements": [
                {"preparation": "核对SHA256：" + DIGEST + "与修订号后再读取"}
            ],
        }
    }
    assert issues(doc) == []


def test_hashes_and_uuids_cannot_hide_english_instructions():
    doc = {
        "semantics": {
            "boundaries": [
                "中 Collect billing records and report all missing data "
                + DIGEST
                + " 8b33cda4-ea9f-44fe-888a-6fc98348e682",
            ]
        }
    }
    assert issues(doc)[0]["path"] == ["semantics", "boundaries", 0]
