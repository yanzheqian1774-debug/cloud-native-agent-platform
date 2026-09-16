from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[3]


def test_320_workflow_builds_required_modes_and_runs_exact_assets() -> None:
    workflow = (
        REPOSITORY_ROOT
        / ".github"
        / "workflows"
        / "s5-v023-impl-320-kimi-mock-provider.yml"
    ).read_text()
    assert "VITE_SUPPLIER_QUALITY_DEMO_MODE: live" in workflow
    assert "VITE_PROBLEM_DRAFT_ASSISTANCE: enabled" in workflow
    assert "bash scripts/acceptance/s5_v023_impl_320_kimi_mock_provider.sh" in workflow
    assert "test_kimi_responses_draft_adapter.py" in workflow
    assert "test_openai_responses_draft_adapter.py" in workflow


def test_320_playwright_cleanup_and_evidence_are_fail_closed() -> None:
    default_config = (
        REPOSITORY_ROOT / "console" / "frontend" / "playwright.config.ts"
    ).read_text()
    config = (
        REPOSITORY_ROOT / "console" / "frontend" / "playwright.s5-320.config.ts"
    ).read_text()
    runner = (
        REPOSITORY_ROOT
        / "scripts"
        / "acceptance"
        / "s5_v023_impl_320_kimi_mock_provider.sh"
    ).read_text()
    cleanup = (
        REPOSITORY_ROOT / "scripts" / "acceptance" / "s5_v023_impl_320_owned_cleanup.sh"
    ).read_text()
    assert '"**/s5-320-kimi-draft-assistance.real.spec.ts"' in default_config
    assert 'testMatch: "s5-320-kimi-draft-assistance.real.spec.ts"' in config
    assert 'for marker in ("新建对话", "AI 问题理解与草稿辅助")' in runner
    assert "dispatch_count <= reservation_count <= 10" in runner
    assert "TEST_ONLY_SYNTHETIC_USD_QUOTE / NOT_KIMI_PRICE" in runner
    assert 'exit "$browser_status"' in runner
    assert "local exit_code=$?" in cleanup
    assert "local status" not in cleanup
